# ExamSense 🎓
> *"Kya padhna hai, ab AI batayega."*

[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Database](https://img.shields.io/badge/Database-SQLite%20%7C%20PostgreSQL-003B57?style=flat&logo=sqlite&logoColor=white)](https://www.sqlite.org/)
[![ML](https://img.shields.io/badge/ML-TF--IDF%20%26%20Cosine%20Similarity-F7931E?style=flat&logo=scikit-learn&logoColor=white)](https://scikit-learn.org/)
[![AI](https://img.shields.io/badge/AI-Google%20Gemini%20API-4285F4?style=flat&logo=google&logoColor=white)](https://ai.google.dev/)
[![Audience](https://img.shields.io/badge/Audience-For%20Every%20Student%2C%20Every%20Exam-7c3aed?style=flat)]()

---

## 📌 Project Overview
**ExamSense** is a universal AI-powered exam intelligence platform built for **every student and every exam**:
- **School Board Students:** Class 10 & 12 (CBSE, ICSE, State Boards).
- **College & University Students:** Engineering (B.Tech/B.E.), B.Sc, B.Com, BCA, MCA, MBA.
- **Competitive Exam Aspirants:** JEE, NEET, UPSC, SSC, GATE, Banking & Professional Certifications.

Instead of studying blind or drowning in hundreds of textbook pages before an exam, students upload past question papers or study notes. In under 60 seconds, ExamSense:
1. **Direct Multimodal & OCR Extraction:** Sends PDFs or photos directly to Gemini (File API) or PyMuPDF/OCR fallback.
2. **Non-Blocking Background Processing:** Upload returns immediately; real-time polling updates progress (*"Reading page 3 of 12...", "Finding questions...", "Ranking topics..."*).
3. **Repeated Questions Detection:** Identifies recurring questions across exam years via **scikit-learn TF-IDF Vectorization & Cosine Similarity**.
4. **Transparent Priority Prediction:** Computes an explainable Exam Priority Score (0–100) classifying chapters as **High, Medium, or Low Priority**.
5. **Start with Just a Subject Name:** Instant AI curriculum estimate for students without old papers (*Honest note: AI estimate mode provides common curriculum patterns based on syllabus importance, not actual paper statistical frequency*).
6. **Study Notes Upload & Important Questions:** Uploads lecture notes, unlocks high-yield questions with on-demand **AI Answer Outlines**, and gives a **+5 Notes Priority Bonus**.
7. **Study Checklist Tracker:** In-browser persistent checklist to tick off topics as you finish them.
8. **Bilingual Revision Notes & Quizzes:** Instant revision notes (English & Hinglish) and customizable 5/10-question MCQ practice quizzes with confetti.
9. **Reorganized PDF Export:** Customized, print-ready 7-Day study plan with cover, topic tables, repeated questions, checkboxes (☐), and schedule.
10. **Zero-Configuration Samples:** 3 pre-analyzed offline samples (College DBMS CS-501, School Class 10 Science, Competitive Physics) available without any API key!

---

## 🔒 Security & Privacy Architecture
- **Session Visitor Isolation:** Each visitor is assigned a random HTTP-only `examsense_vid` cookie (valid for 1 year). Visitors can only see and delete their own subjects. Shared sample datasets and legacy subjects are read-only (`can_delete=False`).
- **In-Memory Rate Limiting:** 10 file uploads per hour and 40 AI notes/quiz requests per hour per IP with friendly user warnings.
- **Privacy First:** Uploaded papers and notes are private to your session and used solely to build your personal study plan.
- **Safe SQLite & Postgres Migrations:** Automated schema migration at startup via `PRAGMA table_info` + `ALTER TABLE ADD COLUMN` ensures database persistence without breaking existing rows.

---

## ⚙️ Environment Variables & Configuration

Copy `.env.example` to `.env`:
```env
# Google Gemini API Configuration
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.5-flash

# Maximum upload size in Megabytes (default: 40 MB)
MAX_UPLOAD_SIZE_MB=40

# Database Connection (SQLite by default, or Postgres on Render/Neon/Supabase)
DATABASE_URL=sqlite:///./examsense.db
# DATABASE_URL=postgresql://user:password@ep-xyz.neon.tech/examsense?sslmode=require

# Server Configuration
PORT=8000
HOST=0.0.0.0
UPLOAD_DIR=./uploads
```

### Checking System & AI Health
Inspect system configuration and active model status at any time:
```bash
curl http://localhost:8000/api/health
```
Example response:
```json
{
  "status": "healthy",
  "gemini_api_configured": true,
  "gemini_working": true,
  "model_in_use": "gemini-2.5-flash",
  "last_error": null,
  "app": "ExamSense v1.2",
  "tagline": "Kya padhna hai, ab AI batayega.",
  "max_upload_size_mb": 40
}
```

---

## 🚀 Running Locally

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run the application
uvicorn app.main:app --reload --port 8000

# 3. Open in your browser
http://localhost:8000
```

### Running Tests
Execute the comprehensive 20-point test suite:
```bash
python test_app.py
```

---

## ☁️ Deployment on Render (Free Plan)

A `Procfile` is included for deployment on Render:
```
web: uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

### Free Plan Persistence Note
On Render's free tier, the local disk is ephemeral and SQLite resets when the service spins down due to inactivity.
To maintain permanent data across restarts:
1. Create a free PostgreSQL database on [Neon.tech](https://neon.tech) or [Supabase](https://supabase.com).
2. In the Render Dashboard under **Environment**, set:
   - `DATABASE_URL` = `your_neon_or_supabase_postgres_url` (ExamSense automatically converts `postgres://` to `postgresql://`).
   - `GEMINI_API_KEY` = your Google AI Studio API key.
   - `MAX_UPLOAD_SIZE_MB` = `40`.

---

## 🔬 Exam Priority Scoring Formula

$$\text{Priority Score (0--100)} = \text{FreqPts (40\%)} + \text{MarksPts (25\%)} + \text{RecencyPts (15\%)} + \text{GapBonus (20\%)} + \text{NotesBonus (+5)}$$

1. **Exam Frequency (40%):** Consistency of appearance across past examination papers.
2. **Total Marks Weight (25%):** Cumulative marks relative to standard question weight.
3. **Recency Weight (15%):** Topics appearing in the most recent exam cycle.
4. **Gap Comeback Bonus (20%):** High-frequency topics skipped in the immediately preceding 1–2 cycles have a high probability of rotational return.
5. **Notes Reinforcement Bonus (+5 pts):** Topics found in both your uploaded papers and your study notes receive an extra boost.

---

## 📄 License & Credits
- **Project:** ExamSense
- **Tagline:** *"Kya padhna hai, ab AI batayega."*
- **Theme:** Universal AI exam preparation platform for all students.
