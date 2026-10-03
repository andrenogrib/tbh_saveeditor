"use strict";
const $ = (s, r = document) => r.querySelector(s);
const el = (t, c, h) => { const e = document.createElement(t); if (c) e.className = c; if (h != null) e.innerHTML = h; return e; };

let STATE = { heroes: [], hero: null, item: null, locale: "pt", materialsCache: {}, tab: "equip", loaded: false,
  view: "hero", bag: [] };
// itens da tela atual: os equipados do heroi escolhido ou os da mochila/bau
const currentItems = () => STATE.view === "bag" ? STATE.bag : (STATE.hero != null ? STATE.heroes[STATE.hero].items : []);
const fmt = (n) => (+n).toLocaleString("pt-BR");

// token da sessao do servidor (vem na pagina); /api/* recusa sem ele
const TOKEN = (document.querySelector('meta[name="tbh-token"]') || {}).content || "";

async function api(method, path, body) {
  const r = await fetch(path, {
    method, headers: { "Content-Type": "application/json", "X-TBH-Token": TOKEN },
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.error || ("HTTP " + r.status));
  return data;
}
function toast(msg, kind = "") {
  const t = $("#toast"); t.textContent = msg; t.className = "toast show " + kind;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => (t.className = "toast"), kind === "warn" ? 6000 : 2600);
}
// sucesso, ou aviso quando o servidor devolve "warning"
function done(msg, res) {
  if (res && res.warning) toast(msg + " · ⚠ " + res.warning, "warn"); else toast(msg, "ok");
}
function iconEl(url, fallback) {
  if (url) { const i = el("img"); i.src = url; i.alt = ""; return i; }
  return el("div", "ico", fallback || "?");
}

// ---------- carregar / salvar ----------
async function boot() {
  const st = await api("GET", "/api/state");
  $("#savePath").value = st.path || "";
  $("#locale").value = st.locale || "pt";
  showState(st);
  setInterval(() => api("GET", "/api/state").then(showState).catch(() => {}), 10000);
}
// jogo aberto + caminho do save do jogo = Salvar bloqueado (o servidor tambem recusa)
function showState(st) {
  STATE.gameBlocks = !!(st.isGameSave && st.gameRunning !== false);
  const gs = $("#gameState");
  gs.classList.toggle("hidden", !STATE.gameBlocks);
  gs.textContent = st.gameRunning === null
    ? "Não deu para conferir se o jogo está aberto — o Salvar fica bloqueado no save do jogo."
    : "O Taskbar Hero está aberto: feche o jogo para salvar (ele regrava o save a cada 3 min e ao fechar).";
  const v = [st.dataVersion && "dados do jogo " + st.dataVersion, st.saveVersion && "save " + st.saveVersion];
  $("#versions").textContent = v.filter(Boolean).join(" · ") +
    (st.saveVersion && st.dataVersion && st.saveVersion !== st.dataVersion ? " ⚠ versões diferentes" : "");
  $("#btnSave").disabled = !STATE.loaded || STATE.gameBlocks;
}
async function doLoad() {
  try {
    const data = await api("POST", "/api/load", { path: $("#savePath").value.trim(), locale: $("#locale").value });
    applyHeroes(data);
    STATE.loaded = true;
    STATE.materialsCache = {};
    showState(await api("GET", "/api/state"));
    updateAutoBuildUI();
    if (STATE.tab === "player") refreshPlayer();
    toast("Save carregado (" + data.heroes.length + " heróis)", "ok");
  } catch (e) { toast("Erro: " + e.message, "err"); }
}
async function doSave() {
  try {
    // previa: o que muda em relacao ao arquivo em disco
    const d = await api("GET", "/api/diff");
    if (d.fileChanged) return toast("O arquivo mudou desde que foi carregado (o jogo salvou?): carregue de novo e refaça a edição", "err");
    if (!d.changes.length) return toast("Nada mudou em relação ao arquivo — nada para salvar", "");
    const lines = d.changes.slice(0, 25).map((c) => `• [${c.area}] ${c.text}`);
    if (d.changes.length > 25) lines.push(`… e mais ${d.changes.length - 25}`);
    if (!confirm(`Gravar ${d.changes.length} mudança(s) no save?\n\n${lines.join("\n")}`)) return;
    const r = await api("POST", "/api/save", {});
    const fix = r.fixed ? ` · ${r.fixed} item(ns) com contador corrigido` : "";
    done("Salvo!" + fix + " · ponto de volta " + r.restorePoint, r);
    if (STATE.tab === "backups") refreshBackups();
  } catch (e) { toast("Erro ao salvar: " + e.message, "err"); }
}
function applyHeroes(data) {
  STATE.heroes = data.heroes; STATE.locale = data.locale; STATE.playTimeMinutes = data.playTimeMinutes;
  STATE.hero = null; STATE.item = null; STATE.view = "hero"; STATE.bag = [];
  renderHeroes(); renderHeroEdit();
  $("#itemGrid").innerHTML = ""; $("#itemEmpty").style.display = "block";
  $("#enchBody").innerHTML = ""; $("#enchEmpty").style.display = "block"; $("#enchTitle").textContent = "Encantamentos";
}

// ---------- abas ----------
function switchTab(t) {
  STATE.tab = t;
  $("#mainEquip").classList.toggle("hidden", t !== "equip");
  $("#mainPlayer").classList.toggle("hidden", t !== "player");
  $("#mainBackups").classList.toggle("hidden", t !== "backups");
  $("#tabEquip").classList.toggle("active", t === "equip");
  $("#tabPlayer").classList.toggle("active", t === "player");
  $("#tabBackups").classList.toggle("active", t === "backups");
  if (t === "player") refreshPlayer();
  if (t === "backups") refreshBackups();
}

// ---------- heróis ----------
function renderHeroes() {
  const list = $("#heroList"); list.innerHTML = "";
  STATE.heroes.forEach((h, idx) => {
    const d = el("div", "hero" + (STATE.hero === idx ? " sel" : ""));
    d.append(el("span", null, (h.name || "Herói " + h.heroKey)), el("span", "lv", "Nv " + h.level));
    d.onclick = () => selectHero(idx);
    list.append(d);
  });
  if (!STATE.heroes.length) return;
  const b = el("div", "hero" + (STATE.view === "bag" ? " sel" : ""));
  b.append(el("span", null, "🎒 Mochila e baú"), el("span", "lv", STATE.bag.length ? String(STATE.bag.length) : ""));
  b.onclick = selectBag;
  list.append(b);
}
async function selectBag() {
  try { STATE.bag = (await api("GET", "/api/items")).items; } catch (e) { return toast("Erro: " + e.message, "err"); }
  STATE.view = "bag"; STATE.hero = null; STATE.item = null;
  renderHeroes(); renderHeroEdit(); renderItems();
  $("#enchBody").innerHTML = ""; $("#enchEmpty").style.display = "block"; $("#enchTitle").textContent = "Encantamentos";
  updateAutoBuildUI();
}
function selectHero(idx) {
  STATE.view = "hero"; STATE.hero = idx; STATE.item = null; renderHeroes(); renderHeroEdit(); renderItems();
  $("#enchBody").innerHTML = ""; $("#enchEmpty").style.display = "block"; $("#enchTitle").textContent = "Encantamentos";
  updateAutoBuildUI();
}

// ---------- auto-build (melhor build por classe) ----------
function updateAutoBuildUI() {
  const bar = $("#autoBuild"); if (!bar) return;
  bar.classList.toggle("hidden", !STATE.loaded);
  const noHero = STATE.hero == null;
  const bh = $("#abHero"); if (bh) bh.disabled = noHero;
  const bs = $("#abSkillHero"); if (bs) bs.disabled = noHero;
}
async function doSetSkills(scope) {
  const mode = $("#abMode").value;
  const body = { mode };
  if (scope === "hero") {
    if (STATE.hero == null) return toast("Selecione um herói primeiro.", "err");
    body.heroKey = STATE.heroes[STATE.hero].heroKey;
  }
  try {
    const res = await api("POST", "/api/set_skills", body);
    refreshHeroesPreserving(res);
    const who = scope === "hero" ? "este herói" : "todos os heróis";
    toast(`Skills (${mode}) em ${who}: ${res.changed} herói(s) atualizado(s) — lembre de Salvar`, "ok");
  } catch (e) { toast("Erro: " + e.message, "err"); }
}
function refreshHeroesPreserving(data) {
  const prevHeroKey = STATE.hero != null ? STATE.heroes[STATE.hero].heroKey : null;
  const prevItemUid = STATE.item ? STATE.item.uniqueId : null;
  STATE.heroes = data.heroes; STATE.locale = data.locale;
  if (STATE.view === "bag") { renderHeroes(); updateAutoBuildUI(); return; }  // auto-build nao mexe na mochila
  const idx = prevHeroKey != null ? STATE.heroes.findIndex((h) => h.heroKey === prevHeroKey) : -1;
  STATE.hero = idx >= 0 ? idx : null;
  STATE.item = null;
  renderHeroes(); renderHeroEdit();
  if (STATE.hero != null) {
    renderItems();
    if (prevItemUid) {
      const it = STATE.heroes[STATE.hero].items.find((x) => x.uniqueId === prevItemUid);
      if (it) { STATE.item = it; renderItems(); renderEnchants(); }
    }
  } else {
    $("#itemGrid").innerHTML = ""; $("#itemEmpty").style.display = "block";
    $("#enchBody").innerHTML = ""; $("#enchEmpty").style.display = "block"; $("#enchTitle").textContent = "Encantamentos";
  }
  updateAutoBuildUI();
}
async function doAutoBuild(scope) {
  const mode = $("#abMode").value, overwrite = $("#abOverwrite").checked;
  const body = { mode, overwrite };
  if (scope === "hero") {
    if (STATE.hero == null) return toast("Selecione um herói primeiro.", "err");
    body.heroKey = STATE.heroes[STATE.hero].heroKey;
  }
  try {
    const res = await api("POST", "/api/auto_build", body);
    refreshHeroesPreserving(res);
    const who = scope === "hero" ? "este herói" : "todos os heróis";
    toast(`Build ${mode} em ${who}: ${res.items} item(ns), ${res.slots} slot(s) alterado(s) — lembre de Salvar`, "ok");
  } catch (e) { toast("Erro: " + e.message, "err"); }
}

// ---------- editor do herói (nível / exp / skill points) ----------
function renderHeroEdit() {
  const box = $("#heroEdit");
  const h = STATE.hero != null ? STATE.heroes[STATE.hero] : null;
  box.innerHTML = "";
  box.classList.toggle("hidden", !h);
  if (!h) return;
  box.append(el("div", "he-title", `<b>${h.name}</b> · pontos gastos nas skills: <b>${h.allocatedPoints}</b>`));
  if (h.skills && h.skills.length) {
    const active = h.skills.filter((s) => !s.base);
    box.append(el("div", "he-skills", "Skills ativas: " +
      (active.length ? active.map((s) => `<b>${s.name}</b>`).join(" · ") : "<i>nenhuma</i>")));
  }
  const mkRow = (label, value, opts) => {
    const r = el("div", "row");
    r.append(el("label", null, label));
    const i = el("input"); i.type = "number";
    Object.assign(i, opts || {});
    i.value = value;
    r.append(i); box.append(r);
    return i;
  };
  if (h.build && h.build.length) {
    const det = el("details", "build");
    det.append(el("summary", null, `Resumo da build (${h.build.reduce((n, b) => n + b.slots, 0)} slots encantados)`));
    h.build.forEach((b) => det.append(el("div", "row",
      `<span>${b.stat} <small>${b.modType}</small></span><span>${fmt(b.total)} <small>· ${b.slots} slot(s)</small></span>`)));
    det.append(el("div", "hint", "Soma dos valores dos encantamentos dos itens equipados, na mesma unidade dos slots."));
    box.append(det);
  }
  if (!h.unlocked) {
    box.append(el("div", "readonly", "Herói bloqueado no jogo — não editável."));
    return;
  }
  const inLv = mkRow("Nível", h.level, { min: 1, max: h.levelMax });
  const inAp = mkRow("Skill points", h.abilityPoint, { min: 0, max: h.apCap, title: "pontos de habilidade sobrando (não gastos)" });
  const inXp = mkRow("EXP", h.exp, { min: 0, step: "any" });
  const hint = el("div", "hint"); box.append(hint);
  const syncXp = () => {  // EXP so abaixo do nivel maximo; ao mudar o nivel, recomeca em 0
    const atMax = +inLv.value >= h.levelMax;
    inXp.disabled = atMax;
    if (+inLv.value !== h.level) inXp.value = atMax ? h.exp : 0;
    hint.textContent = `nível 1–${h.levelMax}` +
      (atMax ? " · no nível máximo a EXP é só exibição" : (h.expCap && +inLv.value === h.level ? ` · EXP abaixo de ${fmt(h.expCap)}` : "")) +
      ` · pontos livres até ${h.apCap} (nível − ${h.allocatedPoints} já alocados)` +
      (STATE.playTimeMinutes < 3000 && +inLv.value >= 50 ? " · ⚠ nível ≥ 50/80 com pouco tempo de jogo gera relatório ao servidor" : "");
  };
  inLv.oninput = syncXp; syncXp();
  const apply = el("button", "primary", "Aplicar");
  apply.onclick = async () => {
    try {
      const body = { heroKey: h.heroKey, level: +inLv.value, abilityPoint: +inAp.value };
      if (!inXp.disabled) body.exp = +inXp.value;
      const r = await api("POST", "/api/set_hero", body);
      Object.assign(h, r.hero);
      renderHeroes(); renderHeroEdit();
      done("Herói atualizado — lembre de Salvar no jogo", r);
    } catch (e) { toast("Erro: " + e.message, "err"); }
  };
  const act = el("div", "actions"); act.append(apply); box.append(act);
}

// ---------- itens ----------
function renderItems() {
  const grid = $("#itemGrid"); grid.innerHTML = "";
  const items = currentItems();
  $("#itemEmpty").style.display = items.length ? "none" : "block";
  items.forEach((it) => {
    const c = el("div", "card" + (STATE.item && STATE.item.uniqueId === it.uniqueId ? " sel" : ""));
    c.append(iconEl(it.icon, it.group || "?"));
    const sub = it.where ? [it.where, it.grade].filter(Boolean).join(" · ") : (it.group || "");
    c.append(el("div", "nm", it.name), el("div", "grp", sub));
    c.onclick = () => selectItem(it);
    grid.append(c);
  });
}
function selectItem(it) {
  STATE.item = it; renderItems(); renderEnchants();
}

// ---------- encantamentos ----------
function renderEnchants() {
  const it = STATE.item, body = $("#enchBody");
  $("#enchEmpty").style.display = "none";
  $("#enchTitle").textContent = it.name + "  ·  " + (it.group || "") + (it.grade ? "  ·  " + it.grade : "");
  body.innerHTML = "";
  if (it.readOnly) body.append(el("div", "readonly", "Somente leitura: " + it.readOnly));
  it.enchants.forEach((e) => body.append(slotCard(e, !!it.readOnly)));
}
function slotCard(e, readOnly) {
  const s = el("div", "slot" + (e.allowed ? "" : " locked"));
  const head = el("div", "head");
  head.append(el("span", "tag " + e.type, e.label));
  const cur = el("div", "cur");
  if (!e.allowed) {
    cur.innerHTML = `<i>indisponível — a grade do item não tem este slot</i>`;
  } else if (e.filled) {
    cur.innerHTML = `<b>${e.materialName}</b> — <span class="stat">${e.stat}</span> · T${e.tier} · <b>${e.value}</b>`;
    if (e.errors && e.errors.length) cur.append(el("div", "legacy",
      "⚠ fora das tabelas da versão atual do jogo (encantamento legado; o editor não altera sozinho): " +
      e.errors.join("; ")));
  } else cur.innerHTML = `<i>vazio</i>`;
  head.append(cur);
  s.append(head);

  if (e.allowed && !readOnly) {
    const actions = el("div", "actions");
    const edit = el("button", "", e.filled ? "Editar" : "Adicionar");
    edit.onclick = () => openEditor(s, e);
    actions.append(edit);
    if (e.filled) {
      const clr = el("button", "linkbtn", "limpar");
      clr.onclick = () => setEnchant({ uniqueId: STATE.item.uniqueId, slot: e.slot, clear: true });
      actions.append(clr);
    }
    s.append(actions);
  }
  return s;
}

// editor inline de um slot
async function openEditor(slotEl, e) {
  // remove editor anterior
  slotEl.querySelectorAll(".editor").forEach((x) => x.remove());
  const box = el("div", "editor");
  // 1) material
  const mats = await loadMaterials(e.slot);
  const rowMat = el("div", "row"); rowMat.append(el("label", null, "Material"));
  const selMat = el("select");
  selMat.append(new Option("— escolher —", ""));
  mats.forEach((m) => selMat.append(new Option(m.name, m.key)));
  if (e.filled) selMat.value = e.materialKey;
  rowMat.append(selMat); box.append(rowMat);

  // containers dinamicos
  const rowStat = el("div", "row", `<label>Stat</label>`); const selStat = el("select"); rowStat.append(selStat);
  const rowTier = el("div", "row", `<label>Tier</label>`); const selTier = el("select"); rowTier.append(selTier);
  const rowVal = el("div", "row"); rowVal.append(el("label", null, "Valor"));
  const valWrap = el("div", "valbox");
  const rng = el("input"); rng.type = "range"; const num = el("input", "num"); num.type = "number";
  const maxBtn = el("button", "", "Máx");
  valWrap.append(rng, num, maxBtn); rowVal.append(valWrap);
  const hint = el("div", "hint");
  box.append(rowStat, rowTier, rowVal, hint);

  let options = [];
  async function onMaterial() {
    selStat.innerHTML = ""; selTier.innerHTML = ""; hint.textContent = "";
    if (!selMat.value) { options = []; return; }
    const data = await api("GET", `/api/options?material=${selMat.value}&item=${STATE.item.itemKey}`);
    options = data.options;
    if (!options.length) { hint.textContent = "Esse material não oferece stats para este tipo de equipamento."; return; }
    options.forEach((o, i) => selStat.append(new Option(`${o.statName} (${o.gearGroup})`, i)));
    if (e.filled) { const k = options.findIndex((o) => o.statModKey === e.statModKey); if (k >= 0) selStat.value = k; }
    onStat();
  }
  function onStat() {
    selTier.innerHTML = "";
    const o = options[selStat.value]; if (!o) return;
    o.tiers.forEach((t) => selTier.append(new Option("Tier " + t.tier, t.tier)));
    if (e.filled) selTier.value = e.tier;
    onTier();
  }
  function onTier() {
    const o = options[selStat.value]; if (!o) return;
    const t = o.tiers.find((t) => String(t.tier) === String(selTier.value)) || o.tiers[0];
    rng.min = num.min = t.min; rng.max = num.max = t.max; rng.step = num.step = t.interval || 1;
    let v = e.filled && e.value >= t.min && e.value <= t.max ? e.value : t.max;
    rng.value = num.value = v;
    hint.textContent = `${o.statName} · range ${t.min}–${t.max} (passo ${t.interval})`;
  }
  selMat.onchange = onMaterial;
  selStat.onchange = onStat;
  selTier.onchange = onTier;
  rng.oninput = () => (num.value = rng.value);
  num.oninput = () => (rng.value = num.value);
  maxBtn.onclick = () => { num.value = rng.value = rng.max; };

  const apply = el("button", "primary", "Aplicar");
  apply.onclick = () => {
    const o = options[selStat.value];
    if (!o) return toast("Escolha material e stat.", "err");
    setEnchant({
      uniqueId: STATE.item.uniqueId, slot: e.slot, materialKey: +selMat.value,
      statModKey: o.statModKey, tier: +selTier.value, value: +num.value,
    });
  };
  const cancel = el("button", "linkbtn", "cancelar");
  cancel.onclick = () => box.remove();
  const act = el("div", "actions"); act.append(apply, cancel); box.append(act);

  slotEl.append(box);
  if (e.filled) await onMaterial();
}

async function loadMaterials(slot) {
  if (STATE.materialsCache[slot]) return STATE.materialsCache[slot];
  const data = await api("GET", "/api/materials?slot=" + slot);
  STATE.materialsCache[slot] = data.materials;
  return data.materials;
}

async function setEnchant(payload) {
  try {
    const item = await api("POST", "/api/set_enchant", payload);
    // atualiza o item no estado e re-renderiza
    const list = currentItems();
    const idx = list.findIndex((x) => x.uniqueId === item.uniqueId);
    if (idx >= 0) list[idx] = Object.assign(item, { where: list[idx].where });
    STATE.item = item;
    renderItems(); renderEnchants();
    toast(payload.clear ? "Slot limpo" : "Encantamento aplicado — lembre de Salvar", "ok");
  } catch (e) { toast("Erro: " + e.message, "err"); }
}

// ---------- aba Jogador (moedas / cubo / pets / runas) ----------
async function refreshPlayer() {
  const panes = document.querySelectorAll("#mainPlayer .pane");
  try {
    const d = await api("GET", "/api/player");
    $("#playerEmpty").classList.add("hidden");
    panes.forEach((p) => p.classList.remove("hidden"));
    renderPlayer(d);
    renderProgress(await api("GET", "/api/progress"));
  } catch (e) {
    $("#playerEmpty").classList.remove("hidden");
    panes.forEach((p) => p.classList.add("hidden"));
  }
}

function renderPlayer(d) {
  // --- recursos (moedas + cubo) ---
  const cl = $("#curList"); cl.innerHTML = "";
  d.currencies.forEach((c) => {
    const kv = el("div", "kv");
    kv.append(el("span", "nm", `<b>${c.name}</b><br><small>${fmt(c.quantity)}</small>`));
    const i = el("input"); i.type = "number"; i.min = 0; i.value = c.quantity;
    const b = el("button", "", "Aplicar");
    b.onclick = async () => {
      try {
        const r = await api("POST", "/api/set_currency", { key: c.key, quantity: +i.value });
        done(c.name + " atualizado — lembre de Salvar no jogo", r);
        refreshPlayer();
      } catch (e) { toast("Erro: " + e.message, "err"); }
    };
    kv.append(i, b); cl.append(kv);
  });
  cl.append(el("div", "hint", "Ouro acima de 100 milhões gera aviso: o valor vai no snapshot ao servidor."));
  if (d.cube && d.cube.level != null) {
    const c = d.cube;
    const kv = el("div", "kv");
    kv.append(el("span", "nm", `<b>Nível do Cubo</b><br><small>1–${c.levelMax}</small>`));
    const i = el("input"); i.type = "number"; i.min = 1; i.max = c.levelMax; i.value = c.level;
    const x = el("input"); x.type = "number"; x.min = 0; x.step = "any"; x.value = c.exp; x.title = "Exp do cubo";
    const sync = () => {
      const atMax = +i.value >= c.levelMax;
      x.disabled = atMax;
      if (+i.value !== c.level) x.value = atMax ? c.exp : 0;
    };
    i.oninput = sync; sync();
    const b = el("button", "", "Aplicar");
    b.onclick = async () => {
      try {
        const body = { level: +i.value };
        if (!x.disabled) body.exp = +x.value;
        const r = await api("POST", "/api/set_cube", body);
        done("Cubo atualizado — lembre de Salvar no jogo", r);
        refreshPlayer();
      } catch (e) { toast("Erro: " + e.message, "err"); }
    };
    kv.append(i, x, b); cl.append(kv);
    cl.append(el("div", "hint", (c.expCap ? `Exp abaixo de ${fmt(c.expCap)} neste nível; ` : "No nível máximo o Exp é fixo; ") +
      "o nível do cubo vai em cube_level da Steam e o nível 10 libera o Trade Ship — não use o editor para liberar o Market."));
  }

  // --- pets ---
  const pg = $("#petGrid"); pg.innerHTML = "";
  d.pets.forEach((pt) => {
    const c = el("div", "card pet");
    c.append(el("div", "nm", pt.name + (String(pt.key) === String(d.arrangedPetKey) ? " ⭐" : "")));
    c.append(el("div", "state " + (pt.unlocked ? "on" : "off"), pt.unlocked ? "desbloqueado" : "bloqueado"));
    if (pt.dlc) { c.append(el("div", "hint", "DLC — gerenciado pela Steam")); pg.append(c); return; }
    if (pt.need) c.append(el("div", "hint", `abates: ${fmt(pt.kills)} / ${fmt(pt.need)}`));
    const b = el("button", "", pt.unlocked ? "Bloquear" : "Desbloquear");
    b.onclick = async () => {
      try {
        const r = await api("POST", "/api/set_pet", { petKey: pt.key, unlock: !pt.unlocked });
        done("Pet atualizado — lembre de Salvar no jogo", r);
        refreshPlayer();
      } catch (e) { toast("Erro: " + e.message, "err"); }
    };
    c.append(b); pg.append(c);
  });
  $("#btnAllPets").onclick = async () => {
    try {
      const locked = d.pets.filter((x) => !x.unlocked && !x.dlc);
      if (!locked.length) return toast("Todos os pets já estão desbloqueados", "ok");
      for (const pt of locked) await api("POST", "/api/set_pet", { petKey: pt.key, unlock: true });
      toast(locked.length + " pet(s) desbloqueado(s) — lembre de Salvar no jogo", "ok");
      refreshPlayer();
    } catch (e) { toast("Erro: " + e.message, "err"); }
  };

  // --- runas ---
  const rb = $("#runeBox"); rb.innerHTML = "";
  const r = d.runes;
  rb.append(el("div", null,
    `<b>${r.maxed}</b> de <b>${r.total}</b> runas no nível máximo` +
    (r.below ? ` · <b>${r.below}</b> comuns podem subir` : "") +
    (r.chest ? ` · <b>${r.chest}</b> de baú abaixo do máximo` : "") +
    (r.unknown ? ` · <small>${r.unknown} sem dados na tabela</small>` : "")));
  const chk = el("label", "ab-check");
  const inc = el("input"); inc.type = "checkbox"; inc.disabled = !r.chest;
  chk.append(inc, document.createTextNode(" incluir as runas de baú (risco alto)"));
  const btn = el("button", "primary", "Maximizar runas");
  btn.onclick = async () => {
    const includeChest = inc.checked;
    if (includeChest && !confirm(
      `Subir também as ${r.chest} runa(s) de baú?\n\n` +
      "• Elas aumentam chance de drop, capacidade e auto-abertura de baús — baús que o servidor do jogo " +
      "processa e cujos itens podem ir para o Steam Market.\n" +
      `• No jogo, completar essas runas custa ${fmt(r.chestGoldCost)} de ouro; o editor não desconta ouro.\n` +
      "• O snapshot enviado ao servidor na próxima abertura mostra as runas no máximo, e o jogo tem " +
      "relatório próprio de taxa/volume de baús que não depende do tempo de jogo.\n\n" +
      "Risco para a conta: alto. Continuar?")) return;
    try {
      const res = await api("POST", "/api/max_runes", { includeChest });
      const extra = (res.skippedChest.length ? ` · ${res.skippedChest.length} de baú ficaram de fora` : "") +
        (res.blockedByTree.length ? ` · ${res.blockedByTree.length} esperam o nó pai` : "");
      if (res.changed) done(`${res.changed} runa(s) elevadas ao máximo${extra} — lembre de Salvar`, res);
      else toast(`Nenhuma runa mudou: ${res.runes.maxed} já no máximo${extra}` +
        (res.runes.unknown ? `, ${res.runes.unknown} sem dados` : ""), "");
      refreshPlayer();
    } catch (e) { toast("Erro: " + e.message, "err"); }
  };
  const act = el("div", "actions"); act.append(btn, chk); rb.append(act);
  rb.append(el("div", "hint", "Sobem até o MaxLevel da tabela do jogo, respeitando a árvore (o nó pai antes " +
    "do filho). Por padrão as runas de baú (chance de drop, capacidade, auto-abertura, abrir todos) ficam " +
    "de fora; marque a opção para incluí-las."));
}

// ---------- progresso (somente leitura; o servidor do jogo manda nos estágios) ----------
function renderProgress(p) {
  const box = $("#progressBox"); box.innerHTML = "";
  const st = (s) => (s && s.name ? `${s.name} <small>(${s.difficulty} ${s.act}-${s.no}, ${s.type})</small>` : (s && s.key) || "—");
  const row = (k, v) => { const r = el("div", "row"); r.append(el("span", null, k), el("span", null, v)); box.append(r); };
  row("Estágio atual", st(p.current) + (p.wave != null ? ` · onda ${p.wave}` : ""));
  row("Desbloqueado até", st(p.unlockedUpTo));
  row("Último estágio vencido", st(p.lastCleared));
  row("Intensidade da Peste (última escolhida)",
    p.plague.filter((x) => x.intensity).map((x) => `${x.difficulty} ${x.intensity}`).join(" · ") || "—");
  row("Tempo de jogo", `${fmt(p.playTimeHours)} h`);
  box.append(el("div", "hint", "O servidor do jogo é a autoridade sobre o progresso e sobrescreve o que estiver no save; por isso não há edição aqui."));
}

// ---------- pontos de volta ----------
async function refreshBackups() {
  const box = $("#backupList"); box.innerHTML = "";
  try {
    const d = await api("GET", "/api/backups");
    $("#backupDir").textContent = `Pasta: ${d.dir} · guarda os ${d.keep} mais novos`;
    if (!d.backups.length) { box.append(el("div", "empty", "Nenhum ponto de volta ainda: o primeiro sai no próximo Salvar.")); return; }
    d.backups.forEach((b) => {
      const kv = el("div", "kv");
      kv.append(el("span", "nm", `<b>${b.time}</b> · ${b.reason}<br><small>${b.source} · ${fmt(b.size)} bytes</small>`));
      const btn = el("button", "", "Restaurar");
      btn.onclick = () => doRestore(b);
      kv.append(btn); box.append(kv);
    });
  } catch (e) { box.append(el("div", "err", "Erro: " + e.message)); }
}
async function doRestore(b) {
  if (!confirm(`Restaurar o save de ${b.time}?\n\n` +
    "• Só com o jogo FECHADO.\n" +
    "• O arquivo volta inteiro para aquele momento: o que o jogo gravou depois some do arquivo " +
    "(o servidor repõe o que ele controla, como itens e progresso).\n" +
    "• Edições não salvas no editor são descartadas.\n" +
    "• O arquivo atual vira outro ponto de volta: dá para desfazer.")) return;
  try {
    const r = await api("POST", "/api/restore", { id: b.id });
    toast("Restaurado · o arquivo anterior virou o ponto de volta " + (r.undo || "—"), "ok");
    const st = await api("GET", "/api/state");
    if (st.loaded && st.path === r.path) applyHeroes(await api("GET", "/api/heroes"));
    showState(st);
    refreshBackups();
  } catch (e) { toast("Erro: " + e.message, "err"); }
}

// ---------- bind ----------
$("#btnLoad").onclick = doLoad;
$("#btnSave").onclick = doSave;
$("#abHero").onclick = () => doAutoBuild("hero");
$("#abAll").onclick = () => doAutoBuild("all");
$("#abSkillHero").onclick = () => doSetSkills("hero");
$("#abSkillAll").onclick = () => doSetSkills("all");
$("#tabEquip").onclick = () => switchTab("equip");
$("#tabPlayer").onclick = () => switchTab("player");
$("#tabBackups").onclick = () => switchTab("backups");
$("#savePath").addEventListener("keydown", (e) => { if (e.key === "Enter") doLoad(); });
boot();
