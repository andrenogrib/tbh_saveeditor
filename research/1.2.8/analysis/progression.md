# Progressão na 1.2.8 × funções do editor

Escopo: heróis, skills, skins, pets, runas, cubo e moeda da **1.2.8**, confrontados com
`set_hero`, `set_currency`, `set_pet`, `max_runes`, `set_cube`, `set_skills` e
`autobuild` (`ROLE`/`RECOMMENDED_SKILLS`). Tudo foi feito em cópias; nenhum arquivo do projeto
foi alterado. Evidência = linha do `dump.cs`/`game_src`, RVA de função (disassembly da
**cópia** `~/tbh_re/1.2.8/bin/GameAssembly.dll`), tabela + chave, ou save + caminho JSON.
Onde é dedução, está marcado **(inferência)**.

## Resumo: veredito por função

| Função | Veredito | Mudança necessária | Faixa segura (tipo C# / tabela) |
|---|---|---|---|
| `set_hero` → `level` | **Corrigir** | teto = `max(LevelInfoData.Level) + 1` = **101** (hoje aceita até 1000) | `int HeroLevel`; o jogo não passa de 101 (§1.3) |
| `set_hero` → `exp` | OK | nada técnico; avisar que em L<101 o excedente vira nível no próximo ganho de XP | `double HeroExp`; 1e15 < 2^53, sem perda |
| `set_hero` → `abilityPoint` | **Corrigir** | modo estrito `AP ≤ HeroLevel − AllocatedHeroAbilityPoint` | `int`; orçamento do jogo = 1 inicial + 1 por nível (§1.4) |
| `set_currency` | OK | nenhuma obrigatória (só existe a moeda 100001) | `long Quantity`; 1e13 ≪ 9,22e18 (§7) |
| `set_pet` | **Corrigir** | recusar desbloqueio de pet `UnlockCondition=DLC` (6001–6003); avisar nos `KillMonster` | `bool`; o jogo re-deriva só pets travados (§4) |
| `max_runes` | OK, com ajuste | usar `RuneInfoData` da 1.2.8 (com `data/` é no-op no save atual) | `int Level` ∈ [0, MaxLevel]; acima disso dá NullReference (§5) |
| `set_cube` | **Corrigir** | `Level` 1..100; `Exp` < `ExpForLevelUp(Level)`, ou 999999999 no nível 100 | `int Level`, **`float Exp`** (§6) |
| `set_skills` + `RECOMMENDED_SKILLS` | OK, com ajuste | validar: ativa do herói, atributo ≥ 1, slot 3 só com runa 27, `len == 3`, vazio = −1 | `int[3]`; `[0]` é forçado pelo jogo (§2) |
| autobuild `ROLE` | OK | opcional: ler `HeroInfoData.IsMeleeHero` em vez de fixar no código | `ROLE` bate com `ClassType`; `EHeroType` não é usado (§1.2) |
| skins (sem função no editor) | **Não criar** | — | a posse vem do Steam Inventory; skin não possuída é resetada e logada no backend (§3) |

O que mais pesa:

1. **Pontos de habilidade.** Um herói novo nasce com `AbilityPoint = 1`, ganha +1 por nível e só
   transfere pontos entre `AbilityPoint` e `AllocatedHeroAbilityPoint`. No nível máximo (101), o
   orçamento é de **101 pontos**. Para maximizar a árvore são precisos **174** (Knight) ou **172**
   (demais). O save atual já tem 174/172 alocados, e isso vem desde 14/06, antes do primeiro commit
   do editor.
2. **O jogo envia um snapshot do progresso para o backend** (`qh.SnapShot`: moeda, heróis,
   atributos, pets, runas, cubo, itens). Toda edição fica visível para o desenvolvedor, e a string
   `PopUp_BlockedUser` existe. O editor deve manter os valores dentro do que o jogo consegue gerar e
   avisar o usuário. Nada aqui tenta esconder edição.
3. **`max_runes` com `data/` (1.00.17) não faz nada no save atual.** As 20 runas abaixo do máximo
   são todas da 1.2.x e aparecem como "unknown". Com `research/1.2.8` ela altera 20 runas e chega a
   248/248 (testado, §10).

---

## 0. Método

- Código: `game_src` (assinaturas + offsets) e `dump.cs`. Os corpos dos métodos foram lidos por
  disassembly (capstone) da cópia do `GameAssembly.dll`. Scripts em
  `C:/Users/andre/tbh_re/scratch/progression/tools/`:
  - `il2dis.py <rva>`: disassembla e anota chamadas e metadados;
  - `callxref.py <rva>`: lista quem chama;
  - `xref.py`: acha referências RIP-relative;
  - `writers.py` e `reads.py`: acham quem escreve ou lê um offset.

  Exemplo: `python .../tools/il2dis.py 9D8720`.
- Os literais de string do jogo são cifrados pelo ofuscador (nenhum `Popup_*` aparece em
  `stringliteral.json`), então não há xref por string. As chaves de texto citadas vêm de
  `research/1.2.8/strings_en.json`.
- Histórico: os 24 snapshots foram decodificados em `C:/Users/andre/tbh_re/scratch/progression/hist/<arquivo>/player.json`.
- `graphify` (grafo do jogo) serviu para orientação (`explain HeroSaveData`, `PetSaveData` etc.).
  O grafo não tem arestas de chamada, então as chamadas foram resolvidas por disassembly.

---

## 1. Heróis

### 1.1 HeroInfoData (6 heróis)

Diff `data/` → `research/1.2.8` (script sobre os dois CSVs):

| HeroKey | ClassType | AttackSpeed | MovementSpeed | IsMeleeHero (nova) | DLCAppId |
|---|---|---|---|---|---|
| 101 | Knight | 90→80 | 950 | True | 0 |
| 201 | Ranger | 100 | 850 | False | 0 |
| 301 | Sorcerer | 55→50 | 770 | False | 0 |
| 401 | Priest | 90→80 | 700→770 | True | 4427410 |
| 501 | Hunter | 70→55 | 750→850 | False | 4427420 |
| 601 | Slayer | 70→55 | 850→900 | True | 4427430 |

- Offsets (`dump.cs:77601-77635`): `SkillKey` 0x54, `IsMeleeHero` 0x80, `IsAvailable` 0x81,
  `IsFirstAvailable` 0x82, `DLCAppId` 0xB0.
- `IsMeleeHero` é lido só por `wj.kha` (RVA 0x9D48A0), chamado por `Hero.guq` (0xCE9470). Esse
  método escolhe uma constante float estática de `td` (+0xD0 se for melee, +0xD4 se não). É um
  parâmetro de combate ou posicionamento **(inferência)**. Não afeta o save.
- **Heróis de DLC:** no `wj..ctor` (0x9CCF90, trecho 0x9CD2AF–0x9CD32C), se `DLCAppId != 0`, o
  `IsUnLock` em runtime é sobrescrito por `DLCManager.hit(DLCAppId)`. Esse método (0xD1D800) chama
  `Heathen...DlcData.get_IsSubscribed`, ou seja, verifica a posse da DLC na Steam. Editar `IsUnLock`
  de 401/501/601 não tem efeito. O editor já não faz isso.

### 1.2 EHeroType × heroKey × `ROLE`

- `EHeroType` (`dump.cs:77587`): Knight=0, Archer=1, Wizard=2, Priest=3, Hunter=4, Barbarian=5. São
  nomes internos. As 7 ocorrências no `dump.cs` são só a declaração, e nenhum campo ou assinatura
  usa esse enum, então ele é **vestigial**.
- O jogo usa `HeroInfoData.ClassType : EEquipClassType` (`dump.cs:77835`): All=0, Knight=1,
  Ranger=2, Sorcerer=3, Priest=4, Hunter=5, Slayer=6. Nos dados, heroKey = 100·ClassType + 1
  (101..601). Isso é uma observação da tabela, não uma regra do código, porque o jogo sempre busca a
  linha pela `HeroKey`.
- `ROLE` em `core/autobuild.py:63` comparado com os dados da 1.2.8:

| heroKey | ROLE | IsMeleeHero | ataque-base (SkillInfoData) | Leitura |
|---|---|---|---|---|
| 101 | melee | True | 10001 Physical / Melee | coerente |
| 601 | melee | True | 60001 Physical / Melee | coerente |
| 201 | projP | False | 20001 Physical / Projectile | coerente |
| 501 | projE | False | 50001 Physical / Projectile (skills 50101 Fire, 50201 Cold) | coerente com as skills recomendadas |
| 301 | aoeE | False | 30001 Fire / Projectile (ativas quase todas AOE) | coerente |
| 401 | support | **True** | 40001 Physical / **Melee**; 40301 Lightning AOE | escolha de design: `IAOE` serve a Wrath of Heaven, mas o jogo classifica o Priest como melee |

Veredito: as chaves de `ROLE` estão corretas e não há heroKey novo. Melhoria opcional: derivar o
flag melee de `IsMeleeHero`.

### 1.3 Nível máximo do herói = 101

- `LevelInfoData`: Level 1..100, e `ExpForLevelUp` é `int` (`dump.cs:78106-78110`). O maior valor
  é 1.997.771.834 < 2^31. Para ir de 1 a 101 são 42.291.336.533 de XP.
- `wj.dx` (0x9CE9C0, trecho 0x9CEBCA–0x9CEC1D) faz `HeroExp += ganho`, pega
  `info = bdc.nna(HeroLevel)` e sobe de nível só se `info != null && HeroExp >= info.ExpForLevelUp`.
  `bdc.nna` (0xB6ED60) é um `TryGetValue` que devolve null para nível ausente.
- `wj.kjt` (0x9D8720) é o laço de level-up: `HeroExp -= ExpForLevelUp` (0x9D88DB), `HeroLevel++`
  (0x9D891F) e `AbilityPoint += 1` (0x9D8D23–0x9D8D50). Também dispara conquistas Steam (`ze`) nos
  níveis 10/20/30/50/60/70/80 e um `HeroLevelUpLog` no `LogManager`. Esse log é a UI local
  (`LogManager` tem `LogScroll`, `dump.cs:59904`), não o backend.
- Como não existe linha 101, o nível **101 é o máximo alcançável** e a XP passa a só acumular. Os
  saves confirmam: todos os heróis estão em L101 desde 1.01.05, e o `HeroExp` do 201 sobe de 1,08e11
  para 1,55e11 sem mudar de nível.
- `wj.kis` (0x9D55B0) copia `HeroLevel`, `AbilityPoint`, `Allocated` e `HeroExp` do save **sem
  clamp**. Nível 1000 não trava (a tabela devolve null), mas é um valor que o jogo nunca produz.

### 1.4 AbilityPoint × AllocatedHeroAbilityPoint

| Evento | Código | Efeito |
|---|---|---|
| Herói criado | `HeroSaveData..ctor` 0xAB4A50 (0xAB4ABC, 0xAB4ACB) | `HeroLevel=1`, `AbilityPoint=1`, `Allocated=0`, `HeroExp=0` |
| Level-up | `wj.kjt` 0x9D8D23–0x9D8D50 | `AbilityPoint += 1` |
| Alocar/devolver | `wj.fjz` 0x9D1010 (`kjx` 0x9D91C0 é chamado por `AttributeCache.kfj`/`kfn`) | move pontos entre AP e Allocated (a soma não muda) |
| `wj.kjw(n)` 0x9D9150 | `AP += n` | **sem chamador direto e sem METHODREF**. Uma busca por bytes mostra que só métodos de `wj` escrevem no campo de AP (`bytesearch.py`) |

- Semântica: `AbilityPoint` = pontos livres; `AllocatedHeroAbilityPoint` = pontos gastos. Nos 24
  saves vale sempre `Allocated == Σ(Level × RequiredPoint)` dos atributos do herói (script sobre
  `attributeSaveDatas`).
- Orçamento que o jogo gera: `AP + Allocated = HeroLevel`, ou seja, no máximo 101.
- Custo para maximizar a árvore: `Σ(MaxLevel × RequiredPoint)` = **174** (101) ou **172** (201..601)
  em `AttributeInfoData`. Pela regra do jogo não dá para maximizar tudo.
- O save atual tem AP=0 e Allocated=174/172, tudo no máximo. No backup 1.00.11 (14/06, antes do
  primeiro commit do editor em 05/07) já havia `AP + Allocated > HeroLevel`, por exemplo 101 em L34
  com 48+174. A origem é desconhecida **(inferência: edição anterior)**. Para esse save,
  `abilityPoint` não tem utilidade: não há nada para gastar.

### 1.5 Atributos

- `attributeSaveDatas`: 132 entradas = 6 × 22 chaves de `AttributeInfoData`, com `Level` entre 0 e
  `MaxLevel` (3/5/8/10). `ATTRIBUTETYPE` é `PASSIVESKILL` (Value → `PassiveSkillInfoData`, 108
  linhas) ou `ACTIVESKILL` (Value → SkillKey). Todas têm `RequiredPoint = 1`.
- `AttributeGroupInfoData` (sem mudança): grupos 10001..10008 com `RequiredAllocatedPoint`
  0/10/.../70. `wh.tw.ivn` (0x93C2D0) compara `RequiredAllocatedPoint` (offset 0x34) com a contagem
  de pontos para liberar o grupo **(inferência sobre qual contador é usado)**.
- `unlockedAttributeGroupKeys` guarda os grupos liberados; 10001 é implícito. O
  `PlayerSaveData.PostLoad` (0x927AE0, trecho 0x928343–0x928358) cria `int[0]` se estiver null, e
  `wj.khp` (0x9D4B10) adiciona.
- O editor não mexe em atributos. Se um dia mexer, precisa manter
  `Allocated == Σ(Level × RequiredPoint)` e os grupos coerentes.

---

## 2. Skills

**Não há skill nova.** Os 6 `SkillName_` novos são nomes do ataque básico: `SkillName_10001` =
"Knight Basic Attack", até `60001`. As 36 ativas (`x0101..x0601`) têm as mesmas chaves que já
existiam em `data/strings_en.json` (1.00.17). Só mudou o texto de `SkillDescription_30201` (Slows →
Chills).

- `SkillInfoData`: 125 linhas (42 de herói + 83 de monstro/boss). `SkillLevelInfoData`: níveis
  1..10 para cada uma das 36 ativas. `AttributeInfoData` ACTIVESKILL tem `MaxLevel` 5.
- Conferência de `RECOMMENDED_SKILLS` contra `AttributeInfoData` (script):

| modo | herói | skills | ativa do herói? | nível do atributo no save |
|---|---|---|---|---|
| balanced | 101 | 10301 Retribution Strike, 10501 Sacred Blade | sim (101013, 101033) | 5 / 5 |
| balanced | 201 | 20301 Arrow Rain, 20601 Skewer Shot | sim | 5 / 5 |
| balanced | 301 | 30601 Meteor Strike, 30501 Snowstorm | sim | 5 / 5 |
| balanced | 401 | 40301 Wrath of Heaven, 40201 Blessing Of Might | sim | 5 / 5 |
| balanced | 501 | 50101 Explosive Bolt, 50201 Frost Bolt | sim | 5 / 5 |
| balanced | 601 | 60501 Axe Spin, 60201 Crushing Blow | sim | 5 / 5 |
| survival | 101/301/401/501/601 | 10501+10601, 30501+30601, 40401+40101, 50201+50101, 60501+60301 | sim | 5 |
| survival | 201 | igual ao balanced (comentado no código) | sim | 5 |

  O fallback de `skill_loadout` (`str(hk)[:2] + "001"`) bate com `HeroInfoData.SkillKey` nos 6
  heróis.

**Regras de `equippedSKillKey`, tiradas do código:**

| Regra | Evidência |
|---|---|
| Criado como `int[3]` = `[-1,-1,-1]` no herói novo; todos os 24 saves têm 3 posições | `HeroSaveData..ctor` faz `new int[3]` (0xAB4BCD) e `InitializeArray` do campo `<PrivateImplementationDetails>.8688D2…` (`dump.cs:86255`, metadata 0xB1E660 = `ff×12`) |
| O jogo **não redimensiona** o array: equipar escreve por índice com checagem de limite | `wj.kvg` 0x9CDF40 (IndexOutOfRange se o índice ≥ len) |
| `[0]` é sobrescrito no load por `HeroInfoData.SkillKey` (ataque-base) | `wj..ctor` 0x9CD828–0x9CD855 (array vazio aqui dá exceção) |
| Slot vazio = `-1` | `wj.npb` 0x9D6D00 procura −1 |
| Ao montar o herói, chave ≤ 0 é ignorada; `[2]` exige `AccountStat UnlockSkillSlotCount (28) ≥ 1`, senão o jogo grava −1; chave fora de `SkillInfoData` também vira −1 | `Hero.gwb` 0xCED490 (trechos 0xCED737–0xCED77C e 0xCED79C–0xCED7C0); `wh.vr.jwj` 0x9A5310 é um dicionário montado de **todas** as linhas de `SkillInfoData` (0x9A4DB0) |
| UI: slot 0 sempre aberto; slot i aberto se `i < UnlockSkillSlotCount + 1` | `SkillSlot.mlf` 0xAEDA50 |
| `UnlockSkillSlotCount` vem só da runa **27** (valor 1) | `RuneLevelInfoData` STATTYPE=UnlockSkillSlotCount; no save a runa 27 está em Level 1 |

O código não checa se a skill é do herói nem se o atributo foi aprendido: `jwj` só confirma que a
chave existe em `SkillInfoData`. A UI é que restringe. **Mudança:** o editor deve reproduzir as
regras da UI. Isso significa aceitar só `ACTIVESKILL` com `HeroKey` do herói e `Level ≥ 1` em
`attributeSaveDatas`, gravar `[2]` só se a runa 27 estiver em `Level ≥ 1` (senão −1), preservar
`len == 3` e usar −1 como vazio.

---

## 3. Skins

- `SkinInfoData` é nova na 1.2.x. Tem 12 linhas: `25hhh001` (`IsDefault`) e `25hhh002` "Dusk
  Wanderer". 25101002 tem `IsFree=True` (promo); as demais pertencem a `SetId 25001002` (bundle
  pago). São 16 strings `Skin_*` novas. `EquippedSkinKey` não existe nos saves 1.01.05 e aparece no
  1.2.3.
- Chave: `SkinKey.eiw(h, i) = (h + 25000)·1000 + i` e a skin padrão é
  `SkinKey.eix(h) = h·1000 + 25.000.001` (0x891D30 / 0x891D40; constantes em `dump.cs:3285`).
- **Não existe lista de skins no save nem na conta.** `PlayerSaveData`, `AccountSaveData` e
  `CommonSaveData` não têm campo de skin. A posse vem do **Steam Inventory**:
  `bs.<TryLoadUnlockedSkinAsync>` (0x893930) espera um `InventoryResult`, lê
  `Heathen...ItemDetail.get_Definition`, chama `bdc.nlm` (SkinInfoData) e guarda num
  `HashSet<ObscuredInt>` (`bs`, `dump.cs:2662`). A checagem é `bs.egz(key)` = `Contains` (0x886740).
- No load do herói (`wj..ctor` 0x9CD470–0x9CD7A4):
  - `EquippedSkinKey == 0` → usa a padrão;
  - skins não carregadas → usa a padrão (`Popup_SkinLoadFailed`: "All skin equip data has been reset");
  - skin não padrão e **não possuída** → envia `qh.hhr(...)` (log ao backend) e volta para a padrão.
- `PcSkinInfo` (100 linhas: Body/Hair/Eyes/...) **não é usada pelo código**: não há classe,
  campo em `bdc` nem literal "PcSkin" no `dump.cs`. É um asset sobrando e não tem relação com o save.
- **Veredito:** skins não são editáveis de forma útil. Só dá para trocar entre skins que o jogador
  já possui, e isso o jogo faz sozinho. Não criar função.

---

## 4. Pets

- **Nenhum pet novo.** `PetInfoData` tem 8 linhas (1001–1005 `KillMonster`; 6001–6003 `DLC`
  AppId 4427390). Os `PetName_` são idênticos na 1.00.17 e na 1.2.8, e o save tem os mesmos 8 pets
  desde 1.00.11. `PetStatInfoData` tem 11 linhas.
- Carga (`PetManager.lro` 0xABABF0):
  1. Cria uma entrada `{PetKey, IsUnlock:false, IsViewed:false}` para pet da tabela que falta no
     save.
  2. Clona a entrada para o runtime.
  3. **Só para pet travado:** se `UnlockCondition == DLC (2)`, faz
     `IsUnlock = DLCManager.hit(Param1)` (0xABB096–0xABB0DA). Se for `KillMonster`, chama `lrq`.
  4. Chama `lrs` e depois `lrp`.
- `lrq` (0xABB370): `IsUnlock = kills(Param1) ≥ Param2` (0xABB4DD–0xABB4F6), via `xb.kob`
  (agregado MonsterKill). Também é chamado por `UI_PetArrange.men` (0xADC600) quando o monstro do
  pet exibido morre. Portanto um pet `KillMonster` desbloqueado sem as kills pode **voltar a
  travar**.
- `lrs` e `lrt` (0xABB6C0 / 0xABB820): **todo pet desbloqueado** aplica os seus `PetStatInfoData`
  como stat de conta (`bbd.dwf`), não só o arranjado **(inferência: bônus por fonte = petKey)**.
- `IsViewed` é o selo de "novo": `lrp` gera o RedDot `UnlockedPet (9)` para `IsUnlock && !IsViewed`
  (enum em `ERedDotEvent`).
- `ArrangedPetKey` fica em `commonSaveData` (`CommonSaveData.cs:21-22`). `PetManager.lrr`
  (0xABB610) alterna entre a chave e **−1 (nenhum)**. Nenhum load valida se o pet arranjado está
  desbloqueado.
- No save do usuário os 5 pets `KillMonster` têm kills muito acima de 5000 (`aggregateSaveDatas`
  Type 0: 10031 → 81.337, 20051 → 35.387, 20091 → 14.822, 30091 → 65.005, 30051 → 556.238) e os
  3 de DLC estão desbloqueados desde 1.00.11. Tudo coerente.
- **Veredito para `set_pet`:**
  - **Travar:** não tem efeito duradouro em pet cuja condição está cumprida, porque o jogo
    desbloqueia de novo no próximo load.
  - **Desbloquear pet de DLC:** o jogo nunca rechecara o valor, e isso contorna conteúdo pago. **Recusar.**
  - **Desbloquear `KillMonster` sem as kills:** pode ser desfeito pelo evento da UI. Avisar.

---

## 5. Runas

- As +51 runas são **novas de fato**: 11 `RuneName_*` novos (Plague...), e `RuneSaveData` passa de
  197 para 248 entradas entre o save 1.01.05 e o 1.2.3.
- `RuneLevelInfoData` tem 833 linhas; linhas por runa = `MaxLevel` em todas as 248. O custo é
  sempre em ouro (100001), entre 100 e 1e9 por nível (`int`). A única mudança de custo é a runa 128
  (330.060.000 → 250.060.000). Na queda de ouro de 8,98e9 para 2,16e8 entre 1.2.3 e 1.2.8, a compra
  das runas novas soma 9,29e9: foi gasto legítimo, não clamp.
- A árvore é `NextRuneKey` (pai → filhos). Cada filho tem um pai só, e a raiz é a runa 1.
  `PrevNodeRequiredLevel` vale 1 em 14 runas, 5 em 3 e fica vazio no resto. Regra observada nos 24
  saves, sem nenhuma exceção: se o filho tem `Level > 0`, o pai tem `Level ≥ max(1, PrevNodeRequiredLevel)`.
  A leitura "vazio = pai no máximo" é falsa: aparece 8 vezes já no 1.00.11.
- Código:
  - `RunePage.ngr` (0xB4BFC0) percorre **todas** as `RuneInfoData`. Para runa sem entrada no save,
    cria `RuneSaveData(key, 0)` e adiciona (0xB4C375–0xB4C434). **Runa ausente = nível 0, nunca
    inicializada.**
  - `RuneNode.ngd` (0xB35760): se `Level > 0`, faz `bdc.nkr(key, Level)` e aplica o stat com
    `bbd.lpd` (0xB35BDB–0xB35C4E). Se a linha não existe (`Level > MaxLevel`), dá
    **NullReference** (0xB35C30 → 0xB35F5C). Não há checagem do pai no load: o stat é aplicado pelo
    `Level` puro **(inferência pela ausência de leitura do nó pai em `ngd`)**.
  - `bilr` (offset 0x34) é o `MaxLevel`, e o próximo nível é `min(Level+1, MaxLevel)` (0xB35C60).
- Save atual com dados 1.2.8: 228 runas no máximo, 12 em 0 e 8 parciais. **As 20 abaixo do máximo
  são todas novas (1.2.x).** Faltam **28.665.000.000** de ouro para completar. Custo total de todas
  as runas: 49.946.590.050.
- **Veredito para `max_runes`:** a regra "Level = MaxLevel" continua válida e mantém a árvore
  coerente, porque tudo fica no máximo. Duas condições:
  - trocar a fonte para a `RuneInfoData` da 1.2.8. Com `data/` o teste deu `changed=0` e
    `unknown=51`;
  - nunca passar de `MaxLevel`.

  Para edição parcial futura, respeitar `pai ≥ max(1, PrevNodeRequiredLevel)`. Não é preciso criar
  entradas ausentes: o jogo cria ao montar a página. O save atual já tem as 248.

---

## 6. Cubo

- `CubeLevelInfoData` (`dump.cs:76968`): Level 1..100, `ExpForLevelUp` é **float**. A linha 100
  vale 999999999, que em float é exatamente 1.000.000.000 (sentinela). Para ir de 1 a 100 são
  234.760.055 de XP. `CubeLevelSaveData`: `int Level`, **`float Exp`** (`CubeLevelSaveData.cs:7-10`).
- Código:
  - `bdc.LoadInfoData` (0xB55D20–0xB55D91) calcula `maxCubeLevel = max(CubeLevelInfoData.Level)` = 100.
  - `wh.Cube.iyq` (load, 0x914DC0) lê `Level` e `Exp` sem validar. Se `Level > max`, **clampa para
    max** (0x915451–0x9154B6); senão chama `izk`.
  - `wh.Cube.izk` (0x9181C0) é o laço `while Exp ≥ ExpForLevelUp(Level): Exp -= need;
    Level = min(Level+1, max)` (0x918316–0x91840C). No fim, **se `Level == max`, faz
    `Exp = ExpForLevelUp(max)`** (0x918456–0x9184A1).
  - `wh.Cube.izl` (ganho de XP, 0x918670): no nível máximo **não soma XP** (0x9186E4).
  - `wh.Cube.ixr` (0x9136D0) faz `List.Find(Level == atual)`. Se o nível não existe, dá
    NullReference (0x913825).
- Consequências:
  - **`(Level 100, Exp 1e9)` do save atual é o estado canônico que o jogo grava no máximo**, não
    lixo de edição.
  - `Level > 100` é corrigido no próximo load, mas até lá o save tem valor inválido e o editor
    permite 999.
  - `Exp` enorme em L<100 sobe vários níveis no load. Com `Exp ≥ ~1,8e16` (ulp do float ≥ 2^31 >
    1e9) a subtração deixa de mudar o valor e o laço **não termina, o que congela o jogo**
    **(inferência pela aritmética de float; o teto atual de 1e12 está longe disso)**.
- `cubeRecipeSaveDatas` (`CubeRecipeTypeInt`, `CubeKey`, `MaxUnlockRecipeKey`):
  `MaxUnlockRecipeKey` é a maior sub-receita liberada da cadeia (`CubeSubRecipeInfoData`; a chave
  sobe de 10 em 10 por tier) e 0 significa nenhuma. Estado atual:
  - Synthesis 100091 (tier 9, máximo);
  - Crafting 600081: o 600091 exige cubo 90 e `UnlockCost` 50.000, ainda não liberado;
  - Corrosion 200111. A receita CORROSION é nova: o tipo 9 aparece no save 1.2.3 com 0, junto com
    `ERecipeType.CORROSION=9` e as strings `CORROSION` e `Cube_RecipeTooltip_Corrosion`.

  O editor não mexe em receitas.
- **Veredito para `set_cube`:**
  - limitar `Level` a 1..100 (derivado da tabela);
  - `Exp` ∈ [0, ExpForLevelUp(Level)) quando L<100;
  - em L=100 gravar 999999999, que é o valor que o jogo usa;
  - manter o teto de 1e12.

---

## 7. Moeda e limites numéricos

- `CurrencyInfoData` não mudou: uma linha, 100001, `InitialAmount` 100. `wh.ul.fqm` (0x94E130)
  percorre a tabela e cria no save a moeda que faltar. Chaves que não estão na tabela são ignoradas.
- `CurrencySaveData.Quantity` é **`long`** (`CurrencySaveData.cs:9`). Em runtime vira
  `ObscuredLong` (`wh.um`, `dump.cs:42776`).
  - ctor/sync (0x94F250 / 0x94F5A0): cópia sem clamp.
  - Somar (`jdu` 0x94F600): `long + long` sem checagem (0x94F657).
  - Gastar (`gab` 0x94F360): compara `(float)saldo ≥ custo(float)` e desconta `(long)custo`.
  - Não há teto. O maior valor visto num save é 13.094.739.558 (1.00.11). **Sem risco de overflow
    até 9,22e18.**

| Campo | Tipo no save | Runtime | Faixa que o jogo produz/aceita | `server.py _num()` hoje | Proposta |
|---|---|---|---|---|---|
| `currenySaveDatas[].Quantity` | `long` | `ObscuredLong` | ≥ 0, sem teto | 0..1e13 | manter |
| `HeroLevel` | `int` | `ObscuredInt` | 1..**101** | 1..1000 | 1..`max(LevelInfoData.Level)+1` |
| `HeroExp` | `double` | `ObscuredDouble` | ≥ 0; acumula em 101 | 0..1e15 | manter; aviso em L<101 |
| `AbilityPoint` | `int` | `ObscuredInt` | `AP + Allocated ≤ HeroLevel` | 0..999999 | 0..`max(0, HeroLevel − Allocated)` (modo estrito) |
| `AllocatedHeroAbilityPoint` | `int` | `ObscuredInt` | `= Σ Level×RequiredPoint` | não edita | não editar |
| `cubeSaveLevelData.Level` | `int` | `ObscuredInt` | 1..100 | 1..999 | 1..100 |
| `cubeSaveLevelData.Exp` | **`float`** | `ObscuredFloat` | L<100: < ExpForLevelUp(L); L=100: 999999999 | 0..1e12 | idem à coluna "jogo" |
| `RuneSaveData[].Level` | `int` | (RuneNode) | 0..MaxLevel | = MaxLevel | 0..MaxLevel |
| `equippedSKillKey` | `int[3]` | `ObscuredInt[3]` | ver §2 | via RECOMMENDED | validar §2 |
| `PetSaveData.IsUnlock` | `bool` | — | condição da tabela | livre | ver §4 |
| `EquippedSkinKey` | `int` | `ObscuredInt` | padrão ou possuída | — | não editar |

---

## 8. O que o jogo valida ou reporta (riscos para o usuário)

**Normalizações no load:**

- `skill[0]` é forçado para a skill-base, e `[2]`/chaves inválidas viram −1;
- skin não possuída ou não carregada volta para a padrão;
- `IsUnLock` de herói de DLC e `IsUnlock` de pet travado são re-derivados da posse de DLC e das
  kills;
- `Level` do cubo acima do máximo é clampado e a XP é normalizada no máximo;
- `PostLoad` cria listas faltando.

**O que não é validado no load:** `HeroLevel`, `HeroExp`, `AbilityPoint`/`Allocated`, `Quantity`,
nível de runa (acima do máximo dá exceção), `IsUnlock` de pet já desbloqueado.

**Backend:**

- `qh.SnapShot` (0xD223B0), chamado por `qh.Update` e por `qu.*`, copia do `PlayerSaveData` (via
  `tl.iut`, 0x937360) `commonSaveData`, moeda, heróis, atributos, pets, runas, inventário, stash,
  cubo e itens. Serializa em JSON e envia comprimido (`qh.<CompressAndSendSnapShotAsync>`).
- `qh.hhr` (0xD24D30) manda logs nomeados. É chamado, entre outros, pelo `wj..ctor` quando a skin
  equipada não é possuída e pela carga de skins (`bs.*`).
- Existem as strings `PopUp_BlockedUser` ("Suspicious activity was detected, so your account has
  been blocked.") e `PopUp_BlockedUser_TradeShip`. **O que o servidor faz com o snapshot não é
  visível no cliente.**

**Outros efeitos:**

- ACTk (`Obscured*`) protege a memória em runtime e não se aplica ao arquivo de save. Não foi
  analisado nem contornado.
- Conquistas Steam (`ze`) usam nível de herói e de cubo; valores editados podem liberar conquistas
  **(inferência pelos chamadores de `wj.khj`/`izk`)**.

Recomendação: o editor mostra um aviso fixo de que o progresso é sincronizado com o servidor do
jogo, oferece por padrão só valores alcançáveis, e deixa claro que o risco de edição fica com o
usuário.

---

## 9. Tabelas que só existem em `research/1.2.8`: novas ou só não extraídas?

| Tabela | Situação | Evidência |
|---|---|---|
| AttributeInfoData | não extraída antes | 132 `attributeSaveDatas` com as mesmas chaves no save 1.00.11 |
| LevelInfoData | não extraída | `HeroLevel`/`HeroExp` já no 1.00.11 |
| SkillInfoData / SkillLevelInfoData / PassiveSkillInfoData | não extraídas; só nomes de ataque básico novos | `SkillName_x0101..x0601` em `data/strings_en.json`; `equippedSKillKey` no 1.00.11 |
| PetInfoData / PetStatInfoData | não extraídas; sem pet novo | `PetName_*` iguais; 8 `PetSaveData` no 1.00.11 |
| CubeLevelInfoData / CubeRecipeInfoData / CubeSubRecipeInfoData | não extraídas; **CORROSION é nova** | cubo no 1.00.11; `CubeRecipeTypeInt 9` surge no 1.2.3; `ERecipeType+CORROSION` no DIFF |
| SkinInfoData | **nova (1.2.x)** | 16 `Skin_*` novas; `EquippedSkinKey` ausente em 1.01.05 e presente em 1.2.3 |
| PcSkinInfo | **sem uso no código** | nenhum tipo, campo em `bdc` ou literal "PcSkin" no `dump.cs` |
| RuneInfoData / RuneLevelInfoData (já em `data/`) | **+51 novas** | 11 `RuneName_*` novas; 197→248 entradas no save |

---

## 10. Testes locais (só cópias)

Script `C:/Users/andre/tbh_re/scratch/progression/test/run_editor_tests.py`. Ele sobe o
`server.Handler` numa porta livre, com `GD` = `data/` ou `research/1.2.8`, e chama as rotas reais
sobre `work_<tag>.es3`, uma cópia de `saves/20260929_013650/SaveFile_Live.es3`. O `/api/load`
sempre recebe caminho explícito. Resultados em `result_data.json` e `result_1.2.8.json`.

| Chamada | `data/` (1.00.17) | `research/1.2.8` |
|---|---|---|
| `set_hero level=1000` | 200, aceito (**inválido no jogo**) | idem |
| `set_hero abilityPoint=999999` | 200, aceito | idem |
| `set_currency 1e13` / `1e13+1` / key 100002 | 200 / 400 / 404 | idem |
| `set_pet 6003 unlock=false` (arranjado) | 400 (bloqueado, correto) | idem |
| `set_pet 6001 unlock=false/true` (DLC) | 200 / 200 (**deveria recusar**) | idem |
| `max_runes` | `changed=0`, `maxed=197`, `unknown=51` | `changed=20`, 248/248 |
| `set_cube level=999` | 200, aceito (**inválido**) | idem |
| `set_skills survival` → `balanced` | 5 heróis mudam (201 igual), depois volta | idem |
| `auto_build balanced` | 60 itens, 187 slots, 0 erros de validação | 60 itens, 187 slots, 0 erros com as tabelas 1.2.8 |
| `/api/save` + recarregar | OK | OK; `save_lab info`: HMAC OK; `roundtrip`: conteúdo e string idênticos |

---

## 11. Mudanças propostas (não aplicadas)

1. **Fonte de dados:** `GameData` precisa carregar da 1.2.8 pelo menos `HeroInfoData`,
   `RuneInfoData`/`RuneLevelInfoData`, `CurrencyInfoData`, strings e, para validar, `LevelInfoData`,
   `CubeLevelInfoData`, `AttributeInfoData`, `SkillInfoData` e `PetInfoData`.
2. **`set_hero`:**
   - `level ≤ maxHeroLevel` (= 101, calculado da tabela);
   - `abilityPoint ≤ max(0, HeroLevel − AllocatedHeroAbilityPoint)`, com o limite mostrado na UI
     (no save atual dá 0);
   - se o usuário subir `HeroLevel`, avisar que o jogo daria +1 AP por nível e que editar `HeroExp`
     faz o jogo processar os níveis pela regra dele.
3. **`set_pet`:**
   - recusar `unlock=true` quando `UnlockCondition == DLC`;
   - para `KillMonster`, mostrar kills atuais × `Param2` (agregado `Type 0`, `SubKey=Param1`) e
     avisar sobre o re-trave;
   - informar que todo pet desbloqueado soma stats.
4. **`max_runes`:**
   - limitar sempre a `MaxLevel` da tabela 1.2.8 (continua valendo);
   - mostrar quanto de ouro a operação "vale" (28,7e9 no save atual);
   - em edição individual futura, exigir `pai ≥ max(1, PrevNodeRequiredLevel)`.
5. **`set_cube`:** `level ∈ [1, maxCubeLevel]`; `exp < ExpForLevelUp(level)` quando
   `level < max`; no máximo, gravar `ExpForLevelUp(max)` (999999999).
6. **`set_skills` / `skill_loadout`:**
   - base = `HeroInfoData.SkillKey`;
   - validar cada ativa (`AttributeInfoData` ACTIVESKILL do herói com `Level ≥ 1`);
   - `[2]` só se a runa 27 estiver em `Level ≥ 1`, senão −1;
   - manter `len == 3`.
7. **UI:** usar `SkillName_x0001` para o ataque-base (hoje o texto é fixo "Ataque base"). Não criar
   edição de skin. Aviso de sincronização com o backend (§8).

## Perguntas em aberto

- Que checagens o servidor faz sobre o snapshot (`qh.SnapShot`)? No cliente só dá para ver que o
  snapshot é enviado.
- Equipar uma ativa com o atributo em nível 0 quebra algo em combate? O código de spawn não recusa;
  a regra "precisa de nível ≥ 1" vem da UI **(inferência)**.
- `wj.kjw(+n)` (AP extra) não tem chamador. Resta confirmar se algum evento via reflexão/UnityEvent
  o usa.
- Significado exato de `Hero.guq` (constante de `td` escolhida por `IsMeleeHero`).
