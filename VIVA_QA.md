# 🎓 ExamSense — Viva Examination Questions & Answers
> **Comprehensive 15-Question Preparation Guide for College Minor Project Viva Evaluation**  
> Covers: Architecture, NLP (TF-IDF & Cosine Similarity), Priority Formula, Databases, Error Handling & Limitations.

---

### Q1. What is the core problem statement of ExamSense?
**Answer:**  
In Indian engineering universities (e.g., RGPV, AKTU, VTU), semester syllabi are broad, and students often struggle to prioritize their revision time in the final weeks before exams. While previous years' question papers (PYQs) contain cyclical trends and repeated questions, manual analysis of multiple PDFs is time-consuming and subjective. ExamSense automates this entire pipeline: extracting questions from past papers, discovering recurring questions using TF-IDF similarity, calculating a transparent 4-factor priority score, and generating revision notes and quizzes.

---

### Q2. Explain the overall system architecture of ExamSense.
**Answer:**  
ExamSense follows a decoupled, 3-tier modular architecture:
1. **Frontend Presentation Tier:** Lightweight Vanilla HTML5, CSS3, and modern JavaScript served directly by FastAPI. It utilizes Chart.js for data visualization and Marked.js for rendering markdown revision notes, eliminating the overhead of heavy frameworks like React or Angular.
2. **Application / Service Tier (FastAPI):**
   - `pdf_service.py`: Extracts raw text via PyMuPDF (`fitz`) with OCR fallback.
   - `ai_service.py`: Interfaces with Google Gemini API for question boundary segmentation, topic normalization, and notes/quiz generation.
   - `analysis_service.py`: Computes TF-IDF vectorization and cosine similarity to find near-duplicate questions.
   - `priority_service.py`: Computes transparent, explainable priority metrics.
   - `pdf_export_service.py`: Generates printable study plan PDFs using ReportLab.
3. **Data Persistence Tier (SQLite + SQLAlchemy):** Stores subjects, papers, extracted questions, calculated topics, repeated question groups, and cached revision notes/quizzes.

---

### Q3. Why did you choose FastAPI over Flask or Django?
**Answer:**  
1. **Performance & Asynchronous I/O:** FastAPI is built on Starlette and ASGI, providing near-Node.js/Go performance for asynchronous I/O operations such as handling multiple concurrent PDF uploads and LLM streaming calls.
2. **Pydantic Validation & OpenAPI:** FastAPI natively integrates Pydantic for strict request/response data validation and auto-generates interactive Swagger API documentation at `/docs`.
3. **Simplicity over Django:** Django is monolithic with heavy ORM overhead, which is unnecessary for a lightweight, fast semester project. Flask lacks native async and modern type-hinted validation.

---

### Q4. How does the TF-IDF and Cosine Similarity algorithm work to find repeated questions?
**Answer:**  
1. **Text Preprocessing:** The question text is normalized by stripping exam prefixes (e.g., `Q.1`, `Question 2(a)`), removing marks labels (`[7M]`), lowercasing, and removing English stop words.
2. **TF-IDF Vectorization:**
   - **Term Frequency (TF):** Measures how frequently a word occurs in a question.
   - **Inverse Document Frequency (IDF):** Penalizes generic words across the question corpus and rewards domain-specific keywords (e.g., *“BCNF”*, *“Serializability”*, *“Deadlock”*).
   - Each question is transformed into a high-dimensional sparse vector.
3. **Cosine Similarity:** The dot product of two normalized vectors computes the cosine of the angle between them:
   $$\text{Cosine Similarity}(A, B) = \frac{A \cdot B}{\|A\| \|B\|}$$
   Values range from $0.0$ to $1.0$. Pairs with a score $\ge 0.65$ are clustered using connected component graph traversal, capturing questions that test the same concept even if worded slightly differently across years.

---

### Q5. What is the mathematical formula used for Priority Prediction, and why is it explainable?
**Answer:**  
ExamSense predicts topic priority on a scale of $0$ to $100$ using four transparent weighted parameters:
$$\text{Score} = \text{Frequency Pts (40\%)} + \text{Marks Pts (25\%)} + \text{Recency Pts (15\%)} + \text{Gap Bonus (20\%)}$$

- **Frequency Pts (up to 40):** Calculated as $\min(40, \text{Frequency} \times 10)$. Core syllabus topics asked repeatedly earn maximum points.
- **Marks Pts (up to 25):** Evaluates total cumulative marks relative to standard question weight.
- **Recency Pts (up to 15):** Topics asked in the most recent exam cycle get up to 15 points.
- **University Gap Comeback Bonus (up to 20):** If a high-frequency topic ($\ge 2$ appearances) was omitted in the latest exam cycle ($Y_{\text{latest}} - Y_{\text{topic}} = 1$), it receives a 20-point bonus because university examiners routinely rotate core omitted concepts back into the upcoming examination.

Topics with scores $\ge 65$ are classified as **High Priority**, $42\text{--}64$ as **Medium Priority**, and $< 42$ as **Low Priority**.

---

### Q6. How do you handle malformed or invalid JSON returned by the LLM?
**Answer:**  
In `app/services/ai_service.py`:
1. The prompt enforces strict JSON formatting: `Return ONLY a valid JSON array adhering to this schema...`.
2. A sanitization function (`clean_and_parse_json`) strips markdown code fences (````json ... ````), extracts outermost brackets `[...]`, and cleans trailing commas before closing braces.
3. If JSON parsing fails on the first attempt, the function automatically catches the exception, updates the prompt with explicit strict JSON instructions, and executes an automated second retry.
4. If both LLM attempts fail or the API is unavailable, the system seamlessly falls back to a deterministic regex-based question segmenter, preventing runtime crashes.

---

### Q7. How does PyMuPDF extract text, and how do you handle scanned/image PDFs?
**Answer:**  
In `app/services/pdf_service.py`:
1. We use **PyMuPDF (`fitz`)**, which parses the PDF's internal font and glyph dictionaries to extract digital text across pages in milliseconds.
2. If the total extracted text across all pages is under 60 characters, the PDF is recognized as a scanned or image-based document.
3. If `pytesseract` and Tesseract OCR are installed, the engine renders each PDF page to a 200 DPI image and applies optical character recognition.
4. If OCR is unavailable or the scan is illegible, the service raises a user-friendly error instructing the student to provide a readable copy or explore the pre-built Demo mode.

---

### Q8. Why did you use SQLite and SQLAlchemy instead of MongoDB or PostgreSQL?
**Answer:**  
1. **Zero Configuration & Portability:** SQLite is a self-contained, serverless, file-based relational database (`examsense.db`). An examiner or student can clone the repository and run it instantly without configuring database servers, Docker containers, or managing connection pools.
2. **Relational Integrity:** The domain model has strict relational dependencies (Subjects $\rightarrow$ Papers $\rightarrow$ Questions $\rightarrow$ Topics $\rightarrow$ Caches). SQLAlchemy ORM provides type-safe cascading deletes, migrations, and declarative schema models.
3. **Concurrency Control:** Configured with `check_same_thread=False` to handle asynchronous multi-threaded requests smoothly in FastAPI.

---

### Q9. How does caching work for Revision Notes and Practice Quizzes?
**Answer:**  
LLM API calls consume credits and introduce network latency (1 to 3 seconds). ExamSense implements a caching layer via `NoteCache` and `QuizCache` database tables:
1. When a user requests notes for a topic (e.g. `GET /api/topics/5/notes?language=en`), the endpoint queries `NoteCache` where `topic_id = 5` and `language = 'en'`.
2. If a cached record exists, it returns immediately in $< 10$ milliseconds.
3. If no cache exists, it invokes Gemini, stores the generated output in SQLite, and returns the response. Future requests for the same topic require zero API calls.

---

### Q10. What is the significance of the Hindi/English (Hinglish) toggle for notes?
**Answer:**  
Most Indian engineering students think and communicate in colloquial Hinglish (*Hindi written in English script*). Academic English textbooks can be verbose and hard to digest during the night before an exam. The prompt instructs Gemini:
> *"Write in student-friendly, natural Hinglish (e.g., 'Normalization ka main purpose database me redundancy aur anomalies ko eliminate karna hota hai.')."*  
This pedagogical feature helps students understand abstract concepts faster without translating mental models.

---

### Q11. How does the 1-Click "Load Demo Data" work without an internet connection or Gemini API key?
**Answer:**  
In `app/services/demo_service.py`:
- We bundled a realistic, curated question bank based on 4 years of RGPV CS-501 Database Management Systems exam papers (25 questions across 8 core topics).
- When the user clicks **"Load Demo Data"**, the service executes pure Python algorithms locally: populating subjects, executing TF-IDF repeat clustering, computing priority scores, and seeding notes and quizzes into SQLite.
- This ensures 100% reliable evaluation during college vivas even if college Wi-Fi is down or API quotas are exhausted.

---

### Q12. How do you prevent security vulnerabilities like SQL Injection, Path Traversal, and DoS?
**Answer:**  
1. **SQL Injection:** Avoided by using SQLAlchemy's parameterized query builder rather than raw SQL string concatenation.
2. **Path Traversal:** File uploads are processed using `sanitize_filename()`, stripping `../`, path separators, and special characters before writing to the `uploads/` directory.
3. **File Size & DoS Protection:** Rejects files exceeding 10 MB and restricts input to `.pdf` extensions.
4. **XSS Protection:** User-rendered content in `app.js` is sanitized with HTML entity escaping (`escapeHtml`).

---

### Q13. How does the PDF Study Plan export feature work?
**Answer:**  
In `app/services/pdf_export_service.py`, ExamSense utilizes **ReportLab**:
1. Creates an in-memory `io.BytesIO` buffer (avoiding temporary disk files).
2. Assembles structured `Flowable` elements (`Paragraph`, `Table`, `HRFlowable`) styled with custom typography and color palettes.
3. Generates a multi-page document containing the executive summary, prioritized study matrix, and recurring question clusters.
4. Returns the buffer via FastAPI's `StreamingResponse` with `Content-Disposition: attachment; filename=...`.

---

### Q14. What are the current limitations of ExamSense?
**Answer:**  
1. **Heavily Degraded Scanned Papers:** Low-resolution, skewed, or handwritten exam scans may yield poor OCR accuracy without advanced computer vision pre-processing.
2. **Mathematical Diagrams & Circuit Diagrams:** Pure text extraction cannot extract electrical circuit diagrams, graphs, or equations embedded as bitmaps.
3. **Historical Data Dependency:** Priority prediction requires at least 3 years of papers to establish a meaningful statistical pattern.

---

### Q15. What are the future enhancements you plan to add to this project?
**Answer:**  
1. **Multimodal Vision Models:** Leveraging Gemini Multimodal Vision to interpret handwritten equations, circuit diagrams, and mathematical matrices.
2. **Automated Syllabus Unit Mapping:** Ingesting the university syllabus PDF to map questions automatically to Unit 1 through Unit 5.
3. **Audio Revision Flashcards:** Generating short 60-second podcast-style audio summaries for each topic so students can revise while commuting.
4. **Peer Study Rooms:** Real-time quiz battles with classmates via WebSockets.
