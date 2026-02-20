// Enhanced Real-time UI Updates
function handleEnhancedRealtime(data) {
  // Silently log in production
  if (window.location.hostname === 'localhost') {
    console.log("📡 Enhanced Real-time Update:", data);
  }
  
  // Handle all price update variants
  if (data.type && data.type.startsWith("PRICE_UPDATE")) {
    updateEnhancedPriceUI(data);
    return;
  }
  
  switch(data.type) {
    case "ENHANCED_PRICE_UPDATE":
      updateEnhancedPriceUI(data);
      break;
      
    case "REALTIME_ALERT":
      showRealtimeAlert(data);
      break;
      
    case "SYSTEM_STATUS":
      updateSystemStatus(data);
      break;
      
    case "MARKET_STATUS":
      updateMarketIndices(data);
      break;
      
    default:
      // Silently ignore unknown types
      break;
  }
}

function updateEnhancedPriceUI(data) {
  const { ticker, price, change_pct, volume, high, low, open } = data;
  
  if (!ticker || !price) return;
  
  // Update price cache
  state.realtimePrices[ticker] = price;
  
  // Update Scanner Table
  updateScannerRow(ticker, price, change_pct, volume);
  
  // Update Portfolio
  updatePortfolioRow(ticker, price, change_pct);
  
  // Update Watchlist
  updateWatchlistRow(ticker, price, change_pct);
  
  // Update active prediction if ticker matches
  updateActivePrediction(ticker, price, change_pct);
  
  // Show visual indicator for real-time update
  showRealtimeIndicator(ticker, price, change_pct);
  
  // Show toast for significant changes (only if > 1% to avoid spam)
  if (Math.abs(change_pct) >= 1.0) {
    showToast(`${ticker} Alert`, `${ticker}: ${change_pct >= 0 ? '📈' : '📉'} ${change_pct.toFixed(2)}%`, 
                change_pct >= 0 ? "success" : "warn");
  }
}

function updateScannerRow(ticker, price, change_pct, volume) {
  const rows = elements.scannerTbody?.querySelectorAll("tr");
  if (!rows) return;
  
  rows.forEach(row => {
    const tickerCell = row.cells[0];
    if (tickerCell && tickerCell.textContent === ticker) {
      row.cells[1].textContent = `₹${price.toFixed(2)}`;
      
      const pctCell = row.cells[2];
      if (pctCell) {
        pctCell.textContent = `${change_pct >= 0 ? '+' : ''}${change_pct.toFixed(2)}%`;
        pctCell.className = change_pct >= 0 ? "cell-positive" : "cell-negative";
      }
      
      const volCell = row.cells[3];
      if (volCell && volume) {
        volCell.textContent = formatVolume(volume);
      }
      
      // Add pulse animation for significant changes
      if (Math.abs(change_pct) >= 1.0) {
        row.style.animation = "pulse 1s ease-in-out";
        setTimeout(() => row.style.animation = "", 1000);
      }
    }
  });
}

function updatePortfolioRow(ticker, price, change_pct) {
  const rows = elements.portTbody?.querySelectorAll("tr");
  if (!rows) return;
  
  rows.forEach(row => {
    if (row.cells[0].textContent === ticker) {
      const currentPriceCell = row.cells[3];
      const plCell = row.cells[4];
      const avgPrice = parseFloat(row.cells[2].textContent);
      
      if (currentPriceCell) {
        currentPriceCell.textContent = `₹${price.toFixed(2)}`;
      }
      
      if (plCell && !isNaN(avgPrice)) {
        const pl = ((price - avgPrice) / avgPrice) * 100;
        plCell.textContent = `${pl >= 0 ? '+' : ''}${pl.toFixed(2)}%`;
        plCell.className = pl >= 0 ? "cell-positive" : "cell-negative";
        
        // Update P&L value
        const quantity = parseFloat(row.cells[1].textContent);
        const plValue = (price - avgPrice) * quantity;
        const plValueCell = row.cells[5];
        if (plValueCell) {
          plValueCell.textContent = `₹${Math.abs(plValue).toFixed(2)}`;
          plValueCell.className = pl >= 0 ? "cell-positive" : "cell-negative";
        }
      }
    }
  });
}

function updateWatchlistRow(ticker, price, change_pct) {
  const rows = elements.watchTbody?.querySelectorAll("tr");
  if (!rows) return;
  
  rows.forEach(row => {
    if (row.cells[0].textContent === ticker) {
      const priceCell = row.cells[1];
      const changeCell = row.cells[2];
      
      if (priceCell) {
        priceCell.textContent = `₹${price.toFixed(2)}`;
      }
      
      if (changeCell) {
        changeCell.textContent = `${change_pct >= 0 ? '📈' : '📉'} ${change_pct.toFixed(2)}%`;
        changeCell.className = change_pct >= 0 ? "cell-positive" : "cell-negative";
      }
    }
  });
}

function updateActivePrediction(ticker, price, change_pct) {
  const metaElement = elements.tickerMeta;
  if (metaElement && metaElement.textContent.includes(ticker)) {
    // Update prediction display with current price
    const priceCards = document.querySelectorAll(".summary-card__value");
    priceCards.forEach(card => {
      if (card.textContent.includes("₹0.00") || card.textContent.includes("N/A")) {
        card.textContent = `₹${price.toFixed(2)}`;
        card.style.animation = "pulse 0.5s ease-in-out";
        setTimeout(() => card.style.animation = "", 500);
      }
    });
  }
}

function showRealtimeAlert(data) {
  const { ticker, level, change_pct, price, message } = data;
  
  // Create enhanced alert notification
  const alertType = level === "WARNING" ? "error" : "warn";
  showToast(`${ticker} ${level}`, message, alertType);
  
  // Update alert history in UI
  updateAlertHistory(data);
  
  // Flash relevant rows
  flashRow(ticker, level === "WARNING" ? "alert-flash-critical" : "alert-flash-warning");
}

function updateSystemStatus(data) {
  const statusElement = byId("system-status-pill");
  if (statusElement) {
    const { status, active_watchlist, active_portfolio, cached_symbols } = data;
    
    statusElement.innerHTML = `
      <span class="pulse-dot"></span> 
      ${status === "REALTIME_STARTED" ? "STREAMING_LIVE" : "SYSTEM_READY"}
      <span style="font-size: 0.7rem; margin-left: 8px;">
        (${active_watchlist + active_portfolio} symbols)
      </span>
    `;
  }
}

function updateMarketIndices(data) {
  const { indices } = data;
  
  // Update market indices display (add to dashboard if needed)
  const marketWidget = document.createElement("div");
  marketWidget.className = "market-indices-widget";
  marketWidget.innerHTML = `
    <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; margin-bottom: 16px;">
      ${Object.entries(indices).map(([symbol, data]) => `
        <div class="mini-card" style="padding: 8px; text-align: center;">
          <div style="font-size: 0.7rem; color: var(--text-muted);">${symbol.replace('^', '')}</div>
          <div style="font-weight: 600;">${data.price.toFixed(2)}</div>
          <div class="${data.change_pct >= 0 ? 'cell-positive' : 'cell-negative'}" style="font-size: 0.8rem;">
            ${data.change_pct >= 0 ? '+' : ''}${data.change_pct.toFixed(2)}%
          </div>
        </div>
      `).join('')}
    </div>
  `;
  
  // Insert into dashboard (if not already present)
  const existing = document.querySelector(".market-indices-widget");
  if (!existing) {
    const dashboard = document.querySelector(".result-panel");
    if (dashboard) {
      dashboard.insertBefore(marketWidget, dashboard.firstChild);
    }
  }
}

function updateAlertHistory(alert) {
  // Create or update alert history panel
  let historyPanel = byId("alert-history");
  if (!historyPanel) {
    historyPanel = document.createElement("div");
    historyPanel.id = "alert-history";
    historyPanel.className = "alert-history-panel";
    historyPanel.innerHTML = `
      <h3 style="color: var(--accent); margin-bottom: 12px;">🚨 Real-time Alerts</h3>
      <div id="alert-list" style="max-height: 200px; overflow-y: auto;"></div>
    `;
    
    // Insert into sidebar
    const sidebar = document.querySelector(".side-panel");
    if (sidebar) {
      sidebar.appendChild(historyPanel);
    }
  }
  
  const alertList = byId("alert-list");
  if (alertList) {
    const alertItem = document.createElement("div");
    alertItem.className = "alert-item";
    alertItem.innerHTML = `
      <div style="display: flex; justify-content: space-between; align-items: center; padding: 8px; border-bottom: 1px solid var(--border);">
        <div>
          <strong>${alert.ticker}</strong>
          <span style="color: ${alert.level === "WARNING" ? "var(--danger)" : "var(--warning)"};">
            ${alert.change_pct >= 0 ? '📈' : '📉'} ${alert.change_pct.toFixed(2)}%
          </span>
        </div>
        <div style="font-size: 0.7rem; color: var(--text-muted);">
          ${new Date(alert.timestamp).toLocaleTimeString()}
        </div>
      </div>
    `;
    
    alertList.insertBefore(alertItem, alertList.firstChild);
    
    // Keep only last 10 alerts
    while (alertList.children.length > 10) {
      alertList.removeChild(alertList.lastChild);
    }
  }
}

function flashRow(ticker, flashClass) {
  // Flash row in all tables
  ["scanner-tbody", "portfolio-tbody", "watchlist-tbody"].forEach(tableId => {
    const table = byId(tableId);
    if (table) {
      const rows = table.querySelectorAll("tr");
      rows.forEach(row => {
        if (row.cells[0] && row.cells[0].textContent === ticker) {
          row.classList.add(flashClass);
          setTimeout(() => row.classList.remove(flashClass), 2000);
        }
      });
    }
  });
}

function formatVolume(volume) {
  if (volume >= 10000000) {
    return `${(volume / 10000000).toFixed(1)}Cr`;
  } else if (volume >= 100000) {
    return `${(volume / 100000).toFixed(1)}L`;
  } else if (volume >= 1000) {
    return `${(volume / 1000).toFixed(1)}K`;
  }
  return volume.toString();
}

// Enhanced WebSocket message handler
function initEnhancedWebSocket() {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const wsUrl = `${protocol}//${window.location.host}/ws/stream`;
  
  const ws = new WebSocket(wsUrl);
  
  ws.onopen = () => {
    if (window.location.hostname === 'localhost') {
      console.log("🚀 Enhanced WebSocket connected to STK-STREAM");
    }
    showToast("STREAM_ACTIVE", "Real-time streaming enabled", "success");
    
    // Start heartbeat
    if (state.wsInterval) clearInterval(state.wsInterval);
    state.wsInterval = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send("ping");
      }
    }, 20000);
    
    // Request initial status
    ws.send(JSON.stringify({ type: "REQUEST_STATUS" }));
  };
  
  ws.onmessage = (event) => {
    // Handle plain text pong/ping responses BEFORE parsing
    if (typeof event.data === 'string' && (event.data === "pong" || event.data === "ping")) {
      return;
    }
    
    try {
      // Try to parse as JSON
      const data = JSON.parse(event.data);
      
      // Handle pong as object
      if (data === "pong" || data.type === "pong") {
        return;
      }
      
      // Handle enhanced real-time messages
      handleEnhancedRealtime(data);
      
    } catch (error) {
      // Silently ignore parse errors in production
      if (window.location.hostname === 'localhost') {
        console.log("WebSocket message parse error:", error.message);
      }
    }
  };
  
  ws.onerror = (error) => {
    if (window.location.hostname === 'localhost') {
      console.log("WebSocket error:", error);
    }
    showToast("STREAM_ERROR", "Real-time stream interrupted", "error");
  };
  
  ws.onclose = () => {
    if (window.location.hostname === 'localhost') {
      console.log("WebSocket disconnected");
    }
    if (state.wsInterval) {
      clearInterval(state.wsInterval);
      state.wsInterval = null;
    }
    
    // Auto-reconnect with exponential backoff
    setTimeout(() => {
      if (window.location.hostname === 'localhost') {
        console.log("🔄 Attempting to reconnect...");
      }
      initEnhancedWebSocket();
    }, 5000);
  };
  
  state.ws = ws;
}

// Add CSS animations for real-time updates
const enhancedStyles = `
  @keyframes pulse {
    0% { transform: scale(1); }
    50% { transform: scale(1.05); }
    100% { transform: scale(1); }
  }
  
  @keyframes alert-flash-warning {
    0%, 100% { background-color: transparent; }
    50% { background-color: rgba(255, 193, 7, 0.2); }
  }
  
  @keyframes alert-flash-critical {
    0%, 100% { background-color: transparent; }
    50% { background-color: rgba(220, 53, 69, 0.2); }
  }
  
  .alert-history-panel {
    margin-top: 16px;
    padding: 12px;
    border: 1px solid var(--border);
    border-radius: 8px;
    background: rgba(0, 0, 0, 0.3);
  }
  
  .alert-item {
    transition: all 0.3s ease;
  }
  
  .alert-item:hover {
    background: rgba(255, 255, 255, 0.05);
  }
  
  .market-indices-widget {
    margin-bottom: 16px;
  }
`;

// Inject enhanced styles
const styleSheet = document.createElement("style");
styleSheet.textContent = enhancedStyles;
document.head.appendChild(styleSheet);

// Replace existing WebSocket init with enhanced version
if (typeof initWebSocket !== 'undefined') {
  // Store original for fallback
  window.originalInitWebSocket = initWebSocket;
  // Replace with enhanced version
  window.initWebSocket = initEnhancedWebSocket;
}
