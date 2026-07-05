"""
Extrai as tabelas de dados (TextAssets CSV) de sharedassets0.assets para data/tables/.
Roda 1x numa maquina com o jogo instalado + UnityPy (pip install UnityPy).
O resultado (data/tables/*.csv) e portavel e vai junto com a app.
"""
import os
import UnityPy

GAME_DATA = r"C:\Program Files (x86)\Steam\steamapps\common\TaskbarHero\TaskBarHero_Data"
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "tables")

# Tabelas necessarias para itens + encantamentos (e algumas extras uteis).
WANTED = {
    "GearInfoData", "GearTypeInfoData", "GearTypeScaleInfoData", "ItemTypeScaleInfoData",
    "MaterialInfoData", "StatModInfoData", "StatModGroupInfoData", "GradeInfoData",
    "AttributeGroupInfoData", "InventoryInfoData", "SynthesisRecipeInfoData",
    "RuneInfoData", "RuneLevelInfoData", "CurrencyInfoData", "HeroInfoData",
}


def main():
    os.makedirs(OUT, exist_ok=True)
    env = UnityPy.load(os.path.join(GAME_DATA, "sharedassets0.assets"))
    found = 0
    for obj in env.objects:
        if obj.type.name != "TextAsset":
            continue
        d = obj.read()
        name = d.m_Name
        if name not in WANTED:
            continue
        raw = d.m_Script
        if isinstance(raw, str):
            raw = raw.encode("utf-8", "surrogateescape")
        path = os.path.join(OUT, name + ".csv")
        with open(path, "wb") as fh:
            fh.write(bytes(raw))
        print(f"  {name}.csv  ({len(raw)} bytes)")
        found += 1
    print(f"\nExtraidas {found}/{len(WANTED)} tabelas para {OUT}")


if __name__ == "__main__":
    main()
