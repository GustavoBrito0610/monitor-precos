# -*- coding: utf-8 -*-
# monitor.py - Monitor de precos multi-usuario + multi-loja

import os
import sys
import time
import re
import json
import logging
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import schedule

import db
from config import TELEGRAM_TOKEN, INTERVALO_MINUTOS


LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "monitor.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ]
)
log = logging.getLogger(__name__)


# ============================================================
# TELEGRAM
# ============================================================
def enviar_telegram(chat_id, mensagem):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        r = requests.post(url, json={"chat_id": chat_id, "text": mensagem}, timeout=10)
        return r.status_code == 200
    except Exception as e:
        log.error(f"erro telegram: {e}")
        return False


# ============================================================
# HEADERS
# ============================================================
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}


# ============================================================
# HELPER - converte texto de preco pra float
# ============================================================
def _texto_para_float(txt):
    """Converte '1.234,56' ou '1234.56' ou 'R$ 199' em float."""
    if not txt:
        return None
    txt = str(txt).replace("R$", "").strip()
    # Detecta formato BR (com virgula) vs US (com ponto)
    if "," in txt:
        txt = txt.replace(".", "").replace(",", ".")
    m = re.search(r"(\d+\.?\d*)", txt)
    if m:
        try:
            v = float(m.group(1))
            return v if v > 0 else None
        except ValueError:
            return None
    return None


# ============================================================
# AMAZON
# ============================================================
def pegar_preco_amazon(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        if r.status_code != 200:
            log.warning(f"[amazon] status {r.status_code}")
            return None

        soup = BeautifulSoup(r.text, "html.parser")
        seletores = [
            "span.a-price-whole",
            "span.priceToPay span.a-price-whole",
            "span#priceblock_ourprice",
            "span#priceblock_dealprice",
            "span.a-offscreen",
        ]
        for sel in seletores:
            el = soup.select_one(sel)
            if el:
                preco = _texto_para_float(el.get_text())
                if preco:
                    return preco
        return None
    except Exception as e:
        log.error(f"[amazon] {e}")
        return None


# ============================================================
# KABUM
# ============================================================
def pegar_preco_kabum(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        log.info(f"[kabum] status {r.status_code}, {len(r.text)} chars")

        if r.status_code != 200:
            return None

        html = r.text

        # 1) Meta tag (mais confiavel)
        m = re.search(r'<meta[^>]+property=["\']product:price:amount["\'][^>]+content=["\']([\d.,]+)["\']', html)
        if m:
            preco = _texto_para_float(m.group(1))
            if preco:
                log.info(f"[kabum] via meta: R$ {preco}")
                return preco

        # 2) JSON-LD (structured data)
        for script in re.findall(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', html, re.DOTALL):
            try:
                data = json.loads(script)
                items = data if isinstance(data, list) else [data]
                for item in items:
                    if isinstance(item, dict) and item.get("@type") == "Product":
                        offers = item.get("offers", {})
                        if isinstance(offers, list):
                            offers = offers[0] if offers else {}
                        preco = offers.get("price") or offers.get("lowPrice")
                        if preco:
                            p = _texto_para_float(preco)
                            if p:
                                log.info(f"[kabum] via JSON-LD: R$ {p}")
                                return p
            except Exception:
                continue

        # 3) Regex "finalPrice" (Kabum usa styled-components, as classes mudam)
        m = re.search(r'["\']price["\']\s*:\s*["\']?(\d+\.?\d*)', html)
        if m:
            preco = _texto_para_float(m.group(1))
            if preco:
                log.info(f"[kabum] via price key: R$ {preco}")
                return preco

        # 4) Regex generico "R$ XXX,XX"
        matches = re.findall(r'R\$\s*([\d.]+,\d{2})', html)
        if matches:
            precos = [_texto_para_float(x) for x in matches]
            precos = [p for p in precos if p and p > 0]
            if precos:
                # Pega o MENOR preco (geralmente e o principal, sem parcelamento)
                preco = min(precos)
                log.info(f"[kabum] via regex generico: R$ {preco}")
                return preco

        log.warning(f"[kabum] nao achei preco no HTML")
        return None

    except Exception as e:
        log.error(f"[kabum] erro: {e}")
        return None


# ============================================================
# DISPATCHER
# ============================================================
def pegar_preco(url):
    url_lower = url.lower()
    if "amazon" in url_lower:
        return pegar_preco_amazon(url)
    elif "kabum" in url_lower:
        return pegar_preco_kabum(url)
    else:
        log.warning(f"loja nao suportada: {url}")
        return None


# ============================================================
# MONITOR
# ============================================================
def verificar_todos():
    produtos = db.listar_todos_produtos_ativos()
    log.info(f"verificando {len(produtos)} produtos...")

    for p in produtos:
        nome = p["nome"]
        url = p["url"]
        alvo = p["preco_alvo"]
        ultimo = p["ultimo_preco"]
        chat_id = p["telegram_chat_id"]
        produto_id = p["id"]

        preco = pegar_preco(url)
        if preco is None:
            log.warning(f"[X] {nome}: nao consegui pegar preco")
            continue

        db.atualizar_preco(produto_id, preco)

        emoji = "ALVO" if preco <= alvo else "ok"
        log.info(f"[{emoji}] {nome}: R$ {preco:.2f} (alvo: R$ {alvo:.2f})")

        if not chat_id:
            continue

        if preco <= alvo:
            enviar_telegram(chat_id,
                f"🔔 PRECO BAIXOU!\n\n"
                f"{nome}\n"
                f"R$ {preco:.2f}\n"
                f"Alvo: R$ {alvo:.2f}\n\n"
                f"{url}"
            )
            log.info(f"-> ALERTA enviado para {p['usuario_nome']}")

        elif ultimo and preco < ultimo:
            enviar_telegram(chat_id,
                f"📉 Preco caiu\n\n{nome}\nDe R$ {ultimo:.2f} por R$ {preco:.2f}\n\n{url}"
            )


# ============================================================
# MAIN
# ============================================================
def main():
    db.init_db()
    log.info("=" * 60)
    log.info("  MONITOR DE PRECOS - Multi-usuario + Multi-loja")
    log.info("=" * 60)

    verificar_todos()
    schedule.every(INTERVALO_MINUTOS).minutes.do(verificar_todos)
    log.info(f"Verificando a cada {INTERVALO_MINUTOS} min")

    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log.info("encerrado")