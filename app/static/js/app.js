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
  
  // Charts
  frequencyChart: null,
  priorityChart: null,
};

// ============================================================================
// Initialization & Theme Handling
// ============================================================================

document.addEventListener("DOMContentLoaded", () => {
  initTheme();
  loadSubjectsList();
});

function initTheme() {
  const savedTheme = localStorage.getItem("examsense_theme") || "light";
  if (savedTheme === "dark") {
    document.body.classList.remove("theme-light");
    document.body.classList.add("theme-dark");
    document.getElementById("themeIcon").textContent = "☀️";
  } else {
    document.body.classList.remove("theme-dark");
    document.body.classList.add("theme-light");
    document.getElementById("themeIcon").textContent = "🌙";
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

  // Update chart text colors if charts exist
  if (state.frequencyChart && state.currentSubjectData) {
    renderCharts(state.currentSubjectData);
  }
}

// Toast Notifications
function showToast(message, type = "info") {
  const container = document.getElementById("toastContainer");
  const toast = document.createElement("div");
  toast.className = `toast toast-${type}`;
  
  const icon = type === "success" ? "✅" : (type === "error" ? "⚠️" : "ℹ️");
  toast.innerHTML = `<span>${icon}</span><span>${message}</span>`;
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transform = "translateY(10px)";
    toast.style.transition = "all 0.3s ease";
    setTimeout(() => toast.remove(), 300);
  }, 4000);
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
      subjects.forEach((s) => {
        const opt = document.createElement("option");
        opt.value = s.id;
        opt.textContent = `${s.name} (${s.code})`;
        select.appendChild(opt);
      });

      // If no subject selected, load the first one by default
      if (!state.currentSubjectId) {
        select.value = subjects[0].id;
        loadSubjectDashboard(subjects[0].id);
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

    // Switch view to dashboard
    document.getElementById("landingView").style.display = "none";
    document.getElementById("dashboardView").style.display = "flex";

    // Update dropdown
    const select = document.getElementById("subjectSelect");
    if (select) select.value = subjectId;

    // Render components
    renderDashboardHeader(data);
    renderKpiCards(data.stats);
    renderCharts(data);
    renderTopicsTable(data.topics);
    renderRepeatedQuestions(data.repeated_groups);

    window.scrollTo({ top: 0, behavior: "smooth" });
  } catch (err) {
    showToast(err.message, "error");
    showLandingView();
  }
}

// ============================================================================
// Render Dashboard Components
// ============================================================================

function renderDashboardHeader(data) {
  const subject = data.subject;
  const stats = data.stats;

  document.getElementById("dashSubjectCode").textContent = subject.code;
  document.getElementById("dashSubjectName").textContent = subject.name;

  const yearsStr = stats.years_covered && stats.years_covered.length > 0
    ? `${stats.years_covered.join(", ")} Exam Papers`
    : `${stats.total_papers} Exam Papers`;
  document.getElementById("dashExamYears").textContent = yearsStr;

  document.getElementById("dashSubjectSummary").textContent =
    `Based on comprehensive AI extraction of ${stats.total_questions} university exam questions across ${stats.total_papers} papers.`;
}

function renderKpiCards(stats) {
  document.getElementById("kpiHighPriority").textContent = stats.high_priority_count || 0;
  document.getElementById("kpiRepeatedQuestions").textContent = stats.repeated_groups_count || 0;
  document.getElementById("kpiTotalQuestions").textContent = stats.total_questions || 0;
  document.getElementById("kpiExamYears").textContent = (stats.years_covered || []).length || stats.total_papers || 0;
}

// Chart.js Visualization
function renderCharts(data) {
  const isDark = document.body.classList.contains("theme-dark");
  const textColor = isDark ? "#cbd5e1" : "#475569";
  const gridColor = isDark ? "#1f2937" : "#f1f5f9";

  // 1. Topic Frequency Bar Chart
  const freqCanvas = document.getElementById("topicFrequencyChart");
  if (state.frequencyChart) state.frequencyChart.destroy();

  const topTopics = data.topics.slice(0, 8); // Top 8 topics
  const labels = topTopics.map((t) => t.name.length > 25 ? t.name.substring(0, 22) + "..." : t.name);
  const frequencies = topTopics.map((t) => t.frequency);
  const barColors = topTopics.map((t) => {
    if (t.priority_level === "High") return "#ef4444";
    if (t.priority_level === "Medium") return "#f59e0b";
    return "#10b981";
  });

  state.frequencyChart = new Chart(freqCanvas, {
    type: "bar",
    data: {
      labels: labels,
      datasets: [{
        label: "Exam Frequency (Times Asked)",
        data: frequencies,
        backgroundColor: barColors,
        borderRadius: 6,
        barThickness: 24,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: (ctx) => ` Asked ${ctx.raw} times across papers`,
          },
        },
      },
      scales: {
        x: {
          ticks: { color: textColor, font: { family: "Plus Jakarta Sans", size: 11 } },
          grid: { display: false },
        },
        y: {
          beginAtZero: true,
          ticks: { stepSize: 1, color: textColor, font: { family: "Plus Jakarta Sans", size: 11 } },
          grid: { color: gridColor },
        },
      },
    },
  });

  // 2. Priority Donut Chart
  const donutCanvas = document.getElementById("priorityDonutChart");
  if (state.priorityChart) state.priorityChart.destroy();

  const stats = data.stats;
  state.priorityChart = new Chart(donutCanvas, {
    type: "doughnut",
    data: {
      labels: ["High Priority (Must Study)", "Medium Priority", "Low Priority"],
      datasets: [{
        data: [
          stats.high_priority_count || 0,
          stats.medium_priority_count || 0,
          stats.low_priority_count || 0,
        ],
        backgroundColor: ["#ef4444", "#f59e0b", "#10b981"],
        borderWidth: 2,
        borderColor: isDark ? "#111827" : "#ffffff",
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: "68%",
      plugins: {
        legend: {
          position: "bottom",
          labels: {
            color: textColor,
            font: { family: "Plus Jakarta Sans", size: 12, weight: 600 },
            padding: 16,
            usePointStyle: true,
            pointStyle: "circle",
          },
        },
      },
    },
  });
}

// Topics Table Rendering
function renderTopicsTable(topics) {
  const tbody = document.getElementById("topicsTableBody");
  tbody.innerHTML = "";

  if (!topics || topics.length === 0) {
    tbody.innerHTML = `<tr><td colspan="8" class="text-center" style="padding: 30px; color: var(--text-muted);">No topics matching search criteria.</td></tr>`;
    return;
  }

  topics.forEach((t) => {
    const tr = document.createElement("tr");

    // Priority badge
    const badgeClass = t.priority_level === "High" ? "badge-priority-high" : (t.priority_level === "Medium" ? "badge-priority-medium" : "badge-priority-low");
    const badgeIcon = t.priority_level === "High" ? "🔥" : (t.priority_level === "Medium" ? "⚡" : "🌱");
    
    // Score Bar
    const barClass = t.priority_level === "High" ? "bar-high" : (t.priority_level === "Medium" ? "bar-medium" : "bar-low");
    const scorePct = Math.min(100, Math.max(10, t.priority_score));

    // Years string
    const yearsStr = (t.years_asked || []).join(", ");

    tr.innerHTML = `
      <td>
        <span class="badge-priority ${badgeClass}">
          <span>${badgeIcon}</span>
          <span>${t.priority_level}</span>
        </span>
      </td>
      <td>
        <div style="font-weight: 600; color: var(--text-primary); font-size: 14px;">${escapeHtml(t.name)}</div>
        <div style="font-size: 11px; color: var(--text-muted); margin-top: 2px;">
          ${t.priority_breakdown?.gap_reason || "Analyzed from past examinations."}
        </div>
      </td>
      <td><b>${t.frequency}x</b></td>
      <td><b>${t.total_marks} M</b></td>
      <td><span style="font-family: monospace; font-size: 12px;">${yearsStr}</span></td>
      <td><b>${t.last_year_asked}</b></td>
      <td>
        <div class="score-cell">
          <div class="score-cell-val">${t.priority_score} <span style="font-size: 10px; color: var(--text-muted);">/100</span></div>
          <div class="score-bar-bg">
            <div class="score-bar-fill ${barClass}" style="width: ${scorePct}%;"></div>
          </div>
        </div>
      </td>
      <td class="text-right">
        <div class="table-actions">
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

// Repeated Questions Section
function renderRepeatedQuestions(repeatedGroups) {
  const container = document.getElementById("repeatedQuestionsContainer");
  const badge = document.getElementById("repeatedCountBadge");
  badge.textContent = `${repeatedGroups.length} Recurring Patterns`;

  container.innerHTML = "";

  if (!repeatedGroups || repeatedGroups.length === 0) {
    container.innerHTML = `
      <div style="padding: 24px; text-align: center; color: var(--text-muted); background: var(--bg-main); border-radius: var(--radius-md);">
        No repeating questions detected across the uploaded exam cycles.
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
// Demo Data Loader (Instant Offline Demo)
// ============================================================================

async function triggerLoadDemo() {
  const btn = document.getElementById("btnLoadDemo");
  const origText = btn.innerHTML;
  btn.innerHTML = '<span>⏳ Loading Demo...</span>';
  btn.disabled = true;

  try {
    showToast("Populating RGPV CS-501 DBMS Demo Dataset...", "info");
    const res = await fetch("/api/demo/load", { method: "POST" });
    if (!res.ok) throw new Error("Failed to load demo data.");
    const data = await res.json();

    showToast(data.message, "success");
    await loadSubjectsList();
    if (data.subject_id) {
      loadSubjectDashboard(data.subject_id);
    }
  } catch (err) {
    showToast(err.message, "error");
  } finally {
    btn.innerHTML = origText;
    btn.disabled = false;
  }
}

// ============================================================================
// PDF Export Feature
// ============================================================================

function downloadStudyPlanPDF() {
  if (!state.currentSubjectId) {
    showToast("Please select a subject first.", "error");
    return;
  }
  showToast("Generating ExamSense Study Plan PDF...", "info");
  window.open(`/api/subjects/${state.currentSubjectId}/export-pdf`, "_blank");
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
    if (!res.ok) throw new Error("Could not delete subject.");
    showToast(`Deleted '${name}' successfully.`, "success");
    state.currentSubjectId = null;
    await loadSubjectsList();
  } catch (err) {
    showToast(err.message, "error");
  }
}

// ============================================================================
// Upload Papers Feature
// ============================================================================

function openUploadModal() {
  document.getElementById("uploadModal").style.display = "flex";
  document.getElementById("uploadErrorBanner").style.display = "none";
  document.getElementById("uploadProgressBox").style.display = "none";
  document.getElementById("btnSubmitUpload").disabled = false;
  
  // Clear previous files
  state.selectedFiles = [];
  document.getElementById("selectedFilesList").innerHTML = "";
  document.getElementById("selectedFilesSection").style.display = "none";
  document.getElementById("fileInput").value = "";
}

function closeUploadModal() {
  document.getElementById("uploadModal").style.display = "none";
}

function handleFileSelection(event) {
  const files = Array.from(event.target.files);
  if (!files || files.length === 0) return;

  state.selectedFiles = files;
  const listContainer = document.getElementById("selectedFilesList");
  listContainer.innerHTML = "";

  const currentYear = new Date().getFullYear();

  files.forEach((file, idx) => {
    // Try to guess year from filename (e.g., "DBMS_2022.pdf" -> 2022)
    const matchYear = file.name.match(/20\d\d/);
    const guessedYear = matchYear ? parseInt(matchYear[0]) : (currentYear - idx);

    const row = document.createElement("div");
    row.className = "file-row-item";
    row.innerHTML = `
      <div class="file-row-name" title="${file.name}">📄 ${escapeHtml(file.name)}</div>
      <input type="number" class="file-row-year" id="fileYear_${idx}" value="${guessedYear}" min="2000" max="2035" required>
    `;
    listContainer.appendChild(row);
  });

  document.getElementById("selectedFilesSection").style.display = "block";
}

async function handleUploadSubmit(event) {
  event.preventDefault();

  const name = document.getElementById("inputSubjectName").value.trim();
  const code = document.getElementById("inputSubjectCode").value.trim();
  const errorBanner = document.getElementById("uploadErrorBanner");
  const progressBox = document.getElementById("uploadProgressBox");
  const submitBtn = document.getElementById("btnSubmitUpload");

  errorBanner.style.display = "none";

  if (!state.selectedFiles || state.selectedFiles.length === 0) {
    errorBanner.textContent = "Please select at least one PDF question paper.";
    errorBanner.style.display = "block";
    return;
  }

  // Collect years
  const years = [];
  for (let i = 0; i < state.selectedFiles.length; i++) {
    const yrInput = document.getElementById(`fileYear_${i}`);
    years.push(yrInput ? yrInput.value : 2023);
  }

  // Build FormData
  const formData = new FormData();
  formData.append("subject_name", name);
  formData.append("subject_code", code);
  formData.append("years", years.join(","));

  state.selectedFiles.forEach((file) => {
    formData.append("files", file);
  });

  // UI state
  progressBox.style.display = "flex";
  submitBtn.disabled = true;

  try {
    const res = await fetch("/api/upload", {
      method: "POST",
      body: formData,
    });

    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || "Upload analysis failed.");
    }

    showToast(`Successfully analyzed ${data.papers_processed} papers and ${data.questions_extracted} questions!`, "success");
    closeUploadModal();
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
// Feature 6: Revision Notes Modal & Language Switcher
// ============================================================================

async function openNotesModal(topicId, topicName) {
  state.activeNotesTopicId = topicId;
  state.activeNotesTopicName = topicName;
  state.activeNotesLanguage = "en"; // default English

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
// Feature 6: Interactive Practice Quiz (5 MCQs)
// ============================================================================

async function openQuizModal(topicId, topicName) {
  state.activeQuizTopicId = topicId;
  state.activeQuizTopicName = topicName;
  state.activeQuizUserAnswers = {};
  state.activeQuizCurrentIndex = 0;

  document.getElementById("quizModalTopicTitle").textContent = topicName;
  document.getElementById("quizModal").style.display = "flex";
  
  // Show active view, hide result view
  document.getElementById("quizActiveContainer").style.display = "none";
  document.getElementById("quizResultContainer").style.display = "none";
  document.getElementById("quizLoadingBox").style.display = "flex";

  // Reset footer buttons
  document.getElementById("btnQuizPrev").style.display = "none";
  document.getElementById("btnQuizNext").style.display = "inline-flex";
  document.getElementById("btnQuizSubmit").style.display = "none";
  document.getElementById("btnQuizRetry").style.display = "none";

  try {
    const res = await fetch(`/api/topics/${topicId}/quiz`);
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

  // Counter & Progress
  document.getElementById("quizQuestionCounter").textContent = `Question ${idx + 1} of ${questions.length}`;
  const pct = Math.round(((idx + 1) / questions.length) * 100);
  document.getElementById("quizProgressFill").style.width = `${pct}%`;

  // Question Text
  document.getElementById("quizQuestionText").textContent = q.question;

  // Options
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

  // Footer Buttons
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

  // Trigger celebration confetti if score >= 3
  if (score >= 3 && typeof confetti === "function") {
    confetti({
      particleCount: 80,
      spread: 70,
      origin: { y: 0.6 },
    });
  }

  // Display Result View
  document.getElementById("quizActiveContainer").style.display = "none";
  document.getElementById("quizResultContainer").style.display = "block";

  document.getElementById("resultScoreNum").textContent = score;
  document.getElementById("resultCelebrationIcon").textContent = score >= 4 ? "🏆" : (score >= 3 ? "👍" : "📚");

  const feedbackText = score === 5
    ? "Flawless score! You have completely mastered this exam topic."
    : (score >= 3
      ? "Solid performance! You are well-prepared for university questions on this topic."
      : "Revise the notes above and attempt the quiz again to lock in your score.");
  document.getElementById("resultFeedback").textContent = feedbackText;

  // Build review breakdown
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

  // Toggle footer buttons
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
