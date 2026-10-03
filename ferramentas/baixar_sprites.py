"""Baixa os retratos e sprites do PMDCollab (SpriteCollab) para static/pmd/ e gera static/pmd/pmd.json.

Fonte: https://github.com/PMDCollab/SpriteCollab (site: https://sprites.pmdcollab.org/).
Licença: CC BY-NC 4.0 (https://creativecommons.org/licenses/by-nc/4.0/): uso não comercial e com crédito aos artistas.
Os créditos vêm do tracker.json (artista principal e secundários de cada retrato/sprite) e os nomes/contatos do
credit_names.txt. O app mostra o crédito na ficha de cada pokémon e a lista completa na aba Pokémon.
Também copia o spritebot_credits.txt (créditos de todo o repositório, por artista e imagem) para static/pmd/: foi o
arquivo que o Audino, do PMDCollab, indicou para acompanhar o programa quando ele for distribuído.

Modificação feita (a licença pede que seja indicada): do sprite só fica a animação parada (Idle) virada para a frente;
as outras direções e animações são descartadas.

Os arquivos originais ficam em ferramentas/pmd/ (cache, no .gitignore); rodar de novo só baixa o que falta.
Para atualizar tudo (artistas redesenham com o tempo), apagar ferramentas/pmd/ antes.

Rodar depois do gerar_pokemon.py: .venv/bin/python ferramentas/baixar_sprites.py
"""
import json
import re
import shutil
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image

from gerar_pokemon import ler_csv

RAIZ = Path(__file__).resolve().parent.parent
CACHE = RAIZ / "ferramentas" / "pmd"
SAIDA = RAIZ / "static" / "pmd"
URL = "https://raw.githubusercontent.com/PMDCollab/SpriteCollab/master/{}"
# Prefixo do nome no jogo -> nome da forma no PMDCollab
FORMAS = {"Alolan ": "Alola", "Galarian ": "Galar"}


def baixar(caminho):
    """Arquivo do repositório (com cache local). None se não existir."""
    arq = CACHE / caminho
    if arq.exists():
        return arq if arq.stat().st_size else None
    arq.parent.mkdir(parents=True, exist_ok=True)
    try:
        with urllib.request.urlopen(URL.format(caminho), timeout=60) as r:
            dados = r.read()
    except urllib.error.HTTPError as e:
        if e.code != 404:
            raise
        dados = b""
    arq.write_bytes(dados)
    return arq if dados else None


def no_do_pokemon(tracker, especies, nome):
    """Caminho no repositório ('0019/0001') e nó do tracker do pokémon, na forma certa."""
    forma = next((f for p, f in FORMAS.items() if nome.startswith(p)), "")
    base = nome[len(next(p for p in FORMAS if nome.startswith(p))):] if forma else nome
    num = f"{especies[base]:04d}"
    no = tracker[num]
    if forma:
        sub = next(k for k, v in no["subgroups"].items() if v["name"] == forma)
        return f"{num}/{sub}", no["subgroups"][sub]
    return num, no


def shiny(caminho, no):
    """Nó shiny: fica em .../0001 abaixo da forma (a forma normal é a subpasta 0000)."""
    if "/" not in caminho:
        caminho, no = f"{caminho}/0000", no["subgroups"].get("0000")
    s = no and no["subgroups"].get("0001")
    return (f"{caminho}/0001", s) if s and s["name"] == "Shiny" else (None, None)


def creditos(c):
    return [c["primary"], *c["secondary"]] if c and c.get("primary") else []


def retrato(caminho, no):
    if "Normal" not in no["portrait_files"] or not baixar(f"portrait/{caminho}/Normal.png"):
        return None
    arq = caminho.replace("/", "-") + ".png"
    shutil.copy(CACHE / "portrait" / caminho / "Normal.png", SAIDA / "retrato" / arq)
    return {"f": arq, "c": creditos(no["portrait_credit"])}


def sprite(caminho, no):
    """Animação Idle virada para a frente (1ª linha da folha): {f: arquivo, w, h, d: durações em 1/60 s}."""
    if not no["sprite_files"] or not (xml := baixar(f"sprite/{caminho}/AnimData.xml")):
        return None
    anims = {a.findtext("Name"): a for a in ET.parse(xml).getroot().iter("Anim")}
    nome = "Idle" if "Idle" in anims else "Walk"
    while anims[nome].findtext("CopyOf"):
        nome = anims[nome].findtext("CopyOf")
    a = anims[nome]
    w, h = int(a.findtext("FrameWidth")), int(a.findtext("FrameHeight"))
    durs = [int(d.text) for d in a.iter("Duration")]
    folha = baixar(f"sprite/{caminho}/{nome}-Anim.png")
    if not folha:
        return None
    arq = caminho.replace("/", "-") + ".png"
    with Image.open(folha) as img:
        img.crop((0, 0, w * len(durs), h)).save(SAIDA / "sprite" / arq, optimize=True)
    return {"f": arq, "w": w, "h": h, "d": durs, "c": creditos(no["sprite_credit"])}


def imagens(caminho, no):
    r = {}
    if x := retrato(caminho, no):
        r["r"] = x
    if x := sprite(caminho, no):
        r["a"] = x
    return r


def main():
    for pasta in ("retrato", "sprite"):
        (SAIDA / pasta).mkdir(parents=True, exist_ok=True)
    tracker = json.load(open(baixar("tracker.json"), encoding="utf-8"))
    nomes = {}
    for linha in open(baixar("credit_names.txt"), encoding="utf-8").read().splitlines()[1:]:
        partes = linha.split("\t")
        if len(partes) >= 2:
            nomes[partes[1].strip()] = [partes[0].strip(), partes[2].strip() if len(partes) > 2 else ""]
    especies = {r["name"]: int(r["pokemon_species_id"]) for r in ler_csv("pokemon_species_names") if r["local_language_id"] == "9"}
    pokemons = json.load(open(RAIZ / "static" / "pokemon.json", encoding="utf-8"))

    def um(nome):
        caminho, no = no_do_pokemon(tracker, especies, nome)
        r = imagens(caminho, no)
        cs, ns = shiny(caminho, no)
        if cs and (s := imagens(cs, ns)):
            r["s"] = s
        return nome, r

    with ThreadPoolExecutor(16) as ex:
        saida = {n: r for n, r in ex.map(um, pokemons) if r}

    # Artistas citados: id -> [nome, contato]. Quem não se registrou no bot aparece pelo ID do Discord.
    ids = sorted({c for r in saida.values() for g in (r, r.get("s", {})) for k in "ra" if k in g for c in g[k]["c"]})
    artistas = {}
    for i in ids:
        nome, contato = nomes.get(i, ["", ""])
        num = re.sub(r"\D", "", i)
        artistas[i] = [nome or (f"Discord {num}" if num else i), contato if contato.startswith("http") else ""]
    json.dump({"pokemon": saida, "artistas": artistas}, open(SAIDA / "pmd.json", "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    shutil.copyfile(baixar("spritebot_credits.txt"), SAIDA / "spritebot_credits.txt")
    sem = [n for n in pokemons if "r" not in saida.get(n, {})]
    print(f"{len(saida)} pokémon; {sum('a' in r for r in saida.values())} com sprite; {sum('s' in r for r in saida.values())} com shiny; "
          f"{len(artistas)} artistas" + (f"; sem retrato: {sem}" if sem else ""))


if __name__ == "__main__":
    main()
