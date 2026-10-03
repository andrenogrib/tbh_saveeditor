"""Ponto de volta automatico a cada Salvar e restauracao (docs/ROADMAP.md, item 1)."""
import os

from tests.support import SaveCase, call, server
import save_lab  # noqa: E402  (tools/ entra no sys.path via tests.support)


class BackupTest(SaveCase):
    def patch(self, obj, name, value):
        old = getattr(obj, name)
        setattr(obj, name, value)
        self.addCleanup(setattr, obj, name, old)

    def gold(self):
        return self.save.player["currenySaveDatas"][0]["Quantity"]

    def edit_and_save(self):
        cur = self.save.player["currenySaveDatas"][0]
        self.ok("POST", "/api/set_currency", {"key": cur["Key"], "quantity": cur["Quantity"] + 1})
        self.ok("POST", "/api/save", {})

    def backups(self):
        return self.ok("GET", "/api/backups")["backups"]

    def test_salvar_cria_ponto_de_volta_com_o_arquivo_de_antes(self):
        self.edit_and_save()
        bks = self.backups()
        self.assertEqual(len(bks), 1)
        self.assertEqual(bks[0]["source"], self.path)
        with open(self.snapshot, "rb") as a, open(bks[0]["file"], "rb") as b:
            self.assertEqual(a.read(), b.read())

    def test_restaurar_volta_o_arquivo_e_recarrega(self):
        g0 = self.gold()
        self.edit_and_save()
        with open(self.path, "rb") as fh:
            edited = fh.read()
        bid = self.backups()[0]["id"]
        res = self.ok("POST", "/api/restore", {"id": bid})
        with open(self.path, "rb") as a, open(self.snapshot, "rb") as b:
            self.assertEqual(a.read(), b.read())
        self.assertEqual(server.State.save.player["currenySaveDatas"][0]["Quantity"], g0)  # recarregado
        undo = next(b for b in self.backups() if b["id"] == res["undo"])  # restaurar tambem se desfaz
        with open(undo["file"], "rb") as fh:
            self.assertEqual(fh.read(), edited)
        self.ok("POST", "/api/save", {})  # o carimbo do arquivo restaurado vale para o proximo Salvar

    def test_restaurar_recusa_com_o_jogo_aberto_e_backup_invalido(self):
        self.edit_and_save()
        bk = self.backups()[0]
        with open(self.path, "rb") as fh:
            before = fh.read()
        self.patch(server.tbh_paths, "is_protected", lambda p: server.same_file(p, self.path))  # so o save
        self.patch(server.tbh_paths, "game_running", lambda: True)
        self.assertEqual(call("POST", "/api/restore", {"id": bk["id"]})[0], 409)
        self.patch(server.tbh_paths, "game_running", lambda: False)
        with open(bk["file"], "r+b") as fh:  # backup corrompido: nao decripta / HMAC errado
            fh.seek(40)
            fh.write(b"\0" * 16)
        self.assertEqual(call("POST", "/api/restore", {"id": bk["id"]})[0], 400)
        for bad in ("../x", "", "nao-existe"):
            self.assertIn(call("POST", "/api/restore", {"id": bad})[0], (400, 404))
        with open(self.path, "rb") as fh:
            self.assertEqual(fh.read(), before)

    def test_guarda_so_os_mais_novos(self):
        self.patch(server, "KEEP_BACKUPS", 2)
        for _ in range(3):
            self.edit_and_save()
        bks = self.backups()
        self.assertEqual(len(bks), 2)
        _obj, _acc, ply = save_lab.load_es3(bks[0]["file"])  # o mais novo primeiro
        self.assertEqual(ply["currenySaveDatas"][0]["Quantity"], self.gold() - 1)
