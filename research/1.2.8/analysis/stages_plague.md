# Mapas, estágios e Plaguelands — Taskbar Hero 1.2.8

Compilado pela sessão principal a partir do resultado estruturado do agente `research:stages_plague`
(o harness não deixou o subagente gravar o arquivo). Evidências = tabelas de `research/1.2.8/tables`,
`dump.cs`/RVAs da cópia do `GameAssembly.dll` e os 24 snapshots em `~/tbh_re/saves/20260929_013650/`.
Tabela linha a linha dos 189 estágios: [stages_table.md](stages_table.md). Ferramentas do agente:
`~/tbh_re/scratch/stages_plague/` (`stage_model.py` com o validador, `test_edits.py`, `tbhdis.py`, `xref.py`).

## 0. Resumo

- **189 estágios.** Os 120 NORMAL/ACTBOSS (4 dificuldades × 3 atos × 10) **já existiam** — a
  `StageInfoData` só não tinha sido extraída. **Novos da 1.2.x:** 60 **PLAGUE** (Plaguelands de
  Pesadelo/Inferno/Tormento, atos 21–23, `StageNo` 1–20 = intensidade) e 9 **CONTAMINACTBOSS** (chaves
  `d119/d219/d319`). Não entrou mapa nem ato novo na progressão normal.
- **O servidor manda no progresso.** O jogo envia `lastClearedStageKey` no `InventoryInitRequest` e
  sobrescreve os campos locais com o valor do servidor (no init e a cada `StageClear`). Contaminação,
  intensidade liberada, cooldown e desbloqueio de dificuldade existem **só no servidor**.
- **Itens de praga** (`CONTENTTYPE=PLAGUE`): Plague Fruit 150103–150107, Contaminated Soulstone
  190102–190104 e 81 caixas. Nenhum apareceu nos 24 snapshots. (`IsSteamItem` é `True` em **todas**
  as 6237 linhas de `ItemInfoData` — não serve de critério.)
- **Recomendação para o editor:** progresso **somente leitura**; no máximo um "reparar posição"
  validado e o reset de `lastPlayedPlagueIntensity`.

## 1. Estrutura (StageInfoData)

| Tipo | Qtde | Chave | Observações |
|---|---|---|---|
| NORMAL | 108 | `D A NN` (D 1 Normal, 2 Pesadelo, 3 Inferno, 4 Tormento; A ato 1–3; NN 01–09) | cadeia única `NextStageKey` 1101 → 4310 (120 estágios), chave estritamente crescente — o jogo compara progresso numericamente |
| ACTBOSS | 12 | `D A 10` | chefe do ato |
| CONTAMINACTBOSS (novo) | 9 | `D A 19` (só D 2–4) | `StageNo` 10, nível = ACTBOSS do ato; `PrevStageKey` = o ACTBOSS; entrada custa 1 Contaminated Soulstone (190102/190103/190104); sem `Next` |
| PLAGUE (novo) | 60 | `201000 + (D)·100 + i` → 2012NN / 2013NN / 2014NN | Act 21/22/23 = Pesadelo/Inferno/Tormento; `StageNo` 1–20 = intensidade; `StageLevel` fixo 40/65/90 |

Nomes (iguais em todas as dificuldades): Ato 1 — Pasture, Shadow Meadow, Wasteland, Eerie Canyon,
Burning Village Entrance, Rumstreet Square, City Outskirts, Cemetery, Cursed Land, **Throne of
Darkness** (chefe). Ato 2 — Oasis Road … Pharaoh's Crypt, **Pharaoh's Underchannel**. Ato 3 — Snowbound
Outpost … Core of the Abyss, **Hell Command Chamber**. Contaminados: Contaminated Throne / Underchannel /
Command Chamber. Praga: Nightmare / Hell / Torment Plaguelands.

Níveis: Normal 1–32, Pesadelo 33–52, Inferno 53–77, Tormento 78–95. `StageLevelInfoData` (níveis
1–170) não mostra mudança; a praga reusa 40/65/90. `PlagueIntensityInfoData` (nova) = 20 intensidades ×
3 buffs ADDITIVE de **monstro** (MovementSpeed +600→+2900, MaxHp +1500→+405000, AttackDamage +50→+5000).

Evidência de "novo": `data/strings_en.json` (1.00.17) já tinha `StageName_1101…1310` e
`Difficulty_TORMENT`, e o save 1.00.11 já tinha `maxCompletedStage=4310`; as 12 `StageName_*` de
praga/contaminados, os enums `EStageType.PLAGUE=2`/`CONTAMINACTBOSS=3` e os monstros
`MonsterName_2010001–2010004` são novos; o save só ganha os campos de praga na 1.2.3.

## 2. Campos de progresso no save (`commonSaveData`)

| Campo | Significado (desmontagem) | Editabilidade |
|---|---|---|
| `maxCompletedStage` | **maior estágio DESBLOQUEADO** = `Next(lastClearedStageKey)` (ou o próprio, sem Next). Com `lastCleared > 0` o valor do save é ignorado e recalculado; o `PreSave` regrava o recalculado (`wh.wb.kab` 0x9B7C80) | **somente leitura** ("desbloqueado até") |
| `lastClearedStageKey` | maior NORMAL/ACTBOSS completado; completado ⇔ `0 < key ≤ lastCleared`. Libera o chefe contaminado e as Plaguelands. **Reportado ao servidor** no `InventoryInitRequest` e **sobrescrito** pela resposta (init e cada StageClear) (`yi.kvz` 0xA4DB40, `yi.kwa` 0xA4DC00, `wh.wb.jzj`/`jzm`) | **nunca editar** |
| `currentStageKey` | estágio atual (default 1101). Chave inexistente → `KeyNotFoundException` no init (`wh.wb.bad` 0x9A64BD); ACTBOSS → carrega key−1; PLAGUE/CONTAMINACTBOSS → volta para `prevNormalStageKey`. Define a recompensa offline (StageLevel → `OfflineRewardInfoData`) | só "reparar posição": NORMAL existente e ≤ `maxCompletedStage` |
| `currentStageWave` | onda atual; carregada e **zerada** no próprio init (`wh.wb.jyk` 0x9B3739) | não expor (no máximo 0) |
| `prevNormalStageKey` | último NORMAL visitado; ponto de retorno ao sair da praga. No load é usado sem checar tipo: apontar para PLAGUE pularia as checagens de entrada | NORMAL, existente, ≤ max |
| `lastPlayedPlagueIntensity` | `int[4]` por dificuldade (0 Normal sempre 0); última intensidade escolhida na UI; o jogo **limita** ao teto liberado pelo servidor `Clamp(StageNo(plagueClear[dif])+1, 1, 20)` | reset (0) ou 0..20 com `[0]=0`; editar para cima não libera nada |
| `TutorialCleared` | `bool[7]` por `ETutorialType` | `true` é seguro (pula tutorial) |
| `arrangedHeroKey` / `ArrangedPetKey` | heróis no grupo (`int[3]`) / pet ativo (−1 = nenhum) | ver progressão |

Fluxo: no load `wh.wb.jye` copia o save para estáticos `ObscuredInt` (o save é só *fallback* para
`lastCleared`/`max`); o servidor escreve nos mesmos estáticos; o `PreSave` (`wh.wb.jyd`) copia de volta.
Com o servidor respondendo, **o save espelha o servidor**.

Histórico nos snapshots: 1.00.11/1.01.05 sem os campos novos; 1.2.3 gravado **dentro** da praga
(`cur=201401`, `prevNormal=4305`, `lastPlayed[3]=1`, `lastCleared=4309` = derivação de migração);
todos os 1.2.8 em `cur=4305`, `lastCleared=4310` (o chefe final limpo 128 vezes pelos agregados),
`lastPlayed=[0,0,0,11]`.

## 3. Plaguelands no servidor (nenhum campo no save)

`plagueClear` (maior intensidade limpa por dificuldade), `lastClearPlagueStageKey`, Contaminação
(`pollutionValue`/`pollutionUpdateAt`, consumo e recarga por tempo), `plagueIn`, `plagueEnterableAt`
(cooldown), `plagueLocked` (bloqueio de até 1 h) e `PlaguelandsInitData` (máximos, taxas, chaves de
entrada, `unlockStageKey` por dificuldade) — `InventoryInitResult` dump.cs:55188,
`PlaguelandsInitData` dump.cs:55012, `StageClearFunctionResult` dump.cs:55710.

Regras no cliente: dificuldade liberada ⇔ `kac(unlockStageKey[dif])` (chave do servidor); limpar a
intensidade N libera N+1 (até 20); entrada falha sem Contaminação suficiente ou em cooldown; o chefe
contaminado exige o ACTBOSS do ato completado e 1 Contaminated Soulstone; completar CONTAMINACTBOSS não
mexe no progresso.

Contaminação por item (inferência sobre a fórmula): `ContaminOverride` ou
`GradeInfoData.BaseContamin(_Material)` × `ContaminScale`/1000; a **Corrosão** (receita de cubo
`CORROSION`, CubeKey 200101 / sub 200111, cubo nv 30, custo 10000) consome itens **no servidor**
(`CorrosionFunctionRequest{items, useBoxKeyList, cubeLev}`), que devolve `pollutionValue`.

Onde a praga aparece no save: `lastPlayedPlagueIntensity`; `aggregateSaveDatas` com `Content`
(`EAggregateContent` 0 Total / 1 Normal / 2 Plague — 443 clears de praga no save atual, 201401–201413);
34 runas de praga em `RuneSaveData`; a receita `CubeKey 200101` em `cubeRecipeSaveDatas`.

## 4. Editabilidade e riscos

| Campo/área | Política |
|---|---|
| `maxCompletedStage`, `lastClearedStageKey` | somente leitura — reportados e sobrescritos pelo servidor |
| `currentStageKey` + `prevNormalStageKey` | "reparar posição" opcional: NORMAL, existe, ≤ max; gravar os dois iguais e `currentStageWave=0` |
| `currentStageWave` | não expor |
| `lastPlayedPlagueIntensity` | reset ou 0..20, `[0]=0` (sem ganho real) |
| Contaminação, intensidade liberada, desbloqueio, cooldown | impossível pelo save (servidor) |
| Itens `CONTENTTYPE=PLAGUE` | não criar nem alterar; `150101`/`150102` só têm nome (ID inválido) |

Riscos: (1) chave inexistente quebra o load; (2) `currentStageKey` acima do desbloqueado ou
`prevNormalStageKey` apontando para PLAGUE contornam checagens do servidor — vetar; (3) toda mudança de
progresso vai ao servidor no `InventoryInitRequest`.

Validador proposto (implementado em `stage_model.py`, testado em 9 edições de cópia com roundtrip e HMAC
OK): todas as chaves existem em `StageInfoData`; `lastCleared` e `max` são NORMAL/ACTBOSS, com
`max == Next(lastCleared)` ou `== lastCleared`, e iguais aos do save carregado; `prevNormal` é NORMAL e
≤ max; `current` é NORMAL e ≤ max (aviso se ACTBOSS/PLAGUE/CONTAMINACTBOSS); `lastPlayedPlagueIntensity`
é `int[4]` com `[0]=0` e cada valor 0 ou 1..20.

## 5. Correções da verificação adversarial (15 confirmados, 7 parciais, 0 refutados)

- O loader vivo é **`wh.wb.jye`** (0x9B1FB0, chamado por `qu.qp.MoveNext` 0xD2C924); `wh.wb.bad`,
  citado acima, é clone do ofuscador sem chamador (mesmos bytes). O mesmo vale para `xm.hj` (vivo:
  `xm.kri` 0xA25910) e `bde.dez` (vivo: `bde.nof` 0xB86990). Referências cruzadas precisam contar
  `call` (E8) **e** `jmp` de tail-call (E9): `kab` tem 15 sítios, não 12.
- Só `currentStageKey` **diferente de zero e inexistente** estoura no load. `currentStageKey = 0` ou
  `prevNormalStageKey` inválido caem no 1º estágio da lista (reset silencioso de posição).
- `lastPlayedPlagueIntensity` não passa pelo estático 0x70 (esse vem só do servidor:
  `GetMaxPlagueClearStageKey` = máximo de `plagueClear`); "o save espelha o servidor" vale para
  `lastClearedStageKey`/`maxCompletedStage`, não para posição/onda/prevNormal. O `InventoryInitRequest`
  leva só `steamId` e `stageKey`.
- "Contornar checagens do servidor" com `prevNormalStageKey` em PLAGUE não foi provado; o provado é
  contornar as checagens **do cliente**.
- ACTBOSS também exige pedra (1110→190001 … 4310→190004); `EStageEnterResultType` tem ainda
  `FailReasonCanNotAddIntensity=5` e `FailReasonIntensityLocked=6`.
- `StageBoxRequestAbuseGuard` (dump.cs:32332): limitador do cliente para pedidos de caixa de estágio,
  acionado na troca de estágio, com bloqueio persistido em PlayerPrefs (fora do save).
- Monstros novos da praga entram a partir da intensidade **5** (Mouth Bug), não 6.
- `CubeSubRecipeInfoData` 200111 tem `RecipeTier` vazio (receita de tier único).
- `TutorialCleared` precisa continuar `bool[7]` (acesso com bounds-check).
- O `validate()` de `stage_model.py` é protótipo: não implementa todas as regras da §4 (aceita rebaixar
  `lastClearedStageKey`, só avisa `prevNormal > max`, aceita `last = max = 4305`). Reescrever a partir da
  §4 na migração.

## 6. Perguntas em aberto

- Valores que só o servidor tem (`unlockStageKey`, limites de Contaminação, `plagueClear` real —
  inferência: Tormento ≥ 201413).
- O que o servidor faz com o `stageKey` do `InventoryInitRequest` (aceita, ignora ou registra anomalia) —
  assumir o pior caso.
- Confirmar em runtime (jogo fechado, cópia) que `currentStageWave` é zerado e o efeito de
  `currentStageKey` inexistente.
- Se os `aggregateSaveDatas` também são reportados ao servidor (o DataSnap os deixa de fora — ver
  integrity_backend.md §3.4).
