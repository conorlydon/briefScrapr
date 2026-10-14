import { listFields, parseItems, toMarkdown } from "/assets/plan.mjs";

const form = document.querySelector("#upload-form");
const fileInput = document.querySelector("#brief-file");
const fileLabel = document.querySelector("#file-label");
const statusLine = document.querySelector("#status");
const button = document.querySelector("#analyse-button");
const results = document.querySelector("#results");
const progressPanel = document.querySelector("#analysis-progress");
const progressBar = document.querySelector("#progress-bar");
const progressLog = document.querySelector("#progress-log");
let currentSource = "";
let githubSession = null;
const issuePanel = document.querySelector("#issue-panel");
const repoSelect = document.querySelector("#github-repository");
const issuePreview = document.querySelector("#issue-preview");
const createIssues = document.querySelector("#create-issues");

const fields = {
  project_name: document.querySelector("#project-name"),
  description: document.querySelector("#description"),
  languages: document.querySelector("#languages"),
  technologies: document.querySelector("#technologies"),
  requirements: document.querySelector("#requirements"),
  components: document.querySelector("#components"),
  deliverables: document.querySelector("#deliverables"),
  filename: document.querySelector("#filename"),
};

fileInput.addEventListener("change", () => {
  fileLabel.textContent = fileInput.files[0]?.name || "Drag one here, or click to browse";
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();

  const file = fileInput.files[0];
  if (!file) {
    showStatus("Choose a PDF brief first.", true);
    return;
  }

  const formData = new FormData();
  formData.append("file", file);

  button.disabled = true;
  fileInput.disabled = true;
  results.hidden = true;
  progressPanel.hidden = false;
  progressBar.max = 1;
  progressBar.value = 0;
  progressLog.replaceChildren();
  showStatus("Uploading and reading your PDF...");

  try {
    const response = await fetch("/api/briefs/analyse/stream", {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      const payload = await response.json();
      throw new Error(payload.detail || "Analysis failed.");
    }
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let complete = false;
    function handleLine(line) {
      if (!line.trim()) return;
      const payload = JSON.parse(line);
      if (payload.type === "error") throw new Error(payload.message);
      if (payload.type === "progress") {
        progressBar.max = payload.total;
        progressBar.value = payload.completed;
        showStatus(`${payload.message} (${payload.completed}/${payload.total} completed)`);
        const entry = document.createElement("li");
        entry.textContent = payload.message;
        progressLog.append(entry);
        progressLog.scrollTop = progressLog.scrollHeight;
      } else if (payload.type === "complete") {
        complete = true;
        renderResults(payload);
        showStatus("Analysis complete.");
      }
    }
    try {
      while (true) {
        const { value, done } = await reader.read();
        buffer += done ? decoder.decode() : decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop();
        for (const line of lines) handleLine(line);
        if (done) break;
      }
      handleLine(buffer);
      if (!complete) throw new Error("Connection interrupted before analysis completed. Please try again.");
    } finally {
      await reader.cancel();
    }
  } catch (error) {
    showStatus(error.message, true);
  } finally {
    button.disabled = false;
    fileInput.disabled = false;
  }
});

function showStatus(message, isError = false) {
  statusLine.textContent = message;
  statusLine.classList.toggle("error", isError);
}

function renderResults(payload) {
  const analysis = payload.analysis;
  fields.project_name.value = analysis.project_name || "";
  fields.description.value = analysis.description || "";
  fields.filename.textContent = payload.filename;
  currentSource = payload.source_text || "";
  document.querySelector("#source-text").textContent = currentSource || "Upload the PDF again to compare its extracted text.";

  renderList(fields.languages, analysis.languages);
  renderList(fields.technologies, analysis.technologies);
  renderList(fields.requirements, analysis.requirements);
  renderList(fields.components, analysis.components);
  renderList(fields.deliverables, analysis.deliverables);

  results.hidden = false;
  issuePanel.hidden = !githubSession?.authenticated;
  issuePreview.replaceChildren();
  document.querySelector("#created-issues").replaceChildren();
  document.querySelector("#issue-status").textContent = "";
  createIssues.disabled = true;
  saveDraft();
  results.scrollIntoView({ behavior: "smooth", block: "start" });
}

function renderList(element, items = []) {
  element.value = items.join("\n");
  element.placeholder = "None specified";
}

function editedPlan() {
  return { project_name: fields.project_name.value.trim(), description: fields.description.value.trim(),
    ...Object.fromEntries(listFields.map(field => [field, parseItems(fields[field].value)])) };
}

function saveDraft() {
  if (results.hidden) return;
  try {
    localStorage.setItem("briefscrapr-draft", JSON.stringify({analysis: editedPlan(), filename: fields.filename.textContent, source_text: currentSource}));
  } catch { /* Editing and export still work when browser storage is unavailable. */ }
}
results.addEventListener("input", event => {
  if (Object.values(fields).includes(event.target)) saveDraft();
});

document.querySelector("#download-markdown").addEventListener("click", () => {
  const plan = editedPlan();
  const url = URL.createObjectURL(new Blob([toMarkdown(plan, fields.filename.textContent)], {type: "text/markdown;charset=utf-8"}));
  const link = document.createElement("a");
  link.href = url;
  link.download = `${(plan.project_name || "build-plan").replace(/[^a-z0-9_-]+/gi, "-").slice(0, 80)}.md`;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
});

async function githubApi(path, options = {}) {
  const response = await fetch(`/api/github/${path}`, {
    ...options, headers: {"Content-Type": "application/json", "X-CSRF-Token": githubSession?.csrf_token || "", ...options.headers},
  });
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "GitHub request failed.");
  return data;
}

async function loadGitHub() {
  const status = document.querySelector("#github-status");
  try {
    githubSession = await githubApi("session");
    document.querySelector("#github-login").hidden = !githubSession.configured || githubSession.authenticated;
    document.querySelector("#github-logout").hidden = !githubSession.authenticated;
    issuePanel.hidden = !githubSession.authenticated || results.hidden;
    status.textContent = githubSession.authenticated ? `Connected as ${githubSession.login}` :
      githubSession.configured ? "Sign in to create issues from your reviewed requirements." :
      "GitHub setup required: add the client ID and secret to .env, then restart the backend. Editing and downloads work now.";
    if (!githubSession.authenticated) return;
    repoSelect.replaceChildren(new Option("Choose a repository", ""));
    for (let page = 1; ; page++) {
      const data = await githubApi(`repositories?page=${page}`);
      for (const repo of data.repositories) repoSelect.add(new Option(repo.full_name, repo.full_name));
      if (!data.has_more) break;
    }
    if (repoSelect.options.length === 1) status.textContent += ". No writable repositories with issues enabled were found.";
  } catch (error) { status.textContent = error.message; }
}

document.querySelector("#github-login").addEventListener("click", saveDraft);
document.querySelector("#github-logout").addEventListener("click", async () => {
  try { await githubApi("logout", {method: "POST"}); await loadGitHub(); }
  catch (error) { document.querySelector("#github-status").textContent = error.message; }
});

function updateIssueButton() {
  createIssues.disabled = !repoSelect.value || !issuePreview.querySelector("input[type=checkbox]:checked");
}
repoSelect.addEventListener("change", updateIssueButton);
issuePreview.addEventListener("change", updateIssueButton);
document.querySelector("#preview-issues").addEventListener("click", () => {
  issuePreview.replaceChildren();
  const plan = editedPlan();
  for (const requirement of plan.requirements) {
    const row = document.createElement("article");
    row.className = "issue-draft";
    const label = document.createElement("label");
    const selected = document.createElement("input"); selected.type = "checkbox";
    label.append(selected, document.createTextNode(" Create this issue"));
    const titleLabel = document.createElement("label"); titleLabel.textContent = "Issue title";
    const title = document.createElement("input"); title.className = "issue-title"; title.value = requirement.slice(0, 256); title.maxLength = 256;
    titleLabel.append(title);
    const bodyLabel = document.createElement("label"); bodyLabel.textContent = "Issue description";
    const body = document.createElement("textarea"); body.className = "issue-body"; body.rows = 4; body.maxLength = 10000;
    body.value = `Project: ${plan.project_name}\n\n${requirement}\n\nSource brief: ${fields.filename.textContent}`;
    bodyLabel.append(body);
    row.append(label, titleLabel, bodyLabel); issuePreview.append(row);
  }
  document.querySelector("#issue-status").textContent = plan.requirements.length ? "Choose a repository and select issues to create (maximum 50 at once)." : "Add requirements to your plan first.";
  updateIssueButton();
});

createIssues.addEventListener("click", async () => {
  const status = document.querySelector("#issue-status");
  const rows = [...issuePreview.querySelectorAll(".issue-draft")].filter(row => row.querySelector("input[type=checkbox]").checked);
  const issues = rows.map(row => ({title: row.querySelector(".issue-title").value.trim(), body: row.querySelector(".issue-body").value}));
  if (!issues.length || issues.length > 50 || issues.some(issue => !issue.title)) {
    status.textContent = "Select 1–50 issues with non-empty titles."; return;
  }
  createIssues.disabled = true;
  status.textContent = `Creating ${issues.length} issue(s) in ${repoSelect.value}…`;
  try {
    const result = await githubApi("issues", {method: "POST", body: JSON.stringify({repository: repoSelect.value, issues})});
    const list = document.querySelector("#created-issues");
    for (const issue of result.created) {
      const li = document.createElement("li"); const link = document.createElement("a");
      link.href = issue.url; link.target = "_blank"; link.rel = "noopener noreferrer";
      link.textContent = `#${issue.number}: ${issue.title}`; li.append(link); list.append(li);
    }
    rows.slice(0, result.created.length).forEach(row => { row.querySelector("input[type=checkbox]").checked = false; });
    status.textContent = `${result.created.length} issue(s) ready. ${result.errors.map(error => `${error.title}: ${error.message}`).join(" ")}`;
  } catch (error) { status.textContent = error.message; }
  finally { updateIssueButton(); }
});

try {
  const draft = JSON.parse(localStorage.getItem("briefscrapr-draft") || "null");
  if (draft?.analysis) renderResults(draft);
} catch { /* Ignore invalid saved drafts. */ }
if (new URLSearchParams(location.search).get("github") === "failed") {
  showStatus("GitHub sign-in did not complete. Try signing in again.", true);
}
loadGitHub();
