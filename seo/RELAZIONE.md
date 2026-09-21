# Tuttoluce — Relazione su robots.txt e indicizzazione

Data: 21 settembre 2026

---

## In breve

**Non ho potuto eseguire l'analisi sui dati reali.** Questa sessione non ha
accesso a Search Console, al server, né al sito: l'egress di rete verso
`www.tuttoluce.com` è bloccato dalla policy, non esiste un client SSH né
credenziali, e il repository è vuoto. Dettaglio in *Limiti di accesso*.
Le domande 1–4, 7 e 8 richiedono quei dati e **restano aperte**: non le
riempio con stime.

**Ho però trovato un problema verificabile senza accesso al sito, e va
affrontato prima di qualunque altra cosa.** La bozza di robots.txt contenuta
nella richiesta **non bloccherebbe quasi nulla di ciò che intende bloccare**:
24 delle sue 38 regole non combaciano con nessuna URL reale generata da
WooCommerce o YITH. Filtri, ordinamenti e add-to-cart passerebbero al 100%.

Se la configurazione attualmente in produzione usa la stessa forma di
pattern — cosa probabile, dato che la bozza è presentata come evoluzione
dell'esistente — allora **la premessa della richiesta va rovesciata**: non
stiamo valutando se un robots.txt efficace abbia ridotto troppo
l'indicizzazione, stiamo guardando un robots.txt che con ogni probabilità
non ha mai limitato il crawling delle URL tecniche. L'aumento delle pagine
indicizzate va quindi spiegato altrove, e la prima verifica sui dati cambia
di conseguenza (vedi *Prossimo passo*).

Consegnato in questo ramo: un toolkit che produce la relazione completa una
volta eseguito dove i dati sono raggiungibili, un robots.txt corretto da
validare, e la motivazione di ogni regola.

---

## Limiti di accesso

| Serve per | Stato |
|---|---|
| Search Console (Q1, Q2, Q7, Q8) | **nessun accesso.** Connettori disponibili: Gmail, Google Calendar, Google Drive. Nessuno espone Search Console. Non esiste API di export per il rapporto di indicizzazione. |
| Log del server (Q3, Q4, prima/dopo) | **nessun accesso.** `ssh` non è installato, nessuna chiave in `~/.ssh/`, nessuna credenziale nell'ambiente. |
| robots.txt e sitemap live (Q5, Q6, Q7) | **bloccato dalla policy di rete.** `CONNECT www.tuttoluce.com:443` → 403. Confermato sia via `curl` sia via fetch lato server. |
| Codice del sito | **assente.** Il repository contiene solo `.gitkeep`, in tutta la storia dei commit. |

Non ho aggirato il blocco di rete e non ho modificato nulla in produzione,
come richiesto.

---

## Le dieci domande

### 1. L'aumento riguarda URL utili o indesiderate?

**Senza dati.** Serve il confronto fra due export di Search Console.
`analisi/gsc_report.py --confronta-con` produce la classificazione
dell'incremento (prodotti / categorie / sottocategorie / marchi / pagine /
articoli / filtri / parametri / paginazione / tecniche) e il verdetto.

Una cosa da dire subito, perché cambia l'interpretazione: se le regole
attualmente in produzione sono inerti come quelle della bozza, l'aumento
**non può essere una conseguenza del robots.txt** — né in bene né in male. Le
cause da guardare per prime diventano altre: nuovi prodotti pubblicati,
crescita dell'autorevolezza del dominio, un cambio di permalink, la comparsa
di `srsltid` da Google Shopping, o filtri YITH con pretty URL attive
(vedi Q3).

### 2. Quanti prodotti indicizzati oggi rispetto a prima?

**Senza dati.** Search Console non espone lo storico via export: se non
esiste un export del periodo precedente, il confronto **non è
ricostruibile a posteriori**. Il grafico a 3/6 mesi in *Indicizzazione →
Pagine* è l'unica fonte dello storico e va letto a mano.

Va costruito il triangolo **pubblicati → in sitemap → indicizzati**
(comandi in `raccolta_dati.md`, punto 5). I due scarti hanno cause diverse:

- pubblicati ≫ in sitemap → configurazione del plugin SEO
- in sitemap ≫ indicizzati → qualità o duplicazione del contenuto, oppure
  profondità di link interni. **Non si risolve col robots.txt.**

### 3. Quali URL stanno consumando crawling inutilmente?

**Senza dati**, ma lo strumento è pronto: `analisi/analizza_log.py --report`
classifica ogni richiesta di Googlebot e produce la classifica delle URL di
spreco.

Un'ipotesi da verificare per prima, perché se vera invalida tutto
l'approccio basato sui parametri: **YITH WooCommerce Ajax Navigation può
generare URL di filtro come percorsi** invece che come query string
("SEO friendly URLs"). In quel caso i filtri sono URL normali, nessuna
regola sui parametri li intercetta, e ognuna di esse è indicizzabile —
il che spiegherebbe da sé un aumento delle pagine indicizzate. Verifica in
`raccolta_dati.md`, punto 6. **Da controllare prima di tutto il resto.**

### 4. Quanto crawling va a parametri, filtri, add-to-cart, URL tecniche?

**Senza dati.** `analizza_log.py` riporta la quota per qualificatore e il
confronto prima/dopo per richieste/giorno. Serve un log con user-agent
(formato `combined`).

Nota sul metodo: le *Statistiche di scansione* di Search Console coprono solo
90 giorni. Se la modifica al robots.txt è più vecchia, il prima/dopo si fa
**solo** sui log del server.

### 5. Le regole attuali stanno bloccando questi pattern?

**Questa ha una risposta, e non richiede accesso al sito.**

Sulla bozza fornita nella richiesta: **no, quasi per nulla.**
`robots_matcher.py` — motore conforme a RFC 9309, con 49 test — rileva
**24 regole inerti su 38**. Verifica su URL reali:

| URL | esito con la bozza |
|---|---|
| `/categoria-prodotto/lampadine/?filter_colore=bianco` | **consentita** |
| `/categoria-prodotto/faretti/led/?min_price=10&max_price=90` | **consentita** |
| `/prodotto/lampada-e27/?add-to-cart=12345` | **consentita** |
| `/categoria-prodotto/lampadine/?orderby=price` | **consentita** |
| `/categoria-prodotto/lampadine/?yith_wcan=1&filtering=1` | **consentita** |
| `/categoria-prodotto/lampadine/?s=led` | **consentita** |
| `/categoria-prodotto/lampadine/feed/` | **consentita** |
| `/?add-to-cart=12345` | bloccata |
| `/?filter_colore=bianco` | bloccata |

Su un campione di 178 URL: **0%** dei filtri, **0%** degli add-to-cart,
**0%** degli ordinamenti bloccati. Solo le varianti sulla home vengono
intercettate.

Tre cause di forma, tutte verificabili:

1. **`Disallow: /?filter_` combacia solo dalla radice.** Le URL di filtro
   stanno sulle categorie, il cui percorso non comincia per `/?filter_`.
   Serve `/*filter_`.
2. **`Disallow: /&add-to-cart=` non combacia mai con niente.** `&` non può
   trovarsi subito dopo la barra iniziale. Sono 11 righe inerti.
3. **In `Allow: /.js$` il punto è letterale**: significa la URL esatta
   `/.js`. Serve `/*.js$`.

Con `robots_attuale.txt` lo stesso comando dà la risposta per la produzione:

```bash
python3 analisi/robots_matcher.py robots_attuale.txt
```

### 6. Esistono regole che ostacolano la scoperta dei prodotti?

**Nella bozza, no** — verificato: nessuna URL utile del campione risulta
bloccata, e `Allow: /wp-includes/js/` prevale correttamente su
`Disallow: /wp-includes/` (vince il pattern più lungo), quindi jQuery resta
accessibile.

**Sulla produzione: da verificare**, con
`robots_check.py --robots robots_attuale.txt --urls url_da_log.txt`. Il
comando esce con codice 2 se trova URL utili bloccate.

Due trappole da controllare in modo specifico, perché sono silenziose:

- **Stili dei blocchi Gutenberg.** `Disallow: /wp-includes/` con solo
  `Allow: /*.css$` lascia bloccato `/wp-includes/blocks/.../style.css`: il
  `Disallow` è più lungo e quindi vince. Serve `Allow: /wp-includes/blocks/`.
- **`admin-ajax.php`.** Se `Disallow: /wp-admin/` non è accompagnato da
  `Allow: /wp-admin/admin-ajax.php`, e il tema carica le griglie prodotto via
  AJAX, Google può non vedere i prodotti nelle pagine categoria.

### 7. La sitemap contiene solo URL da indicizzare?

**Senza dati.** `analisi/audit_sitemap.py` verifica composizione per tipo,
duplicati, URL con parametri, URL in sitemap **bloccate da robots.txt**
(segnale contraddittorio) e, su campione, `noindex` e canonical divergenti.

### 8. Ci sono conflitti fra canonical, noindex e robots?

**Senza dati** per la parte specifica del sito. Il principio, che vale a
prescindere e che è la fonte più comune di errore:

**Bloccare in robots.txt una URL già indicizzata non la deindicizza.**
Impedisce a Google di leggerne il `noindex`, e la URL può restare in indice
come *"Indicizzata, ma bloccata da robots.txt"*.

Ordine corretto per URL **già indicizzate** da rimuovere:

1. `noindex`, lasciando la URL **scansionabile**
2. attendere che Google la escluda
3. **solo dopo** bloccarla in robots.txt

Per URL **non ancora indicizzate**, il blocco immediato è corretto. Poiché
la bozza non blocca nulla oggi, gran parte dei filtri potrebbe già essere
in indice: **in quel caso passare direttamente al blocco li congela in
indice**. Va verificato con l'export "Indicizzate" prima di pubblicare, ed è
la ragione principale per cui la sequenza conta più del contenuto del file.

### 9. Quali modifiche sono consigliabili?

In ordine. I punti 1–3 non richiedono decisioni, sono verifiche.

1. **Verificare se le pretty URL di YITH sono attive** (`raccolta_dati.md`,
   punto 6). Se lo sono, è probabilmente la spiegazione dell'aumento di
   pagine indicizzate e va affrontato prima del robots.txt — con `noindex`
   e canonical, non con un blocco.
2. **Far girare `robots_matcher.py` sul robots.txt di produzione.** Se anche
   quello è pieno di regole inerti, la premessa della richiesta va corretta:
   il crawling delle URL tecniche non è mai stato limitato.
3. **Verificare che la produzione non blocchi URL utili** (Q6), incluse le
   due trappole silenziose. Questa ha priorità su tutto il resto: una URL
   utile bloccata è un danno attivo, una regola inerte è un'occasione persa.
4. **Correggere la forma dei pattern**, usando `/*param=` al posto di
   `/?param=` e `/&param=`. È il cuore della correzione.
5. **Sequenziare secondo Q8**: per i filtri già indicizzati, prima
   `noindex`, poi il blocco.
6. **Non toccare la paginazione.** Confermo il ragionamento della richiesta,
   e aggiungo il meccanismo: la paginazione di WordPress è `/page/2/`, un
   percorso, quindi `Disallow: /?paged=` sarebbe inerte comunque; ma se
   diventasse efficace impedirebbe a Google di raggiungere i prodotti oltre
   la prima pagina di categoria — l'opposto dell'obiettivo.
7. **Non bloccare `/wp-content/plugins/` né `/wp-content/themes/`.**
   Confermo: la proposta non li blocca e li dichiara esplicitamente `Allow`.
8. **Separare gli strumenti**: robots.txt per il crawling, `noindex` per
   l'indice, canonical per i duplicati, sitemap per la scoperta.

Da non fare: ridurre le pagine indicizzate come obiettivo in sé. Se
l'incremento è fatto di prodotti, è il risultato voluto.

### 10. Quale robots.txt definitivo?

`robots/robots_proposto.txt`, con motivazione di ogni regola in
`robots/NOTE_REGOLE.md`.

**Non è pubblicabile così com'è**: presuppone slug che non ho potuto
verificare. Le verifiche obbligatorie sono in fondo a `NOTE_REGOLE.md`.

Esito misurato sul campione di 178 URL, bozza → proposta:

| | bozza | proposta |
|---|---|---|
| filtri bloccati | 0% | 100% |
| add-to-cart bloccati | 0% | 100% |
| ordinamenti bloccati | 0% | 100% |
| ricerca interna bloccata | 100% | 100% |
| **URL utili bloccate** | **0** | **0** |
| prodotti scansionabili | sì | sì |
| paginazione scansionabile | sì | sì |
| CSS/JS di tema e plugin | accessibili | accessibili |
| stili blocchi Gutenberg | accessibili | accessibili |
| `admin-ajax.php` | accessibile | accessibile |
| regole inerti | 24 su 38 | 0 |

---

## Prossimo passo

Due modi per chiudere l'analisi.

**A — mi dai accesso.** Basta uno fra:

- gli output elencati in `raccolta_dati.md` punto 7, incollati qui (è la via
  più rapida e non richiede di cambiare nulla nell'ambiente);
- l'abilitazione di `www.tuttoluce.com` nella policy di egress, così leggo
  robots.txt e sitemap da qui;
- credenziali SSH in sola lettura per i log — tenendo presente che questo
  ambiente non ha un client SSH installato.

Con i log e un export di Search Console riempio le domande 1–4, 7 e 8 con
numeri reali e aggiorno questa relazione.

**B — li esegui tu.** `raccolta_dati.md` ha i comandi; il toolkit gira con
Python 3 senza dipendenze esterne. Serve solo copiare `seo/analisi/` sul
server.

In entrambi i casi la produzione resta invariata finché i dati non ci sono,
come richiesto.

---

## File consegnati

```
seo/
├── RELAZIONE.md                questo documento
├── raccolta_dati.md            comandi per raccogliere i dati (sola lettura)
├── robots/
│   ├── robots_proposto.txt     candidato corretto — NON pubblicare prima delle verifiche
│   └── NOTE_REGOLE.md          motivazione di ogni regola (Q10) + i tre errori di forma
└── analisi/
    ├── classifica.py           tassonomia URL su due dimensioni
    ├── robots_matcher.py       motore RFC 9309 + rilevatore di regole inerti
    ├── robots_check.py         verifica un robots.txt su URL reali; confronta due versioni
    ├── analizza_log.py         classifica le richieste di Googlebot; confronto prima/dopo
    ├── audit_sitemap.py        audit sitemap + conflitti robots/canonical/noindex
    ├── gsc_report.py           analizza gli export di Search Console; confronto fra periodi
    ├── test_matcher.py         49 test sul motore di matching
    └── config.json             slug del sito — DA VERIFICARE
```

Nessuno di questi strumenti scrive sul sito: leggono log, export e URL.
