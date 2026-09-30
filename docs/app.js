'use strict';

const CATALOG_URL = 'data/catalog.json';

// ─── Live gallery: which replays, in which groups, and what each one shows ────
// Explanations are written from the trees, the replay traces and the results rows.

const GALLERY = [
  {
    title: 'Where rootstocks change the outcome (𝒞 vs 𝒞∖ℛ)',
    open: true,
    desc: 'The same prompt under both contract methods. Under 𝒞∖ℛ, most failures come from tree structure the agent writes itself: an extra guard, an open or close in the wrong place, or a step that was never asked for.',
    pairs: [
      {
        prompt: 'Search pantry, then fridge for bread. If found, place it on table_tabletop.',
        meta: 'Sonnet 5 · Core60 · task 31 · search-and-place',
        keys: ['core60_sonnet_mcore_task31', 'core60_sonnet_b1_task31'],
      },
      {
        prompt: 'Pick bread from pantry and place it at fridge.',
        meta: 'Gemma4:31b · Core60 · task 25 · pick-and-place',
        keys: ['core60_gemma_mcore_task25', 'core60_gemma_b1_task25'],
      },
      {
        prompt: 'Return to dining while holding snacks, but only after you have first checked table_tabletop and then pantry, found them, and picked them up.',
        meta: 'Sonnet 5 · Lang50 · task 47 · clause reordering',
        keys: ['lang50_sonnet_mcore_lang47', 'lang50_sonnet_b1_lang47'],
      },
    ],
  },
  {
    title: 'Hard15: beyond the patterns rootstocks encode',
    desc: 'Structurally deeper tasks that no rootstock was written for. Each method has a characteristic failure here.',
    pairs: [
      {
        prompt: 'Search the pantry then the fridge for bread; deliver it to the table_tabletop, then return to the kitchen.',
        meta: 'Sonnet 5 · Hard15 · hard11 · the tree in the paper’s Fig. 2',
        keys: ['hard15_sonnet_mcore_hard11', 'hard15_sonnet_obtea_hard11'],
      },
    ],
    singles: ['hard15_sonnet_mcore_hard08', 'hard15_sonnet_obtea_hard07'],
  },
  {
    title: 'Prior30: dependence on a symbolic world model',
    desc: 'The world is the same in every task; only the prior given to LLM-OBTEA changes. The contract methods get no prior and search at execution time.',
    pairs: [
      {
        prompt: 'Look for the butter in the pantry and the fridge, then put it on the table.',
        meta: 'Sonnet 5 · Prior30 · i03 · incomplete prior',
        keys: ['prior30_sonnet_mcore_i03', 'prior30_sonnet_obtea_i03'],
      },
    ],
    singles: ['prior30_sonnet_mcore_s04', 'core60_sonnet_obtea_task31'],
  },
];

const WHY = {
  core60_sonnet_mcore_task31:
    'A two-branch selector search. The pantry branch detects the bread, so the fridge branch is never ticked; the tree then goes to the table and places the bread.',
  core60_sonnet_b1_task31:
    'Nearly the same tree, with one extra node per branch: the guard <code>detected_objects contains bread</code>. <code>detect</code> writes instance names (<code>bread0</code>) to that key, so the guard fails even though the bread was found. The selector abandons the pantry, searches the fridge, and <code>detect</code> fails there. The difference between two almost identical trees is a single condition node. Gemma’s 𝒞∖ℛ tree for Core60 task 41 fails the same way.',
  core60_gemma_mcore_task25:
    'A plain sequence: go to the pantry, open it, detect, pick, go to the fridge, place.',
  core60_gemma_b1_task25:
    'The tree picks the bread, then tries to <code>open</code> the fridge while holding it. The skill schema says open and close need an empty gripper on this single-arm robot, and the fridge was already open. <code>open_fridge</code> fails and the run ends. Rootstocks order these steps structurally; 𝒞’s Runtime Failures are 0.2% (Sonnet) and 1.2% (Gemma) of task-runs, against 21.4% and 24.2% under 𝒞∖ℛ.',
  lang50_sonnet_mcore_lang47:
    'Reordered clauses, same structure: search the table, then the pantry, pick the snacks, and go to dining holding them.',
  lang50_sonnet_b1_lang47:
    'The search succeeds, but the tree ends with a <code>place</code> the prompt never asked for. <code>place</code> needs an object spawn to put the snacks on, and the robot is standing in the dining room, not at one, so it fails. The robot is in dining holding the snacks, so the goal holds, but the tree returned <code>FAILURE</code>, so the run is scored a failure.',
  hard15_sonnet_mcore_hard11:
    'The tree drawn in the paper’s Fig. 2: a search-then-deliver rootstock, extended with the return to the kitchen. It succeeds in 10 of 10 runs.',
  hard15_sonnet_obtea_hard11:
    'Stage 1 parsed the goal as <code>Holding(bread) ∧ On(bread,table) ∧ RobotNear(kitchen)</code>. A conjunction of literals cannot say “first … then”, so the goal asks to hold the bread and have it on the table at once. The compiled tree fails its first tick. LLM-OBTEA solves this task in 0 of 10 runs, with a correct prior.',
  hard15_sonnet_mcore_hard08:
    '<em>“Take the soda from the fridge to the table_tabletop, and leave the fridge as you found it.”</em> The fridge starts open. The tree returns and closes it, as the open/close bracketing of the retrieve-and-restore rootstock suggests, so the goal (fridge open) fails. This one task accounts for 20 of 𝒞’s 25 Hard15 goal mismatches across both models.',
  hard15_sonnet_obtea_hard07:
    '<em>“Open the fridge, take the butter to the desk_desktop, then go back and close the fridge.”</em> Stage 1 parsed <code>On(butter,desk) ∧ RobotNear(fridge)</code>: the goal language has no literal for a closed container. The tree delivers the butter and returns to the fridge, the tree succeeds, and the fridge is still open.',
  prior30_sonnet_mcore_i03:
    'No prior: the tree searches the pantry, then the fridge, finds the butter and puts it on the table.',
  prior30_sonnet_obtea_i03:
    'The incomplete prior omits the butter, so no action can establish where it is. The planner expands to a 686-node tree, whose only applicable rule navigates to <code>butter</code>, an object rather than a place. It retries until the 30 s budget runs out. Every incomplete-prior tree, for both models and in all ten runs, runs out its budget.',
  prior30_sonnet_mcore_s04:
    'Stale prior family: the prior LLM-OBTEA receives puts the bread on the desk. 𝒞 never sees a prior. It searches the pantry, finds the bread and delivers it. LLM-OBTEA’s tree for this task goes to the desk and fails in all 10 runs; its tree is in the explorer.',
  core60_sonnet_obtea_task31:
    'LLM-OBTEA with a correct prior: a priority list of rules, each guarded by the conditions that make it applicable, ticked in policy mode. Every tick re-evaluates from the goal condition down, which is why the upper rules flash on each tick. Its condition-to-fallback ratio on Core60 is 10, against 0 for 𝒞.',
};

// ─── State ────────────────────────────────────────────────────────────────────

const state = {
  catalog: null,
  cache: {},
  env: 'pyrobosim',
  model: 'sonnet',
  method: 'mcore',
  suite: 'core60',
  taskId: null,
  filter: 'all',
  search: '',
  zoom: false,
};

const $ = (id) => document.getElementById(id);

function esc(v) {
  return String(v ?? '').replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;').replaceAll("'", '&#39;');
}
function badge(label, tone = '', title = '') {
  return `<span class="badge${tone ? ' badge--' + tone : ''}"${title ? ` title="${esc(title)}"` : ''}>${esc(label)}</span>`;
}
function pct(x) { return `${x.toFixed(1)}%`; }
function methodInfo(id) { return state.catalog.methods.find((m) => m.id === id); }
function modelLabel(id) { return state.catalog.models.find((m) => m.id === id)?.label ?? id; }
function suiteLabel(id) { return state.catalog.suites[id]?.label ?? id; }

async function loadBatch(name) {
  if (!state.cache[name]) {
    const b = state.catalog.batches.find((x) => x.name === name);
    const res = await fetch(`data/${b.file}`);
    if (!res.ok) throw new Error(`HTTP ${res.status} for ${b.file}`);
    state.cache[name] = await res.json();
  }
  return state.cache[name];
}

// ─── MCP tools ────────────────────────────────────────────────────────────────

function renderMcpTools() {
  $('mcpTools').innerHTML = state.catalog.mcp_tools.map((t) => `
    <div class="mcp-tool-card">
      <div class="mcp-tool-card__head">
        <code class="mcp-tool-card__name">${esc(t.served)}()</code>
        <span class="mcp-tool-card__arrow">&rarr;</span>
        <span class="mcp-tool-card__return">${esc(t.returns)}</span>
        ${t.full_only ? '<span class="badge" title="Not served under 𝒞∖ℛ">𝒞 only</span>' : ''}
      </div>
      ${t.paper !== t.served ? `<div class="mcp-tool-card__alias">in the paper: <code>${esc(t.paper)}</code></div>` : ''}
      <p class="mcp-tool-card__desc">${esc(t.desc)}</p>
    </div>`).join('');
}

// ─── Contract ─────────────────────────────────────────────────────────────────

function block(name, count, body, open = false) {
  return `<details class="contract-block"${open ? ' open' : ''}>
    <summary class="contract-block__head"><span class="contract-block__name">${esc(name)}</span>
    <span class="contract-count">${esc(count)}</span></summary>${body}</details>`;
}

function paramList(params) {
  if (!params.length) return '<span class="muted-note">none</span>';
  return params.map((p) => `<code>${esc(p.name)}: ${esc(p.type ?? 'any')}</code>`).join(' ');
}

function vocabBlock(vocab, labels) {
  return `<div class="vocab">${Object.entries(labels).filter(([k]) => vocab[k]).map(([k, label]) => `
    <div class="vocab__row"><div class="vocab__label">${esc(label)}</div>
    <div class="vocab__chips">${vocab[k].map((v) => `<code class="chip">${esc(v)}</code>`).join('')}</div></div>`).join('')}</div>`;
}

function rootstockCard(r, extra = '') {
  return `<div class="contract-rootstock">
    <div class="contract-rootstock__head">
      <span class="contract-rootstock__name">${esc(r.name)}</span>
      <span class="contract-rootstock__desc">${esc(r.description)}</span>
    </div>
    ${r.svg ? `<div class="contract-rootstock__svg">${r.svg}</div>` : ''}
    ${extra}
  </div>`;
}

// Documentation for the skills and operators each contract names.
const PYROBOSIM_ACTIONS = 'https://pyrobosim.readthedocs.io/en/latest/usage/robot_actions.html';
const PYTREES_DOCS = {
  sequence: 'https://py-trees.readthedocs.io/en/devel/composites.html#sequence',
  selector: 'https://py-trees.readthedocs.io/en/devel/composites.html#selector',
  parallel: 'https://py-trees.readthedocs.io/en/devel/composites.html#parallel',
  inverter: 'https://py-trees.readthedocs.io/en/devel/decorators.html#py_trees.decorators.Inverter',
  retry: 'https://py-trees.readthedocs.io/en/devel/decorators.html#py_trees.decorators.Retry',
};
const BTCPP = 'https://behaviortree.github.io/BehaviorTree.CPP/';
const BTCPP_DOCS = {
  Sequence: 'd9/ddd/class_b_t_1_1_sequence_node.html',
  SequenceWithMemory: 'de/d69/class_b_t_1_1_sequence_with_memory.html',
  Fallback: 'dc/da6/class_b_t_1_1_fallback_node.html',
  Parallel: 'd1/dee/class_b_t_1_1_parallel_node.html',
  ReactiveSequence: 'de/d9f/class_b_t_1_1_reactive_sequence.html',
  ReactiveFallback: 'dc/d04/class_b_t_1_1_reactive_fallback.html',
  KeepRunningUntilFailure: 'de/d22/class_b_t_1_1_keep_running_until_failure_node.html',
  Repeat: 'd6/d78/class_b_t_1_1_repeat_node.html',
  RetryUntilSuccessful: 'dd/de4/class_b_t_1_1_retry_node.html',
  Inverter: 'd2/ded/class_b_t_1_1_inverter_node.html',
  ForceSuccess: 'd7/db8/class_b_t_1_1_force_success_node.html',
  ForceFailure: 'd4/d8c/class_b_t_1_1_force_failure_node.html',
  RunOnce: 'dd/dbd/class_b_t_1_1_run_once_node.html',
  AlwaysSuccess: 'dd/dce/class_b_t_1_1_always_success_node.html',
};

function docCode(name, url) {
  const code = `<code>${esc(name)}</code>`;
  return url ? `<a class="doc-link" href="${esc(url)}" target="_blank" rel="noopener">${code}</a>` : code;
}

function renderContract() {
  const sim = state.catalog.contract.sim;
  const hw = state.catalog.contract.hw;
  const skills = `<div class="contract-table-wrap"><table class="contract-table">
    <thead><tr><th>Skill</th><th>Parameters</th><th>Description</th></tr></thead><tbody>
    ${sim.skills.map((s) => `<tr><td>${docCode(s.name, PYROBOSIM_ACTIONS)}</td><td>${paramList(s.params)}</td>
      <td>${esc(s.description)}<details class="outputs"><summary>Blackboard outputs (${s.outputs.length})</summary>${s.outputs.map((o) => `<code>${esc(o)}</code>`).join(' ')}</details></td></tr>`).join('')}
    </tbody></table></div>`;
  const f = sim.format;
  const format = `<div class="contract-table-wrap"><table class="contract-table">
    <thead><tr><th>Element</th><th>Allowed</th></tr></thead><tbody>
      <tr><td>Node types</td><td>${f.node_types.map((n) => docCode(n, PYTREES_DOCS[n])).join(' ')}</td></tr>
      <tr><td>Composites</td><td>${docCode('sequence', PYTREES_DOCS.sequence)}, ${docCode('selector', PYTREES_DOCS.selector)}: <code>children</code>, <code>memory</code>. ${docCode('parallel', PYTREES_DOCS.parallel)}: <code>children</code>, <code>policy</code> (<code>success_on_all</code> | <code>success_on_one</code>)</td></tr>
      <tr><td>Decorators</td><td>${f.decorators.map((n) => docCode(n, PYTREES_DOCS[n])).join(' ')} (one <code>child</code>; <code>retry</code> takes <code>num_failures</code>)</td></tr>
      <tr><td>Conditions</td><td><code>key</code> <em>operator</em> <code>value</code> on the blackboard, with operators ${f.condition_operators.map((n) => `<code>${esc(n)}</code>`).join(' ')}</td></tr>
      <tr><td>Blackboard</td><td>optional <code>blackboard.initial</code>; action <code>outputs</code> map results to keys</td></tr>
    </tbody></table></div>
    <ul class="format-notes">${f.notes.map((n) => `<li>${esc(n)}</li>`).join('')}</ul>`;
  const rootstocks = `<div class="rootstock-cards">${sim.rootstocks.map((r) => rootstockCard(r, `
      <dl class="rootstock-meta">
        <dt>When to use</dt><dd>${esc(r.when_to_use)}</dd>
        <dt>Slots</dt><dd>${Object.entries(r.slots).map(([k, v]) => `<code>${esc(k)}</code>: ${esc(v)}`).join('<br>')}</dd>
        <dt>Anti-pattern</dt><dd>${esc(r.anti_pattern)}</dd>
      </dl>`)).join('')}</div>`;
  const vocab = vocabBlock(sim.vocabulary, {
    rooms: 'Rooms', locations: 'Locations', object_spawns: 'Object spawns', object_categories: 'Object categories',
    objects: 'Objects', hallways: 'Hallways',
  }) + '<p class="table-note">Names only. The agent is never told where an object is; it must find out at execution time with <code>detect</code>.</p>';

  $('contract-sim').innerHTML =
    block('Skill Library', `${sim.skills.length} skills · list_skills`, skills, true) +
    block('BT Format and Operators', `get_bt_format`, format) +
    block('Rootstock Templates', `${sim.rootstocks.length} rootstocks · list_rootstocks_tool`, rootstocks) +
    block('World Vocabulary', `list_world_entities`, vocab);

  const hwSkills = `<div class="contract-table-wrap"><table class="contract-table">
    <thead><tr><th>Skill</th><th>Parameters</th><th>Description</th></tr></thead><tbody>
    ${hw.skills.map((s) => `<tr><td><code>${esc(s.name)}</code></td><td>${paramList(s.params)}</td><td>${esc(s.description)}</td></tr>`).join('')}
    </tbody></table></div>`;
  const hwOps = `<div class="contract-table-wrap"><table class="contract-table">
    <thead><tr><th>Node</th><th>Description</th></tr></thead><tbody>
    ${hw.operators.map((o) => `<tr><td>${docCode(o.name, BTCPP_DOCS[o.name] && BTCPP + BTCPP_DOCS[o.name])}</td><td>${esc(o.description)}</td></tr>`).join('')}
    </tbody></table></div>`;
  const hwRs = `<div class="rootstock-cards">${hw.rootstocks.map((r) => rootstockCard(r,
    `<details class="raw-block"><summary>Template text as served</summary><pre class="pre-code">${esc(r.prose)}</pre></details>`)).join('')}</div>`;
  const hwVocab = vocabBlock(hw.vocabulary, { locations: 'Locations', detection_classes: 'Detection classes' }) +
    '<p class="table-note">Location names containing the lab’s name are shown as <code>[lab]</code> for double-blind review.</p>';
  $('contract-hw').innerHTML =
    block('Skill Library', `${hw.skills.length} skills · list_skills`, hwSkills, true) +
    block('BT.CPP Operators', `${hw.operators.length} node types · get_bt_format`, hwOps) +
    block('Rootstock Templates', `${hw.rootstocks.length} rootstocks · list_rootstocks_tool`, hwRs) +
    block('World Vocabulary', 'list_world_entities', hwVocab);
}

document.querySelectorAll('.contract-tabs').forEach((bar) => {
  bar.addEventListener('click', (e) => {
    const tab = e.target.closest('.contract-tab');
    if (!tab) return;
    bar.querySelectorAll('.contract-tab').forEach((t) => {
      t.classList.toggle('is-active', t === tab);
      t.setAttribute('aria-selected', t === tab ? 'true' : 'false');
    });
    bar.closest('section').querySelectorAll('.contract-pane').forEach((p) => { p.hidden = p.id !== tab.dataset.target; });
  });
});

// ─── Paper tables ─────────────────────────────────────────────────────────────

function toneCell(c) {
  return `<td class="${c.tone ? 'tone-' + c.tone : ''}">${esc(c.text)}</td>`;
}

function renderTables() {
  const t = state.catalog.tables;
  const head = `<thead>
    <tr><th rowspan="2"></th><th colspan="3">Sonnet 5</th><th colspan="3" class="group-start">Gemma4:31b</th></tr>
    <tr><th>LLM-OBTEA</th><th>𝒞∖ℛ</th><th class="col-full">𝒞</th><th class="group-start">LLM-OBTEA</th><th>𝒞∖ℛ</th><th class="col-full">𝒞</th></tr></thead>`;
  const body = t.table1.map((sec) => `
    <tr class="section-row"><td colspan="7"><strong>${esc(sec.suite)}</strong> <span class="muted-note">${esc(sec.note)}</span></td></tr>
    ${sec.rows.map((r) => `<tr class="${r.level ? 'sub-row' : 'main-row'}"><td>${esc(r.label)}</td>
      ${r.cells.map((c, i) => toneCell(c).replace('<td class="', `<td class="${i === 3 ? 'group-start ' : ''}${i === 2 || i === 5 ? 'col-full ' : ''}`)).join('')}</tr>`).join('')}`).join('');
  $('table1').innerHTML = `<div class="table-tools"><button type="button" class="link-button" id="toggleSubRows" aria-pressed="false">Hide the archetype and variation rows</button></div>
    <table class="results-table results-table--paper" id="table1Grid">${head}<tbody>${body}</tbody></table>`;
  $('toggleSubRows').addEventListener('click', (e) => {
    const hide = $('table1Grid').classList.toggle('hide-sub');
    e.target.setAttribute('aria-pressed', String(hide));
    e.target.textContent = hide ? 'Show the archetype and variation rows' : 'Hide the archetype and variation rows';
  });

  $('table2').innerHTML = `<table class="results-table results-table--paper">
    <thead><tr><th>Model</th><th>Method</th><th>Never valid</th><th>Runtime failure</th><th>Goal mismatch</th><th>Failure rate</th></tr></thead>
    <tbody>${t.table2.map((r, i) => `<tr class="${i === 3 ? 'row-sep' : ''}"><td>${esc(r.model)}</td><td>${esc(r.method)}</td>
      <td>${esc(r.never_valid)}</td><td>${esc(r.runtime)}</td><td>${esc(r.goal_mismatch)}</td><td><strong>${esc(r.failure_rate)}</strong></td></tr>`).join('')}</tbody></table>`;

  $('table3').innerHTML = `<table class="results-table results-table--paper">
    <thead><tr><th rowspan="2">Prior</th><th rowspan="2">Method</th><th colspan="2">Sonnet 5</th><th colspan="2" class="group-start">Gemma4:31b</th></tr>
    <tr><th>Success (%)</th><th>Nodes</th><th class="group-start">Success (%)</th><th>Nodes</th></tr></thead>
    <tbody>${t.table3.map((r, i) => `<tr class="${i % 2 === 0 && i ? 'row-sep' : ''}"><td>${i % 2 === 0 ? esc(r.prior) : ''}</td><td>${esc(r.method)}</td>
      ${toneCell(r.sonnet)}<td>${esc(r.sonnet_nodes)}</td>${toneCell(r.gemma).replace('<td class="', '<td class="group-start ')}<td>${esc(r.gemma_nodes)}</td></tr>`).join('')}</tbody></table>`;

  $('tableHw').innerHTML = `<table class="results-table results-table--paper">
    <thead><tr><th rowspan="2">Method</th><th rowspan="2">Model</th><th colspan="2">Nav (3)</th><th colspan="2">React (4)</th><th colspan="2">Track (3)</th><th colspan="2">Multi (4)</th></tr>
    <tr>${'<th>V</th><th>S</th>'.repeat(4)}</tr></thead>
    <tbody>${t.hardware.map((r, i) => `<tr class="${i === 2 ? 'row-sep' : ''}"><td>${i % 2 === 0 ? esc(r.method) : ''}</td><td>${esc(r.model)}</td>
      ${r.cells.map((c) => `<td>${esc(c)}</td>`).join('')}</tr>`).join('')}</tbody></table>`;
}

// ─── OOC10 ────────────────────────────────────────────────────────────────────

// label -> [symbol, tone, words]; this is also the order chips appear in a cell
const OOC_LABELS = {
  refused: ['✓', 'good', 'refused'],
  rejected: ['✓', 'good', 'no goal'],
  approximated: ['~', 'warn', 'approximated'],
  hallucinated: ['×', 'bad', 'hallucinated'],
  invalid: ['!', 'bad', 'invalid'],
  planner_fail: ['p', 'bad', 'planner failure'],
  chat: ['c', 'chat', 'chat'],
  clarify: ['?', 'chat', 'asked a question'],
  other: ['o', 'chat', 'other'],
  timeout: ['t', 'chat', 'timeout'],
};

function oocChips(counts) {
  return Object.keys(OOC_LABELS).filter((k) => counts?.[k]).map((k) => {
    const [sym, tone, words] = OOC_LABELS[k];
    return `<span class="ooc-chip ooc-chip--${tone}" title="${esc(words)}: ${counts[k]} of 10 runs">${sym}${counts[k]}</span>`;
  }).join('');
}

function oocRate(r) {
  return r ? `${r.mean.toFixed(0)} ± ${r.sd.toFixed(0)}%` : '';
}

function renderOoc() {
  const o = state.catalog.ooc10;
  const cells = o.cells;
  const groupStart = (i) => (i % 2 === 0 ? ' ooc-group' : '');

  $('oocBody').innerHTML = o.tasks.map((t, i) => `<tr>
    <td class="ooc-num">${i + 1}</td>
    <td class="ooc-prompt"><em>“${esc(t.prompt)}”</em></td>
    ${cells.map((c, j) => (c.pending
      ? `<td class="ooc-cell ooc-cell--pending${groupStart(j)}">pending</td>`
      : `<td class="ooc-cell${groupStart(j)}">${oocChips(c.per_task[t.id])}</td>`)).join('')}</tr>`).join('');

  const rateRow = (label, key) => `<tr><td></td><td class="ooc-total-label">${label}</td>
    ${cells.map((c, j) => `<td class="ooc-total${groupStart(j)}">${c.pending ? '–' : oocRate(c[key])}</td>`).join('')}</tr>`;
  $('oocFoot').innerHTML = cells.length
    ? rateRow('Declined, all 10 prompts', 'rate') + rateRow('Declined, without prompt 8', 'rate_wo08')
    : '';

  const pending = cells.filter((c) => c.pending);
  if (pending.length) {
    const names = pending.map((c) => `${modelLabel(c.model)} ${c.method === 'obtea' ? 'LLM-OBTEA' : '𝒞'}`);
    $('oocStatus').innerHTML = `<strong>In progress.</strong> ${esc(names.join(' and '))}: runs pending, shown here when complete. The other cells are final.`;
    $('oocStatus').hidden = false;
  }

  const runs = o.runs || [];
  $('oocRunPick').innerHTML = runs.map((r, i) => `<button type="button" class="ooc-run-btn" id="oocRun-${esc(r)}"
      data-run="${esc(r)}" aria-pressed="${i === 0}">Run ${i + 1}</button>`).join('');
  $('oocRunPick').onclick = (ev) => {
    const btn = ev.target.closest('.ooc-run-btn');
    if (!btn) return;
    $('oocRunPick').querySelectorAll('.ooc-run-btn').forEach((b) => b.setAttribute('aria-pressed', String(b === btn)));
    renderOocRun(btn.dataset.run);
  };
  if (runs.length) renderOocRun(runs[0]);
}

function oocSends(sends) {
  if (!sends.length) return '<p class="ooc-sends">Sent no tree.</p>';
  const items = sends.map((s, i) => {
    const what = s.valid ? 'accepted' : `rejected${s.issues.length ? ` (${[...new Set(s.issues)].join(', ')})` : ''}`;
    const missed = s.missed.length ? `; the offline contract check flagged ${[...new Set(s.missed)].join(', ')}` : '';
    return `<li><span class="ooc-sends__mark ooc-sends__mark--${s.valid ? (s.missed.length ? 'bad' : 'warn') : 'bad'}">${s.valid ? '✓' : '✗'}</span>
      Tree ${i + 1} ${esc(what)}${esc(missed)}</li>`;
  }).join('');
  return `<ul class="ooc-sends">${items}</ul>`;
}

function oocAttempts(attempts) {
  return `<ol class="ooc-attempts">${attempts.map((a) => `<li><code>${esc(a.reply || '(empty reply)')}</code>
      ${a.error ? `<span class="ooc-attempts__err">rejected: ${esc(a.error)}</span>` : '<span class="ooc-attempts__ok">parsed</span>'}</li>`).join('')}</ol>`;
}

function renderOocRun(run) {
  const o = state.catalog.ooc10;
  const n = o.runs.indexOf(run) + 1;
  const cellName = (c) => `${c.method === 'obtea' ? 'LLM-OBTEA' : '𝒞'} · ${modelLabel(c.model)}`;
  $('oocExamples').innerHTML = o.tasks.map((t, i) => {
    const ex = o.examples[t.id] || {};
    const parts = o.cells.filter((c) => !c.pending && ex[c.cell]?.[run]).map((c) => {
      const e = ex[c.cell][run];
      const [sym, tone, words] = OOC_LABELS[e.label] || ['', 'chat', e.label];
      const head = `<div class="ooc-ex__who">${esc(cellName(c))}
          <span class="ooc-chip ooc-chip--${tone}">${sym} ${esc(words)}</span></div>`;
      if (c.method === 'obtea') {
        const goal = e.goal ? `Goal <code>${esc(e.goal)}</code>` : `No goal after ${e.attempts.length} attempt${e.attempts.length === 1 ? '' : 's'}`;
        return `<div class="ooc-ex">${head}<p class="ooc-goal">${goal}</p>${oocAttempts(e.attempts)}</div>`;
      }
      return `<div class="ooc-ex">${head}<blockquote class="ooc-reply">${esc(e.text)}</blockquote>${oocSends(e.sends)}</div>`;
    }).join('');
    return `<article class="ooc-example">
      <h4><span class="ooc-example__num">${i + 1}</span> “${esc(t.prompt)}”</h4>
      ${t.reason ? `<p class="ooc-reason">Out of contract: ${esc(t.reason)}.</p>` : ''}
      <div class="ooc-ex-grid">${parts}</div></article>`;
  }).join('');
  $('oocExamples').setAttribute('aria-label', `Run ${n}`);
}

// ─── Live player ──────────────────────────────────────────────────────────────

const STATUS_WORD = { R: 'running', S: 'succeeded', F: 'failed' };

class LivePlayer {
  constructor(el, key) {
    this.el = el;
    this.key = key;
    this.h = state.catalog.highlights[key];
    this.trace = null;
    this.last = null;
    this.render();
  }

  render() {
    const h = this.h;
    const ok = h.recorded.success;
    this.el.innerHTML = `
      <div class="live-media">
        <video muted playsinline loop preload="none" poster="${esc(h.video.replace('.mp4', '.jpg'))}"
          aria-label="PyRoboSim replay: ${esc(h.prompt)}"></video>
        <div class="live-controls">
          <button type="button" class="live-play" aria-label="Play">▶</button>
          <input type="range" class="live-scrub" min="0" max="1000" value="0" aria-label="Replay position">
          <select class="live-speed" aria-label="Playback speed">
            <option value="0.25">0.25×</option><option value="0.5" selected>0.5×</option><option value="1">1×</option>
          </select>
        </div>
        <div class="live-status" aria-live="off"><span class="live-clock">—</span><span class="live-active">Press play.</span></div>
      </div>
      <div class="live-tree-col">
        ${h.svg ? '<div class="live-tree__bar"><button type="button" class="link-button live-fit">Fit whole tree</button></div>' : ''}
        <div class="live-tree bt-live">${h.svg ?? `<div class="bt-tree-empty">This ${h.nodes}-node tree is too large to draw here; below is its running branch, root first. The full tree is in the <a href="#explorer" data-open="${esc(h.cell)}|${esc(h.task_id)}">explorer</a>.</div><ol class="live-branch"></ol>`}</div>
      </div>`;
    this.branch = this.el.querySelector('.live-branch');
    this.treeBox = this.el.querySelector('.live-tree');
    this.svg = this.el.querySelector('.live-tree svg');
    this.fitButton = this.el.querySelector('.live-fit');
    if (this.svg) {
      requestAnimationFrame(() => this.autoFit());
      this.el.closest('details')?.addEventListener('toggle', () => this.autoFit());
      this.fitButton.addEventListener('click', () => { this.userFit = true; this.setFit(!this.fit); });
    }
    this.video = this.el.querySelector('video');
    this.play = this.el.querySelector('.live-play');
    this.scrub = this.el.querySelector('.live-scrub');
    this.clock = this.el.querySelector('.live-clock');
    this.active = this.el.querySelector('.live-active');
    this.nodes = [...this.el.querySelectorAll('.live-tree g.bt-node')];
    this.edges = new Map([...this.el.querySelectorAll('.live-tree line[data-to]')].map((l) => [Number(l.dataset.to), l]));
    this.play.addEventListener('click', () => this.toggle());
    this.el.querySelector('.live-speed').addEventListener('change', (e) => { this.video.playbackRate = Number(e.target.value); });
    this.scrub.addEventListener('input', async () => {
      await this.ensure();
      this.video.pause();
      this.video.currentTime = (Number(this.scrub.value) / 1000) * (this.video.duration || 0);
      this.update();
    });
    this.video.addEventListener('play', () => { this.play.textContent = '❚❚'; this.play.setAttribute('aria-label', 'Pause'); this.loop(); });
    this.video.addEventListener('pause', () => { this.play.textContent = '▶'; this.play.setAttribute('aria-label', 'Play'); });
    this.video.addEventListener('seeked', () => this.update());
    this.video.addEventListener('timeupdate', () => this.update());
    this.clock.textContent = ok ? 'Recorded outcome: success' : `Recorded outcome: ${h.recorded.exec_status}${h.recorded.failed_node ? ' at ' + h.recorded.failed_node : ''}`;
  }

  // Fit the whole tree unless that would shrink its text below legibility; then
  // draw it at actual size and keep the running node in view. Decided once the
  // tree has a width (a collapsed gallery group has none), and again on resize.
  autoFit() {
    if (!this.svg || this.userFit) return;
    const width = this.treeBox.clientWidth;
    if (!width) return;
    this.setFit(this.svg.viewBox.baseVal.width <= width * 1.35);
  }

  setFit(fit) {
    this.fit = fit;
    this.treeBox.classList.toggle('is-fit', fit);
    this.treeBox.classList.toggle('is-actual', !fit);
    this.fitButton.textContent = fit ? 'Actual size' : 'Fit whole tree';
  }

  follow(i) {
    if (this.fit || !this.svg || i < 0) return;
    const g = this.nodes[i];
    if (!g) return;
    const box = this.treeBox.getBoundingClientRect();
    const r = g.getBoundingClientRect();
    const cx = r.left + r.width / 2 - box.left;
    const cy = r.top + r.height / 2 - box.top;
    if (cx < box.width * 0.2 || cx > box.width * 0.8) this.treeBox.scrollLeft += cx - box.width / 2;
    if (cy < 30 || cy > box.height - 30) this.treeBox.scrollTop += cy - box.height / 2;
  }

  async ensure() {
    if (this.trace) return;
    const res = await fetch(this.h.trace);
    this.trace = await res.json();
    this.times = this.trace.ticks.map((t) => t.t);
    if (!this.video.src) this.video.src = this.h.video;
    this.autoFit();
    this.video.playbackRate = Number(this.el.querySelector('.live-speed').value);
  }

  async toggle() {
    await this.ensure();
    if (this.video.paused) {
      document.querySelectorAll('.live-card video').forEach((v) => { if (v !== this.video) v.pause(); });
      this.video.play().catch(() => {});
    } else {
      this.video.pause();
    }
  }

  loop() {
    if (this.video.paused) return;
    this.update();
    requestAnimationFrame(() => this.loop());
  }

  tickIndex(t) {
    let lo = 0, hi = this.times.length - 1, ans = -1;
    while (lo <= hi) {
      const mid = (lo + hi) >> 1;
      if (this.times[mid] <= t) { ans = mid; lo = mid + 1; } else hi = mid - 1;
    }
    return ans;
  }

  update() {
    if (!this.trace) return;
    const t = this.video.currentTime;
    if (this.video.duration) this.scrub.value = String(Math.round((t / this.video.duration) * 1000));
    const idx = this.tickIndex(t);
    const s = idx >= 0 ? this.trace.ticks[idx].s : null;
    const tr = this.trace;
    if (idx < 0) {
      this.clock.textContent = `${t.toFixed(1)} s`;
      this.active.textContent = t < tr.bt_start_s ? 'Tree not started.' : '';
    } else {
      this.clock.textContent = `${t.toFixed(1)} s · tick ${idx + 1} of ${tr.ticks.length}`;
      const running = [];
      for (let i = 0; i < s.length; i++) if (s[i] === 'R') running.push(this.h.names[i]);
      if (t >= tr.bt_end_s) {
        const r = tr.replay;
        this.active.innerHTML = r.exec_status === 'SUCCESS'
          ? `Tree returned <strong>SUCCESS</strong>; goal ${r.goal_satisfied ? 'met' : '<strong>not met</strong>'}.`
          : r.exec_status === 'TIMEOUT'
            ? `<strong>TIMEOUT</strong>: the ${tr.settings.timeout_s} s budget ran out.`
            : `Tree returned <strong>FAILURE</strong>${r.failed_node ? ` at <code>${esc(r.failed_node)}</code>` : ''}.`;
      } else {
        const shown = running.filter((n) => n !== 'sequence' && n !== 'selector');
        this.active.innerHTML = running.length
          ? `running: ${(shown.length ? shown : running).slice(-2).map((n) => `<code>${esc(n)}</code>`).join(' › ')}`
          : 'between ticks';
      }
    }
    if (s === this.last) return;
    this.last = s;
    this.follow(s ? s.lastIndexOf('R') : -1);
    if (this.branch) {
      const rows = [];
      if (s) for (let i = 0; i < s.length; i++) {
        if (s[i] === 'R' || s[i] === 'F') {
          rows.push(`<li class="st-${s[i]}" style="--d:${this.h.depths[i]}"><code>${esc(this.h.names[i])}</code> <span>${STATUS_WORD[s[i]]}</span></li>`);
        }
      }
      this.branch.innerHTML = rows.slice(0, 40).join('') || '<li class="muted-note">No node ticked yet.</li>';
    }
    for (let i = 0; i < this.nodes.length; i++) {
      const c = s ? s[i] : '.';
      const g = this.nodes[i];
      const up = c.toUpperCase();
      g.classList.toggle('st-R', up === 'R');
      g.classList.toggle('st-S', up === 'S');
      g.classList.toggle('st-F', up === 'F');
      g.classList.toggle('st-idle', c === '.');
      g.classList.toggle('st-stale', c !== up && c !== '.');
      const edge = this.edges.get(i);
      if (edge) edge.classList.toggle('on', c === 'R');
    }
  }
}

function liveCard(key, compact = false) {
  const h = state.catalog.highlights[key];
  if (!h) return '';
  const m = h.cell.split('_');
  const method = methodInfo(m[2]);
  const ok = h.recorded.success;
  const tag = ok ? '<span class="gallery-tag gallery-tag--good">Success</span>'
    : `<span class="gallery-tag gallery-tag--bad">${esc(h.recorded.exec_status === 'SUCCESS' ? 'Goal mismatch' : h.recorded.exec_status === 'TIMEOUT' ? 'Timeout' : 'Runtime failure')}</span>`;
  return `<figure class="gallery-card live-card ${ok ? 'gallery-card--success' : 'gallery-card--fail'}${compact ? ' live-card--stacked' : ''}">
    <div class="live-card__head">
      <span class="live-card__method">${esc(method.symbol)}</span>
      <span class="gallery-meta">${esc(modelLabel(m[1]))} · ${esc(method.label)} · ${esc(suiteLabel(m[0]))}</span>
      ${tag}
    </div>
    <div class="live-player" data-live="${esc(key)}"></div>
    <figcaption>
      ${compact ? '' : `<p class="live-card__prompt">“${esc(h.prompt)}”</p>`}
      <p>${WHY[key] ?? ''}</p>
      <p class="live-card__links"><a href="#explorer" data-open="${esc(h.cell)}|${esc(h.task_id)}">Open in the explorer</a>
      · ${esc(h.nodes)} nodes · replay matched the recorded run</p>
    </figcaption>
  </figure>`;
}

function renderLiveGallery() {
  $('liveGallery').innerHTML = GALLERY.map((g) => `
    <details class="gallery-group"${g.open ? ' open' : ''}>
      <summary class="gallery-group__head">${esc(g.title)}</summary>
      <p class="gallery-group__desc">${esc(g.desc)}</p>
      ${(g.pairs ?? []).map((p) => `
        <div class="comparison-pair">
          <p class="comparison-pair__prompt">“${esc(p.prompt)}” <span class="comparison-pair__model">${esc(p.meta)}</span></p>
          <div class="comparison-pair__cards">${p.keys.map((k) => liveCard(k, true)).join('')}</div>
        </div>`).join('')}
      ${g.singles ? `<div class="comparison-pair"><div class="comparison-pair__cards">${g.singles.map((k) => liveCard(k)).join('')}</div></div>` : ''}
    </details>`).join('');
  document.querySelectorAll('.live-player').forEach((el) => { el.player = new LivePlayer(el, el.dataset.live); });
  let resizeTimer;
  window.addEventListener('resize', () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => document.querySelectorAll('.live-player').forEach((el) => el.player.autoFit()), 150);
  });
}

// ─── Explorer ─────────────────────────────────────────────────────────────────

function batchesFor(env, model) {
  return state.catalog.batches.filter((b) => b.environment === env && b.model === model);
}

function currentBatch() {
  return state.catalog.batches.find((b) => b.environment === state.env && b.model === state.model &&
    b.method === state.method && b.suite === state.suite) ?? null;
}

function setOptions(select, items, selected) {
  select.innerHTML = items.map(({ value, label }) =>
    `<option value="${esc(value)}"${value === selected ? ' selected' : ''}>${esc(label)}</option>`).join('');
}

function syncSelectors() {
  const envs = [...new Set(state.catalog.batches.map((b) => b.environment))];
  setOptions($('envSelect'), envs.map((e) => ({ value: e, label: e === 'panther' ? 'Panther (hardware)' : 'PyRoboSim (simulation)' })), state.env);
  setOptions($('modelSelect'), state.catalog.models.map((m) => ({ value: m.id, label: m.label })), state.model);
  const avail = batchesFor(state.env, state.model);
  const suites = [...new Set(avail.map((b) => b.suite))];
  if (!suites.includes(state.suite)) state.suite = suites[0];
  setOptions($('suiteSelect'), suites.map((s) => ({ value: s, label: suiteLabel(s) })), state.suite);
  const methods = state.catalog.methods.filter((m) => avail.some((b) => b.suite === state.suite && b.method === m.id));
  if (!methods.some((m) => m.id === state.method)) state.method = methods.some((m) => m.id === 'mcore') ? 'mcore' : methods[0].id;
  setOptions($('methodSelect'), methods.map((m) => ({ value: m.id, label: `${m.label} (${m.symbol})`.replace('LLM-OBTEA (LLM-OBTEA)', 'LLM-OBTEA') })), state.method);
  $('taskFilter').value = state.filter;
}

function renderSummary(batch) {
  const tile = (label, value, note = '') => `<div class="stat-tile"><div class="stat-tile__label">${esc(label)}</div>
    <div class="stat-tile__value">${value}</div>${note ? `<div class="stat-tile__note">${esc(note)}</div>` : ''}</div>`;
  const m = methodInfo(batch.method);
  const tiles = [
    tile('Cell', `${esc(m.symbol)} · ${esc(suiteLabel(batch.suite))}`, `${modelLabel(batch.model)}`),
    tile('Tasks', batch.count),
  ];
  if (batch.environment === 'panther') {
    tiles.push(tile('Valid@1', `${batch.run01.valid_at_1}/14`, 'one run per task'));
    tiles.push(tile('Success', 'observed', 'see the hardware table'));
  } else {
    const ten = batch.ten_runs;
    tiles.push(tile('Valid@1, run 1', batch.run01.valid_at_1 == null ? 'n/a' : `${batch.run01.valid_at_1}/${batch.count}`,
      ten.valid_mean == null ? 'grounded by construction' : `10 runs: ${ten.valid_mean.toFixed(1)} ± ${ten.valid_sd.toFixed(1)}%`));
    tiles.push(tile('Success, run 1', `${batch.run01.success}/${batch.count}`, `10 runs: ${ten.success_mean.toFixed(1)} ± ${ten.success_sd.toFixed(1)}%`));
  }
  $('batchSummary').innerHTML = `<div class="batch-stat-row">${tiles.join('')}</div>`;
}

function renderRootstocksPanel(batch) {
  const show = batch.method === 'mcore' && batch.environment === 'pyrobosim';
  $('rootstocksPanel').hidden = !show;
  $('rootstocksView').innerHTML = show ? state.catalog.contract.sim.rootstocks.map((r) => `
    <article class="rootstock-card"><div class="rootstock-card__head"><h4><code>${esc(r.name)}</code></h4></div>
    <div class="rootstock-card__svg">${r.svg}</div><p class="rootstock-card__desc">${esc(r.description)}</p></article>`).join('') : '';
}

function taskOutcome(task, panther) {
  if (panther) return badge(task.valid_at_1 ? 'Valid@1' : 'First submission invalid', task.valid_at_1 ? 'good' : 'warn');
  if (task.success) return badge('Success', 'good');
  return badge(task.category ?? 'Failure', 'bad', task.cause_note ?? '');
}

function filteredTasks(tasks, panther) {
  const q = state.search.trim().toLowerCase();
  return tasks.filter((t) => {
    if (q && !`${t.prompt ?? ''} ${t.id}`.toLowerCase().includes(q)) return false;
    switch (state.filter) {
      case 'fail': return panther ? false : !t.success;
      case 'success': return panther ? true : t.success;
      case 'invalid1': return t.valid_at_1 === false;
      default: return true;
    }
  });
}

function renderTaskList(batch, detail) {
  const panther = batch.environment === 'panther';
  const tasks = filteredTasks(detail.tasks, panther);
  $('taskListMeta').textContent = `${tasks.length} of ${detail.tasks.length}`;
  if (!tasks.some((t) => t.id === state.taskId)) state.taskId = tasks[0]?.id ?? null;
  $('taskList').innerHTML = tasks.length ? tasks.map((t) => {
    const num = detail.tasks.indexOf(t) + 1;
    const extra = [
      t.variation ? badge(t.variation) : t.prior ? badge(`${t.prior} prior`) : badge(t.archetype ?? ''),
      taskOutcome(t, panther),
      !panther && t.valid_at_1 === false ? badge('1st invalid', 'warn', 'The first submission failed validation') : '',
      !panther ? badge(`${t.runs_succeeded}/${t.runs} runs`, t.runs_succeeded === t.runs ? '' : t.runs_succeeded === 0 ? 'bad' : 'warn', 'Runs, of ten, in which this task succeeded') : '',
      t.live ? badge('▶ live', 'live', 'A live replay is in the gallery') : '',
    ].join('');
    const sel = t.id === state.taskId;
    return `<button type="button" class="task-item${sel ? ' is-selected' : ''}" data-task-id="${esc(t.id)}" role="option" aria-selected="${sel}">
      <span class="task-item__num">${num}</span>
      <span class="task-item__body"><span class="task-item__prompt">${esc(t.prompt)}</span>
      <span class="task-item__tags">${extra}</span></span></button>`;
  }).join('') : '<div class="task-list-empty">No tasks match this filter.</div>';
}

function successSpecHtml(spec) {
  if (spec == null) return '';
  const phrase = (k, v) => {
    if (k === 'all_of' || k === 'any_of') {
      return `<strong>${k === 'all_of' ? 'All of' : 'Any of'}:</strong><ul>${v.map((x) => `<li>${successSpecHtml(x)}</li>`).join('')}</ul>`;
    }
    if (v && typeof v === 'object') {
      return `<code>${esc(k)}</code>: ${Object.entries(v).map(([a, b]) => `${esc(a)} = <code>${esc(b)}</code>`).join(', ')}`;
    }
    return `<code>${esc(k)}</code>: <code>${esc(v)}</code>`;
  };
  return Object.entries(spec).map(([k, v]) => phrase(k, v)).join('<br>');
}

function card(label, value, tone = '') {
  return `<div class="result-card"><div class="result-card__label">${esc(label)}</div>
    <div class="result-card__value${tone ? ' tone-' + tone : ''}">${value}</div></div>`;
}

function renderTaskDetail(batch, detail) {
  const panther = batch.environment === 'panther';
  const task = detail.tasks.find((t) => t.id === state.taskId);
  const wrap = $('btTreeView');
  if (!task) {
    $('taskPrompt').textContent = 'Select a task from the list.';
    $('taskBadgeRow').innerHTML = '';
    wrap.className = 'bt-tree-empty';
    wrap.innerHTML = 'Select a task.';
    $('btRawView').textContent = '';
    $('taskSpecView').innerHTML = '';
    $('resultSummaryView').innerHTML = '';
    $('taskLive').innerHTML = '';
    $('taskIdMeta').textContent = '';
    return;
  }
  $('taskIdMeta').textContent = task.id;
  $('taskPrompt').textContent = task.prompt;
  $('taskBadgeRow').innerHTML = [
    badge(task.archetype ?? ''),
    task.variation ? badge(task.variation) : '',
    task.prior ? badge(`${task.prior} prior`) : '',
    taskOutcome(task, panther),
  ].join('');
  $('taskLive').innerHTML = task.live
    ? `<p class="live-link">A live replay of this tree is in the gallery. <a href="#live" data-live-jump="${esc(task.live)}">Watch it with the tree ticking ▶</a></p>` : '';

  if (task.svg) {
    wrap.className = `bt-svg-wrap${state.zoom ? ' is-actual' : ''}`;
    wrap.innerHTML = task.svg;
  } else if (task.bt || task.xml) {
    wrap.className = 'bt-tree-empty';
    wrap.innerHTML = `This tree has ${task.nodes} nodes, too many to draw legibly. Its full specification is below.`;
  } else {
    wrap.className = 'bt-tree-empty';
    wrap.innerHTML = 'No tree was executed: no submission for this task passed validation.';
  }
  $('btZoom').hidden = !task.svg;
  $('btZoom').textContent = state.zoom ? 'Fit to width' : 'Actual size';
  $('btFormatMeta').textContent = panther ? `BT.CPP XML · ${task.nodes ?? '—'} nodes` : task.bt ? `PyTrees JSON · ${task.nodes} nodes` : '';
  $('btRawView').textContent = panther ? (task.xml || '(none)') : task.bt ? JSON.stringify(task.bt, null, 2) : '(none)';

  if (panther) {
    $('taskSpecView').innerHTML = `<div class="spec-card"><div class="spec-card__title">Category</div>${esc(task.archetype)}</div>
      <div class="spec-card"><div class="spec-card__title">Success</div>Judged by supervised observation of the robot. Per-category results are in the hardware table.</div>`;
    $('resultSummaryView').innerHTML = [
      card('Valid@1', task.valid_at_1 ? 'Yes' : 'No', task.valid_at_1 ? 'good' : 'bad'),
      card('Submissions', task.submissions),
      task.first_issues.length ? card('First submission', esc(task.first_issues.join('; '))) : '',
      task.earlier_sessions ? card('Note', 'This task was run again later the same day; the later session is shown.') : '',
      card('Tree file', `<code>${esc(task.bt_file ?? '—')}</code>`),
    ].join('');
    return;
  }

  $('taskSpecView').innerHTML = `
    <div class="spec-card"><div class="spec-card__title">Goal condition</div>${successSpecHtml(task.success_spec)}</div>
    ${task.mechanism ? `<div class="spec-card"><div class="spec-card__title">Prior given to LLM-OBTEA</div>${esc(task.prior)}: ${esc(task.mechanism)}</div>` : ''}
    <div class="spec-card"><div class="spec-card__title">Time budget</div>${{ core60: 60, lang50: 60, hard15: 120, prior30: 30 }[batch.suite]} s at realtime factor 5</div>`;

  const exec = task.exec_status;
  $('resultSummaryView').innerHTML = [
    card('Valid@1', task.valid_at_1 == null ? 'n/a' : task.valid_at_1 ? 'Yes' : 'No', task.valid_at_1 === false ? 'bad' : task.valid_at_1 ? 'good' : ''),
    task.submissions != null ? card('Submissions', task.submissions) : '',
    task.first_issues.length ? card('First submission', esc(task.first_issues.join('; '))) : '',
    card('Execution', exec ? `<code>${esc(exec)}</code>` : 'not executed', exec === 'SUCCESS' ? 'good' : exec ? 'bad' : ''),
    card('Goal met', task.goal_satisfied == null ? '—' : task.goal_satisfied ? 'Yes' : 'No', task.goal_satisfied ? 'good' : task.goal_satisfied === false ? 'bad' : ''),
    card('Success', task.success ? 'Yes' : 'No', task.success ? 'good' : 'bad'),
    task.category ? card('Failure', `${esc(task.category)}<div class="result-card__note">${esc(task.cause_note)} <code>${esc(task.failure_cause)}</code></div>`, 'bad') : '',
    task.failed_node ? card('First failing node', `<code>${esc(task.failed_node)}</code>`) : '',
    task.tick_count != null ? card('Ticks · runtime', `${task.tick_count} · ${(task.runtime_ms / 1000).toFixed(1)} s`) : '',
    card('Success over 10 runs', `${task.runs_succeeded}/${task.runs}`),
    card('Tree file', `<code>${esc(task.bt_file ?? '—')}</code>`),
  ].join('');
}

async function renderExplorer() {
  syncSelectors();
  const batch = currentBatch();
  if (!batch) return;
  renderSummary(batch);
  renderRootstocksPanel(batch);
  $('taskList').innerHTML = '<div class="task-list-empty">Loading…</div>';
  let detail;
  try {
    detail = await loadBatch(batch.name);
  } catch (err) {
    $('taskList').innerHTML = `<div class="task-list-empty">Could not load this cell (${esc(err.message)}).</div>`;
    return;
  }
  if (batch !== currentBatch()) return; // selection changed while loading
  renderTaskList(batch, detail);
  renderTaskDetail(batch, detail);
}

function onSelect(key) {
  return (e) => { state[key] = e.target.value; if (key !== 'filter') state.taskId = null; renderExplorer(); };
}
$('envSelect').addEventListener('change', onSelect('env'));
$('modelSelect').addEventListener('change', onSelect('model'));
$('methodSelect').addEventListener('change', onSelect('method'));
$('suiteSelect').addEventListener('change', onSelect('suite'));
$('taskFilter').addEventListener('change', onSelect('filter'));
$('taskSearch').addEventListener('input', (e) => {
  state.search = e.target.value;
  const batch = currentBatch();
  const detail = batch && state.cache[batch.name];
  if (!detail) return;
  renderTaskList(batch, detail);
  renderTaskDetail(batch, detail);
});
$('taskList').addEventListener('click', (e) => {
  const btn = e.target.closest('[data-task-id]');
  if (!btn) return;
  state.taskId = btn.dataset.taskId;
  const batch = currentBatch();
  const detail = state.cache[batch.name];
  renderTaskList(batch, detail);
  renderTaskDetail(batch, detail);
});
$('btZoom').addEventListener('click', () => {
  state.zoom = !state.zoom;
  $('btTreeView').classList.toggle('is-actual', state.zoom);
  $('btZoom').textContent = state.zoom ? 'Fit to width' : 'Actual size';
});

function openInExplorer(cell, taskId) {
  const b = state.catalog.batches.find((x) => x.name === cell);
  if (!b) return;
  Object.assign(state, { env: b.environment, model: b.model, method: b.method, suite: b.suite, taskId, filter: 'all' });
  renderExplorer();
  $('explorer').scrollIntoView({ behavior: 'smooth' });
}

document.addEventListener('click', (e) => {
  const open = e.target.closest('[data-open]');
  if (open) {
    e.preventDefault();
    const [cell, taskId] = open.dataset.open.split('|');
    openInExplorer(cell, taskId);
    return;
  }
  const jump = e.target.closest('[data-live-jump]');
  if (jump) {
    e.preventDefault();
    const el = document.querySelector(`.live-player[data-live="${CSS.escape(jump.dataset.liveJump)}"]`);
    if (!el) return;
    el.closest('details').open = true;
    el.closest('.live-card').scrollIntoView({ behavior: 'smooth', block: 'center' });
    el.player.toggle();
  }
});

// ─── Robot demo tree ──────────────────────────────────────────────────────────

async function renderVideoBt() {
  try {
    const detail = await loadBatch('panther_gemma_mcore');
    const task = detail.tasks.find((t) => t.num === 13);
    $('videoBtPrompt').textContent = `“${task.prompt}”`;
    const box = $('videoBtTree');
    box.innerHTML = task.svg ?? '<div class="bt-tree-empty">Tree not found.</div>';
    $('videoBtMeta').textContent = `BT.CPP XML · ${task.nodes} nodes · ${task.bt_file.split('/').pop()}`;
    const svg = box.querySelector('svg');
    if (!svg) return;
    // Fit the tree unless its text would become illegible; otherwise scroll it.
    const button = $('videoBtFit');
    const setFit = (fit) => {
      box.classList.toggle('is-fit', fit);
      box.classList.toggle('is-actual', !fit);
      button.textContent = fit ? 'Actual size' : 'Fit whole tree';
      box.dataset.fit = fit ? '1' : '';
    };
    let chosen = false;
    const auto = () => { if (!chosen && box.clientWidth) setFit(svg.viewBox.baseVal.width <= box.clientWidth * 1.35); };
    button.hidden = false;
    button.addEventListener('click', () => { chosen = true; setFit(!box.dataset.fit); });
    auto();
    window.addEventListener('resize', auto);
  } catch {
    $('videoBtTree').innerHTML = '<div class="bt-tree-empty">Tree not found.</div>';
  }
}

// ─── Navigation bar ───────────────────────────────────────────────────────────

(function topbar() {
  const bar = $('topbar');
  const links = [...bar.querySelectorAll('.topbar__links a')];
  const sections = links.map((a) => document.querySelector(a.getAttribute('href'))).filter(Boolean);
  const hero = $('top');
  new IntersectionObserver(([entry]) => bar.classList.toggle('is-visible', !entry.isIntersecting))
    .observe(hero);
  let queued = false;
  const mark = () => {
    queued = false;
    const y = bar.offsetHeight + 24;
    let current = null;
    for (const sec of sections) if (sec.getBoundingClientRect().top <= y) current = sec;
    links.forEach((a) => {
      const on = current && a.getAttribute('href') === `#${current.id}`;
      a.classList.toggle('is-current', Boolean(on));
      if (on) a.setAttribute('aria-current', 'location'); else a.removeAttribute('aria-current');
    });
    // Keep the current section's link in view when the bar is narrower than its links.
    const cur = links.find((a) => a.classList.contains('is-current'));
    const box = bar.querySelector('.topbar__links');
    if (cur && (cur.offsetLeft < box.scrollLeft || cur.offsetLeft + cur.offsetWidth > box.scrollLeft + box.clientWidth)) {
      box.scrollLeft = cur.offsetLeft - (box.clientWidth - cur.offsetWidth) / 2;
    }
  };
  window.addEventListener('scroll', () => { if (!queued) { queued = true; requestAnimationFrame(mark); } }, { passive: true });
  mark();
})();

// ─── Boot ─────────────────────────────────────────────────────────────────────

(async function boot() {
  try {
    const res = await fetch(CATALOG_URL);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    state.catalog = await res.json();
  } catch (err) {
    document.querySelectorAll('.muted-note').forEach((n) => { n.textContent = `Could not load the data (${err.message}).`; });
    return;
  }
  renderMcpTools();
  renderTables();
  renderLiveGallery();
  renderContract();
  renderOoc();
  renderExplorer();
  renderVideoBt();
})();
