# Itens e encantamentos na 1.2.8 — o que muda para o editor

Análise de 2026-09-29. Fontes: tabelas `research/1.2.8/tables/*.csv` (1.2.8) vs `data/tables` (1.00.17);
save mais novo `~/tbh_re/saves/20260929_013650/SaveFile_Live.es3` (1.2.8, salvo 2026-09-29 01:35) e os
outros 23 snapshots (1.00.11 → 1.2.8); `~/tbh_re/1.2.8/game_src` + `dump/dump.cs`; desmontagem da **cópia**
`~/tbh_re/1.2.8/bin/GameAssembly.dll` (capstone, RVAs do Il2CppDumper). Nada no save vivo nem na instalação
foi lido; nenhum arquivo do projeto foi alterado. Scripts e saídas em `~/tbh_re/scratch/items_enchants/`.

Convenção de evidência: `gs:` = `~/tbh_re/1.2.8/game_src/Assembly-CSharp/`; `RVA 0x…` = endereço do método
no `dump.cs`, conferido por desmontagem; "inferência" marca o que não foi provado.

## 0. Resumo

1. **Heurísticas de chave do `gamedata.py`**: `gear_group` e `grade` pelo dígito valem para **todos** os 5954
   equipamentos da 1.2.8 (incluindo as 194 chaves novas). Quebram fora de equipamento: nome/ícone errado para
   10 materiais novos (`160101-160110`), sem ícone para 13 materiais de ícone compartilhado, e caixas
   (STAGEBOX) sem nome/ícone e com grade errada em 121/140 (`920901` no save aparece COMMON, é RARE).
   A 1.2.8 tem `ItemInfoData` (GRADE, GearGroup, NameKey, IconPath por ItemKey) — use a tabela, não o dígito.
2. **Chaves `x193`/`x173`** = **variante 3** (6º dígito) do modelo 19 (Lv90) / 17 (Lv80). Ex.: `301193` =
   Espada, UNCOMMON, modelo 19, var. 3 → `base_key` 300019 "Eternal Sword" / `SWORD_300019` (correto).
   Substituem as variantes 1/2, que viraram `IsDeletedInServer=True`.
3. **Regra "9 dígitos + 900"**: nunca aparece no save (0 em 24 snapshots) nem nas tabelas. É a convenção do
   **itemdef da Steam Inventory** (`ItemKey·1000+900`, ctor do item RVA 0x989BE0), não uma chave de save.
   Empilhamento na 1.2.8 = `Quantity` no slot de inventário/baú.
4. **`DIFF.md` subestima as tabelas de encantamento** (o `diff_versions.py` compara só a 1ª linha por chave):
   `StatModGroupInfoData` mudou **16** linhas (não 2) e `StatModInfoData` mudou **28** linhas (DIFF diz
   "igual") — resistências T4–T10 ficaram maiores (ex. T10 50–55 → 80–90).
5. Com `data/` (1.00.17) o editor **oferece 1286** combinações (material, grupo, stat, tier, valor) inválidas
   na 1.2.8 e **recusa 2481** válidas. Nenhum dos 243 encantamentos existentes usa uma opção alterada.
6. **Validação**: 243/243 encantamentos do save mais novo passam no `validate_enchant` da 1.2.8 **e** da
   1.00.17, e nas checagens extras (RecipeType, StatType/ModType, slot permitido, contadores). Idem nos
   24 snapshots. Auto-build planejado (561 encantamentos, 3 modos) também é válido na 1.2.8.
7. **Correção de invariante**: na 1.2.8 o efeito de um slot é aplicado quando `Tier > 0`, usando
   **`StatType`/`ModType`/`Value` gravados no save** (`wj.kjq`, RVA 0x9D7B70); `EnchantCount` **não** é lido
   nesse caminho. `EnchantCount` continua importando para colocar encantamento novo, UI e restrições.
8. O jogo 1.2.8 grava `EnchantVersion = Application.version` ao rolar (`wh.Cube.jbs`, RVA 0x9216F0); o
   editor **remove** a chave `EnchantVersion` do slot que escreve (viola a invariante 2 do CLAUDE.md).
9. Stats-base/inerentes e UniqueMod são **derivados da tabela em runtime** (`wh.vc.va.jla`, RVA 0x98E640):
   o rebalanceamento de `GearInfoData` não migra o save (61 itens rebalanceados ficaram byte-idênticos
   entre 1.01.05 e 1.2.8).
10. `IsChaotic`: bool persistido, `false` nos 270 itens e em todos os snapshots; único setter (`jlf`) sem
    chamador direto; o painel "Chaotic" do tooltip é sempre desligado. **Contaminação** é valor do
    **servidor** (`pollutionValue`), não está no save; Corrosão (novo `CORROSION=9`) consome itens no servidor.
11. **Risco principal para itens**: o servidor conhece `(ItemKey, UniqueId, Quantity)` de cada item e guarda
    dados de restauração **com encantamentos**; um item restaurado pelo servidor sobrescreve os encantamentos
    locais no load (`EnchantBackUpData`). Encantar no jogo é transação de servidor (`TxId`).

## 1. Anatomia do ItemKey na 1.2.8

### 1.1 Layout (6 dígitos)

| Posição | Significado | Evidência |
|---|---|---|
| 1º | categoria: 1=MATERIAL, 3=arma principal, 4=arma secundária, 5=armadura, 6=acessório, 9=STAGEBOX | `ItemInfoData`: 6237 linhas, 100% consistente (GEAR 5954, MATERIAL 143, STAGEBOX 140) |
| 1º–2º (gear) | `PARTS`/`GEARTYPE`: 30 SWORD, 31 BOW, 32 STAFF, 33 SCEPTER, 34 CROSSBOW, 35 AXE, 40 SHIELD, 41 ARROW, 42 ORB, 43 TOME, 44 BOLT, 45 HATCHET, 50 HELMET, 51 ARMOR, 52 GLOVES, 53 BOOTS, 60 AMULET, 61 EARING, 62 RING, 63 BRACER | idem, 1 tipo por prefixo em 5954/5954 |
| 3º (gear) | grade `EGradeType` (0 COMMON … 9 COSMIC); acessório começa em 1 | 5954/5954 = `ItemInfoData.GRADE` |
| 4º–5º (gear, grade≥1) | modelo 01–19 = nível (01→Lv1, 02→Lv5 … 19→Lv90; grades altas começam mais alto, ex. COSMIC espada 12–19); nome/ícone do modelo = `ItemName_<cat><tipo>00<modelo>` | `NameKey`/`IconPath`/`Level` de 5954/5954 |
| 6º (gear, grade≥1) | variante 1/2/3 (rolagens de stat diferentes da mesma arma) | `GearInfoData` |
| COMMON armas/armaduras | `<cat><tipo>00MM`, MM 01–20 (20 = Lv100, ex. `300020` "Radiant Sword"): sem dígito de variante, o próprio key é o modelo (20 por tipo, 16 tipos) | `ItemInfoData` |
| materiais | `1 T G NNN` só "parece" ter grade no 3º dígito para 11x–14x; 15x/16x/19x não seguem | `160001`..`160010` = COMMON..COSMIC; `190001` = IMMORTAL |

`GearKey == ItemKey` para todo GEAR (5954/5954). `GearTypeInfoData` (16 linhas) não tem
AMULET/EARING/RING/BRACER: acessório não tem stat-base — `jla` pula stat-base para `PARTS` 7–10
(RVA 0x98E640, `cmp [ItemInfoData+0x40], 7..0xa`).

### 1.2 Veredito de cada heurística do `core/gamedata.py`

Universo testado: todas as chaves de `ItemInfoData` (6237), que contém todas as de `GearInfoData` (5954),
`MaterialInfoData` (143), `ItemGroupInfoData` (2190 linhas) e os 270 `ItemKey` do save (nenhuma chave fora
de `ItemInfoData`). `GearTypeInfoData` é indexada por nome de tipo: usada para conferir o mapa de prefixos.
Script: `scratch/items_enchants/heur_test.py`.

| # | Heurística (linha) | Resultado | Veredito |
|---|---|---|---|
| H1 | `gear_group`: 1º dígito 3/4→WEAPON, 5→ARMOR, 6→ACCESSORY (L176) | 6237/6237 = `ItemInfoData.GearGroup` (None p/ MATERIAL/STAGEBOX) | **continua válida** |
| H2 | `grade_id`: 3º dígito se ≥300000 (L118) | GEAR 5954/5954; STAGEBOX 19/140 (ex. `915001`→ARCANA, tabela COMMON; **no save `920901`→COMMON, tabela RARE**, 2 itens); MATERIAL devolve None mas a tabela tem grade (ex. `112001` RARE) | **válida só para GEAR**; quebra p/ caixas |
| H3 | `max_slots`/`slot_allowed` via grade (L126/L135) | 5954/5954 = `GradeInfoData[ItemInfoData.GRADE]`; o jogo faz o mesmo (`jla`: `nkk(GRADE)` → `ExtraSlotAmount_*`, RVA 0x98E8DE) | **válida**; o fallback 2/2/2 para grade desconhecida é permissivo demais |
| H4 | `base_key` → nome (L152/L166) | GEAR 5954/5954 (inclui as 194 novas); MATERIAL 133/143 — `160101`..`160109` viram `160010` "Eternal Empire 1000th Anniversary Coin" (certo: `ItemName_16000x`), `160110` vira `#160110`; STAGEBOX 0/140 (`NameKey` é texto literal, ex. "Stage Boss Box Lv90") | **quebra** p/ OFFERING nova e caixas |
| H5 | `base_key` → ícone (`icon_file`/`has_icon`, L170-174) | GEAR 5954/5954; MATERIAL 121/143 (ícone compartilhado: `150002-4`→`Item_150001`, `150006-7`→`150005`, `150009-10`→`150008`, `150103-7`→`150101`, `1601xx`→`1600xx`); STAGEBOX 5/140 (sprites `Item_910011`/`Item_920011` não extraídos) | **quebra** fora de GEAR; `IconPath` resolve todos os materiais (os PNG já existem) |
| H6 | 9 dígitos terminando em `900` → 6 dígitos (L158) | 0 chaves de 9 dígitos nas tabelas e em 24 snapshots. No jogo, `ItemKey·1000+900` é o id de itemdef da Steam Inventory: ctor `wh.vc.va` faz `int.Parse(ItemKey + "900")` quando `ItemInfoData.IsSteamItem` e o flag do ctor está ligado (RVA 0x989F24-0x989F53) e passa a `ys` (handle de item Steam) | **morta para o save** (nunca dispara); inofensiva |
| H7 | `SLOT_MATERIAL_TYPE` 0,1 DECO / 2,3 ENG / 4,5 INSC (L18) | `td..cctor` (RVA 0x92EFF0): 3 tipos × 2 slots, índices DECO=0, ENG=1, INSC=2; `jkx` coloca em `idx·2+k` (RVA 0x98DF40); save 243/243 no slot do tipo certo | **válida** |
| H8 | `RECIPE_TYPE` 3/4/5 (L20) | `ERecipeType` DECORATION=3, ENGRAVING=4, INSCRIPTION=5 (`gs:TaskbarHero.Data/ERecipeType.cs`); save 243/243 | **válida** |
| H9 | `COUNT_FIELD`/`COUNT_INDEX` + `bump_applied` (L29/L35/L146) | `jkx` incrementa `EnchantCount[idx]` e `Decoration/Engraving/InscriptionAppliedTotalCount` (0x1B0/0x1C0/0x1D0) por aplicação | **válida** |
| H10 | `recount_enchants` (L140) | save: 270/270 `EnchantCount` = slots preenchidos | **válida como coerência**; ver §3.1 (não é o que ativa o efeito) |
| H11 | `stat_options` filtra `{gear_group, COMMON}` (L192) | jogo: INSCRIPTION usa `COMMON`, DECO/ENG usam o grupo do item (`jbs`, RVA 0x92177D-0x921786); tabela 1.2.8: INSCRIPTION só tem linhas COMMON, DECO/ENG só WEAPON/ARMOR/ACCESSORY → equivalente | **lógica válida; dados de `data/` desatualizados** (§3.2) |
| H12 | `validate_enchant` faixa + passo (L259) | jogo rola `Value = Min + k·Interval`, k uniforme em `[0, (Max−Min) div Interval]`, clamp `[Min,Max]` (`py.cfr`, RVA 0xD1F9D0) | **faixa/passo válidos**; não checa RecipeType, StatType/ModType, `slot_allowed`, `Tier≥1` |
| H13 | `build_enchant`/`empty_enchant` (L240/L255) | não escrevem `EnchantVersion`; o jogo 1.2.8 grava `Application.version` (RVA 0x921883) | **viola a invariante 2** (chave some do slot) |
| H14 | `describe_enchant` `valuePct = Value/10` (L300) | só exibição; não verificado | fora do escopo |

### 1.3 Chaves novas de equipamento (194)

`GearInfoData`/`ItemInfoData`: +194 chaves, 0 removidas. Todas terminam em `193` (180) ou `173` (14):
variante **3** do modelo 19 (Lv90) em 20 tipos × 9 grades (UNCOMMON..COSMIC) + 14 do modelo 17 (Lv80).
Lista completa no Apêndice A.

Exemplos pedidos:

| Chave | Decodificação | `base_key` → nome / ícone | `ItemInfoData` 1.2.8 | OK? |
|---|---|---|---|---|
| `301193` | 3 arma principal, 0 SWORD, grade 1 UNCOMMON, modelo 19 (Lv90), var. 3 | `300019` "Eternal Sword" / `300019.png` | `NameKey=ItemName_300019`, `IconPath=SWORD_300019`, WEAPON | sim |
| `522193` | 5 armadura, 2 GLOVES, grade 2 RARE, modelo 19, var. 3 | `520019` "Eternal Gloves" / `520019.png` | `ItemName_520019`, `GLOVES_520019`, ARMOR | sim |

O que é a variante 3 (evidência `ItemInfoData`/`GearInfoData`/`ItemGroupInfoData`):
- `301193` tem os mesmos stats de `301191` (BaseStat 382/40, AttackSpeed MULT 162); `522193` = `522191`.
  No conjunto: 121 variantes 3 têm exatamente os stats da v1, 59 diferem da v1 só no `UniqueModKey` e as 14
  `x173` diferem nos inerentes.
- `IsDeletedInServer=True` em **toda** variante 2 de equipamento (2720) e em 1500 variantes 1; nenhuma
  variante 3 está marcada. `ItemGroupInfoData` (grupos de drop/síntese) lista as 194 novas e **nenhuma**
  `x191`/`x192` (ex. grupo `1100900` "언커먼 주무기 90레벨" → `301193`).
- Inferência: a 1.2.x aposentou v1/v2 no servidor e reemitiu como v3. O save do usuário não tem nenhum item
  `IsDeletedInServer` (0/270) e tem 40 instâncias de 27 chaves novas (todas resolvem nome/ícone certo).

### 1.4 Materiais novos/alterados (MaterialInfoData 125 → 143)

| Chaves | Tipo | Nome (names_en) | Grade | Observação |
|---|---|---|---|---|
| `150001`-`150004` | CRAFTING→**ETC** | Coin | COMMON..LEGENDARY | ícone único `Item_150001` |
| `150005`-`150007` | CRAFTING→**ETC** | Coin Pile | IMMORTAL..BEYOND | `Item_150005` |
| `150008`-`150010` | CRAFTING→**ETC** | Gold Bar | CELESTIAL..COSMIC | `Item_150008` |
| `150103`-`150107` (novos) | **ETC**, `CONTENTTYPE=PLAGUE` | Plague Fruit | RARE..BEYOND | `ContaminOverride` 12/16/32/64/128; drop em `DropInfoData` 9250011.. |
| `160101`-`160110` (novos) | OFFERING | reusa `ItemName_160001..160010` (Kingdom 1st Anniversary Coin … Eternal Empire 1000th Anniversary Coin) | COMMON..COSMIC | `IsTempMarketableFalse=True` (a série `1600xx` é `IsCanExchangeMarketable`); usados em `CubeSubRecipeInfoData` 701011.. (inferência: versão não-negociável) |
| `190102`-`190104` (novos) | SOULSTONE, PLAGUE | Contaminated Soulstone - Nightmare / Hell / Torment | ARCANA..CELESTIAL | `ContaminOverride` 18/24/54 |

`names_en` também ganhou `150101`, `150102`, `150108`-`150110` (Plague Fruit) que **não** são itens (só
localização). Nenhum material novo tem `StatModGroupKey` → nenhum é material de encantamento.

## 2. Grades

- `EGradeType` igual: COMMON=0 … COSMIC=9, NONE=10 (`research/1.2.8/enums.json`; DIFF.md:10).
- `GradeInfoData`: comparação linha a linha das colunas comuns = **0 diferenças** — `InherentSlotAmount` e
  `ExtraSlotAmount_Decoration/Engraving/Inscription` **não mudaram**. Colunas novas (inferência: rendimento
  de Contaminação na Corrosão, paralelo a `BaseAlchemyGold`):

| GRADE | Inerentes | Deco/Eng/Insc | BaseContamin | BaseContamin_Material |
|---|---|---|---|---|
| COMMON | 0 | 0/0/0 | 1 | 2 |
| UNCOMMON | 1 | 0/0/0 | 2 | 3 |
| RARE | 1 | 1/0/0 | 3 | 4 |
| LEGENDARY | 2 | 2/0/0 | 5 | 6 |
| IMMORTAL | 2 | 2/1/0 | 10 | 8 |
| ARCANA | 3 | 2/1/1 | 30 | 12 |
| BEYOND | 3 | 2/2/1 | 50 | 16 |
| CELESTIAL | 3 | 2/2/2 | 100 | 20 |
| DIVINE | 3 | 2/2/2 | 250 | 25 |
| COSMIC | 3 | 2/2/2 | 500 | 30 |

- O jogo usa `ItemInfoData.GRADE` (campo 0x38), não o dígito: `jla` → `bdc.nkk(GRADE)` → `bgka =
  InherentSlotAmount`, `bgkb[idx] = ExtraSlotAmount_*` (RVA 0x98E8D5-0x98E987; offsets em
  `gs:TaskbarHero.Data/GradeInfoData.cs`).
- Tamanho gravado de `EnchantData` = `jkp()` (RVA 0x98D0D0): 0 se não é GEAR; senão `2·(último tipo com
  slot + 1)` → COMMON/UNCOMMON 0, RARE/LEGENDARY 2, IMMORTAL 4, ARCANA+ 6. Confere com 270/270 itens do save
  (0:75, 2:70, 4:84, 6:41). O load aceita qualquer tamanho e copia `min(len, 6)` (RVA 0x98D669-0x98D6B7).

Grades no save mais novo (`ItemInfoData.GRADE`):

| Tipo | COMMON | UNCOMMON | RARE | LEGENDARY | IMMORTAL | ARCANA | BEYOND | CELESTIAL | Total |
|---|---|---|---|---|---|---|---|---|---|
| GEAR | 9 | 11 | 21 | 49 | 84 | 31 | 6 | 4 | 215 |
| MATERIAL | 3 | 6 | 1 | 7 | 12 | 12 | 9 | 1 | 51 |
| STAGEBOX | 2 | – | 2 | – | – | – | – | – | 4 |

DIVINE e COSMIC: nenhum item no save.

## 3. Cadeia do encantamento

### 3.1 Como a 1.2.8 rola, aplica, carrega, grava e usa (desmontado)

| Etapa | Método (RVA) | O que faz |
|---|---|---|
| Rolar | `wh.Cube.jbs(gear, material, recipe)` (0x9216F0, `gs:_global/wh.Cube.cs:424`) | `gg = gear.GearGroup`; se `recipe==5` (INSCRIPTION) `gg=COMMON(4)`; `si = material.jkt(gg)` (StatModInfoData do grupo do material); grava `StatModKey`, `Tier`, `Value = py.cfr(Min,Max,Interval)`, `RecipeType`, `ModType`, `StatType`, `MaterialKey`, **`EnchantVersion = Application.version`** |
| Transação | `wh.Cube.jbl(material, …, enchantData)` → `(string txId, int code)` (`wh.Cube.cs:402`); `PendingEnchantSaveData{MaterialUniqueId, GearUniqueId, RecipeType, Enchant, TxId, TimestampTicks}` (dump.cs:63418) | material consumido no servidor (inferência pelo `TxId` + `MaterialUniqueId`); pendência reprocessada no próximo load ("Popup_Notice_Recovery_Enchant") |
| Aplicar | `wh.vc.va.jkx(ItemEnchantData)` (0x98DF40, `wh.vc.va.cs:167`) | `AppliedTotalCount[tipo]++`; se `EnchantCount[idx] < 2` põe no 1º slot do par `idx·2..idx·2+1` com `Tier ≤ 0`; `EnchantCount[idx]++`; `jky()` dispara evento quando os 3 tipos têm 2 |
| Carregar | `wh.vc.va.jkq(ItemSaveData)` (0x98D2B0, `wh.vc.va.cs:98`) | copia flags; se o servidor restaurou o item (`yi.kwe` → `EnchantBackUpData` com mesmo ItemKey) **substitui** EnchantCount/EnchantData/contadores pelo backup; copia `EnchantCount` como está; copia `min(len,6)` slots para um array fixo de 6. **Nenhuma consulta a StatModInfoData** (sem validação de faixa) |
| Gravar | `wh.vc.jlo()` chamado por `PlayerSaveData.PreSave` (0x979320 / 0x928640) | recria `ItemSaveData`; `EnchantData` com `jkp()` entradas; `IsChaotic` de `jjn()` |
| **Efeito** | `wj.kjq(ulong)` (0x9D7B70, `gs:_global/wj.cs:446`), chamado por `wj.kja(slot, uid)` (equipar) | aplica os 5 `GearModData` do item (base/inerentes) e, **para cada um dos 6 slots com `Tier > 0`**, cria `wu(StatType, ModType, Value, MODSOURCE=1, uid)` com os valores **do save**. Não lê `EnchantCount` nem `StatModInfoData` |

Consequências para o editor:
- A invariante 3 do CLAUDE.md ("EnchantCount … é o que ATIVA o efeito") **não vale na 1.2.8**: o efeito
  vem de `Tier>0` + `StatType/ModType/Value`. `EnchantCount` coerente continua necessário: é a condição de
  slot livre para encantar no jogo (`jkx`), e é lido por UI e restrições (`jkj` chamado por `rz.iju(MoveRequest)`,
  `se.img/ksl`, `wh.Cube.izh/jbe`, `CubeMiddleTextSetter.lys`, `EnchantSlotViewer.miw` — xrefs no
  `GameAssembly.dll`).
- Como o efeito usa `StatType`/`ModType` do save, eles **precisam** bater com `StatModInfoData` do
  `StatModKey/Tier` — `validate_enchant` não confere isso hoje (o save atual está coerente, 243/243).
- "Slot ocupado" no jogo = `Tier > 0`; no editor = `MaterialKey != 0`. Equivalente enquanto o editor nunca
  gravar `Tier>0` com `MaterialKey=0` (não grava).
- Valor fora da faixa não é barrado no load (a faixa só é imposta ao rolar). Isso não é permissão: é o
  motivo de o editor manter a validação estrita.

### 3.2 Mudanças das tabelas (comparação linha a linha)

`tools/diff_versions.py:25` faz `keyed.setdefault(r[0], r)` — em tabela com várias linhas por chave só a
**1ª linha** é comparada. Por isso `DIFF.md:79-83` mostra 2 linhas e `DIFF.md:85` diz "StatModInfoData —
igual". Comparação completa (multiconjunto de linhas, `scratch/items_enchants/fulldiff.py`):

**StatModGroupInfoData — 16 linhas trocadas (474 linhas nas duas versões):**

| Grupo (material) | Grupo de item | 1.00.17 | 1.2.8 |
|---|---|---|---|
| 1100011 (110001 Minor Ruby) | ARMOR | 101201 FireRes T1 | 101201 FireRes **T2** |
| 1120011..1120041 (112001-4 Ruby/Sapphire/Topaz/Emerald) | ARMOR | 1012/1013/1014/1015-01 T3 | mesmas **T4** |
| 1200011 (120001 Goblin Hide) | ARMOR | FireRes T1 + ColdRes T1 | **T2** + **T2** |
| 1230011 (123001 Skull) | ARMOR | LightningRes T4 | **FireRes** T4 |
| 1230041 (123004 Nightshade Extract) | ARMOR | ColdRes T4 | **ChaosRes** T4 |
| **1250011** (125001 Minotaur Horn) | WEAPON | 102601 ColdDamage% T7 | **102501 FireDamage%** T7 |
| 1250011 | ARMOR | LightningRes T6 | **FireRes** T6 |
| **1250021** (125002 Griffin Beak) | WEAPON | 102601 ColdDamage% T7 | **102701 LightningDamage%** T7 |
| 1260021 (126002 Kraken Ink) | ARMOR | LightningRes T7 | **ColdRes** T7 |
| 1260041 (126004 Void Ichor) | ARMOR | ColdRes T7 | **ChaosRes** T7 |
| 1280011 (128001 Primordial Sap) | ARMOR | ChaosRes T9 | **FireRes** T9 |
| 1290021 (129002 Void Tendril) | ARMOR | FireRes T10 | **ChaosRes** T10 |

**StatModInfoData — 28 linhas trocadas**: `101201/101301/101401/101501` (Fire/Cold/Lightning/Chaos
Resistance) tiers 4–10: T4 20–25→20–30, T5 25–30→30–40, T6 30–35→40–50, T7 35–40→50–60, T8 40–45→60–70,
T9 45–50→70–80, T10 50–55→80–90. Isso muda também todos os pergaminhos de Inscrição 131001–139001 (faixas
maiores em WEAPON/ARMOR/ACCESSORY).

Efeito nas **opções oferecidas** (`options_diff.py`, `option_space.py`): 51 pares (material × grupo de item)
mudaram; o espaço (material, grupo, StatModKey, tier, valor) tem 63 799 pontos com `data/` e 64 994 com a
1.2.8; **1286 pontos oferecidos por `data/` são inválidos na 1.2.8** (ex. `137001` ARMOR FireRes T8 valor 40)
e **2481 válidos são recusados** (ex. `125002` WEAPON LightningDamage% T7; `136001` WEAPON FireRes T7–T9 até 80).

Efeito nos **encantamentos existentes**: nenhum. No save mais novo 50 dos 243 usam um material cujas opções
mudaram (129002, 127002, 137001, 115002…), mas **0** usam uma opção alterada (StatModKey de resistência:
0; 125001/125002: 0). Todos validam nas duas versões. Se um dia existir encantamento antigo fora da faixa
nova, o jogo o mantém (load não valida — §3.1); o editor deve tratá-lo como "legado" (aviso), nunca
"consertar" sozinho. Em que versão (1.01.x ou 1.2.x) as linhas mudaram: indeterminado (não há tabelas
intermediárias; o save não tem encantamento de resistência).

Integridade 1.2.8: todo `StatModGroupKey` de material tem linhas; toda linha de grupo aponta para
`(StatModKey, Tier)` existente; INSCRIPTION só usa `COMMON` (10 grupos), DECO (36) e ENG (33) só
WEAPON/ARMOR/ACCESSORY. Armadilha: `104701` (IncreaseExpAmount) tem `Max−Min = 9` e `Interval = 10` em todos
os tiers → o jogo só rola o `Min`; "valor = Max" (como o auto-build escolhe) seria inválido para esse stat.

### 3.3 Enums novos

| Enum novo | Quem usa | Encantamento? |
|---|---|---|
| `StatType.MaxAllElementalResistance = 64` (dump.cs:50629) | só `CommonStatModInfoData` 4510006/4510007 (via UniqueMod `StatValueUp` 1001006/1001007); string nova `Stat_MaxAllElementalResistance_FLAT` | **não** (nenhum `StatModInfoData` usa) |
| `ERecipeType.CORROSION = 9` (dump.cs:77065) | `CubeRecipeInfoData` 200101 e `CubeSubRecipeInfoData` 200111 (Cube Lv30, custo 10000); função de servidor `CorrosionFunction` (consome itens, devolve `pollutionValue`, dump.cs:52660) | **não** (save: `RecipeType` só 3/4/5) |
| `EMaterialType.ETC = 7` (dump.cs:78156) | 150001-150010 (ex-CRAFTING) e Plague Fruit 150103-150107 | **não** (sem `StatModGroupKey`; `materials_by_type` ignora) |

### 3.4 UniqueModInfoData e CommonStatModInfoData — derivados, não gravados

- `ItemSaveData` não tem campo de afixo (`gs:TaskbarHero.EasySaveData/ItemSaveData.cs:5-28`).
- `jla` copia `GearInfoData.UniqueModKey` (+0x60) para `wh.vc.va.bgkv` (0x230) (RVA 0x98E884-0x98E897);
  `CommonStatModInfoData` é parâmetro de `UniqueMod = StatValueUp` (1001001–1001009 → 4510001–4510009).
- Trocar `ItemKey` troca o UniqueMod — mais um motivo para o editor não mexer em `ItemKey`.
- Existência antes da 1.2.8: `UniqueModInfoData` **já existia** (não tinha sido extraída) — o
  `GearInfoData` 1.00.17 referencia 36 `UniqueModKey`, todos presentes na 1.2.8, e havia 22 strings
  `UniqueMod_*`; a 1.2.8 acrescentou 52 chaves e 22 strings novas. `CommonStatModInfoData` é
  provavelmente **nova** (inferência: só `StatValueUp` a usa, `UniqueMod_StatValueUp` é string nova e usa o
  `StatType` 64 novo). `ItemInfoData` já existia (o save 1.00.11 tem chaves 9xxxxx/1xxxxx que só ela
  define; `ItemType_STAGEBOX` já estava nas strings 1.00.17). `ItemGroupInfoData`: existência anterior
  indeterminada; o conteúdo atual inclui as 194 chaves novas.

## 4. Rebalanceamento do GearInfoData: derivado em runtime

- `GearInfoData` 5760 → 5954; 2257 linhas com `BaseStat2_Value`/`InherentStat*`/`UniqueModKey` alterados.
- Nenhum stat é gravado: `ItemSaveData` só tem ItemKey, ids, flags, encantamentos e contadores.
- `wh.vc.va..ctor(ItemInfoData, ItemSaveData, bool)` (0x989BE0) chama `jla()` (0x98E640): `bdc.nld(GearKey)`
  → `GearInfoData`; grava `bgkc` (BaseStat1 = +0x34), `bgkd` (BaseStat2 = +0x38, só `PARTS==MAIN_WEAPON`),
  `bgke..bgkg` (InherentStat1–3 = +0x3C..+0x5C, conforme `InherentSlotAmount`), tipos/modos de
  `GearTypeInfoData`. `wj.kjq` aplica esses 5 `GearModData` ao herói.
- Save: 174 itens comuns entre 1.2.3 e 1.2.8 são **idênticos**; entre 1.01.05 e 1.2.8, 61 itens cujo
  `GearKey` foi rebalanceado continuam byte-idênticos (ex. `344171` BaseStat2 20→35, UniqueId
  …534226). O novo valor vem da tabela ao carregar; o editor não precisa migrar nada, mas deve exibir stats
  a partir das tabelas da **mesma versão** do jogo.

## 5. Coverage e validação de todos os encantamentos

`python tools/save_lab.py coverage <SaveFile_Live.es3> --data research/1.2.8`:

```
[item] 3 desconhecido(s)
  910051           sem nome (names_*.json)
  920901           sem nome (names_*.json)
  910901           sem nome (names_*.json)
```
(caixas: `NameKey` literal, não é `ItemName_` — ver H4.)

Contra `data/` (1.00.17): 30 itens (27 chaves `x193`/`x173` "equipamento fora de GearInfoData" + as 3
caixas) e 51 runas fora de `RuneInfoData`. Com `data/`, `server.py` não bloqueia esses itens (a invariante 4
não é aplicada no `item_payload`); funcionam só porque H1/H2 acertam para GEAR.

Validação (`scratch/items_enchants/validate_all.py`, usa `GameData('research/1.2.8').validate_enchant` e
`GameData('data')`, mais checagens extras):

| Checagem | Save mais novo | 24 snapshots |
|---|---|---|
| `validate_enchant` 1.2.8 | **243/243 OK** | OK em todos (241–249 por save; 1 no 1.00.11) |
| `validate_enchant` 1.00.17 | 243/243 OK | OK em todos |
| `RecipeType` = tipo do slot; `StatType`/`ModType` = `StatModInfoData` | 0 falhas | 0 |
| slot permitido pela grade; `EnchantVersion` nulo | 0 falhas | 0 |
| `EnchantCount` = slots preenchidos; `*AppliedTotalCount` ≥ preenchidos | 0 falhas | 0 |
| `len(EnchantData)` = `jkp()` | 0 falhas | só o 1.00.11 (todos com 6) |

Perfil (inferência sobre a origem): 242/243 estão no tier máximo do material **e** no valor máximo do tier
(padrão do auto-build do editor); o único "aleatório" é `345141` slot 0 (AttackDamage T5 = 12 em 10–15),
presente desde 1.01.05. Nenhum encantamento novo foi criado pelo jogo nos snapshots 1.2.x (histórico em
`new_enchants.py`).

Testes locais (só cópias, saída em scratch):
- `save_lab.py roundtrip … --out scratch/…`: HMAC original OK, regravado OK, conteúdo idêntico.
- `autobuild_check.py`: `plan_item` para os 60 itens equipados × 3 modos = 561 encantamentos, válidos na
  1.2.8 tanto planejando com `data/` quanto com `research/1.2.8` (o auto-build não usa as opções alteradas).
- `sim_edit.py` (caminho de `/api/set_enchant` e `/api/auto_build` em memória, gravado em
  `scratch/…/sim_edit_SaveFile_Live.es3`, HMAC OK ao recarregar): o slot escrito **perde a chave
  `EnchantVersion`**; o auto-build aumenta `EnchantData` de um RARE de 2 para 6 entradas (o jogo aceita e
  corta de volta para 2 no próximo save — §2).

## 6. IsChaotic, Chaos e Contaminação

| Termo | O que é | Onde fica | Evidência |
|---|---|---|---|
| `IsChaotic` | flag de item persistido; semântica de jogo **não confirmada** | `itemSaveDatas[].IsChaotic` (bool, 0x28), desde ≤1.00.11 | `ItemSaveData.cs:12-13`; load → `bgkj` ObscuredBool (`jkq` 0x98D3A1); save ← `jjn()` (`jlo` 0x979574); único setter `jlf()` (0x98EDF0: se já true só loga, senão põe true) **sem chamada direta** no binário; `ItemTooltip.panel_ChaoticPanel` (dump.cs:35459) é sempre `SetActive(false)` (`icy` 0x8CFFF2, `icz`, `ida`); vem também no registro de restauração do servidor (`ItemRestorationData.IsChaotic`, dump.cs:3702); `false` em 270/270 itens e em todos os 24 snapshots; nenhuma string "Chaotic" na localização |
| Chaos | elemento de dano/resistência (`ChaosResistance`, `ChaosDamagePercent`… "Chaos Resistance" = `StatName_PoisonResistance`), nomes de material (Chaos Diamond, Chaos Spore…) | stats de tabela | strings_en; sem relação com `IsChaotic` (inferência) |
| Contaminação (`pollution`) | recurso para entrar nas Plaguelands, consumido com o tempo; ganho jogando ou por **Corrosão** | **servidor** — `InventoryInitResult.pollutionValue` (dump.cs:55200), `CorrosionFunctionResult.pollutionValue`, `PlaguelandsInitData.pollution*`; **não existe no save** (grep em player/account.json: só `IsChaotic` e `lastPlayedPlagueIntensity`) | strings `Contamination_Tooltip`, `Cube_RecipeTooltip_Corrosion`, `Notice_WillGetCorrosionContaminationText`; colunas `BaseContamin*`, `ContaminScale`, `ContaminOverride` (inferência: rendimento da Corrosão) |

Como o editor pode quebrar isso:
- Mudar `IsChaotic`: efeito desconhecido; o servidor guarda o valor na restauração → divergência. Tratar
  como somente leitura.
- Contaminação não é editável pelo save; tentar "dar" Plague Fruit/Contaminated Soulstone criando itens
  bate na reconciliação do servidor (§7).
- Não há encantamento com `RecipeType=9`; nunca gravar `CORROSION` em `EnchantData`.

## 7. O que o jogo valida/reporta (para o editor avisar, não para contornar)

- **Reconciliação de itens com o servidor**: o servidor mantém `ServerItemEntry{ItemKey, UniqueId, Quantity}`
  (dump.cs:56715) e o cliente sincroniza (`wh.vc.jcr/jly/btz…(IReadOnlyList<ServerItemEntry>)`). Strings:
  "When server items and local save files do not match due to errors or manipulation below, automatic sync
  is triggered … 3. Items created through abnormal means" (`Notice_Delete_OnlyInventoryItem_PopUpText2/3`)
  e "Items have been recovered from the server" (`Notice_Create_OnlyServerItem`, nova). → Criar/remover
  item, trocar `ItemKey`/`UniqueId` ou mexer em `Quantity` é visível para o servidor.
- **Restauração com encantamentos**: `ItemRestorationData` traz `EnchantCount`/`EnchantData`/contadores
  (dump.cs:3702); `yi.kwf` (0xA4E380, chamado na inicialização `qu.hlk`) cria `EnchantBackUpData`
  e o `jkq` o aplica por cima do save. → Um encantamento feito pelo editor pode ser **sobrescrito** se o
  servidor restaurar o item (inferência sobre a origem dos dados do servidor; não testável offline).
- **Encantar é transação**: `PendingEnchantSaveData.TxId`; `pendingEnchantList`/`pendingItemRestorationList`
  vazios no save atual. Editar um item listado ali conflita com o reprocessamento.
- **Telemetria** (`pc.EReportType`, dump.cs:27762): ACTk_*, taxas de caixa, `Trade_*` e `Grade_*`
  (ARCANA..COSMIC), `ItemLevel_50/80`, `Level_50/80`, `Gold_Massive`, `Save_Tampered`; chamada por `ox`
  (janelas de taxa por grade/caixa) e pelo gerenciador de save `bde` (`dez`/`nof`). → Editar só dentro dos
  valores válidos e não criar itens de grade alta.
- **Regra de jogo com efeito real**: item encantado não pode ser negociado nem entrar no Cube
  (`Toast_NotAllowedEnchantedTrade`, `Toast_CannotInputEnchantedItem`). Encantar pelo editor torna o item
  não-negociável no Mercado Steam.

## 8. O que o editor deve mudar (prioridade)

1. **Tabelas de encantamento da 1.2.8** (`MaterialInfoData`, `StatModGroupInfoData`, `StatModInfoData`,
   `GradeInfoData`) no `GameData` antes de qualquer edição na 1.2.8 (promoção de `research/1.2.8` via
   `/portar-versao`).
2. **`ItemInfoData` como fonte** de GRADE, GearGroup, nome (`NameKey`; STAGEBOX = texto literal) e ícone
   (`IconPath` → número do sprite); heurísticas de dígito só como fallback com aviso. Extrair também os
   sprites de `IconPath` das caixas.
3. **Preservar `EnchantVersion`**: escrever o encantamento atualizando o dict existente campo a campo (não
   substituir o objeto). Valor a gravar em slot novo: decisão do usuário (§9).
4. **Não inflar `EnchantData`**: preencher só até `jkp()` = `2·(último tipo com slot+1)` (auto_build hoje
   completa até 6, `server.py:284`; `set_enchant` completa até o slot, `server.py:239`).
5. **`validate_enchant`**: acrescentar `RecipeType` = tipo do slot, `StatType`/`ModType` = `StatModInfoData`,
   `Tier ≥ 1`, `slot_allowed`, e "máximo atingível" = `Min + ((Max−Min) div Interval)·Interval` (caso `104701`).
6. **Atualizar a invariante 3** do CLAUDE.md: efeito = slots com `Tier>0` usando `StatType/ModType/Value`
   do save; `EnchantCount` = contagem por tipo que o jogo usa para slot livre, UI e restrições (manter coerente).
7. **`diff_versions.py`**: comparar tabelas multi-linha como multiconjunto (afeta `StatModGroupInfoData`,
   `StatModInfoData`, `RuneLevelInfoData`).
8. **Campos somente leitura** em `itemSaveDatas[]`: `ItemKey`, `UniqueId`, `PrevUniqueId`, `RegisterID`,
   `IsChaotic`, `IsBlocked`, `ItemGetSourceType`; e `Quantity` dos slots. Recusar edição de item presente em
   `pendingEnchantList`/`pendingItemRestorationList`.
9. Remover (ou comentar como "id de itemdef Steam, não aparece no save") a regra `900` de `base_key`.
10. UI: avisar que encantar torna o item não-negociável e que restauração do servidor pode desfazer a edição.

## 9. Decisões e perguntas abertas

Decisões do usuário:
- `EnchantVersion` em encantamento criado pelo editor: manter `null` (como os 243 atuais) ou gravar a versão
  do save. O load não lê o campo; o jogo grava a versão ao rolar.
- Aceitar encantamento "legado" (válido na 1.00.17, fora da faixa 1.2.8) com aviso, ou bloquear edição do
  item? Hoje não existe nenhum no save.
- Manter o auto-build em "tier máximo, valor máximo" (é o padrão que identifica os 242 encantamentos atuais)
  ou rolar dentro da faixa.

Perguntas abertas:
- Semântica de `IsChaotic` (flag legado? setter chamado por delegate?). Nunca observado `true`.
- Se o servidor guarda os encantamentos feitos pelo editor (a restauração usa dados do servidor).
- Versão exata em que resistências e grupos mudaram (1.01.x ou 1.2.x).
- Fórmula da Contaminação por Corrosão (`BaseContamin` × escalas) — só inferência.

## Apêndice A — 194 chaves novas de equipamento

Todas: `GearKey == ItemKey`, `IsDeletedInServer` vazio, nome/ícone = `base_key` (correto).

| Prefixo | PARTS/GEARTYPE | Sufixo | Lv | Nome (`base_key`) | Grades (3º dígito) | Chaves |
|---|---|---|---|---|---|---|
| 30 | MAIN_WEAPON/SWORD | x193 | 90 | Eternal Sword (300019) | 1–9 | 301193 302193 303193 304193 305193 306193 307193 308193 309193 |
| 31 | MAIN_WEAPON/BOW | x193 | 90 | Eternal Bow (310019) | 1–9 | 311193 312193 313193 314193 315193 316193 317193 318193 319193 |
| 32 | MAIN_WEAPON/STAFF | x193 | 90 | Eternal Staff (320019) | 1–9 | 321193 322193 323193 324193 325193 326193 327193 328193 329193 |
| 33 | MAIN_WEAPON/SCEPTER | x173 | 80 | Dimensional Scepter (330017) | 5 | 335173 |
| 33 | MAIN_WEAPON/SCEPTER | x193 | 90 | Eternal Scepter (330019) | 1–9 | 331193 332193 333193 334193 335193 336193 337193 338193 339193 |
| 34 | MAIN_WEAPON/CROSSBOW | x173 | 80 | Dimensional Crossbow (340017) | 6, 8 | 346173 348173 |
| 34 | MAIN_WEAPON/CROSSBOW | x193 | 90 | Eternal Crossbow (340019) | 1–9 | 341193 342193 343193 344193 345193 346193 347193 348193 349193 |
| 35 | MAIN_WEAPON/AXE | x173 | 80 | Dimensional Axe (350017) | 9 | 359173 |
| 35 | MAIN_WEAPON/AXE | x193 | 90 | Eternal Axe (350019) | 1–9 | 351193 352193 353193 354193 355193 356193 357193 358193 359193 |
| 40 | SUB_WEAPON/SHIELD | x193 | 90 | Eternal Shield (400019) | 1–9 | 401193 402193 403193 404193 405193 406193 407193 408193 409193 |
| 41 | SUB_WEAPON/ARROW | x193 | 90 | Ancient Arrow (410019) | 1–9 | 411193 412193 413193 414193 415193 416193 417193 418193 419193 |
| 42 | SUB_WEAPON/ORB | x193 | 90 | Eternal Orb (420019) | 1–9 | 421193 422193 423193 424193 425193 426193 427193 428193 429193 |
| 43 | SUB_WEAPON/TOME | x193 | 90 | Eternal Tome (430019) | 1–9 | 431193 432193 433193 434193 435193 436193 437193 438193 439193 |
| 44 | SUB_WEAPON/BOLT | x173 | 80 | Dimensional Bolt (440017) | 8 | 448173 |
| 44 | SUB_WEAPON/BOLT | x193 | 90 | Ancient Bolt (440019) | 1–9 | 441193 442193 443193 444193 445193 446193 447193 448193 449193 |
| 45 | SUB_WEAPON/HATCHET | x173 | 80 | Dimensional Hatchet (450017) | 6 | 456173 |
| 45 | SUB_WEAPON/HATCHET | x193 | 90 | Eternal Hatchet (450019) | 1–9 | 451193 452193 453193 454193 455193 456193 457193 458193 459193 |
| 50 | HELMET/HELMET | x193 | 90 | Eternal Helmet (500019) | 1–9 | 501193 502193 503193 504193 505193 506193 507193 508193 509193 |
| 51 | ARMOR/ARMOR | x173 | 80 | Dimensional Armor (510017) | 6–9 | 516173 517173 518173 519173 |
| 51 | ARMOR/ARMOR | x193 | 90 | Eternal Armor (510019) | 1–9 | 511193 512193 513193 514193 515193 516193 517193 518193 519193 |
| 52 | GLOVES/GLOVES | x173 | 80 | Dimensional Gloves (520017) | 5 | 525173 |
| 52 | GLOVES/GLOVES | x193 | 90 | Eternal Gloves (520019) | 1–9 | 521193 522193 523193 524193 525193 526193 527193 528193 529193 |
| 53 | BOOTS/BOOTS | x193 | 90 | Eternal Boots (530019) | 1–9 | 531193 532193 533193 534193 535193 536193 537193 538193 539193 |
| 60 | AMULET/AMULET | x193 | 90 | Abyss Amulet (600019) | 1–9 | 601193 602193 603193 604193 605193 606193 607193 608193 609193 |
| 61 | EARING/EARING | x193 | 90 | Abyss Earring (610019) | 1–9 | 611193 612193 613193 614193 615193 616193 617193 618193 619193 |
| 62 | RING/RING | x173 | 80 | Ethereal Ring (620017) | 5 | 625173 |
| 62 | RING/RING | x193 | 90 | Abyss Ring (620019) | 1–9 | 621193 622193 623193 624193 625193 626193 627193 628193 629193 |
| 63 | BRACER/BRACER | x173 | 80 | Ethereal Bracer (630017) | 6, 9 | 636173 639173 |
| 63 | BRACER/BRACER | x193 | 90 | Abyss Bracer (630019) | 1–9 | 631193 632193 633193 634193 635193 636193 637193 638193 639193 |

No save mais novo: 305193, 314193, 322193 (×2), 325193, 335173, 344193 (×3), 354193, 405193, 414193, 421193,
454193, 504193 (×2), 512193, 514193, 521193, 522193, 524193, 525193, 531193, 603193, 612193 (×2),
614193 (×5), 621193 (×4), 623193, 624193, 631193 (×2), 632193 — 27 chaves, 40 itens.

## Apêndice B — reprodução

Pasta `~/tbh_re/scratch/items_enchants/` (rodar a partir de `saveEditor/`):

| Script | O quê |
|---|---|
| `heur_test.py` | §1.2, heurísticas × 6237 chaves + save |
| `fulldiff.py` / `options_diff.py` / `option_space.py` | §3.2, diff linha a linha e espaço de opções |
| `validate_all.py <save> [-v]` | §5, validação completa de um save |
| `new_enchants.py` / `ench_profile.py` / `flags_survey.py` / `keysurvey.py` / `history.py` | histórico dos snapshots |
| `autobuild_check.py` / `sim_edit.py` | testes locais do caminho de escrita (só scratch) |
| `tbhdis.py <rva>` / `xrefs.py <rva>…` / `build_index.py` | desmontagem da cópia do `GameAssembly.dll` e referências cruzadas |
