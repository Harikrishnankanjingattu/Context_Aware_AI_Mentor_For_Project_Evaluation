/* =============================================================
   LUCA — app.js
   Handles: page navigation, guide generation streaming,
            task extraction from markdown, detail view,
            completion tracking, project grid.
   ============================================================= */

// ── State ──────────────────────────────────────────────────────
const state = {
  projects:       [],
  activeSlug:     null,
  tasks:          [],
  completedTasks: new Set(),
  rawMarkdown:    '',
  previousPage:   'home'
};

// ── Init ───────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  loadProjects();
  marked.setOptions({ breaks: true, gfm: true });
});

// ── Page Navigation ────────────────────────────────────────────
function showPage(name) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
  document.getElementById('page-' + name).classList.add('active');
  const nb = document.getElementById('nav-' + name);
  if (nb) nb.classList.add('active');
}

function showHome() {
  state.previousPage = 'home';
  showPage('home');
}

function showProjects() {
  loadProjects();
  showPage('projects');
  state.previousPage = 'projects';
}

function goBack() {
  showPage(state.previousPage || 'home');
}

// ── Fill example chips ─────────────────────────────────────────
function fillExample(name, abstract) {
  document.getElementById('input-name').value     = name;
  document.getElementById('input-abstract').value = abstract;
  document.getElementById('input-abstract').focus();
}

// ── Load Projects ──────────────────────────────────────────────
async function loadProjects() {
  try {
    const res       = await fetch('/api/projects');
    state.projects  = await res.json();
    renderProjectsGrid();
  } catch (e) {
    console.error('Failed to load projects:', e);
  }
}

function renderProjectsGrid() {
  const grid = document.getElementById('projects-grid');
  if (!state.projects.length) {
    grid.innerHTML = `
      <div class="no-projects">
        <i class="fa-regular fa-folder-open"></i>
        <h3>No guides yet</h3>
        <p>Generate your first project guide from the Home page.</p>
      </div>`;
    return;
  }
  grid.innerHTML = state.projects.slice().reverse().map(p => `
    <div class="project-card" onclick="openGuide('${p.slug}')">
      <div class="project-card-icon"><i class="fa-solid fa-diagram-project"></i></div>
      <div class="project-card-name">${escHtml(p.name)}</div>
      <div class="project-card-abstract">${escHtml(p.abstract || '')}</div>
      <div class="project-card-date">${formatDate(p.created)}</div>
      <div class="project-card-arrow"><i class="fa-solid fa-arrow-right"></i></div>
    </div>
  `).join('');
}

// ── Open Existing Guide ────────────────────────────────────────
async function openGuide(slug) {
  state.activeSlug    = slug;
  state.completedTasks = new Set();
  showPage('guide');
  showStreamLoader('Loading guide…');

  try {
    const res  = await fetch(`/api/projects/${slug}`);
    const data = await res.json();
    if (data.error) throw new Error(data.error);

    const project = state.projects.find(p => p.slug === slug);
    state.rawMarkdown = data.content;

    document.getElementById('guide-project-name').textContent = project ? project.name : slug;
    document.getElementById('guide-project-date').textContent = project ? formatDate(project.created) : '';

    buildTaskList(data.content);
    hideStreamLoader();
    showDetailEmpty();
  } catch (e) {
    hideStreamLoader();
    console.error(e);
  }
}

// ── Generate New Guide ─────────────────────────────────────────
async function startGeneration() {
  const name     = document.getElementById('input-name').value.trim();
  const abstract = document.getElementById('input-abstract').value.trim();
  if (!name)     { alert('Please enter a project name.'); return; }
  if (!abstract) { alert('Please describe your project idea.'); return; }

  showPage('guide');
  state.activeSlug    = null;
  state.tasks         = [];
  state.completedTasks = new Set();
  document.getElementById('guide-project-name').textContent = name;
  document.getElementById('guide-project-date').textContent  = 'Generating…';
  document.getElementById('task-list').innerHTML = '';
  document.getElementById('progress-bar').style.width = '0%';
  document.getElementById('progress-label').textContent    = '';
  showDetailEmpty();
  showStreamLoader('Generating your build guide…');

  let fullText = '';
  const preview = document.getElementById('stream-preview');
  preview.textContent = '';

  try {
    const response = await fetch('/api/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, abstract })
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);

    const reader  = response.body.getReader();
    const decoder = new TextDecoder();
    let   buffer  = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop();

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue;
        const jsonStr = line.slice(6).trim();
        if (!jsonStr) continue;
        try {
          const data = JSON.parse(jsonStr);
          if (data.error) throw new Error(data.error);
          if (data.chunk) {
            fullText += data.chunk;
            preview.textContent = fullText.slice(-800);
            preview.scrollTop   = preview.scrollHeight;
          }
          if (data.done) {
            state.activeSlug = data.slug;
            document.getElementById('guide-project-date').textContent = 'Saved just now';
          }
        } catch (pe) { console.error('Parse error:', pe); }
      }
    }

    state.rawMarkdown = fullText;
    buildTaskList(fullText);
    hideStreamLoader();
    await loadProjects();

  } catch (e) {
    console.error('Generation error:', e);
    hideStreamLoader();
    const empty = document.getElementById('detail-empty');
    document.getElementById('detail-content').style.display = 'none';
    empty.style.display = 'flex';
    empty.innerHTML = `
      <div class="detail-empty-icon" style="background:#fce7f3">
        <i class="fa-solid fa-triangle-exclamation" style="color:#dc2626"></i>
      </div>
      <h3 style="color:#dc2626">Generation Failed</h3>
      <p>${escHtml(e.message)}</p>`;
  }
}

// ── Build Task List from Markdown ──────────────────────────────
function buildTaskList(markdown) {
  const tasks = extractTasks(markdown);
  state.tasks = tasks;

  const list = document.getElementById('task-list');
  list.innerHTML = '';

  if (!tasks.length) {
    list.innerHTML = '<li style="padding:20px;color:var(--text-muted);font-size:.875rem">No steps found in this guide.</li>';
    return;
  }

  let currentPhase = null;

  tasks.forEach((task, idx) => {
    if (task.phase && task.phase !== currentPhase) {
      currentPhase = task.phase;
      const phaseEl = document.createElement('li');
      phaseEl.className   = 'task-phase-label';
      phaseEl.textContent = task.phase;
      list.appendChild(phaseEl);
    }

    const diffClass = (task.difficulty || '').toLowerCase();
    const li = document.createElement('li');
    li.className   = 'task-item';
    li.dataset.idx = idx;
    li.innerHTML   = `
      <div class="task-check"></div>
      <div class="task-info">
        <div class="task-title">${escHtml(task.title)}</div>
        <div class="task-meta">
          ${task.time ? `<span class="task-time-badge"><i class="fa-regular fa-clock"></i>${escHtml(task.time)}</span>` : ''}
          ${task.difficulty ? `<span class="task-diff-badge ${diffClass}">${escHtml(task.difficulty)}</span>` : ''}
        </div>
      </div>`;
    li.addEventListener('click', () => selectTask(idx));
    list.appendChild(li);
  });

  updateProgress();
  if (tasks.length > 0) selectTask(0);
}

// ══════════════════════════════════════════════════════════════
//  TASK EXTRACTOR
//  Parses the markdown guide into an array of task objects.
//  Each task: { title, phase, time, difficulty, body }
//  Body = ALL content between this numbered item and the next,
//         including blank lines (needed for markdown rendering).
// ══════════════════════════════════════════════════════════════
function extractTasks(markdown) {
  const tasks = [];
  const lines = markdown.split('\n');

  const reTime = /Time\s+required?[:\s]+([^\n,]+)/i;
  const reDiff = /Complexity[:\s]+(Simple|Easy|Hard)/i;

  let currentPhase = null;
  let currentTask  = null;
  let bodyLines    = [];

  // Finalise the task being assembled and push it
  const pushTask = () => {
    if (!currentTask) return;

    // Try extracting time / difficulty from the body if not already in the title
    const rawBody = bodyLines.join('\n');
    if (!currentTask.time) {
      const m = rawBody.match(reTime);
      if (m) currentTask.time = m[1].trim().replace(/[.,]$/, '');
    }
    if (!currentTask.difficulty) {
      const m = rawBody.match(reDiff);
      if (m) currentTask.difficulty = capFirst(m[1]);
    }

    // Remove time / diff annotation lines from the body text so they
    // don't render as duplicate info in the detail panel
    const cleanBody = bodyLines
      .filter(l => !reTime.test(l.trim()) && !reDiff.test(l.trim()))
      .join('\n')
      .trim();

    tasks.push({ ...currentTask, body: cleanBody });
    currentTask = null;
    bodyLines   = [];
  };

  for (const raw of lines) {
    const t = raw.trim();

    // ── Headings: phase separators
    if (/^#{1,4}\s+/.test(t)) {
      pushTask();
      // Treat as phase label if it mentions Phase / Step
      if (/phase|step/i.test(t)) {
        currentPhase = t.replace(/^#+\s*/, '').trim();
      }
      // Any other heading just closes the current task; no new task starts
      continue;
    }

    // ── Numbered list item → start a new task
    const nm = t.match(/^(\d+)\.\s+(.+)/);
    if (nm) {
      pushTask();
      let title = nm[2].trim();

      // Strip inline time / complexity from the title line
      let time = null, difficulty = null;
      const tM = title.match(reTime);
      if (tM) { time  = tM[1].trim().replace(/[.,]$/, ''); title = title.replace(tM[0], '').trim(); }
      const dM = title.match(reDiff);
      if (dM) { difficulty = capFirst(dM[1]); title = title.replace(dM[0], '').trim(); }
      title = title.replace(/[,\s]+$/, '');

      currentTask = { title, phase: currentPhase, time, difficulty };
      bodyLines   = [];
      continue;
    }

    // ── Everything else while inside a task → body content
    //    Blank lines are intentionally kept so markdown renders paragraphs
    if (currentTask) {
      bodyLines.push(raw);
    }
  }
  pushTask(); // flush last task

  return tasks.filter(task => task.title && task.title.length > 3);
}

// ── Select Task → Show Detail ──────────────────────────────────
function selectTask(idx) {
  const task = state.tasks[idx];
  if (!task) return;

  // Highlight sidebar item
  document.querySelectorAll('.task-item').forEach(el => {
    el.classList.toggle('active', Number(el.dataset.idx) === idx);
  });

  const diffClass = (task.difficulty || '').toLowerCase();

  // Badges
  document.getElementById('detail-time-text').textContent = task.time || 'Not specified';
  document.getElementById('detail-diff-text').textContent = task.difficulty || 'Not specified';
  document.getElementById('detail-diff-badge').className  = `badge badge-diff ${diffClass}`;

  // Title
  document.getElementById('detail-title').textContent = task.title;

  // Body — render markdown; if empty show a helpful placeholder
  const bodyEl = document.getElementById('detail-body');
  if (task.body && task.body.trim().length > 0) {
    bodyEl.innerHTML = marked.parse(task.body);
  } else {
    // Fallback: construct a meaningful placeholder from the title itself
    bodyEl.innerHTML = `
      <p>This step focuses on: <strong>${escHtml(task.title)}</strong>.</p>
      <p>Follow the phase instructions above and refer to sections 7 and 8 of your guide (Core Logic Explained and Testing Strategy) for deeper context on this step.</p>
      ${task.time ? `<p><strong>Estimated time:</strong> ${escHtml(task.time)}.</p>` : ''}
      ${task.difficulty ? `<p><strong>Complexity level:</strong> ${escHtml(task.difficulty)}.</p>` : ''}`;
  }

  // Mark-complete button
  const checkBtn = document.getElementById('btn-task-check');
  if (state.completedTasks.has(idx)) {
    checkBtn.innerHTML = '<i class="fa-solid fa-circle-check"></i> Completed';
    checkBtn.classList.add('done');
  } else {
    checkBtn.innerHTML = '<i class="fa-regular fa-circle-check"></i> Mark Complete';
    checkBtn.classList.remove('done');
  }
  checkBtn.dataset.taskIdx = idx;

  // Show detail panel
  document.getElementById('detail-empty').style.display   = 'none';
  document.getElementById('stream-loader').style.display  = 'none';
  document.getElementById('detail-content').style.display = 'flex';
}

// ── Toggle Task Completion ─────────────────────────────────────
function toggleCurrentTask() {
  const btn = document.getElementById('btn-task-check');
  const idx = Number(btn.dataset.taskIdx);
  if (isNaN(idx)) return;

  if (state.completedTasks.has(idx)) {
    state.completedTasks.delete(idx);
    btn.innerHTML = '<i class="fa-regular fa-circle-check"></i> Mark Complete';
    btn.classList.remove('done');
  } else {
    state.completedTasks.add(idx);
    btn.innerHTML = '<i class="fa-solid fa-circle-check"></i> Completed';
    btn.classList.add('done');
  }

  document.querySelectorAll('.task-item').forEach(el => {
    if (Number(el.dataset.idx) === idx) {
      el.classList.toggle('done', state.completedTasks.has(idx));
    }
  });

  updateProgress();
}

function updateProgress() {
  const total = state.tasks.length;
  const done  = state.completedTasks.size;
  const pct   = total ? Math.round((done / total) * 100) : 0;
  document.getElementById('progress-bar').style.width   = pct + '%';
  document.getElementById('progress-label').textContent = `${done} of ${total} tasks completed`;
}

// ── Stream Loader Helpers ──────────────────────────────────────
function showStreamLoader(msg) {
  document.getElementById('stream-text').textContent      = msg;
  document.getElementById('stream-loader').style.display  = 'flex';
  document.getElementById('detail-empty').style.display   = 'none';
  document.getElementById('detail-content').style.display = 'none';
}
function hideStreamLoader() {
  document.getElementById('stream-loader').style.display = 'none';
}
function showDetailEmpty() {
  document.getElementById('detail-empty').style.display   = 'flex';
  document.getElementById('detail-content').style.display = 'none';
  document.getElementById('stream-loader').style.display  = 'none';
}

// ── Export Markdown ────────────────────────────────────────────
async function exportGuide() {
  if (!state.activeSlug) return;
  try {
    const res  = await fetch(`/api/projects/${state.activeSlug}`);
    const data = await res.json();
    const blob = new Blob([data.content], { type: 'text/markdown;charset=utf-8;' });
    const url  = URL.createObjectURL(blob);
    const a    = Object.assign(document.createElement('a'), { href: url, download: `${state.activeSlug}.md` });
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  } catch (e) { alert('Export failed: ' + e.message); }
}

// ── Utilities ──────────────────────────────────────────────────
function escHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function capFirst(str) {
  return str ? str.charAt(0).toUpperCase() + str.slice(1) : str;
}

function formatDate(ts) {
  if (!ts || ts.length < 8) return '';
  return `${ts.slice(6, 8)}/${ts.slice(4, 6)}/${ts.slice(0, 4)}`;
}
