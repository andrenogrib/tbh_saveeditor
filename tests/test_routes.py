"""
Rotas de edicao do server.py sobre uma copia do snapshot: cada uma em memoria, depois
/api/save na copia, HMAC, "so o editado mudou" e campos 1.2.x preservados.
Bugs conhecidos do plano (docs/UPDATE_1.2.8.md, secao 5) ficam como expectedFailure.
"""
import copy
import unittest

from tests import support
from tests.support import SaveCase
from core import gamedata

GD = lambda: support.server.GD  # noqa: E731  (o modulo pode trocar o GD)
ENCHANT_FIELDS = ("StatModKey", "Tier", "Value", "RecipeType", "ModType", "MaterialKey", "StatType")


def _core(ed):
    return tuple(ed.get(k, 0) for k in ENCHANT_FIELDS)


def _option(item_key, slot, skip=None):
    """Primeira opcao valida (material, stat, tier max, valor max) para o slot do item."""
    gd = GD()
    for mk in gd.materials_by_type[gd.slot_material_type(slot)]:
        for o in gd.stat_options(mk, gd.gear_group(item_key)):
            t = o["tiers"][-1]
            cand = (int(mk), o["statModKey"], t["tier"], t["max"])
            if cand != skip:
                return cand
    return None


class RoutesTest(SaveCase):
    # ---------- alvos ----------
    def slot_target(self, filled, keyless=False):
        """(item, slot) com slot permitido pela grade, vazio ou preenchido (qualquer item).
        keyless: so slot sem a chave EnchantVersion (o P1-4 tem teste proprio)."""
        gd = GD()
        items = [it for it in self.save.player["itemSaveDatas"] if gd.gear_group(it["ItemKey"])]
        for it in items:
            for i, ed in enumerate(it.get("EnchantData", [])[:6]):
                if keyless and "EnchantVersion" in ed:
                    continue
                if gd.slot_allowed(it["ItemKey"], i) and bool(ed.get("MaterialKey")) == filled:
                    return it, i
        if not filled:  # slot permitido alem do fim do EnchantData (o jogo completa pela grade)
            for it in items:
                n = len(it.get("EnchantData", []))
                if n < 6 and gd.slot_allowed(it["ItemKey"], n):
                    return it, n
        self.skipTest("nenhum slot %s no save" % ("preenchido" if filled else "vazio"))

    def set_enchant(self, it, slot, opt):
        mk, smk, tier, value = opt
        return self.api("POST", "/api/set_enchant", {"uniqueId": str(it["UniqueId"]), "slot": slot,
                                                     "materialKey": mk, "statModKey": smk,
                                                     "tier": tier, "value": value})

    # ---------- leitura e noop ----------
    def test_load_e_save_sem_edicao(self):
        self.save_and_check(allowed=())

    def test_rotas_de_leitura(self):
        for path in ("/api/state", "/api/heroes", "/api/player", "/api/materials?slot=0"):
            self.ok("GET", path)

    # ---------- encantamento ----------
    def test_set_enchant_slot_vazio(self):
        try:
            it, slot = self.slot_target(filled=False, keyless=True)
        except unittest.SkipTest:  # save com tudo preenchido: esvazia um slot antes
            it, slot = self.slot_target(filled=True, keyless=True)
            self.ok("POST", "/api/set_enchant", {"uniqueId": str(it["UniqueId"]), "slot": slot, "clear": True})
        mt = gamedata.SLOT_MATERIAL_TYPE[slot]
        before = copy.deepcopy(it)
        opt = _option(it["ItemKey"], slot)
        code, res = self.set_enchant(it, slot, opt)
        self.assertEqual(code, 200, res)
        ed = it["EnchantData"][slot]
        self.assertEqual((ed["MaterialKey"], ed["StatModKey"], ed["Tier"], ed["Value"]), opt)
        self.assertEqual(ed["RecipeType"], gamedata.RECIPE_TYPE[mt])
        self.assertEqual(GD().validate_enchant(slot, it["ItemKey"], ed), [])
        idx = gamedata.COUNT_INDEX[mt]
        self.assertEqual(it["EnchantCount"][idx], before["EnchantCount"][idx] + 1)
        fld = gamedata.COUNT_FIELD[mt]
        self.assertEqual(it[fld], before.get(fld, 0) + 1)
        self.save_and_check(allowed=["player.itemSaveDatas[%d]" % self.item_index(it)])

    def test_set_enchant_limpar_nao_desloca(self):
        it, slot = self.slot_target(filled=True, keyless=True)
        mt = gamedata.SLOT_MATERIAL_TYPE[slot]
        before = copy.deepcopy(it)
        self.ok("POST", "/api/set_enchant", {"uniqueId": str(it["UniqueId"]), "slot": slot, "clear": True})
        self.assertEqual(_core(it["EnchantData"][slot]), (0,) * 7)
        for i, ed in enumerate(it["EnchantData"]):
            if i != slot:
                self.assertEqual(ed, before["EnchantData"][i])
        idx = gamedata.COUNT_INDEX[mt]
        self.assertEqual(it["EnchantCount"][idx], before["EnchantCount"][idx] - 1)
        fld = gamedata.COUNT_FIELD[mt]
        self.assertEqual(it.get(fld), before.get(fld))  # Extracao nao conta aplicacao
        self.save_and_check(allowed=["player.itemSaveDatas[%d]" % self.item_index(it)])

    def test_set_enchant_preserva_enchant_version(self):
        """P1-4: slot alterado recebe a versao do save; limpar mantem a chave."""
        it, slot = self.slot_target(filled=False)
        it["EnchantData"][slot]["EnchantVersion"] = None  # como o jogo grava
        self.assertEqual(self.set_enchant(it, slot, _option(it["ItemKey"], slot))[0], 200)
        self.assertEqual(it["EnchantData"][slot].get("EnchantVersion"), self.save.account.get("version"))
        it2, slot2 = self.slot_target(filled=True)
        it2["EnchantData"][slot2]["EnchantVersion"] = "1.2.3"
        self.ok("POST", "/api/set_enchant", {"uniqueId": str(it2["UniqueId"]), "slot": slot2, "clear": True})
        self.assertIn("EnchantVersion", it2["EnchantData"][slot2])

    def test_set_enchant_invalido_nao_muta(self):
        """P2-1: erro 400 nao deixa o item alterado."""
        gd = GD()
        it = next((it for it in self.save.player["itemSaveDatas"]
                   if gd.gear_group(it["ItemKey"]) and len(it.get("EnchantData", [])) < 6
                   and not gd.slot_allowed(it["ItemKey"], 5)), None)
        if it is None:
            self.skipTest("nenhum item com EnchantData curto")
        before = copy.deepcopy(it)
        code, _res = self.api("POST", "/api/set_enchant", {"uniqueId": str(it["UniqueId"]), "slot": 5,
                                                           "materialKey": 1, "statModKey": 1, "tier": 1, "value": 1})
        self.assertEqual(code, 400)
        self.assertEqual(it, before)

    # ---------- auto-build ----------
    def test_auto_build(self):
        lens = {id(it): len(it.get("EnchantData", [])) for it in self.save.player["itemSaveDatas"]}
        res = self.ok("POST", "/api/auto_build", {"mode": "balanced", "overwrite": True})
        self.assertTrue(res.get("ok"))
        gd = GD()
        idx = set()
        for _h, it in self.equipped_items():
            idx.add(self.item_index(it))
            for i, ed in enumerate(it.get("EnchantData", [])[:6]):
                if gd.slot_allowed(it["ItemKey"], i):
                    self.assertEqual(gd.validate_enchant(i, it["ItemKey"], ed), [], (it["ItemKey"], i))
            # P3-1: so completa ate a grade, nunca alem
            self.assertEqual(len(it["EnchantData"]), max(lens[id(it)], gd.enchant_len(it["ItemKey"])))
        self.save_and_check(allowed=["player.itemSaveDatas[%d]" % i for i in sorted(idx)])

    def test_set_enchant_item_fora_de_gear(self):
        """Invariante 4: so encanta item que existe em GearInfoData."""
        it = next((it for it in self.save.player["itemSaveDatas"] if str(it["ItemKey"]) not in GD().gear), None)
        if it is None:
            self.skipTest("todo item do save e equipamento")
        before = copy.deepcopy(it)
        code, _res = self.api("POST", "/api/set_enchant", {"uniqueId": str(it["UniqueId"]), "slot": 0,
                                                           "materialKey": 119001, "statModKey": 103401,
                                                           "tier": 10, "value": 160})
        self.assertEqual(code, 400)
        self.assertEqual(it, before)

    def test_auto_build_nao_reescreve_slot_igual(self):
        """P1-3: so os 7 campos contam; slot igual nao e regravado nem contado."""
        self.ok("POST", "/api/auto_build", {"mode": "balanced", "overwrite": True})
        # o jogo regrava todo slot com "EnchantVersion": null
        for _h, it in self.equipped_items():
            for ed in it.get("EnchantData", []):
                ed.setdefault("EnchantVersion", None)
        before = copy.deepcopy(self.save.player["itemSaveDatas"])
        res = self.ok("POST", "/api/auto_build", {"mode": "balanced", "overwrite": True})
        self.assertEqual(res["slots"], 0)
        self.assertEqual(self.save.player["itemSaveDatas"], before)

    # ---------- skills ----------
    def test_set_skills(self):
        self.ok("POST", "/api/set_skills", {"mode": "balanced"})
        for h in self.save.player["heroSaveDatas"]:
            self.assertEqual(len(h["equippedSKillKey"]), 3)
        self.save_and_check(allowed=["player.heroSaveDatas"])

    # ---------- heroi ----------
    def test_set_hero(self):
        h = self.save.player["heroSaveDatas"][0]
        self.ok("POST", "/api/set_hero", {"heroKey": h["heroKey"], "level": h["HeroLevel"],
                                          "abilityPoint": h["AbilityPoint"], "exp": h["HeroExp"]})
        self.save_and_check(allowed=())
        self.ok("POST", "/api/set_hero", {"heroKey": h["heroKey"], "level": 100, "exp": 0})
        self.assertEqual((h["HeroLevel"], h["HeroExp"]), (100, 0.0))
        self.assertIsInstance(h["HeroExp"], float)

    def test_set_hero_limites_do_jogo(self):
        """P1-5/P2-4: nivel 1..101, EXP abaixo do necessario e so abaixo do maximo, AP estrito."""
        h = self.save.player["heroSaveDatas"][0]
        before = copy.deepcopy(h)
        key = h["heroKey"]
        lv_max = GD().hero_level_max()
        cap = GD().hero_exp_cap(lv_max - 1)
        for body in ({"level": lv_max + 1}, {"level": 0},
                     {"level": lv_max - 1, "exp": cap},                      # EXP tem de ficar < cap
                     {"level": lv_max - 1},                                  # EXP atual nao cabe no nivel
                     {"level": lv_max, "exp": float(h["HeroExp"]) + 1},     # no maximo, EXP so exibicao
                     {"abilityPoint": max(0, h["HeroLevel"] - h["AllocatedHeroAbilityPoint"]) + 1}):
            body["heroKey"] = key
            code, res = self.api("POST", "/api/set_hero", body)
            self.assertEqual(code, 400, (body, res))
        self.assertEqual(h, before)
        h["IsUnLock"] = False
        self.assertEqual(self.api("POST", "/api/set_hero", {"heroKey": key, "level": 50, "exp": 0})[0], 400)

    # ---------- moeda ----------
    def test_set_currency(self):
        cur = self.save.player["currenySaveDatas"][0]
        self.ok("POST", "/api/set_currency", {"key": cur["Key"], "quantity": cur["Quantity"] + 1})
        self.assertEqual(self.api("POST", "/api/set_currency", {"key": 999999, "quantity": 5})[0], 404)
        self.assertEqual(self.api("POST", "/api/set_currency", {"key": cur["Key"], "quantity": 10 ** 13 + 1})[0], 400)
        self.save_and_check(allowed=["player.currenySaveDatas[0].Quantity"])

    # ---------- pets ----------
    def _pets(self):
        arranged = (self.save.player.get("commonSaveData") or {}).get("ArrangedPetKey")
        return self.save.player["PetSaveData"], arranged

    def test_set_pet(self):
        pets, arranged = self._pets()
        pet = next((p for p in pets if p["PetKey"] != arranged and p["PetKey"] < 6000), None)
        if pet is None:
            self.skipTest("sem pet de abate fora do equipado")
        self.ok("POST", "/api/set_pet", {"petKey": pet["PetKey"], "unlock": False})
        self.assertFalse(pet["IsUnlock"])
        self.ok("POST", "/api/set_pet", {"petKey": pet["PetKey"], "unlock": True})
        self.assertTrue(pet["IsUnlock"])
        if arranged:
            self.assertEqual(self.api("POST", "/api/set_pet", {"petKey": arranged, "unlock": False})[0], 400)
        self.save_and_check(allowed=["player.PetSaveData"])

    @unittest.expectedFailure  # P1-7: o editor trava/destrava pet de DLC sem checar posse
    def test_set_pet_dlc_so_exibicao(self):
        pets, arranged = self._pets()
        pet = next((p for p in pets if p["PetKey"] != arranged and p["PetKey"] >= 6000), None)
        if pet is None:
            self.skipTest("sem pet de DLC no save")
        for unlock in (False, True):
            code, _res = self.api("POST", "/api/set_pet", {"petKey": pet["PetKey"], "unlock": unlock})
            self.assertEqual(code, 400)

    # ---------- runas ----------
    def test_max_runes(self):
        self.ok("POST", "/api/max_runes", {})
        gd = GD()
        for r in self.save.player["RuneSaveData"]:
            mx = gd.rune_max_level(r["RuneKey"])
            if mx is not None:
                self.assertLessEqual(r["Level"], mx)
        self.save_and_check(allowed=["player.RuneSaveData"])

    # ---------- cubo ----------
    def test_set_cube(self):
        cube = self.save.player["cubeSaveLevelData"]
        self.ok("POST", "/api/set_cube", {"level": cube["Level"]})
        self.save_and_check(allowed=())

    def test_set_cube_limites_do_jogo(self):
        """P1-6: nivel 1..100; Exp < necessario do nivel; no maximo, o valor que o jogo grava."""
        cube = self.save.player["cubeSaveLevelData"]
        gd = GD()
        mx = gd.cube_level_max()
        for body in ({"level": mx + 1}, {"level": 0}, {"level": mx - 1, "exp": gd.cube_exp_cap(mx - 1)}):
            self.assertEqual(self.api("POST", "/api/set_cube", body)[0], 400, body)
        self.ok("POST", "/api/set_cube", {"level": 50})
        self.assertEqual(cube["Level"], 50)
        self.assertLess(cube["Exp"], gd.cube_exp_cap(50))
        self.assertIsInstance(cube["Exp"], float)
        self.ok("POST", "/api/set_cube", {"level": mx})
        self.assertEqual((cube["Level"], cube["Exp"]), (mx, 1e9))  # float(999999999) = 1e9


if __name__ == "__main__":
    unittest.main()
