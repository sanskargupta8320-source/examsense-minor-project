import os
import re
import json
import logging
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("examsense.ai_service")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()

# Initialize Google Generative AI
genai_client = None
if GEMINI_API_KEY:
    try:
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_API_KEY)
        genai_client = genai
        logger.info("Google Generative AI configured successfully.")
    except Exception as e:
        logger.warning(f"Could not initialize Google Generative AI: {e}")
else:
    logger.info("No GEMINI_API_KEY detected. AI operations will use heuristic intelligent fallback.")


def get_gemini_model():
    """Returns the Gemini GenerativeModel instance with preferred fallback order."""
    if not genai_client:
        return None
    # Prioritize gemini-1.5-flash or gemini-2.0-flash
    for model_name in ["gemini-1.5-flash", "gemini-2.0-flash", "gemini-1.5-pro", "gemini-pro"]:
        try:
            return genai_client.GenerativeModel(model_name)
        except Exception:
            continue
    try:
        return genai_client.GenerativeModel("gemini-1.5-flash")
    except Exception:
        return None


def clean_and_parse_json(raw_text: str) -> Any:
    """
    Cleans markdown formatting, removes backticks, handles common LLM syntax irregularities,
    and safely loads JSON.
    """
    cleaned = raw_text.strip()
    
    # Strip markdown code blocks like ```json ... ``` or ``` ... ```
    if "```" in cleaned:
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned, re.IGNORECASE)
        if match:
            cleaned = match.group(1).strip()
        else:
            cleaned = cleaned.replace("```json", "").replace("```", "").strip()

    # Sometimes LLMs append conversational text before/after JSON; extract outermost [ ... ] or { ... }
    bracket_match = re.search(r"(\[[\s\S]*\]|\{[\s\S]*\})", cleaned)
    if bracket_match:
        cleaned = bracket_match.group(1).strip()

    # Remove trailing commas before closing braces/brackets (common syntax error)
    cleaned = re.sub(r",\s*([\]}])", r"\1", cleaned)

    return json.loads(cleaned)


# ---------------------------------------------------------------------------
# Feature 2: Question Extraction
# ---------------------------------------------------------------------------

def extract_questions_with_regex_fallback(text: str, year: int) -> List[Dict[str, Any]]:
    """Heuristic fallback to extract questions from university papers when Gemini is offline."""
    lines = text.split("\n")
    questions = []
    current_q = []
    current_num = ""

    # Common university patterns like: "Q.1(a)", "1. (b)", "Question 3", "4 a)", "OR"
    pattern = re.compile(
        r"^(Q(?:uestion)?\s*\.?\s*\d+\s*[\.\:\-\)]?|\d+[\.\)]\s*(?:\([a-zA-Z0-9]+\))?|\([a-zA-Z0-9]+\))\s*(.*)",
        re.IGNORECASE,
    )

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        
        # Check if new question line
        match = pattern.match(stripped)
        if match and len(stripped) > 10:
            if current_q:
                q_text = " ".join(current_q).strip()
                if len(q_text) >= 15:
                    questions.append({
                        "question_text": q_text,
                        "marks": 7,
                        "unit_or_topic_guess": "General",
                        "year": year,
                    })
                current_q = []
            current_q.append(stripped)
        elif current_q:
            # Continue previous question
            current_q.append(stripped)

    if current_q:
        q_text = " ".join(current_q).strip()
        if len(q_text) >= 15:
            questions.append({
                "question_text": q_text,
                "marks": 7,
                "unit_or_topic_guess": "General",
                "year": year,
            })

    # If regex found almost nothing (e.g. unnumbered paragraphs), split into paragraphs
    if not questions:
        paras = [p.strip() for p in text.split("\n\n") if len(p.strip()) > 30]
        for p in paras[:15]:
            questions.append({
                "question_text": p,
                "marks": 7,
                "unit_or_topic_guess": "General",
                "year": year,
            })

    return questions


def extract_questions_from_paper(
    paper_text: str, year: int, subject_name: str = ""
) -> List[Dict[str, Any]]:
    """
    Uses Gemini LLM to split an examination paper's raw text into individual questions.
    Returns strict JSON:
        [{"question_text": str, "marks": int, "unit_or_topic_guess": str, "year": int}]
    Validates and safely retries once if output is malformed.
    """
    model = get_gemini_model()
    if not model:
        logger.info("Using heuristic regex question extractor (no GEMINI_API_KEY).")
        return extract_questions_with_regex_fallback(paper_text, year)

    prompt = f"""You are an expert exam analyzer for Indian university engineering examinations (like RGPV, AKTU, VTU).
Extract all individual questions from the following {year} examination question paper for the subject "{subject_name}".

RAW EXAM PAPER TEXT:
\"\"\"
{paper_text[:12000]}
\"\"\"

INSTRUCTIONS:
1. Identify and split every individual sub-question (e.g., if a question has Q1(a) and Q1(b), output them as separate questions).
2. If marks are specified (e.g. "[7]", "(10 Marks)", "7M"), extract the integer marks. If not stated, default to 7.
3. Guess the core academic topic/concept (e.g., "ER Diagrams", "Normalization", "Concurrency Control", "SQL Queries").
4. Strip out exam header boilerplate (e.g. "Total No. of Questions: 8", "Maximum Marks: 70", "Roll No", "Note: Attempt any five questions").
5. Output ONLY valid JSON adhering to this exact schema (no markdown explanations outside the JSON):

[
  {{
    "question_text": "Full text of the question here",
    "marks": 7,
    "unit_or_topic_guess": "Specific Topic Name",
    "year": {year}
  }}
]
"""

    # First attempt
    for attempt in range(2):
        try:
            response = model.generate_content(prompt)
            data = clean_and_parse_json(response.text)
            if isinstance(data, list) and len(data) > 0:
                # Sanitize records
                sanitized = []
                for item in data:
                    if isinstance(item, dict) and "question_text" in item:
                        sanitized.append({
                            "question_text": str(item["question_text"]).strip(),
                            "marks": int(item.get("marks") or 7),
                            "unit_or_topic_guess": str(item.get("unit_or_topic_guess") or "General").strip(),
                            "year": year,
                        })
                if sanitized:
                    return sanitized
        except Exception as err:
            logger.warning(f"Gemini question extraction attempt {attempt+1} failed: {err}")
            # Modify prompt slightly for retry
            prompt += "\nIMPORTANT: Return ONLY a raw JSON array. Do not include any introductory or concluding text."

    logger.warning("Gemini extraction failed after 2 attempts. Falling back to heuristic extractor.")
    return extract_questions_with_regex_fallback(paper_text, year)


# ---------------------------------------------------------------------------
# Feature 3: Topic Normalization and Clustering
# ---------------------------------------------------------------------------

def normalize_topics_with_llm(
    topics_list: List[str], subject_name: str = ""
) -> Dict[str, str]:
    """
    Groups and normalizes similar topic names (e.g. "Normalization", "3NF", "DB Normalization" -> "Normalization & Normal Forms")
    Returns a dictionary mapping original raw topic name -> standardized canonical topic name.
    """
    unique_topics = sorted(list(set(t.strip() for t in topics_list if t and t.strip())))
    if len(unique_topics) <= 1:
        return {t: t for t in unique_topics}

    model = get_gemini_model()
    if not model:
        # Heuristic normalization mapping
        mapping = {}
        for t in unique_topics:
            mapping[t] = t.title()
        return mapping

    prompt = f"""You are an academic curriculum coordinator for the university subject "{subject_name}".
Below is a list of raw topic names extracted from various exam papers:
{json.dumps(unique_topics, indent=2)}

Please cluster and normalize these topics into standardized, coherent syllabus topics (e.g. combine "Normalization", "Normal Forms", "BCNF & 3NF" into "Normalization & Normal Forms"). Aim for approximately 5 to 10 distinct standard topics.

Return a JSON object mapping each raw topic to its canonical normalized name:
{{
  "raw_topic_name_1": "Standard Canonical Name",
  "raw_topic_name_2": "Standard Canonical Name"
}}
"""
    try:
        response = model.generate_content(prompt)
        mapping = clean_and_parse_json(response.text)
        if isinstance(mapping, dict):
            # Ensure all raw topics exist in mapping
            for t in unique_topics:
                if t not in mapping:
                    mapping[t] = t
            return mapping
    except Exception as e:
        logger.warning(f"Topic normalization LLM call failed: {e}")

    return {t: t for t in unique_topics}


# ---------------------------------------------------------------------------
# Feature 6: Revision Notes Generation (with Hindi/English support)
# ---------------------------------------------------------------------------

def generate_revision_notes(
    topic_name: str,
    subject_name: str,
    sample_questions: List[str] = None,
    language: str = "en",
) -> str:
    """
    Generates concise, exam-oriented revision notes formatted in clean Markdown.
    Includes: Key points, definitions, formulas/diagrams, and one clear example.
    Supports English ('en') and Hinglish / Hindi-English student style ('hi').
    """
    sample_qs_str = "\n".join(f"- {q}" for q in (sample_questions or [])[:4])
    lang_instruction = (
        "Write in student-friendly, natural Hinglish (Hindi written in English alphabet, e.g. 'Normalization ka main purpose redundancy ko remove karna hota hai.'). This makes it easy for Indian students to grasp quickly."
        if language == "hi"
        else "Write in clear, formal, exam-oriented English with crisp bullet points."
    )

    model = get_gemini_model()
    if not model:
        # High quality offline fallback notes
        return get_offline_fallback_notes(topic_name, subject_name, language)

    prompt = f"""You are a top-rank university engineering professor creating last-minute revision notes for exam preparation.
Subject: {subject_name}
Topic: {topic_name}

Past Exam Questions on this topic:
{sample_qs_str}

Language Instruction: {lang_instruction}

Create high-yield, exam-winning revision notes formatted in GitHub Markdown with these exact sections:
1. 📌 **Quick Definition & Concept** (2-3 punchy sentences)
2. 🔑 **Must-Remember Key Points** (5 high-yield bullet points that examiners look for)
3. 📐 **Formulas / Architecture / Rules** (Clear ASCII representation or rules)
4. 💡 **Solved University Exam Example** (A classic 7-mark question solved simply)
5. ⚠️ **Viva & Exam Tips** (Common mistakes students make and what examiner checks)

Keep it concise, actionable, and strictly relevant to college semester examinations.
"""

    try:
        response = model.generate_content(prompt)
        if response.text and len(response.text.strip()) > 100:
            return response.text.strip()
    except Exception as e:
        logger.warning(f"Gemini notes generation failed: {e}")

    return get_offline_fallback_notes(topic_name, subject_name, language)


def get_offline_fallback_notes(topic_name: str, subject_name: str, language: str = "en") -> str:
    """Pre-crafted structured notes when offline or API key absent."""
    if language == "hi":
        return f"""# 📝 Revision Notes: {topic_name}
*Subject: {subject_name} (Language: Hinglish / Hindi-English)*

---

### 📌 Quick Definition & Concept
**{topic_name}** ka core objective exam point of view se theoretical understanding aur practical implementation dono me master hona hai. Is concept se har saal 7 ya 14 marks ke questions zaroor aate hain.

### 🔑 Must-Remember Key Points
1. **Core Purpose:** System ki efficiency, data integrity aur reliability ko maintain karna.
2. **Standard Terminology:** Exam me standard definitions aur technical keywords use karein taaki full marks milein.
3. **Classification:** Is topic ke standard types aur variations ko step-by-step point format me likhein.
4. **Comparison Matrix:** Difference table (e.g., Pros vs Cons) draw karne par examiner full marks deta hai.
5. **Real-world application:** Theory ke sath practical banking ya e-commerce use-case zaroor mention karein.

### 📐 Formulas / Architecture
```
[ Input / Entity ] ---> [ Processing / Algorithm ] ---> [ Optimized Result ]
        |                         |                              |
        v                         v                              v
   Constraint Check          State Validation            Consistency Check
```

### 💡 Solved University Exam Example
**Q: Explain {topic_name} with an example.**
- **Step 1:** Define the concept with formal terminology.
- **Step 2:** Draw the architectural / procedural diagram.
- **Step 3:** Show input data and step-by-step transformation.
- **Conclusion:** State why this approach is optimal in database / software systems.

### ⚠️ Viva & Exam Tips
- **Viva Tip:** Examiner aksar 'Edge cases' aur 'Why do we need this instead of previous technique?' puchte hain.
- **Exam Tip:** Diagram ko hamesha pencil aur clean labeling ke sath draw karein. Bullet points me likhein, lambe paragraphs avoid karein.
"""

    return f"""# 📝 Revision Notes: {topic_name}
*Subject: {subject_name} | ExamSense Quick Study Material*

---

### 📌 Quick Definition & Concept
**{topic_name}** represents a fundamental pillar within {subject_name}. In university examination patterns (such as RGPV and autonomous universities), questions from this topic carry high weightage (7 to 14 marks) and evaluate conceptual clarity, architectural modeling, and analytical problem-solving.

### 🔑 Must-Remember Key Points
1. **Fundamental Objective:** Designed to eliminate redundancy, optimize runtime complexity, and ensure robust architectural guarantees.
2. **Core Axioms & Rules:** Always list the formal mathematical or operational conditions governing the behavior of this topic.
3. **Step-by-Step Procedure:** When asked for an algorithm or process, number your steps sequentially with clear pre-conditions and post-conditions.
4. **Comparative Analysis:** Prepare a 4-point comparison table contrasting this technique with alternative standard paradigms.
5. **Trade-offs:** Mention trade-offs explicitly (e.g., storage overhead vs. query execution latency).

### 📐 Architecture / Structural Flow
```
+-----------------------------------------------------------+
|                      {topic_name.upper()}                     |
+-----------------------------------------------------------+
           |                                     |
           v                                     v
   [ Component / Step A ]               [ Component / Step B ]
           |                                     |
           +-----------------+-------------------+
                             |
                             v
                [ Validated / Desired State ]
```

### 💡 Solved University Exam Example
**Question:** Explain the mechanism and significance of {topic_name}.
- **Approach:**
  1. Define the formal scope and mathematical/logical constraints.
  2. Illustrate with a concrete scenario (e.g., Employee-Department schema or Transaction Log).
  3. Detail the transformation step-by-step and prove correctness.
- **Key Takeaway:** Demonstrates complete mastery of both theoretical foundation and practical application.

### ⚠️ Viva & Exam Tips
- **Common Mistake:** Omitting the diagram or failing to state the boundary conditions.
- **Viva Examiner Favorite:** "Under what specific condition does this approach fail or become inefficient?"
- **Presentation Rule:** Always underline key technical terms and wrap final solutions in a rectangular box.
"""


# ---------------------------------------------------------------------------
# Feature 6: Practice Quiz Generator (5 MCQs with Explanations)
# ---------------------------------------------------------------------------

def generate_practice_quiz(
    topic_name: str, subject_name: str, sample_questions: List[str] = None
) -> List[Dict[str, Any]]:
    """
    Generates 5 high-quality exam MCQs with 4 options, the correct answer index (0-3),
    and a clear academic explanation.
    """
    model = get_gemini_model()
    if not model:
        return get_offline_fallback_quiz(topic_name, subject_name)

    sample_qs_str = "\n".join(f"- {q}" for q in (sample_questions or [])[:3])

    prompt = f"""You are a college exam quiz generator.
Subject: {subject_name}
Topic: {topic_name}

Past questions:
{sample_qs_str}

Generate exactly 5 challenging, exam-oriented Multiple Choice Questions (MCQs) testing core concepts of "{topic_name}".
Return ONLY a valid JSON array adhering strictly to this format:

[
  {{
    "id": 1,
    "question": "Clear, precise question text?",
    "options": ["Option A", "Option B", "Option C", "Option D"],
    "correct_index": 0,
    "explanation": "Clear 1-2 sentence explanation of why this answer is correct."
  }}
]

Make sure:
- 'options' has exactly 4 items.
- 'correct_index' is an integer between 0 and 3.
- Questions test fundamental viva and semester exam concepts.
"""

    try:
        response = model.generate_content(prompt)
        data = clean_and_parse_json(response.text)
        if isinstance(data, list) and len(data) >= 3:
            sanitized_quiz = []
            for i, item in enumerate(data[:5]):
                if (
                    isinstance(item, dict)
                    and "question" in item
                    and "options" in item
                    and len(item["options"]) == 4
                ):
                    correct_idx = int(item.get("correct_index", 0))
                    if correct_idx < 0 or correct_idx > 3:
                        correct_idx = 0
                    sanitized_quiz.append({
                        "id": i + 1,
                        "question": str(item["question"]),
                        "options": [str(opt) for opt in item["options"]],
                        "correct_index": correct_idx,
                        "explanation": str(item.get("explanation", "Correct based on core principles.")),
                    })
            if len(sanitized_quiz) >= 3:
                return sanitized_quiz
    except Exception as e:
        logger.warning(f"Gemini quiz generation failed: {e}")

    return get_offline_fallback_quiz(topic_name, subject_name)


def get_offline_fallback_quiz(topic_name: str, subject_name: str) -> List[Dict[str, Any]]:
    """Pre-built standard questions for robust offline operation."""
    # Check if topic relates to DBMS
    t_lower = topic_name.lower()
    if "normal" in t_lower:
        return [
            {
                "id": 1,
                "question": "Which Normal Form strictly eliminates transitive functional dependencies?",
                "options": ["First Normal Form (1NF)", "Second Normal Form (2NF)", "Third Normal Form (3NF)", "Boyce-Codd Normal Form (BCNF)"],
                "correct_index": 2,
                "explanation": "3NF requires that a relation is in 2NF and no non-prime attribute is transitively dependent on the primary key."
            },
            {
                "id": 2,
                "question": "What is the primary condition for a relation to be in Boyce-Codd Normal Form (BCNF)?",
                "options": ["Every determinant must be a super key", "All multi-valued dependencies are removed", "No partial dependencies exist", "Attributes must be atomic only"],
                "correct_index": 0,
                "explanation": "In BCNF, for every functional dependency X -> Y, X must be a super key of the relation."
            },
            {
                "id": 3,
                "question": "A relation has a composite primary key (A, B). If an attribute C depends solely on A, which normal form is violated?",
                "options": ["1NF", "2NF", "3NF", "4NF"],
                "correct_index": 1,
                "explanation": "A partial dependency exists where a non-prime attribute depends on part of a composite key, violating 2NF."
            },
            {
                "id": 4,
                "question": "What type of dependency is addressed by Fourth Normal Form (4NF)?",
                "options": ["Join Dependencies", "Partial Dependencies", "Transitive Dependencies", "Multi-valued Dependencies"],
                "correct_index": 3,
                "explanation": "4NF deals with multi-valued dependencies (MVDs) where independent attributes are multi-valuedly related."
            },
            {
                "id": 5,
                "question": "Which normalization property guarantees that the original table can be accurately reconstructed without spurious tuples?",
                "options": ["Lossless Join Decomposition", "Dependency Preservation", "Atomic Value Invariance", "Referential Integrity"],
                "correct_index": 0,
                "explanation": "Lossless join decomposition ensures natural join of decomposed relations yields the exact original relation without extra phantom rows."
            }
        ]
    elif "transaction" in t_lower or "acid" in t_lower or "concurrency" in t_lower:
        return [
            {
                "id": 1,
                "question": "Which ACID property guarantees that all operations of a transaction succeed, or none do?",
                "options": ["Atomicity", "Consistency", "Isolation", "Durability"],
                "correct_index": 0,
                "explanation": "Atomicity (all-or-nothing property) ensures transaction operations are executed as an indivisible atomic unit."
            },
            {
                "id": 2,
                "question": "Which database recovery component is primarily responsible for ensuring the Durability property?",
                "options": ["Lock Manager", "Write-Ahead Log (WAL)", "Query Optimizer", "Parser"],
                "correct_index": 1,
                "explanation": "Write-Ahead Logging writes all changes to non-volatile disk logs before committing, guaranteeing durability across crashes."
            },
            {
                "id": 3,
                "question": "In Two-Phase Locking (2PL), when does the shrinking phase begin?",
                "options": ["When the first lock is acquired", "When the first lock is released", "When the transaction commits", "When deadlock is detected"],
                "correct_index": 1,
                "explanation": "Once a transaction releases any lock, it enters the shrinking phase and can no longer acquire any new locks."
            },
            {
                "id": 4,
                "question": "What is the Dirty Read concurrency problem?",
                "options": ["Reading data that was never written", "Reading uncommitted changes made by another active transaction", "Two transactions overwriting each other", "Reading different values for the same key in a transaction"],
                "correct_index": 1,
                "explanation": "A dirty read occurs when Transaction A reads modifications made by Transaction B before B has committed (and B might rollback)."
            },
            {
                "id": 5,
                "question": "Which graph algorithm is standardly used by database engines to detect deadlocks?",
                "options": ["Dijkstra's Algorithm", "Cycle detection in Wait-For Graph (WFG)", "Kruskal's Minimum Spanning Tree", "Topological Sort"],
                "correct_index": 1,
                "explanation": "A cycle in a directed Wait-For Graph indicates a circular wait condition, which defines a deadlock."
            }
        ]
    else:
        return [
            {
                "id": 1,
                "question": f"What is the primary objective of studying {topic_name} in {subject_name}?",
                "options": [
                    f"To optimize performance and eliminate design flaws in {topic_name}",
                    "To increase memory footprint unnecessarily",
                    "To bypass standard validation checks",
                    "To restrict modular architecture"
                ],
                "correct_index": 0,
                "explanation": f"Understanding {topic_name} ensures robust system design, correctness, and optimal resource utilization."
            },
            {
                "id": 2,
                "question": f"Which of the following is a key advantage of applying {topic_name}?",
                "options": [
                    "Decreases system maintainability",
                    "Provides structural consistency and predictable behavior",
                    "Forces all operations to run sequentially in one thread",
                    "Disables error reporting"
                ],
                "correct_index": 1,
                "explanation": f"Applying {topic_name} standardizes system architecture and guarantees reliable, consistent behavior."
            },
            {
                "id": 3,
                "question": f"In a university examination question regarding {topic_name}, what earns the highest marks?",
                "options": [
                    "Writing a single paragraph without headings",
                    "Clear definitions, well-labeled diagrams, and step-by-step examples",
                    "Leaving the question unanswered",
                    "Copying questions from previous pages"
                ],
                "correct_index": 1,
                "explanation": "Examiners reward structured answers with clear definitions, diagrams, and illustrative examples."
            },
            {
                "id": 4,
                "question": f"What is a common pitfall or misconception regarding {topic_name}?",
                "options": [
                    "It has no real-world application",
                    "Assuming it works without respecting underlying boundary conditions",
                    "It requires no computational resources",
                    "It cannot be combined with other engineering concepts"
                ],
                "correct_index": 1,
                "explanation": "Ignoring boundary constraints is the most frequent reason for design failures in real-world systems."
            },
            {
                "id": 5,
                "question": f"Which metric is most commonly evaluated when testing {topic_name}?",
                "options": [
                    "Time and Space Efficiency / Reliability",
                    "Color scheme of the server chassis",
                    "Font size of code comments",
                    "Operating system wallpaper"
                ],
                "correct_index": 0,
                "explanation": "Algorithmic efficiency, time complexity, and operational reliability are the core metrics tested in exams."
            }
        ]
