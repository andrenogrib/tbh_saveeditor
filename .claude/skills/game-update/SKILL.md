---
name: game-update
description: Estuda uma atualização do Taskbar Hero e escreve o plano de migração em docs/UPDATE_<versão>.md. Use quando a versão instalada difere da de data/, quando o save traz ID ou campo que o editor não conhece, ou quando a chave HMAC / senha ES3 para de conferir.
---

# Game update

Uma atualização pode mexer em quatro camadas, da mais rara à mais comum: **senha ES3**,
**chave HMAC** do `SystemInfo`, **esquema do save** (campos novos) e **dados** (tabelas, textos,
ícones, enums). Esta skill extrai, compara, entende e **planeja**; quem migra é a
`/portar-versao`, que só o usuário dispara. Aqui você não altera `data/` nem o código do editor.

## Passos

1. **Versão e chaves** — `python tools/save_lab.py snapshot --all` (os backups diários do jogo
   são os saves das versões anteriores) e `info` no `SaveFile_Live.es3` do snapshot. Pronto
   quando você sabe a versão do jogo (`tools/tbh_paths.py` → `game_version()`), a do save e se o
   HMAC confere. Não conferiu → [RE.md](RE.md), "Chave HMAC".
2. **Dump do código** — `python tools/il2cpp_dump.py --split` e depois
   `graphify update $HOME/tbh_re/<versão>/game_src` (grafo do jogo). Pronto quando
   `graphify explain "PlayerSaveData" --graph $HOME/tbh_re/<versão>/game_src/graphify-out/graph.json`
   responde.
3. **Extrair os dados** — `python tools/extract_version.py` → `research/<versão>/`. Se essa
   pasta já existe, extraia em `--out research/<versão>-<AAAAMMDD>` e compare; não sobrescreva.
   Pronto quando o comando sai com código 0, `VERSION` lista `enums,icons,loc,tables` e a saída
   não tem "PULADO".
4. **Comparar** — `python tools/diff_versions.py data research/<versão> --out
   research/<versão>/DIFF.md` (nome novo se já existir); `save_lab.py coverage <snapshot> --data
   research/<versão>`; `save_lab.py schema <save-da-versão-anterior> --vs <snapshot>`. Tabela que
   só existe em `research/` pode ser apenas "não extraída antes": chame de nova só com evidência
   (strings novas, histórico de saves). Pronto quando DIFF.md existe, o coverage só lista IDs que
   você explica e cada linha +/-/~ do schema está anotada.
5. **Entender** — para cada mudança que o editor consome (membro novo ou valor mudado em enum,
   coluna nova ou faixa alterada em tabela lida pelo editor, IDs novos, campos novos no save), ache
   a semântica no código do jogo pelo grafo e pelo `dump.cs`. Registre em
   `docs/UPDATE_<versão>.md`: achados com evidência, riscos, plano priorizado e decisões do
   usuário. Pronto quando todo item do DIFF que toca o editor tem veredito.
6. **Entregar o plano** — pronto quando `docs/UPDATE_<versão>.md` tem veredito para todo item e
   as decisões pendentes listadas. Peça ao usuário para rodar `/portar-versao <versão>`.

## Referência

- Enum que muda de número é bug silencioso: o save guarda números (`StatType`, `ModType`,
  `RecipeType`), as tabelas guardam nomes. `diff_versions.py` marca "VALOR MUDOU";
  `enums_all.json` traz todos os enums do jogo para comparar entre versões.
- Nomes ofuscados NÃO são estáveis entre versões: o gerenciador do save / keystore era
  `bal`/`bam` na 1.00.17 e é `bde`/`bdf` na 1.2.8 (`bal`/`bam` viraram classes de buff).
  Reidentifique cada classe por consts (`"SystemInfo"`), campos, `[JsonProperty]` e vizinhos no
  grafo, nunca pelo nome antigo.
- Engenharia reversa (dump, grafo do jogo, gerenciador do save, chave HMAC, senha ES3):
  [RE.md](RE.md).
