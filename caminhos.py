"""Onde ficam os arquivos do programa e os dados do usuário.

- Rodando pelo código (WSL, run.py): tudo na pasta do projeto, como sempre.
- Versão desktop empacotada (PyInstaller, desktop.py): os arquivos do programa (templates, static) vêm de dentro do
  pacote e os dados do usuário (precos.db, capturas) ficam em %APPDATA%\\Trainer's Notebook, para atualizar ou trocar
  a versão do programa sem mexer nos dados.
"""
import os
import sys
from pathlib import Path

EMPACOTADO = getattr(sys, "frozen", False)
PROGRAMA = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
if EMPACOTADO:
    DADOS = Path(os.environ.get("APPDATA", Path.home())) / "Trainer's Notebook"
else:
    DADOS = Path(__file__).resolve().parent
DADOS.mkdir(parents=True, exist_ok=True)
