"""Lê as ofertas de um print do market do OTPokemon.

Cada oferta tem duas linhas no print:
    Jogador: Vonbull
    Quantidade: 1  Preço: 4500 = ...

Se o print incluir a lista de itens à esquerda da janela "Buscar ofertas", o item
selecionado é o que aparece em branco (os outros ficam em azul).
"""
import io
import re

import numpy as np
from PIL import Image

from db import DOLARES_POR_HD

RE_JOGADOR = re.compile(r"Jogador\s*:\s*(.+)", re.IGNORECASE)
RE_OFERTA = re.compile(r"Quantidade\s*:\s*(\d+)\s*Pre[çc]o\s*:\s*(\d+)", re.IGNORECASE)

# Razão vermelho/azul dos pixels claros do texto: azul fica ~0.25, branco ~1.0
FAIXA_BRANCO = (0.85, 1.2)
# Brilho do fundo: lista ~48 (selecionado ~62), campo de busca ~163
FUNDO_MAX_LISTA = 110

_motor = None


def _ocr():
    # Carregar o modelo leva alguns segundos, então só fazemos isso no primeiro print
    global _motor
    if _motor is None:
        from rapidocr import RapidOCR
        _motor = RapidOCR()
    return _motor


def _cores(pixels, caixa):
    """Devolve (razão vermelho/azul das letras, brilho do fundo) dentro da caixa."""
    x0, y0, x1, y1 = caixa
    recorte = pixels[y0:y1, x0:x1].reshape(-1, 3)
    if len(recorte) == 0:
        return None, None
    fundo = float(np.median(recorte.max(axis=1)))
    letras = recorte[recorte.max(axis=1) > 150]
    if len(letras) == 0 or letras[:, 2].mean() == 0:
        return None, fundo
    return letras[:, 0].mean() / letras[:, 2].mean(), fundo


def _item_selecionado(textos, pixels, inicio_ofertas):
    """Na lista de itens (à esquerda das ofertas), acha o único nome em branco.

    O campo de busca também tem texto branco, mas o fundo dele é claro;
    o título "Buscar ofertas" é amarelo.
    """
    brancos = []
    for t in textos:
        if t["caixa"][2] >= inicio_ofertas:
            continue
        cor, fundo = _cores(pixels, t["caixa"])
        if cor is not None and FAIXA_BRANCO[0] <= cor <= FAIXA_BRANCO[1] and fundo < FUNDO_MAX_LISTA:
            brancos.append(t)
    return brancos[0]["texto"].strip() if len(brancos) == 1 else None


def _linhas(textos):
    """Junta os pedaços que o OCR separou numa mesma linha (ex.: "Quantidade: 59" e "Preço:89800")."""
    linhas = []
    for t in sorted(textos, key=lambda t: (t["caixa"][1] + t["caixa"][3]) / 2):
        meio = (t["caixa"][1] + t["caixa"][3]) / 2
        if linhas and abs(meio - linhas[-1]["meio"]) <= 8:
            linhas[-1]["pedacos"].append(t)
        else:
            linhas.append({"meio": meio, "pedacos": [t]})
    return [" ".join(p["texto"] for p in sorted(l["pedacos"], key=lambda p: p["caixa"][0])) for l in linhas]


def ler_print(imagem: bytes):
    """Devolve {"item": nome ou None, "ofertas": [...]}, com preços já em HD."""
    pixels = np.array(Image.open(io.BytesIO(imagem)).convert("RGB")).astype(int)
    resultado = _ocr()(imagem)
    if resultado.txts is None:
        return {"item": None, "ofertas": []}

    textos = []
    for caixa, texto in zip(resultado.boxes, resultado.txts):
        xs, ys = [int(p[0]) for p in caixa], [int(p[1]) for p in caixa]
        textos.append({"texto": texto, "caixa": (max(min(xs), 0), max(min(ys), 0), max(xs), max(ys))})
    # A coluna das ofertas começa onde aparecem os "Jogador:"
    xs_jogador = [t["caixa"][0] for t in textos if RE_JOGADOR.search(t["texto"])]
    inicio_ofertas = min(xs_jogador) if xs_jogador else None

    ofertas, jogador = [], ""
    coluna_ofertas = [t for t in textos if inicio_ofertas is None or t["caixa"][0] >= inicio_ofertas - 5]
    for linha in _linhas(coluna_ofertas):
        if m := RE_JOGADOR.search(linha):
            jogador = m.group(1).strip()
        elif m := RE_OFERTA.search(linha):
            ofertas.append({
                "jogador": jogador,
                "quantidade": int(m.group(1)),
                "preco": int(m.group(2)) / DOLARES_POR_HD,
            })
            jogador = ""

    item = _item_selecionado(textos, pixels, inicio_ofertas) if inicio_ofertas else None
    return {"item": item, "ofertas": ofertas}
