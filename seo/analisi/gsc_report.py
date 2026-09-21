#!/usr/bin/env python3
"""Analizza gli export di Google Search Console e classifica le URL.

Risponde a Q1 e Q2 della relazione:
  Q1 - l'aumento delle pagine indicizzate riguarda URL utili o indesiderate?
  Q2 - quanti prodotti sono indicizzati oggi rispetto a prima?

GSC non espone via export la serie storica completa delle URL indicizzate,
quindi il confronto "prima/dopo" si costruisce con DUE export fatti in due
momenti diversi. Se non esiste un export del periodo precedente, il
confronto puo' essere ricostruito solo in parte: vedi raccolta_dati.md.

Come ottenere i dati (Search Console, proprieta' www.tuttoluce.com):
  Indicizzazione > Pagine > (clic su un motivo) > Esporta > CSV/Fogli
  Conviene esportare almeno:
    - "Indicizzate"
    - "Scansionata, attualmente non indicizzata"
    - "Rilevata, attualmente non indicizzata"
    - "Pagina duplicata: Google ha scelto una pagina canonica diversa"
    - "Pagina alternativa con tag canonico corretto"
    - "Bloccata da robots.txt"

Uso:
  # un singolo export
  python3 gsc_report.py --file indicizzate.csv --etichetta "indicizzate set-2026"

  # piu' export insieme, con il motivo preso dal nome del file
  python3 gsc_report.py --file indicizzate.csv --file scansionate_non_indicizzate.csv

  # confronto fra due momenti
  python3 gsc_report.py --file oggi.csv --confronta-con giugno.csv

  # incrocio col robots.txt: quali URL "non indicizzate" sono bloccate
  python3 gsc_report.py --file scansionate_non_indicizzate.csv --robots robots.txt
"""

from __future__ import annotations

import argparse
import collections
import csv
import os
import sys

from classifica import carica_config, classifica

# Intestazioni possibili della colonna URL negli export GSC (IT/EN).
COLONNE_URL = {
    "url", "urls", "pagina", "pagine", "page", "pages", "indirizzo",
    "ultima scansione", "address",
}


def _trova_colonna_url(intestazioni: list[str]) -> int:
    """Individua la colonna che contiene le URL."""
    for i, nome in enumerate(intestazioni):
        if nome.strip().lower() in COLONNE_URL:
            return i
    # fallback: la prima colonna i cui valori sembrano URL
    return 0


def leggi_export(percorso: str) -> list[str]:
    """Legge un CSV/TSV di GSC e ritorna le URL."""
    with open(percorso, encoding="utf-8-sig", errors="replace", newline="") as fh:
        campione = fh.read(8192)
        fh.seek(0)
        try:
            dialetto = csv.Sniffer().sniff(campione, delimiters=",;\t")
        except csv.Error:
            dialetto = csv.excel
        lettore = csv.reader(fh, dialetto)
        righe = list(lettore)

    if not righe:
        return []

    intestazioni = righe[0]
    indice = _trova_colonna_url(intestazioni)

    # se la prima riga e' gia' una URL, non era un'intestazione
    inizio = 0 if intestazioni[indice].startswith("http") else 1

    url = []
    for riga in righe[inizio:]:
        if len(riga) <= indice:
            continue
        valore = riga[indice].strip()
        if valore.startswith("http"):
            url.append(valore)
    return url


def riassumi(url: list[str], cfg: dict, etichetta: str, robots=None) -> dict:
    unici = sorted(set(url))
    tipi: collections.Counter = collections.Counter()
    qualificatori: collections.Counter = collections.Counter()
    utili = spreco = 0
    bloccate: list[str] = []

    for u in unici:
        info = classifica(u, cfg)
        tipi[info["tipo"]] += 1
        qualificatori[info["qualificatore"]] += 1
        if info["utile"]:
            utili += 1
        if info["spreco"]:
            spreco += 1
        if robots is not None and robots.bloccato(u):
            bloccate.append(u)

    print(f"\n{'=' * 74}\n{etichetta}\n{'=' * 74}")
    print(f"URL nell'export : {len(url):,}")
    print(f"URL distinte    : {len(unici):,}")
    if not unici:
        return {"tipi": tipi, "totale": 0}

    print(f"\n  UTILI  {utili:>8,}  {100.0 * utili / len(unici):>6.1f}%")
    print(f"  SPRECO {spreco:>8,}  {100.0 * spreco / len(unici):>6.1f}%")

    print(f"\n--- PER TIPO ---")
    print(f"  {'tipo':30} {'URL':>9} {'quota':>8}")
    print(f"  {'-' * 30} {'-' * 9} {'-' * 8}")
    for t, n in tipi.most_common():
        print(f"  {t:30} {n:>9,} {100.0 * n / len(unici):>7.1f}%")

    non_vuoti = {q: n for q, n in qualificatori.items() if q != "nessuno"}
    if non_vuoti:
        print(f"\n--- CON QUERY STRING / PARAMETRI ---")
        print("  Se queste URL risultano INDICIZZATE, sono duplicati da")
        print("  canonicalizzare o da bloccare. Se risultano ESCLUSE, e' normale.")
        for q, n in sorted(non_vuoti.items(), key=lambda kv: -kv[1]):
            print(f"  {q:30} {n:>9,}")

    if robots is not None:
        print(f"\n--- INCROCIO COL ROBOTS.TXT ---")
        print(f"  URL bloccate da robots.txt: {len(bloccate):,} "
              f"({100.0 * len(bloccate) / len(unici):.1f}%)")
        if bloccate:
            utili_bloccate = [u for u in bloccate if classifica(u, cfg)["utile"]]
            if utili_bloccate:
                print(f"  !! di cui UTILI: {len(utili_bloccate):,} -> ostacolo diretto (Q6)")
                for u in utili_bloccate[:10]:
                    print(f"     {u}")

    return {"tipi": tipi, "qualificatori": qualificatori, "totale": len(unici),
            "utili": utili, "spreco": spreco, "url": set(unici)}


def confronta(prima: dict, dopo: dict, etichetta_prima: str, etichetta_dopo: str) -> None:
    print(f"\n{'=' * 74}")
    print(f"CONFRONTO: {etichetta_prima}  ->  {etichetta_dopo}")
    print(f"{'=' * 74}")

    tipi = sorted(set(prima["tipi"]) | set(dopo["tipi"]))
    print(f"  {'tipo':30} {'prima':>9} {'dopo':>9} {'delta':>9} {'var %':>9}")
    print(f"  {'-' * 30} {'-' * 9} {'-' * 9} {'-' * 9} {'-' * 9}")
    for t in sorted(tipi, key=lambda k: -(dopo["tipi"].get(k, 0))):
        a = prima["tipi"].get(t, 0)
        b = dopo["tipi"].get(t, 0)
        var = f"{(100.0 * (b - a) / a):+.1f}%" if a else ("nuovo" if b else "-")
        print(f"  {t:30} {a:>9,} {b:>9,} {b - a:>+9,} {var:>9}")

    print(f"\n  {'-' * 30} {'-' * 9} {'-' * 9} {'-' * 9}")
    for chiave, etichetta in (("totale", "TOTALE"), ("utili", "UTILI"), ("spreco", "SPRECO")):
        a, b = prima.get(chiave, 0), dopo.get(chiave, 0)
        var = f"{(100.0 * (b - a) / a):+.1f}%" if a else "-"
        print(f"  {etichetta:30} {a:>9,} {b:>9,} {b - a:>+9,} {var:>9}")

    nuove = dopo.get("url", set()) - prima.get("url", set())
    perse = prima.get("url", set()) - dopo.get("url", set())
    print(f"\n  URL nuove rispetto a prima : {len(nuove):,}")
    print(f"  URL non piu' presenti      : {len(perse):,}")

    if nuove:
        cfg = carica_config()
        composizione = collections.Counter(classifica(u, cfg)["tipo"] for u in nuove)
        print(f"\n--- DI COSA E' FATTO L'AUMENTO (risposta diretta a Q1) ---")
        for t, n in composizione.most_common():
            print(f"  {t:30} {n:>9,} {100.0 * n / len(nuove):>7.1f}%")

        utili_nuove = sum(1 for u in nuove if classifica(u, cfg)["utile"])
        quota = 100.0 * utili_nuove / len(nuove)
        print(f"\n  URL utili fra le nuove: {utili_nuove:,} su {len(nuove):,} ({quota:.1f}%)")
        print()
        if quota >= 80:
            print("  VERDETTO: l'aumento e' costituito prevalentemente da URL utili.")
            print("  E' il risultato desiderato: NON va ridotto.")
        elif quota >= 50:
            print("  VERDETTO: aumento misto. Vale la pena isolare la parte")
            print("  indesiderata senza toccare quella utile.")
        else:
            print("  VERDETTO: l'aumento e' prevalentemente di URL indesiderate.")
            print("  Qui si' che conviene intervenire su robots/canonical.")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--file", action="append", required=True,
                    help="export CSV di GSC (ripetibile)")
    ap.add_argument("--confronta-con", action="append", default=[],
                    help="export del periodo precedente (ripetibile)")
    ap.add_argument("--etichetta", help="nome del periodo corrente")
    ap.add_argument("--etichetta-confronto", help="nome del periodo precedente")
    ap.add_argument("--robots", help="robots.txt per l'incrocio")
    ap.add_argument("--config", help="percorso di config.json")
    args = ap.parse_args()

    cfg = carica_config(args.config)

    robots = None
    if args.robots:
        from robots_matcher import Robots
        robots = (Robots.da_url(args.robots) if args.robots.startswith("http")
                  else Robots.da_file(args.robots))

    url_ora: list[str] = []
    for percorso in args.file:
        lette = leggi_export(percorso)
        print(f"letto {percorso}: {len(lette):,} URL")
        if not lette:
            print(f"  ATTENZIONE: nessuna URL riconosciuta in {percorso}.")
            print("  Verifica che il CSV contenga una colonna con URL complete (http...).")
        url_ora.extend(lette)

    if not url_ora:
        print("\nERRORE: nessuna URL letta dagli export forniti.", file=sys.stderr)
        return 1

    etichetta_ora = args.etichetta or f"PERIODO CORRENTE ({len(args.file)} export)"
    ora = riassumi(url_ora, cfg, etichetta_ora, robots)

    if args.confronta_con:
        url_prima: list[str] = []
        for percorso in args.confronta_con:
            lette = leggi_export(percorso)
            print(f"\nletto {percorso}: {len(lette):,} URL")
            url_prima.extend(lette)
        if url_prima:
            etichetta_prima = args.etichetta_confronto or "PERIODO PRECEDENTE"
            prima = riassumi(url_prima, cfg, etichetta_prima, robots)
            confronta(prima, ora, etichetta_prima, etichetta_ora)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
