"""Recebe os prints copiados no Windows (Win+Shift+S) sem precisar salvar arquivo.

No WSL (run.py), roda o vigiar_clipboard.ps1 pelo powershell.exe do Windows. Na versão desktop (Windows), vigia
a área de transferência pelo próprio Python, do mesmo jeito: quando o número de sequência dela muda e há uma imagem,
salva como PNG. Guarda o nome da última captura para a página buscar.
"""
import atexit
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

from caminhos import DADOS

PASTA = DADOS / "capturas"
SCRIPT = Path(__file__).parent / "vigiar_clipboard.ps1"
DIAS_GUARDANDO = 7

_lock = threading.Lock()
_capturas = []  # nomes dos arquivos, na ordem em que chegaram


def ultima_depois(indice):
    """Devolve (indice, nome) da captura mais recente após `indice`, ou None."""
    with _lock:
        if len(_capturas) > indice:
            return len(_capturas), _capturas[-1]
    return None


def total():
    with _lock:
        return len(_capturas)


def _limpar_antigas():
    limite = time.time() - DIAS_GUARDANDO * 86400
    for arquivo in PASTA.glob("captura-*.png"):
        if arquivo.stat().st_mtime < limite:
            arquivo.unlink()


def _caminho_windows(caminho):
    return subprocess.run(["wslpath", "-w", str(caminho)], capture_output=True, text=True, check=True).stdout.strip()


def _ler_saida(processo):
    for linha in processo.stdout:
        nome = linha.strip()
        if nome.startswith("captura-") and (PASTA / nome).exists():
            with _lock:
                _capturas.append(nome)


def _vigiar_windows():
    """Versão desktop: o mesmo laço do vigiar_clipboard.ps1, em Python."""
    import ctypes
    from PIL import Image, ImageGrab
    sequencia = ctypes.windll.user32.GetClipboardSequenceNumber
    ultimo = sequencia()
    while True:
        time.sleep(0.5)
        atual = sequencia()
        if atual == ultimo:
            continue
        ultimo = atual
        try:
            imagem = ImageGrab.grabclipboard()
        except Exception:
            ultimo = 0  # área de transferência ocupada por outro programa: tenta no próximo ciclo
            continue
        if not isinstance(imagem, Image.Image):
            continue
        nome = f"captura-{datetime.now():%Y%m%d-%H%M%S-%f}"[:-3] + ".png"
        imagem.save(PASTA / nome)
        with _lock:
            _capturas.append(nome)


def iniciar():
    """Inicia o vigia. Devolve False se não estiver no WSL/Windows."""
    if sys.platform != "win32" and not shutil.which("powershell.exe"):
        return False
    PASTA.mkdir(exist_ok=True)
    _limpar_antigas()
    if sys.platform == "win32":
        threading.Thread(target=_vigiar_windows, daemon=True).start()
        return True
    processo = subprocess.Popen(
        ["powershell.exe", "-NoProfile", "-STA", "-ExecutionPolicy", "Bypass",
         "-File", _caminho_windows(SCRIPT), "-Pasta", _caminho_windows(PASTA)],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
    )
    atexit.register(processo.terminate)
    threading.Thread(target=_ler_saida, args=(processo,), daemon=True).start()
    return True
