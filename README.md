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

  It also sets the **2 recommended active skills** per class (only skills the hero has learned;
  the third slot only with the rune that unlocks it). Apply to one hero or to all at once.
- **Heroes**: level (1–101), EXP (below what the level needs; display only at 101) and unspent
  **skill points** (at most level − points already allocated). Locked heroes are read-only.
- **Resources** (*Player* tab): amount of **Gold** (warning above 100 M) and **Cube** level/Exp
  (1–100, Exp consistent with the level).
- **Pets** (*Player* tab): lock/unlock the kill-unlock pets (the game may lock them again if the
  kill condition is not met). DLC pets are display-only: ownership belongs to Steam.
- **Runes** (*Player* tab): raise them to the max level from the game tables, except the chest
  family (drop chance, capacity, auto-open, open all), which the editor leaves alone.
- **Progress** (*Player* tab): current stage, unlocked stage and Plague intensity, read-only —
  the game server is the authority on progress.

Out of scope, always: creating/duplicating items, stages, skins, play time and statistics,
unlocking DLC pets, raising chest runes.

> **Everything you save goes to the game's server the next time the game starts** (it uploads a
> snapshot of gold, heroes, runes, cube and every item with its enchantments). The editor keeps
> values inside what the game itself can produce, but the developer can see the save.

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
5. In the **Player** tab: edit Gold and Cube, lock/unlock pets, max out runes, see progress.
6. **Save to game** writes the `.es3` atomically (with a `.es3.bak` backup of the previous file)
   and recalculates the `SystemInfo`.

> **Close the game before saving.** The game rewrites the save every 3 minutes and on exit, so
> the editor refuses to save the game's save while the game is running, and also refuses if the
> file changed since you loaded it (load it again and redo the edit).

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

The data in `data/` was extracted from version **1.2.8** (see `data/VERSION`). If the game updates and the values
change, extract the new version into `research/<version>/` (needs `pip install UnityPy`), compare
it, and only then promote it to `data/`:

```
python tools/extract_version.py
python tools/diff_versions.py data research/<version> --out research/<version>/DIFF.md
```

The study and migration steps are in `docs/UPDATE_<version>.md` (latest: `docs/UPDATE_1.2.8.md`).
Tests: `python -m unittest discover -s tests -v` (uses a copy of the newest snapshot made by
`python tools/save_lab.py snapshot`).

If an update changes the `SystemInfo` **HMAC key**, `python tools/save_lab.py info <copy>` stops
saying "OK"; the key must then be read from a copy of the game binary (`docs/SAVE_PORTING.md`).
**Do not inject a DLL/trainer into the game on 1.2.x**: its anti-cheat detects it, reports it and
closes the game.

## How validation works

`material → MaterialInfoData (type + group) → StatModGroupInfoData (StatModKey + tier per GearGroup)
→ StatModInfoData (StatType, ModType, Value range per tier)`. The item's GearGroup
(WEAPON/ARMOR/ACCESSORY) comes from the ItemKey range. The editor only allows combinations that
exist in the game, so the resulting enchantments are legitimate.
