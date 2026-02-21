const byId = (id) => document.getElementById(id);

const elements = {
  resultJson: byId("result-json"),
  summaryCards: byId("summary-cards"),
  workflowId: byId("workflow-id"),
  workflowView: byId("workflow-view"),
  healthView: byId("health-view"),
  btnWorkflowPoll: byId("btn-workflow-poll"),
  explanationView: byId("explanation-view"),
  tickerMeta: byId("result-ticker-meta"),
  // Scanner Elements
  btnRunScan: byId("btn-run-scan"),
  scanPreset: byId("scan-preset"),
  scannerTbody: byId("scanner-tbody"),
  scanMeta: byId("scan-meta"),
  // Portfolio Elements
  portTbody: byId("portfolio-tbody"),
  portMeta: byId("portfolio-meta"),
  // Watchlist Elements
  watchTbody: byId("watchlist-tbody"),
  // Chart Container
  tvChartContainer: byId("tv-chart-container"),
  fundamentalsView: byId("fundamentals-view"),
  btnExport: byId("btn-export"),
  btAnalytics: byId("backtest-analytics"),
  btMetricsGrid: byId("bt-metrics-grid"),
  riskProtocol: byId("risk-protocol"),
  riskMetricsGrid: byId("risk-metrics-grid"),
  toastContainer: byId("toast-container"),
  sectorRotationList: byId("sector-rotation-list"),
  correlationMap: byId("correlation-map"),
  riskSimTicker: byId("risk-sim-ticker"),
  btnRunRiskSim: byId("btn-run-risk-sim"),
  chatToggle: byId("chat-toggle"),
  chatBox: byId("chat-box"),
  chatClose: byId("chat-close"),
  chatMessages: byId("chat-messages"),
  chatInput: byId("chat-input"),
  chatSend: byId("chat-send"),
  announcer: byId("app-announcer"),
  kpiSymbol: byId("kpi-symbol"),
  kpiLivePrice: byId("kpi-live-price"),
  kpiForecast: byId("kpi-forecast"),
  kpiConfidence: byId("kpi-confidence"),
  kpiTrend: byId("kpi-trend"),
  kpiUpdated: byId("kpi-updated"),
  forecastChartCanvas: byId("forecast-chart"),
  volumeChartCanvas: byId("volume-chart"),
};

const state = {
  pollTimer: null,
  tvChart: null,
  tvSeries: null,
  equityChart: null,
  ws: null,
  realtimePrices: {},
  riskImpactChart: null,
  wsInterval: null,
  activeTicker: null,
  activeExchange: "NSE",
  forecastChart: null,
  volumeChart: null,
  chartDataCache: new Map(),
  chartRequestController: null,
  realtimePaintAt: {},
};

// --- Core Utilities ---
function pretty(value) {
  return JSON.stringify(value, null, 2);
}

function toFiniteNumber(value, fallback = 0) {
  const num = Number(value);
  return Number.isFinite(num) ? num : fallback;
}

function getCurrencyCode(exchange) {
  return exchange === "NSE" || exchange === "BSE" ? "INR" : "USD";
}

function formatCurrency(value, exchange = "NSE") {
  const num = toFiniteNumber(value, 0);
  const currency = getCurrencyCode(exchange);
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
    maximumFractionDigits: 2,
  }).format(num);
}

function stampKpiUpdate() {
  if (elements.kpiUpdated) {
    elements.kpiUpdated.textContent = new Date().toLocaleTimeString();
  }
}

function announceStatus(message) {
  if (!elements.announcer) return;
  elements.announcer.textContent = "";
  // Force assistive tech to re-announce repeated status updates.
  setTimeout(() => {
    elements.announcer.textContent = message;
  }, 20);
}

function getChartCacheKey(ticker, exchange, period) {
  return `${String(ticker).toUpperCase()}|${String(exchange).toUpperCase()}|${String(period).toLowerCase()}`;
}

function updateDashboardKpis(payload = {}) {
  if (!payload || payload.success === false) return;
  const ticker = payload.ticker || payload.stock || state.activeTicker || "N/A";
  const exchange = payload.resolved_exchange || payload.exchange || state.activeExchange || "NSE";
  const prediction = payload.prediction || {};

  if (elements.kpiSymbol) {
    elements.kpiSymbol.textContent = `${ticker} (${exchange})`;
  }
  if (elements.kpiForecast) {
    const predictedPrice = prediction.predicted_price ?? payload.prediction_value;
    elements.kpiForecast.textContent = predictedPrice != null
      ? formatCurrency(predictedPrice, exchange)
      : "--";
  }
  if (elements.kpiConfidence) {
    elements.kpiConfidence.textContent = prediction.confidence || "Medium";
  }
  if (elements.kpiTrend) {
    const trend = prediction.trend || "Neutral";
    elements.kpiTrend.textContent = trend;
    elements.kpiTrend.classList.remove("cell-positive", "cell-negative");
    if (trend === "Bullish") elements.kpiTrend.classList.add("cell-positive");
    if (trend === "Bearish") elements.kpiTrend.classList.add("cell-negative");
  }
  stampKpiUpdate();
}

function updateLivePriceKpi(price, exchange = "NSE") {
  if (elements.kpiLivePrice) {
    elements.kpiLivePrice.textContent = formatCurrency(price, exchange);
  }
  stampKpiUpdate();
}

function destroyChartInstance(chartInstanceKey) {
  if (state[chartInstanceKey]) {
    state[chartInstanceKey].destroy();
    state[chartInstanceKey] = null;
  }
}

function renderForecastBandChart(payload) {
  if (!elements.forecastChartCanvas || typeof Chart === "undefined" || !payload || payload.success === false) return;
  const prediction = payload.prediction || {};
  const lower = toFiniteNumber(prediction.lower_bound, 0);
  const mid = toFiniteNumber(prediction.predicted_price ?? payload.prediction_value, 0);
  const upper = toFiniteNumber(prediction.upper_bound, 0);

  destroyChartInstance("forecastChart");
  state.forecastChart = new Chart(elements.forecastChartCanvas.getContext("2d"), {
    type: "line",
    data: {
      labels: ["Lower", "Forecast", "Upper"],
      datasets: [{
        label: "Prediction Band",
        data: [lower, mid, upper],
        borderColor: "#1564ff",
        backgroundColor: "rgba(21, 100, 255, 0.15)",
        borderWidth: 2,
        tension: 0.35,
        pointRadius: 3,
        fill: true,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { grid: { display: false }, ticks: { color: "#67749a" } },
        y: {
          ticks: { color: "#67749a" },
          grid: { color: "rgba(188, 200, 232, 0.4)" },
        },
      },
    },
  });
}

function renderVolumeChart(ohlcv = []) {
  if (!elements.volumeChartCanvas || typeof Chart === "undefined" || !Array.isArray(ohlcv) || ohlcv.length === 0) return;
  const slice = ohlcv.slice(-20);
  const labels = slice.map((row) => {
    const rawDate = row.Date || row.date;
    const date = new Date(rawDate);
    return Number.isNaN(date.getTime()) ? "" : date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
  });
  const values = slice.map((row) => toFiniteNumber(row.Volume ?? row.volume, 0));

  destroyChartInstance("volumeChart");
  state.volumeChart = new Chart(elements.volumeChartCanvas.getContext("2d"), {
    type: "bar",
    data: {
      labels,
      datasets: [{
        label: "Volume",
        data: values,
        backgroundColor: "rgba(19, 143, 78, 0.35)",
        borderColor: "#138f4e",
        borderWidth: 1.2,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { grid: { display: false }, ticks: { color: "#67749a", maxTicksLimit: 6 } },
        y: {
          ticks: {
            color: "#67749a",
            callback: (value) => `${Math.round(Number(value) / 1000)}k`,
          },
          grid: { color: "rgba(188, 200, 232, 0.35)" },
        },
      },
    },
  });
}

function setButtonLoading(button, loading, text = "Loading...") {
  if (!button) return;
  if (loading) {
    button.dataset.label = button.textContent;
    button.textContent = text;
    button.disabled = true;
    button.setAttribute("aria-busy", "true");
  } else {
    button.textContent = button.dataset.label || button.textContent;
    button.disabled = false;
    button.setAttribute("aria-busy", "false");
  }
}

async function postJson(url, payload) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const contentType = response.headers.get("content-type") || "";
  const body = contentType.includes("application/json") ? await response.json() : await response.text();
  if (!response.ok) {
    let errorMessage = "Request failed";
    if (typeof body === "string") {
      errorMessage = body;
    } else {
      const detail = body.detail || body.error || body.error_message;
      if (Array.isArray(detail)) {
        errorMessage = detail.map(d => `${d.loc.join('.')}: ${d.msg}`).join(" | ");
      } else if (typeof detail === "object") {
        errorMessage = JSON.stringify(detail);
      } else {
        errorMessage = detail || `Error ${response.status}`;
      }
    }
    throw new Error(errorMessage);
  }
  return body;
}

async function getJson(url) {
  const response = await fetch(url);
  const body = await response.json();
  if (!response.ok) {
    throw new Error(body.detail || body.error || `Request failed (${response.status})`);
  }
  return body;
}

async function getChartData(ticker, exchange = "NSE", period = "2y", { useCache = true } = {}) {
  const cacheKey = getChartCacheKey(ticker, exchange, period);
  if (useCache && state.chartDataCache.has(cacheKey)) {
    return state.chartDataCache.get(cacheKey);
  }

  if (state.chartRequestController) {
    state.chartRequestController.abort();
  }
  state.chartRequestController = new AbortController();

  const response = await fetch(
    `/api/chart-data/${encodeURIComponent(ticker)}?exchange=${encodeURIComponent(exchange)}&period=${encodeURIComponent(period)}`,
    { signal: state.chartRequestController.signal }
  );
  const body = await response.json();
  if (!response.ok) {
    throw new Error(body.detail || body.error || `Request failed (${response.status})`);
  }

  state.chartDataCache.set(cacheKey, body);
  if (state.chartDataCache.size > 24) {
    const oldestKey = state.chartDataCache.keys().next().value;
    if (oldestKey) state.chartDataCache.delete(oldestKey);
  }
  return body;
}

function renderError(error) {
  const message = typeof error === 'string' ? error : (error.message || JSON.stringify(error));
  elements.summaryCards.innerHTML = `
    <div class="summary-card" style="border-left: 4px solid var(--danger); grid-column: 1 / -1;">
      <div class="summary-card__label" style="color: var(--danger);">ERROR_ENCOUNTERED</div>
      <div class="summary-card__value" style="font-size: 0.8rem; white-space: pre-wrap;">${message}</div>
    </div>
  `;
  elements.resultJson.textContent = message;
  if (elements.kpiTrend) {
    elements.kpiTrend.textContent = "Error";
    elements.kpiTrend.classList.remove("cell-positive");
    elements.kpiTrend.classList.add("cell-negative");
  }
  stampKpiUpdate();
}

function metricCard(label, value) {
  const card = document.createElement("article");
  card.className = "summary-card";
  card.innerHTML = `<div class="summary-card__label">${label}</div><div class="summary-card__value">${value}</div>`;
  return card;
}

function clearSummary() {
  elements.summaryCards.innerHTML = "";
  elements.explanationView.innerHTML = "";
  if (state.equityChart) {
    state.equityChart.destroy();
    state.equityChart = null;
  }
  destroyChartInstance("forecastChart");
  elements.btAnalytics.style.display = "none";
  elements.riskProtocol.style.display = "none";
}

function showLoadingSkeleton() {
  elements.summaryCards.innerHTML = `
    <div class="skeleton-card" style="grid-column: 1 / -1;">
      <div class="skeleton-header">
        <div class="skeleton-badge"></div>
        <div class="skeleton-badge"></div>
        <div class="skeleton-title"></div>
      </div>
      <div class="skeleton-text"></div>
      <div class="skeleton-text"></div>
      <div class="skeleton-grid">
        <div class="skeleton-stat"></div>
        <div class="skeleton-stat"></div>
        <div class="skeleton-stat"></div>
      </div>
    </div>
  `;

  if (elements.tickerMeta) {
    elements.tickerMeta.textContent = "// NEURAL_PROCESSING...";
  }
}

function renderTVChart(ohlcvData) {
  if (!ohlcvData || ohlcvData.length === 0) return;
  if (!window.LightweightCharts) return;
  if (state.tvChart) {
    state.tvChart.remove();
  }

  // Get container dimensions
  const container = elements.tvChartContainer;
  const containerHeight = container.clientHeight || 380;
  const containerWidth = container.clientWidth || 800;

  const chart = LightweightCharts.createChart(container, {
    width: containerWidth,
    height: containerHeight,
    layout: {
      background: { type: 'solid', color: 'transparent' },
      textColor: '#888',
    },
    grid: {
      vertLines: { color: '#222' },
      horzLines: { color: '#222' },
    },
    rightPriceScale: { borderColor: '#333' },
    timeScale: { borderColor: '#333' },
  });

  chart.applyOptions({
    crosshair: {
      horzLine: { visible: true, labelVisible: true },
      vertLine: { visible: true, labelVisible: true, labelBackgroundColor: '#00ffa3' },
    },
    localization: { priceFormatter: price => formatCurrency(price, state.activeExchange || "NSE") },
  });

  // Handle window resize
  const resizeObserver = new ResizeObserver(entries => {
    if (entries.length === 0 || entries[0].target !== container) return;
    const newWidth = container.clientWidth;
    const newHeight = container.clientHeight || 380;
    chart.applyOptions({ width: newWidth, height: newHeight });
  });
  resizeObserver.observe(container);

  const candlestickSeries = chart.addCandlestickSeries({
    upColor: '#00ffa3', downColor: '#ff2d55',
    borderDownColor: '#ff2d55', borderUpColor: '#00ffa3',
    wickDownColor: '#ff2d55', wickUpColor: '#00ffa3',
  });

  const volumeSeries = chart.addHistogramSeries({
    color: '#26a69a',
    priceFormat: { type: 'volume' },
    priceScaleId: 'volume',
    lastValueVisible: false,
    priceLineVisible: false,
  });

  chart.priceScale('volume').applyOptions({
    scaleMargins: { top: 0.8, bottom: 0 },
    visible: false,
  });

  const formattedData = ohlcvData.map(d => ({
    time: Math.floor(new Date(d.Date).getTime() / 1000),
    open: d.Open, high: d.High, low: d.Low, close: d.Close,
    volume: d.Volume || 0
  })).sort((a, b) => a.time - b.time);

  // Calculate SMAs
  const calculateSMA = (data, period) => {
    let result = [];
    for (let i = 0; i < data.length; i++) {
      if (i < period - 1) {
        // Not enough data for SMA
        continue;
      }
      let sum = 0;
      for (let j = 0; j < period; j++) {
        sum += data[i - j].close;
      }
      result.push({ time: data[i].time, value: sum / period });
    }
    return result;
  };

  const sma20Series = chart.addLineSeries({
    color: '#ffcc00',
    lineWidth: 2,
    title: 'SMA 20',
  });

  const sma50Series = chart.addLineSeries({
    color: '#00ccff',
    lineWidth: 2,
    title: 'SMA 50',
  });

  const sma20Data = calculateSMA(formattedData, 20);
  const sma50Data = calculateSMA(formattedData, 50);

  candlestickSeries.setData(formattedData);
  volumeSeries.setData(formattedData.map(d => ({
    time: d.time,
    value: d.volume,
    color: d.close >= d.open ? 'rgba(0, 255, 163, 0.3)' : 'rgba(255, 45, 85, 0.3)'
  })));

  sma20Series.setData(sma20Data);
  sma50Series.setData(sma50Data);

  chart.timeScale().fitContent();
  state.tvChart = chart;
  state.tvSeries = candlestickSeries;
  state.lastCandle = formattedData[formattedData.length - 1];
}

function showToast(title, message, type = "info") {
  if (!elements.toastContainer) return;
  const activeToasts = elements.toastContainer.querySelectorAll(".toast");
  if (activeToasts.length >= 5) {
    activeToasts[0].remove();
  }
  const toast = document.createElement("div");
  toast.className = `toast toast--${type}`;
  toast.innerHTML = `
    <div class="toast__header">
      <div class="toast__title">${title}</div>
      <div class="toast__ts">${new Date().toLocaleTimeString()}</div>
    </div>
    <div class="toast__msg">${message}</div>
  `;
  elements.toastContainer.appendChild(toast);
  announceStatus(`${title}. ${message}`);

  // Auto remove after 5s
  setTimeout(() => {
    toast.classList.add("toast-fade-out");
    setTimeout(() => toast.remove(), 400);
  }, 5000);
}

function initWebSocket() {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const wsUrl = `${protocol}//${window.location.host}/ws/stream`;

  const ws = new WebSocket(wsUrl);

  ws.onopen = () => {
    console.log("WebSocket connected to STK-STREAM");
    showToast("SYSTEM_CONNECTED", "Live telemetry stream established.", "info");
    const statusText = byId("system-status-text");
    if (statusText) statusText.textContent = "Stream Connected";

    // Pulse Heartbeat to prevent timeouts
    if (state.wsInterval) clearInterval(state.wsInterval);
    state.wsInterval = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send("ping");
      }
    }, 20000); // 20s heartbeat
  };

  ws.onmessage = (event) => {
    // Handle plain text pong/ping responses BEFORE parsing
    if (typeof event.data === 'string' && (event.data === "pong" || event.data === "ping")) {
      return;
    }

    try {
      const data = JSON.parse(event.data);

      // Handle pong as object
      if (data === "pong" || data.type === "pong") {
        return;
      }

      if (data.type === "PRICE_UPDATE") {
        state.realtimePrices[data.ticker] = data.price;
        updateLiveUI(data.ticker, data.price, data.change_pct);
      } else if (data.type === "ALERT") {
        showToast(`ALERT: ${data.ticker}`, data.message, "warn");
      }
    } catch (error) {
      // Silently ignore parse errors in production
      if (window.location.hostname === 'localhost') {
        console.log("WebSocket parse error:", error.message);
      }
    }
  };

  ws.onerror = (error) => {
    console.log("WebSocket error (expected during reconnect):", error);
  };

  ws.onclose = () => {
    console.log("WebSocket disconnected");
    const statusText = byId("system-status-text");
    if (statusText) statusText.textContent = "Stream Reconnecting";
    if (state.wsInterval) {
      clearInterval(state.wsInterval);
      state.wsInterval = null;
    }
    setTimeout(initWebSocket, 5000); // Reconnect
  };

  state.ws = ws;
}

function updateLiveUI(ticker, price, change) {
  const now = typeof performance !== "undefined" && performance.now ? performance.now() : Date.now();
  const lastPaint = state.realtimePaintAt[ticker] || 0;
  if (now - lastPaint < 120) {
    return;
  }
  state.realtimePaintAt[ticker] = now;

  updateLivePriceKpi(price, state.activeExchange || "NSE");

  // Update Scanner row if present
  const scanRow = elements.scannerTbody?.querySelector(`tr[data-ticker="${ticker}"]`);
  if (scanRow) {
    scanRow.cells[1].textContent = price.toFixed(2);
    const pctCell = scanRow.cells[2];
    if (pctCell) {
      pctCell.textContent = `${change.toFixed(2)}%`;
      pctCell.className = change >= 0 ? "cell-positive" : "cell-negative";
    }
  }

  // Update Portfolio row if present
  const portRow = elements.portTbody?.querySelector(`tr[data-ticker="${ticker}"]`);
  if (portRow) {
    const currentPriceCell = portRow.cells[3];
    const plCell = portRow.cells[4];
    const avgPrice = parseFloat(portRow.cells[2].textContent);

    currentPriceCell.textContent = price.toFixed(2);
    const pl = avgPrice > 0 ? ((price - avgPrice) / avgPrice) * 100 : 0;
    plCell.textContent = `${pl >= 0 ? "+" : ""}${pl.toFixed(2)}%`;
    plCell.className = pl >= 0 ? "cell-positive" : "cell-negative";

    const qty = toFiniteNumber(portRow.cells[1].textContent, 0);
    const pnlValueCell = portRow.cells[5];
    if (pnlValueCell) {
      const pnlValue = (price - avgPrice) * qty;
      pnlValueCell.textContent = `${pnlValue >= 0 ? "+" : ""}${pnlValue.toFixed(2)}`;
      pnlValueCell.className = pnlValue >= 0 ? "cell-positive" : "cell-negative";
    }
  }

  // Real-time Chart Update (Candlestick Pulse)
  if (state.tvSeries && state.activeTicker === ticker && state.lastCandle) {
    state.lastCandle.close = price;
    if (price > state.lastCandle.high) state.lastCandle.high = price;
    if (price < state.lastCandle.low) state.lastCandle.low = price;

    // Smooth update for all series layers
    state.tvSeries.update(state.lastCandle);

    if (state.areaSeries) {
      state.areaSeries.update({
        time: state.lastCandle.time,
        value: price
      });
    }

    // Dynamic legend update for the live pulse
    if (typeof updateDynamicLegendPulse === 'function') {
      updateDynamicLegendPulse(state.lastCandle);
    }
  }
}

function renderSummaryCards(payload) {
  clearSummary();

  const ticker = payload.ticker || payload.stock || "N/A";

  if (payload.success === false) {
    renderError(payload.error || "Neural pipeline interrupted.");
    if (elements.tickerMeta) {
      elements.tickerMeta.textContent = `// SCAN_FAILURE: ${ticker}`;
    }
    return;
  }

  const fundamentals = payload.fundamentals || {};
  const financials = payload.financials || [];
  const telemetry = payload.model_telemetry || {};
  const pred = payload.prediction || {};

  // Standardize values - handle both nested and flat structures
  const predictedPrice = pred.predicted_price || payload.prediction_value || 0;
  const predicted = Number(predictedPrice).toFixed(2);
  const trend = pred.trend || "Neutral";
  const confidence = pred.confidence || "Medium";

  // 1. Build Narrative - Prioritize high-quality LLM explanation
  const exchange = payload.resolved_exchange || payload.exchange || state.activeExchange || "NSE";
  const symbol = getCurrencyCode(exchange) === "INR" ? "Rs " : "$";
  const companyName = fundamentals.name && fundamentals.name !== "N/A" ? fundamentals.name : (ticker || "N/A");

  const narrativeText = payload.explanation ? payload.explanation.replace(/\n/g, '<br>') : `
    ${companyName} (${ticker}), operating in the ${fundamentals.sector && fundamentals.sector !== 'N/A' ? fundamentals.sector : 'Global'} market, 
    has shown significant performance cues in the ${fundamentals.industry && fundamentals.industry !== 'N/A' ? fundamentals.industry : 'financial'} domain. 
    Our Neural Ensemble, synthesizing data across multiple regimes, projects a 
    <span class="${trend === 'Bullish' ? 'cell-positive' : 'cell-negative'}" style="font-weight:800;">${trend}</span> outlook 
    with a target price of <strong>${symbol}${predicted}</strong>. 
    ${fundamentals.summary && fundamentals.summary !== 'No summary available.' ? fundamentals.summary : 'Market dynamics suggest volatility with high-confidence signals detected in volume profiles.'}
  `;

  // Update explanation view if it exists
  if (elements.explanationView) {
    elements.explanationView.innerHTML = payload.explanation || "";
  }

  // 2. Main Result Template
  elements.summaryCards.innerHTML = `
    <div class="plx-result" style="grid-column: 1 / -1;">
      <div class="plx-header">
        <div class="plx-badge">${fundamentals.sector || 'EQUITY'}</div>
        <div class="plx-badge">${payload.resolved_exchange || 'Global'}</div>
        <h2 class="plx-company-name">${companyName}</h2>
      </div>

      <div class="plx-narrative">
        ${narrativeText}
        <span class="plx-source-tag">yFinance</span>
        <span class="plx-source-tag">STK_ENGINE_V2</span>
      </div>

      <div class="plx-card-grid">
        <div class="plx-stat-card">
          <div class="plx-stat-label">Estimated Price</div>
          <div class="plx-stat-value">${symbol}${predicted}</div>
        </div>
        <div class="plx-stat-card" style="border-left-color: ${trend === 'Bullish' ? 'var(--success)' : (trend === 'Bearish' ? 'var(--danger)' : 'var(--border)')}">
          <div class="plx-stat-label">Sentiment Trend</div>
          <div class="plx-stat-value" style="color: ${trend === 'Bullish' ? 'var(--success)' : (trend === 'Bearish' ? 'var(--danger)' : 'var(--text-muted)')}">
            ${trend === 'Bullish' ? 'Up' : (trend === 'Bearish' ? 'Down' : 'Flat')} ${trend}
          </div>
        </div>
        <div class="plx-stat-card" style="border-left-color: var(--border-bright);">
          <div class="plx-stat-label">Neural Confidence</div>
          <div class="plx-stat-value">${confidence}</div>
        </div>
      </div>

      ${financials.length > 0 ? (() => {
      // Use correct currency label based on exchange
      const isIndia = exchange === 'NSE' || exchange === 'BSE';
      const currLabel = isIndia ? '\u20b9 Cr' : '$ M';
      // Indian financials come in full rupees; divide by 10M for Crores, or by 1M for USD millions
      const divisor = isIndia ? 10000000 : 1000000;
      const fmt = (v) => (Number(v || 0) / divisor).toFixed(0);
      return `
        <div class="result-header" style="border-bottom:none; margin-bottom: 12px;">
          <div class="header-main" style="font-size: 1.2rem;">FINANCIAL_HIGHLIGHTS</div>
        </div>
        <div class="plx-table-container">
          <table class="plx-table">
            <thead>
              <tr>
                <th>YEAR</th>
                <th>REVENUE (${currLabel})</th>
                <th>NET INCOME (${currLabel})</th>
                <th>EBIT (${currLabel})</th>
                <th>GROWTH NOTES</th>
              </tr>
            </thead>
            <tbody>
              ${financials.map(f => `
                <tr>
                  <td>${f.year}</td>
                  <td>${fmt(f.revenue)}</td>
                  <td>${fmt(f.net_income)}</td>
                  <td>${fmt(f.ebit)}</td>
                  <td style="color: var(--accent); font-size: 0.7rem;">${f.growth_notes}</td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        </div>
        `;
    })() : ''}

      <div class="plx-model-grid">
        <div class="result-header" style="border-bottom:none; margin-bottom: 16px;">
          <div class="header-main" style="font-size: 1rem; color: var(--text-muted);">NEURAL_ENSEMBLE_TRANSPARENCY</div>
        </div>
        ${telemetry.lstm > 0 ? renderModelBar("TRANSFORMER_LSTM", telemetry.lstm, predicted) : ''}
        ${telemetry.xgboost > 0 ? renderModelBar("GRADIENT_BOOST_XGB", telemetry.xgboost, predicted) : ''}
        ${telemetry.random_forest > 0 ? renderModelBar("RANDOM_FOREST_QUANT", telemetry.random_forest, predicted) : ''}
      </div>

      ${payload.research && payload.research.synthesis ? `
        <div class="explanation-area" style="margin-top: 32px; border: 1px solid var(--border); background: rgba(0,255,163,0.02);">
          <div class="result-header" style="border-bottom:none; padding-bottom: 0;">
            <div class="header-main" style="font-size: 1.1rem; color: var(--accent);">NEURAL_RESEARCH_CONTEXT</div>
          </div>
          <div style="font-size: 0.95rem; line-height: 1.6; margin: 16px 0;">
            ${payload.research.synthesis}
          </div>
          ${(payload.research.catalysts || []).length > 0 ? `
          <div style="display: flex; flex-wrap: wrap; gap: 8px;">
            ${payload.research.catalysts.map(c => {
      const label = typeof c === 'object' ? (c.catalyst || JSON.stringify(c)) : c;
      return `<div class="plx-badge" style="background:var(--bg-deep);">${label}</div>`;
    }).join('')}
          </div>` : ''}
          ${(payload.research.headlines || []).length > 0 ? `
          <div style="margin-top: 16px; font-size: 0.7rem; color: var(--text-muted);">
            LATEST_INTEL: ${payload.research.headlines.join(' | ')}
          </div>` : ''}
        </div>
      ` : ''}
    </div>
  `;

  updateDashboardKpis(payload);
  renderForecastBandChart(payload);

  if (elements.tickerMeta) {
    elements.tickerMeta.textContent = `// ACTIVE_SCAN: ${ticker}`;
  }

  if (elements.btnExport) {
    elements.btnExport.style.display = "block";
    elements.btnExport.onclick = () => exportReport(ticker, payload.exchange || "NSE");
  }

  // Load Charts & Analytics
  if (payload.backtest) {
    renderBacktestAnalytics(payload.backtest);
    renderRiskProtocol(payload.backtest);
  }

  // Note: loadAdvancedInsights is now called directly from individual functions
  // to ensure correct ticker is used
}

function renderModelBar(label, value, target) {
  const pct = Math.min(100, Math.max(10, (value / target) * 100));
  return `
    <div class="plx-model-bar-container">
      <div class="plx-model-header">
        <span>${label}</span>
        <span style="color: var(--accent);">${Number(value).toFixed(2)}</span>
      </div>
      <div class="plx-bar-bg">
        <div class="plx-bar-fill" style="width: ${pct}%"></div>
      </div>
    </div>
  `;
}
async function loadQuantumAnalytics() {
  try {
    // 1. Sector Rotation
    const rotationData = await getJson("/api/analytics/sector-rotation");
    if (rotationData.success) {
      elements.sectorRotationList.innerHTML = rotationData.rotation.map(item => `
        <div style="display: flex; justify-content: space-between; padding: 10px; border-bottom: 1px solid var(--border); font-family: var(--font-data);">
          <span style="color: var(--text-main);">${item.sector}</span>
          <span class="${item.performance_pct >= 0 ? 'cell-positive' : 'cell-negative'}">${item.performance_pct.toFixed(2)}%</span>
        </div>
      `).join("");
    }

    // 2. Correlation
    const corrData = await getJson("/api/analytics/correlation");
    if (corrData.success && !corrData.correlation.error) {
      const { tickers, matrix } = corrData.correlation;
      let html = `<table style="width:100%; border-collapse: collapse;"><tr><td></td>`;
      tickers.forEach(t => html += `<td style="color:var(--accent); padding:4px;">${t}</td>`);
      html += `</tr>`;
      matrix.forEach((row, i) => {
        html += `<tr><td style="color:var(--accent); padding:4px;">${tickers[i]}</td>`;
        row.forEach(val => {
          const color = val > 0.7 ? "var(--danger)" : val < 0.3 ? "var(--success)" : "var(--text-main)";
          html += `<td style="color:${color}; padding:4px; border:1px solid var(--border); text-align:center;">${val}</td>`;
        });
        html += `</tr>`;
      });
      html += `</table>`;
      elements.correlationMap.innerHTML = html;
    }
  } catch (e) {
    console.error("Quantum analytics load error", e);
  }
}

async function runRiskImpactSimulation() {
  const ticker = elements.riskSimTicker.value.trim();
  if (!ticker) return;

  setButtonLoading(elements.btnRunRiskSim, true, "Running...");
  try {
    const res = await getJson(`/api/analytics/risk-impact/${ticker}`);
    if (res.success && res.impact.buy_and_hold) {
      const ctx = document.getElementById('risk-impact-chart').getContext('2d');
      if (state.riskImpactChart) state.riskImpactChart.destroy();

      state.riskImpactChart = new Chart(ctx, {
        type: 'line',
        data: {
          labels: res.impact.buy_and_hold.map((_, i) => i),
          datasets: [
            {
              label: 'BUY_AND_HOLD',
              data: res.impact.buy_and_hold,
              borderColor: '#8b949e',
              borderWidth: 1,
              pointRadius: 0,
              fill: false
            },
            {
              label: 'DYNAMIC_RISK_MANAGED',
              data: res.impact.risk_managed,
              borderColor: '#00ffcc',
              borderWidth: 2,
              pointRadius: 0,
              fill: true,
              backgroundColor: 'rgba(0, 255, 204, 0.05)'
            }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { display: true, labels: { color: '#888', font: { size: 10 } } } },
          scales: {
            x: { display: false },
            y: { grid: { color: '#222' }, ticks: { color: '#888', font: { size: 10 } } }
          }
        }
      });

      showToast("SIMULATION_COMPLETE", `Risk impact analyzed for ${ticker}.`, "info");
    }
  } catch (e) {
    showToast("SIM_FAILED", e.message, "danger");
  } finally {
    setButtonLoading(elements.btnRunRiskSim, false);
  }
}

async function sendChatMessage() {
  const message = elements.chatInput.value.trim();
  if (!message) return;

  // Visual feedback
  elements.chatInput.disabled = true;
  if (elements.chatSend) elements.chatSend.disabled = true;

  // Add User Message
  appendChatMessage(message, "user");
  elements.chatInput.value = "";

  try {
    const res = await postJson("/api/chat", { message });
    appendChatMessage(res.message, "bot");

    // Auto scroll
    elements.chatMessages.scrollTop = elements.chatMessages.scrollHeight;

    // Execute actions if specified
    if (res.action === "RUN_PREDICTION") {
      const tickerEl = byId("predict-stock");
      if (tickerEl) tickerEl.value = res.data.ticker || "";
      const exchEl = byId("predict-exchange");
      if (exchEl && res.data.exchange) exchEl.value = res.data.exchange;
      const dateEl = byId("predict-date");
      if (dateEl && res.data.target_date) dateEl.value = res.data.target_date;

      runPrediction(false, res.data.history_days);
    } else if (res.action === "RUN_SCAN") {
      if (elements.scanPreset) { elements.scanPreset.value = res.data.preset; runScanner(); }
    } else if (res.action === "REFRESH_PORTFOLIO") {
      renderPortfolio();
      showToast("PORTFOLIO_UPDATED", "Positions refreshed via chat command.", "success");
    } else if (res.action === "REFRESH_WATCHLIST") {
      renderWatchlist();
      showToast("WATCHLIST_UPDATED", "Radar updated via chat command.", "success");
    } else if (res.action === "RUN_ANALYSIS") {
      const tickerEl = byId("analyze-stock");
      if (tickerEl) tickerEl.value = res.data.ticker || "";
      const exchEl = byId("analyze-exchange");
      if (exchEl && res.data.exchange) exchEl.value = res.data.exchange;

      runAnalyze();
    } else if (res.action === "RUN_BACKTEST") {
      const tickerEl = byId("backtest-stock");
      if (tickerEl) tickerEl.value = res.data.ticker || "";
      const exchEl = byId("backtest-exchange");
      if (exchEl && res.data.exchange) exchEl.value = res.data.exchange;
      const daysEl = byId("backtest-days");
      if (daysEl) daysEl.value = res.data.days || 30;

      runBacktest();
    } else if (res.action === "RUN_ROTATION" || res.action === "RUN_CORRELATION") {
      // Switch to Quant Tab
      const quantTab = document.querySelector('[data-tab="tab-quant"]');
      if (quantTab) quantTab.click();
      loadQuantumAnalytics();
    }
  } catch (e) {
    appendChatMessage(`Error: ${e.message}`, "bot");
  } finally {
    elements.chatInput.disabled = false;
    if (elements.chatSend) elements.chatSend.disabled = false;
    elements.chatInput.focus();
  }
}

function appendChatMessage(text, sender) {
  const msg = document.createElement("div");
  msg.className = `msg msg--${sender}`;
  msg.textContent = text;
  elements.chatMessages.appendChild(msg);
  elements.chatMessages.scrollTop = elements.chatMessages.scrollHeight;
}

function renderBacktestAnalytics(bt) {
  elements.btAnalytics.style.display = "block";
  elements.btMetricsGrid.innerHTML = "";

  const m = [
    { label: "SHARPE_RATIO", val: bt.sharpe_ratio.toFixed(2) },
    { label: "WIN_RATE", val: bt.win_rate.toFixed(1) + "%" },
    { label: "MAX_DRAWDOWN", val: bt.max_drawdown_pct.toFixed(2) + "%" },
    { label: "TOTAL_TRADES", val: bt.total_trades }
  ];

  m.forEach(i => {
    const card = document.createElement("div");
    card.className = "summary-card";
    card.style.padding = "10px";
    card.innerHTML = `<div style="font-size: 0.6rem; color: var(--text-muted);">${i.label}</div><div style="font-size: 1rem; color: var(--accent); font-family: var(--font-data);">${i.val}</div>`;
    elements.btMetricsGrid.appendChild(card);
  });

  // Render Equity Curve via Chart.js
  const ctx = document.getElementById('equity-chart').getContext('2d');
  if (state.equityChart) state.equityChart.destroy();

  state.equityChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: bt.equity_curve.map((_, i) => i),
      datasets: [{
        label: 'EQUITY_CURVE (Simulated Capital)',
        data: bt.equity_curve,
        borderColor: '#00ffa3',
        backgroundColor: 'rgba(0, 255, 163, 0.1)',
        borderWidth: 2,
        fill: true,
        pointRadius: 0
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { display: false },
        y: { grid: { color: '#222' }, ticks: { color: '#888', font: { size: 10 } } }
      }
    }
  });
}

function renderRiskProtocol(bt) {
  elements.riskProtocol.style.display = "block";
  elements.riskMetricsGrid.innerHTML = "";

  // Calculate Kelly & sizing based on backtest results
  const kelly = (bt.win_rate / 100) * 0.5; // Simple proxy for Kelly
  const var95 = (bt.max_drawdown_pct / 4); // Simple proxy

  const m = [
    { label: "KELLY_POSITION_SIZE", val: (kelly * 100).toFixed(1) + "%", detail: "Suggested % of capital" },
    { label: "VALUE_AT_RISK (95%)", val: var95.toFixed(1) + "%", detail: "Max daily expected loss" },
    { label: "RISK_RATING", val: bt.sharpe_ratio > 1.5 ? "STABLE" : "SPECULATIVE", detail: "System analysis" }
  ];

  m.forEach(i => {
    const card = document.createElement("div");
    card.className = "mini-card";
    card.style.borderTop = "2px solid var(--danger)";
    card.innerHTML = `
      <div style="font-size: 0.6rem; color: var(--text-muted);">${i.label}</div>
      <div style="font-size: 1.4rem; color: var(--text-main); font-family: var(--font-header); margin: 4px 0;">${i.val}</div>
      <div style="font-size: 0.65rem; color: var(--accent);">${i.detail}</div>
    `;
    elements.riskMetricsGrid.appendChild(card);
  });
}

async function exportReport(ticker, exchange) {
  try {
    const res = await getJson(`/api/export-report/${ticker}?exchange=${exchange}`);
    if (res.success) {
      const blob = new Blob([res.report], { type: "text/plain" });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = res.filename;
      a.click();
    }
  } catch (e) {
    alert("Export failed: " + e.message);
  }
}

async function loadAdvancedInsights(ticker, exchange, period = "2y") {
  if (!ticker || ticker === "N/A" || ticker === "null") return;

  state.activeTicker = ticker;
  state.activeExchange = exchange || "NSE";

  // Update button active states
  document.querySelectorAll(".btn-time, .range-btn").forEach(btn => {
    btn.classList.remove("active");
    const p = period.toLowerCase();
    const key = (btn.dataset.period || btn.textContent || "").toLowerCase().trim();
    const normalizedKey = key.replace("mo", "m");
    const normalizedPeriod = p.replace("mo", "m");
    if (normalizedKey === normalizedPeriod) {
      btn.classList.add("active");
    }
  });

  // Load Chart and Price Table
  loadTickerData(ticker, exchange, period);

  // Load Fundamentals
  fetchAndRenderFundamentals(ticker);
}

// Generic function to load ticker data (chart + table)
async function loadTickerData(ticker, exchange = "NSE", period = "2y") {
  try {
    const chartData = await getChartData(ticker, exchange, period, { useCache: true });
    if (chartData.success) {
      state.activeTicker = ticker;
      state.activeExchange = chartData.exchange || exchange;

      // Use enhanced chart if available, otherwise fallback to original
      if (typeof renderEnhancedTVChart === 'function') {
        renderEnhancedTVChart(chartData.ohlcv);
      } else {
        renderTVChart(chartData.ohlcv);
      }

      renderVolumeChart(chartData.ohlcv || []);
      if (chartData.current_price && chartData.current_price.price != null) {
        updateLivePriceKpi(chartData.current_price.price, state.activeExchange);
      }
      if (elements.kpiSymbol) {
        elements.kpiSymbol.textContent = `${ticker} (${state.activeExchange})`;
      }
      announceStatus(`Loaded chart data for ${ticker}`);

      // Load price data table for ALL tickers
      if (typeof priceTable !== 'undefined') {
        if (typeof priceTable.renderFromPayload === "function") {
          priceTable.renderFromPayload(chartData);
        } else {
          priceTable.loadTickerData(ticker, exchange, period);
        }
      }
    }
  } catch (e) {
    if (e && e.name === "AbortError") return;
    console.error("Ticker data load error", e);
  }
}

function renderJSON(payload) {
  elements.resultJson.textContent = pretty(payload);
}


function workflowMarkup(payload) {
  const data = payload.workflow ? payload.workflow : payload;
  const progress = data.progress || {};
  const completed = Array.isArray(progress.completed_steps)
    ? progress.completed_steps.join(" -> ")
    : "n/a";
  const pct = progress.progress_percentage ?? data.progress_percentage ?? 0;
  const status = data.status || (payload.success ? "completed" : "pending");
  const failed = data.failed_step || "none";
  const err = data.error_message || payload.error || "none";
  const statusClass = status === "completed" ? "status-good" : status === "failed" ? "status-bad" : "";

  return `
    <div><strong>Workflow:</strong> ${data.id || data.workflow_id || "n/a"}</div>
    <div><strong>Status:</strong> <span class="${statusClass}">${status}</span></div>
    <div><strong>Progress:</strong> ${pct}%</div>
    <div><strong>Completed:</strong> ${completed || "none"}</div>
    <div><strong>Failed Step:</strong> ${failed}</div>
    <div><strong>Error:</strong> ${err}</div>
  `;
}

function healthMarkup(payload) {
  const deps = payload.dependencies || {};
  const depRows = Object.entries(deps)
    .map(([name, ok]) => `<li>${name}: <span class="${ok ? "status-good" : "status-bad"}">${ok}</span></li>`)
    .join("");
  return `
    <div><strong>Status:</strong> <span class="${payload.status === "healthy" ? "status-good" : "status-bad"}">${payload.status}</span></div>
    <div><strong>Timestamp:</strong> ${payload.timestamp || "n/a"}</div>
    <div><strong>Model Artifacts:</strong> ${payload?.models?.artifact_count ?? "n/a"}</div>
    <div><strong>Cache Size:</strong> ${payload?.cache?.size_bytes ?? "n/a"} bytes</div>
    <ul>${depRows}</ul>
  `;
}

async function runPrediction(quick = false, historyDays = null) {
  const button = quick ? byId("btn-quick") : byId("btn-predict");
  if (!button) return;

  setButtonLoading(button, true, quick ? "Running quick..." : "Predicting...");
  if (typeof showLoadingSkeleton === 'function') {
    showLoadingSkeleton();
  } else {
    elements.summaryCards.innerHTML = `
      <div class="summary-card" style="grid-column: 1 / -1;">
        <div class="summary-card__label">PROCESSING_NEURAL_PIPELINE</div>
        <div class="summary-card__value" style="animation: pulse 2s infinite;">Analyzing market data...</div>
      </div>
    `;
  }

  try {
    const stockEl = byId("predict-stock");
    const exchEl = byId("predict-exchange");
    const dateEl = byId("predict-date");
    const modelEl = byId("predict-model");

    if (!stockEl) throw new Error("Input element 'predict-stock' not found.");

    const targetDate = dateEl?.value || null;
    let exchangeValue = exchEl ? exchEl.value : "NSE";
    exchangeValue = exchangeValue.replace(/\s*\([^)]*\)/g, '').trim();

    const tickerValue = stockEl.value.trim().toUpperCase();
    if (!/^[A-Z0-9]+$/.test(tickerValue)) {
      throw new Error("Invalid ticker format. Please use alphanumeric characters only.");
    }

    const includeResearch = byId("predict-research")?.checked || false;

    // ── STEP 1: Fire prediction WITHOUT research for fast results ──────────
    const fastPayload = {
      ticker: tickerValue,
      exchange: exchangeValue,
      target_date: targetDate && targetDate.trim() !== "" ? targetDate : null,
      model_type: modelEl ? modelEl.value : "ensemble",
      include_backtest: byId("predict-backtest")?.checked || false,
      include_sentiment: byId("predict-sentiment")?.checked || false,
      include_research: false,  // Always false for the fast first pass
      history_days: historyDays || 500
    };

    const data = await postJson(quick ? "/api/predict/quick" : "/api/predict", fastPayload);

    state.activeTicker = tickerValue;
    state.activeExchange = exchangeValue;

    // Render prediction immediately
    renderSummaryCards(data);
    renderJSON(data);
    loadTickerData(tickerValue, exchangeValue);
    setButtonLoading(button, false);

    // ── STEP 2: Stream research in background if requested ─────────────────
    if (includeResearch && !quick) {
      _streamResearchIntoResult(tickerValue, exchangeValue);
    }

  } catch (error) {
    renderError(error);
    setButtonLoading(button, false);
  }
}

/** Streams research via SSE and patches the live dashboard without re-rendering. */
function _streamResearchIntoResult(ticker, exchange) {
  // Inject a "Research Loading" placeholder into the existing result
  const existing = elements.summaryCards.querySelector(".plx-result");
  if (!existing) return;

  let researchPanel = document.createElement("div");
  researchPanel.id = "live-research-panel";
  researchPanel.style.cssText = "margin-top:24px; border:1px solid var(--border); padding:16px; border-radius:8px; background:rgba(0,255,163,0.02);";
  researchPanel.innerHTML = `
    <div style="color:var(--accent); font-family:var(--font-data); font-size:0.8rem; margin-bottom:10px;">⚡ LIVE_RESEARCH_AGENT</div>
    <div id="research-stream-log" style="font-size:0.75rem; color:var(--text-muted); font-family:var(--font-data);">
      &gt; Connecting to research pipeline...
    </div>
  `;
  existing.appendChild(researchPanel);

  const logEl = document.getElementById("research-stream-log");
  const url = `/api/research/stream?ticker=${ticker}&exchange=${exchange}`;
  const es = new EventSource(url);

  es.onmessage = (e) => {
    const evData = JSON.parse(e.data);

    if (evData.status === "complete") {
      es.close();
      const r = evData.result || {};
      researchPanel.innerHTML = `
        <div style="color:var(--accent); font-family:var(--font-data); font-size:0.8rem; margin-bottom:12px;">✅ RESEARCH_COMPLETE</div>
        ${r.synthesis ? `<div style="font-size:0.92rem; line-height:1.65; margin-bottom:12px;">${r.synthesis}</div>` : ""}
        ${(r.catalysts || []).length > 0 ? `
          <div style="display:flex; flex-wrap:wrap; gap:8px; margin-bottom:10px;">
            ${r.catalysts.map(c => {
        const lbl = typeof c === 'object' ? (c.catalyst || JSON.stringify(c)) : c;
        return `<div class="plx-badge" style="background:var(--bg-deep);">${lbl}</div>`;
      }).join('')}
          </div>` : ""}
        ${(r.risks || []).length > 0 ? `
          <div style="margin-top:8px; font-size:0.72rem; color:var(--danger);">
            ⚠ RISKS: ${r.risks.slice(0, 3).map(rk => typeof rk === 'object' ? rk.risk : rk).join(' | ')}
          </div>` : ""}
        ${(r.headlines || []).length > 0 ? `
          <div style="margin-top:8px; font-size:0.68rem; color:var(--text-muted);">
            LATEST_INTEL: ${r.headlines.join(' | ')}
          </div>` : ""}
      `;
      // Update full JSON view to include research
      renderJSON({ ...window._lastPredictionData, research: r });
    } else if (evData.status === "error") {
      es.close();
      researchPanel.innerHTML += `<div style="color:var(--danger);">&gt; Research unavailable: ${evData.message || "timeout"}</div>`;
    } else {
      const msg = evData.message || evData.status;
      if (logEl) logEl.innerHTML += `<br>&gt; ${msg}`;
    }
  };

  es.onerror = () => {
    es.close();
    if (researchPanel) researchPanel.innerHTML = `<div style="color:var(--danger); font-size:0.8rem;">&gt; Research stream interrupted.</div>`;
  };
}


async function runDeepResearch() {
  const button = byId("btn-deep-research");
  const ticker = byId("research-stock")?.value.trim().toUpperCase();
  const exchange = byId("research-exchange")?.value || "NSE";

  if (!ticker || !button) return;

  setButtonLoading(button, true, "Starting...");
  elements.summaryCards.innerHTML = `
    <div class="plx-result" style="grid-column: 1 / -1;">
      <div class="plx-header">
        <div class="plx-badge" style="background:var(--accent); color:var(--bg-deep);">LIVE_RESEARCH</div>
        <h2 class="plx-company-name">Analyzing ${ticker}</h2>
      </div>
      <div id="research-progress" style="margin-top: 20px; font-family: var(--font-data);">
        <div style="color: var(--accent); margin-bottom: 10px;">> Initializing Neural Pipeline...</div>
      </div>
    </div>
  `;

  const progressEl = byId("research-progress");

  try {
    const url = `/api/research/stream?ticker=${ticker}&exchange=${exchange}`;
    const es = new EventSource(url);

    es.onmessage = (e) => {
      const data = JSON.parse(e.data);
      console.log("Research Stream:", data);

      if (data.status === "complete") {
        es.close();
        setButtonLoading(button, false);
        // Transform the research result into a format renderSummaryCards expects
        const payload = {
          success: true,
          ticker: ticker,
          exchange: exchange,
          research: data.result,
          fundamentals: {
            name: data.result.ticker,
            sector: "RESEARCH_INSIGHT",
            summary: data.result.synthesis
          },
          prediction: { predicted_price: 0, trend: "N/A" }
        };
        renderSummaryCards(payload);
        renderJSON(data.result);
      } else if (data.status === "error") {
        es.close();
        renderError(data.message);
        setButtonLoading(button, false);
      } else {
        const msg = data.message || `Executing: ${data.status}`;
        const color = data.status.includes('done') || data.status === 'searching' ? 'var(--success)' : 'var(--accent)';
        progressEl.innerHTML += `<div style="color: ${color}; margin-top: 5px;">> ${msg}</div>`;
      }
    };

    es.onerror = (err) => {
      console.error("SSE Error:", err);
      es.close();
      setButtonLoading(button, false);
      showToast("RESEARCH_LIMIT", "Research stream interrupted. Check terminal logs.", "danger");
    };

  } catch (error) {
    renderError(error);
    setButtonLoading(button, false);
  }
}

async function runBacktest() {
  const button = byId("btn-backtest");
  if (!button) return;
  setButtonLoading(button, true, "Backtesting...");
  try {
    const stockEl = byId("backtest-stock");
    const exchEl = byId("backtest-exchange");
    const daysEl = byId("backtest-days");

    if (!stockEl) throw new Error("Input 'backtest-stock' not found.");

    const payload = {
      ticker: stockEl.value.trim(),
      exchange: exchEl ? exchEl.value : "NSE",
      days: daysEl ? parseInt(daysEl.value) : 30,
    };
    const data = await postJson("/api/backtest", payload);
    renderSummaryCards(data);
    renderJSON(data);

    // Load price data table for the backtested ticker
    loadTickerData(payload.ticker, payload.exchange);
  } catch (error) {
    renderError(error);
  } finally {
    setButtonLoading(button, false);
  }
}

async function checkWorkflow() {
  const id = elements.workflowId.value.trim();
  if (!id) {
    elements.workflowView.className = "mini-card";
    elements.workflowView.textContent = "Enter a workflow id first.";
    return;
  }
  const button = byId("btn-workflow-check");
  setButtonLoading(button, true, "Checking...");
  try {
    const data = await getJson(`/api/workflow/${encodeURIComponent(id)}`);
    elements.workflowView.className = "mini-card";
    elements.workflowView.innerHTML = workflowMarkup(data);
    renderJSON(data);
  } catch (error) {
    elements.workflowView.className = "mini-card status-bad";
    elements.workflowView.textContent = error.message;
  } finally {
    setButtonLoading(button, false);
  }
}

function toggleWorkflowPolling() {
  if (state.pollTimer) {
    clearInterval(state.pollTimer);
    state.pollTimer = null;
    elements.btnWorkflowPoll.textContent = "Auto Poll";
    return;
  }
  checkWorkflow();
  state.pollTimer = setInterval(checkWorkflow, 5000);
  elements.btnWorkflowPoll.textContent = "Stop Poll";
}

async function refreshHealth() {
  const button = byId("btn-health");
  setButtonLoading(button, true, "Refreshing...");
  try {
    const data = await getJson("/api/health");
    elements.healthView.innerHTML = healthMarkup(data);
    const statusText = byId("system-status-text");
    if (statusText) {
      statusText.textContent = data.status === "healthy" ? "System Healthy" : "System Degraded";
    }
    announceStatus(`Health status updated: ${data.status}`);
  } catch (error) {
    elements.healthView.className = "status-bad";
    elements.healthView.textContent = error.message;
  } finally {
    setButtonLoading(button, false);
  }
}

async function fetchAndRenderFundamentals(ticker) {
  try {
    const res = await getJson(`/api/fundamentals/${ticker}`);
    if (res.success && res.data.name) {
      elements.fundamentalsView.style.display = "block";
      elements.fundamentalsView.innerHTML = `
        <div style="color: var(--accent); font-weight: 700; margin-bottom: 8px;">COMPANY_PROFILE: ${res.data.name}</div>
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; font-size: 0.75rem;">
          <div><span style="color: var(--text-muted);">SECTOR:</span> ${res.data.sector}</div>
          <div><span style="color: var(--text-muted);">PE_RATIO:</span> ${res.data.pe_ratio.toFixed(2)}</div>
          <div><span style="color: var(--text-muted);">MKT_CAP:</span> ${(res.data.market_cap / 1e9).toFixed(2)}B</div>
          <div><span style="color: var(--text-muted);">BETA:</span> ${res.data.beta.toFixed(2)}</div>
        </div>
        <p style="margin-top: 12px; color: var(--text-muted); font-size: 0.7rem; line-height: 1.4;">${res.data.summary}</p>
      `;
    }
  } catch (e) {
    console.error("Fundamentals error", e);
  }
}

async function renderPortfolio() {
  try {
    const data = await getJson("/api/portfolio");
    if (!data.success) return;

    elements.portTbody.innerHTML = data.items.map(item => `
      <tr data-ticker="${item.ticker}">
        <td style="color: var(--accent); font-weight: 700;">${item.ticker}</td>
        <td>${item.quantity}</td>
        <td>${item.avg_price.toFixed(2)}</td>
        <td>--</td>
        <td>--</td>
        <td>--</td>
        <td><button class="btn-ghost" style="color: var(--danger);" onclick="updatePortfolio('${item.ticker}', 'remove')">REMOVE</button></td>
      </tr>
    `).join("") || '<tr><td colspan="7" style="text-align:center; padding: 20px;">NO_DATA</td></tr>';
  } catch (e) {
    console.error(e);
  }
}

async function updatePortfolioManual() {
  const ticker = byId("port-ticker").value.trim().toUpperCase();
  const qty = parseFloat(byId("port-qty").value) || 0;
  const price = parseFloat(byId("port-price").value) || 0;

  if (!ticker) return;
  await postJson("/api/portfolio", { ticker, quantity: qty, avg_price: price, action: "add" });
  renderPortfolio();
  announceStatus(`Position added for ${ticker}`);
}

// Global for inline onclick
window.updatePortfolio = async (ticker, action) => {
  await postJson("/api/portfolio", { ticker, action });
  renderPortfolio();
  announceStatus(`Portfolio ${action} for ${ticker}`);
};

async function renderWatchlist() {
  try {
    const data = await getJson("/api/watchlist");
    if (!data.success) return;

    elements.watchTbody.innerHTML = data.items.map(item => `
      <tr data-ticker="${item.ticker}">
        <td style="color: var(--accent); font-weight: 700;">${item.ticker}</td>
        <td>--</td>
        <td><span class="status-good">MONITORING</span></td>
        <td>${item.exchange}</td>
        <td><button class="btn-ghost" style="color: var(--danger);" onclick="updateWatchlist('${item.ticker}', 'remove')">REMOVE</button></td>
      </tr>
    `).join("") || '<tr><td colspan="5" style="text-align:center; padding: 20px;">EMPTY_RADAR</td></tr>';
  } catch (e) {
    console.error(e);
  }
}

async function updateWatchlistManual() {
  const ticker = byId("watch-ticker").value.trim().toUpperCase();
  if (!ticker) return;
  await postJson("/api/watchlist", { ticker, action: "add" });
  renderWatchlist();
  announceStatus(`Watchlist add for ${ticker}`);
}

window.updateWatchlist = async (ticker, action) => {
  await postJson("/api/watchlist", { ticker, action });
  renderWatchlist();
  announceStatus(`Watchlist ${action} for ${ticker}`);
};

async function runScanner() {
  if (!elements.scanPreset) {
    showToast("SCAN_FAILED", "Scanner configuration missing from UI.", "danger");
    return;
  }
  const preset = elements.scanPreset.value;
  setButtonLoading(elements.btnRunScan, true, "Scanning...");
  elements.scannerTbody.innerHTML = '<tr><td colspan="7" style="text-align:center; padding: 40px; color: var(--accent);">INITIALIZING_PARALLEL_SCAN...</td></tr>';

  try {
    const data = await postJson("/api/scan", { preset });
    if (elements.scanMeta) {
      elements.scanMeta.textContent = `// PRESET: ${preset} // COUNT: ${data.count}`;
    }

    if (data.results.length === 0) {
      elements.scannerTbody.innerHTML = '<tr><td colspan="7" style="text-align:center; padding: 40px;">NO_RESULTS_FOUND</td></tr>';
      return;
    }

    elements.scannerTbody.innerHTML = data.results.map(item => {
      const changeClass = item.change_pct >= 0 ? 'cell-positive' : 'cell-negative';
      const aiClass = item.ai_direction === 'UP' ? 'cell-positive' : 'cell-negative';
      const guessedExchange = item.ticker?.endsWith(".NS")
        ? "NSE"
        : item.ticker?.endsWith(".BO")
          ? "BSE"
          : (preset === "BLUECHIP_US" ? "NASDAQ" : "NSE");
      return `
        <tr data-ticker="${item.ticker}" onclick="loadTickerData('${item.ticker}', '${guessedExchange}')" style="cursor: pointer;" title="Click to load price data">
          <td style="color: var(--text-main); font-weight: 700;">${item.ticker}</td>
          <td class="cell-val">${(item.price || 0).toFixed(2)}</td>
          <td class="${changeClass}">${(item.change_pct || 0).toFixed(2)}%</td>
          <td>--</td>
          <td>${(item.rsi || 0).toFixed(1)}</td>
          <td style="color: var(--accent); font-size: 0.7rem;">${item.signal || "N/A"}</td>
          <td class="${aiClass}" style="font-weight: 800;">${item.ai_direction || "N/A"}</td>
        </tr>
      `;
    }).join("");

  } catch (error) {
    announceStatus(`Scanner error: ${error.message}`);
    elements.scannerTbody.innerHTML = `<tr><td colspan="7" style="text-align:center; padding: 40px; color: var(--danger);">${error.message}</td></tr>`;
  } finally {
    setButtonLoading(elements.btnRunScan, false);
  }
}

function handleTabSwitch(event) {
  const tabId = event.target.dataset.tab;
  if (!tabId) return;

  // Update Buttons
  document.querySelectorAll(".tab-link").forEach(btn => {
    btn.classList.remove("active");
    btn.setAttribute("aria-selected", "false");
    btn.setAttribute("tabindex", "-1");
  });
  event.target.classList.add("active");
  event.target.setAttribute("aria-selected", "true");
  event.target.setAttribute("tabindex", "0");

  // Update Panes
  document.querySelectorAll(".tab-pane").forEach(pane => {
    pane.classList.remove("active");
    pane.setAttribute("hidden", "true");
  });
  const targetPane = byId(tabId);
  if (!targetPane) return;
  targetPane.classList.add("active");
  targetPane.removeAttribute("hidden");
  announceStatus(`${event.target.textContent.trim()} tab opened`);

  if (tabId === "tab-quant") {
    loadQuantumAnalytics();
  }
}

function bindEvents() {
  // Tab Switching
  document.querySelectorAll(".tab-link").forEach(btn => {
    btn.addEventListener("click", handleTabSwitch);
  });

  const tabButtons = Array.from(document.querySelectorAll(".tab-link"));
  const tabList = document.querySelector(".nav-tabs");
  if (tabList) {
    tabList.addEventListener("keydown", (event) => {
      if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
      event.preventDefault();
      const currentIndex = tabButtons.findIndex((btn) => btn === document.activeElement);
      if (currentIndex < 0) return;
      let nextIndex = currentIndex;
      if (event.key === "ArrowRight") nextIndex = (currentIndex + 1) % tabButtons.length;
      if (event.key === "ArrowLeft") nextIndex = (currentIndex - 1 + tabButtons.length) % tabButtons.length;
      if (event.key === "Home") nextIndex = 0;
      if (event.key === "End") nextIndex = tabButtons.length - 1;
      const nextTab = tabButtons[nextIndex];
      if (nextTab) {
        nextTab.focus();
        nextTab.click();
      }
    });
  }

  byId("predict-form").addEventListener("submit", (event) => {
    event.preventDefault();
    runPrediction(false);
  });
  byId("btn-quick").addEventListener("click", () => runPrediction(true));

  byId("research-form").addEventListener("submit", (event) => {
    event.preventDefault();
    runDeepResearch();
  });

  byId("backtest-form").addEventListener("submit", (event) => {
    event.preventDefault();
    runBacktest();
  });

  document.querySelectorAll(".btn-time").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".btn-time").forEach((x) => x.classList.remove("active"));
      btn.classList.add("active");
      if (!state.activeTicker) return;
      const period = btn.dataset.period || "2y";
      loadAdvancedInsights(state.activeTicker, state.activeExchange || "NSE", period);
    });
  });

  // Scanner
  elements.btnRunScan.addEventListener("click", runScanner);

  // Portfolio & Watchlist
  byId("btn-add-port").addEventListener("click", updatePortfolioManual);
  byId("btn-add-watch").addEventListener("click", updateWatchlistManual);

  elements.btnWorkflowPoll.addEventListener("click", toggleWorkflowPolling);
  byId("btn-health").addEventListener("click", refreshHealth);
  elements.btnRunRiskSim.addEventListener("click", runRiskImpactSimulation);

  // Chat Events
  elements.chatToggle.addEventListener("click", () => {
    elements.chatBox.classList.remove("hidden");
    elements.chatBox.setAttribute("aria-hidden", "false");
    elements.chatToggle.setAttribute("aria-expanded", "true");
    elements.chatInput.focus();
    announceStatus("Chat opened");
  });
  elements.chatClose.addEventListener("click", () => {
    elements.chatBox.classList.add("hidden");
    elements.chatBox.setAttribute("aria-hidden", "true");
    elements.chatToggle.setAttribute("aria-expanded", "false");
    elements.chatToggle.focus();
    announceStatus("Chat closed");
  });
  elements.chatInput.addEventListener("keypress", (e) => {
    if (e.key === "Enter") sendChatMessage();
  });
  if (elements.chatSend) {
    elements.chatSend.addEventListener("click", sendChatMessage);
  }

  // Initialize tab semantics for first render.
  document.querySelectorAll(".tab-pane").forEach((pane) => {
    if (pane.classList.contains("active")) {
      pane.removeAttribute("hidden");
    } else {
      pane.setAttribute("hidden", "true");
    }
  });
  if (elements.chatBox && elements.chatBox.classList.contains("hidden")) {
    elements.chatBox.setAttribute("aria-hidden", "true");
  }
}

function bootstrapApp() {
  bindEvents();
  stampKpiUpdate();
  initWebSocket();
  refreshHealth();

  const idleRun = () => {
    renderPortfolio();
    renderWatchlist();
  };

  if ("requestIdleCallback" in window) {
    window.requestIdleCallback(idleRun, { timeout: 1200 });
  } else {
    setTimeout(idleRun, 0);
  }
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", bootstrapApp, { once: true });
} else {
  bootstrapApp();
}

window.addEventListener("beforeunload", () => {
  if (state.wsInterval) {
    clearInterval(state.wsInterval);
    state.wsInterval = null;
  }
  if (state.ws && state.ws.readyState === WebSocket.OPEN) {
    state.ws.close();
  }
});


