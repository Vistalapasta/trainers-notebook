import csv
import io
import json
import sqlite3
import subprocess
import urllib.request
from bisect import bisect_left, bisect_right
from datetime import datetime, timedelta

from flask import Flask, Response, jsonify, render_template, request, send_from_directory
from PIL import UnidentifiedImageError

import clipboard
import db
import leitor_print
from caminhos import PROGRAMA
from versao import FORMULARIO_PREENCHIDO, REPOSITORIO, VERSAO

app = Flask(__name__, template_folder=str(PROGRAMA / "templates"), static_folder=str(PROGRAMA / "static"))

# Quanto o valor de mercado atual precisa estar abaixo/acima da média de mercado de 30 dias
LIMITE_OTIMO = -0.15
LIMITE_BOM = -0.05
LIMITE_CARO = 0.10
MINIMO_REGISTROS = 3

# Fora da curva: preço abaixo de 60% ou acima de 167% da mediana dos registros
# vizinhos (até 15 dias antes/depois). Só avalia com pelo menos 3 vizinhos.
FORA_ABAIXO = 0.6
FORA_ACIMA = 1 / FORA_ABAIXO
JANELA_FORA = 15
MINIMO_VIZINHOS = 3


def media(valores):
    return sum(valores) / len(valores) if valores else None


def sinal(atual, media30, registros):
    if atual is None or media30 is None or registros < MINIMO_REGISTROS:
        return "poucos dados"
    diff = (atual - media30) / media30
    if diff <= LIMITE_OTIMO:
        return "ótimo"
    if diff <= LIMITE_BOM:
        return "bom"
    if diff >= LIMITE_CARO:
        return "caro"
    return "normal"


def mediana(valores):
    ordenados = sorted(valores)
    meio = len(ordenados) // 2
    return ordenados[meio] if len(ordenados) % 2 else (ordenados[meio - 1] + ordenados[meio]) / 2


def marcar_fora_da_curva(precos):
    """Marca cada registro com "fora" (True/False) e "referencia" (mediana usada).

    Compara o valor de mercado ("mercado") de cada registro. Um registro é fora da curva quando fica abaixo de FORA_ABAIXO ou acima de
    FORA_ACIMA vezes a mediana dos outros registros até JANELA_FORA dias antes
    ou depois dele. O campo "ignorar" do registro, quando preenchido, manda.
    """
    # precos vem ordenado por data, então a janela de vizinhos sai por busca binária
    datas = [datetime.fromisoformat(p["registrado_em"]) for p in precos]
    janela = timedelta(days=JANELA_FORA)
    for i, p in enumerate(precos):
        ini = bisect_left(datas, datas[i] - janela)
        fim = bisect_right(datas, datas[i] + janela)
        vizinhos = [
            precos[j]["mercado"] for j in range(ini, fim)
            if j != i and precos[j]["ignorar"] != 1
        ]
        ref = mediana(vizinhos) if len(vizinhos) >= MINIMO_VIZINHOS else None
        p["referencia"] = ref
        auto = ref is not None and not (FORA_ABAIXO * ref <= p["mercado"] <= FORA_ACIMA * ref)
        p["fora_auto"] = auto
        p["fora"] = bool(p["ignorar"]) if p["ignorar"] is not None else auto
    return precos


def mediana_ponderada(ofertas):
    """Preço do "meio do estoque": onde a quantidade acumulada passa da metade."""
    ofertas = sorted(ofertas, key=lambda o: o["preco"])
    metade = sum(o["quantidade"] for o in ofertas) / 2
    acumulado = 0
    for o in ofertas:
        acumulado += o["quantidade"]
        if acumulado >= metade:
            return o["preco"]


def historico_item(conn, item_id):
    """Registros do item em ordem de data, com o valor de mercado e a marcação de fora da curva.

    "mercado" é a mediana das ofertas do print ponderada pela quantidade, que
    quase não se abala com isca de 1 unidade. Registros manuais usam o próprio preço.
    """
    precos = [dict(p) for p in conn.execute(
        "SELECT id, preco, obs, registrado_em, ignorar FROM precos WHERE item_id = ? ORDER BY registrado_em",
        (item_id,),
    )]
    ofertas = {}
    for o in conn.execute(
        "SELECT o.preco_id, o.preco, o.quantidade FROM ofertas o "
        "JOIN precos p ON p.id = o.preco_id WHERE p.item_id = ?",
        (item_id,),
    ):
        ofertas.setdefault(o["preco_id"], []).append(o)
    for p in precos:
        do_print = ofertas.get(p["id"], [])
        p["n_ofertas"] = len(do_print)
        p["quantidade"] = sum(o["quantidade"] for o in do_print)
        p["oferta_min"] = min((o["preco"] for o in do_print), default=None)
        p["oferta_max"] = max((o["preco"] for o in do_print), default=None)
        p["mercado"] = mediana_ponderada(do_print) if do_print else p["preco"]
    return marcar_fora_da_curva(precos)


def resumo_item(conn, item):
    agora = datetime.now()
    precos = historico_item(conn, item["id"])
    validos = [p for p in precos if not p["fora"]]

    def ultimos(dias):
        corte = (agora - timedelta(days=dias)).strftime("%Y-%m-%d %H:%M:%S")
        return [p["mercado"] for p in validos if p["registrado_em"] >= corte]

    p30 = ultimos(30)
    # Médias, mínimo, máximo e sinal usam o valor de mercado (tendência).
    # O "atual" é o menor preço do último registro: o que se pagaria agora.
    # O sinal compara mercado com mercado, porque o menor preço de um print é
    # sempre abaixo da mediana dele e pareceria "barato" o tempo todo.
    atual = precos[-1]["preco"] if precos else None
    mercado_atual = precos[-1]["mercado"] if precos else None
    m30 = media(p30)
    return {
        "id": item["id"],
        "nome": item["nome"],
        "categoria": item["categoria"],
        "registros": len(precos),
        "fora_da_curva": sum(p["fora"] for p in precos),
        "atual": atual,
        "alvo": item["alvo"],
        "mercado_atual": mercado_atual,
        "atual_fora": precos[-1]["fora"] if precos else False,
        "atualizado_em": precos[-1]["registrado_em"] if precos else None,
        "media7": media(ultimos(7)),
        "media30": m30,
        "min30": min(p30) if p30 else None,
        "max30": max(p30) if p30 else None,
        "diff30": (mercado_atual - m30) / m30 if mercado_atual is not None and m30 else None,
        "sinal": sinal(mercado_atual, m30, len(p30)),
    }


def hd(valor):
    """Formata em HD no padrão brasileiro: 7480 -> "7.480", 29.99 -> "29,99"."""
    texto = f"{valor:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
    return texto.removesuffix(",00")


def verificar_alertas(conn, item_id):
    """Chamado a cada preço registrado: cria os avisos que o novo registro disparou."""
    item = conn.execute("SELECT * FROM itens WHERE id = ?", (item_id,)).fetchone()
    r = resumo_item(conn, item)
    novos = []
    if r["sinal"] == "ótimo":
        novos.append(("otimo", f"{r['nome']}: mercado a {hd(r['mercado_atual'])} HD, "
                               f"{abs(r['diff30']) * 100:.0f}% abaixo da média de 30 dias"))
    if r["alvo"] is not None and r["atual"] is not None and r["atual"] <= r["alvo"]:
        novos.append(("alvo", f"{r['nome']}: menor preço {hd(r['atual'])} HD, no seu alvo de {hd(r['alvo'])} HD"))
    criados = []
    for tipo, mensagem in novos:
        cur = conn.execute(
            "INSERT INTO alertas (item_id, tipo, mensagem) VALUES (?, ?, ?)", (item_id, tipo, mensagem)
        )
        criados.append({"id": cur.lastrowid, "item_id": item_id, "tipo": tipo, "mensagem": mensagem})
    return criados


@app.get("/")
def index():
    return render_template("index.html", versao=VERSAO, repositorio=REPOSITORIO, formulario=FORMULARIO_PREENCHIDO)


# Aviso de versão nova: pergunta ao GitHub qual é a última release (uma vez por execução; o único acesso
# do programa à internet). Sem internet ou com erro, não mostra nada.
_versao_nova = None


def _como_numeros(versao):
    try:
        return tuple(int(p) for p in versao.lstrip("v").split("."))
    except ValueError:
        return ()


@app.get("/api/versao-nova")
def versao_nova():
    global _versao_nova
    if _versao_nova is None:
        _versao_nova = {}
        api = REPOSITORIO.replace("https://github.com/", "https://api.github.com/repos/") + "/releases/latest"
        try:
            pedido = urllib.request.Request(api, headers={"Accept": "application/vnd.github+json",
                                                          "User-Agent": f"TrainersNotebook/{VERSAO}"})
            with urllib.request.urlopen(pedido, timeout=5) as r:
                ultima = json.load(r)
            tag = ultima.get("tag_name", "")
            if _como_numeros(tag) > _como_numeros(VERSAO):
                _versao_nova = {"versao": tag.lstrip("v"), "url": ultima.get("html_url") or f"{REPOSITORIO}/releases/latest"}
        except Exception:
            _versao_nova = None  # tenta de novo na próxima vez que a página abrir
            return jsonify({})
    return jsonify(_versao_nova)


@app.get("/mini")
def mini():
    return render_template("mini.html")


@app.post("/api/abrir-mini")
def abrir_mini():
    """Abre o modo mini: na versão desktop, a janela própria (desktop.py); no WSL, uma janela do Edge sem barra de
    endereço (modo app)."""
    if app.config.get("ABRIR_MINI"):
        app.config["ABRIR_MINI"]()
        return "", 204
    try:
        subprocess.Popen(
            ["cmd.exe", "/c", "start", "", "msedge", f"--app=http://localhost:{request.host.split(':')[-1]}/mini",
             "--window-size=360,620"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, cwd="/mnt/c",
        )
    except FileNotFoundError:
        return jsonify(erro="Não consegui abrir o Edge. Abra http://localhost:5000/mini manualmente."), 500
    return "", 204


def verificar_cronometros(conn):
    """Cronômetros que acabaram viram alerta (uma vez cada). Roda a cada consulta dos alertas (3 s)."""
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for c in conn.execute("SELECT * FROM cronometros WHERE fim <= ? AND avisado = 0", (agora,)).fetchall():
        conn.execute("INSERT INTO alertas (tipo, mensagem) VALUES ('cronometro', ?)",
                     (f"{c['nome']}: terminou ({duracao(c['segundos'])})",))
        conn.execute("UPDATE cronometros SET avisado = 1 WHERE id = ?", (c["id"],))


def duracao(segundos):
    """3600 -> "1h", 5400 -> "1h30", 900 -> "15min"."""
    h, m = divmod(segundos // 60, 60)
    return f"{h}h{m:02d}" if h and m else f"{h}h" if h else f"{m}min"


@app.get("/api/alertas")
def listar_alertas():
    """Últimos avisos (ou só os posteriores a `depois`) e quantos ainda não foram lidos."""
    depois = request.args.get("depois", type=int)
    with db.conectar() as conn:
        verificar_cronometros(conn)
        if depois is None:
            linhas = conn.execute("SELECT * FROM alertas ORDER BY id DESC LIMIT 30").fetchall()
        else:
            linhas = conn.execute("SELECT * FROM alertas WHERE id > ? ORDER BY id DESC LIMIT 50", (depois,)).fetchall()
        nao_lidos = conn.execute("SELECT COUNT(*) FROM alertas WHERE lido = 0").fetchone()[0]
    return jsonify(alertas=[dict(l) for l in linhas], nao_lidos=nao_lidos)


@app.post("/api/alertas/lidos")
def marcar_alertas_lidos():
    with db.conectar() as conn:
        conn.execute("UPDATE alertas SET lido = 1 WHERE lido = 0")
    return "", 204


@app.put("/api/itens/<int:item_id>/alvo")
def definir_alvo(item_id):
    alvo = request.get_json().get("alvo")
    try:
        alvo = None if alvo in (None, "") else float(alvo)
    except (TypeError, ValueError):
        return jsonify(erro="Alvo inválido."), 400
    if alvo is not None and alvo <= 0:
        return jsonify(erro="O alvo precisa ser maior que zero."), 400
    with db.conectar() as conn:
        conn.execute("UPDATE itens SET alvo = ? WHERE id = ?", (alvo, item_id))
    return "", 204


@app.get("/api/itens")
def listar_itens():
    with db.conectar() as conn:
        itens = conn.execute("SELECT * FROM itens ORDER BY categoria, nome").fetchall()
        return jsonify([resumo_item(conn, i) for i in itens])


@app.post("/api/itens")
def criar_item():
    dados = request.get_json()
    nome = db.padronizar(dados.get("nome") or "")
    if not nome:
        return jsonify(erro="Informe o nome do item."), 400
    categoria = db.padronizar(dados.get("categoria") or "") or db.categoria_padrao(nome)
    try:
        with db.conectar() as conn:
            cur = conn.execute("INSERT INTO itens (nome, categoria) VALUES (?, ?)", (nome, categoria))
            return jsonify(id=cur.lastrowid), 201
    except sqlite3.IntegrityError:
        return jsonify(erro=f"O item '{nome}' já existe."), 409


@app.delete("/api/itens/<int:item_id>")
def remover_item(item_id):
    with db.conectar() as conn:
        conn.execute("DELETE FROM itens WHERE id = ?", (item_id,))
    return "", 204


@app.get("/api/itens/<int:item_id>/precos")
def historico(item_id):
    with db.conectar() as conn:
        return jsonify(historico_item(conn, item_id))


@app.post("/api/precos")
def registrar_preco():
    dados = request.get_json()
    try:
        preco = float(dados["preco"])
        quantidade = int(dados.get("quantidade") or 1)
    except (KeyError, TypeError, ValueError):
        return jsonify(erro="Preço ou quantidade inválidos."), 400
    if preco <= 0 or quantidade <= 0:
        return jsonify(erro="Preço e quantidade precisam ser maiores que zero."), 400

    with db.conectar() as conn:
        if not conn.execute("SELECT 1 FROM itens WHERE id = ?", (dados.get("item_id"),)).fetchone():
            return jsonify(erro="Item não encontrado."), 404
        cur = conn.execute(
            "INSERT INTO precos (item_id, preco, obs) VALUES (?, ?, ?)",
            (dados["item_id"], preco / quantidade, (dados.get("obs") or "").strip()),
        )
        alertas = verificar_alertas(conn, dados["item_id"])
    return jsonify(id=cur.lastrowid, alertas=alertas), 201


@app.post("/api/ler-print")
def ler_print():
    arquivo = request.files.get("imagem")
    if not arquivo:
        return jsonify(erro="Nenhuma imagem enviada."), 400
    try:
        lido = leitor_print.ler_print(arquivo.read())
    except UnidentifiedImageError:
        return jsonify(erro="Não consegui abrir a imagem."), 400
    if not lido["ofertas"]:
        return jsonify(erro="Não encontrei ofertas no print. É a tela do market?"), 422
    return jsonify(lido)


@app.post("/api/ofertas")
def registrar_ofertas():
    """Registra as ofertas de um print: o preço do momento é a menor oferta.

    O item vem pelo nome (como aparece no jogo) e é cadastrado se ainda não existir.
    """
    dados = request.get_json()
    nome = db.padronizar(str(dados.get("item") or ""))
    if not nome:
        return jsonify(erro="Informe o item do print."), 400
    try:
        ofertas = [
            {"jogador": str(o.get("jogador") or "").strip(),
             "quantidade": int(o["quantidade"]),
             "preco": float(o["preco"])}
            for o in dados["ofertas"]
        ]
    except (KeyError, TypeError, ValueError):
        return jsonify(erro="Ofertas inválidas."), 400
    if not ofertas or any(o["preco"] <= 0 or o["quantidade"] <= 0 for o in ofertas):
        return jsonify(erro="Confira os preços e quantidades."), 400

    menor = min(ofertas, key=lambda o: o["preco"])
    with db.conectar() as conn:
        item = conn.execute("SELECT id, nome FROM itens WHERE nome = ?", (nome,)).fetchone()
        if item:
            item_id = item["id"]
            # Nome lido do print é a grafia do jogo: corrige a cadastrada se só diferir em maiúsculas
            if dados.get("detectado") and item["nome"] != nome:
                conn.execute("UPDATE itens SET nome = ? WHERE id = ?", (nome, item_id))
        else:
            item_id = conn.execute(
                "INSERT INTO itens (nome, categoria) VALUES (?, ?)", (nome, db.categoria_padrao(nome))
            ).lastrowid
        cur = conn.execute(
            "INSERT INTO precos (item_id, preco, obs) VALUES (?, ?, ?)",
            (item_id, menor["preco"], f"print: {len(ofertas)} oferta(s), menor de {menor['jogador'] or '?'}"),
        )
        conn.executemany(
            "INSERT INTO ofertas (preco_id, jogador, quantidade, preco) VALUES (?, ?, ?, ?)",
            [(cur.lastrowid, o["jogador"], o["quantidade"], o["preco"]) for o in ofertas],
        )
        alertas = verificar_alertas(conn, item_id)
    return jsonify(id=cur.lastrowid, item_id=item_id, novo_item=not item, preco=menor["preco"], alertas=alertas), 201


@app.get("/api/capturas")
def ultima_captura():
    """A página pergunta de tempos em tempos se chegou print novo pelo clipboard."""
    nova = clipboard.ultima_depois(request.args.get("depois", type=int, default=0))
    if not nova:
        return jsonify(total=clipboard.total(), nome=None)
    total, nome = nova
    return jsonify(total=total, nome=nome)


@app.get("/capturas/<nome>")
def arquivo_captura(nome):
    return send_from_directory(clipboard.PASTA, nome)


@app.patch("/api/precos/<int:preco_id>")
def ajustar_preco(preco_id):
    """Força usar (0) ou ignorar (1) um registro nas médias; null volta ao automático."""
    ignorar = request.get_json().get("ignorar")
    if ignorar not in (None, 0, 1):
        return jsonify(erro="Valor inválido."), 400
    with db.conectar() as conn:
        conn.execute("UPDATE precos SET ignorar = ? WHERE id = ?", (ignorar, preco_id))
    return "", 204


@app.delete("/api/precos/<int:preco_id>")
def remover_preco(preco_id):
    with db.conectar() as conn:
        conn.execute("DELETE FROM precos WHERE id = ?", (preco_id,))
    return "", 204


# ---------- Times ----------

MAXIMO_MEMBROS = 6


def time_json(t):
    return {"id": t["id"], "nome": t["nome"], "membros": json.loads(t["membros"]), "atualizado_em": t["atualizado_em"]}


def membros_validos(membros):
    """Até 6 membros com pokémon, held item, nature, TMs e golpes do Move Tutor; campos extras são descartados."""
    if not isinstance(membros, list) or len(membros) > MAXIMO_MEMBROS:
        return None
    limpos = []
    for m in membros:
        if not isinstance(m, dict):
            return None
        tms, tutor = m.get("tms") or [], m.get("u") or []
        limpos.append({"p": str(m.get("p") or "").strip(), "h": str(m.get("h") or "").strip(),
                       "n": str(m.get("n") or "").strip(), "tms": [str(c) for c in tms if isinstance(c, str)],
                       "u": [str(g) for g in tutor if isinstance(g, str)]})
    return limpos


@app.get("/api/times")
def listar_times():
    with db.conectar() as conn:
        return jsonify([time_json(t) for t in conn.execute("SELECT * FROM times ORDER BY nome COLLATE NOCASE")])


@app.post("/api/times")
def criar_time():
    nome = " ".join(str((request.get_json() or {}).get("nome") or "").split()) or "Novo time"
    with db.conectar() as conn:
        cur = conn.execute("INSERT INTO times (nome) VALUES (?)", (nome,))
        return jsonify(time_json(conn.execute("SELECT * FROM times WHERE id = ?", (cur.lastrowid,)).fetchone())), 201


@app.put("/api/times/<int:time_id>")
def salvar_time(time_id):
    dados = request.get_json() or {}
    nome = " ".join(str(dados.get("nome") or "").split())
    membros = membros_validos(dados.get("membros"))
    if not nome:
        return jsonify(erro="Dê um nome ao time."), 400
    if membros is None:
        return jsonify(erro=f"Um time tem no máximo {MAXIMO_MEMBROS} pokémon."), 400
    with db.conectar() as conn:
        conn.execute("UPDATE times SET nome = ?, membros = ?, atualizado_em = datetime('now', 'localtime') WHERE id = ?",
                     (nome, json.dumps(membros, ensure_ascii=False), time_id))
    return "", 204


@app.delete("/api/times/<int:time_id>")
def remover_time(time_id):
    with db.conectar() as conn:
        conn.execute("DELETE FROM times WHERE id = ?", (time_id,))
    return "", 204


# ---------- Farm (aba Mercado > Farm) ----------

def farm_json(f):
    return {"id": f["id"], "local": f["local"], "data": f["data"], "minutos": f["minutos"],
            "drops": json.loads(f["drops"]), "gastos": json.loads(f["gastos"]), "obs": f["obs"]}


def linhas_farm(lista):
    """[{"i": nome, "q": quantidade > 0}] ou None se inválido."""
    if not isinstance(lista, list):
        return None
    limpas = []
    for l in lista:
        if not isinstance(l, dict):
            return None
        nome, q = " ".join(str(l.get("i") or "").split()), l.get("q")
        if not isinstance(q, (int, float)) or q < 0:
            return None
        limpas.append({"i": nome, "q": q})
    return limpas


@app.get("/api/farms")
def listar_farms():
    with db.conectar() as conn:
        return jsonify([farm_json(f) for f in conn.execute("SELECT * FROM farms ORDER BY data DESC, id DESC")])


@app.post("/api/farms")
def criar_farm():
    local = " ".join(str((request.get_json() or {}).get("local") or "").split())
    with db.conectar() as conn:
        cur = conn.execute("INSERT INTO farms (local) VALUES (?)", (local,))
        return jsonify(farm_json(conn.execute("SELECT * FROM farms WHERE id = ?", (cur.lastrowid,)).fetchone())), 201


@app.put("/api/farms/<int:farm_id>")
def salvar_farm(farm_id):
    dados = request.get_json() or {}
    local = " ".join(str(dados.get("local") or "").split())
    data, minutos = str(dados.get("data") or ""), dados.get("minutos")
    drops, gastos = linhas_farm(dados.get("drops")), linhas_farm(dados.get("gastos"))
    try:
        datetime.strptime(data, "%Y-%m-%d")
    except ValueError:
        return jsonify(erro="Data inválida."), 400
    if not isinstance(minutos, int) or not 1 <= minutos <= 24 * 60:
        return jsonify(erro="A duração vai de 1 minuto a 24 horas."), 400
    if drops is None or gastos is None:
        return jsonify(erro="Drops ou gastos inválidos."), 400
    with db.conectar() as conn:
        conn.execute("UPDATE farms SET local = ?, data = ?, minutos = ?, drops = ?, gastos = ?, obs = ?, "
                     "atualizado_em = datetime('now', 'localtime') WHERE id = ?",
                     (local, data, minutos, json.dumps(drops, ensure_ascii=False), json.dumps(gastos, ensure_ascii=False),
                      str(dados.get("obs") or "").strip(), farm_id))
    return "", 204


@app.delete("/api/farms/<int:farm_id>")
def remover_farm(farm_id):
    with db.conectar() as conn:
        conn.execute("DELETE FROM farms WHERE id = ?", (farm_id,))
    return "", 204


@app.get("/api/precos-npc")
def listar_precos_npc():
    with db.conectar() as conn:
        return jsonify({l["nome"]: l["preco"] for l in conn.execute("SELECT * FROM precos_npc")})


@app.put("/api/precos-npc")
def salvar_preco_npc():
    """{"nome", "preco"}; preco vazio/null apaga (volta a usar o market)."""
    dados = request.get_json() or {}
    nome, preco = " ".join(str(dados.get("nome") or "").split()), dados.get("preco")
    if not nome or (preco is not None and (not isinstance(preco, (int, float)) or preco <= 0)):
        return jsonify(erro="Preço inválido."), 400
    with db.conectar() as conn:
        if preco is None:
            conn.execute("DELETE FROM precos_npc WHERE nome = ?", (nome,))
        else:
            conn.execute("INSERT INTO precos_npc (nome, preco) VALUES (?, ?) ON CONFLICT(nome) DO UPDATE SET preco = excluded.preco",
                         (nome, preco))
    return "", 204


# ---------- Quests (aba Jogo > Quests) ----------

@app.get("/api/quests-feitas")
def listar_quests_feitas():
    with db.conectar() as conn:
        return jsonify({l["quest"]: l["feita_em"] for l in conn.execute("SELECT * FROM quests_feitas")})


@app.put("/api/quests-feitas")
def marcar_quest():
    """{"quest": título na wiki, "feita": true/false}"""
    dados = request.get_json() or {}
    quest = str(dados.get("quest") or "").strip()
    if not quest:
        return jsonify(erro="Quest inválida."), 400
    with db.conectar() as conn:
        if dados.get("feita"):
            conn.execute("INSERT OR IGNORE INTO quests_feitas (quest) VALUES (?)", (quest,))
        else:
            conn.execute("DELETE FROM quests_feitas WHERE quest = ?", (quest,))
    return "", 204


# ---------- Contadores (aba Breeding: ovos chocados) ----------

CONTADORES = {"ovos_chocados"}


@app.get("/api/contadores/<nome>")
def ler_contador(nome):
    if nome not in CONTADORES:
        return jsonify(erro="Contador desconhecido."), 404
    with db.conectar() as conn:
        linha = conn.execute("SELECT valor FROM contadores WHERE nome = ?", (nome,)).fetchone()
    return jsonify(valor=linha["valor"] if linha else 0)


@app.put("/api/contadores/<nome>")
def salvar_contador(nome):
    valor = (request.get_json() or {}).get("valor")
    if nome not in CONTADORES or not isinstance(valor, int) or valor < 0:
        return jsonify(erro="Valor inválido."), 400
    with db.conectar() as conn:
        conn.execute("INSERT INTO contadores (nome, valor) VALUES (?, ?) ON CONFLICT(nome) DO UPDATE SET valor = excluded.valor", (nome, valor))
    return "", 204


@app.get("/api/cronometros")
def listar_cronometros():
    """restante = segundos até acabar (None = parado, 0 = já terminou)."""
    agora = datetime.now()
    with db.conectar() as conn:
        linhas = conn.execute("SELECT * FROM cronometros ORDER BY id").fetchall()
    return jsonify([{
        "id": c["id"], "nome": c["nome"], "segundos": c["segundos"],
        "restante": None if c["fim"] is None else max(0, round((datetime.fromisoformat(c["fim"]) - agora).total_seconds())),
    } for c in linhas])


@app.post("/api/cronometros")
def criar_cronometro():
    dados = request.get_json() or {}
    nome = " ".join(str(dados.get("nome", "")).split())
    segundos = dados.get("segundos")
    if not nome or not isinstance(segundos, int) or not 60 <= segundos <= 7 * 24 * 3600:
        return jsonify(erro="Informe um nome e um tempo entre 1 minuto e 7 dias."), 400
    with db.conectar() as conn:
        cur = conn.execute("INSERT INTO cronometros (nome, segundos) VALUES (?, ?)", (nome, segundos))
    return jsonify(id=cur.lastrowid), 201


@app.post("/api/cronometros/<int:cid>/<acao>")
def acionar_cronometro(cid, acao):
    """iniciar: conta de novo desde agora; parar: zera."""
    with db.conectar() as conn:
        c = conn.execute("SELECT * FROM cronometros WHERE id = ?", (cid,)).fetchone()
        if not c or acao not in ("iniciar", "parar"):
            return jsonify(erro="Cronômetro não encontrado."), 404
        fim = (datetime.now() + timedelta(seconds=c["segundos"])).strftime("%Y-%m-%d %H:%M:%S") if acao == "iniciar" else None
        conn.execute("UPDATE cronometros SET fim = ?, avisado = 0 WHERE id = ?", (fim, cid))
    return "", 204


@app.delete("/api/cronometros/<int:cid>")
def remover_cronometro(cid):
    with db.conectar() as conn:
        conn.execute("DELETE FROM cronometros WHERE id = ?", (cid,))
    return "", 204


@app.get("/api/padrao-geral")
def padrao_geral():
    """Registros de todos os itens, cada um com o mercado e a mediana dos vizinhos dele (a mesma do fora da curva),
    para a análise de dia/horário juntando tudo: cada item é comparado com o próprio normal."""
    with db.conectar() as conn:
        ids = [l["id"] for l in conn.execute("SELECT id FROM itens")]
        return jsonify([
            {"registrado_em": p["registrado_em"], "mercado": p["mercado"], "referencia": p["referencia"], "fora": p["fora"]}
            for i in ids for p in historico_item(conn, i)
        ])


@app.get("/exportar.csv")
def exportar():
    with db.conectar() as conn:
        linhas = conn.execute(
            "SELECT i.nome, i.categoria, p.preco, p.obs, p.registrado_em "
            "FROM precos p JOIN itens i ON i.id = p.item_id "
            "ORDER BY p.registrado_em"
        ).fetchall()
    saida = io.StringIO()
    escritor = csv.writer(saida, delimiter=";")
    escritor.writerow(["item", "categoria", "preco_unitario_hd", "obs", "data"])
    for l in linhas:
        escritor.writerow([l["nome"], l["categoria"], str(l["preco"]).replace(".", ","), l["obs"], l["registrado_em"]])
    return Response(
        "﻿" + saida.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=precos.csv"},
    )


db.inicializar()
