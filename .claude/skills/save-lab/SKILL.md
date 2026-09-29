---
name: save-lab
description: Laboratório de saves do Taskbar Hero. Use antes de ler, comparar, testar ou editar um arquivo de save (.es3), ao investigar um save que o jogo recusou, ou ao mexer no caminho de gravação do editor (core/es3.py, rotas de edição e /api/save do server.py).
---

# Save lab

Todo experimento com save acontece numa **cópia** no lab (`~/tbh_re/saves/`), via
`tools/save_lab.py`, que recusa gravar dentro da pasta do save vivo ou do jogo. Use só os passos
que a tarefa pede; toda escrita termina no passo 4.

## Passos

1. **Snapshot** — `python tools/save_lab.py snapshot` (só o vivo) ou `snapshot --all` (vivo +
   todos os backups que o jogo mantém: são os saves das versões anteriores). Pronto quando cada
   arquivo sai com `ver=<versão>` (uma linha "ERRO na copia" = o jogo gravava naquele instante;
   rode de novo).
2. **Inspecionar** — `info <cópia>` (versão, data do save, HMAC do SystemInfo, topo do
   PlayerSaveData) e `dump <cópia> --out <dir>` (account.json / player.json legíveis). Pronto
   quando você sabe a versão e o estado do HMAC. HMAC "FALHOU" num save que o jogo aceitou =
   chave nova → skill `game-update`.
3. **Comparar** — `schema <a> --vs <b>` lista os caminhos de account+player que entraram (+),
   saíram (-) ou mudaram de tipo (~); `coverage <cópia> [--data research/<versão>]` lista IDs
   que os dados não conhecem e diz o que checou e o que não checou. Pronto quando cada linha
   +/-/~ e cada ID desconhecido tem explicação ou virou pergunta.
4. **Provar a escrita** — toda mudança no caminho de gravação termina com
   `roundtrip <cópia>`: exit 0 = "HMAC do original: OK", "HMAC do regravado: OK" e "conteudo
   identico: sim" (comparação estrita, troca de tipo conta). Para testar uma edição, aplique-a em
   memória sobre a cópia (`es3.SaveFile.load`), grave `to_es3_bytes()` num arquivo do lab, rode
   `info` nele e compare o resto do JSON com o original: só o que você editou pode mudar.
5. **Entregar** — gravar no save vivo segue a regra do CLAUDE.md ("O save do usuário é
   produção").

## Referência

- Formato e chaves: [docs/SAVE_PORTING.md](../../../docs/SAVE_PORTING.md) (ES3 AES-128-CBC com
  IV nos 16 primeiros bytes; `AccountSaveData`/`PlayerSaveData` são strings com JSON aninhado;
  `SystemInfo` = HMAC).
- Regravar reserializa com `separators=(",", ":")`; só a notação de alguns floats muda
  (`1E+09` → `1000000000.0`, dígitos finais de doubles longos). É o mesmo double e o jogo aceita
  — por isso "string identica: nao" é esperado.
- Backups que o próprio jogo grava na pasta do save: `Live_daily_*.es3`,
  `SaveFile_Live_N.es3.bak` (rotativo), `SaveFile_Live_backup_*.es3`,
  `SaveFile_Live_BackendBackUp.es3`. `SaveFile_Live.es3.bak` é o do editor e guarda só o estado
  de antes do ÚLTIMO Salvar — o ponto de volta confiável é um snapshot.
- Tempos (`lastSavedTime`, `LastDailyBackUpTime`...) são `DateTime.Ticks` do .NET (100 ns desde
  0001-01-01); `info` converte.
