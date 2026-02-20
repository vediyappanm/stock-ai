// Real-time Visual Indicators
function showRealtimeIndicator(ticker, price, change_pct) {
  // Update system status pill
  const statusPill = document.getElementById('system-status-pill');
  if (statusPill) {
    statusPill.classList.add('pulse-active');
    setTimeout(() => statusPill.classList.remove('pulse-active'), 1000);
  }
  
  // Update KPI if it's the active ticker
  if (state.activeTicker && ticker.includes(state.activeTicker)) {
    updateLivePriceKpi(price, state.activeExchange);
    
    // Update trend indicator
    const trendEl = document.getElementById('kpi-trend');
    if (trendEl && change_pct !== undefined) {
      trendEl.textContent = change_pct >= 0 ? '↗ Bullish' : '↘ Bearish';
      trendEl.className = change_pct >= 0 ? 'cell-positive' : 'cell-negative';
    }
  }
  
  // Show floating notification for significant changes
  if (Math.abs(change_pct) >= 0.5) {
    showFloatingNotification(ticker, price, change_pct);
  }
}

function showFloatingNotification(ticker, price, change_pct) {
  const container = document.getElementById('realtime-notifications');
  if (!container) {
    // Create container if it doesn't exist
    const newContainer = document.createElement('div');
    newContainer.id = 'realtime-notifications';
    newContainer.style.cssText = `
      position: fixed;
      top: 80px;
      right: 20px;
      z-index: 1000;
      display: flex;
      flex-direction: column;
      gap: 10px;
      max-width: 300px;
    `;
    document.body.appendChild(newContainer);
  }
  
  const notification = document.createElement('div');
  const isPositive = change_pct >= 0;
  notification.className = 'realtime-notification';
  notification.style.cssText = `
    background: ${isPositive ? 'rgba(19, 143, 78, 0.95)' : 'rgba(214, 58, 69, 0.95)'};
    color: white;
    padding: 12px 16px;
    border-radius: 8px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    font-family: var(--font-data);
    font-size: 0.9rem;
    animation: slideInRight 0.3s ease-out;
    cursor: pointer;
  `;
  
  notification.innerHTML = `
    <div style="display: flex; justify-content: space-between; align-items: center;">
      <div>
        <div style="font-weight: 700;">${ticker}</div>
        <div style="font-size: 0.85rem; opacity: 0.9;">
          ${formatCurrency(price, state.activeExchange || 'NSE')} 
          <span style="margin-left: 8px;">${isPositive ? '📈' : '📉'} ${change_pct.toFixed(2)}%</span>
        </div>
      </div>
      <div style="font-size: 1.2rem;">⚡</div>
    </div>
  `;
  
  notification.onclick = () => notification.remove();
  
  const notifContainer = document.getElementById('realtime-notifications');
  if (notifContainer) {
    notifContainer.appendChild(notification);
    
    // Auto-remove after 5 seconds
    setTimeout(() => {
      notification.style.animation = 'slideOutRight 0.3s ease-in';
      setTimeout(() => notification.remove(), 300);
    }, 5000);
  }
}

// Add CSS animations
if (!document.getElementById('realtime-animations')) {
  const style = document.createElement('style');
  style.id = 'realtime-animations';
  style.textContent = `
    @keyframes slideInRight {
      from {
        transform: translateX(400px);
        opacity: 0;
      }
      to {
        transform: translateX(0);
        opacity: 1;
      }
    }
    
    @keyframes slideOutRight {
      from {
        transform: translateX(0);
        opacity: 1;
      }
      to {
        transform: translateX(400px);
        opacity: 0;
      }
    }
    
    .pulse-active {
      animation: pulse 1s ease-in-out;
    }
    
    @keyframes pulse {
      0%, 100% {
        opacity: 1;
      }
      50% {
        opacity: 0.7;
        transform: scale(1.05);
      }
    }
  `;
  document.head.appendChild(style);
}

// Export functions
window.showRealtimeIndicator = showRealtimeIndicator;
window.showFloatingNotification = showFloatingNotification;
