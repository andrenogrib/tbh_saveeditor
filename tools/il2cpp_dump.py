"""
Dump IL2CPP do jogo (Il2CppDumper) para <TBH_RE>/<versao>/ -- fora do repo.

  python tools/il2cpp_dump.py                 copia binarios + roda o dumper -> <RE>/<ver>/dump/
  python tools/il2cpp_dump.py --split         + fatia dump.cs (1 arquivo por tipo) -> <RE>/<ver>/game_src/
  python tools/il2cpp_dump.py --split --only  so refaz o fatiamento de um dump existente

Il2CppDumper nao vem junto: baixe o release oficial (build net6-win) de
https://github.com/Perfare/Il2CppDumper/releases e extraia em <RE>/tools/Il2CppDumper/
(ou passe --dumper). Metadata v31 (Unity 6000.0) funciona com a v6.7.46.

O grafo do codigo do jogo sai de:  graphify update <RE>/<ver>/game_src
e se consulta com:                 graphify query "..." --graph <RE>/<ver>/game_src/graphify-out/graph.json
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tbh_paths  # noqa: E402

TYPE_DECL = re.compile(r"\b(class|struct|enum|interface)\s+([^\s:{]+).*//\s*TypeDefIndex:\s*(\d+)")
IMAGE_HDR = re.compile(r"^// Image \d+: (\S+) - (\d+)")


def run_dumper(dumper, gdir, ver_dir):
    bin_dir = os.path.join(ver_dir, "bin")
    out_dir = os.path.join(ver_dir, "dump")
    os.makedirs(tbh_paths.assert_writable(bin_dir), exist_ok=True)
    os.makedirs(tbh_paths.assert_writable(out_dir), exist_ok=True)
    gdd = tbh_paths.game_data_dir(gdir)
    srcs = [os.path.join(gdir, "GameAssembly.dll"),
            os.path.join(gdd, "il2cpp_data", "Metadata", "global-metadata.dat")]
    for s in srcs:
        shutil.copy2(s, os.path.join(bin_dir, os.path.basename(s)))  # so leitura na origem
    cfg_path = os.path.join(os.path.dirname(dumper), "config.json")
    with open(cfg_path, encoding="utf-8") as fh:
        cfg = json.load(fh)
    if cfg.get("RequireAnyKey", True) or cfg.get("GenerateDummyDll", True):
        cfg.update({"RequireAnyKey": False, "GenerateDummyDll": False})
        with open(cfg_path, "w", encoding="utf-8") as fh:
            json.dump(cfg, fh, indent=2)
    cmd = [dumper] + [os.path.join(bin_dir, os.path.basename(s)) for s in srcs] + [out_dir]
    print("rodando:", " ".join('"%s"' % c for c in cmd))
    r = subprocess.run(cmd, capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=1800)
    print(r.stdout[-3000:])
    if r.returncode != 0 or not os.path.exists(os.path.join(out_dir, "dump.cs")):
        print(r.stderr[-3000:])
        raise SystemExit("Il2CppDumper falhou (rc=%s)" % r.returncode)
    return out_dir


def split_dump(dump_cs, dest, images):
    """Fatia dump.cs em <dest>/<Imagem>/<namespace>/<Tipo>.cs, so das imagens pedidas."""
    with open(dump_cs, encoding="utf-8", errors="replace") as fh:
        lines = fh.read().split("\n")
    starts = []  # (inicio_TypeDefIndex, imagem)
    for ln in lines[:2000]:
        m = IMAGE_HDR.match(ln)
        if m:
            starts.append((int(m.group(2)), m.group(1)))
    starts.sort()

    def image_of(idx):
        img = None
        for st, name in starts:
            if idx >= st:
                img = name
        return img

    blocks, cur = [], None
    for ln in lines:
        if ln.startswith("// Namespace:"):
            cur = [ln]
            blocks.append(cur)
        elif cur is not None:
            cur.append(ln)
    written, taken = {}, set()  # taken: caminhos em normcase (o disco do Windows ignora caixa)
    tbh_paths.assert_writable(dest)
    os.makedirs(dest, exist_ok=True)
    skipped = 0
    for b in blocks:
        head = b[:next((i for i, x in enumerate(b) if x.strip() == "{"), len(b))]  # ate o '{'
        decl = next((TYPE_DECL.search(x) for x in head if TYPE_DECL.search(x)), None)
        if not decl:
            skipped += 1
            continue
        img = image_of(int(decl.group(3)))
        if images and img not in images:
            continue
        ns = b[0][len("// Namespace:"):].strip() or "_global"
        name = re.sub(r"[^\w.-]", "_", decl.group(2))[:120]
        folder = os.path.join(dest, (img or "unknown").replace(".dll", ""), re.sub(r"[^\w.-]", "_", ns))
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, name + ".cs")
        n = 1
        while os.path.normcase(path) in taken:  # mesmo nome saneado (ou so muda a caixa)
            n += 1
            path = os.path.join(folder, "%s_%d.cs" % (name, n))
        taken.add(os.path.normcase(path))
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(b).rstrip() + "\n")
        written[path] = img
    print("fatiado: %d tipos -> %s%s" % (len(written), dest,
                                          (" (%d blocos sem declaracao reconhecida)" % skipped) if skipped else ""))
    return written


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--game", help="pasta do jogo (padrao: detectada pela Steam)")
    ap.add_argument("--version", help="rotulo da versao (padrao: Version.txt do jogo)")
    ap.add_argument("--dumper", default=os.path.join(tbh_paths.re_root(), "tools", "Il2CppDumper", "Il2CppDumper.exe"))
    ap.add_argument("--split", action="store_true", help="fatia dump.cs por tipo em game_src/")
    ap.add_argument("--only", action="store_true", help="nao roda o dumper; so fatia o dump existente")
    ap.add_argument("--images", default="Assembly-CSharp.dll",
                    help="imagens (dll) a manter no fatiamento, separadas por virgula; --images= (vazio) = todas")
    a = ap.parse_args()
    gdir = a.game or tbh_paths.game_dir()
    ver = a.version or tbh_paths.game_version(gdir)
    if not gdir or not ver:
        raise SystemExit("jogo nao encontrado; use --game/--version")
    ver_dir = os.path.join(tbh_paths.re_root(), ver)
    if not a.only:
        if not os.path.isfile(a.dumper):
            raise SystemExit("Il2CppDumper nao encontrado em %s (ver docstring)" % a.dumper)
        run_dumper(a.dumper, gdir, ver_dir)
        with open(tbh_paths.assert_writable(os.path.join(ver_dir, "VERSION")), "w", encoding="utf-8") as fh:
            fh.write("%s build=%s game=%s\n" % (ver, tbh_paths.game_build_guid(gdir), gdir))
    if a.split or a.only:
        images = {x.strip() for x in a.images.split(",") if x.strip()}
        split_dump(os.path.join(ver_dir, "dump", "dump.cs"), os.path.join(ver_dir, "game_src"), images)
    print("ok ->", ver_dir)


if __name__ == "__main__":
    main()
