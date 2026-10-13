# -*- coding: utf-8 -*-
# debug_ml.py - descobre o que o ML ta retornando

import requests
import re

URL = "https://www.mercadolivre.com.br/fone-de-ouvido-soundcore-by-anker-p20i-graves-poderosos-e-impactantes-bluetooth-53-30h-de-reproducao-resistencia-agua-2-mics-ia-para-chamadas-claras-personalizacao-de-som-via-app-cor-preto/p/MLB24028629"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}

print("Baixando pagina...")
r = requests.get(URL, headers=HEADERS, timeout=20)
print(f"Status: {r.status_code}")
print(f"Tamanho: {len(r.text)} caracteres")
print()

# Salva o HTML pra analisar
with open("C:\\MonitorPrecos\\pagina.html", "w", encoding="utf-8") as f:
    f.write(r.text)
print("HTML salvo em C:\\MonitorPrecos\\pagina.html")

# Procura preco com regex
print("\n=== Procurando padroes de preco ===")
padroes = [
    r'"price":\s*([\d.]+)',
    r'R\$\s*([\d.,]+)',
    r'andes-money-amount__fraction[^>]*>([\d.]+)',
    r'price-tag-fraction[^>]*>([\d.]+)',
]

for p in padroes:
    matches = re.findall(p, r.text[:500000])
    if matches:
        print(f"Padrao {p}")
        print(f"  Achei {len(matches)} ocorrencias")
        print(f"  Primeiras: {matches[:5]}")
    else:
        print(f"Padrao {p}: nada")

# Verifica se tem captcha
if "captcha" in r.text.lower():
    print("\n!! TEM CAPTCHA NA PAGINA !!")
if "blocked" in r.text.lower() or "acesso negado" in r.text.lower():
    print("\n!! ACESSO BLOQUEADO !!")