# ExamSense 🎓
> *"Kya padhna hai, ab AI batayega."*

[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![SQLite](https://img.shields.io/badge/Database-SQLite%20%2B%20SQLAlchemy-003B57?style=flat&logo=sqlite&logoColor=white)](https://www.sqlite.org/)
[![Scikit-Learn](https://img.shields.io/badge/ML-TF--IDF%20%26%20Cosine%20Similarity-F7931E?style=flat&logo=scikit-learn&logoColor=white)](https://scikit-learn.org/)
[![Gemini AI](https://img.shields.io/badge/AI-Google%20Gemini%20API-4285F4?style=flat&logo=google&logoColor=white)](https://ai.google.dev/)
[![Status](https://img.shields.io/badge/Status-Complete%20%26%20Viva--Ready-success?style=flat)]()

---

## 📌 Project Overview
**ExamSense** is an AI-powered examination intelligence platform designed specifically for Indian university and college students (e.g., **RGPV, AKTU, VTU, Mumbai University, Anna University**). 

Instead of randomly studying 500 pages of notes 24 hours before a semester exam, students upload 3–5 years of previous year question papers (PDFs). ExamSense automatically:
1. **Splits and extracts individual questions** with marks and topics using PyMuPDF and LLMs.
2. **Detects recurring & repeated questions** across exam cycles using **TF-IDF Vectorization & Cosine Similarity**.
3. **Calculates a mathematically explainable Exam Priority Score (0–100)** to classify topics as **High, Medium, or Low Priority**.
4. **Generates instant revision notes** with an **English / Hinglish (Hindi-English)** toggle.
5. **Generates an interactive 5-question Practice Quiz** with instant scoring and detailed answers.
6. **Exports a downloadable ExamSense Study Plan PDF** ready for printing.
7. **Includes a 1-Click "Load Demo Data" button** that pre-loads realistic RGPV *CS-501 Database Management Systems* exam papers for complete offline presentation during viva without requiring an internet connection or API key!

---

## 🚀 Key Features

### 1. Multi-Year PDF Upload & Text Extraction
- Upload multiple university PDF papers simultaneously.
- Assign exam year to each paper (e.g., 2020, 2021, 2022, 2023).
- Fast text extraction via **PyMuPDF (`fitz`)** with OCR fallback for scanned papers.
- Input validation, file size limits (10 MB), and sanitization.

### 2. Intelligent Question Splitting
- Uses **Google Gemini 1.5 Flash / 2.0 Flash** to parse messy question papers into strict JSON records:
  ```json
  [
    {
      "question_text": "What is Normalization? Explain 1NF, 2NF and 3NF with examples.",
      "marks": 7,
      "unit_or_topic_guess": "Normalization & Normal Forms",
      "year": 2021
    }
  ]
  ```
- Safe JSON cleaning and automated retry handling.
- Built-in heuristic fallback regex extractor if offline.

### 3. Topic Analysis & TF-IDF Repeat Detection Engine
- Normalizes and groups similar topic variations (e.g., *"Normalization"* and *"DB Normalization"* $\rightarrow$ *"Normalization & Normal Forms"*).
- Calculates topic frequency, total marks, years appeared, and recency.
- Detects near-duplicate questions across different years using **scikit-learn TF-IDF + Cosine Similarity** ($\ge 65\%$ semantic match).

### 4. Transparent Exam Priority Prediction Formula
Unlike "black box" AI, ExamSense uses an explainable formula tailored for Indian university exam cycles:

$$\text{Priority Score (0--100)} = \text{FreqPts (40\%)} + \text{MarksPts (25\%)} + \text{RecencyPts (15\%)} + \text{GapBonus (20\%)}$$

- **Frequency Weight (0–40 pts):** Consistency across papers (10 pts per appearance).
- **Marks Weight (0–25 pts):** Aggregate marks relative to average question weight.
- **Recency Weight (0–15 pts):** Topics asked in the latest exam cycle carry higher baseline relevance.
- **University Gap Comeback Bonus (0–20 pts):** If a historically high-frequency topic ($\ge 2$ appearances) was skipped in the preceding 1–2 cycles, professors frequently bring it back!
- **Classification:**
  - 🔥 **High Priority ($\ge 65$ pts):** Core chapters that account for ~60% of question paper weightage.
  - ⚡ **Medium Priority ($42\text{--}64$ pts):** Expected standard questions.
  - 🌱 **Low Priority ($< 42$ pts):** Secondary or elective topics.

### 5. Interactive Visual Dashboard
- **Chart.js Bar Chart:** Topic frequency distribution across past years.
- **Chart.js Donut Chart:** High / Medium / Low priority split.
- **Filterable Priority Matrix:** Live search, filter by priority tier, and inspect formula breakdown.
- **Repeated Questions Accordion:** View exact variations asked across multiple years.
- **Download Study Plan:** Exports a professional multi-page PDF study guide via **ReportLab**.

### 6. Revision Notes & Practice Quizzes
- **Revision Notes:** Formatted in Markdown with definitions, key points, ASCII diagrams, and solved examples.
- **Hinglish / English Toggle:** Switch between formal English and natural student Hinglish (*"Normalization ka main goal redundancy reduce karna hai"*).
- **Practice Quiz:** 5 interactive MCQs with instant feedback, celebration confetti, and detailed solution reviews.
- **Smart Database Caching:** Caches notes and quizzes in SQLite to eliminate redundant API calls.

---

## 🛠️ Tech Stack & Architecture

```
ExamSense/
├── app/
│   ├── main.py                  # FastAPI server, endpoints, and static mounts
│   ├── database.py              # SQLite configuration with SQLAlchemy
│   ├── models.py                # Subject, Paper, Question, Topic, NoteCache, QuizCache
│   ├── services/
│   │   ├── pdf_service.py       # PyMuPDF text extraction & OCR detection
│   │   ├── ai_service.py        # Gemini API integration, retry logic & offline fallbacks
│   │   ├── analysis_service.py  # TF-IDF cosine similarity & topic grouping
│   │   ├── priority_service.py  # Transparent 4-factor scoring formula
│   │   ├── demo_service.py      # Preloaded RGPV CS-501 DBMS dataset
│   │   └── pdf_export_service.py# ReportLab PDF study plan generator
│   ├── static/
│   │   ├── css/style.css        # Modern glassmorphism, responsive styles & dark mode
│   │   └── js/app.js            # SPA controller, Chart.js, Marked.js, modals
│   └── templates/
│       └── index.html           # Single-page student dashboard UI
├── uploads/                     # Uploaded examination PDFs
├── requirements.txt             # Python dependencies
├── .env.example                 # Environment configuration template
├── README.md                    # Project documentation
├── DEMO_SCRIPT.md               # 3-minute viva presentation walkthrough
└── VIVA_QA.md                   # 15 viva examination questions & answers
```

---

## ⚙️ Setup and Installation

### Prerequisites
- Python 3.10 or higher
- `pip` package manager

### 1. Clone the repository
```bash
git clone https://github.com/your-username/examsense.git
cd examsense
```

### 2. Create and activate a virtual environment (Recommended)
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux / macOS
python3 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
# Windows
copy .env.example .env

# Linux / macOS
cp .env.example .env
```

Open `.env` and add your Google Gemini API Key:
```env
GEMINI_API_KEY=your_actual_gemini_api_key_here
DATABASE_URL=sqlite:///./examsense.db
UPLOAD_DIR=./uploads
PORT=8000
HOST=127.0.0.1
```

> **Note:** If you do not have a Gemini API key right now, ExamSense still works 100%! Simply click **"Load Demo Data"** on the dashboard to test all features with pre-analyzed RGPV exam papers.

---

## 🔑 How to Get a Free Google Gemini API Key

1. Go to [Google AI Studio](https://aistudio.google.com/).
2. Sign in with your Google account.
3. Click on **"Get API key"** in the top navigation.
4. Click **"Create API key in new project"**.
5. Copy your generated key and paste it into `.env` as `GEMINI_API_KEY=AIzaSy...`.

---

## ▶️ How to Run Locally

Start the development server with auto-reload:
```bash
uvicorn app.main:app --reload --port 8000
```

Open your browser and navigate to:
```
http://127.0.0.1:8000
```

---

## 🖥️ UI Screenshots & Walkthrough

| Feature | Description |
|---|---|
| **Landing Page** | 3-step explanation of the platform with quick-start buttons. |
| **Interactive Dashboard** | Real-time KPI counters, Chart.js frequency & priority charts. |
| **Topic Priority Matrix** | High/Medium/Low badges, search, filter, and score progress bars. |
| **Repeated Questions** | Semantic TF-IDF similarity clusters with match percentages. |
| **English / Hinglish Notes** | Markdown revision material tailored for Indian university students. |
| **Interactive Quiz** | 5-question MCQ challenge with confetti animation and solution review. |
| **PDF Study Plan Export** | Print-ready multi-page study strategy guide. |

---

## 🔮 Future Scope
- **Syllabus Unit Mapping:** Automatically map extracted questions to official university syllabus unit numbers (Unit 1 to Unit 5).
- **Multi-Subject Comparison:** Compare topic weights across different semesters or engineering branches.
- **Voice Revision:** Text-to-speech audio flashcards for quick revision while traveling.
- **Student Performance Tracker:** Track completed topics and score improvement over time.

---

## 👨‍💻 Author & Project Credits
- **Project Name:** ExamSense
- **Academic Project:** College Minor Project (B.Tech / B.E. Computer Science & Engineering)
- **Tagline:** *"Kya padhna hai, ab AI batayega."*
