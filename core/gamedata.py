"""
Base de conhecimento do jogo (tabelas CSV + nomes + enums + icones) e a logica de
validacao de encantamentos.

Cadeia de um encantamento (EnchantData):
  slot (indice 0..5) -> tipo: DECORATION(0,1) / ENGRAVING(2,3) / INSCRIPTION(4,5)
  material (MaterialKey) -> MaterialInfoData -> MATERIALTYPE (deve casar com o slot) + StatModGroupKey
  StatModGroupKey + GearGroup do item (WEAPON/ARMOR/ACCESSORY, +COMMON) -> StatModGroupInfoData
      -> opcoes (StatModKey, MinTier..MaxTier)
  StatModKey + Tier -> StatModInfoData -> STATTYPE, MODTYPE, MinValue, MaxValue, Interval
  Value escolhido em [MinValue, MaxValue] com passo Interval.
"""
import csv
import json
import os

# indice do slot -> tipo de material exigido
SLOT_MATERIAL_TYPE = ["DECORATION", "DECORATION", "ENGRAVING", "ENGRAVING", "INSCRIPTION", "INSCRIPTION"]
# tipo de material -> RecipeType (ERecipeType)
RECIPE_TYPE = {"DECORATION": 3, "ENGRAVING": 4, "INSCRIPTION": 5}


def _read_csv(path):
    with open(path, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


# tipo de material -> campo de contador acumulado no itemSaveData
COUNT_FIELD = {
    "DECORATION": "DecorationAppliedTotalCount",
    "ENGRAVING": "EngravingAppliedTotalCount",
    "INSCRIPTION": "InscriptionAppliedTotalCount",
}
# tipo de material -> indice em EnchantCount[3]
COUNT_INDEX = {"DECORATION": 0, "ENGRAVING": 1, "INSCRIPTION": 2}


class GameData:
    def __init__(self, data_dir):
        self.dir = data_dir
        t = os.path.join(data_dir, "tables")
        self.materials = {r["ItemKey"]: r for r in _read_csv(os.path.join(t, "MaterialInfoData.csv"))}
        self.gear = {r["GearKey"]: r for r in _read_csv(os.path.join(t, "GearInfoData.csv"))}
        # grupo -> linhas
        self.groups = {}
        for r in _read_csv(os.path.join(t, "StatModGroupInfoData.csv")):
            self.groups.setdefault(r["StatModGroupKey"], []).append(r)
        # (StatModKey, Tier) -> linha
        self.statmod = {}
        for r in _read_csv(os.path.join(t, "StatModInfoData.csv")):
            self.statmod[(r["StatModKey"], r["Tier"])] = r
        # materiais agrupados por tipo
        self.materials_by_type = {"DECORATION": [], "ENGRAVING": [], "INSCRIPTION": []}
        for k, r in self.materials.items():
            mt = r["MATERIALTYPE"]
            if mt in self.materials_by_type:
                self.materials_by_type[mt].append(k)
        # nomes e icones
        self.names = {
            "en": json.load(open(os.path.join(data_dir, "names_en.json"), encoding="utf-8")),
            "pt": json.load(open(os.path.join(data_dir, "names_pt.json"), encoding="utf-8")),
        }
        self.icon_map = json.load(open(os.path.join(data_dir, "icon_map.json"), encoding="utf-8"))
        self._named = set(self.names["en"])  # keys que tem nome/icone proprio (modelos base)
        self.strings = {
            "en": json.load(open(os.path.join(data_dir, "strings_en.json"), encoding="utf-8")),
            "pt": json.load(open(os.path.join(data_dir, "strings_pt.json"), encoding="utf-8")),
        }
        enums = json.load(open(os.path.join(data_dir, "enums.json"), encoding="utf-8"))
        self.stat_name_to_id = {v: int(k) for k, v in enums["StatType"].items()}
        self.modtype_name_to_id = {v: int(k) for k, v in enums["MODTYPE"].items()}
        self.egrade = enums["EGradeType"]  # id(str) -> nome
        self.grades_by_name = {r["GRADE"]: r for r in _read_csv(os.path.join(t, "GradeInfoData.csv"))}
        self.hero_info = {r["HeroKey"]: r for r in _read_csv(os.path.join(t, "HeroInfoData.csv"))}
        self.rune_info = {r["RuneKey"]: r for r in _read_csv(os.path.join(t, "RuneInfoData.csv"))}
        self.currency_info = {r["CurrencyKey"]: r for r in _read_csv(os.path.join(t, "CurrencyInfoData.csv"))}

    # ---- herois ----
    def hero_name(self, herokey, locale="en"):
        return (self.strings.get(locale, {}).get("HeroName_%s" % herokey)
                or self.strings["en"].get("HeroName_%s" % herokey)
                or self.hero_info.get(str(herokey), {}).get("ClassType")
                or ("Herói %s" % herokey))

    def hero_class(self, herokey):
        return self.hero_info.get(str(herokey), {}).get("ClassType", "")

    def skill_name(self, skillkey, locale="en"):
        """Nome da skill; x0001 (ataque-base) nao tem nome proprio."""
        s = str(skillkey)
        if s.endswith("001") and len(s) == 5:  # ex 10001, 20001 -> ataque base
            return "Ataque base"
        return self.string("SkillName_%s" % skillkey, locale, "Skill %s" % skillkey)

    # ---- strings localizadas genericas ----
    def string(self, key, locale="en", fallback=None):
        return (self.strings.get(locale, {}).get(key)
                or self.strings["en"].get(key) or fallback)

    def currency_name(self, key, locale="en"):
        return self.string("CurrencyName_%s" % key, locale, "Moeda %s" % key)

    def pet_name(self, key, locale="en"):
        return self.string("PetName_%s" % key, locale, "Pet %s" % key)

    # ---- runas ----
    def rune_max_level(self, rune_key):
        """Nivel maximo da runa pela tabela do jogo (None se desconhecido)."""
        r = self.rune_info.get(str(rune_key))
        if not r:
            return None
        try:
            return int(r["MaxLevel"])
        except (KeyError, TypeError, ValueError):
            return None

    # ---- grade e slots ----
    def grade_id(self, itemkey):
        s = str(itemkey)
        return int(s[2]) if len(s) == 6 and s.isdigit() and int(s) >= 300000 else None

    def grade_name(self, itemkey):
        g = self.grade_id(itemkey)
        return self.egrade.get(str(g)) if g is not None else None

    def max_slots(self, itemkey):
        """Quantos slots de cada tipo a grade do item permite."""
        r = self.grades_by_name.get(self.grade_name(itemkey))
        if not r:
            return {"DECORATION": 2, "ENGRAVING": 2, "INSCRIPTION": 2}  # fallback permissivo
        return {"DECORATION": int(r["ExtraSlotAmount_Decoration"]),
                "ENGRAVING": int(r["ExtraSlotAmount_Engraving"]),
                "INSCRIPTION": int(r["ExtraSlotAmount_Inscription"])}

    def slot_allowed(self, itemkey, slot_index):
        mt = SLOT_MATERIAL_TYPE[slot_index]
        return (slot_index % 2) < self.max_slots(itemkey)[mt]

    # ---- contadores (corrige o bug: o jogo usa EnchantCount p/ ATIVAR o efeito) ----
    def recount_enchants(self, item):
        """Recalcula EnchantCount[3] = nº de slots preenchidos [deco, eng, insc]."""
        ed = item.get("EnchantData", [])
        f = lambda i: 1 if i < len(ed) and ed[i].get("MaterialKey", 0) != 0 else 0
        item["EnchantCount"] = [f(0) + f(1), f(2) + f(3), f(4) + f(5)]

    def bump_applied(self, item, slot_index):
        """Incrementa o contador acumulado (AppliedTotalCount) do tipo do slot."""
        fld = COUNT_FIELD[SLOT_MATERIAL_TYPE[slot_index]]
        item[fld] = int(item.get(fld, 0)) + 1

    # ---- resolucao item-instancia -> modelo base (que tem nome/icone) ----
    def base_key(self, itemkey):
        """Itens no save sao instancias (com grade); nome/icone ficam no 'modelo base'.
        Ex: 604111 (amulet grade 4, modelo 11) -> 600011. Materiais com sufixo 900 -> base."""
        s = str(itemkey)
        if s in self._named:
            return s
        if len(s) == 9 and s.endswith("900") and s[:6] in self._named:  # material empilhado
            return s[:6]
        k = int(itemkey)
        modelo = (k % 10000 // 10) % 100
        b = str((k // 10000) * 10000 + modelo)
        return b if b in self._named else s

    # ---- lookups basicos ----
    def name(self, itemkey, locale="en"):
        bk = self.base_key(itemkey)
        return (self.names.get(locale, {}).get(bk) or self.names["en"].get(bk) or f"#{itemkey}")

    def icon_file(self, itemkey):
        return self.icon_map.get(self.base_key(itemkey))

    def has_icon(self, itemkey):
        return self.base_key(itemkey) in self.icon_map

    def gear_group(self, itemkey):
        d = int(itemkey) // 100000
        return {3: "WEAPON", 4: "WEAPON", 5: "ARMOR", 6: "ACCESSORY"}.get(d)

    def slot_material_type(self, slot_index):
        return SLOT_MATERIAL_TYPE[slot_index]

    # nome legivel de um StatType (ex PhysicalDamagePercent -> "Physical Damage %")
    @staticmethod
    def pretty_stat(stattype_name):
        import re
        words = re.findall(r"[A-Z][a-z0-9]*", stattype_name or "")
        s = " ".join(words) if words else (stattype_name or "")
        return s.replace(" Percent", " %")

    # ---- opcoes de stat para um material num item ----
    def stat_options(self, material_key, gear_group):
        """Retorna as opcoes de stat que um material pode dar num item daquele gear_group.
        Cada opcao: {statModKey, statType, statTypeId, statName, modType, modTypeId, tiers:[...]}."""
        mat = self.materials.get(str(material_key))
        if not mat:
            return []
        rows = self.groups.get(mat["StatModGroupKey"], [])
        allowed = {gear_group, "COMMON"}
        opts = []
        for row in rows:
            if row["GearGroup"] not in allowed:
                continue
            tiers = []
            for tier in range(int(row["MinTier"]), int(row["MaxTier"]) + 1):
                si = self.statmod.get((row["StatModKey"], str(tier)))
                if si:
                    tiers.append({
                        "tier": tier,
                        "min": int(si["MinValue"]),
                        "max": int(si["MaxValue"]),
                        "interval": int(si["Interval"]),
                        "statType": si["STATTYPE"],
                        "modType": si["MODTYPE"],
                    })
            if not tiers:
                continue
            st = tiers[0]["statType"]
            mtp = tiers[0]["modType"]
            opts.append({
                "statModKey": int(row["StatModKey"]),
                "gearGroup": row["GearGroup"],
                "statType": st,
                "statTypeId": self.stat_name_to_id.get(st, 0),
                "statName": self.pretty_stat(st),
                "modType": mtp,
                "modTypeId": self.modtype_name_to_id.get(mtp, 0),
                "tiers": tiers,
            })
        return opts

    def stat_range(self, statmodkey, tier):
        si = self.statmod.get((str(statmodkey), str(tier)))
        if not si:
            return None
        return {"min": int(si["MinValue"]), "max": int(si["MaxValue"]), "interval": int(si["Interval"]),
                "statType": si["STATTYPE"], "modType": si["MODTYPE"]}

    # ---- construir / validar um EnchantData ----
    def build_enchant(self, slot_index, material_key, statmodkey, tier, value):
        si = self.statmod.get((str(statmodkey), str(tier)))
        if not si:
            raise ValueError("StatModKey/Tier inexistente")
        mtype = SLOT_MATERIAL_TYPE[slot_index]
        return {
            "StatModKey": int(statmodkey),
            "Tier": int(tier),
            "Value": int(value),
            "RecipeType": RECIPE_TYPE[mtype],
            "ModType": self.modtype_name_to_id.get(si["MODTYPE"], 0),
            "MaterialKey": int(material_key),
            "StatType": self.stat_name_to_id.get(si["STATTYPE"], 0),
        }

    def empty_enchant(self):
        return {"StatModKey": 0, "Tier": 0, "Value": 0, "RecipeType": 0,
                "ModType": 0, "MaterialKey": 0, "StatType": 0}

    def validate_enchant(self, slot_index, item_key, ed):
        """Valida coerencia de um EnchantData (nao-vazio). Retorna lista de erros (vazia = ok)."""
        errs = []
        if not ed or ed.get("MaterialKey", 0) == 0:
            return errs  # slot vazio e valido
        mk = str(ed["MaterialKey"])
        mat = self.materials.get(mk)
        if not mat:
            return [f"MaterialKey {mk} desconhecido"]
        want = SLOT_MATERIAL_TYPE[slot_index]
        if mat["MATERIALTYPE"] != want:
            errs.append(f"material e {mat['MATERIALTYPE']}, mas o slot e {want}")
        gg = self.gear_group(item_key)
        opt = next((o for o in self.stat_options(mk, gg) if o["statModKey"] == ed.get("StatModKey")), None)
        if not opt:
            errs.append("StatModKey nao pertence ao material/grupo do item")
            return errs
        tier = next((t for t in opt["tiers"] if t["tier"] == ed.get("Tier")), None)
        if not tier:
            errs.append(f"Tier {ed.get('Tier')} invalido para esse stat")
            return errs
        v = ed.get("Value", 0)
        if not (tier["min"] <= v <= tier["max"]):
            errs.append(f"Value {v} fora do range [{tier['min']},{tier['max']}]")
        elif tier["interval"] and (v - tier["min"]) % tier["interval"] != 0:
            errs.append(f"Value {v} nao respeita o passo {tier['interval']}")
        return errs

    def describe_enchant(self, ed, locale="en", enums=None):
        """Texto curto legivel de um EnchantData para a UI."""
        if not ed or ed.get("MaterialKey", 0) == 0:
            return None
        si = self.statmod.get((str(ed.get("StatModKey")), str(ed.get("Tier"))))
        stat = self.pretty_stat(si["STATTYPE"]) if si else f"stat#{ed.get('StatType')}"
        val = ed.get("Value", 0)
        return {
            "material": self.name(ed.get("MaterialKey"), locale),
            "materialKey": ed.get("MaterialKey"),
            "stat": stat,
            "tier": ed.get("Tier"),
            "value": val,
            "valuePct": round(val / 10.0, 1),  # heuristica de exibicao
        }
