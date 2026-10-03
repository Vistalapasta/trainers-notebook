"""Gera a versão desktop para Windows: dist/Trainers Notebook-<data>.zip (pasta com "Trainers Notebook.exe").

Roda no WSL, mas o empacotamento (PyInstaller) precisa acontecer no Windows: o script copia os arquivos do programa
para uma pasta do Windows, cria lá um ambiente Python com as dependências (na primeira vez) e chama o PyInstaller.

Precisa do Python 3.13 instalado no Windows só para o usuário (python.org, em %LOCALAPPDATA%\\Programs\\Python\\Python313).
Rodar: .venv/bin/python ferramentas/empacotar.py
Com --instalar, também atualiza a cópia que o usuário usa (%LOCALAPPDATA%\\Programs\\Trainers Notebook, a do atalho
da área de trabalho, criado se não existir). O programa precisa estar fechado.
"""
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from versao import FORMULARIO, REPOSITORIO, VERSAO  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
NOME = "Trainers Notebook"
# Arquivos do programa que vão para o pacote (dados do usuário, ferramentas e caches ficam de fora)
ARQUIVOS = ["app.py", "db.py", "caminhos.py", "versao.py", "clipboard.py", "leitor_print.py", "desktop.py", "templates", "static"]
DEPENDENCIAS = ["flask", "rapidocr", "onnxruntime", "pillow", "numpy", "pywebview", "winotify", "pyinstaller", "pip-licenses"]
# Usados só para empacotar: não vão no programa, então ficam fora da lista de licenças
SO_PARA_EMPACOTAR = ["pyinstaller", "pyinstaller-hooks-contrib", "altgraph", "pefile", "pywin32-ctypes", "packaging",
                     "setuptools", "pip", "pip-licenses", "prettytable", "wcwidth", "tomli"]


def windows(comando):
    """Saída de um comando do cmd.exe, sem o \\r."""
    return subprocess.run(["cmd.exe", "/c", comando], capture_output=True, text=True, cwd="/mnt/c").stdout.strip()


def caminho_wsl(caminho_windows):
    return Path(subprocess.run(["wslpath", "-u", caminho_windows], capture_output=True, text=True, check=True).stdout.strip())


def rodar(exe, *args, pasta):
    print("›", Path(exe).name, *args, flush=True)
    subprocess.run([str(exe), *args], cwd=pasta, check=True)


def main():
    local = windows("echo %LOCALAPPDATA%")
    python = caminho_wsl(local + r"\Programs\Python\Python313\python.exe")
    if not python.exists():
        sys.exit("Python 3.13 não encontrado no Windows (%LOCALAPPDATA%\\Programs\\Python\\Python313).")
    base = caminho_wsl(local) / "TrainersNotebook-build"
    fonte, venv = base / "src", base / "venv"
    pip, py = venv / "Scripts" / "pip.exe", venv / "Scripts" / "python.exe"

    # 1. Copia os arquivos do programa (sempre do zero, para não levar sobra de versões antigas)
    shutil.rmtree(fonte, ignore_errors=True)
    fonte.mkdir(parents=True)
    for nome in ARQUIVOS:
        origem = RAIZ / nome
        if origem.is_dir():
            shutil.copytree(origem, fonte / nome, ignore=shutil.ignore_patterns("__pycache__"))
        else:
            shutil.copy2(origem, fonte / nome)

    # 2. Ambiente Python no Windows (só na primeira vez; apagar a pasta venv para reinstalar as dependências)
    if not py.exists():
        rodar(python, "-m", "venv", str(venv_windows(venv)), pasta=base)
        rodar(py, "-m", "pip", "install", "--upgrade", "pip", pasta=base)
        rodar(pip, "install", *DEPENDENCIAS, pasta=base)
        # O RapidOCR baixa os modelos na primeira vez que é usado: baixa agora, para irem dentro do pacote
        rodar(py, "-c", "from rapidocr import RapidOCR; RapidOCR()", pasta=base)

    # 3. PyInstaller: pasta com o .exe (sem console), os arquivos do programa e os modelos do OCR
    src = venv_windows(fonte)  # caminhos completos: o PyInstaller lê os relativos a partir da pasta do .spec
    rodar(py, "-m", "PyInstaller", "--noconfirm", "--clean", "--windowed", "--name", NOME,
          "--icon", src + r"\static\icone.ico",
          "--add-data", src + r"\templates;templates", "--add-data", src + r"\static;static",
          "--collect-data", "rapidocr", "--collect-binaries", "onnxruntime",
          "--distpath", r"..\dist", "--workpath", r"..\work", "--specpath", r"..\work",
          "desktop.py", pasta=fonte)

    # 4. Zip para distribuir (com os créditos do PMDCollab e um leia-me ao lado do .exe)
    pasta = base / "dist" / NOME
    shutil.copy2(RAIZ / "static" / "pmd" / "spritebot_credits.txt", pasta / "spritebot_credits.txt")
    # Licenças das bibliotecas que vão dentro do .exe (algumas, como a Apache 2.0 do RapidOCR, pedem o texto junto)
    if not (venv / "Scripts" / "pip-licenses.exe").exists():
        rodar(pip, "install", "pip-licenses", pasta=base)
    rodar(venv / "Scripts" / "pip-licenses.exe", "--from=mixed", "--with-urls", "--with-license-file", "--no-license-path",
          "--format=plain-vertical", "--ignore-packages", *SO_PARA_EMPACOTAR,
          "--output-file", venv_windows(pasta / "LICENCAS-DE-TERCEIROS.txt"), pasta=base)
    (pasta / "LICENCA.md").write_text((RAIZ / "LICENSE.md").read_text(encoding="utf-8"), encoding="utf-8")
    (pasta / "LEIA-ME.txt").write_text(LEIA_ME.format(versao=VERSAO, repositorio=REPOSITORIO, formulario=FORMULARIO), encoding="utf-8")
    saida = RAIZ / "dist" / f"{NOME} {VERSAO}.zip"
    saida.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(saida, "w", zipfile.ZIP_DEFLATED) as z:
        for arq in pasta.rglob("*"):
            z.write(arq, Path(NOME) / arq.relative_to(pasta))
    print(f"\nPronto: {saida.relative_to(RAIZ)} ({saida.stat().st_size / 1e6:.0f} MB)")
    print(f"Para testar sem descompactar: {pasta}")
    if "--instalar" in sys.argv:
        instalar(pasta, local)


def instalar(pasta, local):
    """Copia a pasta do programa para %LOCALAPPDATA%\\Programs e cria o atalho na área de trabalho."""
    destino = caminho_wsl(local) / "Programs" / NOME
    shutil.rmtree(destino, ignore_errors=True)
    shutil.copytree(pasta, destino)
    exe = venv_windows(destino / f"{NOME}.exe")
    subprocess.run(["powershell.exe", "-NoProfile", "-Command",
                    "$a = (New-Object -ComObject WScript.Shell).CreateShortcut("
                    "[Environment]::GetFolderPath('Desktop') + '\\Trainer''s Notebook.lnk'); "
                    f"$a.TargetPath = '{exe}'; $a.WorkingDirectory = '{venv_windows(destino)}'; "
                    f"$a.IconLocation = '{exe},0'; $a.Description = 'Caderno do treinador para o otPokemon'; $a.Save()"],
                   check=True, cwd="/mnt/c")
    print(f"Instalado em {destino} (atalho \"Trainer's Notebook\" na área de trabalho)")


def venv_windows(caminho):
    return subprocess.run(["wslpath", "-w", str(caminho)], capture_output=True, text=True, check=True).stdout.strip()


LEIA_ME = """Trainer's Notebook {versao}
========================

Caderno do treinador para o otPokemon: acompanha os preços do market pelos prints que você tira, ajuda a montar
times, breeding, farm e quests. Programa de fã, gratuito e não oficial (veja "Sobre", no botão ⓘ).

Como usar
- Descompacte a pasta e abra "Trainers Notebook.exe". Na primeira vez o Windows pode avisar que o editor é
  desconhecido: clique em "Mais informações" e "Executar assim mesmo".
- Os seus dados ficam em %APPDATA%\\Trainer's Notebook (não somem ao atualizar o programa).
- O programa não mexe no jogo: não clica, não aperta teclas, não lê a memória nem tira print sozinho.
  Ele só lê os prints que você tira (Win+Shift+S).

Créditos
- Retratos e sprites do PMDCollab (https://sprites.pmdcollab.org/), licença CC BY-NC 4.0: uso não comercial,
  com crédito aos artistas. Créditos completos em spritebot_credits.txt, nesta pasta, e no botão ⓘ > Créditos.
- Dados da wiki do otPokemon e da PokéAPI.

Código aberto, licença PolyForm Noncommercial 1.0.0 (uso livre, sem fins comerciais, sem garantia): LICENCA.md.
Bibliotecas usadas e as suas licenças: LICENCAS-DE-TERCEIROS.txt.
Versão oficial e atualizações: {repositorio}
Problemas e ideias: {formulario} (ou ⓘ > Enviar problema ou ideia, no programa)
Versões modificadas por outras pessoas não foram conferidas com a staff do otPokemon.
"""

if __name__ == "__main__":
    main()
