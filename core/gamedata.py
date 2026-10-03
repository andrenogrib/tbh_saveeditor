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
TYPES = ("DECORATION", "ENGRAVING", "INSCRIPTION")
# os 7 campos de um encantamento; o resto do dict (ex. EnchantVersion) e preservado
ENCHANT_FIELDS = ("StatModKey", "Tier", "Value", "RecipeType", "ModType", "MaterialKey", "StatType")
# ItemKey acima de 9.999.999 e id de item da Steam: o editor so le (P3-8)
STEAM_ITEM_KEY_MIN = 10000000


def empty_fields():
    return dict.fromkeys(ENCHANT_FIELDS, 0)


def is_filled(ed):
    """Slot ocupado: o jogo aplica o efeito de todo slot com Tier > 0."""
    return bool(ed) and (ed.get("MaterialKey", 0) != 0 or ed.get("Tier", 0) > 0)


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
        self.grades_by_name = {r["GRADE"]: r for r in _read_csv(os.path.join(t, "GradeInfoData.csv"))}
        self.hero_info = {r["HeroKey"]: r for r in _read_csv(os.path.join(t, "HeroInfoData.csv"))}
        self.rune_info = {r["RuneKey"]: r for r in _read_csv(os.path.join(t, "RuneInfoData.csv"))}
        self.currency_info = {r["CurrencyKey"]: r for r in _read_csv(os.path.join(t, "CurrencyInfoData.csv"))}
        self.item_info = {r["ItemKey"]: r for r in _read_csv(os.path.join(t, "ItemInfoData.csv"))}
        # nivel -> XP para subir (heroi e cubo); limites reais do jogo
        self.level_exp = {int(r["Level"]): float(r["ExpForLevelUp"])
                          for r in _read_csv(os.path.join(t, "LevelInfoData.csv"))}
        self.cube_exp = {int(r["Level"]): float(r["ExpForLevelUp"])
                         for r in _read_csv(os.path.join(t, "CubeLevelInfoData.csv"))}
        self.pet_info = {r["PetKey"]: r for r in _read_csv(os.path.join(t, "PetInfoData.csv"))}
        self.skill_info = {r["SkillKey"]: r for r in _read_csv(os.path.join(t, "SkillInfoData.csv"))}
        # (heroKey, skillKey) -> AttributeKey da skill ativa (aprendida = atributo com Level >= 1)
        self.active_skill_attr = {(int(r["HeroKey"]), int(r["Value"])): int(r["AttributeKey"])
                                  for r in _read_csv(os.path.join(t, "AttributeInfoData.csv"))
                                  if r["ATTRIBUTETYPE"] == "ACTIVESKILL"}
        self.rune_stats = {}  # LevelDataKey -> STATTYPEs dos niveis da runa
        for r in _read_csv(os.path.join(t, "RuneLevelInfoData.csv")):
            self.rune_stats.setdefault(r["LevelKey"], set()).add(r["STATTYPE"])
        self.stage_info = {r["StageKey"]: r for r in _read_csv(os.path.join(t, "StageInfoData.csv"))}
        self.plague_max = max(int(r["PlagueIntensity"])
                              for r in _read_csv(os.path.join(t, "PlagueIntensityInfoData.csv")))
        # versao do jogo de onde data/ saiu (data/VERSION: "<versao> build=...")
        vp = os.path.join(data_dir, "VERSION")
        self.version = open(vp, encoding="utf-8").read().split()[0] if os.path.exists(vp) else None

    # ---- herois ----
    def hero_name(self, herokey, locale="en"):
        return (self.strings.get(locale, {}).get("HeroName_%s" % herokey)
                or self.strings["en"].get("HeroName_%s" % herokey)
                or self.hero_info.get(str(herokey), {}).get("ClassType")
                or ("Herói %s" % herokey))

    def hero_class(self, herokey):
        return self.hero_info.get(str(herokey), {}).get("ClassType", "")

    def skill_name(self, skillkey, locale="en"):
        """Nome da skill (SkillName_<key>; o ataque-base x0001 tambem tem o seu)."""
        s = str(skillkey)
        base = s.endswith("001") and len(s) == 5  # ex 10001, 20001 -> ataque base
        return self.string("SkillName_%s" % skillkey, locale, "Ataque base" if base else "Skill %s" % skillkey)

    # ---- strings localizadas genericas ----
    def string(self, key, locale="en", fallback=None):
        return (self.strings.get(locale, {}).get(key)
                or self.strings["en"].get(key) or fallback)

    def currency_name(self, key, locale="en"):
        return self.string("CurrencyName_%s" % key, locale, "Moeda %s" % key)

    def pet_name(self, key, locale="en"):
        return self.string("PetName_%s" % key, locale, "Pet %s" % key)

    # ---- limites do heroi e do cubo (LevelInfoData / CubeLevelInfoData) ----
    def hero_level_max(self):
        """O jogo leva o heroi ate max(LevelInfoData.Level)+1 (= 101 na 1.2.8) e nao corrige acima."""
        return max(self.level_exp) + 1

    def hero_exp_cap(self, level):
        """XP para sair do nivel (EXP valida < isso); None no nivel maximo."""
        return self.level_exp.get(int(level))

    def cube_level_max(self):
        return max(self.cube_exp)

    def cube_exp_cap(self, level):
        return self.cube_exp.get(int(level))

    def hero_base_skill(self, hero_key):
        v = self.hero_info.get(str(hero_key), {}).get("SkillKey")
        return int(v) if v else None

    # ---- pets ----
    def stage(self, stage_key, locale="en"):
        """Resumo de um estagio pela StageInfoData (nome localizado, tipo, ato, numero)."""
        r = self.stage_info.get(str(stage_key))
        if not r:
            return {"key": stage_key, "name": None}
        return {"key": stage_key, "name": self.string(r["StageNameKey"], locale, r["StageNameKey"]),
                "type": r["STAGETYPE"], "difficulty": r["STAGEDIFFICULITY"],
                "act": r["Act"], "no": r["StageNo"]}

    def difficulties(self):
        """Dificuldades na ordem em que aparecem pela StageKey (NORMAL, NIGHTMARE, ...)."""
        out = []
        for k in sorted(self.stage_info, key=int):
            d = self.stage_info[k]["STAGEDIFFICULITY"]
            if d not in out:
                out.append(d)
        return out

    def pet_is_dlc(self, pet_key):
        return self.pet_info.get(str(pet_key), {}).get("UnlockCondition") == "DLC"

    # ---- runas ----
    def rune_is_chest(self, rune_key):
        """Runa da familia bau (chance de drop, capacidade, auto-abertura, abrir todos)."""
        r = self.rune_info.get(str(rune_key)) or {}
        stats = self.rune_stats.get(r.get("LevelDataKey") or str(rune_key), ())
        return any("Chest" in s for s in stats)

    def rune_keys_with_stat(self, stattype):
        return {k for k, r in self.rune_info.items()
                if stattype in self.rune_stats.get(r.get("LevelDataKey") or k, ())}

    def rune_name(self, rune_key, locale="en"):
        nk = (self.rune_info.get(str(rune_key)) or {}).get("NameKey", "")
        return self.string(nk, locale, "Runa %s" % rune_key)

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
    def grade_name(self, itemkey):
        """Grade pela ItemInfoData (item fora da tabela = None)."""
        r = self.item_info.get(str(itemkey))
        return (r.get("GRADE") or None) if r else None

    def max_slots(self, itemkey):
        """Quantos slots de cada tipo a grade do item permite (grade desconhecida = nenhum)."""
        r = self.grades_by_name.get(self.grade_name(itemkey))
        if not r:
            return dict.fromkeys(TYPES, 0)
        return {"DECORATION": int(r["ExtraSlotAmount_Decoration"]),
                "ENGRAVING": int(r["ExtraSlotAmount_Engraving"]),
                "INSCRIPTION": int(r["ExtraSlotAmount_Inscription"])}

    def slot_allowed(self, itemkey, slot_index):
        if not 0 <= slot_index < len(SLOT_MATERIAL_TYPE):
            return False
        mt = SLOT_MATERIAL_TYPE[slot_index]
        return (slot_index % 2) < self.max_slots(itemkey)[mt]

    def enchant_len(self, itemkey):
        """Tamanho de EnchantData que o jogo grava para a grade do item (0/2/4/6)."""
        ms = self.max_slots(itemkey)
        return max([2 * (i + 1) for i, t in enumerate(TYPES) if ms[t] > 0] or [0])

    def enchantable(self, itemkey):
        """None se o editor pode encantar o item; senao o motivo (invariante 4, P3-8)."""
        try:
            k = int(itemkey)
        except (TypeError, ValueError):
            return "ItemKey inválido"
        if k >= STEAM_ITEM_KEY_MIN:
            return "item da Steam (ItemKey %s): somente leitura" % k
        if str(k) not in self.gear:
            return "item %s fora de GearInfoData" % k
        if self.grade_name(k) not in self.grades_by_name:
            return "grade do item %s desconhecida" % k
        return None

    # ---- contadores ----
    def recount_enchants(self, item):
        """EnchantCount[3] = slots ocupados por tipo [deco, eng, insc]. O jogo usa para achar
        slot livre, na UI e no mercado; nunca pode ficar menor que os slots ocupados."""
        ed = item.get("EnchantData") or []
        f = lambda i: 1 if i < len(ed) and is_filled(ed[i]) else 0
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
        n = self.names.get(locale, {}).get(bk) or self.names["en"].get(bk)
        if n:
            return n
        # sem nome pelo modelo base: NameKey de ItemInfoData (caixas trazem o nome literal)
        nk = (self.item_info.get(str(itemkey)) or {}).get("NameKey") or ""
        if nk.startswith("ItemName_"):
            k = nk[len("ItemName_"):]
            n = self.names.get(locale, {}).get(k) or self.names["en"].get(k)
        elif nk:
            n = self.string(nk, locale, nk)
        return n or f"#{itemkey}"

    def icon_key(self, itemkey):
        """Chave em icon_map para o item: modelo base ou o sufixo de ItemInfoData.IconPath."""
        bk = self.base_key(itemkey)
        if bk in self.icon_map:
            return bk
        ip = (self.item_info.get(str(itemkey)) or {}).get("IconPath") or ""
        k = ip.rsplit("_", 1)[-1]
        return k if k in self.icon_map else None

    def icon_file(self, itemkey):
        k = self.icon_key(itemkey)
        return self.icon_map.get(k) if k else None

    def has_icon(self, itemkey):
        return self.icon_key(itemkey) is not None

    def gear_group(self, itemkey):
        """WEAPON/ARMOR/ACCESSORY pela ItemInfoData (material, caixa ou fora da tabela = None)."""
        r = self.item_info.get(str(itemkey))
        return (r.get("GearGroup") or None) if r else None

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
            if st not in self.stat_name_to_id or mtp not in self.modtype_name_to_id:
                continue  # stat/modtype fora dos enums: nao oferecer (P2-5)
            opts.append({
                "statModKey": int(row["StatModKey"]),
                "gearGroup": row["GearGroup"],
                "statType": st,
                "statTypeId": self.stat_name_to_id[st],
                "statName": self.pretty_stat(st),
                "modType": mtp,
                "modTypeId": self.modtype_name_to_id[mtp],
                "tiers": tiers,
            })
        return opts

    def stat_range(self, statmodkey, tier):
        si = self.statmod.get((str(statmodkey), str(tier)))
        if not si:
            return None
        return {"min": int(si["MinValue"]), "max": int(si["MaxValue"]), "interval": int(si["Interval"]),
                "statType": si["STATTYPE"], "modType": si["MODTYPE"]}

    # ---- construir / validar / gravar um EnchantData ----
    def enchant_fields(self, slot_index, item_key, material_key, statmodkey, tier, value):
        """Os 7 campos de um encantamento que o jogo gera para esse slot do item.
        ValueError se a combinacao nao existe nas tabelas; nao mexe no item."""
        why = self.enchantable(item_key)
        if why:
            raise ValueError(why)
        if not self.slot_allowed(item_key, slot_index):
            raise ValueError("a grade %s do item não tem esse slot" % self.grade_name(item_key))
        si = self.statmod.get((str(statmodkey), str(tier)))
        if not si:
            raise ValueError("StatModKey/Tier inexistente")
        if si["STATTYPE"] not in self.stat_name_to_id or si["MODTYPE"] not in self.modtype_name_to_id:
            raise ValueError("StatType/ModType %s/%s fora dos enums" % (si["STATTYPE"], si["MODTYPE"]))
        mtype = SLOT_MATERIAL_TYPE[slot_index]
        ed = {
            "StatModKey": int(statmodkey),
            "Tier": int(tier),
            "Value": int(value),
            "RecipeType": RECIPE_TYPE[mtype],
            "ModType": self.modtype_name_to_id[si["MODTYPE"]],
            "MaterialKey": int(material_key),
            "StatType": self.stat_name_to_id[si["STATTYPE"]],
        }
        errs = self.validate_enchant(slot_index, item_key, ed)
        if errs:
            raise ValueError("; ".join(errs))
        return ed

    def validate_enchant(self, slot_index, item_key, ed):
        """Confere um EnchantData contra as tabelas da versao de data/. Lista de erros (vazia = ok)."""
        if not is_filled(ed):
            return []  # slot vazio e valido
        errs = []
        want = SLOT_MATERIAL_TYPE[slot_index] if 0 <= slot_index < len(SLOT_MATERIAL_TYPE) else None
        if not self.slot_allowed(item_key, slot_index):
            errs.append("a grade do item não tem esse slot")
        mk = str(ed.get("MaterialKey", 0))
        mat = self.materials.get(mk)
        if not mat:
            return errs + [f"MaterialKey {mk} desconhecido"]
        if mat["MATERIALTYPE"] != want:
            errs.append(f"material é {mat['MATERIALTYPE']}, mas o slot é {want}")
        if want and ed.get("RecipeType") != RECIPE_TYPE[want]:
            errs.append(f"RecipeType {ed.get('RecipeType')} não é o do slot ({RECIPE_TYPE[want]})")
        if int(ed.get("Tier", 0)) < 1:
            errs.append("Tier menor que 1")
        gg = self.gear_group(item_key)
        opt = next((o for o in self.stat_options(mk, gg) if o["statModKey"] == ed.get("StatModKey")), None)
        if not opt:
            errs.append("StatModKey não pertence ao material/grupo do item")
            return errs
        tier = next((t for t in opt["tiers"] if t["tier"] == ed.get("Tier")), None)
        if not tier:
            errs.append(f"Tier {ed.get('Tier')} inválido para esse stat")
            return errs
        if (ed.get("StatType"), ed.get("ModType")) != (self.stat_name_to_id.get(tier["statType"]),
                                                       self.modtype_name_to_id.get(tier["modType"])):
            errs.append("StatType/ModType não batem com a tabela")
        v = ed.get("Value", 0)
        if not (tier["min"] <= v <= tier["max"]):
            errs.append(f"Value {v} fora do range [{tier['min']},{tier['max']}]")
        elif tier["interval"] and (v - tier["min"]) % tier["interval"] != 0:
            errs.append(f"Value {v} não respeita o passo {tier['interval']}")
        return errs

    def pad_enchants(self, item):
        """Completa EnchantData ate o tamanho da grade, como o jogo ao salvar; nunca corta."""
        eds = item.setdefault("EnchantData", [])
        while len(eds) < self.enchant_len(item["ItemKey"]):
            eds.append(dict(empty_fields(), EnchantVersion=None))
        return eds

    def write_enchant(self, item, slot_index, fields, version):
        """Grava os 7 campos no dict do slot, campo a campo (preserva o resto). Slot que muda
        recebe EnchantVersion = version, como o jogo ao rolar; slot igual nao e tocado.
        Devolve True se mudou."""
        eds = self.pad_enchants(item)
        ed = eds[slot_index]
        if all(ed.get(k, 0) == v for k, v in fields.items()):
            return False
        ed.update(fields)
        ed["EnchantVersion"] = version
        return True

    def clear_enchant(self, item, slot_index):
        """Extracao: zera o slot sem deslocar os outros. Devolve True se havia encantamento."""
        eds = item.get("EnchantData") or []
        if not 0 <= slot_index < len(eds) or not is_filled(eds[slot_index]):
            return False
        eds[slot_index].update(empty_fields())
        eds[slot_index]["EnchantVersion"] = None
        return True

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
