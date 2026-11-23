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
    sentiment: null,
    sentimentLoaded: false,
    radarLoaded: false,
    radarLoading: false,
    profileSymbol: null,
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
  const yiText = (value, digits = 2) => {
    if (value === null || value === undefined || value === "") return "--";
    const n = Number(value);
    if (!Number.isFinite(n)) return "--";
    return `${n > 0 ? "+" : ""}${n.toFixed(digits)} 亿`;
  };
  const nval = (id) => {
    const raw = String($(id).value || "").trim();
    if (!raw) return null;
    const n = Number(raw);
    return Number.isFinite(n) ? n : null;
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
    if (name === "radar") ensureRadar();
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

  // ---------------------------------------------------------------- market radar
  function renderSentimentError(message) {
    $("radarAsOf").textContent = "市场快照不可用";
    $("radarAsOf").className = "head-badge";
    $("sentimentCards").innerHTML = `
      <div class="sentiment-card" style="grid-column:span 4">
        <div class="sent-kicker">MARKET SNAPSHOT</div>
        <div class="sent-value warn">不可用</div>
        <div class="sent-sub">${esc(message)}</div>
      </div>`;
    $("breadthBar").innerHTML = '<div class="breadth-empty">涨跌家数不可用</div>';
    $("breadthLegend").innerHTML = "";
    $("breadthBadge").textContent = "失败";
    $("breadthBadge").className = "mini-badge bad";
    ["limitUpTable", "weakTable", "dragonTable"].forEach((id) => {
      const cols = id === "limitUpTable" ? 7 : (id === "weakTable" ? 5 : 6);
      $(id).querySelector("tbody").innerHTML = `<tr><td colspan="${cols}" class="empty">${esc(message)}</td></tr>`;
    });
    $("sectorFlow").innerHTML = `<div class="muted small" style="padding:0 20px 18px">${esc(message)}</div>`;
    $("radarSummary").textContent = "全市场快照不可用，稍后重试或查看数据源状态。";
  }

  function renderSentiment(data) {
    if (!data || !data.ok) {
      renderSentimentError((data && data.error) || "市场数据请求失败");
      return;
    }
    state.sentiment = data;
    const b = data.breadth || {};
    const zt = data.limit_up || {};
    const dt = data.limit_down || {};
    const zb = data.broken_board || {};
    $("radarAsOf").textContent = `数据日 ${data.as_of || "--"}${data.quote_time ? ` · ${String(data.quote_time).slice(11, 16)}` : ""}`;
    $("radarAsOf").className = "head-badge";

    const breadthClass = clsByChange(b.median_pct);
    const cards = [
      {
        kicker: "涨 / 跌",
        value: `<span class="up">${num(b.up, 0)}</span><small>/</small><span class="down">${num(b.down, 0)}</span>`,
        sub: `平盘 ${num(b.flat, 0)} · 有效 ${num(b.total, 0)} 只`,
      },
      {
        kicker: "涨停",
        value: `${num(zt.count, 0)}<small>只</small>`,
        sub: zt.max_streak ? `最高 ${zt.max_streak} 连板 · 炸板 ${num(zb.count, 0)}` : `炸板 ${num(zb.count, 0)}`,
      },
      {
        kicker: "跌停",
        value: `${num(dt.count, 0)}<small>只</small>`,
        sub: `跌停池前 ${Math.min((dt.items || []).length, 12)} 只列在下方`,
      },
      {
        kicker: "封板率",
        value: `${num(zt.seal_rate, 1)}<small>%</small>`,
        sub: `涨停 ${num(zt.count, 0)} / 炸板 ${num(zb.count, 0)}`,
      },
      {
        kicker: "全市场成交额",
        value: `${num(b.amount_yi, 0)}<small>亿</small>`,
        sub: "全 A 快照合计",
      },
      {
        kicker: "涨幅中位数",
        value: pct(b.median_pct),
        sub: `强势 ≥5% ${num(b.strong_up, 0)} 只`,
        cls: breadthClass,
      },
      {
        kicker: "强势股 ≥5%",
        value: `${num(b.strong_up, 0)}<small>只</small>`,
        sub: `占有效样本 ${num((b.strong_up || 0) / Math.max(1, b.total || 1) * 100, 1)}%`,
      },
      {
        kicker: "弱势股 ≤-5%",
        value: `${num(b.strong_down, 0)}<small>只</small>`,
        sub: `占有效样本 ${num((b.strong_down || 0) / Math.max(1, b.total || 1) * 100, 1)}%`,
        cls: "down",
      },
    ];
    $("sentimentCards").innerHTML = cards.map((card) => `
      <div class="sentiment-card">
        <div class="sent-kicker">${esc(card.kicker)}</div>
        <div class="sent-value ${card.cls || ""}">${card.value}</div>
        <div class="sent-sub">${esc(card.sub)}</div>
      </div>
    `).join("");

    const total = Math.max(1, (b.up || 0) + (b.down || 0) + (b.flat || 0));
    const upW = (b.up || 0) / total * 100;
    const flatW = (b.flat || 0) / total * 100;
    const downW = (b.down || 0) / total * 100;
    $("breadthBar").innerHTML = `
      <div class="breadth-seg up" style="width:${upW}%"></div>
      <div class="breadth-seg flat" style="width:${flatW}%"></div>
      <div class="breadth-seg down" style="width:${downW}%"></div>`;
    $("breadthLegend").innerHTML = `
      <span><i class="up"></i>上涨 ${num(b.up, 0)}（${num(upW, 1)}%）</span>
      <span><i class="flat"></i>平盘 ${num(b.flat, 0)}（${num(flatW, 1)}%）</span>
      <span><i class="down"></i>下跌 ${num(b.down, 0)}（${num(downW, 1)}%）</span>
      <span>中位 ${pct(b.median_pct)} · 成交额 ${num(b.amount_yi, 0)} 亿</span>`;
    $("breadthBadge").textContent = `${num(b.total, 0)} 只`;
    $("breadthBadge").className = "mini-badge ok";
    $("breadthSub").textContent = `数据日 ${data.as_of || "--"} · 巨潮代码表 + 腾讯批量行情 · 有效样本 ${num(b.total, 0)} 只`;

    const upItems = zt.items || [];
    $("limitUpBadge").textContent = `${num(zt.count, 0)} 只`;
    $("limitUpBadge").className = `mini-badge ${zt.count ? "ok" : "warn"}`;
    $("limitUpSub").textContent = `最高 ${num(zt.max_streak, 0)} 连板 · 封板率 ${num(zt.seal_rate, 1)}% · 炸板 ${num(zb.count, 0)} 只`;
    const upBody = $("limitUpTable").querySelector("tbody");
    if (!upItems.length) {
      upBody.innerHTML = `<tr><td colspan="7" class="empty">${zt.error ? esc(zt.error) : "今日暂无涨停池数据"}</td></tr>`;
    } else {
      upBody.innerHTML = upItems.map((item) => `
        <tr class="clickable" data-symbol="${esc(item.symbol)}" data-name="${esc(item.name)}">
          <td><div class="cell-name">${esc(item.name)}</div><div class="cell-symbol">${esc(item.symbol)}</div></td>
          <td class="r mono up">${pct(item.pct)}</td>
          <td class="r mono">${item.streak ? `${item.streak} 板` : "--"}</td>
          <td class="r mono small">${esc(item.first_seal || "--")}</td>
          <td class="r mono">${yiText(item.seal_fund_yi)}</td>
          <td class="r mono ${item.broken_times ? "down" : ""}">${num(item.broken_times, 0)}</td>
          <td class="muted small">${esc(item.industry || "--")}</td>
        </tr>
      `).join("");
      upBody.querySelectorAll("tr[data-symbol]").forEach((row) => {
        row.addEventListener("click", () => selectStock(row.dataset.symbol, row.dataset.name));
      });
    }

    const weakRows = [
      ...(dt.items || []).map((item) => ({ ...item, kind: "跌停" })),
      ...(zb.items || []).map((item) => ({ ...item, kind: "炸板" })),
    ];
    $("weakBadge").textContent = `跌停 ${num(dt.count, 0)} · 炸板 ${num(zb.count, 0)}`;
    $("weakBadge").className = `mini-badge ${dt.count || zb.count ? "warn" : "ok"}`;
    $("weakSub").textContent = `跌停池 ${num(dt.count, 0)} 只 · 炸板池 ${num(zb.count, 0)} 只`;
    const weakBody = $("weakTable").querySelector("tbody");
    if (!weakRows.length) {
      weakBody.innerHTML = '<tr><td colspan="5" class="empty">今日暂无跌停或炸板数据</td></tr>';
    } else {
      weakBody.innerHTML = weakRows.map((item) => `
        <tr class="clickable" data-symbol="${esc(item.symbol)}" data-name="${esc(item.name)}">
          <td><span class="weak-tag ${item.kind === "跌停" ? "dt" : "zb"}">${esc(item.kind)}</span></td>
          <td><div class="cell-name">${esc(item.name)}</div><div class="cell-symbol">${esc(item.symbol)}</div></td>
          <td class="r mono ${clsByChange(item.pct)}">${pct(item.pct)}</td>
          <td class="r mono">${item.kind === "跌停" ? yiText(item.seal_fund_yi) : `${num(item.broken_times, 0)} 次`}</td>
          <td class="muted small">${esc(item.industry || "--")}</td>
        </tr>
      `).join("");
      weakBody.querySelectorAll("tr[data-symbol]").forEach((row) => {
        row.addEventListener("click", () => selectStock(row.dataset.symbol, row.dataset.name));
      });
    }

    const sectors = data.sectors || {};
    const sectorRows = (rows) => rows.length ? rows.map((item) => `
      <div class="sector-row">
        <div class="sector-name">${esc(item.name)}<small>${esc(item.leader || "暂无领涨")}</small></div>
        <div class="sector-net ${clsByChange(item.main_net_yi)}">${yiText(item.main_net_yi)}</div>
        <div class="sector-pct">${pct(item.main_pct)}</div>
      </div>
    `).join("") : '<div class="muted small">暂无数据</div>';
    if (!sectors.ok || (!(sectors.inflow || []).length && !(sectors.outflow || []).length)) {
      $("sectorBadge").textContent = "不可用";
      $("sectorBadge").className = "mini-badge bad";
      $("sectorFlow").innerHTML = `<div class="muted small" style="padding:0 20px 18px">${esc(sectors.note || sectors.error || "板块资金流接口暂不可用")}</div>`;
    } else {
      $("sectorBadge").textContent = "观察";
      $("sectorBadge").className = "mini-badge warn";
      $("sectorFlow").innerHTML = `
        <div class="sector-side">
          <div class="sector-side-title">主力净流入</div>
          ${sectorRows(sectors.inflow || [])}
        </div>
        <div class="sector-side">
          <div class="sector-side-title">主力净流出</div>
          ${sectorRows(sectors.outflow || [])}
        </div>
        <div class="sector-note" style="grid-column:1/-1">${esc(sectors.note || "")}</div>`;
    }

    const dragon = data.dragon_tiger || {};
    $("dragonBadge").textContent = dragon.ok ? `${num(dragon.count, 0)} 只` : "不可用";
    $("dragonBadge").className = `mini-badge ${dragon.ok ? "ok" : "bad"}`;
    $("dragonSub").textContent = dragon.ok ? `数据日 ${dragon.date || data.as_of} · 按净买入额排序` : "龙虎榜接口暂不可用";
    const dragonBody = $("dragonTable").querySelector("tbody");
    if (!dragon.ok || !(dragon.items || []).length) {
      dragonBody.innerHTML = `<tr><td colspan="6" class="empty">${esc(dragon.error || "今日暂无龙虎榜数据")}</td></tr>`;
    } else {
      dragonBody.innerHTML = dragon.items.map((item) => `
        <tr class="clickable" data-symbol="${esc(item.code)}" data-name="${esc(item.name)}">
          <td><div class="cell-name">${esc(item.name)}</div><div class="cell-symbol">${esc(item.code)}</div></td>
          <td class="r mono ${clsByChange(item.pct)}">${pct(item.pct)}</td>
          <td class="r mono ${clsByChange(item.net_buy_yi)}">${yiText(item.net_buy_yi)}</td>
          <td class="r mono">${yiText(item.buy_yi)}</td>
          <td class="r mono">${yiText(item.sell_yi)}</td>
          <td class="muted small">${esc(item.reason || "--")}</td>
        </tr>
      `).join("");
      dragonBody.querySelectorAll("tr[data-symbol]").forEach((row) => {
        const symbol = row.dataset.symbol;
        const normalized = symbol.includes(".") ? symbol : `${symbol}.${String(symbol).startsWith("6") ? "SH" : (String(symbol).startsWith("8") || String(symbol).startsWith("4") ? "BJ" : "SZ")}`;
        row.addEventListener("click", () => selectStock(normalized, row.dataset.name));
      });
    }
  }

  async function loadSentiment(force = false) {
    $("radarAsOf").textContent = "正在加载全市场快照…";
    $("radarAsOf").className = "head-badge";
    try {
      const data = await api(`/api/market/sentiment?refresh=${force ? "true" : "false"}`);
      renderSentiment(data);
      state.sentimentLoaded = true;
    } catch (error) {
      renderSentimentError(error.message);
      state.sentimentLoaded = true;
      toast(`市场雷达加载失败：${error.message}`, "bad");
    }
  }

  function buildRadarQuery() {
    const params = new URLSearchParams();
    const q = $("radarQ").value.trim();
    if (q) params.set("q", q);
    params.set("board", $("radarBoard").value);
    const numeric = [
      ["min_pct", "radarMinPct"], ["max_pct", "radarMaxPct"],
      ["min_turnover", "radarMinTurnover"], ["max_turnover", "radarMaxTurnover"],
      ["min_amount_yi", "radarMinAmount"], ["max_amount_yi", "radarMaxAmount"],
      ["min_cap_yi", "radarMinCap"], ["max_cap_yi", "radarMaxCap"],
      ["min_pe", "radarMinPe"], ["max_pe", "radarMaxPe"],
    ];
    numeric.forEach(([key, id]) => {
      const value = nval(id);
      if (value !== null) params.set(key, String(value));
    });
    params.set("exclude_st", $("radarExcludeSt").value);
    params.set("sort", $("radarSort").value);
    params.set("order", $("radarOrder").value);
    params.set("limit", String(Math.max(10, Math.min(300, Number($("radarLimit").value) || 120))));
    return params;
  }

  async function loadRadar() {
    const body = $("radarTable").querySelector("tbody");
    body.innerHTML = '<tr><td colspan="9" class="empty">正在筛选全市场快照…</td></tr>';
    try {
      const data = await api(`/api/market/radar?${buildRadarQuery().toString()}`);
      if (!data.ok) throw new Error(data.error || "雷达接口返回失败");
      $("radarSummary").textContent = `全市场 ${num(data.total, 0)} 只 · 命中 ${num(data.matched, 0)} 只 · 显示 ${num(data.displayed, 0)} 只 · 数据日 ${data.as_of || "--"}`;
      if (!data.items || !data.items.length) {
        body.innerHTML = '<tr><td colspan="9" class="empty">没有命中的标的，试试放宽涨跌幅、换手或市值条件</td></tr>';
        state.radarLoaded = true;
        return;
      }
      body.innerHTML = data.items.map((item) => `
        <tr class="clickable" data-symbol="${esc(item.symbol)}" data-name="${esc(item.name)}">
          <td><div class="cell-name">${esc(item.name)}</div><div class="cell-symbol">${esc(item.symbol)}</div></td>
          <td class="muted small">${esc(item.board || "--")}</td>
          <td class="r mono">${num(item.price, 3)}</td>
          <td class="r mono ${clsByChange(item.pct)}">${pct(item.pct)}</td>
          <td class="r mono">${num(item.turnover, 2)}%</td>
          <td class="r mono">${num((item.amount || 0) / 1e8, 2)} 亿</td>
          <td class="r mono">${num(item.market_cap_yi, 1)} 亿</td>
          <td class="r mono">${item.pe !== null && item.pe !== undefined && Number(item.pe) > 0 ? num(item.pe, 1) : '<span class="muted">亏损</span>'}</td>
          <td class="r mono">${num(item.pb, 2)}</td>
        </tr>
      `).join("");
      body.querySelectorAll("tr[data-symbol]").forEach((row) => {
        row.addEventListener("click", () => selectStock(row.dataset.symbol, row.dataset.name));
      });
      state.radarLoaded = true;
    } catch (error) {
      $("radarSummary").textContent = `雷达加载失败：${error.message}`;
      body.innerHTML = `<tr><td colspan="9" class="empty">${esc(error.message)}</td></tr>`;
      state.radarLoaded = false;
    }
  }

  async function ensureRadar(force = false) {
    if (state.radarLoading) return;
    state.radarLoading = true;
    try {
      if (force || !state.sentimentLoaded) await loadSentiment(force);
      if (force || !state.radarLoaded) await loadRadar();
    } finally {
      state.radarLoading = false;
    }
  }

  function resetRadar() {
    ["radarQ", "radarMinPct", "radarMaxPct", "radarMinTurnover", "radarMaxTurnover",
      "radarMinAmount", "radarMaxAmount", "radarMinCap", "radarMaxCap", "radarMinPe", "radarMaxPe"]
      .forEach((id) => { $(id).value = ""; });
    $("radarBoard").value = "all";
    $("radarSort").value = "pct";
    $("radarOrder").value = "desc";
    $("radarExcludeSt").value = "true";
    $("radarLimit").value = "120";
    loadRadar();
  }

  $("runRadar").addEventListener("click", loadRadar);
  $("resetRadar").addEventListener("click", resetRadar);
  if ($("refreshRadar")) $("refreshRadar").addEventListener("click", () => ensureRadar(true));
  $("radarQ").addEventListener("keydown", (event) => { if (event.key === "Enter") loadRadar(); });

  // ---------------------------------------------------------------- stock profile / flow
  function renderProfile(data) {
    const container = $("profileStrip");
    if (!data || data.ok === false || data.error) {
      container.innerHTML = `<div class="profile-cell wide"><span>估值与归属</span><b>${esc((data && data.error) || "个股快照不可用")}</b></div>`;
      return;
    }
    const pe = data.pe_ttm !== null && data.pe_ttm !== undefined ? Number(data.pe_ttm) : null;
    const pb = data.pb !== null && data.pb !== undefined ? Number(data.pb) : null;
    const industry = data.industry || "";
    const concepts = data.concepts || [];
    const tags = [
      industry ? `<span class="concept-tag">${esc(industry)}</span>` : "",
      ...concepts.slice(0, 8).map((item) => `<span class="concept-tag">${esc(item)}</span>`),
    ].join("");
    container.innerHTML = `
      <div class="profile-cell"><span>PE(TTM)</span><b>${pe === null ? "--" : (pe > 0 ? num(pe, 2) : "亏损")}</b></div>
      <div class="profile-cell"><span>PB</span><b>${pb === null ? "--" : num(pb, 2)}</b></div>
      <div class="profile-cell"><span>总市值</span><b>${data.market_cap_yi === null || data.market_cap_yi === undefined ? "--" : `${num(data.market_cap_yi, 1)} 亿`}</b></div>
      <div class="profile-cell"><span>流通市值</span><b>${data.float_cap_yi === null || data.float_cap_yi === undefined ? "--" : `${num(data.float_cap_yi, 1)} 亿`}</b></div>
      <div class="profile-cell"><span>换手</span><b>${data.turnover === null || data.turnover === undefined ? "--" : `${num(data.turnover, 2)}%`}</b></div>
      <div class="profile-cell wide"><span>估值 / 行业 / 概念</span><b>${tags || "行业与概念快照暂不可用（当前仅腾讯 PE/PB/市值）"}</b></div>`;
  }

  function renderFlow(data) {
    const bars = $("flowBars");
    const summary = $("flowSummary");
    const badge = $("flowBadge");
    if (!data || data.ok === false || !(data.items || []).length) {
      badge.textContent = "不可用";
      badge.className = "mini-badge bad";
      bars.innerHTML = `<div class="muted small" style="padding:0 20px 18px">${esc((data && data.error) || "资金流数据不可用")}</div>`;
      summary.innerHTML = "";
      return;
    }
    const items = data.items;
    const nets = items.map((item) => Math.abs(Number(item.main_net_yi || 0)));
    const maxAbs = Math.max(0.01, ...nets);
    badge.textContent = `${items.length} 日`;
    badge.className = "mini-badge warn";
    bars.innerHTML = items.map((item) => {
      const value = Number(item.main_net_yi || 0);
      const width = Math.min(100, Math.abs(value) / maxAbs * 100);
      const cls = clsByChange(value);
      return `
        <div class="flow-row">
          <span class="flow-date">${esc(String(item.date || "--").slice(5))}</span>
          <div class="flow-track"><div class="flow-fill ${cls}" style="width:${width}%"></div></div>
          <span class="flow-value ${cls}">${yiText(value)}</span>
        </div>`;
    }).join("");
    const s = data.summary || {};
    summary.innerHTML = `
      <div class="flow-sum-item"><span>最新</span><b>${yiText(s.last_main_net_yi)}</b></div>
      <div class="flow-sum-item"><span>近 5 日</span><b>${yiText(s.sum5_yi)}</b></div>
      <div class="flow-sum-item"><span>近 10 日</span><b>${yiText(s.sum10_yi)}</b></div>
      <div class="flow-sum-item"><span>近 20 日</span><b>${yiText(s.sum20_yi)}</b></div>`;
    bars.innerHTML += `<div class="flow-note">${esc(data.note || "")}</div>`;
  }

  async function loadProfileAndFlow(symbol) {
    state.profileSymbol = symbol;
    try {
      const profile = await api(`/api/stock/profile?symbol=${encodeURIComponent(symbol)}`);
      if (state.currentSymbol === symbol) renderProfile(profile);
    } catch (error) {
      if (state.currentSymbol === symbol) renderProfile({ error: error.message });
    }
    try {
      const flow = await api(`/api/stock/flow?symbol=${encodeURIComponent(symbol)}&days=10`);
      if (state.currentSymbol === symbol) renderFlow(flow);
    } catch (error) {
      if (state.currentSymbol === symbol) renderFlow({ error: error.message });
    }
  }

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
    $("profileStrip").innerHTML = '<div class="profile-cell wide"><span>估值与归属</span><b>正在读取…</b></div>';
    $("flowBars").innerHTML = '<div class="muted small" style="padding:0 20px 18px">正在读取资金流…</div>';
    $("flowSummary").innerHTML = "";
    $("flowBadge").textContent = "--";
    $("flowBadge").className = "mini-badge";
    loadProfileAndFlow(symbol);
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
          strict_gates: $("strictGates").value === "on",
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
    $("topPicksSub").textContent = `质量过滤 ${result.quality_filter ? "开启" : "关闭"} · ${result.strict_gates ? "严格四灯" : "核心日线+周线"} · 合格 ${result.eligible || 0} 只 · 新信号 ${result.fresh || 0} 只 · Top ${result.daily_top_k || 0}`;
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
          <div class="top-pick-flags">${flags || '<span class="top-pick-ok">核心灯通过</span>'}</div>
        </button>
      `;
    }).join("");
    $("topPicks").querySelectorAll(".top-pick").forEach((button) => {
      button.addEventListener("click", () => selectStock(button.dataset.symbol, button.dataset.name));
    });
  }

  function renderScreenResults(result) {
    renderTopPicks(result);
    loadLedger();
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

  async function loadLedger() {
    try {
      const data = await api("/api/ledger?days=30&limit=100");
      const summary = data.summary || {};
      $("ledgerSummary").textContent = summary.total
        ? `近 ${data.days} 天：${summary.total} 条 · ${summary.days} 个数据日 · 新信号 ${summary.fresh || 0} 条 · ${summary.first_date || "--"} 至 ${summary.last_date || "--"}`
        : "近 30 天暂无记录；运行一次带 Top K 的选股后自动写入";
      const body = $("ledgerTable").querySelector("tbody");
      if (!data.items || !data.items.length) {
        body.innerHTML = '<tr><td colspan="8" class="empty">暂无台账记录</td></tr>';
        return;
      }
      body.innerHTML = data.items.map((item) => `
        <tr class="clickable" data-symbol="${esc(item.symbol)}" data-name="${esc(item.name)}">
          <td class="mono">${esc(item.trade_date)}</td>
          <td><div class="cell-name">${esc(item.name)}</div><div class="cell-symbol">${esc(item.symbol)}</div></td>
          <td class="r mono">${num(item.top_rank, 0)}</td>
          <td class="r mono">${num(item.quality_score, 0)}</td>
          <td><span class="quality-grade grade-${esc(item.grade || "D")}">${esc(item.grade || "D")}</span></td>
          <td>${esc(item.signal_status || "")}${item.fresh_signal ? ' <span class="signal-pill fresh">新</span>' : ""}</td>
          <td class="r mono">${num(item.trend_score, 0)}</td>
          <td class="mono small">${esc(item.recorded_at)}</td>
        </tr>
      `).join("");
      body.querySelectorAll("tr[data-symbol]").forEach((row) => {
        row.addEventListener("click", () => selectStock(row.dataset.symbol, row.dataset.name));
      });
    } catch (error) {
      $("ledgerSummary").textContent = `台账读取失败：${error.message}`;
    }
  }

  $("refreshLedger").addEventListener("click", loadLedger);

  // ---------------------------------------------------------------- global refresh
  async function refreshAll() {
    await Promise.all([loadHealth(), loadIndices(), loadWatchlist(), loadSources(false), loadLedger()]);
    tickClock();
    toast("行情已刷新", "ok");
  }
  $("refreshAll").addEventListener("click", refreshAll);

  // ---------------------------------------------------------------- init
  async function init() {
    tickClock();
    setInterval(tickClock, 1000);
    renderConditionChips();
    await Promise.all([loadHealth(), loadIndices(), loadWatchlist(), loadSources(false), loadLedger()]);
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
