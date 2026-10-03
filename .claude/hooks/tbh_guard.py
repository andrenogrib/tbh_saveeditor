"""
Hooks do Claude Code para o TBH Save Editor.

  python .claude/hooks/tbh_guard.py pre      (PreToolUse: Write|Edit|MultiEdit|NotebookEdit|Bash|PowerShell)
      Pede confirmacao ao usuario ("ask") quando uma tool call pode ESCREVER no save vivo
      (AppData/LocalLow/TesseractStudio/TaskbarHero) ou na instalacao do jogo
      (steamapps/common/TaskbarHero). Leitura passa direto.
  python .claude/hooks/tbh_guard.py session  (SessionStart)
      Injeta contexto curto: versao do jogo x versao de data/, e se o jogo esta rodando.

E um cinto de seguranca que casa TEXTO: nao enxerga caminho montado em runtime por uma
ferramenta. A defesa real e tbh_paths.assert_writable() dentro de cada tools/*.py.
Falha aberta: qualquer erro -> sai 0 sem saida (nunca trava o trabalho por bug do hook).
"""
import json
import os
import re
import sys

ADJ = re.compile(r"tesseractstudio[\\/]+taskbarhero|steamapps[\\/]+common[\\/]+taskbarhero")

# inicio de segmento que so le (bash e powershell, com aliases comuns)
READ_ONLY = re.compile(
    r"""^(?:ls|dir|cat|head|tail|stat|file|wc|du|sha\d+sum|md5sum|xxd|hexdump|od|strings|cmp|diff
        |grep|rg|find|sort|cut|uniq|tr|awk|sed|less|more|column|jq|echo|printf|cd|pushd|popd|tasklist
        |get-childitem|gci|get-item|gi|get-content|gc|test-path|get-filehash|get-itemproperty
        |select-string|sls|measure-object|measure|select-object|select|where-object|where|\?
        |sort-object|foreach-object|foreach|%|format-\w+|ft|fl|out-string|out-host|write-output
        |write-host|resolve-path|split-path|join-path|get-date|get-process|set-location|sl
        |\[(?:system\.)?io\.(?:file|path|directory)\]::(?:read\w*|exists|get\w*|combine)
        |(?:python3?|py)\s+(?:\./)?tools[\\/][\w.-]+\.py
        |graphify\s+(?:query|path|explain|affected|god-nodes|diagnose)\b)""",
    re.I | re.X)
# verbo de leitura usado com flag que escreve
WRITE_FLAGS = re.compile(
    r"^(?:find\b.*\s-(?:delete|exec|execdir|ok|okdir|fprint\w*)\b|sed\b.*\s-i|xxd\b.*\s-r\b"
    r"|sort\b.*\s-o\b|awk\b.*(?:>|system\())", re.I | re.S)
COPY_VERBS = re.compile(r"^(?:cp|copy-item|cpi|copy|xcopy)\b", re.I)
WRITE_VERBS = re.compile(
    r"\b(?:cp|mv|rm|rmdir|dd|tee|install|rsync|ln|touch|truncate|chmod|mkdir|unzip|tar|7z|copy|move"
    r"|del|erase|ren|xcopy|robocopy|mklink|copy-item|cpi|move-item|mi|remove-item|ri|set-content|sc"
    r"|add-content|ac|out-file|new-item|ni|rename-item|rni|expand-archive|compress-archive"
    r"|clear-content|set-itemproperty)\b|::(?:write|copy|move|delete|append|create)\w*", re.I)
# codigo embutido: heredoc (corpo julgado so pelo que escreve) e segmento "python -c ..." etc.
HEREDOC = re.compile(r"<<-?\s*(['\"]?)(\w+)\1[^\n]*\n(.*?)\n[ \t]*\2[ \t]*(?=\n|$)", re.S)
CODE_INVOKE = re.compile(
    r"""^["']?[^\s"']*?(?:python[\d.]*|py|node|pwsh|powershell)(?:\.exe)?["']?\s+(?:-\w+\s+)*?
        (?:-c|-command|-e|-)(?:\s|$)""", re.I | re.X)
CODE_WRITES = re.compile(
    r"""open\s*\([^)]*?['"](?:w|a|x|r\+|rb\+|wb|ab)|\.write\w*\s*\(|write_(?:bytes|text)|shutil\.\w+
        |os\.(?:remove|unlink|rename|replace|rmdir|removedirs|makedirs|mkdir|symlink|link|truncate|chmod)
        |\.(?:unlink|rename|touch|mkdir|save)\s*\(|to_es3_bytes|file\]::(?:write|copy|move|delete|append)
        |set-content|out-file|add-content|copy-item|move-item|remove-item|new-item|rename-item|expand-archive""",
    re.I | re.X)
REDIRECT = re.compile(r"(?<![<>=\-])\d*>{1,2}(?![&>])\s*(\"[^\"]*\"|'[^']*'|\S+)")
NULL_TARGETS = {"$null", "/dev/null", "nul", "nul:"}
PROP_SET = re.compile(r"\)\s*\.\s*\w+\s*=(?!=)")


# copias em ~/tbh_re (snapshots, scratch) tem o mesmo nome do save vivo, mas nao sao ele
RE_COPY = re.compile(r"[^\s|;&<>()]*tbh_re[\\/][^\s|;&<>()]*")
NOT_A_COPY = ("..", "tesseract", "locallow", "steamapps", "tesser~1", "taskba~1")


def _drop_re_copies(t):
    """Tira do texto os caminhos dentro de tbh_re/ (exceto com .. ou pastas do jogo no meio)."""
    return RE_COPY.sub(lambda m: m.group(0) if any(s in m.group(0) for s in NOT_A_COPY) else " ", t)


def mentions(text):
    """O texto cita o save vivo ou a instalacao do jogo (com ou sem aspas, barras, 8.3...)?"""
    t = _drop_re_copies((text or "").lower().replace('"', "").replace("'", ""))
    return bool(ADJ.search(t)) or "tesseractstudio" in t or "savefile_live" in t \
        or "tesser~1" in t or "taskba~1" in t \
        or ("taskbarhero" in t and ("steamapps" in t or "locallow" in t)) \
        or "live_save_path" in t or "save_dir(" in t or "game_dir(" in t or "game_data_dir(" in t


def split_commands(cmd):
    """Quebra em comandos simples respeitando aspas: && || ; | & e quebra de linha."""
    segs, cur, q, i = [], [], None, 0
    while i < len(cmd):
        c = cmd[i]
        if q:
            cur.append(c)
            if c == q:
                q = None
        elif c in "\"'":
            q = c
            cur.append(c)
        elif cmd.startswith("&&", i) or cmd.startswith("||", i):
            segs.append("".join(cur))
            cur = []
            i += 2
            continue
        elif c == "&" and (i > 0 and cmd[i - 1] == ">" or cmd[i + 1:i + 2] == ">"):
            cur.append(c)  # 2>&1, &> fazem parte do redirecionamento
        elif c in ";|\n&":
            segs.append("".join(cur))
            cur = []
        else:
            cur.append(c)
        i += 1
    segs.append("".join(cur))
    return segs


def tokens(seg):
    """Palavras separadas por espaco fora de aspas, sem as aspas."""
    out, cur, q = [], [], None
    for c in seg:
        if q:
            if c == q:
                q = None
            else:
                cur.append(c)
        elif c in "\"'":
            q = c
        elif c.isspace():
            if cur:
                out.append("".join(cur))
                cur = []
        else:
            cur.append(c)
    if cur:
        out.append("".join(cur))
    return out


def clean(seg):
    seg = seg.strip().lstrip("({").strip()
    seg = re.sub(r"^(?:\$[\w:]+\s*=\s*|[A-Za-z_]\w*=\S*\s+)+", "", seg)  # $x = ... / VAR=v cmd
    return re.sub(r"^&\s*", "", seg).strip()                               # & "exe" (powershell)


def copy_dest(seg):
    """Destino de cp/Copy-Item/copy (ou None se nao der para saber)."""
    toks = tokens(seg)[1:]
    for i, t in enumerate(toks):
        low = t.lower()
        if low in ("-t", "--target-directory", "-destination", "-dest") and i + 1 < len(toks):
            return toks[i + 1]
        if low.startswith("--target-directory="):
            return t.split("=", 1)[1]
    pos = [t for t in toks if not t.startswith("-") and not t.startswith("/")
           or re.match(r"^/[a-z]/", t, re.I)]  # /c/... e caminho, /y e flag do copy
    return pos[-1] if len(pos) >= 2 else None


def segment_writes(seg, cmd_mentions, protected_cwd):
    if not seg or re.fullmatch(r"""(["'])[^"']*\1""", seg):  # vazio ou so um literal
        return False
    low = seg.lower()
    for tgt in REDIRECT.findall(re.sub(r"\"[^\"]*\"|'[^']*'", lambda m: m.group(0) if re.search(r">", m.group(0)) is None else "", seg)):
        t = tgt.strip("\"'").lower()
        if t in NULL_TARGETS:
            continue
        if protected_cwd or mentions(t) or "$" in t or "%" in t:
            return True
    if PROP_SET.search(seg) and (mentions(seg) or "$" in seg):
        return True
    is_read = bool(READ_ONLY.match(seg)) and not WRITE_FLAGS.match(seg)
    if is_read:
        if re.match(r"(?:python3?|py)\s", low):  # tools/*.py: so preocupa um --out protegido
            m = re.search(r"--out(?:put)?[=\s]+(\"[^\"]*\"|'[^']*'|\S+)", seg)
            return bool(m and mentions(m.group(1)))
        return False
    if COPY_VERBS.match(seg):
        dest = copy_dest(seg)
        if dest is not None and not mentions(dest) and "$" not in dest and "%" not in dest \
                and not protected_cwd:
            return False  # copia A PARTIR da pasta protegida = leitura
        return True
    if mentions(seg) or protected_cwd:
        return True
    return cmd_mentions and ("$" in seg or "%" in seg or "~" in seg) and bool(WRITE_VERBS.search(seg))


def shell_may_write(cmd, cwd=""):
    protected_cwd = mentions(cwd)
    cmd_mentions = mentions(cmd)
    if not (cmd_mentions or protected_cwd):
        return False
    # codigo (corpo de heredoc, "python -c ...") e julgado pelo que escreve, nao por citar a pasta
    bodies = [m.group(3) for m in HEREDOC.finditer(cmd)]
    shell = HEREDOC.sub(lambda m: m.group(0).split("\n", 1)[0], cmd)
    inner = re.findall(r"\$\(([^()]*(?:\([^()]*\)[^()]*)*)\)|`([^`]*)`", shell)
    segs = [clean(raw) for raw in split_commands(shell) + [a or b for a, b in inner]]
    code = bodies + [s for s in segs if CODE_INVOKE.match(s)]
    if any(CODE_WRITES.search(c) for c in code):
        return True
    for seg in segs:
        if CODE_INVOKE.match(seg):
            continue
        if re.match(r"^(?:cd|pushd|set-location|sl|chdir)\b", seg, re.I) and mentions(seg):
            protected_cwd = True
            continue
        if segment_writes(seg, cmd_mentions, protected_cwd):
            return True
    return False


def pre(event):
    tool = event.get("tool_name", "")
    ti = event.get("tool_input") or {}
    if not isinstance(ti, dict):
        return
    if tool in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
        path = str(ti.get("file_path") or ti.get("notebook_path") or "")
        hit = mentions(path) or mentions(os.path.normpath(path)) if path else False
    elif tool in ("Bash", "PowerShell"):
        hit = shell_may_write(str(ti.get("command") or ""), str(event.get("cwd") or ""))
    else:
        hit = False
    if not hit:
        return
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "ask",
        "permissionDecisionReason": (
            "TBH guard: esta chamada pode escrever no save vivo ou na instalacao do jogo. "
            "Trabalhe em copias (python tools/save_lab.py snapshot). Escrita real no save so "
            "com o jogo fechado e pedido explicito do usuario."),
    }}, ensure_ascii=False))


def _project_root():
    here = os.path.dirname(os.path.abspath(__file__))
    return os.environ.get("CLAUDE_PROJECT_DIR") or os.path.dirname(os.path.dirname(here))


def _data_version(root):
    try:
        with open(os.path.join(root, "data", "VERSION"), encoding="utf-8") as fh:
            return fh.read().split()[0]
    except (OSError, IndexError):
        pass
    try:
        with open(os.path.join(root, "README.md"), encoding="utf-8") as fh:
            m = re.search(r"extracted from version \*\*([\d.]+)\*\*", fh.read())
            return m.group(1) if m else None
    except OSError:
        return None


def session(_event):
    root = _project_root()
    sys.path.insert(0, os.path.join(root, "tools"))
    import tbh_paths
    gver, dver = tbh_paths.game_version(), _data_version(root)
    running = tbh_paths.game_running()
    parts = ["TBH: jogo instalado %s (%s); data/ extraido da %s%s." % (
        gver or "?", tbh_paths.game_dir() or "pasta do jogo nao encontrada", dver or "?",
        " -> DESATUALIZADO, ver skill game-update" if gver and dver and gver != dver else "")]
    if running:
        parts.append("O jogo esta RODANDO: ele reescreve o save; nao escreva em SaveFile_Live.es3.")
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart",
                                             "additionalContext": " ".join(parts)}}, ensure_ascii=False))


if __name__ == "__main__":
    try:
        mode = sys.argv[1] if len(sys.argv) > 1 else "pre"
        raw = sys.stdin.buffer.read().decode("utf-8", "replace") if not sys.stdin.isatty() else "{}"
        event = json.loads(raw or "{}")
        if isinstance(event, dict):
            {"pre": pre, "session": session}[mode](event)
    except Exception:
        pass
    sys.exit(0)
