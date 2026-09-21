#!/usr/bin/env python3
"""Test del motore di matching e del classificatore.

Tutta l'analisi si appoggia su robots_matcher.py: se il matching e' sbagliato,
ogni conclusione successiva e' sbagliata. Questi test fissano il comportamento
atteso secondo RFC 9309, inclusi i casi che si sbagliano piu' spesso.

Eseguire con:  python3 test_matcher.py
"""

from classifica import carica_config, classifica
from robots_matcher import Robots

FALLITI: list[str] = []
PASSATI = 0


def verifica(descrizione: str, ottenuto, atteso) -> None:
    global PASSATI
    if ottenuto == atteso:
        PASSATI += 1
    else:
        FALLITI.append(f"{descrizione}\n    atteso: {atteso!r}\n    ottenuto: {ottenuto!r}")


# --------------------------------------------------------------------------
# 1. Il match avviene dall'inizio del percorso: "/?x=" copre solo la radice.
# --------------------------------------------------------------------------
r = Robots("User-agent: *\nDisallow: /?filter_\n")
verifica("'/?filter_' blocca la home con filtro",
         r.bloccato("/?filter_colore=bianco"), True)
verifica("'/?filter_' NON blocca una categoria con filtro",
         r.bloccato("/categoria-prodotto/x/?filter_colore=bianco"), False)

r = Robots("User-agent: *\nDisallow: /*?filter_\n")
verifica("'/*?filter_' blocca la categoria con filtro",
         r.bloccato("/categoria-prodotto/x/?filter_colore=bianco"), True)

# --------------------------------------------------------------------------
# 2. "/&x=" non puo' combaciare con nessuna URL reale.
# --------------------------------------------------------------------------
r = Robots("User-agent: *\nDisallow: /&add-to-cart=\n")
verifica("'/&add-to-cart=' non blocca il parametro in mezzo alla query",
         r.bloccato("/prodotto/x/?a=1&add-to-cart=9"), False)
verifica("'/&add-to-cart=' non blocca nemmeno alla radice",
         r.bloccato("/?add-to-cart=9"), False)

r = Robots("User-agent: *\nDisallow: /*add-to-cart=\n")
verifica("'/*add-to-cart=' blocca in posizione iniziale",
         r.bloccato("/prodotto/x/?add-to-cart=9"), True)
verifica("'/*add-to-cart=' blocca in posizione intermedia",
         r.bloccato("/prodotto/x/?a=1&add-to-cart=9"), True)

# --------------------------------------------------------------------------
# 3. Il punto e' letterale: "/.js$" non e' "tutti i .js".
# --------------------------------------------------------------------------
r = Robots("User-agent: *\nDisallow: /\nAllow: /.js$\n")
verifica("'/.js$' NON consente un vero file .js",
         r.bloccato("/wp-content/themes/t/app.js"), True)

r = Robots("User-agent: *\nDisallow: /\nAllow: /*.js$\n")
verifica("'/*.js$' consente un vero file .js",
         r.bloccato("/wp-content/themes/t/app.js"), False)
verifica("'/*.js$' non consente .js seguito da query ('$' ancora la fine)",
         r.bloccato("/wp-content/themes/t/app.js?ver=1"), True)

# --------------------------------------------------------------------------
# 4. Vince il pattern PIU' LUNGO, non l'ordine di scrittura.
# --------------------------------------------------------------------------
r = Robots("User-agent: *\nDisallow: /wp-includes/\nAllow: /wp-includes/js/\n")
verifica("Allow piu' lungo vince sul Disallow piu' corto",
         r.bloccato("/wp-includes/js/jquery/jquery.min.js"), False)
verifica("Disallow resta valido fuori dal ramo consentito",
         r.bloccato("/wp-includes/version.php"), True)

# ordine invertito: il risultato deve essere identico
r = Robots("User-agent: *\nAllow: /wp-includes/js/\nDisallow: /wp-includes/\n")
verifica("l'ordine delle righe non cambia l'esito",
         r.bloccato("/wp-includes/js/jquery/jquery.min.js"), False)

# a parita' di lunghezza vince Allow
r = Robots("User-agent: *\nDisallow: /aaa/\nAllow: /aaa/\n")
verifica("a parita' di lunghezza vince Allow", r.bloccato("/aaa/"), False)

# un Allow corto NON salva da un Disallow lungo: il trap dei blocchi Gutenberg
r = Robots("User-agent: *\nDisallow: /wp-includes/\nAllow: /*.css$\n")
verifica("Allow generico su .css NON basta contro Disallow /wp-includes/",
         r.bloccato("/wp-includes/blocks/gallery/style.css"), True)
r = Robots("User-agent: *\nDisallow: /wp-includes/\nAllow: /wp-includes/blocks/\n")
verifica("serve un Allow specifico per i blocchi Gutenberg",
         r.bloccato("/wp-includes/blocks/gallery/style.css"), False)

# --------------------------------------------------------------------------
# 5. Selezione del gruppo User-agent.
# --------------------------------------------------------------------------
r = Robots("User-agent: *\nDisallow: /\n\nUser-agent: Googlebot\nDisallow:\n")
verifica("Googlebot usa il proprio gruppo, non '*'",
         r.bloccato("/prodotto/x/", "Googlebot"), False)
verifica("un altro bot ricade su '*'",
         r.bloccato("/prodotto/x/", "bingbot"), True)
verifica("il match sull'UA e' sul product token",
         r.bloccato("/prodotto/x/", "Mozilla/5.0 (compatible; Googlebot/2.1)"), False)

# Disallow vuoto = consenti tutto
r = Robots("User-agent: *\nDisallow:\n")
verifica("'Disallow:' vuoto consente tutto", r.bloccato("/qualunque/"), False)

# robots.txt vuoto = tutto consentito
verifica("robots.txt vuoto consente tutto", Robots("").bloccato("/x/"), False)

# direttive fuori da un gruppo vengono ignorate
r = Robots("Disallow: /tutto/\nUser-agent: *\nDisallow: /altro/\n")
verifica("Disallow prima di User-agent viene ignorato", r.bloccato("/tutto/"), False)
verifica("il Disallow dentro il gruppo funziona", r.bloccato("/altro/"), True)

# --------------------------------------------------------------------------
# 6. Wildcard interni e '$'.
# --------------------------------------------------------------------------
r = Robots("User-agent: *\nDisallow: /*/feed/\n")
verifica("'/*/feed/' blocca il feed di categoria",
         r.bloccato("/categoria-prodotto/lampadine/feed/"), True)
verifica("'/*/feed/' non blocca la categoria stessa",
         r.bloccato("/categoria-prodotto/lampadine/"), False)

r = Robots("User-agent: *\nDisallow: /*?\n")
verifica("'/*?' blocca qualunque URL con query string",
         r.bloccato("/prodotto/x/?a=1"), True)
verifica("'/*?' non blocca le URL senza query string",
         r.bloccato("/prodotto/x/"), False)

# --------------------------------------------------------------------------
# 7. Rilevamento delle regole inerti.
# --------------------------------------------------------------------------
bozza = Robots(
    "User-agent: *\n"
    "Disallow: /?filter_\n"
    "Disallow: /&filter_\n"
    "Allow: /.css$\n"
    "Disallow: /feed/\n"
)
inerti = {regola.pattern for regola, _ in bozza.regole_inerti()}
verifica("rileva '/?filter_' come inerte", "/?filter_" in inerti, True)
verifica("rileva '/&filter_' come inerte", "/&filter_" in inerti, True)
verifica("rileva '/.css$' come inerte", "/.css$" in inerti, True)
verifica("rileva '/feed/' senza compagna come inerte", "/feed/" in inerti, True)

con_compagna = Robots("User-agent: *\nDisallow: /feed/\nDisallow: /*/feed/\n")
verifica("NON segnala '/feed/' se esiste '/*/feed/'",
         "/feed/" in {r.pattern for r, _ in con_compagna.regole_inerti()}, False)

corretto = Robots(
    "User-agent: *\n"
    "Disallow: /*filter_\n"
    "Disallow: /*add-to-cart=\n"
    "Allow: /*.css$\n"
    "Disallow: /feed/\n"
    "Disallow: /*/feed/\n"
)
verifica("nessuna regola inerte in una configurazione corretta",
         len(corretto.regole_inerti()), 0)

# --------------------------------------------------------------------------
# 8. Classificatore: le due dimensioni restano indipendenti.
# --------------------------------------------------------------------------
cfg = carica_config()

c = classifica("/prodotto/x/?add-to-cart=1", cfg)
verifica("tipo di una URL add-to-cart resta 'prodotto'", c["tipo"], "prodotto")
verifica("qualificatore add-to-cart riconosciuto", c["qualificatore"], "add_to_cart")
verifica("una URL add-to-cart e' spreco", c["spreco"], True)
verifica("una URL add-to-cart non e' utile", c["utile"], False)

c = classifica("/prodotto/x/", cfg)
verifica("un prodotto pulito e' utile", c["utile"], True)
verifica("un prodotto pulito non e' spreco", c["spreco"], False)

c = classifica("/categoria-prodotto/a/b/", cfg)
verifica("profondita' 3 = sottocategoria", c["tipo"], "sottocategoria_prodotto")
c = classifica("/categoria-prodotto/a/", cfg)
verifica("profondita' 2 = categoria", c["tipo"], "categoria_prodotto")

c = classifica("/categoria-prodotto/a/page/2/", cfg)
verifica("la paginazione non e' spreco", c["spreco"], False)
verifica("la paginazione e' riconosciuta", c["qualificatore"], "paginazione")
verifica("una categoria paginata resta utile", c["utile"], True)

c = classifica("/wp-content/plugins/yith/assets/style.css", cfg)
verifica("i CSS dei plugin sono asset, non URL tecniche", c["tipo"], "asset_statico")
verifica("gli asset non sono spreco", c["spreco"], False)

c = classifica("/categoria-prodotto/a/?yith_wcan=1", cfg)
verifica("yith_wcan e' un filtro", c["qualificatore"], "filtro")

c = classifica("/categoria-prodotto/a/?orderby=price", cfg)
verifica("orderby e' ordinamento", c["qualificatore"], "ordinamento")

c = classifica("/prodotto/x/?utm_source=google", cfg)
verifica("utm_source e' tracking", c["qualificatore"], "tracking")

# --------------------------------------------------------------------------
# esito
# --------------------------------------------------------------------------
print(f"\ntest superati: {PASSATI}")
if FALLITI:
    print(f"test FALLITI: {len(FALLITI)}\n")
    for f in FALLITI:
        print(f"  [FALLITO] {f}")
    raise SystemExit(1)
print("tutti i test superati.")
