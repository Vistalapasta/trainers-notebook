"""Versão desktop (Windows): o app numa janela própria (pywebview + WebView2), sem terminal nem navegador.

O servidor Flask roda por dentro, numa porta fixa (a mesma sempre, para o navegador interno lembrar tema e filtros;
se ela estiver ocupada, o programa já está aberto). Os dados ficam em %APPDATA%\\Trainer's Notebook (caminhos.py).
O modo mini é uma segunda janela, sempre por cima (como o PowerToys fazia): janela separada, não toca no jogo.
As notificações saem pelo Windows (winotify), porque a janela não tem as notificações do navegador.

Empacotado por ferramentas/empacotar.py. Para testar sem empacotar (no Windows): python desktop.py
"""
import ctypes
import socket
import sys
import threading

import webview
from werkzeug.serving import make_server

import clipboard
from app import app
from caminhos import DADOS, PROGRAMA

PORTA = 53817
TITULO = "Trainer's Notebook"
ICONE = PROGRAMA / "static" / "icone.png"

janelas = {"principal": None, "mini": None}


def em_paralelo(funcao):
    """Mexer na janela de dentro de uma chamada da página trava o programa (a chamada espera a janela e a janela
    espera a chamada): faz a mudança numa thread à parte e responde à página na hora."""
    threading.Thread(target=funcao, daemon=True).start()


class Api:
    """Funções que as páginas chamam por window.pywebview.api."""

    def notificar(self, titulo, texto):
        from winotify import Notification
        Notification(app_id=TITULO, title=titulo, msg=texto, icon=str(ICONE)).show()

    def por_cima(self, ligar):
        mini = janelas["mini"]
        if mini:
            em_paralelo(lambda: setattr(mini, "on_top", bool(ligar)))
        return bool(ligar)

    def mostrar_principal(self):
        principal = janelas["principal"]
        if principal:
            em_paralelo(lambda: (principal.restore(), principal.show()))


def abrir_mini():
    """Chamado pela rota /api/abrir-mini (botão "Modo mini")."""
    if janelas["mini"]:
        janelas["mini"].restore()
        janelas["mini"].show()
        return
    mini = webview.create_window(f"{TITULO} · mini", f"http://127.0.0.1:{PORTA}/mini", js_api=Api(),
                                 width=360, height=620, min_size=(280, 300), on_top=True)
    mini.events.closed += lambda: janelas.update(mini=None)
    janelas["mini"] = mini


def aviso(texto):
    ctypes.windll.user32.MessageBoxW(None, texto, TITULO, 0x40)


def main():
    try:
        servidor = make_server("127.0.0.1", PORTA, app, threaded=True)
    except OSError:
        aviso("O Trainer's Notebook já está aberto.")
        sys.exit(0)
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    clipboard.iniciar()
    app.config["ABRIR_MINI"] = abrir_mini

    webview.settings["OPEN_EXTERNAL_LINKS_IN_BROWSER"] = True  # wiki, vídeos e créditos abrem no navegador
    webview.settings["ALLOW_DOWNLOADS"] = True                 # Exportar CSV
    principal = webview.create_window(TITULO, f"http://127.0.0.1:{PORTA}/", js_api=Api(),
                                      width=1360, height=880, min_size=(760, 500))
    janelas["principal"] = principal

    def ao_fechar_principal():
        if janelas["mini"]:
            janelas["mini"].destroy()
    principal.events.closed += ao_fechar_principal

    # private_mode=False: guarda o localStorage (tema, filtros) entre uma abertura e outra
    webview.start(private_mode=False, storage_path=str(DADOS / "webview"))
    servidor.shutdown()


if __name__ == "__main__":
    main()
