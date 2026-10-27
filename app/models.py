import json
from datetime import datetime
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Float,
    Boolean,
    DateTime,
    ForeignKey,
)
from sqlalchemy.orm import relationship
from app.database import Base


class Subject(Base):
    __tablename__ = "subjects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    code = Column(String(50), nullable=False, index=True)
    exam_type = Column(String(50), nullable=True, default="General")
    owner_id = Column(String(100), nullable=True, index=True)
    is_demo = Column(Boolean, default=False, nullable=True)
    source = Column(String(50), nullable=True, default="papers")  # "papers", "ai_estimate", "demo"
    status = Column(String(50), nullable=True, default="ready")   # "processing", "ready", "failed"
    progress_text = Column(String(255), nullable=True, default="Ready")
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    papers = relationship("Paper", back_populates="subject", cascade="all, delete-orphan")
    questions = relationship("Question", back_populates="subject", cascade="all, delete-orphan")
    topics = relationship("Topic", back_populates="subject", cascade="all, delete-orphan")
    repeated_groups = relationship(
        "RepeatedQuestionGroup", back_populates="subject", cascade="all, delete-orphan"
    )
    suggested_questions = relationship(
        "SuggestedQuestion", back_populates="subject", cascade="all, delete-orphan"
    )

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "code": self.code,
            "exam_type": self.exam_type or "General",
            "owner_id": self.owner_id,
            "is_demo": bool(self.is_demo),
            "source": self.source or "papers",
            "status": self.status or "ready",
            "progress_text": self.progress_text or "Ready",
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "papers_count": len(self.papers),
            "topics_count": len(self.topics),
            "suggested_questions_count": len(self.suggested_questions) if self.suggested_questions else 0,
        }


class Paper(Base):
    __tablename__ = "papers"

    id = Column(Integer, primary_key=True, index=True)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False)
    year = Column(Integer, nullable=False)
    filename = Column(String(255), nullable=False)
    filepath = Column(String(500), nullable=False)
    extracted_text = Column(Text, nullable=True)
    is_ocr = Column(Boolean, default=False)
    doc_type = Column(String(50), nullable=True, default="paper")  # "paper" or "notes"
    questions_found = Column(Integer, default=0, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    subject = relationship("Subject", back_populates="papers")
    questions = relationship("Question", back_populates="paper", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "subject_id": self.subject_id,
            "year": self.year,
            "filename": self.filename,
            "is_ocr": self.is_ocr,
            "doc_type": self.doc_type or "paper",
            "questions_found": self.questions_found if self.questions_found is not None else len(self.questions),
            "text_length": len(self.extracted_text) if self.extracted_text else 0,
            "questions_count": len(self.questions),
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Question(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True, index=True)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False)
    paper_id = Column(Integer, ForeignKey("papers.id"), nullable=True)
    year = Column(Integer, nullable=False)
    question_text = Column(Text, nullable=False)
    marks = Column(Integer, default=7)
    unit_or_topic_guess = Column(String(100), default="General")
    topic_id = Column(Integer, ForeignKey("topics.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    subject = relationship("Subject", back_populates="questions")
    paper = relationship("Paper", back_populates="questions")
    topic = relationship("Topic", back_populates="questions")

    def to_dict(self):
        return {
            "id": self.id,
            "subject_id": self.subject_id,
            "paper_id": self.paper_id,
            "year": self.year,
            "question_text": self.question_text,
            "marks": self.marks,
            "unit_or_topic_guess": self.unit_or_topic_guess,
            "topic_id": self.topic_id,
        }


class Topic(Base):
    __tablename__ = "topics"

    id = Column(Integer, primary_key=True, index=True)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False)
    name = Column(String(255), nullable=False, index=True)
    frequency = Column(Integer, default=1)
    total_marks = Column(Integer, default=7)
    years_asked = Column(String(200), default="[]")  # JSON list of years
    last_year_asked = Column(Integer, default=2023)
    priority_score = Column(Float, default=0.0)
    priority_level = Column(String(20), default="Medium")  # "High", "Medium", "Low"
    priority_breakdown = Column(Text, default="{}")  # JSON string of calculation weights
    has_notes_source = Column(Boolean, default=False, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    subject = relationship("Subject", back_populates="topics")
    questions = relationship("Question", back_populates="topic")
    notes = relationship("NoteCache", back_populates="topic", cascade="all, delete-orphan")
    quizzes = relationship("QuizCache", back_populates="topic", cascade="all, delete-orphan")
    suggested_questions = relationship("SuggestedQuestion", back_populates="topic")

    def get_years_list(self):
        try:
            return json.loads(self.years_asked)
        except Exception:
            return [int(y.strip()) for y in self.years_asked.split(",") if y.strip().isdigit()]

    def get_breakdown_dict(self):
        try:
            return json.loads(self.priority_breakdown)
        except Exception:
            return {}

    def to_dict(self):
        return {
            "id": self.id,
            "subject_id": self.subject_id,
            "name": self.name,
            "frequency": self.frequency,
            "total_marks": self.total_marks,
            "years_asked": self.get_years_list(),
            "last_year_asked": self.last_year_asked,
            "priority_score": round(self.priority_score, 1),
            "priority_level": self.priority_level,
            "priority_breakdown": self.get_breakdown_dict(),
            "has_notes_source": bool(self.has_notes_source),
            "questions_count": len(self.questions) if self.questions else self.frequency,
        }


class RepeatedQuestionGroup(Base):
    __tablename__ = "repeated_question_groups"

    id = Column(Integer, primary_key=True, index=True)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False)
    canonical_question = Column(Text, nullable=False)
    similarity_score = Column(Float, default=0.85)
    years = Column(String(200), default="[]")  # JSON list of years
    question_ids = Column(String(200), default="[]")  # JSON list of question IDs
    questions_data = Column(Text, default="[]")  # JSON array of {text, year, marks}
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    subject = relationship("Subject", back_populates="repeated_groups")

    def get_questions_list(self):
        try:
            return json.loads(self.questions_data)
        except Exception:
            return []

    def get_years_list(self):
        try:
            return json.loads(self.years)
        except Exception:
            return []

    def to_dict(self):
        return {
            "id": self.id,
            "subject_id": self.subject_id,
            "canonical_question": self.canonical_question,
            "similarity_score": round(self.similarity_score * 100, 1),
            "years": self.get_years_list(),
            "questions": self.get_questions_list(),
            "repeat_count": len(self.get_questions_list()),
        }


class SuggestedQuestion(Base):
    __tablename__ = "suggested_questions"

    id = Column(Integer, primary_key=True, index=True)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False)
    topic_id = Column(Integer, ForeignKey("topics.id"), nullable=True)
    topic_name = Column(String(255), nullable=False)
    question_text = Column(Text, nullable=False)
    question_type = Column(String(50), default="short answer")  # short answer, long answer, numerical, MCQ, definition
    expected_marks = Column(Integer, default=5)
    why_important = Column(Text, nullable=True)
    difficulty = Column(String(20), default="Medium")  # Easy, Medium, Hard
    answer_outline = Column(Text, nullable=True)
    source = Column(String(50), default="notes")  # "notes" or "ai_estimate"
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    subject = relationship("Subject", back_populates="suggested_questions")
    topic = relationship("Topic", back_populates="suggested_questions")

    def to_dict(self):
        return {
            "id": self.id,
            "subject_id": self.subject_id,
            "topic_id": self.topic_id,
            "topic_name": self.topic_name,
            "question_text": self.question_text,
            "question_type": self.question_type,
            "expected_marks": self.expected_marks,
            "why_important": self.why_important,
            "difficulty": self.difficulty,
            "answer_outline": self.answer_outline,
            "source": self.source,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class NoteCache(Base):
    __tablename__ = "note_caches"

    id = Column(Integer, primary_key=True, index=True)
    topic_id = Column(Integer, ForeignKey("topics.id"), nullable=False)
    language = Column(String(10), default="en")  # "en" or "hi"
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    topic = relationship("Topic", back_populates="notes")

    def to_dict(self):
        return {
            "id": self.id,
            "topic_id": self.topic_id,
            "language": self.language,
            "content": self.content,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class QuizCache(Base):
    __tablename__ = "quiz_caches"

    id = Column(Integer, primary_key=True, index=True)
    topic_id = Column(Integer, ForeignKey("topics.id"), nullable=False)
    quiz_json = Column(Text, nullable=False)  # JSON array of 5 questions
    difficulty = Column(String(20), default="medium", nullable=True)
    question_count = Column(Integer, default=5, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    topic = relationship("Topic", back_populates="quizzes")

    def to_dict(self):
        try:
            quiz_data = json.loads(self.quiz_json)
        except Exception:
            quiz_data = []
        return {
            "id": self.id,
            "topic_id": self.topic_id,
            "difficulty": self.difficulty or "medium",
            "question_count": self.question_count or len(quiz_data),
            "quiz": quiz_data,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class ExtractionCache(Base):
    """Caches raw AI question extraction and classification by SHA-256 file content hash."""
    __tablename__ = "extraction_caches"

    id = Column(Integer, primary_key=True, index=True)
    file_hash = Column(String(64), unique=True, index=True, nullable=False)
    extracted_json = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        try:
            return json.loads(self.extracted_json)
        except Exception:
            return {}

