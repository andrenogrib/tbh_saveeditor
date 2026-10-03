"""
Previa do Salvar: o que muda entre o save em disco e o que o editor vai gravar, em linhas
legiveis por area (Moedas, Herois, Pets, Runas, Cubo, Encantamentos). Qualquer campo que mude
fora dessas areas sai em "Outros" com o caminho: nada muda calado.
"""
import re

from .gamedata import is_filled, ENCHANT_FIELDS

SLOT_LABELS = ["Decoration", "Decoration", "Engraving", "Engraving", "Inscription", "Inscription"]
# caminhos que as areas acima ja descrevem (o resto vira "Outros")
COVERED = re.compile(r"""^player\.(?:currenySaveDatas\[\d+\]\.Quantity
    |heroSaveDatas\[\d+\]\.(?:HeroLevel|HeroExp|AbilityPoint|IsUnLock|equippedSKillKey(?:\[\d+\])?)
    |PetSaveData\[\d+\]\.(?:IsUnlock|IsViewed)
    |RuneSaveData\[\d+\]\.Level
    |cubeSaveLevelData\.(?:Level|Exp)
    |itemSaveDatas\[\d+\]\.(?:EnchantData.*|EnchantCount.*|\w+AppliedTotalCount))$""", re.X)


def deep_diff(a, b, path, out):
    """(caminho, antes, depois) de cada folha que mudou; tipo conta (1 != 1.0 != True)."""
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


def _by(player, lst, key):
    return {str(x.get(key)): x for x in player.get(lst) or [] if isinstance(x, dict)}


def describe(gd, acc0, ply0, acc1, ply1, locale="pt"):
    """Lista de {"area", "text"} do que muda de (acc0, ply0) para (acc1, ply1)."""
    out = []

    def add(area, text):
        out.append({"area": area, "text": text})

    def pairs(lst, key):
        a, b = _by(ply0, lst, key), _by(ply1, lst, key)
        return [(k, a.get(k) or {}, b.get(k) or {}) for k in sorted(a.keys() | b.keys(), key=_num_key)]

    for k, a, b in pairs("currenySaveDatas", "Key"):
        if a.get("Quantity") != b.get("Quantity"):
            add("Moedas", "%s: %s → %s" % (gd.currency_name(k, locale), fmt(a.get("Quantity")), fmt(b.get("Quantity"))))

    def skills(v):
        return ", ".join(gd.skill_name(s, locale) for s in v or [] if int(s) > 0) or "nenhuma"

    fields = (("HeroLevel", "nível", fmt), ("HeroExp", "EXP", fmt), ("AbilityPoint", "pontos livres", fmt),
              ("IsUnLock", "desbloqueado", fmt), ("equippedSKillKey", "skills", skills))
    for k, a, b in pairs("heroSaveDatas", "heroKey"):
        for f, label, show in fields:
            if (type(a.get(f)), a.get(f)) != (type(b.get(f)), b.get(f)):
                add("Heróis", "%s: %s %s → %s" % (gd.hero_name(k, locale), label, show(a.get(f)), show(b.get(f))))

    for k, a, b in pairs("PetSaveData", "PetKey"):
        if a.get("IsUnlock") != b.get("IsUnlock"):
            st = lambda v: "destravado" if v else "travado"  # noqa: E731
            add("Pets", "%s: %s → %s" % (gd.pet_name(k, locale), st(a.get("IsUnlock")), st(b.get("IsUnlock"))))

    for k, a, b in pairs("RuneSaveData", "RuneKey"):
        if a.get("Level") != b.get("Level"):
            add("Runas", "%s [%s]: nível %s → %s" % (gd.rune_name(k, locale), gd.rune_effect(k),
                                                     fmt(a.get("Level")), fmt(b.get("Level"))))

    c0, c1 = ply0.get("cubeSaveLevelData") or {}, ply1.get("cubeSaveLevelData") or {}
    for f, label in (("Level", "nível"), ("Exp", "Exp")):
        if (type(c0.get(f)), c0.get(f)) != (type(c1.get(f)), c1.get(f)):
            add("Cubo", "%s %s → %s" % (label, fmt(c0.get(f)), fmt(c1.get(f))))

    owner = {str(u): gd.hero_name(h.get("heroKey"), locale)
             for h in ply1.get("heroSaveDatas") or [] for u in h.get("equippedItemIds") or []}
    for uid, a, b in pairs("itemSaveDatas", "UniqueId"):
        ea, eb = a.get("EnchantData") or [], b.get("EnchantData") or []
        where = " (%s)" % owner[uid] if uid in owner else ""
        name = gd.name(b.get("ItemKey") or a.get("ItemKey"), locale) + where
        for i in range(min(6, max(len(ea), len(eb)))):
            x = ea[i] if i < len(ea) else {}
            y = eb[i] if i < len(eb) else {}
            if any(x.get(f, 0) != y.get(f, 0) for f in ENCHANT_FIELDS):
                add("Encantamentos", "%s · slot %d (%s): %s → %s" % (
                    name, i + 1, SLOT_LABELS[i], _enchant(gd, x, locale), _enchant(gd, y, locale)))

    rest = deep_diff(acc0, acc1, "account", []) + deep_diff(ply0, ply1, "player", [])
    for path, a, b in sorted(rest):
        if not COVERED.match(path):
            add("Outros", "%s: %s → %s" % (path, _short(a), _short(b)))
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


def _num_key(k):
    return (0, int(k)) if str(k).lstrip("-").isdigit() else (1, str(k))
