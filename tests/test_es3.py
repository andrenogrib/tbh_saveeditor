"""Camada ES3: cripto + SystemInfo, num save sintetico e no snapshot real."""
import json
import os
import shutil
import tempfile
import unittest

from tests import support
from core import es3
import save_lab


def _write_synthetic(path):
    acc = {"version": "1.2.8", "ownerSteamId": 76561190000000000, "playTime": 1.5}
    ply = {"heroSaveDatas": [], "itemSaveDatas": [], "texto": "çã"}
    obj = {"AccountSaveData": {"__type": "string", "value": json.dumps(acc)},
           "PlayerSaveData": {"__type": "string", "value": json.dumps(ply)},
           "SystemInfo": {"__type": "string", "value": ""}}
    with open(path, "wb") as fh:
        fh.write(es3.es3_encrypt(json.dumps(obj).encode("utf-8")))
    return acc, ply


class Es3Test(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="tbh_test_")
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def test_sintetico_salva_com_hmac_e_backup(self):
        p = os.path.join(self.tmp, "s.es3")
        acc, ply = _write_synthetic(p)
        with open(p, "rb") as fh:
            before = fh.read()
        es3.SaveFile.load(p).save(p, backup=True)
        obj, acc1, ply1 = save_lab.load_es3(p)
        self.assertTrue(save_lab.systeminfo_ok(obj, acc1))
        self.assertEqual((acc1, ply1), (acc, ply))
        with open(p + ".bak", "rb") as fh:
            self.assertEqual(fh.read(), before)

    def test_roundtrip_do_snapshot_sem_edicao(self):
        src = support.require_snapshot()
        p = os.path.join(self.tmp, "SaveFile_Live.es3")
        shutil.copy2(src, p)
        obj0, acc0, ply0 = save_lab.load_es3(p)
        self.assertTrue(save_lab.systeminfo_ok(obj0, acc0), "snapshot ja vem com HMAC invalido")
        es3.SaveFile.load(p).save(p, backup=False)
        obj1, acc1, ply1 = save_lab.load_es3(p)
        self.assertTrue(save_lab.systeminfo_ok(obj1, acc1))
        # igualdade estrita (1 != 1.0 != True): json com chaves ordenadas
        self.assertEqual(json.dumps([acc0, ply0], sort_keys=True), json.dumps([acc1, ply1], sort_keys=True))


if __name__ == "__main__":
    unittest.main()
