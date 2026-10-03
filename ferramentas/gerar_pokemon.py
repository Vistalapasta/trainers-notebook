"""Gera static/pokemon.json, static/tms.json, static/golpes.json e static/helditems.json com os dados do otPokemon.

Fontes:
- PokéAPI (CSV do GitHub): tipos e stats oficiais; para o breeding, sexo, família de evolução e os egg groups que a
  wiki não tem. Baixados para ferramentas/pokeapi/ na primeira vez.
- Wiki do otPokemon: stats do jogo, moveset padrão, TMs e Move Tutor. A wiki bloqueia acesso automático (Cloudflare),
  então as páginas vêm de XML exportado pelo usuário no navegador:
    1. Abrir https://wiki.otponline.com/Especial:Exportar
    2. Colar os títulos das páginas (um por linha; `python ferramentas/gerar_pokemon.py --titulos` imprime a lista)
    3. Marcar "Incluir apenas a revisão atual" e exportar
    4. Salvar o .xml em ferramentas/wiki/ (pode haver vários; todos são lidos)
  Só os held items: `python ferramentas/gerar_pokemon.py --titulos-held` imprime as páginas deles ("Held Item" e
  "Mega Evolução"); exportar e salvar do mesmo jeito. Breeding: `--titulos-breeding` (Day Care, ovos e egg groups).

Rodar: .venv/bin/python ferramentas/gerar_pokemon.py
"""
import csv
import glob
import html
import json
import re
import sys
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PASTA_CSV = RAIZ / "ferramentas" / "pokeapi"
PASTA_WIKI = RAIZ / "ferramentas" / "wiki"
URL_CSV = "https://raw.githubusercontent.com/PokeAPI/pokeapi/master/data/v2/csv/{}.csv"

# Pokédex da wiki (páginas "Primeira Geração" a "Setima Geração"): #1 a #809
ULTIMO_NUMERO = 809
# Página "Regional Forms" da wiki (identificador no PokéAPI -> nome no jogo)
REGIONAIS = {
    "rattata-alola": "Alolan Rattata", "raticate-alola": "Alolan Raticate", "vulpix-alola": "Alolan Vulpix",
    "ninetales-alola": "Alolan Ninetales", "exeggutor-alola": "Alolan Exeggutor", "marowak-alola": "Alolan Marowak",
    "ponyta-galar": "Galarian Ponyta", "rapidash-galar": "Galarian Rapidash", "mr-mime-galar": "Galarian Mr. Mime",
    "mr-rime": "Mr. Rime",
}
# 8ª geração de eventos: tem página completa na wiki, mas não aparece na Pokédex dela
EVENTOS = ["cinderace", "dreepy", "drakloak", "dragapult", "ursaluna"]
# Título da página na wiki quando difere do nome (a página "Nidoranma" só redireciona para "Nidoran")
TITULO_WIKI = {"Nidoran♀": "Nidoran"}
# TMs que só aparecem como texto nas páginas: categoria e tipo conferidos à mão
TMS_MANUAIS = {"TM18": ["X-Scissor", "Físico", "Bug", ""]}

# Páginas da wiki além das dos pokémon (entram na lista do --titulos)
PAGINA_HELD = "Held Item"
PAGINA_MEGA = "Mega Evolução"
PAGINAS_BREEDING = ["Day Care", "Green Egg", "Orange Egg", "Pink Egg", "Purple Egg", "Egg Group"]
# Páginas dos ovos (cor no app, horas para chocar segundo a página "Day Care")
OVOS = {"Green Egg": ("Verde", 6), "Orange Egg": ("Laranja", 18), "Pink Egg": ("Rosa", 30), "Purple Egg": ("Roxo", 42)}
# Nomes das páginas de ovos que diferem do nome no jogo
NOMES_OVOS = {"Nidoran Fe": "Nidoran♀", "Nidoran Ma": "Nidoran♂"}

# Breeding (página "Day Care"): bebês que o Day Care Man ainda não consegue tirar do ovo (o ovo vem com a forma evoluída)
BEBES_SEM_OVO = {"Azurill", "Wynaut", "Budew", "Chingling", "Bonsly", "Mime Jr.", "Happiny", "Tyrogue", "Mantyke", "Munchlax"}
# Exclusivos de quest/evento que não dão ovo (página "Day Care") e cuja ficha na wiki está sem egg group
SEM_OVO_MANUAL = {"Absol"}
# O que nasce quando a família passa por uma forma regional que a cadeia da PokéAPI não conhece
NASCE_MANUAL = {"Mr. Rime": "Galarian Mr. Mime"}
# Egg groups: identificador da PokéAPI -> nome usado na wiki (sem o "Group")
EGG_GROUPS = {"monster": "Monster", "water1": "Water 1", "bug": "Bug", "flying": "Flying", "ground": "Field", "fairy": "Fairy",
              "plant": "Grass", "humanshape": "Human-Like", "water3": "Water 3", "mineral": "Mineral", "indeterminate": "Amorphous",
              "water2": "Water 2", "ditto": "Ditto", "dragon": "Dragon", "no-eggs": "Undiscovered"}

ORDEM_STATS = ["HP", "Attack", "Defense", "Sp. Attack", "Sp. Defense", "Speed"]
EFEITO = r"([+-]\d+\s+(?:Sp\.? )?(?:Attack|Defense|Speed|Accuracy|Evasion))"


def chave(texto):
    return re.sub(r"[^a-z0-9]", "", texto.lower().replace("♀", "f").replace("♂", "m"))


# ---------- PokéAPI ----------

def ler_csv(nome):
    arq = PASTA_CSV / f"{nome}.csv"
    if not arq.exists():
        PASTA_CSV.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(URL_CSV.format(nome), arq)
    return list(csv.DictReader(open(arq, encoding="utf-8")))


def lista_base():
    """Nome -> (tipos, stats oficiais, id da espécie) dos pokémon do jogo, na ordem da Pokédex."""
    nomes = {r["pokemon_species_id"]: r["name"] for r in ler_csv("pokemon_species_names") if r["local_language_id"] == "9"}
    tipos_id = {r["id"]: r["identifier"].capitalize() for r in ler_csv("types")}
    pokemon = {r["identifier"]: r for r in ler_csv("pokemon")}
    escolhidos = sorted(((r["id"], nomes[r["species_id"]]) for r in pokemon.values()
                         if r["is_default"] == "1" and int(r["species_id"]) <= ULTIMO_NUMERO), key=lambda x: int(x[0]))
    escolhidos += [(pokemon[i]["id"], nomes[pokemon[i]["species_id"]]) for i in EVENTOS]
    escolhidos += [(pokemon[i]["id"], n) for i, n in REGIONAIS.items()]
    ids = {pid for pid, _ in escolhidos}
    stats, tipos = {}, {}
    for r in ler_csv("pokemon_stats"):
        if r["pokemon_id"] in ids:
            stats.setdefault(r["pokemon_id"], {})[int(r["stat_id"])] = int(r["base_stat"])
    for r in sorted(ler_csv("pokemon_types"), key=lambda r: int(r["slot"])):
        if r["pokemon_id"] in ids:
            tipos.setdefault(r["pokemon_id"], []).append(tipos_id[r["type_id"]])
    especie = {r["id"]: r["species_id"] for r in pokemon.values()}
    return {n: (tipos[pid], [stats[pid][i] for i in range(1, 7)], especie[pid]) for pid, n in escolhidos}


def breeding_pokeapi(base):
    """Nome -> {e: egg groups, x: sexo ("MF", "M", "F" ou "-" sem sexo), b: o que nasce do ovo}.
    O ovo vem da família da mãe: o primeiro estágio da evolução (sem os bebês de BEBES_SEM_OVO, e a forma regional
    quando a mãe é regional)."""
    especies = {r["id"]: r for r in ler_csv("pokemon_species")}
    grupos_id = {r["id"]: EGG_GROUPS[r["identifier"]] for r in ler_csv("egg_groups")}
    grupos = {}
    for r in ler_csv("pokemon_egg_groups"):
        grupos.setdefault(r["species_id"], []).append(grupos_id[r["egg_group_id"]])
    nome_padrao = {esp: n for n, (_, _, esp) in base.items() if not n.startswith(("Alolan ", "Galarian "))}
    r = {}
    for n, (_, _, esp) in base.items():
        taxa = int(especies[esp]["gender_rate"])
        atual = esp
        while True:
            antes = especies[atual]["evolves_from_species_id"]
            if not antes or antes not in nome_padrao or nome_padrao[antes] in BEBES_SEM_OVO:
                break
            atual = antes
        nasce = nome_padrao.get(atual, n)
        regional = n.split(" ")[0] + " " + nasce
        if n.startswith(("Alolan ", "Galarian ")) and regional in base:
            nasce = regional
        r[n] = {"e": grupos.get(esp, []), "x": "-" if taxa < 0 else "M" if taxa == 0 else "F" if taxa == 8 else "MF",
                "b": NASCE_MANUAL.get(n, nasce)}
    return r


def egg_groups_wiki(texto):
    """Egg groups da ficha da wiki ("[[Field Group]]", "[[1 Water Group]]"); vazio quando a ficha tem "-"."""
    m = re.search(r"Egg Groups</b>\s*\n\|-\s*\n\|[^\n]*?\|(.*?)\n\|-", texto, re.S)
    if not m:
        return []
    return [re.sub(r"^(\d) Water$", r"Water \1", g.replace(" Group", "").strip()) for g in re.findall(r"\[\[([^\]|]+)", m.group(1))]


# ---------- Wiki (XML do Especial:Exportar) ----------

def paginas_wiki():
    r = {}
    for arq in sorted(glob.glob(str(PASTA_WIKI / "*.xml"))):
        s = open(arq, encoding="utf-8").read()
        for p in re.findall(r"<page>.*?</page>", s, flags=re.S):
            texto = re.search(r"<text[^>]*>(.*?)</text>", p, re.S)
            r[html.unescape(re.search(r"<title>(.*?)</title>", p).group(1))] = html.unescape(texto.group(1)) if texto else ""
    return r


def secao(texto, titulo):
    i = texto.find(titulo)
    if i < 0:
        return ""
    j = texto.find("\n== ", i + len(titulo))
    return texto[i:j if j > 0 else len(texto)]


def limpar(x):
    x = re.sub(r"\[\[Arquivo:[^\]]*\]\]", " ", x)
    x = re.sub(r"\[\[(?:[^\]|]*\|)?([^\]]*)\]\]", r"\1", x)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", x)).strip()


def golpe_do_trecho(trecho):
    """Categoria, tipo e efeito do texto que segue o ícone de um golpe."""
    txt = limpar(trecho)
    cat = re.search(r"\b(Status|Especial|Físico)\b", txt)
    tipo = re.search(r"(?:Status|Especial|Físico)\s+([A-Z][a-z]+)", txt)
    return (cat.group(1) if cat else "", tipo.group(1) if tipo else "", " ".join(dict.fromkeys(re.findall(EFEITO, txt))))


def ler_stats(st):
    vals = []
    for k in ORDEM_STATS:
        # Layout atual: rótulo "HP:", célula das estrelas e depois a célula só com o número
        m = re.search(re.escape(k) + r":\s*\n(?:[^\n]*\n){0,3}?[^\n]*\|\s*(\d+(?:\.\d+)?)\s*\n", st)
        vals.append(float(m.group(1)) if m else None)
    if None in vals:
        # Layout "wikitable" (ex.: Probopass): "| HP" / estrelas / "| <b>1.8</b>"
        vals = []
        for k in ORDEM_STATS:
            m = re.search(r"\|\s*" + k.replace("Sp.", "SP") + r"\s*\n\|[^\n]*\n\|\s*<b>\s*(\d+(?:\.\d+)?)\s*</b>", st)
            vals.append(float(m.group(1)) if m else None)
    return None if None in vals else vals


def ler_moveset(mv):
    pos = list(re.finditer(r"Arquivo:([^|\]]+?)-move-otp", mv))
    golpes = []
    for i, m in enumerate(pos):
        cat, tipo, efeito = golpe_do_trecho(mv[m.end(): pos[i + 1].start() if i + 1 < len(pos) else len(mv)])
        if cat:
            golpes.append([m.group(1).strip(), cat, tipo, efeito])
    if not golpes:
        # Layout "wikitable": '''M1''' / nome em negrito / ícone da categoria / ícone do tipo
        cats = {"Physical": "Físico", "Special": "Especial", "Status": "Status"}
        for b in re.split(r"'''M\d+'''", mv)[1:]:
            nome = re.search(r"'''([^']+)'''", b)
            cat = re.search(r"Arquivo:(Physical|Special|Status) move", b)
            tipo = re.search(r"Arquivo:(\w+)-type-otp", b)
            if nome and cat:
                golpes.append([nome.group(1).strip(), cats[cat.group(1)], tipo.group(1).capitalize() if tipo else "", ""])
    return golpes


def ler_tms(tm):
    # O link do ícone traz o código ("link=TM05 - Waterfall")
    pos = list(re.finditer(r"Arquivo:[^|\]]+?-move-otp[^\]]*?link=((?:TM|HM)\d+)\s*-\s*([^\]|]+)", tm))
    tms = []
    for i, m in enumerate(pos):
        tms.append([m.group(1), m.group(2).strip(), *golpe_do_trecho(tm[m.end(): pos[i + 1].start() if i + 1 < len(pos) else len(tm)])])
    # TMs que só aparecem como texto ("[[TM99 - Hyper Voice]]")
    ja = {x[0] for x in tms}
    for c, nome in re.findall(r"\[\[((?:TM|HM)\d+)\s*-\s*([^\]|]+)\]\]", tm):
        if c not in ja:
            tms.append([c, nome.strip(), "", "", ""])
            ja.add(c)
    return tms


def ler_tutor(sec):
    """Golpes do Move Tutor: [golpe, categoria, tipo, efeito, custo em Battle Points]."""
    # Custos numa linha ("208 [[Arquivo:B-ps.png...") e ícones dos golpes na seguinte, na mesma ordem
    custos = re.findall(r"(\d+)\s*\[\[Arquivo:(?:B-ps|Battle points)\.png", sec)
    pos = list(re.finditer(r"Arquivo:[^|\]]+?-move-otp[^\]]*?link=([^\]|]+)", sec))
    golpes = []
    for i, m in enumerate(pos):
        cat, tipo, efeito = golpe_do_trecho(sec[m.end(): pos[i + 1].start() if i + 1 < len(pos) else len(sec)])
        golpes.append([m.group(1).strip(), cat, tipo, efeito, int(custos[i]) if len(custos) == len(pos) else None])
    return golpes


def ler_pagina(texto):
    return {
        "stats": ler_stats(secao(texto, "== Status")),
        "golpes": ler_moveset(secao(texto, "== Moveset")),
        "tms": ler_tms(secao(texto, "== TMs")),
        "tutor": ler_tutor(secao(texto, "== Move Tutor")),
    }


# ---------- Held items ----------

def linhas_tabela(tabela):
    """Células de cada linha de uma tabela wiki ("|-" separa linhas, cada célula começa com "|" ou "!")."""
    linhas = []
    for bloco in re.split(r"\n\s*\|-[^\n]*", tabela)[1:]:
        celulas = [c.strip() for c in re.findall(r"^\s*[|!]\s*(?!\})(.*)$", bloco, flags=re.M)]
        # Célula com atributos ("style=... | texto"): fica só o texto
        celulas = [c.split("|", 1)[1].strip() if re.match(r"^[a-z-]+\s*=", c) and "|" in c and "[[" not in c.split("|", 1)[0] else c for c in celulas]
        if celulas:
            linhas.append(celulas)
    return linhas


def mega_stones(texto):
    """Mega Stones da página Mega Evolução: [imagem, nome, descrição, imagens das megas]."""
    r = {}
    for c in linhas_tabela(secao(texto, "==Held Items==")):
        if len(c) >= 3 and limpar(c[1]) and limpar(c[1]) != "Nome":
            pokemon = re.findall(r"\[\[(?!Arquivo:)([^\]|]+)", c[2])
            r[limpar(c[1])] = {"c": "Mega Stone", "e": limpar(c[2]), "p": pokemon}
    return r


def held_items(texto, pokemon):
    """Página Held Item: tabela [imagem, nome, descrição]. Itens exclusivos ("segurado por Cubone ou Marowak") ganham a lista de pokémon."""
    r = {}
    for c in linhas_tabela(secao(texto, "== Held Items ==")):
        nome = limpar(c[1]).strip("'").strip() if len(c) >= 3 else ""
        if not nome or nome in ("Nome", "Held"):
            continue
        # A wiki escreve alguns em minúsculas ("Choice scarf", "Metal coat"): iniciais maiúsculas como no jogo
        nome = re.sub(r"(^|\s)(\w)", lambda m: m.group(1) + m.group(2).upper(), nome)
        efeito = limpar(c[2])
        dono = re.search(r"segurado por ([^.]+?)\.", efeito)
        donos = [n for n in re.split(r",\s*|\s+ou\s+|\s+e\s+", dono.group(1).replace("'", "’")) if n in pokemon] if dono else []
        r[nome] = {"c": "Held Item", "e": efeito, "p": donos}
    return r


def ovos_wiki(paginas, nomes):
    """Páginas Green/Orange/Pink/Purple Egg: tabela com o nome de cada pokémon que pode vir no ovo.
    Devolve (cor -> {h: horas, p: [pokémon]}, nomes que não batem com a lista do jogo)."""
    por_chave = {chave(n): n for n in nomes}
    r, desconhecidos = {}, []
    for pagina, (cor, horas) in OVOS.items():
        lista = []
        for n in re.findall(r"<small>'''\[\[(?:[^\]|]*\|)?([^\]]+)\]\]'''</small>", paginas.get(pagina, "")):
            n = NOMES_OVOS.get(n.strip(), n.strip())
            if chave(n) in por_chave:
                lista.append(por_chave[chave(n)])
            else:
                desconhecidos.append(f"{pagina}: {n}")
        if lista:
            r[cor] = {"h": horas, "p": lista}
    return r, desconhecidos


# ---------- Montagem ----------

def main():
    base = lista_base()
    if "--titulos-held" in sys.argv:
        print(f"{PAGINA_HELD}\n{PAGINA_MEGA}")
        return
    if "--titulos-breeding" in sys.argv:
        print("\n".join(PAGINAS_BREEDING))
        return
    if "--titulos" in sys.argv:
        print("\n".join([PAGINA_HELD, PAGINA_MEGA, *PAGINAS_BREEDING] + [TITULO_WIKI.get(n, n) for n in base]))
        return
    paginas = paginas_wiki()
    wiki = {chave(t): x for t, x in paginas.items()}
    saida, tms, golpes, da_wiki = {}, {}, {}, 0

    def catalogar(golpe, cat, tipo, efeito):
        if golpe not in golpes or (not golpes[golpe][0] and cat):
            golpes[golpe] = [cat, tipo, efeito]

    breeding = breeding_pokeapi(base)
    egg_diferentes = []
    for nome, (tipos, oficiais, _) in base.items():
        # Stats do otP = oficiais × 0,03, arredondados a 0,05; usados quando a wiki não tem a página completa
        p = {"t": tipos, "s": [round(v * 0.03 * 20) / 20 for v in oficiais]}
        texto = wiki.get(chave(TITULO_WIKI.get(nome, nome)), "")
        d = ler_pagina(texto)
        # Breeding: egg groups da wiki (o jogo pode mudar algum); sem dados na wiki, os da PokéAPI
        br = breeding[nome]
        eg = egg_groups_wiki(texto)
        if eg and sorted(eg) != sorted(br["e"]):
            egg_diferentes.append(f"{nome}: wiki {eg}, PokéAPI {br['e']}")
        p.update({"e": ["Undiscovered"] if nome in SEM_OVO_MANUAL else eg or br["e"], "x": br["x"], "b": br["b"]})
        if not eg and nome not in SEM_OVO_MANUAL:
            p["ep"] = 1  # egg groups só da PokéAPI: a wiki não confirma, o jogo pode não deixar cruzar
        if d["stats"]:
            p["s"], p["w"] = d["stats"], 1
            da_wiki += 1
        if d["golpes"]:
            p["g"] = d["golpes"]
            for g in d["golpes"]:
                catalogar(*g)
        if d["tutor"]:
            p["u"] = [[g[0], g[4]] for g in d["tutor"]]
            for g in d["tutor"]:
                catalogar(*g[:4])
        if d["tms"]:
            p["m"] = [x[0] for x in d["tms"]]
            for c, golpe, cat, tipo, efeito in d["tms"]:
                if c not in tms or (not tms[c][1] and cat):
                    tms[c] = [golpe, cat, tipo, efeito]
                catalogar(golpe, cat, tipo, efeito)
        saida[nome] = p
    for c, v in TMS_MANUAIS.items():
        if c in tms and not tms[c][1]:
            tms[c] = v
        golpes[v[0]] = v[1:]
    ordem = sorted(tms, key=lambda c: (c[:2] != "HM", int(c[2:])))
    json.dump(saida, open(RAIZ / "static" / "pokemon.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    json.dump(dict(sorted(golpes.items())), open(RAIZ / "static" / "golpes.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    json.dump({c: tms[c] for c in ordem}, open(RAIZ / "static" / "tms.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    held = {**held_items(paginas.get(PAGINA_HELD, ""), saida), **mega_stones(paginas.get(PAGINA_MEGA, ""))}
    json.dump(dict(sorted(held.items())), open(RAIZ / "static" / "helditems.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    ovos, desconhecidos = ovos_wiki(paginas, saida)
    if ovos:
        json.dump(ovos, open(RAIZ / "static" / "ovos.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
        no_ovo = {n for o in ovos.values() for n in o["p"]}
        sem_cor = sorted({p["b"] for p in saida.values() if "Undiscovered" not in p["e"] and p["b"] not in no_ovo})
        print("Ovos: " + ", ".join(f"{c} {len(o['p'])}" for c, o in ovos.items())
              + (f"\n  nomes que não batem: {desconhecidos}" if desconhecidos else "")
              + (f"\n  nascem de ovo mas não estão em nenhuma página de ovo ({len(sem_cor)}): {sem_cor}" if sem_cor else ""))
    if egg_diferentes:
        print(f"Egg groups da wiki diferentes da PokéAPI (vale a wiki): {len(egg_diferentes)}\n  " + "\n  ".join(egg_diferentes))
    print(f"{len(held)} held items" + ("" if PAGINA_HELD in paginas else f' (página "{PAGINA_HELD}" não exportada: só as Mega Stones)'))
    print(f"{len(saida)} pokémon, {da_wiki} com dados da wiki; {len(tms)} TMs/HMs; {sum(1 for x in saida.values() if 'u' in x)} com Move Tutor; {len(golpes)} golpes"
          + (f"; golpes sem categoria: {[n for n, v in golpes.items() if not v[0]]}" if any(not v[0] for v in golpes.values()) else "")
          + (f" ({sum(1 for c in tms if not tms[c][1])} sem categoria: completar em TMS_MANUAIS)" if any(not v[1] for v in tms.values()) else ""))


if __name__ == "__main__":
    main()
