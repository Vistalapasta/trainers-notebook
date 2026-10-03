# Trainer's Notebook

Caderno do treinador para o **otPokemon**: acompanha os preços do market a partir dos prints que você tira e ajuda a
decidir quando comprar. Também monta times, ajuda no breeding, calcula o lucro do farm e lista as quests.

Programa de fã, **gratuito e não oficial**. Não tem ligação com The Pokémon Company, Nintendo, Game Freak, Creatures,
nem com o otPokemon ou a sua equipe.

## Baixar

Na página de [Releases](../../releases), baixe o `.zip` da versão mais recente, descompacte e abra
`Trainers Notebook.exe` (Windows 10 ou 11).

Na primeira vez o Windows pode avisar que o editor é desconhecido, porque o programa não tem assinatura digital:
clique em **Mais informações** e **Executar assim mesmo**. Cada release traz o link da verificação no VirusTotal.

Os seus dados ficam em `%APPDATA%\Trainer's Notebook` e não somem ao atualizar o programa.

## O que ele faz

- **Mercado**: registra preços pelo print do market (Win+Shift+S; a leitura do texto é feita no seu computador),
  mostra preço de mercado, médias, sinal de compra, alertas, volume à venda e quando os itens costumam ficar mais baratos.
  **Farm**: anote drops e gastos de cada caçada e compare o lucro por hora.
- **Pokémon**: ficha de cada pokémon (perfil tanque ou atacante, tipagem, nature, TMs e Move Tutor), montagem de times
  com o custo em HD e breeding (casal, o que nasce, nature, ball, ovos e Day Care).
- **Jogo**: as quests da wiki, para marcar as que você já fez.
- **Cronômetros** que você inicia e avisam quando acabam, e um **modo mini** para deixar por cima do jogo.

## O que ele não faz

O programa **não interage com o jogo**: não clica, não aperta teclas, não envia comandos, não lê nem altera a memória,
os arquivos ou a conexão do cliente, não tira print sozinho e não automatiza nenhuma ação (comprar, vender, andar,
caçar). Ele só lê os prints que você mesmo tira. Também não serve para vender itens por dinheiro real.

O uso e a distribuição gratuita foram conferidos com a staff do otPokemon, **desde que o programa continue assim**.
Só a versão publicada aqui foi conferida; versões modificadas por outras pessoas podem não seguir essas regras.

## Rodar pelo código

Precisa de Python 3.13 ou mais novo.

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt   # no Windows: .venv\Scripts\pip
.venv/bin/python run.py                     # abre em http://localhost:5000
```

A versão desktop (janela própria, `desktop.py`) é empacotada por `ferramentas/empacotar.py`.

## Problemas e ideias

Achou um erro ou tem uma sugestão? Mande pelo [formulário](https://docs.google.com/forms/d/e/1FAIpQLSe8dEuFWtZ10hLPwnk9UNeDvFbMa73l7XBLzDRhmPGIjUsMcA/viewform)
(não precisa de conta; no programa: ⓘ > Enviar problema ou ideia) ou abra uma [issue](../../issues).

## Créditos e licenças

- **Código**: [PolyForm Noncommercial 1.0.0](LICENSE.md). Pode usar, estudar, modificar e compartilhar, **sem fins
  comerciais**. Sem garantia: o autor não responde pelo uso do programa nem por versões modificadas.
- **Retratos e sprites**: [PMD Sprite Repository](https://sprites.pmdcollab.org/)
  ([PMDCollab/SpriteCollab](https://github.com/PMDCollab/SpriteCollab)), licença
  [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/). Créditos de cada artista na ficha do pokémon, no
  botão ⓘ > Créditos e em `static/pmd/spritebot_credits.txt`. Modificação: dos sprites só é usada a animação parada,
  virada para a frente.
- **Dados**: [wiki do otPokemon](https://wiki.otponline.com/) e [PokéAPI](https://pokeapi.co/). Os vídeos das quests
  são dos criadores no YouTube, com os links publicados na wiki.
- **Fonte**: Atkinson Hyperlegible (Braille Institute), SIL Open Font License (`static/fontes/`).
- **Bibliotecas**: [Flask](https://flask.palletsprojects.com/), [RapidOCR](https://github.com/RapidAI/RapidOCR) (com os
  modelos do PaddleOCR), [ONNX Runtime](https://onnxruntime.ai/), [pywebview](https://pywebview.flowrl.com/),
  [winotify](https://github.com/versa-syahptr/winotify) e [Chart.js](https://www.chartjs.org/) (`static/chart.umd.min.js`, MIT).
  O zip da versão desktop traz as licenças de todas em `LICENCAS-DE-TERCEIROS.txt`.
- Pokémon e os nomes dos pokémon são marcas de The Pokémon Company, Nintendo, Game Freak e Creatures.
