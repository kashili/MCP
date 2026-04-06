// ── State ────────────────────────────────────────────────────────────────────
let currentProject = null;
let metrics = null;

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

// ── Init ─────────────────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", async () => {
  await loadProjects();
  await loadHealth();

  $("#project-select").addEventListener("change", onProjectChange);
  $("#sync-btn").addEventListener("click", onSync);
  $("#chat-form").addEventListener("submit", onAsk);

  $$(".quick-btn").forEach((btn) =>
    btn.addEventListener("click", () => {
      $("#chat-input").value = btn.dataset.q;
      $("#chat-form").dispatchEvent(new Event("submit"));
    })
  );
});

// ── API helpers ──────────────────────────────────────────────────────────────
async function api(path, opts = {}) {
  const res = await fetch(path, opts);
  if (!res.ok) throw new Error(`API ${res.status}`);
  return res.json();
}

function postJSON(path, body) {
  return api(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

// ── Load projects ────────────────────────────────────────────────────────────
async function loadProjects() {
  try {
    const projects = await api("/api/projects");
    const sel = $("#project-select");
    sel.innerHTML = "";

    if (projects.length === 0) {
      sel.innerHTML = '<option value="">No projects found</option>';
      showEmpty();
      return;
    }

    projects.forEach((p) => {
      const opt = document.createElement("option");
      opt.value = p.id;
      opt.textContent = `${p.name}  [${p.id}]`;
      sel.appendChild(opt);
    });

    await loadProject(projects[0].id);
  } catch (e) {
    toast("Failed to load projects", true);
  }
}

// ── Load single project ──────────────────────────────────────────────────────
async function loadProject(id) {
  showLoading();
  try {
    metrics = await api(`/api/projects/${id}`);
    currentProject = id;
    renderDashboard();
    renderPanels();
  } catch (e) {
    toast(`Failed to load project: ${e.message}`, true);
    showEmpty();
  }
}

function onProjectChange(e) {
  if (e.target.value) loadProject(e.target.value);
}

// ── Render dashboard cards ───────────────────────────────────────────────────
function renderDashboard() {
  const m = metrics;
  const riskClass = `risk-${m.risk_level.toLowerCase()}`;

  $("#dash-content").innerHTML = `
    <div class="dashboard">
      <div class="card">
        <div class="card-label">Completion</div>
        <div class="card-value">${m.completion_pct}%</div>
        <div class="progress-track">
          <div class="progress-fill" style="width:${m.completion_pct}%"></div>
        </div>
        <div class="card-sub">${m.tasks_done} of ${m.tasks_total} tasks done</div>
      </div>
      <div class="card">
        <div class="card-label">Risk Level</div>
        <div class="card-value ${riskClass}">${m.risk_level}</div>
        <div class="card-sub">${m.buffer_days} day buffer</div>
      </div>
      <div class="card">
        <div class="card-label">Projected Finish</div>
        <div class="card-value" style="font-size:1.25rem">${m.projected_finish}</div>
        <div class="card-sub">Deadline: ${m.deadline}</div>
      </div>
      <div class="card">
        <div class="card-label">Status</div>
        <div class="card-value" style="font-size:1.25rem">${m.on_track ? "On Track" : "Behind"}</div>
        <div class="card-sub">${m.adjusted_remaining_hours}h remaining</div>
      </div>
    </div>
  `;
}

// ── Render detail panels ─────────────────────────────────────────────────────
function renderPanels() {
  const m = metrics;

  // Task breakdown
  const tasks = [
    { label: "Done", count: m.tasks_done, dot: "dot-done" },
    { label: "In Progress", count: m.tasks_in_progress, dot: "dot-inprogress" },
    { label: "Blocked", count: m.tasks_blocked, dot: "dot-blocked" },
    { label: "To Do", count: m.tasks_todo, dot: "dot-todo" },
  ];

  const taskHTML = tasks
    .map(
      (t) => `
    <div class="task-row">
      <span><span class="task-dot ${t.dot}"></span>${t.label}</span>
      <strong>${t.count}</strong>
    </div>`
    )
    .join("");

  // Team
  const teamHTML = m.team_analysis
    .map(
      (t) => `
    <div class="team-row">
      <div>
        <strong>${t.name}</strong>
        <span style="color:var(--text-dim);font-size:0.78rem;margin-left:6px">${t.role}</span>
      </div>
      <div style="display:flex;align-items:center;gap:8px">
        <span style="font-size:0.8rem;color:var(--text-dim)">${t.tasks_done}/${t.tasks_assigned} tasks</span>
        <span class="load-tag load-${t.load_status}">${t.load_status}</span>
      </div>
    </div>`
    )
    .join("");

  // Risk factors
  const riskHTML = m.risk_factors
    .map((r) => `<div class="risk-item">${r}</div>`)
    .join("");

  // Priorities
  const prioHTML = m.priorities
    .map((p, i) => `<div class="risk-item"><strong>${i + 1}.</strong> ${p}</div>`)
    .join("");

  $("#panels-content").innerHTML = `
    <div class="panels">
      <div class="panel">
        <h3>Task Breakdown</h3>
        ${taskHTML}
      </div>
      <div class="panel">
        <h3>Team</h3>
        ${teamHTML || '<div class="empty-state">No team data</div>'}
      </div>
    </div>
    <div class="panels">
      <div class="panel">
        <h3>Risk Factors</h3>
        ${riskHTML}
      </div>
      <div class="panel">
        <h3>Priorities</h3>
        ${prioHTML}
      </div>
    </div>
  `;
}

// ── Chat ─────────────────────────────────────────────────────────────────────
async function onAsk(e) {
  e.preventDefault();
  const input = $("#chat-input");
  const question = input.value.trim();
  if (!question || !currentProject) return;

  addMessage(question, "user");
  input.value = "";
  $("#send-btn").disabled = true;

  try {
    const data = await postJSON("/api/ask", {
      project_id: currentProject,
      question,
    });
    addMessage(data.answer, "bot");
  } catch (err) {
    addMessage("Error: could not get a response.", "bot");
  }

  $("#send-btn").disabled = false;
}

function addMessage(text, role) {
  const container = $("#chat-messages");
  const label = role === "user" ? "You" : "MCP";
  container.innerHTML += `
    <div class="msg msg-${role}">
      <div class="msg-label">${label}</div>
      <div class="msg-bubble">${escapeHTML(text)}</div>
    </div>`;
  container.scrollTop = container.scrollHeight;
}

function escapeHTML(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

// ── Sync ─────────────────────────────────────────────────────────────────────
async function onSync() {
  const btn = $("#sync-btn");
  btn.disabled = true;
  btn.textContent = "Syncing...";
  toast("Sync started...");

  try {
    await postJSON("/api/sync", {});
    // Poll for completion
    const poll = setInterval(async () => {
      const st = await api("/api/sync/status");
      if (!st.running) {
        clearInterval(poll);
        btn.disabled = false;
        btn.textContent = "Sync Jira";
        if (st.error) {
          toast("Sync failed: " + st.error, true);
        } else {
          toast("Sync complete!");
          await loadProjects();
        }
      }
    }, 2000);
  } catch (e) {
    btn.disabled = false;
    btn.textContent = "Sync Jira";
    toast("Sync failed", true);
  }
}

// ── Health ────────────────────────────────────────────────────────────────────
async function loadHealth() {
  try {
    const h = await api("/api/health");
    $("#backend-badge").textContent = h.llm_backend;
  } catch {
    $("#backend-badge").textContent = "offline";
  }
}

// ── UI helpers ───────────────────────────────────────────────────────────────
function showLoading() {
  $("#dash-content").innerHTML =
    '<div class="loading"><div class="spinner"></div><div>Loading project...</div></div>';
  $("#panels-content").innerHTML = "";
}

function showEmpty() {
  $("#dash-content").innerHTML =
    '<div class="empty-state">No project data. Run sync to fetch from Jira.</div>';
  $("#panels-content").innerHTML = "";
}

function toast(msg, isError = false) {
  const el = $("#toast");
  el.textContent = msg;
  el.className = "toast show" + (isError ? " error" : "");
  setTimeout(() => (el.className = "toast"), 3000);
}
