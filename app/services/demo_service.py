import json
import logging
from sqlalchemy.orm import Session
from app.models import Subject, Paper, Question, Topic, RepeatedQuestionGroup, NoteCache, QuizCache
from app.services.analysis_service import find_repeated_questions, aggregate_topics_and_priorities
from app.services.ai_service import get_offline_fallback_notes, get_offline_fallback_quiz

logger = logging.getLogger("examsense.demo_service")

# ---------------------------------------------------------------------------
# Demo 1: College / University (Database Management Systems CS-501)
# ---------------------------------------------------------------------------
COLLEGE_DEMO_SUBJECT = {
    "name": "Database Management Systems",
    "code": "CS-501",
    "exam_type": "College/University",
}

COLLEGE_DEMO_QUESTIONS = [
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
        "unit_or_topic_guess": "ER Modeling & Schema Mapping",
        "question_text": "Explain the step-by-step reduction of an ER diagram with weak entities and composite attributes into Relational Schema.",
    },
    {
        "year": 2022,
        "marks": 7,
        "unit_or_topic_guess": "Indexing & B/B+ Trees",
        "question_text": "Differentiate between Primary Index, Clustering Index and Secondary Index. Explain Dense vs Sparse indices.",
    },
    {
        "year": 2022,
        "marks": 7,
        "unit_or_topic_guess": "Database Recovery Techniques",
        "question_text": "What is Checkpointing in DBMS? How does checkpointing reduce recovery overhead during system restart?",
    },
    {
        "year": 2022,
        "marks": 7,
        "unit_or_topic_guess": "SQL Queries & Views",
        "question_text": "Explain Views in SQL. What are updatable views and what constraints must be satisfied to update records through a view?",
    },
    {
        "year": 2022,
        "marks": 7,
        "unit_or_topic_guess": "Concurrency Control & Two-Phase Locking",
        "question_text": "Explain Timestamp-Ordering Protocol for concurrency control. Differentiate Timestamp ordering with 2PL.",
    },
    {
        "year": 2022,
        "marks": 7,
        "unit_or_topic_guess": "Database Architecture & Data Models",
        "question_text": "Compare Hierarchical, Network, and Relational Data Models with schemas and relationship structures.",
    },

    # 2023 Paper
    {
        "year": 2023,
        "marks": 7,
        "unit_or_topic_guess": "Normalization & Normal Forms",
        "question_text": "Given a relation R(A, B, C, D, E) with FDs: A->BC, CD->E, B->D, E->A. Find candidate keys and determine the highest normal form.",
    },
    {
        "year": 2023,
        "marks": 7,
        "unit_or_topic_guess": "Transaction Processing & ACID Properties",
        "question_text": "Explain ACID properties of transactions. How does DBMS ensure Isolation using lock manager?",
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

# Legacy alias for backward compatibility
DEMO_SUBJECT = COLLEGE_DEMO_SUBJECT
DEMO_QUESTIONS = COLLEGE_DEMO_QUESTIONS


# ---------------------------------------------------------------------------
# Demo 2: School Board (Class 10 Science)
# ---------------------------------------------------------------------------
SCHOOL_DEMO_SUBJECT = {
    "name": "Class 10 Science",
    "code": "SCI-10",
    "exam_type": "School Board",
}

SCHOOL_DEMO_QUESTIONS = [
    # 2020 Paper
    {
        "year": 2020,
        "marks": 5,
        "unit_or_topic_guess": "Chemical Reactions & Equations",
        "question_text": "What is a balanced chemical equation? Write balanced equations for: (a) Hydrogen + Chlorine -> Hydrogen Chloride, (b) Barium chloride + Aluminium sulphate -> Barium sulphate + Aluminium chloride.",
    },
    {
        "year": 2020,
        "marks": 5,
        "unit_or_topic_guess": "Electricity & Ohm's Law",
        "question_text": "State Ohm's Law. Draw a labeled schematic diagram of an electric circuit to verify Ohm's Law. Define electric resistance and its SI unit.",
    },
    {
        "year": 2020,
        "marks": 5,
        "unit_or_topic_guess": "Life Processes & Nutrition",
        "question_text": "Explain the process of photosynthesis in green plants. Write the balanced chemical equation and mention the three major events occurring during this process.",
    },
    {
        "year": 2020,
        "marks": 5,
        "unit_or_topic_guess": "Light: Reflection and Refraction",
        "question_text": "State the laws of refraction of light. Define refractive index and Snell's law with mathematical formulation.",
    },
    {
        "year": 2020,
        "marks": 5,
        "unit_or_topic_guess": "Acids, Bases and Salts",
        "question_text": "What happens when an acid reacts with a metal? Give balanced chemical equation. Why should curd and sour substances not be kept in brass and copper vessels?",
    },

    # 2021 Paper
    {
        "year": 2021,
        "marks": 5,
        "unit_or_topic_guess": "Chemical Reactions & Equations",
        "question_text": "Differentiate between combination, decomposition, displacement, and double displacement reactions with one balanced example for each.",
    },
    {
        "year": 2021,
        "marks": 5,
        "unit_or_topic_guess": "Electricity & Ohm's Law",
        "question_text": "Derive the mathematical expression for equivalent resistance of three resistors R1, R2, R3 connected in parallel. State Joule's law of heating.",
    },
    {
        "year": 2021,
        "marks": 5,
        "unit_or_topic_guess": "Life Processes & Nutrition",
        "question_text": "Draw a neat labeled diagram of human digestive system. Mention the functions of salivary amylase, bile juice, and trypsin in digestion.",
    },
    {
        "year": 2021,
        "marks": 5,
        "unit_or_topic_guess": "Light: Reflection and Refraction",
        "question_text": "Draw ray diagrams showing the image formed by a concave mirror when an object is placed (a) at Center of curvature (C), (b) between Focus (F) and Pole (P).",
    },
    {
        "year": 2021,
        "marks": 5,
        "unit_or_topic_guess": "Acids, Bases and Salts",
        "question_text": "What is the pH scale? How does pH change along the scale from 0 to 14? Explain the importance of pH in everyday life (soil, tooth decay, digestive system).",
    },

    # 2022 Paper
    {
        "year": 2022,
        "marks": 5,
        "unit_or_topic_guess": "Chemical Reactions & Equations",
        "question_text": "Define oxidation and reduction (Redox reactions). Identify the substance oxidized and reduced in: CuO + H2 -> Cu + H2O and MnO2 + 4HCl -> MnCl2 + 2H2O + Cl2.",
    },
    {
        "year": 2022,
        "marks": 5,
        "unit_or_topic_guess": "Electricity & Ohm's Law",
        "question_text": "State Ohm's Law. On what factors does the resistance of a cylindrical conductor depend? Define resistivity and state its SI unit.",
    },
    {
        "year": 2022,
        "marks": 5,
        "unit_or_topic_guess": "Life Processes & Nutrition",
        "question_text": "Differentiate between aerobic and anaerobic respiration. Mention the pathways of breakdown of glucose in cytoplasm, mitochondria, and yeast.",
    },
    {
        "year": 2022,
        "marks": 5,
        "unit_or_topic_guess": "Light: Reflection and Refraction",
        "question_text": "Define power of a lens and state its SI unit (Dioptre). A convex lens forms a real, inverted image at 50 cm. Find object distance if magnification is -1.",
    },
    {
        "year": 2022,
        "marks": 5,
        "unit_or_topic_guess": "Acids, Bases and Salts",
        "question_text": "Write the chemical formula and preparation method of Plaster of Paris (POP) and Bleaching Powder. Why should POP be stored in moisture-proof containers?",
    },

    # 2023 Paper
    {
        "year": 2023,
        "marks": 5,
        "unit_or_topic_guess": "Chemical Reactions & Equations",
        "question_text": "What is a neutralization reaction? Explain why respiration is considered an exothermic reaction. Write balanced equations.",
    },
    {
        "year": 2023,
        "marks": 5,
        "unit_or_topic_guess": "Electricity & Ohm's Law",
        "question_text": "An electric lamp of 100 ohms, a toaster of 50 ohms, and a water filter of 500 ohms are connected in parallel to 220V. Find equivalent resistance and current drawn.",
    },
    {
        "year": 2023,
        "marks": 5,
        "unit_or_topic_guess": "Life Processes & Nutrition",
        "question_text": "Draw a schematic diagram of the human heart showing blood circulation. Explain double circulation and why it is necessary in birds and mammals.",
    },
    {
        "year": 2023,
        "marks": 5,
        "unit_or_topic_guess": "Light: Reflection and Refraction",
        "question_text": "State the mirror formula and magnification formula. A concave mirror has focal length 15 cm. At what distance should an object be placed to get an image at 30 cm?",
    },
    {
        "year": 2023,
        "marks": 5,
        "unit_or_topic_guess": "Acids, Bases and Salts",
        "question_text": "Why does distilled water not conduct electricity whereas rain water does? What is universal indicator and how does it measure acid-base strength?",
    },
]


# ---------------------------------------------------------------------------
# Demo 3: Competitive Exam (General Science & Physics)
# ---------------------------------------------------------------------------
COMPETITIVE_DEMO_SUBJECT = {
    "name": "General Science & Physics",
    "code": "COMP-PHY",
    "exam_type": "Competitive Exam",
}

COMPETITIVE_DEMO_QUESTIONS = [
    # 2020 Paper
    {
        "year": 2020,
        "marks": 4,
        "unit_or_topic_guess": "Mechanics & Newton's Laws",
        "question_text": "State Newton's Second Law of Motion. Derive F = ma and explain conservation of linear momentum with application to rocket propulsion and gun recoil.",
    },
    {
        "year": 2020,
        "marks": 4,
        "unit_or_topic_guess": "Thermodynamics & Heat Transfer",
        "question_text": "Explain the First and Second Laws of Thermodynamics. Calculate the efficiency of a Carnot heat engine operating between 500 K and 300 K.",
    },
    {
        "year": 2020,
        "marks": 4,
        "unit_or_topic_guess": "Modern Physics & Photoelectric Effect",
        "question_text": "Explain Einstein's Photoelectric equation: hv = phi + KE_max. Define threshold frequency, stopping potential, and work function with characteristic curves.",
    },
    {
        "year": 2020,
        "marks": 4,
        "unit_or_topic_guess": "Electrostatics & Current Electricity",
        "question_text": "State Coulomb's Law and Gauss's Law in electrostatics. Apply Gauss's Law to find the electric field intensity due to an infinitely long uniformly charged wire.",
    },
    {
        "year": 2020,
        "marks": 4,
        "unit_or_topic_guess": "Ray Optics & Wave Motion",
        "question_text": "Explain Total Internal Reflection (TIR) and write the relation between refractive index and critical angle. Mention applications in optical fibers and mirage.",
    },

    # 2021 Paper
    {
        "year": 2021,
        "marks": 4,
        "unit_or_topic_guess": "Mechanics & Newton's Laws",
        "question_text": "Explain work-energy theorem. Differentiate between elastic and inelastic collision in one dimension. Show that kinetic energy is conserved in elastic collision.",
    },
    {
        "year": 2021,
        "marks": 4,
        "unit_or_topic_guess": "Thermodynamics & Heat Transfer",
        "question_text": "Differentiate between isothermal and adiabatic processes. Derive the work done during isothermal expansion of an ideal gas (W = nRT ln(V2/V1)).",
    },
    {
        "year": 2021,
        "marks": 4,
        "unit_or_topic_guess": "Modern Physics & Photoelectric Effect",
        "question_text": "State de Broglie's hypothesis of matter waves. Derive the expression for de Broglie wavelength of an electron accelerated through potential difference V.",
    },
    {
        "year": 2021,
        "marks": 4,
        "unit_or_topic_guess": "Electrostatics & Current Electricity",
        "question_text": "State Kirchhoff's Current Law (KCL) and Voltage Law (KVL). Derive Wheatstone Bridge balance condition P/Q = R/S.",
    },
    {
        "year": 2021,
        "marks": 4,
        "unit_or_topic_guess": "Ray Optics & Wave Motion",
        "question_text": "State Huygens' Principle. Use Huygens' wave theory to prove the laws of reflection and refraction at a plane surface.",
    },

    # 2022 Paper
    {
        "year": 2022,
        "marks": 4,
        "unit_or_topic_guess": "Mechanics & Newton's Laws",
        "question_text": "State Kepler's Three Laws of Planetary Motion. Derive relation between acceleration due to gravity g and universal gravitational constant G.",
    },
    {
        "year": 2022,
        "marks": 4,
        "unit_or_topic_guess": "Thermodynamics & Heat Transfer",
        "question_text": "State the Zeroth, First and Second laws of thermodynamics. Explain entropy as a measure of disorder in irreversible processes.",
    },
    {
        "year": 2022,
        "marks": 4,
        "unit_or_topic_guess": "Modern Physics & Photoelectric Effect",
        "question_text": "Explain Bohr's postulates for hydrogen atom. Derive expression for radius of nth orbit and energy of electron in nth Bohr orbit.",
    },
    {
        "year": 2022,
        "marks": 4,
        "unit_or_topic_guess": "Electrostatics & Current Electricity",
        "question_text": "Derive expression for capacitance of a parallel plate capacitor with dielectric slab inserted. Explain energy stored in a charged capacitor (U = 1/2 CV^2).",
    },
    {
        "year": 2022,
        "marks": 4,
        "unit_or_topic_guess": "Ray Optics & Wave Motion",
        "question_text": "Explain Young's Double Slit Experiment (YDSE). Derive the expression for fringe width beta = lambda*D/d for constructive and destructive interference.",
    },

    # 2023 Paper
    {
        "year": 2023,
        "marks": 4,
        "unit_or_topic_guess": "Mechanics & Newton's Laws",
        "question_text": "State Newton's Second Law of Motion. Explain centripetal acceleration and derive safe velocity of a vehicle on banked circular road.",
    },
    {
        "year": 2023,
        "marks": 4,
        "unit_or_topic_guess": "Thermodynamics & Heat Transfer",
        "question_text": "Calculate efficiency of Carnot cycle operating between temperatures T1 and T2. Why can practical efficiency never reach 100%?",
    },
    {
        "year": 2023,
        "marks": 4,
        "unit_or_topic_guess": "Modern Physics & Photoelectric Effect",
        "question_text": "Explain photoelectric effect characteristics: effect of intensity, frequency, and potential on photocurrent. Why wave theory fails to explain photoelectric effect.",
    },
    {
        "year": 2023,
        "marks": 4,
        "unit_or_topic_guess": "Electrostatics & Current Electricity",
        "question_text": "State Biot-Savart Law and Ampere's Circuital Law. Find magnetic field at center of a circular loop carrying current I.",
    },
    {
        "year": 2023,
        "marks": 4,
        "unit_or_topic_guess": "Ray Optics & Wave Motion",
        "question_text": "Explain Total Internal Reflection and conditions for it. Calculate critical angle for diamond (n=2.42) and water (n=1.33).",
    },
]


def load_demo_data(db: Session, demo_type: str = "college") -> Subject:
    """
    Creates or reuses one shared read-only demo subject for:
    - 'college': Database Management Systems (CS-501)
    - 'school': Class 10 Science (SCI-10)
    - 'competitive': General Science & Physics (COMP-PHY)
    """
    clean_type = (demo_type or "college").lower().strip()
    if "school" in clean_type:
        config = SCHOOL_DEMO_SUBJECT
        q_bank = SCHOOL_DEMO_QUESTIONS
    elif "comp" in clean_type:
        config = COMPETITIVE_DEMO_SUBJECT
        q_bank = COMPETITIVE_DEMO_QUESTIONS
    else:
        config = COLLEGE_DEMO_SUBJECT
        q_bank = COLLEGE_DEMO_QUESTIONS

    # Re-use existing shared demo subject if already populated
    existing = db.query(Subject).filter(Subject.code == config["code"]).first()
    if existing and len(existing.topics) > 0:
        logger.info(f"Reusing existing shared demo subject '{existing.name}' ({existing.code}) [ID: {existing.id}].")
        existing.is_demo = True
        existing.owner_id = "demo"
        existing.exam_type = config.get("exam_type", "General")
        db.commit()
        return existing

    # If exists but empty/corrupt, delete and rebuild
    if existing:
        db.delete(existing)
        db.commit()

    # 1. Create Subject
    subject = Subject(
        name=config["name"],
        code=config["code"],
        exam_type=config.get("exam_type", "General"),
        owner_id="demo",
        is_demo=True,
    )
    db.add(subject)
    db.flush()

    # 2. Create Paper records for 2020, 2021, 2022, 2023
    years = [2020, 2021, 2022, 2023]
    paper_map = {}
    for y in years:
        paper = Paper(
            subject_id=subject.id,
            year=y,
            filename=f"{config['code']}_{y}_Paper.pdf",
            filepath=f"uploads/{config['code']}_{y}_Paper.pdf",
            extracted_text=f"Official Examination Question Paper\nSubject: {config['name']} ({config['code']})\nExam Year: {y}\nTime: 3 Hours  Maximum Marks: 70\nNote: Answer all questions with proper steps.",
            is_ocr=False,
        )
        db.add(paper)
        db.flush()
        paper_map[y] = paper

    # 3. Create Questions
    question_records = []
    question_dicts_for_analysis = []

    for item in q_bank:
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
        notes_en = get_offline_fallback_notes(topic_obj.name, subject.name, "en", subject.exam_type)
        notes_hi = get_offline_fallback_notes(topic_obj.name, subject.name, "hi", subject.exam_type)
        db.add(NoteCache(topic_id=topic_obj.id, language="en", content=notes_en))
        db.add(NoteCache(topic_id=topic_obj.id, language="hi", content=notes_hi))

        # Pre-seed practice quiz
        quiz_data = get_offline_fallback_quiz(topic_obj.name, subject.name, subject.exam_type)
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
