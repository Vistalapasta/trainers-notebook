"""Inicia o app. Depois, abra http://localhost:5000 no navegador."""
import threading
import webbrowser

import clipboard
from app import app

PORTA = 5000

if __name__ == "__main__":
    if clipboard.iniciar():
        print("Vigiando a área de transferência: prints do Win+Shift+S vão direto para o app.")
    print(f"App rodando em http://localhost:{PORTA}  (Ctrl+C para parar)")
    threading.Timer(1, lambda: webbrowser.open(f"http://localhost:{PORTA}")).start()
    app.run(host="127.0.0.1", port=PORTA)
