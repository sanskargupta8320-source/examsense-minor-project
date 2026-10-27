import json
import logging
from sqlalchemy.orm import Session
from app.models import Subject, Paper, Question, Topic, RepeatedQuestionGroup, NoteCache, QuizCache
from app.services.analysis_service import find_repeated_questions, aggregate_topics_and_priorities
from app.services.ai_service import get_offline_fallback_notes, get_offline_fallback_quiz

logger = logging.getLogger("examsense.demo_service")

# High-yield RGPV / Indian University DBMS Exam Question Bank
DEMO_SUBJECT = {
    "name": "Database Management Systems",
    "code": "CS-501",
}

DEMO_QUESTIONS = [
    # 2020 Paper
    {
        "year": 2020,
        "marks": 7,
        "unit_or_topic_guess": "Normalization & Normal Forms",
        "question_text": "What is Normalization? Explain First, Second and Third Normal Forms (1NF, 2NF, 3NF) with suitable examples.",
    },
    {
        "year": 2020,
        "marks": 7,
        "unit_or_topic_guess": "Transaction Processing & ACID Properties",
        "question_text": "Define a Transaction in DBMS. Explain the ACID properties with the help of a state transition diagram.",
    },
    {
        "year": 2020,
        "marks": 7,
        "unit_or_topic_guess": "Concurrency Control & Two-Phase Locking",
        "question_text": "Explain Two-Phase Locking (2PL) protocol. Differentiate between Strict 2PL and Rigorous 2PL.",
    },
    {
        "year": 2020,
        "marks": 7,
        "unit_or_topic_guess": "Relational Algebra & Calculus",
        "question_text": "Describe the basic relational algebra operations: Select, Project, Cartesian Product, Union and Set Difference with examples.",
    },
    {
        "year": 2020,
        "marks": 7,
        "unit_or_topic_guess": "Deadlock Handling in DBMS",
        "question_text": "What is Deadlock in DBMS? How is deadlock detected and prevented using Wait-For Graph (WFG)?",
    },
    {
        "year": 2020,
        "marks": 7,
        "unit_or_topic_guess": "Database Architecture & Data Models",
        "question_text": "Explain the Three-Schema Architecture of DBMS. What is physical and logical data independence?",
    },

    # 2021 Paper
    {
        "year": 2021,
        "marks": 7,
        "unit_or_topic_guess": "Normalization & Normal Forms",
        "question_text": "Define Normalization. Discuss 1NF, 2NF, 3NF and Boyce-Codd Normal Form (BCNF) with illustrative examples.",
    },
    {
        "year": 2021,
        "marks": 7,
        "unit_or_topic_guess": "Transaction Processing & ACID Properties",
        "question_text": "Explain ACID properties in detail. Why is durability critical in banking database systems?",
    },
    {
        "year": 2021,
        "marks": 7,
        "unit_or_topic_guess": "ER Modeling & Schema Mapping",
        "question_text": "Draw an Entity-Relationship (ER) diagram for a University Management System. Explain entity, attribute, cardinality and primary key.",
    },
    {
        "year": 2021,
        "marks": 7,
        "unit_or_topic_guess": "Database Recovery Techniques",
        "question_text": "Explain Log-Based Recovery techniques. Differentiate between Deferred Database Modification and Immediate Database Modification.",
    },
    {
        "year": 2021,
        "marks": 7,
        "unit_or_topic_guess": "Relational Algebra & Calculus",
        "question_text": "Explain Natural Join, Theta Join, and Outer Joins (Left, Right, Full) in relational algebra with sample tables.",
    },
    {
        "year": 2021,
        "marks": 7,
        "unit_or_topic_guess": "SQL Queries & Views",
        "question_text": "Write SQL queries demonstrating GROUP BY, HAVING, and aggregate functions (COUNT, SUM, AVG) with an Employee table schema.",
    },

    # 2022 Paper
    {
        "year": 2022,
        "marks": 7,
        "unit_or_topic_guess": "Transaction Processing & ACID Properties",
        "question_text": "What is serializability? Explain conflict serializability and view serializability with precedence graph examples.",
    },
    {
        "year": 2022,
        "marks": 7,
        "unit_or_topic_guess": "Concurrency Control & Two-Phase Locking",
        "question_text": "Discuss the Lock-Based Concurrency Control protocols. What are Shared (S) and Exclusive (X) locks?",
    },
    {
        "year": 2022,
        "marks": 7,
        "unit_or_topic_guess": "ER Modeling & Schema Mapping",
        "question_text": "How do you convert an ER model into relational database tables? Explain with rules for strong and weak entity sets.",
    },
    {
        "year": 2022,
        "marks": 7,
        "unit_or_topic_guess": "Indexing & B/B+ Trees",
        "question_text": "What is Indexing in databases? Compare Primary, Secondary and Clustered indexing with diagrams.",
    },
    {
        "year": 2022,
        "marks": 7,
        "unit_or_topic_guess": "Database Recovery Techniques",
        "question_text": "What is Checkpointing in DBMS? How does checkpointing reduce recovery time after a system crash?",
    },
    {
        "year": 2022,
        "marks": 7,
        "unit_or_topic_guess": "Database Architecture & Data Models",
        "question_text": "Compare Relational Data Model, Hierarchical Data Model and Network Data Model with advantages and limitations.",
    },

    # 2023 Paper
    {
        "year": 2023,
        "marks": 7,
        "unit_or_topic_guess": "Normalization & Normal Forms",
        "question_text": "Why do we normalize databases? Explain 2NF, 3NF and BCNF with functional dependencies and decomposition examples.",
    },
    {
        "year": 2023,
        "marks": 7,
        "unit_or_topic_guess": "Transaction Processing & ACID Properties",
        "question_text": "Explain ACID properties of database transactions. What happens if Atomicity or Consistency is violated?",
    },
    {
        "year": 2023,
        "marks": 7,
        "unit_or_topic_guess": "Concurrency Control & Two-Phase Locking",
        "question_text": "Explain Two-Phase Locking (2PL) protocol in detail. How does 2PL ensure conflict serializability?",
    },
    {
        "year": 2023,
        "marks": 7,
        "unit_or_topic_guess": "Deadlock Handling in DBMS",
        "question_text": "Explain Deadlock detection and Deadlock prevention mechanisms in DBMS. What are Wait-Die and Wound-Wait schemes?",
    },
    {
        "year": 2023,
        "marks": 7,
        "unit_or_topic_guess": "Indexing & B/B+ Trees",
        "question_text": "Explain the structure of B-Tree and B+ Tree with insertion and deletion operations. Why are B+ trees preferred in database indexing?",
    },
    {
        "year": 2023,
        "marks": 7,
        "unit_or_topic_guess": "Relational Algebra & Calculus",
        "question_text": "Write relational algebra expressions for: Selection, Projection, Cartesian Product, and Natural Join.",
    },
    {
        "year": 2023,
        "marks": 7,
        "unit_or_topic_guess": "SQL Queries & Views",
        "question_text": "Explain Nested Queries and Correlated Subqueries in SQL with practical examples.",
    },
]


def load_demo_data(db: Session) -> Subject:
    """
    Creates or resets the realistic 'Database Management Systems (CS-501)' demo subject
    with 4 years of university exam questions, automated TF-IDF repeated question detection,
    transparent priority scores, pre-cached notes, and practice quizzes.
    """
    # Check if demo subject already exists; if so, delete it and recreate fresh
    existing = db.query(Subject).filter(Subject.code == DEMO_SUBJECT["code"]).first()
    if existing:
        db.delete(existing)
        db.commit()

    # 1. Create Subject
    subject = Subject(name=DEMO_SUBJECT["name"], code=DEMO_SUBJECT["code"])
    db.add(subject)
    db.flush()

    # 2. Create Paper records for 2020, 2021, 2022, 2023
    years = [2020, 2021, 2022, 2023]
    paper_map = {}
    for y in years:
        paper = Paper(
            subject_id=subject.id,
            year=y,
            filename=f"DBMS_RGPV_{y}_EndSem.pdf",
            filepath=f"uploads/DBMS_RGPV_{y}_EndSem.pdf",
            extracted_text=f"Rajiv Gandhi Proudyogiki Vishwavidyalaya, Bhopal\nCredit Based Grading System\nCS-501 Database Management Systems\nExam Year: {y}\nTime: 3 Hours  Maximum Marks: 70\nNote: Attempt all questions. Internal choice is given.",
            is_ocr=False,
        )
        db.add(paper)
        db.flush()
        paper_map[y] = paper

    # 3. Create Questions
    question_records = []
    question_dicts_for_analysis = []

    for item in DEMO_QUESTIONS:
        q = Question(
            subject_id=subject.id,
            paper_id=paper_map[item["year"]].id,
            year=item["year"],
            question_text=item["question_text"],
            marks=item["marks"],
            unit_or_topic_guess=item["unit_or_topic_guess"],
        )
        db.add(q)
        db.flush()
        question_records.append(q)
        question_dicts_for_analysis.append({
            "id": q.id,
            "year": q.year,
            "marks": q.marks,
            "unit_or_topic_guess": q.unit_or_topic_guess,
            "question_text": q.question_text,
        })

    # 4. Run Topic Aggregation & Priority Scoring
    aggregated_topics = aggregate_topics_and_priorities(
        questions=question_dicts_for_analysis,
        all_subject_years=years,
    )

    topic_records_map = {}
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
        topic_records_map[t_data["name"]] = topic_obj

        # Link questions to this topic
        for q in question_records:
            if q.unit_or_topic_guess == t_data["name"]:
                q.topic_id = topic_obj.id

        # Pre-seed English and Hindi revision notes
        notes_en = get_offline_fallback_notes(topic_obj.name, subject.name, "en")
        notes_hi = get_offline_fallback_notes(topic_obj.name, subject.name, "hi")
        db.add(NoteCache(topic_id=topic_obj.id, language="en", content=notes_en))
        db.add(NoteCache(topic_id=topic_obj.id, language="hi", content=notes_hi))

        # Pre-seed practice quiz
        quiz_data = get_offline_fallback_quiz(topic_obj.name, subject.name)
        db.add(QuizCache(topic_id=topic_obj.id, quiz_json=json.dumps(quiz_data)))

    # 5. Run Repeated Question Detection (TF-IDF + Cosine Similarity)
    repeated_groups = find_repeated_questions(question_dicts_for_analysis, similarity_threshold=0.48)
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
    db.refresh(subject)
    logger.info(f"Loaded demo dataset successfully for subject: {subject.name} ({subject.code})")
    return subject
