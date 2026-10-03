"""Previa do Salvar: o que vai mudar no arquivo, em linhas legiveis (docs/ROADMAP.md, item 2)."""
import collections

from tests.support import SaveCase
from core import es3


def br(n):
    return "{:,}".format(n).replace(",", ".")


class DiffTest(SaveCase):
    def changes(self):
        return self.ok("GET", "/api/diff")

    def test_sem_edicao_nada_muda(self):
        d = self.changes()
        self.assertEqual(d["changes"], [])
        self.assertFalse(d["fileChanged"])

    def test_ouro_com_antes_e_depois(self):
        cur = self.save.player["currenySaveDatas"][0]
        q0 = cur["Quantity"]
        self.ok("POST", "/api/set_currency", {"key": cur["Key"], "quantity": q0 + 1})
        [c] = self.changes()["changes"]
        self.assertEqual(c["area"], "Moedas")
        self.assertIn(br(q0), c["text"])
        self.assertIn(br(q0 + 1), c["text"])

    def test_encantamento_uma_linha_por_slot(self):
        _h, it = next((h, it) for h, it in self.equipped_items()
                      if any(e.get("MaterialKey") for e in it.get("EnchantData", [])))
        slot = next(i for i, e in enumerate(it["EnchantData"]) if e.get("MaterialKey"))
        self.ok("POST", "/api/set_enchant", {"uniqueId": str(it["UniqueId"]), "slot": slot, "clear": True})
        lines = self.changes()["changes"]
        self.assertEqual([c["area"] for c in lines], ["Encantamentos"])  # contadores nao viram ruido
        self.assertIn("vazio", lines[0]["text"])

    def test_cada_area_editavel_aparece(self):
        h = self.save.player["heroSaveDatas"][0]
        self.ok("POST", "/api/set_hero", {"heroKey": h["heroKey"], "level": 100, "exp": 0})
        arranged = self.save.player["commonSaveData"].get("ArrangedPetKey")
        pet = next(p for p in self.save.player["PetSaveData"] if p["PetKey"] < 6000 and p["PetKey"] != arranged)
        self.ok("POST", "/api/set_pet", {"petKey": pet["PetKey"], "unlock": not pet["IsUnlock"]})
        runes = self.ok("POST", "/api/max_runes", {"includeChest": True})["changed"]
        self.ok("POST", "/api/set_cube", {"level": 50})
        areas = collections.Counter(c["area"] for c in self.changes()["changes"])
        self.assertEqual(areas["Heróis"], 2)  # nivel e EXP
        self.assertEqual(areas["Pets"], 1)
        self.assertEqual(areas["Runas"], runes)
        self.assertGreaterEqual(areas["Cubo"], 1)
        self.assertEqual(areas["Outros"], 0)

    def test_campo_fora_das_areas_nao_muda_calado(self):
        common = self.save.player["commonSaveData"]
        common["useStorage"] = not common.get("useStorage")
        lines = self.changes()["changes"]
        self.assertEqual([c["area"] for c in lines], ["Outros"])
        self.assertIn("useStorage", lines[0]["text"])

    def test_depois_de_salvar_nada_muda_e_arquivo_regravado_avisa(self):
        cur = self.save.player["currenySaveDatas"][0]
        self.ok("POST", "/api/set_currency", {"key": cur["Key"], "quantity": cur["Quantity"] + 1})
        self.ok("POST", "/api/save", {})
        self.assertEqual(self.changes()["changes"], [])
        es3.SaveFile.load(self.path).save(self.path, backup=False)  # o jogo regravou (outro IV)
        d = self.changes()
        self.assertTrue(d["fileChanged"])
        self.assertEqual(d["changes"], [])
