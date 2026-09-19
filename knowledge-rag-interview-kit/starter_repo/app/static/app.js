// Every data request goes to FastAPI on this origin, never to a database.
const $ = (id) => document.getElementById(id);
const state = { documentPage: 1, elasticPage: 1, searchPage: 1, search: null, redisCursor: 0, view: 'documents' };
let documentRequest = 0;
let redisRequest = 0;
let searchRequest = 0;
let elasticRequest = 0;

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

async function api(path, options = {}) {
  const { timeout = 30000, ...requestOptions } = options;
  const response = await fetch(path, {
    ...requestOptions,
    headers: { ...(options.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }), ...options.headers },
    signal: AbortSignal.timeout(timeout),
  });
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = body?.detail;
    const message = Array.isArray(detail)
      ? detail.map((item) => `${item.loc.slice(1).join('.')}: ${item.msg}`).join('; ')
      : typeof detail === 'string' ? detail : `Request failed (${response.status}). Check the backend services.`;
    throw new Error(message);
  }
  return body;
}

function errorMessage(error) {
  if (error.name === 'TimeoutError') return 'The request timed out. Check the backend and try again.';
  if (error instanceof TypeError) return 'Could not reach the backend. Check that the API is running.';
  return error.message;
}

function notice(message, error = false) {
  $('notice').textContent = message;
  $('notice').className = error ? 'error' : '';
  $('notice').hidden = false;
}

function metadata(raw) {
  let value;
  try { value = JSON.parse(raw.trim() || '{}'); }
  catch { throw new Error('Metadata must be valid JSON, for example {"team":"finance"}.'); }
  if (!value || Array.isArray(value) || typeof value !== 'object') throw new Error('Metadata must be a JSON object.');
  return value;
}

const tags = (raw) => raw.split(',').map((tag) => tag.trim()).filter(Boolean);
const formatDate = (raw) => new Date(raw).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });

function tagList(values) {
  const list = element('div', 'tag-list');
  for (const value of values) list.append(element('span', 'tag', value));
  if (!values.length) list.append(element('span', '', '—'));
  return list;
}

async function showDocument(id) {
  try {
    const document = await api(`/documents/${encodeURIComponent(id)}`);
    $('detail-title').textContent = document.title;
    $('detail-source').textContent = `${document.source} · ${formatDate(document.created_at)} · ${document.id}`;
    $('detail-content').textContent = document.content;
    $('detail-json').textContent = JSON.stringify(document, null, 2);
    $('detail-rag').onclick = () => {
      $('rag-document-id').value = document.id;
      $('rag-index-status').textContent = `Selected: ${document.title}. Click Index document to prepare it for RAG.`;
      $('rag-index-form').closest('details').open = true;
      $('document-dialog').close();
      location.hash = 'rag';
    };
    if (!$('document-dialog').open) $('document-dialog').showModal();
  } catch (error) { notice(errorMessage(error), true); }
}

function documentButton(document) {
  const button = element('button', 'document-title', document.title);
  button.type = 'button';
  button.addEventListener('click', () => showDocument(document.id));
  return button;
}

async function loadDocuments() {
  const request = ++documentRequest;
  $('documents-state').hidden = false;
  $('documents-state').textContent = 'Loading documents…';
  $('documents-table').hidden = true;
  $('documents-prev').disabled = $('documents-next').disabled = true;
  try {
    const documents = await api(`/documents?page=${state.documentPage}&page_size=20`);
    if (request !== documentRequest) return;
    $('documents-body').replaceChildren();
    for (const document of documents) {
      const row = element('tr');
      const title = element('td');
      title.append(documentButton(document), element('p', 'excerpt', document.content.slice(0, 160)));
      const tagCell = element('td');
      tagCell.append(tagList(document.tags));
      row.append(title, element('td', '', document.source), tagCell, element('td', '', formatDate(document.created_at)));
      $('documents-body').append(row);
    }
    $('documents-state').hidden = documents.length > 0;
    $('documents-state').textContent = state.documentPage === 1
      ? 'No documents yet. Create your first document to start building your library.'
      : 'No more documents. Return to the previous page.';
    $('documents-table').hidden = !documents.length;
    $('documents-page').textContent = `Page ${state.documentPage} · ${documents.length} records`;
    $('documents-next').disabled = documents.length < 20;
  } catch (error) { $('documents-state').textContent = errorMessage(error); }
  finally { if (request === documentRequest) $('documents-prev').disabled = state.documentPage <= 1; }
}

async function runSearch(page = 1) {
  const request = ++searchRequest;
  const button = $('search-form').querySelector('button[type="submit"]');
  button.disabled = true;
  button.textContent = 'Searching…';
  $('search-pagination').hidden = $('context-panel').hidden = true;
  $('search-results').replaceChildren(element('div', 'state', 'Searching your documents…'));
  try {
    const result = await api('/query', { method: 'POST', body: JSON.stringify({ ...state.search, page, page_size: 10 }) });
    if (request !== searchRequest) return;
    state.searchPage = page;
    $('search-summary').textContent = `${result.total} matching documents`;
    $('search-results').replaceChildren();
    for (const hit of result.results) {
      const article = element('article', 'result');
      const top = element('div', 'result-top');
      top.append(documentButton(hit.document), element('span', 'score', `score ${hit.score.toFixed(3)}`));
      const meta = element('div', 'result-meta');
      meta.append(element('span', '', hit.document.source), tagList(hit.document.tags));
      article.append(top, element('p', '', hit.document.content.slice(0, 500) + (hit.document.content.length > 500 ? '…' : '')), meta);
      $('search-results').append(article);
    }
    if (!result.results.length) $('search-results').append(element('div', 'state', 'No matches. Try a different phrase or remove some filters.'));
    $('query-context').textContent = result.context;
    $('query-citations').textContent = JSON.stringify(result.citations, null, 2);
    $('context-panel').hidden = !result.results.length;
    $('search-pagination').hidden = result.total === 0;
    $('search-page').textContent = `Page ${page} of ${Math.max(1, Math.ceil(result.total / 10))}`;
    $('search-prev').disabled = page <= 1;
    $('search-next').disabled = page * 10 >= result.total;
  } catch (error) {
    if (request === searchRequest) {
      $('search-summary').textContent = 'Search unavailable';
      $('search-results').replaceChildren(element('div', 'state', errorMessage(error)));
    }
  } finally {
    if (request === searchRequest) { button.disabled = false; button.textContent = 'Search →'; }
  }
}

function updateTtls() {
  document.querySelectorAll('[data-expires]').forEach((badge) => {
    const remaining = Math.max(0, Math.ceil((Number(badge.dataset.expires) - Date.now()) / 1000));
    badge.textContent = remaining ? `~${remaining}s remaining` : 'Expired · refresh';
    badge.classList.toggle('expired', remaining === 0);
  });
}

async function loadRedis(cursor = 0) {
  const request = ++redisRequest;
  $('redis-state').hidden = false;
  $('redis-state').textContent = 'Reading cache…';
  $('redis-more').hidden = true;
  $('redis-entries').replaceChildren();
  try {
    const result = await api(`/inspector/redis?cursor=${cursor}`);
    if (request !== redisRequest) return;
    state.redisCursor = result.next_cursor;
    for (const entry of result.entries) {
      const item = element('details', 'cache-entry');
      const summary = element('summary');
      const heading = element('div');
      const query = entry.value && typeof entry.value === 'object' ? entry.value.query : null;
      heading.append(element('strong', '', query || 'Cached response'), element('code', '', entry.key));
      const ttl = element('span', 'ttl', 'No expiry');
      if (entry.ttl_seconds >= 0) ttl.dataset.expires = Date.now() + entry.ttl_seconds * 1000;
      summary.append(heading, ttl);
      const value = typeof entry.value === 'string' ? entry.value : JSON.stringify(entry.value, null, 2);
      item.append(summary, element('p', 'helper', `${entry.size_bytes.toLocaleString()} bytes${entry.truncated ? ' · preview truncated to 64 KiB' : ''}`), element('pre', '', value));
      $('redis-entries').append(item);
    }
    $('redis-state').hidden = result.entries.length > 0;
    $('redis-state').textContent = result.next_cursor
      ? 'No app cache keys in this scan batch. Continue to the next batch.'
      : 'No active cache entries in this batch. Run a search and refresh within 30 seconds.';
    $('redis-more').hidden = !result.next_cursor;
    updateTtls();
  } catch (error) { if (request === redisRequest) $('redis-state').textContent = errorMessage(error); }
}

async function loadHealth() {
  try {
    const health = await api('/health');
    $('connections').replaceChildren();
    for (const [key, name] of [['storage', 'PostgreSQL'], ['cache', 'Redis'], ['search', 'Elasticsearch']]) {
      const ok = health[key] === 'ok';
      const row = element('div', 'connection');
      row.append(element('span', `dot${ok ? '' : ' bad'}`), element('span', '', name), element('span', '', ok ? 'Connected' : 'Unavailable'));
      $('connections').append(row);
    }
  } catch { $('connections').textContent = 'Backend unavailable'; }
}

async function loadElastic() {
  const request = ++elasticRequest;
  $('elastic-prev').disabled = $('elastic-next').disabled = true;
  $('elastic-mapping').textContent = '';
  $('elastic-records').replaceChildren(element('div', 'state', 'Reading the Elasticsearch index…'));
  try {
    const result = await api(`/inspector/elasticsearch?page=${state.elasticPage}`);
    if (request !== elasticRequest) return;
    $('elastic-summary').textContent = `${result.index_name} · ${result.total} documents`;
    $('elastic-mapping').textContent = JSON.stringify(result.mappings, null, 2);
    $('elastic-records').replaceChildren();
    for (const record of result.documents) {
      const item = element('details', 'cache-entry');
      const summary = element('summary');
      const heading = element('div');
      heading.append(element('strong', '', record.source.title || record.id), element('code', '', record.id));
      summary.append(heading, element('span', 'tag', record.source.source || 'document'));
      item.append(summary, element('pre', '', JSON.stringify(record.source, null, 2)));
      $('elastic-records').append(item);
    }
    if (!result.documents.length) $('elastic-records').append(element('div', 'state', 'No indexed documents. Create a document to see it here.'));
    $('elastic-page').textContent = `Page ${state.elasticPage} · ${result.total} documents`;
    $('elastic-next').disabled = state.elasticPage * 20 >= result.total || state.elasticPage >= 500;
  } catch (error) {
    if (request === elasticRequest) $('elastic-records').replaceChildren(element('div', 'state', errorMessage(error)));
  } finally { if (request === elasticRequest) $('elastic-prev').disabled = state.elasticPage <= 1; }
}

let ragEnabled = false;
let ragAsking = false;
let ragIndexing = false;

function updateRagButtons() {
  $('rag-ask-button').disabled = !ragEnabled || ragAsking;
  $('rag-index-button').disabled = !ragEnabled || ragIndexing;
}

async function loadRagStatus() {
  $('rag-refresh').disabled = true;
  try {
    const config = await api('/rag/status');
    ragEnabled = config.enabled;
    $('rag-status').textContent = config.enabled
      ? `RAG enabled · Embeddings: ${config.embedding_model} · Answers: ${config.chat_model}. Models and Qdrant must be running.`
      : 'RAG is disabled. You can upload PDFs now; enable RAG to index and ask questions.';
    $('rag-setup').open = !config.enabled;
  } catch (error) {
    ragEnabled = false;
    $('rag-status').textContent = error.message === 'Not Found'
      ? 'This API is running an older version. Restart it with RAG_ENABLED=true to load the RAG endpoints.'
      : errorMessage(error);
    $('rag-setup').open = true;
  } finally {
    updateRagButtons();
    $('rag-refresh').disabled = false;
  }
}

$('rag-refresh').addEventListener('click', loadRagStatus);
$('rag-pdf-file').addEventListener('change', (event) => {
  const file = event.currentTarget.files?.[0];
  if (!file) {
    $('rag-upload-status').textContent = 'No PDF selected.';
    return;
  }

  const isPdf = file.type === 'application/pdf'
    || file.name.toLowerCase().endsWith('.pdf');
  if (!isPdf) {
    event.currentTarget.value = '';
    $('rag-upload-status').textContent = 'Please choose a PDF file.';
    return;
  }
  if (file.size > 10 * 1024 * 1024) {
    event.currentTarget.value = '';
    $('rag-upload-status').textContent = 'This PDF is larger than 10 MiB.';
    return;
  }

  const size = file.size < 1024 * 1024
    ? Math.max(1, Math.round(file.size / 1024)) + ' KiB'
    : (file.size / 1024 / 1024).toFixed(1) + ' MiB';
  $('rag-upload-status').textContent = file.name
    + ' selected (' + size + '). Click Upload PDF to continue.';
});
$('rag-upload-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const data = new FormData(form);
  const button = form.querySelector('button');
  const file = data.get('file');
  if (!file.size || file.size > 10 * 1024 * 1024) {
    $('rag-upload-status').textContent = 'Choose a non-empty PDF of at most 10 MiB.';
    return;
  }
  button.disabled = true;
  $('rag-upload-status').textContent = 'Uploading and extracting PDF text…';
  try {
    const document = await api('/rag/pdf', { method: 'POST', body: data, timeout: 180000 });
    $('rag-document-id').value = document.id;
    $('rag-upload-status').textContent = `Saved “${document.title}”. Next: click Index document. ID: ${document.id}`;
    $('rag-index-status').textContent = 'PDF saved. Indexing has not started yet.';
    form.reset();
  } catch (error) {
    $('rag-upload-status').textContent = errorMessage(error) + ' If the request timed out, check the document library before uploading again.';
  } finally { button.disabled = false; }
});

$('rag-index-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  if (ragIndexing || !ragEnabled) return;
  const id = $('rag-document-id').value.trim();
  if (!id) return;
  ragIndexing = true;
  updateRagButtons();
  $('rag-index-status').textContent = 'Splitting text and generating embeddings… This may take a few minutes.';
  try {
    const result = await api(`/rag/documents/${encodeURIComponent(id)}/index`, {
      method: 'POST', timeout: 600000,
      body: JSON.stringify({ strategy: $('rag-strategy').value, chunk_size: 800, overlap: 80 }),
    });
    $('rag-index-status').textContent = `Indexed “${result.document.title}”: ${result.chunks} chunks. Ready for questions.`;
  } catch (error) { $('rag-index-status').textContent = errorMessage(error); }
  finally { ragIndexing = false; updateRagButtons(); }
});

$('rag-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  if (ragAsking || !ragEnabled) return;
  const query = $('rag-question').value.trim();
  if (!query) { $('rag-question').focus(); return; }
  ragAsking = true;
  updateRagButtons();
  $('rag-result').setAttribute('aria-busy', 'true');
  $('rag-result').replaceChildren(element('div', 'state', 'Retrieving evidence and generating a local answer…'));
  try {
    const result = await api('/rag/query', {
      method: 'POST', timeout: 600000,
      body: JSON.stringify({ query, top_k: Number($('rag-top-k').value),
        score_threshold: Number($('rag-threshold').value),
        source: $('rag-source').value.trim() || null, tags: tags($('rag-tags').value) }),
    });
    const article = element('article', 'result');
    article.append(element('h2', '', 'Answer'), element('p', 'helper', `Question: ${result.query} · Model: ${result.model}`),
      element('div', 'rag-answer', result.answer));
    if (result.citations.length) {
      article.append(element('h3', '', 'Source evidence'));
      for (const citation of result.citations) {
        const evidence = element('details', 'rag-evidence');
        evidence.append(element('summary', '', `[${citation.number}] ${citation.title} · page ${citation.page}`),
          element('blockquote', '', citation.text),
          element('p', 'helper', `Source: ${citation.source} · Similarity: ${citation.score.toFixed(3)}`));
        const open = element('button', '', 'Open source document');
        open.type = 'button';
        open.addEventListener('click', () => showDocument(citation.document_id));
        evidence.append(open);
        article.append(evidence);
      }
      const context = element('details', 'context');
      context.append(element('summary', '', 'View the context sent to the model'), element('pre', '', result.context));
      article.append(context);
    } else {
      article.append(element('p', 'helper', 'No supporting chunks found. Index a document, remove filters, or adjust the similarity threshold.'));
    }
    $('rag-result').replaceChildren(article);
  } catch (error) {
    $('rag-result').replaceChildren(element('div', 'error', errorMessage(error)));
  } finally {
    ragAsking = false;
    $('rag-result').removeAttribute('aria-busy');
    updateRagButtons();
  }
});

function navigate() {
  const names = { documents: 'Documents', search: 'Search & query', rag: 'RAG answers', redis: 'Redis cache', elastic: 'Elasticsearch' };
  state.view = Object.hasOwn(names, location.hash.slice(1)) ? location.hash.slice(1) : 'documents';
  document.querySelectorAll('.view').forEach((view) => { view.hidden = view.id !== `view-${state.view}`; });
  document.querySelectorAll('[data-view]').forEach((link) => {
    if (link.dataset.view === state.view) link.setAttribute('aria-current', 'page');
    else link.removeAttribute('aria-current');
  });
  $('breadcrumb').textContent = names[state.view];
  if (state.view === 'documents') loadDocuments();
  if (state.view === 'redis') loadRedis();
  if (state.view === 'elastic') loadElastic();
  if (state.view === 'rag') loadRagStatus();
  loadHealth();
}

$('create-open').addEventListener('click', () => { $('create-error').hidden = true; $('create-dialog').showModal(); });
$('create-close').addEventListener('click', () => $('create-dialog').close());
$('detail-close').addEventListener('click', () => $('document-dialog').close());
$('create-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const button = form.querySelector('button[type="submit"]');
  $('create-error').hidden = true;
  let payload;
  try {
    const values = Object.fromEntries(new FormData(form));
    payload = { ...values, tags: tags(values.tags), metadata: metadata(values.metadata) };
  } catch (error) { $('create-error').textContent = error.message; $('create-error').hidden = false; return; }
  button.disabled = true;
  button.textContent = 'Saving…';
  try {
    const document = await api('/documents', { method: 'POST', body: JSON.stringify(payload) });
    form.reset();
    $('create-dialog').close();
    state.documentPage = 1;
    notice(`“${document.title}” created and indexed. Ready to search.`);
    loadDocuments();
  } catch (error) { $('create-error').textContent = errorMessage(error); $('create-error').hidden = false; }
  finally { button.disabled = false; button.textContent = 'Create document'; }
});
$('documents-refresh').addEventListener('click', loadDocuments);
$('documents-prev').addEventListener('click', () => { state.documentPage--; loadDocuments(); });
$('documents-next').addEventListener('click', () => { state.documentPage++; loadDocuments(); });
$('search-form').addEventListener('submit', (event) => {
  event.preventDefault();
  try {
    const query = $('query').value.trim();
    if (!query) throw new Error('Enter a search phrase.');
    state.search = { query, source: $('filter-source').value.trim() || null, tags: tags($('filter-tags').value), metadata: metadata($('filter-metadata').value) };
    $('notice').hidden = true;
    runSearch();
  } catch (error) { notice(error.message, true); }
});
$('search-prev').addEventListener('click', () => runSearch(state.searchPage - 1));
$('search-next').addEventListener('click', () => runSearch(state.searchPage + 1));
$('redis-refresh').addEventListener('click', () => loadRedis());
$('redis-more').addEventListener('click', () => loadRedis(state.redisCursor));
$('elastic-refresh').addEventListener('click', loadElastic);
$('elastic-prev').addEventListener('click', () => { state.elasticPage--; loadElastic(); });
$('elastic-next').addEventListener('click', () => { state.elasticPage++; loadElastic(); });
document.querySelector('.skip').addEventListener('click', (event) => { event.preventDefault(); $('main').focus(); });
const kibana = new URL(location.href);
kibana.port = '5601'; kibana.pathname = '/'; kibana.search = ''; kibana.hash = '';
$('kibana-link').href = kibana.href;
api('/ui/config').then((config) => {
  $('mode').textContent = config.semantic_enabled ? 'Hybrid search' : 'BM25 · semantic off';
  $('index-name').textContent = config.index_name;
  $('elastic-query').textContent = `GET ${config.index_name}/_search\n{ "query": { "match_all": {} }, "size": 20 }\n\nGET ${config.index_name}/_mapping`;
}).catch(() => { $('mode').textContent = 'Search mode unavailable'; });
window.addEventListener('hashchange', navigate);
setInterval(updateTtls, 1000);
navigate();
