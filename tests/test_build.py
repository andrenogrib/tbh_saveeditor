"""Resumo da build por heroi: soma dos encantamentos dos itens equipados (docs/ROADMAP.md, item 4)."""
from tests.support import SaveCase, server


class BuildSummaryTest(SaveCase):
    def filled_slots(self, h):
        by_uid = {str(it["UniqueId"]): it for it in self.save.player["itemSaveDatas"]}
        out = []
        for u in h["equippedItemIds"]:
            it = by_uid.get(str(u))
            for i, ed in enumerate((it or {}).get("EnchantData", [])[:6]):
                if ed.get("MaterialKey") and server.GD.slot_allowed(it["ItemKey"], i):
                    out.append(ed)
        return out

    def test_soma_os_slots_ocupados_de_cada_heroi(self):
        for hp in self.ok("GET", "/api/heroes")["heroes"]:
            h = next(x for x in self.save.player["heroSaveDatas"] if x["heroKey"] == hp["heroKey"])
            filled = self.filled_slots(h)
            self.assertEqual(sum(b["slots"] for b in hp["build"]), len(filled))
            self.assertEqual(sum(b["total"] for b in hp["build"]), sum(ed["Value"] for ed in filled))
            self.assertEqual(len({(b["stat"], b["modType"]) for b in hp["build"]}), len(hp["build"]))

    def test_acompanha_o_auto_build(self):
        h = self.save.player["heroSaveDatas"][0]
        before = next(x for x in self.ok("GET", "/api/heroes")["heroes"] if x["heroKey"] == h["heroKey"])["build"]
        res = self.ok("POST", "/api/auto_build", {"mode": "survival", "overwrite": True, "heroKey": h["heroKey"]})
        after = next(x for x in res["heroes"] if x["heroKey"] == h["heroKey"])["build"]
        if res["slots"]:
            self.assertNotEqual(before, after)
        self.assertEqual(sum(b["slots"] for b in after), len(self.filled_slots(h)))
