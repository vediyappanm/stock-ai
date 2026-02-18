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
};

// --- Core Utilities ---
function pretty(value) {
  return JSON.stringify(value, null, 2);
}

function setButtonLoading(button, loading, text = "Loading...") {
  if (!button) return;
  if (loading) {
    button.dataset.label = button.textContent;
    button.textContent = text;
    button.disabled = true;
  } else {
    button.textContent = button.dataset.label || button.textContent;
    button.disabled = false;
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

function renderError(error) {
  const message = typeof error === 'string' ? error : (error.message || JSON.stringify(error));
  elements.summaryCards.innerHTML = `
    <div class="summary-card" style="border-left: 4px solid var(--danger); grid-column: 1 / -1;">
      <div class="summary-card__label" style="color: var(--danger);">ERROR_ENCOUNTERED</div>
      <div class="summary-card__value" style="font-size: 0.8rem; white-space: pre-wrap;">${message}</div>
    </div>
  `;
  elements.resultJson.textContent = message;
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
  elements.btAnalytics.style.display = "none";
  elements.riskProtocol.style.display = "none";
}

function renderTVChart(ohlcvData) {
  if (!ohlcvData || ohlcvData.length === 0) return;
  if (!window.LightweightCharts) return;
  if (state.tvChart) {
    state.tvChart.remove();
  }
  const chart = LightweightCharts.createChart(elements.tvChartContainer, {
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
    localization: { priceFormatter: price => `₹${price.toFixed(2)}` },
  });

  const candlestickSeries = chart.addCandlestickSeries({
    upColor: '#00ffa3', downColor: '#ff2d55',
    borderDownColor: '#ff2d55', borderUpColor: '#00ffa3',
    wickDownColor: '#ff2d55', wickUpColor: '#00ffa3',
  });

  const volumeSeries = chart.addHistogramSeries({
    color: '#26a69a',
    priceFormat: { type: 'volume' },
    priceScaleId: '', // set as overlay
  });

  volumeSeries.priceScale().applyOptions({
    scaleMargins: { top: 0.8, bottom: 0 },
  });

  const formattedData = ohlcvData.map(d => ({
    time: Math.floor(new Date(d.Date).getTime() / 1000),
    open: d.Open, high: d.High, low: d.Low, close: d.Close,
    volume: d.Volume || 0
  })).sort((a, b) => a.time - b.time);

  candlestickSeries.setData(formattedData);
  volumeSeries.setData(formattedData.map(d => ({
    time: d.time,
    value: d.volume,
    color: d.close >= d.open ? 'rgba(0, 255, 163, 0.3)' : 'rgba(255, 45, 85, 0.3)'
  })));

  chart.timeScale().fitContent();
  state.tvChart = chart;
  state.tvSeries = candlestickSeries;
  state.lastCandle = formattedData[formattedData.length - 1];
}

function showToast(title, message, type = "info") {
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

    // Pulse Heartbeat to prevent timeouts
    if (state.wsInterval) clearInterval(state.wsInterval);
    state.wsInterval = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send("ping");
      }
    }, 20000); // 20s heartbeat
  };

  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);

    if (data.type === "PRICE_UPDATE") {
      state.realtimePrices[data.ticker] = data.price;
      updateLiveUI(data.ticker, data.price, data.change_pct);
    } else if (data.type === "ALERT") {
      showToast(`ALERT: ${data.ticker}`, data.message, "warn");
    }
  };

  ws.onclose = () => {
    console.log("WebSocket disconnected");
    setTimeout(initWebSocket, 5000); // Reconnect
  };

  state.ws = ws;
}

function updateLiveUI(ticker, price, change) {
  // Update Scanner Table if ticker exists
  const rows = elements.scannerTbody.querySelectorAll("tr");
  rows.forEach(row => {
    const tickerCell = row.cells[0];
    if (tickerCell && tickerCell.textContent === ticker) {
      row.cells[1].textContent = price.toFixed(2);
      const pctCell = row.cells[2];
      pctCell.textContent = `${change.toFixed(2)}%`;
      pctCell.className = change >= 0 ? "cell-positive" : "cell-negative";
    }
  });

  // Update Portfolio if ticker exists
  const portRows = elements.portTbody.querySelectorAll("tr");
  portRows.forEach(row => {
    if (row.cells[0].textContent === ticker) {
      const currentPriceCell = row.cells[3];
      const plCell = row.cells[4];
      const avgPrice = parseFloat(row.cells[2].textContent);

      currentPriceCell.textContent = price.toFixed(2);
      const pl = ((price - avgPrice) / avgPrice) * 100;
      plCell.className = pl >= 0 ? "cell-positive" : "cell-negative";
    }
  });

  // Real-time Chart Update (Candlestick Pulse)
  if (state.tvSeries && state.activeTicker === ticker && state.lastCandle) {
    state.lastCandle.close = price;
    if (price > state.lastCandle.high) state.lastCandle.high = price;
    if (price < state.lastCandle.low) state.lastCandle.low = price;
    state.tvSeries.update(state.lastCandle);
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

  // Standardize values
  const predicted = Number(pred.predicted_price || 0).toFixed(2);
  const trend = pred.trend || "N/A";
  const confidence = pred.confidence || "N/A";

  // 1. Build Narrative
  const companyName = fundamentals.name || ticker;
  const narrativeText = `
    ${companyName} (${ticker}), operating in the ${fundamentals.sector || 'Global'} market, 
    has shown significant performance cues in the ${fundamentals.industry || 'financial'} domain. 
    Our Neural Ensemble, synthesizing data across multiple regimes, projects a 
    <span class="${trend === 'Bullish' ? 'cell-positive' : 'cell-negative'}" style="font-weight:800;">${trend}</span> outlook 
    with a target price of <strong>₹${predicted}</strong>. 
    ${fundamentals.summary || 'Market dynamics suggest volatility with high-confidence signals detected in volume profiles.'}
  `;

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
          <div class="plx-stat-value">₹${predicted}</div>
        </div>
        <div class="plx-stat-card" style="border-left-color: ${trend === 'Bullish' ? 'var(--success)' : 'var(--danger)'}">
          <div class="plx-stat-label">Sentiment Trend</div>
          <div class="plx-stat-value" style="color: ${trend === 'Bullish' ? 'var(--success)' : 'var(--danger)'}">
            ${trend === 'Bullish' ? '↑' : '↓'} ${trend}
          </div>
        </div>
        <div class="plx-stat-card" style="border-left-color: var(--border-bright);">
          <div class="plx-stat-label">Neural Confidence</div>
          <div class="plx-stat-value">${confidence}</div>
        </div>
      </div>

      ${financials.length > 0 ? `
        <div class="result-header" style="border-bottom:none; margin-bottom: 12px;">
          <div class="header-main" style="font-size: 1.2rem;">FINANCIAL_HIGHLIGHTS</div>
        </div>
        <div class="plx-table-container">
          <table class="plx-table">
            <thead>
              <tr>
                <th>YEAR</th>
                <th>REVENUE ($M)</th>
                <th>NET INCOME ($M)</th>
                <th>EBIT ($M)</th>
                <th>GROWTH NOTES</th>
              </tr>
            </thead>
            <tbody>
              ${financials.map(f => `
                <tr>
                  <td>${f.year}</td>
                  <td>${(Number(f.revenue || 0) / 1000000).toFixed(0)}</td>
                  <td>${(Number(f.net_income || 0) / 1000000).toFixed(0)}</td>
                  <td>${(Number(f.ebit || 0) / 1000000).toFixed(0)}</td>
                  <td style="color: var(--accent); font-size: 0.7rem;">${f.growth_notes}</td>
                </tr>
              `).join("")}
            </tbody>
          </table>
        </div>
      ` : ''}

      <div class="plx-model-grid">
        <div class="result-header" style="border-bottom:none; margin-bottom: 16px;">
          <div class="header-main" style="font-size: 1rem; color: var(--text-muted);">NEURAL_ENSEMBLE_TRANSPARENCY</div>
        </div>
        ${renderModelBar("TRANSFORMER_LSTM", telemetry.lstm || 0, predicted)}
        ${renderModelBar("GRADIENT_BOOST_XGB", telemetry.xgboost || 0, predicted)}
        ${renderModelBar("RANDOM_FOREST_QUANT", telemetry.random_forest || 0, predicted)}
      </div>

      ${payload.research ? `
        <div class="explanation-area" style="margin-top: 32px; border: 1px solid var(--border); background: rgba(0,255,163,0.02);">
          <div class="result-header" style="border-bottom:none; padding-bottom: 0;">
            <div class="header-main" style="font-size: 1.1rem; color: var(--accent);">NEURAL_RESEARCH_CONTEXT</div>
          </div>
          <div style="font-size: 0.95rem; line-height: 1.6; margin: 16px 0;">
            ${payload.research.synthesis}
          </div>
          <div style="display: flex; flex-wrap: wrap; gap: 8px;">
            ${(payload.research.catalysts || []).map(c => `<div class="plx-badge" style="background:var(--bg-deep);">${c}</div>`).join("")}
          </div>
          <div style="margin-top: 16px; font-size: 0.7rem; color: var(--text-muted);">
            LATEST_INTEL: ${(payload.research.headlines || []).join(" | ")}
          </div>
        </div>
      ` : ''}
    </div>
  `;

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

  loadAdvancedInsights(ticker, payload.exchange || "NSE");
}

function renderModelBar(label, value, target) {
  const pct = Math.min(100, Math.max(10, (value / target) * 100));
  return `
    <div class="plx-model-bar-container">
      <div class="plx-model-header">
        <span>${label}</span>
        <span style="color: var(--accent);">₹${Number(value).toFixed(2)}</span>
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

async function loadAdvancedInsights(ticker, exchange) {
  if (!ticker || ticker === "N/A" || ticker === "null") return;

  state.activeTicker = ticker;

  // Load Chart
  try {
    const chartData = await getJson(`/api/chart-data/${ticker}?exchange=${exchange}`);
    if (chartData.success) {
      renderTVChart(chartData.ohlcv);
    }
  } catch (e) {
    console.error("Chart load error", e);
  }

  // Load Fundamentals
  fetchAndRenderFundamentals(ticker);
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
  try {
    const stockEl = byId("predict-stock");
    const exchEl = byId("predict-exchange");
    const dateEl = byId("predict-date");
    const modelEl = byId("predict-model");

    if (!stockEl) throw new Error("Input element 'predict-stock' not found.");

    const targetDate = dateEl?.value || null;

    const payload = {
      ticker: stockEl.value.trim(),
      exchange: exchEl ? exchEl.value : "NSE",
      target_date: targetDate && targetDate.trim() !== "" ? targetDate : null,
      model_type: modelEl ? modelEl.value : "ensemble",
      include_backtest: byId("predict-backtest")?.checked || false,
      include_sentiment: byId("predict-sentiment")?.checked || false,
      history_days: historyDays || 500
    };
    const data = await postJson(quick ? "/api/predict/quick" : "/api/predict", payload);
    renderSummaryCards(data);
    renderJSON(data);
  } catch (error) {
    renderError(error);
  } finally {
    setButtonLoading(button, false);
  }
}

async function runAnalyze() {
  const button = byId("btn-analyze");
  if (!button) return;
  setButtonLoading(button, true, "Analyzing...");
  try {
    const stockEl = byId("analyze-stock");
    const exchEl = byId("analyze-exchange");
    if (!stockEl) throw new Error("Input 'analyze-stock' not found.");

    const payload = {
      ticker: stockEl.value.trim(),
      exchange: exchEl ? exchEl.value : "NSE",
    };
    const data = await postJson("/api/analyze", payload);
    renderSummaryCards(data);
    renderJSON(data);
  } catch (error) {
    renderError(error);
  } finally {
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
      days: Number(daysEl ? daysEl.value : 30),
    };
    const data = await postJson("/api/backtest", payload);
    renderSummaryCards(data);
    renderJSON(data);
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
      <tr>
        <td style="color: var(--accent); font-weight: 700;">${item.ticker}</td>
        <td>${item.quantity}</td>
        <td>${item.avg_price.toFixed(2)}</td>
        <td>--</td>
        <td>--</td>
        <td><button class="btn-ghost" style="color: var(--danger);" onclick="updatePortfolio('${item.ticker}', 'remove')">REMOVE</button></td>
      </tr>
    `).join("") || '<tr><td colspan="6" style="text-align:center; padding: 20px;">NO_DATA</td></tr>';
  } catch (e) {
    console.error(e);
  }
}

async function updatePortfolioManual() {
  const ticker = byId("port-ticker").value;
  const qty = parseFloat(byId("port-qty").value) || 0;
  const price = parseFloat(byId("port-price").value) || 0;

  if (!ticker) return;
  await postJson("/api/portfolio", { ticker, quantity: qty, avg_price: price, action: "add" });
  renderPortfolio();
}

// Global for inline onclick
window.updatePortfolio = async (ticker, action) => {
  await postJson("/api/portfolio", { ticker, action });
  renderPortfolio();
};

async function renderWatchlist() {
  try {
    const data = await getJson("/api/watchlist");
    if (!data.success) return;

    elements.watchTbody.innerHTML = data.items.map(item => `
      <tr>
        <td style="color: var(--accent); font-weight: 700;">${item.ticker}</td>
        <td>${item.exchange}</td>
        <td><span class="status-good">MONITORING</span></td>
        <td><button class="btn-ghost" style="color: var(--danger);" onclick="updateWatchlist('${item.ticker}', 'remove')">REMOVE</button></td>
      </tr>
    `).join("") || '<tr><td colspan="4" style="text-align:center; padding: 20px;">EMPTY_RADAR</td></tr>';
  } catch (e) {
    console.error(e);
  }
}

async function updateWatchlistManual() {
  const ticker = byId("watch-ticker").value;
  if (!ticker) return;
  await postJson("/api/watchlist", { ticker, action: "add" });
  renderWatchlist();
}

window.updateWatchlist = async (ticker, action) => {
  await postJson("/api/watchlist", { ticker, action });
  renderWatchlist();
};

async function runScanner() {
  if (!elements.scanPreset) {
    showToast("SCAN_FAILED", "Scanner configuration missing from UI.", "danger");
    return;
  }
  const preset = elements.scanPreset.value;
  setButtonLoading(elements.btnRunScan, true, "Scanning...");
  elements.scannerTbody.innerHTML = '<tr><td colspan="6" style="text-align:center; padding: 40px; color: var(--accent);">INITIALIZING_PARALLEL_SCAN...</td></tr>';

  try {
    const data = await postJson("/api/scan", { preset });
    if (elements.scanMeta) {
      elements.scanMeta.textContent = `// PRESET: ${preset} // COUNT: ${data.count}`;
    }

    if (data.results.length === 0) {
      elements.scannerTbody.innerHTML = '<tr><td colspan="6" style="text-align:center; padding: 40px;">NO_RESULTS_FOUND</td></tr>';
      return;
    }

    elements.scannerTbody.innerHTML = data.results.map(item => {
      const changeClass = item.change_pct >= 0 ? 'cell-positive' : 'cell-negative';
      const aiClass = item.ai_direction === 'UP' ? 'cell-positive' : 'cell-negative';
      return `
        <tr>
          <td style="color: var(--text-main); font-weight: 700;">${item.ticker}</td>
          <td class="cell-val">${(item.price || 0).toFixed(2)}</td>
          <td class="${changeClass}">${(item.change_pct || 0).toFixed(2)}%</td>
          <td>${(item.rsi || 0).toFixed(1)}</td>
          <td style="color: var(--accent); font-size: 0.7rem;">${item.signal || "N/A"}</td>
          <td class="${aiClass}" style="font-weight: 800;">${item.ai_direction || "N/A"}</td>
        </tr>
      `;
    }).join("");

  } catch (error) {
    elements.scannerTbody.innerHTML = `<tr><td colspan="6" style="text-align:center; padding: 40px; color: var(--danger);">${error.message}</td></tr>`;
  } finally {
    setButtonLoading(elements.btnRunScan, false);
  }
}

function handleTabSwitch(event) {
  const tabId = event.target.dataset.tab;
  if (!tabId) return;

  // Update Buttons
  document.querySelectorAll(".tab-link").forEach(btn => btn.classList.remove("active"));
  event.target.classList.add("active");

  // Update Panes
  document.querySelectorAll(".tab-pane").forEach(pane => pane.classList.remove("active"));
  byId(tabId).classList.add("active");

  if (tabId === "tab-quant") {
    loadQuantumAnalytics();
  }
}

function bindEvents() {
  // Tab Switching
  document.querySelectorAll(".tab-link").forEach(btn => {
    btn.addEventListener("click", handleTabSwitch);
  });

  byId("predict-form").addEventListener("submit", (event) => {
    event.preventDefault();
    runPrediction(false);
  });
  byId("btn-quick").addEventListener("click", () => runPrediction(true));

  byId("analyze-form").addEventListener("submit", (event) => {
    event.preventDefault();
    runAnalyze();
  });

  byId("backtest-form").addEventListener("submit", (event) => {
    event.preventDefault();
    runBacktest();
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
    elements.chatInput.focus();
  });
  elements.chatClose.addEventListener("click", () => elements.chatBox.classList.add("hidden"));
  elements.chatInput.addEventListener("keypress", (e) => {
    if (e.key === "Enter") sendChatMessage();
  });
  if (elements.chatSend) {
    elements.chatSend.addEventListener("click", sendChatMessage);
  }
}

bindEvents();
refreshHealth();
renderPortfolio();
renderWatchlist();
initWebSocket();

