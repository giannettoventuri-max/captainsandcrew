#!/usr/bin/env python3
"""Analizza i log del server per capire cosa richiede REALMENTE Googlebot.

Risponde alle domande Q3 e Q4 della relazione:
  Q3 - quali URL stanno consumando crawling inutilmente?
  Q4 - quanto crawling va a parametri, filtri, add-to-cart, URL tecniche?

e, con --taglio, alla sezione ANALISI PRIMA/DOPO.

Uso tipico sul server (vedi ../raccolta_dati.md):

  # 1. panoramica dei primi segmenti di percorso, per verificare gli slug reali
  python3 analizza_log.py /var/log/nginx/access.log* --scopri

  # 2. analisi completa
  python3 analizza_log.py /var/log/nginx/access.log* --report

  # 3. confronto prima/dopo la modifica del robots.txt
  python3 analizza_log.py /var/log/nginx/access.log* --taglio 2026-07-15

  # 4. quante richieste il robots.txt attuale avrebbe evitato
  python3 analizza_log.py /var/log/nginx/access.log* --robots /percorso/robots.txt

  # 5. esporta le URL distinte per robots_check.py
  python3 analizza_log.py /var/log/nginx/access.log* --esporta-url urls.txt

Formati supportati: Apache/Nginx "combined" e "common", anche .gz.
"""

from __future__ import annotations

import argparse
import collections
import datetime as dt
import glob
import gzip
import io
import os
import re
import sys

from classifica import carica_config, classifica

# --------------------------------------------------------------------------
# Parsing dei log
# --------------------------------------------------------------------------

# combined: host - - [data] "METODO percorso protocollo" stato byte "referer" "ua"
RE_LOG = re.compile(
    r'^(?P<host>\S+)\s+\S+\s+(?P<utente>\S+)\s+'
    r'\[(?P<data>[^\]]+)\]\s+'
    r'"(?P<metodo>[A-Z_]+)\s+(?P<percorso>[^"]*?)\s+(?P<protocollo>HTTP/[\d.]+)"\s+'
    r'(?P<stato>\d{3})\s+(?P<byte>\S+)'
    r'(?:\s+"(?P<referer>[^"]*)"\s+"(?P<ua>[^"]*)")?'
)

MESI = {
    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
    "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12,
}

# Tutti i crawler della famiglia Google che possono comparire nei log.
RE_BOT_GOOGLE = re.compile(
    r"(Googlebot|Googlebot-Image|Googlebot-Video|Googlebot-News|Storebot-Google"
    r"|Google-InspectionTool|GoogleOther|Google-Extended|AdsBot-Google"
    r"|Mediapartners-Google|APIs-Google|FeedFetcher-Google)",
    re.I,
)

RE_ALTRI_BOT = re.compile(
    r"(bingbot|Yandex|Baiduspider|DuckDuckBot|Applebot|facebookexternalhit"
    r"|Twitterbot|SemrushBot|AhrefsBot|MJ12bot|DotBot|PetalBot|Bytespider"
    r"|GPTBot|ClaudeBot|CCBot|PerplexityBot)",
    re.I,
)


def apri(percorso: str):
    if percorso.endswith(".gz"):
        return io.TextIOWrapper(gzip.open(percorso, "rb"), encoding="utf-8", errors="replace")
    return open(percorso, encoding="utf-8", errors="replace")


def parse_data(testo: str) -> dt.date | None:
    # formato: 10/Oct/2026:13:55:36 +0200
    try:
        giorno = int(testo[0:2])
        mese = MESI[testo[3:6]]
        anno = int(testo[7:11])
        return dt.date(anno, mese, giorno)
    except (ValueError, KeyError, IndexError):
        return None


def espandi(percorsi: list[str]) -> list[str]:
    risultato: list[str] = []
    for p in percorsi:
        trovati = sorted(glob.glob(p))
        if trovati:
            risultato.extend(f for f in trovati if os.path.isfile(f))
        elif os.path.isfile(p):
            risultato.append(p)
        else:
            print(f"ATTENZIONE: nessun file per '{p}'", file=sys.stderr)
    return risultato


# --------------------------------------------------------------------------
# Aggregazione
# --------------------------------------------------------------------------

class Aggregato:
    def __init__(self, nome: str):
        self.nome = nome
        self.totale = 0
        self.per_tipo: collections.Counter = collections.Counter()
        self.per_qualificatore: collections.Counter = collections.Counter()
        self.per_stato: collections.Counter = collections.Counter()
        self.stato_per_tipo: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
        self.spreco = 0
        self.utile = 0
        self.asset = 0
        self.byte = 0
        self.url_distinte: set[str] = set()
        self.top_spreco: collections.Counter = collections.Counter()
        self.top_utile: collections.Counter = collections.Counter()
        self.parametri: collections.Counter = collections.Counter()
        self.giorni: collections.Counter = collections.Counter()
        self.bloccate_da_robots = 0

    def aggiungi(self, info: dict, stato: str, byte: int, giorno, robots=None) -> None:
        self.totale += 1
        self.per_tipo[info["tipo"]] += 1
        self.per_qualificatore[info["qualificatore"]] += 1
        self.per_stato[stato] += 1
        self.stato_per_tipo[info["tipo"]][stato] += 1
        self.byte += byte
        if giorno:
            self.giorni[giorno] += 1
        self.url_distinte.add(info["url"])
        for nome in info["parametri"]:
            self.parametri[nome] += 1

        if info["asset"]:
            self.asset += 1
        elif info["spreco"]:
            self.spreco += 1
            self.top_spreco[info["url"]] += 1
        elif info["utile"]:
            self.utile += 1
            self.top_utile[info["percorso"]] += 1

        if robots is not None and robots.bloccato(info["url"]):
            self.bloccate_da_robots += 1


def _pct(parte: int, totale: int) -> str:
    return f"{(100.0 * parte / totale):.1f}%" if totale else "-"


def stampa_aggregato(agg: Aggregato, robots_usato: bool, top: int) -> None:
    t = agg.totale
    print(f"\n{'=' * 74}\n{agg.nome}\n{'=' * 74}")
    if not t:
        print("nessuna richiesta nel periodo")
        return

    print(f"richieste totali      : {t:,}")
    print(f"URL distinte          : {len(agg.url_distinte):,}")
    print(f"traffico              : {agg.byte / 1024 / 1024:,.1f} MB")
    if agg.giorni:
        giorni = len(agg.giorni)
        print(f"giorni coperti        : {giorni}  ({min(agg.giorni)} -> {max(agg.giorni)})")
        print(f"media richieste/giorno: {t / giorni:,.0f}")

    print(f"\n  URL UTILI (prodotti, categorie, marchi, pagine, articoli)")
    print(f"    {agg.utile:>9,}  {_pct(agg.utile, t):>7}")
    print(f"  ASSET (css/js/immagini: servono al rendering, non sono spreco)")
    print(f"    {agg.asset:>9,}  {_pct(agg.asset, t):>7}")
    print(f"  SPRECO (filtri, ordinamenti, add-to-cart, tecniche)")
    print(f"    {agg.spreco:>9,}  {_pct(agg.spreco, t):>7}")

    if robots_usato:
        print(f"\n  richieste che il robots.txt indicato avrebbe BLOCCATO:")
        print(f"    {agg.bloccate_da_robots:>9,}  {_pct(agg.bloccate_da_robots, t):>7}")
        non_bloccato = agg.spreco - agg.bloccate_da_robots
        if non_bloccato > 0:
            print(f"  -> spreco NON coperto dalle regole: {non_bloccato:,} richieste "
                  f"({_pct(non_bloccato, t)} del totale)")

    print(f"\n--- TIPO DI RISORSA ---")
    print(f"  {'tipo':28} {'richieste':>11} {'quota':>8}   codici di stato")
    print(f"  {'-' * 28} {'-' * 11} {'-' * 8}   {'-' * 24}")
    for tipo, numero in agg.per_tipo.most_common():
        stati = agg.stato_per_tipo[tipo]
        riassunto = " ".join(f"{s}:{n:,}" for s, n in sorted(stati.most_common()[:4]))
        print(f"  {tipo:28} {numero:>11,} {_pct(numero, t):>8}   {riassunto}")

    print(f"\n--- QUALIFICATORE (query string / suffisso) ---")
    print(f"  {'qualificatore':28} {'richieste':>11} {'quota':>8}")
    print(f"  {'-' * 28} {'-' * 11} {'-' * 8}")
    for q, numero in agg.per_qualificatore.most_common():
        marca = "  <-- SPRECO" if q in {
            "add_to_cart", "rimozione_carrello", "filtro", "ordinamento",
            "ricerca_interna", "parametro_tecnico", "tracking", "parametro_anomalo",
        } else ""
        print(f"  {q:28} {numero:>11,} {_pct(numero, t):>8}{marca}")

    if agg.parametri:
        print(f"\n--- PARAMETRI DI QUERY STRING PIU' RICHIESTI ---")
        print("  (da confrontare con i pattern del robots.txt: i nomi reali")
        print("   contano piu' di quelli che diamo per scontati)")
        for nome, numero in agg.parametri.most_common(top):
            print(f"  {nome:34} {numero:>9,}")

    if agg.top_spreco:
        print(f"\n--- TOP URL DI SPRECO (Q3: cosa consuma crawling) ---")
        for url, numero in agg.top_spreco.most_common(top):
            print(f"  {numero:>7,}  {url[:150]}")

    if agg.top_utile:
        print(f"\n--- TOP URL UTILI PIU' SCANSIONATE ---")
        for url, numero in agg.top_utile.most_common(min(top, 10)):
            print(f"  {numero:>7,}  {url[:150]}")


def stampa_scoperta(segmenti: collections.Counter, estensioni: collections.Counter,
                    parametri: collections.Counter, top: int) -> None:
    print(f"\n{'=' * 74}")
    print("MODALITA' SCOPERTA - struttura reale delle URL")
    print(f"{'=' * 74}")
    print("Serve a compilare config.json con gli slug VERI del sito, invece di")
    print("fidarsi dei default. Confronta questa lista con DEFAULT_CONFIG in")
    print("classifica.py e correggi le differenze.\n")
    print(f"--- primo segmento di percorso (top {top}) ---")
    for segmento, numero in segmenti.most_common(top):
        print(f"  {numero:>9,}  /{segmento}/")
    print(f"\n--- estensioni di file (top 15) ---")
    for est, numero in estensioni.most_common(15):
        print(f"  {numero:>9,}  {est or '(nessuna)'}")
    print(f"\n--- nomi di parametri (top {top}) ---")
    print("  IMPORTANTE: questi sono i parametri che il robots.txt deve coprire.")
    for nome, numero in parametri.most_common(top):
        print(f"  {numero:>9,}  {nome}")


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("log", nargs="+", help="file di log (glob e .gz ammessi)")
    ap.add_argument("--bot", default="google",
                    choices=["google", "tutti", "altri"],
                    help="quale user-agent analizzare (default: google)")
    ap.add_argument("--taglio", help="data YYYY-MM-DD: confronta prima/dopo")
    ap.add_argument("--robots", help="robots.txt da incrociare coi log")
    ap.add_argument("--scopri", action="store_true",
                    help="mostra la struttura reale delle URL (per compilare config.json)")
    ap.add_argument("--esporta-url", help="scrive le URL distinte in un file")
    ap.add_argument("--esporta-spreco", help="scrive le sole URL di spreco in un file")
    ap.add_argument("--report", action="store_true", help="report completo (default)")
    ap.add_argument("--top", type=int, default=25, help="quante voci nelle classifiche")
    ap.add_argument("--config", help="percorso di config.json")
    args = ap.parse_args()

    cfg = carica_config(args.config)

    robots = None
    if args.robots:
        from robots_matcher import Robots
        robots = (Robots.da_url(args.robots) if args.robots.startswith("http")
                  else Robots.da_file(args.robots))

    taglio = None
    if args.taglio:
        taglio = dt.date.fromisoformat(args.taglio)

    file_log = espandi(args.log)
    if not file_log:
        print("ERRORE: nessun file di log leggibile", file=sys.stderr)
        return 1
    print(f"file analizzati: {len(file_log)}")
    for f in file_log:
        print(f"  {f}")

    globale = Aggregato("TOTALE PERIODO")
    prima = Aggregato(f"PRIMA del {args.taglio}") if taglio else None
    dopo = Aggregato(f"DAL {args.taglio} IN POI") if taglio else None

    segmenti: collections.Counter = collections.Counter()
    estensioni: collections.Counter = collections.Counter()
    parametri_scoperti: collections.Counter = collections.Counter()

    righe_totali = 0
    righe_non_lette = 0
    righe_bot = 0
    url_distinte: set[str] = set()
    url_spreco: set[str] = set()

    for percorso in file_log:
        with apri(percorso) as fh:
            for riga in fh:
                righe_totali += 1
                m = RE_LOG.match(riga)
                if not m:
                    righe_non_lette += 1
                    continue

                ua = m.group("ua") or ""
                if args.bot == "google" and not RE_BOT_GOOGLE.search(ua):
                    continue
                if args.bot == "altri" and not RE_ALTRI_BOT.search(ua):
                    continue

                righe_bot += 1
                url = m.group("percorso")
                stato = m.group("stato")
                byte_grezzi = m.group("byte")
                byte = int(byte_grezzi) if byte_grezzi.isdigit() else 0
                giorno = parse_data(m.group("data"))

                info = classifica(url, cfg)
                globale.aggiungi(info, stato, byte, giorno, robots)

                if taglio and giorno:
                    (dopo if giorno >= taglio else prima).aggiungi(info, stato, byte, giorno, robots)

                if args.scopri:
                    parti = [p for p in info["percorso"].strip("/").split("/") if p]
                    segmenti[parti[0].lower() if parti else "(home)"] += 1
                    estensioni[os.path.splitext(info["percorso"].rstrip("/"))[1].lower()] += 1
                    for nome in info["parametri"]:
                        parametri_scoperti[nome] += 1

                if args.esporta_url:
                    url_distinte.add(url)
                if args.esporta_spreco and info["spreco"]:
                    url_spreco.add(url)

    print(f"\nrighe lette      : {righe_totali:,}")
    print(f"righe non parsate: {righe_non_lette:,} ({_pct(righe_non_lette, righe_totali)})")
    if righe_non_lette > righe_totali * 0.2:
        print("  ATTENZIONE: molte righe non parsate. Il formato di log potrebbe")
        print("  non essere 'combined'. Controlla log_format in nginx.conf.")
    print(f"richieste del bot selezionato ({args.bot}): {righe_bot:,}")

    if righe_bot == 0:
        print("\nNessuna richiesta del bot selezionato. Verifica che i log")
        print("contengano lo user-agent (log_format combined) e il periodo giusto.")
        return 1

    if args.scopri:
        stampa_scoperta(segmenti, estensioni, parametri_scoperti, args.top)

    if args.report or not args.scopri:
        stampa_aggregato(globale, robots is not None, args.top)
        if taglio:
            stampa_aggregato(prima, robots is not None, args.top)
            stampa_aggregato(dopo, robots is not None, args.top)
            print(f"\n{'=' * 74}\nCONFRONTO PRIMA / DOPO {args.taglio}\n{'=' * 74}")
            print(f"  {'metrica':34} {'prima':>12} {'dopo':>12} {'variazione':>12}")
            print(f"  {'-' * 34} {'-' * 12} {'-' * 12} {'-' * 12}")

            def riga_confronto(etichetta: str, a: float, b: float, percentuale: bool = False) -> None:
                if percentuale:
                    print(f"  {etichetta:34} {a:>11.1f}% {b:>11.1f}% {b - a:>+11.1f}p")
                else:
                    delta = f"{(100.0 * (b - a) / a):+.1f}%" if a else "n/d"
                    print(f"  {etichetta:34} {a:>12,.0f} {b:>12,.0f} {delta:>12}")

            gp, gd = max(len(prima.giorni), 1), max(len(dopo.giorni), 1)
            riga_confronto("richieste/giorno", prima.totale / gp, dopo.totale / gd)
            riga_confronto("richieste utili/giorno", prima.utile / gp, dopo.utile / gd)
            riga_confronto("richieste spreco/giorno", prima.spreco / gp, dopo.spreco / gd)
            riga_confronto("quota richieste utili", 100.0 * prima.utile / max(prima.totale, 1),
                           100.0 * dopo.utile / max(dopo.totale, 1), percentuale=True)
            riga_confronto("quota richieste spreco", 100.0 * prima.spreco / max(prima.totale, 1),
                           100.0 * dopo.spreco / max(dopo.totale, 1), percentuale=True)
            for chiave in ("prodotto", "categoria_prodotto", "sottocategoria_prodotto", "marchio"):
                riga_confronto(f"{chiave}/giorno",
                               prima.per_tipo.get(chiave, 0) / gp,
                               dopo.per_tipo.get(chiave, 0) / gd)
            for chiave in ("add_to_cart", "filtro", "ordinamento", "ricerca_interna"):
                riga_confronto(f"{chiave}/giorno",
                               prima.per_qualificatore.get(chiave, 0) / gp,
                               dopo.per_qualificatore.get(chiave, 0) / gd)

            print("\nLETTURA DEL RISULTATO:")
            print("  L'obiettivo e' 'richieste utili/giorno' in AUMENTO e")
            print("  'richieste spreco/giorno' stabile o in CALO. Se entrambe")
            print("  crescono in proporzione, il crawl budget non e' stato")
            print("  riallocato: e' solo aumentato il crawling complessivo.")

    if args.esporta_url:
        with open(args.esporta_url, "w", encoding="utf-8") as fh:
            for u in sorted(url_distinte):
                fh.write(u + "\n")
        print(f"\nesportate {len(url_distinte):,} URL distinte in {args.esporta_url}")
        print(f"  usale con: python3 robots_check.py --robots <file> --urls {args.esporta_url}")

    if args.esporta_spreco:
        with open(args.esporta_spreco, "w", encoding="utf-8") as fh:
            for u in sorted(url_spreco):
                fh.write(u + "\n")
        print(f"esportate {len(url_spreco):,} URL di spreco in {args.esporta_spreco}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
