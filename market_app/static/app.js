(() => {
  "use strict";

  const state = {
    watchlist: [],
    watchQuotes: [],
    currentSymbol: "600519.SH",
    currentName: "贵州茅台",
    currentPeriod: "day",
    analysis: null,
    chart: null,
    sourceData: [],
    screenJob: null,
    screenTimer: null,
    loading: false,
    conditions: ["ma_bull", "above_ma20", "macd_positive", "rsi_50_75", "volume_expand"],
  };

  const CONDITION_LABELS = {
    ma_bull: "均线多头排列",
    above_ma20: "站上 MA20",
    above_ma60: "站上 MA60",
    macd_positive: "MACD 柱线为正",
    macd_gold: "近 5 日 MACD 金叉",
    rsi_50_75: "RSI 50–75",
    volume_expand: "放量 1.2 倍",
    near_high20: "接近 20 日高点",
    breakout20: "突破 20 日高点",
    ret20_positive: "20 日涨幅为正",
    kdj_gold: "KDJ 金叉",
  };

  const $ = (id) => document.getElementById(id);
  const esc = (value) => String(value ?? "")
    .replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;").replaceAll("'", "&#39;");
  const num = (value, digits = 2) => {
    if (value === null || value === undefined || value === "") return "--";
    const n = Number(value);
    if (!Number.isFinite(n)) return "--";
    return n.toFixed(digits);
  };
  const pct = (value, digits = 2) => {
    if (value === null || value === undefined || value === "") return "--";
    const n = Number(value);
    if (!Number.isFinite(n)) return "--";
    return `${n > 0 ? "+" : ""}${n.toFixed(digits)}%`;
  };
  const clsByChange = (value) => {
    const n = Number(value);
    if (!Number.isFinite(n) || n === 0) return "flat";
    return n > 0 ? "up" : "down";
  };
  const amountText = (value) => {
    const n = Number(value);
    if (!Number.isFinite(n)) return "--";
    if (Math.abs(n) >= 1e8) return `${(n / 1e8).toFixed(2)} 亿`;
    if (Math.abs(n) >= 1e4) return `${(n / 1e4).toFixed(2)} 万`;
    return n.toFixed(0);
  };
  const timeText = (value) => {
    if (!value) return "--";
    return String(value).replace("T", " ");
  };
  let toastTimer = null;
  const toast = (message, kind = "") => {
    const el = $("toast");
    el.textContent = message;
    el.className = `toast ${kind}`;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => el.classList.add("hidden"), 3500);
  };

  async function api(path, options = {}) {
    const response = await fetch(path, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });
    let payload = null;
    try { payload = await response.json(); } catch (_) { payload = null; }
    if (!response.ok) {
      const detail = payload && (payload.detail || payload.error);
      throw new Error(detail || `请求失败（HTTP ${response.status}）`);
    }
    return payload;
  }

  // ---------------------------------------------------------------- clock
  function tickClock() {
    try {
      const now = new Date();
      const text = new Intl.DateTimeFormat("zh-CN", {
        timeZone: "Asia/Shanghai",
        year: "numeric", month: "2-digit", day: "2-digit",
        hour: "2-digit", minute: "2-digit", second: "2-digit",
        hour12: false,
      }).format(now).replaceAll("/", "-");
      $("beijingTime").textContent = `北京时间 ${text}`;
    } catch (_) {
      $("beijingTime").textContent = "北京时间 --";
    }
  }

  // ---------------------------------------------------------------- navigation
  function switchPage(name) {
    document.querySelectorAll(".page").forEach((page) => {
      page.classList.toggle("active", page.id === `page-${name}`);
    });
    document.querySelectorAll(".nav-item").forEach((item) => {
      item.classList.toggle("active", item.dataset.page === name);
    });
    if (name === "stock" && state.chart) {
      setTimeout(() => state.chart.resize(), 60);
    }
  }

  document.querySelectorAll(".nav-item").forEach((item) => {
    item.addEventListener("click", () => {
      const name = item.dataset.page;
      switchPage(name);
      if (name === "stock" && !state.analysis && !state.loading) {
        selectStock(state.currentSymbol, state.currentName);
      }
    });
  });
  document.querySelectorAll("[data-goto]").forEach((item) => {
    item.addEventListener("click", () => switchPage(item.dataset.goto));
  });

  // ---------------------------------------------------------------- health
  async function loadHealth() {
    try {
      const data = await api("/api/health");
      $("healthDot").className = "dot live";
      $("healthText").textContent = `本地服务 ${data.time.split(" ")[1] || ""}`;
    } catch (error) {
      $("healthDot").className = "dot bad";
      $("healthText").textContent = "本地服务不可用";
    }
  }

  // ---------------------------------------------------------------- search
  let searchTimer = null;
  const searchInput = $("searchInput");
  const suggestions = $("suggestions");

  function hideSuggestions() {
    suggestions.classList.add("hidden");
    suggestions.innerHTML = "";
  }

  function renderSuggestions(items) {
    if (!items.length) {
      suggestions.innerHTML = '<div class="suggestion"><span class="muted">未找到匹配标的</span></div>';
      suggestions.classList.remove("hidden");
      return;
    }
    suggestions.innerHTML = items.map((item) => `
      <div class="suggestion" data-symbol="${esc(item.symbol)}" data-name="${esc(item.name)}">
        <div>
          <div class="suggestion-name">${esc(item.name)}</div>
          <div class="suggestion-meta">${esc(item.symbol)} · ${esc(item.type_label || item.type || "")}</div>
        </div>
        <span class="mini-badge">选择</span>
      </div>
    `).join("");
    suggestions.classList.remove("hidden");
    suggestions.querySelectorAll(".suggestion[data-symbol]").forEach((item) => {
      item.addEventListener("click", () => {
        hideSuggestions();
        searchInput.value = "";
        selectStock(item.dataset.symbol, item.dataset.name);
      });
    });
  }

  searchInput.addEventListener("input", () => {
    const query = searchInput.value.trim();
    clearTimeout(searchTimer);
    if (!query) { hideSuggestions(); return; }
    searchTimer = setTimeout(async () => {
      try {
        const data = await api(`/api/search?q=${encodeURIComponent(query)}&limit=12`);
        renderSuggestions(data.items || []);
      } catch (error) {
        renderSuggestions([]);
      }
    }, 220);
  });

  searchInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      const first = suggestions.querySelector(".suggestion[data-symbol]");
      if (first) {
        const symbol = first.dataset.symbol;
        const name = first.dataset.name;
        hideSuggestions();
        searchInput.value = "";
        selectStock(symbol, name);
      }
    }
    if (event.key === "Escape") hideSuggestions();
  });

  document.addEventListener("click", (event) => {
    if (!event.target.closest(".search-wrap")) hideSuggestions();
  });

  $("focusSearch").addEventListener("click", () => {
    switchPage("overview");
    searchInput.focus();
  });

  // ---------------------------------------------------------------- watchlist
  function renderSidebarWatchlist() {
    const container = $("watchlist");
    if (!state.watchQuotes.length) {
      container.innerHTML = '<div class="muted small" style="padding:8px">自选行情暂不可用</div>';
      return;
    }
    container.innerHTML = state.watchQuotes.map((item) => `
      <button class="watch-item" data-symbol="${esc(item.symbol)}" data-name="${esc(item.name)}">
        <div>
          <div class="watch-name">${esc(item.name)}</div>
          <div class="watch-symbol">${esc(item.symbol)}</div>
        </div>
        <div class="watch-right">
          <div class="watch-price ${clsByChange(item.change_pct)}">${num(item.price)}</div>
          <div class="watch-change ${clsByChange(item.change_pct)}">${pct(item.change_pct)}</div>
        </div>
      </button>
    `).join("");
    container.querySelectorAll(".watch-item").forEach((item) => {
      item.addEventListener("click", () => selectStock(item.dataset.symbol, item.dataset.name));
    });
  }

  function renderWatchTable() {
    const body = $("watchTable").querySelector("tbody");
    if (!state.watchQuotes.length) {
      body.innerHTML = '<tr><td colspan="6" class="empty">自选行情暂不可用，请稍后刷新</td></tr>';
      return;
    }
    body.innerHTML = state.watchQuotes.map((item) => `
      <tr class="clickable" data-symbol="${esc(item.symbol)}" data-name="${esc(item.name)}">
        <td><div class="cell-name">${esc(item.name)}</div><div class="cell-symbol">${esc(item.symbol)}</div></td>
        <td class="r mono">${num(item.price)}</td>
        <td class="r mono ${clsByChange(item.change_pct)}">${pct(item.change_pct)}</td>
        <td class="r mono">${amountText(item.amount)}</td>
        <td class="r mono">${num(item.turnover, 2)}%</td>
        <td class="muted small">${esc(timeText(item.time))}</td>
      </tr>
    `).join("");
    body.querySelectorAll("tr[data-symbol]").forEach((row) => {
      row.addEventListener("click", () => selectStock(row.dataset.symbol, row.dataset.name));
    });
  }

  async function loadWatchlist() {
    try {
      const data = await api("/api/watchlist");
      state.watchlist = data.symbols || [];
      state.watchQuotes = data.items || [];
      if (!state.watchQuotes.length && state.watchlist.length) {
        state.watchQuotes = state.watchlist.map((symbol) => ({ symbol, name: symbol, price: null, change_pct: null }));
      }
      renderSidebarWatchlist();
      renderWatchTable();
    } catch (error) {
      $("watchlist").innerHTML = '<div class="muted small" style="padding:8px">自选读取失败</div>';
      toast(`自选读取失败：${error.message}`, "bad");
    }
  }

  async function toggleCurrentWatch() {
    if (!state.analysis) return;
    const symbol = state.analysis.symbol;
    const exists = state.watchlist.includes(symbol);
    try {
      await api("/api/watchlist", {
        method: "POST",
        body: JSON.stringify({ symbol, action: exists ? "remove" : "add" }),
      });
      toast(exists ? "已移出自选" : "已加入自选", "ok");
      await loadWatchlist();
      updateWatchButton();
    } catch (error) {
      toast(`操作失败：${error.message}`, "bad");
    }
  }

  function updateWatchButton() {
    if (!state.analysis) return;
    const exists = state.watchlist.includes(state.analysis.symbol);
    $("toggleWatch").textContent = exists ? "移出自选" : "加入自选";
  }

  $("toggleWatch").addEventListener("click", toggleCurrentWatch);
  $("refreshWatchlist").addEventListener("click", loadWatchlist);

  // ---------------------------------------------------------------- indices
  async function loadIndices() {
    const grid = $("indexCards");
    try {
      const data = await api("/api/indices");
      const items = data.items || [];
      if (!items.length) throw new Error("指数行情为空");
      grid.innerHTML = items.map((item) => {
        const changeClass = clsByChange(item.change_pct);
        return `
          <div class="index-card">
            <div class="index-name"><span>${esc(item.name)}</span><span class="index-code">${esc(item.symbol)}</span></div>
            <div class="index-price ${changeClass}">${num(item.price)}</div>
            <div class="index-change ${changeClass}">${pct(item.change_pct)} <span class="muted-2">${num(item.change)}</span></div>
            <div class="index-meta">成交额 ${amountText(item.amount)} · ${esc(timeText(item.time))}</div>
          </div>
        `;
      }).join("");
      $("marketBreadth").textContent = `行情时间 ${timeText(items[0].time)} · 腾讯`;
      $("dataStamp").textContent = `行情 ${timeText(items[0].time)}`;
    } catch (error) {
      grid.innerHTML = '<div class="index-card"><div class="muted">指数行情暂不可用</div></div>';
      $("marketBreadth").textContent = "指数行情不可用";
      $("dataStamp").textContent = "行情不可用";
    }
  }

  // ---------------------------------------------------------------- sources
  function sourceStatusBadge(item) {
    if (item.ok) return '<span class="mini-badge ok">可用</span>';
    return '<span class="mini-badge bad">不可用</span>';
  }

  function renderSourceMini(items) {
    const container = $("sourceMini");
    if (!items.length) { container.innerHTML = '<div class="muted">暂无检测结果</div>'; return; }
    container.innerHTML = items.map((item) => `
      <div class="source-mini-row">
        <span class="dot ${item.ok ? "live" : "bad"}"></span>
        <span>${esc(item.name)}</span>
        <span class="status-text">${item.ok ? `${item.latency_ms} ms` : "失败"} · ${esc(item.checked_at.split(" ")[1] || "")}</span>
      </div>
    `).join("");
  }

  function renderSourceCards(items) {
    const container = $("sourceCards");
    container.innerHTML = items.map((item) => `
      <div class="source-card">
        <div class="source-top">
          <div class="source-name"><span class="dot ${item.ok ? "live" : "bad"}"></span>${esc(item.name)}</div>
          ${sourceStatusBadge(item)}
        </div>
        <div class="source-kind">${esc(item.kind)}</div>
        <div class="source-meta">
          <span>接口</span><span class="v">${esc(item.endpoint)}</span>
          <span>许可</span><span class="v">${esc(item.license)}</span>
          <span>延迟</span><span class="v">${item.latency_ms} ms</span>
          <span>检测时间</span><span class="v">${esc(item.checked_at)}</span>
        </div>
        <div class="source-detail">${esc(item.ok ? (item.detail || "接口返回正常") : (item.error || "接口不可用"))}</div>
        <div class="source-detail">${esc(item.note || "")}</div>
      </div>
    `).join("");
  }

  async function loadSources(refresh = false) {
    try {
      const data = await api(`/api/sources?refresh=${refresh ? "true" : "false"}`);
      state.sourceData = data.items || [];
      renderSourceMini(state.sourceData);
      renderSourceCards(state.sourceData);
    } catch (error) {
      $("sourceMini").innerHTML = '<div class="muted">数据源检测失败</div>';
      $("sourceCards").innerHTML = '<div class="source-card muted">数据源检测失败</div>';
      toast(`数据源检测失败：${error.message}`, "bad");
    }
  }

  $("refreshSources").addEventListener("click", () => loadSources(true));

  // ---------------------------------------------------------------- stock analysis
  async function selectStock(symbol, name = "") {
    state.currentSymbol = symbol;
    state.currentName = name || symbol;
    switchPage("stock");
    $("stockName").textContent = name || "加载中";
    $("stockSymbol").textContent = symbol;
    $("stockPrice").textContent = "--";
    $("stockChange").textContent = "--";
    $("stockQuoteTime").textContent = "正在拉取行情…";
    $("trendLabel").textContent = "加载中";
    $("trendScore").textContent = "--";
    $("qualityScore").textContent = "--";
    $("qualityStatus").textContent = "加载中";
    $("qualityBadge").textContent = "--";
    $("qualityLights").innerHTML = "";
    $("qualityNotes").innerHTML = '<li class="muted">正在计算信号质量…</li>';
    await loadAnalysis();
  }

  function setPeriod(period) {
    state.currentPeriod = period;
    document.querySelectorAll(".period-btn").forEach((button) => {
      button.classList.toggle("active", button.dataset.period === period);
    });
    if (state.currentSymbol) loadAnalysis();
  }

  document.querySelectorAll(".period-btn").forEach((button) => {
    button.addEventListener("click", () => setPeriod(button.dataset.period));
  });

  async function loadAnalysis() {
    if (state.loading) return;
    state.loading = true;
    try {
      const data = await api(`/api/analyze?symbol=${encodeURIComponent(state.currentSymbol)}&period=${state.currentPeriod}&bars=320`);
      state.analysis = data;
      renderStock(data);
      updateWatchButton();
    } catch (error) {
      toast(`分析失败：${error.message}`, "bad");
      $("trendLabel").textContent = "数据不可用";
      $("checks").innerHTML = `<div class="check-item"><span class="check-dot bad"></span><div><div class="check-name">请求失败</div><div class="check-msg">${esc(error.message)}</div></div></div>`;
    } finally {
      state.loading = false;
    }
  }

  function renderStock(data) {
    const snapshot = data.snapshot || {};
    const quote = data.quote || {};
    const trend = snapshot.trend || {};
    const levels = snapshot.levels || {};
    const periodLabel = { day: "日线", week: "周线", month: "月线" }[data.period] || "日线";
    $("stockName").textContent = data.name || data.symbol;
    $("stockSymbol").textContent = data.symbol;
    $("stockPrice").textContent = num(quote.price || snapshot.close);
    const change = quote.change_pct ?? snapshot.change_pct;
    $("stockChange").textContent = pct(change);
    $("stockChange").className = `stock-change ${clsByChange(change)}`;
    $("stockQuoteTime").textContent = quote.time ? `腾讯快照 ${timeText(quote.time)}` : `K 线截至 ${snapshot.as_of}`;

    $("chartSub").textContent = `${periodLabel} · 前复权 · 截至 ${snapshot.as_of}`;
    $("chartNote").textContent = `K 线 ${data.series.date.length} 根；成交量单位股；价格前复权。数据源：${data.provenance.source}。`;

    $("trendScore").textContent = trend.score ?? "--";
    $("trendLabel").textContent = trend.label || "--";
    $("trendAsOf").textContent = `截至 ${snapshot.as_of} · 置信度 ${(Number(trend.confidence || 0) * 100).toFixed(0)}%`;
    $("trendConfidence").textContent = trend.confidence >= 0.8 ? "数据完整" : "数据部分缺失";
    $("trendConfidence").className = `mini-badge ${trend.confidence >= 0.8 ? "ok" : "warn"}`;

    const components = trend.components || {};
    const bars = [
      ["均线结构", components.ma, 25],
      ["MACD", components.macd, 20],
      ["RSI", components.rsi, 15],
      ["量能", components.volume, 15],
      ["价格位置", components.position, 15],
      ["相对强度", components.relative, 10],
    ];
    $("scoreBars").innerHTML = bars.map(([label, value, max]) => {
      const p = Math.max(0, Math.min(100, Number(value || 0) / max * 100));
      return `<div class="score-row"><span>${label}</span><div class="score-track"><div class="score-fill" style="width:${p}%"></div></div><span class="mono">${num(value, 0)}/${max}</span></div>`;
    }).join("");

    $("trendReasons").innerHTML = (trend.reasons || []).length
      ? trend.reasons.map((item) => `<li>${esc(item)}</li>`).join("")
      : '<li class="muted">没有足够的正向信号</li>';
    $("trendRisks").innerHTML = (trend.risks || []).length
      ? trend.risks.map((item) => `<li>${esc(item)}</li>`).join("")
      : '<li class="muted">暂无明显风险项</li>';

    renderLevels(snapshot, levels);
    renderIndicators(snapshot);
    renderQuality(snapshot.signal_quality || {});
    renderChecks(data);
    renderPriceChart(data, levels);
  }

  function renderQuality(quality) {
    const q = quality || {};
    const gates = q.gates || {};
    const m = q.metrics || {};
    const on = Boolean(q.eligible);
    const grade = q.grade || "D";
    const badge = $("qualityBadge");
    badge.textContent = on ? `${grade} · ${q.status || "合格"}` : `${grade} · ${q.status || "不合格"}`;
    badge.className = `mini-badge ${on ? (q.fresh_signal ? "ok" : "warn") : "bad"}`;
    $("qualityScore").textContent = q.ok ? (q.score ?? "--") : "--";
    $("qualityStatus").textContent = q.ok ? (q.status || "--") : "数据不可用";
    $("qualityAsOf").textContent = q.ok
      ? `截至 ${q.as_of || "--"} · ${q.confirmed ? "收盘确认" : "盘中 provisional"}`
      : "--";

    const weekly = m.weekly_st_dir;
    const weeklyText = weekly === 1 ? "周线多头" : (weekly === -1 ? "周线空头" : "周线未确认");
    const lights = [
      {
        label: "趋势",
        on: Boolean(gates.daily_trend && gates.weekly_trend),
        detail: `日线 ST ${gates.daily_trend ? "多头" : "未多"} / ${weeklyText}`,
      },
      {
        label: "VWAP",
        on: Boolean(gates.vwap),
        detail: `VWAP20 ${num(m.vwap20)} · 偏离 ${m.vwap20_dist_pct === null || m.vwap20_dist_pct === undefined ? "--" : `${num(m.vwap20_dist_pct)}%`}`,
      },
      {
        label: "量能",
        on: Boolean(gates.volume),
        detail: `量比 ${num(m.vol_ratio_20_prev, 2)}× / 门槛 1.20×`,
      },
      {
        label: "实体",
        on: Boolean(gates.body),
        detail: `实体 ${m.body_pct === null || m.body_pct === undefined ? "--" : `${num(m.body_pct, 1)}%`} / 门槛 50%`,
      },
    ];
    $("qualityLights").innerHTML = lights.map((light) => `
      <div class="quality-light ${light.on ? "on" : "off"}">
        <span class="quality-dot"></span>
        <div><div class="quality-light-label">${esc(light.label)}</div><div class="quality-light-detail">${esc(light.detail)}</div></div>
        <span class="quality-state">${light.on ? "过" : "未过"}</span>
      </div>
    `).join("");

    const notes = [];
    (q.reasons || []).forEach((item) => notes.push(item));
    (q.warnings || []).forEach((item) => notes.push(`注意：${item}`));
    if (q.vwap_note) notes.push(`VWAP 口径：${q.vwap_note}`);
    $("qualityNotes").innerHTML = notes.length
      ? notes.map((item) => `<li>${esc(item)}</li>`).join("")
      : '<li class="muted">暂无信号质量数据</li>';
  }

  function renderLevels(snapshot, levels) {
    const range = snapshot.range || {};
    const rows = [
      ["最近支撑", levels.support],
      ["最近阻力", levels.resistance],
      ["距支撑", levels.distance_to_support_pct !== null && levels.distance_to_support_pct !== undefined ? `${num(levels.distance_to_support_pct)}%` : null],
      ["距阻力", levels.distance_to_resistance_pct !== null && levels.distance_to_resistance_pct !== undefined ? `${num(levels.distance_to_resistance_pct)}%` : null],
      ["20 日高", range.high20],
      ["20 日低", range.low20],
      ["60 日高", range.high60],
      ["60 日低", range.low60],
      ["ATR 2倍止损", levels.atr_stop],
      ["ATR 占价", snapshot.atr ? `${num(snapshot.atr.pct)}%` : null],
    ];
    $("levelGrid").innerHTML = rows.map(([label, value]) => `
      <div class="level-cell"><div class="level-label">${esc(label)}</div><div class="level-value">${value === null || value === undefined ? "--" : (typeof value === "number" ? num(value) : esc(value))}</div></div>
    `).join("");
  }

  function renderIndicators(snapshot) {
    const ma = snapshot.moving_averages || {};
    const macd = snapshot.macd || {};
    const rsi = snapshot.rsi || {};
    const kdj = snapshot.kdj || {};
    const boll = snapshot.boll || {};
    const ret = snapshot.returns || {};
    const vol = snapshot.volume || {};
    const cells = [
      ["MA5", num(ma.ma5)], ["MA10", num(ma.ma10)],
      ["MA20", num(ma.ma20)], ["MA60", num(ma.ma60)],
      ["MA120", num(ma.ma120)], ["MACD DIF", num(macd.dif, 3)],
      ["MACD DEA", num(macd.dea, 3)], ["MACD 柱", num(macd.hist, 3)],
      ["RSI14", num(rsi.rsi14)], ["KDJ K", num(kdj.k, 2)],
      ["KDJ D", num(kdj.d, 2)], ["BOLL 上轨", num(boll.upper)],
      ["BOLL 中轨", num(boll.mid)], ["BOLL 下轨", num(boll.lower)],
      ["量比 5日", num(vol.ratio_5, 2)], ["量比 20日", num(vol.ratio_20, 2)],
      ["20日涨幅", pct(ret.ret20)], ["60日涨幅", pct(ret.ret60)],
      ["120日涨幅", pct(ret.ret120)], ["ATR14", num(snapshot.atr && snapshot.atr.value)],
    ];
    $("indicatorTable").innerHTML = cells.map(([key, value]) => `
      <div class="indicator-cell"><span class="k">${esc(key)}</span><span class="v">${esc(value)}</span></div>
    `).join("");
  }

  function renderChecks(data) {
    const checks = data.source_checks || [];
    const skipped = checks.some((check) => check.skipped);
    $("provenanceSub").textContent = `主源 ${data.provenance.source} · 抓取 ${data.provenance.fetched_at}（北京时间）`;
    $("sourceBadge").textContent = skipped ? "快照校验" : "双源校验";
    $("sourceBadge").className = `mini-badge ${skipped ? "warn" : "ok"}`;
    $("checks").innerHTML = checks.map((check) => `
      <div class="check-item">
        <span class="check-dot ${check.ok ? (check.skipped ? "skip" : "ok") : "bad"}"></span>
        <div><div class="check-name">${esc(check.name)}</div><div class="check-msg">${esc(check.message || "")}</div></div>
      </div>
    `).join("");
  }

  // ---------------------------------------------------------------- chart
  function renderPriceChart(data, levels) {
    const series = data.series || {};
    if (!state.chart) {
      state.chart = echarts.init($("priceChart"), null, { renderer: "canvas" });
    }
    const dates = series.date || [];
    const candle = (series.open || []).map((open, index) => [
      open, series.close[index], series.low[index], series.high[index],
    ]);
    const volumes = (series.volume || []).map((value, index) => ({
      value,
      itemStyle: { color: (series.close[index] >= series.open[index]) ? "rgba(239,83,80,.65)" : "rgba(38,166,154,.65)" },
    }));
    const macdBars = (series.macd_hist || []).map((value) => ({
      value,
      itemStyle: { color: Number(value) >= 0 ? "rgba(239,83,80,.8)" : "rgba(38,166,154,.8)" },
    }));
    const markLines = [];
    if (levels && levels.support) markLines.push({ yAxis: levels.support, name: "支撑", lineStyle: { color: "#f2b56b", type: "dashed" } });
    if (levels && levels.resistance) markLines.push({ yAxis: levels.resistance, name: "阻力", lineStyle: { color: "#ef5350", type: "dashed" } });
    if (levels && levels.atr_stop) markLines.push({ yAxis: levels.atr_stop, name: "ATR止损", lineStyle: { color: "#67b7ff", type: "dotted" } });

    const option = {
      animation: false,
      backgroundColor: "transparent",
      textStyle: { color: "#8c9aaa", fontFamily: "Microsoft YaHei, sans-serif", fontSize: 10 },
      tooltip: {
        trigger: "axis",
        axisPointer: { type: "cross", lineStyle: { color: "#355064" } },
        backgroundColor: "#0f1821",
        borderColor: "#2a3c4c",
        textStyle: { color: "#e8eff6", fontSize: 11 },
        padding: 10,
      },
      axisPointer: { link: [{ xAxisIndex: "all" }] },
      grid: [
        { left: 58, right: 22, top: 18, height: "48%" },
        { left: 58, right: 22, top: "55%", height: "11%" },
        { left: 58, right: 22, top: "70%", height: "24%" },
      ],
      xAxis: [
        { type: "category", data: dates, gridIndex: 0, boundaryGap: true, axisLine: { lineStyle: { color: "#22303d" } }, axisLabel: { show: false }, axisTick: { show: false } },
        { type: "category", data: dates, gridIndex: 1, boundaryGap: true, axisLine: { lineStyle: { color: "#22303d" } }, axisLabel: { show: false }, axisTick: { show: false } },
        { type: "category", data: dates, gridIndex: 2, boundaryGap: true, axisLine: { lineStyle: { color: "#22303d" } }, axisLabel: { color: "#647383", fontSize: 9, hideOverlap: true, interval: "auto", formatter: (value) => String(value).slice(5) }, axisTick: { show: false } },
      ],
      yAxis: [
        { scale: true, gridIndex: 0, position: "left", splitNumber: 4, axisLabel: { color: "#8c9aaa", fontSize: 9 }, splitLine: { lineStyle: { color: "#17232e" } } },
        { scale: true, gridIndex: 1, position: "left", splitNumber: 2, axisLabel: { color: "#647383", fontSize: 8, formatter: (value) => `${(value / 10000).toFixed(0)}万` }, splitLine: { show: false } },
        { scale: true, gridIndex: 2, position: "left", splitNumber: 3, axisLabel: { color: "#8c9aaa", fontSize: 9 }, splitLine: { lineStyle: { color: "#17232e" } } },
      ],
      dataZoom: [
        { type: "inside", xAxisIndex: [0, 1, 2], start: dates.length > 200 ? 45 : 0, end: 100 },
        { type: "slider", xAxisIndex: [0, 1, 2], bottom: 2, height: 16, borderColor: "#22303d", backgroundColor: "#0e141b", fillerColor: "rgba(79,209,197,.10)", handleStyle: { color: "#4fd1c5" }, textStyle: { color: "#647383", fontSize: 9 }, start: dates.length > 200 ? 45 : 0, end: 100 },
      ],
      series: [
        {
          name: "K线", type: "candlestick", data: candle, xAxisIndex: 0, yAxisIndex: 0,
          itemStyle: { color: "#ef5350", color0: "#26a69a", borderColor: "#ef5350", borderColor0: "#26a69a" },
          markLine: { symbol: "none", silent: true, label: { color: "#8c9aaa", fontSize: 9, position: "insideEndTop" }, data: markLines },
        },
        { name: "MA5", type: "line", data: series.ma5, xAxisIndex: 0, yAxisIndex: 0, smooth: true, showSymbol: false, lineStyle: { width: 1, color: "#f2b56b" } },
        { name: "MA10", type: "line", data: series.ma10, xAxisIndex: 0, yAxisIndex: 0, smooth: true, showSymbol: false, lineStyle: { width: 1, color: "#8bd3ff" } },
        { name: "MA20", type: "line", data: series.ma20, xAxisIndex: 0, yAxisIndex: 0, smooth: true, showSymbol: false, lineStyle: { width: 1.2, color: "#67b7ff" } },
        { name: "MA60", type: "line", data: series.ma60, xAxisIndex: 0, yAxisIndex: 0, smooth: true, showSymbol: false, lineStyle: { width: 1.2, color: "#c69cff" } },
        { name: "VWAP20", type: "line", data: series.vwap20, xAxisIndex: 0, yAxisIndex: 0, showSymbol: false, lineStyle: { width: 1.4, color: "#f7d774" } },
        { name: "Supertrend", type: "line", data: series.st_line, xAxisIndex: 0, yAxisIndex: 0, showSymbol: false, lineStyle: { width: 1.6, color: "#4fd1c5" } },
        { name: "BOLL上轨", type: "line", data: series.boll_upper, xAxisIndex: 0, yAxisIndex: 0, showSymbol: false, lineStyle: { width: 1, color: "rgba(79,209,197,.38)", type: "dashed" } },
        { name: "BOLL下轨", type: "line", data: series.boll_lower, xAxisIndex: 0, yAxisIndex: 0, showSymbol: false, lineStyle: { width: 1, color: "rgba(79,209,197,.38)", type: "dashed" } },
        { name: "成交量", type: "bar", data: volumes, xAxisIndex: 1, yAxisIndex: 1, barWidth: "62%" },
        { name: "MACD柱", type: "bar", data: macdBars, xAxisIndex: 2, yAxisIndex: 2, barWidth: "62%" },
        { name: "DIF", type: "line", data: series.macd_dif, xAxisIndex: 2, yAxisIndex: 2, showSymbol: false, lineStyle: { width: 1, color: "#f2b56b" } },
        { name: "DEA", type: "line", data: series.macd_dea, xAxisIndex: 2, yAxisIndex: 2, showSymbol: false, lineStyle: { width: 1, color: "#67b7ff" } },
        { name: "RSI14", type: "line", data: series.rsi14, xAxisIndex: 2, yAxisIndex: 2, showSymbol: false, lineStyle: { width: 1, color: "rgba(198,156,255,.55)" } },
      ],
    };
    state.chart.setOption(option, true);
    state.chart.resize();
  }

  // ---------------------------------------------------------------- screener
  function renderConditionChips() {
    const container = $("conditionChips");
    container.innerHTML = Object.entries(CONDITION_LABELS).map(([key, label]) => `
      <button class="chip ${state.conditions.includes(key) ? "active" : ""}" data-condition="${key}">${esc(label)}</button>
    `).join("");
    container.querySelectorAll(".chip").forEach((chip) => {
      chip.addEventListener("click", () => {
        const key = chip.dataset.condition;
        if (state.conditions.includes(key)) {
          state.conditions = state.conditions.filter((item) => item !== key);
        } else {
          state.conditions.push(key);
        }
        renderConditionChips();
      });
    });
  }

  function resetConditions() {
    state.conditions = ["ma_bull", "above_ma20", "macd_positive", "rsi_50_75", "volume_expand"];
    renderConditionChips();
  }

  $("resetConditions").addEventListener("click", resetConditions);
  $("universeSelect").addEventListener("change", () => {
    $("customField").style.display = $("universeSelect").value === "custom" ? "" : "none";
  });

  async function runScreen() {
    const button = $("runScreen");
    button.disabled = true;
    $("screenStatus").textContent = "正在构建股票池…";
    $("screenProgress").style.width = "0%";
    $("screenTable").querySelector("tbody").innerHTML = '<tr><td colspan="10" class="empty">选股运行中…</td></tr>';
    $("topPicks").innerHTML = '<div class="empty">选股运行中…</div>';
    $("topPicksSub").textContent = "按 P0 信号质量排序，默认只取前 5 只";
    $("topPicksBadge").textContent = "--";
    const universe = $("universeSelect").value;
    const symbols = $("customSymbols").value.split(/[,，\s]+/).map((item) => item.trim()).filter(Boolean);
    if (universe === "custom" && !symbols.length) {
      toast("请输入至少一个代码", "bad");
      button.disabled = false;
      return;
    }
    try {
      const job = await api("/api/screen", {
        method: "POST",
        body: JSON.stringify({
          universe,
          symbols,
          conditions: state.conditions,
          match_mode: $("matchMode").value,
          min_matches: Number($("minMatches").value) || 1,
          max_results: Number($("maxResults").value) || 80,
          quality_filter: $("qualityFilter").value === "on",
          daily_top_k: Number($("dailyTopK").value) || 0,
          cooldown_days: Number($("cooldownDays").value) || 10,
        }),
      });
      state.screenJob = job.job_id;
      pollScreen();
    } catch (error) {
      toast(`选股启动失败：${error.message}`, "bad");
      $("screenStatus").textContent = "启动失败";
      button.disabled = false;
    }
  }

  function pollScreen() {
    clearTimeout(state.screenTimer);
    state.screenTimer = setTimeout(async () => {
      try {
        const job = await api(`/api/screen/${state.screenJob}`);
        $("screenProgress").style.width = `${job.progress || 0}%`;
        if (job.status === "queued") $("screenStatus").textContent = "排队中…";
        if (job.status === "running") $("screenStatus").textContent = `正在计算 ${job.done}/${job.total} · ${job.current || ""}`;
        if (job.status === "completed") {
          const result = job.result || {};
          $("screenStatus").textContent = `完成：合格 ${result.eligible || 0} 只，新信号 ${result.fresh || 0} 只`;
          $("screenSummary").textContent = `股票池 ${result.total || 0} 只 · 合格 ${result.eligible || 0} 只 · 新信号 ${result.fresh || 0} 只 · 显示 ${result.displayed || 0} 只${result.stale || result.fallback ? ` · 缓存 ${result.stale || 0} / BaoStock ${result.fallback || 0}` : ""}`;
          $("screenErrorCount").textContent = result.error_count ? `${result.error_count} 只取数失败` : (result.stale ? `${result.stale} 只使用本地缓存` : "");
          renderScreenResults(result);
          $("runScreen").disabled = false;
          return;
        }
        if (job.status === "failed") {
          $("screenStatus").textContent = `失败：${job.error}`;
          $("runScreen").disabled = false;
          toast(`选股失败：${job.error}`, "bad");
          return;
        }
        pollScreen();
      } catch (error) {
        $("screenStatus").textContent = `轮询失败：${error.message}`;
        $("runScreen").disabled = false;
      }
    }, 1400);
  }

  function renderSignalPill(item) {
    const status = String(item.signal_status || "不合格");
    const cls = item.fresh_signal ? "fresh" : (item.quality && item.quality.eligible ? "ok" : "warn");
    return `<span class="signal-pill ${cls}">${esc(status)}</span>`;
  }

  function renderTopPicks(result) {
    const picks = result.top_picks || [];
    const badge = $("topPicksBadge");
    badge.textContent = picks.length ? `${picks.length} 只` : "无";
    badge.className = `mini-badge ${picks.length ? "ok" : "warn"}`;
    $("topPicksSub").textContent = `质量过滤 ${result.quality_filter ? "开启" : "关闭"} · 合格 ${result.eligible || 0} 只 · 新信号 ${result.fresh || 0} 只 · Top ${result.daily_top_k || 0}`;
    if (!picks.length) {
      $("topPicks").innerHTML = '<div class="empty">没有合格候选。可关闭质量过滤，或放宽选股条件。</div>';
      return;
    }
    $("topPicks").innerHTML = picks.map((item, index) => {
      const q = item.quality || {};
      const m = q.metrics || {};
      const flags = (q.warnings || []).slice(0, 2).map((text) => `<span class="top-pick-warn">${esc(text)}</span>`).join("");
      return `
        <button class="top-pick clickable" data-symbol="${esc(item.symbol)}" data-name="${esc(item.name)}">
          <div class="top-pick-head">
            <span class="top-pick-rank">${String(index + 1).padStart(2, "0")}</span>
            <span class="top-pick-name">${esc(item.name)}</span>
            <span class="top-pick-symbol">${esc(item.symbol)}</span>
            <span class="quality-grade grade-${esc(q.grade || "D")}">${esc(q.grade || "D")}</span>
          </div>
          <div class="top-pick-score">${num(item.quality_score, 0)}<small>质量分</small></div>
          <div class="top-pick-meta">${esc(item.signal_status || "")} · VWAP ${m.vwap20_dist_pct === null || m.vwap20_dist_pct === undefined ? "--" : `${num(m.vwap20_dist_pct)}%`} · 量比 ${num(m.vol_ratio_20_prev, 2)}× · 实体 ${m.body_pct === null || m.body_pct === undefined ? "--" : `${num(m.body_pct, 1)}%`}</div>
          <div class="top-pick-flags">${flags || '<span class="top-pick-ok">四灯通过</span>'}</div>
        </button>
      `;
    }).join("");
    $("topPicks").querySelectorAll(".top-pick").forEach((button) => {
      button.addEventListener("click", () => selectStock(button.dataset.symbol, button.dataset.name));
    });
  }

  function renderScreenResults(result) {
    renderTopPicks(result);
    const body = $("screenTable").querySelector("tbody");
    if (!result.results || !result.results.length) {
      body.innerHTML = '<tr><td colspan="10" class="empty">没有命中的标的，试试放宽条件、关闭质量过滤或换股票池</td></tr>';
      return;
    }
    body.innerHTML = result.results.map((item) => `
      <tr class="clickable" data-symbol="${esc(item.symbol)}" data-name="${esc(item.name)}">
        <td><div class="cell-name">${esc(item.name)}</div><div class="cell-symbol">${esc(item.symbol)}</div></td>
        <td class="r mono">${num(item.metrics.close)}</td>
        <td class="r mono ${clsByChange(item.metrics.change_pct)}">${pct(item.metrics.change_pct)}</td>
        <td class="r mono">${num(item.score, 0)}</td>
        <td class="r mono">${num(item.quality_score, 0)}</td>
        <td>${renderSignalPill(item)}</td>
        <td class="conditions-cell">${(item.matched || []).map((key) => `<span class="condition-tag">${esc(CONDITION_LABELS[key] || key)}</span>`).join("") || '<span class="muted small">评分排序</span>'}</td>
        <td class="r mono">${num(item.metrics.rsi14, 1)}</td>
        <td class="r mono">${num(item.quality && item.quality.metrics ? item.quality.metrics.vol_ratio_20_prev : item.metrics.vol_ratio_5, 2)}</td>
        <td class="r mono ${clsByChange(item.metrics.ret20)}">${pct(item.metrics.ret20, 1)}</td>
      </tr>
    `).join("");
    body.querySelectorAll("tr[data-symbol]").forEach((row) => {
      row.addEventListener("click", () => selectStock(row.dataset.symbol, row.dataset.name));
    });
  }

  $("runScreen").addEventListener("click", runScreen);

  // ---------------------------------------------------------------- global refresh
  async function refreshAll() {
    await Promise.all([loadHealth(), loadIndices(), loadWatchlist(), loadSources(false)]);
    tickClock();
    toast("行情已刷新", "ok");
  }
  $("refreshAll").addEventListener("click", refreshAll);

  // ---------------------------------------------------------------- init
  async function init() {
    tickClock();
    setInterval(tickClock, 1000);
    renderConditionChips();
    await Promise.all([loadHealth(), loadIndices(), loadWatchlist(), loadSources(false)]);
    loadUniverses();
    window.addEventListener("resize", () => { if (state.chart) state.chart.resize(); });
  }

  async function loadUniverses() {
    try {
      const data = await api("/api/universes");
      const select = $("universeSelect");
      for (const item of data.items || []) {
        const option = Array.from(select.options).find((opt) => opt.value === item.id);
        if (option && item.count) option.textContent = `${item.name}（${item.count} 只）`;
      }
    } catch (_) {}
  }

  init();
})();
