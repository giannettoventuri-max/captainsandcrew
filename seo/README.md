# Toolkit SEO Tuttoluce — robots.txt, crawling, indicizzazione

Strumenti per rispondere con dati reali alle domande su robots.txt, crawl
budget e indicizzazione dei prodotti.

**Leggere prima [`RELAZIONE.md`](RELAZIONE.md).** Contiene lo stato
dell'analisi, cosa è già stabilito e cosa richiede accesso ai dati.

Requisiti: Python 3.9+, nessuna dipendenza esterna. Tutti gli strumenti sono
in **sola lettura**: non modificano il sito.

---

## Avvio rapido

```bash
cd seo/analisi

# 0. verifica che il toolkit funzioni (49 test)
python3 test_matcher.py

# 1. il robots.txt attuale contiene regole che non fanno nulla?
python3 robots_matcher.py /percorso/robots_attuale.txt

# 2. quali sono gli slug e i parametri VERI del sito?
python3 analizza_log.py '/var/log/nginx/access.log*' --scopri
#    -> aggiornare config.json con quello che si vede

# 3. cosa richiede davvero Googlebot
python3 analizza_log.py '/var/log/nginx/access.log*' --report --top 40

# 4. confronto prima/dopo la modifica al robots.txt
python3 analizza_log.py '/var/log/nginx/access.log*' --taglio 2026-07-15

# 5. il robots.txt attuale blocca URL utili? (la domanda più importante)
python3 analizza_log.py '/var/log/nginx/access.log*' --esporta-url url.txt
python3 robots_check.py --robots /percorso/robots_attuale.txt --urls url.txt

# 6. confronto fra attuale e proposto
python3 robots_check.py --robots /percorso/robots_attuale.txt \
                        --confronta ../robots/robots_proposto.txt --urls url.txt

# 7. audit della sitemap (richiede rete verso il sito)
python3 audit_sitemap.py https://www.tuttoluce.com/sitemap_index.xml \
                         --robots /percorso/robots_attuale.txt

# 8. export di Search Console
python3 gsc_report.py --file indicizzate_oggi.csv \
                      --confronta-con indicizzate_giugno.csv
```

Comandi completi per la raccolta dei dati sul server:
[`raccolta_dati.md`](raccolta_dati.md).

---

## Gli strumenti

| File | A cosa serve | Domande |
|---|---|---|
| `robots_matcher.py` | Motore di matching RFC 9309 + rilevatore di regole inerti | Q5 |
| `robots_check.py` | Verifica un robots.txt su URL reali; confronta due versioni | Q5, Q6 |
| `analizza_log.py` | Classifica le richieste di Googlebot; confronto prima/dopo | Q3, Q4 |
| `audit_sitemap.py` | Audit sitemap; conflitti con robots/canonical/noindex | Q7, Q8 |
| `gsc_report.py` | Analizza gli export di Search Console; confronto fra periodi | Q1, Q2 |
| `classifica.py` | Tassonomia condivisa delle URL | tutte |
| `test_matcher.py` | 49 test sul motore | — |

`robots_check.py` esce con **codice 2** se trova URL utili bloccate: è usabile
in uno script di controllo.

---

## Come vengono classificate le URL

Due dimensioni indipendenti, perché servono a rispondere a domande diverse:

- **`tipo`** — che risorsa è: `prodotto`, `categoria_prodotto`,
  `sottocategoria_prodotto`, `marchio`, `pagina`, `articolo`, `feed`,
  `transazionale`, `tecnica`, `asset_statico`, …
- **`qualificatore`** — cosa aggiunge la query string: `filtro`,
  `ordinamento`, `add_to_cart`, `ricerca_interna`, `paginazione`,
  `tracking`, `parametro_tecnico`, `nessuno`

Tenerle separate evita il doppio conteggio.
`/categoria-prodotto/lampadine/?filter_colore=bianco` è **categoria** *e*
**filtro**: sommarle come se fossero categorie alternative falserebbe le
percentuali. Da qui si derivano `utile` e `spreco`.

Due scelte deliberate, coerenti con l'obiettivo:

- la **paginazione non è spreco**: è il modo in cui Google scopre i prodotti
  oltre la prima pagina di categoria;
- **CSS e JS di tema e plugin non sono spreco**: servono al rendering.

---

## Verificare gli slug prima di fidarsi dei numeri

`config.json` contiene i valori tipici di WooCommerce in italiano
(`/prodotto/`, `/categoria-prodotto/`, `/marca/`, …) ma **non sono stati
verificati sul sito reale.** Se gli slug non corrispondono, i prodotti
vengono classificati come `pagina` e tutte le percentuali sono sbagliate.

```bash
python3 analizza_log.py '/var/log/nginx/access.log*' --scopri
```

Mostra i primi segmenti di percorso e i nomi reali dei parametri, ordinati
per frequenza. Correggere `config.json` con quello che si vede.

---

## Le tre regole di robots.txt che si sbagliano più spesso

Tutte verificabili con `python3 robots_matcher.py <file>`. Spiegazione
completa in [`robots/NOTE_REGOLE.md`](robots/NOTE_REGOLE.md).

**1. Il pattern combacia dall'inizio del percorso.**
`Disallow: /?filter_` copre `/?filter_x=1` ma **non**
`/categoria-prodotto/lampadine/?filter_x=1`. Le URL di filtro stanno sulle
categorie, quindi la regola non protegge nulla. Serve `/*filter_`.

**2. `Disallow: /&param=` non combacia mai con niente.**
`&` non può stare subito dopo la barra iniziale. Usare `/*param=`, che copre
sia `?param=` sia `&param=`.

**3. Il punto è letterale.** `Allow: /.js$` significa la URL esatta `/.js`.
Serve `/*.js$`.

**E una quarta, che vale per tutto il file: vince il pattern più lungo, non
l'ordine delle righe.** Un `Allow` generico non salva da un `Disallow` più
specifico: con `Disallow: /wp-includes/` + `Allow: /*.css$`, il file
`/wp-includes/blocks/gallery/style.css` resta **bloccato**. Serve un `Allow`
altrettanto specifico.

---

## Cosa il robots.txt non può fare

| Strumento | A cosa serve |
|---|---|
| **robots.txt** | evitare la **scansione** di URL senza valore |
| **noindex** | tenere fuori dall'**indice** una URL che resta scansionabile |
| **canonical** | indicare la versione principale fra URL duplicate |
| **sitemap** | far **scoprire** le URL canoniche che vogliamo indicizzare |

Due conseguenze pratiche:

- **Il robots.txt non deindicizza.** Bloccare una URL già indicizzata
  impedisce a Google di leggerne il `noindex`: può restare in indice come
  *"Indicizzata, ma bloccata da robots.txt"*. Per le URL già in indice
  l'ordine è: prima `noindex` lasciandole scansionabili, poi il blocco.
- **Il robots.txt non aumenta l'indicizzazione dei prodotti.** Libera
  capacità di scansione, utile solo se la scansione era il collo di
  bottiglia. Se i prodotti sono *"Scansionata, attualmente non
  indicizzata"*, Google li ha già letti e ha deciso di no: la causa è il
  contenuto, e nessuna modifica al robots.txt la cambia.

---

## Dati di prova

`dati/` contiene fixture sintetiche per verificare il funzionamento degli
strumenti senza accesso al sito:

- `finto_access.log` — log Googlebot sintetico su due periodi
- `gsc_giugno.csv`, `gsc_settembre.csv` — export GSC finti
- `robots_bozza_utente.txt` — la bozza di robots.txt da analizzare

```bash
./autotest.sh     # esegue tutto il toolkit sulle fixture
```

Sono dati **inventati**: servono a verificare gli strumenti, non a trarre
conclusioni sul sito.
