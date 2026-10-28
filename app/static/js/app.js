/**
 * ExamSense — Frontend Application Controller
 * Tagline: "Kya padhna hai, ab AI batayega."
 */

// Global Application State
const state = {
  currentSubjectId: null,
  currentSubjectData: null,
  allSubjects: [],
  selectedFiles: [],
  uploadMode: "files", // 'files' | 'text'
  activeQuestionsFilter: "all", // 'all' | 'papers' | 'notes'
  
  // Notes state
  activeNotesTopicId: null,
  activeNotesTopicName: "",
  activeNotesLanguage: "en",
  
  // Quiz state
  activeQuizTopicId: null,
  activeQuizTopicName: "",
  activeQuizQuestions: [],
  activeQuizUserAnswers: {},
  activeQuizCurrentIndex: 0,
  activeQuizCount: 5,
  activeQuizDifficulty: "medium",
  
  // Charts
  frequencyChart: null,
  priorityChart: null,

  // Polling interval tracker
  uploadPollInterval: null,
  
  // UI Language
  uiLang: "en", // 'en' | 'hi'
};

// ============================================================================
// Bilingual UI Dictionary (English vs Hinglish)
// ============================================================================

const i18n = {
  en: {
    tagline: "Kya padhna hai, ab AI batayega.",
    sampleBtn: "Sample",
    uploadBtn: "Upload Papers",
    heroBadge: "For every student, every exam",
    heroTitle1: "Know what to study.",
    heroTitle2: "Upload old question papers and get a smart, ranked study plan in seconds.",
    heroDesc: "Whether school board, college degree, or competitive exams (JEE, NEET, UPSC, SSC, GATE) — upload question papers or notes to instantly discover repeated questions, predict high-priority topics, and practice with smart quizzes.",
    heroBtnUpload: "Upload my papers",
    heroBtnTopic: "Start with just a subject name",
    howItWorksTitle: "How ExamSense Works in 3 Steps",
    howItWorksSubtitle: "From past papers to targeted exam preparation in under 60 seconds",
    step1Title: "Upload Papers or Notes",
    step1Desc: "Drop PDFs or photos from your camera (even 1 paper works!), or paste question text directly. Auto-detects paper type and year.",
    step2Title: "AI Pattern & Repeat Detection",
    step2Desc: "TF-IDF vectors uncover repeated questions across years. Transparent formula ranks topics into High, Medium, and Low priority.",
    step3Title: "Targeted Study Plan & Notes",
    step3Desc: "Export a 7-day revision schedule as PDF. Review quick bullet notes in English or Hinglish and test yourself with 5-MCQ quizzes.",
    kpiHigh: "High Priority Topics (Must Study)",
    kpiRepeated: "Repeated Question Patterns",
    kpiTotal: "Total Questions Mapped",
    kpiYears: "Exam Cycles Analyzed",
    dashDownload: "Download Study Plan (PDF)",
    dashAddPapers: "Add Papers",
    dashAddNotes: "Add Notes",
    checklistTitle: "🎯 Study Checklist",
    checklistSubtitle: "Tick topics as you finish them to track your revision progress",
  },
  hi: {
    tagline: "Kya padhna hai, ab AI batayega.",
    sampleBtn: "Sample Dekhein",
    uploadBtn: "Papers Upload Karein",
    heroBadge: "Har Student, Har Exam Ke Liye",
    heroTitle1: "Janiye kya padhna hai.",
    heroTitle2: "Pichle saal ke question papers upload karein aur paayein smart, ranked study plan.",
    heroDesc: "School ho, college ho ya competitive exams (JEE, NEET, UPSC, SSC, GATE) — question papers ya notes upload karein aur paayein repeat hone wale questions, high-priority topics, revision notes aur quizzes.",
    heroBtnUpload: "Apne Papers Upload Karein",
    heroBtnTopic: "Sirf Subject Name Se Shuru Karein",
    howItWorksTitle: "ExamSense Kaise Kaam Karta Hai (3 Steps)",
    howItWorksSubtitle: "Purane papers se smart exam preparation sirf 60 seconds mein",
    step1Title: "Papers Ya Notes Upload Karein",
    step1Desc: "Camera photos, PDF ya text paste karein (1 paper bhi chalega!). Year aur type auto-detect hota hai.",
    step2Title: "Repeat Questions & Priority",
    step2Desc: "TF-IDF technology repeat questions dhundhti hai aur transparent formula se High, Medium, Low priority tay hoti hai.",
    step3Title: "Study Plan & Revision Notes",
    step3Desc: "7-Day revision plan PDF download karein, English ya Hinglish mein revision notes padhein aur MCQ quiz solve karein.",
    kpiHigh: "High Priority Topics (Zaroor Padhein)",
    kpiRepeated: "Repeat Hone Wale Questions",
    kpiTotal: "Total Mapped Questions",
    kpiYears: "Analyze Kiye Gaye Exam Years",
    dashDownload: "Study Plan PDF Download Karein",
    dashAddPapers: "Aur Papers Dalein",
    dashAddNotes: "Notes Dalein",
    checklistTitle: "🎯 Study Checklist",
    checklistSubtitle: "Padhe huye topics par tick karein aur apni revision track karein",
  }
};

// ============================================================================
// Initialization & Theme Handling
// ============================================================================

document.addEventListener("DOMContentLoaded", () => {
  initTheme();
  initLanguage();
  checkAiHealth();
  loadSubjectsList();
  updatePomoDisplay();
  updateXpDisplay();
});

function initTheme() {
  const savedTheme = localStorage.getItem("examsense_theme") || "light";
  if (savedTheme === "dark") {
    document.body.classList.remove("theme-light");
    document.body.classList.add("theme-dark");
    const icon = document.getElementById("themeIcon");
    if (icon) icon.textContent = "☀️";
  } else {
    document.body.classList.remove("theme-dark");
    document.body.classList.add("theme-light");
    const icon = document.getElementById("themeIcon");
    if (icon) icon.textContent = "🌙";
  }
}

function toggleTheme() {
  const isDark = document.body.classList.contains("theme-dark");
  if (isDark) {
    document.body.classList.remove("theme-dark");
    document.body.classList.add("theme-light");
    document.getElementById("themeIcon").textContent = "🌙";
    localStorage.setItem("examsense_theme", "light");
  } else {
    document.body.classList.remove("theme-light");
    document.body.classList.add("theme-dark");
    document.getElementById("themeIcon").textContent = "☀️";
    localStorage.setItem("examsense_theme", "dark");
  }

  if (state.frequencyChart && state.currentSubjectData) {
    renderCharts(state.currentSubjectData);
  }
}

function initLanguage() {
  const savedLang = localStorage.getItem("examsense_ui_lang") || "en";
  setUiLanguage(savedLang);
}

function toggleUiLanguage() {
  const nextLang = state.uiLang === "en" ? "hi" : "en";
  setUiLanguage(nextLang);
}

function setUiLanguage(lang) {
  state.uiLang = lang;
  localStorage.setItem("examsense_ui_lang", lang);

  const labelEl = document.getElementById("uiLangLabel");
  const iconEl = document.getElementById("uiLangIcon");
  if (labelEl && iconEl) {
    if (lang === "hi") {
      labelEl.textContent = "English";
      iconEl.textContent = "🇬🇧";
    } else {
      labelEl.textContent = "Hinglish";
      iconEl.textContent = "🇮🇳";
    }
  }

  // Update text elements
  const t = i18n[lang];
  if (!t) return;

  const updateText = (id, text) => {
    const el = document.getElementById(id);
    if (el) el.textContent = text;
  };

  updateText("navSampleBtnText", t.sampleBtn);
  updateText("navUploadBtnText", t.uploadBtn);
  updateText("heroBadgeText", t.heroBadge);
  updateText("heroTitleLine1", t.heroTitle1);
  updateText("heroTitleLine2", t.heroTitle2);
  updateText("heroDescText", t.heroDesc);
  updateText("heroBtnUpload", t.heroBtnUpload);
  updateText("heroBtnTopic", t.heroBtnTopic);
  updateText("howItWorksTitle", t.howItWorksTitle);
  updateText("howItWorksSubtitle", t.howItWorksSubtitle);
  updateText("step1Title", t.step1Title);
  updateText("step1Desc", t.step1Desc);
  updateText("step2Title", t.step2Title);
  updateText("step2Desc", t.step2Desc);
  updateText("step3Title", t.step3Title);
  updateText("step3Desc", t.step3Desc);
  updateText("kpiHighPriorityLabel", t.kpiHigh);
  updateText("kpiRepeatedQuestionsLabel", t.kpiRepeated);
  updateText("kpiTotalQuestionsLabel", t.kpiTotal);
  updateText("kpiExamYearsLabel", t.kpiYears);
  updateText("dashDownloadPdfBtnText", t.dashDownload);
  updateText("dashAddPapersBtnText", t.dashAddPapers);
  updateText("dashAddNotesBtnText", t.dashAddNotes);
}

// Toast Notifications
function showToast(message, type = "info") {
  const container = document.getElementById("toastContainer");
  if (!container) return;
  const toast = document.createElement("div");
  toast.className = `toast toast-${type}`;
  
  const icon = type === "success" ? "✅" : (type === "error" ? "⚠️" : "ℹ️");
  toast.innerHTML = `<span>${icon}</span><span>${escapeHtml(message)}</span>`;
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transform = "translateY(10px)";
    toast.style.transition = "all 0.3s ease";
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

// Share Functionality
function shareExamSense() {
  const url = window.location.origin;
  if (navigator.clipboard) {
    navigator.clipboard.writeText(url).then(() => {
      showToast("Link copied to clipboard! Share ExamSense with classmates.", "success");
    }).catch(() => {
      prompt("Copy ExamSense link:", url);
    });
  } else {
    prompt("Copy ExamSense link:", url);
  }
}

// Check AI Health on startup (uses cached/last-known state, 0 AI calls)
async function checkAiHealth() {
  try {
    const res = await fetch("/api/health");
    if (!res.ok) return;
    const data = await res.json();
    const banner = document.getElementById("aiUnavailableBanner");
    const bannerText = document.getElementById("aiUnavailableBannerText");
    const bannerIcon = document.getElementById("aiUnavailableBannerIcon");
    if (banner) {
      if (data.quota_exhausted) {
        banner.style.display = "block";
        if (bannerIcon) bannerIcon.textContent = "⏳";
        if (bannerText) {
          const resetsIn = data.quota_resets_in_seconds;
          let timeMsg = "";
          if (resetsIn > 0) {
            const h = Math.floor(resetsIn / 3600);
            const m = Math.floor((resetsIn % 3600) / 60);
            timeMsg = h > 0 ? ` (resets in ~${h}h ${m}m)` : ` (resets in ~${Math.max(1, m)}m)`;
          }
          bannerText.textContent = `Daily free-tier AI quota reached${timeMsg}. You can still explore the sample study plans below or enter your own Gemini API key in settings.`;
        }
      } else if (data.gemini_working === false) {
        banner.style.display = "block";
        if (bannerIcon) bannerIcon.textContent = "⚠️";
        if (bannerText) {
          bannerText.textContent = "AI is currently unavailable, you can still view the sample.";
        }
      } else {
        banner.style.display = "none";
      }
    }
  } catch (err) {
    console.warn("Health check error:", err);
  }
}

// ============================================================================
// Subject Loading & Switching
// ============================================================================

async function loadSubjectsList() {
  try {
    const res = await fetch("/api/subjects");
    if (!res.ok) throw new Error("Failed to load subjects");
    const subjects = await res.json();
    state.allSubjects = subjects;

    const dropdownWrapper = document.getElementById("subjectDropdownWrapper");
    const select = document.getElementById("subjectSelect");

    if (subjects.length > 0) {
      dropdownWrapper.style.display = "block";
      select.innerHTML = '<option value="">Switch Subject...</option>';

      // Separate visitor subjects vs demo/sample subjects
      const userSubjects = subjects.filter((s) => !s.is_demo && s.owner_id !== "demo");
      const sampleSubjects = subjects.filter((s) => s.is_demo || s.owner_id === "demo");

      if (userSubjects.length > 0) {
        const userGroup = document.createElement("optgroup");
        userGroup.label = "Your Subjects";
        userSubjects.forEach((s) => {
          const opt = document.createElement("option");
          opt.value = s.id;
          opt.textContent = `${s.name} (${s.code})`;
          userGroup.appendChild(opt);
        });
        select.appendChild(userGroup);
      }

      if (sampleSubjects.length > 0) {
        const sampleGroup = document.createElement("optgroup");
        sampleGroup.label = "Samples & Demos";
        sampleSubjects.forEach((s) => {
          const opt = document.createElement("option");
          opt.value = s.id;
          opt.textContent = `⚡ ${s.name} (${s.code})`;
          sampleGroup.appendChild(opt);
        });
        select.appendChild(sampleGroup);
      }

      // If user has their own subjects and nothing is selected yet, open their latest subject
      if (!state.currentSubjectId) {
        if (userSubjects.length > 0) {
          select.value = userSubjects[0].id;
          loadSubjectDashboard(userSubjects[0].id);
        } else {
          showLandingView();
        }
      }
    } else {
      dropdownWrapper.style.display = "none";
      showLandingView();
    }
  } catch (err) {
    console.error("Error loading subjects:", err);
  }
}

function onSubjectChange(subjectId) {
  if (subjectId) {
    loadSubjectDashboard(parseInt(subjectId));
  } else {
    showLandingView();
  }
}

function showLandingView() {
  document.getElementById("landingView").style.display = "block";
  document.getElementById("dashboardView").style.display = "none";
  state.currentSubjectId = null;
  const select = document.getElementById("subjectSelect");
  if (select) select.value = "";
}

async function loadSubjectDashboard(subjectId) {
  try {
    const res = await fetch(`/api/subjects/${subjectId}`);
    if (!res.ok) throw new Error("Could not fetch subject dashboard data.");
    const data = await res.json();

    state.currentSubjectId = subjectId;
    state.currentSubjectData = data;

    // Switch view
    document.getElementById("landingView").style.display = "none";
    document.getElementById("dashboardView").style.display = "block";

    // Update select dropdown value
    const select = document.getElementById("subjectSelect");
    if (select) select.value = subjectId;

    // Header info & Source Badge
    const subject = data.subject;
    document.getElementById("dashSubjectName").textContent = subject.name;
    document.getElementById("dashSubjectCode").textContent = subject.code;
    
    // Exam level
    const levelBadge = document.getElementById("dashExamLevel");
    levelBadge.textContent = subject.exam_type || "General";

    // Source badge
    const sourceBadge = document.getElementById("dashSourceBadge");
    if (subject.is_demo || subject.source === "demo") {
      sourceBadge.textContent = "SAMPLE";
      sourceBadge.className = "badge-source badge-source-demo";
    } else if (subject.source === "ai_estimate") {
      sourceBadge.textContent = "AI estimate";
      sourceBadge.className = "badge-source badge-source-ai";
    } else {
      sourceBadge.textContent = "Based on your papers";
      sourceBadge.className = "badge-source badge-source-papers";
    }

    // AI estimate banner handling
    const aiBanner = document.getElementById("aiEstimateBanner");
    const repSection = document.getElementById("repeatedQuestionsSection");
    const repCard = document.getElementById("kpiRepeatedQuestionsCard");
    const yearsCard = document.getElementById("kpiExamYearsCard");
    const thYears = document.getElementById("thYearsAsked");
    const thLastExam = document.getElementById("thLastExam");

    if (subject.source === "ai_estimate") {
      if (aiBanner) aiBanner.style.display = "block";
      if (repSection) repSection.style.display = "none";
      if (repCard) repCard.style.display = "none";
      if (yearsCard) yearsCard.style.display = "none";
      if (thYears) thYears.style.display = "none";
      if (thLastExam) thLastExam.style.display = "none";
    } else {
      if (aiBanner) aiBanner.style.display = "none";
      if (repSection) repSection.style.display = "block";
      if (repCard) repCard.style.display = "flex";
      if (yearsCard) yearsCard.style.display = "flex";
      if (thYears) thYears.style.display = "";
      if (thLastExam) thLastExam.style.display = "";
    }

    // Delete button permission check
    const deleteBtn = document.getElementById("btnDeleteSubject");
    if (deleteBtn) {
      deleteBtn.style.display = subject.can_delete ? "inline-flex" : "none";
    }

    // Exam years
    const years = data.stats.years_covered || [];
    const yearsStr = years.length > 0
      ? (years.length === 1 ? `${years[0]} Paper` : `${years[0]} – ${years[years.length - 1]} Papers`)
      : (subject.source === "ai_estimate" ? "Curriculum Analysis" : "1 Paper Cycle");
    document.getElementById("dashExamYears").textContent = yearsStr;

    // KPIs
    document.getElementById("kpiHighPriority").textContent = data.stats.high_priority_count;
    document.getElementById("kpiRepeatedQuestions").textContent = data.stats.repeated_groups_count;
    document.getElementById("kpiTotalQuestions").textContent = data.stats.total_questions;
    document.getElementById("kpiExamYears").textContent = years.length || (subject.source === "ai_estimate" ? "1" : data.stats.total_papers);

    // Render components
    renderChecklist(subjectId, data.topics);
    renderCharts(data);
    renderTopicsTable(data.topics);
    if (subject.source !== "ai_estimate") {
      renderRepeatedQuestions(data.repeated_groups);
    }
    renderImportantQuestions();
    loadFormulaWall();

    window.scrollTo({ top: 0, behavior: "smooth" });
  } catch (err) {
    showToast(err.message, "error");
  }
}

// ============================================================================
// Study Checklist Tracker (Persisted in localStorage)
// ============================================================================

function getChecklistKey(subjectId) {
  return `examsense_checklist_${subjectId}`;
}

function renderChecklist(subjectId, topics) {
  const container = document.getElementById("checklistItemsList");
  const progressText = document.getElementById("checklistProgressText");
  const progressFill = document.getElementById("checklistProgressFill");

  if (!container || !topics || topics.length === 0) {
    if (container) container.innerHTML = `<div class="text-muted" style="font-size: 13px;">No topics available yet.</div>`;
    updateMarksCoverageMeter(0);
    return;
  }

  const saved = JSON.parse(localStorage.getItem(getChecklistKey(subjectId)) || "{}");
  container.innerHTML = "";

  // Apply Panic Mode filters if active
  let displayTopics = topics;
  if (currentStudyMode === "panic12") {
    displayTopics = topics.filter(t => t.priority_level === "High" || t.priority_score >= 60);
    if (displayTopics.length < 3) displayTopics = topics.slice(0, Math.min(5, topics.length));
  } else if (currentStudyMode === "panic6") {
    displayTopics = [...topics].sort((a, b) => b.priority_score - a.priority_score).slice(0, Math.min(5, topics.length));
  }

  let completedCount = 0;
  let completedMarks = 0;
  let totalMarks = 0;

  displayTopics.forEach((topic) => {
    const isChecked = Boolean(saved[topic.id]);
    const topicMarks = Number(topic.total_marks) || (topic.frequency * 7) || 7;
    totalMarks += topicMarks;

    if (isChecked) {
      completedCount++;
      completedMarks += topicMarks;
    }

    const item = document.createElement("div");
    item.className = `checklist-item ${isChecked ? "completed" : ""}`;
    item.innerHTML = `
      <input type="checkbox" id="chk_${topic.id}" ${isChecked ? "checked" : ""} onchange="toggleChecklistItem(${subjectId}, ${topic.id})">
      <label for="chk_${topic.id}" class="checklist-item-label">
        <span class="checklist-priority-dot dot-${topic.priority_level.toLowerCase()}"></span>
        <span class="checklist-item-text" onclick="event.preventDefault(); openTopicDrawer(${topic.id})" style="cursor: pointer;" title="Click to open Topic Study Drawer & Answers">
          ${escapeHtml(topic.name)} <span class="badge-explore">Explore 📖</span>
        </span>
      </label>
    `;
    container.appendChild(item);
  });

  const total = displayTopics.length;
  const pct = total > 0 ? Math.round((completedCount / total) * 100) : 0;
  if (progressText) progressText.textContent = `${completedCount} of ${total} topics completed (${pct}%)`;
  if (progressFill) progressFill.style.width = `${pct}%`;

  // Calculate and update Estimated Exam Marks Coverage Meter
  const marksCoveragePct = totalMarks > 0 ? Math.min(100, Math.round((completedMarks / totalMarks) * 100)) : 0;
  updateMarksCoverageMeter(marksCoveragePct);

  // Safely format only topic label text with KaTeX
  container.querySelectorAll(".checklist-item-text").forEach(el => renderMath(el));
}

function updateMarksCoverageMeter(pct) {
  const coverageVal = document.getElementById("coverageMarksValue");
  const coverageFill = document.getElementById("coverageProgressFill");
  const statusBadge = document.getElementById("coverageStatusBadge");

  if (coverageVal) coverageVal.textContent = `${pct}%`;
  if (coverageFill) {
    coverageFill.style.width = `${pct}%`;
    if (pct < 35) {
      coverageFill.style.background = "linear-gradient(90deg, #ef4444, #f97316)";
    } else if (pct < 60) {
      coverageFill.style.background = "linear-gradient(90deg, #f59e0b, #eab308)";
    } else if (pct < 75) {
      coverageFill.style.background = "linear-gradient(90deg, #10b981, #06b6d4)";
    } else {
      coverageFill.style.background = "linear-gradient(90deg, #6366f1, #a855f7)";
    }
  }

  if (statusBadge) {
    if (pct === 0) {
      statusBadge.className = "coverage-status-badge badge-neutral";
      statusBadge.textContent = "⚠️ Start studying to enter safe zone";
    } else if (pct < 40) {
      statusBadge.className = "coverage-status-badge badge-danger";
      statusBadge.textContent = `⚠️ Below Passing Threshold (~${pct}%) — Focus on High Priority topics!`;
    } else if (pct < 60) {
      statusBadge.className = "coverage-status-badge badge-warning";
      statusBadge.textContent = `🟡 Safe Passing Zone Reached! (~${pct}% of Expected Exam Marks)`;
    } else if (pct < 75) {
      statusBadge.className = "coverage-status-badge badge-success";
      statusBadge.textContent = `🟢 First Class Secured! (~${pct}% of Exam Marks Covered)`;
    } else {
      statusBadge.className = "coverage-status-badge badge-distinction";
      statusBadge.textContent = `🏆 Distinction Zone! (~${pct}% Exam Marks Covered — Top Rank Range)`;
    }
  }
}

function toggleChecklistItem(subjectId, topicId) {
  const key = getChecklistKey(subjectId);
  const saved = JSON.parse(localStorage.getItem(key) || "{}");
  const wasChecked = Boolean(saved[topicId]);
  saved[topicId] = !wasChecked;
  localStorage.setItem(key, JSON.stringify(saved));

  if (!wasChecked) {
    addStudentXp(50);
  }

  if (state.currentSubjectData) {
    renderChecklist(subjectId, state.currentSubjectData.topics);
  }
}

// ============================================================================
// Analytics Charts Rendering
// ============================================================================

function renderCharts(data) {
  const isDark = document.body.classList.contains("theme-dark");
  const textColor = isDark ? "#cbd5e1" : "#475569";
  const gridColor = isDark ? "#1e293b" : "#f1f5f9";

  // 1. Frequency Bar Chart
  const topTopics = [...data.topics].slice(0, 10);
  const labels = topTopics.map((t) => (t.name.length > 18 ? t.name.substring(0, 16) + "..." : t.name));
  const counts = topTopics.map((t) => t.frequency);

  const freqCtx = document.getElementById("topicFrequencyChart")?.getContext("2d");
  if (freqCtx) {
    if (state.frequencyChart) state.frequencyChart.destroy();
    state.frequencyChart = new Chart(freqCtx, {
      type: "bar",
      data: {
        labels: labels,
        datasets: [{
          label: "Times Tested",
          data: counts,
          backgroundColor: "rgba(79, 70, 229, 0.75)",
          borderColor: "#4f46e5",
          borderWidth: 1.5,
          borderRadius: 6,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              title: (items) => topTopics[items[0].dataIndex]?.name || "",
            },
          },
        },
        scales: {
          x: {
            ticks: { color: textColor, font: { size: 11 } },
            grid: { display: false },
          },
          y: {
            ticks: { color: textColor, stepSize: 1, precision: 0 },
            grid: { color: gridColor },
            beginAtZero: true,
          },
        },
      },
    });
  }

  // 2. Priority Donut Chart
  const highCount = data.stats.high_priority_count;
  const medCount = data.stats.medium_priority_count;
  const lowCount = data.stats.low_priority_count;

  const donutCtx = document.getElementById("priorityDonutChart")?.getContext("2d");
  if (donutCtx) {
    if (state.priorityChart) state.priorityChart.destroy();
    state.priorityChart = new Chart(donutCtx, {
      type: "doughnut",
      data: {
        labels: ["High Priority", "Medium Priority", "Low Priority"],
        datasets: [{
          data: [highCount, medCount, lowCount],
          backgroundColor: ["#ef4444", "#f59e0b", "#10b981"],
          borderWidth: 2,
          borderColor: isDark ? "#111827" : "#ffffff",
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            position: "bottom",
            labels: { color: textColor, padding: 14, font: { size: 12, weight: 600 } },
          },
        },
        cutout: "68%",
      },
    });
  }
}

// ============================================================================
// Topics Table Rendering & Filtering
// ============================================================================

function renderTopicsTable(topics) {
  const tbody = document.getElementById("topicsTableBody");
  if (!tbody) return;
  tbody.innerHTML = "";

  if (!topics || topics.length === 0) {
    tbody.innerHTML = `<tr><td colspan="8" class="text-center" style="padding: 30px; color: var(--text-muted);">No topics matching search criteria.</td></tr>`;
    return;
  }

  const isAiEstimate = state.currentSubjectData?.subject?.source === "ai_estimate";

  topics.forEach((t) => {
    const tr = document.createElement("tr");

    const badgeClass = t.priority_level === "High" ? "badge-priority-high" : (t.priority_level === "Medium" ? "badge-priority-medium" : "badge-priority-low");
    const badgeIcon = t.priority_level === "High" ? "🔥" : (t.priority_level === "Medium" ? "⚡" : "🌱");
    
    const barClass = t.priority_level === "High" ? "bar-high" : (t.priority_level === "Medium" ? "bar-medium" : "bar-low");
    const scorePct = Math.min(100, Math.max(10, t.priority_score));

    const yearsStr = (t.years_asked || []).join(", ");
    const bonusBadge = t.has_notes_source ? `<span class="notes-bonus-badge" title="Reinforced by your notes (+5 Priority Bonus)">+5 Notes Bonus</span>` : "";

    tr.innerHTML = `
      <td>
        <span class="badge-priority ${badgeClass}">
          <span>${badgeIcon}</span>
          <span>${t.priority_level}</span>
        </span>
      </td>
      <td>
        <div style="font-weight: 600; color: var(--text-primary); font-size: 14px; cursor: pointer;" onclick="openTopicDrawer(${t.id})" title="Click to open Topic Study Drawer & Answers">
          ${escapeHtml(t.name)} ${bonusBadge} <span class="badge-explore">Explore 📖</span>
        </div>
        <div style="font-size: 11px; color: var(--text-muted); margin-top: 2px;">
          ${escapeHtml(t.priority_breakdown?.gap_reason || (isAiEstimate ? "Standard syllabus priority" : "Analyzed from past exams"))}
        </div>
      </td>
      <td><b>${t.frequency}x</b></td>
      <td><b>${t.total_marks} M</b></td>
      ${!isAiEstimate ? `<td><span style="font-family: monospace; font-size: 12px;">${yearsStr || "—"}</span></td>` : ""}
      ${!isAiEstimate ? `<td><b>${t.last_year_asked || "—"}</b></td>` : ""}
      <td>
        <div class="score-cell">
          <div class="score-cell-val">${Math.round(t.priority_score)} <span style="font-size: 10px; color: var(--text-muted);">/100</span></div>
          <div class="score-bar-bg">
            <div class="score-bar-fill ${barClass}" style="width: ${scorePct}%;"></div>
          </div>
        </div>
      </td>
      <td class="text-right">
        <div class="table-actions">
          <button class="btn-action-drawer" onclick="openTopicDrawer(${t.id})" title="Explore deep-dive, formulas, and PYQs">
            🔍 Explore
          </button>
          <button class="btn-action-notes" onclick="openNotesModal(${t.id}, '${escapeQuote(t.name)}')">
            📝 Notes
          </button>
          <button class="btn-action-quiz" onclick="openQuizModal(${t.id}, '${escapeQuote(t.name)}')">
            🎯 Quiz
          </button>
        </div>
      </td>
    `;
    tbody.appendChild(tr);
  });
  renderMath(tbody);
}

function filterTopicsTable() {
  if (!state.currentSubjectData) return;
  const search = document.getElementById("topicSearchInput").value.toLowerCase().trim();
  const priorityFilter = document.getElementById("priorityFilterSelect").value;

  const filtered = state.currentSubjectData.topics.filter((t) => {
    const matchSearch = t.name.toLowerCase().includes(search);
    const matchPriority = priorityFilter === "ALL" || t.priority_level === priorityFilter;
    return matchSearch && matchPriority;
  });

  renderTopicsTable(filtered);
}

// ============================================================================
// Repeated Questions Section
// ============================================================================

function renderRepeatedQuestions(repeatedGroups) {
  const container = document.getElementById("repeatedQuestionsContainer");
  const badge = document.getElementById("repeatedCountBadge");
  if (!container || !badge) return;

  badge.textContent = `${repeatedGroups ? repeatedGroups.length : 0} Recurring Patterns`;
  container.innerHTML = "";

  if (!repeatedGroups || repeatedGroups.length === 0) {
    container.innerHTML = `
      <div style="padding: 24px; text-align: center; color: var(--text-muted); background: var(--bg-main); border-radius: var(--radius-md);">
        No repeating questions detected across the uploaded exam cycles. Uploading 2+ years helps detect recurrence.
      </div>`;
    return;
  }

  repeatedGroups.forEach((rg, idx) => {
    const card = document.createElement("div");
    card.className = "repeat-card";

    const yearsPills = (rg.years || []).map((y) => `<span class="year-tag">${y}</span>`).join("");
    const questionsListHtml = (rg.questions || []).map((q) => `
      <li>
        <b>[${q.year} — ${q.marks}M]</b> ${escapeHtml(q.question_text)}
      </li>
    `).join("");

    card.innerHTML = `
      <div class="repeat-card-header">
        <div class="repeat-years-tags">
          <span style="font-size: 11px; font-weight: 700; color: var(--text-muted); margin-right: 4px;">APPEARED IN:</span>
          ${yearsPills}
        </div>
        <div class="match-score-badge">
          ⚡ ${rg.similarity_score}% Match (TF-IDF)
        </div>
      </div>
      <div class="repeat-canonical-text">
        "${escapeHtml(rg.canonical_question)}"
      </div>
      <button class="repeat-variants-toggle" onclick="toggleVariantsList(${idx})">
        <span id="variantToggleText_${idx}">▶ Show all ${rg.repeat_count} year question variations</span>
      </button>
      <ul class="repeat-variants-list" id="variantsList_${idx}" style="display: none;">
        ${questionsListHtml}
      </ul>
    `;
    container.appendChild(card);
  });
}

function toggleVariantsList(idx) {
  const el = document.getElementById(`variantsList_${idx}`);
  const textEl = document.getElementById(`variantToggleText_${idx}`);
  if (el.style.display === "none") {
    el.style.display = "flex";
    textEl.textContent = "▼ Hide variations";
  } else {
    el.style.display = "none";
    textEl.textContent = "▶ Show variations";
  }
}

// ============================================================================
// Important Questions Section & Outlines
// ============================================================================

function filterQuestionsTab(tab) {
  state.activeQuestionsFilter = tab;
  ["all", "papers", "notes"].forEach((t) => {
    const btn = document.getElementById(`tabFilter${t.charAt(0).toUpperCase() + t.slice(1)}`);
    if (btn) {
      if (t === tab) btn.classList.add("active");
      else btn.classList.remove("active");
    }
  });
  renderImportantQuestions();
}

function renderImportantQuestions() {
  const container = document.getElementById("importantQuestionsList");
  if (!container || !state.currentSubjectData) return;

  const data = state.currentSubjectData;
  const search = (document.getElementById("questionsSearchInput")?.value || "").toLowerCase().trim();

  // Combine suggested questions from notes and questions from papers
  const paperQuestions = (data.topics || []).flatMap((t) =>
    (t.questions || []).map((q) => ({
      id: `p_${q.id}`,
      db_id: q.id,
      topic_name: t.name,
      question_text: q.question_text,
      marks: q.marks,
      source: "paper",
      type: "Past Paper Question",
      difficulty: "Exam",
    }))
  );

  const notesQuestions = (data.suggested_questions || []).map((sq) => ({
    id: `sq_${sq.id}`,
    sq_id: sq.id,
    topic_name: sq.topic_name,
    question_text: sq.question_text,
    marks: sq.expected_marks,
    source: "notes",
    type: sq.question_type,
    difficulty: sq.difficulty,
    why_important: sq.why_important,
    answer_outline: sq.answer_outline,
  }));

  let combined = [];
  if (state.activeQuestionsFilter === "all") {
    combined = [...notesQuestions, ...paperQuestions];
  } else if (state.activeQuestionsFilter === "notes") {
    combined = notesQuestions;
  } else {
    combined = paperQuestions;
  }

  if (search) {
    combined = combined.filter((q) =>
      q.question_text.toLowerCase().includes(search) || q.topic_name.toLowerCase().includes(search)
    );
  }

  container.innerHTML = "";

  if (combined.length === 0) {
    container.innerHTML = `
      <div style="padding: 24px; text-align: center; color: var(--text-muted); background: var(--bg-main); border-radius: var(--radius-md);">
        No questions found for this filter. Try adding study notes to generate AI questions.
      </div>`;
    return;
  }

  combined.slice(0, 30).forEach((q, idx) => {
    const card = document.createElement("div");
    card.className = "question-card";

    const isNotes = q.source === "notes";
    const sourceBadge = isNotes
      ? `<span class="badge-source badge-source-ai">✨ AI Suggested from Notes</span>`
      : `<span class="badge-source badge-source-papers">📄 Past Paper</span>`;

    const outlineBtn = isNotes
      ? `<button class="btn-outline-outline" id="btnOutline_${q.id}" onclick="toggleAnswerOutline(${q.sq_id}, '${q.id}')">💡 Show Answer Outline</button>`
      : "";

    card.innerHTML = `
      <div class="question-card-header">
        <div class="question-meta-row">
          ${sourceBadge}
          <span class="question-topic-pill">${escapeHtml(q.topic_name)}</span>
          <span class="question-marks-pill">${q.marks} Marks</span>
        </div>
        <span class="question-type-tag">${escapeHtml(q.type || "Exam Question")}</span>
      </div>
      <div class="question-card-body">
        <p class="question-text">${escapeHtml(q.question_text)}</p>
        ${q.why_important ? `<div class="question-why-important">🎯 <b>Why it matters:</b> ${escapeHtml(q.why_important)}</div>` : ""}
      </div>
      ${outlineBtn ? `
        <div class="question-card-footer">
          ${outlineBtn}
          <div class="answer-outline-container" id="outlineBox_${q.id}" style="display: none;"></div>
        </div>` : ""}
    `;
    container.appendChild(card);
  });
}

async function toggleAnswerOutline(sqId, cardId) {
  const box = document.getElementById(`outlineBox_${cardId}`);
  const btn = document.getElementById(`btnOutline_${cardId}`);
  if (!box || !btn) return;

  if (box.style.display === "block") {
    box.style.display = "none";
    btn.textContent = "💡 Show Answer Outline";
    return;
  }

  box.style.display = "block";
  box.innerHTML = `<div class="spinner-sm"></div> <span style="font-size: 12px; color: var(--text-muted);">Generating answer outline...</span>`;
  btn.textContent = "▲ Hide Answer Outline";

  try {
    const res = await fetch(`/api/suggested-questions/${sqId}/outline`, { method: "POST" });
    if (!res.ok) throw new Error("Could not load answer outline.");
    const data = await res.json();
    box.innerHTML = marked.parse(data.answer_outline || "No outline available.");
  } catch (err) {
    box.innerHTML = `<div class="text-danger" style="font-size: 12px;">${err.message}</div>`;
  }
}

// ============================================================================
// Demo Data Loader (Instant Offline Demo: College / School / Competitive)
// ============================================================================

async function triggerLoadDemo(demoType = "college") {
  const btn = document.getElementById("btnLoadDemo");
  const origText = btn ? btn.innerHTML : "";
  if (btn) {
    btn.innerHTML = '<span>⏳ Loading...</span>';
    btn.disabled = true;
  }

  try {
    showToast(`Loading sample dataset (${demoType})...`, "info");
    const res = await fetch(`/api/demo/load?demo_type=${encodeURIComponent(demoType)}`, { method: "POST" });
    if (!res.ok) throw new Error("Failed to load sample data.");
    const data = await res.json();

    showToast(data.message, "success");
    await loadSubjectsList();
    if (data.subject_id) {
      loadSubjectDashboard(data.subject_id);
    }
  } catch (err) {
    showToast(err.message, "error");
  } finally {
    if (btn) {
      btn.innerHTML = origText;
      btn.disabled = false;
    }
  }
}

// ============================================================================
// PDF Export Feature & Customizer Modal
// ============================================================================

function openCustomizePdfModal() {
  const modal = document.getElementById("customizePdfModal");
  if (!modal) return;
  const isAiEstimate = state.currentSubjectData?.subject?.source === "ai_estimate";
  const repOpt = document.getElementById("pdfSecRepeatedOption");
  if (repOpt) repOpt.style.display = isAiEstimate ? "none" : "flex";
  modal.style.display = "flex";
}

function closeCustomizePdfModal() {
  const modal = document.getElementById("customizePdfModal");
  if (modal) modal.style.display = "none";
}

function executeCustomPdfDownload() {
  if (!state.currentSubjectId) {
    showToast("Please select a subject first.", "error");
    return;
  }

  const sections = [];
  if (document.getElementById("pdfSecSummary")?.checked) sections.push("summary");
  if (document.getElementById("pdfSecTopics")?.checked) sections.push("topics");
  if (document.getElementById("pdfSecRepeated")?.checked) sections.push("repeated");
  if (document.getElementById("pdfSecQuestions")?.checked) sections.push("questions");
  if (document.getElementById("pdfSecPlan")?.checked) sections.push("plan");

  const secParam = sections.length > 0 ? `?sections=${sections.join(",")}` : "";
  closeCustomizePdfModal();
  showToast("Generating custom ExamSense Study Plan PDF...", "info");
  window.open(`/api/subjects/${state.currentSubjectId}/export-pdf${secParam}`, "_blank");
}

function downloadStudyPlanPDF() {
  openCustomizePdfModal();
}

// ============================================================================
// Delete Subject
// ============================================================================

async function confirmDeleteCurrentSubject() {
  if (!state.currentSubjectId || !state.currentSubjectData) return;
  const name = state.currentSubjectData.subject.name;
  if (!confirm(`Are you sure you want to delete '${name}' and its analyzed data?`)) return;

  try {
    const res = await fetch(`/api/subjects/${state.currentSubjectId}`, { method: "DELETE" });
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || "Could not delete subject.");
    }
    showToast(`Deleted '${name}' successfully.`, "success");
    state.currentSubjectId = null;
    await loadSubjectsList();
  } catch (err) {
    showToast(err.message, "error");
  }
}

// ============================================================================
// Upload Papers Feature with Live Status Polling
// ============================================================================

function switchUploadMode(mode) {
  state.uploadMode = mode;
  const tabFiles = document.getElementById("tabFilesContent");
  const tabText = document.getElementById("tabTextContent");
  const btnFiles = document.getElementById("btnTabUploadFiles");
  const btnText = document.getElementById("btnTabPasteText");

  if (mode === "text") {
    if (tabFiles) tabFiles.style.display = "none";
    if (tabText) tabText.style.display = "block";
    if (btnFiles) btnFiles.classList.remove("active");
    if (btnText) btnText.classList.add("active");
  } else {
    if (tabFiles) tabFiles.style.display = "block";
    if (tabText) tabText.style.display = "none";
    if (btnFiles) btnFiles.classList.add("active");
    if (btnText) btnText.classList.remove("active");
  }
}

function openUploadModal() {
  const modal = document.getElementById("uploadModal");
  if (!modal) return;
  modal.style.display = "flex";
  resetUploadForm();

  // Pre-fill exam level from localStorage if available
  const savedLevel = localStorage.getItem("examsense_exam_level");
  if (savedLevel) {
    const levelSelect = document.getElementById("inputExamLevel");
    if (levelSelect) levelSelect.value = savedLevel;
  }
}

function openUploadModalForCurrentSubject() {
  openUploadModal();
  if (state.currentSubjectData) {
    const nameInput = document.getElementById("inputSubjectName");
    if (nameInput) nameInput.value = state.currentSubjectData.subject.name;
  }
}

function closeUploadModal() {
  if (state.uploadPollInterval) {
    clearInterval(state.uploadPollInterval);
    state.uploadPollInterval = null;
  }
  const modal = document.getElementById("uploadModal");
  if (modal) modal.style.display = "none";
}

function resetUploadForm() {
  const errorBanner = document.getElementById("uploadErrorBanner");
  const progressBox = document.getElementById("uploadProgressBox");
  const submitBtn = document.getElementById("btnSubmitUpload");

  if (errorBanner) errorBanner.style.display = "none";
  if (progressBox) progressBox.style.display = "none";
  if (submitBtn) submitBtn.disabled = false;

  state.selectedFiles = [];
  const listEl = document.getElementById("selectedFilesList");
  if (listEl) listEl.innerHTML = "";
  const secEl = document.getElementById("selectedFilesSection");
  if (secEl) secEl.style.display = "none";
  const fileInput = document.getElementById("fileInput");
  if (fileInput) fileInput.value = "";
  const textInput = document.getElementById("inputPastedText");
  if (textInput) textInput.value = "";
}

function handleFileSelection(event) {
  const files = Array.from(event.target.files);
  if (!files || files.length === 0) return;

  state.selectedFiles = files;
  const listContainer = document.getElementById("selectedFilesList");
  listContainer.innerHTML = "";

  const currentYear = new Date().getFullYear();

  files.forEach((file, idx) => {
    const matchYear = file.name.match(/20\d\d/);
    const guessedYear = matchYear ? parseInt(matchYear[0]) : (currentYear - idx);

    const row = document.createElement("div");
    row.className = "file-row-item";
    row.innerHTML = `
      <div class="file-row-name" title="${file.name}">📄 ${escapeHtml(file.name)}</div>
      <div class="file-row-inputs">
        <select class="file-row-doctype" id="fileDocType_${idx}">
          <option value="paper">Question Paper</option>
          <option value="notes">Study Notes</option>
        </select>
        <input type="number" class="file-row-year" id="fileYear_${idx}" value="${guessedYear}" min="2000" max="2035" required title="Exam Year">
      </div>
    `;
    listContainer.appendChild(row);
  });

  document.getElementById("selectedFilesSection").style.display = "block";
}

async function handleUploadSubmit(event) {
  event.preventDefault();

  const name = document.getElementById("inputSubjectName")?.value.trim() || "";
  const examLevel = document.getElementById("inputExamLevel")?.value || "General";
  const pastedText = document.getElementById("inputPastedText")?.value.trim() || "";
  const errorBanner = document.getElementById("uploadErrorBanner");
  const errorMessage = document.getElementById("uploadErrorMessage");
  const progressBox = document.getElementById("uploadProgressBox");
  const progressText = document.getElementById("uploadProgressText");
  const submitBtn = document.getElementById("btnSubmitUpload");

  if (errorBanner) errorBanner.style.display = "none";

  const hasFiles = state.selectedFiles && state.selectedFiles.length > 0;
  const hasText = state.uploadMode === "text" && pastedText.length >= 20;

  if (!hasFiles && !hasText) {
    if (errorMessage) errorMessage.textContent = "Please select at least one question paper file or paste question text.";
    if (errorBanner) errorBanner.style.display = "block";
    return;
  }

  // Save exam level preference
  localStorage.setItem("examsense_exam_level", examLevel);

  // Build FormData
  const formData = new FormData();
  if (name) formData.append("subject_name", name);
  formData.append("exam_type", examLevel);

  if (hasFiles) {
    const years = [];
    for (let i = 0; i < state.selectedFiles.length; i++) {
      const yrInput = document.getElementById(`fileYear_${i}`);
      years.push(yrInput ? yrInput.value : new Date().getFullYear());
    }
    formData.append("years", years.join(","));
    state.selectedFiles.forEach((file) => formData.append("files", file));
  } else {
    formData.append("pasted_text", pastedText);
  }

  // Show progress state
  if (progressBox) progressBox.style.display = "flex";
  if (progressText) progressText.textContent = "Uploading question papers & starting AI analysis...";
  if (submitBtn) submitBtn.disabled = true;

  try {
    const res = await fetch("/api/upload", { method: "POST", body: formData });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Upload analysis failed.");

    const subjectId = data.subject_id;
    if (!subjectId) throw new Error("Server did not return a valid subject ID.");

    // Start polling status
    pollSubjectStatus(subjectId);
  } catch (err) {
    if (progressBox) progressBox.style.display = "none";
    if (submitBtn) submitBtn.disabled = false;
    if (errorMessage) errorMessage.textContent = err.message;
    if (errorBanner) errorBanner.style.display = "block";
  }
}

function pollSubjectStatus(subjectId) {
  const progressText = document.getElementById("uploadProgressText");
  const progressBox = document.getElementById("uploadProgressBox");
  const errorBanner = document.getElementById("uploadErrorBanner");
  const errorMessage = document.getElementById("uploadErrorMessage");
  const submitBtn = document.getElementById("btnSubmitUpload");

  if (state.uploadPollInterval) clearInterval(state.uploadPollInterval);

  state.uploadPollInterval = setInterval(async () => {
    try {
      const res = await fetch(`/api/subjects/${subjectId}/status`);
      if (!res.ok) return;
      const statusData = await res.json();

      if (progressText && statusData.progress_text) {
        progressText.textContent = statusData.progress_text;
      }

      if (statusData.status === "ready") {
        clearInterval(state.uploadPollInterval);
        state.uploadPollInterval = null;
        showToast("Analysis complete! Study plan ready.", "success");
        closeUploadModal();
        await loadSubjectsList();
        loadSubjectDashboard(subjectId);
      } else if (statusData.status === "failed") {
        clearInterval(state.uploadPollInterval);
        state.uploadPollInterval = null;
        if (progressBox) progressBox.style.display = "none";
        if (submitBtn) submitBtn.disabled = false;
        if (errorMessage) errorMessage.textContent = statusData.error_message || "Processing failed. Try a clearer photo or a different PDF.";
        if (errorBanner) errorBanner.style.display = "block";
      }
    } catch (pollErr) {
      console.warn("Status poll error:", pollErr);
    }
  }, 2000);
}

// Drag & Drop handlers
const dropzone = document.getElementById("uploadDropzone");
if (dropzone) {
  ["dragenter", "dragover"].forEach((eventName) => {
    dropzone.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropzone.style.borderColor = "var(--primary)";
      dropzone.style.background = "rgba(79, 70, 229, 0.1)";
    });
  });

  ["dragleave", "drop"].forEach((eventName) => {
    dropzone.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropzone.style.borderColor = "";
      dropzone.style.background = "";
    });
  });

  dropzone.addEventListener("drop", (e) => {
    const dt = e.dataTransfer;
    const files = dt.files;
    if (files && files.length > 0) {
      handleFileSelection({ target: { files: files } });
    }
  });
}

// ============================================================================
// Phase 6: Start with Just a Subject Name Modal Handler
// ============================================================================

function openSubjectTopicModal() {
  const modal = document.getElementById("subjectTopicModal");
  if (!modal) return;
  modal.style.display = "flex";
  document.getElementById("topicErrorBanner").style.display = "none";
  document.getElementById("topicProgressBox").style.display = "none";
  document.getElementById("btnSubmitTopicPlan").disabled = false;
}

function closeSubjectTopicModal() {
  const modal = document.getElementById("subjectTopicModal");
  if (modal) modal.style.display = "none";
}

async function handleSubjectTopicSubmit(event) {
  event.preventDefault();

  const name = document.getElementById("topicInputSubjectName").value.trim();
  const examLevel = document.getElementById("topicInputExamLevel").value;
  const board = document.getElementById("topicInputBoard").value.trim();
  const classLevel = document.getElementById("topicInputClass").value.trim();

  const errorBanner = document.getElementById("topicErrorBanner");
  const progressBox = document.getElementById("topicProgressBox");
  const submitBtn = document.getElementById("btnSubmitTopicPlan");

  if (!name) {
    errorBanner.textContent = "Subject name is required.";
    errorBanner.style.display = "block";
    return;
  }

  const formData = new FormData();
  formData.append("subject_name", name);
  formData.append("exam_level", examLevel);
  if (board) formData.append("board_name", board);
  if (classLevel) formData.append("class_level", classLevel);

  progressBox.style.display = "flex";
  submitBtn.disabled = true;
  errorBanner.style.display = "none";

  try {
    const res = await fetch("/api/subjects/from-topic", { method: "POST", body: formData });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Failed to generate study plan from topic.");

    showToast(`AI generated ${data.topics_count} core curriculum topics!`, "success");
    closeSubjectTopicModal();
    await loadSubjectsList();
    if (data.subject_id) {
      loadSubjectDashboard(data.subject_id);
    }
  } catch (err) {
    errorBanner.textContent = err.message;
    errorBanner.style.display = "block";
  } finally {
    progressBox.style.display = "none";
    submitBtn.disabled = false;
  }
}

// ============================================================================
// Phase 7: Add Notes Modal Handler
// ============================================================================

function openAddNotesModal() {
  if (!state.currentSubjectId) {
    showToast("Please select a subject first.", "error");
    return;
  }
  const modal = document.getElementById("addNotesModal");
  if (!modal) return;
  modal.style.display = "flex";
  document.getElementById("addNotesErrorBanner").style.display = "none";
  document.getElementById("addNotesProgressBox").style.display = "none";
  document.getElementById("btnSubmitAddNotes").disabled = false;
}

function closeAddNotesModal() {
  const modal = document.getElementById("addNotesModal");
  if (modal) modal.style.display = "none";
}

async function handleAddNotesSubmit(event) {
  event.preventDefault();
  if (!state.currentSubjectId) return;

  const fileInput = document.getElementById("notesFileInput");
  const textInput = document.getElementById("notesTextInput");
  const errorBanner = document.getElementById("addNotesErrorBanner");
  const progressBox = document.getElementById("addNotesProgressBox");
  const submitBtn = document.getElementById("btnSubmitAddNotes");

  const file = fileInput?.files?.[0];
  const text = textInput?.value.trim() || "";

  if (!file && text.length < 20) {
    errorBanner.textContent = "Please upload a notes document/photo or paste at least 20 characters of notes text.";
    errorBanner.style.display = "block";
    return;
  }

  const formData = new FormData();
  if (file) formData.append("notes_file", file);
  if (text) formData.append("notes_text", text);

  progressBox.style.display = "flex";
  submitBtn.disabled = true;
  errorBanner.style.display = "none";

  try {
    const res = await fetch(`/api/subjects/${state.currentSubjectId}/add-notes`, {
      method: "POST",
      body: formData,
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Failed to analyze study notes.");

    showToast(data.message || "Successfully extracted important questions from your notes!", "success");
    closeAddNotesModal();
    // Reload dashboard to reflect new questions and +5 notes priority bonus
    await loadSubjectDashboard(state.currentSubjectId);
  } catch (err) {
    errorBanner.textContent = err.message;
    errorBanner.style.display = "block";
  } finally {
    progressBox.style.display = "none";
    submitBtn.disabled = false;
  }
}

// ============================================================================
// Feature 6: Revision Notes Modal & Language Switcher
// ============================================================================

async function openNotesModal(topicId, topicName) {
  state.activeNotesTopicId = topicId;
  state.activeNotesTopicName = topicName;
  state.activeNotesLanguage = "en";

  document.getElementById("notesModalTopicTitle").textContent = topicName;
  document.getElementById("langBtnEn").classList.add("active");
  document.getElementById("langBtnHi").classList.remove("active");

  document.getElementById("notesModal").style.display = "flex";
  await fetchAndDisplayNotes(topicId, "en");
}

function closeNotesModal() {
  document.getElementById("notesModal").style.display = "none";
}

async function switchNotesLanguage(lang) {
  if (state.activeNotesLanguage === lang) return;
  state.activeNotesLanguage = lang;

  if (lang === "hi") {
    document.getElementById("langBtnHi").classList.add("active");
    document.getElementById("langBtnEn").classList.remove("active");
  } else {
    document.getElementById("langBtnEn").classList.add("active");
    document.getElementById("langBtnHi").classList.remove("active");
  }

  await fetchAndDisplayNotes(state.activeNotesTopicId, lang);
}

async function fetchAndDisplayNotes(topicId, language) {
  const loadingBox = document.getElementById("notesLoadingBox");
  const contentArea = document.getElementById("notesContentArea");

  contentArea.innerHTML = "";
  loadingBox.style.display = "flex";

  try {
    const res = await fetch(`/api/topics/${topicId}/notes?language=${language}`);
    if (!res.ok) throw new Error("Could not retrieve notes.");
    const data = await res.json();

    loadingBox.style.display = "none";
    contentArea.innerHTML = marked.parse(data.notes);
  } catch (err) {
    loadingBox.style.display = "none";
    contentArea.innerHTML = `<div class="alert-banner alert-danger">${err.message}</div>`;
  }
}

function copyNotesToClipboard() {
  const content = document.getElementById("notesContentArea").innerText;
  navigator.clipboard.writeText(content).then(() => {
    showToast("Revision notes copied to clipboard!", "success");
  });
}

// ============================================================================
// Practice Quiz Modal (5/10 MCQs, Easy/Medium/Hard)
// ============================================================================

async function openQuizModal(topicId, topicName) {
  state.activeQuizTopicId = topicId;
  state.activeQuizTopicName = topicName;
  state.activeQuizUserAnswers = {};
  state.activeQuizCurrentIndex = 0;
  state.activeQuizCount = parseInt(document.getElementById("quizQuestionCountSelect")?.value || "5");
  state.activeQuizDifficulty = document.getElementById("quizDifficultySelect")?.value || "medium";

  document.getElementById("quizModalTopicTitle").textContent = topicName;
  document.getElementById("quizModal").style.display = "flex";
  
  document.getElementById("quizActiveContainer").style.display = "none";
  document.getElementById("quizResultContainer").style.display = "none";
  document.getElementById("quizLoadingBox").style.display = "flex";

  document.getElementById("btnQuizPrev").style.display = "none";
  document.getElementById("btnQuizNext").style.display = "inline-flex";
  document.getElementById("btnQuizSubmit").style.display = "none";
  document.getElementById("btnQuizRetry").style.display = "none";

  await fetchQuizQuestions();
}

async function changeQuizConfig() {
  state.activeQuizCount = parseInt(document.getElementById("quizQuestionCountSelect")?.value || "5");
  state.activeQuizDifficulty = document.getElementById("quizDifficultySelect")?.value || "medium";
  state.activeQuizUserAnswers = {};
  state.activeQuizCurrentIndex = 0;

  document.getElementById("quizActiveContainer").style.display = "none";
  document.getElementById("quizResultContainer").style.display = "none";
  document.getElementById("quizLoadingBox").style.display = "flex";

  await fetchQuizQuestions();
}

async function fetchQuizQuestions() {
  try {
    const res = await fetch(`/api/topics/${state.activeQuizTopicId}/quiz?count=${state.activeQuizCount}&difficulty=${state.activeQuizDifficulty}`);
    if (!res.ok) throw new Error("Could not load practice quiz.");
    const data = await res.json();

    state.activeQuizQuestions = data.quiz;
    document.getElementById("quizLoadingBox").style.display = "none";
    document.getElementById("quizActiveContainer").style.display = "block";

    renderCurrentQuizQuestion();
  } catch (err) {
    document.getElementById("quizLoadingBox").style.display = "none";
    showToast(err.message, "error");
    closeQuizModal();
  }
}

function closeQuizModal() {
  document.getElementById("quizModal").style.display = "none";
}

function renderCurrentQuizQuestion() {
  const questions = state.activeQuizQuestions;
  const idx = state.activeQuizCurrentIndex;
  const q = questions[idx];
  if (!q) return;

  document.getElementById("quizQuestionCounter").textContent = `Question ${idx + 1} of ${questions.length}`;
  const pct = Math.round(((idx + 1) / questions.length) * 100);
  document.getElementById("quizProgressFill").style.width = `${pct}%`;

  document.getElementById("quizQuestionText").textContent = q.question;

  const letters = ["A", "B", "C", "D"];
  const list = document.getElementById("quizOptionsList");
  list.innerHTML = "";

  const selectedAnswer = state.activeQuizUserAnswers[idx];

  q.options.forEach((optText, optIdx) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = `quiz-option-btn ${selectedAnswer === optIdx ? "selected" : ""}`;
    btn.onclick = () => selectQuizOption(idx, optIdx);

    btn.innerHTML = `
      <span class="option-letter">${letters[optIdx]}</span>
      <span>${escapeHtml(optText)}</span>
    `;
    list.appendChild(btn);
  });

  const btnPrev = document.getElementById("btnQuizPrev");
  const btnNext = document.getElementById("btnQuizNext");
  const btnSubmit = document.getElementById("btnQuizSubmit");

  btnPrev.style.display = idx > 0 ? "inline-flex" : "none";

  if (idx === questions.length - 1) {
    btnNext.style.display = "none";
    btnSubmit.style.display = "inline-flex";
  } else {
    btnNext.style.display = "inline-flex";
    btnSubmit.style.display = "none";
  }
}

function selectQuizOption(questionIdx, optionIdx) {
  state.activeQuizUserAnswers[questionIdx] = optionIdx;
  renderCurrentQuizQuestion();
}

function quizNextQuestion() {
  if (state.activeQuizCurrentIndex < state.activeQuizQuestions.length - 1) {
    state.activeQuizCurrentIndex++;
    renderCurrentQuizQuestion();
  }
}

function quizPreviousQuestion() {
  if (state.activeQuizCurrentIndex > 0) {
    state.activeQuizCurrentIndex--;
    renderCurrentQuizQuestion();
  }
}

function quizSubmitAll() {
  const questions = state.activeQuizQuestions;
  let score = 0;

  questions.forEach((q, idx) => {
    const userAns = state.activeQuizUserAnswers[idx];
    if (userAns !== undefined && userAns === q.correct_index) {
      score++;
    }
  });

  const passThreshold = Math.ceil(questions.length * 0.6);
  if (score >= passThreshold && typeof confetti === "function") {
    confetti({ particleCount: 80, spread: 70, origin: { y: 0.6 } });
  }

  document.getElementById("quizActiveContainer").style.display = "none";
  document.getElementById("quizResultContainer").style.display = "block";

  document.getElementById("resultScoreNum").textContent = score;
  document.getElementById("resultScoreDen").textContent = `/ ${questions.length}`;
  document.getElementById("resultCelebrationIcon").textContent = score >= passThreshold ? "🏆" : "📚";

  const feedbackText = score === questions.length
    ? "Flawless score! You have completely mastered this exam topic."
    : (score >= passThreshold
      ? "Solid performance! You are well-prepared for exam questions on this topic."
      : "Revise the notes above and attempt the quiz again to lock in your score.");
  document.getElementById("resultFeedback").textContent = feedbackText;

  const reviewList = document.getElementById("quizReviewList");
  reviewList.innerHTML = "";

  questions.forEach((q, idx) => {
    const userAns = state.activeQuizUserAnswers[idx];
    const isCorrect = userAns === q.correct_index;

    const userAnsText = userAns !== undefined ? q.options[userAns] : "Not Answered";
    const correctAnsText = q.options[q.correct_index];

    const item = document.createElement("div");
    item.className = `review-item ${isCorrect ? "review-correct" : "review-incorrect"}`;

    item.innerHTML = `
      <div class="review-q-text">Q${idx + 1}: ${escapeHtml(q.question)}</div>
      <div class="review-ans-row">
        Your Answer: <b>${escapeHtml(userAnsText)}</b> ${isCorrect ? "✅" : "❌"}
      </div>
      ${!isCorrect ? `<div class="review-ans-row" style="color: var(--priority-low);">Correct Answer: <b>${escapeHtml(correctAnsText)}</b></div>` : ""}
      <div class="review-explanation">
        💡 <b>Explanation:</b> ${escapeHtml(q.explanation)}
      </div>
    `;
    reviewList.appendChild(item);
  });

  document.getElementById("btnQuizPrev").style.display = "none";
  document.getElementById("btnQuizNext").style.display = "none";
  document.getElementById("btnQuizSubmit").style.display = "none";
  document.getElementById("btnQuizRetry").style.display = "inline-flex";
}

function restartCurrentQuiz() {
  state.activeQuizUserAnswers = {};
  state.activeQuizCurrentIndex = 0;
  document.getElementById("quizResultContainer").style.display = "none";
  document.getElementById("quizActiveContainer").style.display = "block";
  document.getElementById("btnQuizRetry").style.display = "none";
  renderCurrentQuizQuestion();
}

// ============================================================================
// Formula Explanation Modal
// ============================================================================

function openFormulaModal() {
  document.getElementById("formulaModal").style.display = "flex";
}

function closeFormulaModal() {
  document.getElementById("formulaModal").style.display = "none";
}

// ============================================================================
// Sanitization Helpers
// ============================================================================

function escapeHtml(text) {
  if (!text) return "";
  return String(text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function escapeQuote(text) {
  if (!text) return "";
  return String(text).replace(/'/g, "\\'").replace(/"/g, "&quot;");
}

// ============================================================================
// Safe KaTeX / MathJax Equation Rendering
// ============================================================================

function renderMath(container = document.body) {
  if (typeof renderMathInElement === "function" && container) {
    try {
      renderMathInElement(container, {
        delimiters: [
          { left: "$$", right: "$$", display: true },
          { left: "$", right: "$", display: false },
          { left: "\\(", right: "\\)", display: false },
          { left: "\\[", right: "\\]", display: true }
        ],
        ignoredTags: ["script", "noscript", "style", "textarea", "pre", "code", "input", "button", "select", "option", "a"],
        ignoredClasses: ["btn", "pomo-btn", "quiz-opt-btn", "dash-nav-tab", "panic-btn", "btn-copy-formula", "checklist-item", "search-input-box"],
        throwOnError: false,
      });
    } catch (e) {
      console.warn("KaTeX render error:", e);
    }
  }
}

// ============================================================================
// Interactive Topic Explorer & Answer Drawer Controller
// ============================================================================

let currentDrawerTopicData = null;

async function openTopicDrawer(topicId) {
  const modal = document.getElementById("topicDrawerModal");
  if (!modal) return;
  modal.style.display = "flex";

  const titleEl = document.getElementById("drawerTopicTitle");
  const badgesEl = document.getElementById("drawerBadges");
  const conceptBox = document.getElementById("drawerConceptBox");
  const formulasBox = document.getElementById("drawerFormulasBox");
  const tipsBox = document.getElementById("drawerTipsBox");
  const questionsList = document.getElementById("drawerQuestionsList");
  const qCountBadge = document.getElementById("drawerQuestionCount");
  const searchInput = document.getElementById("drawerSearchInput");
  if (searchInput) searchInput.value = "";

  conceptBox.innerHTML = `<div class="progress-box"><div class="spinner"></div><div class="progress-text">Analyzing topic deep-dive & PYQs...</div></div>`;
  formulasBox.innerHTML = "";
  tipsBox.innerHTML = "";
  questionsList.innerHTML = "";

  try {
    const res = await fetch(`/api/topics/${topicId}/deep-dive?language=${state.uiLang}`);
    if (!res.ok) throw new Error("Could not load topic details");
    const data = await res.json();
    currentDrawerTopicData = data;

    titleEl.textContent = data.topic_name;
    const badgeColor = data.priority_level === "High" ? "tier-high" : (data.priority_level === "Medium" ? "tier-med" : "tier-low");
    badgesEl.innerHTML = `
      <span class="tier-pill ${badgeColor}">🔥 ${data.priority_level} Priority (${data.priority_score}/100)</span>
      <span class="badge-mini">Total Marks: ${data.total_marks}M</span>
      <span class="badge-mini">Appeared ${data.frequency}x</span>
      <span class="badge-mini">Years: ${(data.years_asked || []).join(", ") || "Recent"}</span>
    `;

    // Concept Overview
    conceptBox.innerHTML = marked.parse(data.detailed_explanation || "No concept overview available.");

    // Key Formulas Box
    if (data.key_formulas && data.key_formulas.length > 0) {
      formulasBox.innerHTML = data.key_formulas.map(f => `<div>• <b>${escapeHtml(f)}</b></div>`).join("");
      formulasBox.parentElement.style.display = "block";
    } else {
      formulasBox.parentElement.style.display = "none";
    }

    // Exam Tips Box
    if (data.exam_tips && data.exam_tips.length > 0) {
      tipsBox.innerHTML = data.exam_tips.map(tp => `<div>✓ ${escapeHtml(tp)}</div>`).join("");
      tipsBox.parentElement.style.display = "block";
    } else {
      tipsBox.parentElement.style.display = "none";
    }

    // Stop any active voice narration
    updateVoiceButton(false);
    if ('speechSynthesis' in window) window.speechSynthesis.cancel();

    // YouTube Watch Lecture Link
    const ytBtn = document.getElementById("btnYouTubeLecture");
    if (ytBtn) {
      const subjName = state.currentSubjectData?.subject?.name || "";
      const examLvl = state.currentSubjectData?.subject?.exam_type || "";
      const q = `${data.topic_name} ${subjName} ${examLvl} lecture exam preparation`;
      ytBtn.href = `https://www.youtube.com/results?search_query=${encodeURIComponent(q.trim())}`;
    }

    // Exam Answer Structurer Card
    const structCard = document.getElementById("drawerAnswerStructCard");
    if (structCard) {
      const s = data.exam_answer_structure || {};
      structCard.innerHTML = `
        <div class="answer-step-row">
          <span class="step-badge">Step 1 (15%)</span>
          <div class="step-text"><strong>Precise Technical Definition:</strong> ${escapeHtml(s.step_1_intro || `State formal 2-sentence definition of ${data.topic_name} with keywords underlined.`)}</div>
        </div>
        <div class="answer-step-row">
          <span class="step-badge">Step 2 (35%)</span>
          <div class="step-text"><strong>Labeled Diagram / Schematic:</strong> ${escapeHtml(s.step_2_diagram || `Draw neat, boxed schematic/diagram illustrating ${data.topic_name} principles.`)}</div>
        </div>
        <div class="answer-step-row">
          <span class="step-badge">Step 3 (25%)</span>
          <div class="step-text"><strong>Governing Formulas & Equations:</strong> ${escapeHtml(s.step_3_formula || `State primary equations and define every variable with proper SI units.`)}</div>
        </div>
        <div class="answer-step-row">
          <span class="step-badge">Step 4 (20%)</span>
          <div class="step-text"><strong>Step-by-Step Working Mechanism:</strong> ${escapeHtml(s.step_4_working || `Explain working mechanism in 4–5 bullet points with clear sub-headings.`)}</div>
        </div>
        <div class="answer-step-row">
          <span class="step-badge">Step 5 (5%)</span>
          <div class="step-text"><strong>Practical Application & Conclusion:</strong> ${escapeHtml(s.step_5_conclusion || `Conclude with modern real-world engineering or scientific applications.`)}</div>
        </div>
      `;
    }

    // Render PYQs
    renderDrawerQuestions(data.questions || []);

    // Render Concept Flowchart (Mermaid.js)
    renderTopicFlowchart(data.topic_name, data);

    // Load Quick 3-Question Self-Test
    loadDrawerQuickQuiz(topicId, data.topic_name);

    // Safe KaTeX Math Rendering on content elements only
    if (conceptBox) renderMath(conceptBox);
    if (formulasBox) renderMath(formulasBox);
    if (questionsList) renderMath(questionsList);

  } catch (err) {
    console.error("Error opening topic drawer:", err);
    conceptBox.innerHTML = `<div class="text-danger">Unable to load details at this moment.</div>`;
  }
}

// ============================================================================
// Voice Narration (Web Speech Synthesis API)
// ============================================================================

let currentUtterance = null;
let isSpeakingVoice = false;

function updateVoiceButton(speaking) {
  isSpeakingVoice = speaking;
  const btn = document.getElementById("btnVoiceExplain");
  const icon = document.getElementById("voiceIcon");
  const text = document.getElementById("voiceBtnText");
  if (!btn) return;

  if (speaking) {
    btn.classList.add("speaking");
    if (icon) icon.textContent = "⏹️";
    if (text) text.textContent = "Stop Narration";
  } else {
    btn.classList.remove("speaking");
    if (icon) icon.textContent = "🔊";
    if (text) text.textContent = "Listen to Explanation";
  }
}

function toggleVoiceExplanation() {
  if (!('speechSynthesis' in window)) {
    showToast("Text-to-speech is not supported by your browser.", "warning");
    return;
  }

  if (isSpeakingVoice) {
    window.speechSynthesis.cancel();
    updateVoiceButton(false);
    return;
  }

  const conceptBox = document.getElementById("drawerConceptBox");
  if (!conceptBox) return;
  const rawText = conceptBox.innerText || conceptBox.textContent || "";
  if (!rawText.trim() || rawText.includes("Loading")) {
    showToast("Explanation is still loading...", "info");
    return;
  }

  const cleanSpeechText = rawText
    .replace(/[#\*_`]/g, "")
    .replace(/\\[a-zA-Z]+/g, " formula ")
    .replace(/\s+/g, " ")
    .trim();

  currentUtterance = new SpeechSynthesisUtterance(cleanSpeechText);
  currentUtterance.rate = 0.95;
  currentUtterance.pitch = 1.0;

  const voices = window.speechSynthesis.getVoices();
  const hindiVoice = voices.find(v => (v.lang && (v.lang.includes("hi") || v.lang.includes("IN"))) || (v.name && v.name.includes("India")));
  if (state.uiLang === "hi" && hindiVoice) {
    currentUtterance.voice = hindiVoice;
  }

  currentUtterance.onend = () => {
    updateVoiceButton(false);
  };
  currentUtterance.onerror = () => {
    updateVoiceButton(false);
  };

  window.speechSynthesis.speak(currentUtterance);
  updateVoiceButton(true);
}

// ============================================================================
// Concept Flowchart & Mind-Map (Mermaid.js)
// ============================================================================

async function renderTopicFlowchart(topicName, data) {
  const container = document.getElementById("drawerMermaidGraph");
  if (!container) return;

  const cleanName = (topicName || "Topic").replace(/["\(\)\[\]\{\}]/g, " ").trim();
  const formulas = (data.key_formulas || []).slice(0, 2).map((f, i) => `F${i + 1}["📐 ${f.replace(/["\(\)\[\]\{\}]/g, ' ').substring(0, 30)}"]`);
  const tips = (data.exam_tips || []).slice(0, 2).map((t, i) => `T${i + 1}["💡 ${t.replace(/["\(\)\[\]\{\}]/g, ' ').substring(0, 30)}"]`);

  const graphDef = `
    graph TD
      ROOT["📌 ${cleanName}"]
      ROOT --> B1["Core Axioms & Principles"]
      ROOT --> B2["Mathematical Equations"]
      ROOT --> B3["Exam Scoring Focus"]
      ${formulas.length > 0 ? `B2 --> ${formulas.join('\n      B2 --> ')}` : 'B2 --> F0["Standard Formulation: y = f(x)"]'}
      ${tips.length > 0 ? `B3 --> ${tips.join('\n      B3 --> ')}` : 'B3 --> T0["Specify SI Units & Assumptions"]'}
  `;

  try {
    if (window.mermaid) {
      window.mermaid.initialize({ startOnLoad: false, theme: 'default', securityLevel: 'loose' });
      const uniqueId = "mermaidSvg_" + Math.random().toString(36).substring(2, 9);
      const { svg } = await window.mermaid.render(uniqueId, graphDef);
      container.innerHTML = svg;
    } else {
      container.innerHTML = `<div class="text-muted" style="font-size: 12px;">📌 ${escapeHtml(cleanName)} &rarr; Core Principles &rarr; Governing Formulas &rarr; Model Answer</div>`;
    }
  } catch (mErr) {
    console.warn("Mermaid render error:", mErr);
    container.innerHTML = `<div class="text-muted" style="font-size: 12px;">📌 ${escapeHtml(cleanName)} &rarr; Principles &rarr; Equations &rarr; Exam Application</div>`;
  }
}

// ============================================================================
// Quick 3-Question Self-Test Controller
// ============================================================================

async function loadDrawerQuickQuiz(topicId, topicName) {
  const box = document.getElementById("drawerQuizBox");
  if (!box) return;

  box.innerHTML = `<div class="progress-box"><div class="spinner-sm"></div><div class="progress-text">Preparing quick self-test...</div></div>`;

  try {
    const res = await fetch(`/api/topics/${topicId}/quiz?count=3&difficulty=medium`);
    if (!res.ok) throw new Error("Could not load quick quiz");
    const data = await res.json();
    const quizList = data.quiz || [];

    if (quizList.length === 0) {
      box.innerHTML = `<div class="text-muted" style="font-size: 12px;">No quick quiz available for this topic yet. Read full notes to test yourself!</div>`;
      return;
    }

    box.innerHTML = "";
    quizList.slice(0, 3).forEach((item, qIdx) => {
      const card = document.createElement("div");
      card.className = "quiz-card-sm";
      card.id = `drawerQuizItem_${qIdx}`;

      const optionsHtml = (item.options || []).map((opt, optIdx) => `
        <button type="button" class="quiz-opt-btn" onclick="handleDrawerQuizAnswer(${qIdx}, ${optIdx}, ${item.correct_index}, this, '${escapeHtml(item.explanation || "")}')">
          <b>${String.fromCharCode(65 + optIdx)}.</b> ${escapeHtml(opt)}
        </button>
      `).join("");

      card.innerHTML = `
        <div class="quiz-q-title">Q${qIdx + 1}. ${escapeHtml(item.question)}</div>
        <div class="quiz-opts-grid">${optionsHtml}</div>
        <div class="quiz-feedback-box" id="drawerQuizFeedback_${qIdx}" style="display: none;"></div>
      `;
      box.appendChild(card);
    });

    renderMath(box);
  } catch (err) {
    box.innerHTML = `<div class="text-muted" style="font-size: 12px;">Quick quiz offline. Click "Read Complete Notes" below to study all concepts!</div>`;
  }
}

function handleDrawerQuizAnswer(qIdx, selectedIdx, correctIdx, btn, explanation) {
  const card = document.getElementById(`drawerQuizItem_${qIdx}`);
  if (!card) return;
  const allBtns = card.querySelectorAll(".quiz-opt-btn");
  allBtns.forEach(b => b.disabled = true);

  const fbBox = document.getElementById(`drawerQuizFeedback_${qIdx}`);
  if (selectedIdx === correctIdx) {
    btn.classList.add("correct");
    if (fbBox) {
      fbBox.style.display = "block";
      fbBox.style.background = "#dcfce7";
      fbBox.style.color = "#15803d";
      fbBox.innerHTML = `<b>✓ Correct!</b> ${explanation || "Excellent conceptual understanding!"}`;
    }
    confetti({ particleCount: 25, spread: 60, origin: { y: 0.8 } });
  } else {
    btn.classList.add("wrong");
    if (allBtns[correctIdx]) allBtns[correctIdx].classList.add("correct");
    if (fbBox) {
      fbBox.style.display = "block";
      fbBox.style.background = "#fee2e2";
      fbBox.style.color = "#b91c1c";
      fbBox.innerHTML = `<b>✗ Incorrect.</b> Correct Answer: <b>${String.fromCharCode(65 + correctIdx)}</b>. ${explanation || ""}`;
    }
  }
}

function markCurrentTopicDoneFromDrawer() {
  if (!currentDrawerTopicData || !state.currentSubjectId) return;
  const topicId = currentDrawerTopicData.topic_id;
  const key = getChecklistKey(state.currentSubjectId);
  const saved = JSON.parse(localStorage.getItem(key) || "{}");
  if (!saved[topicId]) {
    addStudentXp(50);
  }
  saved[topicId] = true;
  localStorage.setItem(key, JSON.stringify(saved));

  if (state.currentSubjectData) {
    renderChecklist(state.currentSubjectId, state.currentSubjectData.topics);
  }

  showToast(`Marked "${currentDrawerTopicData.topic_name}" as Mastered! 🎉`, "success");
  confetti({ particleCount: 40, spread: 70, origin: { y: 0.7 } });
  closeTopicDrawer();
}

function closeTopicDrawer() {
  if (isSpeakingVoice && 'speechSynthesis' in window) {
    window.speechSynthesis.cancel();
    updateVoiceButton(false);
  }
  const modal = document.getElementById("topicDrawerModal");
  if (modal) modal.style.display = "none";
}

// ============================================================================
// 3 Smart PDF Export Modes Dropdown & Downloads
// ============================================================================

function toggleExportMenu(event) {
  if (event) event.stopPropagation();
  const dropdown = document.getElementById("exportMenuDropdown");
  if (!dropdown) return;
  const isHidden = dropdown.style.display === "none" || !dropdown.style.display;
  dropdown.style.display = isHidden ? "flex" : "none";
}

document.addEventListener("click", (e) => {
  const group = document.querySelector(".dropdown-export-group");
  const dropdown = document.getElementById("exportMenuDropdown");
  if (dropdown && group && !group.contains(e.target)) {
    dropdown.style.display = "none";
  }
});

function exportStudyPlanPdfMode(mode = "master") {
  const dropdown = document.getElementById("exportMenuDropdown");
  if (dropdown) dropdown.style.display = "none";

  if (!state.currentSubjectId) {
    showToast("Please select or load a subject first.", "warning");
    return;
  }
  const url = `/api/subjects/${state.currentSubjectId}/export-pdf?language=${state.uiLang}&mode=${mode}`;
  window.open(url, "_blank");
}

function openTopicNotesFromDrawer() {
  if (currentDrawerTopicData) {
    closeTopicDrawer();
    openNotesModal(currentDrawerTopicData.topic_id, currentDrawerTopicData.topic_name);
  }
}

// ============================================================================
// Download Rich PDF (MathJax / KaTeX Textbook Print)
// ============================================================================

function exportRichMathJaxTextbookPdf() {
  if (!state.currentSubjectData) {
    showToast("Please select or load a subject first.", "warning");
    return;
  }
  const data = state.currentSubjectData;
  const subj = data.subject || {};
  const topics = data.topics || [];
  const repeated = data.repeated_groups || [];

  const container = document.getElementById("richTextbookPrintContainer");
  if (!container) return;

  let topicsHtml = "";
  topics.forEach((t, i) => {
    const qList = (t.questions || []).map(q => `
      <tr>
        <td style="width: 30px; text-align: center;">☐</td>
        <td>${escapeHtml(q.question_text)}</td>
        <td style="width: 60px; text-align: center;">${q.marks}M</td>
        <td style="width: 60px; text-align: center;">${q.year}</td>
      </tr>
    `).join("");

    topicsHtml += `
      <div class="textbook-topic-card">
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <h3 style="font-size: 13pt; margin: 0; color: #1e1b4b;">${i + 1}. ${escapeHtml(t.name)}</h3>
          <span style="font-weight: bold; color: ${t.priority_level === 'High' ? '#dc2626' : '#d97706'};">[${t.priority_level} Priority — Score: ${Math.round(t.priority_score)}/100]</span>
        </div>
        <div style="font-size: 9.5pt; color: #4b5563; margin-top: 3pt;">
          <b>Frequency:</b> ${t.frequency}x asked | <b>Weightage:</b> ${t.total_marks} Marks | <b>Years:</b> ${(t.years_asked || []).join(", ") || "Recent"}
        </div>
        <div class="textbook-formula-box">
          <b>📐 Key Formulas & Principles:</b>
          <div>• Governing Law & Axioms for ${escapeHtml(t.name)}</div>
          <div>• Standard Mathematical Formulation / Circuit Relationships</div>
        </div>
        ${qList ? `
          <table class="textbook-question-table">
            <thead>
              <tr>
                <th>Done</th>
                <th>Question Text</th>
                <th>Marks</th>
                <th>Year</th>
              </tr>
            </thead>
            <tbody>
              ${qList}
            </tbody>
          </table>
        ` : ""}
      </div>
    `;
  });

  let repeatedHtml = "";
  if (repeated.length > 0) {
    repeatedHtml = `
      <div class="print-page-break"></div>
      <h2 class="textbook-section-title">Section 2: Recurring Question Patterns & Model Solutions</h2>
      ${repeated.map((rg, idx) => `
        <div class="textbook-solution-card">
          <div style="font-weight: bold; font-size: 11pt; color: #1e1b4b;">Pattern #${idx + 1}: "${escapeHtml(rg.canonical_question)}"</div>
          <div style="font-size: 9.5pt; color: #4338ca; margin-top: 3pt;">
            Appeared in: ${(rg.years || []).join(", ")} | Semantic Match: ${rg.similarity_score}%
          </div>
          <div style="margin-top: 6pt; font-size: 10pt;">
            <b>Model Answer Structure:</b>
            <div>• <b>Step 1 (Definition):</b> State formal governing principles and assumptions.</div>
            <div>• <b>Step 2 (Formulation):</b> Write out governing formulas with variables defined.</div>
            <div>• <b>Step 3 (Derivation/Working):</b> Step-by-step substitution and algebraic simplification.</div>
            <div>• <b>Step 4 (Conclusion):</b> State final numerical/theoretical result with SI units.</div>
          </div>
        </div>
      `).join("")}
    `;
  }

  container.innerHTML = `
    <div class="textbook-header-banner">
      <div class="textbook-title">ExamSense | Master Study & Solution Guide</div>
      <div class="textbook-subtitle">Publication-Grade Examination Blueprint with Full MathJax / KaTeX Formulas</div>
      <table class="textbook-meta-grid">
        <tr>
          <td><b>Subject:</b> ${escapeHtml(subj.name)} (${escapeHtml(subj.code)})</td>
          <td><b>Examination Level:</b> ${escapeHtml(subj.exam_type || "General")}</td>
          <td><b>Date:</b> ${new Date().toLocaleDateString()}</td>
        </tr>
        <tr>
          <td><b>Total Exam Papers:</b> ${data.stats?.total_papers || 1}</td>
          <td><b>Total Questions:</b> ${data.stats?.total_questions || topics.length}</td>
          <td><b>Topics Mapped:</b> ${topics.length}</td>
        </tr>
      </table>
    </div>

    <h2 class="textbook-section-title">Section 1: Prioritized Topic Deep-Dives & Question Bank</h2>
    ${topicsHtml}

    ${repeatedHtml}

    <div style="margin-top: 20pt; border-top: 1pt solid #d1d5db; padding-top: 8pt; font-size: 9pt; color: #6b7280; font-style: italic;">
      Generated by ExamSense AI Exam Intelligence. Master all concepts thoroughly for maximum exam performance.
    </div>
  `;

  renderMath(container);
  window.print();
}

// ============================================================================
// Built-in Study Pomodoro Timer (25-Min Focus Sprint)
// ============================================================================

let pomoSecondsLeft = 25 * 60;
let isPomoRunning = false;
let pomoInterval = null;

function updatePomoDisplay() {
  const el = document.getElementById("pomoTime");
  const btn = document.getElementById("btnPomoToggle");
  if (!el) return;
  const mins = Math.floor(pomoSecondsLeft / 60);
  const secs = pomoSecondsLeft % 60;
  el.textContent = `${String(mins).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
  if (btn) btn.textContent = isPomoRunning ? "⏸" : "▶";
}

function togglePomodoro() {
  if (isPomoRunning) {
    clearInterval(pomoInterval);
    isPomoRunning = false;
    updatePomoDisplay();
  } else {
    isPomoRunning = true;
    updatePomoDisplay();
    pomoInterval = setInterval(() => {
      if (pomoSecondsLeft > 0) {
        pomoSecondsLeft--;
        updatePomoDisplay();
      } else {
        clearInterval(pomoInterval);
        isPomoRunning = false;
        pomoSecondsLeft = 25 * 60;
        updatePomoDisplay();
        addStudentXp(100);
        showToast("🎯 25-Minute Focus Sprint Complete! +100 XP Earned! Take a 5-min break.", "success");
        if (window.confetti) confetti({ particleCount: 50, spread: 80, origin: { y: 0.6 } });
      }
    }, 1000);
  }
}

function resetPomodoro() {
  clearInterval(pomoInterval);
  isPomoRunning = false;
  pomoSecondsLeft = 25 * 60;
  updatePomoDisplay();
}

// ============================================================================
// Student XP & Level Rank System (Gamified Progress)
// ============================================================================

function getStudentXp() {
  return parseInt(localStorage.getItem("examsense_student_xp") || "0", 10);
}

function getStudentRank(xp) {
  if (xp >= 1500) return { level: 5, title: "🏆 Exam Master", nextXp: 2000, base: 1500 };
  if (xp >= 900) return { level: 4, title: "🥇 Distinction Scholar", nextXp: 1500, base: 900 };
  if (xp >= 500) return { level: 3, title: "🥈 First Class Pro", nextXp: 900, base: 500 };
  if (xp >= 200) return { level: 2, title: "🥉 Revision Cadet", nextXp: 500, base: 200 };
  return { level: 1, title: "🌱 Aspirant", nextXp: 200, base: 0 };
}

function updateXpDisplay() {
  const xp = getStudentXp();
  const rank = getStudentRank(xp);
  const badgeEl = document.getElementById("xpLevelBadge");
  const countEl = document.getElementById("xpCountText");
  const fillEl = document.getElementById("xpFillMini");

  if (badgeEl) badgeEl.textContent = rank.title;
  if (countEl) countEl.textContent = `${xp} XP`;
  if (fillEl) {
    const range = rank.nextXp - rank.base;
    const progress = Math.min(100, Math.max(5, Math.round(((xp - rank.base) / range) * 100)));
    fillEl.style.width = `${progress}%`;
  }
}

function addStudentXp(points = 50) {
  const currentXp = getStudentXp();
  const oldRank = getStudentRank(currentXp);
  const newXp = currentXp + points;
  localStorage.setItem("examsense_student_xp", newXp.toString());
  updateXpDisplay();

  const newRank = getStudentRank(newXp);
  if (newRank.level > oldRank.level) {
    showToast(`🎉 Level Up! You achieved rank: ${newRank.title}! Keep going!`, "success");
    if (window.confetti) confetti({ particleCount: 80, spread: 100, origin: { y: 0.5 } });
  }
}

// ============================================================================
// Card Hover Interactions (Clean & Lightweight)
// ============================================================================

function init3dCardTilt() {
  // 3D tilt removed for lightweight, zero-lag performance and stable stacking contexts
}

// ============================================================================
// Last-Night Panic Mode Urgency Filter & Coverage
// ============================================================================

let currentStudyMode = "all"; // 'all' | 'panic12' | 'panic6'

function setStudyMode(mode) {
  currentStudyMode = mode;

  const btnAll = document.getElementById("btnModeAll");
  const btn12 = document.getElementById("btnModePanic12");
  const btn6 = document.getElementById("btnModePanic6");
  const banner = document.getElementById("panicModeBanner");
  const alertTitle = document.getElementById("panicAlertTitle");
  const alertText = document.getElementById("panicAlertText");
  const subtitle = document.getElementById("panicSubtitleText");

  if (btnAll) btnAll.classList.toggle("active", mode === "all");
  if (btn12) btn12.classList.toggle("active", mode === "panic12");
  if (btn6) btn6.classList.toggle("active", mode === "panic6");

  if (mode === "all") {
    if (banner) banner.style.display = "none";
    if (subtitle) subtitle.textContent = "Standard Full Syllabus View";
  } else if (mode === "panic12") {
    if (banner) banner.style.display = "flex";
    if (alertTitle) alertTitle.textContent = "⚡ Last 12h Survival Mode Activated!";
    if (alertText) alertText.textContent = "Checklist & topics filtered to High-ROI & repeating concepts. Master these to secure 60%+ passing marks in minimum hours!";
    if (subtitle) subtitle.textContent = "Last 12 Hours Priority Focus";
    showToast("⚡ Last 12h Survival Mode: Focused on top-scoring topics!", "info");
  } else if (mode === "panic6") {
    if (banner) banner.style.display = "flex";
    if (alertTitle) alertTitle.textContent = "🔥 6h Critical Pass Mode Activated!";
    if (alertText) alertText.textContent = "Maximum urgency filter: Showing top 5 highest-frequency topics to reach passing marks immediately!";
    if (subtitle) subtitle.textContent = "6h Emergency Critical Pass View";
    showToast("🔥 6h Critical Pass Mode: Highest ROI topics only!", "warning");
  }

  if (state.currentSubjectData && state.currentSubjectId) {
    const allTopics = state.currentSubjectData.topics || [];
    let filteredTopics = allTopics;

    if (mode === "panic12") {
      filteredTopics = allTopics.filter(t => t.priority_level === "High" || t.priority_score >= 60);
      if (filteredTopics.length < 3) filteredTopics = allTopics.slice(0, Math.min(5, allTopics.length));
    } else if (mode === "panic6") {
      filteredTopics = [...allTopics].sort((a, b) => b.priority_score - a.priority_score).slice(0, Math.min(5, allTopics.length));
    }

    renderChecklist(state.currentSubjectId, filteredTopics);
    renderTopicsTable(filteredTopics);
  }
}

// ============================================================================
// Dashboard Navigation Tabs Controller
// ============================================================================

let activeDashboardTab = "overview";

function switchDashboardTab(tabName) {
  activeDashboardTab = tabName;

  const tabs = [
    { name: "overview", btnId: "tabBtnOverview" },
    { name: "checklist", btnId: "tabBtnChecklist" },
    { name: "formulas", btnId: "tabBtnFormulas" },
    { name: "repeated", btnId: "tabBtnRepeated" },
    { name: "questions", btnId: "tabBtnQuestions" },
  ];

  tabs.forEach(t => {
    const btn = document.getElementById(t.btnId);
    if (btn) btn.classList.toggle("active", t.name === tabName);
  });

  const overviewSections = ["analyticsSection", "topicsSection", "checklistCard", "repeatedQuestionsSection", "questionsSection"];
  const formulaWall = document.getElementById("formulaWallSection");

  if (tabName === "overview") {
    overviewSections.forEach(id => {
      const el = document.getElementById(id);
      if (el) el.style.display = "";
    });
    if (formulaWall) formulaWall.style.display = "none";
  } else if (tabName === "formulas") {
    overviewSections.forEach(id => {
      const el = document.getElementById(id);
      if (el) el.style.display = "none";
    });
    if (formulaWall) formulaWall.style.display = "block";
    loadFormulaWall();
  } else if (tabName === "checklist") {
    overviewSections.forEach(id => {
      const el = document.getElementById(id);
      if (el) el.style.display = (id === "checklistCard") ? "" : "none";
    });
    if (formulaWall) formulaWall.style.display = "none";
  } else if (tabName === "repeated") {
    overviewSections.forEach(id => {
      const el = document.getElementById(id);
      if (el) el.style.display = (id === "repeatedQuestionsSection") ? "" : "none";
    });
    if (formulaWall) formulaWall.style.display = "none";
  } else if (tabName === "questions") {
    overviewSections.forEach(id => {
      const el = document.getElementById(id);
      if (el) el.style.display = (id === "questionsSection") ? "" : "none";
    });
    if (formulaWall) formulaWall.style.display = "none";
  }
}

// ============================================================================
// Interactive Formula & Cheat-Sheet Wall Controller
// ============================================================================

let loadedFormulas = [];
let loadedFormulasSubjectId = null;

async function loadFormulaWall() {
  if (!state.currentSubjectId) return;
  const grid = document.getElementById("formulaWallGrid");
  const countBadge = document.getElementById("formulaCountBadge");
  if (!grid) return;

  if (loadedFormulasSubjectId === state.currentSubjectId && loadedFormulas.length > 0) {
    renderFormulaCards(loadedFormulas);
    return;
  }

  grid.innerHTML = `<div class="progress-box"><div class="spinner"></div><div class="progress-text">Extracting formulas & equations with KaTeX...</div></div>`;

  try {
    const res = await fetch(`/api/subjects/${state.currentSubjectId}/formulas`);
    if (!res.ok) throw new Error("Could not fetch formulas");
    const data = await res.json();
    loadedFormulas = data.formulas || [];
    loadedFormulasSubjectId = state.currentSubjectId;

    if (countBadge) countBadge.textContent = loadedFormulas.length;
    renderFormulaCards(loadedFormulas);
  } catch (err) {
    console.error("Formula wall error:", err);
    grid.innerHTML = `<div class="text-muted" style="padding: 20px;">Formulas will appear here as you analyze past papers or topics.</div>`;
  }
}

function renderFormulaCards(formulas) {
  const grid = document.getElementById("formulaWallGrid");
  if (!grid) return;

  if (!formulas || formulas.length === 0) {
    grid.innerHTML = `<div class="text-muted" style="padding: 24px; text-align: center; grid-column: 1 / -1;">No mathematical formulas found for this search filter.</div>`;
    return;
  }

  grid.innerHTML = "";
  formulas.forEach((item, idx) => {
    const card = document.createElement("div");
    card.className = "formula-card-3d";
    const prio = (item.priority_level || "High").toLowerCase();
    const safeText = escapeHtml(item.formula_text);
    const escapedFormula = item.formula_text.replace(/\\/g, "\\\\").replace(/'/g, "\\'").replace(/"/g, '&quot;');

    card.innerHTML = `
      <div class="formula-card-top">
        <span class="formula-topic-tag" onclick="openTopicDrawer(${item.topic_id})" style="cursor: pointer;" title="Explore topic">${escapeHtml(item.topic_name)}</span>
        <button type="button" class="btn-copy-formula" onclick="copyFormulaCard('${escapedFormula}', this)" title="Copy formula to clipboard">📋 Copy</button>
      </div>
      <div class="formula-math-display">${safeText}</div>
      <div class="formula-card-footer">
        <span class="tier-dot dot-${prio}"></span>
        <span class="formula-priority-label">${item.priority_level || "High"} Priority</span>
      </div>
    `;
    grid.appendChild(card);
  });

  // Safely format only formula display elements without touching buttons
  grid.querySelectorAll(".formula-math-display").forEach(el => renderMath(el));
}

function filterFormulaWall() {
  const searchInput = document.getElementById("formulaSearchInput");
  if (!searchInput) return;
  const q = searchInput.value.toLowerCase().trim();
  if (!q) {
    renderFormulaCards(loadedFormulas);
    return;
  }
  const filtered = loadedFormulas.filter(f => 
    (f.formula_text && f.formula_text.toLowerCase().includes(q)) ||
    (f.topic_name && f.topic_name.toLowerCase().includes(q))
  );
  renderFormulaCards(filtered);
}

function copyFormulaCard(text, btn) {
  if (!text) return;
  navigator.clipboard.writeText(text).then(() => {
    if (btn) {
      const orig = btn.innerHTML;
      btn.innerHTML = "✓ Copied!";
      btn.style.borderColor = "#10b981";
      btn.style.color = "#10b981";
      setTimeout(() => {
        btn.innerHTML = orig;
        btn.style.borderColor = "";
        btn.style.color = "";
      }, 1800);
    }
    showToast("Formula copied to clipboard! 📋", "success");
  }).catch(() => {
    showToast("Unable to copy to clipboard", "warning");
  });
}

function copyAllFormulas() {
  if (!loadedFormulas || loadedFormulas.length === 0) {
    showToast("No formulas loaded to copy.", "warning");
    return;
  }
  const combined = loadedFormulas.map((f, i) => `${i + 1}. [${f.topic_name}] ${f.formula_text}`).join("\n\n");
  navigator.clipboard.writeText(combined).then(() => {
    showToast(`Copied all ${loadedFormulas.length} formulas to clipboard! 📋`, "success");
  }).catch(() => {
    showToast("Unable to copy formulas", "warning");
  });
}
