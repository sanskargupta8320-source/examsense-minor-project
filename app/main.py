import os
import io
import re
import time
import json
import uuid
import logging
from collections import defaultdict
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, Depends, UploadFile, File, Form, HTTPException, Query, Request, BackgroundTasks
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import desc, or_

from app.database import engine, SessionLocal, Base, get_db, migrate_db
from app.models import (
    Subject,
    Paper,
    Question,
    Topic,
    RepeatedQuestionGroup,
    SuggestedQuestion,
    NoteCache,
    QuizCache,
)
from app.services.pdf_service import (
    extract_text_from_file,
    sanitize_filename,
    split_pdf_into_batches,
    MAX_UPLOAD_SIZE_MB,
)
from app.services.ai_service import (
    extract_questions_from_paper,
    normalize_topics_with_llm,
    generate_revision_notes,
    generate_practice_quiz,
    guess_subject_from_text,
    detect_document_type,
    generate_syllabus_from_subject_name,
    generate_important_questions_from_notes,
    generate_answer_outline,
    get_topic_deep_dive,
    generate_model_answers,
    get_ai_status,
    run_startup_ai_check,
    set_request_gemini_key,
    AIUnavailableError,
    GEMINI_API_KEY,
)
from app.services.analysis_service import (
    find_repeated_questions,
    aggregate_topics_and_priorities,
)
from app.services.pdf_export_service import generate_study_plan_pdf
from app.services.demo_service import load_demo_data

# Initialize logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("examsense")

# Initialize database tables and run startup migrations
Base.metadata.create_all(bind=engine)
migrate_db()

# Startup: Lazy AI initialization (0 Gemini API calls to preserve daily quota)
try:
    run_startup_ai_check()
except Exception as _e:
    logger.warning(f"Startup AI check warning: {_e}")

# Setup directories
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "./uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# Rate Limiting (In-Memory sliding window per client IP)
# ---------------------------------------------------------------------------
class InMemoryRateLimiter:
    """Simple in-memory sliding-window rate limiter per client IP."""
    def __init__(self, max_requests: int, window_seconds: int = 3600):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.history = defaultdict(list)

    def is_allowed(self, client_ip: str) -> bool:
        now = time.time()
        valid_ts = [ts for ts in self.history[client_ip] if now - ts < self.window_seconds]
        self.history[client_ip] = valid_ts
        if len(valid_ts) >= self.max_requests:
            return False
        self.history[client_ip].append(now)
        return True

upload_limiter = InMemoryRateLimiter(max_requests=10, window_seconds=3600)  # max 10 uploads/hr
ai_limiter = InMemoryRateLimiter(max_requests=40, window_seconds=3600)      # max 40 AI notes/quiz/hr


def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "127.0.0.1"


def extract_year_from_filename_or_text(filename: str, text: str = "", default_year: int = 2023) -> int:
    """Finds a 4-digit exam year (2000-2035) in filename or text, otherwise defaults."""
    m = re.search(r"\b(20[0-3][0-9])\b", filename)
    if m:
        return int(m.group(1))
    if text:
        m = re.search(r"\b(20[0-3][0-9])\b", text[:1000])
        if m:
            return int(m.group(1))
    return default_year


def generate_subject_code() -> str:
    """Generates a clean auto-generated subject identifier like SUB-1A2B3C."""
    return f"SUB-{uuid.uuid4().hex[:6].upper()}"


# Initialize FastAPI App
app = FastAPI(
    title="ExamSense",
    description="Universal AI Exam Intelligence Platform for Students & Aspirants",
    version="1.2.0",
)

# Visitor tracking middleware
@app.middleware("http")
async def visitor_cookie_middleware(request: Request, call_next):
    # Support custom frontend Gemini API key from X-Gemini-Key header
    header_key = request.headers.get("x-gemini-key") or request.headers.get("X-Gemini-Key")
    set_request_gemini_key(header_key)

    vid = request.cookies.get("examsense_vid")
    new_cookie_needed = False
    if not vid:
        vid = f"vid_{uuid.uuid4().hex[:16]}"
        new_cookie_needed = True

    request.state.visitor_id = vid
    response = await call_next(request)

    if new_cookie_needed:
        response.set_cookie(
            key="examsense_vid",
            value=vid,
            max_age=31536000,  # 1 year
            httponly=True,
            samesite="lax",
            path="/",
        )
    return response


# Mount static and templates
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
static_dir = os.path.join(BASE_DIR, "static")
templates_dir = os.path.join(BASE_DIR, "templates")

os.makedirs(static_dir, exist_ok=True)
os.makedirs(templates_dir, exist_ok=True)

app.mount("/static", StaticFiles(directory=static_dir), name="static")
templates = Jinja2Templates(directory=templates_dir)


# ---------------------------------------------------------------------------
# UI Page Routes
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def serve_home(request: Request):
    """Serves the main single-page application dashboard."""
    return templates.TemplateResponse(request=request, name="index.html")


# ---------------------------------------------------------------------------
# Core API Routes
# ---------------------------------------------------------------------------

@app.get("/api/health")
def health_check(deep: Optional[str] = Query(None)):
    """
    Returns application status and active AI engine configurations.
    Lazy by default: reports immediately without calling Gemini to conserve free-tier quota.
    Only runs a real test when deep=1/true, caching the result for 10 minutes.
    """
    is_deep = str(deep).lower() in ["1", "true", "yes"] if deep is not None else False
    ai_status = get_ai_status(deep=is_deep)
    return {
        "status": "healthy",
        "gemini_api_configured": ai_status.get("gemini_api_configured", False),
        "gemini_working": ai_status.get("gemini_working", False),
        "model_in_use": ai_status.get("model_in_use"),
        "last_error": ai_status.get("last_error"),
        "quota_exhausted": ai_status.get("quota_exhausted", False),
        "quota_resets_in_seconds": ai_status.get("quota_resets_in_seconds", 0),
        "quota_message": ai_status.get("quota_message"),
        "ai_calls_today": ai_status.get("ai_calls_today", 0),
        "ai_daily_limit": ai_status.get("ai_daily_limit", 18),
        "app": "ExamSense v1.2",
        "tagline": "Kya padhna hai, ab AI batayega.",
        "ai_engine": ai_status,
        "max_upload_size_mb": MAX_UPLOAD_SIZE_MB,
    }


@app.get("/api/subjects")
def list_subjects(request: Request, db: Session = Depends(get_db)):
    """Lists analyzed subjects for current visitor (plus shared demo and legacy subjects)."""
    visitor_id = getattr(request.state, "visitor_id", None) or request.cookies.get("examsense_vid")

    subjects = db.query(Subject).filter(
        or_(
            Subject.owner_id == visitor_id,
            Subject.owner_id == None,
            Subject.owner_id == "demo",
            Subject.is_demo == True,
        )
    ).order_by(desc(Subject.created_at)).all()

    results = []
    for s in subjects:
        d = s.to_dict()
        can_delete = bool(
            visitor_id and s.owner_id == visitor_id and not s.is_demo and s.owner_id not in [None, "demo"]
        )
        d["can_delete"] = can_delete
        results.append(d)

    return results


@app.get("/api/subjects/{subject_id}/status")
def get_subject_status(subject_id: int, request: Request, db: Session = Depends(get_db)):
    """Polling endpoint for upload modal to track live background analysis progress."""
    subject = db.query(Subject).filter(Subject.id == subject_id).first()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found.")

    visitor_id = getattr(request.state, "visitor_id", None) or request.cookies.get("examsense_vid")
    if subject.owner_id and subject.owner_id not in [None, "demo", visitor_id] and not subject.is_demo:
        raise HTTPException(status_code=404, detail="Subject not found.")

    return {
        "id": subject.id,
        "name": subject.name,
        "code": subject.code,
        "status": subject.status or "ready",
        "progress_text": subject.progress_text or "Ready",
        "error_message": subject.error_message,
        "papers_count": len(subject.papers),
        "topics_count": len(subject.topics),
    }


@app.get("/api/subjects/{subject_id}")
def get_subject_dashboard(subject_id: int, request: Request, db: Session = Depends(get_db)):
    """Returns complete analytical dashboard data for a given subject."""
    subject = db.query(Subject).filter(Subject.id == subject_id).first()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found.")

    visitor_id = getattr(request.state, "visitor_id", None) or request.cookies.get("examsense_vid")
    is_accessible = (
        subject.owner_id is None
        or subject.owner_id in ["demo", visitor_id]
        or bool(subject.is_demo)
    )
    if not is_accessible:
        raise HTTPException(status_code=404, detail="Subject not found.")

    topics = db.query(Topic).filter(Topic.subject_id == subject_id).order_by(desc(Topic.priority_score)).all()
    papers = db.query(Paper).filter(Paper.subject_id == subject_id).order_by(Paper.year).all()
    repeated_groups = (
        db.query(RepeatedQuestionGroup)
        .filter(RepeatedQuestionGroup.subject_id == subject_id)
        .order_by(desc(RepeatedQuestionGroup.similarity_score))
        .all()
    )
    questions = db.query(Question).filter(Question.subject_id == subject_id).all()
    suggested_questions = (
        db.query(SuggestedQuestion)
        .filter(SuggestedQuestion.subject_id == subject_id)
        .order_by(desc(SuggestedQuestion.expected_marks))
        .all()
    )

    high_count = sum(1 for t in topics if t.priority_level == "High")
    med_count = sum(1 for t in topics if t.priority_level == "Medium")
    low_count = sum(1 for t in topics if t.priority_level == "Low")
    years_covered = sorted(list(set(p.year for p in papers if p.doc_type != "notes")))

    subject_dict = subject.to_dict()
    subject_dict["can_delete"] = bool(
        visitor_id and subject.owner_id == visitor_id and not subject.is_demo and subject.owner_id not in [None, "demo"]
    )

    ai_status = get_ai_status()

    return {
        "subject": subject_dict,
        "stats": {
            "total_papers": len(papers),
            "total_questions": len(questions),
            "total_topics": len(topics),
            "total_suggested_questions": len(suggested_questions),
            "high_priority_count": high_count,
            "medium_priority_count": med_count,
            "low_priority_count": low_count,
            "repeated_groups_count": len(repeated_groups),
            "years_covered": years_covered,
        },
        "ai_info": {
            "fallback_active": ai_status.get("ai_fallback_active", False),
            "working_model": ai_status.get("model_in_use"),
            "gemini_working": ai_status.get("gemini_working", False),
        },
        "papers": [p.to_dict() for p in papers],
        "topics": [t.to_dict() for t in topics],
        "repeated_groups": [rg.to_dict() for rg in repeated_groups],
        "suggested_questions": [sq.to_dict() for sq in suggested_questions],
    }


@app.delete("/api/subjects/{subject_id}")
def delete_subject(subject_id: int, request: Request, db: Session = Depends(get_db)):
    """Deletes a visitor's own subject. Sample and shared demo subjects are protected."""
    subject = db.query(Subject).filter(Subject.id == subject_id).first()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found.")

    visitor_id = getattr(request.state, "visitor_id", None) or request.cookies.get("examsense_vid")

    if subject.is_demo or subject.owner_id in [None, "demo"]:
        raise HTTPException(
            status_code=403,
            detail="Sample and shared demo subjects are read-only and cannot be deleted.",
        )

    if subject.owner_id != visitor_id:
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to delete this subject.",
        )

    name = subject.name
    db.delete(subject)
    db.commit()
    return {"message": f"Subject '{name}' deleted successfully."}


@app.post("/api/demo/load")
def load_demo(demo_type: str = Query("college"), db: Session = Depends(get_db)):
    """
    Populates or reuses a shared offline sample dataset.
    Supports:
    - 'college' (Database Management Systems CS-501)
    - 'school' (Class 10 Science SCI-10)
    - 'competitive' (General Science & Physics COMP-PHY)
    """
    try:
        subject = load_demo_data(db, demo_type=demo_type)
        return {
            "success": True,
            "subject_id": subject.id,
            "demo_type": demo_type,
            "message": f"Successfully loaded demo dataset for '{subject.name}' ({subject.code})!",
        }
    except Exception as e:
        logger.error(f"Error loading demo data: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to load demo data. Please try again.")


# ---------------------------------------------------------------------------
# Background Processing Task for Uploads
# ---------------------------------------------------------------------------

def process_subject_papers_background(
    subject_id: int,
    extracted_papers_info: List[Dict[str, Any]],
    clean_name: str,
    clean_exam_type: str,
):
    """Executes paper transcription, question extraction, topic clustering, and priorities in background."""
    db = SessionLocal()
    try:
        subject = db.query(Subject).filter(Subject.id == subject_id).first()
        if not subject:
            return

        subject.status = "processing"
        subject.progress_text = "Reading question papers & transcribing questions..."
        db.commit()

        db_papers = []
        all_raw_questions = []
        notes_topic_names = set()

        # 1. Process each file
        for idx, p_info in enumerate(extracted_papers_info):
            subject.progress_text = f"Extracting questions from {p_info['filename']} ({idx + 1} of {len(extracted_papers_info)})..."
            db.commit()

            doc_type = p_info.get("doc_type") or detect_document_type(p_info["filepath"], p_info["extracted_text"])

            paper_obj = Paper(
                subject_id=subject.id,
                year=p_info["year"],
                filename=p_info["filename"],
                filepath=p_info["filepath"],
                extracted_text=p_info["extracted_text"],
                is_ocr=p_info["is_ocr"],
                doc_type=doc_type,
                questions_found=0,
            )
            db.add(paper_obj)
            db.flush()
            db_papers.append(paper_obj)

            # If document is study notes, extract suggested questions
            if doc_type == "notes":
                subject.progress_text = f"Finding high-yield exam questions from notes: {p_info['filename']}..."
                db.commit()
                try:
                    notes_qs = generate_important_questions_from_notes(
                        notes_text=p_info["extracted_text"],
                        subject_name=clean_name,
                        exam_type=clean_exam_type,
                        file_path=p_info["filepath"],
                    )
                    paper_obj.questions_found = len(notes_qs)
                    for nq in notes_qs:
                        notes_topic_names.add(nq["topic"])
                        sq_obj = SuggestedQuestion(
                            subject_id=subject.id,
                            topic_name=nq["topic"],
                            question_text=nq["question_text"],
                            question_type=nq.get("question_type", "short answer"),
                            expected_marks=nq.get("expected_marks", 5),
                            why_important=nq.get("why_important"),
                            difficulty=nq.get("difficulty", "Medium"),
                            source="notes",
                        )
                        db.add(sq_obj)
                except Exception as n_err:
                    logger.warning(f"Notes question extraction warning: {n_err}")
                continue

            # Standard exam paper questions
            try:
                questions_data = extract_questions_from_paper(
                    paper_text=p_info["extracted_text"],
                    year=p_info["year"],
                    subject_name=clean_name,
                    exam_type=clean_exam_type,
                    file_path=p_info["filepath"],
                    db=db,
                )
            except Exception as q_err:
                logger.warning(f"Error extracting questions from {p_info['filename']}: {q_err}")
                questions_data = []

            paper_obj.questions_found = len(questions_data)
            if hasattr(questions_data, "doc_type") and questions_data.doc_type == "notes":
                paper_obj.doc_type = "notes"
            if hasattr(questions_data, "subject_guess") and questions_data.subject_guess:
                if subject.name in ["My Subject", "Auto-detect", ""]:
                    subject.name = questions_data.subject_guess

            for q_item in questions_data:
                q_obj = Question(
                    subject_id=subject.id,
                    paper_id=paper_obj.id,
                    year=p_info["year"],
                    question_text=q_item["question_text"],
                    marks=q_item.get("marks", 7),
                    unit_or_topic_guess=q_item.get("unit_or_topic_guess", "Core Principles"),
                )
                db.add(q_obj)
                db.flush()
                all_raw_questions.append({
                    "id": q_obj.id,
                    "year": q_obj.year,
                    "marks": q_obj.marks,
                    "unit_or_topic_guess": q_obj.unit_or_topic_guess,
                    "question_text": q_obj.question_text,
                    "db_obj": q_obj,
                })

        # 2. Topic Normalization across all questions
        subject.progress_text = "Clustering & normalizing syllabus topics..."
        db.commit()

        raw_topics = [q["unit_or_topic_guess"] for q in all_raw_questions]
        try:
            topic_mapping = normalize_topics_with_llm(raw_topics, subject_name=clean_name, exam_type=clean_exam_type)
        except Exception:
            topic_mapping = {t: t.title() for t in raw_topics}

        for q in all_raw_questions:
            norm_name = topic_mapping.get(q["unit_or_topic_guess"], q["unit_or_topic_guess"])
            q["unit_or_topic_guess"] = norm_name
            q["db_obj"].unit_or_topic_guess = norm_name

        # 3. Topic Aggregation & Priority Scoring
        subject.progress_text = "Calculating mathematical exam priority scores..."
        db.commit()

        exam_paper_years = [p.year for p in db_papers if p.doc_type != "notes"]
        aggregated_topics = aggregate_topics_and_priorities(
            questions=all_raw_questions,
            all_subject_years=exam_paper_years,
        )

        for t_data in aggregated_topics:
            t_name = t_data["name"]
            has_bonus = t_name in notes_topic_names
            topic_obj = Topic(
                subject_id=subject.id,
                name=t_name,
                frequency=t_data["frequency"],
                total_marks=t_data["total_marks"],
                years_asked=json.dumps(t_data["years_asked"]),
                last_year_asked=t_data["last_year_asked"],
                priority_score=t_data["priority_score"],
                priority_level=t_data["priority_level"],
                priority_breakdown=json.dumps(t_data["priority_breakdown"]),
                has_notes_source=has_bonus,
            )
            db.add(topic_obj)
            db.flush()

            for q in all_raw_questions:
                if q["unit_or_topic_guess"] == t_name:
                    q["db_obj"].topic_id = topic_obj.id

        # 4. Repeated Questions Detection (TF-IDF)
        subject.progress_text = "Scanning for repeated questions (TF-IDF)..."
        db.commit()

        try:
            repeated_groups = find_repeated_questions(all_raw_questions, similarity_threshold=0.55)
            for grp in repeated_groups:
                rep_obj = RepeatedQuestionGroup(
                    subject_id=subject.id,
                    canonical_question=grp["canonical_question"],
                    similarity_score=grp["similarity_score"],
                    years=json.dumps(grp["years"]),
                    question_ids=json.dumps(grp["question_ids"]),
                    questions_data=json.dumps(grp["questions"]),
                )
                db.add(rep_obj)
        except Exception as rep_err:
            logger.warning(f"Repeat question analysis warning: {rep_err}")

        # Mark ready
        subject.status = "ready"
        subject.progress_text = "Analysis complete!"
        db.commit()
    except Exception as e:
        logger.error(f"Background paper processing failed for subject {subject_id}: {e}", exc_info=True)
        try:
            subject = db.query(Subject).filter(Subject.id == subject_id).first()
            if subject:
                subject.status = "failed"
                subject.error_message = "We could not read this file. Try a clearer photo or a different PDF."
                subject.progress_text = "Processing failed."
                db.commit()
        except Exception:
            pass
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Upload Endpoints (Non-blocking with BackgroundTasks + Live Polling)
# ---------------------------------------------------------------------------

@app.post("/api/upload")
async def upload_and_process_papers(
    request: Request,
    background_tasks: BackgroundTasks,
    subject_name: Optional[str] = Form(None),
    subject_code: Optional[str] = Form(None),
    exam_type: Optional[str] = Form("General"),
    years: Optional[str] = Form(None),
    pasted_text: Optional[str] = Form(None),
    files: Optional[List[UploadFile]] = File(None),
    db: Session = Depends(get_db),
):
    """
    Accepts papers (PDF, JPG/PNG/WEBP) or pasted text, creates Subject, and runs analysis.
    Returns immediately with status='processing' so the client can display real-time progress.
    """
    client_ip = get_client_ip(request)
    if not upload_limiter.is_allowed(client_ip):
        raise HTTPException(
            status_code=429,
            detail="Upload limit reached (max 10 uploads per hour). Please wait a while before uploading more papers.",
        )

    visitor_id = getattr(request.state, "visitor_id", None) or request.cookies.get("examsense_vid") or "anonymous"

    valid_files = [f for f in (files or []) if f.filename and f.filename.strip()]
    has_files = len(valid_files) > 0
    has_pasted = bool(pasted_text and len(pasted_text.strip()) >= 20)

    if not has_files and not has_pasted:
        raise HTTPException(
            status_code=400,
            detail="Please select at least one question paper file (PDF or photo) or paste question paper text.",
        )

    year_list = []
    if years and years.strip():
        try:
            year_list = [int(y.strip()) for y in years.split(",") if y.strip().isdigit()]
        except Exception:
            year_list = []

    current_calendar_year = time.localtime().tm_year
    extracted_papers_info = []

    MAX_BYTES = MAX_UPLOAD_SIZE_MB * 1024 * 1024

    # 1. Stream & save files with early rejection
    if has_files:
        for idx, upload_file in enumerate(valid_files):
            filename = upload_file.filename
            ext = os.path.splitext(filename)[1].lower()
            if ext not in [".pdf", ".jpg", ".jpeg", ".png", ".webp"]:
                raise HTTPException(
                    status_code=400,
                    detail=f"File '{filename}' is not supported. Please upload PDF documents or JPG/PNG/WEBP photos.",
                )

            safe_name = sanitize_filename(filename)
            unique_prefix = uuid.uuid4().hex[:8]
            save_path = os.path.join(UPLOAD_DIR, f"{unique_prefix}_{safe_name}")

            total_read = 0
            try:
                with open(save_path, "wb") as f:
                    while chunk := await upload_file.read(1024 * 1024):  # 1MB streamed chunks
                        total_read += len(chunk)
                        if total_read > MAX_BYTES:
                            f.close()
                            if os.path.exists(save_path):
                                os.remove(save_path)
                            raise HTTPException(
                                status_code=400,
                                detail=f"File '{filename}' exceeds {MAX_UPLOAD_SIZE_MB} MB limit. Try splitting the PDF or compressing it at ilovepdf.com.",
                            )
                        f.write(chunk)

                # Check if PDF needs batch splitting (>15MB or >40 pages)
                split_batches = split_pdf_into_batches(save_path, max_pages_per_batch=15)

                for b_path in split_batches:
                    extracted_text, is_ocr, _ = extract_text_from_file(b_path)
                    
                    if idx < len(year_list):
                        paper_year = year_list[idx]
                    else:
                        paper_year = extract_year_from_filename_or_text(
                            filename=os.path.basename(b_path),
                            text=extracted_text,
                            default_year=current_calendar_year - idx,
                        )

                    doc_type = detect_document_type(b_path, extracted_text)

                    extracted_papers_info.append({
                        "filename": os.path.basename(b_path),
                        "filepath": b_path,
                        "extracted_text": extracted_text,
                        "is_ocr": is_ocr,
                        "year": paper_year,
                        "doc_type": doc_type,
                    })
            except HTTPException:
                raise
            except Exception as err:
                logger.error(f"Error handling file upload {filename}: {err}", exc_info=True)
                raise HTTPException(
                    status_code=500,
                    detail="We could not read this file. Try a clearer photo or a different PDF.",
                )

    # 2. Handle pasted text
    if has_pasted and not extracted_papers_info:
        p_text = pasted_text.strip()
        p_year = year_list[0] if year_list else extract_year_from_filename_or_text("", p_text, current_calendar_year)
        save_path = os.path.join(UPLOAD_DIR, f"pasted_{uuid.uuid4().hex[:8]}.txt")
        with open(save_path, "w", encoding="utf-8") as f:
            f.write(p_text)

        doc_type = detect_document_type("", p_text)
        extracted_papers_info.append({
            "filename": "Pasted_Question_Paper.txt",
            "filepath": save_path,
            "extracted_text": p_text,
            "is_ocr": False,
            "year": p_year,
            "doc_type": doc_type,
        })

    # Auto-detect subject name if empty
    sample_text = "\n\n".join(p["extracted_text"][:2000] for p in extracted_papers_info)
    clean_name = (subject_name or "").strip()
    if not clean_name:
        clean_name = guess_subject_from_text(sample_text)

    clean_code = (subject_code or "").strip().upper()
    if not clean_code:
        clean_code = generate_subject_code()

    clean_exam_type = (exam_type or "General").strip()

    # Create Subject in processing status
    subject = Subject(
        name=clean_name,
        code=clean_code,
        exam_type=clean_exam_type,
        owner_id=visitor_id,
        is_demo=False,
        source="papers",
        status="processing",
        progress_text="Starting analysis...",
    )
    db.add(subject)
    db.commit()
    db.refresh(subject)

    # Launch background task
    background_tasks.add_task(
        process_subject_papers_background,
        subject_id=subject.id,
        extracted_papers_info=extracted_papers_info,
        clean_name=clean_name,
        clean_exam_type=clean_exam_type,
    )

    return {
        "success": True,
        "subject_id": subject.id,
        "status": subject.status,
        "progress_text": subject.progress_text,
        "subject_name": subject.name,
        "subject_code": subject.code,
        "message": "Paper upload accepted. Analysis running.",
    }


# ---------------------------------------------------------------------------
# Phase 6: Start with Just a Subject Name (/api/subjects/from-topic)
# ---------------------------------------------------------------------------

@app.post("/api/subjects/from-topic")
@app.post("/api/subjects/from-name")
def create_subject_from_topic(
    request: Request,
    subject_name: str = Form(...),
    exam_level: Optional[str] = Form("General"),
    board_name: Optional[str] = Form(""),
    class_level: Optional[str] = Form(""),
    db: Session = Depends(get_db),
):
    """
    Creates an AI-estimated curriculum study plan based solely on subject name.
    Does not require question paper files. Tagged source='ai_estimate'.
    """
    clean_name = subject_name.strip()
    if not clean_name:
        raise HTTPException(status_code=400, detail="Subject name is required.")

    client_ip = get_client_ip(request)
    if not ai_limiter.is_allowed(client_ip):
        raise HTTPException(status_code=429, detail="AI request limit reached. Please wait a short while.")

    visitor_id = getattr(request.state, "visitor_id", None) or request.cookies.get("examsense_vid") or "anonymous"

    clean_level = (exam_level or "General").strip()
    clean_code = generate_subject_code()

    try:
        topics_data = generate_syllabus_from_subject_name(
            subject_name=clean_name,
            exam_level=clean_level,
            board_name=board_name or "",
            class_level=class_level or "",
        )
    except Exception as e:
        logger.warning(f"Using direct curriculum generator fallback for '{clean_name}': {e}")
        from app.services.ai_service import generate_builtin_curriculum
        topics_data = generate_builtin_curriculum(clean_name, clean_level, board_name or "", class_level or "")

    subject = Subject(
        name=clean_name,
        code=clean_code,
        exam_type=clean_level,
        owner_id=visitor_id,
        is_demo=False,
        source="ai_estimate",
        status="ready",
        progress_text="Ready",
    )
    db.add(subject)
    db.flush()

    for item in topics_data:
        t_name = item["topic_name"]
        importance = item.get("estimated_importance", 7)
        priority_level = "High" if importance >= 8 else ("Medium" if importance >= 5 else "Low")
        priority_score = float(importance * 10)

        breakdown = {
            "importance": importance,
            "formula": "Estimated by AI curriculum analysis based on standard syllabus weightage.",
            "disclaimer": "This plan is an AI estimate based on common exam patterns, not your actual papers.",
        }

        topic_obj = Topic(
            subject_id=subject.id,
            name=t_name,
            frequency=1,
            total_marks=item.get("typical_marks", 7),
            years_asked="[]",
            last_year_asked=time.localtime().tm_year,
            priority_score=priority_score,
            priority_level=priority_level,
            priority_breakdown=json.dumps(breakdown),
        )
        db.add(topic_obj)
        db.flush()

        for q_text in item.get("typical_questions", []):
            q_obj = Question(
                subject_id=subject.id,
                paper_id=None,
                year=time.localtime().tm_year,
                question_text=q_text,
                marks=item.get("typical_marks", 7),
                unit_or_topic_guess=t_name,
                topic_id=topic_obj.id,
            )
            db.add(q_obj)

    db.commit()

    return {
        "success": True,
        "subject_id": subject.id,
        "subject_name": subject.name,
        "subject_code": subject.code,
        "topics_count": len(topics_data),
        "source": "ai_estimate",
    }


# ---------------------------------------------------------------------------
# Phase 7: Add Notes to Existing Subject & Question Outline
# ---------------------------------------------------------------------------

@app.post("/api/subjects/{subject_id}/add-notes")
async def add_notes_to_subject(
    subject_id: int,
    request: Request,
    notes_file: Optional[UploadFile] = File(None),
    notes_text: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """Adds student revision notes to an existing subject and generates important questions."""
    subject = db.query(Subject).filter(Subject.id == subject_id).first()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found.")

    visitor_id = getattr(request.state, "visitor_id", None) or request.cookies.get("examsense_vid")
    if subject.owner_id and subject.owner_id != visitor_id and not subject.is_demo:
        raise HTTPException(status_code=403, detail="You do not have permission to edit this subject.")

    extracted_text = ""
    file_path = None

    if notes_file and notes_file.filename:
        safe_name = sanitize_filename(notes_file.filename)
        file_path = os.path.join(UPLOAD_DIR, f"notes_{uuid.uuid4().hex[:8]}_{safe_name}")
        content = await notes_file.read()
        with open(file_path, "wb") as f:
            f.write(content)
        extracted_text, _, _ = extract_text_from_file(file_path)
    elif notes_text and len(notes_text.strip()) > 20:
        extracted_text = notes_text.strip()
    else:
        raise HTTPException(status_code=400, detail="Please provide notes text or a document file.")

    try:
        suggested = generate_important_questions_from_notes(
            notes_text=extracted_text,
            subject_name=subject.name,
            exam_type=subject.exam_type or "General",
            file_path=file_path,
        )
    except AIUnavailableError as ai_err:
        raise HTTPException(status_code=503, detail=str(ai_err))
    except Exception as e:
        logger.error(f"Error analyzing notes: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Could not analyze notes. Please try again.")

    # Record paper as notes
    paper_obj = Paper(
        subject_id=subject.id,
        year=time.localtime().tm_year,
        filename=notes_file.filename if notes_file else "Pasted_Notes.txt",
        filepath=file_path or "",
        extracted_text=extracted_text,
        is_ocr=False,
        doc_type="notes",
        questions_found=len(suggested),
    )
    db.add(paper_obj)
    db.flush()

    # Link questions to existing topics or create new Topic
    existing_topics_map = {t.name.lower(): t for t in subject.topics}
    for item in suggested:
        t_name = item["topic"]
        matched_topic = existing_topics_map.get(t_name.lower())
        if matched_topic:
            # Grant +5 priority bonus
            matched_topic.has_notes_source = True
            matched_topic.priority_score = min(100.0, matched_topic.priority_score + 5.0)
            topic_id = matched_topic.id
        else:
            new_t = Topic(
                subject_id=subject.id,
                name=t_name,
                frequency=0,
                total_marks=item.get("expected_marks", 5),
                years_asked="[]",
                last_year_asked=time.localtime().tm_year,
                priority_score=50.0,
                priority_level="Medium",
                has_notes_source=True,
            )
            db.add(new_t)
            db.flush()
            existing_topics_map[t_name.lower()] = new_t
            topic_id = new_t.id

        sq_obj = SuggestedQuestion(
            subject_id=subject.id,
            topic_id=topic_id,
            topic_name=t_name,
            question_text=item["question_text"],
            question_type=item.get("question_type", "short answer"),
            expected_marks=item.get("expected_marks", 5),
            why_important=item.get("why_important"),
            difficulty=item.get("difficulty", "Medium"),
            source="notes",
        )
        db.add(sq_obj)

    db.commit()

    return {
        "success": True,
        "subject_id": subject.id,
        "suggested_questions_count": len(suggested),
        "message": f"Successfully extracted {len(suggested)} important exam questions from your notes!",
    }


@app.post("/api/suggested-questions/{question_id}/outline")
def get_question_answer_outline(question_id: int, db: Session = Depends(get_db)):
    """Fetches or generates on demand an answer outline for a suggested question."""
    q = db.query(SuggestedQuestion).filter(SuggestedQuestion.id == question_id).first()
    if not q:
        raise HTTPException(status_code=404, detail="Question not found.")

    if q.answer_outline and len(q.answer_outline.strip()) > 20:
        return {"question_id": q.id, "answer_outline": q.answer_outline}

    outline = generate_answer_outline(
        question_text=q.question_text,
        topic_name=q.topic_name,
        subject_name=q.subject.name,
    )
    q.answer_outline = outline
    db.commit()

    return {"question_id": q.id, "answer_outline": outline}


# ---------------------------------------------------------------------------
# Feature 6: Notes and Quiz Generator (Cached in Database)
# ---------------------------------------------------------------------------

@app.get("/api/topics/{topic_id}/notes")
def get_topic_notes(
    topic_id: int,
    request: Request,
    language: str = Query("en", pattern="^(en|hi)$"),
    db: Session = Depends(get_db),
):
    """Returns exam-oriented revision notes for a topic with caching and rate limiting."""
    topic = db.query(Topic).filter(Topic.id == topic_id).first()
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found.")

    cached = (
        db.query(NoteCache)
        .filter(NoteCache.topic_id == topic_id, NoteCache.language == language)
        .first()
    )
    if cached:
        return {
            "topic_id": topic.id,
            "topic_name": topic.name,
            "language": language,
            "cached": True,
            "notes": cached.content,
        }

    client_ip = get_client_ip(request)
    if not ai_limiter.is_allowed(client_ip):
        raise HTTPException(
            status_code=429,
            detail="AI study session limit reached (max 40 requests per hour). Please take a short break.",
        )

    sample_questions = [q.question_text for q in topic.questions[:4]]
    exam_type = topic.subject.exam_type or "General"

    try:
        notes_markdown = generate_revision_notes(
            topic_name=topic.name,
            subject_name=topic.subject.name,
            sample_questions=sample_questions,
            language=language,
            exam_type=exam_type,
        )
    except AIUnavailableError as ai_err:
        raise HTTPException(status_code=503, detail=str(ai_err))
    except Exception as e:
        logger.error(f"Error generating notes for topic {topic_id}: {e}", exc_info=True)
        notes_markdown = f"# 📝 Revision Notes: {topic.name}\n\nCore revision material for {topic.name}."

    new_cache = NoteCache(
        topic_id=topic.id,
        language=language,
        content=notes_markdown,
    )
    db.add(new_cache)
    db.commit()

    return {
        "topic_id": topic.id,
        "topic_name": topic.name,
        "language": language,
        "cached": False,
        "notes": notes_markdown,
    }


@app.get("/api/topics/{topic_id}/quiz")
def get_topic_quiz(
    topic_id: int,
    request: Request,
    count: int = Query(5, ge=3, le=10),
    difficulty: str = Query("medium", pattern="^(easy|medium|hard)$"),
    db: Session = Depends(get_db),
):
    """Generates or fetches MCQs with options, correct answer, and explanation."""
    topic = db.query(Topic).filter(Topic.id == topic_id).first()
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found.")

    cached = (
        db.query(QuizCache)
        .filter(QuizCache.topic_id == topic_id, QuizCache.difficulty == difficulty, QuizCache.question_count == count)
        .first()
    )
    if not cached:
        # Fallback to any cached quiz for topic if default count
        cached = db.query(QuizCache).filter(QuizCache.topic_id == topic_id).first()

    if cached:
        return {
            "topic_id": topic.id,
            "topic_name": topic.name,
            "cached": True,
            "quiz": cached.to_dict()["quiz"],
        }

    client_ip = get_client_ip(request)
    if not ai_limiter.is_allowed(client_ip):
        raise HTTPException(
            status_code=429,
            detail="AI study session limit reached (max 40 requests per hour). Please take a short break.",
        )

    sample_questions = [q.question_text for q in topic.questions[:3]]
    exam_type = topic.subject.exam_type or "General"

    try:
        quiz_data = generate_practice_quiz(
            topic_name=topic.name,
            subject_name=topic.subject.name,
            sample_questions=sample_questions,
            exam_type=exam_type,
            question_count=count,
            difficulty=difficulty,
        )
    except AIUnavailableError as ai_err:
        raise HTTPException(status_code=503, detail=str(ai_err))
    except Exception as e:
        logger.error(f"Error generating quiz for topic {topic_id}: {e}", exc_info=True)
        quiz_data = []

    new_cache = QuizCache(
        topic_id=topic.id,
        quiz_json=json.dumps(quiz_data),
        difficulty=difficulty,
        question_count=count,
    )
    db.add(new_cache)
    db.commit()

    return {
        "topic_id": topic.id,
        "topic_name": topic.name,
        "cached": False,
        "quiz": quiz_data,
    }


@app.get("/api/topics/{topic_id}/deep-dive")
def get_topic_deep_dive_api(
    topic_id: int,
    language: str = Query("en", pattern="^(en|hi)$"),
    db: Session = Depends(get_db),
):
    """Returns in-depth concept breakdown, formulas, examiner tips, and PYQs for Topic Drawer."""
    topic = db.query(Topic).filter(Topic.id == topic_id).first()
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found.")

    dive = get_topic_deep_dive(
        topic_name=topic.name,
        subject_name=topic.subject.name,
        language=language,
        exam_type=topic.subject.exam_type or "General",
    )
    questions_list = [q.to_dict() for q in topic.questions]
    key_formulas = dive.get("key_formulas", [])
    exam_tips = dive.get("exam_tips", [])
    return {
        "topic_id": topic.id,
        "topic_name": topic.name,
        "priority_level": topic.priority_level,
        "priority_score": round(topic.priority_score, 1),
        "total_marks": topic.total_marks,
        "frequency": topic.frequency,
        "years_asked": topic.get_years_list(),
        "detailed_explanation": dive.get("detailed_explanation", ""),
        "key_formulas": key_formulas,
        "key_formulas_or_points": key_formulas,
        "exam_tips": exam_tips,
        "important_exam_tips": exam_tips,
        "exam_answer_structure": dive.get("exam_answer_structure", {}),
        "questions": questions_list,
    }


@app.get("/api/subjects/{subject_id}/formulas")
def get_subject_formulas_api(
    subject_id: int,
    db: Session = Depends(get_db),
):
    """Returns all extracted formulas, laws, and equations for the Formula & Cheat-Sheet Wall."""
    subject = db.query(Subject).filter(Subject.id == subject_id).first()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found.")

    formulas_list = []
    for t in subject.topics:
        dive = get_topic_deep_dive(
            topic_name=t.name,
            subject_name=subject.name,
            language="en",
            exam_type=subject.exam_type or "General",
        )
        for f in dive.get("key_formulas", []):
            formulas_list.append({
                "topic_id": t.id,
                "topic_name": t.name,
                "priority_level": t.priority_level,
                "formula_text": f,
            })

    return {
        "subject_id": subject.id,
        "subject_name": subject.name,
        "total_formulas": len(formulas_list),
        "formulas": formulas_list,
    }


@app.post("/api/questions/{question_id}/solution")
def get_question_model_solution_api(
    question_id: int,
    language: str = Query("en", pattern="^(en|hi)$"),
    db: Session = Depends(get_db),
):
    """Generates a structured step-by-step model answer for an exam question."""
    q = db.query(Question).filter(Question.id == question_id).first()
    if not q:
        raise HTTPException(status_code=404, detail="Question not found.")

    sol = generate_model_answers(
        question_text=q.question_text,
        topic_name=q.unit_or_topic_guess,
        subject_name=q.subject.name,
        language=language,
    )
    formatted_answer = "\n".join(sol.get("step_by_step_solution", [])) if isinstance(sol, dict) else str(sol)
    return {
        "question_id": q.id,
        "question_text": q.question_text,
        "marks": q.marks,
        "year": q.year,
        "topic_name": q.unit_or_topic_guess,
        "solution": sol,
        "model_answer": formatted_answer,
    }


# ---------------------------------------------------------------------------
# Feature 5 & Phase 8: Download Study Plan as PDF
# ---------------------------------------------------------------------------

@app.get("/api/subjects/{subject_id}/export-pdf")
def export_subject_study_plan_pdf(
    subject_id: int,
    sections: Optional[str] = Query(None),
    language: Optional[str] = Query("en"),
    mode: Optional[str] = Query("master", pattern="^(master|cheatsheet|mock)$"),
    db: Session = Depends(get_db),
):
    """
    Generates and serves study documents in 3 smart modes:
    - 'master': Complete Multi-Page Master Study & Solution Guide
    - 'cheatsheet': 1-Night Before Exam Ultra-Compact Formula Matrix
    - 'mock': AI Predicted Mock Question Paper (70M) with Official Answer Key
    Supports optional ?sections=summary,topics,repeated,questions,plan, ?language=en|hi, and ?mode=master|cheatsheet|mock.
    """
    subject = db.query(Subject).filter(Subject.id == subject_id).first()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found.")

    topics = [t.to_dict() for t in subject.topics]
    topics.sort(key=lambda t: t.get("priority_score", 0), reverse=True)

    repeated_questions = [rg.to_dict() for rg in subject.repeated_groups]
    suggested_questions = [sq.to_dict() for sq in subject.suggested_questions]

    stats = {
        "total_papers": len([p for p in subject.papers if p.doc_type != "notes"]),
        "total_questions": len(subject.questions),
        "total_topics": len(topics),
        "total_suggested": len(suggested_questions),
    }

    sec_list = [s.strip() for s in sections.split(",") if s.strip()] if sections else None

    selected_mode = mode or "master"

    pdf_buffer = generate_study_plan_pdf(
        subject_dict=subject.to_dict(),
        topics=topics,
        repeated_questions=repeated_questions,
        stats=stats,
        suggested_questions=suggested_questions,
        sections=sec_list,
        language=language or "en",
        mode=selected_mode,
    )

    clean_code = re.sub(r"[^A-Za-z0-9_\-]", "_", subject.code or "Exam")
    if selected_mode == "cheatsheet":
        filename = f"ExamSense_1Night_CheatSheet_{clean_code}.pdf"
    elif selected_mode == "mock":
        filename = f"ExamSense_Predicted_Mock_Paper_{clean_code}.pdf"
    else:
        filename = f"ExamSense_Master_Guide_{clean_code}.pdf"

    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
