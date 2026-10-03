"""Gera static/quests.json a partir da página "Quests" da wiki do otPokemon.

A wiki bloqueia acesso automático: exportar a página "Quests" em https://wiki.otponline.com/Especial:Exportar
("Incluir apenas a revisão atual") e salvar o .xml em ferramentas/wiki/ (o mesmo lugar do gerar_pokemon.py).

A página tem três tabelas (Quests, Side Quests, Quests Especiais) com Nome, Level, Premium, Prêmio e Vídeo.
quests.json = [{"n": nome, "w": título da página na wiki, "g": grupo, "l": level (None = sem level), "p": 1 se premium,
"r": prêmio em texto, "v": link do vídeo ou None}]

Rodar: .venv/bin/python ferramentas/gerar_quests.py
"""
import glob
import html
import json
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PASTA_WIKI = RAIZ / "ferramentas" / "wiki"
SAIDA = RAIZ / "static" / "quests.json"
GRUPOS = {"Quests": "Quest", "Side Quests": "Side Quest", "Quests Especiais": "Especial"}


def pagina_quests():
    """Texto da revisão mais recente da página "Quests" entre os XML exportados."""
    achado = None
    for arquivo in sorted(glob.glob(str(PASTA_WIKI / "*.xml"))):
        xml = Path(arquivo).read_text(encoding="utf-8")
        for pagina in re.findall(r"<page>.*?</page>", xml, re.S):
            if re.search(r"<title>Quests</title>", pagina):
                achado = html.unescape(re.search(r"<text[^>]*>(.*?)</text>", pagina, re.S).group(1))
    if achado is None:
        raise SystemExit('Página "Quests" não encontrada em ferramentas/wiki/*.xml. Exporte-a pelo Especial:Exportar.')
    return achado


def texto(celula):
    """Wikitexto da célula -> texto: [[Página|<span>Rótulo</span>]] -> Rótulo, sem tags nem arquivos."""
    celula = re.sub(r"\[\[(?:Arquivo|File):[^\]]*\]\]", "", celula)
    celula = re.sub(r"\[\[[^\]|]*\|([^\]]*)\]\]", r"\1", celula)
    celula = re.sub(r"\[\[([^\]]*)\]\]", r"\1", celula)
    celula = re.sub(r"<[^>]+>", "", celula)
    return " ".join(celula.split()).strip()


def celulas(linha):
    """Linha da tabela -> lista de células sem os atributos ("| data-sort-value=\"1\" | valor")."""
    saida = []
    for c in linha.strip().split("\n"):
        c = c.strip()
        if not c.startswith("|"):
            continue
        partes = c[1:].split("|", 1)
        # "| atributos | valor" (o valor pode ter | dentro de [[link|rótulo]]): o atributo não tem [[
        saida.append(partes[1] if len(partes) == 2 and "[[" not in partes[0] else c[1:])
    return saida


def main():
    wiki = pagina_quests()
    quests, vistos = [], set()
    for secao, grupo in GRUPOS.items():
        m = re.search(r"==\s*" + re.escape(secao) + r"\s*==(.*?)\|\}", wiki, re.S)
        if not m:
            print(f"Aviso: seção {secao} não encontrada")
            continue
        for linha in m.group(1).split("|-")[2:]:  # [0] = antes da tabela, [1] = cabeçalho
            c = celulas(linha)
            if len(c) < 5:
                continue
            titulo = re.search(r"\[\[([^\]|]*)", c[0])
            nome = texto(c[0])
            if not nome or (grupo, nome) in vistos:
                continue
            vistos.add((grupo, nome))
            level = re.search(r"\d+", texto(c[1]))
            video = re.search(r"link=(https?://[^\]|]+)", c[4])
            quests.append({
                "n": nome, "w": titulo.group(1).strip() if titulo else nome, "g": grupo,
                "l": int(level.group()) if level else None, "p": 1 if "Vipon" in c[2] else 0,
                "r": "" if texto(c[3]) in ("—", "-") else texto(c[3]), "v": video.group(1) if video else None,
            })
    SAIDA.write_text(json.dumps(quests, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    por_grupo = {g: sum(q["g"] == g for q in quests) for g in GRUPOS.values()}
    print(f"{len(quests)} quests em {SAIDA.relative_to(RAIZ)}: {por_grupo}")


if __name__ == "__main__":
    main()
