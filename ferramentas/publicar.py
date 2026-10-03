"""Publica uma versão no GitHub: atualiza o repositório público e cria a release com o zip da versão desktop.

O repositório público é uma cópia à parte (../trainers-notebook-publico), com histórico próprio:
- leva só os arquivos versionados aqui, menos os de EXCLUIR (o CLAUDE.md tem as anotações do projeto, com nomes e
  conversas de outras pessoas);
- os commits saem com o e-mail anônimo do GitHub (id+usuario@users.noreply.github.com), não com o e-mail pessoal.

Antes: commitar tudo aqui, mudar VERSAO em versao.py e gerar o zip (ferramentas/empacotar.py). Precisa do gh logado
(`gh auth login`). Na primeira vez cria o repositório público em REPOSITORIO (versao.py).

Rodar: .venv/bin/python ferramentas/publicar.py "o que mudou nesta versão" "link do VirusTotal do zip"
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
from versao import REPOSITORIO, VERSAO  # noqa: E402

PUBLICO = RAIZ.parent / "trainers-notebook-publico"
EXCLUIR = {"CLAUDE.md"}
ZIP = RAIZ / "dist" / f"Trainers Notebook {VERSAO}.zip"


def rodar(*args, pasta=PUBLICO, saida=False):
    r = subprocess.run(args, cwd=pasta, check=True, text=True, capture_output=saida)
    return r.stdout.strip() if saida else None


def main():
    novidades = sys.argv[1] if len(sys.argv) > 1 else f"Versão {VERSAO}"
    virustotal = sys.argv[2] if len(sys.argv) > 2 else ""
    if not virustotal.startswith("https://www.virustotal.com/"):
        sys.exit("Passe o link do VirusTotal do zip como segundo argumento.")
    if rodar("git", "status", "--porcelain", pasta=RAIZ, saida=True):
        sys.exit("Há mudanças não commitadas no projeto: commite antes de publicar.")
    if not ZIP.exists():
        sys.exit(f"Falta {ZIP.relative_to(RAIZ)}: rode ferramentas/empacotar.py antes.")
    conta = json.loads(rodar("gh", "api", "user", pasta=RAIZ, saida=True))
    usuario, email = conta["login"], f"{conta['id']}+{conta['login']}@users.noreply.github.com"
    if f"github.com/{usuario}/" not in REPOSITORIO:
        sys.exit(f"REPOSITORIO em versao.py ({REPOSITORIO}) não é da conta logada ({usuario}).")
    nome_repo = REPOSITORIO.rstrip("/").split("/")[-1]

    # 1. Cópia pública: os arquivos versionados do projeto, menos os excluídos
    if not (PUBLICO / ".git").exists():
        PUBLICO.mkdir(exist_ok=True)
        rodar("git", "init", "-q", "-b", "main")
    arquivos = [a for a in rodar("git", "ls-files", pasta=RAIZ, saida=True).splitlines() if a not in EXCLUIR]
    for velho in PUBLICO.rglob("*"):
        if velho.is_file() and ".git" not in velho.relative_to(PUBLICO).parts and str(velho.relative_to(PUBLICO)) not in arquivos:
            velho.unlink()
    for a in arquivos:
        (PUBLICO / a).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(RAIZ / a, PUBLICO / a)
    rodar("git", "add", "-A")
    if rodar("git", "status", "--porcelain", saida=True):
        rodar("git", "-c", f"user.name={usuario}", "-c", f"user.email={email}", "commit", "-q", "-m",
              f"Versão {VERSAO}\n\n{novidades}")

    # 2. Repositório no GitHub (na primeira vez) e envio
    remotos = rodar("git", "remote", saida=True)
    if "origin" not in remotos:
        existe = subprocess.run(["gh", "repo", "view", f"{usuario}/{nome_repo}"], cwd=PUBLICO, capture_output=True).returncode == 0
        if not existe:
            rodar("gh", "repo", "create", nome_repo, "--public", "--description",
                  "Caderno do treinador para o otPokemon: preços do market, times, breeding, farm e quests. Programa de fã, gratuito.")
        rodar("git", "remote", "add", "origin", f"https://github.com/{usuario}/{nome_repo}.git")
    rodar("gh", "auth", "setup-git", pasta=RAIZ)
    rodar("git", "push", "-q", "-u", "origin", "main")

    # 3. Release com o zip
    notas = NOTAS.format(versao=VERSAO, novidades=novidades, virustotal=virustotal)
    rodar("gh", "release", "create", f"v{VERSAO}", str(ZIP), "--title", f"Trainer's Notebook {VERSAO}", "--notes", notas)
    print(f"Publicado: {REPOSITORIO}/releases/tag/v{VERSAO}")


NOTAS = """{novidades}

## Como instalar
1. Baixe `Trainers Notebook {versao}.zip` (abaixo, em Assets) e descompacte.
2. Abra `Trainers Notebook.exe` (Windows 10 ou 11).
3. Se o Windows avisar "editor desconhecido": **Mais informações** > **Executar assim mesmo**. O aviso aparece porque o programa não tem assinatura digital paga.

Os seus dados ficam em `%APPDATA%\\Trainer's Notebook`: para atualizar, é só trocar a pasta do programa pela nova.

**O programa não interage com o jogo** (não clica, não aperta teclas, não lê a memória, não tira print sozinho): só lê os prints que você tira. Uso e distribuição gratuita conferidos com a staff do otPokemon.

**Verificação**: [VirusTotal]({virustotal}). Quase todos os antivírus não encontram nada; um alerta isolado de antivírus pouco conhecido (como o Bkav) é falso positivo genérico, comum em programas Python empacotados.
"""

if __name__ == "__main__":
    main()
