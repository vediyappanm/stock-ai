// ============================================
// PRODUCTION ENHANCEMENTS FOR STK-ENGINE
// ============================================

// Loading Skeleton UI
function showLoadingSkeleton() {
  elements.summaryCards.innerHTML = `
    <div class="skeleton-card" style="grid-column: 1 / -1; animation: skeleton-pulse 1.5s ease-in-out infinite;">
      <div class="skeleton-header" style="display: flex; gap: 8px; margin-bottom: 16px;">
        <div class="skeleton-badge" style="width: 80px; height: 20px; background: var(--border); border-radius: 4px;"></div>
        <div class="skeleton-badge" style="width: 80px; height: 20px; background: var(--border); border-radius: 4px;"></div>
      </div>
      <div class="skeleton-title" style="width: 60%; height: 32px; background: var(--border); border-radius: 4px; margin-bottom: 16px;"></div>
      <div class="skeleton-text" style="width: 100%; height: 16px; background: var(--border); border-radius: 4px; margin-bottom: 8px;"></div>
      <div class="skeleton-text" style="width: 90%; height: 16px; background: var(--border); border-radius: 4px; margin-bottom: 24px;"></div>
      <div class="skeleton-grid" style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px;">
        <div class="skeleton-stat" style="height: 100px; background: var(--bg-surface); border: 1px solid var(--border); border-radius: 8px;"></div>
        <div class="skeleton-stat" style="height: 100px; background: var(--bg-surface); border: 1px solid var(--border); border-radius: 8px;"></div>
        <div class="skeleton-stat" style="height: 100px; background: var(--bg-surface); border: 1px solid var(--border); border-radius: 8px;"></div>
      </div>
    </div>
  `;

  if (elements.tickerMeta) {
    elements.tickerMeta.textContent = "// NEURAL_PROCESSING...";
  }
}

// SMA Calculation
function calculateSMA(data, period) {
  const smaData = [];
  for (let i = period - 1; i < data.length; i++) {
    let sum = 0;
    for (let j = 0; j < period; j++) {
      sum += data[i - j].close;
    }
    smaData.push({
      time: data[i].time,
      value: sum / period
    });
  }
  return smaData;
}

// Enhanced Chart with SMA overlays
function renderEnhancedTVChart(ohlcvData) {
  if (!ohlcvData || ohlcvData.length === 0) {
    console.warn("No OHLCV data for chart");
    elements.tvChartContainer.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100%;color:var(--text-muted);font-family:var(--font-data);">NO_CHART_DATA_AVAILABLE</div>';
    return;
  }

  if (!window.LightweightCharts) {
    console.error("LightweightCharts library not loaded");
    elements.tvChartContainer.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100%;color:var(--danger);font-family:var(--font-data);flex-direction:column;gap:10px;"><div>⚠️ Chart Library Not Loaded</div><div style="font-size:0.8rem;">Press Ctrl+F5 to reload</div></div>';
    return;
  }

  // Clean container
  if (state.tvChart) {
    try {
      state.tvChart.remove();
      state.tvChart = null;
    } catch (e) {
      console.error("Error removing old chart", e);
    }
  }

  elements.tvChartContainer.innerHTML = '';
  elements.tvChartContainer.style.position = 'relative';

  // Format and sanitize data
  const candleMap = new Map();
  ohlcvData.forEach(d => {
    try {
      if (!d.Date) return;
      const dateObj = new Date(d.Date);
      if (isNaN(dateObj.getTime())) return;

      const timeSec = Math.floor(dateObj.getTime() / 1000);

      // Prevent duplicates (LWC strict requirement)
      if (candleMap.has(timeSec)) return;

      // Validate OHLC bounds
      if (typeof d.Open !== 'number' || typeof d.Close !== 'number') return;

      candleMap.set(timeSec, {
        time: timeSec,
        open: d.Open,
        high: d.High || d.Open,
        low: d.Low || d.Open,
        close: d.Close,
        volume: d.Volume || 0
      });
    } catch (err) { }
  });

  const formattedData = Array.from(candleMap.values()).sort((a, b) => a.time - b.time);

  if (formattedData.length === 0) {
    elements.tvChartContainer.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100%;color:var(--text-muted);font-family:var(--font-data);">SANITIZATION_FAILED: NO_VALID_PNTS</div>';
    return;
  }

  // ── LightweightCharts API version shim ──
  // v3/v4: chart.addCandlestickSeries(opts)
  // v5:    chart.addSeries(LightweightCharts.CandlestickSeries, opts)
  function _addCandlestickSeries(chart, opts) {
    if (typeof chart.addCandlestickSeries === 'function') {
      return chart.addCandlestickSeries(opts);   // v3/v4
    }
    if (typeof chart.addSeries === 'function' && LightweightCharts.CandlestickSeries) {
      return chart.addSeries(LightweightCharts.CandlestickSeries, opts);   // v5
    }
    return null;
  }
  function _addHistogramSeries(chart, opts) {
    if (typeof chart.addHistogramSeries === 'function') {
      return chart.addHistogramSeries(opts);
    }
    if (typeof chart.addSeries === 'function' && LightweightCharts.HistogramSeries) {
      return chart.addSeries(LightweightCharts.HistogramSeries, opts);
    }
    return null;
  }
  function _addLineSeries(chart, opts) {
    if (typeof chart.addLineSeries === 'function') {
      return chart.addLineSeries(opts);
    }
    if (typeof chart.addSeries === 'function' && LightweightCharts.LineSeries) {
      return chart.addSeries(LightweightCharts.LineSeries, opts);
    }
    return null;
  }
  function _addAreaSeries(chart, opts) {
    if (typeof chart.addAreaSeries === 'function') {
      return chart.addAreaSeries(opts);
    }
    if (typeof chart.addSeries === 'function' && LightweightCharts.AreaSeries) {
      return chart.addSeries(LightweightCharts.AreaSeries, opts);
    }
    return null;
  }

  const chart = LightweightCharts.createChart(elements.tvChartContainer, {
    layout: {
      background: { type: 'solid', color: 'transparent' },
      textColor: '#8b949e',
      fontSize: 12,
      fontFamily: 'JetBrains Mono',
    },
    grid: {
      vertLines: { color: 'rgba(33, 38, 45, 0.2)' },
      horzLines: { color: 'rgba(33, 38, 45, 0.2)' },
    },
    rightPriceScale: {
      borderColor: 'rgba(48, 54, 61, 0.8)',
      autoScale: true,
      scaleMargins: { top: 0.1, bottom: 0.2 },
      alignLabels: true,
    },
    timeScale: {
      borderColor: 'rgba(48, 54, 61, 0.8)',
      timeVisible: true,
      secondsVisible: false,
      barSpacing: 10,
    },
    handleScroll: { mouseWheel: true, pressedMouseMove: true },
    handleScale: { axisPressedMouseMove: true, mouseWheel: true, pinch: true },
    crosshair: {
      mode: 0,
      vertLine: { color: '#00ffcc', width: 1, style: 3, labelBackgroundColor: '#00ffcc' },
      horzLine: { color: '#00ffcc', width: 1, style: 3, labelBackgroundColor: '#00ffcc' },
    }
  });

  // Verify chart object is valid (compatible with both v3/v4 and v5 APIs)
  const canAddSeries = chart &&
    (typeof chart.addCandlestickSeries === 'function' ||
      (typeof chart.addSeries === 'function' && LightweightCharts.CandlestickSeries));
  if (!canAddSeries) {
    console.error('Chart object invalid — neither addCandlestickSeries nor addSeries API found');
    elements.tvChartContainer.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100%;color:var(--danger);font-family:var(--font-data);flex-direction:column;gap:10px;"><div>⚠️ Chart Initialization Failed</div><div style="font-size:0.8rem;">Unsupported LightweightCharts version — contact support</div></div>';
    return;
  }

  chart.applyOptions({
    localization: {
      priceFormatter: price => price.toLocaleString(undefined, { minimumFractionDigits: 2 })
    },
  });

  // 1. Premium Area Series (for depth/glow) - Optional, fallback if not available
  let areaSeries = null;
  try {
    areaSeries = _addAreaSeries(chart, {
      topColor: 'rgba(0, 255, 204, 0.2)',
      bottomColor: 'rgba(0, 255, 204, 0)',
      lineColor: '#00ffcc',
      lineWidth: 1,
      priceLineVisible: false,
      lastValueVisible: false,
    });
  } catch (e) {
    // Area series not available in this version
  }

  // 2. High-Fidelity Candlestick Series
  let candlestickSeries;
  try {
    candlestickSeries = _addCandlestickSeries(chart, {
      upColor: '#00ffa3',
      downColor: '#ff2d55',
      borderDownColor: '#ff2d55',
      borderUpColor: '#00ffa3',
      wickDownColor: '#ff2d55',
      wickUpColor: '#00ffa3',
    });
    if (!candlestickSeries) throw new Error('Series returned null');
  } catch (e) {
    console.error('Failed to create candlestick series:', e);
    elements.tvChartContainer.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100%;color:var(--danger);font-family:var(--font-data);flex-direction:column;gap:10px;"><div>⚠️ Chart Series Creation Failed</div><div style="font-size:0.8rem;">Press Ctrl+F5 to reload</div></div>';
    return;
  }

  // 3. Institutional Volume Histogram
  let volumeSeries;
  try {
    volumeSeries = _addHistogramSeries(chart, {
      color: '#26a69a',
      priceFormat: { type: 'volume' },
      priceScaleId: '', // Overlay
    });
    if (volumeSeries) {
      volumeSeries.priceScale().applyOptions({
        scaleMargins: { top: 0.85, bottom: 0 },
      });
    }
  } catch (e) {
    // Volume series optional
  }

  // Set Baseline Data
  if (areaSeries) {
    try {
      areaSeries.setData(formattedData.map(d => ({ time: d.time, value: d.close })));
    } catch (e) {
      // Ignore area series data errors
    }
  }

  if (candlestickSeries) {
    candlestickSeries.setData(formattedData);
  }

  if (volumeSeries) {
    try {
      volumeSeries.setData(formattedData.map(d => ({
        time: d.time,
        value: d.volume,
        color: d.close >= d.open ? 'rgba(0, 255, 163, 0.15)' : 'rgba(255, 45, 85, 0.15)'
      })));
    } catch (e) {
      // Ignore volume series data errors
    }
  }

  // SMA Overlays
  try {
    if (formattedData.length >= 20) {
      const sma20Series = _addLineSeries(chart, { color: '#f2c94c', lineWidth: 1.5, title: 'SMA-20', priceLineVisible: false });
      if (sma20Series) sma20Series.setData(calculateSMA(formattedData, 20));
    }
    if (formattedData.length >= 50) {
      const sma50Series = _addLineSeries(chart, { color: '#58a6ff', lineWidth: 1.5, title: 'SMA-50', priceLineVisible: false });
      if (sma50Series) sma50Series.setData(calculateSMA(formattedData, 50));
    }
  } catch (e) {
    // SMA overlays optional
  }

  chart.timeScale().fitContent();
  state.tvChart = chart;
  state.tvSeries = candlestickSeries;
  if (areaSeries) {
    state.areaSeries = areaSeries; // Store for realtime updates
  }
  state.lastCandle = { ...formattedData[formattedData.length - 1] };

  // Add legend and controls
  addDynamicLegend(chart, candlestickSeries, formattedData);
  addTimeRangeSelector(chart, formattedData); // Moved here to be called after chart creation

  // Responsive Handling
  const resizeObserver = new ResizeObserver(entries => {
    if (entries.length === 0 || !entries[0].contentRect) return;
    const { width, height } = entries[0].contentRect;
    chart.resize(width, height);
    chart.timeScale().fitContent();
  });
  resizeObserver.observe(elements.tvChartContainer);
}

// Time Range Selector
function addTimeRangeSelector(chart, data) {
  const selector = document.createElement('div');
  selector.className = 'time-range-selector';
  selector.innerHTML = `
    <button class="range-btn active" data-range="all">ALL</button>
    <button class="range-btn" data-range="1y">1Y</button>
    <button class="range-btn" data-range="3m">3M</button>
    <button class="range-btn" data-range="1m">1M</button>
    <button class="range-btn" data-range="1w">1W</button>
    <button class="range-btn" data-range="1d">1D</button>
  `;

  elements.tvChartContainer.insertBefore(selector, elements.tvChartContainer.firstChild);

  selector.querySelectorAll('.range-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      selector.querySelectorAll('.range-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');

      const range = btn.dataset.range;
      const now = Math.floor(Date.now() / 1000);
      let from;

      switch (range) {
        case '1d': from = now - 86400; break;
        case '1w': from = now - 604800; break;
        case '1m': from = now - 2592000; break;
        case '3m': from = now - 7776000; break;
        case '1y': from = now - 31536000; break;
        default:
          chart.timeScale().fitContent();
          return;
      }

      chart.timeScale().setVisibleRange({ from, to: now });
    });
  });
}

// Dynamic Legend with OHLC
function addDynamicLegend(chart, series, data) {
  const legend = document.createElement('div');
  legend.className = 'chart-legend';
  legend.style.cssText = `
    position: absolute;
    top: 12px;
    left: 12px;
    background: rgba(13, 17, 23, 0.9);
    padding: 8px 12px;
    border-radius: 4px;
    font-family: var(--font-data);
    font-size: 0.75rem;
    color: var(--text-main);
    pointer-events: none;
    z-index: 10;
    border: 1px solid var(--border);
  `;

  const lastData = data[data.length - 1];
  const updateContent = (d) => {
    const change = d.close - d.open;
    const changePct = (change / d.open) * 100;
    legend.innerHTML = `
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
        <span style="color:var(--accent); font-weight:800; letter-spacing:1px; font-size:0.8rem;">MARKET_INTEL_v2</span>
        <span style="color:${change >= 0 ? '#3fb950' : '#f85149'}; font-weight:700;">${change >= 0 ? '▲' : '▼'} ${Math.abs(changePct).toFixed(2)}%</span>
      </div>
      <div style="display:grid; grid-template-columns: 1fr 1fr; gap:12px; font-size:0.75rem;">
        <div>OPEN: <span style="color:var(--text-main);">${d.open.toFixed(2)}</span></div>
        <div>HIGH: <span style="color:#00ffa3;">${d.high.toFixed(2)}</span></div>
        <div>LOW: <span style="color:#ff2d55;">${d.low.toFixed(2)}</span></div>
        <div>CLOSE: <span style="color:var(--text-main); font-weight:700;">${d.close.toFixed(2)}</span></div>
      </div>
    `;
  };

  updateContent(lastData);

  elements.tvChartContainer.style.position = 'relative';
  elements.tvChartContainer.appendChild(legend);

  // Update legend on crosshair move
  chart.subscribeCrosshairMove((param) => {
    if (!param.time || !param.seriesData.get(series)) {
      updateContent(state.lastCandle);
      return;
    }
    updateContent(param.seriesData.get(series));
  });

  window.updateDynamicLegendPulse = (candle) => {
    updateContent(candle);

    const header = legend.querySelector('div');
    if (header && !header.querySelector('.live-badge')) {
      const live = document.createElement('span');
      live.className = 'live-badge';
      live.style.cssText = 'font-size:0.6rem; background:var(--danger); color:white; padding:1px 4px; border-radius:3px; margin-left:8px; animation: pulse 1.5s infinite;';
      live.textContent = 'LIVE';
      header.appendChild(live);
    }
  };
}

// Override the original renderTVChart function
if (typeof renderTVChart !== 'undefined') {
  window.renderTVChart = renderEnhancedTVChart;
}

// Production enhancements loaded
if (window.location.hostname === 'localhost') {
  console.log('✅ STK-ENGINE Production Enhancements Loaded');
}
