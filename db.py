# -*- coding: utf-8 -*-
# db.py - banco de dados SQLite

import os
import sqlite3
import hashlib
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dados.db")


# ============================================================
# CONEXAO
# ============================================================
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Cria as tabelas se nao existirem."""
    conn = get_conn()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            senha_hash TEXT NOT NULL,
            telegram_chat_id TEXT,
            criado_em TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS produtos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER NOT NULL,
            nome TEXT NOT NULL,
            url TEXT NOT NULL,
            preco_alvo REAL NOT NULL,
            ultimo_preco REAL,
            ativo INTEGER DEFAULT 1,
            criado_em TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS historico (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            produto_id INTEGER NOT NULL,
            preco REAL NOT NULL,
            verificado_em TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (produto_id) REFERENCES produtos(id)
        )
    """)

    conn.commit()
    conn.close()


# ============================================================
# HASH DE SENHA
# ============================================================
def hash_senha(senha):
    return hashlib.sha256(senha.encode("utf-8")).hexdigest()


# ============================================================
# USUARIOS
# ============================================================
def criar_usuario(nome, email, senha, telegram_chat_id=None):
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO usuarios (nome, email, senha_hash, telegram_chat_id) VALUES (?, ?, ?, ?)",
            (nome, email.lower().strip(), hash_senha(senha), telegram_chat_id)
        )
        conn.commit()
        return True, "Usuario criado"
    except sqlite3.IntegrityError:
        return False, "Email ja cadastrado"
    finally:
        conn.close()


def login(email, senha):
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM usuarios WHERE email = ? AND senha_hash = ?",
        (email.lower().strip(), hash_senha(senha))
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_usuario(usuario_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM usuarios WHERE id = ?", (usuario_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def atualizar_chat_id(usuario_id, chat_id):
    conn = get_conn()
    conn.execute("UPDATE usuarios SET telegram_chat_id = ? WHERE id = ?", (chat_id, usuario_id))
    conn.commit()
    conn.close()


# ============================================================
# PRODUTOS
# ============================================================
def adicionar_produto(usuario_id, nome, url, preco_alvo):
    conn = get_conn()
    conn.execute(
        "INSERT INTO produtos (usuario_id, nome, url, preco_alvo) VALUES (?, ?, ?, ?)",
        (usuario_id, nome, url, preco_alvo)
    )
    conn.commit()
    conn.close()


def listar_produtos(usuario_id):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM produtos WHERE usuario_id = ? AND ativo = 1 ORDER BY id DESC",
        (usuario_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def listar_todos_produtos_ativos():
    """Pra usar no monitor (todos usuarios)."""
    conn = get_conn()
    rows = conn.execute("""
        SELECT p.*, u.telegram_chat_id, u.nome as usuario_nome
        FROM produtos p
        JOIN usuarios u ON u.id = p.usuario_id
        WHERE p.ativo = 1
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def remover_produto(produto_id, usuario_id):
    conn = get_conn()
    conn.execute(
        "DELETE FROM produtos WHERE id = ? AND usuario_id = ?",
        (produto_id, usuario_id)
    )
    conn.commit()
    conn.close()


def atualizar_preco(produto_id, novo_preco):
    conn = get_conn()
    conn.execute("UPDATE produtos SET ultimo_preco = ? WHERE id = ?", (novo_preco, produto_id))
    conn.execute(
        "INSERT INTO historico (produto_id, preco) VALUES (?, ?)",
        (produto_id, novo_preco)
    )
    conn.commit()
    conn.close()


# ============================================================
# HISTORICO
# ============================================================
def historico_produto(produto_id, limite=100):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM historico WHERE produto_id = ? ORDER BY verificado_em DESC LIMIT ?",
        (produto_id, limite)
    ).fetchall()
    conn.close()
    return [dict(r) for r in reversed(rows)]


# ============================================================
# INIT
# ============================================================
if __name__ == "__main__":
    init_db()
    print(f"Banco criado/atualizado em {DB_PATH}")