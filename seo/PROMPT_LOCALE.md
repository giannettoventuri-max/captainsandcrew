# Prompt per la sessione locale (con accessi SSH e API GSC)

Questo documento è il prompt da eseguire in una sessione di Claude Code che
ha accesso SSH a tuttoluce.com e credenziali API di Search Console.

**Come usarlo.** Nella sessione locale, dentro il clone del repository:

```
Leggi seo/PROMPT_LOCALE.md ed esegui l'attività che descrive.
```

Tutto il resto è già nel documento. Da qui in avanti il testo è rivolto alla
sessione locale.

---

## 1. Obiettivo

Sei in una sessione con accesso SSH a `tuttoluce.com` (WordPress +
WooCommerce + YITH) e credenziali API di Google Search Console per la
proprietà `www.tuttoluce.com`.

Devi completare un'analisi su robots.txt, crawl budget e indicizzazione, e
produrre una relazione basata su **dati reali**.

L'obiettivo del proprietario del sito, da tenere presente in ogni decisione:

> **PIÙ PAGINE UTILI INDICIZZATE + MENO CRAWLING SPRECATO SU URL INUTILI**
>
> Non: «meno pagine indicizzate».

Nello specifico: aumentare i prodotti WooCommerce indicizzati, mantenere
indicizzabili categorie, sottocategorie, marchi e pagine servizio, ed evitare
che Google spenda scansioni su URL tecniche, duplicate o generate da
WooCommerce/YITH.

Negli ultimi due mesi le pagine indicizzate sono **aumentate**
sensibilmente. Questo **non è di per sé un problema**: la prima cosa da
stabilire è **di cosa è fatto** quell'aumento. Se è fatto di prodotti e altre
URL utili, è il risultato voluto e **non va ridotto**.

## 2. Vincoli assoluti

1. **Non modificare la produzione** prima di aver consegnato la relazione.
   Nessuna modifica a robots.txt, sitemap, plugin, `.htaccess`, database o
   configurazione del server. Tutti i comandi di raccolta dati devono essere
   in **sola lettura**.
2. **Non inventare numeri.** Se un dato non è ottenibile, scrivi esplicitamente
   che non lo è e perché. Una relazione con dei buchi dichiarati è utile; una
   con stime spacciate per misure non lo è.
3. **Non considerare la riduzione delle pagine indicizzate un obiettivo.**
4. **Non bloccare** `/wp-content/plugins/` né `/wp-content/themes/`: i CSS e
   i JS servono a Google per renderizzare le pagine prodotto.
5. **Non bloccare la paginazione** (`/page/2/`, `?paged=`): è il modo in cui
   Google scopre i prodotti oltre la prima pagina di categoria.
6. **Non usare il robots.txt per deindicizzare.** Vedi §9.
7. Chiedi conferma prima di qualunque comando che scriva su disco sul server
   o che generi carico non banale (crawl massivi, query pesanti).

## 3. Cosa è già stabilito — non rifarlo

Un'analisi precedente ha prodotto il toolkit in `seo/` di questo repository,
sul branch `claude/seo-robots-indexing-analysis-xbxjkj`. Parti da lì: gli
strumenti esistono, sono testati, e non vanno riscritti.

Leggi prima: `seo/RELAZIONE.md`, `seo/README.md`,
`seo/robots/NOTE_REGOLE.md`, `seo/raccolta_dati.md`.

### Il risultato principale già acquisito

La bozza di robots.txt che era in discussione (salvata in
`seo/dati/robots_bozza_utente.txt`) **non blocca quasi nulla di ciò che
intende bloccare**. `seo/analisi/robots_matcher.py` rileva **24 regole inerti
su 38**. Verificato su URL reali:

| URL | esito con quella bozza |
|---|---|
| `/categoria-prodotto/lampadine/?filter_colore=bianco` | **consentita** |
| `/prodotto/lampada-e27/?add-to-cart=12345` | **consentita** |
| `/categoria-prodotto/lampadine/?orderby=price` | **consentita** |
| `/categoria-prodotto/lampadine/?yith_wcan=1&filtering=1` | **consentita** |
| `/?add-to-cart=12345` | bloccata ← solo la home |

Tre cause di forma, da conoscere perché guidano tutta la correzione:

1. **Il pattern combacia dall'inizio del percorso.** `Disallow: /?filter_`
   copre `/?filter_x=1` ma **non**
   `/categoria-prodotto/lampadine/?filter_x=1`. Le URL di filtro stanno sulle
   categorie, quindi la regola non protegge nulla. Serve `/*filter_`.
2. **`Disallow: /&param=` non combacia mai con niente**: `&` non può stare
   subito dopo la barra iniziale. Erano 11 righe morte.
3. **Il punto è letterale**: `Allow: /.js$` significa la URL esatta `/.js`.
   Serve `/*.js$`.

E una quarta regola che vale per tutto il file: **vince il pattern più lungo,
non l'ordine delle righe**; a parità di lunghezza vince `Allow`.

### L'ipotesi da verificare per prima

Se il robots.txt **in produzione** usa la stessa forma di pattern, allora il
crawling delle URL tecniche **non è mai stato limitato**, e l'aumento delle
pagine indicizzate va spiegato altrove. In quel caso la premessa iniziale del
lavoro va corretta, e va scritto nella relazione.

## 4. Fase 0 — setup

```bash
git checkout claude/seo-robots-indexing-analysis-xbxjkj
git pull
cd seo && ./autotest.sh        # atteso: tutti i controlli superati
```

Lavora sullo stesso branch. Committa i risultati man mano, non solo alla fine.

Crea `seo/dati_reali/` per gli output veri e **aggiungila a
`seo/.gitignore`** se contiene dati che non vuoi versionare (i log contengono
indirizzi IP). Versiona invece i **risultati aggregati** e la relazione.

## 5. Fase 1 — robots.txt attuale e la sua storia

```bash
curl -s https://www.tuttoluce.com/robots.txt | tee seo/dati_reali/robots_attuale.txt
python3 seo/analisi/robots_matcher.py seo/dati_reali/robots_attuale.txt
```

Questo risponde da solo alla domanda 5. Annota quante regole risultano inerti.

**Come viene servito** (errore frequente: un file fisico fa ignorare il
robots.txt virtuale di WordPress/Yoast/Rank Math, per cui le modifiche fatte
dal pannello non hanno effetto):

```bash
ssh <host> 'ls -la /percorso/public_html/robots.txt 2>/dev/null' \
  && echo "FILE FISICO: vince sul virtuale" || echo "generato da WordPress o plugin SEO"
```

### Ricostruire la versione precedente

Serve per il confronto prima/dopo e per datare la modifica. Tre fonti, in
ordine di affidabilità:

```bash
# 1. mtime del file fisico, se esiste
ssh <host> 'stat /percorso/public_html/robots.txt'

# 2. Wayback Machine: elenco delle versioni distinte
curl -s "http://web.archive.org/cdx/search/cdx?url=www.tuttoluce.com/robots.txt&output=json&from=2025&to=2026&collapse=digest"

# 3. scaricare una versione specifica ('id_' = contenuto originale non riscritto)
curl -s "https://web.archive.org/web/<timestamp>id_/https://www.tuttoluce.com/robots.txt" \
  > seo/dati_reali/robots_precedente.txt
```

Con le due versioni, il confronto è diretto:

```bash
python3 seo/analisi/robots_check.py \
    --robots seo/dati_reali/robots_precedente.txt \
    --confronta seo/dati_reali/robots_attuale.txt \
    --urls seo/dati_reali/url_da_log.txt
```

**Datare la modifica è importante**: è il `--taglio` dell'analisi dei log.

## 6. Fase 2 — struttura reale del sito

Gli slug in `seo/analisi/config.json` sono i default tipici di WooCommerce in
italiano e **non sono verificati**. Se sono sbagliati, i prodotti vengono
classificati come `pagina` e ogni percentuale della relazione è falsa.

```bash
ssh <host> 'wp option get woocommerce_permalinks --format=json'
ssh <host> 'wp option get permalink_structure'
ssh <host> 'wp taxonomy list --format=table'       # per lo slug dei marchi
```

Poi correggi `seo/analisi/config.json` con i valori reali e committa la
correzione.

### Filtri YITH: la verifica decisiva

YITH WooCommerce Ajax Navigation può generare i filtri come **query string**
oppure come **percorsi** ("SEO friendly / pretty URLs"). Nel secondo caso i
filtri sono URL normali, **nessuna regola sui parametri li intercetta**, e
ognuna è indicizzabile: da sola spiegherebbe un aumento delle pagine
indicizzate.

```bash
ssh <host> 'wp option get yith_wcan_settings --format=json' 2>/dev/null
ssh <host> 'wp plugin list --format=table | grep -i yith'

# nei log: percorsi di filtro invece di parametri
ssh <host> "zcat -f /var/log/nginx/access.log* | grep -i googlebot \
  | grep -oP '\"GET \K[^ ?\"]+' | grep -E '/(filter|filtro|filtra)[-_/]' \
  | sort | uniq -c | sort -rn | head -30"
```

Se le pretty URL sono attive: **affronta questo prima del robots.txt**, e con
`noindex` + canonical, non con un blocco (vedi §9). Conta quante sono e
quante risultano indicizzate.

## 7. Fase 3 — log di Googlebot

Verifica formato e storico disponibile:

```bash
ssh <host> 'ls -la /var/log/nginx/ /var/log/apache2/ ~/logs/ 2>/dev/null'
ssh <host> 'zcat -f /var/log/nginx/access.log* | head -3'
ssh <host> "zcat -f /var/log/nginx/access.log* | awk -F'[][]' '{print \$2}' \
  | cut -d: -f1 | sort -u | sed -n '1p;\$p'"
```

Serve il formato `combined` (con user-agent). **Se lo storico non copre la
data della modifica al robots.txt, il confronto prima/dopo dai log non è
possibile**: dillo e passa a §8, dove Search Analytics offre 16 mesi.

Porta i dati in locale filtrando lato server, per ridurre il trasferimento
(preferibile a installare o eseguire script in produzione):

```bash
ssh <host> "zcat -f /var/log/nginx/access.log* | grep -iE 'googlebot|storebot-google|google-inspectiontool'" \
  > seo/dati_reali/googlebot.log
```

Poi:

```bash
cd seo/analisi
python3 analizza_log.py ../dati_reali/googlebot.log --scopri          # conferma gli slug
python3 analizza_log.py ../dati_reali/googlebot.log --report --top 40 # Q3, Q4
python3 analizza_log.py ../dati_reali/googlebot.log --taglio <data-modifica-robots>
python3 analizza_log.py ../dati_reali/googlebot.log --robots ../dati_reali/robots_attuale.txt
python3 analizza_log.py ../dati_reali/googlebot.log --esporta-url ../dati_reali/url_da_log.txt
```

L'ultimo comando serve alla verifica più importante (Q6):

```bash
python3 robots_check.py --robots ../dati_reali/robots_attuale.txt \
                        --urls ../dati_reali/url_da_log.txt
```

**Esce con codice 2 se il robots.txt di produzione blocca URL utili.** Se
succede, è la priorità assoluta della relazione: una URL utile bloccata è un
danno attivo, una regola inerte è solo un'occasione persa.

### Googlebot falso

Parte del traffico che si dichiara Googlebot non lo è, e falserebbe i conteggi
di crawl budget. Verifica a campione i primi IP per volume:

```bash
awk '{print $1}' seo/dati_reali/googlebot.log | sort | uniq -c | sort -rn | head -20
host <ip>    # atteso: *.googlebot.com o *.google.com
```

Se una quota significativa è falsa, filtrala e dichiara il criterio usato.

## 8. Fase 4 — API di Search Console

**Leggi questa sezione prima di scrivere codice: le API non espongono ciò che
si aspetterebbe.**

### Cosa le API NON offrono

- **Nessuna API per il rapporto "Indicizzazione → Pagine"** in forma
  aggregata. I conteggi di *Indicizzate*, *Scansionata attualmente non
  indicizzata*, *Rilevata attualmente non indicizzata* non sono ottenibili
  come totali: vanno lette a mano dall'interfaccia, oppure ricostruite
  per-URL con la URL Inspection API (sotto).
- **Nessuna API per le Statistiche di scansione.** Il crawl rate va letto
  dall'interfaccia (e copre solo 90 giorni) oppure, meglio, dai log di §7.

Annota a mano dall'interfaccia, perché contengono lo storico che l'export non
ha: il grafico *Pagine* a 3 e 6 mesi, e le Statistiche di scansione
(richieste totali, per scopo, per tipo di file, per risposta).

### Cosa le API offrono, e che risolve il problema dello storico

**Search Analytics API** (`searchanalytics.query`) ha **16 mesi** di storico.
Non dà "le URL indicizzate", ma dà **le URL che hanno ricevuto impression**,
che è un ottimo indicatore di tendenza ed è classificabile per tipo. Questo
**rende ricostruibile il confronto prima/dopo** che dagli export era perduto.

Metodo: per ciascun mese degli ultimi 6, query con `dimensions: ["page"]`,
`rowLimit: 25000` con paginazione su `startRow`, poi conta le URL distinte e
classificale con `seo/analisi/classifica.py`.

Da dichiarare come limite: una URL indicizzata con zero impression non
compare, quindi i valori **sottostimano** le pagine indicizzate. Sono validi
per **confrontare periodi**, non come conteggio assoluto.

**URL Inspection API** (`urlInspection.index.inspect`) dà, per singola URL,
esattamente ciò che serve:

- `indexStatusResult.verdict` — PASS / NEUTRAL / FAIL
- `coverageState` — la stessa dizione del rapporto Pagine (es. *Submitted and
  indexed*, *Crawled - currently not indexed*, *Discovered - currently not
  indexed*)
- `robotsTxtState` — ALLOWED / DISALLOWED ← **incrocio diretto con Q6**
- `googleCanonical` e `userCanonical` ← **risponde a Q8**: se differiscono,
  Google ha scelto un'altra canonica
- `indexingState`, `lastCrawlTime`, `pageFetchState`, `sitemap`

Quota: **2000 URL al giorno**, 600 al minuto, per proprietà. Con un catalogo
ampio serve un campione casuale (500–1000 prodotti danno un margine di errore
accettabile) oppure più giorni. Implementa una pausa fra le chiamate e la
ripresa da dove si era interrotto.

**Sitemaps API** (`sitemaps.list`, `sitemaps.get`) dà le sitemap inviate e i
conteggi. Il campo `indexed` spesso non è popolato: non basarci conclusioni,
usa la URL Inspection API.

### Cosa scrivere

Aggiungi al toolkit `seo/analisi/gsc_api.py`, con sottocomandi:

- `storico` — Search Analytics mese per mese, URL distinte classificate per
  tipo, tabella prima/dopo (**Q1, Q2**)
- `ispeziona` — URL Inspection su una lista di URL, con `--campione N`,
  gestione della quota, ripresa, output CSV con
  `coverageState` / `robotsTxtState` / canonical (**Q2, Q6, Q8**)
- `sitemap` — Sitemaps API

Riusa `classifica.py` per la tassonomia: non duplicare la logica. Aggiungi
test in stile `test_matcher.py` per il parsing delle risposte, usando risposte
finte (non chiamare l'API nei test).

`seo/analisi/gsc_report.py` resta valido per gli export CSV fatti a mano
dall'interfaccia, ed è la via più rapida se le API danno problemi di
autenticazione.

## 9. Fase 5 — sitemap, canonical, noindex

```bash
cd seo/analisi
python3 audit_sitemap.py https://www.tuttoluce.com/sitemap_index.xml \
    --robots ../dati_reali/robots_attuale.txt \
    --campione-canonical 100 --pausa 0.5 \
    --esporta-url ../dati_reali/url_sitemap.txt
```

Risponde a **Q7** (la sitemap contiene solo URL da indicizzare?) e a parte di
**Q8** (conflitti). Il conflitto più grave che cerca: una URL presente in
sitemap **e** bloccata da robots.txt — segnale contraddittorio.

### Il principio che deve guidare le raccomandazioni

**Il robots.txt non deindicizza.** Bloccare una URL già indicizzata impedisce
a Google di leggerne il `noindex`: può restare in indice come *"Indicizzata,
ma bloccata da robots.txt"*.

Ordine corretto per URL **già indicizzate** da rimuovere:

1. `noindex`, lasciandole **scansionabili**
2. attendere che Google le escluda
3. **solo dopo** bloccarle in robots.txt per risparmiare scansioni

Per URL **non ancora indicizzate**, il blocco immediato va bene.

**Conseguenza operativa da verificare**: poiché oggi con ogni probabilità
nulla blocca i filtri, molti potrebbero già essere in indice. In quel caso
passare direttamente al blocco **li congela in indice**. Quantificalo con la
URL Inspection API o con l'export "Indicizzate" **prima** di proporre la
pubblicazione, e proponi la sequenza `noindex` → attesa → blocco.

## 10. Fase 6 — prodotti

L'obiettivo primario. Costruisci il triangolo **pubblicati → in sitemap →
indicizzati**:

```bash
ssh <host> 'wp post list --post_type=product --post_status=publish --format=count'
ssh <host> 'wp post list --post_type=product --post_status=private --format=count'

# prodotti messi a noindex dal plugin SEO (Yoast; con Rank Math: rank_math_robots)
ssh <host> "wp db query \"SELECT COUNT(*) FROM wp_postmeta m
  JOIN wp_posts p ON p.ID = m.post_id
  WHERE p.post_type='product' AND p.post_status='publish'
    AND m.meta_key='_yoast_wpseo_meta-robots-noindex' AND m.meta_value='1';\""

# prodotti senza contenuto: candidati tipici a 'Crawled - currently not indexed'
ssh <host> "wp db query \"SELECT COUNT(*) FROM wp_posts
  WHERE post_type='product' AND post_status='publish'
    AND (post_content='' OR post_content IS NULL);\""

# prodotti fuori stock o nascosti dal catalogo
ssh <host> "wp db query \"SELECT tt.taxonomy, t.name, COUNT(*) FROM wp_term_relationships tr
  JOIN wp_term_taxonomy tt ON tt.term_taxonomy_id = tr.term_taxonomy_id
  JOIN wp_terms t ON t.term_id = tt.term_id
  WHERE tt.taxonomy='product_visibility' GROUP BY tt.taxonomy, t.name;\""
```

I due scarti hanno **cause diverse e rimedi diversi**:

- **pubblicati ≫ in sitemap** → configurazione del plugin SEO, o `noindex`
  per-prodotto, o esclusioni per visibilità
- **in sitemap ≫ indicizzati** → qualità o duplicazione del contenuto, o
  profondità dei link interni. **Non si risolve col robots.txt**

Poi cerca i pattern comuni fra i prodotti non indicizzati: usa l'output della
URL Inspection API e verifica se i `Crawled - currently not indexed` hanno
caratteristiche condivise (descrizione vuota, variazioni, fuori stock,
categoria specifica, profondità di link, canonical divergente).

Se emerge che il collo di bottiglia è la **qualità del contenuto** e non la
scansione, scrivilo chiaramente: in quel caso nessuna modifica al robots.txt
aumenterà i prodotti indicizzati, e proporla sarebbe fuorviante.

## 11. Fase 7 — relazione

Riscrivi `seo/RELAZIONE.md` sostituendo ogni «senza dati» con i numeri reali.
Mantieni la struttura a 10 domande e aggiungi, in cima, una sintesi di 10–15
righe che risponda alla domanda di fondo:

> **L'aumento delle pagine indicizzate degli ultimi due mesi è fatto di URL
> utili o di URL indesiderate?**

Per ciascuna delle 10 domande: il numero, la fonte da cui viene, e la data a
cui si riferisce. Dove un dato non è ottenibile, dillo e spiega perché.

Includi la tabella prima/dopo con: prodotti indicizzati, URL indicizzate
totali, URL escluse per motivo, richieste Googlebot/giorno, quota richieste
verso prodotti e categorie, quota verso URL con parametri, numero di URL
add-to-cart, filtro e ordinamento.

## 12. Fase 8 — robots.txt definitivo

Parti da `seo/robots/robots_proposto.txt` (già corretto nella forma dei
pattern) e **adattalo ai dati reali**:

- slug verificati in Fase 2
- parametri realmente presenti nei log (`--scopri`), non quelli presunti
- eventuali pretty URL di YITH, che richiedono regole sul **percorso**
- eventuali filtri che sono landing SEO intenzionali, da sbloccare con un
  `Allow` più lungo del `Disallow`

Verifiche obbligatorie prima di proporre la pubblicazione (in coda a
`seo/robots/NOTE_REGOLE.md`):

```bash
python3 robots_matcher.py ../robots/robots_proposto.txt      # 0 regole inerti
python3 robots_check.py --robots ../dati_reali/robots_attuale.txt \
                        --confronta ../robots/robots_proposto.txt \
                        --urls ../dati_reali/url_da_log.txt   # exit 0 richiesto
python3 audit_sitemap.py <indice> --robots ../robots/robots_proposto.txt
```

Consegna un **piano di pubblicazione sequenziato**, non solo un file:

1. cosa si può bloccare subito (URL non indicizzate)
2. cosa richiede prima `noindex` e quanto attendere (URL già indicizzate)
3. cosa non va toccato con il robots.txt e va gestito altrimenti
4. cosa verificare in Search Console dopo la pubblicazione: *Impostazioni →
   robots.txt*; *Controllo URL* su 3 prodotti, 2 categorie e 1 marchio;
   *Visualizza pagina sottoposta a scansione* su una categoria per verificare
   che non risultino risorse bloccate; *Statistiche di scansione* dopo 2–3
   settimane
5. quali metriche indicano successo: richieste verso prodotti in **aumento**,
   richieste verso URL con parametri in **calo**, prodotti indicizzati in
   **aumento**

**Non pubblicare.** Presenta il piano e attendi conferma.

## 13. Consegna

Committa sul branch `claude/seo-robots-indexing-analysis-xbxjkj`:

- `seo/RELAZIONE.md` aggiornata con i dati reali
- `seo/analisi/gsc_api.py` + test
- `seo/analisi/config.json` con gli slug verificati
- `seo/robots/robots_proposto.txt` adattato + `NOTE_REGOLE.md` aggiornato
- output aggregati in `seo/dati_reali/` (**non** i log grezzi con gli IP)
- `seo/dati_reali/README.md` con data di raccolta e periodo coperto da ogni file

Non aprire una pull request se non viene chiesto.

Riferisci alla fine: le risposte alle 10 domande in forma sintetica, cosa
non è stato possibile misurare e perché, e le due o tre azioni che hanno il
maggior impatto atteso sull'indicizzazione dei prodotti.

## 14. Trappole già identificate, da controllare in produzione

1. **Stili dei blocchi Gutenberg.** `Disallow: /wp-includes/` accompagnato
   solo da `Allow: /*.css$` lascia **bloccato**
   `/wp-includes/blocks/.../style.css`, perché vince il pattern più lungo.
   Serve `Allow: /wp-includes/blocks/`.
2. **`admin-ajax.php`.** Se `Disallow: /wp-admin/` non è accompagnato da
   `Allow: /wp-admin/admin-ajax.php` e il tema carica le griglie prodotto via
   AJAX, Google può non vedere i prodotti nelle pagine categoria.
3. **Feed annidati.** `Disallow: /feed/` da sola copre solo la radice:
   restano scansionabili `/categoria-prodotto/x/feed/` e `/prodotto/y/feed/`,
   che su un catalogo ampio sono tanti quanti prodotti e categorie. Serve
   anche `/*/feed/`.
4. **Ricerca prodotti WooCommerce.** La forma è
   `?post_type=product&s=lampada`: il parametro `s` non è il primo, quindi
   serve `/*&s=` oltre a `/*?s=`.
5. **`srsltid`.** Parametro aggiunto da Google Shopping: su molti store
   WooCommerce è una fonte consistente di duplicati. Controlla se compare nei
   log e in GSC.
6. **robots.txt fisico contro virtuale.** Se esiste il file, le modifiche
   fatte dal pannello del plugin SEO non hanno effetto.
