"""
TBH Save Editor - servidor web local (stdlib, zero dependencias).
Edita os encantamentos (decoration/engraving/inscription) dos itens equipados dos herois,
com validacao pelas tabelas do jogo, e recalcula o SystemInfo ao salvar.

Uso:  python server.py        (abre http://127.0.0.1:8765 no navegador)
"""
import hashlib
import hmac
import http.server
import json
import os
import secrets
import socketserver
import struct
import sys
import threading
import urllib.parse
import webbrowser

from core import es3, gamedata, autobuild

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import tbh_paths  # noqa: E402  (jogo aberto e pastas do jogo; so stdlib)
DATA = os.path.join(ROOT, "data")
WEB = os.path.join(ROOT, "web")
ICONS = os.path.join(DATA, "icons")
PORT = 8765

GD = gamedata.GameData(DATA)
# a pagina servida recebe este token; /api/* exige o token e Host/Origin locais (P2-9)
TOKEN = secrets.token_urlsafe(24)
GOLD_WARN = 100 * 10 ** 6  # ouro acima disso: aviso (vai no snapshot; Gold_Massive em conta nova)
ALLOWED_HOSTS = ("127.0.0.1:%d" % PORT, "localhost:%d" % PORT)
SLOT_LABELS = ["Decoration", "Decoration", "Engraving", "Engraving", "Inscription", "Inscription"]


class State:
    save = None
    path = None
    locale = "pt"
    stamp = None  # (tamanho, sha256) do arquivo no load: o Salvar recusa se ele mudou


def file_stamp(path):
    with open(path, "rb") as fh:
        data = fh.read()
    return len(data), hashlib.sha256(data).hexdigest()


def pending_summary():
    """Transacoes que o jogo ainda vai concluir com o servidor -> (nomes, UniqueIds citados).
    O editor nao edita item citado (P2-2)."""
    p = State.save.player
    names, uids = [], set()
    for x in p.get("pendingEnchantList") or []:
        uids.update(str(x.get(k)) for k in ("GearUniqueId", "MaterialUniqueId"))
    for x in p.get("pendingItemRestorationList") or []:
        uids.add(str(x.get("UniqueId")))
    uids.update(str(x) for x in p.get("AlchemyPendingIdList") or [])
    ex = p.get("pendingExchange")
    ex_open = isinstance(ex, dict) and (ex.get("resultItem") not in (None, -1, 0) or bool(ex.get("items")))
    if ex_open:
        uids.update(str(x) for x in ex.get("items") or [])
    for k in ("pendingEnchantList", "pendingItemRestorationList", "AlchemyPendingIdList"):
        if p.get(k):
            names.append(k)
    if ex_open:
        names.append("pendingExchange")
    return names, uids


def item_lock(it):
    """None se o item pode ser encantado pelo editor; senao o motivo."""
    why = GD.enchantable(it["ItemKey"])
    if why:
        return why
    if str(it.get("UniqueId")) in pending_summary()[1]:
        return "item com transação pendente no servidor — abra o jogo para concluir antes de editar"
    return None


def default_save_path():
    up = os.environ.get("USERPROFILE", "")
    p = os.path.join(up, "AppData", "LocalLow", "TesseractStudio", "TaskbarHero", "SaveFile_Live.es3")
    return p if os.path.exists(p) else ""


# ---------------- serializacao para a UI ----------------
def item_payload(it):
    ikey = it["ItemKey"]
    eds = it.get("EnchantData") or []
    enchants = []
    # mostra tambem os slots da grade que o EnchantData ainda nao tem (o jogo completa)
    for i in range(min(len(SLOT_LABELS), max(len(eds), GD.enchant_len(ikey)))):
        ed = eds[i] if i < len(eds) else {}
        filled = gamedata.is_filled(ed)
        e = {"slot": i, "type": GD.slot_material_type(i), "label": SLOT_LABELS[i],
             "filled": filled, "allowed": GD.slot_allowed(ikey, i)}
        if filled:
            si = GD.statmod.get((str(ed.get("StatModKey")), str(ed.get("Tier"))))
            e.update({
                "materialKey": ed["MaterialKey"],
                "materialName": GD.name(ed["MaterialKey"], State.locale),
                "materialIcon": "/icons/%s" % ed["MaterialKey"] if GD.has_icon(ed["MaterialKey"]) else None,
                "statModKey": ed.get("StatModKey"),
                "tier": ed.get("Tier"),
                "value": ed.get("Value"),
                "stat": GD.pretty_stat(si["STATTYPE"]) if si else "?",
                "errors": GD.validate_enchant(i, ikey, ed),
            })
        enchants.append(e)
    return {
        "uniqueId": str(it["UniqueId"]),
        "itemKey": ikey,
        "name": GD.name(ikey, State.locale),
        "icon": "/icons/%s" % ikey if GD.has_icon(ikey) else None,
        "group": GD.gear_group(ikey),
        "grade": GD.grade_name(ikey),
        "maxSlots": GD.max_slots(ikey),
        "enchantCount": it.get("EnchantCount"),
        "enchants": enchants,
        "readOnly": item_lock(it),
    }


def heroes_payload():
    sf = State.save
    items_by_uid = {str(it["UniqueId"]): it for it in sf.player.get("itemSaveDatas", [])}
    out = []
    for h in sf.player.get("heroSaveDatas", []):
        slots = []
        for uid in h.get("equippedItemIds", []):
            if str(uid) == "0" or str(uid) not in items_by_uid:
                continue
            slots.append(item_payload(items_by_uid[str(uid)]))
        base = GD.hero_base_skill(h.get("heroKey"))
        skills = [{"key": k, "name": GD.skill_name(k, State.locale), "base": k == base}
                  for k in h.get("equippedSKillKey", []) if int(k) > 0]
        d = hero_brief(h)
        d.update({"name": GD.hero_name(h.get("heroKey"), State.locale),
                  "klass": GD.hero_class(h.get("heroKey")), "items": slots, "skills": skills})
        out.append(d)
    return {"heroes": out, "locale": State.locale, "path": State.path,
            "playTimeMinutes": round(float(sf.account.get("playTime") or 0) / 60)}


def options_payload(material_key, item_key):
    gg = GD.gear_group(item_key)
    opts = GD.stat_options(material_key, gg)
    return {"materialKey": int(material_key), "gearGroup": gg, "options": opts}


def learned_skills(h):
    """Ativas do heroi com o atributo aprendido (Level >= 1 em attributeSaveDatas)."""
    lv = {str(a.get("Key")): int(a.get("Level", 0)) for a in State.save.player.get("attributeSaveDatas") or []}
    hk = int(h.get("heroKey"))
    return {sk for (k, sk), attr in GD.active_skill_attr.items() if k == hk and lv.get(str(attr), 0) >= 1}


def third_skill_slot():
    """A 3a posicao de skill so abre com a runa de UnlockSkillSlotCount (runa 27) no nivel >= 1."""
    keys = GD.rune_keys_with_stat("UnlockSkillSlotCount")
    return any(str(r.get("RuneKey")) in keys and int(r.get("Level", 0)) >= 1
               for r in State.save.player.get("RuneSaveData") or [])


def find_item(uid):
    for it in State.save.player.get("itemSaveDatas", []):
        if str(it["UniqueId"]) == str(uid):
            return it
    return None


def find_hero(hero_key):
    for h in State.save.player.get("heroSaveDatas", []):
        if str(h.get("heroKey")) == str(hero_key):
            return h
    return None


def _num(body, key, lo, hi, kind=int):
    """Le body[key] como numero com limites. None se ausente; ValueError se invalido."""
    v = body.get(key)
    if v is None or v == "":
        return None
    try:
        v = kind(v)
    except (TypeError, ValueError):
        raise ValueError("%s inválido" % key)
    if not (lo <= v <= hi):
        raise ValueError("%s fora do intervalo [%s, %s]" % (key, lo, hi))
    return v


def _changed(body, key, cur, lo, hi, kind=int):
    """Como _num, mas None se o valor e igual ao atual: so o que muda passa pelos limites
    (um valor legado fora da faixa, reenviado igual pela UI, nao vira erro)."""
    v = body.get(key)
    if v is None or v == "":
        return None
    try:
        v = kind(v)
    except (TypeError, ValueError):
        raise ValueError("%s inválido" % key)
    if cur is not None and v == cur:
        return None
    if not (lo <= v <= hi):
        raise ValueError("%s fora do intervalo [%s, %s]" % (key, lo, hi))
    return v


def fmt_num(x):
    return "{:,.0f}".format(x).replace(",", ".")


def cube_payload(cube):
    lv = cube.get("Level")
    mx = GD.cube_level_max()
    return {"level": lv, "exp": cube.get("Exp"), "levelMax": mx,
            "expCap": GD.cube_exp_cap(lv) if isinstance(lv, int) and lv < mx else None}


def _f32(x):
    """Valor como o jogo guarda num float (ex. 999999999 -> 1e9)."""
    return struct.unpack("<f", struct.pack("<f", x))[0]


def hero_limits(h):
    lv = h.get("HeroLevel", 1)
    return {"levelMax": GD.hero_level_max(), "expCap": GD.hero_exp_cap(lv),
            "apCap": max(0, int(lv) - int(h.get("AllocatedHeroAbilityPoint", 0))),
            "unlocked": bool(h.get("IsUnLock", True))}


def hero_brief(h):
    d = {"heroKey": h.get("heroKey"), "level": h.get("HeroLevel"), "exp": h.get("HeroExp"),
         "abilityPoint": h.get("AbilityPoint", 0),
         "allocatedPoints": h.get("AllocatedHeroAbilityPoint", 0)}
    d.update(hero_limits(h))
    return d


def runes_summary():
    """Contagem das runas do save: no maximo, abaixo (editaveis / familia bau) e sem dados."""
    total = maxed = unknown = below = chest = 0
    for r in State.save.player.get("RuneSaveData", []):
        total += 1
        mx = GD.rune_max_level(r.get("RuneKey"))
        if mx is None:
            unknown += 1
        elif int(r.get("Level", 0)) >= mx:
            maxed += 1
        elif GD.rune_is_chest(r.get("RuneKey")):
            chest += 1
        else:
            below += 1
    return {"total": total, "maxed": maxed, "unknown": unknown, "below": below, "chest": chest}


def progress_payload():
    """Progresso so para leitura: o servidor do jogo e a autoridade sobre estagios."""
    c = State.save.player.get("commonSaveData") or {}
    st = lambda k: GD.stage(k, State.locale)  # noqa: E731
    plague = c.get("lastPlayedPlagueIntensity") or []
    diffs = GD.difficulties()
    return {"current": st(c.get("currentStageKey")), "wave": c.get("currentStageWave"),
            "unlockedUpTo": st(c.get("maxCompletedStage")), "lastCleared": st(c.get("lastClearedStageKey")),
            "prevNormal": st(c.get("prevNormalStageKey")),
            "plague": [{"difficulty": diffs[i] if i < len(diffs) else str(i), "intensity": v}
                       for i, v in enumerate(plague)],
            "playTimeHours": round(float(State.save.account.get("playTime") or 0) / 3600, 1)}


def pet_progress(pet_key):
    """Condicao de desbloqueio do pet: abates atuais x necessarios (agregado Type 0 do save)."""
    info = GD.pet_info.get(str(pet_key)) or {}
    if info.get("UnlockCondition") != "KillMonster":
        return {"condition": info.get("UnlockCondition")}
    kills = sum(int(a.get("Value", 0)) for a in State.save.player.get("aggregateSaveDatas") or []
                if a.get("Type") == 0 and str(a.get("SubKey")) == str(info.get("Param1")))
    return {"condition": "KillMonster", "monsterKey": info.get("Param1"),
            "kills": kills, "need": int(info.get("Param2") or 0)}


def player_payload():
    p = State.save.player
    currencies = [{"key": c.get("Key"), "name": GD.currency_name(c.get("Key"), State.locale),
                   "quantity": c.get("Quantity", 0)} for c in p.get("currenySaveDatas", [])]
    pets = []
    for x in p.get("PetSaveData", []):
        d = {"key": x.get("PetKey"), "name": GD.pet_name(x.get("PetKey"), State.locale),
             "unlocked": bool(x.get("IsUnlock")), "dlc": GD.pet_is_dlc(x.get("PetKey"))}
        d.update(pet_progress(x.get("PetKey")))
        pets.append(d)
    cube = p.get("cubeSaveLevelData") or {}
    arranged = (p.get("commonSaveData") or {}).get("ArrangedPetKey")
    return {"currencies": currencies, "pets": pets, "arrangedPetKey": arranged,
            "runes": runes_summary(),
            "cube": cube_payload(cube) if cube else None}


# ---------------- HTTP handler ----------------
class Handler(http.server.BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json", headers=None):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False).encode("utf-8")
        elif isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _guard(self, api, post):
        """Mensagem de recusa (403) ou None. Host local em tudo (contra DNS rebinding);
        nas rotas /api/, Origin local, token da pagina e JSON no POST (P2-9)."""
        if (self.headers.get("Host") or "").lower() not in ALLOWED_HOSTS:
            return "host não permitido"
        if not api:
            return None
        origin = (self.headers.get("Origin") or "").lower()
        if origin and origin not in ["http://" + h for h in ALLOWED_HOSTS]:
            return "origem não permitida"
        if not hmac.compare_digest(self.headers.get("X-TBH-Token") or "", TOKEN):
            return "token inválido — recarregue a página do editor"
        if post and not (self.headers.get("Content-Type") or "").lower().startswith("application/json"):
            return "Content-Type deve ser application/json"
        return None

    def _file(self, path, ctype):
        if not os.path.exists(path):
            return self._send(404, {"error": "not found"})
        with open(path, "rb") as f:
            self._send(200, f.read(), ctype)

    def log_message(self, *a):
        pass  # silencioso

    # ---- GET ----
    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(u.query)
        p = u.path
        err = self._guard(p.startswith("/api/"), False)
        if err:
            return self._send(403, {"error": err})
        if p == "/" or p == "/index.html":
            with open(os.path.join(WEB, "index.html"), encoding="utf-8") as fh:
                page = fh.read().replace("__TBH_TOKEN__", TOKEN)
            return self._send(200, page, "text/html; charset=utf-8", {"Cache-Control": "no-store"})
        if p == "/app.js":
            return self._file(os.path.join(WEB, "app.js"), "application/javascript; charset=utf-8")
        if p == "/style.css":
            return self._file(os.path.join(WEB, "style.css"), "text/css; charset=utf-8")
        if p.startswith("/icons/"):
            f = GD.icon_file(p[len("/icons/"):].replace(".png", ""))
            if not f:
                return self._send(404, {"error": "sem ícone"})
            return self._file(os.path.join(ICONS, os.path.basename(f)), "image/png")
        if p == "/api/state":
            path = State.path or default_save_path()
            return self._send(200, {"loaded": State.save is not None, "path": path, "locale": State.locale,
                                    "gameRunning": tbh_paths.game_running(),
                                    "isGameSave": bool(path) and tbh_paths.is_protected(path),
                                    "dataVersion": GD.version,
                                    "saveVersion": State.save.account.get("version") if State.save else None})
        if p == "/api/heroes":
            if not State.save:
                return self._send(400, {"error": "save nao carregado"})
            return self._send(200, heroes_payload())
        if p == "/api/materials":
            try:
                slot = int(q.get("slot", ["0"])[0])
                if slot < 0:
                    raise IndexError
                mtype = GD.slot_material_type(slot)
            except (ValueError, IndexError):
                return self._send(400, {"error": "slot inválido"})
            mats = [{"key": int(k), "name": GD.name(k, State.locale),
                     "icon": "/icons/%s" % k if GD.has_icon(k) else None}
                    for k in GD.materials_by_type[mtype]]
            mats.sort(key=lambda m: m["name"])
            return self._send(200, {"type": mtype, "materials": mats})
        if p == "/api/options":
            try:
                return self._send(200, options_payload(q["material"][0], int(q["item"][0])))
            except (KeyError, IndexError, ValueError):
                return self._send(400, {"error": "parâmetros material e item são obrigatórios"})
        if p == "/api/player":
            if not State.save:
                return self._send(400, {"error": "save nao carregado"})
            return self._send(200, player_payload())
        if p == "/api/progress":
            if not State.save:
                return self._send(400, {"error": "save nao carregado"})
            return self._send(200, progress_payload())
        return self._send(404, {"error": "rota desconhecida"})

    # ---- POST ----
    def do_POST(self):
        u = urllib.parse.urlparse(self.path)
        p = u.path
        err = self._guard(True, True)
        if err:
            return self._send(403, {"error": err})
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length) or b"{}")
            if not isinstance(body, dict):
                raise ValueError
        except ValueError:
            return self._send(400, {"error": "corpo JSON inválido"})
        if p == "/api/load":
            path = body.get("path") or default_save_path()
            State.locale = body.get("locale", State.locale)
            try:
                State.save = es3.SaveFile.load(path)
                State.path = path
                State.stamp = file_stamp(path)
            except Exception as e:
                return self._send(400, {"error": "falha ao carregar: %s" % e})
            return self._send(200, heroes_payload())
        if p == "/api/set_enchant":
            if not State.save:
                return self._send(400, {"error": "save nao carregado"})
            it = find_item(body.get("uniqueId"))
            if not it:
                return self._send(404, {"error": "item nao encontrado"})
            try:
                slot = int(body.get("slot"))
            except (TypeError, ValueError):
                return self._send(400, {"error": "slot inválido"})
            if not 0 <= slot < len(SLOT_LABELS):
                return self._send(400, {"error": "slot inválido"})
            why = item_lock(it)
            if why:
                return self._send(409 if "pendente" in why else 400, {"error": why})
            # valida tudo antes de mexer no item (P2-1)
            if body.get("clear"):
                if GD.clear_enchant(it, slot):  # Extracao: nao conta aplicacao
                    GD.recount_enchants(it)
                return self._send(200, item_payload(it))
            try:
                fields = GD.enchant_fields(slot, it["ItemKey"], int(body["materialKey"]),
                                           int(body["statModKey"]), int(body["tier"]), int(body["value"]))
            except KeyError as e:
                return self._send(400, {"error": "campo %s ausente" % e})
            except (TypeError, ValueError) as e:
                return self._send(400, {"error": str(e)})
            if GD.write_enchant(it, slot, fields, State.save.account.get("version")):
                GD.bump_applied(it, slot)     # +1 no AppliedTotalCount do tipo (so mudanca real)
                GD.recount_enchants(it)
            return self._send(200, item_payload(it))
        if p == "/api/auto_build":
            if not State.save:
                return self._send(400, {"error": "save nao carregado"})
            mode = body.get("mode", "balanced")
            if mode not in ("balanced", "damage", "survival"):
                return self._send(400, {"error": "modo inválido"})
            overwrite = bool(body.get("overwrite", True))
            hero_key = body.get("heroKey")
            heroes = State.save.player.get("heroSaveDatas", [])
            if hero_key not in (None, "", "all"):
                heroes = [h for h in heroes if str(h.get("heroKey")) == str(hero_key)]
                if not heroes:
                    return self._send(404, {"error": "herói não encontrado"})
            items_by_uid = {str(it["UniqueId"]): it for it in State.save.player.get("itemSaveDatas", [])}
            n_items = n_slots = 0
            for h in heroes:
                hk = h.get("heroKey")
                for uid in h.get("equippedItemIds", []):
                    it = items_by_uid.get(str(uid))
                    if not it or item_lock(it):
                        continue
                    plan = autobuild.plan_item(GD, it["ItemKey"], hk, mode=mode,
                                               overwrite=overwrite, current=it.get("EnchantData", []))
                    if not plan:
                        continue
                    touched = False
                    for slot, fields in plan:
                        # compara so os 7 campos; slot igual nao e regravado nem contado (P1-3)
                        if GD.write_enchant(it, slot, fields, State.save.account.get("version")):
                            GD.bump_applied(it, slot)
                            n_slots += 1
                            touched = True
                    if touched:
                        GD.recount_enchants(it)
                        n_items += 1
            res = heroes_payload()
            res.update({"ok": True, "mode": mode, "overwrite": overwrite,
                        "items": n_items, "slots": n_slots})
            return self._send(200, res)
        if p == "/api/set_skills":
            if not State.save:
                return self._send(400, {"error": "save nao carregado"})
            mode = body.get("mode", "balanced")
            if mode not in ("balanced", "damage", "survival"):
                return self._send(400, {"error": "modo inválido"})
            hero_key = body.get("heroKey")
            heroes = State.save.player.get("heroSaveDatas", [])
            if hero_key not in (None, "", "all"):
                heroes = [h for h in heroes if str(h.get("heroKey")) == str(hero_key)]
                if not heroes:
                    return self._send(404, {"error": "herói não encontrado"})
            changed = 0
            third = third_skill_slot()
            for h in heroes:
                if not h.get("IsUnLock", True):
                    continue  # heroi bloqueado nao e editavel
                new = autobuild.skill_loadout(GD, h.get("heroKey"), mode, h.get("equippedSKillKey"),
                                              learned_skills(h), third)
                if new and new != h.get("equippedSKillKey"):
                    h["equippedSKillKey"] = new
                    changed += 1
            res = heroes_payload()
            res.update({"ok": True, "mode": mode, "changed": changed})
            return self._send(200, res)
        if p == "/api/set_hero":
            if not State.save:
                return self._send(400, {"error": "save nao carregado"})
            h = find_hero(body.get("heroKey"))
            if not h:
                return self._send(404, {"error": "herói não encontrado"})
            if not h.get("IsUnLock", True):
                return self._send(400, {"error": "herói bloqueado no jogo — não editável"})
            lv_max = GD.hero_level_max()
            try:  # limites do jogo (P1-5, P2-4); o jogo nao corrige nivel acima de lv_max
                lv = _changed(body, "level", h.get("HeroLevel"), 1, lv_max)
                xp = _changed(body, "exp", h.get("HeroExp"), 0, 10 ** 15, float)
                ap = _changed(body, "abilityPoint", h.get("AbilityPoint"), 0, 999999)
                new_lv = h.get("HeroLevel", 1) if lv is None else lv
                if (lv is not None or xp is not None) and new_lv >= lv_max:
                    if xp is not None:
                        raise ValueError("no nível máximo (%d) a EXP é só exibição" % lv_max)
                elif lv is not None or xp is not None:
                    cap = GD.hero_exp_cap(new_lv)
                    new_xp = float(h.get("HeroExp") or 0) if xp is None else xp
                    if cap is not None and new_xp >= cap:
                        raise ValueError("no nível %d a EXP deve ficar abaixo de %s" % (new_lv, fmt_num(cap)))
                if lv is not None or ap is not None:
                    new_ap = h.get("AbilityPoint", 0) if ap is None else ap
                    ap_cap = max(0, new_lv - int(h.get("AllocatedHeroAbilityPoint", 0)))
                    if new_ap > ap_cap:
                        raise ValueError("pontos livres no máximo %d (nível − pontos já alocados)" % ap_cap)
            except ValueError as e:
                return self._send(400, {"error": str(e)})
            if ap is not None:
                h["AbilityPoint"] = ap
            if lv is not None:
                h["HeroLevel"] = lv
            if xp is not None:
                h["HeroExp"] = xp
            return self._send(200, {"ok": True, "hero": hero_brief(h)})
        if p == "/api/set_currency":
            if not State.save:
                return self._send(400, {"error": "save nao carregado"})
            try:
                key = _num(body, "key", 1, 10 ** 9)
                qty = _num(body, "quantity", 0, 10 ** 13)
            except ValueError as e:
                return self._send(400, {"error": str(e)})
            if key is None or qty is None:
                return self._send(400, {"error": "key e quantity são obrigatórios"})
            curs = State.save.player.setdefault("currenySaveDatas", [])
            entry = next((c for c in curs if str(c.get("Key")) == str(key)), None)
            if not entry:
                if str(key) not in GD.currency_info:
                    return self._send(404, {"error": "moeda desconhecida"})
                entry = {"Key": int(key), "Quantity": 0}
                curs.append(entry)
            entry["Quantity"] = qty
            res = {"ok": True, "key": entry["Key"], "quantity": qty}
            if qty > GOLD_WARN:
                res["warning"] = ("acima de %s: o valor vai no snapshot ao servidor e destoa do "
                                  "total_gold_earned da Steam" % fmt_num(GOLD_WARN))
            return self._send(200, res)
        if p == "/api/set_pet":
            if not State.save:
                return self._send(400, {"error": "save nao carregado"})
            pet = next((x for x in State.save.player.get("PetSaveData", [])
                        if str(x.get("PetKey")) == str(body.get("petKey"))), None)
            if not pet:
                return self._send(404, {"error": "pet não encontrado no save"})
            if str(pet.get("PetKey")) not in GD.pet_info:
                return self._send(400, {"error": "pet fora de PetInfoData"})
            if GD.pet_is_dlc(pet.get("PetKey")):  # P1-7: posse do DLC e da Steam, nao do save
                return self._send(400, {"error": "pet de DLC — gerenciado pela Steam; o editor não trava nem destrava"})
            unlock = bool(body.get("unlock"))
            arranged = (State.save.player.get("commonSaveData") or {}).get("ArrangedPetKey")
            if not unlock and str(arranged) == str(pet.get("PetKey")):
                return self._send(400, {"error": "esse pet está equipado — troque-o no jogo antes de bloquear"})
            pet["IsUnlock"] = unlock
            if unlock:
                pet["IsViewed"] = True
            res = {"ok": True, "petKey": pet.get("PetKey"), "unlocked": unlock}
            prog = pet_progress(pet.get("PetKey"))
            if unlock and prog.get("kills", 0) < prog.get("need", 0):
                res["warning"] = ("condição do jogo não cumprida (%s de %s abates): o jogo pode travar "
                                  "o pet de novo" % (fmt_num(prog["kills"]), fmt_num(prog["need"])))
            return self._send(200, res)
        if p == "/api/max_runes":
            if not State.save:
                return self._send(400, {"error": "save nao carregado"})
            changed, chest = 0, []
            for r in State.save.player.get("RuneSaveData", []):
                mx = GD.rune_max_level(r.get("RuneKey"))
                if mx is None or int(r.get("Level", 0)) >= mx:
                    continue
                if GD.rune_is_chest(r.get("RuneKey")):  # P1-9: familia bau fica de fora
                    chest.append(GD.rune_name(r.get("RuneKey"), State.locale))
                    continue
                r["Level"] = mx
                changed += 1
            return self._send(200, {"ok": True, "changed": changed, "skippedChest": chest,
                                    "runes": runes_summary()})
        if p == "/api/set_cube":
            if not State.save:
                return self._send(400, {"error": "save nao carregado"})
            cube = State.save.player.get("cubeSaveLevelData")
            if not isinstance(cube, dict):
                return self._send(404, {"error": "cubo não encontrado no save"})
            lv_max = GD.cube_level_max()
            try:  # P1-6: nivel 1..max; Exp coerente (o jogo corrige o nivel no load, nao o Exp)
                lv = _changed(body, "level", cube.get("Level"), 1, lv_max)
                xp = _changed(body, "exp", cube.get("Exp"), 0, 10 ** 12, float)
                new_lv = cube.get("Level") if lv is None else lv
                new_xp = None
                if (lv is not None or xp is not None) and new_lv >= lv_max:
                    if xp is not None:
                        raise ValueError("no nível máximo (%d) o Exp é fixo" % lv_max)
                    new_xp = _f32(GD.cube_exp_cap(lv_max))  # o que o jogo grava no maximo
                elif lv is not None or xp is not None:
                    cap = GD.cube_exp_cap(new_lv)
                    new_xp = float(cube.get("Exp") or 0) if xp is None else xp
                    if new_xp >= cap:
                        if xp is not None:
                            raise ValueError("no nível %d o Exp deve ficar abaixo de %s" % (new_lv, fmt_num(cap)))
                        new_xp = 0.0  # o Exp antigo nao cabe no nivel novo
            except ValueError as e:
                return self._send(400, {"error": str(e)})
            if lv is not None:
                cube["Level"] = lv
            if new_xp is not None and new_xp != cube.get("Exp"):
                cube["Exp"] = new_xp
            return self._send(200, {"ok": True, "cube": cube_payload(cube)})
        if p == "/api/save":
            if not State.save:
                return self._send(400, {"error": "nada carregado"})
            # P1-8: o jogo regrava o save a cada 3 min e ao fechar; com ele aberto, a edicao some
            if tbh_paths.is_protected(State.path) and tbh_paths.game_running() is not False:
                return self._send(409, {"error": "o Taskbar Hero está aberto (ou não deu para conferir): "
                                                 "feche o jogo antes de salvar"})
            try:
                now = file_stamp(State.path)
            except OSError:
                now = None
            if now != State.stamp:
                return self._send(409, {"error": "o arquivo mudou desde que foi carregado (o jogo salvou?): "
                                                 "carregue de novo e refaça a edição"})
            # repara EnchantCount diferente dos slots ocupados em todos os itens
            fixed = 0
            for it in State.save.player.get("itemSaveDatas", []):
                before = it.get("EnchantCount")
                GD.recount_enchants(it)
                if it["EnchantCount"] != before:
                    fixed += 1
            try:
                State.save.save(State.path, backup=True)  # atomico: .tmp + os.replace
                State.stamp = file_stamp(State.path)
            except Exception as e:
                return self._send(500, {"error": str(e)})
            res = {"ok": True, "path": State.path, "backup": State.path + ".bak", "fixed": fixed}
            names, _uids = pending_summary()
            if names:  # P2-2: o jogo conclui essas transacoes com o servidor na proxima abertura
                res["warning"] = ("o save tem transações pendentes (%s); os itens citados não foram editados"
                                  % ", ".join(names))
            return self._send(200, res)
        return self._send(404, {"error": "rota desconhecida"})


class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True


def main():
    httpd = Server(("127.0.0.1", PORT), Handler)
    url = "http://127.0.0.1:%d" % PORT
    print("TBH Save Editor em %s  (AES: %s)" % (url, es3.AES_BACKEND))
    print("Ctrl+C para sair.")
    if not os.environ.get("TBH_NO_BROWSER"):
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nencerrando.")


if __name__ == "__main__":
    main()
