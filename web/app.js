"use strict";
const $ = (s, r = document) => r.querySelector(s);
const el = (t, c, h) => { const e = document.createElement(t); if (c) e.className = c; if (h != null) e.innerHTML = h; return e; };

let STATE = { heroes: [], hero: null, item: null, locale: "pt", materialsCache: {} };

async function api(method, path, body) {
  const r = await fetch(path, {
    method, headers: { "Content-Type": "application/json" },
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
    $("#btnSave").disabled = false;
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
  renderHeroes(); $("#itemGrid").innerHTML = ""; $("#itemEmpty").style.display = "block";
  $("#enchBody").innerHTML = ""; $("#enchEmpty").style.display = "block"; $("#enchTitle").textContent = "Encantamentos";
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
  STATE.hero = idx; STATE.item = null; renderHeroes(); renderItems();
  $("#enchBody").innerHTML = ""; $("#enchEmpty").style.display = "block"; $("#enchTitle").textContent = "Encantamentos";
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

// ---------- bind ----------
$("#btnLoad").onclick = doLoad;
$("#btnSave").onclick = doSave;
$("#savePath").addEventListener("keydown", (e) => { if (e.key === "Enter") doLoad(); });
boot();
