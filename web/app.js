"use strict";
const $ = (s, r = document) => r.querySelector(s);
const el = (t, c, h) => { const e = document.createElement(t); if (c) e.className = c; if (h != null) e.innerHTML = h; return e; };

let STATE = { heroes: [], hero: null, item: null, locale: "pt", materialsCache: {}, tab: "equip", loaded: false };
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
  setTimeout(() => (t.className = "toast"), 2600);
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
}
async function doLoad() {
  try {
    const data = await api("POST", "/api/load", { path: $("#savePath").value.trim(), locale: $("#locale").value });
    applyHeroes(data);
    STATE.loaded = true;
    STATE.materialsCache = {};
    $("#btnSave").disabled = false;
    updateAutoBuildUI();
    if (STATE.tab === "player") refreshPlayer();
    toast("Save carregado (" + data.heroes.length + " heróis)", "ok");
  } catch (e) { toast("Erro: " + e.message, "err"); }
}
async function doSave() {
  try {
    const r = await api("POST", "/api/save", {});
    const fix = r.fixed ? ` · ${r.fixed} item(ns) com contador corrigido` : "";
    toast("Salvo!" + fix + " · backup .bak criado", "ok");
  } catch (e) { toast("Erro ao salvar: " + e.message, "err"); }
}
function applyHeroes(data) {
  STATE.heroes = data.heroes; STATE.locale = data.locale;
  STATE.hero = null; STATE.item = null;
  renderHeroes(); renderHeroEdit();
  $("#itemGrid").innerHTML = ""; $("#itemEmpty").style.display = "block";
  $("#enchBody").innerHTML = ""; $("#enchEmpty").style.display = "block"; $("#enchTitle").textContent = "Encantamentos";
}

// ---------- abas ----------
function switchTab(t) {
  STATE.tab = t;
  $("#mainEquip").classList.toggle("hidden", t !== "equip");
  $("#mainPlayer").classList.toggle("hidden", t !== "player");
  $("#tabEquip").classList.toggle("active", t === "equip");
  $("#tabPlayer").classList.toggle("active", t === "player");
  if (t === "player") refreshPlayer();
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
}
function selectHero(idx) {
  STATE.hero = idx; STATE.item = null; renderHeroes(); renderHeroEdit(); renderItems();
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
  const inLv = mkRow("Nível", h.level, { min: 1, max: 1000 });
  const inAp = mkRow("Skill points", h.abilityPoint, { min: 0, title: "pontos de habilidade sobrando (não gastos)" });
  const inXp = mkRow("EXP", h.exp, { min: 0, step: "any" });
  box.append(el("div", "hint", "máx. de nível conhecido no jogo: 101"));
  const apply = el("button", "primary", "Aplicar");
  apply.onclick = async () => {
    try {
      const r = await api("POST", "/api/set_hero", {
        heroKey: h.heroKey, level: +inLv.value, abilityPoint: +inAp.value, exp: +inXp.value,
      });
      Object.assign(h, r.hero);
      renderHeroes(); renderHeroEdit();
      toast("Herói atualizado — lembre de Salvar no jogo", "ok");
    } catch (e) { toast("Erro: " + e.message, "err"); }
  };
  const act = el("div", "actions"); act.append(apply); box.append(act);
}

// ---------- itens ----------
function renderItems() {
  const grid = $("#itemGrid"); grid.innerHTML = "";
  const h = STATE.heroes[STATE.hero];
  $("#itemEmpty").style.display = h.items.length ? "none" : "block";
  h.items.forEach((it) => {
    const c = el("div", "card" + (STATE.item && STATE.item.uniqueId === it.uniqueId ? " sel" : ""));
    c.append(iconEl(it.icon, it.group || "?"));
    c.append(el("div", "nm", it.name), el("div", "grp", it.group || ""));
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
  it.enchants.forEach((e) => body.append(slotCard(e)));
}
function slotCard(e) {
  const s = el("div", "slot" + (e.allowed ? "" : " locked"));
  const head = el("div", "head");
  head.append(el("span", "tag " + e.type, e.label));
  const cur = el("div", "cur");
  if (!e.allowed) {
    cur.innerHTML = `<i>indisponível — a grade do item não tem este slot</i>`;
  } else if (e.filled) {
    cur.innerHTML = `<b>${e.materialName}</b> — <span class="stat">${e.stat}</span> · T${e.tier} · <b>${e.value}</b>`;
    if (e.errors && e.errors.length) cur.append(el("div", "err", "⚠ " + e.errors.join("; ")));
  } else cur.innerHTML = `<i>vazio</i>`;
  head.append(cur);
  s.append(head);

  if (e.allowed) {
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
    const h = STATE.heroes[STATE.hero];
    const idx = h.items.findIndex((x) => x.uniqueId === item.uniqueId);
    if (idx >= 0) h.items[idx] = item;
    STATE.item = item;
    renderItems(); renderEnchants();
    toast(payload.clear ? "Slot limpo" : "Encantamento aplicado", "ok");
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
        await api("POST", "/api/set_currency", { key: c.key, quantity: +i.value });
        toast(c.name + " atualizado — lembre de Salvar no jogo", "ok");
        refreshPlayer();
      } catch (e) { toast("Erro: " + e.message, "err"); }
    };
    kv.append(i, b); cl.append(kv);
  });
  if (d.cube && d.cube.level != null) {
    const kv = el("div", "kv");
    kv.append(el("span", "nm", `<b>Nível do Cubo</b><br><small>exp ${fmt(d.cube.exp || 0)}</small>`));
    const i = el("input"); i.type = "number"; i.min = 1; i.value = d.cube.level;
    const b = el("button", "", "Aplicar");
    b.onclick = async () => {
      try {
        await api("POST", "/api/set_cube", { level: +i.value });
        toast("Cubo atualizado — lembre de Salvar no jogo", "ok");
        refreshPlayer();
      } catch (e) { toast("Erro: " + e.message, "err"); }
    };
    kv.append(i, b); cl.append(kv);
  }

  // --- pets ---
  const pg = $("#petGrid"); pg.innerHTML = "";
  d.pets.forEach((pt) => {
    const c = el("div", "card pet");
    c.append(el("div", "nm", pt.name + (String(pt.key) === String(d.arrangedPetKey) ? " ⭐" : "")));
    c.append(el("div", "state " + (pt.unlocked ? "on" : "off"), pt.unlocked ? "desbloqueado" : "bloqueado"));
    const b = el("button", "", pt.unlocked ? "Bloquear" : "Desbloquear");
    b.onclick = async () => {
      try {
        await api("POST", "/api/set_pet", { petKey: pt.key, unlock: !pt.unlocked });
        toast("Pet atualizado — lembre de Salvar no jogo", "ok");
        refreshPlayer();
      } catch (e) { toast("Erro: " + e.message, "err"); }
    };
    c.append(b); pg.append(c);
  });
  $("#btnAllPets").onclick = async () => {
    try {
      const locked = d.pets.filter((x) => !x.unlocked);
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
    (r.below ? ` · <b>${r.below}</b> podem subir` : "") +
    (r.chest ? ` · <small>${r.chest} de baú ficam de fora</small>` : "") +
    (r.unknown ? ` · <small>${r.unknown} sem dados na tabela</small>` : "")));
  const btn = el("button", "primary", "Maximizar runas");
  btn.onclick = async () => {
    try {
      const res = await api("POST", "/api/max_runes", {});
      const skipped = res.skippedChest.length ? ` · ${res.skippedChest.length} de baú ficaram de fora` : "";
      if (res.changed) toast(`${res.changed} runa(s) elevadas ao máximo${skipped} — lembre de Salvar`, "ok");
      else toast(`Nenhuma runa mudou: ${res.runes.maxed} já no máximo${skipped}` +
        (res.runes.unknown ? `, ${res.runes.unknown} sem dados` : ""), "");
      refreshPlayer();
    } catch (e) { toast("Erro: " + e.message, "err"); }
  };
  const act = el("div", "actions"); act.append(btn); rb.append(act);
  rb.append(el("div", "hint", "Sobem até o MaxLevel da tabela do jogo. As runas de baú (chance de drop, " +
    "capacidade, auto-abertura, abrir todos) ficam de fora: mexem em baús que o servidor processa e " +
    "cujos itens vão para o Steam Market."));
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
$("#savePath").addEventListener("keydown", (e) => { if (e.key === "Enter") doLoad(); });
boot();
