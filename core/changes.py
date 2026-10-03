"""
Previa do Salvar: o que muda entre o save em disco e o que o editor vai gravar, em linhas
legiveis por area (Moedas, Herois, Pets, Runas, Cubo, Encantamentos). Cada linha diz quais
caminhos do save ela explica; qualquer mudanca que nenhuma linha explique sai em "Outros" com o
caminho. Nada muda calado.
"""
from .gamedata import is_filled, ENCHANT_FIELDS

SLOT_LABELS = ["Decoration", "Decoration", "Engraving", "Engraving", "Inscription", "Inscription"]
COUNTERS = ("DecorationAppliedTotalCount", "EngravingAppliedTotalCount", "InscriptionAppliedTotalCount")


def deep_diff(a, b, path, out):
    """(caminho, antes, depois) de cada folha que mudou; tipo conta (1 != 1.0 != True).
    Lista que muda de tamanho vira uma entrada so, no caminho da lista."""
    if isinstance(a, dict) and isinstance(b, dict):
        for k in a.keys() | b.keys():
            deep_diff(a.get(k), b.get(k), "%s.%s" % (path, k), out)
    elif isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        for i, (x, y) in enumerate(zip(a, b)):
            deep_diff(x, y, "%s[%d]" % (path, i), out)
    elif (type(a), a) != (type(b), b):
        out.append((path, a, b))
    return out


def fmt(v):
    if isinstance(v, bool):
        return "sim" if v else "não"
    if isinstance(v, (int, float)):
        return "{:,.0f}".format(v).replace(",", ".") if abs(v) >= 1000 or float(v).is_integer() else "%g" % v
    return "—" if v is None else str(v)


def _differs(a, b):
    return (type(a), a) != (type(b), b)


def describe(gd, acc0, ply0, acc1, ply1, locale="pt"):
    """Lista de {"area", "text"} do que muda de (acc0, ply0) para (acc1, ply1)."""
    out, explained = [], set()

    def add(area, text, *paths):
        out.append({"area": area, "text": text})
        explained.update(paths)

    def rows(lst, key):
        """(chave, antes, depois, caminhos) por entrada; quando a lista muda de tamanho, o
        caminho da lista inteira entra junto (o diff bruto a reporta inteira)."""
        before = {str(x.get(key)): x for x in ply0.get(lst) or [] if isinstance(x, dict)}
        grown = ["player." + lst] if len(ply0.get(lst) or []) != len(ply1.get(lst) or []) else []
        res = []
        for i, x in enumerate(ply1.get(lst) or []):
            if isinstance(x, dict):
                res.append((str(x.get(key)), before.pop(str(x.get(key)), {}), x, "player.%s[%d]" % (lst, i), grown))
        res += [(k, x, {}, "player." + lst, grown) for k, x in before.items()]
        return res

    for k, a, b, path, grown in rows("currenySaveDatas", "Key"):
        if a.get("Quantity") != b.get("Quantity"):
            add("Moedas", "%s: %s → %s" % (gd.currency_name(k, locale), fmt(a.get("Quantity")), fmt(b.get("Quantity"))),
                path + ".Quantity", *grown)

    def skills(v):
        return ", ".join(gd.skill_name(s, locale) for s in v or [] if int(s) > 0) or "nenhuma"

    fields = (("HeroLevel", "nível", fmt), ("HeroExp", "EXP", fmt), ("AbilityPoint", "pontos livres", fmt),
              ("IsUnLock", "desbloqueado", fmt), ("equippedSKillKey", "skills", skills))
    for k, a, b, path, grown in rows("heroSaveDatas", "heroKey"):
        for f, label, show in fields:
            if _differs(a.get(f), b.get(f)):
                add("Heróis", "%s: %s %s → %s" % (gd.hero_name(k, locale), label, show(a.get(f)), show(b.get(f))),
                    "%s.%s" % (path, f), *grown)

    for k, a, b, path, grown in rows("PetSaveData", "PetKey"):
        st = lambda v: "destravado" if v else "travado"  # noqa: E731
        if a.get("IsUnlock") != b.get("IsUnlock"):  # IsViewed acompanha o destravar
            add("Pets", "%s: %s → %s" % (gd.pet_name(k, locale), st(a.get("IsUnlock")), st(b.get("IsUnlock"))),
                path, *grown)
        elif a.get("IsViewed") != b.get("IsViewed"):
            add("Pets", "%s: visto %s → %s" % (gd.pet_name(k, locale), fmt(a.get("IsViewed")), fmt(b.get("IsViewed"))),
                path + ".IsViewed", *grown)

    for k, a, b, path, grown in rows("RuneSaveData", "RuneKey"):
        if a.get("Level") != b.get("Level"):
            add("Runas", "%s [%s]: nível %s → %s" % (gd.rune_name(k, locale), gd.rune_effect(k),
                                                     fmt(a.get("Level")), fmt(b.get("Level"))), path + ".Level", *grown)

    c0, c1 = ply0.get("cubeSaveLevelData") or {}, ply1.get("cubeSaveLevelData") or {}
    for f, label in (("Level", "nível"), ("Exp", "Exp")):
        if _differs(c0.get(f), c1.get(f)):
            add("Cubo", "%s %s → %s" % (label, fmt(c0.get(f)), fmt(c1.get(f))), "player.cubeSaveLevelData." + f)

    owner = {str(u): gd.hero_name(h.get("heroKey"), locale)
             for h in ply1.get("heroSaveDatas") or [] for u in h.get("equippedItemIds") or []}
    for uid, a, b, path, grown in rows("itemSaveDatas", "UniqueId"):
        ea, eb = a.get("EnchantData") or [], b.get("EnchantData") or []
        name = gd.name(b.get("ItemKey") or a.get("ItemKey"), locale) + (" (%s)" % owner[uid] if uid in owner else "")
        slot_lines = 0
        for i in range(min(6, max(len(ea), len(eb)))):
            x = ea[i] if i < len(ea) else {}
            y = eb[i] if i < len(eb) else {}
            if any(x.get(f, 0) != y.get(f, 0) for f in ENCHANT_FIELDS):
                slot_lines += 1  # contadores, EnchantVersion e grade completada sao consequencia
                add("Encantamentos", "%s · slot %d (%s): %s → %s" % (
                    name, i + 1, SLOT_LABELS[i], _enchant(gd, x, locale), _enchant(gd, y, locale)), path, *grown)
        if slot_lines:
            continue
        if _differs(a.get("EnchantCount"), b.get("EnchantCount")):
            add("Encantamentos", "%s: slots ocupados por tipo (EnchantCount) %s → %s" % (
                name, a.get("EnchantCount"), b.get("EnchantCount")), path + ".EnchantCount", *grown)
        for f in COUNTERS:
            if _differs(a.get(f), b.get(f)):
                add("Encantamentos", "%s: %s %s → %s" % (name, f, fmt(a.get(f)), fmt(b.get(f))),
                    "%s.%s" % (path, f), *grown)
        if len(ea) != len(eb):
            add("Encantamentos", "%s: tamanho do EnchantData %d → %d" % (name, len(ea), len(eb)),
                path + ".EnchantData", *grown)

    rest = deep_diff(acc0, acc1, "account", []) + deep_diff(ply0, ply1, "player", [])
    for p, a, b in sorted(rest, key=lambda r: r[0]):
        if not any(p == e or p.startswith(e + ".") or p.startswith(e + "[") for e in explained):
            add("Outros", "%s: %s → %s" % (p, _short(a), _short(b)))
    return out


def _enchant(gd, ed, locale):
    if not is_filled(ed):
        return "vazio"
    si = gd.statmod.get((str(ed.get("StatModKey")), str(ed.get("Tier"))))
    stat = gd.pretty_stat(si["STATTYPE"]) if si else "stat %s" % ed.get("StatType")
    return "%s T%s %s (%s)" % (stat, ed.get("Tier"), ed.get("Value"), gd.name(ed.get("MaterialKey"), locale))


def _short(v):
    s = fmt(v) if not isinstance(v, (dict, list)) else "%s com %d itens" % (type(v).__name__, len(v))
    return s if len(s) <= 80 else s[:77] + "..."
