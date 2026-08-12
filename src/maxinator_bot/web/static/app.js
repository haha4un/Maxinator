const state = {
  summaries: [],
  selectedId: null,
  editable: true,
  data: emptySurvey(),
  modal: null,
};

const $ = (selector) => document.querySelector(selector);
const elements = {
  surveyList: $("#surveyList"),
  questionList: $("#questionList"),
  groupList: $("#groupList"),
  emptyQuestions: $("#emptyQuestions"),
  questionCount: $("#questionCount"),
  groupCount: $("#groupCount"),
  title: $("#title"),
  code: $("#code"),
  version: $("#version"),
  description: $("#description"),
  isActive: $("#isActive"),
  saveButton: $("#saveButton"),
  lockedNotice: $("#lockedNotice"),
  modal: $("#modal"),
  modalTitle: $("#modalTitle"),
  modalBody: $("#modalBody"),
  deleteModalButton: $("#deleteModalButton"),
  importInput: $("#importInput"),
  toast: $("#toast"),
};

function emptySurvey() {
  return {
    code: "",
    title: "",
    description: "",
    version: 1,
    is_active: false,
    categories: [],
  };
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (!response.ok) {
    let detail = `Ошибка ${response.status}`;
    try {
      const body = await response.json();
      detail = formatApiError(body.detail) || detail;
    } catch (_) {}
    throw new Error(detail);
  }
  if (response.status === 204) return null;
  return response.json();
}

function formatApiError(detail) {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail.map((item) => item.msg?.replace(/^Value error, /, "") || "Некорректные данные").join("\n");
  }
  return "";
}

async function loadList(selectId = state.selectedId) {
  state.summaries = await api("/api/questionnaires");
  renderSurveyList();
  if (selectId && state.summaries.some((item) => item.id === selectId)) {
    await selectSurvey(selectId);
  } else if (state.summaries.length && !state.selectedId) {
    await selectSurvey(state.summaries[0].id);
  }
}

async function selectSurvey(id) {
  state.selectedId = id;
  state.data = await api(`/api/questionnaires/${id}`);
  const summary = state.summaries.find((item) => item.id === id);
  state.editable = summary?.editable ?? true;
  render();
}

function collectMeta() {
  state.data.title = elements.title.value.trim();
  state.data.code = elements.code.value.trim();
  state.data.version = Number(elements.version.value) || 1;
  state.data.description = elements.description.value.trim() || null;
  state.data.is_active = elements.isActive.checked;
}

function render() {
  elements.title.value = state.data.title || "";
  elements.code.value = state.data.code || "";
  elements.version.value = state.data.version || 1;
  elements.description.value = state.data.description || "";
  elements.isActive.checked = Boolean(state.data.is_active);
  elements.lockedNotice.classList.toggle("hidden", state.editable);
  elements.saveButton.disabled = !state.editable;
  ["title", "code", "version", "description", "isActive"].forEach((key) => {
    elements[key].disabled = !state.editable;
  });
  renderSurveyList();
  renderQuestions();
  renderGroups();
}

function renderSurveyList() {
  elements.surveyList.innerHTML = state.summaries.map((item) => `
    <button class="survey-item ${item.id === state.selectedId ? "active" : ""}" data-survey-id="${item.id}">
      <strong>${escapeHtml(item.title)}</strong>
      <small>
        <span class="status-dot ${item.is_active ? "active" : ""}"></span>
        ${item.is_active ? "Опубликован" : "Черновик"} · v${item.version}<br>
        ${item.category_count} групп · ${item.question_count} вопросов
      </small>
    </button>
  `).join("");
  elements.surveyList.querySelectorAll("[data-survey-id]").forEach((button) => {
    button.addEventListener("click", () => selectSurvey(button.dataset.surveyId).catch(showError));
  });
}

function flatQuestions() {
  return state.data.categories.flatMap((category, categoryIndex) =>
    category.questions.map((question, questionIndex) => ({
      category,
      categoryIndex,
      question,
      questionIndex,
    })),
  );
}

function renderQuestions() {
  const questions = flatQuestions();
  elements.questionCount.textContent = questions.length;
  elements.emptyQuestions.classList.toggle("hidden", questions.length > 0);
  elements.questionList.innerHTML = questions.map(({ category, categoryIndex, question, questionIndex }, index) => `
    <article class="question-card">
      <div class="drag">⠿</div>
      <div>
        <div class="question-text">${index + 1}. ${escapeHtml(question.text)}</div>
        ${question.image_url ? '<div class="tags"><span class="tag">Есть картинка</span></div>' : ''}
        <div class="tags">
          <span class="tag group">${escapeHtml(category.name)}</span>
          ${question.is_lie_question
            ? '<span class="tag lie">Контрольный</span>'
            : `<span class="tag">${directionLabel(question.scoring_direction)} · вес ${question.weight}</span>`}
          ${question.is_active === false ? '<span class="tag">Выключен</span>' : ""}
        </div>
      </div>
      <button class="card-menu" data-question="${categoryIndex}:${questionIndex}" ${state.editable ? "" : "disabled"}>•••</button>
    </article>
  `).join("");
  elements.questionList.querySelectorAll("[data-question]").forEach((button) => {
    button.addEventListener("click", () => {
      const [categoryIndex, questionIndex] = button.dataset.question.split(":").map(Number);
      openQuestionModal(categoryIndex, questionIndex);
    });
  });
}

function renderGroups() {
  elements.groupCount.textContent = state.data.categories.length;
  elements.groupList.innerHTML = state.data.categories.map((category, index) => `
    <article class="group-card">
      <div class="group-summary">
        <span class="group-accent"></span>
        <div>
          <strong>${escapeHtml(category.name)}</strong>
          <small>${category.questions.length} вопросов · ${category.interpretations.length} диапазонов</small>
        </div>
        <button class="card-menu" data-group="${index}" ${state.editable ? "" : "disabled"}>•••</button>
      </div>
      <div class="range-list">
        ${category.interpretations.map((range) => `
          <div class="range-row">
            <span>${range.min_score}–${range.max_score}</span>
            <span>${escapeHtml(range.title)}${range.requires_attention ? " ⚑" : ""}</span>
          </div>
        `).join("")}
      </div>
    </article>
  `).join("");
  elements.groupList.querySelectorAll("[data-group]").forEach((button) => {
    button.addEventListener("click", () => openGroupModal(Number(button.dataset.group)));
  });
}

function openQuestionModal(categoryIndex = 0, questionIndex = null) {
  if (!state.editable || !state.data.categories.length) {
    if (!state.data.categories.length) toast("Сначала создайте группу", true);
    return;
  }
  const isNew = questionIndex === null;
  const source = isNew ? {
    text: "",
    image_url: null,
    weight: 1,
    scoring_direction: "direct",
    is_lie_question: false,
    is_active: true,
    answer_scores: {},
  } : structuredClone(state.data.categories[categoryIndex].questions[questionIndex]);
  state.modal = { type: "question", isNew, categoryIndex, questionIndex, source };
  elements.modalTitle.textContent = isNew ? "Новый вопрос" : "Редактирование вопроса";
  elements.deleteModalButton.classList.toggle("hidden", isNew);
  elements.modalBody.innerHTML = `
    <div class="modal-grid">
      <div class="field full">
        <label>Текст вопроса</label>
        <textarea id="qText" rows="4">${escapeHtml(source.text)}</textarea>
      </div>
      <div class="field full">
        <label>Ссылка на картинку в Google Drive</label>
        <input id="qImageUrl" type="url" value="${escapeHtml(source.image_url || '')}" placeholder="https://drive.google.com/file/d/…/view">
      </div>
      <div class="field">
        <label>Группа</label>
        <select id="qCategory">
          ${state.data.categories.map((category, index) =>
            `<option value="${index}" ${index === categoryIndex ? "selected" : ""}>${escapeHtml(category.name)}</option>`
          ).join("")}
        </select>
      </div>
      <div class="field">
        <label>Расчёт</label>
        <select id="qDirection" ${source.is_lie_question ? "disabled" : ""}>
          <option value="direct" ${source.scoring_direction === "direct" ? "selected" : ""}>Прямой</option>
          <option value="reverse" ${source.scoring_direction === "reverse" ? "selected" : ""}>Обратный</option>
          <option value="none" ${source.scoring_direction === "none" ? "selected" : ""}>Не учитывать</option>
        </select>
      </div>
      <div class="field">
        <label>Вес</label>
        <input id="qWeight" type="number" min="0" step="0.01" value="${source.weight}" ${source.is_lie_question ? "disabled" : ""}>
      </div>
      <label class="checkbox-row"><input id="qActive" type="checkbox" ${source.is_active !== false ? "checked" : ""}> Активен</label>
      <label class="checkbox-row full"><input id="qLie" type="checkbox" ${source.is_lie_question ? "checked" : ""}> Контрольный вопрос (шкала достоверности)</label>
      <div id="lieScores" class="field full ${source.is_lie_question ? "" : "hidden"}">
        <label>Контрольные баллы для ответов 1–5</label>
        <div class="modal-grid">
          ${[1,2,3,4,5].map((answer) =>
            `<input class="lie-score" data-answer="${answer}" type="number" min="0" placeholder="Ответ ${answer}" value="${source.answer_scores?.[answer] ?? ""}">`
          ).join("")}
        </div>
      </div>
    </div>
  `;
  $("#qLie").addEventListener("change", (event) => {
    $("#lieScores").classList.toggle("hidden", !event.target.checked);
    $("#qDirection").disabled = event.target.checked;
    $("#qWeight").disabled = event.target.checked;
  });
  showModal();
}

function openGroupModal(groupIndex = null) {
  if (!state.editable) return;
  const isNew = groupIndex === null;
  const source = isNew ? {
    code: "",
    name: "",
    description: "",
    questions: [],
    interpretations: [],
  } : structuredClone(state.data.categories[groupIndex]);
  state.modal = { type: "group", isNew, groupIndex, source };
  elements.modalTitle.textContent = isNew ? "Новая группа" : "Редактирование группы";
  elements.deleteModalButton.classList.toggle("hidden", isNew);
  elements.modalBody.innerHTML = `
    <div class="modal-grid">
      <div class="field">
        <label>Название</label>
        <input id="gName" value="${escapeHtml(source.name)}" placeholder="Тревога">
      </div>
      <div class="field">
        <label>Код</label>
        <input id="gCode" value="${escapeHtml(source.code)}" placeholder="anxiety">
      </div>
      <div class="field full">
        <label>Описание</label>
        <textarea id="gDescription" rows="2">${escapeHtml(source.description || "")}</textarea>
      </div>
    </div>
    <div class="section-heading" style="margin-top:18px">
      <strong>Диапазоны интерпретации</strong>
      <button class="button secondary" id="addRangeButton">+ Диапазон</button>
    </div>
    <div id="rangeEditor" class="range-editor"></div>
  `;
  renderRangeEditor(source.interpretations);
  $("#addRangeButton").addEventListener("click", () => {
    source.interpretations.push({
      min_score: 0, max_score: 0, level_code: `level_${source.interpretations.length + 1}`,
      title: "Новый уровень", description: "", requires_attention: false,
    });
    renderRangeEditor(source.interpretations);
  });
  showModal();
}

function renderRangeEditor(ranges) {
  const editor = $("#rangeEditor");
  editor.innerHTML = ranges.length ? ranges.map((range, index) => `
    <div class="range-edit-row" data-range-row="${index}">
      <input data-range-field="min_score" type="number" step="0.01" value="${range.min_score}" title="Минимум">
      <input data-range-field="max_score" type="number" step="0.01" value="${range.max_score}" title="Максимум">
      <input data-range-field="title" value="${escapeHtml(range.title)}" placeholder="Название уровня">
      <label title="Требует внимания"><input data-range-field="requires_attention" type="checkbox" ${range.requires_attention ? "checked" : ""}> ⚑</label>
      <button class="remove-range" data-remove-range="${index}">×</button>
      <input data-range-field="level_code" value="${escapeHtml(range.level_code)}" placeholder="level_code">
      <textarea data-range-field="description" placeholder="Интерпретация" style="grid-column:2/5">${escapeHtml(range.description || "")}</textarea>
    </div>
  `).join("") : '<div class="empty-state">Диапазонов пока нет</div>';
  editor.querySelectorAll("[data-remove-range]").forEach((button) => {
    button.addEventListener("click", () => {
      readRanges(ranges);
      ranges.splice(Number(button.dataset.removeRange), 1);
      renderRangeEditor(ranges);
    });
  });
}

function readRanges(target) {
  document.querySelectorAll("[data-range-row]").forEach((row) => {
    const index = Number(row.dataset.rangeRow);
    target[index] = {
      min_score: Number(row.querySelector('[data-range-field="min_score"]').value),
      max_score: Number(row.querySelector('[data-range-field="max_score"]').value),
      level_code: row.querySelector('[data-range-field="level_code"]').value.trim(),
      title: row.querySelector('[data-range-field="title"]').value.trim(),
      description: row.querySelector('[data-range-field="description"]').value.trim(),
      requires_attention: row.querySelector('[data-range-field="requires_attention"]').checked,
    };
  });
}

function applyModal() {
  if (!state.modal) return;
  if (state.modal.type === "question") applyQuestionModal();
  else applyGroupModal();
}

function applyQuestionModal() {
  const text = $("#qText").value.trim();
  if (!text) return toast("Введите текст вопроса", true);
  const targetCategory = Number($("#qCategory").value);
  const lie = $("#qLie").checked;
  const answerScores = {};
  if (lie) {
    document.querySelectorAll(".lie-score").forEach((input) => {
      if (input.value !== "") answerScores[input.dataset.answer] = Number(input.value);
    });
  }
  const question = {
    text,
    image_url: $("#qImageUrl").value.trim() || null,
    weight: lie ? 0 : Number($("#qWeight").value),
    scoring_direction: lie ? "none" : $("#qDirection").value,
    is_lie_question: lie,
    is_active: $("#qActive").checked,
    answer_scores: answerScores,
  };
  const { isNew, categoryIndex, questionIndex } = state.modal;
  if (isNew) {
    state.data.categories[targetCategory].questions.push(question);
  } else {
    state.data.categories[categoryIndex].questions.splice(questionIndex, 1);
    state.data.categories[targetCategory].questions.push(question);
  }
  closeModal();
  renderQuestions();
  renderGroups();
}

function applyGroupModal() {
  const name = $("#gName").value.trim();
  const code = $("#gCode").value.trim().toLowerCase();
  if (!name || !code) return toast("Укажите название и код группы", true);
  readRanges(state.modal.source.interpretations);
  const group = {
    ...state.modal.source,
    name,
    code,
    description: $("#gDescription").value.trim() || null,
  };
  if (state.modal.isNew) state.data.categories.push(group);
  else state.data.categories[state.modal.groupIndex] = group;
  closeModal();
  renderQuestions();
  renderGroups();
}

function deleteModalItem() {
  if (state.modal?.type === "question") {
    const { categoryIndex, questionIndex } = state.modal;
    state.data.categories[categoryIndex].questions.splice(questionIndex, 1);
  } else if (state.modal?.type === "group") {
    const group = state.data.categories[state.modal.groupIndex];
    if (group.questions.length && !confirm(`Удалить группу и ${group.questions.length} вопросов?`)) return;
    state.data.categories.splice(state.modal.groupIndex, 1);
  }
  closeModal();
  renderQuestions();
  renderGroups();
}

async function save() {
  collectMeta();
  if (!state.data.title || !state.data.code) {
    return toast("Заполните название и код опросника", true);
  }
  if (state.selectedId) {
    await api(`/api/questionnaires/${state.selectedId}`, {
      method: "PUT",
      body: JSON.stringify(state.data),
    });
  } else {
    const created = await api("/api/questionnaires", {
      method: "POST",
      body: JSON.stringify(state.data),
    });
    state.selectedId = created.id;
  }
  await loadList(state.selectedId);
  toast("Опросник сохранён");
}

function newSurvey() {
  state.selectedId = null;
  state.editable = true;
  state.data = emptySurvey();
  render();
  elements.title.focus();
}

async function cloneSurvey() {
  if (!state.selectedId) return;
  const created = await api(`/api/questionnaires/${state.selectedId}/clone`, { method: "POST" });
  state.selectedId = created.id;
  await loadList(created.id);
  toast("Создана редактируемая версия");
}

function exportJson() {
  collectMeta();
  const blob = new Blob([JSON.stringify(state.data, null, 2)], { type: "application/json" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = `${state.data.code || "questionnaire"}.json`;
  link.click();
  URL.revokeObjectURL(link.href);
}

async function importJson(file) {
  const parsed = JSON.parse(await file.text());
  state.data = parsed;
  state.selectedId = null;
  state.editable = true;
  render();
  toast("JSON загружен. Проверьте данные и сохраните.");
}

function showModal() { elements.modal.classList.remove("hidden"); }
function closeModal() { elements.modal.classList.add("hidden"); state.modal = null; }

function toast(message, error = false) {
  elements.toast.textContent = message;
  elements.toast.classList.toggle("error", error);
  elements.toast.classList.remove("hidden");
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => elements.toast.classList.add("hidden"), 4500);
}
function showError(error) { toast(error.message || String(error), true); }
function directionLabel(value) {
  return { direct: "Прямой", reverse: "Обратный", none: "Без расчёта" }[value] || value;
}
function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;",
  })[char]);
}

$("#newSurveyButton").addEventListener("click", newSurvey);
$("#addQuestionButton").addEventListener("click", () => openQuestionModal(0, null));
$("#addGroupButton").addEventListener("click", () => openGroupModal(null));
elements.saveButton.addEventListener("click", () => save().catch(showError));
$("#cloneButton").addEventListener("click", () => cloneSurvey().catch(showError));
$("#exportButton").addEventListener("click", exportJson);
$("#importButton").addEventListener("click", () => elements.importInput.click());
elements.importInput.addEventListener("change", () => {
  const [file] = elements.importInput.files;
  if (file) importJson(file).catch(showError);
  elements.importInput.value = "";
});
$("#closeModalButton").addEventListener("click", closeModal);
$("#cancelModalButton").addEventListener("click", closeModal);
$("#applyModalButton").addEventListener("click", applyModal);
elements.deleteModalButton.addEventListener("click", deleteModalItem);
elements.modal.addEventListener("click", (event) => {
  if (event.target === elements.modal) closeModal();
});

loadList().catch(showError);
