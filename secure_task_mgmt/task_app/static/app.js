const state = {
  mode: "login",
  token: localStorage.getItem("accessToken"),
  tasklists: [],
  activeListId: null,
};

const $ = (id) => document.getElementById(id);

function authHeaders() {
  return {
    "Content-Type": "application/json",
    Authorization: `Bearer ${state.token}`,
  };
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(state.token ? { Authorization: `Bearer ${state.token}` } : {}),
      ...(options.headers || {}),
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ message: "Request failed" }));
    throw new Error(error.message || "Request failed");
  }

  const text = await response.text();
  return text ? JSON.parse(text) : null;
}

function setMode(mode) {
  state.mode = mode;
  $("loginMode").classList.toggle("active", mode === "login");
  $("registerMode").classList.toggle("active", mode === "register");
  $("nameField").hidden = mode === "login";
  $("confirmField").hidden = mode === "login";
  $("authMessage").textContent = "";
}

function setSignedIn(isSignedIn) {
  $("authPanel").hidden = isSignedIn;
  $("appPanel").hidden = !isSignedIn;
}

async function handleAuth(event) {
  event.preventDefault();
  $("authMessage").textContent = "";

  const email = $("email").value.trim();
  const password = $("password").value;

  try {
    if (state.mode === "register") {
      await api("/register", {
        method: "POST",
        body: JSON.stringify({
          email,
          password,
          full_name: $("fullName").value.trim(),
          confirm_password: $("confirmPassword").value,
        }),
      });
    }

    const tokens = await api("/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
    state.token = tokens.access;
    localStorage.setItem("accessToken", state.token);
    setSignedIn(true);
    await refreshAll();
  } catch (error) {
    $("authMessage").textContent = error.message;
  }
}

async function refreshAll() {
  await Promise.all([loadDashboard(), loadTasklists()]);
  if (state.activeListId) {
    await loadTasks();
  }
}

async function loadDashboard() {
  const stats = await api("/dashboard");
  const items = [
    ["Total", stats.total_tasks],
    ["Pending", stats.pending_tasks],
    ["Completed", stats.completed_tasks],
    ["Overdue", stats.overdue_tasks],
    ["High priority", stats.high_priority_tasks],
  ];

  $("statsGrid").innerHTML = items
    .map(([label, value]) => `<article class="stat"><strong>${value}</strong><span>${label}</span></article>`)
    .join("");
}

async function loadTasklists() {
  state.tasklists = await api("/tasklist");
  if (!state.activeListId && state.tasklists.length) {
    state.activeListId = state.tasklists[0].id;
  }

  $("tasklists").innerHTML = state.tasklists.length
    ? state.tasklists
        .map(
          (list) =>
            `<button class="list-item ${list.id === state.activeListId ? "active" : ""}" data-id="${list.id}">${list.title}</button>`
        )
        .join("")
    : `<p class="empty">Create your first task list.</p>`;

  const active = state.tasklists.find((list) => list.id === state.activeListId);
  $("activeListTitle").textContent = active ? active.title : "Tasks";
}

async function loadTasks() {
  if (!state.activeListId) {
    $("tasks").innerHTML = `<p class="empty">Select or create a list.</p>`;
    return;
  }

  const params = new URLSearchParams();
  if ($("search").value.trim()) params.set("q", $("search").value.trim());
  if ($("filterPriority").value) params.set("priority", $("filterPriority").value);
  params.set("is_completed", $("showDone").checked ? "true" : "false");

  const tasks = await api(`/tasklist/${state.activeListId}/tasks?${params.toString()}`);
  $("tasks").innerHTML = tasks.length
    ? tasks.map(renderTask).join("")
    : `<p class="empty">No tasks match this view.</p>`;
}

function renderTask(task) {
  const due = task.due_date ? new Date(task.due_date).toLocaleString([], { dateStyle: "medium", timeStyle: "short" }) : "No deadline";
  return `
    <article class="task-item">
      <input type="checkbox" ${task.is_completed ? "checked" : ""} data-task-id="${task.id}" aria-label="Toggle task">
      <div>
        <p class="task-title">${task.title}</p>
        <div class="task-meta">
          <span class="badge ${task.priority}">${task.priority}</span>
          <span>${due}</span>
        </div>
      </div>
      <button class="ghost" data-delete-id="${task.id}" title="Delete task" aria-label="Delete task">Delete</button>
    </article>`;
}

async function createTasklist(event) {
  event.preventDefault();
  const title = $("listTitle").value.trim();
  if (!title) return;
  const list = await api("/tasklist", {
    method: "POST",
    body: JSON.stringify({ title, description: "" }),
  });
  $("listTitle").value = "";
  state.activeListId = list.id;
  await refreshAll();
}

async function createTask(event) {
  event.preventDefault();
  if (!state.activeListId) return;
  const dueDate = $("dueDate").value ? new Date($("dueDate").value).toISOString() : null;
  await api(`/tasklist/${state.activeListId}/tasks`, {
    method: "POST",
    body: JSON.stringify({
      title: $("taskTitle").value.trim(),
      description: "",
      priority: $("priority").value,
      due_date: dueDate,
      reminder: null,
      steps: [],
    }),
  });
  $("taskTitle").value = "";
  $("dueDate").value = "";
  await refreshAll();
}

async function toggleTask(taskId, isCompleted) {
  await api(`/tasklist/${state.activeListId}/tasks/${taskId}`, {
    method: "PATCH",
    body: JSON.stringify({ is_completed: isCompleted }),
  });
  await refreshAll();
}

async function deleteTask(taskId) {
  await api(`/tasklist/${state.activeListId}/tasks/${taskId}`, { method: "DELETE" });
  await refreshAll();
}

$("loginMode").addEventListener("click", () => setMode("login"));
$("registerMode").addEventListener("click", () => setMode("register"));
$("authForm").addEventListener("submit", handleAuth);
$("listForm").addEventListener("submit", createTasklist);
$("taskForm").addEventListener("submit", createTask);
$("search").addEventListener("input", loadTasks);
$("filterPriority").addEventListener("change", loadTasks);
$("showDone").addEventListener("change", loadTasks);
$("logoutBtn").addEventListener("click", () => {
  localStorage.removeItem("accessToken");
  state.token = null;
  setSignedIn(false);
});

$("tasklists").addEventListener("click", async (event) => {
  const button = event.target.closest("[data-id]");
  if (!button) return;
  state.activeListId = button.dataset.id;
  await loadTasklists();
  await loadTasks();
});

$("tasks").addEventListener("change", async (event) => {
  if (event.target.matches("[data-task-id]")) {
    await toggleTask(event.target.dataset.taskId, event.target.checked);
  }
});

$("tasks").addEventListener("click", async (event) => {
  const button = event.target.closest("[data-delete-id]");
  if (!button) return;
  await deleteTask(button.dataset.deleteId);
});

setMode("login");
setSignedIn(Boolean(state.token));
if (state.token) refreshAll().catch(() => setSignedIn(false));
