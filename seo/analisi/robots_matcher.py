#!/usr/bin/env python3
"""Implementazione del matching di robots.txt secondo RFC 9309 (lo standard
che Google applica realmente).

Le tre regole che contano e che vengono sbagliate piu' spesso:

1. Il confronto avviene su PERCORSO + QUERY STRING, e il pattern deve
   combaciare a partire dall'INIZIO del percorso.
   Quindi `Disallow: /?filter_` NON blocca
   `/categoria-prodotto/lampadine/?filter_colore=bianco`, perche' quel
   percorso non comincia con `/?filter_`. Serve un wildcard: `/*?filter_`.

2. Vince la regola con il pattern PIU' LUNGO (non la prima, non l'ultima).
   A parita' di lunghezza vince Allow.

3. `*` = qualunque sequenza di caratteri. `$` = fine della URL.
   Sono gli unici due metacaratteri. Il punto e' letterale: `Allow: /.js$`
   significa "la URL esatta /.js", non "i file .js".

Uso come libreria:
    r = Robots.da_file("robots.txt")
    r.consentito("/categoria-prodotto/x/?filter_colore=bianco", "Googlebot")
    r.spiega(url, "Googlebot")   -> (consentito, regola_che_ha_deciso)
"""

from __future__ import annotations

import re
from urllib.parse import urlsplit, quote, unquote


class Regola:
    __slots__ = ("consenti", "pattern", "regex", "lunghezza", "riga")

    def __init__(self, consenti: bool, pattern: str, riga: int):
        self.consenti = consenti
        self.pattern = pattern
        self.riga = riga
        self.lunghezza = len(pattern)
        self.regex = _compila(pattern)

    def combacia(self, percorso: str) -> bool:
        return self.regex.match(percorso) is not None

    def __repr__(self) -> str:
        verbo = "Allow" if self.consenti else "Disallow"
        return f"{verbo}: {self.pattern}  (riga {self.riga})"


def _compila(pattern: str) -> re.Pattern:
    """Converte un pattern robots.txt in regex ancorata all'inizio."""
    ancorato_fine = pattern.endswith("$")
    corpo = pattern[:-1] if ancorato_fine else pattern

    parti = []
    for pezzo in corpo.split("*"):
        parti.append(re.escape(pezzo))
    regex = ".*".join(parti)
    if ancorato_fine:
        regex += "$"
    return re.compile(regex)


def _normalizza(url: str) -> str:
    """Estrae percorso+query nella forma su cui avviene il confronto."""
    if "://" in url:
        pezzi = urlsplit(url)
        percorso, query = pezzi.path or "/", pezzi.query
    elif url.startswith("/"):
        pezzi = urlsplit("http://x" + url)
        percorso, query = pezzi.path or "/", pezzi.query
    else:
        pezzi = urlsplit("http://x/" + url)
        percorso, query = pezzi.path or "/", pezzi.query

    if not percorso.startswith("/"):
        percorso = "/" + percorso
    # Normalizzazione percent-encoding: decodifica e ricodifica in modo
    # coerente, come fa il parser di Google, lasciando intatti i separatori.
    percorso = quote(unquote(percorso), safe="/~:@!$&'()*+,;=-._")
    return percorso + (("?" + query) if query else "")


class Robots:
    def __init__(self, testo: str):
        self.testo = testo
        self.gruppi: dict[str, list[Regola]] = {}
        self.sitemap: list[str] = []
        self.crawl_delay: dict[str, str] = {}
        self.avvisi: list[str] = []
        self._parse(testo)

    # ---------------------------------------------------------------- parsing
    def _parse(self, testo: str) -> None:
        agenti_correnti: list[str] = []
        ultimo_era_agente = False

        for numero, riga_grezza in enumerate(testo.splitlines(), start=1):
            riga = riga_grezza.split("#", 1)[0].strip()
            if not riga:
                continue
            if ":" not in riga:
                self.avvisi.append(f"riga {numero}: riga senza ':' ignorata -> {riga_grezza.strip()!r}")
                continue

            campo, _, valore = riga.partition(":")
            campo = campo.strip().lower()
            valore = valore.strip()

            if campo == "user-agent":
                if not ultimo_era_agente:
                    agenti_correnti = []
                agenti_correnti.append(valore.lower())
                self.gruppi.setdefault(valore.lower(), [])
                ultimo_era_agente = True
                continue

            ultimo_era_agente = False

            if campo == "sitemap":
                self.sitemap.append(valore)
                continue
            if campo == "crawl-delay":
                for a in agenti_correnti or ["*"]:
                    self.crawl_delay[a] = valore
                continue
            if campo in ("allow", "disallow"):
                if not agenti_correnti:
                    self.avvisi.append(
                        f"riga {numero}: '{campo}' fuori da un gruppo User-agent: ignorata da Google"
                    )
                    continue
                if valore == "":
                    # "Disallow:" vuoto = consenti tutto; "Allow:" vuoto = no-op
                    if campo == "disallow":
                        continue
                    continue
                regola = Regola(campo == "allow", valore, numero)
                for a in agenti_correnti:
                    self.gruppi[a].append(regola)
                continue

            self.avvisi.append(f"riga {numero}: campo non riconosciuto '{campo}'")

    # --------------------------------------------------------------- matching
    def _gruppo_per(self, user_agent: str) -> list[Regola]:
        """Seleziona il gruppo: token esatto (case-insensitive), altrimenti '*'."""
        ua = user_agent.lower()
        if ua in self.gruppi:
            return self.gruppi[ua]
        # Google fa match sul product token: "googlebot" combacia con
        # "Googlebot/2.1". Prendiamo il gruppo piu' specifico contenuto nell'UA.
        candidati = [
            (nome, regole) for nome, regole in self.gruppi.items()
            if nome != "*" and nome in ua
        ]
        if candidati:
            candidati.sort(key=lambda c: len(c[0]), reverse=True)
            return candidati[0][1]
        return self.gruppi.get("*", [])

    def spiega(self, url: str, user_agent: str = "Googlebot") -> tuple[bool, Regola | None]:
        """Ritorna (consentito, regola_decisiva)."""
        percorso = _normalizza(url)
        regole = self._gruppo_per(user_agent)

        migliore: Regola | None = None
        for regola in regole:
            if not regola.combacia(percorso):
                continue
            if migliore is None:
                migliore = regola
            elif regola.lunghezza > migliore.lunghezza:
                migliore = regola
            elif regola.lunghezza == migliore.lunghezza and regola.consenti:
                # a parita' di lunghezza vince Allow
                migliore = regola

        if migliore is None:
            return True, None
        return migliore.consenti, migliore

    def consentito(self, url: str, user_agent: str = "Googlebot") -> bool:
        return self.spiega(url, user_agent)[0]

    def bloccato(self, url: str, user_agent: str = "Googlebot") -> bool:
        return not self.consentito(url, user_agent)

    # --------------------------------------------------------------- factory
    @classmethod
    def da_file(cls, percorso: str) -> "Robots":
        with open(percorso, encoding="utf-8", errors="replace") as fh:
            return cls(fh.read())

    @classmethod
    def da_url(cls, url: str, timeout: int = 20) -> "Robots":
        import urllib.request
        richiesta = urllib.request.Request(
            url, headers={"User-Agent": "Mozilla/5.0 (compatible; audit-seo)"}
        )
        with urllib.request.urlopen(richiesta, timeout=timeout) as risposta:
            return cls(risposta.read().decode("utf-8", errors="replace"))

    # --------------------------------------------------------------- diagnosi
    def regole_inerti(self) -> list[tuple[Regola, str]]:
        """Individua le regole che non possono combaciare con nessuna URL reale.

        Sono l'errore piu' frequente e il piu' invisibile: sembrano proteggere
        il sito, in realta' non fanno nulla.
        """
        problemi: list[tuple[Regola, str]] = []
        visti: set[tuple[str, bool]] = set()

        # Tutti i pattern presenti, per riconoscere le regole "compagne":
        # '/feed/' da sola e' inerte, ma '/feed/' + '/*/feed/' e' corretto.
        tutti_i_pattern = {
            regola.pattern for regole in self.gruppi.values() for regola in regole
        }

        for regole in self.gruppi.values():
            for regola in regole:
                chiave = (regola.pattern, regola.consenti)
                if chiave in visti:
                    continue
                visti.add(chiave)
                p = regola.pattern

                # 1. "/&param=" : una URL non puo' avere '&' subito dopo '/'
                if p.startswith("/&"):
                    problemi.append((
                        regola,
                        "non combacia mai: '&' non puo' comparire subito dopo la radice. "
                        f"I parametri in mezzo alla query richiedono un wildcard, es. '/*{p[2:]}'",
                    ))
                    continue

                # 2. "/?param=" senza wildcard: blocca solo la radice
                if p.startswith("/?") and "*" not in p:
                    problemi.append((
                        regola,
                        "combacia SOLO con la home (es. '/?s=...'): non copre le URL di "
                        f"categoria o prodotto. Serve il wildcard, es. '/*{p[1:]}'",
                    ))
                    continue

                # 3. "/.ext$" : il punto e' letterale
                if re.match(r"^/\.[a-z0-9]+\$$", p, re.I):
                    problemi.append((
                        regola,
                        f"il '.' e' letterale: combacia solo con la URL esatta '{p[:-1]}'. "
                        f"Per i file serve '/*{p[1:]}'",
                    ))
                    continue

                # 4. "/feed/" o "/trackback/" senza wildcard: solo radice.
                #    Non e' un problema se esiste la regola compagna '/*/feed/'.
                if p in ("/feed/", "/trackback/", "/comments/") and f"/*{p}" not in tutti_i_pattern:
                    problemi.append((
                        regola,
                        f"copre solo '{p}' alla radice: le stesse URL annidate sotto "
                        f"categorie e prodotti (es. '/categoria-prodotto/x{p}') restano "
                        f"scansionabili. Serve anche '/*{p}'",
                    ))
                    continue

        return problemi


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("uso: robots_matcher.py <robots.txt> [url ...]", file=sys.stderr)
        raise SystemExit(2)

    r = Robots.da_file(sys.argv[1])
    if len(sys.argv) == 2:
        print(f"gruppi User-agent: {sorted(r.gruppi)}")
        print(f"sitemap: {r.sitemap}")
        for regola, motivo in r.regole_inerti():
            print(f"[INERTE] {regola}\n         {motivo}")
        for a in r.avvisi:
            print(f"[AVVISO] {a}")
    else:
        for url in sys.argv[2:]:
            ok, regola = r.spiega(url)
            print(f"{'CONSENTITA' if ok else 'BLOCCATA  '}  {url}\n              regola: {regola or '(nessuna)'}")
