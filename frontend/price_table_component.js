// Enhanced table component for OHLCV data display.
class PriceDataTable {
  constructor(containerId) {
    this.container = byId(containerId);
    this.currentTicker = null;
    this.currentData = null;
    this.requestController = null;
  }

  getCurrencyCode(exchange = "NSE") {
    return exchange === "NSE" || exchange === "BSE" ? "INR" : "USD";
  }

  formatCurrency(value, exchange = "NSE") {
    const num = Number(value);
    const safe = Number.isFinite(num) ? num : 0;
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: this.getCurrencyCode(exchange),
      maximumFractionDigits: 2,
    }).format(safe);
  }

  renderFromPayload(data) {
    if (!data || !data.success) {
      this.showError((data && (data.error || data.detail)) || "Failed to load data");
      return;
    }
    this.currentTicker = data.ticker;
    this.currentData = data;
    this.render(data);
  }

  async loadTickerData(ticker, exchange = "NSE", period = "1mo") {
    try {
      if (this.requestController) {
        this.requestController.abort();
      }
      this.requestController = new AbortController();

      const response = await fetch(
        `/api/chart-data/${encodeURIComponent(ticker)}?exchange=${encodeURIComponent(exchange)}&period=${encodeURIComponent(period)}`,
        { signal: this.requestController.signal }
      );
      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || data.error || `Request failed (${response.status})`);
      }

      this.renderFromPayload(data);
    } catch (error) {
      if (error && error.name === "AbortError") return;
      console.error("Error loading ticker data:", error);
      this.showError(error.message);
    }
  }

  render(data) {
    const { table_data, current_price, ticker, exchange } = data;

    if (!table_data || table_data.length === 0) {
      this.showError("No data available");
      return;
    }

    const html = `
      <div class="price-data-table-container">
        <div class="table-header">
          <h3>${ticker} (${exchange}) - Price Data</h3>
          <div class="current-price-display">
            <div class="current-price">${this.formatCurrency(current_price.price, exchange)}</div>
            <div class="price-change ${current_price.change_pct >= 0 ? "positive" : "negative"}">
              ${current_price.change_pct >= 0 ? "+" : ""}${current_price.change_pct.toFixed(2)}%
              (${current_price.change >= 0 ? "+" : ""}${this.formatCurrency(current_price.change, exchange)})
            </div>
          </div>
        </div>

        <div class="table-controls">
          <div class="price-stats">
            <span class="stat">High: ${this.formatCurrency(current_price.high, exchange)}</span>
            <span class="stat">Low: ${this.formatCurrency(current_price.low, exchange)}</span>
            <span class="stat">Volume: ${this.formatVolume(current_price.volume)}</span>
          </div>
        </div>

        <div class="price-data-table-wrapper">
          <table class="price-data-table">
            <caption class="sr-only">Recent OHLCV rows for ${ticker}</caption>
            <thead>
              <tr>
                <th>Date</th>
                <th>Open</th>
                <th>High</th>
                <th>Low</th>
                <th>Close</th>
                <th>Change</th>
                <th>Change %</th>
                <th>Volume</th>
              </tr>
            </thead>
            <tbody>
              ${table_data.map((row) => `
                <tr class="${row.change_pct >= 0 ? "positive-row" : "negative-row"}">
                  <td class="date-cell">${this.formatDate(row.date)}</td>
                  <td class="price-cell">${this.formatCurrency(row.open, exchange)}</td>
                  <td class="price-cell">${this.formatCurrency(row.high, exchange)}</td>
                  <td class="price-cell">${this.formatCurrency(row.low, exchange)}</td>
                  <td class="price-cell">${this.formatCurrency(row.close, exchange)}</td>
                  <td class="change-cell ${row.change >= 0 ? "positive" : "negative"}">
                    ${row.change >= 0 ? "+" : ""}${this.formatCurrency(row.change, exchange)}
                  </td>
                  <td class="change-cell ${row.change_pct >= 0 ? "positive" : "negative"}">
                    ${row.change_pct >= 0 ? "+" : ""}${row.change_pct.toFixed(2)}%
                  </td>
                  <td class="volume-cell">${this.formatVolume(row.volume)}</td>
                </tr>
              `).join("")}
            </tbody>
          </table>
        </div>

        <div class="table-footer">
          <span>Showing last ${table_data.length} trading days</span>
          <button onclick="priceTable.exportToCSV()" class="btn-export" type="button">Export CSV</button>
        </div>
      </div>
    `;

    this.container.innerHTML = html;
    this.container.style.display = "block";
  }

  formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString("en-US", {
      day: "2-digit",
      month: "short",
      year: "numeric",
    });
  }

  formatVolume(volume) {
    const safe = Number(volume) || 0;
    if (safe >= 10000000) return `${(safe / 10000000).toFixed(1)}Cr`;
    if (safe >= 100000) return `${(safe / 100000).toFixed(1)}L`;
    if (safe >= 1000) return `${(safe / 1000).toFixed(1)}K`;
    return String(safe);
  }

  showError(message) {
    this.container.innerHTML = `
      <div class="price-data-error">
        <div class="error-icon">!</div>
        <div class="error-message">${message}</div>
        <button onclick="this.parentElement.parentElement.style.display='none'" class="btn-close" aria-label="Close panel">x</button>
      </div>
    `;
    this.container.style.display = "block";
  }

  exportToCSV() {
    if (!this.currentData || !this.currentData.table_data) return;

    const { table_data, ticker } = this.currentData;
    const headers = ["Date", "Open", "High", "Low", "Close", "Change", "Change %", "Volume"];
    const csvContent = [
      headers.join(","),
      ...table_data.map((row) => [
        row.date,
        row.open,
        row.high,
        row.low,
        row.close,
        row.change,
        row.change_pct,
        row.volume,
      ].join(",")),
    ].join("\n");

    const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = `${ticker}_price_data.csv`;
    link.style.display = "none";
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }

  hide() {
    this.container.style.display = "none";
  }
}

// Global price table instance
const priceTable = new PriceDataTable("price-data-table-container");

// Table-specific styles
const tableStyles = `
  .price-data-table-container {
    margin-top: 14px;
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    background: #fff;
    overflow: hidden;
  }

  .table-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 12px 14px;
    border-bottom: 1px solid var(--border);
    background: var(--bg-muted);
  }

  .table-header h3 {
    margin: 0;
    color: var(--text-primary);
    font-size: 1rem;
  }

  .current-price-display {
    text-align: right;
  }

  .current-price {
    font-size: 1.05rem;
    font-weight: 700;
    color: var(--text-primary);
    font-family: var(--font-data);
  }

  .price-change {
    font-size: 0.8rem;
    font-family: var(--font-data);
  }

  .price-change.positive {
    color: var(--success);
  }

  .price-change.negative {
    color: var(--danger);
  }

  .table-controls {
    padding: 10px 14px;
    border-bottom: 1px solid var(--border);
    background: #fff;
  }

  .price-stats {
    display: flex;
    gap: 14px;
    flex-wrap: wrap;
  }

  .price-stats .stat {
    font-size: 0.8rem;
    color: var(--text-secondary);
    font-family: var(--font-data);
  }

  .price-data-table-wrapper {
    max-height: 360px;
    overflow-y: auto;
  }

  .price-data-table {
    width: 100%;
    border-collapse: collapse;
    font-family: var(--font-data);
    font-size: 0.78rem;
  }

  .price-data-table thead {
    position: sticky;
    top: 0;
    background: var(--bg-muted);
    z-index: 10;
  }

  .price-data-table th,
  .price-data-table td {
    padding: 8px 10px;
    text-align: left;
    border-bottom: 1px solid var(--border);
  }

  .price-data-table th {
    font-weight: 600;
    color: var(--text-secondary);
    text-transform: uppercase;
    font-size: 0.68rem;
    letter-spacing: 0.04em;
  }

  .price-data-table tbody tr:hover {
    background: #f9fbff;
  }

  .price-data-table tbody tr.positive-row {
    border-left: 2px solid var(--success);
  }

  .price-data-table tbody tr.negative-row {
    border-left: 2px solid var(--danger);
  }

  .date-cell {
    color: var(--text-primary);
  }

  .price-cell,
  .change-cell {
    font-family: var(--font-data);
  }

  .change-cell.positive {
    color: var(--success);
  }

  .change-cell.negative {
    color: var(--danger);
  }

  .volume-cell {
    color: var(--text-secondary);
  }

  .table-footer {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 10px 14px;
    border-top: 1px solid var(--border);
    font-size: 0.75rem;
    color: var(--text-muted);
    background: #fff;
  }

  .btn-export {
    background: var(--accent);
    color: #fff;
    border: none;
    padding: 6px 10px;
    border-radius: var(--radius-sm);
    cursor: pointer;
    font-size: 0.72rem;
  }

  .btn-export:hover {
    background: var(--accent-hover);
  }

  .price-data-error {
    position: relative;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 10px;
    padding: 20px;
    text-align: center;
    color: var(--danger);
    background: #fff5f6;
  }

  .error-icon {
    font-size: 1rem;
    font-weight: 700;
  }

  .error-message {
    font-size: 0.88rem;
  }

  .btn-close {
    position: absolute;
    top: 6px;
    right: 8px;
    border: none;
    background: transparent;
    color: var(--text-muted);
    font-size: 1rem;
    cursor: pointer;
  }
`;

const tableStyleSheet = document.createElement("style");
tableStyleSheet.textContent = tableStyles;
document.head.appendChild(tableStyleSheet);

function autoLoadPriceTable(ticker, exchange = "NSE") {
  if (priceTable && ticker) {
    priceTable.loadTickerData(ticker, exchange);
  }
}
