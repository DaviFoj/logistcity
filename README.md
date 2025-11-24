# LogistiCity

<img src="assets/logo.png" alt="LogistiCity Logo" width="300"/>

Simulação casual sobre logística urbana, escrita em Python com pygame. O jogador recebe lotes aleatórios de caixas e escolhe algoritmos de ordenação (Bubble, Selection, Insertion ou Quick) para organizar o carregamento antes que o cronômetro termine. O projeto inclui HUD completa, tela de pausa, tela de placar e persistência em JSON para configurações e estatísticas.

## Pré-requisitos

- Python 3.12+
- pip
- pygame (incluído no `requirements.txt`)

## Instalação

```bash
python -m venv venv
.\venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Executando

```bash
.\venv\Scripts\python main.py
```

### Controles principais

- **Jogar / Pausar:** botão de pause no canto superior esquerdo.
- **Escolha de algoritmo:** clique em um dos cards na parte inferior.
- **Opções / Abandonar:** use o modal de pausa.
- **Mudo/Desmudo:** ícone de som no canto superior direito do menu.

## Estrutura

- `main.py`: ponto de entrada, alterna entre menu e gameplay.
- `src/ui/menu.py`: menu principal com iconografia e toggle de música.
- `src/ui/gameplay.py`: lógica visual do modo padrão, efeitos, HUD, tela de placar.
- `src/game/mode_padrao.py`: núcleo da simulação (lotes, stats, timers).
- `src/algorithms/sorting.py`: implementações instrumentadas dos algoritmos.
- `src/utils/storage.py`: leitura/escrita do arquivo `save/game_state.json`.
- `assets/`: sprites, sons UI e trilhas em loop.

## Licença dos assets

Ver `assets/sounds/UI Soundpack/readme.txt` para crédito do Universal UI Soundpack (CC BY 4.0). Trilha musical proveniente do “Music Loop Bundle – Troubadeck”.

## Créditos

- **Desenvolvimento e arte:** Davi Jorge
- **Desenvolvimento:** Gabriela Mattusack
