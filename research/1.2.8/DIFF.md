# Diff de dados: `data` -> `research/1.2.8`

- `data`: (sem VERSION)
- `research/1.2.8`: 1.2.8 build=3a1772f1bac841dab68ca5cd5e0e157c extraido=2026-09-29 steps=enums,icons,loc,tables

## Enums

- `EAggregateType`: novo (20 membros)
- `EGearType`: novo (21 membros)
- `EGradeType`: igual (11)
- `EHeroType`: novo (6 membros)
- `EItemType`: novo (4 membros)
- `EMaterialType`: +['ETC=7'] -[]
- `ERecipeType`: +['CORROSION=9'] -[]
- `EStageType`: novo (4 membros)
- `MODTYPE`: igual (3)
- `StatType`: +['MaxAllElementalResistance=64'] -[]

## Tabelas

- so em `research/1.2.8`: AttributeInfoData, BuffGroupInfoData, BuffInfoData, CommonStatModInfoData, CraftingRecipeInfoData, CubeLevelInfoData, CubeRecipeInfoData, CubeSubRecipeInfoData, DropInfoData, ExtractionCostInfoData, ItemGroupInfoData, ItemInfoData, ItemLevelScaleInfoData, LevelInfoData, MonsterInfoData, OfflineRewardInfoData, PassiveSkillInfoData, PcSkinInfo, PetInfoData, PetStatInfoData, PlagueIntensityInfoData, SkillInfoData, SkillLevelInfoData, SkinInfoData, SoundInfoData, StageInfoData, StageLevelInfoData, StashInfoData, StatusEffectInfoData, StorageInfoData, SynthesisDropInfoData, TradingStashInfoData, UniqueModInfoData
- so em `data`: -

### AttributeGroupInfoData — igual (8 linhas)

### CurrencyInfoData — igual (1 linhas)

### GearInfoData — 5760 -> 5954 linhas
- +194: 301193, 302193, 303193, 304193, 305193, 306193, 307193, 308193, 309193, 311193, 312193, 313193 ...
- 2257 linhas alteradas; colunas mais alteradas: BaseStat2_Value(1520), InherentStat1_Value(675), InherentStat2_Value(347), InherentStat3_Value(245), UniqueModKey(2)
  - `300001`: BaseStat2_Value 10->20
  - `300002`: BaseStat2_Value 10->20
  - `300003`: BaseStat2_Value 15->25
  - `300004`: BaseStat2_Value 15->25
  - `300005`: BaseStat2_Value 20->30
  - `300006`: BaseStat2_Value 20->30

### GearTypeInfoData — igual (16 linhas)

### GearTypeScaleInfoData — 20 -> 20 linhas
- colunas: +['ContaminScale']  -[]

### GradeInfoData — 10 -> 10 linhas
- colunas: +['BaseContamin', 'BaseContamin_Material']  -[]

### HeroInfoData — 6 -> 6 linhas
- colunas: +['IsMeleeHero']  -[]
- 5 linhas alteradas; colunas mais alteradas: AttackSpeed(5), MovementSpeed(3)
  - `101`: AttackSpeed 90->80
  - `301`: AttackSpeed 55->50
  - `401`: AttackSpeed 90->80; MovementSpeed 700->770
  - `501`: AttackSpeed 70->55; MovementSpeed 750->850
  - `601`: AttackSpeed 70->55; MovementSpeed 850->900

### InventoryInfoData — igual (260 linhas)

### ItemTypeScaleInfoData — 2 -> 2 linhas
- colunas: +['ContaminScale']  -[]

### MaterialInfoData — 125 -> 143 linhas
- +18: 150103, 150104, 150105, 150106, 150107, 160101, 160102, 160103, 160104, 160105, 160106, 160107 ...
- 10 linhas alteradas; colunas mais alteradas: MATERIALTYPE(10)
  - `150001`: MATERIALTYPE CRAFTING->ETC
  - `150002`: MATERIALTYPE CRAFTING->ETC
  - `150003`: MATERIALTYPE CRAFTING->ETC
  - `150004`: MATERIALTYPE CRAFTING->ETC
  - `150005`: MATERIALTYPE CRAFTING->ETC
  - `150006`: MATERIALTYPE CRAFTING->ETC

### RuneInfoData — 197 -> 248 linhas
- +51: 1162, 11621, 11622, 11623, 11624, 11629, 1163, 11631, 11632, 11633, 1164, 11641 ...
- 8 linhas alteradas; colunas mais alteradas: NextRuneKey(8)
  - `113`: NextRuneKey 114 1131 1132->114 1131 1132 1133
  - `116`: NextRuneKey 117 1161->117 1161 1162
  - `121`: NextRuneKey 122->122 1211
  - `123`: NextRuneKey 124->124 1164
  - `124`: NextRuneKey 125 1241->125 1241 1242
  - `127`: NextRuneKey 128->128 1271

### RuneLevelInfoData — 663 -> 833 linhas
- chave: LevelKey+Level+CostItemKey+CostValue
- +184: 1162/1/100001/6000000, 11621/1/100001/15000000, 11622/1/100001/50000000, 11623/1/100001/200000000, 11624/1/100001/500000000, 11629/1/100001/5000000, 11629/2/100001/10000000, 11629/3/100001/20000000, 11629/4/100001/30000000, 11629/5/100001/40000000, 1163/1/100001/30000000, 11631/1/100001/30000000 ...
- -14: 127/2/100001/273090000, 127/3/100001/292800000, 127/4/100001/311630000, 127/5/100001/332100000, 128/1/100001/330060000, 128/2/100001/409640000, 128/3/100001/439200000, 128/4/100001/467450000, 128/5/100001/498150000, 409/5/100001/75000, 409/5/100001/80000, 409/5/100001/85000 ...

### StatModGroupInfoData — 474 -> 474 linhas
- chave: StatModGroupKey+GearGroup+StatModKey
- +9: 1230011/ARMOR/101201, 1230041/ARMOR/101501, 1250011/ARMOR/101201, 1250011/WEAPON/102501, 1250021/WEAPON/102701, 1260021/ARMOR/101301, 1260041/ARMOR/101501, 1280011/ARMOR/101201, 1290021/ARMOR/101501
- -9: 1230011/ARMOR/101401, 1230041/ARMOR/101301, 1250011/ARMOR/101401, 1250011/WEAPON/102601, 1250021/WEAPON/102601, 1260021/ARMOR/101401, 1260041/ARMOR/101301, 1280011/ARMOR/101501, 1290021/ARMOR/101201
- 7 linhas alteradas; colunas mais alteradas: MinTier(7), MaxTier(7)
  - `1100011/ARMOR/101201`: MinTier 1->2; MaxTier 1->2
  - `1120011/ARMOR/101201`: MinTier 3->4; MaxTier 3->4
  - `1120021/ARMOR/101301`: MinTier 3->4; MaxTier 3->4
  - `1120031/ARMOR/101401`: MinTier 3->4; MaxTier 3->4
  - `1120041/ARMOR/101501`: MinTier 3->4; MaxTier 3->4
  - `1200011/ARMOR/101201`: MinTier 1->2; MaxTier 1->2

### StatModInfoData — 620 -> 620 linhas
- chave: StatModKey+Tier
- 28 linhas alteradas; colunas mais alteradas: MaxValue(28), MinValue(24)
  - `101201/10`: MinValue 50->80; MaxValue 55->90
  - `101201/4`: MaxValue 25->30
  - `101201/5`: MinValue 25->30; MaxValue 30->40
  - `101201/6`: MinValue 30->40; MaxValue 35->50
  - `101201/7`: MinValue 35->50; MaxValue 40->60
  - `101201/8`: MinValue 40->60; MaxValue 45->70

### SynthesisRecipeInfoData — 533 -> 587 linhas
- +54: 10109010, 10109011, 10109012, 10109013, 10109014, 10109015, 10109016, 10109017, 10109018, 10109020, 10109021, 10109022 ...

## names_en (ItemKey -> nome) — 511 -> 534 chaves (+23, -0, ~0)
  - + `150001` = Coin
  - + `150002` = Coin
  - + `150003` = Coin
  - + `150004` = Coin
  - + `150005` = Coin Pile
  - + `150006` = Coin Pile
  - + `150007` = Coin Pile
  - + `150008` = Gold Bar
  - + `150009` = Gold Bar
  - + `150010` = Gold Bar
  - + `150101` = Plague Fruit
  - + `150102` = Plague Fruit

## names_pt (ItemKey -> nome) — 511 -> 534 chaves (+23, -0, ~0)

## strings_en (textos) — 1223 -> 1456 chaves (+234, -1, ~16)
- + por prefixo: Satistics(46), Credits(29), UniqueMod(22), Skin(16), AccountStat(13), Popup(13), StageName(12), RuneName(11), ServerIssueReward(8), Toast(8), Plaguelands(7), SkillName(6), PopUp(5), Setting(5), MonsterName(4), Notice(4), Shop(3), UI(3), Contamination(2), MailReward(2)
- - por prefixo: Notice(1)
- ~ por prefixo: UniqueMod(6), ItemTooltip(3), SubRecipeName(2), Notice(1), PopUp(1), SkillDescription(1), Toast(1), TradeShip(1)
  - + `AccountStat_DropChancePlagueNormalChest` = Plaguelands: Common Chest Drop Chance +{0}%
  - + `AccountStat_DropChancePlagueNormalChestPercent` = Plaguelands: {0}% Increased Common Chest Drop Chance Multiplier
  - + `AccountStat_DropChancePlagueStageBossChest` = Plaguelands: Stage Boss Chest Drop Chance +{0}%
  - + `AccountStat_DropChancePlagueStageBossChestPercent` = Plaguelands: {0}% Increased Stage Boss Chest Drop Chance Multiplier
  - + `AccountStat_MaxAmountPlagueActBossChest` = Plaguelands: Act Boss Chest Max Capacity +{0}
  - + `AccountStat_MaxAmountPlagueNormalChest` = Plaguelands: Common Chest Max Capacity +{0}
  - + `AccountStat_MaxAmountPlagueStageBossChest` = Plaguelands: Stage Boss Chest Max Capacity +{0}
  - + `AccountStat_ReduceAutoOpenPlagueActBossChestTime` = Plaguelands: Auto-Open Act Boss Chest Time -{0}s
  - + `AccountStat_ReduceAutoOpenPlagueNormalChestTime` = Plaguelands: Auto-Open Normal Chest Time -{0}s
  - + `AccountStat_ReduceAutoOpenPlagueStageBossChestTime` = Plaguelands: Auto-Open Stage Boss Chest Time -{0}s
  - + `AccountStat_UnlockAutoOpenPlagueActBossChest` = Plaguelands: Unlock Auto-Open Act Boss Chest
  - + `AccountStat_UnlockAutoOpenPlagueNormalChest` = Plaguelands: Unlock Auto-Open Normal Chest
  - - `Notice_Delete_OnlyInventoryItem` = Items not held on the server have been cleaned up.
  - ~ `ItemTooltip_Material_EngravingStatList_Accessory`: Accessory Engraving Effect List -> Accessory Engraving Effects
  - ~ `ItemTooltip_Material_EngravingStatList_Armor`: Armor Engraving Effect List -> Armor Engraving Effects
  - ~ `ItemTooltip_Material_EngravingStatList_Weapon`: Weapon Engraving Effect List -> Weapon Engraving Effects
  - ~ `Notice_NotMatchAppVersion`: Game version is outdated.\nAn update is required.\n\n ※ How  -> An update is required.\n\n ※ Steam > Library > TBH > Propert
  - ~ `PopUp_Function_DISABLED`: Temporarily unavailable due to a server issue. -> Temporarily unavailable due to a server error ({0}).
  - ~ `SkillDescription_30201`: Summon an ice orb and hurl it at enemies. Slows enemies hit  -> Summon an ice orb and hurl it at enemies. Chills enemies hit

## icon_map — 511 -> 518 chaves (+7, -0, ~0)

