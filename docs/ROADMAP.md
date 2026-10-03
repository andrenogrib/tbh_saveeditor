# Próximas funções do editor

Levantamento de 2026-10-03, depois da migração para a 1.2.8. No save do usuário quase tudo o que
o editor mexe já está no teto: 6 heróis no 101 com a árvore de atributos inteira, cubo 100, pets
liberados, runas no máximo e encantamentos no valor máximo. O que falta é mais segurança e
conveniência do que poder.

## Vale incluir (ordem de prioridade)

| # | Função | Para quê | Risco para a conta | Estado |
|---|---|---|---|---|
| 1 | Ponto de volta automático a cada Salvar + lista para restaurar | o `.bak` guarda só o estado de antes do último Salvar | nenhum | **feito** (aba "Pontos de volta"; `~/tbh_re/editor_backups`, 30 mais novos) |
| 2 | Prévia do que vai mudar antes de Salvar | ver "ouro 66 M → X", "runa Y 1 → 3", "item Z slot 2: A → B" antes de gravar | nenhum | **feito** (o Salvar mostra a lista e pede confirmação; `GET /api/diff`) |
| 3 | Encantar itens da mochila e do baú | hoje a tela só mostra os equipados (a rota já aceita qualquer item) | o do encantamento de hoje (baixo–médio) | **feito** ("🎒 Mochila e baú" na lista de heróis; item do Trade Ship é só leitura) |
| 4 | Resumo da build por herói | soma dos encantamentos por atributo, para comparar os modos do auto-build | nenhum | **feito** (painel do herói) |
| 5 | Editor da árvore de atributos | redistribuir pontos ou outro save; no save atual não muda nada (tudo no máximo) | médio | não planejado |

## Não dá ou não vale

- **Plaguelands, estágios, skins, Contaminação:** ficam no servidor
  ([stages_plague](../research/1.2.8/analysis/stages_plague.md) §3–§4).
- **Criar/duplicar itens ou mudar quantidade de material:** o servidor apaga e registra; mexe na
  economia do Steam Market.
- **Receitas do cubo:** a que falta (Crafting 600091) libera no próprio jogo (cubo 90, custo 50.000).
- **Heróis e pets de DLC:** a posse é da Steam.
