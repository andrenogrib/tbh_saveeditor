"""
Compara duas pastas no formato de data/ (ex: data vs research/1.2.8) e imprime um
relatorio em markdown: enums, tabelas (colunas; linhas pela menor chave composta unica
formada pelas primeiras colunas; sem chave unica, linha inteira), nomes de item, strings
(agrupadas por prefixo) e icones.

  python tools/diff_versions.py data research/1.2.8 --out research/1.2.8/DIFF.md [--examples 12]
"""
import argparse
import csv
import json
import os
import re
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tbh_paths  # noqa: E402

MAX_KEY_COLS = 4


def read_rows(path):
    with open(path, encoding="utf-8-sig", newline="") as fh:
        rows = [r for r in csv.reader(fh) if r and any(c.strip() for c in r)]
    return (rows[0], rows[1:]) if rows else ([], [])


def key_width(header, *bodies):
    """Menor k tal que as k primeiras colunas identificam cada linha em todos os lados."""
    for k in range(1, min(len(header), MAX_KEY_COLS) + 1):
        if all(len({tuple(r[:k]) for r in b}) == len(b) for b in bodies):
            return k
    return None


def load_json(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except OSError:
        return None


def prefix(key):
    m = re.match(r"([A-Za-z]+?)(?:_|\d|$)", key)
    return m.group(1) if m else key[:12]


def fmt_key(k):
    return "/".join(k)


def diff_table(t, a, b, n, out):
    ha, ra = read_rows(os.path.join(a, "tables", t + ".csv"))
    hb, rb = read_rows(os.path.join(b, "tables", t + ".csv"))
    col_add, col_rem = [c for c in hb if c not in ha], [c for c in ha if c not in hb]
    title = "### %s — %d -> %d linhas" % (t, len(ra), len(rb))
    k = key_width(hb, ra, rb) if ha[:MAX_KEY_COLS] == hb[:MAX_KEY_COLS] else None
    lines = []
    if col_add or col_rem:
        lines.append("- colunas: +%s  -%s" % (col_add or "[]", col_rem or "[]"))
    if k is None:
        common = [c for c in hb if c in ha]  # compara so as colunas presentes nos dois lados
        ca = Counter(tuple(dict(zip(ha, r)).get(c, "") for c in common) for r in ra)
        cb = Counter(tuple(dict(zip(hb, r)).get(c, "") for c in common) for r in rb)
        rem, add = ca - cb, cb - ca
        if rem or add:
            lines.append("- sem chave unica nas %d primeiras colunas: comparacao por linha inteira"
                         " (-%d +%d)" % (MAX_KEY_COLS, sum(rem.values()), sum(add.values())))
            for r in list(rem)[: n // 2]:
                lines.append("  - - `%s`" % ",".join(r)[:120])
            for r in list(add)[: n // 2]:
                lines.append("  - + `%s`" % ",".join(r)[:120])
    else:
        ka = {tuple(r[:k]): dict(zip(ha, r)) for r in ra}
        kb = {tuple(r[:k]): dict(zip(hb, r)) for r in rb}
        add, rem = sorted(set(kb) - set(ka)), sorted(set(ka) - set(kb))
        common_cols = [c for c in hb if c in ha]
        changed = {}
        for key in sorted(set(ka) & set(kb)):
            cols = [c for c in common_cols if ka[key].get(c) != kb[key].get(c)]
            if cols:
                changed[key] = cols
        if k > 1:
            lines.append("- chave: %s" % "+".join(hb[:k]))
        if add:
            lines.append("- +%d: %s%s" % (len(add), ", ".join(fmt_key(x) for x in add[:n]), " ..." if len(add) > n else ""))
        if rem:
            lines.append("- -%d: %s%s" % (len(rem), ", ".join(fmt_key(x) for x in rem[:n]), " ..." if len(rem) > n else ""))
        if changed:
            cc = Counter(c for cols in changed.values() for c in cols)
            lines.append("- %d linhas alteradas; colunas mais alteradas: %s" % (
                len(changed), ", ".join("%s(%d)" % kv for kv in cc.most_common(8))))
            for key in list(changed)[: max(3, n // 2)]:
                lines.append("  - `%s`: " % fmt_key(key) + "; ".join(
                    "%s %s->%s" % (c, ka[key].get(c), kb[key].get(c)) for c in changed[key][:6]))
    if not lines:
        out.append("### %s — igual (%d linhas)\n" % (t, len(rb)))
    else:
        out.extend([title] + lines + [""])


def diff_tables(a, b, n, out):
    ta = {f[:-4] for f in os.listdir(os.path.join(a, "tables")) if f.endswith(".csv")}
    tb = {f[:-4] for f in os.listdir(os.path.join(b, "tables")) if f.endswith(".csv")}
    out.append("## Tabelas\n")
    out.append("- so em `%s`: %s" % (b, ", ".join(sorted(tb - ta)) or "-"))
    out.append("- so em `%s`: %s\n" % (a, ", ".join(sorted(ta - tb)) or "-"))
    for t in sorted(ta & tb):
        diff_table(t, a, b, n, out)


def diff_map(title, da, db, n, out, group=False):
    if da is None or db is None:
        out.append("## %s\n- (arquivo ausente em um dos lados)\n" % title)
        return
    add = sorted(set(db) - set(da))
    rem = sorted(set(da) - set(db))
    chg = sorted(k for k in set(da) & set(db) if da[k] != db[k])
    out.append("## %s — %d -> %d chaves (+%d, -%d, ~%d)" % (title, len(da), len(db), len(add), len(rem), len(chg)))
    if group:
        for label, keys in (("+", add), ("-", rem), ("~", chg)):
            if keys:
                cnt = Counter(prefix(k) for k in keys)
                out.append("- %s por prefixo: %s" % (label, ", ".join("%s(%d)" % kv for kv in cnt.most_common(20))))
    for k in add[:n]:
        out.append("  - + `%s` = %s" % (k, str(db[k])[:90].replace("\n", " ")))
    for k in rem[:n]:
        out.append("  - - `%s` = %s" % (k, str(da[k])[:90].replace("\n", " ")))
    for k in chg[: n // 2]:
        out.append("  - ~ `%s`: %s -> %s" % (k, str(da[k])[:60].replace("\n", " "), str(db[k])[:60].replace("\n", " ")))
    out.append("")


def diff_enums(ea, eb, out):
    out.append("## Enums\n")
    if ea is None or eb is None:
        out.append("- (enums.json ausente)\n")
        return
    for name in sorted(set(ea) | set(eb)):
        a, b = ea.get(name), eb.get(name)
        if a is None or b is None:
            out.append("- `%s`: %s" % (name, "novo (%d membros)" % len(b) if b else "sumiu"))
            continue
        inv_a = {v: k for k, v in a.items()}
        inv_b = {v: k for k, v in b.items()}
        moved = ["%s %s->%s" % (m, inv_a[m], inv_b[m]) for m in inv_a if m in inv_b and inv_a[m] != inv_b[m]]
        add = ["%s=%s" % (m, inv_b[m]) for m in inv_b if m not in inv_a]
        rem = ["%s=%s" % (m, inv_a[m]) for m in inv_a if m not in inv_b]
        if not (moved or add or rem):
            out.append("- `%s`: igual (%d)" % (name, len(b)))
            continue
        out.append("- `%s`: +%s -%s%s" % (name, add or "[]", rem or "[]",
                                          ("  **VALOR MUDOU: %s**" % moved) if moved else ""))
    out.append("")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("old")
    ap.add_argument("new")
    ap.add_argument("--out")
    ap.add_argument("--examples", type=int, default=12)
    a = ap.parse_args()
    if a.out:
        tbh_paths.assert_writable(a.out)
    out = ["# Diff de dados: `%s` -> `%s`\n" % (a.old, a.new)]
    for d in (a.old, a.new):
        v = os.path.join(d, "VERSION")
        out.append("- `%s`: %s" % (d, open(v, encoding="utf-8").read().strip() if os.path.exists(v) else "(sem VERSION)"))
    out.append("")
    diff_enums(load_json(os.path.join(a.old, "enums.json")), load_json(os.path.join(a.new, "enums.json")), out)
    diff_tables(a.old, a.new, a.examples, out)
    for loc in ("en", "pt"):
        diff_map("names_%s (ItemKey -> nome)" % loc, load_json(os.path.join(a.old, "names_%s.json" % loc)),
                 load_json(os.path.join(a.new, "names_%s.json" % loc)), a.examples if loc == "en" else 0, out)
    diff_map("strings_en (textos)", load_json(os.path.join(a.old, "strings_en.json")),
             load_json(os.path.join(a.new, "strings_en.json")), a.examples, out, group=True)
    diff_map("icon_map", load_json(os.path.join(a.old, "icon_map.json")),
             load_json(os.path.join(a.new, "icon_map.json")), 0, out)
    text = "\n".join(out) + "\n"
    if a.out:
        with open(a.out, "w", encoding="utf-8") as fh:
            fh.write(text)
        print("->", a.out)
    else:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        print(text)


if __name__ == "__main__":
    main()
