"""Dados promovidos da 1.2.8 (data/) e regras derivadas deles; nao precisa de save."""
import os
import unittest

from core import gamedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GD = gamedata.GameData(os.path.join(ROOT, "data"))


class GameDataTest(unittest.TestCase):
    def test_versao_dos_dados(self):
        self.assertEqual(GD.version, "1.2.8")

    def test_limites_do_jogo(self):
        self.assertEqual(GD.hero_level_max(), 101)
        self.assertIsNone(GD.hero_exp_cap(101))
        self.assertEqual(GD.cube_level_max(), 100)
        self.assertEqual(GD.cube_exp_cap(100), 999999999.0)

    def test_tamanho_do_enchantdata_pela_grade(self):
        lens = {GD.grade_name(k): GD.enchant_len(k) for k in GD.gear}
        self.assertEqual((lens["COMMON"], lens["RARE"], lens["IMMORTAL"], lens["ARCANA"]), (0, 2, 4, 6))
        self.assertTrue(set(lens.values()) <= {0, 2, 4, 6})

    def test_item_fora_de_gear_e_item_steam_sao_somente_leitura(self):
        self.assertIsNone(GD.enchantable(604111))
        self.assertIsNotNone(GD.enchantable(120001))     # material
        self.assertIsNotNone(GD.enchantable(604111900))  # ItemKey de item Steam
        self.assertEqual(GD.max_slots(999999), dict.fromkeys(gamedata.TYPES, 0))  # sem fallback
        self.assertIsNone(GD.gear_group(999999))

    def test_enchant_fields_recusa_o_que_o_jogo_nao_gera(self):
        mk, o = next((mk, o) for mk in GD.materials_by_type["DECORATION"]
                     for o in GD.stat_options(mk, "ACCESSORY"))
        t = o["tiers"][-1]
        ok = GD.enchant_fields(0, 604111, int(mk), o["statModKey"], t["tier"], t["max"])
        self.assertEqual((ok["RecipeType"], ok["Value"]), (3, t["max"]))
        smk = o["statModKey"]
        for args in ((2, 604111, int(mk), smk, t["tier"], t["max"]),      # decoracao no slot de gravacao
                     (0, 604111, int(mk), smk, t["tier"], t["max"] + 1),  # fora da faixa
                     (0, 604111, int(mk), smk, 99, t["max"]),             # tier inexistente
                     (0, 120001, int(mk), smk, t["tier"], t["max"])):     # material nao e equipamento
            with self.assertRaises(ValueError):
                GD.enchant_fields(*args)

    def test_runas_de_bau_e_slot_de_skill(self):
        chest = {k for k in GD.rune_info if GD.rune_is_chest(k)}
        self.assertTrue(chest)
        self.assertFalse(GD.rune_is_chest(27))
        self.assertEqual(GD.rune_keys_with_stat("UnlockSkillSlotCount"), {"27"})

    def test_pets_dlc(self):
        self.assertEqual({k for k in GD.pet_info if GD.pet_is_dlc(k)}, {"6001", "6002", "6003"})

    def test_nomes_e_icones_via_iteminfodata(self):
        self.assertEqual(GD.name(910051, "en"), "Normal Monster Box 2")  # nome literal na tabela
        self.assertEqual(GD.icon_key(604111), "600011")
        self.assertEqual(GD.difficulties()[0], "NORMAL")


if __name__ == "__main__":
    unittest.main()
