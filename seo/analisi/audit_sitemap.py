#!/usr/bin/env python3
"""Audit di sitemap_index.xml e di tutte le sitemap collegate.

Risponde a Q7 e Q8 della relazione:
  Q7 - la sitemap contiene SOLO URL che vogliamo far indicizzare?
  Q8 - esistono conflitti fra canonical, noindex e robots.txt?

Il conflitto piu' grave e' una URL presente in sitemap ma bloccata da
robots.txt: stiamo dicendo a Google "indicizza questa" e insieme "non
leggerla". Google segnala l'incoerenza e non indicizza.

Il secondo, meno visibile: una URL in sitemap che ha noindex o un canonical
verso un'altra pagina. La sitemap perde autorevolezza come segnale.

Richiede accesso di rete al sito. Va eseguito da una macchina che raggiunge
www.tuttoluce.com (il server stesso va benissimo).

  # audit strutturale (veloce, solo le sitemap)
  python3 audit_sitemap.py https://www.tuttoluce.com/sitemap_index.xml

  # con verifica dei conflitti robots.txt
  python3 audit_sitemap.py https://www.tuttoluce.com/sitemap_index.xml \
      --robots https://www.tuttoluce.com/robots.txt

  # con controllo canonical/noindex su un campione di pagine (lento)
  python3 audit_sitemap.py https://www.tuttoluce.com/sitemap_index.xml \
      --robots https://www.tuttoluce.com/robots.txt \
      --campione-canonical 60 --pausa 0.5

  # esporta l'elenco completo delle URL in sitemap
  python3 audit_sitemap.py <indice> --esporta-url sitemap_urls.txt
"""

from __future__ import annotations

import argparse
import collections
import gzip
import io
import re
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET

from classifica import carica_config, classifica

UA = "Mozilla/5.0 (compatible; audit-seo-tuttoluce)"
NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}


def scarica(url: str, timeout: int = 30) -> bytes:
    richiesta = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(richiesta, timeout=timeout) as risposta:
        dati = risposta.read()
    if url.endswith(".gz") or dati[:2] == b"\x1f\x8b":
        dati = gzip.decompress(dati)
    return dati


def _testo(elemento, tag: str) -> str | None:
    trovato = elemento.find(f"sm:{tag}", NS)
    if trovato is None:
        trovato = elemento.find(tag)
    return trovato.text.strip() if trovato is not None and trovato.text else None


def leggi_sitemap(url: str) -> tuple[str, list[dict]]:
    """Ritorna (tipo, voci). tipo e' 'index' oppure 'urlset'."""
    radice = ET.fromstring(scarica(url))
    etichetta = radice.tag.split("}")[-1]

    if etichetta == "sitemapindex":
        voci = []
        for nodo in radice.findall("sm:sitemap", NS) or radice.findall("sitemap"):
            loc = _testo(nodo, "loc")
            if loc:
                voci.append({"loc": loc, "lastmod": _testo(nodo, "lastmod")})
        return "index", voci

    voci = []
    for nodo in radice.findall("sm:url", NS) or radice.findall("url"):
        loc = _testo(nodo, "loc")
        if loc:
            voci.append({
                "loc": loc,
                "lastmod": _testo(nodo, "lastmod"),
                "changefreq": _testo(nodo, "changefreq"),
                "priority": _testo(nodo, "priority"),
            })
    return "urlset", voci


RE_CANONICAL = re.compile(
    r"""<link[^>]+rel=["']canonical["'][^>]*href=["']([^"']+)["']""", re.I)
RE_CANONICAL_INV = re.compile(
    r"""<link[^>]+href=["']([^"']+)["'][^>]*rel=["']canonical["']""", re.I)
RE_META_ROBOTS = re.compile(
    r"""<meta[^>]+name=["']robots["'][^>]*content=["']([^"']+)["']""", re.I)
RE_META_ROBOTS_INV = re.compile(
    r"""<meta[^>]+content=["']([^"']+)["'][^>]*name=["']robots["']""", re.I)


def ispeziona_pagina(url: str, timeout: int = 25) -> dict:
    """Legge canonical, meta robots e X-Robots-Tag di una pagina."""
    try:
        richiesta = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(richiesta, timeout=timeout) as risposta:
            stato = risposta.status
            intestazioni = {k.lower(): v for k, v in risposta.headers.items()}
            html = risposta.read(400_000).decode("utf-8", errors="replace")
    except Exception as errore:                      # noqa: BLE001
        return {"url": url, "errore": str(errore)}

    m = RE_CANONICAL.search(html) or RE_CANONICAL_INV.search(html)
    canonical = m.group(1).strip() if m else None
    m = RE_META_ROBOTS.search(html) or RE_META_ROBOTS_INV.search(html)
    meta_robots = m.group(1).strip().lower() if m else None
    x_robots = intestazioni.get("x-robots-tag", "").lower() or None

    noindex = bool(
        (meta_robots and "noindex" in meta_robots)
        or (x_robots and "noindex" in x_robots)
    )
    return {
        "url": url,
        "stato": stato,
        "canonical": canonical,
        "meta_robots": meta_robots,
        "x_robots_tag": x_robots,
        "noindex": noindex,
        "canonical_diverso": bool(canonical and canonical.rstrip("/") != url.rstrip("/")),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("indice", help="URL di sitemap_index.xml")
    ap.add_argument("--robots", help="robots.txt (file o URL) per il controllo dei conflitti")
    ap.add_argument("--campione-canonical", type=int, default=0,
                    help="quante pagine ispezionare per canonical/noindex (0 = nessuna)")
    ap.add_argument("--pausa", type=float, default=0.4,
                    help="secondi fra le richieste HTTP (default 0.4)")
    ap.add_argument("--esporta-url", help="scrive tutte le URL trovate in un file")
    ap.add_argument("--config", help="percorso di config.json")
    args = ap.parse_args()

    cfg = carica_config(args.config)

    robots = None
    if args.robots:
        from robots_matcher import Robots
        robots = (Robots.da_url(args.robots) if args.robots.startswith("http")
                  else Robots.da_file(args.robots))

    print(f"{'=' * 74}\nAUDIT SITEMAP: {args.indice}\n{'=' * 74}")

    try:
        tipo, voci = leggi_sitemap(args.indice)
    except Exception as errore:                      # noqa: BLE001
        print(f"ERRORE nel leggere l'indice: {errore}", file=sys.stderr)
        return 1

    if tipo == "index":
        print(f"indice con {len(voci)} sitemap collegate:\n")
        sotto_sitemap = [v["loc"] for v in voci]
    else:
        print("ATTENZIONE: l'URL fornito non e' un indice ma una sitemap singola.\n")
        sotto_sitemap = [args.indice]

    tutte: list[str] = []
    per_sitemap: dict[str, list[str]] = {}

    for loc in sotto_sitemap:
        try:
            _, elementi = leggi_sitemap(loc)
        except Exception as errore:                  # noqa: BLE001
            print(f"  [ERRORE] {loc}\n           {errore}")
            continue
        url_trovate = [e["loc"] for e in elementi]
        per_sitemap[loc] = url_trovate
        tutte.extend(url_trovate)
        print(f"  {len(url_trovate):>7,} URL   {loc}")
        time.sleep(args.pausa)

    if not tutte:
        print("\nNessuna URL trovata nelle sitemap.")
        return 1

    print(f"\ntotale URL in sitemap: {len(tutte):,}")
    unici = set(tutte)
    print(f"URL distinte         : {len(unici):,}")

    duplicati = [u for u, n in collections.Counter(tutte).items() if n > 1]
    if duplicati:
        print(f"\n!! DUPLICATI: {len(duplicati)} URL compaiono piu' volte nelle sitemap")
        for u in duplicati[:10]:
            print(f"   {u}")

    # --- composizione per tipo (Q7) --------------------------------------
    print(f"\n--- COMPOSIZIONE DELLA SITEMAP ---")
    tipi: collections.Counter = collections.Counter()
    qualificatori: collections.Counter = collections.Counter()
    sospette: list[str] = []
    for u in unici:
        info = classifica(u, cfg)
        tipi[info["tipo"]] += 1
        qualificatori[info["qualificatore"]] += 1
        if info["spreco"] or info["qualificatore"] != "nessuno":
            sospette.append(u)

    print(f"  {'tipo':30} {'URL':>9} {'quota':>8}")
    print(f"  {'-' * 30} {'-' * 9} {'-' * 8}")
    for t, n in tipi.most_common():
        print(f"  {t:30} {n:>9,} {100.0 * n / len(unici):>7.1f}%")

    if len(qualificatori) > 1 or "nessuno" not in qualificatori:
        print(f"\n  query string presenti nelle URL di sitemap:")
        for q, n in qualificatori.most_common():
            marca = "" if q == "nessuno" else "  <-- da rimuovere dalla sitemap"
            print(f"    {q:28} {n:>9,}{marca}")

    if sospette:
        print(f"\n!! {len(sospette)} URL in sitemap NON dovrebbero esserci")
        print("   (filtri, parametri, URL tecniche: la sitemap deve contenere")
        print("    solo URL canoniche che vogliamo indicizzare)")
        for u in sospette[:15]:
            print(f"   {u}")

    # --- conflitto sitemap / robots.txt (Q8) -----------------------------
    if robots is not None:
        bloccate = [u for u in unici if robots.bloccato(u)]
        print(f"\n--- CONFLITTO SITEMAP / ROBOTS.TXT (Q8) ---")
        if bloccate:
            print(f"!! {len(bloccate)} URL sono in sitemap MA bloccate da robots.txt.")
            print("   E' un segnale contraddittorio: Google non le indicizzera'.")
            print("   Va risolto togliendole dalla sitemap oppure sbloccandole.\n")
            for u in bloccate[:15]:
                _, regola = robots.spiega(u)
                print(f"   {u}\n      bloccata da: {regola}")
            if len(bloccate) > 15:
                print(f"   ... e altre {len(bloccate) - 15}")
        else:
            print("OK - nessuna URL di sitemap e' bloccata da robots.txt.")

    # --- canonical / noindex a campione (Q8) -----------------------------
    if args.campione_canonical > 0:
        import random
        campione = random.sample(sorted(unici), min(args.campione_canonical, len(unici)))
        print(f"\n--- CANONICAL / NOINDEX su {len(campione)} pagine a campione ---")
        problemi_noindex, problemi_canonical, errori = [], [], []
        for i, u in enumerate(campione, 1):
            esito = ispeziona_pagina(u)
            if "errore" in esito:
                errori.append(esito)
            else:
                if esito["noindex"]:
                    problemi_noindex.append(esito)
                if esito["canonical_diverso"]:
                    problemi_canonical.append(esito)
            if i % 10 == 0:
                print(f"    ...{i}/{len(campione)}")
            time.sleep(args.pausa)

        print(f"\n  pagine con NOINDEX ma presenti in sitemap: {len(problemi_noindex)}")
        for e in problemi_noindex[:10]:
            print(f"    {e['url']}\n       robots: {e['meta_robots'] or e['x_robots_tag']}")
        print(f"\n  pagine con CANONICAL verso un'altra URL: {len(problemi_canonical)}")
        for e in problemi_canonical[:10]:
            print(f"    {e['url']}\n       canonical -> {e['canonical']}")
        if errori:
            print(f"\n  pagine non raggiungibili: {len(errori)}")
            for e in errori[:10]:
                print(f"    {e['url']}  ({e['errore']})")

        if not problemi_noindex and not problemi_canonical and not errori:
            print("  OK - nessun conflitto canonical/noindex nel campione.")

    if args.esporta_url:
        with open(args.esporta_url, "w", encoding="utf-8") as fh:
            for u in sorted(unici):
                fh.write(u + "\n")
        print(f"\nesportate {len(unici):,} URL in {args.esporta_url}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
