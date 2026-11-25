/* AndesMart case study: charts + simulator. Data: data.json (src/data_gen/export_site_data.py). */
(() => {
  "use strict";

  // ------------------------------------------------------------------ i18n
  const ES = {
    "nav.finding": "Hallazgo", "nav.simulator": "Simulador", "nav.architecture": "Arquitectura", "nav.results": "Resultados",
    "hero.eyebrow": "Forward-deployed engineering · Databricks",
    "hero.title": "Mismo inventario, <em>57% menos</em> ventas perdidas.",
    "hero.lede": "Una cadena de ropa se quedaba sin tallas M y L mientras liquidaba XS y XXL. Lo llevé de discovery a producción en Databricks: un lakehouse gobernado, controles de calidad, un forecast de demanda, una política de reposición y un agente Genie que responde en español.",
    "hero.repo": "Ver el código en GitHub", "hero.try": "Probar el simulador ↓",
    "hero.disclaimer": "Cliente simulado y datos sintéticos, trabajados como un engagement real.",
    "stat.lost": "ventas perdidas, mismo inventario", "stat.m": "tasa de quiebre en talla M",
    "stat.est": "error del estimador de venta perdida, tras depurarlo", "stat.genie": "preguntas de evaluación de Genie",
    "problem.title": "El problema",
    "problem.quote": "“Se nos acaban las M y L de lo que más se vende y terminamos la temporada liquidando XS y XL al 50%. Nos enteramos tarde.”",
    "problem.who": "Gerente de Operaciones (simulado)",
    "problem.f1": "tiendas en Perú, Chile, Colombia y México", "problem.f2": "SKUs (modelo × color × talla)",
    "problem.f3": "semanales de consolidación manual en Excel", "problem.f4": "forecasts de demanda; reposición semanal “a ojo”",
    "finding.title": "El hallazgo: es la curva de tallas, no el volumen",
    "finding.lede": "El planner reparte cada pedido en partes iguales entre tallas. La demanda no es pareja: M y L son más de la mitad, pero cada una recibe la misma parte del stock que XS.",
    "finding.chart": "Participación en la demanda vs. en el stock, por talla (ropa)",
    "common.table": "Ver como tabla",
    "sim.title": "Simulador de reposición",
    "sim.lede": "El mismo año, con exactamente la misma demanda de clientes, repetido con tres políticas de reposición. Elige una y compárala con la práctica actual.",
    "policy.even_split": "Reparto parejo (hoy)", "policy.size_curve": "Curva de tallas", "policy.size_aware": "Curva + demanda sin censura",
    "sim.bySize": "Tasa de quiebre por talla", "sim.weekly": "Tasa de quiebre semanal durante el año",
    "sim.note": "Backtest contrafactual con el simulador del proyecto: 1 año y 12 tiendas; KPIs promediados en 3 semillas, gráficos con la semilla 42. Quiebre = SKU con demanda en los últimos 14 días que cierra el día sin stock.",
    "arch.title": "Cómo está construido", "arch.lede": "Todo corre en Databricks, desplegado como código desde GitHub.",
    "arch.s1": "Archivos POS y ERP, clima, feriados", "arch.s1d": "Generador sintético + APIs de Open-Meteo y Nager.Date",
    "arch.s2d": "Ingesta incremental, todo como texto crudo, sin perder nada",
    "arch.s3": "Reglas + cuarentena", "arch.s3d": "Las filas inválidas se guardan con el motivo del rechazo",
    "arch.s4": "Quiebres y venta perdida", "arch.s4d": "Quiebre diario, KPIs semanales, curva de tallas, venta perdida estimada",
    "arch.s5d": "Frena el job si la cuarentena supera el 1% o una tabla queda vacía",
    "arch.s6d": "Forecast semanal; solo pasa a “champion” si le gana al baseline",
    "arch.s7d": "Vistas semánticas en español con definición de negocio por columna",
    "res.title": "Resultados", "res.wape": "Error del forecast (WAPE, menor es mejor)",
    "res.est": "Estimador de venta perdida validado contra la verdad",
    "res.estd": "La primera versión sobreestimaba un 60%: el inventario es al cierre, así que un SKU que se quebró a media jornada contaba como día perdido completo. Corregido, queda a ~8% de la verdad.",
    "res.genie": "Agente Genie: 6 → 9 → 10 → 12 de 12",
    "res.genied": "La mitad de las fallas iniciales estaban en mi SQL de referencia, no en el agente. Las definiciones de negocio quedaron escritas en las instrucciones, así el puntaje no sale de sobreajustar al benchmark.",
    "res.train": "Entrenado con demanda sin censura",
    "res.traind": "En los días de quiebre la venta está censurada. El modelo aprende de venta + venta perdida estimada; si no, subestimaría justo las tallas que se quiebran.",
    "ai.title": "AI-first, con criterio",
    "ai.lede": "Construido con Claude Code. Cada pieza generada por IA se revisó con tests y se validó contra la verdad. Algunas cosas que eso detectó:",
    "ai.b1": "Espiral de quiebres", "ai.b1d": "La primera simulación reponía según ventas ya censuradas. La demanda perdida era 3× la venta real.",
    "ai.b2": "Venta perdida inflada", "ai.b2d": "El estimador se pasaba un 60%. Validarlo contra la verdad del generador expuso el problema del snapshot al cierre.",
    "ai.b3": "Decimal → pandas", "ai.b3d": "Los decimal de Spark se volvían objetos Decimal de Python y rompían el forecast. Detectado en una corrida local de punta a punta, antes de producción.",
    "ai.b4": "Errores de I/O en producción", "ai.b4d": "Los jobs fallaban de forma intermitente al leer el código desde el workspace. Se resolvió empaquetándolo como un wheel versionado en un Volume de Unity Catalog.",
    "footer.text": "Proyecto de portafolio · cliente simulado, datos sintéticos.",
    // dinámicos
    "pdesc.even_split": "Práctica actual: el planner proyecta la venta reciente del modelo-color y la reparte en partes iguales entre tallas.",
    "pdesc.size_curve": "Mismo total que hoy, repartido según la curva de tallas observada. Sin comprar más inventario.",
    "pdesc.size_aware": "La solución: curva de tallas + demanda sin censura (venta + venta perdida estimada), como hacen el forecast y la capa Gold.",
    "kpi.stockout": "Tasa de quiebre", "kpi.fill": "Fill rate (demanda atendida)", "kpi.lost": "Unidades perdidas / año", "kpi.inv": "Inventario promedio",
    "kpi.vsToday": "vs. hoy", "kpi.baseline": "línea base",
    "s.demand": "Demanda", "s.stock": "Stock", "s.today": "Hoy (reparto parejo)", "s.selected": "Política elegida",
    "t.size": "Talla", "t.week": "Semana (cierre)", "t.level": "Nivel",
    "w.model": "Modelo", "w.naive": "Semana anterior", "w.roll": "Promedio 4 semanas",
    "lvl.store_sku": "Tienda × SKU", "lvl.store_model_color": "Tienda × modelo-color", "lvl.country_category": "País × categoría",
  };
  const EN = {
    "pdesc.even_split": "Today's practice: the planner projects recent model-color sales and splits the order evenly across sizes.",
    "pdesc.size_curve": "Same total as today, allocated by the observed size curve. No extra inventory purchased.",
    "pdesc.size_aware": "The solution: size curve + uncensored demand (sales + estimated lost sales), as the forecast and the Gold layer do.",
    "kpi.stockout": "Stockout rate", "kpi.fill": "Fill rate (demand served)", "kpi.lost": "Lost units / year", "kpi.inv": "Average inventory",
    "kpi.vsToday": "vs. today", "kpi.baseline": "baseline",
    "s.demand": "Demand", "s.stock": "Stock", "s.today": "Today (even split)", "s.selected": "Selected policy",
    "t.size": "Size", "t.week": "Week (ending)", "t.level": "Level",
    "w.model": "Model", "w.naive": "Last week", "w.roll": "4-week average",
    "lvl.store_sku": "Store × SKU", "lvl.store_model_color": "Store × model-color", "lvl.country_category": "Country × category",
  };
  const staticEN = {};
  document.querySelectorAll("[data-i18n]").forEach(el => { staticEN[el.dataset.i18n] = el.innerHTML; });

  const store = {
    get(k) { try { return localStorage.getItem(k); } catch { return null; } },
    set(k, v) { try { localStorage.setItem(k, v); } catch { /* sin storage */ } },
  };
  let lang = store.get("lang") || ((navigator.language || "").startsWith("es") ? "es" : "en");
  const t = k => (lang === "es" ? ES[k] : (EN[k] ?? staticEN[k])) ?? k;
  const locale = () => (lang === "es" ? "es-PE" : "en-US");
  const pct = (v, d = 1) => (v * 100).toLocaleString(locale(), { maximumFractionDigits: d, minimumFractionDigits: d }) + "%";
  const num = v => Math.round(v).toLocaleString(locale());

  function applyLang() {
    document.documentElement.lang = lang;
    document.querySelectorAll("[data-i18n]").forEach(el => { el.innerHTML = t(el.dataset.i18n); });
    document.getElementById("lang-toggle").textContent = lang === "es" ? "EN" : "ES";
  }

  // ------------------------------------------------------------------ theme
  function applyTheme(theme) {
    if (theme) document.documentElement.dataset.theme = theme;
    else delete document.documentElement.dataset.theme;
  }
  applyTheme(store.get("theme"));
  const isDark = () => {
    const th = document.documentElement.dataset.theme;
    return th ? th === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
  };
  const css = name => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

  // ------------------------------------------------------------------ charts
  const SERIES = { even_split: "--series-current", size_curve: "--series-curve", size_aware: "--series-solution" };
  let DATA = null, policy = "size_aware";
  const charts = {};

  function baseOptions({ yPct = true, yMax } = {}) {
    const text = css("--text-secondary"), grid = css("--grid");
    return {
      responsive: true, maintainAspectRatio: false, animation: { duration: 250 },
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: css("--surface-1"), titleColor: css("--text-primary"), bodyColor: css("--text-primary"),
          borderColor: css("--border"), borderWidth: 1, padding: 10, boxPadding: 4, usePointStyle: true,
          callbacks: { label: c => ` ${c.dataset.label}: ${yPct ? pct(c.parsed.y) : c.parsed.y.toFixed(2)}` },
        },
      },
      scales: {
        x: { grid: { display: false }, ticks: { color: text, font: { family: "Inter" } }, border: { color: grid } },
        y: {
          beginAtZero: true, max: yMax, grid: { color: grid }, border: { display: false },
          ticks: { color: text, font: { family: "Inter" }, callback: v => (yPct ? pct(v, 0) : v.toFixed(1)), maxTicksLimit: 6 },
        },
      },
    };
  }
  const bar = color => ({ backgroundColor: color, borderRadius: { topLeft: 4, topRight: 4 }, borderSkipped: "bottom",
    borderColor: css("--surface-1"), borderWidth: { left: 1, right: 1 }, maxBarThickness: 36, categoryPercentage: 0.7, barPercentage: 0.9 });

  function legend(id, items, line = false) {
    document.getElementById(id).innerHTML = items.map(([label, color]) =>
      `<span><i class="swatch${line ? " line" : ""}" style="background:${color}"></i>${label}</span>`).join("");
  }
  function table(id, head, rows, scroll = false) {
    const h = `<tr>${head.map(x => `<th scope="col">${x}</th>`).join("")}</tr>`;
    const b = rows.map(r => `<tr>${r.map(x => `<td>${x}</td>`).join("")}</tr>`).join("");
    document.getElementById(id).innerHTML = `<div class="${scroll ? "table-scroll" : ""}"><table>${h}${b}</table></div>`;
  }
  function upsert(key, canvasId, config) {
    if (charts[key]) charts[key].destroy();
    charts[key] = new Chart(document.getElementById(canvasId), config);
  }

  function renderFinding() {
    const sc = DATA.size_curve, cD = css("--series-solution"), cS = css("--series-current");
    upsert("finding", "chart-finding", {
      type: "bar",
      data: { labels: sc.map(r => r.size), datasets: [
        { label: t("s.demand"), data: sc.map(r => r.demand_share), ...bar(cD) },
        { label: t("s.stock"), data: sc.map(r => r.stock_share), ...bar(cS) },
      ] },
      options: baseOptions(),
    });
    legend("legend-finding", [[t("s.demand"), cD], [t("s.stock"), cS]]);
    table("table-finding", [t("t.size"), t("s.demand"), t("s.stock")], sc.map(r => [r.size, pct(r.demand_share), pct(r.stock_share)]));
  }

  function renderSimulator() {
    const cur = DATA.policies.even_split, sel = DATA.policies[policy];
    const sumCur = DATA.summary.even_split, sumSel = DATA.summary[policy];
    const cCur = css(SERIES.even_split), cSel = css(SERIES[policy]);
    const same = policy === "even_split";

    document.querySelectorAll("#policy-picker button").forEach(b => b.setAttribute("aria-checked", String(b.dataset.policy === policy)));
    document.getElementById("policy-desc").textContent = t(`pdesc.${policy}`);

    // flecha = dirección del cambio; color = si es bueno o malo para el negocio
    const deltaHtml = (d, text, lowerIsBetter) => {
      if (same) return `<div class="kpi-delta">● ${t("kpi.baseline")}</div>`;
      if (Math.abs(d) < 0.01) return `<div class="kpi-delta">● ${text} ${t("kpi.vsToday")}</div>`;
      const good = lowerIsBetter ? d < 0 : d > 0;
      return `<div class="kpi-delta ${good ? "good" : "bad"}">${d < 0 ? "▼" : "▲"} ${text} ${t("kpi.vsToday")}</div>`;
    };
    const delta = (a, b, lowerIsBetter = true) => {
      const d = b / a - 1;
      return deltaHtml(d, `${d > 0 ? "+" : ""}${pct(d, 0)}`, lowerIsBetter);
    };
    const fd = sumSel.fill_rate - sumCur.fill_rate;
    const fillDelta = deltaHtml(fd * 10, `${fd > 0 ? "+" : ""}${(fd * 100).toFixed(1)} pp`, false);
    document.getElementById("kpis").innerHTML = [
      [t("kpi.stockout"), pct(sumSel.stockout_rate), delta(sumCur.stockout_rate, sumSel.stockout_rate)],
      [t("kpi.fill"), pct(sumSel.fill_rate), fillDelta],
      [t("kpi.lost"), num(sumSel.lost_units), delta(sumCur.lost_units, sumSel.lost_units)],
      [t("kpi.inv"), num(sumSel.avg_inventory_units), delta(sumCur.avg_inventory_units, sumSel.avg_inventory_units)],
    ].map(([l, v, d]) => `<div class="kpi"><div class="kpi-label">${l}</div><div class="kpi-value">${v}</div>${d}</div>`).join("");

    const sizes = Object.keys(cur.by_size);
    const dsSize = [{ label: t("s.today"), data: sizes.map(s => cur.by_size[s].stockout_rate), ...bar(cCur) }];
    if (!same) dsSize.push({ label: t(`policy.${policy}`), data: sizes.map(s => sel.by_size[s].stockout_rate), ...bar(cSel) });
    upsert("size", "chart-size", { type: "bar", data: { labels: sizes, datasets: dsSize }, options: baseOptions() });
    legend("legend-size", dsSize.map(d => [d.label, d.backgroundColor]));
    table("table-size", [t("t.size"), t("s.today"), ...(same ? [] : [t(`policy.${policy}`)])],
      sizes.map(s => [s, pct(cur.by_size[s].stockout_rate), ...(same ? [] : [pct(sel.by_size[s].stockout_rate)])]));

    const fmtWeek = w => new Date(w + "T00:00:00").toLocaleDateString(locale(), { month: "short", day: "numeric" });
    const weeks = cur.weekly.map(w => fmtWeek(w.week_end));
    const line = (label, color, data) => ({ label, data, borderColor: color, backgroundColor: color, borderWidth: 2,
      pointRadius: 0, pointHoverRadius: 5, pointHoverBorderWidth: 2, pointHoverBorderColor: css("--surface-1"), tension: 0.25 });
    const dsW = [line(t("s.today"), cCur, cur.weekly.map(w => w.stockout_rate))];
    if (!same) dsW.push(line(t(`policy.${policy}`), cSel, sel.weekly.map(w => w.stockout_rate)));
    const optW = baseOptions();
    optW.scales.x.ticks.maxTicksLimit = 7;
    optW.scales.x.ticks.autoSkip = true;
    optW.scales.x.ticks.maxRotation = 0;
    upsert("weekly", "chart-weekly", { type: "line", data: { labels: weeks, datasets: dsW }, options: optW });
    legend("legend-weekly", dsW.map(d => [d.label, d.borderColor]), true);
    table("table-weekly", [t("t.week"), t("s.today"), ...(same ? [] : [t(`policy.${policy}`)])],
      cur.weekly.map((w, i) => [w.week_end, pct(w.stockout_rate), ...(same ? [] : [pct(sel.weekly[i].stockout_rate)])]), true);
  }

  function renderWape() {
    const rows = DATA.measured.forecast_wape;
    const cM = css("--series-solution"), cN = css("--series-current"), cR = css("--series-curve");
    const labels = rows.map(r => t(`lvl.${r.level}`));
    const ds = [
      { label: t("w.model"), data: rows.map(r => r.model), ...bar(cM) },
      { label: t("w.roll"), data: rows.map(r => r.naive_roll_4), ...bar(cR) },
      { label: t("w.naive"), data: rows.map(r => r.naive_last_week), ...bar(cN) },
    ];
    upsert("wape", "chart-wape", { type: "bar", data: { labels, datasets: ds }, options: baseOptions({ yPct: false, yMax: 0.7 }) });
    legend("legend-wape", ds.map(d => [d.label, d.backgroundColor]));
    table("table-wape", [t("t.level"), t("w.model"), t("w.roll"), t("w.naive")],
      rows.map((r, i) => [labels[i], r.model.toFixed(2), r.naive_roll_4.toFixed(2), r.naive_last_week.toFixed(2)]));
  }

  function renderHero() {
    const s = DATA.summary;
    document.getElementById("stat-lost").textContent = pct(s.size_aware.lost_units_vs_current, 0).replace("-", "−");
    document.getElementById("stat-m").textContent = `${pct(s.even_split.stockout_rate_M, 0)} → ${pct(s.size_aware.stockout_rate_M, 0)}`;
  }

  function renderAll() {
    if (!DATA || !window.Chart) return;
    Chart.defaults.font.family = "Inter, system-ui, sans-serif";
    renderHero(); renderFinding(); renderSimulator(); renderWape();
  }

  // ------------------------------------------------------------------ events
  document.getElementById("policy-picker").addEventListener("click", e => {
    const b = e.target.closest("button[data-policy]");
    if (!b) return;
    policy = b.dataset.policy;
    renderSimulator();
  });
  document.getElementById("policy-picker").addEventListener("keydown", e => {
    if (!["ArrowLeft", "ArrowRight"].includes(e.key)) return;
    const order = ["even_split", "size_curve", "size_aware"];
    const i = (order.indexOf(policy) + (e.key === "ArrowRight" ? 1 : order.length - 1)) % order.length;
    policy = order[i];
    renderSimulator();
    document.querySelector(`#policy-picker [data-policy="${policy}"]`).focus();
  });
  document.getElementById("lang-toggle").addEventListener("click", () => {
    lang = lang === "es" ? "en" : "es";
    store.set("lang", lang);
    applyLang(); renderAll();
  });
  document.getElementById("theme-toggle").addEventListener("click", () => {
    const next = isDark() ? "light" : "dark";
    store.set("theme", next);
    applyTheme(next); renderAll();
  });
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => { if (!document.documentElement.dataset.theme) renderAll(); });

  applyLang();
  fetch("data.json").then(r => r.json()).then(d => { DATA = d; renderAll(); })
    .catch(err => { console.error("No se pudo cargar data.json", err); });
})();
