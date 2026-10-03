"""Itens fora dos herois: mochila, bau e Trade Ship (docs/ROADMAP.md, item 3)."""
from tests.support import SaveCase, call, server

PLACES = ("mochila", "baú", "Trade Ship", "fora dos slots")


class BagTest(SaveCase):
    def bag(self):
        return self.ok("GET", "/api/items")["items"]

    def test_lista_so_equipamento_nao_equipado_com_o_local(self):
        items = self.bag()
        self.assertTrue(items)
        equipped = {str(it["UniqueId"]) for _h, it in self.equipped_items()}
        gear = {str(it["UniqueId"]) for it in self.save.player["itemSaveDatas"] if str(it["ItemKey"]) in server.GD.gear}
        self.assertEqual({it["uniqueId"] for it in items}, gear - equipped)
        for it in items:
            self.assertIn(it["where"], PLACES)

    def test_encantar_item_da_mochila_so_muda_ele(self):
        gd = server.GD
        it, slot, opt = None, None, None
        for row in self.bag():
            if row["readOnly"]:
                continue
            for e in row["enchants"]:
                if e["allowed"]:
                    mt = gd.slot_material_type(e["slot"])
                    for mk in gd.materials_by_type[mt]:
                        for o in gd.stat_options(mk, row["group"]):
                            t = o["tiers"][0]
                            if not e["filled"] or (e["statModKey"], e["tier"]) != (o["statModKey"], t["tier"]):
                                it, slot, opt = row, e["slot"], (int(mk), o["statModKey"], t["tier"], t["min"])
                                break
                        if it:
                            break
                if it:
                    break
            if it:
                break
        if it is None:
            self.skipTest("nenhum item editavel fora dos herois")
        mk, smk, tier, value = opt
        res = self.ok("POST", "/api/set_enchant", {"uniqueId": it["uniqueId"], "slot": slot, "materialKey": mk,
                                                   "statModKey": smk, "tier": tier, "value": value})
        self.assertTrue(res["enchants"][slot]["filled"])
        idx = next(i for i, x in enumerate(self.save.player["itemSaveDatas"]) if str(x["UniqueId"]) == it["uniqueId"])
        self.save_and_check(allowed=["player.itemSaveDatas[%d]" % idx])

    def test_item_no_trade_ship_e_somente_leitura(self):
        row = next(r for r in self.bag() if not r["readOnly"])
        ship = self.save.player.setdefault("remakeTradingStashSaveDatas", [])
        ship.append({"Index": len(ship), "ItemUniqueId": int(row["uniqueId"]), "IsUnLock": True, "Quantity": 1})
        moved = next(r for r in self.bag() if r["uniqueId"] == row["uniqueId"])
        self.assertTrue(moved["readOnly"])
        code, _res = call("POST", "/api/set_enchant", {"uniqueId": row["uniqueId"], "slot": 0, "clear": True})
        self.assertEqual(code, 400)
