"""
TBH Save Editor - servidor web local (stdlib, zero dependencias).
Edita os encantamentos (decoration/engraving/inscription) dos itens equipados dos herois,
com validacao pelas tabelas do jogo, e recalcula o SystemInfo ao salvar.

Uso:  python server.py        (abre http://127.0.0.1:8765 no navegador)
"""
import http.server
import json
import os
import socketserver
import threading
import urllib.parse
import webbrowser

from core import es3, gamedata

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, "data")
WEB = os.path.join(ROOT, "web")
ICONS = os.path.join(DATA, "icons")
PORT = 8765

GD = gamedata.GameData(DATA)
SLOT_LABELS = ["Decoration", "Decoration", "Engraving", "Engraving", "Inscription", "Inscription"]


class State:
    save = None
    path = None
    locale = "pt"


def default_save_path():
    up = os.environ.get("USERPROFILE", "")
    p = os.path.join(up, "AppData", "LocalLow", "TesseractStudio", "TaskbarHero", "SaveFile_Live.es3")
    return p if os.path.exists(p) else ""


# ---------------- serializacao para a UI ----------------
def item_payload(it):
    ikey = it["ItemKey"]
    enchants = []
    for i, ed in enumerate(it.get("EnchantData", [])[:6]):
        filled = ed.get("MaterialKey", 0) != 0
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
        out.append({"heroKey": h.get("heroKey"), "level": h.get("HeroLevel"),
                    "name": GD.hero_name(h.get("heroKey"), State.locale),
                    "klass": GD.hero_class(h.get("heroKey")), "items": slots})
    return {"heroes": out, "locale": State.locale, "path": State.path}


def options_payload(material_key, item_key):
    gg = GD.gear_group(item_key)
    opts = GD.stat_options(material_key, gg)
    return {"materialKey": int(material_key), "gearGroup": gg, "options": opts}


def find_item(uid):
    for it in State.save.player.get("itemSaveDatas", []):
        if str(it["UniqueId"]) == str(uid):
            return it
    return None


# ---------------- HTTP handler ----------------
class Handler(http.server.BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False).encode("utf-8")
        elif isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

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
        if p == "/" or p == "/index.html":
            return self._file(os.path.join(WEB, "index.html"), "text/html; charset=utf-8")
        if p == "/app.js":
            return self._file(os.path.join(WEB, "app.js"), "application/javascript; charset=utf-8")
        if p == "/style.css":
            return self._file(os.path.join(WEB, "style.css"), "text/css; charset=utf-8")
        if p.startswith("/icons/"):
            key = GD.base_key(p[len("/icons/"):].replace(".png", ""))
            return self._file(os.path.join(ICONS, "%s.png" % key), "image/png")
        if p == "/api/state":
            return self._send(200, {"loaded": State.save is not None, "path": State.path or default_save_path(),
                                    "locale": State.locale})
        if p == "/api/heroes":
            if not State.save:
                return self._send(400, {"error": "save nao carregado"})
            return self._send(200, heroes_payload())
        if p == "/api/materials":
            slot = int(q.get("slot", ["0"])[0])
            mtype = GD.slot_material_type(slot)
            mats = [{"key": int(k), "name": GD.name(k, State.locale),
                     "icon": "/icons/%s" % k if GD.has_icon(k) else None}
                    for k in GD.materials_by_type[mtype]]
            mats.sort(key=lambda m: m["name"])
            return self._send(200, {"type": mtype, "materials": mats})
        if p == "/api/options":
            return self._send(200, options_payload(q["material"][0], int(q["item"][0])))
        return self._send(404, {"error": "rota desconhecida"})

    # ---- POST ----
    def do_POST(self):
        u = urllib.parse.urlparse(self.path)
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")
        p = u.path
        if p == "/api/load":
            path = body.get("path") or default_save_path()
            State.locale = body.get("locale", State.locale)
            try:
                State.save = es3.SaveFile.load(path)
                State.path = path
            except Exception as e:
                return self._send(400, {"error": "falha ao carregar: %s" % e})
            return self._send(200, heroes_payload())
        if p == "/api/set_enchant":
            it = find_item(body["uniqueId"])
            if not it:
                return self._send(404, {"error": "item nao encontrado"})
            slot = int(body["slot"])
            while len(it.get("EnchantData", [])) <= slot:
                it.setdefault("EnchantData", []).append(GD.empty_enchant())
            if body.get("clear"):
                it["EnchantData"][slot] = GD.empty_enchant()
                GD.recount_enchants(it)  # mantem EnchantCount coerente
                return self._send(200, item_payload(it))
            if not GD.slot_allowed(it["ItemKey"], slot):
                return self._send(400, {"error": "a grade %s do item não permite esse slot" % GD.grade_name(it["ItemKey"])})
            try:
                ed = GD.build_enchant(slot, int(body["materialKey"]), int(body["statModKey"]),
                                      int(body["tier"]), int(body["value"]))
            except Exception as e:
                return self._send(400, {"error": str(e)})
            errs = GD.validate_enchant(slot, it["ItemKey"], ed)
            if errs:
                return self._send(400, {"error": "; ".join(errs)})
            it["EnchantData"][slot] = ed
            GD.bump_applied(it, slot)     # +1 no AppliedTotalCount do tipo
            GD.recount_enchants(it)       # EnchantCount = nº ativos por tipo (ATIVA o efeito no jogo)
            return self._send(200, item_payload(it))
        if p == "/api/save":
            if not State.save:
                return self._send(400, {"error": "nada carregado"})
            # repara EnchantCount inconsistente em TODOS os itens (corrige bugs antigos
            # onde o encantamento aparecia mas nao tinha efeito).
            fixed = 0
            for it in State.save.player.get("itemSaveDatas", []):
                before = it.get("EnchantCount")
                GD.recount_enchants(it)
                if it["EnchantCount"] != before:
                    fixed += 1
            try:
                State.save.save(State.path, backup=True)
            except Exception as e:
                return self._send(500, {"error": str(e)})
            return self._send(200, {"ok": True, "path": State.path, "backup": State.path + ".bak", "fixed": fixed})
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
