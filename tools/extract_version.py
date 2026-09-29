"""
Extrai os dados de UMA versao do jogo para research/<versao>/ no mesmo formato de data/,
reusando os extratores de extract/ (sem modifica-los): so troca os caminhos fixos deles
pelos detectados nesta maquina e a pasta de saida. data/ nunca e tocado.

  python tools/extract_version.py                       tudo (tabelas, textos, icones, enums)
  python tools/extract_version.py --steps tables,loc    so alguns passos
  python tools/extract_version.py --only-wanted         so as 15 tabelas que o editor usa hoje

Por padrao exporta TODAS as TextAssets (inventario em tables/_inventory.json), para achar
tabelas novas (mapas, skins, skills...). Enums saem do dump.cs de tools/il2cpp_dump.py.
Requer: pip install UnityPy
"""
import argparse
import datetime as dt
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "extract"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tbh_paths  # noqa: E402

# alem dos enums de extract_enums.WANTED: os que numeram campos do save 1.2.x
# (aceita nome qualificado por classe externa, ex. 'wh.vc.EItemGetSourceType')
EXTRA_ENUMS = ["EItemGetSourceType", "EGearGroup", "EAggregateType", "EAggregateContent",
               "EEquipClassType", "EHeroType", "EItemType", "EGearType", "EStageType"]
STEPS = ("tables", "loc", "icons", "enums")


def parse_enum_q(text, name):
    """Como extract_enums.parse_enum, mas aceita 'public enum Outer.Inner.NOME'."""
    m = re.search(r"public enum (?:[\w.]+\.)?%s // TypeDefIndex: \d+\n\{" % re.escape(name), text)
    if not m:
        return None
    body = text[m.end():text.find("}", m.end())]
    return {v: k for k, v in re.findall(r"public const [\w.]+ (\w+) = (-?\d+);", body) if k != "value__"}


def all_game_enums(text):
    """Todos os enums de Assembly-CSharp: {nome (qualificado): {valor: membro}}."""
    m = re.search(r"^// Image \d+: (?!Assembly-CSharp\.dll)\S+ - (\d+)", text, re.M)
    limit = int(m.group(1)) if m else 10 ** 9
    out = {}
    for em in re.finditer(r"public enum ([\w.]+) // TypeDefIndex: (\d+)\n\{", text):
        if int(em.group(2)) >= limit:
            continue
        body = text[em.end():text.find("}", em.end())]
        out[em.group(1)] = {v: k for k, v in re.findall(r"public const [\w.]+ (\w+) = (-?\d+);", body)
                            if k != "value__"}
    return out


def inventory(gdd):
    """Todas as TextAssets de todos os .assets/levelN: [{name, file, bytes}]."""
    import UnityPy
    out = []
    for fn in sorted(os.listdir(gdd)):
        if not (fn.endswith(".assets") or fn.startswith("level")) or fn.endswith(".resS"):
            continue
        try:
            env = UnityPy.load(os.path.join(gdd, fn))
        except Exception as e:  # noqa: BLE001
            print("  (ignorado %s: %s)" % (fn, e))
            continue
        for obj in env.objects:
            if obj.type.name == "TextAsset":
                d = obj.read()
                raw = d.m_Script
                out.append({"name": d.m_Name, "file": fn,
                            "bytes": len(raw.encode("utf-8", "surrogateescape") if isinstance(raw, str) else raw)})
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--game", help="pasta do jogo (padrao: detectada pela Steam)")
    ap.add_argument("--out", help="pasta de saida (padrao: research/<versao>)")
    ap.add_argument("--steps", default="tables,loc,icons,enums")
    ap.add_argument("--only-wanted", action="store_true", help="so as tabelas de extract_tables.WANTED")
    ap.add_argument("--dump", help="dump.cs (padrao: <TBH_RE>/<versao>/dump/dump.cs)")
    a = ap.parse_args()

    gdir = a.game or tbh_paths.game_dir()
    ver = tbh_paths.game_version(gdir)
    if not gdir or not ver:
        raise SystemExit("jogo nao encontrado; use --game")
    gdd = tbh_paths.game_data_dir(gdir)
    out = os.path.abspath(a.out or os.path.join(ROOT, "research", ver))
    if os.path.normcase(out).startswith(os.path.normcase(os.path.join(ROOT, "data"))):
        raise SystemExit("recusado: data/ so e atualizado na migracao revisada (ver skill game-update)")
    tbh_paths.assert_writable(out)
    steps = {s.strip() for s in a.steps.split(",") if s.strip()}
    bad = steps - set(STEPS)
    if bad:
        ap.error("passo(s) desconhecido(s): %s (validos: %s)" % (",".join(sorted(bad)), ",".join(STEPS)))
    os.makedirs(out, exist_ok=True)
    done = []
    print("jogo %s em %s -> %s" % (ver, gdir, out))

    if "tables" in steps:
        import extract_tables
        inv = inventory(gdd)
        os.makedirs(os.path.join(out, "tables"), exist_ok=True)
        with open(os.path.join(out, "tables", "_inventory.json"), "w", encoding="utf-8") as fh:
            json.dump(inv, fh, ensure_ascii=False, indent=1)
        others = sorted({t["file"] for t in inv} - {"sharedassets0.assets"})
        if others:
            print("  AVISO: ha TextAssets fora de sharedassets0.assets (%s); veja _inventory.json" % others)
        extract_tables.GAME_DATA = gdd
        extract_tables.OUT = os.path.join(out, "tables")
        if not a.only_wanted:
            extract_tables.WANTED = {t["name"] for t in inv if t["file"] == "sharedassets0.assets"}
        print("== tabelas (%d TextAssets no inventario) ==" % len(inv))
        extract_tables.main()
        done.append("tables")

    if "loc" in steps:
        import extract_localization
        extract_localization.AA = os.path.join(gdd, "StreamingAssets", "aa", "StandaloneWindows64")
        extract_localization.OUT = out
        print("== localizacao ==")
        extract_localization.main()
        done.append("loc")

    if "icons" in steps:
        import extract_sprites
        extract_sprites.GAME_DATA = gdd
        extract_sprites.DATA = out
        extract_sprites.ICONS = os.path.join(out, "icons")
        print("== icones ==")
        extract_sprites.main()
        done.append("icons")

    if "enums" in steps:
        dump = a.dump or os.path.join(tbh_paths.re_root(), ver, "dump", "dump.cs")
        if os.path.exists(dump):
            import extract_enums
            extract_enums.DUMP = dump
            extract_enums.OUT = os.path.join(out, "enums.json")
            print("== enums ==")
            extract_enums.main()  # os enums que o editor ja usa
            with open(dump, encoding="utf-8", errors="ignore") as fh:
                text = fh.read()
            with open(extract_enums.OUT, encoding="utf-8") as fh:
                enums = json.load(fh)
            missing = []
            for name in EXTRA_ENUMS:
                e = parse_enum_q(text, name)
                if e:
                    enums[name] = e
                else:
                    missing.append(name)
            with open(extract_enums.OUT, "w", encoding="utf-8") as fh:
                json.dump(enums, fh, ensure_ascii=False, indent=2)
            every = all_game_enums(text)
            with open(os.path.join(out, "enums_all.json"), "w", encoding="utf-8") as fh:
                json.dump(every, fh, ensure_ascii=False, indent=1, sort_keys=True)
            print("  extras: %d/%d; enums_all.json: %d enums do jogo%s" % (
                len(EXTRA_ENUMS) - len(missing), len(EXTRA_ENUMS), len(every),
                ("; NAO achados: %s" % ", ".join(missing)) if missing else ""))
            done.append("enums")
        else:
            print("== enums: PULADO (sem %s; rode tools/il2cpp_dump.py) ==" % dump)

    build = tbh_paths.game_build_guid(gdir)
    vfile = os.path.join(out, "VERSION")
    recorded = list(done)
    try:  # mesma versao/build: acumula os passos ja feitos em rodadas anteriores
        with open(vfile, encoding="utf-8") as fh:
            prev = fh.read()
        if prev.split()[:2] == [ver, "build=%s" % build]:
            recorded = sorted(set(done) | set(re.search(r"steps=(\S*)", prev).group(1).split(",")) - {""})
    except (OSError, AttributeError, IndexError):
        pass
    with open(vfile, "w", encoding="utf-8") as fh:
        fh.write("%s build=%s extraido=%s steps=%s\n" % (ver, build, dt.date.today().isoformat(), ",".join(recorded)))
    print("\nok -> %s (passos feitos agora: %s)" % (out, ",".join(done) or "nenhum"))
    return 0 if steps <= set(done) else 1


if __name__ == "__main__":
    sys.exit(main())
