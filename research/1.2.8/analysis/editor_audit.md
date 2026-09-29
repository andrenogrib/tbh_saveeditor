# Auditoria do editor contra o save 1.2.8 (com teste local)

Data: 2026-09-29. Save testado: cópia `~/tbh_re/saves/20260929_013650/SaveFile_Live.es3`
(1.2.8, HMAC OK). Nada foi gravado no save vivo nem na instalação do jogo. Nenhum arquivo
existente do projeto foi alterado; só este relatório e rascunhos em `~/tbh_re/scratch/editor_audit/`.

## Resumo

- **Gravação.** O caminho de gravação do editor continua íntegro na 1.2.8. Rodei 17 cenários
  com cada um dos dois GameData (`data` = 1.00.17 e `research/1.2.8`), 34 gravações no total.
  Em todas: HMAC OK (também pelo `save_lab.py info`), arquivo relido idêntico ao que estava em
  memória, `.bak` idêntico ao original e **nenhuma** mudança fora dos caminhos esperados. Os
  campos novos da 1.2.x foram preservados, com uma exceção: a chave `EnchantVersion` some dos
  slots que o editor reescreve (P1-4).
- **P0 confirmado: nenhum.** Falta o teste final, que só você pode fazer: com o jogo fechado,
  abrir no 1.2.8 um save escrito pelo editor. A evidência indireta é boa: o 1.01.05 aceitou um
  save do editor em 17/08 (ver §4).
- **O maior problema é o `data/` velho.** Na **StatModInfoData** mudaram 28 linhas: as faixas de
  resistência T4–T10 (por exemplo, Chaos T10 passou de 50–55 para 80–90). Na
  **StatModGroupInfoData** mudaram 16 linhas. Com `data/`, o `set_enchant` **aceitou 6**
  combinações que o 1.2.8 não gera (ex.: Minotaur Horn → ColdDamagePercent) e **recusou 7**
  combinações válidas. Durante a auditoria, a versão antiga do `diff_versions.py` escondia essas
  mudanças (o DIFF.md dizia "StatModInfoData — igual"). Às 02:13 a ferramenta e o DIFF.md foram
  corrigidos, fora desta auditoria. Conferi o DIFF.md atual com `fulldiff_tables.py`: bate
  (28 / 16 / RuneLevel +184 −14).
- **Bug no `auto_build`.** Ele compara o dicionário inteiro do slot (`server.py:288`). Por causa
  da chave `EnchantVersion`, **178 de 187** slots parecem "alterados" sem nenhuma mudança real.
  O editor então reescreve esses slots e soma +1 em `*AppliedTotalCount` (+187 por execução). O
  save real mostra que isso já aconteceu: a soma foi de 731 para 915 com só 8 slots realmente
  novos. O jogo usa esse contador para uma conquista Steam (≥86 inscrições num item).
- **Valores fora do jogo, sem aviso.** A API aceita nível de herói até 1000 (o jogo vai até 101),
  cubo até 999 (a tabela vai até 100), desbloqueio de pets **de DLC** e runas 1.2.x de drop de
  baú (Plaguelands) no máximo. Também não impede salvar com o jogo aberto (o 1.2.8 grava a cada
  1–2 min) nem com tarefas de servidor pendentes.

## Como rodar o teste

```
python C:/Users/andre/tbh_re/scratch/editor_audit/audit_routes.py
python C:/Users/andre/tbh_re/scratch/editor_audit/audit_routes.py --gd research/1.2.8 --save <outro snapshot .es3>
```

- O script importa `server.py` como módulo, sem chamar `main()` nem abrir porta. Troca
  `server.default_save_path` por uma função vazia e executa o **código real** das rotas:
  `Handler.do_GET/do_POST` recebem um handler falso que injeta path e body e captura
  `(status, json)`.
- Para cada cenário, o snapshot é copiado para
  `scratch/editor_audit/work/<gd>/<cenario>/SaveFile_Live.es3`. Depois vêm `/api/load`, as rotas
  do cenário e `/api/save`, que grava só nessa cópia e no `.bak` dela. Em seguida o script
  decripta de novo e confere: HMAC, igualdade profunda com a memória e com o original (com
  caminhos permitidos por cenário), contagem dos campos 1.2.x e `save_lab.py info`.
- Saída: resumo no stdout e `results_data.json` / `results_research_1.2.8.json` em
  `scratch/editor_audit/`. Leva cerca de 7 s.

Outros scripts usados, todos em `scratch/editor_audit/`:

| script | para quê |
|---|---|
| `fulldiff_tables.py` | diff linha a linha (multiset) de `data/tables` × `research/1.2.8/tables`; corrige o ponto cego do `diff_versions.py` |
| `check_enchantcount.py` | confere `EnchantCount == slots preenchidos por tipo` nos 24 snapshots |
| `scan_versions.py` | formato do `EnchantData` (tamanho por grade, `EnchantVersion`) por versão do save |
| `raw_compare.py` | compara a string crua do save original com a regravada (notação de float) |
| `ga_disasm.py`, `find_callers.py`, `scan_fields.py` | disassembler (capstone) da **cópia** `~/tbh_re/1.2.8/bin/GameAssembly.dll`, com nomes do `script.json` |

## 1. Rotas e UI com o save 1.2.8

Legenda: **OK** funciona · **DEGRADA** funciona, mas com dado/limite errado ou incompleto ·
**CORROMPE** grava estado inválido. Os cenários `sNN` estão em `audit_routes.py`.

| rota / função | código | com `data/` (1.00.17) | com `research/1.2.8` | evidência |
|---|---|---|---|---|
| `GET /`, `/app.js`, `/style.css` | server.py:187-192 | OK | OK | — |
| `GET /icons/<key>` | server.py:193-195 | OK | OK para os 60 itens equipados; ícones novos dependem de `data/icons` (ICONS fixo, server.py:21) | s01 `items_sem_icone=[]` |
| `GET /api/state` | server.py:196-198 | OK | OK | s11 |
| `GET /api/heroes` → `heroes_payload`/`item_payload` | server.py:74-92, 41-71 | OK hoje (6 heróis, 60 itens, 238 entradas, 0 erros); valida com faixas velhas | OK | s01 |
| `GET /api/materials` | server.py:203-210 | OK (36/33/10; ETC/OFFERING/SOULSTONE ficam fora) | OK | s01; `slot=6` gera IndexError não tratado (P3-2) |
| `GET /api/options` → `stat_options` | server.py:211-212; gamedata.py:192-230 | **DEGRADA**: 51 pares (material × grupo) diferem do 1.2.8 | OK (0 divergências) | s01 `options_divergentes_vs_1_2_8` |
| `GET /api/player` → `player_payload`/`runes_summary` | server.py:147-157, 135-144 | **DEGRADA**: 51 runas "sem dados" | OK (248/248) | s01 |
| `POST /api/load` | server.py:225-233 | OK | OK | não avisa sobre pendências nem sobre jogo aberto (P1-8, P2-2) |
| `POST /api/set_enchant` | server.py:234-258 | **DEGRADA**: aceita combos impossíveis no 1.2.8 e recusa válidos | OK nos stats | s02, s12. Nos dois: remove `EnchantVersion` (P1-4) e estende a lista mesmo com erro 400 (P2-1) |
| `POST /api/auto_build` (3 modos × sobrescrever/manter) | server.py:259-299; autobuild.py:248-277 | OK nos stats (0 inválidos vs 1.2.8, por sorte) | OK nos stats | s03: 178/187 reescritas falsas + AppliedTotalCount +187 (P1-3); 45 listas estendidas para 6 (P3-1) |
| `POST /api/set_skills` (3 modos) | server.py:300-320; autobuild.py:206-241 | OK (as 16 skills existem e estão aprendidas neste save) | OK | s04; não valida se a skill foi aprendida (P2-3) |
| `POST /api/set_hero` | server.py:321-339 | **DEGRADA**: aceita nível 102..1000 | idem | s05 gravou nível 102 com status 200 (P1-5) |
| `POST /api/set_currency` | server.py:340-358 | OK | OK | s06 (`Quantity` int, long no jogo) |
| `POST /api/set_pet` / "Desbloquear todos" | server.py:359-373; app.js:393-401 | **DEGRADA**: desbloqueia DLC | idem | s07; PetInfoData 6001-6003 = DLC (P1-7) |
| `POST /api/max_runes` | server.py:374-383 | **DEGRADA**: 0 alteradas, as 20 abaixo do máximo são runas 1.2.x | sobe 20 runas, inclusive Plague (risco, P1-9) | s08 |
| `POST /api/set_cube` | server.py:384-399; app.js:362-375 | **DEGRADA**: aceita nível 101..999 | idem | s09 gravou nível 101 com status 200 (P1-6) |
| `POST /api/save` (reparo de EnchantCount + gravar) | server.py:400-415; es3.py:114-121 | OK | OK | s00: 0 diffs; reparo 0/270 no save 1.2.8 íntegro; s10 conserta contador corrompido de propósito. Sem checagem de jogo aberto/mtime; escrita não atômica (P1-8) |
| UI: carregar, salvar, abas, lista de heróis | app.js:27-83 | OK | OK | — |
| UI: `renderHeroEdit` | app.js:143-180 | **DEGRADA**: input `max: 1000` (L164) contra dica "101" (L167); envia os 3 campos sempre (L171-173) | idem | s05 |
| UI: auto-build e skills | app.js:86-140 | OK; toast mostra slots alterados inflados (L138) | idem | s03 |
| UI: itens e encantamentos (`renderItems`...`setEnchant`) | app.js:183-329 | **DEGRADA** (opções velhas) | OK; mostra só os slots que existem em `EnchantData`, cujo tamanho segue a grade no 1.2.x | s01, s02 |
| UI: aba Jogador (moedas, cubo, pets, runas) | app.js:332-419 | cubo sem máximo (L365), pets de DLC, runas sem aviso | idem | s07-s09 |

## 2. O que muda na 1.2.x no modelo de encantamento (confirmado no código)

| fato | evidência |
|---|---|
| `EnchantData` no save tem tamanho por grade: 0/2/4/6 (RARE/LEGENDARY=2, IMMORTAL=4, ARCANA+=6). No 1.00.11 eram sempre 6 | `scan_versions.py`: 1.00.11 só len 6; 1.01.05+ len por grade |
| O runtime sempre aloca **6** slots (td.bfky=3 × td.bfkz=2) e copia `min(len(save), 6)` entradas. Uma lista maior ou menor é tolerada | disasm `wh.vc.va.khr` RVA 0x98F880 (98fc39-98fc84); `td..cctor` RVA 0x92EFF0 (`[+0x30]=3`, `[+0x34]=2`); td.cs:77-78 |
| `ItemEnchantSaveData.EnchantVersion` (string) apareceu entre a 1.00.11 e a 1.01.05 (não há save 1.00.17 para comparar) e está **null** em 722/722 entradas do save atual | ItemEnchantSaveData.cs:20-21; `scan_versions.py` |
| Ao rolar um encantamento no Cubo, o 1.2.8 grava `EnchantVersion = Application.version` | disasm `wh.Cube.jbs` RVA 0x9216F0 (921883 `Application.get_version` → struct[0x0]); `ItemEnchantSaveData..ctor` RVA 0xAB5120 copia o campo para o save |
| Aplicar no jogo: `*AppliedTotalCount` do tipo +1 **sempre**; coloca o encantamento no 1º slot do tipo com `Tier ≤ 0`; depois `EnchantCount[tipo]++` | disasm `wh.vc.va.jpf` RVA 0x98F270 (98f38a-98f48a, 98f4da-98f53b, 98f5d1) |
| Inscrição: com `InscriptionAppliedTotalCount ≥ 86` num item, o jogo chama `ze.lbn(...)`, que faz Steam `GetAchievement/SetAchievement/StoreStats` | jpf 98f3a9-98f43b (`cmp eax, 0x56`); `ze.lbn` RVA 0xA6DCF0 |
| `EnchantCount[tipo]` decide se ainda há vaga (`EnchantCount < slots da grade`). O invariante 3 do CLAUDE.md vale | `wh.vc.va.dls` RVA 0x98AB90 → `jku` RVA 0x98DD30 (campo 0x1a8 contra 0x58); 24 snapshots com 0 divergências (`check_enchantcount.py`) |
| A Remoção limpa **um** slot e faz `EnchantCount--`, sem compactar. Um buraco (slot 0 vazio, slot 1 cheio) é estado legítimo do jogo, então o "limpar" do editor está correto | `wh.vc.va.brd` RVA 0x98A300 / `jkz` RVA 0x98E410 (`ObscuredInt.zbb`) |
| `ItemSaveData.IsValid()` = `ItemKey > 0 && UniqueId > 0`; nada de encantamento | disasm RVA 0xAB51F0 |

## 3. Lista priorizada

Todos os comandos rodam a partir de `C:/Users/andre/Dropbox/projetos/saveEditor`, salvo indicação.
Onde está escrito `audit_routes.py`, o caminho é `C:/Users/andre/tbh_re/scratch/editor_audit/audit_routes.py`.

### P0 — corrompe o save

**Nenhum confirmado.** Das 34 gravações, nenhuma perdeu campo, quebrou o HMAC ou mudou algo fora
do esperado (tabela do §1; `results_*.json`, campos `verify`). Os itens P1-5, P1-6 e P1-8
**podem** virar P0 no jogo, mas não foi possível verificar sem abrir o jogo.

### P1 — comportamento errado

| id | problema | onde | reproduzir | correção proposta |
|---|---|---|---|---|
| P1-1 | `data/` (1.00.17) diverge do 1.2.8 em **StatModInfoData** (28 linhas: Fire/Cold/Lightning/Chaos Resistance T4–T10; ex. T10 50–55 → 80–90) e **StatModGroupInfoData** (16 linhas; ex. 125001 Minotaur Horn WEAPON 102601 Cold → 102501 Fire; 125002 → 102701 Lightning; 110001 ARMOR T1 → T2). Resultado: o editor **aceitou 6** combinações que o 1.2.8 não gera e **recusou 7** válidas | server.py:19,24 (GD = `data/`); gamedata.py:192-285 | `python fulldiff_tables.py`; `python audit_routes.py --gd data`, cenário `s12_stale_combos` | Promover `research/1.2.8` → `data/` (skill game-update), revisando o DIFF.md atual (já corrigido, P1-2). O autobuild dá o mesmo plano com os dois dados (0 inválidos), mas o `set_enchant` manual não |
| P1-2 **(resolvido durante a auditoria)** | O `diff_versions.py` antigo usava a 1ª coluna como chave (1ª ocorrência vencia) e escondia mudanças em StatModInfoData, StatModGroupInfoData e RuneLevelInfoData. Ele foi reescrito às 02:12 (fora desta auditoria): chave composta mínima via `key_width`, ou linha inteira quando não há chave única. O DIFF.md foi regenerado às 02:13 | tools/diff_versions.py:20-34, 54-70 (versão atual); DIFF.md:80-104 | `python fulldiff_tables.py` e comparar com DIFF.md: StatModInfoData 28, StatModGroupInfoData 16, RuneLevelInfoData +184 −14 — iguais | Nada além de conferir; manter `fulldiff_tables.py` como teste de regressão do diff |
| P1-3 | `auto_build` compara o dict inteiro (`!=`). A entrada do jogo tem `EnchantVersion: null` e a do plano não, então **178/187** slots (balanced), 180 (damage) e 146 (survival) são reescritos sem mudança real e ganham +1 em `*AppliedTotalCount` cada. O toast também mostra números inflados. No save real, entre o `.bak` do editor (17/08) e o daily de 22/08, a soma subiu 731 → 915 com só 8 slots novos. O contador conta para conquista Steam (§2) | server.py:287-292; gamedata.py:146-149 | `audit_routes.py`, `s03_auto_build_*_ow`: `slots_reescritos_so_por_EnchantVersion`, `applied_total_incrementos` | Comparar só `StatModKey, Tier, Value, RecipeType, ModType, MaterialKey, StatType`. Só gravar e dar `bump_applied` se mudou |
| P1-4 | `build_enchant`/`empty_enchant` montam um dict novo **sem `EnchantVersion`** (viola o invariante 2). Ele é gravado nos slots editados, limpos ou do autobuild. Hoje equivale a null para o jogo, mas o 1.2.8 carimba a versão ao encantar (§2) | gamedata.py:240-257; server.py:242, 255, 289 | s02: `enchantVersion_depois=false`; s03: `EnchantVersion` presente em 722 → 535 entradas | Atualizar o dict existente **no lugar** (`ed.update(...)`) preservando chaves. Para slot novo, gravar `EnchantVersion` explicitamente; o valor é decisão do usuário (ver `user_decisions`) |
| P1-5 | `set_hero` aceita `level` de 1 a 1000. No jogo o teto é 101: LevelInfoData tem 1..100 (EXP para subir) e os 6 heróis estão em 101. O lookup do jogo é `TryGetValue` e devolve null fora da tabela; o comportamento a jusante não foi verificado. A UI tem `max: 1000` mas mostra "101" | server.py:329; app.js:164,167; `bdc.nna` RVA 0xB6ED60 | s05 `nivel_acima_do_jogo`: status 200, gravado 102 | Teto = `max(LevelInfoData.Level)+1` (dado, não constante); a UI usa o mesmo valor |
| P1-6 | `set_cube` aceita nível 1..999; CubeLevelInfoData vai de 1 a 100 (100 = 999999999 de EXP). Inferência: o jogo busca a linha com `Find(Predicate<CubeLevelInfoData>)` (`wh.Cube.__c.iwp`), que dá null fora da tabela. A UI não tem `max` | server.py:391; app.js:365; wh.Cube.__c.cs:18-19 | s09 `nivel_acima_tabela`: status 200, gravado 101 | Teto = `max(CubeLevelInfoData.Level)` |
| P1-7 | `set_pet`/"Desbloquear todos" desbloqueia pets de **DLC** (PetInfoData 6001-6003 `UnlockCondition=DLC`, `Param1=4427390`) sem checar posse. O servidor informa os DLC do jogador (`InventoryInitResult.dlc`) | server.py:359-373; app.js:393-401; research/1.2.8/tables/PetInfoData.csv | s07 `pets_dlc_na_tabela` | Carregar PetInfoData; não oferecer desbloqueio de DLC (mostrar a condição); para `KillMonster`, avisar |
| P1-8 | `/api/save` não verifica se o jogo está aberto nem se o arquivo mudou desde o load. O 1.2.8 grava a cada ~1–2 min (backups rotativos com lastSavedTime 01:29:44, 01:31:46, 01:32:46, 01:34:47, 01:35:51): a edição some ou sobrescreve progresso mais novo. A escrita é direta (`open(path,'wb')`), sem tmp + replace | server.py:400-415; es3.py:114-121 | `python tools/save_lab.py info <snap>/SaveFile_Live_{1..5}.es3.bak` | Recusar se `tbh_paths.game_running()`; guardar hash/mtime no `/api/load` e recusar se mudou; gravar em `path.tmp` + `os.replace` |
| P1-9 | Com dados 1.2.8, `max_runes` sobe 20 runas novas, incluindo Plague (`DropChancePlague*`, `MaxAmountPlague*Chest`, `ReduceAutoOpenPlague*`). Elas mexem em drop de baús STAGEBOX (`IsSteamItem=True`). Inferência: o drop passa pelo servidor, pois existe o erro "PopUp_BoxDropError_WrongReport = Invalid request". Existe bloqueio por atividade suspeita ("PopUp_BlockedUser_TradeShip", novo desde a 1.00.17) | server.py:374-383; RuneInfoData.csv; ItemInfoData.csv | `audit_routes.py --gd research/1.2.8`, cenário `s08_max_runes` | Não subir runas que afetam drop, baú ou servidor sem confirmação explícita; listar o que vai mudar antes |

### P2 — funcionalidade faltando / proteção ausente

| id | problema | onde | reproduzir / evidência | correção proposta |
|---|---|---|---|---|
| P2-1 | `set_enchant` estende `EnchantData` **antes** de validar; uma chamada recusada (400) deixa o item mutado | server.py:238-240 (validação só em L245) | s02 `slot_nao_permitido`: item 522193 (RARE), len 2 → 6, `mutou_mesmo_com_erro=true` | Validar slot, grade e opção antes de qualquer mutação; não estender além do necessário |
| P2-2 | Sem guarda para tarefas de servidor pendentes (`pendingEnchantList`, `pendingItemRestorationList`, `AlchemyPendingIdList`, `backendPostList`, `pendingExchange`). O jogo reprocessa essas tarefas no load ("Popup_Notice_Recovery_Enchant", novo desde a 1.00.17) | server.py:225-233, 400-415; PlayerSaveData.cs (campos 0x30-0x58); PendingEnchantSaveData.cs:6-17 | no snapshot estão vazias (`save_lab.py info`) | No load, avisar e bloquear edição se alguma não estiver vazia (ou ao menos do item citado em `GearUniqueId`) |
| P2-3 | `set_skills` não valida se a skill foi **aprendida** (AttributeInfoData `ACTIVESKILL` → `attributeSaveDatas` Level>0) nem se pertence ao herói. Heróis bloqueados (`IsUnLock=false`, DLC 401/501/601) podem ser editados | server.py:300-339; autobuild.py:231-241 | s04 `checks` (neste save todos estão aprendidos) | Usar SkillInfoData + AttributeInfoData; pular herói bloqueado |
| P2-4 | `AbilityPoint` aceita 0..999999, sem teto do jogo (no save: 0 livres, 172–174 alocados em nível 101) | server.py:328 | s05 `ability_999999` gravado | Levantar o total de pontos que se consegue no jogo e limitar |
| P2-5 | `stat_name_to_id.get(...,0)` / `modtype_name_to_id.get(...,0)` gravam `StatType=0 (NONE)` em silêncio se o enum estiver atrás da tabela (hoje cobre 100%) | gamedata.py:224, 227, 250, 252 | enums 1.2.8 cobrem todos os STATTYPE/MODTYPE | Lançar erro em vez de 0 |
| P2-6 | `extract_enums`: o regex `public enum NAME\b` não pega enum aninhado (`wh.vc.EItemGetSourceType`, usado por `ItemGetSourceType` no save). WANTED/EXTRA_ENUMS tem nomes que não existem (GearGroup, GEARGROUP, ECubeRecipeType, EClassType, ECurrencyType, EPlagueIntensity, ERuneType, EPetType, ESkinType). Faltam EGearGroup, ESTAGEDIFFICULTY, ECubeDataType, EEquipClassType, ESlotType, EItemParts, EItemSynthesisType | extract/extract_enums.py:13,18; tools/extract_version.py:26-29 | `grep "enum .*EItemGetSourceType" ~/tbh_re/1.2.8/dump/dump.cs` | Regex `public enum (?:[\w.]+\.)?NAME\b` e lista corrigida |
| P2-7 | Tabelas úteis que o editor não consome (ver §5) | gamedata.py:38-76 | — | Carregar ItemInfoData, LevelInfoData, CubeLevelInfoData, PetInfoData, SkillInfoData e AttributeInfoData (limites e validação) |
| P2-8 | `save_lab coverage` não confere skills × SkillInfoData/AttributeInfoData, pets × PetInfoData, HeroLevel/Cube × tabelas, runas de drop | tools/save_lab.py:148-209 | — | Estender o coverage com as tabelas novas |
| P2-9 | Servidor local aceita POST sem checar Content-Type/Origin (`json.loads` do corpo cru). Uma página web aberta pode mandar `text/plain` para 127.0.0.1:8765 e editar ou salvar (CSRF; depende do navegador) | server.py:220-223 | análise de código | Exigir `application/json`, checar `Origin`/`Host` e usar token por sessão |
| P2-10 | docs/SAVE_PORTING.md §4 recomenda injetar DLL/trainer para tirar a chave. O 1.2.x detecta ("Notice_DetectAnticheat": fecha o jogo e pode restringir o Market). A chave não mudou, então não é preciso. O CLAUDE.md:12 cita `docs/UPDATE_1.2.8.md`, que não existe | docs/SAVE_PORTING.md:58-72; CLAUDE.md:12 | strings_en 1.2.8 | Aviso no doc; criar o UPDATE_1.2.8.md na migração |

### P3 — cosmético / robustez

| id | problema | onde | evidência | correção |
|---|---|---|---|---|
| P3-1 | `auto_build` estende `EnchantData` para 6 (45 itens). O jogo tolera (copia `min(len,6)`) e volta ao tamanho por grade quando regrava | server.py:284-285 | s03 `enchantdata_estendido`; §2 | Só estender até o último tipo com slot na grade |
| P3-2 | `/api/materials?slot=6` gera IndexError não tratado (conexão cai); `/api/options` sem parâmetro gera KeyError | server.py:204-205, 212 | s01 `materials_slot_invalido` = 599 IndexError | Validar parâmetros e devolver 400 |
| P3-3 | `base_key` erra 160101–160110 (OFFERING, nome de 160010); 16 nomes sem ícone (ETC/OFFERING). Não afeta a UI atual (só equipamento) | gamedata.py:152-163 | comparação com ItemInfoData: 0 erros em 5954 GEAR, 10 em materiais, 162 ícones em STAGEBOX/materiais | Usar ItemInfoData.NameKey/IconPath |
| P3-4 | Docstring do autobuild tem números velhos ("+3% a +5.5%" de resistência; agora a individual T10 é 8–9%). O perfil *survival* ignora resistências individuais; `IsMeleeHero` não é usado | autobuild.py:20-32, 119-122 | StatModInfoData 1.2.8 | Revisar texto e perfil (decisão de build) |
| P3-5 | O reparo de `EnchantCount` passa por **todos** os itens (materiais e caixas). Hoje é no-op (0/270), mas deveria mexer só em GEAR | server.py:406-410 | s00 `fixed=0` | Filtrar `gear_group` |
| P3-6 | `data/` sem VERSION; comentário 1.00.17 em es3.py:15; README com 1.00.17 | — | DIFF.md:3 | Gravar VERSION na promoção |
| P3-7 | A UI não mostra `IsUnLock`, `equippedItemBlocked`, `IsBlocked`, `EquippedSkinKey` | server.py:74-92 | save 1.2.8 | Só exibir |
| P3-8 | Regravar muda só a notação de float (`5856266597.3554688` → `…355469`; `1E+09` → `1000000000.0`) e o envelope (CRLF/espaços). Mesmo valor; o 1.01.05 aceitou esse formato | es3.py:96-112 | `raw_compare.py`; `save_lab.py roundtrip` = "conteudo identico: sim" | Nada a fazer |

## 4. O que o jogo valida ou reporta (para o editor ficar dentro do que o jogo aceita)

| mecanismo | evidência | o que o editor deve respeitar |
|---|---|---|
| HMAC `SystemInfo` no load (chave igual à da 1.00.17) | `save_lab.py info`: OK nos 24 snapshots e nas 34 gravações; string `UI_PopUp_SaveDataCheat` | recalcular sempre (já faz); nunca trocar `ownerSteamId` |
| Inventário autoritativo no servidor: itens (`itemKey`, `itemId`, `count`), DLC, estágio, Plaguelands | `InventoryInitResult.cs` (items, dlc, lastClearStageKey, plagueClear, plaguelands); strings `Notice_Delete_OnlyInventoryItem_PopUpText1-3`, `Notice_Create_OnlyServerItem` (novo desde a 1.00.17) | nunca criar, apagar ou trocar ItemKey/UniqueId/quantidade; não editar progresso de estágio |
| Itens encantados não vão para o Market | `TradeShip_UploadItemConditionNotice`, `Toast_NotAllowedEnchantedTrade`; `UploadToSteamData.cs` só leva ItemKey/SteamUniqueId/qty | encantamento fica local (o risco de economia é baixo); isso não vale para runas de drop (P1-9) |
| Coleta em detecção de cheat: nível, estágio, tempo de jogo, id da regra | `UI_DataCollectGuide_Context` | nível, runas, ouro e cubo acima do possível são o tipo de dado que é coletado; avisar o usuário |
| Bloqueio do Trade Ship por atividade suspeita (novo desde a 1.00.17); anti-cheat de programa | `PopUp_BlockedUser_TradeShip`, `Notice_DetectAnticheat` | não usar injeção (P2-10); a regra do servidor é desconhecida |
| Tarefas pendentes reprocessadas no load | `Popup_Notice_Recovery_Enchant` (novo desde a 1.00.17); `PendingEnchantSaveData` (TxId, TimestampTicks) | não editar com pendências (P2-2) |
| Conquista Steam ligada a `InscriptionAppliedTotalCount ≥ 86` | disasm jpf + `ze.lbn` (§2) | não inflar contadores (P1-3) |

Evidência de que o jogo aceita saves escritos pelo editor: `SaveFile_Live.es3.bak` (mtime
17/08 00:30:29) é o backup que o próprio editor cria (o jogo usa `_N.es3.bak`, `_backup_*`,
`Live_daily_*`). O daily de 22/08 (1.01.05, HMAC OK) contém 8 encantamentos novos no valor máximo
do tier, típicos do editor, e a soma de AppliedTotalCount subiu de 731 para 915. O 1.2.8 usa a
mesma cripto e a mesma chave, mas **ainda não houve teste real no 1.2.8**.

## 5. Consumir os dados 1.2.8 (item 3) e extratores (item 4)

`GameData('research/1.2.8')` **carrega sem erro**: 143 materiais (36/33/10 por tipo), 5954 gear,
620 statmods, 248 runas, 534 nomes, 518 ícones. Coverage do save contra ela: só 3 caixas
STAGEBOX sem nome (910051, 910901, 920901), que o editor não mostra. Contra `data/`: 27
equipamentos fora de GearInfoData e 51 runas desconhecidas.

O que precisa mudar no código:

| item | onde | precisa mudar? |
|---|---|---|
| MATERIALTYPE `CRAFTING→ETC` (150001-150010) + ETC/OFFERING/SOULSTONE novos | gamedata.py:53-57 | Não: só entram DECORATION/ENGRAVING/INSCRIPTION |
| Enums novos: `EMaterialType.ETC=7`, `ERecipeType.CORROSION=9`, `StatType.MaxAllElementalResistance=64` | gamedata.py:18-20, 69-72 | Não: valores 3/4/5 inalterados; nenhum enchant usa o stat 64 (StatModInfoData não tem) |
| Faixas e grupos de encantamento | data/tables | **Sim**: promover (P1-1) |
| Limites de nível, cubo e pets | server.py:321-399 | **Sim**: LevelInfoData, CubeLevelInfoData, PetInfoData (P1-5/6/7) |
| Skills | server.py:300-320 | **Sim**: SkillInfoData + AttributeInfoData (P2-3) |
| Nomes e ícones de itens novos (xxx193 etc.) | gamedata.py:152-174 | Não para gear (60/60 com nome e ícone; heurística exata nas 5954 linhas GEAR); usar ItemInfoData para materiais novos (P3-3) |
| `EnchantVersion` | gamedata.py:240-257 | **Sim** (P1-4) |

Tabelas de `research/1.2.8` úteis ao editor — **nova no jogo** ou só **não extraída antes**:

| tabela | uso no editor | nova? (evidência) |
|---|---|---|
| ItemInfoData | GRADE, GearGroup, PARTS, NameKey, IconPath, IsSteamItem, IsCanExchangeMarketable | provavelmente só não extraída (gear já existia); colunas novas não verificáveis |
| LevelInfoData | teto de nível | não extraída antes (HeroLevel existe desde 1.00.11) |
| CubeLevelInfoData | teto do cubo | não extraída antes (`cubeSaveLevelData` no 1.00.11) |
| PetInfoData | DLC / condição | não extraída antes (`PetSaveData` e `PetName_` já na 1.00.17) |
| SkillInfoData + AttributeInfoData | validar skills | não extraídas antes (`attributeSaveDatas` no 1.00.11; `AttributeGroupInfoData` em data/) |
| SkinInfoData / PcSkinInfo | exibir `EquippedSkinKey` | **nova no 1.2.x**: campo entrou no save entre 1.01.05 e 1.2.8 (`save_lab schema --vs`) + 16 strings `Skin*` novas |
| StageInfoData / PlagueIntensityInfoData | só exibir (progresso é do servidor) | Plaguelands é **nova**: `lastPlayedPlagueIntensity` no save a partir da 1.2.x + strings `Plaguelands*`/`StageName_*19` novas |
| RuneLevelInfoData | custo das runas | já extraída; +51 chaves |

Extratores (`tools/extract_version.py` + `extract/*.py`):

- **Tabelas: completo.** 48 de 48 TextAssets do `sharedassets0` extraídas. As 7 de
  `resources.assets` são de TextMeshPro, perf test e nv-templates, sem dado de jogo
  (`tables/_inventory.json`).
- **Localização:** só en/pt e só as coleções ItemTable e StringTable
  (extract_localization.py:17-20, 60-61). Não dá para confirmar se há outras coleções sem abrir
  os bundles. Sugestão: listar todos os `m_TableCollectionName` do shared bundle e avisar.
- **Ícones:** só `sharedassets0` e só chaves de `names_en` com sprite `Item_<k>`/`<TIPO>_<k>`
  (extract_sprites.py:14, 19-20). 16 nomes sem ícone. Nada de herói, pet, runa ou skin. Para
  materiais novos, usar ItemInfoData.IconPath.
- **Enums:** P2-6.
- **Diff:** P1-2, já corrigido.

## 6. Artefatos

- Relatório: este arquivo.
- Scripts e resultados: `C:/Users/andre/tbh_re/scratch/editor_audit/` (`audit_routes.py`,
  `results_data.json`, `results_research_1.2.8.json`, `work/<gd>/<cenario>/`, `fulldiff_tables.py`,
  `check_enchantcount.py`, `scan_versions.py`, `raw_compare.py`, `ga_disasm.py`, `find_callers.py`,
  `scan_fields.py`, `jbs.txt`, `live128/` com o dump JSON do save).
- Efeito colateral no projeto: só `__pycache__` (git-ignored), por causa de `import server` e
  `py_compile`.
