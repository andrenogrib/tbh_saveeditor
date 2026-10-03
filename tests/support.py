"""
Apoio dos testes: snapshot do save, copia temporaria, chamada das rotas reais do server.py
sem abrir porta (handler falso) e comparacao "so o editado mudou".

Os testes NUNCA tocam o save vivo: usam o snapshot mais novo de ~/tbh_re/saves (ou
TBH_TEST_SAVE), copiado para uma pasta temporaria. Sem snapshot, os testes que precisam de um
save real sao pulados (python tools/save_lab.py snapshot cria um).
"""
import io
import json
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (ROOT, os.path.join(ROOT, "tools")):
    if p not in sys.path:
        sys.path.insert(0, p)

import server  # noqa: E402  (carrega GameData de data/; main() nunca e chamado)
import save_lab  # noqa: E402
import tbh_paths  # noqa: E402

# a UI e o /api/load sem caminho usariam o save vivo: nos testes, nunca
server.default_save_path = lambda: ""


def snapshot_path():
    """Save de teste: TBH_TEST_SAVE ou o snapshot mais novo de <RE>/saves."""
    env = os.environ.get("TBH_TEST_SAVE")
    if env:
        return env if os.path.isfile(env) else None
    base = os.path.join(tbh_paths.re_root(), "saves")
    if not os.path.isdir(base):
        return None
    for d in sorted(os.listdir(base), reverse=True):
        p = os.path.join(base, d, tbh_paths.LIVE_SAVE_NAME)
        if os.path.isfile(p):
            return p
    return None


def require_snapshot():
    p = snapshot_path()
    if not p:
        raise unittest.SkipTest("sem snapshot de save (rode: python tools/save_lab.py snapshot)")
    return p


class Headers(dict):
    """Cabecalhos com busca sem diferenciar maiusculas (como http.client.HTTPMessage)."""

    def get(self, key, default=None):
        for k, v in self.items():
            if k.lower() == key.lower():
                return v
        return default


class FakeHandler(server.Handler):
    def __init__(self):  # nao chama BaseHTTPRequestHandler.__init__
        self.result = None

    def _send(self, code, body, ctype="application/json", headers=None):
        self.result = (code, body)


def request_headers(raw_len):
    origin = "http://127.0.0.1:%d" % server.PORT
    h = Headers({"Content-Length": str(raw_len), "Content-Type": "application/json",
                 "Host": "127.0.0.1:%d" % server.PORT, "Origin": origin})
    token = getattr(server, "TOKEN", None)
    if token:
        h["X-TBH-Token"] = token
    return h


def call(method, path, body=None, headers=None):
    """Executa a rota real; devolve (status, json)."""
    h = FakeHandler()
    h.path = path
    raw = json.dumps(body or {}).encode("utf-8")
    h.headers = headers if headers is not None else request_headers(len(raw))
    h.rfile = io.BytesIO(raw)
    (h.do_GET if method == "GET" else h.do_POST)()
    return h.result


def deep_diff(a, b, path="", out=None):
    """Lista (caminho, tipo, antes, depois); tipo e valor juntos (1 != 1.0 != True)."""
    if out is None:
        out = []
    if isinstance(a, dict) and isinstance(b, dict):
        for k in a:
            if k not in b:
                out.append((path + "." + k, "REMOVIDO", a[k], None))
            else:
                deep_diff(a[k], b[k], path + "." + k, out)
        for k in b:
            if k not in a:
                out.append((path + "." + k, "ADICIONADO", None, b[k]))
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            out.append((path, "TAMANHO", len(a), len(b)))
        for i in range(min(len(a), len(b))):
            deep_diff(a[i], b[i], "%s[%d]" % (path, i), out)
    elif (type(a), a) != (type(b), b):
        out.append((path, "MUDOU", a, b))
    return out


class SaveCase(unittest.TestCase):
    """Cada teste recebe uma copia propria do snapshot, ja carregada pelo /api/load."""

    @classmethod
    def setUpClass(cls):
        cls.snapshot = require_snapshot()

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="tbh_test_")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.path = os.path.join(self.tmp, tbh_paths.LIVE_SAVE_NAME)
        tbh_paths.assert_writable(self.path)  # cinto: a copia nunca esta numa pasta protegida
        shutil.copy2(self.snapshot, self.path)
        self.obj0, self.acc0, self.ply0 = save_lab.load_es3(self.path)
        code, res = call("POST", "/api/load", {"path": self.path, "locale": "pt"})
        self.assertEqual(code, 200, res)
        self.save = server.State.save

    # ---- atalhos ----
    def api(self, method, path, body=None):
        return call(method, path, body)

    def ok(self, method, path, body=None):
        code, res = call(method, path, body)
        self.assertEqual(code, 200, res)
        return res

    def item_index(self, it):
        return self.save.player["itemSaveDatas"].index(it)

    def equipped_items(self):
        by_uid = {str(it["UniqueId"]): it for it in self.save.player["itemSaveDatas"]}
        out = []
        for h in self.save.player["heroSaveDatas"]:
            for uid in h.get("equippedItemIds", []):
                if str(uid) in by_uid:
                    out.append((h, by_uid[str(uid)]))
        return out

    # ---- gravar e conferir ----
    def save_and_check(self, allowed=(), allow_removed=False):
        """POST /api/save na copia; confere HMAC, arquivo == memoria e que so os caminhos
        `allowed` (prefixos de player./account.) mudaram. Devolve (diffs, player gravado)."""
        acc_mem = json.loads(json.dumps(self.save.account))
        ply_mem = json.loads(json.dumps(self.save.player))
        code, res = call("POST", "/api/save", {})
        self.assertEqual(code, 200, res)
        obj1, acc1, ply1 = save_lab.load_es3(self.path)
        self.assertTrue(save_lab.systeminfo_ok(obj1, acc1), "SystemInfo (HMAC) invalido")
        self.assertEqual(acc1.get("ownerSteamId"), self.acc0.get("ownerSteamId"))
        self.assertEqual(deep_diff(acc_mem, acc1) + deep_diff(ply_mem, ply1), [], "arquivo != memoria")
        with open(self.path + ".bak", "rb") as a, open(self.snapshot, "rb") as b:
            self.assertEqual(a.read(), b.read(), ".bak deveria ser o arquivo de antes do Salvar")
        diffs = deep_diff(self.acc0, acc1, "account") + deep_diff(self.ply0, ply1, "player")
        fora = [d for d in diffs if not any(d[0].startswith(p) for p in allowed)]
        self.assertEqual(fora, [], "mudou fora do editado")
        if not allow_removed:
            self.assertEqual([d for d in diffs if d[1] == "REMOVIDO"], [], "campo do save sumiu (invariante 2)")
        return diffs, ply1
