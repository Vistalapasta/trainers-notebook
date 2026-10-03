import re
import sqlite3
from caminhos import DADOS

DB_PATH = DADOS / "precos.db"

# Todos os preços são guardados em HD; o market do jogo mostra em dólares
DOLARES_POR_HD = 100

ITENS_INICIAIS = [
    ("Fire Stone", "Stones"),
    ("Water Stone", "Stones"),
    ("Thunder Stone", "Stones"),
    ("Leaf Stone", "Stones"),
    ("Earth Stone", "Stones"),
    ("Heart Stone", "Stones"),
]

SCHEMA = """
CREATE TABLE IF NOT EXISTS itens (
    id         INTEGER PRIMARY KEY,
    nome       TEXT NOT NULL UNIQUE COLLATE NOCASE,
    categoria  TEXT NOT NULL DEFAULT '',
    criado_em  TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS precos (
    id             INTEGER PRIMARY KEY,
    item_id        INTEGER NOT NULL REFERENCES itens(id) ON DELETE CASCADE,
    preco          REAL NOT NULL,          -- preço por unidade
    obs            TEXT NOT NULL DEFAULT '',
    registrado_em  TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

-- Ofertas lidas de um print do market; o registro em "precos" guarda a menor delas
CREATE TABLE IF NOT EXISTS ofertas (
    id          INTEGER PRIMARY KEY,
    preco_id    INTEGER NOT NULL REFERENCES precos(id) ON DELETE CASCADE,
    jogador     TEXT NOT NULL DEFAULT '',
    quantidade  INTEGER NOT NULL,
    preco       REAL NOT NULL
);

-- Avisos gerados quando um preço novo é registrado (item "ótimo" ou preço-alvo atingido)
-- ou quando um cronômetro termina (sem item)
CREATE TABLE IF NOT EXISTS alertas (
    id         INTEGER PRIMARY KEY,
    item_id    INTEGER REFERENCES itens(id) ON DELETE CASCADE,
    tipo       TEXT NOT NULL,              -- 'otimo', 'alvo' ou 'cronometro'
    mensagem   TEXT NOT NULL,
    lido       INTEGER NOT NULL DEFAULT 0,
    criado_em  TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

-- Times montados na aba Times. membros = JSON com até 6 pokémon:
-- [{"p": nome (pode começar com "Shiny "), "h": held item (nome do item), "n": nature ("" = não escolhida), "tms": ["TM05", ...],
--   "u": golpes do Move Tutor ["Drain Punch", ...]}]
CREATE TABLE IF NOT EXISTS times (
    id             INTEGER PRIMARY KEY,
    nome           TEXT NOT NULL,
    membros        TEXT NOT NULL DEFAULT '[]',
    atualizado_em  TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

-- Contadores do usuário (ex.: "ovos_chocados" na aba Breeding)
CREATE TABLE IF NOT EXISTS contadores (
    nome   TEXT PRIMARY KEY,
    valor  INTEGER NOT NULL DEFAULT 0
);

-- Cronômetros do botão ⏱: o usuário inicia na mão; fim = quando termina (NULL = parado).
-- avisado = 1 depois que o alerta de "terminou" foi criado
CREATE TABLE IF NOT EXISTS cronometros (
    id        INTEGER PRIMARY KEY,
    nome      TEXT NOT NULL,
    segundos  INTEGER NOT NULL,
    fim       TEXT,
    avisado   INTEGER NOT NULL DEFAULT 0
);

-- Sessões de farm (aba Mercado > Farm): onde caçou, quando, quanto tempo, o que dropou e o que gastou.
-- drops e gastos = JSON [{"i": nome do item, "q": quantidade}]
CREATE TABLE IF NOT EXISTS farms (
    id             INTEGER PRIMARY KEY,
    local          TEXT NOT NULL DEFAULT '',
    data           TEXT NOT NULL DEFAULT (date('now', 'localtime')),
    minutos        INTEGER NOT NULL DEFAULT 60,
    drops          TEXT NOT NULL DEFAULT '[]',
    gastos         TEXT NOT NULL DEFAULT '[]',
    obs            TEXT NOT NULL DEFAULT '',
    atualizado_em  TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

-- Preço fixo de NPC (HD por unidade), por nome de item: vale no lugar do market no farm.
-- Não precisa o item estar cadastrado na aba Mercado (loot que só vende no NPC).
CREATE TABLE IF NOT EXISTS precos_npc (
    nome   TEXT PRIMARY KEY COLLATE NOCASE,
    preco  REAL NOT NULL
);

-- Quests marcadas como feitas (aba Jogo > Quests), pelo título da página na wiki (campo "w" de quests.json)
CREATE TABLE IF NOT EXISTS quests_feitas (
    quest     TEXT PRIMARY KEY,
    feita_em  TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE INDEX IF NOT EXISTS idx_precos_item_data ON precos(item_id, registrado_em);
"""


def padronizar(texto):
    """Texto todo em minúsculas ganha iniciais maiúsculas, como o jogo escreve ("shiny stone" -> "Shiny Stone")."""
    texto = " ".join(texto.split())
    return texto.title() if texto == texto.lower() else texto


def categoria_padrao(nome):
    nome = nome.lower()
    if nome.endswith(" stone"):
        return "Stones"
    if re.match(r"(tm|hm)\s*\d+", nome):  # "TM05 - Waterfall": o preço aparece na aba Pokémon
        return "TMs"
    return ""


def conectar():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def inicializar():
    novo = not DB_PATH.exists()
    with conectar() as conn:
        conn.executescript(SCHEMA)
        if conn.execute("PRAGMA user_version").fetchone()[0] < 1:
            # Versão 1: preços passam a ser guardados em HD (antes eram dólares, como o jogo mostra)
            conn.execute("UPDATE precos SET preco = preco / ?", (DOLARES_POR_HD,))
            conn.execute("UPDATE ofertas SET preco = preco / ?", (DOLARES_POR_HD,))
            conn.execute("PRAGMA user_version = 1")
        if conn.execute("PRAGMA user_version").fetchone()[0] < 2:
            # Versão 2: nomes digitados em minúsculas ganham a grafia do jogo e as stones sua categoria
            for item in conn.execute("SELECT id, nome, categoria FROM itens").fetchall():
                nome = padronizar(item["nome"])
                categoria = padronizar(item["categoria"])
                if categoria.lower() in ("stone", "stones") or not categoria:
                    categoria = categoria_padrao(nome) or categoria
                conn.execute("UPDATE itens SET nome = ?, categoria = ? WHERE id = ?", (nome, categoria, item["id"]))
            conn.execute("PRAGMA user_version = 2")
        if conn.execute("PRAGMA user_version").fetchone()[0] < 3:
            # Versão 3: alertas.item_id pode ser NULL (alerta de cronômetro). SQLite não altera NOT NULL: recria a tabela
            if conn.execute("SELECT \"notnull\" FROM pragma_table_info('alertas') WHERE name = 'item_id'").fetchone()[0]:
                conn.executescript("""
                    ALTER TABLE alertas RENAME TO alertas_v2;
                    CREATE TABLE alertas (
                        id         INTEGER PRIMARY KEY,
                        item_id    INTEGER REFERENCES itens(id) ON DELETE CASCADE,
                        tipo       TEXT NOT NULL,
                        mensagem   TEXT NOT NULL,
                        lido       INTEGER NOT NULL DEFAULT 0,
                        criado_em  TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
                    );
                    INSERT INTO alertas SELECT id, item_id, tipo, mensagem, lido, criado_em FROM alertas_v2;
                    DROP TABLE alertas_v2;
                """)
            conn.execute("PRAGMA user_version = 3")
        colunas = {c["name"] for c in conn.execute("PRAGMA table_info(precos)")}
        if "ignorar" not in colunas:
            # NULL = automático (fora da curva decide), 0 = sempre usar, 1 = sempre ignorar
            conn.execute("ALTER TABLE precos ADD COLUMN ignorar INTEGER")
        colunas_itens = {c["name"] for c in conn.execute("PRAGMA table_info(itens)")}
        if "alvo" not in colunas_itens:
            # Preço-alvo em HD: avisa quando o menor preço registrado ficar igual ou abaixo
            conn.execute("ALTER TABLE itens ADD COLUMN alvo REAL")
        if novo:
            conn.executemany(
                "INSERT INTO itens (nome, categoria) VALUES (?, ?)", ITENS_INICIAIS
            )
