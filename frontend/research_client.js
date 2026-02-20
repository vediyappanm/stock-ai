/**
 * STK-ENGINE Research Streaming Client
 * Connects to the SSE endpoint and updates the dashboard UI in real time.
 *
 * Usage:
 *   import { runResearch } from './research_client.js';
 *   runResearch({ ticker: 'NVDA', exchange: 'NASDAQ' });
 */

const STATUS_MESSAGES = {
  starting:     { label: 'Initialising…',          progress: 5  },
  searching:    { label: 'Searching news sources…', progress: 20 },
  search_done:  { label: 'Sources collected',       progress: 35 },
  fetching:     { label: 'Fetching articles…',      progress: 50 },
  fetch_done:   { label: 'Content extracted',       progress: 62 },
  chunking:     { label: 'Building RAG chunks…',    progress: 70 },
  chunk_done:   { label: 'Chunks ready',            progress: 75 },
  reranking:    { label: 'Semantic reranking…',     progress: 82 },
  rerank_done:  { label: 'Reranking complete',      progress: 88 },
  synthesizing: { label: 'AI synthesis…',           progress: 95 },
  complete:     { label: 'Research complete ✅',    progress: 100 },
  cache_hit:    { label: 'Loaded from cache ⚡',    progress: 100 },
  error:        { label: 'Using fallback data ⚠️',  progress: 100 },
};

/**
 * Run research for a ticker and stream progress to the UI.
 *
 * @param {Object} opts
 * @param {string} opts.ticker        - Stock ticker, e.g. 'NVDA'
 * @param {string} opts.exchange      - Exchange, e.g. 'NASDAQ'
 * @param {string} [opts.companyName] - Optional company name
 * @param {Function} [opts.onProgress]- Called with (percent, label, rawEvent)
 * @param {Function} [opts.onResult]  - Called with final result object
 * @param {Function} [opts.onError]   - Called with error message
 * @returns {EventSource}             - EventSource instance (call .close() to cancel)
 */
export function runResearch({
  ticker,
  exchange = 'NASDAQ',
  companyName = '',
  onProgress = () => {},
  onResult = () => {},
  onError = () => {},
}) {
  const params = new URLSearchParams({
    ticker,
    exchange,
    company_name: companyName,
  });

  const url = `/api/research/stream?${params.toString()}`;
  const es = new EventSource(url);

  es.onmessage = (event) => {
    let data;
    try {
      data = JSON.parse(event.data);
    } catch {
      return; // Ignore malformed events
    }

    const status = data.status || 'unknown';
    const meta = STATUS_MESSAGES[status] || { label: status, progress: 0 };

    // Report progress
    onProgress(meta.progress, data.message || meta.label, data);

    // Terminal events
    if (status === 'complete' || status === 'cache_hit') {
      onResult(data.result);
      es.close();
      return;
    }

    if (status === 'error') {
      onError(data.message || 'Research failed');
      onResult(data.result); // Fallback result
      es.close();
      return;
    }
  };

  es.onerror = () => {
    onError('Connection to research stream lost');
    es.close();
  };

  return es;
}


/**
 * Render research result into standard dashboard elements.
 * Expects HTML elements with these IDs (create if missing):
 *   #research-synthesis, #research-catalysts, #research-sources,
 *   #research-sentiment, #research-confidence, #research-risk,
 *   #research-progress-bar, #research-progress-label
 *
 * @param {Object} result - Result from onResult callback
 */
export function renderResearchResult(result) {
  _setText('research-synthesis', result.synthesis || '—');
  _setText('research-sentiment', result.sentiment || 'neutral');
  _setText('research-confidence', `${Math.round((result.confidence_overall || 0) * 100)}%`);

  // Catalysts
  const catalystsList = document.getElementById('research-catalysts');
  if (catalystsList) {
    catalystsList.innerHTML = '';
    (result.catalysts || []).forEach((cat) => {
      const li = document.createElement('li');
      const conf = Math.round(cat.confidence * 100);
      const badge = `<span class="impact-${cat.impact}">${cat.impact}</span>`;
      const sourceRefs = cat.source_ids?.map(id => `<a href="${result.sources?.[id]?.url || '#'}" target="_blank">[${id}]</a>`).join('') || '';
      li.innerHTML = `${badge} ${cat.catalyst} ${sourceRefs} <small>${conf}% confidence</small>`;
      catalystsList.appendChild(li);
    });
  }

  // Risk factors
  const riskList = document.getElementById('research-risk');
  if (riskList) {
    riskList.innerHTML = '';
    (result.risk_factors || []).forEach((risk) => {
      const li = document.createElement('li');
      li.textContent = risk;
      riskList.appendChild(li);
    });
  }

  // Sources / citations
  const sourcesEl = document.getElementById('research-sources');
  if (sourcesEl) {
    sourcesEl.innerHTML = '';
    Object.entries(result.sources || {}).forEach(([id, src]) => {
      const a = document.createElement('a');
      a.href = src.url;
      a.target = '_blank';
      a.textContent = `[${id}] ${src.title || src.url}`;
      const div = document.createElement('div');
      div.appendChild(a);
      sourcesEl.appendChild(div);
    });
  }

  // Progress bar to 100%
  _setProgress(100, 'Research complete ✅');
}

/**
 * Update progress bar and label.
 * @param {number} percent 0-100
 * @param {string} label
 */
export function updateProgress(percent, label) {
  _setProgress(percent, label);
}

// ─── Private helpers ────────────────────────────────────────────────────────

function _setText(id, text) {
  const el = document.getElementById(id);
  if (el) el.textContent = text;
}

function _setProgress(percent, label) {
  const bar = document.getElementById('research-progress-bar');
  const lbl = document.getElementById('research-progress-label');
  if (bar) bar.style.width = `${percent}%`;
  if (lbl) lbl.textContent = label;
}
