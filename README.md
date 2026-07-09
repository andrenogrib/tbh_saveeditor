# TBH Save Editor

A local web app (runs in your browser) to edit **Taskbar Hero** save files, with
**validation against the real game tables** and **automatic `SystemInfo` recalculation**
(the anti-tamper checksum) on save.

## What you can edit

- **Enchantments** (decoration / engraving / inscription) on the heroes' equipped items.
- **Auto-build** (⚙ button): fills every slot with the **best build for the hero's class**,
  respecting how many slots the item's grade allows. Class profiles are derived from the
  game's real skills and stats (Knight/Slayer physical melee, Ranger physical projectile,
  Hunter/Sorcerer elemental AoE, Priest support). Three modes:
  - **Balanced** — solid damage with defensive armor;
  - **Max damage** — offense everywhere;
  - **Survival** — keeps your damage and stacks Max HP + Damage Reduction + Life Leech +
    resistance, for the 3-9 map / Core of the Abyss.

  It also sets the **2 recommended active skills** per class. Apply to one hero or to all at once.
- **Heroes**: level, EXP, and unspent **skill points** (`AbilityPoint`).
- **Resources** (*Player* tab): amount of **Gold** and **Cube** level.
- **Pets** (*Player* tab): unlock/lock each one (or all at once).
- **Runes** (*Player* tab): raise them all to the max level from the game tables.

## How to use (on the machine where you play)

Prerequisite: **Python 3** installed. Nothing else — no `pip install`.

```
cd saveEditor
python server.py
```

Opens `http://127.0.0.1:8765` in your browser. Then:

1. The path to `SaveFile_Live.es3` is pre-filled (auto-detected). Click **Load**.
2. Pick a **hero** → hero panel (level / EXP / skill points) + **equipped items**.
3. Click an **item** → **enchantment** panel (2 Decoration, 2 Engraving, 2 Inscription).
4. **Edit/Add** a slot: choose the **material** → the **stat** (only the options valid for that
   equipment type) → the **tier** → the **value** (within range; **Max** button). Only coherent
   values are accepted.
   - Or use **⚙ Auto-build**: pick the mode (Balanced / Max damage / Survival) and click
     **Apply to this hero** or **Apply to ALL**. Check *overwrite existing* to optimize what's
     already there, or uncheck it to only fill empty slots.
5. In the **Player** tab: edit Gold and Cube level, unlock pets, and max out runes.
6. **Save to game** writes the `.es3` (with a `.es3.bak` backup) and recalculates the `SystemInfo`.

> **Close the game before saving** — otherwise it overwrites the file on exit.

## Project structure

```
saveEditor/
  server.py          # local web server (stdlib, zero deps)
  core/
    es3.py           # decrypt/encrypt the .es3 + recalculate the SystemInfo (HMAC)
    aes_pure.py      # pure-Python AES-128 (fallback with no dependencies)
    gamedata.py      # game tables + enchantment validation
    autobuild.py     # per-class best-build logic + skill recommendations
  web/               # interface (HTML/CSS/JS)
  data/              # data extracted from the game (portable; ships with the app)
    tables/*.csv     # StatModInfoData, MaterialInfoData, StatModGroupInfoData, GradeInfoData...
    names_en.json / names_pt.json   # translated names per ItemKey
    enums.json       # StatType / MODTYPE / ERecipeType / EMaterialType / EGradeType
    icons/*.png      # item/material icons
  extract/           # scripts that GENERATE data/ (run once, require UnityPy)
```

## Re-extracting data (when the game updates)

The data in `data/` was extracted from version **1.00.17**. If the game updates and the values
change, re-extract (on a machine with the game + `pip install UnityPy`):

```
python extract/extract_all.py
```

If an update changes the `SystemInfo` **HMAC key**, update `SYSTEMINFO_HMAC_KEY` in
`core/es3.py` (extractable at runtime via `dtcore.dll`, hotkey F8).

## How validation works

`material → MaterialInfoData (type + group) → StatModGroupInfoData (StatModKey + tier per GearGroup)
→ StatModInfoData (StatType, ModType, Value range per tier)`. The item's GearGroup
(WEAPON/ARMOR/ACCESSORY) comes from the ItemKey range. The editor only allows combinations that
exist in the game, so the resulting enchantments are legitimate.
