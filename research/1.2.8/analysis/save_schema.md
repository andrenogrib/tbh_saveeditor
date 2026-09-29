# Esquema do save 1.2.8 — mapa completo, evolução e invariantes

Escopo: `SaveFile_Live.es3` do Taskbar Hero na **1.2.8** (build `3a1772f1…`), comparado com saves
1.00.11, 1.01.05 e 1.2.3. Tudo foi feito sobre **cópias** (`~/tbh_re/saves/20260929_013650/`) e sobre
a cópia do `GameAssembly.dll` em `~/tbh_re/1.2.8/bin/`; nada do save vivo nem da instalação foi lido.

## 0. Resumo para quem vai mexer no editor

1. **Formato estável**: 3 chaves ES3 (`AccountSaveData`, `PlayerSaveData`, `SystemInfo`); Account e
   Player são strings com JSON do Newtonsoft, `JsonConvert.SerializeObject(object)` sem settings
   (`dump.cs:869698-869699`, chamado em `bde.nnm` 0xB83F04). O roundtrip do editor segue íntegro na
   1.2.8 (`save_lab roundtrip`: conteúdo idêntico, HMAC OK).
2. **Cadeado mudou de lugar na 1.2.8**: o travamento ("Item is locked") agora vive no **slot**
   (`inventorySaveDatas[].IsBlocked`, `stashSaveDatas[].IsBlocked`, `heroSaveDatas[].equippedItemBlocked[i]`).
   `itemSaveDatas[].IsBlocked` virou legado: o jogo **sempre grava `false`** (`wh.vc.jlo` 0x979585) e só
   o lê no load para migrar (OR com o flag do slot).
3. **Modelo de pilha mudou na 1.2.8**: material empilhável tem **1 `ItemSaveData` por ItemKey**; vários
   slots apontam para o **mesmo `UniqueId`**, cada um com `Quantity` 1..5 (`MaxStack`=5 para todo
   MATERIAL). Equipamento continua 1 item = 1 slot com `Quantity`=1. Total de um material = soma das
   `Quantity` dos slots que apontam para o UniqueId dele.
4. **O jogo reconstrói do zero** a cada save: heróis, itens, moedas, cubo, agregados e listas pendentes
   (`PlayerSaveData.PreSave` 0x928640). Campo que o runtime não guarda **some**: `PrevUniqueId` sai
   sempre 0, `IsBlocked` do item sai sempre `false`, `EnchantData` é redimensionado pela raridade.
5. **O load descarta/normaliza** coisas inválidas: item com `ItemKey` desconhecido ou `UniqueId`
   duplicado é removido (`wh.vc.jln` 0x978F80); `Quantity<=0` com item vira 1 (`PostLoad`);
   slot de navio além do limite do DLC perde o item (`TradingStashCache..ctor` 0x9F71E7);
   `currentStageKey` fora de `StageInfoData` estoura `KeyNotFound` (`wh.wb.bad` 0x9A64BD).
6. **Limites reais** que o editor hoje não respeita: `HeroLevel` máx **101** (editor aceita 1000);
   `cubeSaveLevelData.Level` máx **100** (editor aceita 999). Campos `int` do C# não aceitam > 2³¹-1.
7. **Servidor**: itens são itens de Steam Inventory ("TBH is a server-based game where all items can
   be traded on the Steam Market"); o jogo monta snapshots de parte do save (`qh.SnapShot` →
   `tl.iut(PlayerSaveData)`) e tem `qh.<CompressAndSendSnapShotAsync>` — envio ao backend (inferência
   pelos nomes e handlers; §3.13), e há textos novos de bloqueio de
   conta/navio por "atividade suspeita". Listas `BoxBucket*`, `Alchemy*`, `pending*`, `backendPostList`
   são transações em trânsito com o servidor — **nunca editar**.

Checagem no save mais novo (`SaveFile_Live.es3`, 1.2.8, 2026-09-29 01:35:51): todas as invariantes
passam; as duas "falhas" do script (L2 e H3) são **o comportamento projetado da 1.2.8** (seções 4 e 6).

## 1. Fontes, método e convenções de evidência

| Fonte | Uso |
|---|---|
| `~/tbh_re/1.2.8/game_src/Assembly-CSharp/<ns>/<Tipo>.cs` | campos, tipos, offsets, atributos. Citado como `EasySaveData/HeroSaveData.cs:20` (`EasySaveData` = `TaskbarHero.EasySaveData`, `TH` = `TaskbarHero`, `_g` = `_global`). |
| `GameAssembly.dll` (cópia) + `script.json` | corpo dos métodos. Citado como `Classe.metodo RVA` (ex. `wj.kis 0x9D55B0`) e endereço da instrução. Reproduz com `python ~/tbh_re/scratch/save_schema/il2dis.py 0x9D55B0`. |
| grafo graphify do jogo | orientação (quem referencia quem); ex. `graphify explain "PlayerSaveData"`. |
| saves (24 cópias) | `python tools/save_lab.py schema/dump`, `union_schema.py`, `check_invariants.py` (scratch). |
| `research/1.2.8/tables`, `strings_en.json` | validação de IDs/limites e semântica de UI. |

Ferramentas escritas para esta análise (todas em `~/tbh_re/scratch/save_schema/`):
`il2dis.py` (desmontador IL2CPP anotado com nomes de método, TypeInfo e literais), `dis_batch.py`,
`scan_class.py` (varre todos os métodos de uma classe por regex), `xref_meta.py` / `xref_call.py`
(quem referencia um símbolo / quem chama um RVA), `psd_fields.py` (quem lê/escreve cada campo de
`PlayerSaveData`/`CommonSaveData` via `ob<bde>.gkj()`; saída em `psd_fields.txt`), `union_schema.py`
(união de esquemas por versão; `union_schema.json`), `class_vs_json.py` (classe × chaves JSON;
`class_vs_json.txt`), `check_invariants.py` (invariantes; `invariants_SaveFile_Live.txt`).

Nomes ofuscados relevantes na 1.2.8: gerenciador do save = **`bde`** (`_g/bde.cs`; na 1.00.17 era
`bal`, hoje `bal` é um buff — `_g/bal.cs`), heróis = `wh.uw`/`wj`, itens = `wh.vc`/`wh.vc.va`,
inventário = `wh.uy`/`wm`, baú = `wh.Stash`/`wh.StashCache`, estágios = `wh.wb`, Plaguelands =
`wh.Plaguelands`, moedas = `wh.ul`, cubo = `wh.Cube`, agregados = `xb`, alquimia = `xg`,
encantamento pendente = `xo`, troca pendente = `xq`, correio de backend = `xi`, caixas do servidor =
`xm`, inventário do servidor = `yi`, snapshot para o servidor = `qh`/`tl`.

## 2. Serialização: o que vale para todas as classes

- **Serializador**: Newtonsoft `JsonConvert.SerializeObject(object)` / `DeserializeObject<T>(string)`
  com settings padrão (`bde.dez` 0xB7E2DE e 0xB7E3F7; `dump.cs:869698`). Consequências (padrão do
  Newtonsoft — inferência sobre a lib, confirmada pela saída observada): `null` é gravado (ex.
  `"pendingExchange":null`, `"EnchantVersion":null`); enums saem como **inteiros**; chaves
  desconhecidas no load são **ignoradas** (por isso `BoxData`/`IsServerPendingItem` antigos somem na
  1ª gravação); campo ausente no JSON mantém o valor do **construtor** da classe.
- **Construtores com parâmetro**: `HeroSaveData(int heroKey)`, `InventorySaveData(int index)`,
  `StashSaveData(int index)`, `RuneSaveData(int,int)`, `PetSaveData(int,bool,bool)`,
  `CurrencySaveData(int,long)`, `CubeRecipeSaveData(int,int)`, `AttributeSaveData(int)` não têm ctor
  vazio: o Newtonsoft chama esse ctor e depois preenche os campos presentes (comportamento padrão da
  lib — inferência, coerente com os saves migrados). Por isso save antigo sem
  `equippedItemBlocked` carrega com `bool[10]` todo `false` (ctor `HeroSaveData` 0xAB4AAA..0xAB4BC1) e
  sem `Quantity` carrega com 0 (ctor `InventorySaveData` 0xAB510B), corrigido depois pelo `PostLoad`.
- **`[JsonObject(1)]` = OptIn** em `AlchemyReceipt` e `ExchangeReceipt` (`TH/AlchemyReceipt.cs:2`,
  `TH/ExchangeReceipt.cs:2`): só os membros com `[JsonProperty]` saem; os `ObscuredX o_*` privados
  (ACTk) não vão para o JSON e são copiados para os públicos por `CopyByObscured()` antes de salvar.
- **Propriedade só-leitura serializada**: `CommonSaveData.FirstUnlockHeroKey { get; }`
  (`TH/CommonSaveData.cs:44`) não tem `[JsonProperty]` nem setter; sai no JSON (última chave de
  `commonSaveData`) mas é **ignorada no load**; o valor real é o campo privado
  `firstUnlockHeroKey` (linha 25), preenchido em runtime (`HeroUI.lti` escreve; `wh.uw.jex` lê).
- **Ciclo**: `bde.dez` → `DeserializeObject<PlayerSaveData>` → **`PlayerSaveData.PostLoad`**
  (0x927AE0: cria listas/objetos nulos com defaults, `unlockedAttributeGroupKeys` nulo → `int[0]`,
  `Quantity<=0` com item → 1). Ao salvar: **`PreSave`** (0x928640) chama os "dumpers" de cada
  subsistema: `wh.uw.jew` (heróis), `wh.vc.jlo` (itens), `wh.ul.jdl` (moedas), `wh.Cube.iys` (cubo),
  `wh.wb.jyd` (estágio), `wh.Plaguelands.jpy`, `xb.koh` (agregados), `xg.kpd` (alquimia),
  `xo.ksp` (encantamento pendente), `xq.ktj` (troca pendente), `yi.kwh` (restauração pendente),
  `xi.kqn` (posts do backend). Inventário, baú, navio, runas, pets, atributos e configurações são
  editados **in place** (os slots embrulham o próprio objeto do save: `wm.bgup`, `StashCache.bgrr`,
  `TradingStashCache.bgvk`).
- **Integridade**: entre o `Deserialize<AccountSaveData>` e o `Deserialize<PlayerSaveData>`, `bde.dez`
  lê `ownerSteamId` (+0x50), chama `bde.nnv(string,string,string)` e `bde.hkv(string,string)`
  (0xB7E356/0xB7E367), obtém um id por `bde.nnx(out string)` (0xB7E37F) e compara strings
  (0xB7E3BB); os ramos de erro chamam `StartOption.lup`/`luo` (0xB7E4E0/0xB7E58F). Leitura (inferência
  pela assinatura + o mesmo fluxo documentado em `docs/SAVE_PORTING.md` §3 como `bal.mcr`): HMAC do
  `SystemInfo` e dono Steam. O HMAC atual confere nos 24 saves (`save_lab info`).

## 3. Tabelas por classe

Legenda "Desde": `≤1.00.11` = já existia no save mais antigo disponível. "Impacto" = o que o editor
deve fazer. Offsets são do objeto IL2CPP (`// 0x..` no `.cs`).

### 3.1 `AccountSaveData` (`TH/AccountSaveData.cs:6-29`) — chave ES3 `AccountSaveData`

Nenhuma mudança de chaves entre 1.00.11 e 1.2.8 (10 chaves nas 4 versões — `union_schema.json`).

| Caminho JSON | Tipo C# (off) | Desde | Significado (evidência) | Impacto no editor |
|---|---|---|---|---|
| `version` | string (0x18) | ≤1.00.11 | versão do jogo que gravou ("1.00.11" … "1.2.8") | só leitura; usar para detectar versão |
| `isFirstRun` | bool (0x20) | ≤1.00.11 | 1ª execução; ctor = `true` (0x912948); escrito por `qu.hlt/vm` (`psd_fields.txt`) | não tocar |
| `forceApplyServerData` | bool (0x21) | ≤1.00.11 | força aplicar dados do servidor no próximo login (nome; sempre `false` nos 24 saves) | não tocar |
| `lastSavedTime` | long (0x28) | ≤1.00.11 | `DateTime.Ticks` **hora local** do save (639262425516675463 = 2026-09-29 01:35:51.667 = mtime do arquivo 01:35:51.68) | preservar |
| `playTime` | float (0x30) | ≤1.00.11 | tempo de jogo em segundos (2369979.25 s); igual a `commonSaveData.playTime` | preservar (float32: passo 0,25 s nessa magnitude) |
| `lastExitSteamUnixSecEncrypted` | long (0x38) | ≤1.00.11 | instante de saída (unix s, relógio Steam) **cifrado pelo ACTk**: `Get/SetLastExitSteamUnixSec` usam `ObscuredDateTime.yuw/yuv/yuo` (0x912860, 0x912890) | **nunca tocar** (anti-tempo / recompensa offline) |
| `lastExitSteamUnixSecKey` | long (0x40) | ≤1.00.11 | chave aleatória desse valor cifrado (0x9128A2) | **nunca tocar** |
| `sessionCounter` | uint (0x48) | ≤1.00.11 | contador de sessões (16 → 88 → 89 → 94 ao longo das versões) | não tocar |
| `ownerSteamId` | string (0x50) | ≤1.00.11 | SteamID64 do dono; entra no HMAC e é comparado com o Steam logado (`bde.dez`) | **nunca trocar** |
| `playerId` | string (propriedade, backing field privado 0x10) | ≤1.00.11 | id do jogador no backend (vazio neste save) | não tocar |

### 3.2 `PlayerSaveData` — topo (`TH/PlayerSaveData.cs:6-51`)

| Caminho JSON | Tipo C# (off) | Desde | Significado (evidência) | Impacto |
|---|---|---|---|---|
| `commonSaveData` | CommonSaveData (0x10) | ≤1.00.11 | §3.3 | |
| `settingSaveData` | SettingSaveData (0x18) | ≤1.00.11 | §3.4 | |
| `BoxBucketUseBoxList` | List\<string\> (0x20) | 1.01.05 | UniqueIds (decimal em string) de **caixas-balde usadas** ainda não confirmadas pelo servidor; `xm.hj` faz `ToArray()` (0xA23F46/0xA23F5A) e passa como 3º arg de `yi.kxd(stageKey, get[], use[], ok, erro)` (0xA23FE0), que grava em `InventoryProcessBoxRequest.useItemKeyList` (+0x48, 0xA511BE) e envia (`JsonUtility.ToJson` 0xA511E7). Os 10 ids do save mais novo **não existem** em `itemSaveDatas` | **nunca editar** |
| `BoxBucketGetBoxList` | List\<string\> (0x28) | 1.01.05 | UniqueIds de **caixas-balde obtidas** ainda não confirmadas: 2º arg de `yi.kxd` → `getitemkey` (+0x40, 0xA511AE); `xm.hj` 0xA23F08. Os 3 ids do save mais novo existem como `STAGEBOX` (910901/920901, `IsBucketBox=True`) fora de qualquer slot | **nunca editar**; não "limpar" caixas órfãs |
| `AlchemyPendingIdList` | List\<string\> (0x30) | 1.01.05 | ids de alquimias aguardando o servidor (`xg.kpd` 0xA14578 grava a partir de `List<ObscuredString>`) | nunca editar; editor deve recusar editar se ≠ [] |
| `AlchemyReceiptList` | List\<AlchemyReceipt\> (0x38) | 1.01.05 | recibos de ouro de alquimia pendentes (`xg.kpd` 0xA14688) | idem |
| `pendingEnchantList` | List\<PendingEnchantSaveData\> (0x40) | 1.01.05 | encantamentos aguardando confirmação do servidor (`xo.ksp` 0xA3C437) | idem; não editar item citado |
| `pendingExchange` | ExchangeReceipt (0x48) | 1.01.05 | troca/síntese pendente no servidor (`xq.ktj` 0xA3EB4F; `null` quando não há) | idem |
| `backendPostList` | List\<BackendPostSaveData\> (0x50) | 1.01.05 | cache de posts/correio do backend (`xi.kqn` 0xA1DBD7) | não editar |
| `pendingItemRestorationList` | List\<ItemRestorationPendingSaveData\> (0x58) | 1.01.05 | itens aguardando restauração de encantamento pelo servidor; atualizada in place por `yi.kwh` no `PreSave` (0x928E7A; usa o TypeInfo da classe em 0xA4E8B0) | não editar item citado |
| `currenySaveDatas` | List\<CurrencySaveData\> (0x60) | ≤1.00.11 | moedas (grafia "curreny" é do jogo); reconstruída no save (`wh.ul.jdl` 0x94ED62) | §3.11 |
| `heroSaveDatas` | List\<HeroSaveData\> (0x68) | ≤1.00.11 | reconstruída no save a partir dos heróis vivos (`wh.uw.jew` 0x959BC8) | §3.5 |
| `mailSaveDatas` | SerializedMailData (0x70) | ≤1.00.11 | caixa de correio local (vazia nos 24 saves) | não editar |
| `attributeSaveDatas` | List\<AttributeSaveData\> (0x78) | ≤1.00.11 | pontos na árvore de atributos (lido por `wh.tw.ivt`) | §3.11 |
| `PetSaveData` | List\<PetSaveData\> (0x80) | ≤1.00.11 | pets (`PetManager.lro/lry`) | §3.11 |
| `RuneSaveData` | List\<RuneSaveData\> (0x88) | ≤1.00.11 | runas (`RunePage.ngr`) | §3.11 |
| `inventorySaveDatas` | List\<InventorySaveData\> (0x90) | ≤1.00.11 | 260 slots de inventário; no load `wh.uy.jgp` indexa por `Index` e cria o slot que faltar para cada linha de `InventoryInfoData` (0x96839E/0x968401) | §3.8 |
| `stashSaveDatas` | List\<StashSaveData\> (0x98) | ≤1.00.11 | baú (343 slots neste save, todos `IsUnLock`) | §3.9 |
| `remakeTradingStashSaveDatas` | List\<RemakeTradingStashSaveData\> (0xA0) | 1.01.05 | navio de troca (10 slots) — substituiu `tradingStashSaveDatas` | §3.10 |
| `cubeRecipeSaveDatas` | List\<CubeRecipeSaveData\> (0xA8) | ≤1.00.11 | receitas do cubo desbloqueadas; reconstruída (`wh.Cube.iys` 0x9159D9) | §3.11 |
| `cubeSaveLevelData` | CubeLevelSaveData (0xB0) | ≤1.00.11 | nível/exp do cubo; reconstruída (`wh.Cube.iys` 0x9158B6) | §3.11 |
| `itemSaveDatas` | List\<ItemSaveData\> (0xB8) | ≤1.00.11 | todos os itens; **reconstruída** a cada save (`wh.vc.jlo` 0x979320) | §3.6 |
| `aggregateSaveDatas` | List\<AggregateSaveData\> (0xC0) | ≤1.00.11 | estatísticas; reconstruída (`xb.koh` 0xA0D42B) | §3.11 |
| ~~`BoxData`~~ | SerializedBoxData | ≤1.00.11, **removido na 1.2.3** | sistema antigo de caixas (`BoxTypes`/`BoxUniqueId`/`BoxQuantity`, `TH/SerializedBoxData.cs:6-11`); vazio em todos os saves antigos; classe ainda existe mas não é referenciada | ignorado no load (chave desconhecida) |
| ~~`tradingStashSaveDatas`~~ | List\<TradingStashSaveData\> | 1.00.11, **removido na 1.01.05** | navio antigo (`EasySaveData/TradingStashSaveData.cs:6-11`) | idem |

### 3.3 `CommonSaveData` (`TH/CommonSaveData.cs:5-41`)

Defaults do ctor (0x912A80): `isFirstPlay=true`, `TutorialCleared=bool[7]`, `ArrangedPetKey=-1`,
`maxCompletedStage=1101`, `lastClearedStageKey=0`, `currentStageKey=1101`, `currentStageWave=1`,
`prevNormalStageKey=1101`, `lastPlayedPlagueIntensity=int[4]`, `useStorage=false`.

| Caminho JSON | Tipo C# (off) | Desde | Significado (evidência) | Impacto |
|---|---|---|---|---|
| `commonSaveData.version` | string (0x10) | ≤1.00.11 | versão que gravou | só leitura |
| `.lastSavedTime` | long (0x18) | ≤1.00.11 | ticks locais do save (= Account) | preservar |
| `.playTime` | float (0x20) | ≤1.00.11 | segundos de jogo (= Account) | preservar |
| `.isFirstPlay` | bool (0x24) | ≤1.00.11 | escrito por `qu.hlt/vm` | não tocar |
| `.LastRollingBackUpTime` | long (0x28) | ≤1.00.11 | ticks do último backup rotativo que o próprio jogo gravou (= 01:05:27.064, mesma hora de `SaveFile_Live_backup_20260929_010527.es3`) | preservar |
| `.LastDailyBackUpTime` | long (0x30) | 1.01.05 | ticks do último `Live_daily_*.es3` (idem, 01:05:27) | preservar |
| `.SendSteamId` | bool (0x38) | ≤1.00.11 | já enviou o SteamId ao backend (`pg.<SendAsync>` escreve) | não tocar |
| `.TutorialCleared` | bool[] (0x40) | ≤1.00.11 | 7 posições = `ETutorialType` 0..6 (`TH.Tutorial/ETutorialType.cs`); ctor `bool[7]` | pode editar, manter len 7 |
| `.ArrangedPetKey` | int (0x48) | ≤1.00.11 | pet ativo (`PetManager.lro/lrr/lrx`); -1 = nenhum | editor já impede bloquear o pet ativo |
| `.arrangedHeroKey` | int[] (0x50) | ≤1.00.11 | os 3 heróis da equipe (`wh.uw.*` lê) | só `heroKey` desbloqueado; len 3 |
| `FirstUnlockHeroKey` | *propriedade* get-only (campo privado 0x58) | ≤1.00.11 | herói inicial escolhido; **ignorado no load** (§2) | ignorar |
| `.maxCompletedStage` | int (0x5C) | ≤1.00.11 | **progresso máximo** (estágio mais avançado liberado); escrito por `wh.wb.jyd` 0x9B1E5C | só chaves de `StageInfoData` |
| `.lastClearedStageKey` | int (0x60) | **1.2.3** | último estágio **efetivamente limpo**; gravado de `wb.bgps` (`wh.wb.jyd` 0x9B1F8F). Se 0 no load, o jogo deriva: estágio não-Plague cujo `NextStageKey == maxCompletedStage` (`wh.wb.bad` 0x9A673E→`wh.wb.jzz` 0x9B7A40, compara `+0xA0`=`NextStageKey`). Por isso a 1.2.3 migrou para 4309 com max 4310 | só `StageInfoData`; ≤ progresso |
| `.currentStageKey` | int (0x64) | ≤1.00.11 | estágio atual; no load `Dictionary<int,StageCache>.get_Item(key)` (`wh.wb.bad` 0x9A64BD) → chave inexistente = exceção; se `StageCache.kai()`==1 (ACTBOSS) ajusta a chave com `ObscuredInt.zbb` (0x9A6520-0x9A657E; provável "volta 1 estágio"), se ==2/3 (PLAGUE/CONTAMINACTBOSS) usa `prevNormalStageKey` via `TryGetValue` e, sem ele, o 1º estágio (0x9A6628-0x9A66E0) | **só chaves de `StageInfoData`** |
| `.currentStageWave` | int (0x68) | ≤1.00.11 | onda atual no estágio (`jyd` 0x9B1F0C) | 0..WaveAmount |
| `.prevNormalStageKey` | int (0x6C) | **1.2.3** | último estágio **normal** antes de entrar nas Plaguelands; destino de retorno (usado em `wh.wb.bad` 0x9A6692, `eot/jyp/fnw`); gravado de `wb.bgpz` (`jyd` 0x9B1F46) | só estágio NORMAL de `StageInfoData` |
| `.lastPlayedPlagueIntensity` | int[] (0x70) | **1.2.3** | última Intensidade de Praga jogada **por dificuldade**: índice = `ESTAGEDIFFICULTY` (0 NORMAL, 1 NIGHTMARE, 2 HELL, 3 TORMENT); 0 = nunca. Load lê até 4 posições e só >0 (`wh.Plaguelands.jpx` 0x9848F7-0x984942); save força len 4 (`jpy` 0x984A63-0x984A89). Save: `[0,0,0,11]` (Torment, intensidade 11); `PlagueIntensityInfoData` tem 1..20 | len 4; valores 0..20 |
| `.useStorage` | bool (0x78) | ≤1.00.11 | usar armazenamento no cubo (`wh.Cube.ixw` lê, `izj` escreve) | pode editar |
| `.isOpeningDirectionPlayed` | bool (0x79) | ≤1.00.11 | abertura já exibida (`StageManager.<SpawnFriendlyUnitAsync>`) | não tocar |

### 3.4 `SettingSaveData` (`TH/SettingSaveData.cs:5-52`)

Defaults = ctor 0x929890 (idênticos ao bloco inline do `PostLoad` 0x928171..0x9281B7). Save antigo sem
o campo recebe o default do ctor — confirmado: a 1.2.3 veio com exatamente esses valores.

| Caminho JSON | Tipo C# (off) | Desde | Default | Significado (UI, `strings_en.json`) |
|---|---|---|---|---|
| `language` | `UnityEngine.SystemLanguage` (0x10) | ≤1.00.11 | 10 | idioma (int do enum Unity; 10 = English) |
| `isAlwaysOnTop` | bool (0x14) | ≤1.00.11 | false | janela sempre no topo |
| `maxFps` | EMaxFPS (0x18) | ≤1.00.11 | 0 | `Setting_MaxFPS` (0=60,1=45,2=30) |
| `windowZoomRate` | EWindowZoomRate (0x1C) | ≤1.00.11 | 0 | `Setting_Zoom` (0=1x,1=1.25,2=1.5,3=2,4=3) |
| `windowLayoutPreset` | EWindowLayoutPreset (0x20) | ≤1.00.11 | 0 | posição da janela (0 None … 6 RightTop) |
| `FixingLog` | bool (0x24) | ≤1.00.11 | false | `Option_FixingLog` "Pin Travel Log" |
| `LogFilter` | ELogFilter (0x28, flags) | ≤1.00.11 | -1 | filtro do log (-1 = All; bits `TH.Log/ELogFilter.cs`) |
| `LogShowTime` | bool (0x2C) | ≤1.00.11 | false | hora no log |
| `isAutoStart` | bool (0x2D) | ≤1.00.11 | false | iniciar com o Windows |
| `StageRepeatStageFailed` | bool (0x2E) | ≤1.00.11 | false | repetir estágio ao falhar |
| `RepeatActBossDuringConsumeAllStone` | bool (0x2F) | ≤1.00.11 | false | repetir chefe de ato enquanto houver pedra |
| `AskWarningAlchemy` | bool (0x30) | ≤1.00.11 | true | `Setting_ShowAlchemyWarning` |
| `AskWarningTradingStash` | bool (0x31) | **1.01.05** | true | `Option_TradingStashWarning` "Trade Ship - Show confirmation" |
| `BoxAlphaValue` | float (0x34) | ≤1.00.11 | 1.0 | `Option_SettingBoxAlpha` transparência das caixas |
| `WindowOpacityValue` | float (0x38) | **1.2.3** | 1.0 | `Setting_WindowOpacity` "Screen Opacity" (string nova) |
| `BoxShowWhenHover` | bool (0x3C) | ≤1.00.11 | false | `Option_ToggleBoxOption` |
| `ShowQuickMenu` | bool (0x3D) | ≤1.00.11 | true | menu rápido |
| `ForceSynthesisOnCubeOpen` | bool (0x3E) | ≤1.00.11 | false | abrir cubo já em Síntese |
| `AlwaysShowCoolTimeSlider` | bool (0x3F) | ≤1.00.11 | false | barra de recarga sempre visível |
| `ShowEnchantSlotView` | bool (0x40) | **1.2.3** | true | `Setting_ShowEnchantSlotOption` "Always show equipment enhancement sockets" (nova) |
| `AlwaysShowItemLevel` | bool (0x41) | **1.2.3** | false | `Setting_AlwaysItemLevelShow` "Always show item level" (nova) |
| `IsTooltipExpanded` | bool (0x42) | ≤1.00.11 | false | tooltip expandido |
| `UseOpenOneTypeChestAllAtOnce` | bool (0x43) | **1.2.3** | true | `Setting_OpenOneTypeChestAllAtOnce` "Bulk open boxes" (nova; a habilidade vem da runa `OpenOneTypeChestAllAtOnce`) |
| `UseOpenAllTypeChestAllAtOnce` | bool (0x44) | **1.2.3** | true | `Setting_OpenAllTypeChestAllAtOnce` "Bulk open all boxes" (nova) |

Impacto: só preferências de UI, seguras; enums devem ficar dentro dos membros listados.

### 3.5 `HeroSaveData` (`EasySaveData/HeroSaveData.cs:6-27`)

Load: `wj..ctor` 0x9CCF90 → `wj.kis` 0x9D55B0. Save: `wh.uw.jew` 0x959810 cria `new HeroSaveData(heroKey)`
e preenche tudo do runtime. Ctor (0xAB4A50): `HeroLevel=1`, `HeroExp=0`, `IsUnLock=false`,
`AbilityPoint=1`, `Allocated=0`, `equippedItemIds=ulong[count(EItemParts)-1]=10`,
`equippedItemBlocked=bool[len(ids)]`, `equippedSKillKey=int[3]`, `unlockedAttributeGroupKeys=int[0]`,
`EquippedSkinKey=0`.

| Caminho JSON | Tipo C# (off) | Desde | Significado (evidência) | Impacto |
|---|---|---|---|---|
| `heroKey` | int (0x10) | ≤1.00.11 | `HeroInfoData.HeroKey` (101…601) | chave; não mudar |
| `HeroLevel` | int (0x14) | ≤1.00.11 | nível → `ObscuredInt` (kis 0x9D567F). Máx **101**: `LevelInfoData` tem 1..100 e o jogo trata 101 à parte (`wh.vl.jpu` 0x99B613 `cmp ebx,0x65` → usa linha 100; fora da tabela `wh.uw.jev` 0x9597F0 devolve 0). Todos os heróis estão em 101 | **limitar 1..101** (hoje 1..1000) |
| `IsUnLock` | bool (0x18) | ≤1.00.11 | desbloqueado (kis 0x9D5651). Herói com `DLCAppId` tem o valor **sobrescrito** pela posse do DLC (`wj..ctor` 0x9CD2AF-0x9CD32C, `DLCManager.hit`) | não editar herói de DLC |
| `HeroExp` | double (0x20) | ≤1.00.11 | exp → `ObscuredDouble` (kis 0x9D56CD); continua acumulando no nível 101 (1,5e11) | ≥0; double |
| `AbilityPoint` | int (0x28) | ≤1.00.11 | pontos livres (kis 0x9D5699) | int32; relação com nível não verificada (§9) |
| `AllocatedHeroAbilityPoint` | int (0x2C) | ≤1.00.11 | pontos gastos na árvore (kis 0x9D56B3); 172-174 | não mexer sem refazer `attributeSaveDatas` |
| `equippedItemIds` | ulong[] (0x30) | ≤1.00.11 | item por parte: índice **i ↔ `EItemParts(i+1)`** (MAIN_WEAPON…BRACER) — verificado nos 60 slots (check H9). `null` = NullReference no load (kis 0x9D571A) | manter len 10; 0 = vazio; só UniqueIds de GEAR da parte certa |
| `equippedItemBlocked` | bool[] (0x38) | **1.2.8** | cadeado do slot equipado. Load: aloca `ObscuredBool[len(ids)]`, copia `min(len)` posições e faz **OR** com o `IsBlocked` legado do item (kis 0x9D57C9-0x9D59BA). Save grava `wj.kig(i)` (jew 0x959AB0-0x959AE7) | **manter len == len(equippedItemIds)**; é o cadeado real do item equipado |
| `equippedSKillKey` | int[] (0x40) | ≤1.00.11 | 3 skills ativas (grafia do jogo "SKill") | só `SkillInfoData` do herói; len 3 |
| `unlockedAttributeGroupKeys` | int[] (0x48) | ≤1.00.11 | grupos de atributo liberados → `HashSet<int>`; `null` → vazio (kis 0x9D5A79; PostLoad 0x928343) | derivado de pontos; não editar isolado |
| `EquippedSkinKey` | int (0x50) | **1.2.3** | skin equipada (`SkinInfoData`; 25101002 = "Dusk Wanderer Knight"). 0 → skin padrão `SkinKey.eix(heroKey)` (`wj..ctor` 0x9CD435-0x9CD469); se um flag estático (`bs`+0x30) estiver falso o jogo também troca pela padrão (0x9CD4C6-0x9CD500) — leitura como "catálogo de skins não carregou" é inferência pela string nova `Popup_SkinLoadFailed` ("All skin equip data has been reset") | só `SkinKey` do próprio herói (prefixo `25<classe>`); skins pagas (SetId 25001002) exigem posse |

### 3.6 `ItemSaveData` (`EasySaveData/ItemSaveData.cs:6-29`)

Load real: `wh.vc.jln` 0x978F80 (chamado por `qu.qp.MoveNext` 0xD2C860; os clones `lif/gy/fbm/gwq` são
iscas do ofuscador com constantes trocadas — só `jln` tem chamador). Para cada item, de trás para
frente: `ItemKey > 10.000.000` → não instancia (0x9791A8; como o save reconstrói a lista só com itens
vivos, esse item some na gravação seguinte — inferência); `ItemInfoData` inexistente (0x9791EC) ou
`UniqueId` já carregado (0x979236) → **log + `RemoveAt`**; senão `wh.vc.jmb` → `wh.vc.va..ctor`
0x989BE0 → `va.jkq` 0x98D2B0. Save: `wh.vc.jlo` 0x979320 reconstrói a lista a partir do dicionário de
itens vivos.

| Caminho JSON | Tipo C# (off) | Desde | Significado (evidência) | Impacto |
|---|---|---|---|---|
| `ItemKey` | int (0x10) | ≤1.00.11 | `ItemInfoData.ItemKey`; → `ObscuredInt` (va ctor 0x989E01) | só chaves conhecidas (senão o item é apagado no load) |
| `UniqueId` | ulong (0x18) | ≤1.00.11 | id do item (Steam/servidor) → `ObscuredULong` (jkq 0x98D367); `IsValid` exige `ItemKey>0 && UniqueId>0` (0xAB51F0); duplicado = removido | **nunca criar/alterar** |
| `PrevUniqueId` | ulong (0x20) | 1.01.05 | id **antes de um "rekey" do servidor** (mesmo nome em `TH/ItemRekeyedData.cs:5`, junto de `ChangedUniqueId`). Na 1.2.8 **não é lido** (jkq não acessa +0x20; o remapeamento vem de `yi.kwc` em runtime, 0x98D4A1) e **sai sempre 0** (ctor 0xAB54A4, `jlo` não escreve). 0 em todos os 24 saves | ignorar; preservar |
| `IsChaotic` | bool (0x28) | ≤1.00.11 | variante "caótica" → `ObscuredBool` (jkq 0x98D3A1); gravado de `va.jjn` (jlo 0x979582). `false` em todos os saves; semântica exata não confirmada | não editar |
| `IsBlocked` | bool (0x29) | ≤1.00.11 | cadeado **legado**: lido para `ObscuredBool` (jkq 0x98D3C9) e usado só para migrar o slot (`StashCache..ctor` 0x9C0D94, `wm..ctor` 0x9F8EFA, `wj.kis` OR); **o save 1.2.8 grava sempre `false`** (`jlo` 0x979585 `mov byte [rsi+0x29],0`) | não usar como cadeado; escrever no slot (§5) |
| `RegisterID` | string (0x30) | 1.01.05 | id de registro no mercado/navio (`GameMarketItemRegisterRequest.Initialize(string registerId, …)`); → `ObscuredString` (jkq 0x98D3EB), gravado de `va.jjy` (jlo 0x97958E). Vazio nos 24 saves | nunca editar |
| `EnchantCount` | int[] (0x38) | ≤1.00.11 | slots preenchidos por tipo (Decoration, Engraving, Inscription) — len 3 (ctor 0xAB54FD); gravado de `va.jki(i)` (jlo 0x9796FF) | regra já documentada no CLAUDE.md |
| `EnchantData` | ItemEnchantSaveData[] (0x40) | ≤1.00.11 | encantamentos; load copia `min(len,6)` (jkq 0x98D6B2); save grava **len = `va.jkp()`** = 6 se a raridade tem `ExtraSlotAmount_Inscription>0`, 4 se `…Engraving>0`, 2 se `…Decoration>0`, senão 0 (jkp 0x98D0D0; conferido nos 270 itens: 100% batem) | manter o len da regra |
| `ItemGetSourceType` → campo `GetSourceType` | int (0x48) | 1.01.05 | origem, enum `wh.vc.EItemGetSourceType` (`_g/wh.vc.EItemGetSourceType.cs`: 0 None, 2 Synthesis, 3 Offering, 4 Crafting, 5 OpenBox, 6 MonsterDieReward, 7 BackendPost, 8 UpdateInventoryNewBox, 9 BoxInventoryInit, 10 UploadToSteam, 11 NewMail, 12 DownloadToSteam, 13 MailExchangeBox, 14 FirstClearRewardBox, 15 ClaimMail, **16 StackMigration**). Save: {0:68, 2:43, 3:32, 4:2, 5:122, 6:3}; 16 não aparece em nenhum save | não editar |
| `DecorationAppliedTotalCount` | int (0x4C) | ≤1.00.11 | aplicações acumuladas (jlo 0x979723) | regra do CLAUDE.md |
| `EngravingAppliedTotalCount` | int (0x50) | ≤1.00.11 | idem (0x979730) | idem |
| `InscriptionAppliedTotalCount` | int (0x54) | ≤1.00.11 | idem (0x97973D) | idem |
| ~~`IsServerPendingItem`~~ | — | só 1.00.11 | item aguardando servidor (sistema antigo) | ignorado |

Observação de risco: `va.jkq` consulta `yi.kwe(id, out EnchantBackUpData)` e, se houver backup com o
mesmo `ItemKey`, **usa o encantamento do backup** em vez do save (0x98D4C2-0x98D5B7; struct
`TH/EnchantBackUpData.cs`). O dicionário é preenchido em runtime pelo fluxo de servidor; em load a frio
deve estar vazio (inferência), mas é um caminho em que o servidor prevalece sobre o save.

### 3.7 `ItemEnchantSaveData` (struct, `EasySaveData/ItemEnchantSaveData.cs:6-21`)

| Caminho JSON | Tipo C# (off) | Desde | Significado | Impacto |
|---|---|---|---|---|
| `EnchantData[].StatModKey` | int (0x0) | ≤1.00.11 | `StatModInfoData` | validar como hoje |
| `.Tier` | int (0x4) | ≤1.00.11 | tier | idem |
| `.Value` | int (0x8) | ≤1.00.11 | valor | range/passo |
| `.RecipeType` | int (0xC) | ≤1.00.11 | `ERecipeType` (0 ALCHEMY … 9 **CORROSION** novo na 1.2.8, DIFF.md) | int do enum |
| `.ModType` | int (0x10) | ≤1.00.11 | `MODTYPE` | idem |
| `.MaterialKey` | int (0x14) | ≤1.00.11 | material usado (0 = slot vazio) | idem |
| `.StatType` | int (0x18) | ≤1.00.11 | `StatType` (+`MaxAllElementalResistance=64` na 1.2.8) | idem |
| `.EnchantVersion` | string (0x20) | 1.01.05 | versão do encantamento; runtime `ObscuredString` (`wh.vc.ItemEnchantData`, ctor save 0xAB51CA). `null` nos 722 registros | gravar `null` |

### 3.8 `InventorySaveData` (`EasySaveData/InventorySaveData.cs:6-17`) — slot `wm`

| Caminho JSON | Tipo C# (off) | Desde | Significado (evidência) | Impacto |
|---|---|---|---|---|
| `Index` | int (0x10) | ≤1.00.11 | posição = `InventoryInfoData.Index` (0..259) | não mudar |
| `ItemUniqueId` | ulong (0x18) | ≤1.00.11 | item no slot (0 = vazio) | só UniqueId existente |
| `IsUnlock` | bool (0x20) | ≤1.00.11 | liberado por custo; o load força `true` se `CostForUnlock<=0` (`wm..ctor` 0x9F8E77-0x9F8E8D) | não editar (compra/servidor) |
| `IsUnlockedByRune` | bool (0x21) | ≤1.00.11 | liberado por runa (84 slots) | não editar |
| `IsBlocked` | bool (0x22) | **1.2.8** | **cadeado do item neste slot**; migrado do item legado no load (`wm..ctor` 0x9F8ED9-0x9F8EFA); limpo junto com o slot | é aqui que se trava/destrava |
| `Quantity` | int (0x24) | **1.2.8** | tamanho da pilha no slot; `PostLoad` põe 1 se há item e ≤0 (0x928413-0x928420); capacidade = `min(kdb()=5, MaxStack(ItemKey))` (`ben.nqy` 0xBC7650, `wh.vc.jlr`) | GEAR = 1; MATERIAL 1..5; vazio = 0 |

### 3.9 `StashSaveData` (`EasySaveData/StashSaveData.cs:6-15`) — slot `wh.StashCache`

Métodos do slot (desmontados): `kcx`=ItemUniqueId, `kcw`=IsUnLock, `kda`=Quantity, `kdc`=IsBlocked se
ocupado, `kdb`=5 (capacidade), `kdi(id,q)` põe item só se vazio, `id≠0`, `q>0` (0x9C120F-0x9C122C),
`kdh(n)` soma `Quantity` se couber (0x9C113F), `kdj()` limpa id, `Quantity` e `IsBlocked` (0x9C1340-0x9C1361),
`kdk(lock)` grava `IsBlocked` (0x9C14FC).

| Caminho JSON | Tipo C# (off) | Desde | Significado | Impacto |
|---|---|---|---|---|
| `Index` | int (0x10) | ≤1.00.11 | posição (0..342) | não mudar |
| `ItemUniqueId` | ulong (0x18) | ≤1.00.11 | item no slot | só existentes |
| `IsUnLock` | bool (0x20) | ≤1.00.11 | **forçado `true` no load** (`StashCache..ctor` 0x9C0D2F) | irrelevante editar |
| `IsBlocked` | bool (0x21) | **1.2.8** | cadeado do item no slot; migração do legado 0x9C0D48-0x9C0D94 | travar aqui |
| `Quantity` | int (0x24) | **1.2.8** | pilha (idem inventário; `PostLoad` 0x9284D3-0x9284E0) | GEAR 1; MATERIAL 1..5 |

### 3.10 `RemakeTradingStashSaveData` (`EasySaveData/RemakeTradingStashSaveData.cs:6-13`) — navio

| Caminho JSON | Tipo C# (off) | Desde | Significado (evidência) | Impacto |
|---|---|---|---|---|
| `Index` | int (0x10) | 1.01.05 | posição 0..9 (`TradingStashInfoData`) | |
| `ItemUniqueId` | ulong (0x18) | 1.01.05 | item carregado no navio (vai ao Mercado Steam) | **não editar** |
| `IsUnLock` | bool (0x20) | 1.01.05 | **recalculado no load** pela posse do DLC de app id 4877934 (0x4A6A6E, `DLCManager.hip/hit`; provavelmente o "Trade Ship Pack" da loja, `Shop_TradingStashPack` — inferência): limite 4 sem o DLC, 9 com; slot com `Index>=limite` perde o item (`ItemUniqueId=0`) e fica bloqueado (`TradingStashCache..ctor` 0x9F714A-0x9F71F8). Save: 4 true / 6 false; na 1.01.05 eram 10 true | não editar |
| `Quantity` | int (0x24) | **1.2.8** | pilha no slot (`PostLoad` 0x9285A5-0x9285B2) | não editar |

`TradingStashSaveData` (`Index`, `ItemUniqueId`, `IsUnLock`): só na 1.00.11; classe ainda no código,
fora de `PlayerSaveData`.

### 3.11 Demais coleções

| Caminho JSON | Tipo C# | Desde | Significado (evidência) | Impacto |
|---|---|---|---|---|
| `currenySaveDatas[].Key` | int | ≤1.00.11 | `CurrencyInfoData` (só 100001 = ouro) | só chaves da tabela |
| `currenySaveDatas[].Quantity` | **long** | ≤1.00.11 | saldo (`EasySaveData/CurrencySaveData.cs:9`) | 0..9,2e18; editor usa 1e13 (ok) |
| `attributeSaveDatas[].Key` | int | ≤1.00.11 | `AttributeInfoData.AttributeKey` (por herói) | 132/132 conhecidos |
| `attributeSaveDatas[].Level` | int | ≤1.00.11 | nível ≤ `AttributeInfoData.MaxLevel` (check T3 OK) | coerente com `AllocatedHeroAbilityPoint` |
| `PetSaveData[].PetKey` | int | ≤1.00.11 | `PetInfoData` (8 pets) | |
| `PetSaveData[].IsUnlock` | bool | ≤1.00.11 | pet liberado | editor edita (ok) |
| `PetSaveData[].IsViewed` | bool | ≤1.00.11 | selo "novo" já visto | editor põe true ao liberar (ok) |
| `RuneSaveData[].RuneKey` | int | ≤1.00.11 | `RuneInfoData` (248/248 no save; +51 runas na 1.2.8) | |
| `RuneSaveData[].Level` | int | ≤1.00.11 | nível ≤ `RuneInfoData.MaxLevel` (228 no máximo) | usar `MaxLevel` da 1.2.8 |
| `cubeSaveLevelData.Level` | int | ≤1.00.11 | nível do cubo; `CubeLevelInfoData` 1..100 | **limitar 1..100** (hoje 999) |
| `cubeSaveLevelData.Exp` | **float** | ≤1.00.11 | exp; no nível 100 `ExpForLevelUp=999999999` (sentinela) e o save tem 1e9 | float32 (passo 64 perto de 1e9) |
| `cubeRecipeSaveDatas[].CubeRecipeTypeInt` | int | ≤1.00.11 | `ERecipeType` da receita | coerente com `CubeRecipeInfoData.RECIPETYPE` (T4 OK) |
| `cubeRecipeSaveDatas[].CubeKey` | int | ≤1.00.11 | `CubeRecipeInfoData.CubeKey` | |
| `cubeRecipeSaveDatas[].MaxUnlockRecipeKey` | int | ≤1.00.11 | maior sub-receita liberada (`CubeSubRecipeInfoData`) | |
| `aggregateSaveDatas[].Type` | int | ≤1.00.11 | `EAggregateType` (0 MonsterKill … 19 SteamOriginItemBuy) | estatística; não editar |
| `aggregateSaveDatas[].SubKey` | int | ≤1.00.11 | subchave (ex. monstro, `EBoxType`, estágio) | |
| `aggregateSaveDatas[].Value` | **long** | ≤1.00.11 | contador (máx 14814928272 > int32) | long |
| `aggregateSaveDatas[].Content` | int | **1.2.3** | `EAggregateContent`: 0 Total, 1 Normal, 2 **Plague** (`TH/EAggregateContent.cs`); ctor 4-args (`AggregateSaveData.cs:24`). Save: {0:147, 1:22, 2:72}; (Type,SubKey,Content) único | não editar |

### 3.12 Classes de transação com o servidor (todas vazias/nulas no save mais novo)

| Caminho JSON | Tipo C# | Desde | Significado (evidência) | Impacto |
|---|---|---|---|---|
| `AlchemyReceiptList[].uniqueId` | string (`TH/AlchemyReceipt.cs:10`) | 1.01.05 | id da alquimia (OptIn; `o_uniqueId` Obscured fora do JSON) | não editar |
| `AlchemyReceiptList[].addedGold` | long (linha 12) | 1.01.05 | ouro creditado aguardando confirmação (lista reconstruída por `xg.kpd` 0xA14654-0xA14688, que copia os `o_*` para os campos públicos) | não editar |
| `pendingExchange.resultItem` | int (`TH/ExchangeReceipt.cs:12`) | 1.01.05 | `SynthesisRecipeKey` da troca/síntese pendente (10309011 existe em `SynthesisRecipeInfoData`, visto no save de 22/09); -1 = limpo (1.01.05) | não editar |
| `pendingExchange.items` | string[] (linha 14) | 1.01.05 | ingredientes (strings; `null` nas amostras) | não editar |
| `pendingExchange.source` | string (linha 16) | 1.01.05 | origem ("" nas amostras) | não editar |
| `pendingExchange.timeStamp` | string (linha 18) | 1.01.05 | carimbo textual ("" nas amostras) | não editar |
| `pendingEnchantList[].MaterialUniqueId` | ulong (`EasySaveData/PendingEnchantSaveData.cs:7`) | 1.01.05 | material consumido | não editar |
| `pendingEnchantList[].GearUniqueId` | ulong (linha 9) | 1.01.05 | equipamento alvo | não editar o item citado |
| `pendingEnchantList[].RecipeType` | int (linha 11) | 1.01.05 | `ERecipeType` | — |
| `pendingEnchantList[].Enchant` | ItemEnchantSaveData (linha 13) | 1.01.05 | encantamento proposto (§3.7) | — |
| `pendingEnchantList[].TxId` | string (linha 15) | 1.01.05 | id da transação no servidor; `IsValid` = ids ≠0 e `TxId` não vazio (0xABA7A0) | — |
| `pendingEnchantList[].TimestampTicks` | long (linha 17) | 1.01.05 | ticks .NET | — |
| `pendingItemRestorationList[].UniqueId` / `.ItemKey` | ulong / int (`EasySaveData/ItemRestorationPendingSaveData.cs:7-9`) | 1.01.05 | item a restaurar | não editar o item citado |
| `pendingItemRestorationList[].EnchantCount` / `.EnchantData` | int[] / ItemEnchantSaveData[] (linhas 11-13) | 1.01.05 | estado de encantamento a reaplicar | — |
| `pendingItemRestorationList[].DecorationAppliedTotalCount` / `Engraving…` / `Inscription…` | int ×3 (linhas 15-19) | 1.01.05 | contadores a reaplicar | — |
| `backendPostList[].title` / `.content` / `.author` / `.inDate` | string ×4 (`TH/BackendPostSaveData.cs:7-13`) | 1.01.05 | post do backend (`BackendPostData.ToSaveData` 0xA0ED00) | não editar |
| `backendPostList[].expirationTicks` / `.reservationTicks` | long ×2 (linhas 15-17) | 1.01.05 | validade / liberação (ticks) | não editar |
| `backendPostList[].items[].itemID` / `.itemName` / `.count` | int / string / int (`TH/BackendPostItemSaveData.cs:7-11`) | 1.01.05 | anexos | não editar |
| `mailSaveDatas.Keys` | List\<ulong\> (`TH/SerializedMailData.cs:7`) | ≤1.00.11 | chaves das cartas | não editar |
| `mailSaveDatas.MailData[].index` | int (`TH/MailSaveData.cs:7`) | ≤1.00.11 | posição | não editar |
| `mailSaveDatas.MailData[].receivedDate` | DateTime (linha 9) | ≤1.00.11 | recebimento (string ISO no JSON — padrão Newtonsoft, sem amostra) | não editar |
| `mailSaveDatas.MailData[].itemInstanceId` | ulong (linha 11) | ≤1.00.11 | item anexado | não editar |
| `mailSaveDatas.MailData[].isRead` / `.isClaimedItem` / `.wasMarketItem` | bool ×3 (linhas 13-19) | ≤1.00.11 | lida / resgatada / veio do mercado | não editar |
| `mailSaveDatas.MailData[].ItemKey` / `.ItemQuantity` | int ×2 (linhas 17, 21) | ≤1.00.11 | item e quantidade | não editar |

Impacto comum: o editor deve **recusar editar** (ou ao menos avisar) quando qualquer uma dessas listas
não estiver vazia ou `pendingExchange != null` — há transação em voo com o servidor.

Legados (só em saves antigos; ignorados no load 1.2.8):

| Caminho JSON | Tipo C# | Existiu em | Significado | Impacto |
|---|---|---|---|---|
| `BoxData.BoxTypes` | List\<EBoxType\> (`TH/SerializedBoxData.cs:7`) | 1.00.11–1.01.05 | tipo da caixa (0 NORMAL, 1 BOSS, 2 ACTBOSS) | nenhum (vazio em todos) |
| `BoxData.BoxUniqueId` | List\<ulong\> (linha 9) | 1.00.11–1.01.05 | id da caixa | nenhum |
| `BoxData.BoxQuantity` | List\<int\> (linha 11) | 1.00.11–1.01.05 | quantidade | nenhum |
| `tradingStashSaveDatas[].Index` / `.ItemUniqueId` / `.IsUnLock` | int / ulong / bool (`EasySaveData/TradingStashSaveData.cs:7-11`) | 1.00.11 | navio antigo | nenhum |
| `itemSaveDatas[].IsServerPendingItem` | (sem campo na 1.2.8) | 1.00.11 | item pendente de servidor (sistema antigo) | nenhum |

### 3.13 Campos de classe sem chave no JSON e chaves JSON sem campo (`class_vs_json.txt`)

- **Chave JSON sem `[JsonProperty]`**: `commonSaveData.FirstUnlockHeroKey` (propriedade get-only,
  todas as versões); legados sem campo na 1.2.8: `BoxData` (1.00.11–1.01.05), `tradingStashSaveDatas`
  (1.00.11), `itemSaveDatas[].IsServerPendingItem` (1.00.11). Nome JSON ≠ nome do campo:
  `ItemGetSourceType` → `GetSourceType`.
- **Campo sem chave em nenhum dos 24 saves**: todos os de `PendingEnchantSaveData`,
  `ItemRestorationPendingSaveData`, `BackendPostSaveData`, `BackendPostItemSaveData`, `MailSaveData`,
  `AlchemyReceipt` — só porque as listas estão sempre vazias. Campos privados que nunca vão ao JSON:
  `CommonSaveData.firstUnlockHeroKey`, `AccountSaveData.<playerId>k__BackingField` (sai via
  propriedade `playerId`), `AlchemyReceipt.o_*`, `ExchangeReceipt.o_*`.
- **Classe espelho** `tl` (`_g/tl.cs:5-32`): mesmos `[JsonProperty]` de um subconjunto de
  `PlayerSaveData` (common, BoxBucket*, moedas, heróis, atributos, pets, runas, inventário, baú, navio,
  cubo, itens). Usada por `qh.SnapShot` (0xD223B0 → `tl.iut` 0x937360); `qh` tem
  `<CompressAndSendSnapShotAsync>` e handlers de `BackendReturnObject` → o jogo envia esse recorte do
  save ao servidor (inferência pelo nome + handlers; não segui o envio).

## 4. Evolução entre versões

Comandos: `python tools/save_lab.py schema <antigo> --vs <novo>` (saídas em
`~/tbh_re/scratch/save_schema/vs_*.txt`) e `union_schema.py` (união de todos os 24 saves por versão,
para enxergar campos dentro de listas que estão vazias em um save isolado). `AccountSaveData` não mudou.

**1.00.11 → 1.01.05** (`SaveFile_Live_BackendBackUp.es3` → `Live_daily_20260907_203338.es3`)

| + entrou | − saiu |
|---|---|
| `AlchemyPendingIdList`, `AlchemyReceiptList`, `BoxBucketGetBoxList`, `BoxBucketUseBoxList`, `backendPostList`, `pendingEnchantList`, `pendingExchange`, `pendingItemRestorationList` | `itemSaveDatas[].IsServerPendingItem` |
| `remakeTradingStashSaveDatas[]{Index,IsUnLock,ItemUniqueId}` | `tradingStashSaveDatas[]{Index,IsUnLock,ItemUniqueId}` |
| `commonSaveData.LastDailyBackUpTime`, `settingSaveData.AskWarningTradingStash` | |
| `itemSaveDatas[].PrevUniqueId`, `.RegisterID`, `.ItemGetSourceType`, `.EnchantData[].EnchantVersion` | |

Leitura: é a versão que trouxe a camada de servidor/Steam Inventory (transações pendentes, rekey,
registro no mercado, navio refeito). `BoxData` ainda coexistia.

**1.01.05 → 1.2.3** (`Live_daily_20260907_203338.es3` → `Live_daily_20260914_170107.es3`)

| + entrou | − saiu |
|---|---|
| `commonSaveData.lastClearedStageKey`, `.prevNormalStageKey`, `.lastPlayedPlagueIntensity` | `BoxData{BoxQuantity,BoxTypes,BoxUniqueId}` |
| `heroSaveDatas[].EquippedSkinKey` | |
| `aggregateSaveDatas[].Content` | |
| `settingSaveData.AlwaysShowItemLevel`, `.ShowEnchantSlotView`, `.UseOpenAllTypeChestAllAtOnce`, `.UseOpenOneTypeChestAllAtOnce`, `.WindowOpacityValue` | |

Leitura: Plaguelands (estágios 2012xx–2014xx, intensidade, estatística por conteúdo), skins e opções de
UI. Evidência de "novo no jogo" e não só "não extraído": strings `Plaguelands*`, `StageName_2012/13/1401`,
`Skin_*`, `Setting_*` marcadas NEW em relação a `data/strings_en.json` (1.00.17), e os campos só
aparecem no save a partir da 1.2.3. `SkinInfoData`/`PlagueIntensityInfoData` só existem em
`research/1.2.8/tables`; a tabela em si pode não ter sido extraída antes, mas o conteúdo é novo
(inferência pelas strings e pelo histórico de saves).

**1.2.3 → 1.2.8** (`Live_daily_20260914_170107.es3` → `SaveFile_Live.es3`)

| + entrou | − saiu |
|---|---|
| `heroSaveDatas[].equippedItemBlocked` | — |
| `inventorySaveDatas[].IsBlocked`, `.Quantity` | |
| `stashSaveDatas[].IsBlocked`, `.Quantity` | |
| `remakeTradingStashSaveDatas[].Quantity` | |

Mudanças de **modelo** que o diff de chaves não mostra (confirmadas por `check_invariants.py`):

| Aspecto | 1.2.3 | 1.2.8 |
|---|---|---|
| Material empilhável | 1 `ItemSaveData` **por unidade** (ex. 145002 com 12 itens), 1 slot = 1 UniqueId | **1 `ItemSaveData` por ItemKey**; N slots com o mesmo UniqueId e `Quantity` 1..5 (L2d "nenhum" nos 17 saves 1.2.8) |
| Contagem de itens | 330 (113 MATERIAL) | 251 no 1º save 1.2.8 (40 MATERIAL); 270 no mais novo (51) |
| Migração observada | — | no 1º save 1.2.8 (22/09) quase todas as pilhas vieram com `Quantity`=1 (1 slot com 2; ex. 145002 em 14 slots), consolidadas depois até 5 por slot. Classes `MergeInventoryInit*`, `MergeRekeyedItemData{from,to,itemId}`, `ItemMergedRecordData` indicam que a fusão foi feita pelo servidor com rekey |
| Cadeado | `itemSaveDatas[].IsBlocked` | flag no slot; item sempre `false` |
| Navio | 10 slots `IsUnLock` | 4 (sem o DLC 4877934; §3.10) |

## 5. Semântica dos campos novos — detalhes e evidências

**Cadeado (`IsBlocked` / `equippedItemBlocked`).** UI: `Toast_BlockedItem` "Item is locked.",
`Toast_FailTradeInsert_BlockedItem` "Locked items cannot be loaded on the trade ship." (strings já
existentes na 1.00.17). Fluxo 1.2.8: slot carrega `IsBlocked` do JSON e, se o item legado estava
travado, trava o slot (`StashCache..ctor` 0x9C0D38-0x9C0D94; `wm..ctor` 0x9F8E91-0x9F8EFA; herói: OR em
`wj.kis` 0x9D58AD-0x9D59BA); travar/destravar escreve no slot (`StashCache.kdk` 0x9C14FC) e esvaziar o
slot destrava (`kdj` 0x9C1361); ao salvar o item sai com `IsBlocked=false` (`wh.vc.jlo` 0x979585).
Dado: herói 601, slot 7 (`EARING`, índice 7 = parte 8) tem `equippedItemBlocked=true` e o item
`IsBlocked=false` em todos os 17 saves 1.2.8 — exatamente esse modelo.

**`Quantity`.** Tamanho da pilha **no slot**. Capacidade por slot `min(5, ItemInfoData.MaxStack)`
(`StashCache.kdb`/`wm.kdb` = 5 em 0x9C0F70; `ben.nqy` 0xBC7650). `MaxStack` = 5 para os 143 MATERIAL e
vazio para GEAR/STAGEBOX. GEAR sempre 1. Slot vazio = 0.

**`EquippedSkinKey`.** Ver §3.5. `SkinInfoData`: `25x01001` padrão (`IsDefault`), `25101002` grátis
(Knight), `25x01002` dos demais no conjunto 25001002 ("Dusk Wanderers Bundle", compra). O save tem as
seis `x01002`.

**`lastClearedStageKey` / `prevNormalStageKey` / `lastPlayedPlagueIntensity`.** Ver §3.3. Sequência
nos saves: 1.2.3 `currentStageKey=201401` (Torment Plaguelands) com `prevNormalStageKey=4305` e
intensidade `[0,0,0,1]`; 1.2.8 de volta em 4305 com intensidade 11.

**`aggregateSaveDatas[].Content`.** `EAggregateContent` (0 Total, 1 Normal, 2 Plague); na 1.2.3 os
agregados antigos migraram como Content 0 e surgiram linhas 1/2 para os tipos que distinguem conteúdo
(MonsterKill, BoxObtain, BoxOpen, StageClear, ActBossKill…) — strings novas `Satistics_Plague*`.

**Flags de `settingSaveData`.** Ver §3.4 (5 novas na 1.2.3, 1 na 1.01.05).

**`BoxData` → `BoxBucket*`.** O antigo `SerializedBoxData` (listas paralelas tipo/id/quantidade) saiu na
1.2.3; desde a 1.01.05 as caixas de estágio são itens `STAGEBOX` com `IsBucketBox=True` e
`IsSteamItem=True` (`ItemInfoData.cs:0x70/0x83`) guardados fora dos slots, e as duas listas de string
guardam o que falta sincronizar com o servidor (`InventoryProcessBoxRequest{getitemkey, useItemKeyList,
stageKey, addDlcNumber}`). Save mais novo: 3 caixas em `Get` (existem em `itemSaveDatas`), 10 ids em
`Use` (já não existem); 1 caixa 910051 órfã desde a 1.00.11, fora das listas.

## 6. Invariantes — resultado no save mais novo

Script: `python ~/tbh_re/scratch/save_schema/check_invariants.py <save>` (saída completa em
`invariants_SaveFile_Live.txt`). Rodado nos 17 saves 1.2.8: mesmo resultado em todos.

| # | Invariante | Resultado (SaveFile_Live.es3) | O que o jogo faz se violar |
|---|---|---|---|
| I1 | `UniqueId` único em `itemSaveDatas` | OK (270/270) | remove o duplicado no load (`wh.vc.jln`) |
| I2 | `UniqueId` ≠ 0 e `ItemKey` > 0 | OK | `ItemSaveData.IsValid` falso |
| I2b | faixa de `UniqueId` | 5,017e17..5,276e17: **> 2⁵³** (inseguro em JS), < 2⁶³ | — (editor já manda como string à UI, `server.py:62`) |
| I3 | `ItemKey` ∈ `ItemInfoData` 1.2.8 | OK | item apagado no load (`jln`) |
| L1 | toda referência (equip/inventário/baú/navio) aponta para item existente | OK (266 refs, 0 quebradas) | não verificado (slot mostraria ItemKey -1, `StashCache.kcz`) |
| L2 | GEAR em no máximo 1 lugar | OK | — |
| L2' | MATERIAL: 1 `ItemSaveData` por ItemKey, UniqueId pode repetir entre slots | OK (17 UniqueIds em 2-5 slots; "falha" do L2 genérico é o modelo) | desconhecido (StackMigration=16 existe; não achei o chamador) |
| L3 | itens sem slot | 4 STAGEBOX (3 em `BoxBucketGetBoxList`, 1 legado 910051) | esperado para caixas-balde |
| H1 | `len(equippedItemBlocked) == len(equippedItemIds) == 10` | OK (6 heróis) | load aloca pelo tamanho de `ids` e copia o mínimo |
| H9 | `equippedItemIds[i]` tem `PARTS == EItemParts(i+1)` | OK (60 slots) | — |
| H3 | `equippedItemBlocked[i] == item.IsBlocked` | "falha" 1 (herói 601 slot 7) — **esperado** (§5) | — |
| B1/B2 | `IsBlocked` de slot × item; slot vazio sem cadeado | OK | `kdj` limpa ao esvaziar |
| Q1 | vazio ⇒ `Quantity`=0; ocupado ⇒ ≥1 | OK | `PostLoad` põe 1 |
| Q3 | GEAR com `Quantity`=1 | OK | — |
| Q4 | `Quantity` ≤ `min(5, MaxStack)` | OK (máx 5) | `kdg` recusa somar acima |
| S1 | `Index` único 0..n-1 (inv 260, baú 343, navio 10) | OK | inventário recria slots faltantes (`wh.uy.jgp`) |
| E1 | `len(EnchantData)` = regra da raridade (0/2/4/6) | OK (270/270) | reescrito no save |
| G1 | `maxCompletedStage`, `lastClearedStageKey`, `currentStageKey`, `prevNormalStageKey` ∈ `StageInfoData` | OK (4310/4310/4305/4305) | `currentStageKey` ausente ⇒ exceção no load |
| G2 | `len(lastPlayedPlagueIntensity)==4`, valores 0..20 | OK `[0,0,0,11]` | save força len 4 |
| H4/H5 | `heroKey` ∈ `HeroInfoData`; `EquippedSkinKey` ∈ `SkinInfoData` | OK | skin inválida ⇒ padrão |
| R1/R2 | runa ∈ `RuneInfoData`, `Level ≤ MaxLevel` | OK (248; 228 no máximo) | — |
| T3/T4 | atributos ≤ MaxLevel; receitas coerentes com as tabelas | OK | — |
| A1 | agregado `(Type,SubKey,Content)` único | OK (241) | — |
| M1 | `mailSaveDatas.Keys` e `MailData` do mesmo tamanho | OK (0/0) | — |
| Z1 | listas pendentes vazias / `pendingExchange` nulo | OK (todas vazias) | — |
| RT | roundtrip pelo caminho do editor | OK: conteúdo idêntico, HMAC OK (`save_lab roundtrip … --out scratch`) | — |

Significados pedidos: `PrevUniqueId` = id anterior a rekey do servidor (morto na 1.2.8); `RegisterID` =
registro de venda no mercado/navio; `IsChaotic` = flag "caótico" do item, lido para `ObscuredBool` e
regravado de `va.jjn`, sem nenhum item `true` nos 24 saves — significado de jogo não confirmado;
`ItemGetSourceType` = enum de origem (§3.6).

## 7. Codificações numéricas e limites de tipo

| Campo | Tipo C# | JSON observado | Limite válido | Nota para o editor |
|---|---|---|---|---|
| `HeroLevel` | int32 | 101 | **1..101** | hoje 1..1000 |
| `HeroExp` | double | 154908782431.04541 | ≥0, finito | Python regrava com `repr` (dígitos finais mudam, mesmo double) |
| `AbilityPoint` | int32 | 0 | 0..2³¹-1 | hoje 0..999999 (ok) |
| `AllocatedHeroAbilityPoint` | int32 | 172–174 | idem | não editado |
| `currenySaveDatas[].Quantity` | int64 | 37681109 | 0..9,22e18 | hoje 1e13 (ok) |
| `cubeSaveLevelData.Level` | int32 | 100 | **1..100** | hoje 1..999 |
| `cubeSaveLevelData.Exp` | float32 | 1000000000.0 | ≥0; ≤3,4e38 | valores não representáveis arredondam |
| `RuneSaveData[].Level` | int32 | — | 0..`MaxLevel` | usar tabela 1.2.8 |
| `Quantity` (slots) | int32 | 1–5 | 0..5 | — |
| `UniqueId`, `ItemUniqueId`, `equippedItemIds[]`, `mailSaveDatas.Keys[]` | uint64 | 527630583597553364 | 1..2⁶⁴-1 | > 2⁵³: nunca passar por double/JS number |
| `BoxBucket*[]`, `AlchemyPendingIdList[]` | string | "527630583597553296" | — | ulong em texto decimal |
| `lastSavedTime`, `LastRollingBackUpTime`, `LastDailyBackUpTime`, `expirationTicks`, `reservationTicks`, `TimestampTicks` | int64 | 639262425516675463 | ticks .NET (100 ns desde 0001-01-01), hora **local** | `save_lab.ticks_to_dt` |
| `playTime` (account/common) | float32 | 2369979.25 | — | resolução cai com o tempo de jogo |
| `lastExitSteamUnixSec*` | int64 | -823198293684408749 / 8811772890731132700 | cifrado ACTk | intocável |
| `sessionCounter` | uint32 | 94 | — | — |
| `aggregateSaveDatas[].Value` | int64 | 14814928272 | — | já > int32 |
| `BoxAlphaValue`, `WindowOpacityValue` | float32 | 1.0 | 0..1 (inferência) | — |
| enums (`language`, `maxFps`, `windowZoomRate`, `windowLayoutPreset`, `LogFilter`, `RecipeType`, `ModType`, `StatType`, `CubeRecipeTypeInt`, `Type`, `Content`) | int | 10, 0, -1… | membros do enum | sempre número, nunca nome |
| `MailSaveData.receivedDate` | DateTime | (sem amostra) | string ISO 8601 do Newtonsoft (inferência) | não editar |

Regras de escrita (inferência sobre o Newtonsoft padrão, coerente com os tipos do dump): valor fora da
faixa de `int`/`uint` ou número com parte decimal (`5.0`) num campo inteiro faz o
`DeserializeObject<PlayerSaveData>` lançar exceção — o save inteiro deixa de carregar. O editor já
converte com `int()` em `_num` (`server.py`), mas os limites superiores precisam respeitar a tabela acima.

## 8. Impacto no editor — recomendações (ordem de prioridade)

1. **Cercas de valor** (baixo esforço, evita save quebrado): `HeroLevel` 1..101; cubo `Level` 1..100;
   todo campo `int` ≤ 2³¹-1; `EquippedSkinKey` só da lista do herói.
2. **Recusar edição com transação em voo**: se `AlchemyPendingIdList`, `AlchemyReceiptList`,
   `pendingEnchantList`, `pendingItemRestorationList`, `backendPostList` não vazias, `pendingExchange`
   não nulo ou `BoxBucket*` não vazias, avisar/bloquear (as `BoxBucket*` quase sempre têm algo: pelo
   menos avisar e jamais tocar nelas).
3. **Nunca tocar**: `AccountSaveData` inteiro (exceto ler versão), `LastRolling/DailyBackUpTime`,
   `UniqueId`/`ItemUniqueId`/`PrevUniqueId`/`RegisterID`/`ItemGetSourceType`/`IsChaotic`, navio,
   `IsUnlock*` de slots, `aggregateSaveDatas`.
4. **Cadeado**: se o editor um dia mostrar/alterar cadeado, ler/escrever o flag do **slot**
   (`inventorySaveDatas[].IsBlocked`, `stashSaveDatas[].IsBlocked`, `equippedItemBlocked[i]`), nunca o
   do item; manter `len(equippedItemBlocked) == len(equippedItemIds)`.
5. **Pilhas**: qualquer feature de materiais precisa do modelo 1.2.8 (1 `ItemSaveData` por ItemKey,
   `Quantity` por slot ≤ 5). Recomendo **não** implementar criação de itens: UniqueIds são itens do
   servidor/Steam Inventory (`Notice_Delete_OnlyInventoryItem` "Items not held on the server have been
   cleaned up", 1.00.17; `Deleted_RemovedInventory` "Untradable items have been removed from your Steam
   Inventory", 1.00.17 e 1.2.8).
6. **Encantamento**: manter `len(EnchantData)` pela regra da raridade (`GradeInfoData.ExtraSlotAmount_*`)
   — o jogo corta o excedente no próximo save; `EnchantVersion=null`.
7. **Dados**: promover para `data/` ao menos `ItemInfoData` (ITEMTYPE, MaxStack, IsBucketBox),
   `LevelInfoData`, `CubeLevelInfoData`, `StageInfoData`, `SkinInfoData`, `AttributeInfoData`,
   `RuneInfoData` 1.2.8 (+51 runas, +194 equipamentos, `CORROSION`, `StatType 64`).
8. **Aviso ao usuário**: o jogo manda snapshots do save ao backend e tem textos de bloqueio de conta e
   de navio por "atividade suspeita" (`PopUp_BlockedUser`, `PopUp_BlockedUser_TradeShip`, novos na
   1.2.8; `Notice_DetectAnticheat`). O editor deve deixar isso explícito antes de gravar.

## 9. Perguntas em aberto

- Relação exata entre `HeroLevel`, `AbilityPoint`, `AllocatedHeroAbilityPoint` e
  `attributeSaveDatas` (o jogo recalcula/valida? não achei o validador).
- Onde `EItemGetSourceType.StackMigration (16)` é usado (nenhum chamador direto com a constante; nenhum
  item 16 nos saves) e o que o cliente faz com dois `ItemSaveData` do mesmo material.
- O que acontece no load com slot apontando para UniqueId inexistente (L1) — não desmontei esse caminho.
- `IsChaotic`: significado de jogo (nenhum item `true` em 24 saves).
- A caixa 910051 órfã desde a 1.00.11 (fora de `BoxBucket*`) — resíduo inofensivo ou pendência.
- O conteúdo exato enviado por `qh.<CompressAndSendSnapShotAsync>` e com que frequência (não segui;
  fora do escopo de contornar verificações, mas relevante para avisar o usuário).

## 10. Reprodução

```
# a partir de C:/Users/andre/Dropbox/projetos/saveEditor
python tools/save_lab.py schema <save_1.2.3> --vs <save_1.2.8>
python ~/tbh_re/scratch/save_schema/union_schema.py          # uniao por versao -> union_schema.json
python ~/tbh_re/scratch/save_schema/check_invariants.py ~/tbh_re/saves/20260929_013650/SaveFile_Live.es3
python ~/tbh_re/scratch/save_schema/class_vs_json.py         # classe x JSON
python ~/tbh_re/scratch/save_schema/psd_fields.py            # quem le/escreve cada campo do PlayerSaveData
python ~/tbh_re/scratch/save_schema/il2dis.py 0x9D55B0       # desmonta wj.kis (qualquer RVA do dump.cs)
python ~/tbh_re/scratch/save_schema/xref_call.py 0x978F80    # quem chama um metodo
python tools/save_lab.py roundtrip ~/tbh_re/saves/20260929_013650/SaveFile_Live.es3 --out ~/tbh_re/scratch/save_schema/rt/rt.es3
```
