import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./examsense.db")

# Normalize Render/Heroku postgres:// URLs to postgresql:// for SQLAlchemy compatibility
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# For SQLite, check_same_thread=False and timeout=30 are required for FastAPI concurrency
connect_args = {"check_same_thread": False, "timeout": 30} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)

if DATABASE_URL.startswith("sqlite"):
    from sqlalchemy import event
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        try:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL;")
            cursor.execute("PRAGMA busy_timeout=30000;")
            cursor.close()
        except Exception:
            pass

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """Dependency that yields a database session and closes it afterwards."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def migrate_db():
    """Ensure newly added columns exist in existing SQLite/Postgres DBs without breaking existing data."""
    try:
        from sqlalchemy import inspect, text
        inspector = inspect(engine)
        tables = inspector.get_table_names()

        # 1. Migrate subjects table
        if "subjects" in tables:
            subj_cols = [col["name"] for col in inspector.get_columns("subjects")]
            with engine.begin() as conn:
                if "exam_type" not in subj_cols:
                    conn.execute(text("ALTER TABLE subjects ADD COLUMN exam_type VARCHAR(50) DEFAULT 'General'"))
                if "owner_id" not in subj_cols:
                    conn.execute(text("ALTER TABLE subjects ADD COLUMN owner_id VARCHAR(100)"))
                if "is_demo" not in subj_cols:
                    conn.execute(text("ALTER TABLE subjects ADD COLUMN is_demo BOOLEAN DEFAULT 0"))
                if "source" not in subj_cols:
                    conn.execute(text("ALTER TABLE subjects ADD COLUMN source VARCHAR(50) DEFAULT 'papers'"))
                if "status" not in subj_cols:
                    conn.execute(text("ALTER TABLE subjects ADD COLUMN status VARCHAR(50) DEFAULT 'ready'"))
                if "progress_text" not in subj_cols:
                    conn.execute(text("ALTER TABLE subjects ADD COLUMN progress_text VARCHAR(255) DEFAULT 'Ready'"))
                if "error_message" not in subj_cols:
                    conn.execute(text("ALTER TABLE subjects ADD COLUMN error_message TEXT"))

        # 2. Migrate papers table
        if "papers" in tables:
            paper_cols = [col["name"] for col in inspector.get_columns("papers")]
            with engine.begin() as conn:
                if "doc_type" not in paper_cols:
                    conn.execute(text("ALTER TABLE papers ADD COLUMN doc_type VARCHAR(50) DEFAULT 'paper'"))
                if "questions_found" not in paper_cols:
                    conn.execute(text("ALTER TABLE papers ADD COLUMN questions_found INTEGER DEFAULT 0"))

        # 3. Migrate topics table
        if "topics" in tables:
            topic_cols = [col["name"] for col in inspector.get_columns("topics")]
            with engine.begin() as conn:
                if "has_notes_source" not in topic_cols:
                    conn.execute(text("ALTER TABLE topics ADD COLUMN has_notes_source BOOLEAN DEFAULT 0"))

        # 4. Migrate quiz_caches table
        if "quiz_caches" in tables:
            quiz_cols = [col["name"] for col in inspector.get_columns("quiz_caches")]
            with engine.begin() as conn:
                if "difficulty" not in quiz_cols:
                    conn.execute(text("ALTER TABLE quiz_caches ADD COLUMN difficulty VARCHAR(20) DEFAULT 'medium'"))
                if "question_count" not in quiz_cols:
                    conn.execute(text("ALTER TABLE quiz_caches ADD COLUMN question_count INTEGER DEFAULT 5"))
    except Exception as e:
        logger.warning(f"Database migration note: {e}")


