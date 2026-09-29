# TBH Save Editor — glossário

Vocabulário do save do Taskbar Hero e do editor. Um termo por conceito; os nomes entre crases
são os do save/tabelas do jogo.

## Save

**Save vivo**:
O arquivo `SaveFile_Live.es3` que o jogo lê e reescreve (a cada poucos minutos e ao fechar).
_Avoid_: save original, arquivo do jogo

**Snapshot**:
Cópia de um save feita por `tools/save_lab.py snapshot` em `~/tbh_re/saves/`; é onde toda
análise e teste acontecem.
_Avoid_: backup (reservado aos `.bak` e backups do próprio jogo)

**ES3**:
O contêiner Easy Save 3: AES-128-CBC sobre um JSON com três chaves — `AccountSaveData`,
`PlayerSaveData` e `SystemInfo`.

**AccountSaveData / PlayerSaveData**:
Strings JSON aninhadas dentro do ES3: conta (dono Steam, versão, contadores) e jogador (heróis,
itens, runas, progresso...). O editor as edita como dicts.

**SystemInfo**:
HMAC-SHA256 em Base64 sobre `account|player|steamId`; o jogo recusa o save se não bater.
_Avoid_: checksum, hash

## Itens

**ItemKey**:
O TIPO de um item (modelo + grade), um número das tabelas (`GearInfoData`, `MaterialInfoData`).
_Avoid_: id do item

**UniqueId**:
A INSTÂNCIA de um item no save (`itemSaveDatas[].UniqueId`); é o que heróis, inventário e baú
referenciam.
_Avoid_: id do item

**Modelo base**:
A `ItemKey` "sem grade" que tem nome e ícone nas tabelas de localização; `GameData.base_key()`
resolve uma ItemKey de instância para ele.

**GearGroup**:
`WEAPON` / `ARMOR` / `ACCESSORY`: decide quais stats um material pode dar. Vem do 1º dígito da
ItemKey (3–4 arma, 5 armadura, 6 acessório).

**Grade**:
Raridade do item (`EGradeType`: COMMON … COSMIC), 3º dígito da ItemKey de equipamento; define
quantos slots de encantamento de cada tipo existem (`GradeInfoData.ExtraSlotAmount_*`).

## Encantamento

**Encantamento**:
Um `EnchantData` de um item: material + stat + tier + valor. Seis slots por item: 0–1
Decoration, 2–3 Engraving, 4–5 Inscription.
_Avoid_: enchant, afixo, runa

**Tipo de slot**:
`DECORATION` / `ENGRAVING` / `INSCRIPTION` (`MATERIALTYPE` do material; `RecipeType` 3/4/5 no
save).

**StatModKey / Tier**:
Par que identifica uma linha de `StatModInfoData`: qual stat (`STATTYPE`), como soma
(`MODTYPE`) e a faixa `MinValue..MaxValue` com passo `Interval`.

**Grupo de stats**:
`StatModGroupKey` do material: lista, por GearGroup, os StatModKey e tiers que ele pode rolar
(`StatModGroupInfoData`).

**EnchantCount**:
`[deco, eng, insc]` = slots preenchidos por tipo; o jogo o usa para achar slot livre, na UI e no
mercado (o efeito em si vem dos slots com `Tier > 0`). Distinto de `*AppliedTotalCount`, contador
acumulado de aplicações que alimenta conquistas Steam.

**Extração**:
A remoção oficial de um encantamento (receita `EXTRACTION`): zera o slot sem deslocar os outros e
decrementa `EnchantCount`; o material não volta e o item volta a ser negociável.
_Avoid_: remover, apagar encantamento

## Servidor

**DataSnap**:
Snapshot do estado do save (ouro, heróis, runas, cubo, itens com encantamentos...) que o jogo envia
ao backend do estúdio a cada abertura e a cada 8 h de jogo.

**Item do servidor**:
Todo item (`UniqueId` + `ItemKey` + quantidade) é espelho do inventário do backend/Steam Inventory;
item que só existe no save é apagado no próximo sync.

**Plaguelands**:
Modo da 1.2.x (estágios PLAGUE 2012xx–2014xx, intensidade 1–20, chefes contaminados `DA19`) cujo
progresso e Contaminação vivem no servidor; o save só guarda a última intensidade escolhida.

## Progressão

**Herói**:
Um dos seis `heroKey` (101 Knight … 601 Slayer); nível (máx. 101), EXP, pontos (`AbilityPoint`
livres + `AllocatedHeroAbilityPoint` gastos = nível), 10 itens equipados (`equippedItemIds`) e 3
skills (`equippedSKillKey`: ataque-base + 2 ativas; −1 = vazio).

**Runa**:
Nó da árvore de runas (`RuneInfoData`, ligada por `NextRuneKey`) com nível em `RuneSaveData`.

**Cubo**:
Sistema de crafting com nível/EXP (`cubeSaveLevelData`) e receitas desbloqueadas
(`cubeRecipeSaveDatas`).
