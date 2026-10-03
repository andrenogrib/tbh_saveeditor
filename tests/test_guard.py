"""Hook .claude/hooks/tbh_guard.py (modo pre): pede confirmacao so quando pode escrever no save
vivo ou no jogo. So passa texto ao hook pelo stdin, como o Claude Code faz; nada e executado."""
import json
import os
import subprocess
import sys
import unittest

HOOK = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".claude", "hooks", "tbh_guard.py")
LIVE = "/c/Users/andre/AppData/LocalLow/TesseractStudio/TaskbarHero/SaveFile_Live.es3"
COPY = "~/tbh_re/saves/20261003_015031/SaveFile_Live.es3"


def asks(tool, text):
    key = "command" if tool in ("Bash", "PowerShell") else "file_path"
    ev = {"tool_name": tool, "tool_input": {key: text}, "cwd": ""}
    out = subprocess.run([sys.executable, HOOK, "pre"], input=json.dumps(ev), capture_output=True,
                         text=True, encoding="utf-8").stdout
    return '"ask"' in out


class GuardTest(unittest.TestCase):
    def test_escrita_no_save_vivo_pede_confirmacao(self):
        for text in ("cp edited.es3 " + LIVE,
                     "cp %s %s" % (COPY, LIVE),
                     "S=%s && rm $S" % LIVE,
                     "cp x.es3 ~/tbh_re/../AppData/LocalLow/TesseractStudio/TaskbarHero/SaveFile_Live.es3",
                     'cp %s "$SAVE_DIR/"' % COPY,          # copia para destino variavel
                     "mv %s $DEST" % COPY):
            self.assertTrue(asks("Bash", text), text)
        self.assertTrue(asks("PowerShell", "Copy-Item %s -Destination $env:X" % COPY))
        self.assertTrue(asks("Write", r"C:\Users\andre\AppData\LocalLow\TesseractStudio\TaskbarHero\SaveFile_Live.es3"))

    def test_copias_em_tbh_re_passam(self):
        for text in ("S=%s && python tools/save_lab.py info $S" % COPY,
                     "for S in %s; do TBH_TEST_SAVE=$S python -m unittest discover -s tests; done" % COPY,
                     "rm -f ~/tbh_re/scratch/e2e/SaveFile_Live.es3.bak",
                     "python tools/save_lab.py roundtrip %s --out ~/tbh_re/scratch/rt.es3" % COPY):
            self.assertFalse(asks("Bash", text), text)
        self.assertFalse(asks("Write", r"C:\Users\andre\tbh_re\scratch\SaveFile_Live.es3"))

    def test_leitura_do_save_vivo_passa(self):
        self.assertFalse(asks("Bash", "ls /c/Users/andre/AppData/LocalLow/TesseractStudio/TaskbarHero"))
        self.assertFalse(asks("Bash", "python tools/save_lab.py info " + LIVE))


if __name__ == "__main__":
    unittest.main()
