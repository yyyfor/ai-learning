// Lab interactions use the same FastAPI origin and shared request/error helpers.
(() => {
  const labViews = new Set(['graph', 'governance', 'evaluation', 'observability', 'agent', 'durable-agent']);
  let libraryPromise;
  let library = [];
  let asset = null;
  let governanceRequest = 0;
  let governanceLoadedId = '';
  let evaluationResult = null;
  let traceRows = [];
  let metricsBusy = false;
  let metricsTimer;
  const documentSelections = new Map();
  const lines = (text) => text.split('\n').map((line) => line.trim()).filter(Boolean);
  const endpoint = (prefix, id) => `${prefix}/${encodeURIComponent(id)}`;
  const jsonOptions = (body, method = 'POST', timeout = 600000) => ({ method, body: JSON.stringify(body), timeout });
  const nameOf = (id) => library.find((doc) => doc.id === id)?.title || id;
  const display = (value) => value === null || value === undefined ? '—' : String(value);

  function message(id, text = '', error = false, busy = false) {
    $(id).textContent = text;
    $(id).dataset.error = String(error);
    $(id).dataset.busy = String(busy);
  }

  function rawDetails(body, label = 'Full API response') {
    const details = element('details', 'context');
    details.append(element('summary', '', label), element('pre', '', JSON.stringify(body, null, 2)));
    return details;
  }

  function table(headers, rows) {
    const wrapper = element('div', 'table-wrap');
    const grid = element('table');
    const head = element('thead');
    const header = element('tr');
    headers.forEach((text) => header.append(element('th', '', text)));
    head.append(header);
    const body = element('tbody');
    rows.forEach((values) => {
      const row = element('tr');
      values.forEach((value) => {
        const cell = element('td');
        cell.append(value instanceof Node ? value : document.createTextNode(display(value)));
        row.append(cell);
      });
      body.append(row);
    });
    grid.append(head, body);
    wrapper.append(grid);
    return wrapper;
  }

  function sourceButton(id) {
    const button = element('button', 'document-title', nameOf(id));
    button.type = 'button';
    button.addEventListener('click', () => showDocument(id));
    return button;
  }

  function populatePicker(select) {
    const selected = documentSelections.has(select.id) ? [documentSelections.get(select.id)]
      : [...select.selectedOptions].map((option) => option.value);
    select.replaceChildren(new Option(library.length ? 'Choose a document…' : 'No documents — create one in Documents', ''));
    library.forEach((doc) => select.append(new Option(doc.title, doc.id)));
    [...select.options].forEach((option) => { option.selected = selected.includes(option.value); });
    documentSelections.delete(select.id);
  }

  async function loadLibrary(refresh = false) {
    if (refresh) libraryPromise = undefined;
    if (!libraryPromise) {
      libraryPromise = (async () => {
        const documents = [];
        for (let page = 1; ; page++) {
          const batch = await api(`/documents?page=${page}&page_size=100`);
          documents.push(...batch);
          if (batch.length < 100) break;
        }
        library = documents;
        document.querySelectorAll('.document-picker').forEach(populatePicker);
        return documents;
      })().catch((error) => { libraryPromise = undefined; throw error; });
    }
    return libraryPromise;
  }

  // Lock only this action's controls and restore their prior state after completion.
  async function action(container, statusId, pending, operation) {
    if (container.dataset.busy === 'true') return;
    container.dataset.busy = 'true';
    container.setAttribute('aria-busy', 'true');
    const controls = [...new Set([...container.querySelectorAll('button,input,textarea,select'),
      ...(statusId === 'governance-message' ? [...$('view-governance').querySelectorAll('button'), $('governance-document')] : [])])];
    const previous = controls.map((control) => control.disabled);
    controls.forEach((control) => { control.disabled = true; });
    message(statusId, pending, false, true);
    try { await operation(); }
    catch (error) { message(statusId, errorMessage(error), true); }
    finally {
      controls.forEach((control, index) => { control.disabled = previous[index]; });
      if (statusId === 'governance-message') {
        $('gov-transition').disabled = !transitions[asset?.status];
        $('gov-rollback').disabled = !asset?.history?.length;
      }
      delete container.dataset.busy;
      container.removeAttribute('aria-busy');
      $(statusId).dataset.busy = 'false';
    }
  }

  function documentId(picker) {
    const value = $(picker).value;
    if (!value) throw new Error('Choose a document first.');
    return value;
  }

  // Lab 8: the server remains authoritative for roles and lifecycle transitions.
  const stages = ['draft', 'validated', 'approved', 'published', 'deprecated'];
  const transitions = { draft: ['validate', 'Validate draft'], validated: ['approve', 'Approve version'],
    approved: ['publish', 'Publish version'], published: ['deprecate', 'Deprecate version'] };
  const govFields = { source_uri: 'gov-source-uri', source_owner: 'gov-source-owner',
    business_owner: 'gov-business-owner', effective_date: 'gov-effective-date', expiry_date: 'gov-expiry-date',
    security_level: 'gov-security-level', confidence_score: 'gov-confidence' };

  function renderAsset(record) {
    asset = record;
    $('governance-lifecycle').replaceChildren();
    stages.forEach((stage) => {
      const item = element('li', '', stage);
      if (stage === record?.status) item.setAttribute('aria-current', 'step');
      $('governance-lifecycle').append(item);
    });
    Object.entries(govFields).forEach(([key, id]) => {
      $(id).value = record?.[key] ?? ({ effective_date: new Date().toISOString().slice(0, 10),
        source_uri: 'lab://knowledge', security_level: 0, confidence_score: 1 }[key] ?? '');
    });
    const next = transitions[record?.status];
    $('gov-transition').disabled = !next;
    $('gov-transition').textContent = next?.[1] || 'No further transition';
    $('governance-current').textContent = record ? `Version ${record.version} · ${record.status}` : 'Not registered yet. Save a draft to begin.';
    const history = record?.history || [];
    $('gov-rollback-version').replaceChildren(new Option('Choose a version…', ''));
    history.forEach((snapshot) => $('gov-rollback-version').append(new Option(`Version ${snapshot.version} · ${snapshot.status}`, snapshot.version)));
    $('gov-rollback').disabled = !history.length;
    $('gov-citation-version').value = record?.version || '';
    $('governance-history').replaceChildren(history.length
      ? table(['Version', 'Action', 'Actor', 'Reason', 'Time'], record.provenance_chain.map((row) =>
        [row.version, row.action, row.actor, row.reason, new Date(row.at).toLocaleString()]))
      : element('p', 'helper', 'No versions yet.'));
    if (record) $('governance-history').append(rawDetails(record));
  }

  async function loadAsset() {
    const request = ++governanceRequest;
    const id = $('governance-document').value;
    governanceLoadedId = id;
    $('governance-fields').disabled = true;
    renderAsset(null);
    if (!id) { message('governance-message', 'Choose a document to begin.'); return; }
    message('governance-message', 'Loading governance record…');
    try {
      const record = await api(endpoint('/governance/documents', id));
      if (request !== governanceRequest) return;
      renderAsset(record);
      message('governance-message', `Loaded ${nameOf(id)}.`);
    } catch (error) {
      if (request !== governanceRequest) return;
      message('governance-message', error.status === 404 ? 'No governance record yet. Register ownership below.' : errorMessage(error), error.status !== 404);
    } finally {
      if (request === governanceRequest) $('governance-fields').disabled = false;
    }
  }

  async function freshness() {
    await action($('governance-freshness'), 'governance-message', 'Checking knowledge freshness…', async () => {
      const rows = await api('/governance/freshness');
      $('governance-freshness').replaceChildren(rows.length
        ? table(['Document', 'Version', 'Usable', 'Freshness', 'Age since review'], rows.map((row) => [
          sourceButton(row.knowledge_id), row.version, row.usable ? 'Yes' : 'No', row.freshness_score,
          `${Math.round(row.freshness_lag_seconds / 86400)} days`]))
        : element('div', 'state', 'No registered assets. Save governance metadata to start monitoring freshness.'));
      message('governance-message', 'Freshness updated.');
    });
  }

  $('governance-document').addEventListener('change', loadAsset);
  $('governance-refresh').addEventListener('click', async () => {
    try { await loadLibrary(true); await loadAsset(); } catch (error) { message('governance-message', errorMessage(error), true); }
  });
  $('freshness-refresh').addEventListener('click', freshness);
  $('governance-draft-form').addEventListener('submit', (event) => {
    event.preventDefault();
    action(event.currentTarget, 'governance-message', 'Saving a new draft version…', async () => {
      const payload = Object.fromEntries(Object.entries(govFields).map(([key, id]) => [key, $(id).value.trim()]));
      payload.security_level = Number(payload.security_level);
      payload.confidence_score = Number(payload.confidence_score);
      payload.expiry_date ||= null;
      const result = await api(endpoint('/governance/documents', documentId('governance-document')), jsonOptions(payload, 'PUT'));
      renderAsset(result);
      message('governance-message', `Saved version ${result.version} as draft.`);
    });
  });
  $('governance-transition-form').addEventListener('submit', async (event) => {
    event.preventDefault();
    const next = transitions[asset?.status];
    if (!next) return;
    await action(event.currentTarget, 'governance-message', 'Updating lifecycle status…', async () => {
      const result = await api(`${endpoint('/governance/documents', documentId('governance-document'))}/transition`,
        jsonOptions({ action: next[0], reason: $('gov-transition-reason').value.trim() }));
      renderAsset(result);
      message('governance-message', `Version ${result.version} is ${result.status}.`);
    });
    $('gov-transition').disabled = !transitions[asset?.status];
  });
  $('governance-rollback-form').addEventListener('submit', (event) => {
    event.preventDefault();
    action(event.currentTarget, 'governance-message', 'Restoring a version as a new draft…', async () => {
      const result = await api(`${endpoint('/governance/documents', documentId('governance-document'))}/rollback`,
        jsonOptions({ version: Number($('gov-rollback-version').value), reason: $('gov-rollback-reason').value.trim() }));
      renderAsset(result);
      message('governance-message', `Restored as draft version ${result.version}. Review and publish it again when ready.`);
    });
  });
  $('governance-citation-form').addEventListener('submit', (event) => {
    event.preventDefault();
    action(event.currentTarget, 'governance-message', 'Checking citation against the source…', async () => {
      const result = await api('/governance/citations/validate', jsonOptions({ document_id: documentId('governance-document'),
        text: $('gov-citation-text').value, version: $('gov-citation-version').value ? Number($('gov-citation-version').value) : null }));
      $('governance-citation-result').replaceChildren(element('p', 'status-text', result.valid ? 'Valid source citation' : `Invalid: ${result.reasons.join(', ')}`), rawDetails(result));
      message('governance-message', 'Citation check complete.');
    });
  });

  // Lab 6: extract -> review -> explicitly save, then query/compare.
  $('graph-document').addEventListener('change', () => {
    $('graph-extraction').value = '';
    message('graph-build-message', 'Document selected. Extract relationships to prepare a new preview.');
  });
  $('graph-source').addEventListener('click', () => {
    try { showDocument(documentId('graph-document')); } catch (error) { message('graph-build-message', error.message, true); }
  });
  $('graph-extract').addEventListener('click', () => action($('graph-extract').closest('.lab-panel'), 'graph-build-message', 'Extracting entities and source quotations…', async () => {
    const result = await api(`${endpoint('/graph/documents', documentId('graph-document'))}/extract`, { method: 'POST', timeout: 600000 });
    $('graph-extraction').value = JSON.stringify(result, null, 2);
    message('graph-build-message', `Preview: ${result.entities.length} entities, ${result.relations.length} relations. Review, then save the graph.`);
  }));
  $('graph-save').addEventListener('click', () => action($('graph-save').closest('.lab-panel'), 'graph-build-message', 'Saving the reviewed graph…', async () => {
    let extraction;
    try { extraction = JSON.parse($('graph-extraction').value); } catch { throw new Error('Extraction must be valid JSON. Extract a document first or paste reviewed entities and relations.'); }
    if (!Array.isArray(extraction?.entities) || !Array.isArray(extraction?.relations)) throw new Error('Extraction must contain entities and relations arrays.');
    const result = await api(endpoint('/graph/documents', documentId('graph-document')), jsonOptions(extraction, 'PUT'));
    message('graph-build-message', `Saved ${result.entities} entities and ${result.relations} relations.`);
  }));

  function graphEvidence(result) {
    const fragment = element('div');
    if (result.answer) fragment.append(element('h2', '', 'Graph answer'), element('p', 'agent-answer', result.answer));
    fragment.append(element('h2', '', 'Relationship evidence'));
    if (!result.paths.length) fragment.append(element('div', 'state', 'No relationships found. Save a graph for this entity or try a different starting entity.'));
    result.paths.forEach((path) => {
      const article = element('article', 'result');
      const edge = element('div', 'graph-relationship');
      edge.append(element('strong', '', path.source), element('span', '', `— ${path.relation} →`), element('strong', '', path.target));
      article.append(element('span', 'tag', `Hop ${path.hop}`), edge, element('p', '', path.evidence), sourceButton(path.document_id));
      fragment.append(article);
    });
    return fragment;
  }

  $('graph-query-form').addEventListener('submit', (event) => {
    event.preventDefault();
    const compare = event.submitter?.value === 'compare';
    action(event.currentTarget, 'graph-message', compare ? 'Comparing graph traversal and vector retrieval…' : 'Exploring graph relationships…', async () => {
      const result = await api(`/graph/${compare ? 'compare' : 'query'}`, jsonOptions({ query: $('graph-question').value.trim(),
        entity: $('graph-entity').value.trim(), hops: Number($('graph-hops').value), limit: Number($('graph-limit').value), generate_answer: $('graph-generate').checked }));
      $('graph-results').replaceChildren(graphEvidence(compare ? result.graph : result));
      if (compare) {
        const vector = element('div');
        vector.append(element('h2', '', 'Vector search evidence'));
        result.vector.hits.forEach((hit) => {
          const row = element('article', 'result');
          row.append(sourceButton(hit.document_id), element('p', '', hit.text), element('p', 'helper', `Score: ${hit.score}`));
          vector.append(row);
        });
        if (!result.vector.hits.length) vector.append(element('p', 'helper', 'No vector matches. Index the document in RAG first.'));
        (result.vector.warnings || []).forEach((warning) => vector.append(element('p', 'helper', warning)));
        $('graph-results').append(vector);
      }
      $('graph-results').append(rawDetails(result));
      message('graph-message', 'Graph request complete.');
    });
  });

  // Lab 9: ordinary fields for golden cases; JSON is only an optional result view.
  let caseSequence = 0;
  function addCase() {
    const count = $('evaluation-cases').children.length;
    if (count >= 50) return;
    const id = `eval-case-${++caseSequence}`;
    const fieldset = element('fieldset', 'evaluation-case');
    fieldset.innerHTML = `<legend>Question ${count + 1}</legend><div class="form-grid">
      <label class="full">Question<input data-case="query" required maxlength="2000" placeholder="How many annual leave days do full-time employees receive?"></label>
      <label class="full">Expected source documents · select one or more<select id="${id}-sources" class="document-picker" data-case="sources" multiple size="4" required></select></label>
      <label>Expected facts · one per line<textarea data-case="facts" rows="3" placeholder="Full-time employees receive 20 days each year."></textarea></label>
      <label>Allowed answer<textarea data-case="allowed" rows="3" placeholder="20 days of annual leave each year."></textarea></label>
      <label class="full">Forbidden phrases · one per line<textarea data-case="forbidden" rows="2" placeholder="30 days"></textarea></label></div><button type="button" class="remove-case">Remove question</button>`;
    populatePicker(fieldset.querySelector('.document-picker'));
    fieldset.querySelector('.remove-case').addEventListener('click', () => { fieldset.remove(); numberCases(); });
    $('evaluation-cases').append(fieldset);
    numberCases();
  }

  function numberCases() {
    const cases = [...$('evaluation-cases').children];
    cases.forEach((item, index) => { item.querySelector('legend').textContent = `Question ${index + 1}`; item.querySelector('.remove-case').disabled = cases.length === 1; });
    $('eval-add-case').disabled = cases.length >= 50;
  }

  $('eval-add-case').addEventListener('click', addCase);
  $('eval-use-baseline').addEventListener('click', () => {
    $('eval-baseline').value = evaluationResult.id;
    message('evaluation-message', 'Baseline selected. Keep the golden questions, top-k and judge setting unchanged.');
  });
  $('evaluation-form').addEventListener('submit', async (event) => {
    event.preventDefault();
    await action(event.currentTarget, 'evaluation-message', 'Running golden questions and scoring answers… This may take several minutes.', async () => {
      const cases = [...$('evaluation-cases').children].map((item) => {
        const value = (name) => item.querySelector(`[data-case=${name}]`).value;
        const expected = [...item.querySelector('[data-case=sources]').selectedOptions].map((option) => option.value).filter(Boolean);
        if (!expected.length) throw new Error('Choose at least one expected source for every question.');
        return { query: value('query').trim(), expected_sources: expected, expected_facts: lines(value('facts')), allowed_answer: value('allowed'), forbidden_answer: lines(value('forbidden')) };
      });
      const result = await api('/evaluation/run', jsonOptions({ cases, mode: $('eval-mode').value, top_k: Number($('eval-top-k').value),
        rerank: $('eval-rerank').checked, rewrite: $('eval-rewrite').checked, judge: $('eval-judge').checked,
        baseline_id: $('eval-baseline').value.trim() || null, max_drop: Number($('eval-max-drop').value) }, 'POST', 3600000));
      evaluationResult = result;
      const heading = element('p', 'status-text', result.passed
        ? (result.config.baseline_id ? 'Regression check passed' : 'Evaluation completed') : 'Evaluation needs attention');
      heading.dataset.tone = result.passed ? 'good' : 'bad';
      $('evaluation-results').replaceChildren(heading, element('p', 'helper', `Evaluation ID: ${result.id}`),
        table(['Metric', 'Score'], Object.entries(result.summary).map(([name, value]) => [name, Number(value).toFixed(3)])));
      if (result.regressions.length) $('evaluation-results').append(element('p', 'error', `Regressions: ${result.regressions.join(', ')}`));
      result.failures.forEach((failure) => $('evaluation-results').append(element('p', 'error', `Question ${failure.case + 1}: ${failure.error}`)));
      if (result.cases.length) $('evaluation-results').append(element('h2', '', 'Per-question results'), table(['Question', 'Metrics', 'Warnings'], result.cases.map((row) =>
        [cases[row.case]?.query, Object.entries(row.metrics).map(([key, value]) => `${key}: ${Number(value).toFixed(3)}`).join(' · '), (row.warnings || []).join('; ') || '—'])));
      $('evaluation-results').append(element('p', 'helper', result.note), rawDetails(result));
      message('evaluation-message', 'Evaluation complete.');
    });
    $('eval-use-baseline').disabled = !evaluationResult?.passed;
    numberCases();
  });
  addCase();

  // Lab 10: bounded telemetry, refreshed only when requested or explicitly enabled.
  function renderTraces() {
    const rows = traceRows.filter((row) => !$('traces-errors-only').checked || row.status >= 400 || row.spans.some((span) => span.error));
    $('observability-traces').replaceChildren();
    rows.slice().reverse().forEach((row) => {
      const details = element('details', 'cache-entry');
      const heading = element('summary', 'trace-summary');
      heading.append(element('strong', '', `${row.method} ${row.route}`), element('span', '', `${row.status} · ${row.latency_ms} ms`));
      details.append(heading, element('p', 'helper', `Trace ID: ${row.id} · Input/output tokens: ${row.input_tokens}/${row.output_tokens}`),
        table(['Stage', 'Time (ms)', 'Error'], row.spans.map((span) => [span.name, span.latency_ms, span.error || '—'])));
      $('observability-traces').append(details);
    });
    if (!rows.length) $('observability-traces').append(element('div', 'state', 'No matching traces. Run a query or agent, then refresh.'));
  }

  async function loadMetrics() {
    if (metricsBusy) return;
    metricsBusy = true;
    $('observability-refresh').disabled = true;
    message('observability-message', 'Reading metrics and request traces…');
    const outcomes = await Promise.allSettled([api('/observability/metrics'), api('/observability/traces')]);
    const errors = [];
    if (outcomes[0].status === 'fulfilled') {
      const result = outcomes[0].value;
      const metrics = [['Requests', result.requests], ['P50 / P95 request latency', `${display(result.p50_ms)} / ${display(result.p95_ms)} ms`],
        ['P95 query / retrieval / model latency', `${display(result.query_p95_ms)} / ${display(result.retrieval_p95_ms)} / ${display(result.llm_p95_ms)} ms`],
        ['Server error rate', result.error_rate === null ? '—' : `${(result.error_rate * 100).toFixed(2)}%`],
        ['Input / output tokens', `${result.input_tokens} / ${result.output_tokens}`], ['Estimated total cost', result.estimated_cost],
        ['Estimated cost per query', result.estimated_cost_per_query], ['Unindexed documents', result.unindexed_documents], ['Maximum indexing lag', `${result.max_index_lag_seconds} seconds`]];
      const sloNames = { availability_99_9: 'Availability ≥ 99.9%', retrieval_under_500ms: 'Retrieval < 500 ms', query_under_5s: 'Query < 5 seconds', request_under_5s: 'Request < 5 seconds', index_lag_under_10min: 'Indexing lag < 10 minutes' };
      $('observability-metrics').replaceChildren(element('p', 'helper', result.window), table(['Metric', 'Value'], metrics), element('h2', '', 'SLO checks'),
        table(['Target', 'Observed window'], Object.entries(result.slo).map(([key, value]) => [sloNames[key] || key, value === null ? 'No samples' : value ? 'Met' : 'Not met'])));
      if (result.freshness?.length) $('observability-metrics').append(element('h2', '', 'Knowledge freshness'), table(['Document', 'Usable', 'Freshness score'],
        result.freshness.map((row) => [sourceButton(row.knowledge_id), row.usable ? 'Yes' : 'No', row.freshness_score])));
      $('observability-metrics').append(rawDetails(result));
    } else errors.push(errorMessage(outcomes[0].reason));
    if (outcomes[1].status === 'fulfilled') { traceRows = outcomes[1].value; renderTraces(); }
    else errors.push(errorMessage(outcomes[1].reason));
    message('observability-message', errors.length ? errors.join(' · ') : `Updated ${new Date().toLocaleTimeString()}.`, !!errors.length);
    metricsBusy = false;
    $('observability-refresh').disabled = false;
  }

  function updateMetricsTimer() {
    clearInterval(metricsTimer);
    if (state.view === 'observability' && $('observability-auto').checked) {
      metricsTimer = setInterval(() => { if (!document.hidden) loadMetrics(); }, 10000);
    }
  }
  $('observability-refresh').addEventListener('click', loadMetrics);
  $('observability-auto').addEventListener('change', updateMetricsTimer);
  $('traces-errors-only').addEventListener('change', renderTraces);

  // Labs 11/12 share controls; their API payloads and execution states stay separate.
  const agents = {};
  function setupAgent(prefix, durable) {
    const base = durable ? '/agent/v2/runs' : '/agent/runs';
    const root = $(`${prefix}-workspace`);
    const control = { prefix, durable, base, busy: false, run: null };
    agents[prefix] = control;
    root.innerHTML = `<form id="${prefix}-form" class="lab-panel">
      <label>Example goal<select id="${prefix}-example"><option value="search">Answer a knowledge question</option>${durable ? '' : '<option value="calculate">Calculate 15% of 1200</option><option value="combined">Search contract, then calculate</option>'}<option value="followup">Create a follow-up · requires approval</option></select></label>
      <label>Goal<textarea id="${prefix}-goal" rows="3" maxlength="2000" required></textarea></label>
      ${durable ? '<p class="helper">Execution follows intake → retrieve → plan → verify → approval when needed → execute → finalize. Checkpoints survive API restarts.</p>' : `<details class="context"><summary>Execution settings</summary><div class="form-grid"><label>Model interaction<select id="${prefix}-mode"><option value="structured">Structured JSON actions</option><option value="native_tools">Native tool calling · model support required</option></select></label><label>Maximum steps<input id="${prefix}-steps" type="number" min="1" max="12" value="6" required></label><label>Timeout (seconds)<input id="${prefix}-timeout" type="number" min="5" max="300" value="120" required></label><label>Token budget<input id="${prefix}-tokens" type="number" min="1000" max="100000" value="50000" required></label><label>Cost budget<input id="${prefix}-cost" type="number" min="0.01" max="20" step="0.01" value="1" required></label><label>Approval validity (seconds)<input id="${prefix}-ttl" type="number" min="60" max="86400" value="3600" required></label><label class="check-label"><input id="${prefix}-require-search" type="checkbox"> Require knowledge search first</label><label class="check-label"><input id="${prefix}-require-calculate" type="checkbox"> Require calculator</label></div></details>`}
      <button type="submit" class="primary">Run agent</button><p class="helper">Knowledge searches use indexed RAG documents. Creating a follow-up pauses for your approval.</p>
    </form><form id="${prefix}-load-form" class="run-loader"><label>Run ID<input id="${prefix}-run-id" class="run-id" placeholder="Paste a previous run ID to inspect or recover it" required></label><button type="submit">Load run</button><button id="${prefix}-copy" type="button" disabled>Copy ID</button></form>
    <div id="${prefix}-message" class="lab-message" role="status" aria-live="polite"></div><div id="${prefix}-result" class="lab-output" aria-live="polite"></div>
    <div id="${prefix}-approval" class="approval-review" hidden></div><button id="${prefix}-resume" type="button" hidden>Resume interrupted run</button>
    <div class="lab-divider"><div class="lab-toolbar"><h2>Local follow-up tasks</h2><button id="${prefix}-followups-refresh" type="button">Refresh tasks</button></div><div id="${prefix}-followups" class="lab-output"><p class="helper">Load tasks to see the results of approved writes.</p></div></div>
    ${durable ? `<div class="lab-divider"><div class="lab-toolbar"><h2>Your agent memories</h2><button id="${prefix}-memories-refresh" type="button">Refresh memories</button></div><div id="${prefix}-memories" class="lab-output"></div></div>` : `<details class="context"><summary id="${prefix}-tools-toggle">Available tool schemas</summary><div id="${prefix}-tools"></div></details>`}`;

    function setExample() {
      const choice = $(`${prefix}-example`).value;
      $(`${prefix}-goal`).value = { search: 'How many days of annual leave do full-time employees receive?', calculate: 'Calculate 1200 multiplied by 0.15 and return the result.',
        combined: 'Find the dollar value of Contract C-101 and calculate 15 percent of that amount.',
        followup: 'Create a follow-up task asking HR to confirm the annual leave policy for full-time employees.' }[choice];
      if (!durable) {
        $(`${prefix}-require-search`).checked = choice === 'search' || choice === 'combined';
        $(`${prefix}-require-calculate`).checked = choice === 'calculate' || choice === 'combined';
      }
    }
    $(`${prefix}-example`).addEventListener('change', setExample);
    setExample();
    $(`${prefix}-form`).addEventListener('submit', (event) => {
      event.preventDefault();
      runAgentAction(control, async () => {
        const payload = { goal: $(`${prefix}-goal`).value.trim() };
        if (!durable) Object.assign(payload, { mode: $(`${prefix}-mode`).value, max_steps: Number($(`${prefix}-steps`).value),
          timeout_seconds: Number($(`${prefix}-timeout`).value), token_budget: Number($(`${prefix}-tokens`).value), cost_budget: Number($(`${prefix}-cost`).value),
          approval_ttl_seconds: Number($(`${prefix}-ttl`).value), required_tools: [
            ...($(`${prefix}-require-search`).checked ? ['search_knowledge'] : []), ...($(`${prefix}-require-calculate`).checked ? ['calculate'] : [])] });
        return api(base, jsonOptions(payload));
      }, 'Running the agent… Local model calls can take a few minutes.', true);
    });
    $(`${prefix}-load-form`).addEventListener('submit', (event) => {
      event.preventDefault();
      runAgentAction(control, () => api(endpoint(base, $(`${prefix}-run-id`).value.trim())), 'Loading saved run…', true);
    });
    $(`${prefix}-resume`).addEventListener('click', () => runAgentAction(control,
      () => api(`${endpoint(base, control.run.id)}/resume`, { method: 'POST', timeout: 600000 }), 'Resuming from saved execution state…'));
    $(`${prefix}-copy`).addEventListener('click', async () => {
      try { await navigator.clipboard.writeText($(`${prefix}-run-id`).value); message(`${prefix}-message`, 'Run ID copied.'); }
      catch { $(`${prefix}-run-id`).select(); message(`${prefix}-message`, 'Run ID selected. Use your browser’s copy command.'); }
    });
    $(`${prefix}-followups-refresh`).addEventListener('click', () => loadFollowups(control));
    if (durable) $(`${prefix}-memories-refresh`).addEventListener('click', () => loadMemories(control));
    else $(`${prefix}-tools-toggle`).parentElement.addEventListener('toggle', async (event) => {
      if (!event.currentTarget.open) return;
      try { $(`${prefix}-tools`).replaceChildren(rawDetails(await api('/agent/tools'), 'Tool definitions')); $(`${prefix}-tools`).firstChild.open = true; }
      catch (error) { message(`${prefix}-message`, errorMessage(error), true); }
    });
  }

  async function runAgentAction(control, operation, pending, replacingRun = false) {
    if (control.busy) return;
    const prefix = control.prefix;
    control.busy = true;
    if (replacingRun) {
      control.run = null;
      $(`${prefix}-result`).replaceChildren();
      $(`${prefix}-approval`).replaceChildren();
      $(`${prefix}-approval`).hidden = $(`${prefix}-resume`).hidden = true;
      $(`${prefix}-copy`).disabled = true;
    }
    const controls = [...$(`${prefix}-workspace`).querySelectorAll('button,input,textarea,select')];
    const prior = controls.map((input) => input.disabled);
    controls.forEach((input) => { input.disabled = true; });
    $(`${prefix}-form`).setAttribute('aria-busy', 'true');
    message(`${prefix}-message`, pending, false, true);
    let result;
    try {
      result = await operation();
      control.run = result;
      message(`${prefix}-message`, `Run ${result.id}: ${result.status}.`);
    } catch (error) { message(`${prefix}-message`, errorMessage(error), true); }
    finally {
      control.busy = false;
      controls.forEach((input, index) => { input.disabled = prior[index]; });
      $(`${prefix}-form`).removeAttribute('aria-busy');
      $(`${prefix}-message`).dataset.busy = 'false';
      if (result) renderRun(control);
    }
  }

  function renderRun(control) {
    const { prefix, run, durable } = control;
    $(`${prefix}-run-id`).value = run.id;
    $(`${prefix}-copy`).disabled = false;
    const status = element('p', 'status-text', run.status.replaceAll('_', ' '));
    status.dataset.tone = run.status === 'completed' ? 'good' : ['awaiting_approval', 'running', 'interrupted'].includes(run.status) ? 'pending' : 'bad';
    const result = $(`${prefix}-result`);
    result.replaceChildren(status);
    if (run.answer) result.append(element('h2', '', 'Answer'), element('p', 'agent-answer', run.answer));
    if (run.error || run.last_error) result.append(element('p', 'error', `Execution error: ${run.error || run.last_error}`));
    if (run.verification) {
      const { problems = [], warnings = [] } = run.verification;
      result.append(element('p', problems.length ? 'error' : 'helper', problems.length ? `Verification blocked this run: ${problems.join(', ')}` : 'Verification checks passed.'));
      if (warnings.length) result.append(element('p', 'helper', `Verification warnings: ${warnings.join(', ')}`));
    }
    if (run.citations?.length) {
      result.append(element('h2', '', 'Source evidence'));
      run.citations.forEach((citation) => {
        const item = element('details', 'rag-evidence');
        item.append(element('summary', '', `[${citation.id ?? citation.number ?? ''}] ${nameOf(citation.document_id)}`), element('blockquote', '', citation.text || ''), sourceButton(citation.document_id));
        result.append(item);
      });
    }
    const steps = durable ? run.events || [] : run.steps || [];
    if (steps.length) result.append(element('h2', '', durable ? 'Execution graph' : 'Tool steps'), table(durable ? ['Node', 'Details', 'Time'] : ['Step', 'Tool', 'Status', 'Risk'], steps.map((step) => durable
      ? [step.node, Object.entries(step).filter(([key]) => !['node', 'at'].includes(key)).map(([key, value]) => `${key}: ${typeof value === 'object' ? JSON.stringify(value) : value}`).join(' · ') || '—', new Date(step.at).toLocaleTimeString()]
      : [step.step, step.tool || 'Planning', step.status, step.risk || '—'])));
    if (run.receipt) result.append(element('h2', '', 'Write receipt'), element('p', 'helper', `Follow-up ID: ${run.receipt.followup_id} · Reused existing write: ${run.receipt.reused_existing ? 'yes' : 'no'}`));
    if (durable && run.next?.length) result.append(element('p', 'helper', `Next checkpoint: ${run.next.join(', ')}`));
    if (!durable) result.append(element('p', 'helper', `Reserved tokens: ${run.tokens_reserved} · Estimated cost: ${run.estimated_cost} · Elapsed: ${Number(run.elapsed_seconds).toFixed(1)} s`));
    result.append(rawDetails(run));
    const approval = $(`${prefix}-approval`);
    approval.replaceChildren();
    const pending = durable ? run.approval_request : run.pending;
    approval.hidden = run.status !== 'awaiting_approval' || !pending;
    if (!approval.hidden) {
      approval.append(element('h2', '', 'Review the proposed follow-up'), element('p', 'helper', `Run: ${run.id}`), element('p', 'helper', pending.impact || 'Creates one local follow-up task after your approval.'),
        element('strong', '', pending.arguments.title), element('p', 'agent-answer', pending.arguments.description),
        element('p', 'helper', `Expires: ${new Date(pending.expires_at).toLocaleString()}`), element('p', 'helper', `Idempotency key: ${pending.idempotency_key}`));
      (pending.evidence || []).forEach((item) => approval.append(element('blockquote', '', item.text), sourceButton(item.document_id)));
      const actions = element('div', 'lab-actions');
      for (const approved of [true, false]) {
        const button = element('button', approved ? 'primary' : '', approved ? 'Approve & create task' : 'Reject task');
        button.type = 'button';
        button.addEventListener('click', async () => {
          await runAgentAction(control, () => api(`${endpoint(control.base, control.run.id)}/approval`, jsonOptions({ approved })), approved ? 'Approving the displayed task and continuing…' : 'Rejecting the displayed task…');
          await loadFollowups(control);
        });
        actions.append(button);
      }
      approval.append(actions);
    }
    $(`${prefix}-resume`).hidden = !(durable ? run.status === 'interrupted' : run.status === 'running');
  }

  async function loadFollowups(control) {
    const target = $(`${control.prefix}-followups`);
    try {
      const rows = await api('/agent/followups');
      target.replaceChildren(rows.length ? table(['Task', 'Description', 'Approved by', 'Run'], rows.map((row) => [row.title, row.description, row.approved_by, row.run_id]))
        : element('p', 'helper', 'No tasks yet. A proposed write must be approved before a task appears here.'));
    } catch (error) { target.replaceChildren(element('p', 'error', errorMessage(error))); }
  }

  async function loadMemories(control) {
    const target = $(`${control.prefix}-memories`);
    try {
      const rows = await api('/agent/memories');
      target.replaceChildren();
      rows.forEach((memory) => {
        const article = element('article', 'result');
        article.append(element('strong', '', memory.kind), element('p', '', memory.text),
          element('p', 'helper', `Source: ${memory.source} · Expires: ${new Date(memory.expires_at).toLocaleDateString()}`));
        const forget = element('button', '', 'Forget this memory');
        forget.type = 'button';
        forget.addEventListener('click', async () => {
          forget.disabled = true;
          try { await api(endpoint('/agent/memories', memory.id), { method: 'DELETE' }); await loadMemories(control); }
          catch (error) { message(`${control.prefix}-message`, errorMessage(error), true); forget.disabled = false; }
        });
        article.append(forget);
        target.append(article);
      });
      if (!rows.length) target.append(element('p', 'helper', 'No saved memories yet. Complete a durable run first.'));
      else target.append(rawDetails(rows, 'Memory records'));
    } catch (error) { target.replaceChildren(element('p', 'error', errorMessage(error))); }
  }
  setupAgent('agent', false);
  setupAgent('durable-agent', true);

  async function navigate(view) {
    updateMetricsTimer();
    if (!labViews.has(view)) return;
    const statusId = { graph: 'graph-message', governance: 'governance-message', evaluation: 'evaluation-message',
      observability: 'observability-message', agent: 'agent-message', 'durable-agent': 'durable-agent-message' }[view];
    try {
      await loadLibrary();
      if (state.view !== view) return;
      if (view === 'governance' && governanceLoadedId !== $('governance-document').value) await loadAsset();
      if (view === 'observability') await loadMetrics();
    } catch (error) { message(statusId, errorMessage(error), true); }
  }

  window.labWorkspace = { navigate, isBusy: () => metricsBusy || Object.values(agents).some((control) => control.busy),
    resetAccess() {
      libraryPromise = undefined; library = []; governanceLoadedId = ''; evaluationResult = null; traceRows = [];
      documentSelections.clear(); governanceRequest++;
      renderAsset(null);
      $('governance-fields').disabled = true;
      document.querySelectorAll('.document-picker').forEach(populatePicker);
      document.querySelectorAll('.lab-output').forEach((output) => output.replaceChildren());
      document.querySelectorAll('.lab-message').forEach((output) => { output.textContent = ''; });
      $('graph-extraction').value = $('eval-baseline').value = '';
      $('gov-citation-text').value = '';
      $('governance-citation-result').replaceChildren();
      $('eval-use-baseline').disabled = true;
      for (const control of Object.values(agents)) {
        control.run = null;
        $(`${control.prefix}-run-id`).value = '';
        $(`${control.prefix}-approval`).replaceChildren();
        $(`${control.prefix}-approval`).hidden = $(`${control.prefix}-resume`).hidden = true;
        $(`${control.prefix}-copy`).disabled = true;
      }
    }, invalidateDocuments() { libraryPromise = undefined; governanceLoadedId = ''; }, selectDocument(view, id) {
    const picker = $(`${view}-document`);
    if ([...picker.options].some((option) => option.value === id)) picker.value = id;
    else documentSelections.set(picker.id, id);
  } };
  navigate(state.view);
})();
