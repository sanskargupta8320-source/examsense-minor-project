import os
import io
import json
import logging
from typing import List, Optional
from fastapi import FastAPI, Depends, UploadFile, File, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.database import engine, Base, get_db
from app.models import Subject, Paper, Question, Topic, RepeatedQuestionGroup, NoteCache, QuizCache
from app.services.pdf_service import extract_text_from_pdf, sanitize_filename
from app.services.ai_service import (
    extract_questions_from_paper,
    normalize_topics_with_llm,
    generate_revision_notes,
    generate_practice_quiz,
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

# Initialize database tables
Base.metadata.create_all(bind=engine)

# Setup directories
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "./uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Initialize FastAPI App
app = FastAPI(
    title="ExamSense",
    description="AI-powered Exam Preparation Platform for College Students",
    version="1.0.0",
)

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
def health_check():
    """Returns application status and active AI engine configurations."""
    return {
        "status": "healthy",
        "gemini_api_configured": bool(GEMINI_API_KEY),
        "app": "ExamSense v1.0",
        "tagline": "Kya padhna hai, ab AI batayega.",
    }


@app.get("/api/subjects")
def list_subjects(db: Session = Depends(get_db)):
    """Lists all available analyzed subjects in the database."""
    subjects = db.query(Subject).order_by(desc(Subject.created_at)).all()
    return [s.to_dict() for s in subjects]


@app.get("/api/subjects/{subject_id}")
def get_subject_dashboard(subject_id: int, db: Session = Depends(get_db)):
    """
    Returns complete analytical dashboard data for a given subject:
    - Subject details
    - Papers analyzed
    - Topics sorted by priority with scores and formulas
    - Repeated question groups
    - Summary metrics for charts and dashboards
    """
    subject = db.query(Subject).filter(Subject.id == subject_id).first()
    if not subject:
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

    # Topic frequency breakdown
    high_count = sum(1 for t in topics if t.priority_level == "High")
    med_count = sum(1 for t in topics if t.priority_level == "Medium")
    low_count = sum(1 for t in topics if t.priority_level == "Low")

    # Exam years covered
    years_covered = sorted(list(set(p.year for p in papers)))

    return {
        "subject": subject.to_dict(),
        "stats": {
            "total_papers": len(papers),
            "total_questions": len(questions),
            "total_topics": len(topics),
            "high_priority_count": high_count,
            "medium_priority_count": med_count,
            "low_priority_count": low_count,
            "repeated_groups_count": len(repeated_groups),
            "years_covered": years_covered,
        },
        "papers": [p.to_dict() for p in papers],
        "topics": [t.to_dict() for t in topics],
        "repeated_groups": [rg.to_dict() for rg in repeated_groups],
    }


@app.delete("/api/subjects/{subject_id}")
def delete_subject(subject_id: int, db: Session = Depends(get_db)):
    """Deletes a subject and its associated papers, questions, topics, and caches."""
    subject = db.query(Subject).filter(Subject.id == subject_id).first()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found.")
    db.delete(subject)
    db.commit()
    return {"message": f"Subject '{subject.name}' deleted successfully."}


@app.post("/api/demo/load")
def load_demo(db: Session = Depends(get_db)):
    """
    Populates SQLite database with standard RGPV CS-501 DBMS 4-year examination dataset,
    complete with TF-IDF repeat question clusters, calculated priorities, notes, and quiz.
    Enables instant offline/local demonstration with 0 external dependencies!
    """
    try:
        subject = load_demo_data(db)
        return {
            "success": True,
            "subject_id": subject.id,
            "message": f"Successfully loaded demo dataset for '{subject.name}' ({subject.code})!",
        }
    except Exception as e:
        logger.error(f"Error loading demo data: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to load demo data: {str(e)}")


# ---------------------------------------------------------------------------
# Feature 1 & 2: PDF Upload, Text Extraction, and Question Processing
# ---------------------------------------------------------------------------

@app.post("/api/upload")
async def upload_and_process_papers(
    subject_name: str = Form(...),
    subject_code: str = Form(...),
    years: str = Form(...),  # comma-separated string e.g. "2021,2022,2023"
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    """
    Accepts Subject Name, Subject Code, and multiple PDF files with corresponding exam years.
    Extracts text, splits questions using AI, clusters topics, calculates priority,
    and detects repeated questions across years.
    """
    clean_name = subject_name.strip()
    clean_code = subject_code.strip().upper()

    if not clean_name or not clean_code:
        raise HTTPException(status_code=400, detail="Subject name and subject code are required.")

    if not files:
        raise HTTPException(status_code=400, detail="Please upload at least one PDF question paper.")

    # Parse years
    try:
        year_list = [int(y.strip()) for y in years.split(",") if y.strip()]
    except Exception:
        year_list = [2023] * len(files)

    # Pad or slice years to match file count
    while len(year_list) < len(files):
        year_list.append(year_list[-1] if year_list else 2023)

    # 1. Create or retrieve Subject
    subject = db.query(Subject).filter(Subject.code == clean_code).first()
    if not subject:
        subject = Subject(name=clean_name, code=clean_code)
        db.add(subject)
        db.flush()
    else:
        # Update name if changed
        subject.name = clean_name
        db.flush()

    extracted_papers = []
    all_raw_questions = []

    # 2. Extract text from each uploaded PDF
    for idx, upload_file in enumerate(files):
        if not upload_file.filename.lower().endswith(".pdf"):
            raise HTTPException(
                status_code=400,
                detail=f"File '{upload_file.filename}' is not a PDF. Only PDF files are supported.",
            )

        safe_name = sanitize_filename(upload_file.filename)
        save_path = os.path.join(UPLOAD_DIR, f"{clean_code}_{year_list[idx]}_{safe_name}")

        try:
            content = await upload_file.read()
            if len(content) > 15 * 1024 * 1024:
                raise HTTPException(
                    status_code=400,
                    detail=f"File '{upload_file.filename}' exceeds 10 MB limit.",
                )

            with open(save_path, "wb") as f:
                f.write(content)

            # Extract text via pdf_service
            extracted_text, is_ocr, metadata = extract_text_from_pdf(save_path)

            paper_obj = Paper(
                subject_id=subject.id,
                year=year_list[idx],
                filename=safe_name,
                filepath=save_path,
                extracted_text=extracted_text,
                is_ocr=is_ocr,
            )
            db.add(paper_obj)
            db.flush()
            extracted_papers.append(paper_obj)

            # Feature 2: Question Extraction via LLM
            logger.info(f"Extracting questions from {safe_name} (Year {year_list[idx]})...")
            questions_data = extract_questions_from_paper(
                paper_text=extracted_text,
                year=year_list[idx],
                subject_name=clean_name,
            )

            for q_item in questions_data:
                q_obj = Question(
                    subject_id=subject.id,
                    paper_id=paper_obj.id,
                    year=year_list[idx],
                    question_text=q_item["question_text"],
                    marks=q_item.get("marks", 7),
                    unit_or_topic_guess=q_item.get("unit_or_topic_guess", "General"),
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

        except ValueError as val_err:
            logger.warning(f"Validation error on file {upload_file.filename}: {val_err}")
            raise HTTPException(status_code=400, detail=str(val_err))
        except Exception as err:
            logger.error(f"Error processing {upload_file.filename}: {err}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to process '{upload_file.filename}': {str(err)}")

    if not all_raw_questions:
        raise HTTPException(status_code=400, detail="Could not extract any questions from the uploaded papers.")

    # 3. Topic Normalization & Clustering
    raw_topic_names = [q["unit_or_topic_guess"] for q in all_raw_questions]
    topic_mapping = normalize_topics_with_llm(raw_topic_names, subject_name=clean_name)

    # Apply normalized names
    for q in all_raw_questions:
        norm_name = topic_mapping.get(q["unit_or_topic_guess"], q["unit_or_topic_guess"])
        q["unit_or_topic_guess"] = norm_name
        q["db_obj"].unit_or_topic_guess = norm_name

    # 4. Feature 3 & 4: Topic Aggregation & Priority Scoring
    all_subject_years = [p.year for p in extracted_papers]
    aggregated_topics = aggregate_topics_and_priorities(
        questions=all_raw_questions,
        all_subject_years=all_subject_years,
    )

    for t_data in aggregated_topics:
        topic_obj = Topic(
            subject_id=subject.id,
            name=t_data["name"],
            frequency=t_data["frequency"],
            total_marks=t_data["total_marks"],
            years_asked=json.dumps(t_data["years_asked"]),
            last_year_asked=t_data["last_year_asked"],
            priority_score=t_data["priority_score"],
            priority_level=t_data["priority_level"],
            priority_breakdown=json.dumps(t_data["priority_breakdown"]),
        )
        db.add(topic_obj)
        db.flush()

        # Link questions
        for q in all_raw_questions:
            if q["unit_or_topic_guess"] == t_data["name"]:
                q["db_obj"].topic_id = topic_obj.id

    # 5. Feature 3: Repeated Questions Detection (TF-IDF + Cosine Similarity)
    repeated_groups = find_repeated_questions(all_raw_questions, similarity_threshold=0.62)
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

    db.commit()

    return {
        "success": True,
        "subject_id": subject.id,
        "papers_processed": len(extracted_papers),
        "questions_extracted": len(all_raw_questions),
        "topics_discovered": len(aggregated_topics),
        "repeated_patterns": len(repeated_groups),
    }


# ---------------------------------------------------------------------------
# Feature 6: Notes and Quiz Generator (Cached in Database)
# ---------------------------------------------------------------------------

@app.get("/api/topics/{topic_id}/notes")
def get_topic_notes(
    topic_id: int,
    language: str = Query("en", pattern="^(en|hi)$"),
    db: Session = Depends(get_db),
):
    """
    Returns short exam-oriented revision notes for a topic.
    Checks NoteCache in SQLite first to eliminate redundant API calls.
    Supports English ('en') and Hinglish / Hindi-English ('hi').
    """
    topic = db.query(Topic).filter(Topic.id == topic_id).first()
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found.")

    # Check cache
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

    # Fetch sample questions for context
    sample_questions = [q.question_text for q in topic.questions[:4]]

    # Generate notes via AI service
    notes_markdown = generate_revision_notes(
        topic_name=topic.name,
        subject_name=topic.subject.name,
        sample_questions=sample_questions,
        language=language,
    )

    # Store in database cache
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
def get_topic_quiz(topic_id: int, db: Session = Depends(get_db)):
    """
    Generates or fetches 5 MCQs with 4 options, correct answer, and explanation.
    Caches quiz in SQLite for instant repeat practice.
    """
    topic = db.query(Topic).filter(Topic.id == topic_id).first()
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found.")

    # Check cache
    cached = db.query(QuizCache).filter(QuizCache.topic_id == topic_id).first()
    if cached:
        return {
            "topic_id": topic.id,
            "topic_name": topic.name,
            "cached": True,
            "quiz": cached.to_dict()["quiz"],
        }

    sample_questions = [q.question_text for q in topic.questions[:3]]

    quiz_data = generate_practice_quiz(
        topic_name=topic.name,
        subject_name=topic.subject.name,
        sample_questions=sample_questions,
    )

    # Save to cache
    new_cache = QuizCache(
        topic_id=topic.id,
        quiz_json=json.dumps(quiz_data),
    )
    db.add(new_cache)
    db.commit()

    return {
        "topic_id": topic.id,
        "topic_name": topic.name,
        "cached": False,
        "quiz": quiz_data,
    }


# ---------------------------------------------------------------------------
# Feature 5: Download Study Plan as PDF
# ---------------------------------------------------------------------------

@app.get("/api/subjects/{subject_id}/export-pdf")
def export_subject_study_plan_pdf(subject_id: int, db: Session = Depends(get_db)):
    """Generates and serves a downloadable PDF study plan for the subject."""
    subject = db.query(Subject).filter(Subject.id == subject_id).first()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found.")

    topics = [t.to_dict() for t in subject.topics]
    # Sort topics by priority_score descending
    topics.sort(key=lambda t: t.get("priority_score", 0), reverse=True)

    repeated_questions = [rg.to_dict() for rg in subject.repeated_groups]
    stats = {
        "total_papers": len(subject.papers),
        "total_questions": len(subject.questions),
        "total_topics": len(topics),
    }

    pdf_buffer = generate_study_plan_pdf(
        subject_dict=subject.to_dict(),
        topics=topics,
        repeated_questions=repeated_questions,
        stats=stats,
    )

    filename = f"ExamSense_Study_Plan_{subject.code}.pdf"
    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
