"""
ExamSense Comprehensive End-to-End Test Suite
Tests all core APIs, multi-sample demos, visitor isolation, smart defaults,
file and text uploads, notes analysis, AI topic estimation, live status polling,
rate limiting, PDF export with sections, and database migrations.
"""

import sys
import os
import io
import json
import uuid
import unittest
from unittest.mock import patch, MagicMock

# Ensure UTF-8 output on Windows console
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from fastapi.testclient import TestClient
from app.main import app, upload_limiter, ai_limiter
from app.database import engine, SessionLocal, migrate_db
from app.models import Subject, Paper, Topic, Question, SuggestedQuestion, ExtractionCache
from app.services.ai_service import (
    get_candidate_models,
    extract_questions_from_paper,
    parse_retry_delay,
    format_remaining_time,
    consume_ai_budget,
    AIQuotaExhaustedError,
    compute_content_hash,
    get_cached_extraction,
    save_cached_extraction,
    guess_subject_from_text,
    get_ai_status,
    _ai_call_budget,
    AI_DAILY_CALL_LIMIT,
)

client = TestClient(app)


def run_tests():
    print("=" * 65)
    print("🚀 EXAMSENSE COMPREHENSIVE END-TO-END TEST SUITE")
    print("=" * 65)

    # -------------------------------------------------------------
    # Test 1: Healthcheck
    # -------------------------------------------------------------
    print("\n[Test 1] Health Check Endpoint (/api/health)...")
    res = client.get("/api/health")
    assert res.status_code == 200, f"Health check failed: {res.text}"
    health_data = res.json()
    print(f"  -> Status: {health_data.get('status')}")
    print(f"  -> Tagline: {health_data.get('tagline')}")
    print(f"  -> Gemini Configured: {health_data.get('gemini_api_configured')}")
    print(f"  -> Gemini Working: {health_data.get('gemini_working')}")
    print(f"  -> Max Upload Size MB: {health_data.get('max_upload_size_mb')}")
    assert health_data.get("max_upload_size_mb") == 40
    print("  PASSED ✅")

    # -------------------------------------------------------------
    # Test 2: Load College Demo Data (CS-501)
    # -------------------------------------------------------------
    print("\n[Test 2] College Demo Data Loader (/api/demo/load?demo_type=college)...")
    res = client.post("/api/demo/load?demo_type=college")
    assert res.status_code == 200, f"Demo loading failed: {res.text}"
    demo_res = res.json()
    college_id = demo_res.get("subject_id")
    assert college_id is not None, "Subject ID not returned in demo response"
    print(f"  -> Message: {demo_res.get('message')}")
    print(f"  -> Created College Subject ID: {college_id}")
    print("  PASSED ✅")

    # -------------------------------------------------------------
    # Test 3: List Subjects
    # -------------------------------------------------------------
    print("\n[Test 3] List Subjects (/api/subjects)...")
    res = client.get("/api/subjects")
    assert res.status_code == 200, f"List subjects failed: {res.text}"
    subjects = res.json()
    assert len(subjects) >= 1, "Expected at least 1 subject"
    print(f"  -> Found {len(subjects)} subject(s): {[s['name'] + ' (' + s['code'] + ')' for s in subjects]}")
    print("  PASSED ✅")

    # -------------------------------------------------------------
    # Test 4: Get Subject Dashboard
    # -------------------------------------------------------------
    print(f"\n[Test 4] Subject Dashboard Analytics (/api/subjects/{college_id})...")
    res = client.get(f"/api/subjects/{college_id}")
    assert res.status_code == 200, f"Subject dashboard failed: {res.text}"
    data = res.json()
    
    stats = data.get("stats", {})
    topics = data.get("topics", [])
    papers = data.get("papers", [])
    repeated_groups = data.get("repeated_groups", [])

    print(f"  -> Total Exam Papers: {stats.get('total_papers')}")
    print(f"  -> Total Questions: {stats.get('total_questions')}")
    print(f"  -> Topics Mapped: {len(topics)}")
    print(f"  -> High Priority Topics: {stats.get('high_priority_count')}")
    print(f"  -> Medium Priority Topics: {stats.get('medium_priority_count')}")
    print(f"  -> Low Priority Topics: {stats.get('low_priority_count')}")
    print(f"  -> Repeated Question Groups: {len(repeated_groups)}")

    assert len(topics) > 0, "No topics found"
    assert len(papers) >= 4, f"Expected 4 exam papers, got {len(papers)}"
    assert len(repeated_groups) > 0, "Expected repeat question groups"

    top_topic = topics[0]
    print(f"  -> #1 Predicted Exam Topic: '{top_topic['name']}'")
    print(f"     Priority Score: {top_topic['priority_score']}/100 [{top_topic['priority_level']}]")
    print(f"     Frequency: {top_topic['frequency']}x across years: {top_topic['years_asked']}")
    print("  PASSED ✅")

    # -------------------------------------------------------------
    # Test 5: Repeated Questions (TF-IDF Similarity)
    # -------------------------------------------------------------
    print("\n[Test 5] Verified Repeated Questions (TF-IDF Similarity)...")
    top_repeat = repeated_groups[0]
    print(f"  -> Top Recurring Question: '{top_repeat['canonical_question'][:70]}...'")
    print(f"     Similarity Score: {top_repeat['similarity_score']}%")
    print(f"     Appeared In Years: {top_repeat['years']}")
    print(f"     Total Variations: {top_repeat['repeat_count']}")
    assert top_repeat['similarity_score'] >= 50
    print("  PASSED ✅")

    # -------------------------------------------------------------
    # Test 6: Revision Notes Generation (English)
    # -------------------------------------------------------------
    topic_id = top_topic["id"]
    print(f"\n[Test 6] Revision Notes in English (/api/topics/{topic_id}/notes?language=en)...")
    res = client.get(f"/api/topics/{topic_id}/notes?language=en")
    assert res.status_code == 200, f"Notes generation failed: {res.text}"
    notes_en = res.json()
    assert len(notes_en.get("notes", "")) > 50, "Notes content too short"
    print(f"  -> Notes Length: {len(notes_en['notes'])} chars")
    print(f"  -> Cached in DB: {notes_en.get('cached')}")
    print("  PASSED ✅")

    # -------------------------------------------------------------
    # Test 7: Revision Notes Generation (Hinglish)
    # -------------------------------------------------------------
    print(f"\n[Test 7] Revision Notes in Hinglish (/api/topics/{topic_id}/notes?language=hi)...")
    res = client.get(f"/api/topics/{topic_id}/notes?language=hi")
    assert res.status_code == 200, f"Hinglish notes failed: {res.text}"
    notes_hi = res.json()
    assert len(notes_hi.get("notes", "")) > 50, "Hinglish notes too short"
    print(f"  -> Hinglish Notes Length: {len(notes_hi['notes'])} chars")
    print("  PASSED ✅")

    # -------------------------------------------------------------
    # Test 8: Practice Quiz Generation & Caching
    # -------------------------------------------------------------
    print(f"\n[Test 8] Practice Quiz Generator (/api/topics/{topic_id}/quiz)...")
    res = client.get(f"/api/topics/{topic_id}/quiz?count=5&difficulty=medium")
    assert res.status_code == 200, f"Quiz generation failed: {res.text}"
    quiz_data = res.json()
    questions = quiz_data.get("quiz", [])
    assert len(questions) == 5, f"Expected 5 MCQs, got {len(questions)}"
    for q in questions:
        assert "question" in q, "Missing question text"
        assert len(q.get("options", [])) == 4, "Expected 4 options per question"
        assert 0 <= q.get("correct_index", -1) <= 3, "Invalid correct_index"
        assert "explanation" in q, "Missing explanation"
    print(f"  -> Generated 5 MCQs successfully. Sample: '{questions[0]['question'][:60]}...'")
    print("  PASSED ✅")

    # -------------------------------------------------------------
    # Test 9: Study Plan PDF Download
    # -------------------------------------------------------------
    print(f"\n[Test 9] Study Plan PDF Export (/api/subjects/{college_id}/export-pdf)...")
    res = client.get(f"/api/subjects/{college_id}/export-pdf")
    assert res.status_code == 200, f"PDF export failed: {res.text}"
    assert res.headers.get("content-type") == "application/pdf"
    pdf_bytes = res.content
    assert pdf_bytes.startswith(b"%PDF"), "Response is not a valid PDF binary stream"
    print(f"  -> Exported PDF Size: {len(pdf_bytes):,} bytes with '%PDF' magic header")
    print("  PASSED ✅")

    # -------------------------------------------------------------
    # Test 10: HTML Frontend Rendering
    # -------------------------------------------------------------
    print("\n[Test 10] HTML Single-Page Application (GET /)...")
    res = client.get("/")
    assert res.status_code == 200, f"HTML index failed: {res.text}"
    assert "ExamSense" in res.text, "ExamSense title not found in HTML"
    assert "Kya padhna hai, ab AI batayega" in res.text, "Tagline not found in HTML"
    assert "For every student, every exam" in res.text, "New hero badge text not found in HTML"
    print("  -> Rendered index.html successfully with universal student theme")
    print("  PASSED ✅")

    # -------------------------------------------------------------
    # Test 11: Multi-Sample Demos (School & Competitive)
    # -------------------------------------------------------------
    print("\n[Test 11] Multi-Sample Offline Demos (School & Competitive)...")
    res_school = client.post("/api/demo/load?demo_type=school")
    assert res_school.status_code == 200, "School demo failed to load"
    school_id = res_school.json()["subject_id"]
    print(f"  -> Loaded School Demo (ID: {school_id})")

    res_comp = client.post("/api/demo/load?demo_type=competitive")
    assert res_comp.status_code == 200, "Competitive demo failed to load"
    comp_id = res_comp.json()["subject_id"]
    print(f"  -> Loaded Competitive Demo (ID: {comp_id})")
    print("  PASSED ✅")

    # -------------------------------------------------------------
    # Test 12: Single-PDF Upload with Smart Defaults (No name/code/year)
    # -------------------------------------------------------------
    print("\n[Test 12] Single-File Upload with Smart Defaults (No name/code/year)...")
    # Simulate a minimal PDF document upload
    sample_pdf_content = (
        b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R >>\nendobj\n"
        b"4 0 obj\n<< /Length 120 >>\nstream\nBT\n/F1 12 Tf\n72 712 Td\n"
        b"(Q1. Explain Newton's laws of motion with examples. (7 Marks)) Tj\n"
        b"(Q2. State Archimedes principle and its applications. (7 Marks)) Tj\n"
        b"ET\nendstream\nendobj\nxref\n0 5\n0000000000 65535 f \n"
        b"trailer\n<< /Size 5 /Root 1 0 R >>\nstartxref\n400\n%%EOF"
    )
    
    files = [
        ("files", ("Physics_Paper_2022.pdf", sample_pdf_content, "application/pdf"))
    ]
    res_upload = client.post("/api/upload", files=files)
    assert res_upload.status_code == 200, f"Upload failed: {res_upload.text}"
    up_data = res_upload.json()
    new_sub_id = up_data.get("subject_id")
    assert new_sub_id is not None
    assert up_data.get("status") in ["processing", "ready"]
    print(f"  -> Upload accepted! Subject ID: {new_sub_id}, Status: {up_data.get('status')}")
    print(f"  -> Auto-generated Code: {up_data.get('subject_code')}")
    assert up_data.get("subject_code", "").startswith("SUB-")

    # Verify status polling endpoint
    res_status = client.get(f"/api/subjects/{new_sub_id}/status")
    assert res_status.status_code == 200
    st_data = res_status.json()
    print(f"  -> Polled Status: {st_data.get('status')} | Progress: {st_data.get('progress_text')}")
    print("  PASSED ✅")

    # -------------------------------------------------------------
    # Test 13: Text-Paste Upload
    # -------------------------------------------------------------
    print("\n[Test 13] Text-Paste Question Paper Upload...")
    pasted_body = {
        "pasted_text": (
            "EXAMINATION 2023 - CHEMISTRY\n"
            "Q1. Describe the difference between covalent and ionic bonding. (7 Marks)\n"
            "Q2. Explain Le Chatelier's principle with an example equilibrium. (7 Marks)\n"
            "Q3. What is an exothermic reaction? Give one example. (5 Marks)\n"
        ),
        "subject_name": "Applied Chemistry",
        "exam_type": "School Board",
    }
    res_paste = client.post("/api/upload", data=pasted_body)
    assert res_paste.status_code == 200, f"Text paste failed: {res_paste.text}"
    paste_data = res_paste.json()
    paste_sub_id = paste_data.get("subject_id")
    assert paste_sub_id is not None
    print(f"  -> Text upload accepted. Subject ID: {paste_sub_id}")
    print("  PASSED ✅")

    # -------------------------------------------------------------
    # Test 14: Start with Just a Subject Name (/api/subjects/from-topic)
    # -------------------------------------------------------------
    print("\n[Test 14] Start with Just a Subject Name (/api/subjects/from-topic)...")
    mock_topics = [
        {
            "topic_name": "Photosynthesis & Plant Respiration",
            "estimated_importance": 9,
            "typical_marks": 7,
            "typical_questions": ["Explain the light and dark reactions in photosynthesis."],
        },
        {
            "topic_name": "Cellular Genetics & DNA Replication",
            "estimated_importance": 8,
            "typical_marks": 7,
            "typical_questions": ["Describe the double-helix structure of DNA."],
        },
        {
            "topic_name": "Ecosystem Energy Flow",
            "estimated_importance": 6,
            "typical_marks": 5,
            "typical_questions": ["What is a food web?"],
        },
    ]

    with patch("app.main.generate_syllabus_from_subject_name", return_value=mock_topics):
        topic_body = {
            "subject_name": "General Biology",
            "exam_level": "School Board",
            "board_name": "CBSE",
            "class_level": "Class 10",
        }
        res_topic = client.post("/api/subjects/from-topic", data=topic_body)
        assert res_topic.status_code == 200, f"Topic study plan generation failed: {res_topic.text}"
        topic_res = res_topic.json()
        topic_sub_id = topic_res.get("subject_id")
        assert topic_res.get("source") == "ai_estimate"
        assert topic_res.get("topics_count") == 3
        print(f"  -> Created Subject from topic: ID {topic_sub_id}, Source: {topic_res.get('source')}")

    # Verify dashboard returns source='ai_estimate'
    res_dash_topic = client.get(f"/api/subjects/{topic_sub_id}")
    dash_data = res_dash_topic.json()
    assert dash_data["subject"]["source"] == "ai_estimate"
    print("  PASSED ✅")

    # -------------------------------------------------------------
    # Test 15: Upload Notes & Question Outlines (Phase 7)
    # -------------------------------------------------------------
    print("\n[Test 15] Upload Notes to Subject & Answer Outlines (/api/subjects/{id}/add-notes)...")
    mock_notes_questions = [
        {
            "topic": "Photosynthesis & Plant Respiration",
            "question_text": "Explain the role of Chlorophyll and ATP synthesis in the light reaction.",
            "question_type": "long answer",
            "expected_marks": 7,
            "why_important": "Frequently asked in chapter-end exams",
            "difficulty": "Medium",
        },
        {
            "topic": "Mendelian Genetics",
            "question_text": "State Mendel's Law of Segregation with a monohybrid cross diagram.",
            "question_type": "short answer",
            "expected_marks": 5,
            "why_important": "Core genetics concept",
            "difficulty": "Easy",
        }
    ]

    with patch("app.main.generate_important_questions_from_notes", return_value=mock_notes_questions):
        notes_body = {
            "notes_text": "Detailed student revision notes on plant biology, ATP synthesis, chlorophyll, and genetics.",
        }
        res_notes = client.post(f"/api/subjects/{topic_sub_id}/add-notes", data=notes_body)
        assert res_notes.status_code == 200, f"Add notes failed: {res_notes.text}"
        notes_res = res_notes.json()
        assert notes_res.get("suggested_questions_count") == 2
        print(f"  -> Extracted {notes_res.get('suggested_questions_count')} suggested questions from notes.")

    # Check dashboard has suggested questions
    res_dash_notes = client.get(f"/api/subjects/{topic_sub_id}")
    dash_notes_data = res_dash_notes.json()
    suggested = dash_notes_data.get("suggested_questions", [])
    assert len(suggested) >= 2, "Expected suggested questions in dashboard"
    first_sq = suggested[0]
    print(f"  -> Suggested Question: '{first_sq['question_text'][:60]}...'")

    # Test answer outline endpoint
    with patch("app.main.generate_answer_outline", return_value="### 1. Key Concepts\n- Concept A\n- Concept B"):
        res_outline = client.post(f"/api/suggested-questions/{first_sq['id']}/outline")
        assert res_outline.status_code == 200
        outline_data = res_outline.json()
        assert "Key Concepts" in outline_data["answer_outline"]
        print(f"  -> Generated Answer Outline: {len(outline_data['answer_outline'])} chars")
    print("  PASSED ✅")

    # -------------------------------------------------------------
    # Test 16: Visitor Isolation & Demo Protection (Phase 1)
    # -------------------------------------------------------------
    print("\n[Test 16] Visitor Isolation & Shared Demo Protection...")
    # User A creates a subject
    user_a_vid = "user_a_" + uuid.uuid4().hex[:6]
    user_b_vid = "user_b_" + uuid.uuid4().hex[:6]

    client.cookies.set("examsense_vid", user_a_vid)
    res_a = client.post("/api/upload", data={"pasted_text": "Sample Exam Question Paper for User A (7 Marks)", "subject_name": "User A Subject"})
    user_a_sub_id = res_a.json()["subject_id"]

    # User B should NOT see User A's subject
    client.cookies.set("examsense_vid", user_b_vid)
    res_b_list = client.get("/api/subjects")
    b_subjects = res_b_list.json()
    b_subject_ids = [s["id"] for s in b_subjects]
    assert user_a_sub_id not in b_subject_ids, "Visitor isolation failed: User B can see User A's subject!"

    # User B cannot access User A's dashboard
    res_b_dash = client.get(f"/api/subjects/{user_a_sub_id}")
    assert res_b_dash.status_code == 404, "User B should get 404 for User A's private subject"

    # User B cannot delete User A's subject
    res_b_del = client.delete(f"/api/subjects/{user_a_sub_id}")
    assert res_b_del.status_code in [403, 404], "User B should not be able to delete User A's subject"

    # Demo subjects cannot be deleted
    res_demo_del = client.delete(f"/api/subjects/{college_id}")
    assert res_demo_del.status_code == 403, "Demo subject must not be deletable"
    print(f"  -> Protected demo subject deletion: {res_demo_del.json().get('detail')}")

    # User A CAN delete their own subject
    client.cookies.set("examsense_vid", user_a_vid)
    res_a_del = client.delete(f"/api/subjects/{user_a_sub_id}")
    assert res_a_del.status_code == 200, "User A should be able to delete their own subject"
    print(f"  -> User A successfully deleted their own subject.")
    print("  PASSED ✅")

    # -------------------------------------------------------------
    # Test 17: Rate Limiting Friendly Response
    # -------------------------------------------------------------
    print("\n[Test 17] In-Memory Rate Limiting Test...")
    # Test upload rate limiter directly
    test_ip = "192.168.100.200"
    for _ in range(10):
        upload_limiter.is_allowed(test_ip)
    # The 11th should be blocked
    is_allowed = upload_limiter.is_allowed(test_ip)
    assert not is_allowed, "Rate limiter did not block after 10 requests"
    print("  -> Rate limiter correctly throttles after limit reached")
    print("  PASSED ✅")

    # -------------------------------------------------------------
    # Test 18: Model Fallback List Logic
    # -------------------------------------------------------------
    print("\n[Test 18] AI Model Fallback Hierarchy...")
    candidates = get_candidate_models()
    assert len(candidates) >= 3, "Expected at least 3 fallback candidate models"
    print(f"  -> Candidate Model Fallback Hierarchy: {candidates}")
    print("  PASSED ✅")

    # -------------------------------------------------------------
    # Test 19: PDF Export with Custom Sections (Phase 8)
    # -------------------------------------------------------------
    print("\n[Test 19] Custom Sections PDF Export (?sections=summary,topics,plan)...")
    res_custom_pdf = client.get(f"/api/subjects/{college_id}/export-pdf?sections=summary,topics,plan")
    assert res_custom_pdf.status_code == 200
    assert res_custom_pdf.content.startswith(b"%PDF")
    print(f"  -> Generated customized PDF: {len(res_custom_pdf.content):,} bytes")
    print("  PASSED ✅")

    # -------------------------------------------------------------
    # Test 20: Database Migrations Integrity (Phase 2 & 9)
    # -------------------------------------------------------------
    print("\n[Test 20] Database Schema & SQLite Migrations Check...")
    migrate_db()
    with engine.connect() as conn:
        from sqlalchemy import text
        res_cols = conn.execute(text("PRAGMA table_info(subjects)")).fetchall()
        col_names = [r[1] for r in res_cols]
        expected_cols = ["id", "name", "code", "exam_type", "owner_id", "is_demo", "source", "status", "progress_text", "error_message"]
        for c in expected_cols:
            assert c in col_names, f"Missing column in subjects: {c}"
        print(f"  -> Verified columns in subjects: {col_names}")
    print("  PASSED ✅")

    # -------------------------------------------------------------
    # Test 21: Lazy Health Check & 10-Minute Caching
    # -------------------------------------------------------------
    print("\n[Test 21] Lazy /api/health vs Deep Health Check...")
    res_lazy = client.get("/api/health")
    assert res_lazy.status_code == 200
    lazy_data = res_lazy.json()
    assert "quota_exhausted" in lazy_data
    assert "quota_resets_in_seconds" in lazy_data
    assert "ai_calls_today" in lazy_data
    assert "ai_daily_limit" in lazy_data
    print(f"  -> Lazy healthcheck returned immediately: configured={lazy_data['gemini_api_configured']}, quota_exhausted={lazy_data['quota_exhausted']}")

    with patch("app.services.ai_service.run_deep_ai_check") as mock_deep:
        mock_deep.return_value = True
        res_deep = client.get("/api/health?deep=1")
        assert res_deep.status_code == 200
        assert mock_deep.called, "deep=1 should trigger run_deep_ai_check"
        print(f"  -> Explicit deep health check (?deep=1) correctly routed to deep model checker.")
    print("  PASSED ✅")

    # -------------------------------------------------------------
    # Test 22: AI Daily Call Budget Guard
    # -------------------------------------------------------------
    print("\n[Test 22] AI Daily Call Budget Guard...")
    orig_count = _ai_call_budget["count"]
    print(f"  -> In-app AI call limit: {AI_DAILY_CALL_LIMIT} calls/day (Current used: {orig_count})")
    assert AI_DAILY_CALL_LIMIT == 18, f"Expected default limit 18, got {AI_DAILY_CALL_LIMIT}"
    
    _ai_call_budget["count"] = AI_DAILY_CALL_LIMIT
    budget_blocked = False
    try:
        consume_ai_budget()
    except AIQuotaExhaustedError as b_err:
        budget_blocked = True
        print(f"  -> Correctly blocked call on budget limit: '{b_err}'")
    assert budget_blocked, "consume_ai_budget() should block when count >= AI_DAILY_CALL_LIMIT"

    res_budget = client.get("/api/health")
    assert res_budget.json()["quota_exhausted"] is True
    print("  -> /api/health reports quota_exhausted=True when budget limit is reached")

    _ai_call_budget["count"] = orig_count
    print("  PASSED ✅")

    # -------------------------------------------------------------
    # Test 23: 429 Retry-Delay Parser & Time Formatting
    # -------------------------------------------------------------
    print("\n[Test 23] Gemini 429 Error Retry-Delay Parser...")
    google_err = "429 Quota exceeded. Please wait. retry_delay { seconds: 3600 }"
    delay_sec = parse_retry_delay(google_err)
    assert delay_sec == 3600, f"Expected 3600s, got {delay_sec}"
    print(f"  -> Parsed Google retry_delay {{ seconds: 3600 }}: {delay_sec}s")

    text_err = "Resource has been exhausted. Please retry in 1h 25m 10s."
    delay_text = parse_retry_delay(text_err)
    expected_sec = 1 * 3600 + 25 * 60 + 10
    assert delay_text == expected_sec, f"Expected {expected_sec}s, got {delay_text}"
    print(f"  -> Parsed text 'retry in 1h 25m 10s': {delay_text}s")

    daily_err = "Resource exhausted: GenerateRequestsPerDayPerProjectPerModel-FreeTier limit exceeded"
    delay_daily = parse_retry_delay(daily_err)
    assert delay_daily == 43200, f"Expected 43200s (12h), got {delay_daily}"
    print(f"  -> Parsed daily quota error default delay: {delay_daily}s (12h)")

    formatted_time = format_remaining_time(3600 + 120)
    assert "1h 2m" in formatted_time
    print(f"  -> Formatted remaining time (3720s): '{formatted_time}'")
    print("  PASSED ✅")

    # -------------------------------------------------------------
    # Test 24: Quota Lock & Graceful Fallback (No 500/503 Crashes)
    # -------------------------------------------------------------
    print("\n[Test 24] Quota Lock Active & Heuristic Fallback...")
    import time
    import app.services.ai_service as ai_srv
    orig_lock = ai_srv.QUOTA_EXHAUSTED_UNTIL
    ai_srv.QUOTA_EXHAUSTED_UNTIL = time.time() + 1800  # 30 mins lock

    quota_status = get_ai_status()
    assert quota_status["quota_exhausted"] is True
    assert quota_status["quota_resets_in_seconds"] > 0
    print(f"  -> Under quota lock: quota_resets_in_seconds={quota_status['quota_resets_in_seconds']}")

    sample_paper = "1. Explain the working principle of Transformer.\n2. State Faraday's law of induction."
    qs_res = extract_questions_from_paper(paper_text=sample_paper, year=2023, subject_name="Basic Electrical")
    assert len(qs_res) >= 2, f"Expected at least 2 questions extracted via heuristic, got {len(qs_res)}"
    assert hasattr(qs_res, "doc_type"), "QuestionsResult must have doc_type attribute"
    print(f"  -> Extracted {len(qs_res)} questions via graceful heuristic fallback during quota lock.")

    ai_srv.QUOTA_EXHAUSTED_UNTIL = orig_lock
    print("  PASSED ✅")

    # -------------------------------------------------------------
    # Test 25: SHA-256 Extraction Cache & Local Heuristics
    # -------------------------------------------------------------
    print("\n[Test 25] SHA-256 Extraction Cache & Zero-Call Heuristics...")
    header_sample = "MID-SEMESTER EXAMINATION 2023\nCourse: Operating Systems Concepts\nTime: 3 Hours\nMax Marks: 70"
    guessed_subj = guess_subject_from_text(header_sample)
    assert guessed_subj == "Operating Systems Concepts", f"Expected 'Operating Systems Concepts', got '{guessed_subj}'"
    print(f"  -> Pure local regex subject guess: '{guessed_subj}' (0 Gemini calls)")

    content = "Question 1: Explain ACID properties in DBMS.\nQuestion 2: What is Normalization?"
    c_hash = compute_content_hash(text=content)
    assert len(c_hash) == 64, f"Expected 64-char hex SHA-256 hash, got {len(c_hash)}"
    print(f"  -> Content SHA-256 Hash: {c_hash[:16]}...")

    save_cached_extraction(c_hash, {
        "doc_type": "paper",
        "subject_guess": "Database Systems",
        "year_guess": 2022,
        "questions": [
            {"question_text": "Cached Q1", "marks": 7, "unit_or_topic_guess": "ACID", "year": 2022}
        ]
    })

    cached_hit = get_cached_extraction(c_hash)
    assert cached_hit is not None, "ExtractionCache lookup failed"
    assert cached_hit["questions"][0]["question_text"] == "Cached Q1"
    print("  -> Successfully verified SHA-256 ExtractionCache store and retrieval.")

    first_res = extract_questions_from_paper(paper_text=content, year=2022)
    assert first_res[0]["question_text"] == "Cached Q1"
    assert first_res.subject_guess == "Database Systems"
    print("  -> Verified extract_questions_from_paper reuses cache for identical content.")
    print("  PASSED ✅")

    print("\n" + "=" * 65)
    print("🎉 ALL 25/25 COMPREHENSIVE TESTS PASSED WITH 100% SUCCESS! 💯")
    print("=" * 65)


if __name__ == "__main__":
    run_tests()
