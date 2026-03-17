"""Web dashboard for monitoring the trading system."""
import json
import logging
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from flask import Flask, jsonify, render_template_string

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Dashboard HTML (single-file, no external template dependency)
# ---------------------------------------------------------------------------
DASHBOARD_HTML = r"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>OpenClaw Trading Dashboard</title>
<style>
  :root {
    --bg: #0f1117; --card: #1a1d28; --border: #2a2d3a;
    --text: #e1e4eb; --muted: #8b8fa3; --green: #00c853;
    --red: #ff1744; --amber: #ffab00; --blue: #2979ff;
    --font: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: var(--font); background: var(--bg); color: var(--text); }
  .header { padding: 20px 32px; border-bottom: 1px solid var(--border);
            display: flex; justify-content: space-between; align-items: center; }
  .header h1 { font-size: 20px; font-weight: 600; }
  .header .status { font-size: 13px; color: var(--muted); }
  .header .status .dot { display: inline-block; width: 8px; height: 8px;
                         border-radius: 50%; margin-right: 6px; background: var(--green); }
  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
          gap: 16px; padding: 24px 32px; }
  .card { background: var(--card); border: 1px solid var(--border); border-radius: 10px;
          padding: 20px; }
  .card h2 { font-size: 14px; font-weight: 500; color: var(--muted); margin-bottom: 14px;
             text-transform: uppercase; letter-spacing: 0.05em; }
  .metric { display: flex; justify-content: space-between; align-items: baseline;
            margin-bottom: 10px; }
  .metric .label { font-size: 13px; color: var(--muted); }
  .metric .value { font-size: 15px; font-weight: 600; }
  .metric .value.positive { color: var(--green); }
  .metric .value.negative { color: var(--red); }
  .metric .value.warn { color: var(--amber); }
  .big-number { font-size: 32px; font-weight: 700; margin-bottom: 4px; }
  .big-label { font-size: 13px; color: var(--muted); }
  .bar-container { height: 8px; background: var(--border); border-radius: 4px;
                   margin-top: 8px; overflow: hidden; }
  .bar-fill { height: 100%; border-radius: 4px; transition: width 0.6s ease; }
  .bar-fill.ok { background: var(--green); }
  .bar-fill.warn { background: var(--amber); }
  .bar-fill.danger { background: var(--red); }
  table { width: 100%; border-collapse: collapse; font-size: 13px; }
  th { text-align: left; color: var(--muted); font-weight: 500; padding: 8px 0;
       border-bottom: 1px solid var(--border); }
  td { padding: 8px 0; border-bottom: 1px solid var(--border); }
  .pill { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px;
          font-weight: 600; }
  .pill.green { background: rgba(0,200,83,0.15); color: var(--green); }
  .pill.red { background: rgba(255,23,68,0.15); color: var(--red); }
  .pill.amber { background: rgba(255,171,0,0.15); color: var(--amber); }
  .pill.blue { background: rgba(41,121,255,0.15); color: var(--blue); }
  .wide { grid-column: 1 / -1; }
  .two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
  @media (max-width: 700px) { .grid { padding: 12px; } .two-col { grid-template-columns: 1fr; } }
</style>
</head>
<body>
<div class="header">
  <h1>OpenClaw Trading Dashboard</h1>
  <div class="status"><span class="dot" id="statusDot"></span><span id="statusText">Connecting...</span></div>
</div>
<div class="grid" id="dashboard">
  <div class="card">
    <h2>Account</h2>
    <div class="big-number" id="portfolioValue">--</div>
    <div class="big-label">Portfolio Value</div>
    <div style="margin-top:16px">
      <div class="metric"><span class="label">Cash</span><span class="value" id="cash">--</span></div>
      <div class="metric"><span class="label">Buying Power</span><span class="value" id="buyingPower">--</span></div>
      <div class="metric"><span class="label">Daily P&L</span><span class="value" id="dailyPnl">--</span></div>
    </div>
  </div>
  <div class="card">
    <h2>Risk Posture</h2>
    <div class="big-number" id="postureName" style="text-transform:capitalize">--</div>
    <div class="big-label">Active Posture</div>
    <div style="margin-top:16px">
      <div class="metric"><span class="label">Max Risk / Trade</span><span class="value" id="maxRisk">--</span></div>
      <div class="metric"><span class="label">Max Daily Loss</span><span class="value" id="maxDailyLoss">--</span></div>
      <div class="metric"><span class="label">Min Confidence</span><span class="value" id="minConf">--</span></div>
    </div>
  </div>
  <div class="card">
    <h2>Portfolio Heat</h2>
    <div class="metric"><span class="label">Current Heat</span><span class="value" id="heatValue">--</span></div>
    <div class="metric"><span class="label">Heat Limit</span><span class="value" id="heatLimit">--</span></div>
    <div class="metric"><span class="label">Utilization</span><span class="value" id="heatPct">--</span></div>
    <div class="bar-container"><div class="bar-fill ok" id="heatBar" style="width:0%"></div></div>
  </div>
  <div class="card">
    <h2>Portfolio Greeks</h2>
    <div class="two-col">
      <div><div class="metric"><span class="label">Net Delta</span><span class="value" id="netDelta">--</span></div>
           <div class="metric"><span class="label">Net Gamma</span><span class="value" id="netGamma">--</span></div></div>
      <div><div class="metric"><span class="label">Net Theta</span><span class="value" id="netTheta">--</span></div>
           <div class="metric"><span class="label">Net Vega</span><span class="value" id="netVega">--</span></div></div>
    </div>
  </div>
  <div class="card wide">
    <h2>Open Positions</h2>
    <table>
      <thead><tr><th>Symbol</th><th>Strategy</th><th>Size</th><th>Max Loss</th><th>Max Profit</th><th>Opened</th></tr></thead>
      <tbody id="positionsTable"><tr><td colspan="6" style="color:var(--muted)">No open positions</td></tr></tbody>
    </table>
  </div>
  <div class="card">
    <h2>IV Analysis</h2>
    <div id="ivTable" style="font-size:13px;color:var(--muted)">Loading...</div>
  </div>
  <div class="card">
    <h2>ML Model</h2>
    <div class="metric"><span class="label">Status</span><span class="value" id="mlStatus">--</span></div>
    <div class="metric"><span class="label">Accuracy</span><span class="value" id="mlAccuracy">--</span></div>
    <div class="metric"><span class="label">F1 Score</span><span class="value" id="mlF1">--</span></div>
    <div class="metric"><span class="label">Training Samples</span><span class="value" id="mlSamples">--</span></div>
  </div>
  <div class="card wide">
    <h2>Adjustment Recommendations</h2>
    <table>
      <thead><tr><th>Position</th><th>Action</th><th>Reason</th><th>Urgency</th></tr></thead>
      <tbody id="adjustmentsTable"><tr><td colspan="4" style="color:var(--muted)">No recommendations</td></tr></tbody>
    </table>
  </div>
</div>
<script>
const $ = id => document.getElementById(id);
const fmt = (n, d=2) => n == null ? '--' : Number(n).toLocaleString(undefined, {minimumFractionDigits:d, maximumFractionDigits:d});
const fmtPct = n => n == null ? '--' : (n * 100).toFixed(1) + '%';
const fmtMoney = n => n == null ? '--' : '$' + fmt(n);
const pnlClass = n => n > 0 ? 'positive' : n < 0 ? 'negative' : '';

function update(data) {
  // Account
  if (data.account) {
    $('portfolioValue').textContent = fmtMoney(data.account.portfolio_value);
    $('cash').textContent = fmtMoney(data.account.cash);
    $('buyingPower').textContent = fmtMoney(data.account.buying_power);
  }
  // Risk
  if (data.risk) {
    const r = data.risk;
    $('dailyPnl').textContent = fmtMoney(r.daily_pnl);
    $('dailyPnl').className = 'value ' + pnlClass(r.daily_pnl);
    $('postureName').textContent = r.active_posture || '--';
    const lim = r.risk_limits || {};
    $('maxRisk').textContent = fmtPct(lim.max_portfolio_risk_per_trade);
    $('maxDailyLoss').textContent = fmtPct(lim.max_daily_loss);
    $('minConf').textContent = lim.min_confidence != null ? lim.min_confidence.toFixed(2) : '--';
    $('heatValue').textContent = fmtMoney(r.portfolio_heat);
    $('heatLimit').textContent = fmtMoney(r.portfolio_heat_limit);
    const pct = r.heat_utilization_pct || 0;
    $('heatPct').textContent = pct.toFixed(1) + '%';
    $('heatPct').className = 'value ' + (pct > 80 ? 'negative' : pct > 50 ? 'warn' : 'positive');
    $('heatBar').style.width = Math.min(pct, 100) + '%';
    $('heatBar').className = 'bar-fill ' + (pct > 80 ? 'danger' : pct > 50 ? 'warn' : 'ok');
  }
  // Positions
  if (data.positions) {
    const tb = $('positionsTable');
    if (data.positions.length === 0) {
      tb.innerHTML = '<tr><td colspan="6" style="color:var(--muted)">No open positions</td></tr>';
    } else {
      tb.innerHTML = data.positions.map(p =>
        `<tr><td>${p.symbol}</td><td><span class="pill blue">${p.strategy||'--'}</span></td>` +
        `<td>${p.size||p.qty||'--'}</td><td>${fmtMoney(p.max_loss)}</td>` +
        `<td>${fmtMoney(p.max_profit)}</td><td>${p.opened_at ? p.opened_at.slice(0,16) : '--'}</td></tr>`
      ).join('');
    }
  }
  // Greeks
  if (data.greeks) {
    const g = data.greeks;
    $('netDelta').textContent = fmt(g.net_delta, 3);
    $('netGamma').textContent = fmt(g.net_gamma, 4);
    $('netTheta').textContent = fmt(g.net_theta, 2);
    $('netTheta').className = 'value ' + (g.net_theta < 0 ? 'negative' : 'positive');
    $('netVega').textContent = fmt(g.net_vega, 3);
  }
  // IV
  if (data.iv_data) {
    $('ivTable').innerHTML = data.iv_data.map(iv =>
      `<div class="metric"><span class="label">${iv.symbol}</span>` +
      `<span class="value">Rank ${fmtPct(iv.iv_rank)} | Pctl ${fmtPct(iv.iv_percentile)} | ` +
      `<span class="pill ${iv.regime==='low'?'green':iv.regime==='extreme'?'red':'amber'}">${iv.regime}</span></span></div>`
    ).join('');
  }
  // ML
  if (data.ml) {
    $('mlStatus').innerHTML = data.ml.trained
      ? '<span class="pill green">Trained</span>'
      : '<span class="pill amber">Not Trained</span>';
    $('mlAccuracy').textContent = data.ml.accuracy != null ? fmtPct(data.ml.accuracy) : '--';
    $('mlF1').textContent = data.ml.f1 != null ? fmt(data.ml.f1, 3) : '--';
    $('mlSamples').textContent = data.ml.sample_count || '--';
  }
  // Adjustments
  if (data.adjustments) {
    const tb = $('adjustmentsTable');
    if (data.adjustments.length === 0) {
      tb.innerHTML = '<tr><td colspan="4" style="color:var(--muted)">No recommendations</td></tr>';
    } else {
      tb.innerHTML = data.adjustments.map(a =>
        `<tr><td>${a.position_id||'--'}</td><td>${a.action}</td><td>${a.reason}</td>` +
        `<td><span class="pill ${a.urgency==='high'?'red':a.urgency==='medium'?'amber':'green'}">${a.urgency}</span></td></tr>`
      ).join('');
    }
  }
  // Status
  $('statusDot').style.background = 'var(--green)';
  $('statusText').textContent = 'Live | Updated ' + new Date().toLocaleTimeString();
}

async function poll() {
  try {
    const res = await fetch('/api/status');
    if (res.ok) update(await res.json());
  } catch (e) {
    $('statusDot').style.background = 'var(--red)';
    $('statusText').textContent = 'Disconnected';
  }
}
poll();
setInterval(poll, 5000);
</script>
</body>
</html>
"""


class DashboardServer:
    """Flask-based web dashboard for the trading system."""

    def __init__(
        self,
        risk_manager=None,
        broker=None,
        iv_analyzer=None,
        greeks_monitor=None,
        ml_enhancer=None,
        host: str = "0.0.0.0",
        port: int = 5000,
    ):
        self._risk_manager = risk_manager
        self._broker = broker
        self._iv_analyzer = iv_analyzer
        self._greeks_monitor = greeks_monitor
        self._ml_enhancer = ml_enhancer
        self._host = host
        self._port = port
        self._app = self._create_app()
        self._thread: Optional[threading.Thread] = None
        self._symbols: List[str] = []

    def set_symbols(self, symbols: List[str]):
        """Set the list of symbols to display IV data for."""
        self._symbols = symbols

    # ------------------------------------------------------------------
    # Flask app
    # ------------------------------------------------------------------
    def _create_app(self) -> Flask:
        app = Flask(__name__)
        app.logger.setLevel(logging.WARNING)  # reduce Flask noise

        @app.route("/")
        def index():
            return render_template_string(DASHBOARD_HTML)

        @app.route("/api/status")
        def api_status():
            return jsonify(self._collect_status())

        @app.route("/api/risk")
        def api_risk():
            if self._risk_manager:
                return jsonify(self._risk_manager.get_risk_report())
            return jsonify({})

        @app.route("/api/positions")
        def api_positions():
            if self._risk_manager:
                return jsonify(self._risk_manager.positions)
            return jsonify([])

        @app.route("/api/greeks")
        def api_greeks():
            greeks = self._get_portfolio_greeks()
            return jsonify(greeks)

        @app.route("/api/iv/<symbol>")
        def api_iv(symbol):
            if self._iv_analyzer:
                try:
                    data = self._iv_analyzer.get_iv_data(symbol)
                    return jsonify({
                        "symbol": data.symbol,
                        "iv_rank": data.iv_rank,
                        "iv_percentile": data.iv_percentile,
                        "current_iv": data.current_iv,
                        "hv_20": data.hv_20,
                        "hv_50": data.hv_50,
                        "regime": self._iv_analyzer.get_iv_regime(symbol),
                    })
                except Exception as e:
                    return jsonify({"error": str(e)}), 500
            return jsonify({})

        return app

    # ------------------------------------------------------------------
    # Data collection
    # ------------------------------------------------------------------
    def _collect_status(self) -> Dict:
        """Collect all dashboard data into a single response."""
        status: Dict = {}

        # Account
        if self._broker:
            try:
                status["account"] = self._broker.get_account()
            except Exception:
                status["account"] = {}

        # Risk report and positions
        if self._risk_manager:
            try:
                status["risk"] = self._risk_manager.get_risk_report()
                status["positions"] = list(self._risk_manager.positions)
            except Exception:
                status["risk"] = {}
                status["positions"] = []

        # Portfolio Greeks
        status["greeks"] = self._get_portfolio_greeks()

        # IV data for configured symbols
        status["iv_data"] = self._get_iv_summary()

        # ML model status
        status["ml"] = self._get_ml_status()

        # Adjustment recommendations
        status["adjustments"] = self._get_adjustments()

        return status

    def _get_portfolio_greeks(self) -> Dict:
        """Aggregate portfolio greeks."""
        if not self._greeks_monitor or not self._risk_manager:
            return {"net_delta": 0, "net_gamma": 0, "net_theta": 0, "net_vega": 0}
        try:
            pg = self._greeks_monitor.get_portfolio_greeks(self._risk_manager.positions)
            return {
                "net_delta": pg.net_delta,
                "net_gamma": pg.net_gamma,
                "net_theta": pg.net_theta,
                "net_vega": pg.net_vega,
            }
        except Exception:
            return {"net_delta": 0, "net_gamma": 0, "net_theta": 0, "net_vega": 0}

    def _get_iv_summary(self) -> List[Dict]:
        """Get IV data for all configured symbols."""
        if not self._iv_analyzer or not self._symbols:
            return []
        results = []
        for symbol in self._symbols:
            try:
                data = self._iv_analyzer.get_iv_data(symbol)
                regime = self._iv_analyzer.get_iv_regime(symbol)
                results.append({
                    "symbol": data.symbol,
                    "iv_rank": data.iv_rank,
                    "iv_percentile": data.iv_percentile,
                    "current_iv": data.current_iv,
                    "regime": regime,
                })
            except Exception as e:
                logger.debug(f"IV fetch failed for {symbol}: {e}")
        return results

    def _get_ml_status(self) -> Dict:
        """Get ML model status."""
        if not self._ml_enhancer:
            return {"trained": False}
        try:
            trained = self._ml_enhancer.is_trained()
            result = {"trained": trained}
            if trained and hasattr(self._ml_enhancer, "_metrics") and self._ml_enhancer._metrics:
                m = self._ml_enhancer._metrics
                result["accuracy"] = m.accuracy
                result["f1"] = m.f1
                result["sample_count"] = m.sample_count
            return result
        except Exception:
            return {"trained": False}

    def _get_adjustments(self) -> List[Dict]:
        """Get position adjustment recommendations."""
        if not self._greeks_monitor or not self._risk_manager:
            return []
        try:
            pg = self._greeks_monitor.get_portfolio_greeks(self._risk_manager.positions)
            recs = self._greeks_monitor.check_adjustments(pg, {})
            return [
                {
                    "position_id": r.position_id,
                    "action": r.action,
                    "reason": r.reason,
                    "urgency": r.urgency,
                }
                for r in recs
            ]
        except Exception:
            return []

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def start(self, background: bool = True):
        """Start the dashboard server."""
        if background:
            self._thread = threading.Thread(
                target=self._run_server, daemon=True, name="dashboard"
            )
            self._thread.start()
            logger.info(f"Dashboard started at http://{self._host}:{self._port}")
        else:
            self._run_server()

    def _run_server(self):
        self._app.run(
            host=self._host,
            port=self._port,
            debug=False,
            use_reloader=False,
        )

    def stop(self):
        """Stop is a no-op for daemon threads (they die with the process)."""
        logger.info("Dashboard stop requested")
