/**
 * Genesis AI — Application Script (static/script.js)
 * Black/White/Red minimal UI · vis-network · Chart.js · Async API
 */
'use strict';

// ================================================================
//  STATE
// ================================================================
const STATE = {
  projectId:  null,
  result:     null,
  transcript: [],
  chart:      null,
  network:    null,
  baseBudget: 100000,
  running:    false,
};

const STAGES = ['user','rag','planner','architect','business','critic','output'];

const SPEAKER = {
  Architect: { emoji:'🏗️', cls:'architect' },
  Security:  { emoji:'🛡️', cls:'security'  },
  Finance:   { emoji:'💹', cls:'finance'   },
  Moderator: { emoji:'⚖️', cls:'moderator' },
};

// ================================================================
//  INIT
// ================================================================
document.addEventListener('DOMContentLoaded', () => {
  initKnowledgeGraph();
  recalcWhatIf();
  loadHistory();

  const ta = document.getElementById('problem-statement');
  const cc = document.getElementById('char-counter');
  if (ta && cc) ta.addEventListener('input', () => cc.textContent = `${ta.value.length} / 4000`);
});

// ================================================================
//  TAB SWITCHING (custom — no Bootstrap tab JS needed)
// ================================================================
function switchTab(id, btn) {
  document.querySelectorAll('.tab-pane').forEach(p => p.style.display = 'none');
  document.querySelectorAll('.g-tab').forEach(b => b.classList.remove('active'));
  const pane = document.getElementById('tab-' + id);
  if (pane) pane.style.display = '';
  if (btn)  btn.classList.add('active');
}

// ================================================================
//  KNOWLEDGE GRAPH — vis-network
// ================================================================
function initKnowledgeGraph() {
  const container = document.getElementById('network-graph');
  if (!container || typeof vis === 'undefined') return;

  // Colour palette — black/white/red
  const C = { red:'#e53935', white:'#e8e8e8', grey:'#666666', dim:'#333333', bg:'#1a1a1a', border:'#2e2e2e' };

  const nodeStyle = (color, size=22) => ({
    color: { background: C.bg, border: color, highlight: { background: C.bg, border: color } },
    font:  { color: C.white, size: 12, face: 'Inter' },
    borderWidth: 2,
    size,
  });

  const nodes = new vis.DataSet([
    { id:1,  label:'👤 User',              ...nodeStyle(C.grey, 20),  shape:'ellipse',  title:'Input: problem statement' },
    { id:2,  label:'🧠 Orchestrator',      ...nodeStyle(C.red,  28),  shape:'ellipse',  title:'Central brain — routes to all agents', borderWidth:3 },
    { id:3,  label:'📚 RAG\nResearcher',   ...nodeStyle(C.white,20),  shape:'box',      title:'ChromaDB semantic search' },
    { id:4,  label:'🗄 ChromaDB',          ...nodeStyle(C.grey, 18),  shape:'database', title:'Local vector store' },
    { id:5,  label:'🏗 Architect\nAgent',  ...nodeStyle(C.white,20),  shape:'box',      title:'System architecture + tech stack' },
    { id:6,  label:'💼 Business\nAgent',   ...nodeStyle(C.white,20),  shape:'box',      title:'BMC + budget + government schemes' },
    { id:7,  label:'⬡ IBM\nWatsonx.ai',   ...nodeStyle('#b0b0b0',22), shape:'hexagon',  title:'Granite LLM inference API' },
    { id:8,  label:'🛡 Security\nCritic',  ...nodeStyle(C.red,  20),  shape:'box',      title:'Innovation score ≥7 required' },
    { id:9,  label:'💹 Finance\nCritic',   ...nodeStyle(C.white,20),  shape:'box',      title:'Cost efficiency score ≥6 required' },
    { id:10, label:'⚖ Debate\nRoom',       ...nodeStyle(C.red,  26),  shape:'diamond',  title:'Self-critic loop · max 3 rounds', borderWidth:3 },
    { id:11, label:'💰 Solution A\nLow Cost',      ...nodeStyle(C.red,  18), shape:'triangle', title:'Open-source, shared cloud' },
    { id:12, label:'⚡ Solution B\nHigh Perf',     ...nodeStyle(C.white,18), shape:'triangle', title:'Managed cloud, auto-scaling' },
    { id:13, label:'🌿 Solution C\nEco-Friendly',  ...nodeStyle(C.grey, 18), shape:'triangle', title:'Green cloud, serverless' },
  ]);

  const edgeStyle = (color, dashes=false) => ({
    color:  { color, highlight: color, hover: color },
    width:  1.5,
    dashes,
    smooth: { type:'curvedCW', roundness:0.2 },
    font:   { color:'#666', size:9, face:'Inter', align:'middle' },
    arrows: { to:{ enabled:true, scaleFactor:0.6 } },
  });

  const edges = new vis.DataSet([
    { from:1,  to:2,  label:'submit',   ...edgeStyle(C.grey) },
    { from:2,  to:3,  label:'query',    ...edgeStyle(C.white) },
    { from:3,  to:4,  label:'search',   ...edgeStyle(C.grey, true) },
    { from:4,  to:3,  label:'results',  ...edgeStyle(C.grey, true) },
    { from:3,  to:2,  label:'context',  ...edgeStyle(C.white) },
    { from:2,  to:5,  label:'plan A',   ...edgeStyle(C.white) },
    { from:2,  to:6,  label:'plan B',   ...edgeStyle(C.white) },
    { from:5,  to:7,  label:'prompt',   ...edgeStyle(C.grey, true) },
    { from:6,  to:7,  label:'prompt',   ...edgeStyle(C.grey, true) },
    { from:7,  to:5,  label:'response', ...edgeStyle(C.grey, true) },
    { from:7,  to:6,  label:'response', ...edgeStyle(C.grey, true) },
    { from:5,  to:10, label:'review',   ...edgeStyle(C.red) },
    { from:6,  to:10, label:'review',   ...edgeStyle(C.red) },
    { from:8,  to:10, label:'score',    ...edgeStyle(C.red) },
    { from:9,  to:10, label:'score',    ...edgeStyle(C.white) },
    { from:10, to:5,  label:'revise',   ...edgeStyle(C.red, true) },
    { from:10, to:11, label:'approve',  ...edgeStyle(C.red) },
    { from:10, to:12, label:'approve',  ...edgeStyle(C.white) },
    { from:10, to:13, label:'approve',  ...edgeStyle(C.grey) },
    { from:10, to:8,  label:'',         ...edgeStyle(C.grey, true) },
    { from:10, to:9,  label:'',         ...edgeStyle(C.grey, true) },
  ]);

  const options = {
    nodes: { shadow:false, scaling:{ min:16, max:32 } },
    edges: { selectionWidth:2.5 },
    physics: {
      solver:'forceAtlas2Based',
      stabilization:{ iterations:300, fit:true },
      forceAtlas2Based:{ gravitationalConstant:-55, springLength:110, springConstant:0.06, damping:0.6 },
    },
    interaction: { hover:true, tooltipDelay:150, navigationButtons:false, keyboard:false },
    layout:      { improvedLayout:true },
  };

  STATE.network = new vis.Network(container, { nodes, edges }, options);
  STATE.network.once('stabilizationIterationsDone', () => STATE.network.fit({ animation:true }));
}

// ================================================================
//  DEPLOY AGENTS
// ================================================================
async function deployAgents() {
  if (STATE.running) return;

  const title   = document.getElementById('project-title').value.trim() || 'Untitled Project';
  const problem = document.getElementById('problem-statement').value.trim();

  if (!problem || problem.length < 20) {
    toast('Please enter a detailed problem statement (min 20 chars).', 'error');
    return;
  }

  STATE.running = true;
  const btn  = document.getElementById('btn-deploy');
  const text = document.getElementById('btn-text');
  btn.disabled = true;
  text.innerHTML = '<span class="g-spinner"></span>Agents Running…';

  setStatus('Deploying…', 'active');
  animatePipeline();

  try {
    toast(`Deploying Genesis agents for "${title}"…`, 'info');

    const res = await fetch('/api/orchestrate', {
      method:  'POST',
      headers: { 'Content-Type':'application/json' },
      body:    JSON.stringify({ problem_statement:problem, project_title:title }),
    });

    const data = await res.json();

    if (!res.ok) throw new Error(data.error || `Server error ${res.status}`);

    STATE.projectId  = data.project_id;
    STATE.result     = data.result;
    STATE.transcript = data.result.debate_transcript || [];

    const budgetStr = data.result.solutions?.[0]?.business?.budget_estimate || '';
    const digits    = budgetStr.replace(/\D/g,'');
    if (digits) STATE.baseBudget = Math.min(parseInt(digits.slice(0,7)), 9999999);

    pipelineDone();
    renderDebate(STATE.transcript);
    renderSolutions(data.result.solutions || []);
    renderRadar(data.result.scores);
    renderRAGContext(data.result.rag_context || []);
    updateExportInfo(data.project_id, title);
    recalcWhatIf();
    loadHistory();

    setStatus('Complete', 'live');
    toast(`✅ ${data.result.solutions.length} solutions generated — project #${data.project_id}`, 'success');

    // Auto-switch to analytics tab
    setTimeout(() => {
      const btn = document.querySelector('[data-tab="analytics"]');
      if (btn) switchTab('analytics', btn);
    }, 700);

  } catch(err) {
    console.error(err);
    toast(`Error: ${err.message}`, 'error');
    setStatus('Error', 'error');
    resetPipeline();
  } finally {
    STATE.running    = false;
    btn.disabled     = false;
    text.textContent = '⚡ Deploy Genesis Agents';
  }
}

// ================================================================
//  PIPELINE ANIMATION
// ================================================================
function animatePipeline() {
  const messages = {
    user:'Parsing input…', rag:'Querying ChromaDB…', planner:'Planning solutions…',
    architect:'Generating architectures…', business:'Building financial models…',
    critic:'Security & Finance critiquing…', output:'Finalising results…',
  };
  const delays = [0,700,1500,2600,4000,5600,7500];
  STAGES.forEach((s,i) => {
    setTimeout(() => {
      setStage(s,'active');
      const c = document.getElementById(`conn-${i+1}`);
      if (c) c.classList.add('active');
      const el = document.getElementById('pipeline-status');
      if (el) el.textContent = messages[s] || '';
    }, delays[i]);
  });
}

function setStage(id, state) {
  STAGES.forEach(s => {
    const el = document.getElementById(`icon-${s}`);
    if (el) el.classList.remove('active','done');
  });
  const el = document.getElementById(`icon-${id}`);
  if (el) el.classList.add(state);
}

function pipelineDone() {
  STAGES.forEach((s,i) => {
    const el = document.getElementById(`icon-${s}`);
    if (el) { el.classList.remove('active'); el.classList.add('done'); }
    const c = document.getElementById(`conn-${i+1}`);
    if (c) c.classList.add('active');
  });
  const el = document.getElementById('pipeline-status');
  if (el) el.textContent = '✅ All agents complete';
}

function resetPipeline() {
  STAGES.forEach((s,i) => {
    const el = document.getElementById(`icon-${s}`);
    if (el) el.classList.remove('active','done');
    const c = document.getElementById(`conn-${i+1}`);
    if (c) c.classList.remove('active');
  });
  const el = document.getElementById('pipeline-status');
  if (el) el.textContent = 'Awaiting deployment';
}

// ================================================================
//  DEBATE ROOM
// ================================================================
function renderDebate(transcript) {
  const win = document.getElementById('debate-chat');
  if (!win) return;
  win.innerHTML = '';

  let maxRound = 0;
  let scoreI = '—', scoreC = '—';

  transcript.forEach((t,i) => {
    const m = SPEAKER[t.speaker] || { emoji:'🤖', cls:'' };
    if ((t.round||0) > maxRound) maxRound = t.round||0;

    const im = t.message.match(/Innovation Score:\s*(\d+)/i);
    const cm = t.message.match(/Cost[^:]*:\s*(\d+)/i);
    if (im) scoreI = im[1];
    if (cm) scoreC = cm[1];

    const el = document.createElement('div');
    el.className = `g-msg ${m.cls}`;
    el.style.animationDelay = `${i*50}ms`;
    el.innerHTML = `
      <div class="g-msg-avatar">${m.emoji}</div>
      <div style="flex:1;">
        <div class="g-msg-name">${t.speaker} · Round ${t.round||0}</div>
        <div class="g-msg-bubble">${esc(t.message)}</div>
      </div>`;
    win.appendChild(el);
  });

  win.scrollTop = win.scrollHeight;

  set('score-innovation', scoreI);
  set('score-cost',       scoreC);
  set('debate-round',     `Round ${maxRound}`);
  set('stat-turns',       transcript.length);
  set('stat-rounds',      maxRound);

  const hasConsensus = transcript.some(t => t.message.includes('Consensus'));
  set('stat-consensus', hasConsensus ? 'Yes' : 'No');
  set('debate-status',  hasConsensus ? '✅ Consensus reached' : `⚠ Max rounds reached`);

  const badge = document.getElementById('debate-badge');
  if (badge) badge.style.display = '';
}

// ================================================================
//  SOLUTION CARDS (analytics tab)
// ================================================================
function renderSolutions(solutions) {
  const row = document.getElementById('sol-cards-row');
  if (!row) return;

  const empty = document.getElementById('sol-empty');
  if (empty) empty.remove();

  const colours = { A:'var(--red)', B:'var(--white-3)', C:'var(--white-5)' };
  const icons   = { A:'💰', B:'⚡', C:'🌿' };
  const labels  = { A:'Low Cost', B:'High Performance', C:'Eco-Friendly' };

  solutions.forEach(sol => {
    const arch = sol.architecture || {};
    const biz  = sol.business     || {};
    const sc   = sol.scores       || {};
    const col  = colours[sol.id]  || 'var(--white-3)';
    const icon = icons[sol.id]    || '●';

    const scoreDefs = [
      { k:'cost',           l:'Cost',          c:'var(--red)' },
      { k:'feasibility',    l:'Feasibility',   c:'var(--white-3)' },
      { k:'sustainability', l:'Sustainability', c:'var(--white-3)' },
      { k:'scalability',    l:'Scalability',   c:'var(--white-4)' },
    ];

    const barsHtml = scoreDefs.map(d => `
      <div class="g-score-row">
        <span class="g-score-key">${d.l}</span>
        <div class="g-score-track"><div class="g-score-fill" style="width:${(sc[d.k]||0)*10}%;background:${d.c};"></div></div>
        <span class="g-score-num">${sc[d.k]||'—'}</span>
      </div>`).join('');

    const stackHtml = Object.entries(arch.tech_stack||{}).map(([k,v]) =>
      `<div style="display:flex;gap:8px;padding:4px 0;border-bottom:1px solid var(--border);font-size:11px;">
         <span style="color:var(--white-4);width:70px;flex-shrink:0;text-transform:uppercase;font-size:9px;font-weight:700;">${k}</span>
         <span>${esc(String(v))}</span>
       </div>`).join('');

    const apiHtml = (arch.api_endpoints||[]).slice(0,4).map(ep =>
      `<div style="display:flex;align-items:center;gap:6px;padding:3px 0;font-size:11px;">
         <span class="method-${(ep.method||'GET').toLowerCase()}" style="font-size:9px;font-weight:800;width:38px;flex-shrink:0;">${ep.method||'GET'}</span>
         <code style="font-size:10px;color:var(--white-3);flex:1;">${esc(ep.path||'')}</code>
       </div>`).join('');

    const div = document.createElement('div');
    div.className = 'col-12';
    div.innerHTML = `
      <div class="g-card sol-${sol.id.toLowerCase()}" style="border-left:2px solid ${col};">
        <div class="g-card-head">
          <span style="font-size:12px;font-weight:700;color:${col};">${icon} Solution ${sol.id} — ${labels[sol.id]||sol.label}</span>
          <button class="g-btn-ghost" onclick="toggleSolDetail('sd-${sol.id}',this)">Details ▾</button>
        </div>
        <div class="g-card-body">
          <p style="font-size:12px;color:var(--white-4);margin-bottom:12px;">${esc(arch.system_overview||'Fallback architecture — LLM returned no JSON.')}</p>
          ${barsHtml}
          <div id="sd-${sol.id}" style="display:none;margin-top:14px;">
            <div class="divider"></div>
            <div class="g-label mb-2">Tech Stack</div>
            <div class="mb-3">${stackHtml || '<span style="font-size:11px;color:var(--white-4);">Not available.</span>'}</div>
            <div class="g-label mb-2">API Endpoints</div>
            <div class="mb-3">${apiHtml || '<span style="font-size:11px;color:var(--white-4);">None specified.</span>'}</div>
            <div class="g-label mb-2">Security & Scalability</div>
            <p style="font-size:11px;color:var(--white-4);">🔒 ${esc(arch.security_notes||'—')}</p>
            <p style="font-size:11px;color:var(--white-4);">📈 ${esc(arch.scalability_notes||'—')}</p>
            <div class="g-label mb-2 mt-3">Financial Summary</div>
            <div style="font-size:11px;color:var(--white-4);">
              <span class="c-red" style="font-weight:700;">Budget:</span> ${esc(biz.budget_estimate||'—')} &nbsp;·&nbsp;
              <span style="font-weight:700;">ROI:</span> ${esc(biz.roi_timeline||'—')} &nbsp;·&nbsp;
              <span class="c-red" style="font-weight:700;">Risk:</span> ${esc(biz.risk_summary||'—')}
            </div>
          </div>
        </div>
      </div>`;
    row.appendChild(div);
  });

  const re = document.getElementById('radar-empty');
  if (re) re.style.display = 'none';
}

function toggleSolDetail(id, btn) {
  const el = document.getElementById(id);
  if (!el) return;
  const open = el.style.display !== 'none';
  el.style.display = open ? 'none' : '';
  btn.textContent  = open ? 'Details ▾' : 'Close ▴';
}

// ================================================================
//  RADAR CHART
// ================================================================
function renderRadar(data) {
  const canvas = document.getElementById('radar-chart');
  if (!canvas || !data?.datasets) return;

  if (STATE.chart) { STATE.chart.destroy(); STATE.chart = null; }

  const colours = ['#e53935','#e8e8e8','#666666'];

  STATE.chart = new Chart(canvas, {
    type: 'radar',
    data: {
      labels:   data.labels || ['Cost','Feasibility','Sustainability','Scalability'],
      datasets: data.datasets.map((ds,i) => ({
        ...ds,
        borderColor:          colours[i] || '#fff',
        backgroundColor:      (colours[i]||'#fff') + '18',
        pointBackgroundColor: colours[i] || '#fff',
        pointBorderColor:     '#0a0a0a',
        pointRadius:          4,
        borderWidth:          2,
        fill:                 true,
      })),
    },
    options: {
      responsive: true, maintainAspectRatio: true,
      animation:  { duration:800, easing:'easeInOutQuart' },
      scales: {
        r: {
          min:0, max:10,
          ticks:       { stepSize:2, backdropColor:'transparent', color:'#444', font:{size:9} },
          pointLabels: { color:'#e8e8e8', font:{size:11, weight:'600'} },
          grid:        { color:'#222' },
          angleLines:  { color:'#222' },
        },
      },
      plugins: {
        legend: { position:'bottom', labels:{ color:'#b0b0b0', font:{size:10}, padding:14, boxWidth:10 } },
        tooltip: { backgroundColor:'#1a1a1a', borderColor:'#2e2e2e', borderWidth:1, titleColor:'#e8e8e8', bodyColor:'#666' },
      },
    },
  });
}

// ================================================================
//  RAG CONTEXT
// ================================================================
function renderRAGContext(ctx) {
  const panel = document.getElementById('rag-context-panel');
  const count = document.getElementById('rag-passage-count');
  if (!panel) return;

  if (!ctx || ctx.length === 0) {
    panel.innerHTML = `<div class="g-empty"><div class="g-empty-icon">🔍</div><div class="g-empty-text">No documents in knowledge base.</div></div>`;
    return;
  }

  panel.innerHTML = ctx.map(item => `
    <div class="g-rag-item">
      <div class="g-rag-source">📄 ${esc(item.source||'Document')} · ${item.score||'—'}</div>
      <div style="font-size:11px;color:var(--white-4);">${esc((item.text||'').slice(0,280))}…</div>
    </div>`).join('');

  if (count) count.textContent = `${ctx.length} passages`;
}

function updateExportInfo(id, title) {
  const el = document.getElementById('export-project-info');
  if (el) el.textContent = `Project #${id} · ${title}`;
}

// ================================================================
//  WHAT-IF
// ================================================================
function recalcWhatIf() {
  const budget   = parseInt(document.getElementById('sl-budget')?.value    || 0);
  const team     = parseInt(document.getElementById('sl-team')?.value      || 5);
  const timeline = parseInt(document.getElementById('sl-timeline')?.value  || 18);

  set('lbl-budget',   `Cut ${budget}%`);
  set('lbl-team',     `${team}× Team`);
  set('lbl-timeline', `${timeline} months`);

  const adjBudget = Math.round(STATE.baseBudget * (1 - budget/100));
  const budgetFmt = adjBudget >= 1000000 ? `$${(adjBudget/1e6).toFixed(1)}M` : `$${Math.round(adjBudget/1000)}k`;
  const eng       = Math.max(1, Math.round(team * 2));
  const roi       = Math.round(timeline * (1 + budget/200) / Math.sqrt(team));
  const feasNum   = Math.max(1, Math.min(10, 7 - budget/20 + team/5 - Math.max(0,18-timeline)/10));
  const riskScore = budget/10 + (timeline < 12 ? 3 : 0) - team/5;
  const risk      = riskScore > 4 ? 'High' : riskScore > 2 ? 'Med' : 'Low';
  const velocity  = (team/5 * (1 - budget/150)).toFixed(1) + '×';

  set('wi-budget',     budgetFmt);
  set('wi-team',       `${eng} Eng`);
  set('wi-roi',        `${roi}mo`);
  set('wi-feasibility',`${feasNum.toFixed(1)}/10`);
  set('wi-risk',       risk);
  set('wi-velocity',   velocity);
}

// ================================================================
//  FILE UPLOAD (RAG)
// ================================================================
function handleDragOver(e) {
  e.preventDefault();
  document.getElementById('drop-zone')?.classList.add('over');
}
function handleDragLeave(e) {
  e.preventDefault();
  document.getElementById('drop-zone')?.classList.remove('over');
}
function handleDrop(e) {
  e.preventDefault();
  document.getElementById('drop-zone')?.classList.remove('over');
  Array.from(e.dataTransfer.files).filter(f => f.name.endsWith('.pdf')).forEach(uploadFile);
}
function handleFileSelect(e) {
  Array.from(e.target.files).forEach(uploadFile);
  e.target.value = '';
}

async function uploadFile(file) {
  const area  = document.getElementById('upload-area');
  const fname = document.getElementById('upload-fname');
  const pct   = document.getElementById('upload-pct');
  const bar   = document.getElementById('upload-bar');
  const docs  = document.getElementById('indexed-docs');
  const count = document.getElementById('kb-count');

  area.style.display = '';
  if (fname) fname.textContent = `Uploading ${file.name}…`;

  let p = 0;
  const tick = setInterval(() => {
    p = Math.min(p + 4 + Math.random()*7, 90);
    if (pct) pct.textContent  = `${Math.round(p)}%`;
    if (bar) bar.style.width  = `${Math.round(p)}%`;
  }, 180);

  const fd = new FormData();
  fd.append('file', file);

  try {
    const res  = await fetch('/api/upload_rag', { method:'POST', body:fd });
    clearInterval(tick);
    if (pct) pct.textContent = '100%';
    if (bar) bar.style.width = '100%';

    if (!res.ok) { const e=await res.json(); throw new Error(e.error||'Upload failed'); }

    const data = await res.json();
    toast(`✅ "${data.filename}" — ${data.chunks_added} chunks indexed.`, 'success');

    if (docs) {
      const item = document.createElement('div');
      item.className = 'g-rag-item';
      item.innerHTML = `<div class="g-rag-source">📄 ${esc(data.filename)}</div>
        <div style="font-size:11px;color:var(--white-4);">${data.chunks_added} chunks · Total: ${data.total_docs}</div>`;
      docs.appendChild(item);
    }
    if (count) count.textContent = `${data.total_docs} docs`;

  } catch(err) {
    clearInterval(tick);
    toast(`Upload error: ${err.message}`, 'error');
  } finally {
    setTimeout(() => {
      if (area) area.style.display = 'none';
      if (pct)  pct.textContent    = '0%';
      if (bar)  bar.style.width    = '0%';
    }, 1200);
  }
}

// ================================================================
//  RAG SEARCH
// ================================================================
async function runSearch() {
  const q   = document.getElementById('rag-query')?.value.trim();
  const res = document.getElementById('search-results');
  if (!q) { toast('Enter a search query.', 'error'); return; }
  if (res) res.innerHTML = '<div style="font-size:11px;color:var(--white-4);">Searching…</div>';
  try {
    const r    = await fetch('/api/orchestrate', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ problem_statement:q, project_title:'Search' }),
    });
    const data = await r.json();
    const ctx  = data.result?.rag_context || [];
    if (!ctx.length) { if (res) res.innerHTML = '<div style="font-size:11px;color:var(--white-4);">No results. Upload more documents.</div>'; return; }
    if (res) res.innerHTML = ctx.map(item => `
      <div class="g-rag-item">
        <div class="g-rag-source">📄 ${esc(item.source||'Doc')} · ${item.score}</div>
        <div style="font-size:11px;color:var(--white-4);">${esc((item.text||'').slice(0,360))}</div>
      </div>`).join('');
  } catch(err) {
    if (res) res.innerHTML = `<div style="font-size:11px;color:var(--red);">${esc(err.message)}</div>`;
  }
}

async function checkNovelty() {
  const claim = document.getElementById('patent-input')?.value.trim();
  const out   = document.getElementById('novelty-result');
  if (!claim) { toast('Paste a patent claim first.','error'); return; }
  if (out) out.innerHTML = '<div style="font-size:11px;color:var(--white-4);">Checking…</div>';
  try {
    const r    = await fetch('/api/orchestrate', { method:'POST', headers:{'Content-Type':'application/json'},
      body:JSON.stringify({ problem_statement:claim, project_title:'Novelty Check' }) });
    const data = await r.json();
    const ctx  = data.result?.rag_context || [];
    const maxS = ctx.length ? Math.max(...ctx.map(c=>c.score||0)) : 0;
    const novel = maxS < 0.5;
    if (out) out.innerHTML = `
      <div class="g-rag-item" style="border-left:2px solid ${novel?'#22c55e':'var(--red)'};">
        <div class="g-rag-source">${novel?'✅ Appears Novel':'⚠ Prior Art Detected'}</div>
        <div style="font-size:11px;color:var(--white-4);">Highest similarity: ${maxS.toFixed(3)} · Threshold: 0.50</div>
        <div style="font-size:11px;color:var(--white-4);margin-top:4px;">${novel?'No close matches found.':'Similar content detected — review recommended.'}</div>
      </div>`;
  } catch(err) {
    if (out) out.innerHTML = `<div style="color:var(--red);font-size:11px;">${esc(err.message)}</div>`;
  }
}

// ================================================================
//  EXPORT
// ================================================================
async function exportPDF() {
  if (!STATE.projectId) { toast('No project loaded. Deploy agents first.','error'); return; }
  toast('Generating PDF…','info');
  try {
    const r = await fetch('/api/export_pdf', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ project_id: STATE.projectId }),
    });
    if (!r.ok) { const e=await r.json(); throw new Error(e.error||'PDF failed'); }
    const blob = await r.blob();
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement('a');
    a.href = url; a.download = `Genesis_Report_${STATE.projectId}.pdf`;
    document.body.appendChild(a); a.click(); document.body.removeChild(a);
    URL.revokeObjectURL(url);
    toast('✅ PDF downloaded.','success');
  } catch(err) { toast(`PDF error: ${err.message}`,'error'); }
}

function exportJSON() {
  if (!STATE.result) { toast('No result to export.','error'); return; }
  const blob = new Blob([JSON.stringify(STATE.result,null,2)],{type:'application/json'});
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement('a');
  a.href = url; a.download = `Genesis_Result_${STATE.projectId||'latest'}.json`;
  document.body.appendChild(a); a.click(); document.body.removeChild(a);
  URL.revokeObjectURL(url);
  toast('✅ JSON exported.','success');
}

function copyShareLink() {
  if (!STATE.projectId) { toast('No project loaded.','error'); return; }
  navigator.clipboard.writeText(`${location.origin}/api/projects/${STATE.projectId}`)
    .then(()=>toast('Link copied!','success'))
    .catch(()=>toast('Copy failed.','error'));
}

// ================================================================
//  PROJECT HISTORY
// ================================================================
async function loadHistory() {
  const list = document.getElementById('history-list');
  if (!list) return;
  try {
    const r    = await fetch('/api/projects');
    const data = await r.json();
    const proj = data.projects || [];
    if (!proj.length) { list.innerHTML = '<div class="g-card-body" style="color:var(--white-4);font-size:12px;">No projects yet.</div>'; return; }
    list.innerHTML = proj.slice(0,8).map(p => `
      <div style="display:flex;align-items:center;gap:10px;padding:10px 16px;border-bottom:1px solid var(--border);">
        <div style="flex:1;min-width:0;">
          <div style="font-size:12px;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${esc(p.title)}</div>
          <div style="font-size:10px;color:var(--white-4);">#${p.id} · ${new Date(p.created_at).toLocaleDateString()}</div>
        </div>
        <button onclick="reloadProject(${p.id})" class="g-btn-ghost" style="flex-shrink:0;font-size:10px;">Load</button>
      </div>`).join('');
  } catch(err) {
    list.innerHTML = `<div class="g-card-body" style="color:var(--red);font-size:12px;">Load failed.</div>`;
  }
}

async function reloadProject(id) {
  try {
    const r = await fetch(`/api/projects/${id}`);
    const p = await r.json();
    if (!p.result_json) { toast('No result saved for this project.','error'); return; }
    const result = JSON.parse(p.result_json);
    STATE.projectId  = id; STATE.result = result;
    STATE.transcript = result.debate_transcript||[];
    renderDebate(STATE.transcript);
    renderSolutions(result.solutions||[]);
    renderRadar(result.scores);
    renderRAGContext(result.rag_context||[]);
    updateExportInfo(id, p.title);
    recalcWhatIf();
    toast(`Project #${id} loaded.`,'success');
  } catch(err) { toast(`Load error: ${err.message}`,'error'); }
}

// ================================================================
//  STATUS BAR
// ================================================================
function setStatus(label, state) {
  const lbl = document.getElementById('status-label');
  const dot = document.getElementById('status-dot');
  if (lbl) lbl.textContent = label;
  if (dot) {
    dot.classList.remove('live','error');
    if (state === 'live')   dot.classList.add('live');
    if (state === 'error')  dot.classList.add('error');
  }
}

// ================================================================
//  TOAST
// ================================================================
function toast(msg, type='info', ms=4200) {
  const c = document.getElementById('toasts');
  if (!c) return;
  const icons = { success:'✅', error:'❌', info:'○' };
  const el = document.createElement('div');
  el.className = `g-toast ${type}`;
  el.innerHTML = `<span>${icons[type]||'○'}</span><span>${esc(msg)}</span>`;
  c.appendChild(el);
  setTimeout(() => {
    el.style.opacity = '0'; el.style.transition = 'opacity 0.25s';
    setTimeout(() => el.remove(), 280);
  }, ms);
}

// ================================================================
//  UTILITIES
// ================================================================
function set(id, val) { const el=document.getElementById(id); if(el) el.textContent=String(val); }

function esc(str) {
  return String(str||'')
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
    .replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}
