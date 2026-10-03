# TBH Save Editor

Editor web local do save do **Taskbar Hero** (Steam appid 3678970): `python server.py` →
http://127.0.0.1:8765. Python stdlib no runtime; UI em `web/` (HTML/JS puro). Uso e estrutura:
[README.md](README.md). Cripto ES3, `SystemInfo` (HMAC) e engenharia reversa:
[docs/SAVE_PORTING.md](docs/SAVE_PORTING.md). Vocabulário: [CONTEXT.md](CONTEXT.md).

## Estado das versões

- `data/` é da **1.2.8** (`data/VERSION`; promovido de `research/1.2.8/` em 2026-10-03), a
  mesma versão do jogo instalado e do save.
- Senha ES3 e chave HMAC da 1.00.17 **ainda valem** na 1.2.8 (conferido em 2026-09-29).
- Migração 1.2.8: [docs/UPDATE_1.2.8.md](docs/UPDATE_1.2.8.md) (§0 = o que foi feito e o que
  falta). Falta só o teste no jogo, feito pelo usuário.

## O save do usuário é produção

- `SaveFile_Live.es3` (em `%USERPROFILE%\AppData\LocalLow\TesseractStudio\TaskbarHero\`) você
  **lê**; experimentos acontecem numa cópia (`python tools/save_lab.py snapshot`). O jogo
  reescreve esse arquivo a cada poucos minutos enquanto roda e ao fechar.
- **Escrita no save vivo** só com o jogo fechado e pedido explícito do usuário: (a) ele salva pelo
  editor; ou (b) ele pede que você aplique um arquivo pronto. No caso (b):
  `tbh_paths.game_running() is False` (None = trate como aberto); rode `save_lab.py snapshot` e
  informe a pasta criada (é o ponto de volta); mostre `save_lab.py info` do arquivo (HMAC OK);
  espere o "sim"; copie; rode `info` no vivo.
- O editor (`server.py`) abre por padrão o save **vivo** (`%USERPROFILE%`, não `TBH_SAVE_DIR`)
  e o Salvar grava nele. O Salvar recusa (409) com o jogo aberto quando o caminho é uma pasta
  protegida de `tools/tbh_paths.py`, e quando o arquivo mudou desde o load. Para testar,
  carregue uma cópia pelo campo de caminho da UI ou `POST /api/load {"path": "<cópia>"}` e
  confira `GET /api/state` antes de salvar. `/api/*` exige o cabeçalho `X-TBH-Token` (vem na
  página, `<meta name="tbh-token">`) e Host local.
- A instalação do jogo (`steamapps/common/TaskbarHero`) é somente leitura.
- `.claude/hooks/tbh_guard.py` pede confirmação quando o **texto** de uma tool call cita essas
  pastas com cara de escrita. Ele não vê HTTP para o editor nem caminhos montados em runtime; as
  ferramentas de `tools/` se protegem sozinhas com `tbh_paths.assert_writable()`. É cinto de
  segurança, não autorização.

## Invariantes de escrita (o jogo valida no load)

1. `SystemInfo` = Base64(HMAC-SHA256(chave, `account|player|steamId`)) sobre as strings exatas
   gravadas; `core/es3.py` recalcula no `save()`. Nunca troque `ownerSteamId`.
2. Edite o dict carregado **in-place** e preserve todo campo desconhecido — cada versão do jogo
   acrescenta campos (a 1.2.x trouxe `equippedItemBlocked`, `IsBlocked`, `Quantity`,
   `EquippedSkinKey`, `EnchantVersion`...). Nunca reconstrua objetos do save a partir de um
   esquema: encantamento se grava com `GameData.write_enchant()` (campo a campo; slot alterado
   recebe `EnchantVersion` = versão do save, slot igual não é tocado).
3. Encantamento: o jogo aplica todo slot com `Tier > 0` usando `StatType`/`ModType`/`Value`
   **gravados** — eles têm de bater com `StatModInfoData` (faixa e passo) **da versão instalada**.
   `EnchantCount` (não nulo, 3 posições) = slots preenchidos por tipo, nunca menos que os slots
   com `Tier > 0` (o jogo o usa para achar slot livre, UI e mercado); `*AppliedTotalCount` += 1 só
   por aplicação real (alimenta conquista Steam — não inflar); `len(EnchantData)` pela grade
   (0/2/4/6). Limpar um slot = zerá-lo sem deslocar os outros e decrementar `EnchantCount`, como
   a Extração do jogo.
4. Só IDs que existem nas tabelas do jogo: `GameData.enchantable()` recusa item fora de
   `GearInfoData`, de grade desconhecida ou da Steam (`ItemKey` > 9.999.999); item citado numa
   transação pendente (`pending*`, `AlchemyPendingIdList`) também não é editado. Numa versão
   nova do jogo, rode `save_lab.py coverage` antes de editar.
5. Prova de escrita: skill `save-lab`, passo 4.

## Comandos

- Editor: `python server.py` (`TBH_NO_BROWSER=1` não abre o navegador; ver aviso acima).
- Save (só cópias): `python tools/save_lab.py {snapshot,info,dump,schema,coverage,roundtrip}`.
- Dados de uma versão do jogo → `research/<versão>/`: `python tools/extract_version.py`;
  comparação: `python tools/diff_versions.py data research/<versão> --out <arquivo.md>`.
- Código do JOGO (dump IL2CPP) é outro grafo, fora do repo:
  `graphify query "<pergunta>" --graph $HOME/tbh_re/<versão>/game_src/graphify-out/graph.json`
  (também `explain`/`path`/`affected`). O grafo padrão (`graphify-out/`) só tem o editor.
- Testes: `python -m unittest discover -s tests -v` (rotas reais sobre uma cópia do snapshot
  mais novo de `~/tbh_re/saves`, ou `TBH_TEST_SAVE`; sem snapshot, os de save são pulados) e
  `python -m compileall -q server.py core tools tests`.

## Convenções

- Runtime do editor = stdlib (UnityPy só nos extratores). Comentários em português, sem acento
  no código Python, como o código existente.
- `data/` só muda na `/portar-versao`, promovendo `research/<versão>/`. Os scripts de
  `extract/` gravam direto em `data/` (e têm caminhos fixos de outra máquina): não os rode
  avulsos; `tools/extract_version.py` os reusa apontando para `research/`.
- Caminhos de jogo/save das ferramentas vêm de `tools/tbh_paths.py` (bibliotecas da Steam;
  override `TBH_GAME_DIR`/`TBH_SAVE_DIR`). Artefatos grandes de RE (dump IL2CPP, grafo do jogo,
  snapshots de save) ficam fora do repo, em `~/tbh_re/` (override `TBH_RE`).

## Skills

- `/portar-versao <versão>` (só o usuário invoca) — executa a migração de `docs/UPDATE_<versão>.md`.
- Apoio: `diagnosing-bugs` (bug sem causa óbvia; save recusado começa pela `save-lab`), `tdd`
  (testes de roundtrip e das rotas), `codebase-design` (refatorar `server.py`/`gamedata.py`),
  `domain-modeling` (vocabulário do CONTEXT.md), `grilling` (fechar decisões antes de codar),
  `writing-for-agents` (ao editar skills ou este arquivo).

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
