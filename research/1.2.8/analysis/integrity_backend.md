# Integridade, servidor e anti-cheat — Taskbar Hero 1.2.8

O que o jogo 1.2.8 **valida**, o que **reporta** e o que isso significa para o risco de editar o save.

- Build analisado: 1.2.8 (`build=3a1772f1bac841dab68ca5cd5e0e157c`, arquivo `~/tbh_re/1.2.8/VERSION`). Data: 2026-09-29.
- Método: análise **estática**. `dump.cs`/`script.json` (Il2CppDumper) + disassembly com capstone da **cópia**
  `~/tbh_re/1.2.8/bin/GameAssembly.dll`. As strings do código são ofuscadas (GUPS.Obfuscator): foram
  decodificadas do blob de `<PrivateImplementationDetails>{BC7063EA…}.a` (cctor 0xBE45F0: `byte[0x2288B]` da
  metadata offset 0xB2CFB8, `b[i] ^= (i & 0xFF) ^ 0xAA`; getter → `a_(idx, off, len)` = `UTF8.GetString`).
  Os 4195 literais decodificados estão em `~/tbh_re/scratch/integrity_backend/strgetters.tsv`.
- Nenhum arquivo do jogo, da instalação ou do save vivo foi lido. Os saves usados são as cópias em
  `~/tbh_re/saves/20260929_013650/`.
- Cuidados na leitura: o ofuscador cria **métodos isca** (mesma assinatura, strings Base64 aleatórias, sem
  chamadores) e o linker junta funções idênticas (ICF), então um mesmo RVA pode aparecer com vários nomes. Cada
  afirmação abaixo foi conferida pelo **chamador real** (xref de `call`/`jmp` ou referência a `MethodInfo`).
  Quando algo é inferência, o texto diz.
- Notação: `RVA` = endereço relativo no GameAssembly.dll; `dump.cs:N` = linha no dump; strings coreanas foram
  traduzidas entre parênteses.

---

## 0. Resumo

1. **O save manager é `bde`** (era `bal` na 1.00.17). A validação no load **não mudou**: SystemInfo =
   `Base64(HMAC-SHA256(chave, account + "|" + player + "|" + ownerSteamId))` e `ownerSteamId` precisa ser o Steam
   logado. A chave atual do editor valida **24/24** snapshots (versões 1.00.11 → 1.2.8), e o `roundtrip` do editor
   num save 1.2.8 dá HMAC OK.
2. **Se o HMAC falhar:** o jogo registra no log, **envia o relatório `Save_Tampered`** (HTTP POST para um Google
   Apps Script do estúdio, com o ticket de autenticação Steam), mostra "Save data tampering detected. Attempting
   backup." e **restaura o `.bak` rotativo mais novo que for válido**. A edição é descartada. Se nenhum backup
   servir, o jogo **se recusa a salvar** durante a sessão.
3. **Quem manda no inventário é o servidor** (TheBackend/BACKND, função `inventoryV2`, integrado ao Steam
   Inventory e ao Steam Market). No login e a cada atualização de inventário, itens que só existem no save são
   **apagados** (log `AnomalyItem`). Um `ItemKey` diferente do que o servidor tem para o mesmo `UniqueId` é
   logado como `TemperedItem`/`TamperedItemIdDetected` e o item também sai. A string "Items not held on the server
   have been cleaned up." sumiu, mas a limpeza continua: agora aparece um toast genérico ("Organizing items carried
   away by the trade ship.") e o evento é enviado ao servidor.
4. **Tudo o que o editor mexe chega ao servidor.** A cada boot, e a cada 8 h de jogo (28.800 s), o jogo envia ao
   GameLog do TheBackend (`DataSnap`) um **snapshot comprimido** com `commonSaveData`, moedas, heróis, atributos,
   pets, runas, inventário, baú, trade ship, receitas e nível do cubo, e **todos os itens com seus
   encantamentos**. Qualquer edição fica visível para o desenvolvedor.
5. **O servidor também pode sobrescrever o save.** No boot o jogo baixa do CloudSave do TheBackend a chave
   `snapshot`, que, se existir, é aplicada por cima do progresso local e depois apagada. A chave `itemRestoration`
   sobrescreve os encantamentos de itens específicos. O servidor também pode **bloquear a conta** ("Suspicious
   activity was detected, so your account has been blocked.") ou só o Trade Ship (erro 9002).
6. **Telemetria de abuso (`ox`, via CheatReporter):**
   - `Level_50/80`: roda **no load**, para cada herói, comparando com a estatística Steam `play_time_minutes`
     (limites de 600 e 3000 minutos).
   - `Gold_Massive`: dispara ao ganhar ouro com saldo acima de 100.000.000 e `play_time_minutes` < 600.
   - `ItemLevel_50/80`, `Grade_*` e `Box_*`: disparam em drops e aberturas de caixa.
7. **ACTk:** estão ativos TimeCheating, SpeedHack e ObscuredCheating, mais um watchdog que checa a cada 30 s se os
   detectores continuam ligados. Qualquer detecção gera relatório, popup e **fecha o jogo à força**. Editar o
   arquivo de save **não** aciona o ACTk.
8. **Risco por função do editor** (seção 5.3):

   | Função | Risco |
   |---|---|
   | Skills | baixo |
   | Encantamento dentro das tabelas | baixo a médio |
   | Runas | médio a baixo |
   | Ouro | médio |
   | Herói | médio (limite real é 101; o editor aceita até 1000) |
   | **Cubo** | **alto**: o `cubeLev` vai em toda requisição de consumo ao servidor e o nível 10 libera o Trade Ship/Steam Market; limite real 100, o editor aceita 999 |
   | **Pets 6001–6003** | **alto e fora de escopo**: são DLC; o editor não deve desbloquear |

---

## 1. Pipeline do save na 1.2.8

### 1.1 Nomes: 1.00.17 → 1.2.8

| Papel | 1.00.17 (`docs/SAVE_PORTING.md`) | 1.2.8 | RVA | Evidência |
|---|---|---|---|---|
| Save manager (`ob<T>` singleton) | `bal` | **`bde`** (TypeDefIndex 1638) | — | `dump.cs:76016`; const `biia="SystemInfo"` em `dump.cs:76046`, `biib="\|"` |
| Chave HMAC (campo) | `bgco` | `bde.bihy` (`byte[]`, +0x80) | — | `dump.cs:76044` |
| Inicializa a chave | `bal.Awake`: `bgco = bam.mdj()` | `bde.Awake`: `bdf.nos()` e depois `bihy = bdf.nox()` | Awake 0xB7BE80; `bdf.nos` 0xB8CCC0; `bdf.nox` 0xB8D490 | disasm do Awake (keystore `bdf`, `dump.cs:76382`) |
| Monta o SystemInfo | `mck` | `bde.nnv(a,b,c)` = `Base64(HMACSHA256(bihy).ComputeHash(UTF8(Concat(a,"\|",b,"\|",c))))` | 0xB85550 | disasm: `string[5]{a,"\|",b,"\|",c}` → `String.Concat` → `HMACSHA256..ctor(bihy)` → `ToBase64String` |
| Compara | (em `mcr`) | `bde.hkv(saved, calc)`: compara os bytes UTF-8 em tempo constante (XOR/OR) | 0xB80B90 | disasm |
| Valida no load | `mcr` | **`bde.nof(path)`** | 0xB86990 | seção 1.3 |
| Carrega com fallback | ? | `bde.noe()` | 0xB867D0 | chamado por `qu.qo.MoveNext` (InitSaveDataAsync) 0xD2C490 |
| Restaura de backup | ? | `bde.nog()` | 0xB86F30 | seção 2 |
| Popup de adulteração | `StartOption.kri` | `StartOption.luo` (texto `UI_PopUp_SaveDataCheat`) | 0xABEEA0 | chave em `tj+0xF8`, via `tj..cctor` |
| Popup de SteamId | `StartOption.krj` | `StartOption.lup` (texto `UI_PopUp_NotMatchSteamId`) | 0xABEFE0 | chave em `tj+0xF0` |
| Salvar | `mcc`/`ldo` | `nnp` → `nnr` (SaveAsync) → `nnu` → `nnz` | ver 1.4 | — |

Os textos dos popups em inglês (`research/1.2.8/strings_en.json`): "Save data tampering detected. Attempting
backup." e "Save data account info does not match. Attempting backup."

### 1.2 Sequência: boot → load → valida → joga → salva

1. **Boot** (`qu.qr.MoveNext` 0xD2CEA0, o GameManager):
   - `oy.gsy` 0xD029E0 liga o anti-cheat (§4) e inicializa o CheatReporter (`pc.gth` 0xD04CF0).
   - Passo `"InitSaveDataAsync"`: `qu.qo.MoveNext` 0xD2C490 sai do jogo se não houver Steam ("Steam 환경 미감지 —
     게임 종료" = Steam não detectado, fechando o jogo). Caso contrário chama `bde.noe()` e guarda o resultado em
     `qu.belz` (+0x20) = "load OK".
2. **Load com fallback** (`bde.noe` 0xB867D0):
   1. `noc` apaga o staging `.new` e `nol` cria o BackendBackUp uma única vez (§2).
   2. Se o arquivo principal existe e passa em `nod` (existe e tem ≥ 64 bytes; `bihr=64`, `dump.cs:76037`), chama
      `nof(main)`. Se falhar, chama `nog()`, que tenta os `.bak` rotativos.
   3. Se o principal não existe: `nog()`. Se isso também falhar, cria dados novos (`nnl`, "first game").
3. **Validação** (`bde.nof` 0xB86990): detalhada em 1.3.
4. **Login no servidor e sincronização**, ainda em `qu.qr`:
   - `BackEnd.Backend.InitializeAsync`, `BackendMember.AuthorizeFederation` (Steam) e checagem de versão
     (`BackendUtils.GetLatestVersion`, popup `Notice_NotMatchAppVersion`).
   - CloudSave `snapshot` e `itemRestoration`, e o log `GameAuth` (§3).
   - Inventário do servidor: `yi` (`GameData.GetMyData("SteamItemInfo", …)`) e as funções `initV2`/`mergeInventory`,
     seguidas de `qv.hmd` (SynchronizeInventoryByBackendData, §3.6).
5. **Primeiro save e snapshot:**
   - `bde.nnq` (EnsureFirstSaveAsync, 0xB843C0; chamada em `qu.qr` 0xD2FC19) espera um SteamId válido e **salva
     logo depois do load**.
   - `qu.hlq` 0xD31020 (fim do boot) chama `qh.SnapShot()`, que envia o **DataSnap**, e depois `qu.hlr` 0xD31810
     calcula a recompensa offline.
6. **Durante o jogo**: autosave a cada **180 s** (`bde.<AutoSaveAsync>d__68.MoveNext` 0xB792B0; constante 180.0 em
   0x4B9BC60), mais cerca de **50 chamadores** de `bde.nnp()` (StageManager, cubo, correio…), e save imediato após
   encantar (`wh.Cube.<TryEnchantAsync>` → `nnr`). DataSnap a cada 28.800 s de jogo (§3.5).
7. **Ao fechar**: `bde.OnApplicationQuit` 0xB7BF60 → `nns` 0xB846D0 faz um save síncrono ("종료 시 저장…" = salvar ao
   fechar).

### 1.3 O que `nof` valida (1.2.8)

| # | Checagem | Se falhar | Relatório ao servidor? | Evidência (RVA em `nof`) |
|---|---|---|---|---|
| 1 | chave ES3 `AccountSaveData` existe | log "AccountSaveData 키 없음" (chave ausente), retorna false | não | 0xB86A83 `bif.oor` (KeyExists) |
| 2 | chave `PlayerSaveData` existe | log e false | não | 0xB86AB5 |
| 3 | chave `SystemInfo` existe | log **"HMAC 키 없음 (Legacy 거부)"** (sem HMAC, save legado rejeitado), false | não | 0xB86B46 → 0xB86DFB |
| 4 | `hkv(SystemInfo, nnv(accJson, plyJson, account.ownerSteamId))` | log "세이브파일 변조 의심" (suspeita de adulteração) + **`pc.gtj(Save_Tampered=24, [])`** + `StartOption.luo`, false | **sim** (CheatReporter) | 0xB86BA6 `nnv`, 0xB86BB7 `hkv`, 0xB86DA1 `pc.gtj(0x18)`, 0xB86DDF `luo` |
| 5 | SteamId atual válido (`nnx` = `SteamUser.GetSteamID().ToString()`) | log "현재 SteamId invalid — … skip" (SteamId atual inválido, comparação pulada) | não | 0xB86BCF; `nnx` 0xB857C0 |
| 6 | `account.ownerSteamId == SteamId atual` | log "SteamId 불일치 (도용 의심): saved=…, current=…" (SteamId diferente, suspeita de roubo de conta) + `StartOption.lup`, false | não | 0xB86C0B `op_Inequality` → 0xB86D30 `lup` |
| 7 | se tudo passou | `biha` = account e `bihb` = `JsonConvert.DeserializeObject<PlayerSaveData>(ply)`, depois `PostLoad()`, retorna true | — | 0xB86C47, 0xB86C6B `PlayerSaveData.PostLoad` 0x927AE0 |

**O que não é validado no load**: `version`, `isFirstRun`, `forceApplyServerData`, `lastSavedTime`, `playTime`,
`lastExitSteamUnixSecEncrypted/Key`, `sessionCounter` e `playerId`. Nenhum desses é lido em `nof`, e
`PostLoad` só cria listas vazias para campos nulos (disasm 0x927AE0: apenas `List<>..ctor`, sem comparar versão).
Onde alguns deles aparecem:
- `lastExitSteamUnixSec*` é o horário **do servidor Steam** (`SteamUtils.GetServerRealTime`) na saída, codificado
  como `ObscuredLong` (`AccountSaveData.Get/SetLastExitSteamUnixSec` 0x912860/0x912890). Serve para a recompensa
  offline (`qu.hlr` 0xD31810 → `sd.ilp`).
- A cada save, `bde.nnu` 0xB84B30 regrava `ownerSteamId` com o SteamID atual (0xB84CC3) e `lastExit` com
  `GetServerRealTime` (0xB853C9/0xB853DF), e chama `PlayerSaveData.PreSave` 0x928640, que **reconstrói o save a
  partir do estado em memória**.
- `sessionCounter` e `forceApplyServerData`: não encontrei leitura relevante. Pela lógica são contadores de
  controle, mas isso **não foi rastreado**.

**Comparação com a 1.00.17**: as duas checagens centrais (HMAC e ownerSteamId) são as mesmas descritas em
`docs/SAVE_PORTING.md`, e os dois popups já existiam na 1.00.17 (`data/strings_en.json` tem o mesmo texto). Sem o
dump da 1.00.17 aqui, **não dá para afirmar** se a rejeição de save "Legacy" e o envio de `Save_Tampered` são
novos.

### 1.4 Escrita (`bde.nnz` 0xB85980) e travas

- `nnv` calcula o SystemInfo. Até **3 tentativas** (`bihp=3`, 0xB85A80), com backoff via `Math.Pow`/`Thread.Sleep`.
- Cada tentativa grava no **staging** `SaveFile_Live.es3.new` (`bihi`, montado em `nnk` 0xB83A10) as três chaves por
  `big.oqk<string>` e `big.oqh` (ES3File/Sync). Em seguida **relê e compara** as três strings (`noa` 0xB86210) e
  troca o arquivo de forma atômica com `File.Replace` ou `File.Move` (0xB85C60/0xB85C6A).
- **Trava de segurança** em `bde.<SaveAsync>d__44.MoveNext` 0xB79D50: se o load falhou (`qu.belz == false`), o jogo
  loga "로드에 실패했는데 저장을 하려고 합니다" (o load falhou mas algo tentou salvar) e **não salva**
  (0xB79F5A → 0xB7A05A). Um save inválido não é sobrescrito pelo jogo; a sessão só não persiste.
- Consequência prática: com o jogo aberto, qualquer edição externa é sobrescrita em até 180 s, ou antes, já que os
  saves por evento são frequentes. A regra do projeto "escrever só com o jogo fechado" continua obrigatória.

### 1.5 Checagem da chave atual (comando)

`python tools/save_lab.py info <arquivo>` rodado nos 24 arquivos de `~/tbh_re/saves/20260929_013650/`: **todos**
retornam `SystemInfo : OK (chave HMAC atual confere)`. São quatro versões:

| Versão | Arquivos |
|---|---|
| 1.00.11 | `SaveFile_Live_BackendBackUp.es3` |
| 1.01.05 | 5 arquivos (4 `Live_daily_*` e `SaveFile_Live.es3.bak`) |
| 1.2.3 | `Live_daily_20260914_170107.es3` |
| 1.2.8 | os 17 restantes |

`python tools/save_lab.py roundtrip …/SaveFile_Live.es3 --out ~/tbh_re/scratch/integrity_backend/roundtrip_SaveFile_Live.es3`
deu: HMAC do original OK, HMAC do regravado OK, "conteudo identico: sim", exit 0. A string não é idêntica byte a
byte (só a notação de float muda), e isso não afeta o HMAC porque o editor calcula o HMAC sobre as strings que ele
mesmo grava.

---

## 2. Backups que o jogo grava

Todos são criados por `bde`. Nomes montados em `nnk` 0xB83A10 (`"{0}_{1}{2}.bak"`, `"_BackendBackUp"`, `".new"`) e
constantes em `dump.cs:76035-76047`.

| Arquivo | Quem cria / quando | Retenção | Usado na restauração automática? | Validação antes de copiar |
|---|---|---|---|---|
| `SaveFile_Live.es3.new` | staging de cada save (`nnz`) | apagado por `noc` 0xB86550 | não | releitura das 3 strings (`noa`) |
| `SaveFile_Live_{1..5}.es3.bak` (rotativo) | `nnz`, **após cada save bem-sucedido**: `File.Copy(main, bihj[bihl])` com `bihl = (bihl+1) % 5` (0xB85EB0-0xB85ECF) | 5 | **sim** (único conjunto usado por `nog`) | nenhuma; é cópia do principal já verificado |
| `SaveFile_Live_backup_yyyyMMdd_HHmmss.es3` | `nok(prefixo, "_backup_", 5)` 0xB874E0, quando se passaram **≥ 6 h** desde `commonSaveData.LastRollingBackUpTime` (`noh` 0xB87210; `TimeSpan.FromHours(6.0)` no cctor 0xB7C1F0) | 5 | não | `nod` (tamanho ≥ 64) do principal |
| `Live_daily_yyyyMMdd_HHmmss.es3` | `nok(noj(), "_daily_", 30)`, quando se passaram **≥ 24 h** desde `LastDailyBackUpTime` | 30 | não | `nod` |
| `SaveFile_Live_BackendBackUp.es3` | `nol` 0xB87840 no load: **só se não existir**; copia o principal se `nod` passar e apaga a cópia se ela não passar ("복사본 검증 실패 → 삭제" = cópia inválida, apagada) | 1, nunca atualizado | não | `nod` |
| `SaveFile_Live.es3.bak` (sem número) | **não é do jogo**: é o backup do editor (`State.save.save(path, backup=True)` em `server.py`) | — | não | — |
| `backend.dat`, `backend_cdn.dat` | SDK TheBackend (classes internas do `Backend.dll`; literais "backend.dat load success" e "fail to load backend.dat") | — | não | não são save. Inferência: guardam o token/sessão do SDK |

Os snapshots batem com isso: `_1…_5.bak` com horários de 01:29 a 01:35 (um por save, e o `_1` é idêntico ao
principal de 01:35:51); `_backup_` de 27/09 13:12, 19:13, 28/09 01:15, 07:16 e 29/09 01:05, com cerca de 6 h entre
eles; `Live_daily_*` um por dia, com dailys da 1.01.05 ainda guardados (retenção de 30); BackendBackUp na versão
1.00.11, de 2026-06-14.

**Rollback automático:**
1. **Local**: quando o load falha (HMAC, SteamId ou arquivo pequeno), `nog` 0xB86F30 copia os 5 caminhos
   rotativos, ordena (comparador `bde.<>c.nne` 0xB7AE90, que usa existência e data) e, para cada um, testa
   `File.Exists` → `nod` → **`nof` completo** (HMAC e SteamId). O primeiro que passa vira o principal
   (`File.Copy(bak, main, true)`, log "백업에서 복구 성공" = restaurado do backup). Os `_backup_`, `daily` e
   BackendBackUp **não** entram automaticamente.
2. **Comandado pelo servidor** (§3.5): CloudSave `snapshot` sobrescreve o progresso; `itemRestoration` sobrescreve os
   encantamentos de itens; a sincronização de inventário apaga os itens que só existem no save. Os que só existem no
   servidor voltam pelo correio (inferência, ver §3.6).

Consequência para o editor: um save editado com HMAC inválido é revertido **em silêncio** para o último `.bak`
rotativo válido e ainda gera `Save_Tampered`. Com HMAC válido, os 5 `.bak` rotativos passam a guardar o estado
editado já nos próximos saves, então **o único ponto de volta garantido é o `.es3.bak` do editor** (ou os
`_backup_`/`daily`).

---

## 3. Servidor

### 3.1 Com quem o jogo fala

| Destino | Componente | Para quê | Evidência |
|---|---|---|---|
| TheBackend / BACKND (`*.thebackend.io`: `api.`, `auth.`, `gamer.`, `gameinfo.`, `post.`; um `execute-api` da AWS em ap-northeast-2; `sdk-log.thebackend.io`) | `Backend.dll` (+ `TheBackendSettings.dll`) | login, dados do jogador, funções de servidor, correio, logs, CloudSave | `stringliteral.json:45479-46151`; dono do literal: classe interna do SDK `arNcYmg3r763yx3Ept7.FUvGAvg1tKbyYt5Z0xa` |
| Steam | Steamworks.NET + Heathen | ticket de autenticação, **Inventory Service** (itens negociáveis, `ExchangeItems`/`ConsumeItem`/`GetAllItems`/`StartPurchase`), estatísticas e conquistas, DLC, `GetServerRealTime` | xrefs a partir de `Assembly-CSharp` (`zc`, `yv`, `ze`, `DLCManager`, `bde`) |
| Google Apps Script nº 1 (`script.google.com/macros/s/…/exec`) | `pc` = **"[CheatReporter]"** | relatórios de trapaça e anomalia (§3.8) | `dump.cs:27929` (const `bedf`); POST em `pc.<ReportInBackGroundAsync>d__22.MoveNext` 0xCF3E50 |
| Google Apps Script nº 2 | `pg` = **"[SteamIdReporter]"** | envia `{steamId, appid, auth, ticket}` no boot (`pg.gtx` 0xD06990, chamado em `qu.qr` 0xD2DB0B) | `dump.cs:28151`; `pg.Payload` (TypeDefIndex 622) |

### 3.2 APIs do TheBackend chamadas pelo jogo

Levantamento pelas referências a `Method$BackEnd.*` e chamadas diretas a partir de `Assembly-CSharp`
(`scratch/integrity_backend/backend_mi.txt` e `backend_api.txt`):

| API | Chamadores | Uso |
|---|---|---|
| `BackendMember.AuthorizeFederation` | `qu.qr`, `qh.hhl`, `qh.hny` | login federado via Steam |
| `BackendMember.WithdrawAccount` | `qh.ftc`/`hhy`/… (alguns são isca) | sair da conta no servidor. Inferência: fluxo de reset de dados |
| `BackendUtils.GetLatestVersion` | `qu.qr`, `qj` | versão mínima (`Notice_NotMatchAppVersion`) |
| `BackendUtils.GetServerTime` | `qu.qr`, `qh` | hora do servidor |
| `BFunction.InvokeFunction` | `qh.hhv/hhw/jcs/kcb` | funções de servidor (§3.3) |
| `BGameData.GetMyData` | `yi.yd.kvk` 0xA5D180 | tabela `SteamItemInfo`, colunas `steamSlot`/`marketData`/`pendingTx` e `items` ("[GET MY DATA]") |
| `BUpgradePost.GetPostList` | `xi.dho/fni/hhu/kqf` | correio (posts) |
| `CloudSave.Download` / `Delete` | `qu.qr`, `qh.hhm/hhn` | chaves `snapshot` e `itemRestoration` (§3.5) |
| `BLog.InsertLogV2` (GameLog) | **`qh.hhr` 0xD24D30** (e `lcp`, `nuz`) | logs com `Param{msg, data, server_ver}` (§3.4) |
| `RTNotification.Connect` | `qj.hij` 0xD2A730 | notificações em tempo real |

Não encontrei chamadas de **ranking/leaderboard** (URank, nem `SteamUserStats` de leaderboard), de **cupom** (Coupon),
nem de `ISteamRemoteStorage`.

### 3.3 Funções de servidor (`inventoryV2`)

`InventoryFunction.ktl` = `"inventoryV2"` e `LogFunction` = `"insertLog"`. As ações e parâmetros vêm dos
`get_ActionType`/`GetParam` de cada classe (`dump.cs:52600-55668`):

| Ação | Parâmetros enviados | O que indica |
|---|---|---|
| `initV2` | `steamId`, `stageKey` | devolve **itens do servidor** (`InventoryItemData{itemKey(uniqueKey), itemId, count}`), marketData, steamSlots, dlc, pendingItems, **lastClearStageKey**, peste/poluição |
| `mergeInventory` | `steamId` | itens, `added`, `rekeyed{from,to}` (o servidor renumera itens) |
| `processBoxV3` | `stageKey`, `getitemkey[]`, `useItemKeyList[]`, `addDlcNumber` | abertura de caixa passa pelo servidor, que devolve `added[]` com IDs |
| `consumeV2` | `items`, `useBoxKeyList`, **`cubeLev`**, `contentType` | consumo de materiais (encantamento, cubo…) |
| `exchangeV2` | `resultItemId`, `items`, `useBoxKeyList` | síntese e craft |
| `corrosionV2` | `items`, `useBoxKeyList`, **`cubeLev`** | corrosão |
| `addItem` / `addItems` | `itemId` / `itemIdList` | — |
| `receivePostItem(All)` | `postType`, `postIndate` | resgatar correio |
| `uploadtosteamV2` / `downloadtosteam` | `steamId`, `itemKey`, `slot`, `registerId`, `count` / `steamItemId`, `receiveId` | Trade Ship ↔ Steam Market |
| `processPending`, `verifyDLC`, `stageClear(stageKey)`, `echo` | — | — |
| `insertLog` + `gameMarketItemRegister/Remove`, `gameMailSync(itemList)`, `gameMailReceiveClick`, `gameAuth`, `gameEnter` | `logType`, `logLevel`, `tn`, `steamId` | trilha de auditoria |

### 3.4 Logs enviados ao GameLog (`qh.hhr` → `BLog.InsertLogV2`)

| logType / msg | data | Quando | Onde |
|---|---|---|---|
| `DataSnap` | `{"SnapShot": JSON do tl comprimido}` | todo boot (`qu.hlq` 0xD311C2) e a cada **28.800 s** de jogo (`qh.Update` 0xD22550, `tg.bfnv = 28800.0f` em `tg..cctor` 0x9308AC), só se o load deu certo | `qh.SnapShot` 0xD223B0 → `tl.iut` 0x937360 → `CompressAndSendSnapShotAsync` 0xD1DB60 |
| `CloudSaveDelete` / `ItemRestorationBackup` | `{"compressedPlayerSave": PlayerSaveData **inteiro** comprimido}` | quando há `itemRestoration` no CloudSave | `qu.qr` 0xD2F33E-0xD2F4AE |
| `AnomalyItem` / `RemoveOnlyServerHaveBackend` | `{"deletedItemKeys": …}` | itens locais que o servidor não tem, removidos | `qv.hme` 0xD370E0 |
| `TemperedItem` / `TamperedItemIdDetected` | `{"mismatches": "{0}:{1}:{2}->{3}"…}` | `ItemKey` local diferente do servidor | `qv.hly` 0xD36310 |
| `SkinLog` / `infodata` | `{user: steamId, skinKey}` | herói carregado com skin paga **não possuída**; a skin volta para a padrão (`SkinKey.eix`) | `wj..ctor` 0x9CCF90 (log em 0x9CD6A8; condição: `bs.egz` 0x886740 == false) |
| `RemoveAllItemWhenResetData` / `RemovedAllItem` | `removedItems` | reset de dados | `yv.<DeleteAllItemsExceptSkinItem>` 0xA58790 |
| `SkinPurchase*`, `Receipt` (exchange) | — | compras de skin, recibos de síntese | `bq.egs`, `xq.ktb` |

**Conteúdo do DataSnap** (`tl`, `dump.cs:40885`; `tl.iut` copia os offsets de `PlayerSaveData`): `commonSaveData`,
`BoxBucketUseBoxList`, `BoxBucketGetBoxList`, `currenySaveDatas`, `heroSaveDatas`, `attributeSaveDatas`,
`PetSaveData`, `RuneSaveData`, `inventorySaveDatas`, `stashSaveDatas`, `remakeTradingStashSaveDatas`,
`cubeRecipeSaveDatas`, `cubeSaveLevelData` e `itemSaveDatas`. Ficam de fora só `settingSaveData`, correio,
pendências e `aggregateSaveDatas`.

### 3.5 O save sobe para o servidor? (cloud save)

- **O arquivo `.es3` em si:** o código do jogo não o envia (não há uso de `ISteamRemoteStorage`). O texto
  `Notice_Delete_OnlyInventoryItem_PopUpText4` pede "Please keep Steam Cloud Save enabled so that your save file
  stays up to date.", o que indica **Steam Auto-Cloud** (sincronização feita pelo cliente Steam, com configuração
  fora do código). **Inferência**: não dá para verificar sem ver a configuração do app.
- **O conteúdo do save sobe, sim:** DataSnap em todo boot e a cada 8 h, e o PlayerSaveData completo no fluxo de
  `itemRestoration` (§3.4).
- **CloudSave do TheBackend, lido no boot** (`qu.qr`):
  - `snapshot` (0xD2E350): o callback `qh.qb.hgx` 0xD204A0 faz `JsonConvert.DeserializeObject<tl>` e depois
    `tl.iuu(bde.bihb)` 0x937740, **copiando de volta** para o PlayerSaveData local common, moedas, heróis, pets,
    runas, inventário, baú, itens e cubo. Em seguida `CloudSave.Delete("snapshot")` (0xD2E529). É uma restauração
    empurrada pelo servidor. Inferência: só existe quando o estúdio coloca um snapshot para a conta.
  - `itemRestoration` (0xD2F11F): `ItemRestorationCloudData.restorationItems[]` com `UniqueId` e `EnchantCount`/
    `EnchantData`, aplicado por `yi.kwf`, com salvaguarda "[ItemRestoration] ItemKey mismatch … → 복구 스킵"
    (divergência de ItemKey, restauração pulada; `wh.vc.va.jkq`). A estrutura local pendente é
    `pendingItemRestorationList` (`ItemRestorationPendingSaveData`).

### 3.6 Inventário no servidor e o que muda com o sumiço de `Notice_Delete_OnlyInventoryItem`

- **O servidor é a autoridade:** `ServerItemEntry{ItemKey, UniqueId, Quantity}` (`dump.cs`, TypeDefIndex 1178).
  `qv.hmd` 0xD36FF0 → `qv.<SynchronizeInventoryByBackendData>d__10.MoveNext` 0x8B3550 faz:
  1. `hma`: ids locais, exceto os do Trade Ship.
  2. Conjunto de `UniqueId` do servidor.
  3. `hly` 0xD36310: `ItemKey` divergente vira log `TemperedItem`.
  4. `hlx` 0xD362A0: `localIds.Except(serverIds)`, mais os divergentes.
  5. **`hme` 0xD370E0**: `TryRemove` de cada um ("[MainController] TryRemove | Result…"), toast
     `Toast_TradeShip_SoldItem` (lido de `tj+0x590`) e log `AnomalyItem`.
  6. `wh.vc.jmi`, `wh.vc.jly` e `wh.vi.jol/jom`: atualizam o cache de itens e o correio. Que os itens que só o
     servidor tem **voltam pelo correio** é **inferência**: vem da string nova `Notice_Create_OnlyServerItem`
     (research/1.2.8), mas essa chave, `Notice_CreateMailItem` e `Popup_Notice_Recovery` **não aparecem nos literais
     do código**. É provável que cheguem como texto de post enviado pelo servidor.

  É chamado após login/merge (`yi.dva/iza/kbb/kra/kxu`) e em `zc.<HandleBackendInventoryUpdate>d__46`. A UI também
  limpa slots sem cache: `InventorySlot.mkn` 0xAEB4C0 ("아이템 캐쉬가 없습니다. 서버 요청으로 삭제된 것 같습니다…"
  = o item não está no cache; parece ter sido apagado a pedido do servidor).
- **Comparação de strings** (`data/strings_en.json` × `research/1.2.8/strings_en.json`):

  | Chave | Situação |
  |---|---|
  | `Notice_Delete_OnlyInventoryItem` ("Items not held on the server have been cleaned up.") | só existe na 1.00.17 |
  | `Notice_Create_OnlyServerItem` ("Items have been recovered from the server. Please check your mailbox.") | só existe na 1.2.8 |
  | `…_PopUpText1..6`, `…_Why`, `…_Delete` | existem nas duas versões; nenhum aparece nos literais decodificados do código |

  Os textos PopUpText1..3 dizem: "TBH is a server-based game where all items can be traded on the Steam Market",
  "When server items and local save files do not match due to errors or manipulation below, automatic sync is
  triggered", e na causa 3: "Items created through abnormal means".
- **O que isso indica:** a limpeza de itens que só existem no save **não saiu**. Ela ficou **mais silenciosa para o
  jogador** (toast genérico sobre o trade ship em vez do aviso explícito) e passou a ser **logada no servidor**
  (`AnomalyItem`, com as chaves apagadas). Também apareceu o caminho inverso: itens que só o servidor tem voltam pelo
  correio. Isso é inferência a partir das strings (ver o passo 6 acima). Os textos detalhados podem estar em prefab
  de UI ou vir do servidor. **Inferência**: não verifiquei assets.

### 3.7 Rankings, correio, cupons, ServerIssueReward e bloqueios

- **Rankings/leaderboards**: nada encontrado. Existem só **estatísticas e conquistas Steam** (`ze`):
  `play_time_minutes`, `max_hero_level`, `cube_level`, `highest_gear_grade`, `max_stage_cleared`,
  `total_gold_earned`, `divine_items_found`, `session_count` e outras. São enviadas por `StatData.Set`/`StoreStats`,
  com os deltas de sessão gravados em `ze.lbk` 0xA6C9C0. Ficam no servidor da Valve.
- **Correio/posts**: `BUpgradePost.GetPostList` (`xi`), `receivePostItem(All)`, `gameMailSync`/`gameMailReceiveClick`.
  No save: `backendPostList` e `mailSaveDatas` (`SerializedMailData{Keys, MailData}`). As compras do Steam Market
  chegam pelo correio (`UI_TradingStash_Notice2`).
- **Cupons**: nenhuma API de cupom referenciada.
- **ServerIssueReward1..7**: textos de compensação ("Outage compensation will be sent daily by mail for 7 days"),
  entregues via posts.
- **Bloqueios comandados pelo servidor**:
  - Conta: a resposta do TheBackend "Forbidden blocked user" é tratada em `qu.qr` 0xD2EAB9 e mostra `PopUp_BlockedUser`
    ("Suspicious activity was detected, so your account has been blocked.").
  - Trade Ship: o erro **9002** (`cmp esi, 0x232A` em `yi.kye` 0xA53930) mostra `PopUp_BlockedUser_TradeShip`.

### 3.8 CheatReporter (`pc`) e telemetria de anomalias (`ox`)

`pc.gtj` 0xD05020 → `pc.gtk` 0xD050A0 → `pc.gtp` 0xD05850 faz um POST em JSON. O payload (`pc.Payload`,
TypeDefIndex 614) tem `auth` (derivado da mesma keystore `bdf`), `ticket` (ticket de sessão Steam em hex), `appid`
"3678970", `steamId`, `ruleId` (nome do enum), `param[]`, `gameVersion`, `playtime` (**estatística Steam
`play_time_minutes`**, não o `playTime` do save), `maxStage` (0) e `currentStage` (`wh.wb.jxj`).

Controle de repetição: cooldown de **30 s** por tipo (`bedk=30`; `Dictionary<string,float>` com
`realtimeSinceStartup`); `ox.gsp` 0xCFFD30 só deixa passar **um por tipo por sessão** (`HashSet<EReportType>`).

| EReportType (`dump.cs:27762`) | Gatilho real | Limite | `param` | Onde |
|---|---|---|---|---|
| 0–4 `ACTk_Speed/Time/Memory/Inject/Disabled` | detectores ACTk (§4) | — | `[""]` ou lista de detectores desligados | `oy` |
| 5/6 `Box_*_Rate`, 7/8 `Box_*_Volume` | contagem de caixas (`ox.gsq` 0xCFFDF0, chamado em `StageManager.si`) | cerca de **≥ 25 (ou 15) em 300 s** e **> 120 em 1800 s** (`ox.gso` 0xCFFBA0 grava 25/120/15/120; a correspondência exata tipo↔limite não foi confirmada) | contagem | `ox.gsx` 0xD009C0 |
| 9–13 `Trade_*` | **sem chamador ativo** (os emissores `gsu`/`mna` não têm xref) | — | — | — |
| 14–18 `Grade_Arcana…Cosmic` | drops de grau ≥ 5 (ARCANA) numa janela de **3600 s** | mais de 3 (Arcana, Beyond) ou mais de 2 (Celestial, Divine, Cosmic) | contagem | `ox.gsv` 0xD00490 → `gsw` 0xD00760 |
| 19/20 `ItemLevel_50/80` | drop com item level ≥ 50 e playtime Steam < 600 min, ou ≥ 80 e < 3000 min | — | ItemKey | `ox.gsv` (em `wh.ut.jen/jeo/mgt`, `wh.vi.vg`, `StageBox.OpenBoxAsync`) |
| 21/22 `Level_50/80` | **no load** (`wh.uw.jex` 0x959C30 → `ox.gst` 0xD00150 para cada herói) e em cada level-up (`wj.kjt`) | nível ≥ 50 com playtime < 600, ou ≥ 80 com < 3000 | nível | `ox.gst` |
| 23 `Gold_Massive` | todo ganho de ouro (`wh.um.jdu` 0x94F600 → `ox.gsr(saldo)` 0xCFFF70) | **saldo > 100.000.000** e playtime < 600 | saldo da moeda 100001 | `ox.gsr` |
| 24 `Save_Tampered` | HMAC inválido no load | — | `[]` | `bde.nof` 0xB86DA1 |

Esses relatórios **não fazem nada no cliente** (sem popup, sem punição local). Só alimentam o servidor do estúdio.

---

## 4. ACTk (Anti-Cheat Toolkit)

| Item | Uso na 1.2.8 | Evidência |
|---|---|---|
| Início | `oy.gsy` 0xD029E0 (chamado no boot, `qu.qr` 0xD2D2EE): `TimeCheatingDetector.StartDetection(oy.gsz)`, `SpeedHackDetector.StartDetection(oy.gta)`, `ObscuredCheatingDetector.StartDetection(oy.gtb)` | chamadas 0xD02AD2 / 0xD02AFF / 0xD02B2C |
| TimeCheating | se `CheckResult == CheatDetected (15)`: `pc.gtj(ACTk_Time)` e popup `DetectAntiCheat` | `oy.gsz` 0xD02B50; enum em `dump.cs:1228049` |
| SpeedHack | `pc.gtk(ACTk_Speed)` e popup | `oy.gta` 0xD02CA0 |
| ObscuredCheating (memória) | `pc.gtk(ACTk_Memory=2)` e popup | `oy.gtb` 0xD02E20 |
| Watchdog | a cada **30 s** (`becs=30`) `oy.gte` lista os detectores ausentes ou desativados ("ObscuredCheating", "SpeedHack", "TimeCheating"); se houver algum: `pc.gtk(ACTk_Disabled=4, nomes)` e popup | `oy.<WatchdogLoop>d__8.MoveNext` 0xCF6870 |
| Popup `DetectAntiCheat` (4) | `bct.myy(4)` → `bct.myz` 0xB49A70 → `bct.<ForceGameQuitWhenAntiCheat>d__33`: **fecha o jogo** | `EPopupType` em `dump.cs:72385` |
| Não usados pelo jogo | InjectionDetector (o enum `ACTk_Inject` existe, mas não há `StartDetection`), WallHack, CodeHashGenerator/Genuine e ObscuredPrefs/ObscuredFile para o save | xref de APIs ACTk a partir de `Assembly-CSharp`; os hits restantes são ICF de construtores genéricos |
| Tipos Obscured | cerca de 171 `ObscuredInt`, 106 `ObscuredString`, 36 `ObscuredBool`, 30 `ObscuredFloat`, 17 `ObscuredULong`, 8 `ObscuredLong`, 7 `ObscuredDateTime` em campos | ficam nos DTOs de requisição/resultado do servidor e nos caches de runtime: ouro (`wh.um.bgic` `ObscuredLong`), encantamento em memória (`wh.vc.ItemEnchantData`), estágio (`wh.StageCache`), cache de itens (`wh.vc.va`), herói (`wj`, nível em +0xCC) |
| No arquivo de save | JSON comum: as classes `TaskbarHero.EasySaveData/*`, `PlayerSaveData` e `AccountSaveData` **não têm** campos Obscured. A exceção é `lastExitSteamUnixSecEncrypted/Key` (codificação `ObscuredLong` feita à mão) | grep em `game_src` |

**O que pode denunciar um save editado:** o ACTk, **nada diretamente**. Ele observa tempo, velocidade e memória em
execução. Um save editado é detectado por: (a) HMAC/SteamId no load, (b) sincronização de inventário com o servidor,
(c) `SkinLog`, (d) a telemetria do `ox` (`Level_*` no load, `Gold_Massive` ao ganhar ouro) e (e) o DataSnap, que
não detecta nada sozinho, mas expõe todo o estado ao estúdio. Observação: alterar valores em memória (trainer ou
injeção) é outra conversa, porque ObscuredCheating e SpeedHack **estão ativos** e reportam, avisam e fecham o jogo.
Isso fica fora do escopo do editor.

---

## 5. Avaliação de risco

### 5.1 Local × visível ao servidor

| Área do save | Onde vive a verdade | Visível ao servidor | Como |
|---|---|---|---|
| `AccountSaveData` (`ownerSteamId`, `version`, …) + `SystemInfo` | local | parcial | `steamId` vai em login e relatórios; HMAC ruim gera `Save_Tampered` |
| `itemSaveDatas`: **existência** (`UniqueId`/`ItemKey`/quantidade) | **servidor** | **sim, é validado** | `initV2`/`mergeInventory`, sync (§3.6), DataSnap |
| `itemSaveDatas`: **EnchantData/EnchantCount/*AppliedTotalCount** | local (com possível override do servidor via `itemRestoration`) | sim (passivo) | DataSnap; materiais gastos passam por `consumeV2` com TxId (`pendingEnchantList`) |
| `currenySaveDatas` (ouro 100001) | local | sim (passivo), mais `Gold_Massive` | DataSnap, CheatReporter; a estatística Steam `total_gold_earned` é somada por evento |
| `heroSaveDatas` (nível, EXP, AbilityPoint, skills, `EquippedSkinKey`) | local | sim | DataSnap; `Level_50/80` no load; `SkinLog`; estatística Steam `max_hero_level` |
| `cubeSaveLevelData` (nível, EXP) | local | **sim (ativo)** | **`cubeLev` vai em `consumeV2` e `corrosionV2`**; DataSnap; estatística Steam `cube_level` |
| `PetSaveData` (`IsUnlock`) | local | sim (passivo) | DataSnap. Pets **DLC** (6001–6003, `UnlockCondition=DLC`, app 4427390) dependem de `DLCManager` (`DlcData.IsSubscribed`, 0xD1D800) e existe `verifyDLC` no servidor |
| `RuneSaveData` | local | sim (passivo) | DataSnap |
| `commonSaveData` (estágios, backups, tutorial…) | local, com espelho no servidor | sim | `stageClear`/`initV2` (`lastClearStageKey`), `processBoxV3(stageKey)`, DataSnap |
| `BoxBucket*`, `pendingEnchantList`, `pendingExchange`, `AlchemyPending*`, `pendingItemRestorationList`, `backendPostList`, `mailSaveDatas`, `remakeTradingStashSaveDatas` | espelho de transações do servidor | sim | são IDs e recibos de transações do servidor |
| `settingSaveData` | local | não | fica fora do DataSnap |

### 5.2 O que o jogo faz quando detecta algo

| Gatilho | Reação local | Reação remota |
|---|---|---|
| HMAC inválido | popup, restauração do `.bak` rotativo (ou recusa em salvar) | relatório `Save_Tampered` |
| SystemInfo ausente | restauração do `.bak` | — |
| `ownerSteamId` ≠ Steam logado | popup, restauração do `.bak` | — |
| Item local que o servidor não tem, ou `ItemKey` divergente | item removido e toast genérico | log `AnomalyItem` / `TemperedItem` |
| Skin equipada não possuída | volta para a skin padrão | log `SkinLog` |
| Herói ≥ 50/80, ouro > 100M, drops e caixas fora do normal | nada | relatórios `Level_*`, `Gold_Massive`, `ItemLevel_*`, `Grade_*`, `Box_*` (dependem da estatística Steam `play_time_minutes`) |
| ACTk (tempo, velocidade, memória, detector desligado) | popup e **encerramento forçado** | relatório `ACTk_*` |
| Decisão do estúdio (a partir dos logs; **inferência**) | — | bloqueio de conta (`PopUp_BlockedUser`), bloqueio do Trade Ship (erro 9002), CloudSave `snapshot` sobrescrevendo o progresso, `itemRestoration` |

### 5.3 Matriz de risco por funcionalidade do editor

Considera o código atual de `server.py`. Risco = chance de o jogo rejeitar ou reverter × exposição no servidor ×
impacto em economia real.

| Funcionalidade (endpoint) | Campos | Rejeição/reversão local | Exposição no servidor | Risco | Por quê |
|---|---|---|---|---|---|
| **Encantamento** (`/api/set_enchant`, `/api/auto_build`) | `EnchantData`, `EnchantCount`, `*AppliedTotalCount` de itens **existentes** | nenhuma, se o HMAC estiver ok (o sync compara só `UniqueId`/`ItemKey`) | DataSnap a cada boot e a cada 8 h; `itemRestoration` pode sobrescrever | **baixo a médio** | valores dentro de `StatModInfoData` não se distinguem de encantamentos legítimos; valores fora de faixa aparecem no DataSnap. Itens encantados **não podem ir ao Market** ("Decorated / Engraved / Inscribed items cannot be traded."), então não há efeito econômico |
| **Skills** (`/api/set_skills`) | `equippedSKillKey` | nenhuma | DataSnap | **baixo** | escolha de loadout, reversível no jogo |
| **Herói** (`/api/set_hero`) | `HeroLevel` (editor aceita 1–1000), `HeroExp`, `AbilityPoint` | nenhuma conhecida | DataSnap; **`Level_50/80` no próximo load** se a estatística Steam `play_time_minutes` for < 600/3000 | **médio** | o máximo real é **101** (`LevelInfoData` tem EXP até 100→101; o level-up consulta `LevelInfoData[nível]` via `bdc.nna` 0xB6ED60; o save atual tem 6 heróis em 101). Níveis acima de 101 são estados impossíveis |
| **Ouro** (`/api/set_currency`, até 10^13) | `currenySaveDatas[100001].Quantity` | nenhuma | DataSnap; **`Gold_Massive`** no primeiro ganho de ouro se o saldo > 100M e o playtime Steam < 600 min | **médio** | não é inventário do servidor, mas a diferença entre saldo e `total_gold_earned` (Steam) fica visível. Inferência |
| **Cubo** (`/api/set_cube`, nível até 999) | `cubeSaveLevelData.Level/Exp` | nenhuma conhecida | **ativa**: `cubeLev` vai em toda requisição `consumeV2`/`corrosionV2`; DataSnap; estatística Steam `cube_level` | **alto** | o servidor recebe o nível que o cliente declara; o **nível 10 libera o Trade Ship (Steam Market)** (`Toast_CannotUseTradingStashLowCubeLevel`); o máximo real é **100** (`CubeLevelInfoData`, sentinela 999.999.999 no nível 100) |
| **Pets** (`/api/set_pet`, "desbloquear todos") | `PetSaveData.IsUnlock/IsViewed` | não rastreado | DataSnap; `verifyDLC` | pets 1001–1005: **baixo**; pets **6001–6003: alto e fora de escopo** | 6001–6003 exigem o DLC 4427390; desbloquear pelo editor contorna um direito de DLC |
| **Runas** (`/api/max_runes`) | `RuneSaveData.Level` = `MaxLevel` | nenhuma conhecida | DataSnap | **médio a baixo** | ignora pré-requisitos da árvore (`PrevNodeRequiredLevel`) e custos; runas de capacidade (`MaxInventorySlot`, `UnlockStashPageCount`) mudam inventário e baú, que interagem com o inventário do servidor. Inferência |
| *Fora do editor, para registro* — criar item, mudar `ItemKey`/`UniqueId`/`RegisterID`/`IsBlocked` | — | **o item é apagado no próximo sync** | `AnomalyItem`/`TemperedItem` | **muito alto** | autoridade do servidor e economia do Steam Market |
| *Fora do editor* — `EquippedSkinKey` | — | revertido | `SkinLog` | alto | skins são itens pagos do Steam Inventory |
| *Fora do editor* — estágios, `BoxBucket*`, pendências, correio | — | inconsistência com o servidor | ativa | alto | são transações do servidor |

### 5.4 Recomendações para o editor

1. **Manter o HMAC sempre correto.** O `roundtrip` precisa passar antes de qualquer gravação real. O custo de errar
   agora é maior: o estado volta ao `.bak` rotativo **e** o relatório `Save_Tampered` é enviado.
2. **Travar faixas com base nas tabelas da 1.2.8**:

   | Campo | Faixa |
   |---|---|
   | `HeroLevel` | 1 a 101 (max(`LevelInfoData.Level`) + 1) |
   | `HeroExp` | até `ExpForLevelUp` do nível |
   | `cubeSaveLevelData.Level` | 1 a 100 |
   | `cubeSaveLevelData.Exp` | até `ExpForLevelUp` do nível |
   | Runas | `MaxLevel` respeitando `PrevNodeRequiredLevel` |
   | Encantamentos | faixa e passo de `StatModInfoData`, tier conforme o grau |
3. **Avisos na UI:**
   - "Tudo o que você editar é enviado ao servidor do jogo (DataSnap) na próxima abertura."
   - Ouro > 100.000.000: aviso específico sobre `Gold_Massive`.
   - Herói ≥ 50/80: aviso de `Level_*`, que depende da estatística Steam de horas jogadas.
   - Cubo: avisar que o nível é enviado ao servidor e libera o Trade Ship no 10.
4. **Pets DLC (6001–6003):** tirar do "desbloquear todos" e não permitir desbloqueio individual (mostrar como
   "DLC — gerenciado pela Steam").
5. **Nunca tocar em:** `ItemKey`, `UniqueId`, `PrevUniqueId`, `RegisterID`, `IsBlocked`, `IsChaotic`,
   `ItemGetSourceType`, `EquippedSkinKey`, `BoxBucket*`, `pendingEnchantList`, `pendingExchange`, `AlchemyPending*`,
   `pendingItemRestorationList`, `backendPostList`, `mailSaveDatas`, `remakeTradingStashSaveDatas`, estágios
   (`maxCompletedStage`, `lastClearedStageKey`…), `lastExitSteamUnixSec*`, `sessionCounter`,
   `forceApplyServerData`, `ownerSteamId` e `playerId`. Isso já vale pelo invariante 2 do CLAUDE.md (editar in-place);
   aqui fica o motivo.
6. **Bloquear a edição de itens com transação pendente.** Se `pendingEnchantList` ou `pendingItemRestorationList`
   citar o `UniqueId` do item, não editar. Se `pendingExchange` não for nulo, recusar e pedir para abrir o jogo uma
   vez antes.
7. **Não criar nem duplicar itens**, mesmo sem intenção: o `auto_build` só pode mexer em encantamentos de itens que
   já existem. Hoje já é assim.
8. **Documentar o rollback para o usuário:** o `.es3.bak` do editor é o ponto de volta; os `.bak` rotativos do jogo
   são sobrescritos em poucos saves; `_backup_` e `daily` são manuais.
9. **Checar antes de gravar:** jogo fechado (`tbh_paths.game_running`), HMAC OK, `nod` (arquivo ≥ 64 bytes) e releitura
   após a escrita, no mesmo espírito do `noa`.

### 5.5 Observações do histórico de saves (neutras, para contexto)

`save_lab` nas cópias:

| Snapshot | Heróis | Ouro | Cubo | playTime do save |
|---|---|---|---|---|
| 1.00.11 (BackendBackUp, 2026-06-14) | 34–72 | 13.094.739.558 | 25 | 124 h |
| 1.01.05 (2026-08-16) | todos em **101** | 8,06e9 | 94 | 511 h |
| 1.2.3 (2026-09-14) | — | 8,98e9 | — | — |
| 1.2.8 (2026-09-22) | — | 2,16e8 | — | — |
| 1.2.8 atual | 101 | 37.681.109 | **100** (Exp 1.000.000.000, acima da sentinela 999.999.999) | 658 h |

- Entre 1.2.3 (09-14) e 1.2.8 (09-22), numa **única sessão** (`sessionCounter` 89 → 90, cerca de 20 h), saíram 119
  itens, entraram 40, e o ouro caiu de 8,98e9 para 2,16e8. A causa (gasto legítimo, ajuste do update, sync ou
  restauração pelo servidor) **não foi determinada**.
- Pets 6001–6003 aparecem desbloqueados desde 1.00.11.

### 5.6 Limites deste estudo

- Análise só estática: não observei tráfego de rede nem o jogo rodando.
- Não sei se o servidor **valida** `cubeLev` ou os valores do DataSnap. Sei apenas que os **recebe**.
- A configuração de Steam Auto-Cloud e o valor atual de `play_time_minutes` não são verificáveis daqui.
- Não rastreei completamente o uso de `forceApplyServerData`/`sessionCounter`, nem se o jogo volta a travar pets DLC
  não possuídos no load.
- Sem dump da 1.00.17 local, as diferenças de comportamento de save vêm só do `docs/SAVE_PORTING.md` e das strings.

---

## 6. Correções da verificação adversarial (18 confirmados, 5 parciais, 0 refutados)

Verificador independente (vereditos em `~/tbh_re/scratch/verify_integrity_backend2/verdicts.json`):

- **Tempo de jogo dos relatórios (IB-8):** `play_time_minutes` é gravado pelo próprio jogo a partir do
  save (`xb.kod(15, 0, account.playTime/60)` a cada save; `ze.lbl` → `StatData.Set`/`StoreStats` a cada
  autosave e ao fechar). No save atual: 39.498 min → `Level_*`, `Gold_Massive` e `ItemLevel_*` não
  disparam para esta conta. `Save_Tampered` e `ACTk_*` não passam pelo filtro "1 por sessão" (só o
  cooldown de 30 s). Consequência: o editor nunca deve alterar `playTime` nem `aggregateSaveDatas`.
- **Estatísticas Steam a cada autosave:** `cube_level`, `max_hero_level` e outras saem do estado
  carregado a cada 180 s e ao fechar — cubo 999 ou herói 1000 viram estatística Steam impossível em até
  3 min.
- **Pets DLC (IB-12):** `verifyDLC` não tem relação com pets. `PetManager.lro` só consulta a assinatura
  Steam para pet **travado** e mantém `IsUnlock=true` sem conferir: o jogo nunca volta a travar, e o
  desbloqueio pelo editor contorna o DLC.
- **Sincronização de inventário (IB-15):** compara só `UniqueId → ItemKey` (nem `Quantity` nem
  encantamentos). Roda no boot e depois de cada encantamento no jogo (`TryEnchantAsync` → `yi.kxu` →
  `qv.hmd`). Dos chamadores citados no §3.6, `yi.dva/iza/kbb/kra` são clones sem chamada.
- **Escrita (IB-17):** o "save logo após o boot" (`bde.nnq`) só acontece com `ownerSteamId` vazio; os
  "~50 chamadores" de `nnp` são 49 pontos em 45 métodos, muitos em clones sem chamador.
- **JSON inválido:** cai no bloco de exceção de `nof` (0xB86E84) e é restaurado do `.bak` sem
  `Save_Tampered` e sem popup — a edição some calada.
- **Bloqueio de conta:** HTTP 403 "Forbidden blocked user" interrompe o boot (o jogo não carrega). As
  strings `PopUp_BlockedUser*` são novas desde a 1.00.17.
- **Cubo na matriz:** em `consumeV2` o nível vai sob a chave `"cubeLev "` (com espaço); não está provado
  que o servidor a use.

## Apêndice A — Como reproduzir

Scripts em `C:/Users/andre/tbh_re/scratch/integrity_backend/` (só leem as cópias em `~/tbh_re/1.2.8/`):

| Script | O que faz |
|---|---|
| `build_maps.py` | `script.json` → `maps.pkl` |
| `strblob.py` | decodifica o blob de strings → `strgetters.pkl`/`.tsv` |
| `disasm.py <RVA\|Nome$$metodo>` | disassembly anotado (métodos, metadata, strings decodificadas) |
| `dumpclass.py <classe> <saida>` | todos os métodos de uma classe (`bde.asm`, `ox.asm`, `pc.asm`, `oy.asm`, `yi.asm`…) |
| `xref.py <RVA\|nome>` | quem chama (índice de `call`/`jmp` rel32) |
| `ripref.py '<regex de metadata>'` | quem referencia um `MethodInfo`/`TypeInfo` (delegates) |
| `strusers.py '<regex>'` | quais métodos usam uma string decodificada |
| `backend_api.py`, `acs_types.py` | inventário de APIs TheBackend, Steam e ACTk usadas por `Assembly-CSharp` |

Comandos de save usados (todos em cópias):

```
python tools/save_lab.py info <cada arquivo de ~/tbh_re/saves/20260929_013650>
python tools/save_lab.py roundtrip ~/tbh_re/saves/20260929_013650/SaveFile_Live.es3 --out ~/tbh_re/scratch/integrity_backend/roundtrip_SaveFile_Live.es3
python tools/save_lab.py dump ~/tbh_re/saves/20260929_013650/SaveFile_Live.es3 --out ~/tbh_re/scratch/integrity_backend/live_128
python tools/save_lab.py schema …/SaveFile_Live_BackendBackUp.es3 --vs …/SaveFile_Live.es3
```
