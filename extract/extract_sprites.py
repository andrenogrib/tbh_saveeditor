"""
Extrai os icones dos itens/materiais de sharedassets0.assets -> data/icons/<ItemKey>.png.
Convencao de nome dos sprites: 'Item_<ItemKey>' (materiais) ou '<TIPO>_<GearKey>' (equipamentos).
Cobertura confirmada: 1 sprite por ItemKey, sem ambiguidade.
"""
import json
import os
import re
import UnityPy

GAME_DATA = r"C:\Program Files (x86)\Steam\steamapps\common\TaskbarHero\TaskBarHero_Data"
DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
ICONS = os.path.join(DATA, "icons")
SPRITE_RE = re.compile(r"^(?:Item|[A-Z]+)_(\d+)$")


def main():
    os.makedirs(ICONS, exist_ok=True)
    wanted = set(json.load(open(os.path.join(DATA, "names_en.json"), encoding="utf-8")).keys())
    env = UnityPy.load(os.path.join(GAME_DATA, "sharedassets0.assets"))
    icon_map = {}
    done = 0
    for obj in env.objects:
        if obj.type.name != "Sprite":
            continue
        try:
            sp = obj.read()
        except Exception:
            continue
        m = SPRITE_RE.match(sp.m_Name)
        if not m:
            continue
        key = m.group(1)
        if key not in wanted or key in icon_map:
            continue
        try:
            img = sp.image  # PIL Image recortada do atlas
            out = os.path.join(ICONS, key + ".png")
            img.save(out)
            icon_map[key] = key + ".png"
            done += 1
            if done % 100 == 0:
                print(f"  ...{done} icones")
        except Exception as e:
            print(f"  falha {key}: {e}")
    with open(os.path.join(DATA, "icon_map.json"), "w", encoding="utf-8") as fh:
        json.dump(icon_map, fh, ensure_ascii=False, indent=2)
    print(f"\nExtraidos {done} icones -> {ICONS}")


if __name__ == "__main__":
    main()
