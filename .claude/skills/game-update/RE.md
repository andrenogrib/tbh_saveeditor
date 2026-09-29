# Engenharia reversa do Taskbar Hero

Referência da skill `game-update`. O histórico do método (Ghidra, oráculo, DLL) está em
[docs/SAVE_PORTING.md](../../../docs/SAVE_PORTING.md); aqui fica o que se usa hoje. Os comandos
usam `$HOME` porque funciona no bash e no PowerShell (`~` não expande para executáveis nativos no
PowerShell 5.1).

## Área de trabalho

```
$HOME/tbh_re/
  tools/Il2CppDumper/        release oficial (build net6-win); config.json é ajustado pelo wrapper
  <versão>/bin/              cópias de GameAssembly.dll + global-metadata.dat
  <versão>/dump/             dump.cs, script.json, stringliteral.json, il2cpp.h
  <versão>/game_src/         dump.cs fatiado: <Imagem>/<namespace>/<Tipo>.cs
  <versão>/game_src/graphify-out/graph.json   grafo do código do jogo
  saves/<timestamp>/         snapshots de save (tools/save_lab.py)
  scratch/                   rascunhos de análise
```

## Dump IL2CPP

- `python tools/il2cpp_dump.py --split` copia os binários (só leitura na origem), roda o
  Il2CppDumper e fatia só `Assembly-CSharp.dll` (o código do jogo; `--images=` = todas as
  imagens). Sem o dumper, baixe o release em https://github.com/Perfare/Il2CppDumper/releases
  (`Il2CppDumper-net6-win-*.zip`; exige runtime .NET 6) e extraia em `$HOME/tbh_re/tools/Il2CppDumper/`.
- 1.2.8: metadata v31, Unity 6000.0.72; v6.7.46 funciona. Assembly-CSharp = TypeDefIndex 0–2035.
- Imagens de interesse: `Assembly-CSharp` (jogo), `Backend.dll` (SDK de servidor),
  `ACTk.Runtime.dll` (Anti-Cheat Toolkit), `Newtonsoft.Json` (serialização do save).
- Classes do save: namespace `TaskbarHero.EasySaveData` + `PlayerSaveData`, `AccountSaveData`,
  `CommonSaveData`. Classes ofuscadas se identificam por consts, campos e vizinhos no grafo. Na
  1.2.8: `bde` = gerenciador do save (campos `AccountSaveData`/`PlayerSaveData`, consts
  `"SystemInfo"`, `"|"`, `"_backup_"`, `"_daily_"`, `"SaveFile_"`); `bdf` = keystore estático
  (métodos `static byte[]`, públicos `lxc()` e `gwj()`).

## Armadilhas da ofuscação (GUPS.Obfuscator)

- **Clones sem chamador e métodos isca.** O ofuscador duplica métodos (mesmos bytes, nenhum
  chamador) e o linker funde funções idênticas (um RVA com vários nomes). Antes de citar um RVA como
  evidência, confirme que ele tem chamador — contando `call` (E8) **e** `jmp` de tail-call (E9). Na
  1.2.8 os vivos são `bde.nof` (load), `wh.wb.jye` (estágios), `wh.vc.va.jkq`/`jkx`/`jkz` (itens:
  carregar/encantar/extrair); `bde.dez`, `wh.wb.bad`, `wh.vc.va.jpf`/`khr` são clones mortos.
- **Strings cifradas.** Literais do código vivem num blob XOR em
  `<PrivateImplementationDetails>{GUID}.a` (`b[i] ^= (i & 0xFF) ^ 0xAA`); `stringliteral.json` não acha
  textos de jogo (`Popup_*`, "plague"...). Use as chaves de `research/<versão>/strings_*.json` e o
  decodificador do estudo 1.2.8.
- Desmontadores do estudo 1.2.8 (capstone sobre a cópia do binário, com nomes do `script.json`):
  `$HOME/tbh_re/scratch/{integrity_backend,stages_plague,save_schema,editor_audit}/` — `disasm.py`/
  `tbhdis.py`/`il2dis.py` (desmontar um RVA), `xref.py` (chamadores), `strblob.py` (strings).

## Grafo do jogo (graphify)

- Construir: `graphify update $HOME/tbh_re/<versão>/game_src` — AST local, nada sai da máquina.
  Na 1.2.8: ~30 mil nós; ~130 enums dão aviso de sintaxe (o dump escreve `const` dentro de
  `enum`) e ficam só com o símbolo, sem perda relevante.
- Consultar (de qualquer pasta), sempre com
  `--graph $HOME/tbh_re/<versão>/game_src/graphify-out/graph.json`:
  `graphify explain "HeroSaveData"` (campos/vizinhos), `graphify query "<pergunta>" --budget 3000`,
  `graphify path "A" "B"`, `graphify affected "X"` (quem depende de X).
- Busca exata continua sendo `grep` em `dump.cs` (RVA, offset, atributos) e
  `stringliteral.json` (textos, URLs, nomes de chave).

## Chave HMAC do SystemInfo

- Oráculo: `python tools/save_lab.py info <snapshot>` → "OK" = `SYSTEMINFO_HMAC_KEY` de
  `core/es3.py` ainda vale (vale na 1.2.8).
- Se não valer: a chave é derivada em runtime. 1.00.17: `bal.Awake` → `bgco = bam.mdj()`. 1.2.8:
  `bde.Awake` (0xB7BE80) → `bdf.nos()` (0xB8CCC0) e `bihy = bdf.nox()` (0xB8D490); o SystemInfo é
  montado em `bde.nnv` (0xB85550) e comparado em `bde.hkv`; a validação do load é `bde.nof`
  (0xB86990). Numa versão nova, reache esses papéis pelo mesmo padrão (const `"SystemInfo"`,
  `HMACSHA256..ctor`), não pelos nomes.
- **Não use injeção de DLL/trainer (o "F8" do SAVE_PORTING.md §4) na 1.2.x**: o ACTk detecta,
  reporta e fecha o jogo. Prefira ler a derivação da chave na desmontagem da cópia do binário; se for
  inevitável algo com o jogo aberto, isso é decisão do usuário, com o risco explicado.

## Senha ES3

- Se `save_lab.py info` falha ao decriptar, a senha mudou: SAVE_PORTING.md §2 (construtor de
  `ES3Settings` no gerenciador do save; `stringliteral.json`).
