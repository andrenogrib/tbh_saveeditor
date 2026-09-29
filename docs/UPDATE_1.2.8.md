# Atualização 1.2.8 — o que mudou e como o editor acompanha

Estudo de 2026-09-29 sobre o jogo instalado (1.2.8, build `3a1772f1…`) e o save do usuário.
Tudo foi feito em **cópias**: 24 snapshots de save (versões 1.00.11 → 1.2.8), a cópia do
`GameAssembly.dll` + dump IL2CPP em `~/tbh_re/1.2.8/` e os dados extraídos em `research/1.2.8/`.
Nada foi gravado no save vivo nem na instalação do jogo.

Evidência detalhada (cada afirmação daqui tem origem lá):
[save_schema](../research/1.2.8/analysis/save_schema.md) ·
[items_enchants](../research/1.2.8/analysis/items_enchants.md) ·
[stages_plague](../research/1.2.8/analysis/stages_plague.md) ·
[progression](../research/1.2.8/analysis/progression.md) ·
[integrity_backend](../research/1.2.8/analysis/integrity_backend.md) ·
[editor_audit](../research/1.2.8/analysis/editor_audit.md) ·
[DIFF de dados](../research/1.2.8/DIFF.md).

---

## 1. Resumo

1. **O editor ainda grava saves que o jogo aceita.** Senha ES3 e chave HMAC não mudaram (validam os
   24 snapshots, da 1.00.11 à 1.2.8). O caminho de gravação passou em 34 gravações de teste em cópias
   (todas as rotas, com os dados velhos e os novos) e num teste HTTP de ponta a ponta: HMAC OK, nada
   fora do editado mudou, campos novos preservados — exceto `EnchantVersion` (§5, P1-4). Falta o teste
   final no jogo, que só pode ser feito com o jogo fechado (§6, passo 8).
2. **O jogo virou "baseado em servidor" — este é o fato mais importante.** Desde a 1.01.05 os itens são
   itens do Steam Inventory (negociáveis no Steam Market) e o servidor (TheBackend) é a autoridade sobre
   quais itens existem. A cada abertura do jogo e a cada 8 h de jogo, ele envia ao estúdio um
   **snapshot do save** (ouro, heróis, atributos, pets, runas, inventário, cubo e todos os itens com
   encantamentos). Toda edição fica visível para o desenvolvedor, que tem bloqueio de conta e do
   Trade Ship.
3. **Os dados do editor (1.00.17) estão errados para a 1.2.8 onde importa:** 28 faixas de valor de
   encantamento (resistências T4–T10) e 16 opções de material mudaram. Com `data/` o editor oferece
   1286 combinações que o jogo 1.2.8 não gera e recusa 2481 válidas. Também faltam 194 equipamentos
   (variante 3 dos modelos Lv80/Lv90), 51 runas, 18 materiais e as tabelas de nível/cubo/pets/skills
   que dariam os limites reais.
4. **Bugs do editor que já afetaram o save:** o `auto_build` reescreve à toa ~95% dos slots (por causa
   do `EnchantVersion`) e soma +1 no contador de aplicações de cada um — no save real a soma foi de
   731 para 915 com só 8 encantamentos novos. Esse contador alimenta uma conquista Steam (≥ 100
   inscrições num item, checada quando se encanta **no jogo**; o máximo por item hoje é 24, então não
   disparou). O editor também aceita nível de herói até 1000 (máx. real 101; o jogo **não** corrige) e
   cubo até 999 (máx. 100; o jogo corrige o nível no load, mas não o Exp), e oferece desbloquear pets
   de **DLC** (no seu save eles já estão desbloqueados desde junho, antes do editor existir — o problema
   é o editor oferecer isso).
5. **Plano:** promover os dados da 1.2.8, corrigir o caminho de encantamento, travar valores nos
   limites reais do jogo, retirar o que contorna conteúdo pago ou conversa com a economia do Market, e
   avisar o usuário do que é visível ao servidor. Detalhe em §6; decisões em §7.

---

## 2. Como a 1.2.8 trata o save

### 2.1 Carregar, validar, salvar (gerenciador `bde`; era `bal` na 1.00.17)

| Etapa | O que o jogo faz |
|---|---|
| Load (`bde.noe`/`nof`) | exige as 3 chaves ES3; confere `SystemInfo` = Base64(HMAC-SHA256(chave, `account|player|ownerSteamId`)) e `ownerSteamId` = Steam logado. Não confere `version`, `playTime`, `sessionCounter` etc. |
| HMAC inválido | log + **relatório `Save_Tampered` ao servidor do estúdio** (com o ticket Steam; o reporter já está ativo antes do load) + popup + restaura o `SaveFile_Live_N.es3.bak` rotativo válido mais novo; sem backup válido, não salva na sessão (nem ao fechar) |
| `SystemInfo` ausente / `ownerSteamId` diferente | restaura o `.bak` rotativo, **sem** relatório |
| JSON inválido (save quebrado) | cai no tratamento de exceção e restaura o `.bak` **sem relatório e sem popup** — a edição some calada |
| Conta bloqueada | o servidor responde 403 "Forbidden blocked user" e o boot para: o jogo não carrega |
| Durante o jogo | autosave a cada **180 s**, ~50 pontos de save por evento, save síncrono ao fechar — edição externa com o jogo aberto é sobrescrita em minutos |
| Ao salvar (`PreSave`) | **reconstrói** heróis, itens, moedas, cubo etc. a partir da memória; `EnchantData` volta ao tamanho da grade; item com `ItemKey` desconhecido ou `UniqueId` duplicado some no load |
| Backups do jogo | `SaveFile_Live_1..5.es3.bak` (rotativo, após cada save; o único usado na restauração automática), `SaveFile_Live_backup_*` (≥ 6 h, 5 cópias), `Live_daily_*` (≥ 24 h, 30 cópias), `SaveFile_Live_BackendBackUp.es3` (uma vez; é de 2026-06-14). `SaveFile_Live.es3.bak` é do editor e só guarda o estado de antes do **último** Salvar |

### 2.2 O que sobe para o servidor

| Canal | Conteúdo | Quando |
|---|---|---|
| `DataSnap` (GameLog TheBackend) | `commonSaveData`, moedas, heróis, atributos, pets, runas, inventário, baú, trade ship, receitas e nível do cubo, **todos os itens com encantamentos** (fica de fora: configurações, correio, pendências, agregados) | todo boot e a cada 28.800 s de jogo |
| `inventoryV2` (`initV2`/`mergeInventory`) | inventário autoritativo; a sincronização compara `UniqueId → ItemKey` (não a quantidade nem os encantamentos): item só local é **apagado** (`AnomalyItem`); `ItemKey` divergente é `TemperedItem` | boot e **depois de cada encantamento** feito no jogo |
| Estatísticas Steam | `cube_level`, `max_hero_level`, `play_time_minutes` (= `account.playTime`/60), `total_gold_earned`, `highest_gear_grade`... publicadas a partir do estado carregado | **a cada autosave (180 s)** e ao fechar — um valor impossível vira estatística Steam em até 3 min |
| `consumeV2`/`corrosionV2` | materiais gastos **e o nível do cubo (`cubeLev`)** | a cada encantamento/corrosão |
| `stageClear` / `initV2` | `lastClearedStageKey` (e o servidor sobrescreve o local) | login e cada clear novo |
| CheatReporter | `Save_Tampered`, `Level_50/80` (no load, herói ≥ 50/80 com `play_time_minutes` < 600/3000), `Gold_Massive` (ganho de ouro com saldo > 100 M e playtime < 600 min), `ItemLevel_*`, `Grade_*`, `Box_*`, `ACTk_*`. O playtime vem do próprio save (`playTime`/60, publicado como estatística Steam): no save atual são ~39.500 min, então `Level_*`, `Gold_Massive` e `ItemLevel_*` **não disparam nesta conta** | no evento; `Save_Tampered` e `ACTk_*` com cooldown de 30 s, os demais 1 por tipo por sessão |
| CloudSave do servidor (baixado no boot) | `snapshot` sobrescreve o progresso local; `itemRestoration` sobrescreve encantamentos de itens | quando o estúdio coloca |
| Skins | skin equipada não possuída volta à padrão e gera `SkinLog` | no load |

Rankings, cupons e upload do `.es3` em si não aparecem no código (o arquivo pode ir pelo Steam
Auto-Cloud, configurado fora do jogo).

### 2.3 Anti-cheat (ACTk)

TimeCheating, SpeedHack e ObscuredCheating ativos, com watchdog de 30 s; detecção = relatório +
**fecha o jogo**. Editar o arquivo de save **não** aciona o ACTk. Injetar DLL/trainer aciona — por isso
o passo de "extrair a chave com o trainer (F8)" de `docs/SAVE_PORTING.md` §4 **não deve ser usado** na
1.2.x (e hoje nem é necessário: a chave não mudou).

---

## 3. O que mudou nos dados (1.00.17 → 1.2.8)

Linha do tempo pelo histórico de saves: **1.01.05** trouxe a camada de servidor/Steam Inventory
(pendências, BoxBucket, rekey de itens, trade ship novo); **1.2.3** trouxe Plaguelands, skins,
estatística por conteúdo e opções de UI; **1.2.8** trouxe cadeado no slot e pilhas de material.

| Área | Mudança | Efeito no editor |
|---|---|---|
| Enums | `StatType` +`MaxAllElementalResistance=64`; `ERecipeType` +`CORROSION=9`; `EMaterialType` +`ETC=7`; nenhum valor antigo mudou de número | nenhum encantamento usa os novos; 126 enums do jogo em `research/1.2.8/enums_all.json` |
| Encantamento | `StatModInfoData`: 28 linhas (Fire/Cold/Lightning/Chaos Res T4–T10 maiores, ex. T10 50–55 → 80–90); `StatModGroupInfoData`: 16 linhas (ex. Minotaur Horn arma: Cold% → Fire%; Griffin Beak: → Lightning%; vários tiers de armadura +1) | **validação e opções erradas com `data/`**; nenhum dos 243 encantamentos do save usa opção alterada |
| Efeito do encantamento | o jogo aplica os slots com `Tier > 0` usando `StatType/ModType/Value` **gravados** (não consulta a tabela no load); `EnchantCount` decide slot livre, UI e mercado — se ficar **menor** que os slots ocupados, o jogo pode gravar o próximo encantamento no slot do tipo seguinte; slot fora da grade vale até o próximo save e depois some; ao rolar, o jogo grava `EnchantVersion = versão do jogo` e o load preserva o valor | invariante 3 do CLAUDE.md corrigida; preservar `EnchantVersion`; `EnchantCount` sempre = slots ocupados |
| Equipamentos | +194 chaves (`x193`/`x173` = variante 3 dos modelos Lv90/Lv80); v1/v2 marcadas `IsDeletedInServer`; 2257 linhas rebalanceadas (stats são derivados da tabela em runtime — nada a migrar) | heurísticas de chave continuam certas para GEAR; usar `ItemInfoData` para materiais/caixas |
| Materiais | +18 (Plague Fruit, Contaminated Soulstone, moedas de aniversário não negociáveis); moedas 1500xx CRAFTING → ETC | nenhum é material de encantamento |
| Runas | +51 (34 de Plaguelands), novas de fato | `max_runes` com `data/` não faz nada; com 1.2.8 mexe em runas de drop/baú (§4) |
| Estágios | 120 NORMAL/ACTBOSS já existiam; **novos: 60 PLAGUE + 9 CONTAMINACTBOSS**; o servidor manda no progresso | progresso somente leitura |
| Skins | `SkinInfoData` nova; posse vem do Steam Inventory, não do save | não criar função |
| Pets | nenhum novo; 6001–6003 são **DLC** (app 4427390) | não desbloquear DLC |
| Heróis/skills | sem herói ou skill nova; nível máximo 101; `IsMeleeHero` novo; atributos +1 ponto por nível | limites reais |
| Cubo | nível 1..100 (`Exp` float; 999.999.999 no 100); receita CORROSION (cubo nv 30) | limites reais |
| Esquema do save | 1.2.8: `equippedItemBlocked`, `IsBlocked`/`Quantity` nos slots; material = 1 item por ItemKey com até 5 por slot; `itemSaveDatas[].IsBlocked` virou legado | nada a editar; preservar |

---

## 4. Risco por função do editor

Risco = chance de o jogo rejeitar/reverter × exposição no servidor × efeito em conteúdo pago ou na
economia do Market.

| Função | Risco | Motivo | Proposta |
|---|---|---|---|
| Encantamento dentro das tabelas da 1.2.8 | **baixo–médio** | indistinguível de legítimo; aparece no DataSnap; item encantado não pode ir ao Market | manter, com dados 1.2.8 e validação completa |
| Skills (loadout) | **baixo** | escolha reversível | manter, validando skill aprendida/slot 3 (runa 27) |
| Runas | **alto** para as que faltam | no save atual as 197 runas antigas já estão no máximo; as 20 que faltam (todas novas da 1.2.x) só aumentam chance de drop, capacidade e auto-abertura de baús — baús que o servidor processa e cujos itens são negociáveis no Steam Market; completá-las no jogo custa 28,7 bilhões de ouro; a contagem de caixas tem relatório próprio (`Box_*_Rate/Volume`) que não depende do tempo de jogo | fora do "maximizar": runas de drop/baú não são elevadas pelo editor; nunca acima de `MaxLevel` |
| Ouro | **médio** | aparece no DataSnap e diverge de `total_gold_earned` da Steam; `Gold_Massive` só para contas com pouco tempo de jogo (não a sua) | avisar acima de 100 M |
| Herói (nível/EXP/pontos) | **médio** | aparece no DataSnap e em `max_hero_level` da Steam (a cada 3 min); `Level_50/80` só para contas com pouco tempo de jogo; nível > 101 fica e trava level-ups | nível 1..101; pontos dentro do orçamento do jogo |
| Cubo | **médio** (alto se usado para passar do nível 10) | nível vai no DataSnap, em `cube_level` da Steam e nas requisições de consumo (não provado que o servidor use); nível 10 libera o Trade Ship/Steam Market; o jogo corrige nível > 100 no load, mas **não** o Exp | limitar a 1..100, gravar `Exp` coerente (999.999.999 no 100) e avisar; não usar para liberar o Market |
| Pets de DLC (6001–6003) | **fora de escopo** | o jogo só consulta a assinatura do DLC para pet **travado** e nunca volta a travar — desbloquear pelo editor contorna o DLC (no seu save já estão desbloqueados desde junho) | retirar a opção do editor |
| `playTime`, `aggregateSaveDatas` | **não editar** | alimentam `play_time_minutes` e as estatísticas Steam, e o limiar dos relatórios | somente leitura |
| Criar/duplicar itens, mudar `ItemKey`/`UniqueId`/quantidade, skins, estágios, pendências | **fora de escopo** | servidor apaga/reverte e registra; economia real do Market | o editor não faz nem deve fazer |

Observação sobre o save atual (neutra): ele já contém valores que o jogo não gera — pontos de
atributo alocados (174/172) acima do orçamento de 101, presentes desde o backup de 14/06, e encantamentos
no valor máximo do tier (242 de 243). Tudo isso já foi enviado nos snapshots anteriores.

---

## 5. Problemas do editor atual

Prioridade: P0 corrompe o save · P1 comportamento errado · P2 proteção/funcionalidade faltando ·
P3 cosmético. Reprodução: `~/tbh_re/scratch/editor_audit/audit_routes.py` (roda as rotas reais contra
cópias, ~7 s).

**P0 — nenhum confirmado** (34 gravações em cópias sem perda de campo nem HMAC quebrado).

Já corrigidos durante o estudo (ferramentas, não o editor): P1-2 `diff_versions.py` escondia mudanças
em tabelas com várias linhas por chave; P2-6 enums aninhados (`EItemGetSourceType`) não eram extraídos;
P2-8 `save_lab coverage` não checava skills/pets/atributos/cubo; P2-10 docs apontavam o trainer.

| id | Problema | Onde | Correção |
|---|---|---|---|
| P1-1 | `data/` 1.00.17: faixas e opções de encantamento erradas para a 1.2.8 | `server.py:24` (GD), `gamedata.py` | promover `research/1.2.8` |
| P1-3 | `auto_build` compara o dict inteiro; `EnchantVersion` faz ~95% dos slots parecerem mudados → reescreve e soma +1 em `*AppliedTotalCount` (esse contador dispara conquista Steam com ≥ 100 inscrições num item quando se encanta no jogo) | `server.py:287-292` | comparar só os 7 campos do encantamento; só gravar e contar se mudou de verdade |
| P1-4 | `build_enchant`/`empty_enchant` recriam o dict e apagam `EnchantVersion` | `gamedata.py:240-257`, `server.py:242,255,289` | atualizar o dict existente campo a campo |
| P1-5 | `set_hero` aceita nível 1..1000 (máx. 101); o jogo **não** corrige: o nível impossível fica, trava os level-ups e vai no snapshot | `server.py:329`, `app.js:164` | teto = `max(LevelInfoData.Level)+1` |
| P1-6 | `set_cube` aceita 1..999 (máx. 100); o jogo corrige o nível no load, mas não o `Exp` (float) | `server.py:391`, `app.js:365` | teto = `max(CubeLevelInfoData.Level)`; no nível máximo gravar `Exp` = `ExpForLevelUp` (999.999.999) |
| P1-7 | "Desbloquear todos" oferece pets de DLC sem checar posse | `server.py:359-373`, `app.js:393-401` | ler `PetInfoData`; não oferecer DLC (mostrar "DLC — gerenciado pela Steam") |
| P1-8 | `/api/save` não checa jogo aberto nem se o arquivo mudou desde o load; escrita não atômica | `server.py:400-415`, `es3.py:114-121` | recusar com o jogo aberto; guardar mtime/hash no load; `tmp` + `os.replace` |
| P1-9 | com dados 1.00.17, `max_runes` não faz nada no save atual (as 51 runas da 1.2.x são "sem dados"; as 197 antigas já estão no máximo); com dados 1.2.8 ele subiria as 20 restantes, todas de drop/capacidade/auto-abertura de baús (28,7 bi de ouro no jogo) | `server.py:374-383` | excluir do "maximizar" as runas cujo `STATTYPE` é de drop/baú (`DropChance*`, `MaxAmount*Chest`, `ReduceAutoOpen*`); mostrar o que ficou de fora e por quê |
| P2-1 | `set_enchant` estende `EnchantData` antes de validar (erro 400 deixa o item mudado) | `server.py:238-245` | validar antes de mutar |
| P2-2 | sem guarda para transações pendentes (`pendingEnchantList`, `pendingItemRestorationList`, `AlchemyPending*`, `pendingExchange` — este apareceu não nulo em 2 dos 17 saves 1.2.8, é normal no jogo). `backendPostList` é só cache de correio | `server.py:225-233, 400-415` | checar **na hora de salvar**; avisar/bloquear edição do item citado |
| P2-3 | `set_skills` não valida skill aprendida nem slot 3 (runa 27); herói bloqueado editável | `server.py:300-320` | usar SkillInfoData + AttributeInfoData |
| P2-4 | `AbilityPoint` sem teto do jogo | `server.py:328` | `AP ≤ HeroLevel − Allocated` |
| P2-5 | stat/modtype desconhecido vira 0 (NONE) em silêncio | `gamedata.py:224,227,250,252` | erro em vez de 0 |
| P2-7 | tabelas úteis não consumidas (ItemInfoData, LevelInfoData, CubeLevelInfoData, PetInfoData, SkillInfoData, AttributeInfoData, StageInfoData) | `gamedata.py:38-76` | carregar e usar como fonte de limites/nomes |
| P2-9 | servidor local aceita POST sem checar origem (uma página web aberta poderia editar/salvar) | `server.py:220-223` | exigir `application/json` + checar `Origin`/`Host` + token de sessão |
| P2-11 | o editor abre por padrão o save vivo e não usa `tbh_paths` | `server.py:34-37` | manter o padrão, mas mostrar "jogo rodando" e bloquear o Salvar nesse caso |
| P3-1 | `auto_build` estende `EnchantData` para 6 em qualquer grade | `server.py:284-285` | só até o tamanho da grade (0/2/4/6) |
| P3-2 | `/api/materials?slot=6` e `/api/options` sem parâmetro derrubam a conexão | `server.py:204-212` | validar e responder 400 |
| P3-3 | nomes/ícones errados de materiais novos e caixas | `gamedata.py:152-174` | usar `ItemInfoData.NameKey/IconPath` |
| P3-4 | docstring e perfil *survival* do autobuild com números velhos; `IsMeleeHero` ignorado | `autobuild.py` | revisar (decisão de build) |
| P3-6 | `data/` sem `VERSION`; comentários citam 1.00.17 | `data/`, `es3.py:15`, README | gravar `data/VERSION` na promoção |
| P3-7 | encantar pelo editor não atualiza as estatísticas (`aggregateSaveDatas` tipos 10–12), que o jogo soma ao encantar | `server.py` | só registrar; editar agregados não vale o risco |
| P3-8 | a regra "9 dígitos + 900" do `base_key` parece morta, mas o jogo trata `ItemKey` > 9.999.999 (id de item Steam) | `gamedata.py:158` | **manter** a regra e tratar esses itens como somente leitura |
| P3-9 | "Maximizar runas" mostra aviso verde de sucesso mesmo com 0 alteradas ("0 runa(s) elevadas ao máximo") | `app.js:413` | com 0 alteradas, aviso neutro dizendo por quê (desconhecidas / já no máximo / excluídas) |

---

## 6. Plano de migração (`/portar-versao 1.2.8`)

Cada passo termina com teste. Ordem pensada para nunca deixar o editor pior que hoje.

1. **Rede de segurança** — `tests/` com: roundtrip sem edição; cada rota de edição em memória sobre um
   snapshot fresco + HMAC + "só o editado mudou" + campos 1.2.x preservados; regressões conhecidas
   como `expectedFailure` (P1-3, P1-4, P1-5, P1-6, P1-7, P2-1). Base: `audit_routes.py`.
2. **Dados 1.2.8** — promover `research/1.2.8/` para `data/` (tabelas que o editor usa + ItemInfoData,
   LevelInfoData, CubeLevelInfoData, PetInfoData, SkillInfoData, AttributeInfoData, StageInfoData,
   PlagueIntensityInfoData, SkinInfoData; nomes, textos, ícones, `enums.json`) + `data/VERSION`.
   Aceite: `coverage --data data` limpo (só as 3 caixas de nome literal, agora resolvidas por
   `ItemInfoData`).
3. **Caminho de encantamento** — P1-4 (preservar `EnchantVersion`), P1-3 (comparar só campos de
   encantamento; contar só mudança real), P2-1 (validar antes de mutar), P3-1 (tamanho pela grade),
   validação completa (`RecipeType` = tipo do slot, `StatType/ModType` = tabela, `Tier ≥ 1`, slot
   permitido, valor alcançável `Min + k·Interval`).
4. **Limites reais e conteúdo pago** — P1-5, P1-6, P2-4 (limites vindos das tabelas, não de
   constantes), P1-7 (sem desbloqueio de DLC), P2-3 (skills), P1-9 (runas de drop/baú fora do "maximizar"), P3-9.
5. **Segurança do Salvar** — P1-8 (jogo aberto, mtime/hash, escrita atômica), P2-2 (pendências),
   P2-9 (origem das requisições).
6. **UI e avisos** — banner "tudo o que você grava é enviado ao servidor na próxima abertura";
   avisos de ouro > 100 M, herói ≥ 50/80, cubo; progresso (estágios/Plaguelands) somente leitura com
   nomes da tabela; nomes/ícones via `ItemInfoData` (P3-3).
7. **Docs** — CLAUDE.md (versões, invariante 3), README ("extracted from version"), este arquivo.
8. **Teste no jogo (usuário, com o jogo fechado)** — `save_lab.py snapshot` (ponto de volta), UMA
   edição pequena (ex.: um encantamento válido num item), Salvar UMA vez, abrir o jogo e conferir que
   não aparece "Save data tampering detected" e que o encantamento está lá. Para voltar: jogo fechado,
   copiar o `SaveFile_Live.es3` do snapshot por cima.

---

## 7. Decisões para o usuário

Recomendação em negrito; `/portar-versao` pergunta o que ainda estiver aberto.

1. **Seguir editando o save sabendo que o estúdio vê o estado (DataSnap) e pode bloquear a conta?**
   É decisão sua; o plano reduz o risco, não o elimina. **Recomendo manter o escopo em encantamentos e
   loadout de skills, com os limites reais do jogo.**
2. Pets de DLC: **retirar a opção do editor** — desbloquear sem o DLC contorna conteúdo pago, e não é
   algo que eu implemente (no seu save eles já vêm desbloqueados; nada muda para você).
3. Cubo: **limitar a 1..100 e manter** — ou retirar a função, já que o nível vai em toda requisição de
   consumo e libera o Market no 10?
4. Herói: nível **1..101**; `AbilityPoint` no **modo estrito** (`AP ≤ nível − alocados`) ou só teto de tipo?
5. `EnchantVersion` em encantamento novo: **`null`** (como os 243 atuais) ou a versão do jogo (o que o
   jogo grava ao rolar)?
6. Auto-build: continuar em **"tier máximo, valor máximo"** (padrão que identifica os encantamentos
   feitos pelo editor) ou rolar dentro da faixa como o jogo?
7. Runas: **as runas de drop/baú ficam fora do "maximizar"** — no save atual só sobram essas 20
   (custam 28,7 bilhões de ouro no jogo) e elas aumentam a geração de itens negociáveis no Steam
   Market; isso eu não implemento. As demais continuam elevadas até `MaxLevel`.
8. Progresso: **somente leitura** (recomendado) ou também "reparar posição" validado?
9. Versionamento: commitar `tools/`, `.claude/`, `CLAUDE.md`, `CONTEXT.md`, `research/1.2.8/` e este
   doc antes de começar a migração (a `/portar-versao` pede árvore limpa)?

---

## 8. Numa próxima atualização

Skill `game-update` (estudar e planejar) → `/portar-versao <versão>` (migrar). Ferramentas:
`tools/save_lab.py` (saves em cópias), `tools/il2cpp_dump.py` (dump + grafo do jogo),
`tools/extract_version.py` (dados → `research/<versão>/`), `tools/diff_versions.py` (diff com chave
composta), `graphify ... --graph ~/tbh_re/<versão>/game_src/graphify-out/graph.json` (código do jogo).

## 9. Verificação

Cada relatório de `research/1.2.8/analysis/` passou por um verificador cético que refez as evidências
de forma independente (desmontagem da cópia do binário, tabelas, 24 snapshots) tentando refutá-las:
**122 vereditos — 88 confirmados, 34 parcialmente certos, 0 refutados.** As correções dos parciais já
estão neste documento e nos relatórios (seções "Correções da verificação"). As mais importantes: o
limiar de tempo de jogo dos relatórios vem do `playTime` do próprio save; a conquista de inscrição é
≥ 100 e só checada ao encantar no jogo; o jogo corrige o nível do cubo mas não o do herói; o jogo nunca
volta a travar um pet de DLC; `IsSteamItem` vale para todos os itens.

## 10. Limites deste estudo

- Análise estática (dump + desmontagem da cópia do binário) e testes em cópias; nada observado com o
  jogo rodando nem tráfego de rede. Não se sabe se o servidor **valida** os valores do DataSnap ou o
  `cubeLev` — só que os recebe.
- Sem dump da 1.00.17 nesta máquina: diferenças de comportamento anteriores vêm do
  `docs/SAVE_PORTING.md` e das strings.
- O teste definitivo (o jogo 1.2.8 abrindo um save gravado pelo editor) ainda não foi feito.
