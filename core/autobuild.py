"""
Auto-build: escolhe a MELHOR combinacao de encantamentos por classe do heroi,
respeitando os slots que a grade do item permite.

Fundamento (extraido das tabelas + descricoes de skill do proprio jogo):

  Classe    Dano        Entrega              Observacao
  --------  ----------  -------------------  ----------------------------------
  Knight    Fisico      Melee (tank)         Multistrike ajuda (multi-hit)
  Slayer    Fisico      Melee + AoE          Bloodlust -> HP alto; Life Leech
  Ranger    Fisico      Projetil (varias)    Projectile Count = +1 flecha (enorme)
  Hunter    Elemental   Projetil + AoE       fogo/gelo/raio -> NAO usa Physical %
  Sorcerer  Elemental   AoE (fireball...)    AoE Damage universal; NAO Physical %
  Priest    Suporte     Cura + raio AoE      Skill Heal / CDR / HP; dano AoE

Modtype (do jogo): FLAT = soma direta ("Physical Damage +250%"),
ADDITIVE = "{0}% Increased" (bucket aditivo), MULTIPLICATIVE = "% More"
(multiplicador separado; nenhum encantamento oferece "More").

Chaos / mapa 3-9 (Core of the Abyss): a -60% e uma PENALIDADE de resistencia
por dificuldade de estagio (tooltip do jogo). Nao existe Max Resistance em
nenhum material -> o teto NAO sobe, e resistencia por slot e minuscula
(+3% a +5.5%), entao empilhar resistencia NAO vence o -60%.

Defesa que funciona de verdade (valores reais, guardado/10 = display):
  - Max HP (ADDITIVE) = +30%/slot   -> maior EHP
  - Damage Reduction  = +16%/slot   -> reduz TODO dano (inclusive chaos)
  - Life Leech        = +6.5%/slot do dano vira cura -> melhor sustain p/ build de dano
  - MANTER O DANO ALTO: matar rapido e a melhor defesa (inimigo morto nao bate).
O modo 'survival' NAO sacrifica o dano da arma/acessorio: mantem a ofensiva e
adiciona Life Leech nas inscricoes + Max HP/Damage Reduction/resistencia na
armadura. (Erro da versao anterior: trocava dano por resistencia fraca -> pior.)
"""
from .gamedata import is_filled

# ---- atalhos (statType, modType) ----
AD_ADD   = ("AttackDamage", "ADDITIVE")
AD_FLAT  = ("AttackDamage", "FLAT")
PHYS     = ("PhysicalDamagePercent", "FLAT")
CD       = ("CriticalDamage", "FLAT")
CC_ADD   = ("CriticalChance", "ADDITIVE")
MULTI    = ("Multistrike", "FLAT")
PROJC    = ("ProjectileCount", "FLAT")
IMELEE   = ("IncreaseMeleeDamage", "ADDITIVE")
IPROJ    = ("IncreaseProjectileDamage", "ADDITIVE")
IAOE     = ("IncreaseAreaOfEffectDamage", "ADDITIVE")
CAST     = ("CastSpeed", "ADDITIVE")
CDR      = ("CooldownReduction", "FLAT")
AOE      = ("AreaOfEffect", "ADDITIVE")
SKHEAL   = ("SkillHealIncrease", "FLAT")
SKDUR    = ("SkillDurationIncrease", "FLAT")
HP_ADD   = ("MaxHp", "ADDITIVE")
HP_FLAT  = ("MaxHp", "FLAT")
ARMOR_A  = ("Armor", "ADDITIVE")
DR       = ("DamageReduction", "FLAT")
ABSORB   = ("DamageAbsorption", "FLAT")
CHAOS    = ("ChaosResistance", "FLAT")
ALLRES   = ("AllElementalResistance", "FLAT")
HPREGEN  = ("HpRegenPerSec", "FLAT")
LEECH    = ("HpLeech", "FLAT")
BACR     = ("BaseAttackCountReduction", "FLAT")

# heroKey -> arquetipo
ROLE = {101: "melee", 601: "melee", 201: "projP", 501: "projE",
        301: "aoeE", 401: "support"}

# stat de "dano de entrega" da inscricao, por arquetipo
DELIVERY = {"melee": IMELEE, "projP": IPROJ, "projE": IPROJ,
            "aoeE": IAOE, "support": IAOE}

# ------------------------------------------------------------------
# Preferencias por (grupo, tipo de slot), em ordem de prioridade.
# O builder resolve cada preferencia contra o catalogo do jogo, pula
# as indisponiveis e preenche N slots com as N melhores DISTINTAS.
# ------------------------------------------------------------------

# ---- ARMA (ofensiva; mesma logica em qualquer modo) ----
WPN_DEC = {
    "melee":   [AD_ADD, MULTI, PHYS, CD],
    "projP":   [PROJC, AD_ADD, PHYS, CD],
    "projE":   [PROJC, AD_ADD, CD, CC_ADD],
    "aoeE":    [AD_ADD, CD, CAST, AOE],
    "support": [AD_ADD, CDR, CD, CAST],
}
WPN_ENG = {
    "melee":   [PHYS, CD, AD_ADD, CC_ADD],
    "projP":   [PHYS, CD, AD_ADD, CC_ADD],
    "projE":   [CD, AD_ADD, AOE, CC_ADD],
    "aoeE":    [CD, AD_ADD, AOE, CC_ADD],
    "support": [CDR, AD_ADD, CD, HP_FLAT],
}
WPN_INS = {
    "melee":   [IMELEE, PHYS, CD, AD_ADD],
    "projP":   [IPROJ, PHYS, CD, AD_ADD],
    "projE":   [IPROJ, IAOE, CD, AD_ADD],
    "aoeE":    [IAOE, CD, AD_ADD, CAST],
    "support": [SKHEAL, CDR, IAOE, HP_ADD],
}

# ---- ACESSORIO (ofensivo/crit) ----
_ACC_DEC_CRIT = [CD, AD_ADD, BACR, CC_ADD]
_ACC_DEC_CAST = [CD, CAST, AD_ADD, CDR]
ACC_DEC = {"melee": _ACC_DEC_CRIT, "projP": _ACC_DEC_CRIT, "projE": _ACC_DEC_CRIT,
           "aoeE": _ACC_DEC_CAST, "support": _ACC_DEC_CAST}
_ACC_ENG_CRIT = [CC_ADD, CD, AD_FLAT, HP_FLAT]
_ACC_ENG_CAST = [CAST, CDR, CC_ADD, HP_FLAT]
ACC_ENG = {"melee": _ACC_ENG_CRIT, "projP": _ACC_ENG_CRIT, "projE": _ACC_ENG_CRIT,
           "aoeE": _ACC_ENG_CAST, "support": _ACC_ENG_CAST}
# ACC_INS montado a partir do DELIVERY + cauda por arquetipo
_ACC_INS_TAIL_CRIT = [CD, CC_ADD, AD_ADD]
_ACC_INS_TAIL_CAST = [CAST, CD, CDR]

# ---- ARMADURA (deco/eng defensivos; inscricao varia com o modo) ----
# Numeros reais do jogo (valor guardado /10 = display):
#   Damage Reduction  = +16% menos dano (reduz TODO dano, inclusive chaos) -> defesa pesada
#   Max HP (ADDITIVE) = +30% de vida  -> maior ganho de EHP por slot
#   All Elemental Res = +3% (fogo/gelo/raio);  Chaos/individual = +5.5%  -> complemento fraco
# Por isso a defesa forte e Max HP + Damage Reduction (+ Life Leech nas inscricoes),
# NAO empilhar resistencia (que nem vence a penalidade -60% do mapa).
ARM_DEC_DEF = [DR, ALLRES, HP_ADD, ARMOR_A]
ARM_ENG_DEF = [HP_FLAT, CDR, ARMOR_A, DR]
ARM_DEC_SURV = [DR, ALLRES, HP_ADD, ARMOR_A]
ARM_ENG_SURV = [HP_FLAT, ARMOR_A, DR, ABSORB]


def _catalog(gd, gear_group, mtype):
    """(statType, modType) -> melhor opcao {statModKey, materialKey, tier, value}."""
    cache = getattr(gd, "_autobuild_catalog", None)
    if cache is None:
        cache = gd._autobuild_catalog = {}
    ck = (gear_group, mtype)
    if ck in cache:
        return cache[ck]
    best = {}
    for mk in gd.materials_by_type.get(mtype, []):
        for o in gd.stat_options(mk, gear_group):
            t = o["tiers"][-1]  # maior tier
            key = (o["statType"], o["modType"])
            cand = {"statModKey": o["statModKey"], "materialKey": int(mk),
                    "tier": t["tier"], "value": t["max"]}
            if key not in best or cand["value"] > best[key]["value"]:
                best[key] = cand
    cache[ck] = best
    return best


def _pick(prefs, catalog, n):
    """Resolve as preferencias contra o catalogo e devolve ate n opcoes distintas.
    Se acabarem as preferencias validas antes de n, repete a melhor disponivel."""
    chosen = []
    for key in prefs:
        if len(chosen) >= n:
            break
        opt = catalog.get(key)
        if opt:
            chosen.append((key, opt))
    if not chosen:
        return []
    while len(chosen) < n:            # completa repetindo a melhor
        chosen.append(chosen[0])
    return chosen[:n]


def _acc_ins(role, mode):
    tail = _ACC_INS_TAIL_CAST if role in ("aoeE", "support") else _ACC_INS_TAIL_CRIT
    if mode == "survival":
        return [DELIVERY[role], LEECH, HP_ADD, CD]  # mantem dano + roubo de vida + HP
    return [DELIVERY[role]] + tail


def _arm_ins(role, mode):
    if mode == "survival":
        return [HP_ADD, LEECH, ALLRES, ARMOR_A]     # HP + roubo de vida + resistencia
    if mode == "damage":
        return [DELIVERY[role], CD, IAOE, HP_ADD]
    return [DELIVERY[role], HP_ADD, CD, ARMOR_A]    # balanced: 1 dano + 1 HP


def _prefs(gear_group, mtype, role, mode):
    """Lista ordenada de (statType, modType) para um (grupo, slot, classe, modo)."""
    if gear_group == "WEAPON":
        base = {"DECORATION": WPN_DEC, "ENGRAVING": WPN_ENG, "INSCRIPTION": WPN_INS}[mtype][role]
        if mode == "survival" and mtype == "INSCRIPTION":
            return [DELIVERY[role], LEECH, CD, HP_ADD]  # dano no topo + roubo de vida
        return base
    if gear_group == "ACCESSORY":
        # acessorio fica ofensivo em todo modo (o Crit Damage carrega o dano);
        # no survival, garante Life Leech junto do Crit Damage (sustain em todo acessorio).
        if mtype == "INSCRIPTION":
            return _acc_ins(role, mode)
        if mtype == "DECORATION":
            return [CD, LEECH, AD_ADD, CC_ADD] if mode == "survival" else ACC_DEC[role]
        return ACC_ENG[role]
    # ARMOR
    if mtype == "DECORATION":
        return ARM_DEC_SURV if mode == "survival" else ARM_DEC_DEF
    if mtype == "ENGRAVING":
        return ARM_ENG_SURV if mode == "survival" else ARM_ENG_DEF
    return _arm_ins(role, mode)


# ------------------------------------------------------------------
# Skills recomendadas (2 ativas por heroi; a 3a fica com o ataque-base).
# 'damage' usa o mesmo conjunto de 'balanced'. 'survival' troca por
# skills de CC/cura/sobrevivencia onde a classe tem opcao.
# ------------------------------------------------------------------
RECOMMENDED_SKILLS = {
    "balanced": {
        101: [10301, 10501],  # Retribution Strike + Sacred Blade
        201: [20301, 20601],  # Arrow Rain (AoE) + Skewer Shot (single)
        301: [30601, 30501],  # Meteor Strike + Snowstorm
        401: [40301, 40201],  # Wrath of Heaven + Blessing of Might
        501: [50101, 50201],  # Explosive Bolt + Frost Bolt
        601: [60501, 60201],  # Axe Spin + Crushing Blow
    },
    "survival": {
        101: [10501, 10601],  # Sacred Blade (cura) + Unyielding Will (revive)
        201: [20301, 20601],  # Ranger nao tem skill defensiva -> mata rapido
        301: [30501, 30601],  # Snowstorm (congela/lentifica) + Meteor
        401: [40401, 40101],  # Sanctuary (regen) + Heal
        501: [50201, 50101],  # Frost Bolt (congela = CC) + Explosive Bolt
        601: [60501, 60301],  # Axe Spin + Commander's Cry (atordoa)
    },
}


def _skill_actives(hero_key, mode):
    table = RECOMMENDED_SKILLS["survival" if mode == "survival" else "balanced"]
    return table.get(int(hero_key))


def skill_loadout(gd, hero_key, mode, current, learned, third_slot):
    """Novo equippedSKillKey = [ataque-base, ativa1, ativa2] pelas regras da UI do jogo:
    so ativas do heroi ja aprendidas (`learned`: atributo com Level >= 1); a 3a posicao so
    com a runa que libera o slot (`third_slot`), senao -1; vazio = -1; sempre 3 posicoes.
    Completa com as ativas atuais validas. None se nao ha recomendacao para a classe."""
    actives = _skill_actives(hero_key, mode)
    if not actives:
        return None
    base = gd.hero_base_skill(hero_key)  # o jogo sobrescreve [0] com essa no load
    if base is None:
        base = current[0] if current else -1
    picks = [k for k in actives if k in learned]
    for k in (current or [])[1:]:
        if k in learned and k not in picks:
            picks.append(k)
    return [base, picks[0] if picks else -1, picks[1] if third_slot and len(picks) > 1 else -1]


# slots por tipo de material
_SLOTS = {"DECORATION": (0, 1), "ENGRAVING": (2, 3), "INSCRIPTION": (4, 5)}


def plan_item(gd, item_key, hero_key, mode="balanced", overwrite=True, current=None):
    """Devolve lista de (slot_index, campos do encantamento) a aplicar num item.
    - respeita quantos slots de cada tipo a grade permite;
    - overwrite=False mantem slots ja preenchidos, so completa vazios."""
    role = ROLE.get(int(hero_key), "melee")
    gg = gd.gear_group(item_key)
    if gg is None:
        return []
    if gd.enchantable(item_key):
        return []
    max_slots = gd.max_slots(item_key)
    current = current or []
    out = []
    for mtype, (a, b) in _SLOTS.items():
        n = max_slots.get(mtype, 0)
        if n <= 0:
            continue
        catalog = _catalog(gd, gg, mtype)
        picks = _pick(_prefs(gg, mtype, role, mode), catalog, n)
        for j in range(n):
            slot = a + j
            if not overwrite:
                cur = current[slot] if slot < len(current) else None
                if is_filled(cur):
                    continue  # ja preenchido; nao mexe
            if j >= len(picks):
                continue
            _key, opt = picks[j]
            # so os 7 campos: quem grava (gd.write_enchant) preserva o resto do slot
            fields = gd.enchant_fields(slot, item_key, opt["materialKey"], opt["statModKey"],
                                       opt["tier"], opt["value"])
            out.append((slot, fields))
    return out
