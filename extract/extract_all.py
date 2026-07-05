"""
Orquestra toda a extracao de dados do jogo (roda 1x numa maquina com o Taskbar Hero
instalado + UnityPy). Gera data/ com tabelas, nomes, enums e icones — depois disso a
app (server.py + web/ + data/) e portavel e roda sem o jogo nem dependencias.

Uso:  python extract/extract_all.py
Requer:  pip install UnityPy   (so para a extracao; a app em si nao precisa)
"""
import extract_tables
import extract_enums
import extract_localization
import extract_sprites

if __name__ == "__main__":
    print("== 1/4 tabelas CSV ==");        extract_tables.main()
    print("\n== 2/4 enums do dump ==");     extract_enums.main()
    print("\n== 3/4 localizacao (nomes) =="); extract_localization.main()
    print("\n== 4/4 icones ==");            extract_sprites.main()
    print("\nOK. Dados em saveEditor/data/. Rode 'python server.py'.")
