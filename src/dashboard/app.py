"""Web dashboard for monitoring the trading system."""
import json
import logging
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

from flask import Flask, jsonify, render_template_string, request

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
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
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
  .symbol-select { background: var(--bg); color: var(--text); border: 1px solid var(--border);
                   border-radius: 6px; padding: 6px 12px; font-size: 13px; margin-right: 8px;
                   cursor: pointer; outline: none; }
  .symbol-select:focus { border-color: var(--blue); }
  .period-btn { background: var(--bg); color: var(--muted); border: 1px solid var(--border);
                border-radius: 6px; padding: 4px 10px; font-size: 12px; cursor: pointer;
                margin-right: 4px; transition: all 0.2s; }
  .period-btn:hover { color: var(--text); border-color: var(--blue); }
  .period-btn.active { background: var(--blue); color: #fff; border-color: var(--blue); }
  .chart-controls { display: flex; align-items: center; margin-bottom: 14px; flex-wrap: wrap; gap: 6px; }
  .chart-wrapper { position: relative; height: 300px; }
  .ob-header { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 8px; }
  .ob-side-label { font-size: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em;
                   padding-bottom: 6px; border-bottom: 1px solid var(--border); }
  .ob-side-label.bids { color: var(--green); }
  .ob-side-label.asks { color: var(--red); }
  .ob-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; max-height: 400px;
             overflow-y: auto; }
  .ob-row { display: grid; grid-template-columns: 1fr 1fr 1fr 1fr; gap: 4px; font-size: 12px;
            padding: 3px 0; border-bottom: 1px solid rgba(42,45,58,0.5); }
  .ob-row.header { color: var(--muted); font-weight: 500; font-size: 11px; position: sticky;
                   top: 0; background: var(--card); }
  .ob-cell { text-align: right; }
  .ob-cell:first-child { text-align: left; }
  .ob-cell.bid-price { color: var(--green); }
  .ob-cell.ask-price { color: var(--red); }
  .quote-bar { display: flex; align-items: center; gap: 20px; margin-bottom: 14px;
               padding: 10px 14px; background: var(--bg); border-radius: 8px; }
  .quote-price { font-size: 24px; font-weight: 700; }
  .quote-change { font-size: 14px; font-weight: 600; }
  .quote-detail { font-size: 12px; color: var(--muted); }
  .loading-msg { color: var(--muted); font-size: 13px; padding: 20px 0; text-align: center; }
  @media (max-width: 700px) { .grid { padding: 12px; } .two-col { grid-template-columns: 1fr; } }
</style>
</head>
<body>
<div class="header">
  <h1>OpenClaw Trading Dashboard</h1>
  <div class="status"><span class="dot" id="statusDot"></span><span id="statusText">Connecting...</span></div>
</div>
<div class="grid" id="dashboard">
  <!-- Price Chart Card -->
  <div class="card wide">
    <h2>Price Chart</h2>
    <div class="chart-controls">
      <select class="symbol-select" id="chartSymbol"></select>
      <button class="period-btn active" data-period="5d">5D</button>
      <button class="period-btn" data-period="1mo">1M</button>
      <button class="period-btn" data-period="3mo">3M</button>
      <button class="period-btn" data-period="6mo">6M</button>
      <button class="period-btn" data-period="1y">1Y</button>
    </div>
    <div id="quoteBar" class="quote-bar" style="display:none">
      <div><span class="quote-price" id="quotePrice">--</span></div>
      <div><span class="quote-change" id="quoteChange">--</span></div>
      <div>
        <span class="quote-detail">O: <span id="quoteOpen">--</span></span>
        <span class="quote-detail" style="margin-left:10px">H: <span id="quoteHigh">--</span></span>
        <span class="quote-detail" style="margin-left:10px">L: <span id="quoteLow">--</span></span>
        <span class="quote-detail" style="margin-left:10px">V: <span id="quoteVol">--</span></span>
      </div>
    </div>
    <div class="chart-wrapper"><canvas id="priceChart"></canvas></div>
  </div>

  <!-- Options Order Book Card -->
  <div class="card wide">
    <h2>Options Chain</h2>
    <div class="chart-controls">
      <select class="symbol-select" id="obSymbol"></select>
      <select class="symbol-select" id="obExpiry">
        <option value="">Select expiration...</option>
      </select>
    </div>
    <div id="obContent">
      <div class="loading-msg">Select a symbol and expiration to view the options chain</div>
    </div>
  </div>

  <!-- Existing cards -->
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
const fmtVol = n => { if (n >= 1e9) return (n/1e9).toFixed(1)+'B'; if (n >= 1e6) return (n/1e6).toFixed(1)+'M'; if (n >= 1e3) return (n/1e3).toFixed(1)+'K'; return n; };

/* ---- Price Chart ---- */
let priceChart = null;
let currentPeriod = '5d';

function initPriceChart() {
  const ctx = $('priceChart').getContext('2d');
  priceChart = new Chart(ctx, {
    type: 'line',
    data: { labels: [], datasets: [{
      label: 'Price', data: [], borderColor: '#2979ff', backgroundColor: 'rgba(41,121,255,0.08)',
      borderWidth: 1.5, pointRadius: 0, pointHitRadius: 10, fill: true, tension: 0.1
    }, {
      label: 'Volume', data: [], type: 'bar', backgroundColor: 'rgba(139,143,163,0.2)',
      borderWidth: 0, yAxisID: 'volume', order: 1
    }]},
    options: {
      responsive: true, maintainAspectRatio: false, interaction: { intersect: false, mode: 'index' },
      plugins: { legend: { display: false },
        tooltip: { backgroundColor: '#1a1d28', titleColor: '#e1e4eb', bodyColor: '#8b8fa3',
                   borderColor: '#2a2d3a', borderWidth: 1, padding: 10,
                   callbacks: { label: ctx => ctx.dataset.label === 'Volume' ? 'Vol: ' + fmtVol(ctx.raw) : '$' + ctx.raw.toFixed(2) }}},
      scales: {
        x: { grid: { color: 'rgba(42,45,58,0.5)' }, ticks: { color: '#8b8fa3', maxTicksLimit: 10, font: { size: 11 }}},
        y: { position: 'right', grid: { color: 'rgba(42,45,58,0.5)' }, ticks: { color: '#8b8fa3', font: { size: 11 },
             callback: v => '$' + v.toFixed(v >= 100 ? 0 : 2) }},
        volume: { position: 'left', display: false, beginAtZero: true, grid: { display: false }}
      }
    }
  });
}

async function loadChart(symbol, period) {
  if (!symbol) return;
  try {
    const res = await fetch(`/api/price/${symbol}?period=${period}`);
    if (!res.ok) return;
    const data = await res.json();
    if (data.error) return;
    priceChart.data.labels = data.dates;
    priceChart.data.datasets[0].data = data.close;
    priceChart.data.datasets[0].label = symbol;
    priceChart.data.datasets[1].data = data.volume;
    // Color line based on trend
    const first = data.close[0], last = data.close[data.close.length - 1];
    const color = last >= first ? '#00c853' : '#ff1744';
    priceChart.data.datasets[0].borderColor = color;
    priceChart.data.datasets[0].backgroundColor = color === '#00c853' ? 'rgba(0,200,83,0.08)' : 'rgba(255,23,68,0.08)';
    priceChart.update('none');
    // Update quote bar
    if (data.quote) {
      $('quoteBar').style.display = 'flex';
      $('quotePrice').textContent = '$' + data.quote.price.toFixed(2);
      const chg = data.quote.change;
      const chgPct = data.quote.change_pct;
      $('quoteChange').textContent = (chg >= 0 ? '+' : '') + chg.toFixed(2) + ' (' + (chgPct >= 0 ? '+' : '') + chgPct.toFixed(2) + '%)';
      $('quoteChange').style.color = chg >= 0 ? 'var(--green)' : 'var(--red)';
      $('quoteOpen').textContent = data.quote.open.toFixed(2);
      $('quoteHigh').textContent = data.quote.high.toFixed(2);
      $('quoteLow').textContent = data.quote.low.toFixed(2);
      $('quoteVol').textContent = fmtVol(data.quote.volume);
    }
  } catch (e) { console.error('Chart load error:', e); }
}

/* ---- Options Order Book ---- */
async function loadExpirations(symbol) {
  if (!symbol) return;
  const sel = $('obExpiry');
  sel.innerHTML = '<option value="">Loading...</option>';
  try {
    const res = await fetch(`/api/options/expirations/${symbol}`);
    if (!res.ok) return;
    const data = await res.json();
    sel.innerHTML = '<option value="">Select expiration...</option>';
    (data.expirations || []).forEach(exp => {
      const opt = document.createElement('option');
      opt.value = exp; opt.textContent = exp;
      sel.appendChild(opt);
    });
  } catch (e) { sel.innerHTML = '<option value="">Error loading</option>'; }
}

async function loadOptionsChain(symbol, expiry) {
  const container = $('obContent');
  if (!symbol || !expiry) {
    container.innerHTML = '<div class="loading-msg">Select a symbol and expiration to view the options chain</div>';
    return;
  }
  container.innerHTML = '<div class="loading-msg">Loading options chain...</div>';
  try {
    const res = await fetch(`/api/options/chain/${symbol}?expiry=${expiry}`);
    if (!res.ok) { container.innerHTML = '<div class="loading-msg">Failed to load options chain</div>'; return; }
    const data = await res.json();
    if (data.error) { container.innerHTML = `<div class="loading-msg">${data.error}</div>`; return; }
    renderOptionsChain(data, container);
  } catch (e) { container.innerHTML = '<div class="loading-msg">Error loading options chain</div>'; }
}

function renderOptionsChain(data, container) {
  const calls = data.calls || [];
  const puts = data.puts || [];
  const spot = data.underlying_price || 0;
  // Spot price divider row (spans all 4 columns within a side)
  const spotDivider = `<div style="grid-column:1/-1;display:flex;align-items:center;gap:6px;padding:5px 0;margin:2px 0">` +
    `<div style="flex:1;height:2px;background:var(--blue)"></div>` +
    `<span style="font-size:11px;font-weight:700;color:var(--blue);white-space:nowrap">$${spot.toFixed(2)}</span>` +
    `<div style="flex:1;height:2px;background:var(--blue)"></div></div>`;

  function buildSide(rows, type) {
    const isCall = type === 'call';
    let h = '<div class="ob-row header"><div class="ob-cell">Strike</div><div class="ob-cell">Bid</div><div class="ob-cell">Ask</div><div class="ob-cell">Vol</div></div>';
    let spotInserted = false;
    rows.forEach(r => {
      if (!spotInserted && r.strike > spot) {
        h += spotDivider;
        spotInserted = true;
      }
      const itm = isCall ? r.strike <= spot : r.strike >= spot;
      const bg = itm ? (isCall ? 'background:rgba(0,200,83,0.04)' : 'background:rgba(255,23,68,0.04)') : '';
      h += `<div class="ob-row" style="${bg}">` +
        `<div class="ob-cell" style="font-weight:600">${r.strike.toFixed(1)}</div>` +
        `<div class="ob-cell bid-price">${r.bid != null ? r.bid.toFixed(2) : '--'}</div>` +
        `<div class="ob-cell">${r.ask != null ? r.ask.toFixed(2) : '--'}</div>` +
        `<div class="ob-cell">${r.volume != null ? fmtVol(r.volume) : '--'}</div></div>`;
    });
    if (!spotInserted && rows.length > 0) h += spotDivider;
    return h;
  }

  let html = `<div style="display:flex;align-items:center;gap:8px;margin-bottom:12px;padding:8px 12px;background:var(--bg);border-radius:6px">` +
    `<span style="font-size:13px;color:var(--muted)">Underlying:</span>` +
    `<span style="font-size:18px;font-weight:700;color:var(--blue)">$${spot.toFixed(2)}</span></div>`;
  html += '<div class="ob-header"><div class="ob-side-label bids">CALLS</div><div class="ob-side-label asks">PUTS</div></div>';
  html += '<div class="ob-grid">';
  html += '<div>' + buildSide(calls, 'call') + '</div>';
  html += '<div>' + buildSide(puts, 'put') + '</div>';
  html += '</div>';
  container.innerHTML = html;
}

/* ---- Existing status update ---- */
function update(data) {
  if (data.account) {
    $('portfolioValue').textContent = fmtMoney(data.account.portfolio_value);
    $('cash').textContent = fmtMoney(data.account.cash);
    $('buyingPower').textContent = fmtMoney(data.account.buying_power);
  }
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
  if (data.greeks) {
    const g = data.greeks;
    $('netDelta').textContent = fmt(g.net_delta, 3);
    $('netGamma').textContent = fmt(g.net_gamma, 4);
    $('netTheta').textContent = fmt(g.net_theta, 2);
    $('netTheta').className = 'value ' + (g.net_theta < 0 ? 'negative' : 'positive');
    $('netVega').textContent = fmt(g.net_vega, 3);
  }
  if (data.iv_data) {
    $('ivTable').innerHTML = data.iv_data.map(iv =>
      `<div class="metric"><span class="label">${iv.symbol}</span>` +
      `<span class="value">Rank ${fmtPct(iv.iv_rank)} | Pctl ${fmtPct(iv.iv_percentile)} | ` +
      `<span class="pill ${iv.regime==='low'?'green':iv.regime==='extreme'?'red':'amber'}">${iv.regime}</span></span></div>`
    ).join('');
  }
  if (data.ml) {
    $('mlStatus').innerHTML = data.ml.trained
      ? '<span class="pill green">Trained</span>'
      : '<span class="pill amber">Not Trained</span>';
    $('mlAccuracy').textContent = data.ml.accuracy != null ? fmtPct(data.ml.accuracy) : '--';
    $('mlF1').textContent = data.ml.f1 != null ? fmt(data.ml.f1, 3) : '--';
    $('mlSamples').textContent = data.ml.sample_count || '--';
  }
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
  $('statusDot').style.background = 'var(--green)';
  $('statusText').textContent = 'Live | Updated ' + new Date().toLocaleTimeString();
}

/* ---- Init ---- */
async function init() {
  initPriceChart();
  // Load symbol list
  try {
    const res = await fetch('/api/symbols');
    const data = await res.json();
    const symbols = data.symbols || [];
    [['chartSymbol', true], ['obSymbol', false]].forEach(([id, autoLoad]) => {
      const sel = $(id);
      symbols.forEach(s => { const o = document.createElement('option'); o.value = s; o.textContent = s; sel.appendChild(o); });
      if (symbols.length > 0 && autoLoad) { sel.value = symbols[0]; loadChart(symbols[0], currentPeriod); }
    });
  } catch (e) {}
  // Chart symbol change
  $('chartSymbol').addEventListener('change', e => loadChart(e.target.value, currentPeriod));
  // Period buttons
  document.querySelectorAll('.period-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.period-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentPeriod = btn.dataset.period;
      loadChart($('chartSymbol').value, currentPeriod);
    });
  });
  // Options symbol change
  $('obSymbol').addEventListener('change', e => loadExpirations(e.target.value));
  $('obExpiry').addEventListener('change', e => loadOptionsChain($('obSymbol').value, e.target.value));
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
init();
poll();
setInterval(poll, 5000);
// Refresh chart every 60s during market hours
setInterval(() => { const h = new Date().getHours(); if (h >= 9 && h < 16) loadChart($('chartSymbol').value, currentPeriod); }, 60000);
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
        host: str = "127.0.0.1",
        port: int = 8080,
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
        self._symbols: List[str] = ["SPY", "TSLA", "AAPL", "JPM", "IBM"]

    def set_symbols(self, symbols: List[str]):
        """Set the list of symbols to display IV data for."""
        # Merge with defaults so core tickers are always available
        defaults = ["SPY", "TSLA", "AAPL", "JPM", "IBM"]
        merged = list(dict.fromkeys(symbols + defaults))  # preserves order, dedupes
        self._symbols = merged

    # ------------------------------------------------------------------
    # Flask app
    # ------------------------------------------------------------------
    def _create_app(self) -> Flask:
        app = Flask(__name__)
        app.logger.setLevel(logging.WARNING)  # reduce Flask noise
        logging.getLogger("werkzeug").setLevel(logging.WARNING)  # silence request logs

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

        @app.route("/api/symbols")
        def api_symbols():
            return jsonify({"symbols": self._symbols})

        @app.route("/api/price/<symbol>")
        def api_price(symbol):
            period = request.args.get("period", "1mo")
            return jsonify(self._get_price_data(symbol, period))

        @app.route("/api/options/expirations/<symbol>")
        def api_options_expirations(symbol):
            return jsonify(self._get_option_expirations(symbol))

        @app.route("/api/options/chain/<symbol>")
        def api_options_chain(symbol):
            expiry = request.args.get("expiry", "")
            return jsonify(self._get_options_chain(symbol, expiry))

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

    def _get_price_data(self, symbol: str, period: str = "1mo") -> Dict:
        """Fetch historical price data via yfinance."""
        try:
            import yfinance as yf
            valid_periods = {"5d", "1mo", "3mo", "6mo", "1y", "2y", "5y"}
            if period not in valid_periods:
                period = "1mo"
            # Choose interval based on period
            interval_map = {"5d": "15m", "1mo": "1h", "3mo": "1d", "6mo": "1d", "1y": "1d", "2y": "1wk", "5y": "1wk"}
            interval = interval_map.get(period, "1d")
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period=period, interval=interval)
            if hist.empty:
                return {"error": "No data available"}
            dates = [d.strftime("%b %d %H:%M") if interval in ("15m", "1h") else d.strftime("%b %d") for d in hist.index]
            close = [round(float(c), 2) for c in hist["Close"]]
            volume = [int(v) for v in hist["Volume"]]
            # Build quote summary from latest data
            quote = None
            if len(close) >= 2:
                last = close[-1]
                prev = close[0]
                quote = {
                    "price": last,
                    "change": round(last - prev, 2),
                    "change_pct": round((last - prev) / prev * 100, 2) if prev else 0,
                    "open": round(float(hist["Open"].iloc[-1]), 2),
                    "high": round(float(hist["High"].max()), 2),
                    "low": round(float(hist["Low"].min()), 2),
                    "volume": int(hist["Volume"].iloc[-1]),
                }
            return {"dates": dates, "close": close, "volume": volume, "quote": quote}
        except ImportError:
            return {"error": "yfinance not installed"}
        except Exception as e:
            logger.warning(f"Price data fetch failed for {symbol}: {e}")
            return {"error": str(e)}

    def _get_option_expirations(self, symbol: str) -> Dict:
        """Fetch available option expiration dates via yfinance, excluding weekends."""
        try:
            import yfinance as yf
            ticker = yf.Ticker(symbol)
            raw = list(ticker.options) if ticker.options else []
            # Filter out weekend dates (Saturday=5, Sunday=6)
            expirations = []
            for exp_str in raw:
                try:
                    dt = datetime.strptime(exp_str, "%Y-%m-%d")
                    if dt.weekday() < 5:  # Monday-Friday only
                        expirations.append(exp_str)
                except ValueError:
                    expirations.append(exp_str)  # keep if parsing fails
            return {"expirations": expirations}
        except ImportError:
            return {"error": "yfinance not installed", "expirations": []}
        except Exception as e:
            logger.warning(f"Options expirations fetch failed for {symbol}: {e}")
            return {"error": str(e), "expirations": []}

    def _get_options_chain(self, symbol: str, expiry: str) -> Dict:
        """Fetch options chain (calls + puts) for a given symbol and expiration."""
        if not expiry:
            return {"error": "No expiration date provided"}
        try:
            import yfinance as yf
            ticker = yf.Ticker(symbol)
            chain = ticker.option_chain(expiry)
            # Get underlying price
            info = ticker.history(period="1d")
            underlying = float(info["Close"].iloc[-1]) if not info.empty else 0
            def parse_side(df):
                rows = []
                for _, row in df.iterrows():
                    rows.append({
                        "strike": round(float(row["strike"]), 2),
                        "bid": round(float(row.get("bid", 0)), 2),
                        "ask": round(float(row.get("ask", 0)), 2),
                        "last": round(float(row.get("lastPrice", 0)), 2),
                        "volume": int(row.get("volume", 0)) if not (hasattr(row.get("volume", 0), '__class__') and str(row.get("volume", 0)) == 'nan') else 0,
                        "open_interest": int(row.get("openInterest", 0)) if not (hasattr(row.get("openInterest", 0), '__class__') and str(row.get("openInterest", 0)) == 'nan') else 0,
                        "iv": round(float(row.get("impliedVolatility", 0)) * 100, 1),
                    })
                return rows
            calls = parse_side(chain.calls)
            puts = parse_side(chain.puts)
            return {"calls": calls, "puts": puts, "underlying_price": round(underlying, 2), "expiry": expiry}
        except ImportError:
            return {"error": "yfinance not installed"}
        except Exception as e:
            logger.warning(f"Options chain fetch failed for {symbol}/{expiry}: {e}")
            return {"error": str(e)}

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
