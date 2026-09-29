"""
Localiza jogo, save e area de RE nesta maquina (sem caminho fixo) e protege as
pastas do jogo contra escrita acidental pelas ferramentas.

Ordem de busca:
  jogo : env TBH_GAME_DIR -> bibliotecas da Steam (registro + libraryfolders.vdf)
  save : env TBH_SAVE_DIR -> %USERPROFILE%/AppData/LocalLow/TesseractStudio/TaskbarHero
  RE   : env TBH_RE       -> ~/tbh_re   (dump IL2CPP, snapshots de save, grafo do jogo)
"""
import os
import re
import subprocess

STEAM_APPID = "3678970"
INSTALL_DIR = "TaskbarHero"
EXE_NAME = "TaskBarHero.exe"
LIVE_SAVE_NAME = "SaveFile_Live.es3"


def save_dir():
    env = os.environ.get("TBH_SAVE_DIR")
    if env:
        return env
    home = os.environ.get("USERPROFILE") or os.path.expanduser("~")
    return os.path.join(home, "AppData", "LocalLow", "TesseractStudio", "TaskbarHero")


def live_save_path():
    return os.path.join(save_dir(), LIVE_SAVE_NAME)


def re_root():
    return os.environ.get("TBH_RE") or os.path.join(os.path.expanduser("~"), "tbh_re")


def _steam_root():
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as k:
            return os.path.normpath(winreg.QueryValueEx(k, "SteamPath")[0])
    except Exception:
        return r"C:\Program Files (x86)\Steam"


def steam_libraries():
    root = _steam_root()
    libs = [root]
    try:
        with open(os.path.join(root, "steamapps", "libraryfolders.vdf"), encoding="utf-8", errors="ignore") as fh:
            libs += [p.replace("\\\\", "\\") for p in re.findall(r'"path"\s+"([^"]+)"', fh.read())]
    except OSError:
        pass
    out, seen = [], set()
    for p in libs:
        k = os.path.normcase(os.path.normpath(p))
        if k not in seen:
            seen.add(k)
            out.append(os.path.normpath(p))
    return out


def game_dir():
    """Pasta de instalacao (contem TaskBarHero.exe) ou None se nao achar."""
    env = os.environ.get("TBH_GAME_DIR")
    if env:
        return env
    for lib in steam_libraries():
        d = os.path.join(lib, "steamapps", "common", INSTALL_DIR)
        if os.path.isfile(os.path.join(d, EXE_NAME)):
            return d
    return None


def game_data_dir(gdir=None):
    gdir = gdir or game_dir()
    return os.path.join(gdir, "TaskBarHero_Data") if gdir else None


def game_version(gdir=None):
    """Versao do jogo instalado (Version.txt na raiz, ex '1.2.8') ou None."""
    gdir = gdir or game_dir()
    if not gdir:
        return None
    try:
        with open(os.path.join(gdir, "Version.txt"), encoding="utf-8", errors="ignore") as fh:
            return fh.read().strip() or None
    except OSError:
        return None


def game_build_guid(gdir=None):
    """build-guid do boot.config (muda a cada build publicado)."""
    gdd = game_data_dir(gdir)
    try:
        with open(os.path.join(gdd, "boot.config"), encoding="utf-8", errors="ignore") as fh:
            m = re.search(r"^build-guid=(\w+)", fh.read(), re.M)
            return m.group(1) if m else None
    except (OSError, TypeError):
        return None


def game_running():
    """True se TaskBarHero.exe esta rodando (Windows). None se nao deu para saber."""
    try:
        out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq %s" % EXE_NAME, "/NH"],
                             capture_output=True, text=True, timeout=10).stdout
        return EXE_NAME.lower() in out.lower()
    except Exception:
        return None


def _norm(p):
    p = os.path.realpath(os.path.abspath(p))  # resolve junction/symlink
    if p.startswith("\\\\?\\"):
        p = p[4:]
    return os.path.normcase(p)


def protected_dirs():
    """Pastas que as ferramentas NUNCA escrevem: save vivo e instalacao do jogo.
    Os overrides (TBH_SAVE_DIR/TBH_GAME_DIR) somam as pastas padrao, nao as substituem."""
    home = os.environ.get("USERPROFILE") or os.path.expanduser("~")
    dirs = [save_dir(), os.path.join(home, "AppData", "LocalLow", "TesseractStudio", "TaskbarHero")]
    for lib in steam_libraries():
        dirs.append(os.path.join(lib, "steamapps", "common", INSTALL_DIR))
    g = game_dir()
    if g:
        dirs.append(g)
    return dirs


def is_protected(path):
    p = _norm(path)
    for d in protected_dirs():
        d = _norm(d)
        if p == d or p.startswith(d + os.sep):
            return True
    return False


def assert_writable(path):
    """Levanta erro se `path` cair dentro do save vivo ou da instalacao do jogo."""
    if is_protected(path):
        raise PermissionError(
            "recusado: %s fica dentro de uma pasta protegida do jogo/save. "
            "As ferramentas trabalham em copias (ver tools/save_lab.py snapshot)." % path)
    return path
