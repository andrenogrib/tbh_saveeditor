"""
Laboratorio de save: inspeciona e testa saves do Taskbar Hero SEM tocar no save vivo.
Toda escrita vai para copias em <TBH_RE>/saves (padrao ~/tbh_re/saves) ou --out.

  snapshot [--all]            copia o save vivo (ou todos os .es3/.bak da pasta) p/ o lab
  info FILE                   versao, datas, HMAC do SystemInfo, contagens do topo
  dump FILE [--out DIR]       grava account.json / player.json legiveis
  schema FILE [--vs FILE2]    caminhos do JSON de account+player (com tipos); --vs: o que mudou
  coverage FILE [--data DIR]  IDs do save que os dados de DIR (padrao data/) nao conhecem
  roundtrip FILE [--out F]    carrega -> regrava pelo core/es3 (caminho do editor) -> confere
                              (exit 0 so com HMAC original e regravado OK e conteudo identico)

Uso: python tools/save_lab.py <comando> -h
"""
import argparse
import base64
import csv
import datetime as dt
import glob
import hashlib
import hmac
import json
import os
import shutil
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core import es3, gamedata  # noqa: E402
import tbh_paths  # noqa: E402

LAB = os.path.join(tbh_paths.re_root(), "saves")


# ---------------- base ----------------
def load_es3(path):
    """-> (es3_obj, account_dict, player_dict)."""
    with open(path, "rb") as fh:
        obj = json.loads(es3.es3_decrypt(fh.read()).decode("utf-8"))
    return obj, json.loads(obj["AccountSaveData"]["value"]), json.loads(obj["PlayerSaveData"]["value"])


def systeminfo_ok(obj, account):
    acc, ply = obj["AccountSaveData"]["value"], obj["PlayerSaveData"]["value"]
    msg = es3.SYSTEMINFO_SEP.join([acc, ply, str(account.get("ownerSteamId", ""))]).encode("utf-8")
    calc = base64.b64encode(hmac.new(es3.SYSTEMINFO_HMAC_KEY, msg, hashlib.sha256).digest()).decode()
    return calc == obj["SystemInfo"]["value"]


def ticks_to_dt(ticks):
    """DateTime.Ticks do .NET (100ns desde 0001-01-01) -> datetime."""
    try:
        return dt.datetime(1, 1, 1) + dt.timedelta(microseconds=int(ticks) // 10)
    except (TypeError, ValueError, OverflowError):
        return None


def schema(o, path="", out=None):
    """{caminho: set(tipos)} de todo o JSON (elementos de lista viram '[]', com o tipo)."""
    if out is None:
        out = {}
    if isinstance(o, dict):
        for k, v in o.items():
            p = "%s.%s" % (path, k) if path else k
            out.setdefault(p, set()).add(type(v).__name__)
            schema(v, p, out)
    elif isinstance(o, list):
        for v in o:
            out.setdefault(path + "[]", set()).add(type(v).__name__)
            schema(v, path + "[]", out)
    return out


def save_schema(path):
    """Esquema de account + player de um save, com prefixo 'account.' / 'player.'."""
    _, acc, ply = load_es3(path)
    return {**schema(acc, "account"), **schema(ply, "player")}


def out_path(path):
    tbh_paths.assert_writable(path)  # recusa ANTES de criar qualquer pasta
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    return path


# ---------------- comandos ----------------
def cmd_snapshot(a):
    src_dir = tbh_paths.save_dir()
    files = sorted(glob.glob(os.path.join(src_dir, "*.es3")) + glob.glob(os.path.join(src_dir, "*.es3.bak"))) \
        if a.all else [a.src or tbh_paths.live_save_path()]
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    dest, n = os.path.join(LAB, stamp), 1
    while os.path.exists(dest):  # dois snapshots no mesmo segundo nao se misturam
        n += 1
        dest = os.path.join(LAB, "%s_%d" % (stamp, n))
    tbh_paths.assert_writable(dest)
    os.makedirs(dest)
    for f in files:
        copy = os.path.join(dest, os.path.basename(f))
        for attempt in range(3):  # o jogo pode estar gravando: valida a COPIA e recopia
            shutil.copy2(f, copy)  # so leitura na origem
            try:
                ver = load_es3(copy)[1].get("version")
                break
            except Exception as e:  # noqa: BLE001
                ver = "ERRO na copia: %s" % e
                time.sleep(1)
        print("%-48s ver=%s" % (os.path.basename(f), ver))
    running = tbh_paths.game_running()
    print("\n-> %s  (%d arquivo(s); jogo rodando: %s)" % (dest, len(files), running))


def cmd_info(a):
    obj, acc, ply = load_es3(a.file)
    steam = str(acc.get("ownerSteamId", ""))
    common = ply.get("commonSaveData") or {}
    print("arquivo      :", a.file, "(%d bytes)" % os.path.getsize(a.file))
    print("versao       : account=%s common=%s" % (acc.get("version"), common.get("version")))
    print("salvo em     :", ticks_to_dt(common.get("lastSavedTime") or acc.get("lastSavedTime")))
    print("steamId      : ...%s" % steam[-4:] if steam else "steamId      : (vazio)")
    print("SystemInfo   :", "OK (chave HMAC atual confere)" if systeminfo_ok(obj, acc) else "NAO CONFERE (chave mudou ou save adulterado)")
    print("topo do PlayerSaveData:")
    for k, v in ply.items():
        d = "list[%d]" % len(v) if isinstance(v, list) else "dict{%d}" % len(v) if isinstance(v, dict) else repr(v)[:60]
        print("  %-30s %s" % (k, d))


def cmd_dump(a):
    obj, acc, ply = load_es3(a.file)
    out = a.out or a.file + ".d"
    for name, data in (("account.json", acc), ("player.json", ply)):
        with open(out_path(os.path.join(out, name)), "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=1)
    print("->", out)


def cmd_schema(a):
    s1 = save_schema(a.file)
    if not a.vs:
        for p in sorted(s1):
            print("%s\t%s" % (p, ",".join(sorted(s1[p]))))
        return
    s2 = save_schema(a.vs)
    print("# %s  ->  %s" % (os.path.basename(a.file), os.path.basename(a.vs)))
    for p in sorted(set(s2) - set(s1)):
        print("+ %s  %s" % (p, sorted(s2[p])))
    for p in sorted(set(s1) - set(s2)):
        print("- %s  %s" % (p, sorted(s1[p])))
    for p in sorted(set(s1) & set(s2)):
        if s1[p] != s2[p]:
            print("~ %s  %s -> %s" % (p, sorted(s1[p]), sorted(s2[p])))


def _optional_table(data_dir, name):
    p = os.path.join(data_dir, "tables", name + ".csv")
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8-sig") as fh:
        rows = list(csv.reader(fh))
    return {r[0] for r in rows[1:] if r} if rows else set()


def cmd_coverage(a):
    data_dir = a.data or os.path.join(ROOT, "data")
    gd = gamedata.GameData(data_dir)
    _, _, ply = load_es3(a.file)
    report, notes, checked, skipped = {}, {}, [], []

    def add(kind, key, why):
        report.setdefault(kind, {}).setdefault(str(key), why)

    def table(name, what):
        keys = _optional_table(data_dir, name)
        (checked if keys is not None else skipped).append("%s (%s)" % (what, name))
        return keys

    heroes = ply.get("heroSaveDatas", [])
    checked.append("herois (HeroInfoData)")
    skills = table("SkillInfoData", "skills")
    for h in heroes:
        hk = h.get("heroKey")
        if str(hk) not in gd.hero_info:
            add("heroi", hk, "fora de HeroInfoData")
        for sk in h.get("equippedSKillKey", []):
            if skills is not None:
                if str(sk) not in skills:
                    add("skill", sk, "fora de SkillInfoData")
            elif gd.skill_name(sk).startswith("Skill "):
                add("skill", sk, "sem SkillName_ nas strings")
    item_info = table("ItemInfoData", "itens")
    checked.append("equipamento (GearInfoData) e encantamentos (StatMod*)")
    for it in ply.get("itemSaveDatas", []):
        k = it.get("ItemKey")
        grp = gd.gear_group(k)
        if item_info is not None and str(k) not in item_info:
            add("item", k, "fora de ItemInfoData")
        if grp and str(k) not in gd.gear:
            add("item", k, "equipamento fora de GearInfoData")
        if gd.name(k).startswith("#"):
            notes.setdefault("sem nome em names_*.json", set()).add(str(k))
        for i, ed in enumerate(it.get("EnchantData", [])[:6]):
            errs = gd.validate_enchant(i, k, ed) if grp else []
            if errs:
                add("encantamento", "%s#slot%d" % (k, i), "; ".join(errs))
    checked.append("runas (RuneInfoData)")
    for r in ply.get("RuneSaveData", []):
        if str(r.get("RuneKey")) not in gd.rune_info:
            add("runa", r.get("RuneKey"), "fora de RuneInfoData (max_runes ignora)")
    pets = table("PetInfoData", "pets")
    for p in ply.get("PetSaveData", []):
        if pets is not None and str(p.get("PetKey")) not in pets:
            add("pet", p.get("PetKey"), "fora de PetInfoData")
        elif pets is None and gd.pet_name(p.get("PetKey")).startswith("Pet "):
            add("pet", p.get("PetKey"), "sem PetName_ nas strings")
    checked.append("moedas (CurrencyInfoData)")
    for c in ply.get("currenySaveDatas", []):
        if str(c.get("Key")) not in gd.currency_info:
            add("moeda", c.get("Key"), "fora de CurrencyInfoData")
    attrs = table("AttributeInfoData", "atributos")
    if attrs is not None:
        for x in ply.get("attributeSaveDatas", []):
            if str(x.get("Key")) not in attrs:
                add("atributo", x.get("Key"), "fora de AttributeInfoData")
    groups = table("AttributeGroupInfoData", "grupos de atributo")
    if groups is not None:
        for h in heroes:
            for g in h.get("unlockedAttributeGroupKeys") or []:
                if str(g) not in groups:
                    add("grupo de atributo", g, "fora de AttributeGroupInfoData")
    cubes = table("CubeRecipeInfoData", "receitas do cubo")
    if cubes is not None:
        for c in ply.get("cubeRecipeSaveDatas", []):
            if str(c.get("CubeKey")) not in cubes:
                add("cubo", c.get("CubeKey"), "fora de CubeRecipeInfoData")
    stages = table("StageInfoData", "estagios")
    if stages is not None:
        common = ply.get("commonSaveData") or {}
        for f in ("maxCompletedStage", "lastClearedStageKey", "currentStageKey", "prevNormalStageKey"):
            if common.get(f) and str(common[f]) not in stages:
                add("estagio", common[f], "%s fora de StageInfoData" % f)
    skins = table("SkinInfoData", "skins")
    if skins is not None:
        for h in heroes:
            sk = h.get("EquippedSkinKey")
            if sk and str(sk) not in skins:
                add("skin", sk, "fora de SkinInfoData")

    print("coverage de %s contra %s" % (os.path.basename(a.file), data_dir))
    print("  checado: " + "; ".join(checked))
    if skipped:
        print("  NAO checado (tabela ausente nesta pasta de dados): " + "; ".join(skipped))
    if not report:
        print("  nenhum ID desconhecido no que foi checado.")
    for kind, entries in sorted(report.items()):
        print("\n[%s] %d desconhecido(s)" % (kind, len(entries)))
        for key, why in list(entries.items())[: a.limit]:
            print("  %-16s %s" % (key, why))
        if len(entries) > a.limit:
            print("  ... +%d" % (len(entries) - a.limit))
    for what, keys in notes.items():
        print("\nnota: %d item(ns) %s (nome vem de outra fonte ou falta): %s" % (
            len(keys), what, ", ".join(sorted(keys)[: a.limit])))


def cmd_roundtrip(a):
    obj, acc, ply = load_es3(a.file)
    sf = es3.SaveFile(json.loads(json.dumps(obj)))
    blob = sf.to_es3_bytes()                     # mesmo caminho do "Salvar" do editor
    obj2 = json.loads(es3.es3_decrypt(blob).decode("utf-8"))
    acc2, ply2 = json.loads(obj2["AccountSaveData"]["value"]), json.loads(obj2["PlayerSaveData"]["value"])
    # json.dumps distingue true/1/1.0 (== do Python nao): troca de tipo conta como diferenca
    same = json.dumps([acc, ply], sort_keys=True) == json.dumps([acc2, ply2], sort_keys=True)
    raw_same = obj2["PlayerSaveData"]["value"] == obj["PlayerSaveData"]["value"]
    orig_ok, new_ok = systeminfo_ok(obj, acc), systeminfo_ok(obj2, acc2)
    print("HMAC do original   :", "OK" if orig_ok else "FALHOU (chave do jogo mudou? o jogo recusaria o regravado)")
    print("HMAC do regravado  :", "OK" if new_ok else "FALHOU")
    print("conteudo identico  :", "sim" if same else "NAO (valor ou tipo mudou na regravacao)")
    print("string identica    :", "sim" if raw_same else "nao (esperado: so a notacao de alguns floats muda)")
    out = a.out or os.path.join(LAB, "roundtrip_" + os.path.basename(a.file))
    with open(out_path(out), "wb") as fh:
        fh.write(blob)
    print("->", out)
    return 0 if same and orig_ok and new_ok else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("snapshot", help="copia o save vivo para o lab")
    p.add_argument("--src", help="arquivo de origem (padrao: SaveFile_Live.es3)")
    p.add_argument("--all", action="store_true", help="copia todos os .es3/.es3.bak da pasta do save")
    p.set_defaults(fn=cmd_snapshot)
    for name, fn in (("info", cmd_info), ("roundtrip", cmd_roundtrip), ("dump", cmd_dump)):
        p = sub.add_parser(name)
        p.add_argument("file")
        if name in ("roundtrip", "dump"):
            p.add_argument("--out")
        p.set_defaults(fn=fn)
    p = sub.add_parser("schema")
    p.add_argument("file")
    p.add_argument("--vs", help="segundo save para comparar")
    p.set_defaults(fn=cmd_schema)
    p = sub.add_parser("coverage")
    p.add_argument("file")
    p.add_argument("--data", help="pasta de dados no formato de data/ (ex research/1.2.8)")
    p.add_argument("--limit", type=int, default=25)
    p.set_defaults(fn=cmd_coverage)
    a = ap.parse_args(argv)
    return a.fn(a) or 0


if __name__ == "__main__":
    sys.exit(main())
