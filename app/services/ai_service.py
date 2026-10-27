import os
import re
import json
import time
import logging
import hashlib
from typing import List, Dict, Any, Optional, Tuple
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("examsense.ai_service")

# Custom exceptions for explicit AI failures
class AIUnavailableError(Exception):
    """Raised when an API key is configured but AI service cannot be reached (quota/auth/error)."""
    pass


class AIQuotaExhaustedError(AIUnavailableError):
    """Specific exception when Gemini free-tier quota (429 / RESOURCE_EXHAUSTED) or daily budget is reached."""
    pass


GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
# Check for dummy placeholder
if GEMINI_API_KEY in ["your_gemini_api_key_here", "your_actual_gemini_api_key_here"]:
    GEMINI_API_KEY = ""

DEFAULT_GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip() or "gemini-2.5-flash"

# Fallback candidate list: [GEMINI_MODEL, "gemini-2.5-flash", "gemini-2.0-flash", "gemini-flash-latest", "gemini-1.5-flash"]
RAW_FALLBACK_MODELS = [
    DEFAULT_GEMINI_MODEL,
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-flash-latest",
    "gemini-1.5-flash",
]
CANDIDATE_MODELS = []
for _m in RAW_FALLBACK_MODELS:
    if _m and _m not in CANDIDATE_MODELS:
        CANDIDATE_MODELS.append(_m)


def get_candidate_models() -> List[str]:
    """Returns candidate fallback model list."""
    return list(CANDIDATE_MODELS)


WORKING_MODEL: Optional[str] = DEFAULT_GEMINI_MODEL
GEMINI_WORKING: bool = bool(GEMINI_API_KEY)
LAST_AI_ERROR: Optional[str] = None if GEMINI_API_KEY else "No GEMINI_API_KEY provided"
AI_FALLBACK_ACTIVE: bool = not bool(GEMINI_API_KEY)

# ---------------------------------------------------------------------------
# In-App AI Daily Budget Guard & Quota Tracking
# ---------------------------------------------------------------------------
AI_DAILY_CALL_LIMIT = int(os.getenv("AI_DAILY_CALL_LIMIT", "18"))
_ai_call_budget: Dict[str, Any] = {
    "date": time.strftime("%Y-%m-%d"),
    "count": 0,
}

QUOTA_EXHAUSTED_UNTIL: Optional[float] = None
QUOTA_MESSAGE: Optional[str] = None
LAST_DEEP_HEALTH_CHECK_TIME: float = 0.0


def parse_retry_delay(err_text: str) -> int:
    """Extracts retry delay in seconds from Gemini 429 quota errors."""
    m_sec = re.search(r"retry_delay\s*\{\s*seconds:\s*(\d+)", err_text)
    if m_sec:
        return int(m_sec.group(1))

    m_time = re.search(r"retry in\s+(?:(\d+)\s*h)?\s*(?:(\d+)\s*m)?\s*(?:([\d\.]+)\s*s)?", err_text, re.IGNORECASE)
    if m_time and any(m_time.groups()):
        h = int(m_time.group(1) or 0)
        m = int(m_time.group(2) or 0)
        s = float(m_time.group(3) or 0)
        delay = int(h * 3600 + m * 60 + s)
        if delay > 0:
            return delay

    cleaned = err_text.lower().replace("_", "").replace("-", "")
    if "perday" in cleaned or "requestsperday" in cleaned or "daily" in cleaned:
        return 3600 * 12  # 12 hours for daily limits
    return 60  # 1 minute default for RPM limits


def format_remaining_time(seconds: int) -> str:
    """Formats seconds into human friendly hours and minutes."""
    if seconds <= 0:
        return "a short moment"
    hours = seconds // 3600
    mins = (seconds % 3600) // 60
    if hours > 0:
        return f"{hours}h {mins}m"
    return f"{max(1, mins)}m"


def consume_ai_budget():
    """Checks daily budget limit and active quota lock before allowing an AI call."""
    global QUOTA_EXHAUSTED_UNTIL, QUOTA_MESSAGE
    current_day = time.strftime("%Y-%m-%d")
    if _ai_call_budget["date"] != current_day:
        _ai_call_budget["date"] = current_day
        _ai_call_budget["count"] = 0
        if QUOTA_EXHAUSTED_UNTIL and time.time() > QUOTA_EXHAUSTED_UNTIL:
            QUOTA_EXHAUSTED_UNTIL = None
            QUOTA_MESSAGE = None

    if QUOTA_EXHAUSTED_UNTIL and time.time() < QUOTA_EXHAUSTED_UNTIL:
        rem_sec = int(QUOTA_EXHAUSTED_UNTIL - time.time())
        time_str = format_remaining_time(rem_sec)
        msg = f"Daily free-tier AI quota reached. Resets in ~{time_str}. You can still explore the sample study plans."
        raise AIQuotaExhaustedError(msg)

    if _ai_call_budget["count"] >= AI_DAILY_CALL_LIMIT:
        msg = f"Daily AI call budget reached ({AI_DAILY_CALL_LIMIT}/{AI_DAILY_CALL_LIMIT} calls used today). You can still view samples or try again tomorrow."
        raise AIQuotaExhaustedError(msg)

    _ai_call_budget["count"] += 1


# Initialize SDK (google-genai preferred, fallback to google-generativeai)
genai_client = None
genai_types = None
USE_NEW_SDK = False

if GEMINI_API_KEY:
    try:
        import google.genai as genai_new
        genai_client = genai_new.Client(api_key=GEMINI_API_KEY)
        USE_NEW_SDK = True
        logger.info("Configured Google GenAI SDK.")
    except Exception:
        try:
            import google.generativeai as genai_old
            genai_old.configure(api_key=GEMINI_API_KEY)
            genai_client = genai_old
            USE_NEW_SDK = False
            logger.info("Configured Google Generative AI (legacy SDK).")
        except Exception as e:
            logger.warning(f"Could not initialize Gemini SDK: {e}")
            LAST_AI_ERROR = "SDK initialization failed"
else:
    logger.info("No GEMINI_API_KEY detected. AI operations will use heuristic intelligent fallback.")
    LAST_AI_ERROR = "No GEMINI_API_KEY provided"


def run_deep_ai_check(force: bool = False) -> bool:
    """
    Tests configured models with a tiny test call and caches the working model.
    Runs ONLY when explicitly requested (/api/health?deep=1) and cached for 10 minutes.
    Never executes if currently under a quota lock.
    """
    global WORKING_MODEL, GEMINI_WORKING, LAST_AI_ERROR, AI_FALLBACK_ACTIVE
    global LAST_DEEP_HEALTH_CHECK_TIME, QUOTA_EXHAUSTED_UNTIL, QUOTA_MESSAGE

    if not genai_client or not GEMINI_API_KEY:
        GEMINI_WORKING = False
        AI_FALLBACK_ACTIVE = True
        return False

    if QUOTA_EXHAUSTED_UNTIL and time.time() < QUOTA_EXHAUSTED_UNTIL:
        GEMINI_WORKING = False
        AI_FALLBACK_ACTIVE = True
        return False

    LAST_DEEP_HEALTH_CHECK_TIME = time.time()

    for model_name in CANDIDATE_MODELS:
        try:
            if not USE_NEW_SDK:
                model = genai_client.GenerativeModel(model_name)
                res = model.generate_content("Ping", request_options={"timeout": 6})
                if res and res.text:
                    WORKING_MODEL = model_name
                    GEMINI_WORKING = True
                    LAST_AI_ERROR = None
                    AI_FALLBACK_ACTIVE = False
                    logger.info(f"Deep AI check passed. Active model: '{model_name}'.")
                    return True
            else:
                res = genai_client.models.generate_content(
                    model=model_name,
                    contents="Ping",
                )
                if res and res.text:
                    WORKING_MODEL = model_name
                    GEMINI_WORKING = True
                    LAST_AI_ERROR = None
                    AI_FALLBACK_ACTIVE = False
                    logger.info(f"Deep AI check passed with new SDK. Active model: '{model_name}'.")
                    return True
        except Exception as e:
            err_str = str(e).lower()
            logger.warning(f"Deep AI check for model '{model_name}' failed: {e}")
            if "quota" in err_str or "429" in err_str or "resource_exhausted" in err_str:
                delay = parse_retry_delay(str(e))
                QUOTA_EXHAUSTED_UNTIL = time.time() + delay
                time_str = format_remaining_time(delay)
                QUOTA_MESSAGE = f"Daily free-tier AI quota reached. Resets in ~{time_str}. You can still explore the sample study plans."
                LAST_AI_ERROR = "Quota exceeded (429)"
                GEMINI_WORKING = False
                AI_FALLBACK_ACTIVE = True
                return False
            if "api key" in err_str or "403" in err_str or "400" in err_str:
                LAST_AI_ERROR = "Gemini API key invalid or disabled"
                GEMINI_WORKING = False
                AI_FALLBACK_ACTIVE = True
                return False
            if "not found" in err_str or "404" in err_str or "unsupported" in err_str:
                continue

    GEMINI_WORKING = False
    AI_FALLBACK_ACTIVE = True
    return False


def run_startup_ai_check() -> bool:
    """Lazy startup check: does NOT call Gemini to preserve user free-tier quota."""
    return bool(GEMINI_API_KEY)


def get_ai_status(deep: bool = False) -> Dict[str, Any]:
    """
    Returns honest AI engine status for /api/health and frontend indicators.
    Lazy by default: does NOT make any API calls unless deep=True and 10 mins have passed.
    """
    global LAST_DEEP_HEALTH_CHECK_TIME, GEMINI_WORKING, WORKING_MODEL, LAST_AI_ERROR
    global AI_FALLBACK_ACTIVE, QUOTA_EXHAUSTED_UNTIL, QUOTA_MESSAGE

    if deep and (time.time() - LAST_DEEP_HEALTH_CHECK_TIME > 600):
        run_deep_ai_check(force=True)

    is_quota_locked = bool(QUOTA_EXHAUSTED_UNTIL and time.time() < QUOTA_EXHAUSTED_UNTIL)
    resets_in = max(0, int(QUOTA_EXHAUSTED_UNTIL - time.time())) if is_quota_locked else 0
    is_working = bool(GEMINI_API_KEY) and GEMINI_WORKING and not is_quota_locked and (_ai_call_budget["count"] < AI_DAILY_CALL_LIMIT)

    return {
        "gemini_api_configured": bool(GEMINI_API_KEY),
        "gemini_working": is_working,
        "model_in_use": WORKING_MODEL or DEFAULT_GEMINI_MODEL,
        "last_error": LAST_AI_ERROR,
        "ai_fallback_active": not is_working,
        "quota_exhausted": is_quota_locked or (_ai_call_budget["count"] >= AI_DAILY_CALL_LIMIT),
        "quota_resets_in_seconds": resets_in,
        "quota_message": QUOTA_MESSAGE if is_quota_locked else ("Daily AI call budget reached" if _ai_call_budget["count"] >= AI_DAILY_CALL_LIMIT else None),
        "ai_calls_today": _ai_call_budget["count"],
        "ai_daily_limit": AI_DAILY_CALL_LIMIT,
    }


def clean_and_parse_json(raw_text: str) -> Any:
    """Cleans markdown formatting, backticks, and extracts valid JSON."""
    cleaned = raw_text.strip()
    if "```" in cleaned:
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned, re.IGNORECASE)
        if match:
            cleaned = match.group(1).strip()
        else:
            cleaned = cleaned.replace("```json", "").replace("```", "").strip()

    bracket_match = re.search(r"(\[[\s\S]*\]|\{[\s\S]*\})", cleaned)
    if bracket_match:
        cleaned = bracket_match.group(1).strip()

    cleaned = re.sub(r",\s*([\]}])", r"\1", cleaned)
    return json.loads(cleaned)


def call_gemini_json(prompt: str, contents: Any = None, timeout: int = 35) -> Any:
    """
    Executes a structured JSON call against Gemini using the model fallback list.
    Supports response_mime_type='application/json' where available.
    Retries once, enforces timeout, tracks budget, and raises AIQuotaExhaustedError on 429.
    """
    global WORKING_MODEL, GEMINI_WORKING, LAST_AI_ERROR, AI_FALLBACK_ACTIVE
    global QUOTA_EXHAUSTED_UNTIL, QUOTA_MESSAGE

    if not GEMINI_API_KEY or not genai_client:
        return None

    # Check budget and active quota lock
    consume_ai_budget()

    models_to_try = [WORKING_MODEL] if WORKING_MODEL else []
    for m in CANDIDATE_MODELS:
        if m not in models_to_try:
            models_to_try.append(m)

    payload = contents if contents is not None else prompt

    for model_name in models_to_try:
        for attempt in range(2):
            try:
                if not USE_NEW_SDK:
                    model = genai_client.GenerativeModel(model_name)
                    try:
                        gen_cfg = genai_client.types.GenerationConfig(response_mime_type="application/json")
                        res = model.generate_content(payload, generation_config=gen_cfg, request_options={"timeout": timeout})
                    except Exception:
                        res = model.generate_content(payload, request_options={"timeout": timeout})

                    if res and hasattr(res, "text") and res.text:
                        parsed = clean_and_parse_json(res.text)
                        WORKING_MODEL = model_name
                        GEMINI_WORKING = True
                        LAST_AI_ERROR = None
                        AI_FALLBACK_ACTIVE = False
                        return parsed
                else:
                    res = genai_client.models.generate_content(
                        model=model_name,
                        contents=payload,
                    )
                    if res and hasattr(res, "text") and res.text:
                        parsed = clean_and_parse_json(res.text)
                        WORKING_MODEL = model_name
                        GEMINI_WORKING = True
                        LAST_AI_ERROR = None
                        AI_FALLBACK_ACTIVE = False
                        return parsed
            except Exception as e:
                err_str = str(e).lower()
                logger.warning(f"call_gemini_json with model '{model_name}' attempt {attempt + 1} failed: {e}")
                if "quota" in err_str or "429" in err_str or "resource_exhausted" in err_str:
                    delay = parse_retry_delay(str(e))
                    QUOTA_EXHAUSTED_UNTIL = time.time() + delay
                    time_str = format_remaining_time(delay)
                    msg = f"Daily free-tier AI quota reached. Resets in ~{time_str}. You can still explore the sample study plans."
                    QUOTA_MESSAGE = msg
                    LAST_AI_ERROR = "Quota exceeded (429)"
                    GEMINI_WORKING = False
                    raise AIQuotaExhaustedError(msg)
                if "api key" in err_str or "403" in err_str or "disabled" in err_str:
                    LAST_AI_ERROR = "Gemini API key invalid or disabled"
                    GEMINI_WORKING = False
                    raise AIUnavailableError("AI service is not available right now (invalid or disabled key).")
                if "not found" in err_str or "404" in err_str or "unsupported" in err_str:
                    break

    LAST_AI_ERROR = "All Gemini fallback models failed"
    GEMINI_WORKING = False
    AI_FALLBACK_ACTIVE = True
    raise AIUnavailableError("AI service is not available right now. Please try again later.")


def call_gemini_text(prompt: str, timeout: int = 25) -> Optional[str]:
    """Generates freeform text (e.g. revision notes) with model fallback and budget tracking."""
    global WORKING_MODEL, GEMINI_WORKING, LAST_AI_ERROR, AI_FALLBACK_ACTIVE
    global QUOTA_EXHAUSTED_UNTIL, QUOTA_MESSAGE

    if not GEMINI_API_KEY or not genai_client:
        return None

    consume_ai_budget()

    models_to_try = [WORKING_MODEL] if WORKING_MODEL else []
    for m in CANDIDATE_MODELS:
        if m not in models_to_try:
            models_to_try.append(m)

    for model_name in models_to_try:
        for attempt in range(2):
            try:
                if not USE_NEW_SDK:
                    model = genai_client.GenerativeModel(model_name)
                    res = model.generate_content(prompt, request_options={"timeout": timeout})
                    if res and hasattr(res, "text") and res.text:
                        WORKING_MODEL = model_name
                        GEMINI_WORKING = True
                        LAST_AI_ERROR = None
                        AI_FALLBACK_ACTIVE = False
                        return res.text.strip()
            except Exception as e:
                err_str = str(e).lower()
                logger.warning(f"call_gemini_text with model '{model_name}' failed: {e}")
                if "not found" in err_str or "404" in err_str or "unsupported" in err_str:
                    break
                if "quota" in err_str or "429" in err_str or "resource_exhausted" in err_str:
                    delay = parse_retry_delay(str(e))
                    QUOTA_EXHAUSTED_UNTIL = time.time() + delay
                    time_str = format_remaining_time(delay)
                    msg = f"Daily free-tier AI quota reached. Resets in ~{time_str}. You can still explore the sample study plans."
                    QUOTA_MESSAGE = msg
                    LAST_AI_ERROR = "Quota exceeded (429)"
                    GEMINI_WORKING = False
                    raise AIQuotaExhaustedError(msg)

    AI_FALLBACK_ACTIVE = True
    return None



# ---------------------------------------------------------------------------
# Chunking & Smart Defaults
# ---------------------------------------------------------------------------

def chunk_text(text: str, chunk_size: int = 10000, overlap: int = 300) -> List[str]:
    """Splits long text into semantic chunks of ~10,000 characters with small overlap."""
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0
    total_len = len(text)

    while start < total_len:
        end = min(start + chunk_size, total_len)
        if end < total_len:
            # Try to break on double newline, single newline, or space
            split_at = text.rfind("\n\n", start + chunk_size - 1000, end)
            if split_at == -1:
                split_at = text.rfind("\n", start + chunk_size - 1000, end)
            if split_at != -1 and split_at > start:
                end = split_at + 1

        chunk_content = text[start:end].strip()
        if chunk_content:
            chunks.append(chunk_content)
        if end >= total_len:
            break
        start = max(start + 1, end - overlap)

    return chunks if chunks else [text]


def guess_subject_from_text(paper_text: str) -> str:
    """
    Identifies the subject name from exam paper text using local regex (0 Gemini calls).
    Saves API quota by avoiding separate LLM calls.
    """
    if not paper_text or len(paper_text.strip()) < 5:
        return "My Subject"

    lines = paper_text.split("\n")[:25]
    for line in lines:
        clean = line.strip()
        m = re.search(r"(?:subject|course|paper|name of paper)\s*[:\-]\s*([A-Za-z0-9\s\&\-]{3,50})", clean, re.IGNORECASE)
        if m:
            candidate = m.group(1).strip()
            if len(candidate) >= 3 and not any(w in candidate.lower() for w in ["time", "hours", "marks", "maximum", "total", "code"]):
                return candidate.title()

    for line in lines[:5]:
        clean = line.strip()
        if 4 <= len(clean) <= 45 and not any(w in clean.lower() for w in ["time", "marks", "roll", "page", "exam", "instructions", "attempt"]):
            if re.match(r"^[A-Za-z0-9\s\&\-]+$", clean):
                return clean.title()

    return "My Subject"


def detect_document_type(file_path: str = "", text: str = "") -> str:
    """
    Detects whether a file is an examination paper ('paper') or student notes ('notes').
    Notes must NOT count as exam years in frequency or priority calculation.
    Local heuristic only: uses 0 Gemini quota.
    """
    sample = (text[:3000] if text else "").lower()
    fname = os.path.basename(file_path).lower() if file_path else ""

    if any(k in fname for k in ["note", "summary", "lecture", "module", "handout"]):
        return "notes"
    if any(k in fname for k in ["exam", "paper", "pyq", "question", "endsem", "midsem"]):
        return "paper"

    paper_score = 0
    notes_score = 0

    paper_keywords = [
        "maximum marks", "max marks", "time allowed", "time: 3", "time : 3",
        "attempt all", "attempt any", "roll no", "q.1", "q.2", "question paper",
        "section a", "section b", "[7]", "[10]", "(10 marks)", "(7 marks)", "7m"
    ]
    notes_keywords = [
        "lecture notes", "chapter overview", "summary:", "key takeaways",
        "module 1", "module 2", "unit summary", "author:", "professor:", "syllabus:"
    ]

    for k in paper_keywords:
        if k in sample:
            paper_score += 1
    for k in notes_keywords:
        if k in sample:
            notes_score += 1

    return "notes" if notes_score > paper_score + 1 else "paper"


# ---------------------------------------------------------------------------
# Extraction Cache (SHA-256 by file/text content) & QuestionsResult
# ---------------------------------------------------------------------------

class QuestionsResult(list):
    """
    Subclass of list holding question dicts, while carrying doc_type, subject_guess,
    and year_guess metadata extracted in a single Gemini call.
    Maintains 100% backward compatibility for all list operations.
    """
    def __init__(
        self,
        questions: Optional[List[Dict[str, Any]]] = None,
        doc_type: str = "paper",
        subject_guess: str = "",
        year_guess: Optional[int] = None,
    ):
        super().__init__(questions or [])
        self.doc_type = doc_type
        self.subject_guess = subject_guess
        self.year_guess = year_guess

    def to_dict(self) -> Dict[str, Any]:
        return {
            "doc_type": self.doc_type,
            "subject_guess": self.subject_guess,
            "year_guess": self.year_guess,
            "questions": list(self),
        }


def compute_content_hash(file_path: Optional[str] = None, text: Optional[str] = None) -> str:
    """Computes SHA-256 hash of a file or text string for extraction caching."""
    hasher = hashlib.sha256()
    if file_path and os.path.exists(file_path):
        try:
            with open(file_path, "rb") as f:
                while chunk := f.read(65536):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except Exception:
            pass
    if text:
        hasher.update(text.strip().encode("utf-8"))
        return hasher.hexdigest()
    return ""


def get_cached_extraction(file_hash: str, db: Optional[Any] = None) -> Optional[Dict[str, Any]]:
    """Checks database ExtractionCache for prior extraction with this SHA-256 hash."""
    if not file_hash:
        return None
    try:
        from app.models import ExtractionCache
        should_close = False
        session = db
        if session is None:
            from app.database import SessionLocal
            session = SessionLocal()
            should_close = True
        try:
            cached = session.query(ExtractionCache).filter(ExtractionCache.file_hash == file_hash).first()
            if cached and cached.extracted_json:
                return json.loads(cached.extracted_json)
        finally:
            if should_close:
                session.close()
    except Exception as e:
        logger.warning(f"Error checking ExtractionCache for {file_hash}: {e}")
    return None


def save_cached_extraction(file_hash: str, data: Dict[str, Any], db: Optional[Any] = None) -> None:
    """Persists question extraction into database ExtractionCache by SHA-256 hash."""
    if not file_hash or not data:
        return
    try:
        from app.models import ExtractionCache
        should_close = False
        session = db
        if session is None:
            from app.database import SessionLocal
            session = SessionLocal()
            should_close = True
        try:
            existing = session.query(ExtractionCache).filter(ExtractionCache.file_hash == file_hash).first()
            if not existing:
                rec = ExtractionCache(
                    file_hash=file_hash,
                    extracted_json=json.dumps(data)
                )
                session.add(rec)
                if should_close:
                    session.commit()
                else:
                    session.flush()
        finally:
            if should_close:
                session.close()
    except Exception as e:
        logger.warning(f"Error persisting ExtractionCache for {file_hash}: {e}")


# ---------------------------------------------------------------------------
# Feature 2 & Phase 3: Question Extraction (Single Gemini Call per Paper)
# ---------------------------------------------------------------------------

def extract_questions_with_regex_fallback(text: str, year: int) -> List[Dict[str, Any]]:
    """Heuristic fallback to extract questions from paper text when GEMINI_API_KEY is absent."""
    lines = text.split("\n")
    questions = []
    current_q = []

    pattern = re.compile(
        r"^(Q(?:uestion)?\s*\.?\s*\d+\s*[\.\:\-\)]?|\d+[\.\)]\s*(?:\([a-zA-Z0-9]+\))?|\([a-zA-Z0-9]+\))\s*(.*)",
        re.IGNORECASE,
    )

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        
        match = pattern.match(stripped)
        if match and len(stripped) > 10:
            if current_q:
                q_text = " ".join(current_q).strip()
                if len(q_text) >= 15:
                    questions.append({
                        "question_text": q_text,
                        "marks": 7,
                        "unit_or_topic_guess": "Core Concepts",
                        "year": year,
                    })
                current_q = []
            current_q.append(stripped)
        elif current_q:
            current_q.append(stripped)

    if current_q:
        q_text = " ".join(current_q).strip()
        if len(q_text) >= 15:
            questions.append({
                "question_text": q_text,
                "marks": 7,
                "unit_or_topic_guess": "Core Concepts",
                "year": year,
            })

    if not questions:
        paras = [p.strip() for p in text.split("\n\n") if len(p.strip()) > 30]
        for p in paras[:15]:
            questions.append({
                "question_text": p,
                "marks": 7,
                "unit_or_topic_guess": "Core Concepts",
                "year": year,
            })

    return questions


def extract_questions_from_paper(
    paper_text: str,
    year: int,
    subject_name: str = "",
    exam_type: str = "General",
    file_path: Optional[str] = None,
    db: Optional[Any] = None,
) -> QuestionsResult:
    """
    Extracts individual questions, document type, subject guess, and year guess
    using ONE Gemini call per paper (or page batch for large files), caching by SHA-256.
    Gracefully falls back to heuristic extraction without failing on quota exhaustion.
    """
    content_hash = compute_content_hash(file_path=file_path, text=paper_text)
    
    # 1. Check SHA-256 hash cache first (0 Gemini quota cost)
    if content_hash:
        cached = get_cached_extraction(content_hash, db=db)
        if cached and isinstance(cached, dict) and "questions" in cached:
            logger.info(f"Reusing cached extraction for hash {content_hash[:10]}... (0 Gemini calls)")
            return QuestionsResult(
                questions=cached.get("questions", []),
                doc_type=cached.get("doc_type", "paper"),
                subject_guess=cached.get("subject_guess", ""),
                year_guess=cached.get("year_guess", year),
            )

    local_doc_type = detect_document_type(file_path or "", paper_text)
    local_subject_guess = guess_subject_from_text(paper_text)

    # 2. Check if Gemini is offline, disabled, or currently quota-locked
    if not GEMINI_API_KEY or not genai_client or (QUOTA_EXHAUSTED_UNTIL and time.time() < QUOTA_EXHAUSTED_UNTIL):
        logger.info("Using heuristic regex question extractor (Gemini offline or quota locked).")
        raw_qs = extract_questions_with_regex_fallback(paper_text, year)
        res = QuestionsResult(
            questions=raw_qs,
            doc_type=local_doc_type,
            subject_guess=local_subject_guess,
            year_guess=year,
        )
        if content_hash:
            save_cached_extraction(content_hash, res.to_dict(), db=db)
        return res

    single_prompt = f"""You are an expert exam paper analyzer for {exam_type} examinations.
Analyze this document for the subject "{subject_name or 'Auto-detect'}".
Target Exam Year: {year}

CRITICAL EXTRACTION INSTRUCTIONS:
1. Determine if this document is an examination paper ("paper") or revision notes/handout ("notes"). Return this as "doc_type".
2. Infer the exact academic subject name from the paper as "subject_guess" (e.g. "Database Management Systems", "Engineering Physics").
3. Infer the exam year as "year_guess" (integer e.g. 2023). If not found, use {year}.
4. Extract EVERY individual question and sub-question separately (e.g. Q1(a), Q1(b), OR options must be separate questions).
5. Extract the REAL marks printed in the paper for each question (e.g., [7], (10 Marks), 5M -> integer). If marks are not stated anywhere, default to 7.
6. Assign a SPECIFIC and accurate academic topic name to each question (e.g., "Ohm's Law", "Normalization & 3NF", "Newton's Second Law", "Photosynthesis"). NEVER use generic words like "General", "Miscellaneous", or "Topic 1".
7. Completely IGNORE exam header boilerplate, total marks, time allowed, candidate roll number, and instructions.

Output strictly valid JSON with this exact schema:
{{
  "doc_type": "paper",
  "subject_guess": "Inferred Subject Name",
  "year_guess": {year},
  "questions": [
    {{
      "question_text": "Complete question text",
      "marks": 7,
      "unit_or_topic_guess": "Specific Topic Name",
      "year": {year}
    }}
  ]
}}
"""

    data = None
    uploaded_gemini_file = None

    # 3. Direct File Multimodal Reading (File API or PIL Image)
    if file_path and os.path.exists(file_path):
        ext = os.path.splitext(file_path)[1].lower()
        try:
            if ext == ".pdf":
                uploaded_gemini_file = genai_client.upload_file(path=file_path, mime_type="application/pdf")
                contents = [uploaded_gemini_file, single_prompt]
                data = call_gemini_json(prompt=single_prompt, contents=contents, timeout=40)
            elif ext in [".jpg", ".jpeg", ".png", ".webp"]:
                from PIL import Image
                img = Image.open(file_path)
                contents = [img, single_prompt]
                data = call_gemini_json(prompt=single_prompt, contents=contents, timeout=35)
        except AIQuotaExhaustedError as quota_err:
            logger.warning(f"Quota exhausted during direct file reading: {quota_err}")
            raw_qs = extract_questions_with_regex_fallback(paper_text, year)
            res = QuestionsResult(raw_qs, doc_type=local_doc_type, subject_guess=local_subject_guess, year_guess=year)
            if content_hash:
                save_cached_extraction(content_hash, res.to_dict(), db=db)
            return res
        except Exception as file_err:
            logger.warning(f"Direct file reading failed, attempting chunked text fallback: {file_err}")
        finally:
            if uploaded_gemini_file:
                try:
                    genai_client.delete_file(uploaded_gemini_file.name)
                except Exception:
                    pass

    # 4. Text Chunks Fallback Path (ONE call if len <= 10000)
    if not data:
        chunks = chunk_text(paper_text, chunk_size=10000, overlap=300)
        all_qs = []
        inferred_doc_type = local_doc_type
        inferred_subject = local_subject_guess
        inferred_year = year

        try:
            for chunk_idx, chunk in enumerate(chunks[:2]):  # Cap at max 2 chunks to minimize quota drain
                chunk_prompt = f"""You are an expert exam analyzer for {exam_type} examinations.
Extract all questions and metadata from this exam paper chunk for subject "{subject_name}".
Exam Year: {year}

PAPER CHUNK {chunk_idx + 1} OF {len(chunks)}:
\"\"\"
{chunk}
\"\"\"

Return strictly valid JSON:
{{
  "doc_type": "paper",
  "subject_guess": "Inferred Subject Name",
  "year_guess": {year},
  "questions": [
    {{
      "question_text": "Full question text",
      "marks": 7,
      "unit_or_topic_guess": "Specific Topic Name",
      "year": {year}
    }}
  ]
}}
"""
                c_data = call_gemini_json(prompt=chunk_prompt, timeout=30)
                if c_data and isinstance(c_data, dict):
                    if chunk_idx == 0:
                        inferred_doc_type = c_data.get("doc_type") or inferred_doc_type
                        inferred_subject = c_data.get("subject_guess") or inferred_subject
                        inferred_year = c_data.get("year_guess") or inferred_year
                    q_list = c_data.get("questions", [])
                    all_qs.extend(_sanitize_extracted_questions(q_list, year))
        except AIQuotaExhaustedError:
            logger.warning("Gemini quota exhausted during chunk extraction; falling back to heuristic regex.")
            raw_qs = extract_questions_with_regex_fallback(paper_text, year)
            res = QuestionsResult(raw_qs, doc_type=local_doc_type, subject_guess=local_subject_guess, year_guess=year)
            if content_hash:
                save_cached_extraction(content_hash, res.to_dict(), db=db)
            return res
        except Exception as e:
            logger.warning(f"Chunk text extraction warning: {e}")

        if all_qs:
            deduped = _deduplicate_questions(all_qs)
            result = QuestionsResult(
                questions=deduped,
                doc_type=inferred_doc_type,
                subject_guess=inferred_subject,
                year_guess=inferred_year,
            )
            if content_hash:
                save_cached_extraction(content_hash, result.to_dict(), db=db)
            return result

    # 5. If data came from direct file reading
    if data and isinstance(data, dict):
        q_list = data.get("questions", [])
        sanitized = _sanitize_extracted_questions(q_list, year)
        if sanitized:
            result = QuestionsResult(
                questions=sanitized,
                doc_type=data.get("doc_type") or local_doc_type,
                subject_guess=data.get("subject_guess") or local_subject_guess,
                year_guess=data.get("year_guess") or year,
            )
            if content_hash:
                save_cached_extraction(content_hash, result.to_dict(), db=db)
            return result

    # 6. Final fallback if all AI paths yielded nothing
    raw_qs = extract_questions_with_regex_fallback(paper_text, year)
    result = QuestionsResult(raw_qs, doc_type=local_doc_type, subject_guess=local_subject_guess, year_guess=year)
    if content_hash:
        save_cached_extraction(content_hash, result.to_dict(), db=db)
    return result


def _sanitize_extracted_questions(q_list: List[Any], fallback_year: int) -> List[Dict[str, Any]]:
    """Sanitizes question records, enforces minimum length, and ensures specific topic names."""
    sanitized = []
    for item in q_list:
        if isinstance(item, dict) and "question_text" in item:
            text = str(item["question_text"]).strip()
            if len(text) < 12:
                continue
            marks = int(item.get("marks") or 7)
            marks = max(1, min(100, marks))

            topic = str(item.get("unit_or_topic_guess") or "").strip()
            if not topic or topic.lower() in ["general", "miscellaneous", "unknown", "none", "n/a"]:
                # Derive a specific topic from first 4 words of question
                words = re.findall(r"\b[A-Za-z0-9\-]{3,}\b", text)
                topic = " ".join(words[:3]).title() if words else "Core Subject Principles"

            year = int(item.get("year") or fallback_year)
            sanitized.append({
                "question_text": text,
                "marks": marks,
                "unit_or_topic_guess": topic,
                "year": year,
            })
    return sanitized


def _deduplicate_questions(q_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Removes duplicate questions across chunks based on text similarity."""
    seen_prefixes = set()
    unique = []
    for q in q_list:
        norm = re.sub(r"[^a-zA-Z0-9]", "", q["question_text"][:50].lower())
        if norm not in seen_prefixes:
            seen_prefixes.add(norm)
            unique.append(q)
    return unique


# ---------------------------------------------------------------------------
# Topic Normalization (Global clustering across all papers)
# ---------------------------------------------------------------------------

def normalize_topics_with_llm(
    topics_list: List[str],
    subject_name: str = "",
    exam_type: str = "General",
) -> Dict[str, str]:
    """
    Groups and standardizes all topic names across all papers together in ONE call.
    Validates output so that no topic is normalized to 'General'.
    Skips call if topics <= 3, quota locked, or no API key.
    """
    unique_topics = sorted(list(set(t.strip() for t in topics_list if t and t.strip())))
    if len(unique_topics) <= 3:
        return {t: t.title() for t in unique_topics}

    if not GEMINI_API_KEY or not genai_client or (QUOTA_EXHAUSTED_UNTIL and time.time() < QUOTA_EXHAUSTED_UNTIL):
        return {t: t.title() for t in unique_topics}

    prompt = f"""You are an academic curriculum director for {exam_type} subject "{subject_name}".
Below are all raw topic names extracted from past examination papers:
{json.dumps(unique_topics, indent=2)}

Please cluster and normalize these into 6 to 12 clear, standardized syllabus topics.
RULES:
1. Combine synonymous or sub-topic concepts together (e.g. "2PL", "Concurrency", "Locking" -> "Concurrency Control & 2PL").
2. NEVER use "General" or "Miscellaneous".
3. Return a JSON object mapping each raw topic name to its standardized canonical topic name.

Schema:
{{
  "raw_topic_1": "Canonical Topic Name",
  "raw_topic_2": "Canonical Topic Name"
}}
"""
    try:
        data = call_gemini_json(prompt, timeout=25)
        if isinstance(data, dict):
            mapping = {}
            for t in unique_topics:
                norm = str(data.get(t) or "").strip()
                if not norm or norm.lower() in ["general", "miscellaneous"]:
                    mapping[t] = t.title()
                else:
                    mapping[t] = norm
            return mapping
    except AIQuotaExhaustedError:
        logger.warning("Quota exhausted during topic normalization; using title-cased fallback.")
    except Exception as e:
        logger.warning(f"Global topic normalization failed: {e}")

    return {t: t.title() for t in unique_topics}


# ---------------------------------------------------------------------------
# Phase 6: Start with just a Subject Name (/api/subjects/from-topic)
# ---------------------------------------------------------------------------

def generate_syllabus_from_subject_name(
    subject_name: str,
    exam_level: str = "General",
    board_name: str = "",
    class_level: str = "",
) -> List[Dict[str, Any]]:
    """
    Generates 12-20 important exam topics for subject-name-only mode.
    Returns structured JSON with importance (1-10), typical marks, and typical questions.
    """
    if not GEMINI_API_KEY or not genai_client:
        raise AIUnavailableError("AI service is not available right now. An API key is required for subject-name prediction.")

    prompt = f"""You are a master academic exam predictor.
Create a complete exam curriculum topic breakdown for:
Subject: {subject_name}
Exam Level: {exam_level}
Board/University: {board_name or 'Standard Curriculum'}
Class/Semester: {class_level or 'Standard Level'}

Identify 12 to 18 most important exam topics based on typical examination weightage and historical exam patterns.
For each topic:
1. Assign 'estimated_importance' from 1 to 10 (8-10 = High Priority, 5-7 = Medium Priority, 1-4 = Low Priority).
2. Typical question marks (e.g. 5, 7, or 10).
3. Likely question types (e.g. ["Derivation", "Numerical", "Theory", "Diagram"]).
4. 2-3 typical questions asked on this topic in real exams.

Return strictly valid JSON adhering to this schema:
[
  {{
    "topic_name": "Topic Name",
    "estimated_importance": 9,
    "typical_marks": 7,
    "likely_question_types": ["Theory", "Derivation"],
    "typical_questions": [
      "Typical question 1 here?",
      "Typical question 2 here?"
    ]
  }}
]
"""
    try:
        data = call_gemini_json(prompt, timeout=35)
        if isinstance(data, list) and len(data) >= 5:
            sanitized = []
            for item in data:
                if isinstance(item, dict) and "topic_name" in item:
                    t_name = str(item["topic_name"]).strip()
                    importance = int(item.get("estimated_importance") or 7)
                    importance = max(1, min(10, importance))
                    marks = int(item.get("typical_marks") or 7)
                    q_types = item.get("likely_question_types") or ["Theory"]
                    questions = [str(q).strip() for q in item.get("typical_questions", []) if len(str(q).strip()) > 10]
                    sanitized.append({
                        "topic_name": t_name,
                        "estimated_importance": importance,
                        "typical_marks": marks,
                        "likely_question_types": q_types,
                        "typical_questions": questions if questions else [f"Explain the core concept of {t_name} with an example."],
                    })
            if len(sanitized) >= 5:
                return sanitized
    except AIUnavailableError:
        raise
    except Exception as e:
        logger.error(f"Error in generate_syllabus_from_subject_name: {e}")

    raise AIUnavailableError("Could not generate syllabus from AI. Please try again or upload question papers.")


# ---------------------------------------------------------------------------
# Phase 7: Notes Processing & Important Questions
# ---------------------------------------------------------------------------

def generate_important_questions_from_notes(
    notes_text: str,
    subject_name: str,
    exam_type: str = "General",
    file_path: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Extracts 3-5 important examination questions per major topic from student study notes.
    """
    if not GEMINI_API_KEY or not genai_client:
        raise AIUnavailableError("AI service is not available right now. An API key is required to analyze study notes.")

    prompt = f"""You are an examination question setter.
Analyze these student revision notes for subject "{subject_name}" ({exam_type} level).
Generate high-yield examination questions covering all major topics found in the notes.
Provide 3 to 5 questions per major topic.

For each question:
- 'topic': Major Topic Name
- 'question_text': Precise question
- 'question_type': One of ["short answer", "long answer", "numerical", "MCQ", "definition"]
- 'expected_marks': Integer (e.g. 3, 5, 7, 10)
- 'why_important': 1 sentence explaining why this is high-yield for exams
- 'difficulty': "Easy", "Medium", or "Hard"

NOTES CONTENT:
\"\"\"
{notes_text[:12000]}
\"\"\"

Return strictly valid JSON array:
[
  {{
    "topic": "Topic Name",
    "question_text": "Question text here?",
    "question_type": "short answer",
    "expected_marks": 5,
    "why_important": "Core definition tested in semester exams.",
    "difficulty": "Medium"
  }}
]
"""
    try:
        data = call_gemini_json(prompt, timeout=35)
        if isinstance(data, list) and len(data) > 0:
            sanitized = []
            for item in data:
                if isinstance(item, dict) and "question_text" in item:
                    sanitized.append({
                        "topic": str(item.get("topic") or "Key Concepts").strip(),
                        "question_text": str(item["question_text"]).strip(),
                        "question_type": str(item.get("question_type") or "short answer").strip(),
                        "expected_marks": int(item.get("expected_marks") or 5),
                        "why_important": str(item.get("why_important") or "High probability exam question.").strip(),
                        "difficulty": str(item.get("difficulty") or "Medium").strip(),
                    })
            if sanitized:
                return sanitized
    except AIUnavailableError:
        raise
    except Exception as e:
        logger.error(f"Error extracting questions from notes: {e}")

    raise AIUnavailableError("Unable to analyze notes at this time. Please try again.")


def generate_answer_outline(question_text: str, topic_name: str, subject_name: str) -> str:
    """Generates a concise, exam-winning answer outline for an important question."""
    if not GEMINI_WORKING or not GEMINI_API_KEY:
        return f"- **Core Concept:** Key definition and principles of {topic_name}.\n- **Key Steps:** Define standard terminology and outline equations/diagram.\n- **Conclusion:** State practical significance and real-world example."

    prompt = f"""Provide a crisp, high-scoring exam answer outline for:
Subject: {subject_name}
Topic: {topic_name}
Question: {question_text}

Provide 4 to 6 bullet points of what an examiner looks for in a full-marks answer. Keep it concise.
"""
    try:
        res = call_gemini_text(prompt, timeout=15)
        if res:
            return res
    except Exception:
        pass

    return f"- **Definition:** State formal technical definition of {topic_name}.\n- **Core Points:** List key rules, assumptions, and formulas.\n- **Diagram/Example:** Include schematic representation.\n- **Conclusion:** Summary of operational importance."


# ---------------------------------------------------------------------------
# Revision Notes & Quiz Generation
# ---------------------------------------------------------------------------

def generate_revision_notes(
    topic_name: str,
    subject_name: str,
    sample_questions: List[str] = None,
    language: str = "en",
    exam_type: str = "General",
) -> str:
    """Generates revision notes with English/Hinglish support and level adaptation."""
    sample_qs_str = "\n".join(f"- {q}" for q in (sample_questions or [])[:4])
    
    if language == "hi":
        lang_instruction = "Write in student-friendly, natural Hinglish (Hindi written in English alphabet, e.g. 'Is concept ka main purpose efficiency aur reliability ensure karna hota hai.'). This makes it easy for students to grasp quickly."
    else:
        lang_instruction = "Write in clear, crisp, exam-oriented English with structured bullet points."

    level_instruction = "Focus on structured exam scoring points and core principles."
    if "school" in exam_type.lower():
        level_instruction = "Use simple, visual language suitable for school board exams. Easy to memorize."
    elif "competitive" in exam_type.lower():
        level_instruction = "Focus on high-speed competitive exam mastery (shortcuts, trap points, formula sheet)."
    elif "college" in exam_type.lower() or "university" in exam_type.lower():
        level_instruction = "Focus on technical depth, architectural flow, and semester exam answering structure."

    if not GEMINI_WORKING or not GEMINI_API_KEY or (QUOTA_EXHAUSTED_UNTIL and time.time() < QUOTA_EXHAUSTED_UNTIL):
        return get_offline_fallback_notes(topic_name, subject_name, language, exam_type)

    prompt = f"""You are an expert exam educator creating last-minute revision notes for exam preparation.
Subject: {subject_name}
Topic: {topic_name}
Exam Level: {exam_type}

Past Exam Questions on this topic:
{sample_qs_str}

Language Instruction: {lang_instruction}
Level Guidance: {level_instruction}

Create high-yield revision notes formatted in GitHub Markdown with these exact sections:
1. 📌 **Quick Definition & Concept** (2-3 punchy sentences)
2. 🔑 **Must-Remember Key Points** (5 high-yield bullet points that examiners look for)
3. 📐 **Formulas / Architecture / Rules** (Clear ASCII representation or rules)
4. 💡 **Solved Exam Example** (A classic high-mark question solved simply)
5. ⚠️ **Exam & Review Tips** (Common mistakes students make and what examiners check)

Keep it concise, actionable, and strictly relevant to exam preparation.
"""
    try:
        res = call_gemini_text(prompt, timeout=25)
        if res and len(res) > 100:
            return res
    except AIQuotaExhaustedError:
        logger.warning("Quota exhausted during revision notes generation; falling back to offline notes.")
        return get_offline_fallback_notes(topic_name, subject_name, language, exam_type)
    except AIUnavailableError:
        raise
    except Exception as e:
        logger.warning(f"Notes generation failed: {e}")

    return get_offline_fallback_notes(topic_name, subject_name, language, exam_type)


def get_offline_fallback_notes(
    topic_name: str,
    subject_name: str,
    language: str = "en",
    exam_type: str = "General",
) -> str:
    """Pre-crafted structured notes when offline or API key absent."""
    if language == "hi":
        return f"""# 📝 Revision Notes: {topic_name}
*Subject: {subject_name} (Language: Hinglish / Hindi-English)*

---

### 📌 Quick Definition & Concept
**{topic_name}** ka core objective exam point of view se theoretical understanding aur practical implementation dono me master hona hai. Is concept se exam me consistently high-weightage questions aate hain.

### 🔑 Must-Remember Key Points
1. **Core Purpose:** System ki efficiency, accuracy aur reliability ko maintain karna.
2. **Standard Terminology:** Exam me standard definitions aur technical keywords use karein taaki full marks milein.
3. **Classification:** Is topic ke standard types aur variations ko step-by-step point format me likhein.
4. **Comparison Matrix:** Difference table (e.g., Pros vs Cons) draw karne par examiner full marks deta hai.
5. **Real-world application:** Theory ke sath practical application ya use-case zaroor mention karein.

### 📐 Formulas / Architecture
```
[ Input / Entity ] ---> [ Processing / Algorithm ] ---> [ Optimized Result ]
        |                         |                              |
        v                         v                              v
   Constraint Check          State Validation            Consistency Check
```

### 💡 Solved Exam Example
**Q: Explain {topic_name} with an example.**
- **Step 1:** Define the concept with formal terminology.
- **Step 2:** Draw the architectural / procedural diagram.
- **Step 3:** Show input data and step-by-step transformation.
- **Conclusion:** State why this approach is optimal.

### ⚠️ Exam & Review Tips
- **Key Tip:** Examiner aksar 'Edge cases' aur 'Why do we need this instead of previous technique?' puchte hain.
- **Presentation Tip:** Diagram ko hamesha clean labeling ke sath draw karein. Bullet points me likhein, lambe paragraphs avoid karein.
"""

    return f"""# 📝 Revision Notes: {topic_name}
*Subject: {subject_name} | ExamSense Quick Study Material*

---

### 📌 Quick Definition & Concept
**{topic_name}** represents a fundamental pillar within {subject_name}. In examination patterns across academic and competitive tests, questions from this topic carry high weightage and evaluate conceptual clarity, systematic modeling, and analytical problem-solving.

### 🔑 Must-Remember Key Points
1. **Fundamental Objective:** Designed to eliminate redundancy, optimize runtime complexity, and ensure robust guarantees.
2. **Core Axioms & Rules:** Always list the formal mathematical or operational conditions governing the behavior of this topic.
3. **Step-by-Step Procedure:** When asked for an algorithm or process, number your steps sequentially with clear pre-conditions and post-conditions.
4. **Comparative Analysis:** Prepare a comparison table contrasting this technique with alternative standard paradigms.
5. **Trade-offs:** Mention trade-offs explicitly (e.g., resource overhead vs. execution speed).

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

### 💡 Solved Exam Example
**Question:** Explain the mechanism and significance of {topic_name}.
- **Approach:**
  1. Define the formal scope and logical constraints.
  2. Illustrate with a concrete scenario or schematic diagram.
  3. Detail the transformation step-by-step and prove correctness.
- **Key Takeaway:** Demonstrates complete mastery of both theoretical foundation and practical application.

### ⚠️ Exam & Review Tips
- **Common Mistake:** Omitting the diagram or failing to state the boundary conditions.
- **Frequent Examiner Question:** "Under what specific condition does this approach fail or become inefficient?"
- **Presentation Rule:** Always underline key technical terms and wrap final solutions in a clear box.
"""


def generate_practice_quiz(
    topic_name: str,
    subject_name: str,
    sample_questions: List[str] = None,
    exam_type: str = "General",
    question_count: int = 5,
    difficulty: str = "medium",
) -> List[Dict[str, Any]]:
    """Generates MCQs with 4 options, correct answer index, and explanation."""
    if not GEMINI_WORKING or not GEMINI_API_KEY or (QUOTA_EXHAUSTED_UNTIL and time.time() < QUOTA_EXHAUSTED_UNTIL):
        return get_offline_fallback_quiz(topic_name, subject_name, exam_type)

    sample_qs_str = "\n".join(f"- {q}" for q in (sample_questions or [])[:3])

    prompt = f"""You are an expert exam quiz generator for {exam_type} examinations.
Subject: {subject_name}
Topic: {topic_name}
Difficulty: {difficulty}

Past questions:
{sample_qs_str}

Generate exactly {question_count} exam-oriented Multiple Choice Questions (MCQs) testing core concepts of "{topic_name}".
Return ONLY a valid JSON array:
[
  {{
    "id": 1,
    "question": "Clear question text?",
    "options": ["Option A", "Option B", "Option C", "Option D"],
    "correct_index": 0,
    "explanation": "Clear explanation of why this answer is correct."
  }}
]
"""
    try:
        data = call_gemini_json(prompt, timeout=25)
        if isinstance(data, list) and len(data) >= 3:
            sanitized = []
            for i, item in enumerate(data[:question_count]):
                if isinstance(item, dict) and "question" in item and len(item.get("options", [])) == 4:
                    c_idx = int(item.get("correct_index", 0))
                    if c_idx < 0 or c_idx > 3:
                        c_idx = 0
                    sanitized.append({
                        "id": i + 1,
                        "question": str(item["question"]),
                        "options": [str(opt) for opt in item["options"]],
                        "correct_index": c_idx,
                        "explanation": str(item.get("explanation", "Correct based on core principles.")),
                    })
            if len(sanitized) >= 3:
                return sanitized
    except AIQuotaExhaustedError:
        logger.warning("Quota exhausted during quiz generation; falling back to offline quiz.")
        return get_offline_fallback_quiz(topic_name, subject_name, exam_type)
    except AIUnavailableError:
        raise
    except Exception as e:
        logger.warning(f"Quiz generation failed: {e}")

    return get_offline_fallback_quiz(topic_name, subject_name, exam_type)


def get_offline_fallback_quiz(
    topic_name: str,
    subject_name: str,
    exam_type: str = "General",
) -> List[Dict[str, Any]]:
    """Pre-built standard questions for robust offline operation."""
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
                    f"To master core principles and eliminate fundamental errors in {topic_name}",
                    "To increase memory footprint unnecessarily",
                    "To bypass standard validation checks",
                    "To restrict modular thinking"
                ],
                "correct_index": 0,
                "explanation": f"Understanding {topic_name} ensures robust conceptual mastery, correctness, and optimal exam performance."
            },
            {
                "id": 2,
                "question": f"Which of the following is a key advantage of mastering {topic_name}?",
                "options": [
                    "Decreases subject comprehension",
                    "Provides conceptual consistency and predictable problem-solving",
                    "Forces all operations to run sequentially in one thread",
                    "Disables error reporting"
                ],
                "correct_index": 1,
                "explanation": f"Applying {topic_name} provides structured foundational mastery and predictable exam results."
            },
            {
                "id": 3,
                "question": f"In an examination question regarding {topic_name}, what earns the highest score?",
                "options": [
                    "Writing a single paragraph without structure",
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
                    "Assuming it applies without respecting underlying boundary conditions",
                    "It requires no cognitive effort",
                    "It cannot be combined with other concepts"
                ],
                "correct_index": 1,
                "explanation": "Ignoring boundary constraints is the most frequent reason for mistakes in examination questions."
            },
            {
                "id": 5,
                "question": f"Which metric is most commonly evaluated when testing {topic_name}?",
                "options": [
                    "Conceptual accuracy, logical consistency, and application clarity",
                    "Color scheme of the examination desk",
                    "Font size of code comments",
                    "Operating system wallpaper"
                ],
                "correct_index": 0,
                "explanation": "Conceptual correctness, logical clarity, and problem-solving application are the core criteria tested."
            }
        ]
