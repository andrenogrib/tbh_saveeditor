"""
Protecoes do Salvar e do servidor local: jogo aberto, arquivo mudado desde o load, escrita
atomica, transacoes pendentes (P1-8, P2-2) e origem das requisicoes (P2-9, P3-2).
"""
import io
import json
import os

from tests import support
from tests.support import SaveCase, Headers, call, server


class SaveSafetyTest(SaveCase):
    def patch(self, obj, name, value):
        old = getattr(obj, name)
        setattr(obj, name, value)
        self.addCleanup(setattr, obj, name, old)

    def test_recusa_com_o_jogo_aberto(self):
        self.patch(server.tbh_paths, "is_protected", lambda p: True)
        for running in (True, None):  # None = nao deu para conferir: trata como aberto
            self.patch(server.tbh_paths, "game_running", lambda r=running: r)
            code, res = call("POST", "/api/save", {})
            self.assertEqual(code, 409, res)
        self.assertFalse(os.path.exists(self.path + ".bak"))
        self.patch(server.tbh_paths, "game_running", lambda: False)
        self.ok("POST", "/api/save", {})

    def test_recusa_se_o_arquivo_mudou(self):
        with open(self.path, "ab") as fh:  # o jogo regravou o save depois do load
            fh.write(b"x")
        with open(self.path, "rb") as fh:
            changed = fh.read()
        code, res = call("POST", "/api/save", {})
        self.assertEqual(code, 409, res)
        with open(self.path, "rb") as fh:
            self.assertEqual(fh.read(), changed)

    def test_carimbo_e_dos_bytes_decriptados(self):
        with open(self.path, "rb") as fh:
            self.assertEqual(server.State.stamp, server.stamp_of(fh.read()))

    def test_gravacao_atomica_e_salvar_duas_vezes(self):
        self.save_and_check(allowed=())
        self.assertFalse(os.path.exists(self.path + ".tmp"))
        self.ok("POST", "/api/save", {})  # o carimbo do arquivo e atualizado a cada Salvar

    def test_item_com_transacao_pendente(self):
        it = next(it for _h, it in self.equipped_items())
        self.save.player["pendingEnchantList"] = [{"GearUniqueId": int(it["UniqueId"]), "MaterialUniqueId": 1,
                                                   "RecipeType": 3, "Enchant": None, "TxId": "t",
                                                   "TimestampTicks": 0}]
        code, res = call("POST", "/api/set_enchant", {"uniqueId": str(it["UniqueId"]), "slot": 0, "clear": True})
        self.assertEqual(code, 409, res)
        before = json.dumps(it, sort_keys=True)
        self.ok("POST", "/api/auto_build", {"mode": "damage", "overwrite": True})
        self.assertEqual(json.dumps(it, sort_keys=True), before)
        it["EnchantCount"] = [3, 3, 3]  # o jogo ja contou o encantamento que o servidor vai confirmar
        res = self.ok("POST", "/api/save", {})
        self.assertIn("pendingEnchantList", res.get("warning", ""))
        self.assertEqual(it["EnchantCount"], [3, 3, 3])  # o Salvar nao "repara" item pendente


class RequestGuardTest(SaveCase):
    def raw(self, method, path, headers, body=b"{}"):
        h = support.FakeHandler()
        h.path, h.headers, h.rfile = path, headers, io.BytesIO(body)
        (h.do_GET if method == "GET" else h.do_POST)()
        return h.result

    def test_recusa_requisicao_de_fora(self):
        good = support.request_headers(2)
        cases = [Headers({k: v for k, v in good.items() if k != "X-TBH-Token"}),
                 Headers(dict(good, **{"X-TBH-Token": "outro"})),
                 Headers(dict(good, Host="evil.example:8765")),
                 Headers(dict(good, Origin="http://evil.example")),
                 Headers(dict(good, **{"Content-Type": "text/plain"}))]
        for hdr in cases:
            self.assertEqual(self.raw("POST", "/api/save", hdr)[0], 403, hdr)
        self.assertEqual(self.raw("GET", "/api/heroes", cases[0])[0], 403)
        self.assertEqual(self.raw("GET", "/", Headers(Host="evil.example:8765"))[0], 403)
        code, page = self.raw("GET", "/", Headers(Host="127.0.0.1:%d" % server.PORT))
        self.assertEqual(code, 200)
        self.assertIn(server.TOKEN, page)
        self.assertFalse(os.path.exists(self.path + ".bak"))  # nada foi salvo

    def test_parametros_invalidos_dao_400(self):
        for path in ("/api/materials?slot=6", "/api/materials?slot=x", "/api/options", "/api/options?material=1"):
            self.assertEqual(call("GET", path)[0], 400, path)
        hdr = support.request_headers(3)
        self.assertEqual(self.raw("POST", "/api/set_hero", hdr, b"[1]")[0], 400)
        self.assertEqual(self.raw("POST", "/api/set_hero", hdr, b"{x")[0], 400)
