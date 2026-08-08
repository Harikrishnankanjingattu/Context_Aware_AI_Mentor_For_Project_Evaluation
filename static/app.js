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
  previousPage:   'home',
  activeProjectArea: '',
  activeProjectVideos: [],
  activeVideoIdx: 0,
  activeTab:      'tasks',    // 'tasks' or 'papers'
  papersFilter:   'all',      // 'all' or 'ieee'
  allPapers:      [],
  ieeePapers:     [],
  githubRepo:     null,
  githubCommits:  [],
  taskStartTimes: {}
};

// ── Init ───────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  marked.setOptions({ breaks: true, gfm: true });
  
  const globalRepo = localStorage.getItem('globalGithubRepo');
  if (!globalRepo) {
    showPage('setup');
    document.querySelector('.nav-links').style.display = 'none';
  } else {
    document.querySelector('.nav-links').style.display = 'flex';
    showHome();
    loadProjects();
  }
});

function saveGlobalGithub() {
  const url = document.getElementById('global-github-input').value.trim();
  if (!url) return alert("Please enter a GitHub repository URL.");
  localStorage.setItem('globalGithubRepo', url);
  document.querySelector('.nav-links').style.display = 'flex';
  showHome();
  loadProjects();
}

// ── Page Navigation ────────────────────────────────────────────
function showPage(name) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
  document.getElementById('page-' + name).classList.add('active');
  const nb = document.getElementById('nav-' + name);
  if (nb) nb.classList.add('active');
}

function toggleMobileMenu() {
  const panel = document.querySelector('.task-panel');
  const overlay = document.getElementById('mobile-overlay');
  if (panel.classList.contains('mobile-open')) {
    panel.classList.remove('mobile-open');
    if (overlay) overlay.classList.remove('active');
  } else {
    panel.classList.add('mobile-open');
    if (overlay) overlay.classList.add('active');
  }
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
  state.activeTab = 'tasks';
  state.papersFilter = 'all';
  state.allPapers = [];
  state.ieeePapers = [];
  state.githubRepo = null;
  state.githubCommits = [];
  state.taskStartTimes = {};
  
  document.getElementById('github-unlinked').style.display = 'flex';
  document.getElementById('github-linked').style.display = 'none';

  // Reset tab selection UI
  document.getElementById('tab-tasks').classList.add('active');
  document.getElementById('tab-papers').classList.remove('active');
  document.getElementById('task-list').style.display = 'block';
  document.getElementById('papers-filter-wrap').style.display = 'none';
  document.getElementById('papers-list').style.display = 'none';
  document.getElementById('paper-detail-content').style.display = 'none';

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

    state.activeProjectArea = data.area || '';
    state.activeProjectVideos = data.videos || [];
    state.activeVideoIdx = 0;

    // Fetch GitHub info
    fetch(`/api/projects/${slug}/github`)
      .then(r => r.json())
      .then(ghData => {
        if (ghData.repo_url) {
          state.githubRepo = ghData.repo_url;
          state.githubCommits = ghData.commits || [];
          document.getElementById('github-unlinked').style.display = 'none';
          document.getElementById('github-linked').style.display = 'flex';
          document.getElementById('github-repo-link').href = 'https://github.com/' + state.githubRepo;
          document.getElementById('github-commits-count').textContent = state.githubCommits.length;
        }
        enforceGitHubLink();
      })
      .catch(err => {
        console.error("Error fetching GitHub repo:", err);
        enforceGitHubLink();
      });

    buildTaskList(data.content);
    hideStreamLoader();
    enforceGitHubLink();
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
  state.activeTab = 'tasks';
  state.papersFilter = 'all';
  state.allPapers = [];
  state.ieeePapers = [];

  // Reset tab selection UI
  switchGuideTab('tasks');

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
          if (data.reasoning) {
            // Display reasoning live in the stream text so the user knows it's thinking
            document.getElementById('stream-text').textContent = 'Thinking... ' + data.reasoning.slice(-100);
            preview.textContent = (preview.textContent + data.reasoning).slice(-800);
            preview.scrollTop = preview.scrollHeight;
          }
          if (data.chunk) {
            fullText += data.chunk;
            document.getElementById('stream-text').textContent = 'Generating your build guide…';
            preview.textContent = fullText.slice(-800);
            preview.scrollTop   = preview.scrollHeight;
          }
          if (data.done) {
            state.activeSlug = data.slug;
            document.getElementById('guide-project-date').textContent = 'Saved just now';
          }
        } catch (pe) { 
          if (pe.message && pe.message.includes('Error code')) {
            throw pe;
          } else if (pe.message === jsonStr || jsonStr.includes('error')) {
              throw pe;
          }
          console.error('Parse error:', pe); 
        }
      }
    }

    state.rawMarkdown = fullText;
    
    if (state.activeSlug) {
      const globalRepo = localStorage.getItem('globalGithubRepo');
      if (globalRepo) {
        // Automatically link the global repo to this new project
        try {
          await fetch(`/api/projects/${state.activeSlug}/github`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ repo_url: globalRepo })
          });
        } catch(e) {
          console.error("Failed to auto-link github repo", e);
        }
      }

      try {
        const res = await fetch(`/api/projects/${state.activeSlug}`);
        const data = await res.json();
        state.activeProjectArea = data.area || '';
        state.activeProjectVideos = data.videos || [];
        state.activeVideoIdx = 0;
        
        // Re-fetch GitHub info after auto-linking
        try {
          const ghRes = await fetch(`/api/projects/${state.activeSlug}/github`);
          const ghData = await ghRes.json();
          if (ghData.repo_url) {
            state.githubRepo = ghData.repo_url;
            state.githubCommits = ghData.commits || [];
            document.getElementById('github-unlinked').style.display = 'none';
            document.getElementById('github-linked').style.display = 'flex';
            document.getElementById('github-repo-link').href = 'https://github.com/' + state.githubRepo;
            document.getElementById('github-commits-count').textContent = state.githubCommits.length;
          }
        } catch(e) {
          console.error(e);
        }
      } catch (err) {
        console.error('Failed to load generated project details:', err);
      }
    } else {
      state.activeProjectArea = '';
      state.activeProjectVideos = [];
      state.activeVideoIdx = 0;
    }

    buildTaskList(fullText);
    hideStreamLoader();
    enforceGitHubLink();
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
    bodyEl.innerHTML = `
      <p>This step focuses on: <strong>${escHtml(task.title)}</strong>.</p>
      <p>Follow the phase instructions above and refer to sections 7 and 8 of your guide (Core Logic Explained and Testing Strategy) for deeper context on this step.</p>
      ${task.time ? `<p><strong>Estimated time:</strong> ${escHtml(task.time)}.</p>` : ''}
      ${task.difficulty ? `<p><strong>Complexity level:</strong> ${escHtml(task.difficulty)}.</p>` : ''}`;
  }

  // Start vs Complete buttons
  const startBtn = document.getElementById('btn-task-start');
  const checkBtn = document.getElementById('btn-task-check');
  
  if (state.completedTasks.has(idx)) {
    startBtn.style.display = 'none';
    checkBtn.style.display = 'inline-flex';
    checkBtn.innerHTML = '<i class="fa-solid fa-circle-check"></i> Completed';
    checkBtn.classList.add('done');
  } else if (state.taskStartTimes[idx]) {
    startBtn.style.display = 'none';
    checkBtn.style.display = 'inline-flex';
    checkBtn.innerHTML = '<i class="fa-regular fa-circle-check"></i> Verify & Complete';
    checkBtn.classList.remove('done');
  } else {
    startBtn.style.display = 'inline-flex';
    checkBtn.style.display = 'none';
  }
  startBtn.dataset.taskIdx = idx;
  checkBtn.dataset.taskIdx = idx;

  // Show detail panel
  document.getElementById('detail-empty').style.display   = 'none';
  document.getElementById('stream-loader').style.display  = 'none';
  document.getElementById('detail-content').style.display = 'flex';

  if (window.innerWidth <= 768) {
    const panel = document.querySelector('.task-panel');
    const overlay = document.getElementById('mobile-overlay');
    if (panel) panel.classList.remove('mobile-open');
    if (overlay) overlay.classList.remove('active');
  }
}

// ── Task State Logic ──────────────────────────────────────────
async function editGitHubUrl() {
  const currentUrl = localStorage.getItem('globalGithubRepo') || '';
  const newUrl = prompt("Enter your GitHub repository URL (e.g. owner/repo):", currentUrl);
  if (newUrl !== null) {
    const cleanUrl = newUrl.trim();
    if (!cleanUrl) return alert("URL cannot be empty.");
    localStorage.setItem('globalGithubRepo', cleanUrl);
    
    // If a project is open, update its linked repo immediately
    if (state.activeSlug) {
      await linkRepo(cleanUrl);
    } else {
      alert("Global GitHub repository updated successfully.");
    }
  }
}

async function linkGitHubRepo() {
  const url = document.getElementById('github-repo-input').value.trim();
  await linkRepo(url);
}

async function linkGitHubRepoOverlay() {
  const url = document.getElementById('github-overlay-input').value.trim();
  await linkRepo(url);
}

async function linkRepo(url) {
  if (!url) return alert("Please enter a GitHub URL.");
  if (!state.activeSlug) return;
  
  try {
    const res = await fetch(`/api/projects/${state.activeSlug}/github`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ repo_url: url })
    });
    const data = await res.json();
    if (data.error) throw new Error(data.error);
    
    // Re-fetch to update commits
    openGuide(state.activeSlug);
  } catch (err) {
    alert("Failed to link repo: " + err.message);
  }
}

function startCurrentTask() {
  const btn = document.getElementById('btn-task-start');
  const idx = Number(btn.dataset.taskIdx);
  if (isNaN(idx)) return;
  
  state.taskStartTimes[idx] = Date.now();
  selectTask(idx);
}

async function toggleCurrentTask() {
  const btn = document.getElementById('btn-task-check');
  const idx = Number(btn.dataset.taskIdx);
  if (isNaN(idx)) return;

  if (state.completedTasks.has(idx)) {
    // Un-complete
    state.completedTasks.delete(idx);
    selectTask(idx);
  } else {
    // Verify & Complete
    if (state.githubRepo) {
      const startTime = state.taskStartTimes[idx];
      if (!startTime) return alert("You must start the task first.");
      
      const oneMinuteInMs = 60000;
      if (Date.now() - startTime < oneMinuteInMs) {
        return alert("You must spend at least 1 minute on this task before completing it.");
      }
      
      btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Verifying...';
      try {
        const res = await fetch(`/api/projects/${state.activeSlug}/github`);
        const ghData = await res.json();
        const latestCommits = ghData.commits || [];
        
        let foundValidCommit = false;
        for (const c of latestCommits) {
          const cTime = new Date(c.date).getTime();
          // We check if there's a commit strictly after the task start time.
          if (cTime >= startTime) {
            foundValidCommit = true;
            break;
          }
        }
        
        if (!foundValidCommit) {
          btn.innerHTML = '<i class="fa-regular fa-circle-check"></i> Verify & Complete';
          return alert("No new commits found since you started this task! Please push your code to the linked GitHub repository.");
        }
        state.githubCommits = latestCommits;
        document.getElementById('github-commits-count').textContent = state.githubCommits.length;
      } catch (err) {
        btn.innerHTML = '<i class="fa-regular fa-circle-check"></i> Verify & Complete';
        return alert("Failed to verify commits: " + err.message);
      }
    }
    
    state.completedTasks.add(idx);
    selectTask(idx);
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

// ── Enforce GitHub Link ─────────────────────────────────────────
function enforceGitHubLink() {
  const isLinked = !!state.githubRepo;
  const overlay = document.getElementById('github-overlay');
  const taskPanel = document.querySelector('.task-panel');
  const detailPanel = document.getElementById('detail-panel');
  
  if (!isLinked) {
    if (overlay) overlay.style.display = 'flex';
    if (taskPanel) taskPanel.style.display = 'none';
    if (detailPanel) detailPanel.style.display = 'none';
  } else {
    if (overlay) overlay.style.display = 'none';
    if (taskPanel) taskPanel.style.display = 'flex';
    if (detailPanel) detailPanel.style.display = 'flex';
    
    // Re-initialize correct tab
    switchGuideTab(state.activeTab);
  }
}

// ── Tabs Switching (Overview, Tasks vs Papers) ───────────────────────────
function switchGuideTab(tabName) {
  if (!state.githubRepo) return; // Prevent switching if not linked

  state.activeTab = tabName;
  
  const tabOverview = document.getElementById('tab-overview');
  const tabTasks = document.getElementById('tab-tasks');
  const tabPapers = document.getElementById('tab-papers');
  
  const overviewListWrap = document.getElementById('overview-list-wrap');
  const taskList = document.getElementById('task-list');
  const papersFilterWrap = document.getElementById('papers-filter-wrap');
  const papersList = document.getElementById('papers-list');
  
  const detailEmpty = document.getElementById('detail-empty');
  const detailContent = document.getElementById('detail-content');
  const paperDetailContent = document.getElementById('paper-detail-content');
  const overviewContent = document.getElementById('overview-content');

  // Reset all tabs
  if(tabOverview) tabOverview.classList.remove('active');
  tabTasks.classList.remove('active');
  tabPapers.classList.remove('active');
  
  if (overviewListWrap) overviewListWrap.style.display = 'none';
  taskList.style.display = 'none';
  papersFilterWrap.style.display = 'none';
  papersList.style.display = 'none';
  
  detailEmpty.style.display = 'none';
  detailContent.style.display = 'none';
  paperDetailContent.style.display = 'none';
  if (overviewContent) overviewContent.style.display = 'none';
  const ghReqEmpty = document.getElementById('github-required-empty');
  if (ghReqEmpty) ghReqEmpty.style.display = 'none';

  if (tabName === 'overview') {
    if(tabOverview) tabOverview.classList.add('active');
    if(overviewListWrap) overviewListWrap.style.display = 'block';
    if(overviewContent) {
        overviewContent.style.display = 'block';
        overviewContent.innerHTML = marked.parse(state.rawMarkdown || 'No content generated yet.');
    }
  } else if (tabName === 'tasks') {
    tabTasks.classList.add('active');
    taskList.style.display = 'block';
    
    const activeItem = document.querySelector('.task-item.active:not(.paper-item)');
    if (activeItem) {
      const idx = Number(activeItem.dataset.idx);
      selectTask(idx);
    } else if (state.tasks.length > 0) {
      selectTask(0);
    } else {
      showDetailEmpty();
    }
  } else {
    tabPapers.classList.add('active');
    taskList.style.display = 'none';
    papersFilterWrap.style.display = 'block';
    papersList.style.display = 'block';
    
    document.getElementById('detail-content').style.display = 'none';
    
    if (state.allPapers.length === 0 && state.activeSlug) {
      loadPapers(state.activeSlug);
    } else {
      renderPapersList();
    }
  }
}

async function loadPapers(slug) {
  const listEl = document.getElementById('papers-list');
  listEl.innerHTML = '<li style="padding:20px;color:var(--text-muted);font-size:.875rem"><i class="fa-solid fa-spinner fa-spin"></i> Loading reference papers…</li>';
  
  try {
    const res = await fetch(`/api/projects/${slug}/papers`);
    const data = await res.json();
    if (data.error) throw new Error(data.error);
    
    state.allPapers = data.all_papers || [];
    state.ieeePapers = data.ieee_papers || [];
    
    renderPapersList();
  } catch (e) {
    console.error('Failed to load papers:', e);
    listEl.innerHTML = `<li style="padding:20px;color:var(--red);font-size:.875rem"><i class="fa-solid fa-circle-exclamation"></i> Error: ${escHtml(e.message)}</li>`;
  }
}

function setPaperFilter(filterVal) {
  state.papersFilter = filterVal;
  
  const pillAll = document.getElementById('pill-all-papers');
  const pillIeee = document.getElementById('pill-ieee-papers');
  
  if (filterVal === 'all') {
    pillAll.classList.add('active');
    pillIeee.classList.remove('active');
  } else {
    pillAll.classList.remove('active');
    pillIeee.classList.add('active');
  }
  
  renderPapersList();
}

function renderPapersList() {
  const listEl = document.getElementById('papers-list');
  listEl.innerHTML = '';
  
  const papers = state.papersFilter === 'all' ? state.allPapers : state.ieeePapers;
  
  if (papers.length === 0) {
    listEl.innerHTML = '<li style="padding:20px;color:var(--text-muted);font-size:.875rem">No matching papers found.</li>';
    showDetailEmpty();
    return;
  }
  
  papers.forEach((paper, idx) => {
    const li = document.createElement('li');
    li.className = 'task-item paper-item';
    li.dataset.idx = idx;
    
    let sourceIcon = 'fa-graduation-cap';
    if (paper.source.toLowerCase().includes('arxiv')) sourceIcon = 'fa-file-pdf';
    else if (paper.source.toLowerCase().includes('crossref')) sourceIcon = 'fa-circle-nodes';
    
    li.innerHTML = `
      <div class="task-check" style="border: none; background: transparent; display: flex; align-items: center; justify-content: center; font-size: 1.1rem; color: var(--blue-500); width: 24px; height: 24px; margin-right: 12px; flex-shrink: 0;">
        <i class="fa-solid ${sourceIcon}"></i>
      </div>
      <div class="task-info" style="flex: 1; min-width: 0;">
        <div class="task-title" style="font-weight: 600; line-height: 1.3; font-size: 0.9rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${escHtml(paper.title)}</div>
        <div class="task-meta" style="margin-top: 4px; display: flex; align-items: center; gap: 8px;">
          <span class="task-time-badge" style="font-size: 0.75rem; background: var(--surface); color: var(--text-secondary); border-radius: 4px; padding: 2px 6px;">${escHtml(paper.source)}</span>
          ${paper.year ? `<span class="task-diff-badge simple" style="font-size: 0.75rem; background: var(--blue-50); color: var(--blue-600); border-radius: 4px; padding: 2px 6px;">${escHtml(paper.year)}</span>` : ''}
        </div>
      </div>
    `;
    li.addEventListener('click', () => selectPaper(idx));
    listEl.appendChild(li);
  });
  
  const activePaperItem = document.querySelector('.paper-item.active');
  if (!activePaperItem && papers.length > 0) {
    selectPaper(0);
  }
}

function selectPaper(idx) {
  const papers = state.papersFilter === 'all' ? state.allPapers : state.ieeePapers;
  const paper = papers[idx];
  if (!paper) return;
  
  document.querySelectorAll('.paper-item').forEach(el => {
    el.classList.toggle('active', Number(el.dataset.idx) === idx);
  });
  
  document.getElementById('paper-title').textContent = paper.title;
  document.getElementById('paper-source-text').textContent = paper.source;
  document.getElementById('paper-year-text').textContent = paper.year || 'N/A';
  document.getElementById('paper-authors').textContent = paper.authors || 'Unknown';
  document.getElementById('paper-venue').textContent = paper.venue || 'Not specified';
  
  const doiWrap = document.getElementById('paper-doi-wrap');
  if (paper.doi) {
    doiWrap.style.display = 'block';
    document.getElementById('paper-doi').textContent = paper.doi;
  } else {
    doiWrap.style.display = 'none';
  }
  
  const linkBtn = document.getElementById('paper-link-btn');
  linkBtn.href = paper.url;
  
  document.getElementById('detail-empty').style.display = 'none';
  document.getElementById('detail-content').style.display = 'none';
  document.getElementById('paper-detail-content').style.display = 'flex';
}

// ── Stream Loader Helpers ──────────────────────────────────────
function showStreamLoader(msg) {
  document.getElementById('stream-text').textContent      = msg;
  document.getElementById('stream-loader').style.display  = 'flex';
  document.getElementById('detail-empty').style.display   = 'none';
  document.getElementById('detail-content').style.display = 'none';
  document.getElementById('paper-detail-content').style.display = 'none';
}
function hideStreamLoader() {
  document.getElementById('stream-loader').style.display = 'none';
}
function showDetailEmpty() {
  document.getElementById('detail-empty').style.display   = 'flex';
  document.getElementById('detail-content').style.display = 'none';
  document.getElementById('paper-detail-content').style.display = 'none';
  document.getElementById('stream-loader').style.display  = 'none';
  const ghReqEmpty = document.getElementById('github-required-empty');
  if (ghReqEmpty) ghReqEmpty.style.display = 'none';
  
  if (state.activeTab === 'papers') {
    document.getElementById('empty-title').textContent = 'Select a paper to view details';
    document.getElementById('empty-desc').textContent = 'Click any academic reference paper from the list on the left to see its title, authors, venue, and access the source link.';
  } else {
    document.getElementById('empty-title').textContent = 'Select a task to view details';
    document.getElementById('empty-desc').textContent = 'Click any task from the list on the left to see its full description, time estimate, and difficulty level.';
  }
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
