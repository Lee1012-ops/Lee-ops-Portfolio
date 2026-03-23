'use strict';

// ── State ──────────────────────────────────
let currentData      = null;
let currentMode      = 'simple';   // 'simple' | 'full'
let priceChartInst   = null;
let simpleChartInst  = null;
let scoreChartInst   = null;
let radarChartInst   = null;
let rsiChartInst     = null;
let currentChartMode = 'price';
let simpleChartMode  = 'price';
let lastSimpleData   = null;

// ── Helpers ────────────────────────────────
const $ = id => document.getElementById(id);
const fmt = (v, dec = 2) => (v == null ? '—' : Number(v).toLocaleString('zh-CN', { minimumFractionDigits: dec, maximumFractionDigits: dec }));
const fmtBig = v => {
  if (v == null) return '—';
  const abs = Math.abs(v);
  if (abs >= 1e12) return (v / 1e12).toFixed(2) + ' T';
  if (abs >= 1e8)  return (v / 1e8).toFixed(2) + ' 亿';
  if (abs >= 1e4)  return (v / 1e4).toFixed(2) + ' 万';
  return v.toLocaleString();
};
const fmtVol = v => {
  if (v == null) return '—';
  if (v >= 1e8) return (v / 1e8).toFixed(2) + ' 亿手';
  if (v >= 1e4) return (v / 1e4).toFixed(2) + ' 万手';
  return v.toLocaleString() + ' 手';
};
const na = v => (v == null || v === 'N/A') ? null : v;
const display = (v, suffix = '', dec = 2) => na(v) == null ? '—' : fmt(v, dec) + suffix;
const colorClass = v => {
  if (v == null) return 'na';
  return v > 0 ? 'up' : v < 0 ? 'down' : '';
};
const signedFmt = (v, suf = '%', dec = 2) => {
  if (v == null) return '—';
  const s = v > 0 ? '+' : '';
  return s + fmt(v, dec) + suf;
};

function kvRow(key, value, cls = '') {
  return `<div class="kv-row">
    <span class="kv-key">${key}</span>
    <span class="kv-val ${cls}">${value}</span>
  </div>`;
}

function show(id) { $(id)?.classList.remove('hidden'); }
function hide(id) { $(id)?.classList.add('hidden'); }

// ── Mode Toggle ────────────────────────────
function setMode(mode) {
  currentMode = mode;
  $('mode-simple-btn').classList.toggle('active', mode === 'simple');
  $('mode-full-btn').classList.toggle('active', mode === 'full');
}

// ── Quick Search ───────────────────────────
function quickSearch(code, market) {
  $('stock-input').value = code;
  $('market-select').value = market;
  analyzeStock();
}

// ── Analyze ────────────────────────────────
async function analyzeStock() {
  const code   = $('stock-input').value.trim();
  const market = $('market-select').value;
  const days   = $('days-select').value;
  if (!code) { alert('请输入股票代码'); return; }

  setLoading(true);
  hide('welcome-screen');
  hide('error-panel');
  hide('dashboard');
  hide('simple-dashboard');

  const headers = { 'Content-Type': 'application/json', 'Accept': 'application/json' };
  const payload = { stock_code: code, market, days: Number(days) };

  try {
    if (currentMode === 'simple') {
      const resp = await fetch('/api/stock/simple', {
        method: 'POST',
        headers,
        body: JSON.stringify(payload),
      });
      const json = await resp.json();
      if (!resp.ok) {
        const d = json.detail;
        showError(typeof d === 'string' ? d : (Array.isArray(d) ? d.map(x => x.msg || JSON.stringify(x)).join('; ') : JSON.stringify(d)) || '请求失败');
        return;
      }
      if (json.status === 'error') { showError(json.message || '分析失败'); return; }
      lastSimpleData = json;
      renderSimpleDashboard(json);
      show('simple-dashboard');
    } else {
      const resp = await fetch('/api/stock/analyze', {
        method: 'POST',
        headers,
        body: JSON.stringify(payload),
      });
      const json = await resp.json();
      if (!resp.ok) {
        const d = json.detail;
        showError(typeof d === 'string' ? d : (Array.isArray(d) ? d.map(x => x.msg || JSON.stringify(x)).join('; ') : JSON.stringify(d)) || '请求失败');
        return;
      }
      if (json.status === 'error') { showError(json.message || '分析失败'); return; }
      currentData = json.data;
      renderDashboard(json.data);
      show('dashboard');
    }
  } catch (e) {
    showError('网络错误：' + e.message);
  } finally {
    setLoading(false);
  }
}

function setLoading(on) {
  $('btn-text').textContent = on ? '分析中…' : '分析';
  $('btn-spinner').classList.toggle('hidden', !on);
  $('analyze-btn').disabled = on;
}

function showError(msg) {
  $('error-msg').textContent = msg;
  show('error-panel');
}

// Enter key
$('stock-input').addEventListener('keydown', e => { if (e.key === 'Enter') analyzeStock(); });

// ── Tab Logic ──────────────────────────────
document.querySelectorAll('.tab').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.add('hidden'));
    btn.classList.add('active');
    const target = btn.getAttribute('data-tab');
    $(target)?.classList.remove('hidden');
    if (target === 'tab-technical' && currentData) renderRadar(currentData);
  });
});

// ── Render Dashboard ───────────────────────
function renderDashboard(d) {
  renderHeader(d);
  renderChart(d['历史数据']);
  renderRecommendation(d['投资建议']);
  renderValuation(d['估值指标'], d['财务指标'], d['基础信息']);
  renderTechnical(d['技术指标']);
  renderRisk(d['风险评估'], d['市场对比']);
  renderFundFlow(d['资金流向']);
  renderInstitution(d['机构持仓']);
  renderAnalyst(d['分析师评级']);
  renderLogics(d['投资建议']);
  renderHistory(d['历史数据']);
}

// ── Header ─────────────────────────────────
function renderHeader(d) {
  $('stock-name').textContent = d.stock_name || d.stock_code;
  $('stock-code-badge').textContent = d.stock_code;
  $('market-badge').textContent = d.market;

  const rt = d['实时行情'] || {};
  const price = rt.current_price;
  const chgPct = rt.change_percent;
  const chg = rt.change;
  const isUp = chgPct >= 0;

  $('current-price').textContent = price != null ? price.toLocaleString() : '—';
  const pch = $('price-change');
  pch.textContent = `${signedFmt(chg, '')} (${signedFmt(chgPct)})`;
  pch.className = 'price-change ' + (isUp ? 'up' : 'down');

  $('m-open').textContent    = display(rt.open, '');
  $('m-high').textContent    = display(rt.high, '');
  $('m-low').textContent     = display(rt.low, '');
  $('m-preclose').textContent = display(rt.pre_close, '');
  $('m-volume').textContent  = fmtVol(rt.volume ?? d['成交量额']?.volume);
  $('m-turnover').textContent = rt.turnover_rate != null ? display(rt.turnover_rate, '%') : '—';
  $('m-volratio').textContent = display(rt.volume_ratio, 'x');
  $('m-amplitude').textContent = display(rt.amplitude, '%');
}

// ── Price Chart ────────────────────────────
function renderChart(histData) {
  if (!histData?.history?.length) return;
  const hist = histData.history.slice().reverse();
  const labels = hist.map(r => r.date.slice(5));
  const closes = hist.map(r => r.close);
  const volumes = hist.map(r => r.volume);

  if (priceChartInst) { priceChartInst.destroy(); priceChartInst = null; }

  const ctx = $('priceChart').getContext('2d');
  const chartH = $('priceChart').parentElement.offsetHeight || 260;
  const grad = ctx.createLinearGradient(0, 0, 0, chartH);
  const isUp = closes.length > 1 && closes[closes.length - 1] >= closes[0];
  const mainColor = isUp ? '#3fb950' : '#f85149';
  grad.addColorStop(0, isUp ? 'rgba(63,185,80,.25)' : 'rgba(248,81,73,.25)');
  grad.addColorStop(1, 'rgba(0,0,0,0)');

  priceChartInst = new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [{
        label: '收盘价',
        data: closes,
        borderColor: mainColor,
        backgroundColor: grad,
        borderWidth: 2,
        pointRadius: 0,
        pointHoverRadius: 4,
        fill: true,
        tension: 0.3,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { intersect: false, mode: 'index' },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: '#1c2128',
          borderColor: '#30363d',
          borderWidth: 1,
          titleColor: '#8b949e',
          bodyColor: '#e6edf3',
        }
      },
      scales: {
        x: { ticks: { color: '#8b949e', maxTicksLimit: 8 }, grid: { color: 'rgba(255,255,255,.04)' } },
        y: { ticks: { color: '#8b949e' }, grid: { color: 'rgba(255,255,255,.04)' }, position: 'right' }
      }
    }
  });

  // store volume data for switching
  priceChartInst._volumeData = volumes;
  priceChartInst._closeData  = closes;
  priceChartInst._mainColor  = mainColor;
  priceChartInst._grad       = grad;
}

function switchChart(mode, btn) {
  document.querySelectorAll('.chart-tab').forEach(t => t.classList.remove('active'));
  btn.classList.add('active');
  currentChartMode = mode;
  if (!priceChartInst) return;
  const inst = priceChartInst;

  if (mode === 'volume') {
    inst.data.datasets[0].data = inst._volumeData;
    inst.data.datasets[0].label = '成交量';
    inst.data.datasets[0].borderColor = '#58a6ff';
    inst.data.datasets[0].backgroundColor = 'rgba(88,166,255,.15)';
  } else {
    inst.data.datasets[0].data = inst._closeData;
    inst.data.datasets[0].label = '收盘价';
    inst.data.datasets[0].borderColor = inst._mainColor;
    inst.data.datasets[0].backgroundColor = inst._grad;
  }
  inst.update();
}

// ── Recommendation ─────────────────────────
function renderRecommendation(rec) {
  if (!rec) return;
  const badge = $('rec-badge');
  badge.textContent = rec.recommendation || '—';
  const cls = {
    '强烈买入': 'rec-strong-buy', '买入': 'rec-buy',
    '持有': 'rec-hold', '减持': 'rec-sell', '卖出': 'rec-strong-sell'
  }[rec.recommendation] || 'rec-hold';
  badge.className = 'rec-badge ' + cls;

  const score = rec.评分卡?.综合评分 ?? 0;
  $('score-center').innerHTML = `${score}<br><small>综合</small>`;
  renderScoreDonut(score);

  $('tp-target').textContent  = display(rec.target_price, '');
  $('tp-high').textContent    = display(rec.target_price_high, '');
  $('tp-low').textContent     = display(rec.target_price_low, '');
  $('tp-risk').textContent    = rec.risk_level || '—';
  $('tp-horizon').textContent = rec.investment_horizon || '—';
  $('tp-suitable').textContent = rec.suitable_for || '—';
}

function renderScoreDonut(score) {
  if (scoreChartInst) { scoreChartInst.destroy(); scoreChartInst = null; }
  const color = score >= 70 ? '#3fb950' : score >= 50 ? '#e3b341' : '#f85149';
  const ctx = $('scoreChart').getContext('2d');
  scoreChartInst = new Chart(ctx, {
    type: 'doughnut',
    data: {
      datasets: [{
        data: [score, 100 - score],
        backgroundColor: [color, '#21262d'],
        borderWidth: 0,
        hoverOffset: 0,
      }]
    },
    options: {
      cutout: '72%',
      responsive: false,
      plugins: { legend: { display: false }, tooltip: { enabled: false } },
      animation: { duration: 800 }
    }
  });
}

// ── Valuation & Financials ──────────────────
function renderValuation(val, fin, basic) {
  const vEl = $('valuation-list');
  const fEl = $('financials-list');
  const bEl = $('basic-list');

  vEl.innerHTML = [
    kvRow('市值', fmtBig(val?.market_cap)),
    kvRow('市值 (USD)', fmtBig(val?.market_cap_usd)),
    kvRow('流通市值', fmtBig(val?.circulating_market_cap)),
    kvRow('市盈率 (静态)', display(val?.pe_ratio_static, 'x')),
    kvRow('市盈率 TTM', display(val?.pe_ttm, 'x')),
    kvRow('市净率 PB', display(val?.pb_ratio, 'x')),
    kvRow('市销率 PS(TTM)', display(val?.ps_ratio_ttm, 'x')),
    kvRow('EV/EBITDA', display(val?.ev_ebitda, 'x')),
    kvRow('股息率', display(val?.dividend_yield, '%')),
    kvRow('每股股息', display(val?.dividend_per_share, '')),
    kvRow('派息率', display(val?.payout_ratio, '%')),
  ].join('');

  fEl.innerHTML = [
    kvRow('EPS TTM', display(fin?.eps_ttm, '')),
    kvRow('EPS (摊薄)', display(fin?.eps_diluted, '')),
    kvRow('每股净资产 BVPS', display(fin?.bvps, '')),
    kvRow('ROE (%)', display(fin?.roe, '%'), colorClass(fin?.roe)),
    kvRow('ROA (%)', display(fin?.roa, '%'), colorClass(fin?.roa)),
    kvRow('毛利率', display(fin?.gross_margin, '%')),
    kvRow('营业利润率', display(fin?.operating_margin, '%')),
    kvRow('净利率', display(fin?.net_margin, '%')),
    kvRow('营收 TTM', fmtBig(fin?.revenue_ttm)),
    kvRow('营收增速 YoY', signedFmt(fin?.revenue_growth_yoy), colorClass(fin?.revenue_growth_yoy)),
    kvRow('净利润 TTM', fmtBig(fin?.profit_ttm)),
    kvRow('净利润增速 YoY', signedFmt(fin?.profit_growth_yoy), colorClass(fin?.profit_growth_yoy)),
    kvRow('资产负债率 D/E', display(fin?.debt_to_equity, '%')),
    kvRow('流动比率', display(fin?.current_ratio, 'x')),
    kvRow('速动比率', display(fin?.quick_ratio, 'x')),
    kvRow('自由现金流', fmtBig(fin?.free_cash_flow)),
  ].join('');

  bEl.innerHTML = [
    kvRow('交易所', basic?.exchange || '—'),
    kvRow('行业', basic?.industry || '—'),
    kvRow('板块', basic?.sector || '—'),
    kvRow('货币', basic?.currency || '—'),
    kvRow('上市日期', basic?.listing_date || '—'),
    kvRow('ISIN', basic?.isin || '—'),
    kvRow('官网', basic?.website ? `<a href="${basic.website}" target="_blank" style="color:var(--accent)">${basic.website}</a>` : '—'),
  ].join('');
}

// ── Technical ──────────────────────────────
function renderTechnical(tech) {
  if (!tech) return;
  const ma = tech['均线'] || {};
  const price = currentData?.['实时行情']?.current_price;

  const maEl = $('ma-list');
  maEl.innerHTML = ['ma5','ma10','ma20','ma60','ma120','ma250'].map(k => {
    const v = ma[k];
    const cls = (price && v) ? (price > v ? 'up' : 'down') : '';
    return kvRow(k.toUpperCase(), display(v, ''), cls);
  }).join('');

  const macd = tech.macd || {};
  $('macd-list').innerHTML = [
    kvRow('DIF', display(macd.dif, ''), colorClass(macd.dif)),
    kvRow('DEA', display(macd.dea, '')),
    kvRow('MACD 柱', display(macd.macd, ''), colorClass(macd.macd)),
    kvRow('信号', macd.signal || '—', macd.signal === '金叉' ? 'up' : macd.signal?.includes('死叉') ? 'down' : ''),
    kvRow('趋势', macd.trend || '—', macd.trend === '多头' ? 'up' : 'down'),
  ].join('');

  const kdj = tech.kdj || {};
  $('kdj-list').innerHTML = [
    kvRow('K', display(kdj.k, '')),
    kvRow('D', display(kdj.d, '')),
    kvRow('J', display(kdj.j, '')),
    kvRow('信号', kdj.signal || '—', kdj.signal?.includes('超卖') ? 'up' : kdj.signal?.includes('超买') ? 'down' : ''),
  ].join('');

  const rsi = tech.rsi || {};
  $('rsi-list').innerHTML = [
    kvRow('RSI(6)',  display(rsi.rsi6, '')),
    kvRow('RSI(12)', display(rsi.rsi12, '')),
    kvRow('RSI(24)', display(rsi.rsi24, '')),
    kvRow('信号', rsi.signal || '—'),
  ].join('');

  const boll = tech.boll || {};
  $('boll-list').innerHTML = [
    kvRow('上轨', display(boll.upper, '')),
    kvRow('中轨', display(boll.mid, '')),
    kvRow('下轨', display(boll.lower, '')),
    kvRow('带宽', display(boll.width, '%')),
    kvRow('位置', display(boll.position, '', 3)),
    kvRow('信号', boll.signal || '—'),
  ].join('');

  const other = tech['其他指标'] || {};
  $('other-indicators-list').innerHTML = [
    kvRow('OBV', fmtBig(other.obv)),
    kvRow('CCI', display(other.cci, '')),
    kvRow('威廉指标 %R', display(other['威廉指标'], '')),
    kvRow('SAR', display(other.sar, '')),
    kvRow('ATR', display(other.atr, '')),
  ].join('');

  const pat = tech['形态识别'] || {};
  $('pattern-list').innerHTML = [
    kvRow('形态', pat.pattern || '—'),
    kvRow('趋势强度', pat.trend_strength || '—'),
    kvRow('支撑位', pat.support_level?.length ? pat.support_level.map(v => fmt(v)).join(' / ') : '—'),
    kvRow('压力位', pat.resistance_level?.length ? pat.resistance_level.map(v => fmt(v)).join(' / ') : '—'),
  ].join('');
}

// ── Radar Chart (scores) ───────────────────
function renderRadar(d) {
  const scores = d['投资建议']?.评分卡;
  if (!scores) return;
  const labels = ['估值', '成长性', '盈利能力', '财务健康', '技术面', '资金面'];
  const vals = [
    scores['估值评分'], scores['成长性评分'], scores['盈利能力评分'],
    scores['财务健康评分'], scores['技术面评分'], scores['资金面评分']
  ];

  if (radarChartInst) { radarChartInst.destroy(); radarChartInst = null; }
  const ctx = $('radarChart').getContext('2d');
  radarChartInst = new Chart(ctx, {
    type: 'radar',
    data: {
      labels,
      datasets: [{
        label: '评分',
        data: vals,
        backgroundColor: 'rgba(88,166,255,.18)',
        borderColor: '#58a6ff',
        borderWidth: 2,
        pointBackgroundColor: '#58a6ff',
        pointRadius: 4,
      }]
    },
    options: {
      responsive: false,
      plugins: { legend: { display: false } },
      scales: {
        r: {
          min: 0, max: 100,
          ticks: { color: '#8b949e', backdropColor: 'transparent', stepSize: 20 },
          grid: { color: 'rgba(255,255,255,.1)' },
          angleLines: { color: 'rgba(255,255,255,.1)' },
          pointLabels: { color: '#e6edf3', font: { size: 13 } }
        }
      }
    }
  });
}

// ── Risk ───────────────────────────────────
function renderRisk(risk, compare) {
  const rEl = $('risk-list');
  rEl.innerHTML = [
    kvRow('Beta', display(risk?.beta, '')),
    kvRow('Alpha', display(risk?.alpha, '')),
    kvRow('日波动率', display(risk?.volatility_daily, '%')),
    kvRow('年化波动率', display(risk?.volatility_annual, '%')),
    kvRow('最大回撤 (1年)', display(risk?.max_drawdown_1y, '%'), 'down'),
    kvRow('最大回撤 (3年)', display(risk?.max_drawdown_3y, '%'), 'down'),
    kvRow('夏普比率 (1年)', display(risk?.sharpe_ratio_1y, '')),
    kvRow('夏普比率 (3年)', display(risk?.sharpe_ratio_3y, '')),
    kvRow('索提诺比率', display(risk?.sortino_ratio, '')),
    kvRow('卡玛比率', display(risk?.calmar_ratio, '')),
    kvRow('VaR (95%)', display(risk?.var_95, '%'), 'down'),
    kvRow('CVaR (95%)', display(risk?.cvar_95, '%'), 'down'),
    kvRow('与标普500相关性', display(risk?.correlation_sp500, '')),
    kvRow('与纳斯达克相关性', display(risk?.correlation_nasdaq, '')),
  ].join('');

  const cEl = $('market-compare-list');
  cEl.innerHTML = [
    kvRow('基准指数', compare?.benchmark || '—'),
    kvRow('基准收益', signedFmt(compare?.benchmark_return), colorClass(compare?.benchmark_return)),
    kvRow('股票收益', signedFmt(compare?.stock_return), colorClass(compare?.stock_return)),
    kvRow('超额收益', signedFmt(compare?.excess_return), colorClass(compare?.excess_return)),
    kvRow('相对强度', display(compare?.relative_strength, 'x')),
    kvRow('行业排名', compare?.sector_rank || '—'),
  ].join('');
}

// ── Fund Flow ──────────────────────────────
function renderFundFlow(flow) {
  if (!flow) return;
  const today = flow['今日流向'] || {};
  const d5    = flow['5日流向'] || {};
  const d20   = flow['20日流向'] || {};
  const north = flow['北向资金'] || {};

  $('fund-today-list').innerHTML = [
    kvRow('主力净流入', fmtBig(today.main_net_inflow), colorClass(today.main_net_inflow)),
    kvRow('主力流入', fmtBig(today.main_inflow)),
    kvRow('主力流出', fmtBig(today.main_outflow)),
    kvRow('主力净占比', display(today.main_inflow_ratio, '%'), colorClass(today.main_inflow_ratio)),
    kvRow('散户净流入', fmtBig(today.retail_net_inflow), colorClass(today.retail_net_inflow)),
    kvRow('超大单流入', fmtBig(today.super_large_inflow)),
    kvRow('大单流入', fmtBig(today.large_inflow)),
    kvRow('中单流入', fmtBig(today.medium_inflow)),
    kvRow('小单流入', fmtBig(today.small_inflow)),
  ].join('');

  $('fund-5d-list').innerHTML = [
    kvRow('5日主力净流入', fmtBig(d5.main_net_inflow), colorClass(d5.main_net_inflow)),
    kvRow('趋势', d5.trend || '—'),
    kvRow('净流入天数', display(d5['流入天数'], '天', 0)),
  ].join('');

  $('fund-20d-list').innerHTML = [
    kvRow('20日主力净流入', fmtBig(d20.main_net_inflow), colorClass(d20.main_net_inflow)),
    kvRow('趋势', d20.trend || '—'),
    kvRow('净流入天数', display(d20['流入天数'], '天', 0)),
  ].join('');

  $('fund-north-list').innerHTML = [
    kvRow('今日北向净流入', fmtBig(north.north_inflow_today), colorClass(north.north_inflow_today)),
    kvRow('北向持仓比例', display(north.north_holding_ratio, '%')),
    kvRow('北向持仓股数', fmtBig(north.north_holding_shares)),
    kvRow('5日北向净流入', fmtBig(north.north_5d_inflow), colorClass(north.north_5d_inflow)),
    kvRow('20日北向净流入', fmtBig(north.north_20d_inflow), colorClass(north.north_20d_inflow)),
  ].join('');
}

// ── Institution ────────────────────────────
function renderInstitution(inst) {
  if (!inst) return;
  $('institution-summary-list').innerHTML = [
    kvRow('机构持仓比例', display(inst.institutional_holding_ratio, '%')),
    kvRow('机构持仓股数', fmtBig(inst.institutional_holding_shares)),
    kvRow('机构数量', display(inst.institution_count, '家', 0)),
    kvRow('上季变动', display(inst.recent_quarter_change, '%'), colorClass(inst.recent_quarter_change)),
  ].join('');

  const wrap = $('holders-table-wrap');
  if (!inst.top_holders?.length) {
    wrap.innerHTML = '<p style="color:var(--text-muted);padding:12px">暂无数据</p>';
    return;
  }
  wrap.innerHTML = `<div class="table-wrap"><table class="data-table">
    <thead><tr><th>#</th><th>机构名称</th><th>持股数量</th><th>持仓比例</th></tr></thead>
    <tbody>
      ${inst.top_holders.map((h, i) => `
        <tr>
          <td>${i + 1}</td>
          <td>${h.name || '—'}</td>
          <td>${fmtBig(h.shares)}</td>
          <td>${h.ratio != null ? fmt(h.ratio, 2) + '%' : '—'}</td>
        </tr>`).join('')}
    </tbody>
  </table></div>`;
}

// ── Analyst ────────────────────────────────
function renderAnalyst(analyst) {
  if (!analyst) return;
  const sum = analyst.summary || {};
  const tp  = analyst.target_price || {};
  const total = sum.total_analysts || 1;
  const bars = [
    { label: '强烈买入', count: sum.strong_buy,   cls: 'bar-strong-buy' },
    { label: '买入',     count: sum.buy,          cls: 'bar-buy' },
    { label: '持有',     count: sum.hold,         cls: 'bar-hold' },
    { label: '卖出',     count: sum.sell,         cls: 'bar-sell' },
    { label: '强烈卖出', count: sum.strong_sell,  cls: 'bar-strong-sell' },
  ];

  const consenColor = {
    '强烈买入': '#39d353', '买入': 'var(--up)',
    '持有': 'var(--warn)', '卖出': 'var(--down)', '减持': '#f0883e'
  }[sum.consensus] || 'var(--text-sec)';

  $('analyst-bar-wrap').innerHTML = bars.map(b => {
    const pct = total ? ((b.count || 0) / total * 100).toFixed(1) : 0;
    return `<div class="analyst-bar-row">
      <span class="analyst-bar-label">${b.label}</span>
      <div class="analyst-bar-track">
        <div class="analyst-bar-fill ${b.cls}" style="width:${pct}%"></div>
      </div>
      <span class="analyst-bar-count">${b.count ?? 0}</span>
    </div>`;
  }).join('') + `<div style="margin-top:8px">
    <span class="kv-key">共${total}位分析师 &nbsp;|&nbsp; 共识：</span>
    <span class="consensus-badge" style="color:${consenColor};border:1px solid ${consenColor};background:${consenColor}22">
      ${sum.consensus || '—'}
    </span>
  </div>`;

  $('analyst-target-list').innerHTML = [
    kvRow('目标均价', display(tp.current, '')),
    kvRow('目标高价', display(tp.high, '')),
    kvRow('目标低价', display(tp.low, '')),
    kvRow('目标中位价', display(tp.median, '')),
    kvRow('上行空间', signedFmt(tp.upside), colorClass(tp.upside)),
    kvRow('评级趋势', analyst.ratings_trend || '—'),
    kvRow('近期上调', display(analyst.recent_upgrades, '次', 0)),
    kvRow('近期下调', display(analyst.recent_downgrades, '次', 0)),
  ].join('');
}

// ── Logics ─────────────────────────────────
function renderLogics(rec) {
  if (!rec) return;
  const lEl = $('logics-list');
  const rEl = $('risks-list');
  lEl.innerHTML = (rec['投资逻辑'] || []).map(l => `<li>${l}</li>`).join('') || '<li>暂无数据</li>';
  rEl.innerHTML = (rec['风险提示'] || []).map(r => `<li>${r}</li>`).join('') || '<li>暂无数据</li>';
}

// ── History Table ──────────────────────────
function renderHistory(histData) {
  if (!histData) return;
  const stats = histData.statistics || {};
  $('history-stats-list').innerHTML = [
    kvRow('区间均价', display(stats.avg_close, '')),
    kvRow('日均成交量', fmtVol(stats.avg_volume)),
    kvRow('区间涨跌幅', signedFmt(stats.total_change_percent), colorClass(stats.total_change_percent)),
    kvRow('区间最高', display(stats.max_close, '')),
    kvRow('区间最低', display(stats.min_close, '')),
    kvRow('区间波动率', display(stats.volatility, '%')),
  ].join('');

  const tbody = $('history-tbody');
  tbody.innerHTML = (histData.history || []).map(r => {
    const chgCls = r.change_percent > 0 ? 'up' : r.change_percent < 0 ? 'down' : '';
    return `<tr>
      <td>${r.date}</td>
      <td>${fmt(r.open)}</td>
      <td class="${chgCls}">${fmt(r.close)}</td>
      <td>${fmt(r.high)}</td>
      <td>${fmt(r.low)}</td>
      <td>${fmtVol(r.volume)}</td>
      <td class="${chgCls}">${signedFmt(r.change_percent)}</td>
    </tr>`;
  }).join('');
}

// ══════════════════════════════════════════════════
//  简易版 Dashboard
// ══════════════════════════════════════════════════
function renderSimpleDashboard(d) {
  // ── 头部 ─────────────────────────────────────
  $('s-stock-name').textContent  = d.stock_name || d.stock_code;
  $('s-code-badge').textContent  = d.stock_code;
  $('s-market-badge').textContent = d.market;
  $('s-currency-badge').textContent = d.currency || '—';

  const isUp = (d.change_percent ?? 0) >= 0;
  $('s-current-price').textContent = d.current_price != null ? fmt(d.current_price) : '—';
  const pc = $('s-price-change');
  pc.textContent = `${signedFmt(d.change, '')} (${signedFmt(d.change_percent)})`;
  pc.className = 'price-change ' + (isUp ? 'up' : 'down');

  $('s-open').textContent   = display(d.open,   '');
  $('s-high').textContent   = display(d.high,   '');
  $('s-low').textContent    = display(d.low,    '');
  $('s-close').textContent  = display(d.close,  '');
  $('s-volume').textContent = fmtVol(d.volume);
  $('s-amount').textContent = fmtBig(d.amount);

  // ── MA 指标 ───────────────────────────────────
  const price = d.current_price;
  const ti = d.technical_indicators || {};
  const maRows = [
    { label: 'MA5',  val: ti.ma5  },
    { label: 'MA10', val: ti.ma10 },
    { label: 'MA20', val: ti.ma20 },
  ].map(m => {
    if (m.val == null) return `<div class="ma-row"><span class="ma-label">${m.label}</span><span class="ma-val na">—</span></div>`;
    const above = price != null && price >= m.val;
    const diff  = price != null ? ((price - m.val) / m.val * 100) : null;
    const cls   = above ? 'above' : 'below';
    const diffTxt = diff != null ? `${diff >= 0 ? '+' : ''}${diff.toFixed(2)}%` : '';
    return `<div class="ma-row ${cls}">
      <span class="ma-label">${m.label}</span>
      <span class="ma-val">${fmt(m.val)}</span>
      <span class="ma-diff">${diffTxt}</span>
    </div>`;
  }).join('');
  $('s-ma-block').innerHTML = maRows;

  // ── RSI 仪表盘 ────────────────────────────────
  const rsi = ti.rsi;
  renderSimpleRsi(rsi);

  // ── 投资建议 ─────────────────────────────────
  const rec = d.recommendation || '—';
  const recColorMap = {
    '强烈买入': { cls: 'rec-strong-buy', clr: '#39d353' },
    '买入':     { cls: 'rec-buy',        clr: '#3fb950' },
    '持有':     { cls: 'rec-hold',       clr: '#e3b341' },
    '减持':     { cls: 'rec-sell',       clr: '#f0883e' },
    '卖出':     { cls: 'rec-strong-sell',clr: '#f85149' },
  };
  const rc = recColorMap[rec] || { cls: 'rec-hold', clr: '#e3b341' };
  $('s-rec-block').innerHTML = `
    <div class="simple-rec-badge ${rc.cls}">${rec}</div>
    <div class="simple-rec-info">
      ${kvRow('股票代码', d.stock_code || '—')}
      ${kvRow('所属市场', d.market    || '—')}
      ${kvRow('货币',     d.currency  || '—')}
    </div>`;

  // ── 图表 ─────────────────────────────────────
  renderSimpleChart(d.history || []);

  // ── 历史表格 ──────────────────────────────────
  const tbody = $('s-history-tbody');
  const hist = (d.history || []);
  if (hist.length) {
    tbody.innerHTML = hist.map((r, i) => {
      const prevClose = i < hist.length - 1 ? hist[i + 1].close : r.close;
      const chgPct    = prevClose ? (r.close - prevClose) / prevClose * 100 : 0;
      const cls = chgPct > 0 ? 'up' : chgPct < 0 ? 'down' : '';
      return `<tr>
        <td>${r.date}</td>
        <td>${fmt(r.open)}</td>
        <td class="${cls}">${fmt(r.close)}</td>
        <td>${fmt(r.high)}</td>
        <td>${fmt(r.low)}</td>
        <td>${fmtVol(r.volume)}</td>
      </tr>`;
    }).join('');
  } else {
    tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;color:var(--text-muted)">暂无历史数据</td></tr>';
  }

  // ── JSON 输出 ─────────────────────────────────
  const clean = {
    stock_code: d.stock_code,
    stock_name: d.stock_name,
    market:     d.market,
    currency:   d.currency,
    current_price: d.current_price,
    change:        d.change,
    change_percent: d.change_percent,
    open:   d.open,
    close:  d.close,
    high:   d.high,
    low:    d.low,
    volume: d.volume,
    amount: d.amount,
    technical_indicators: d.technical_indicators,
    recommendation: d.recommendation,
    history: (d.history || []).slice(0, 5),  // 预览前5条
  };
  $('s-json-output').innerHTML = syntaxHighlight(JSON.stringify(clean, null, 2));
}

// ── RSI 圆环仪表盘 ────────────────────────────
function renderSimpleRsi(rsiVal) {
  if (rsiChartInst) { rsiChartInst.destroy(); rsiChartInst = null; }
  const val   = rsiVal != null ? Math.min(100, Math.max(0, rsiVal)) : 50;
  const color = val > 70 ? '#f85149' : val < 30 ? '#3fb950' : val > 55 ? '#e3b341' : '#58a6ff';
  const sig   = val > 70 ? '超买' : val < 30 ? '超卖' : val > 55 ? '偏强' : val < 45 ? '偏弱' : '中性';
  const sigCls = val > 70 ? 'down' : val < 30 ? 'up' : '';

  $('s-rsi-block').innerHTML = `
    <div class="rsi-gauge-wrap" style="position:relative;width:140px;height:140px">
      <canvas id="rsiGaugeChart" width="140" height="140"></canvas>
      <div class="rsi-center-text">
        ${rsiVal != null ? fmt(rsiVal, 1) : '—'}<br><small>RSI(12)</small>
      </div>
    </div>
    <span class="rsi-signal ${sigCls}" style="border:1px solid ${color};color:${color};background:${color}22">${sig}</span>`;

  const ctx = $('rsiGaugeChart')?.getContext('2d');
  if (!ctx) return;
  rsiChartInst = new Chart(ctx, {
    type: 'doughnut',
    data: {
      datasets: [{
        data: [val, 100 - val],
        backgroundColor: [color, '#21262d'],
        borderWidth: 0,
        hoverOffset: 0,
      }]
    },
    options: {
      cutout: '70%', responsive: false,
      plugins: { legend: { display: false }, tooltip: { enabled: false } },
      animation: { duration: 700 },
    }
  });
}

// ── 简易版 K 线图 ─────────────────────────────
function renderSimpleChart(histArr) {
  if (simpleChartInst) { simpleChartInst.destroy(); simpleChartInst = null; }
  if (!histArr.length) return;

  const hist    = histArr.slice().reverse();
  const labels  = hist.map(r => r.date.slice(5));
  const closes  = hist.map(r => r.close);
  const volumes = hist.map(r => r.volume);
  const isUp    = closes.length > 1 && closes[closes.length - 1] >= closes[0];
  const mainClr = isUp ? '#3fb950' : '#f85149';

  const ctx = $('simpleChart').getContext('2d');
  const chartH = $('simpleChart').parentElement.offsetHeight || 260;
  const grad = ctx.createLinearGradient(0, 0, 0, chartH);
  grad.addColorStop(0, isUp ? 'rgba(63,185,80,.25)' : 'rgba(248,81,73,.25)');
  grad.addColorStop(1, 'rgba(0,0,0,0)');

  simpleChartInst = new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [{
        label: '收盘价',
        data: closes,
        borderColor: mainClr,
        backgroundColor: grad,
        borderWidth: 2,
        pointRadius: 0,
        pointHoverRadius: 4,
        fill: true,
        tension: 0.3,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { intersect: false, mode: 'index' },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: '#1c2128', borderColor: '#30363d', borderWidth: 1,
          titleColor: '#8b949e', bodyColor: '#e6edf3',
        }
      },
      scales: {
        x: { ticks: { color: '#8b949e', maxTicksLimit: 8 }, grid: { color: 'rgba(255,255,255,.04)' } },
        y: { ticks: { color: '#8b949e' }, grid: { color: 'rgba(255,255,255,.04)' }, position: 'right' }
      }
    }
  });
  simpleChartInst._closes  = closes;
  simpleChartInst._volumes = volumes;
  simpleChartInst._mainClr = mainClr;
  simpleChartInst._grad    = grad;
}

function switchSimpleChart(mode, btn) {
  document.querySelectorAll('#simple-dashboard .chart-tab').forEach(t => t.classList.remove('active'));
  btn.classList.add('active');
  simpleChartMode = mode;
  if (!simpleChartInst) return;
  const inst = simpleChartInst;
  if (mode === 'volume') {
    inst.data.datasets[0].data  = inst._volumes;
    inst.data.datasets[0].label = '成交量';
    inst.data.datasets[0].borderColor = '#58a6ff';
    inst.data.datasets[0].backgroundColor = 'rgba(88,166,255,.15)';
  } else {
    inst.data.datasets[0].data  = inst._closes;
    inst.data.datasets[0].label = '收盘价';
    inst.data.datasets[0].borderColor = inst._mainClr;
    inst.data.datasets[0].backgroundColor = inst._grad;
  }
  inst.update();
}

// ── JSON 语法高亮 ─────────────────────────────
function syntaxHighlight(json) {
  return json
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/("(\\u[\dA-Fa-f]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+\.?\d*(?:[eE][+\-]?\d+)?)/g, m => {
      if (/^"/.test(m)) {
        if (/:$/.test(m)) return `<span class="jk">${m}</span>`;
        return `<span class="js">${m}</span>`;
      }
      if (/true|false|null/.test(m)) return `<span class="jb">${m}</span>`;
      return `<span class="jn">${m}</span>`;
    });
}

// ── 复制简易 JSON ─────────────────────────────
function copySimpleJson() {
  if (!lastSimpleData) return;
  const clean = {
    stock_code: lastSimpleData.stock_code,
    stock_name: lastSimpleData.stock_name,
    market:     lastSimpleData.market,
    currency:   lastSimpleData.currency,
    current_price: lastSimpleData.current_price,
    change:     lastSimpleData.change,
    change_percent: lastSimpleData.change_percent,
    open: lastSimpleData.open, close: lastSimpleData.close,
    high: lastSimpleData.high, low:   lastSimpleData.low,
    volume: lastSimpleData.volume, amount: lastSimpleData.amount,
    technical_indicators: lastSimpleData.technical_indicators,
    recommendation: lastSimpleData.recommendation,
    history: lastSimpleData.history,
  };
  navigator.clipboard.writeText(JSON.stringify(clean, null, 2))
    .then(() => alert('JSON 已复制到剪贴板'))
    .catch(() => alert('复制失败，请手动选取文本'));
}
