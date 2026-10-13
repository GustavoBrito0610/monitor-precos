# -*- coding: utf-8 -*-
# app.py - interface web com Streamlit

import streamlit as st
import plotly.graph_objects as go
from datetime import datetime

import db


st.set_page_config(page_title="Monitor de Precos", page_icon="🔔", layout="wide")


# ============================================================
# SESSAO
# ============================================================
if "usuario" not in st.session_state:
    st.session_state.usuario = None

db.init_db()


# ============================================================
# HELPERS
# ============================================================
def tela_login():
    st.title("🔔 Monitor de Precos")
    st.caption("Receba alerta no Telegram quando o preco baixar")

    tab1, tab2 = st.tabs(["Entrar", "Criar conta"])

    with tab1:
        with st.form("login"):
            email = st.text_input("Email")
            senha = st.text_input("Senha", type="password")
            ok = st.form_submit_button("Entrar", use_container_width=True)
        if ok:
            u = db.login(email, senha)
            if u:
                st.session_state.usuario = u
                st.rerun()
            else:
                st.error("Email ou senha errados")

    with tab2:
        with st.form("cadastro"):
            nome = st.text_input("Nome")
            email = st.text_input("Email", key="cad_email")
            senha = st.text_input("Senha", type="password", key="cad_senha")
            chat_id = st.text_input(
                "Telegram Chat ID (opcional)",
                help="Manda /start pro @userinfobot pra descobrir seu ID",
            )
            ok = st.form_submit_button("Criar conta", use_container_width=True)
        if ok:
            if not nome or not email or not senha:
                st.error("Preenche tudo")
            else:
                ok, msg = db.criar_usuario(nome, email, senha, chat_id or None)
                if ok:
                    st.success("Conta criada! Faz login.")
                else:
                    st.error(msg)


def tela_app(u):
    col1, col2 = st.columns([6, 1])
    with col1:
        st.title(f"🔔 Ola, {u['nome']}!")
    with col2:
        if st.button("Sair"):
            st.session_state.usuario = None
            st.rerun()

    # Chat ID
    if not u["telegram_chat_id"]:
        st.warning("⚠️ Voce nao configurou seu Chat ID do Telegram. Sem isso voce nao recebe alertas!")
        with st.expander("Como configurar o Chat ID"):
            st.markdown("""
1. Abre o Telegram e busca **@userinfobot**
2. Manda `/start`
3. Ele te da um numero tipo `8047141839`
4. Cola aqui embaixo
            """)
        novo = st.text_input("Seu Chat ID")
        if st.button("Salvar Chat ID"):
            db.atualizar_chat_id(u["id"], novo)
            st.success("Salvo!")
            st.rerun()

    st.divider()

    # Adicionar produto
    st.subheader("Adicionar produto")
    with st.form("add_produto"):
        c1, c2, c3 = st.columns([3, 4, 1])
        with c1:
            nome = st.text_input("Nome")
        with c2:
            url = st.text_input("URL (Amazon)")
        with c3:
            alvo = st.number_input("Preco alvo (R$)", min_value=0.01, value=100.0, step=1.0)
        ok = st.form_submit_button("Adicionar")
    if ok:
        if not nome or not url:
            st.error("Preenche nome e URL")
        else:
            db.adicionar_produto(u["id"], nome, url, alvo)
            st.success("Produto adicionado!")
            st.rerun()

    st.divider()

    # Lista
    st.subheader("Meus produtos")
    produtos = db.listar_produtos(u["id"])
    if not produtos:
        st.info("Nenhum produto cadastrado ainda.")
        return

    for p in produtos:
        with st.expander(f"📦 {p['nome']} — R$ {p['ultimo_preco'] or 0:.2f}"):
            c1, c2 = st.columns([3, 1])
            with c1:
                st.write(f"**URL:** {p['url']}")
                st.write(f"**Alvo:** R$ {p['preco_alvo']:.2f}")
                st.write(f"**Ultimo preco:** R$ {p['ultimo_preco'] or 0:.2f}")
            with c2:
                if st.button("Remover", key=f"del_{p['id']}"):
                    db.remover_produto(p["id"], u["id"])
                    st.rerun()

            # Historico
            hist = db.historico_produto(p["id"], 100)
            if len(hist) >= 2:
                precos = [h["preco"] for h in hist]
                datas = [h["verificado_em"] for h in hist]
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=datas, y=precos, mode="lines+markers",
                    line=dict(color="#00D4FF", width=3),
                    name="Preco"
                ))
                fig.add_hline(y=p["preco_alvo"], line_dash="dash",
                              line_color="red", annotation_text="Alvo")
                fig.update_layout(
                    height=300, margin=dict(l=10, r=10, t=10, b=10),
                    template="plotly_dark", showlegend=False,
                )
                st.plotly_chart(fig, use_container_width=True)


# ============================================================
# MAIN
# ============================================================
if st.session_state.usuario:
    tela_app(st.session_state.usuario)
else:
    tela_login()