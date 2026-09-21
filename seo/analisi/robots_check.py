#!/usr/bin/env python3
"""Verifica un robots.txt contro un insieme reale di URL.

Risponde a due domande della relazione:
  Q5 - le regole attuali stanno DAVVERO bloccando i pattern di spreco?
  Q6 - esistono regole che ostacolano la scoperta di prodotti e categorie?

La seconda e' la piu' importante: una URL utile bloccata e' un danno diretto,
mentre una regola inerte e' "solo" un'occasione persa.

Esempi:
  # diagnosi statica delle regole
  python3 robots_check.py --robots attuale.txt --diagnosi

  # verifica contro le URL realmente richieste da Googlebot
  python3 analizza_log.py access.log --esporta-url urls.txt
  python3 robots_check.py --robots attuale.txt --urls urls.txt

  # confronto fra configurazione attuale e proposta
  python3 robots_check.py --robots attuale.txt --confronta proposto.txt --urls urls.txt
"""

from __future__ import annotations

import argparse
import collections
import sys

from classifica import carica_config, classifica
from robots_matcher import Robots


def _carica_robots(riferimento: str) -> Robots:
    if riferimento.startswith(("http://", "https://")):
        return Robots.da_url(riferimento)
    return Robots.da_file(riferimento)


def _leggi_url(percorso: str) -> list[str]:
    url = []
    sorgente = sys.stdin if percorso == "-" else open(percorso, encoding="utf-8", errors="replace")
    try:
        for riga in sorgente:
            riga = riga.strip()
            if riga and not riga.startswith("#"):
                url.append(riga)
    finally:
        if sorgente is not sys.stdin:
            sorgente.close()
    return url


def stampa_diagnosi(robots: Robots, etichetta: str) -> int:
    print(f"\n{'=' * 74}\nDIAGNOSI STATICA: {etichetta}\n{'=' * 74}")
    print(f"gruppi User-agent : {sorted(robots.gruppi)}")
    for agente, regole in sorted(robots.gruppi.items()):
        print(f"  '{agente}': {len(regole)} regole")
    print(f"sitemap dichiarate: {robots.sitemap or '(NESSUNA)'}")

    inerti = robots.regole_inerti()
    if inerti:
        print(f"\n--- REGOLE INERTI: {len(inerti)} ---")
        print("Queste regole sembrano proteggere il sito ma non combaciano con le URL")
        print("reali generate da WooCommerce/YITH. Sono il problema piu' insidioso:")
        print("danno la falsa impressione che il crawl budget sia protetto.\n")
        for regola, motivo in inerti:
            print(f"  {regola}")
            print(f"     -> {motivo}\n")
    else:
        print("\nNessuna regola inerte rilevata.")

    if robots.avvisi:
        print(f"--- AVVISI DI PARSING: {len(robots.avvisi)} ---")
        for avviso in robots.avvisi:
            print(f"  {avviso}")

    return len(inerti)


def stampa_verifica(robots: Robots, url: list[str], cfg: dict, etichetta: str,
                    mostra_esempi: int = 5) -> dict:
    print(f"\n{'=' * 74}\nVERIFICA SU {len(url)} URL REALI: {etichetta}\n{'=' * 74}")

    per_qualificatore: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    per_tipo: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    utili_bloccate: list[tuple[str, object]] = []
    spreco_passante: list[tuple[str, object]] = []

    for u in url:
        info = classifica(u, cfg)
        consentito, regola = robots.spiega(u)
        stato = "consentita" if consentito else "bloccata"
        per_qualificatore[info["qualificatore"]][stato] += 1
        per_tipo[info["tipo"]][stato] += 1

        if info["utile"] and not consentito:
            utili_bloccate.append((u, regola))
        if info["spreco"] and consentito:
            spreco_passante.append((u, regola))

    def tabella(titolo: str, dati: dict[str, collections.Counter]) -> None:
        print(f"\n{titolo}")
        print(f"  {'categoria':30} {'bloccate':>9} {'consentite':>11} {'% bloccate':>11}")
        print(f"  {'-' * 30} {'-' * 9} {'-' * 11} {'-' * 11}")
        for chiave in sorted(dati, key=lambda k: -sum(dati[k].values())):
            b = dati[chiave]["bloccata"]
            c = dati[chiave]["consentita"]
            tot = b + c
            pct = (100.0 * b / tot) if tot else 0.0
            print(f"  {chiave:30} {b:>9} {c:>11} {pct:>10.1f}%")

    tabella("Per QUALIFICATORE (cosa aggiunge la query string):", per_qualificatore)
    tabella("Per TIPO di risorsa:", per_tipo)

    print(f"\n{'-' * 74}")
    if utili_bloccate:
        print(f"!! ALLARME - {len(utili_bloccate)} URL UTILI BLOCCATE (risposta a Q6)")
        print("   Queste URL hanno valore SEO ma robots.txt ne impedisce la scansione.")
        print("   Va corretto prima di qualunque altra cosa.\n")
        for u, regola in utili_bloccate[:mostra_esempi]:
            print(f"   {u}\n      bloccata da: {regola}")
        if len(utili_bloccate) > mostra_esempi:
            print(f"   ... e altre {len(utili_bloccate) - mostra_esempi}")
    else:
        print("OK - nessuna URL utile risulta bloccata (Q6).")

    print()
    if spreco_passante:
        print(f"ATTENZIONE - {len(spreco_passante)} URL DI SPRECO NON BLOCCATE (risposta a Q5)")
        print("   Sono le URL senza valore SEO che Googlebot puo' ancora scansionare.\n")
        conteggio = collections.Counter(classifica(u, cfg)["qualificatore"] for u, _ in spreco_passante)
        for qualificatore, numero in conteggio.most_common():
            print(f"   {qualificatore:24} {numero:>7}")
        print("\n   esempi:")
        for u, _ in spreco_passante[:mostra_esempi]:
            print(f"   {u}")
    else:
        print("OK - tutte le URL di spreco presenti nel campione sono bloccate (Q5).")

    return {
        "utili_bloccate": len(utili_bloccate),
        "spreco_passante": len(spreco_passante),
        "per_qualificatore": {k: dict(v) for k, v in per_qualificatore.items()},
    }


def stampa_confronto(a: Robots, b: Robots, url: list[str], cfg: dict,
                     nome_a: str, nome_b: str) -> None:
    print(f"\n{'=' * 74}\nCONFRONTO: {nome_a}  ->  {nome_b}\n{'=' * 74}")

    cambi: dict[str, list[str]] = collections.defaultdict(list)
    for u in url:
        ok_a = a.consentito(u)
        ok_b = b.consentito(u)
        if ok_a == ok_b:
            continue
        info = classifica(u, cfg)
        verso = "ora_bloccata" if ok_a and not ok_b else "ora_consentita"
        chiave = f"{verso}|{info['qualificatore']}|{'utile' if info['utile'] else 'spreco' if info['spreco'] else 'neutra'}"
        cambi[chiave].append(u)

    if not cambi:
        print("Nessuna differenza di comportamento sul campione di URL fornito.")
        return

    guadagni = {k: v for k, v in cambi.items() if k.startswith("ora_bloccata") and k.endswith("spreco")}
    rischi = {k: v for k, v in cambi.items() if k.startswith("ora_bloccata") and k.endswith("utile")}
    sblocchi = {k: v for k, v in cambi.items() if k.startswith("ora_consentita")}

    def blocco(titolo: str, dati: dict[str, list[str]], esempi: int = 3) -> None:
        totale = sum(len(v) for v in dati.values())
        print(f"\n{titolo} ({totale} URL)")
        for chiave in sorted(dati, key=lambda k: -len(dati[k])):
            _, qualificatore, _ = chiave.split("|")
            lista = dati[chiave]
            print(f"  {qualificatore:24} {len(lista):>7}")
            for u in lista[:esempi]:
                print(f"      {u}")

    if guadagni:
        blocco("GUADAGNO - spreco che la proposta blocca e prima passava:", guadagni)
    if sblocchi:
        blocco("SBLOCCATE - URL che la proposta consente e prima erano bloccate:", sblocchi)
    if rischi:
        print("\n!! RISCHIO - URL UTILI che la proposta bloccherebbe:")
        blocco("", rischi, esempi=10)
        print("\n   NON pubblicare la proposta finche' queste non sono risolte.")
    else:
        print("\nOK - la proposta non blocca nessuna URL utile del campione.")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--robots", required=True, help="file locale o URL del robots.txt da verificare")
    ap.add_argument("--confronta", help="secondo robots.txt da confrontare col primo")
    ap.add_argument("--urls", help="file con una URL per riga ('-' per stdin)")
    ap.add_argument("--diagnosi", action="store_true", help="solo diagnosi statica delle regole")
    ap.add_argument("--config", help="percorso di config.json con gli slug del sito")
    ap.add_argument("--esempi", type=int, default=5, help="quanti esempi mostrare (default 5)")
    args = ap.parse_args()

    cfg = carica_config(args.config)
    robots = _carica_robots(args.robots)

    stampa_diagnosi(robots, args.robots)

    if args.confronta:
        altro = _carica_robots(args.confronta)
        stampa_diagnosi(altro, args.confronta)

    if not args.urls:
        if not args.diagnosi:
            print("\n(nessun --urls fornito: eseguita solo la diagnosi statica)")
        return 0

    url = _leggi_url(args.urls)
    if not url:
        print("\nATTENZIONE: nessuna URL letta da --urls", file=sys.stderr)
        return 1

    esito = stampa_verifica(robots, url, cfg, args.robots, args.esempi)

    if args.confronta:
        stampa_verifica(altro, url, cfg, args.confronta, args.esempi)
        stampa_confronto(robots, altro, url, cfg, args.robots, args.confronta)

    # exit code 2 se ci sono URL utili bloccate: utile in CI o negli script
    return 2 if esito["utili_bloccate"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
