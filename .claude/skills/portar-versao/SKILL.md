---
name: portar-versao
description: Executa a migração do editor para uma versão do jogo já estudada em docs/UPDATE_<versão>.md (ex. /portar-versao 1.2.8).
argument-hint: "<versão do jogo, ex 1.2.8>"
disable-model-invocation: true
---

# Portar o editor para a versão $ARGUMENTS

Plano, achados e decisões: `docs/UPDATE_$ARGUMENTS.md`. Dados já extraídos:
`research/$ARGUMENTS/`. Regras do save e invariantes de escrita: CLAUDE.md. Se `$ARGUMENTS`
veio vazio, pergunte a versão antes de tudo.

## Passos

1. **Pré-condições** — leia `docs/UPDATE_$ARGUMENTS.md` inteiro. Pergunta sem resposta na seção
   de decisões → resolva com a skill `grilling` antes de codar. `git status --porcelain` não vazio
   → pare e pergunte ao usuário o que versionar (ferramentas, skills e `research/` podem ainda não
   estar no git, e `research/$ARGUMENTS/` é insumo do passo 3); nunca limpe a árvore com
   stash/clean/checkout/reset. Crie a branch `port-$ARGUMENTS`. Pronto quando a branch existe e
   toda decisão do plano está respondida.
2. **Rede de segurança** — antes de mudar comportamento, crie `tests/__init__.py` e testes
   unittest (stdlib) sobre um snapshot fresco (`python tools/save_lab.py snapshot`): roundtrip sem
   edição, cada rota de edição do `server.py` aplicada em memória + HMAC + "nada além do editado
   mudou" + campos novos preservados. Bug conhecido do plano entra como
   `@unittest.expectedFailure` com o motivo. Skill `tdd` para as seams. Pronto quando
   `python -m unittest discover -s tests -v` sai 0 com "Ran N tests" (N ≥ 1 + nº de rotas de
   edição) e cada expectedFailure está listado no plano.
3. **Dados** — promova `research/$ARGUMENTS/` para `data/` no layout atual (tabelas que o editor
   usa + as que o plano manda usar, nomes, textos, ícones, `enums.json`) e grave `data/VERSION`.
   O `data/` antigo continua no histórico do git. Pronto quando
   `save_lab.py coverage <snapshot> --data data` só lista o que o plano explica.
4. **Código** — implemente os itens do plano na ordem de prioridade (P0 → P3), um commit por
   item, com o teste correspondente passando (e o expectedFailure dele virando teste normal).
   Depois de mexer em código: `graphify update .`.
5. **Verificar** — `python -m compileall -q server.py core tools`,
   `python -m unittest discover -s tests -v`, `save_lab.py roundtrip` num snapshot novo, e o editor
   de pé numa **cópia**: `TBH_NO_BROWSER=1 python server.py`, carregue a cópia pelo campo de
   caminho (ele vem preenchido com o save VIVO) ou `POST /api/load {"path": "<cópia>"}`, confira
   `GET /api/state` antes de qualquer Salvar e exercite cada tela alterada.
6. **Revisar** — rode `/code-review` no diff da branch com atenção às invariantes do CLAUDE.md;
   corrija o que for confirmado.
7. **Documentar** — CLAUDE.md ("Estado das versões"), README ("extracted from version"),
   `docs/UPDATE_$ARGUMENTS.md` (marque o que foi feito e o que ficou para depois).
8. **Teste no jogo (usuário)** — entregue um roteiro curto: fechar o jogo;
   `python tools/save_lab.py snapshot` (anote a pasta: é o ponto de volta); abrir o editor, fazer
   UMA edição e Salvar UMA vez; abrir o jogo e conferir. Para voltar: com o jogo fechado, copiar o
   `SaveFile_Live.es3` daquele snapshot por cima, conferindo antes a data com `save_lab.py info`
   (o `.es3.bak` guarda só o estado de antes do ÚLTIMO Salvar). Você não grava o save vivo nesta
   skill.

Rodar `/portar-versao` autoriza commits locais na branch `port-$ARGUMENTS` (um por item); push e
merge só quando o usuário pedir. Ao terminar, resuma o que mudou, o que foi testado e o que o
usuário precisa conferir no jogo.
