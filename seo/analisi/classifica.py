#!/usr/bin/env python3
"""Tassonomia condivisa per classificare le URL del sito.

Ogni URL viene classificata su DUE dimensioni ortogonali, perche' le domande
della relazione sono di due tipi diversi:

  1. `tipo`          -> che risorsa e' (prodotto, categoria, marchio, pagina...)
  2. `qualificatore` -> cosa aggiunge la query string / il suffisso
                        (filtro, ordinamento, add_to_cart, paginazione...)

Tenere separate le due dimensioni evita il doppio conteggio: una URL come
  /categoria-prodotto/lampade/?filter_colore=bianco
e' allo stesso tempo "categoria" (tipo) e "filtro" (qualificatore). Sommare
i due valori come se fossero categorie alternative falserebbe le percentuali.

Da queste due dimensioni si deriva `spreco`: True se la richiesta NON ha
valore SEO e quindi rappresenta crawling sprecato.

ATTENZIONE: gli slug in DEFAULT_CONFIG sono i valori tipici di una
installazione WooCommerce italiana, NON sono stati verificati sul sito reale.
Vanno confermati con `analizza_log.py --scopri` prima di fidarsi dei numeri.
"""

from __future__ import annotations

import json
import os
import re
from urllib.parse import unquote, urlsplit, parse_qsl

# --------------------------------------------------------------------------
# Configurazione degli slug: DA VERIFICARE SUL SITO REALE
# --------------------------------------------------------------------------

DEFAULT_CONFIG = {
    # Prefissi di percorso. Vengono confrontati sul primo segmento dell'URL.
    "prodotto": ["prodotto", "product", "shop", "negozio"],
    "categoria_prodotto": ["categoria-prodotto", "product-category", "categoria"],
    "tag_prodotto": ["tag-prodotto", "product-tag"],
    "marchio": [
        "marca", "marche", "marchio", "marchi", "brand", "brands",
        "product-brand", "pwb-brand", "yith_product_brand", "berocket_brand",
    ],
    "articolo": ["blog", "news", "notizie", "magazine", "guide"],
    "categoria_blog": ["category", "categoria-blog", "argomenti"],
    "autore": ["author", "autore"],
    "transazionale": [
        "carrello", "cart", "checkout", "pagamento", "cassa",
        "il-mio-account", "mio-account", "account", "my-account",
        "lista-dei-desideri", "wishlist", "confronta", "compare",
        "ordine-ricevuto", "order-received",
    ],
    "ricerca_path": ["search", "ricerca", "cerca"],
}

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")


def carica_config(percorso: str | None = None) -> dict:
    """Carica config.json se esiste, altrimenti usa i default."""
    percorso = percorso or CONFIG_PATH
    cfg = {k: list(v) for k, v in DEFAULT_CONFIG.items()}
    if os.path.exists(percorso):
        with open(percorso, encoding="utf-8") as fh:
            utente = json.load(fh)
        for chiave, valore in utente.items():
            if chiave.startswith("_"):      # chiavi di commento
                continue
            if isinstance(valore, list):
                cfg[chiave] = valore
    return cfg


# --------------------------------------------------------------------------
# Parametri di query string
# --------------------------------------------------------------------------

# Filtri: WooCommerce layered nav + YITH WooCommerce Ajax Navigation.
PARAM_FILTRO = re.compile(
    r"^(filter_|query_type_|filtering$|filter$|yith_wcan|min_price$|max_price$"
    r"|rating_filter$|product_visibility$|on_sale$|instock$|in_stock$"
    r"|stock_status$|product_tag$|pa_)",
    re.I,
)

# Ordinamento / densita' di risultati.
PARAM_ORDINAMENTO = {
    "orderby", "order", "products-per-page", "per_page", "perpage",
    "count", "columns", "shop_view", "view", "sort",
}

PARAM_ADD_TO_CART = {"add-to-cart", "add_to_cart", "adding-to-cart"}
PARAM_RIMOZIONE = {"removed_item", "remove_item", "undo_item", "removed-item"}
PARAM_RICERCA = {"s", "search", "q", "search_query", "post_type"}
PARAM_PAGINAZIONE = {"paged", "page", "product-page", "pagina"}

PARAM_TRACKING = re.compile(
    r"^(utm_|gclid$|gbraid$|wbraid$|fbclid$|msclkid$|ttclid$|igshid$|_gl$"
    r"|srsltid$|mc_cid$|mc_eid$|ref$|referrer$)",
    re.I,
)

PARAM_TECNICO = {
    "wc-ajax", "wc-api", "preview", "preview_id", "preview_nonce", "p",
    "replytocom", "unapproved", "moderation-hash", "attachment_id",
    "customize_changeset_uuid", "customize_theme", "customize_messenger_channel",
    "elementor-preview", "nocache", "_wpnonce", "wpnonce", "action",
    "doing_wp_cron", "ver", "v", "cache", "et_fb", "vc_editable",
    "wc_cache", "wc-block", "download_file", "coupon-code",
}

# --------------------------------------------------------------------------
# Percorsi tecnici e asset
# --------------------------------------------------------------------------

PATH_TECNICO = re.compile(
    r"^/?(wp-admin/|wp-login\.php|wp-register\.php|xmlrpc\.php|wp-cron\.php"
    r"|wp-json/|\?rest_route|wp-includes/|wp-content/plugins/|wp-content/themes/"
    r"|wp-content/uploads/.*\.(php|txt)$|wp-signup\.php|wp-trackback\.php"
    r"|trackback/|comments/feed|wc-api/|\.well-known/)",
    re.I,
)

ESTENSIONI_ASSET = {
    ".js", ".mjs", ".css", ".map",
    ".png", ".jpg", ".jpeg", ".webp", ".avif", ".gif", ".svg", ".ico", ".bmp",
    ".woff", ".woff2", ".ttf", ".eot", ".otf",
    ".mp4", ".webm", ".mp3", ".zip", ".pdf",
}

PATH_SITEMAP = re.compile(r"(sitemap[^/]*\.xml(\.gz)?$|robots\.txt$)", re.I)

# Data-based permalink dei post: /2024/05/slug/
RE_DATA_PERMALINK = re.compile(r"^/((19|20)\d{2})/(0[1-9]|1[0-2])(/|$)")
RE_PAGINAZIONE_PATH = re.compile(r"/page/(\d+)/?$|/page/(\d+)/")


# --------------------------------------------------------------------------
# Classificazione
# --------------------------------------------------------------------------

def _primo_segmento(percorso: str) -> str:
    parti = [p for p in percorso.strip("/").split("/") if p]
    return parti[0].lower() if parti else ""


def _profondita(percorso: str) -> int:
    return len([p for p in percorso.strip("/").split("/") if p])


def classifica_qualificatore(query: str) -> tuple[str, list[str]]:
    """Classifica la query string. Ritorna (qualificatore, parametri_trovati).

    L'ordine di precedenza e' deliberato: add-to-cart e i filtri sono i
    problemi che ci interessano di piu', quindi vincono sugli altri.
    """
    if not query:
        return "nessuno", []

    coppie = parse_qsl(query, keep_blank_values=True)
    nomi = [n for n, _ in coppie]
    if not nomi:
        # query presente ma non in forma chiave=valore (es. "?12345")
        return "parametro_anomalo", []

    def presente(insieme) -> bool:
        return any(n.lower() in insieme for n in nomi)

    if presente(PARAM_ADD_TO_CART):
        return "add_to_cart", nomi
    if presente(PARAM_RIMOZIONE):
        return "rimozione_carrello", nomi
    if any(PARAM_FILTRO.match(n) for n in nomi):
        return "filtro", nomi
    if presente(PARAM_ORDINAMENTO):
        return "ordinamento", nomi
    # "s" vuoto o post_type da solo non e' una ricerca: richiediamo s/search/q.
    if any(n.lower() in {"s", "search", "q", "search_query"} for n in nomi):
        return "ricerca_interna", nomi
    if presente(PARAM_TECNICO):
        return "parametro_tecnico", nomi
    if any(PARAM_TRACKING.match(n) for n in nomi):
        return "tracking", nomi
    if presente(PARAM_PAGINAZIONE):
        return "paginazione", nomi
    return "parametro_altro", nomi


def classifica_tipo(percorso: str, cfg: dict) -> str:
    """Classifica il percorso (senza query string)."""
    percorso_norm = unquote(percorso or "/")
    if not percorso_norm.startswith("/"):
        percorso_norm = "/" + percorso_norm

    basso = percorso_norm.lower()

    if PATH_SITEMAP.search(basso):
        return "sitemap_robots"
    if PATH_TECNICO.match(basso) or PATH_TECNICO.match(basso.lstrip("/")):
        # gli asset di temi/plugin sono utili al rendering: non sono "tecnici"
        estensione = os.path.splitext(basso.split("?")[0])[1]
        if estensione in ESTENSIONI_ASSET:
            return "asset_statico"
        return "tecnica"

    estensione = os.path.splitext(basso.rstrip("/"))[1]
    if estensione in ESTENSIONI_ASSET:
        return "asset_statico"

    if basso in ("/", ""):
        return "home"

    if basso.rstrip("/").endswith("/feed"):
        return "feed"

    primo = _primo_segmento(basso)

    def in_lista(chiave: str) -> bool:
        return primo in {s.lower() for s in cfg.get(chiave, [])}

    if in_lista("prodotto"):
        return "prodotto"
    if in_lista("categoria_prodotto"):
        # profondita' 2 = /categoria-prodotto/padre/  -> categoria
        # profondita' 3+ = /categoria-prodotto/padre/figlio/ -> sottocategoria
        senza_pagina = RE_PAGINAZIONE_PATH.sub("/", basso)
        return "categoria_prodotto" if _profondita(senza_pagina) <= 2 else "sottocategoria_prodotto"
    if in_lista("tag_prodotto"):
        return "tag_prodotto"
    if in_lista("marchio"):
        return "marchio"
    if in_lista("articolo"):
        return "articolo"
    if in_lista("categoria_blog"):
        return "categoria_blog"
    if in_lista("autore"):
        return "autore"
    if in_lista("transazionale"):
        return "transazionale"
    if in_lista("ricerca_path"):
        return "ricerca_interna"

    if RE_DATA_PERMALINK.match(basso):
        return "articolo"

    return "pagina"


# Tipi che hanno valore SEO e che vogliamo far scansionare liberamente.
TIPI_UTILI = {
    "prodotto", "categoria_prodotto", "sottocategoria_prodotto",
    "marchio", "pagina", "articolo", "categoria_blog", "home",
}

# Qualificatori che rendono la richiesta crawling sprecato.
QUALIFICATORI_SPRECO = {
    "add_to_cart", "rimozione_carrello", "filtro", "ordinamento",
    "ricerca_interna", "parametro_tecnico", "tracking", "parametro_anomalo",
}

TIPI_SPRECO = {"tecnica", "transazionale", "feed", "autore", "ricerca_interna", "tag_prodotto"}


def classifica(url: str, cfg: dict | None = None) -> dict:
    """Classifica una URL (assoluta o relativa) sulle due dimensioni."""
    cfg = cfg if cfg is not None else carica_config()
    pezzi = urlsplit(url if "://" in url else ("http://x" + url if url.startswith("/") else "http://x/" + url))
    percorso = pezzi.path or "/"
    query = pezzi.query

    tipo = classifica_tipo(percorso, cfg)
    qualificatore, parametri = classifica_qualificatore(query)

    # La paginazione via percorso (/page/2/) e' il caso normale in WordPress.
    if qualificatore == "nessuno" and RE_PAGINAZIONE_PATH.search(percorso):
        qualificatore = "paginazione"

    spreco = (
        qualificatore in QUALIFICATORI_SPRECO
        or tipo in TIPI_SPRECO
        or tipo == "sitemap_robots" and False   # sitemap/robots: neutro
    )
    # La paginazione NON e' spreco: serve a scoprire i prodotti.
    if qualificatore == "paginazione" and tipo in TIPI_UTILI:
        spreco = False

    return {
        "url": url,
        "percorso": percorso,
        "query": query,
        "tipo": tipo,
        "qualificatore": qualificatore,
        "parametri": parametri,
        "utile": tipo in TIPI_UTILI and not spreco,
        "spreco": spreco,
        "asset": tipo == "asset_statico",
    }


if __name__ == "__main__":
    import sys
    cfg = carica_config()
    sorgente = sys.stdin if len(sys.argv) == 1 else iter(sys.argv[1:])
    for riga in sorgente:
        riga = riga.strip()
        if not riga:
            continue
        r = classifica(riga, cfg)
        marca = "SPRECO" if r["spreco"] else ("utile" if r["utile"] else "-")
        print(f"{marca:7} {r['tipo']:26} {r['qualificatore']:20} {riga}")
