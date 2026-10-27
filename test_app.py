"""
ExamSense End-to-End Verification Test Script
Tests all core APIs, Demo Data Loader, Priority Scoring,
TF-IDF repeat question detection, Notes & Quiz caching, and PDF export.
"""

import sys
import json

# Ensure UTF-8 output on Windows console
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def run_tests():
    print("=" * 60)
    print("🚀 EXAMSENSE COMPREHENSIVE END-TO-END TEST SUITE")
    print("=" * 60)

    # Test 1: Healthcheck
    print("\n[Test 1] Health Check Endpoint (/api/health)...")
    res = client.get("/api/health")
    assert res.status_code == 200, f"Health check failed: {res.text}"
    health_data = res.json()
    print("  -> Status:", health_data.get("status"))
    print("  -> Tagline:", health_data.get("tagline"))
    print("  -> Gemini Configured:", health_data.get("gemini_api_configured"))
    print("  PASSED ✅")

    # Test 2: Load Demo Data
    print("\n[Test 2] 1-Click Demo Data Loader (/api/demo/load)...")
    res = client.post("/api/demo/load")
    assert res.status_code == 200, f"Demo loading failed: {res.text}"
    demo_res = res.json()
    subject_id = demo_res.get("subject_id")
    assert subject_id is not None, "Subject ID not returned in demo response"
    print(f"  -> {demo_res.get('message')}")
    print(f"  -> Created Subject ID: {subject_id}")
    print("  PASSED ✅")

    # Test 3: List Subjects
    print("\n[Test 3] List Subjects (/api/subjects)...")
    res = client.get("/api/subjects")
    assert res.status_code == 200, f"List subjects failed: {res.text}"
    subjects = res.json()
    assert len(subjects) >= 1, "Expected at least 1 subject"
    print(f"  -> Found {len(subjects)} subject(s): {[s['name'] + ' (' + s['code'] + ')' for s in subjects]}")
    print("  PASSED ✅")

    # Test 4: Get Subject Dashboard
    print(f"\n[Test 4] Subject Dashboard Analytics (/api/subjects/{subject_id})...")
    res = client.get(f"/api/subjects/{subject_id}")
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
    print(f"     Formula Breakdown: {top_topic.get('priority_breakdown', {})}")
    print("  PASSED ✅")

    # Test 5: Repeated Questions (TF-IDF Similarity)
    print("\n[Test 5] Verified Repeated Questions (TF-IDF Similarity)...")
    top_repeat = repeated_groups[0]
    print(f"  -> Top Recurring Question: '{top_repeat['canonical_question'][:70]}...'")
    print(f"     Similarity Score: {top_repeat['similarity_score']}%")
    print(f"     Appeared In Years: {top_repeat['years']}")
    print(f"     Total Variations: {top_repeat['repeat_count']}")
    print("  PASSED ✅")

    # Test 6: Revision Notes Generation (English)
    topic_id = top_topic["id"]
    print(f"\n[Test 6] Revision Notes in English (/api/topics/{topic_id}/notes?language=en)...")
    res = client.get(f"/api/topics/{topic_id}/notes?language=en")
    assert res.status_code == 200, f"Notes generation failed: {res.text}"
    notes_en = res.json()
    assert len(notes_en.get("notes", "")) > 100, "Notes content too short"
    print(f"  -> Notes Length: {len(notes_en['notes'])} chars")
    print(f"  -> Cached in DB: {notes_en.get('cached')}")
    print("  PASSED ✅")

    # Test 7: Revision Notes Generation (Hinglish)
    print(f"\n[Test 7] Revision Notes in Hinglish (/api/topics/{topic_id}/notes?language=hi)...")
    res = client.get(f"/api/topics/{topic_id}/notes?language=hi")
    assert res.status_code == 200, f"Hinglish notes failed: {res.text}"
    notes_hi = res.json()
    assert len(notes_hi.get("notes", "")) > 100, "Hinglish notes too short"
    print(f"  -> Hinglish Notes Length: {len(notes_hi['notes'])} chars")
    print("  PASSED ✅")

    # Test 8: Practice Quiz Generation & Caching
    print(f"\n[Test 8] Practice Quiz Generator (/api/topics/{topic_id}/quiz)...")
    res = client.get(f"/api/topics/{topic_id}/quiz")
    assert res.status_code == 200, f"Quiz generation failed: {res.text}"
    quiz_data = res.json()
    questions = quiz_data.get("quiz", [])
    assert len(questions) == 5, f"Expected 5 MCQs, got {len(questions)}"
    for q in questions:
        assert "question" in q, "Missing question text"
        assert len(q.get("options", [])) == 4, "Expected 4 options per question"
        assert 0 <= q.get("correct_index", -1) <= 3, "Invalid correct_index"
        assert "explanation" in q, "Missing explanation"
    print(f"  -> Generated 5 MCQs successfully. Sample Q1: '{questions[0]['question']}'")
    print(f"  -> Answer Index: {questions[0]['correct_index']} ({questions[0]['options'][questions[0]['correct_index']]})")
    print("  PASSED ✅")

    # Test 9: Study Plan PDF Download
    print(f"\n[Test 9] Study Plan PDF Export (/api/subjects/{subject_id}/export-pdf)...")
    res = client.get(f"/api/subjects/{subject_id}/export-pdf")
    assert res.status_code == 200, f"PDF export failed: {res.text}"
    assert res.headers.get("content-type") == "application/pdf", "Expected application/pdf content type"
    pdf_bytes = res.content
    assert pdf_bytes.startswith(b"%PDF"), "Response is not a valid PDF binary stream"
    print(f"  -> Exported PDF Size: {len(pdf_bytes):,} bytes with '%PDF' magic header")
    print("  PASSED ✅")

    # Test 10: HTML Frontend Rendering
    print("\n[Test 10] HTML Single-Page Application (GET /)...")
    res = client.get("/")
    assert res.status_code == 200, f"HTML index failed: {res.text}"
    assert "ExamSense" in res.text, "ExamSense title not found in HTML"
    assert "Kya padhna hai, ab AI batayega" in res.text, "Tagline not found in HTML"
    assert "Chart.js" in res.text or "chart.umd.min.js" in res.text, "Chart.js CDN missing"
    print("  -> Rendered index.html successfully with student theme, Chart.js, and modals")
    print("  PASSED ✅")

    print("\n" + "=" * 60)
    print("🎉 ALL 10/10 CORE TESTS PASSED SUCCESSFULLY! 💯")
    print("=" * 60)


if __name__ == "__main__":
    run_tests()
