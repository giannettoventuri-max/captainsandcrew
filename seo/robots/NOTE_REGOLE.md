# robots.txt proposto — motivazione di ogni regola

Risposta alla domanda 10. Ogni blocco di regole di `robots_proposto.txt` è
motivato qui sotto. Il file **non va pubblicato** prima delle verifiche
elencate in fondo.

---

## I tre errori di forma che rendono inefficace la bozza attuale

Prima delle singole regole, i tre meccanismi che spiegano perché la bozza
proposta nella richiesta non avrebbe funzionato. Sono verificabili con
`python3 analisi/robots_matcher.py <file>`.

### 1. Il pattern deve combaciare dall'inizio del percorso

Il confronto avviene su **percorso + query string** e parte dall'inizio.
Quindi:

```
Disallow: /?filter_
```

combacia con `/?filter_colore=bianco` (la home) ma **non** con
`/categoria-prodotto/lampadine/?filter_colore=bianco`, perché quel percorso
non comincia con `/?filter_`.

Le URL di filtro di WooCommerce e YITH stanno **sulle pagine categoria**, non
sulla home. La regola quindi non protegge nulla di ciò che conta. Serve il
wildcard:

```
Disallow: /*filter_
```

### 2. `Disallow: /&parametro=` non combacia mai con nessuna URL

Perché combaciasse, la URL dovrebbe avere `&` immediatamente dopo la barra
iniziale — cosa che non avviene: `&` compare solo **dentro** una query
string, dopo un `?`. Tutte le 11 righe `/&...` della bozza sono inerti.

La forma `/*parametro=` copre entrambe le posizioni (`?parametro=` e
`&parametro=`) con una sola riga.

### 3. In `Allow: /.js$` il punto è letterale

Significa "la URL esatta `/.js`", non "i file `.js`". La forma corretta è
`/*.js$`.

### Esito misurato sulla bozza

`robots_matcher.py` rileva **24 regole inerti su 38** nella bozza. Verificato
su URL reali di tipo WooCommerce:

| URL | esito con la bozza |
|---|---|
| `/categoria-prodotto/lampadine/?filter_colore=bianco` | **consentita** |
| `/categoria-prodotto/faretti/led/?min_price=10&max_price=90` | **consentita** |
| `/prodotto/lampada-e27/?add-to-cart=12345` | **consentita** |
| `/categoria-prodotto/lampadine/?orderby=price` | **consentita** |
| `/categoria-prodotto/lampadine/?yith_wcan=1&filtering=1` | **consentita** |
| `/?add-to-cart=12345` | bloccata |
| `/?filter_colore=bianco` | bloccata |

Vengono bloccate solo le varianti **sulla home**, che sono una quantità
trascurabile. Su un campione di 178 URL: **0%** dei filtri, **0%** degli
add-to-cart e **0%** degli ordinamenti risultano bloccati.

### Una quarta regola, che vale per tutto il file

**Vince il pattern più lungo, non l'ordine delle righe.** A parità di
lunghezza vince `Allow`. Questo ha una conseguenza pratica non ovvia: un
`Allow` generico non salva da un `Disallow` più specifico.

```
Disallow: /wp-includes/          (13 caratteri)
Allow: /*.css$                   (7 caratteri)
```

Con queste due righe `/wp-includes/blocks/gallery/style.css` risulta
**bloccato**, perché il `Disallow` è più lungo. Gli stili dei blocchi
Gutenberg stanno lì. Serve un `Allow` altrettanto specifico:
`Allow: /wp-includes/blocks/`.

---

## Motivazione regola per regola

### Area amministrativa

```
Disallow: /wp-admin/
Allow: /wp-admin/admin-ajax.php
```

`admin-ajax.php` **resta consentito** ed è la riga più importante del blocco:
molti temi e YITH caricano griglie prodotto e filtri via AJAX passando da
qui. Bloccarlo può impedire a Google di renderizzare le pagine categoria,
cioè esattamente il contrario dell'obiettivo. L'`Allow` è più lungo del
`Disallow`, quindi vince.

```
Disallow: /wp-login.php
Disallow: /wp-register.php
Disallow: /xmlrpc.php
Disallow: /wp-cron.php
Disallow: /wp-trackback.php
```

Endpoint senza contenuto indicizzabile. `wp-cron.php` in particolare può
essere richiesto ripetutamente e non produce nulla di utile.

### REST API

```
Disallow: /wp-json/
Disallow: /*?rest_route=
```

Due forme della stessa cosa: con permalink attivi è `/wp-json/`, senza
permalink è `?rest_route=`. La bozza copriva solo la prima.

> Nota: bloccare la REST API è sicuro nella grande maggioranza dei casi, ma
> se il tema costruisce parti della pagina leggendo `/wp-json/` lato client,
> il blocco si vede nel test "Visualizza pagina sottoposta a scansione" di
> Search Console. Va controllato lì dopo la pubblicazione.

### wp-includes

```
Disallow: /wp-includes/
Allow: /wp-includes/js/
Allow: /wp-includes/css/
Allow: /wp-includes/blocks/
```

I tre `Allow` sono **più lunghi** del `Disallow` e quindi prevalgono.
Servono perché: jQuery sta in `/wp-includes/js/`, e gli stili dei blocchi
Gutenberg stanno in `/wp-includes/blocks/` e `/wp-includes/css/`. La bozza
aveva solo `Allow: /wp-includes/js/`, lasciando bloccati gli stili dei
blocchi.

### Feed, trackback, commenti

```
Disallow: /feed/
Disallow: /*/feed/
Disallow: /comments/feed/
Disallow: /*/trackback/
Disallow: /trackback/
Disallow: /*?replytocom=
```

Servono **entrambe** le forme. `Disallow: /feed/` da sola copre solo il feed
alla radice: restano scansionabili `/categoria-prodotto/x/feed/` e
`/prodotto/y/feed/`, che su un catalogo ampio sono tanti quanti i prodotti e
le categorie. `replytocom` genera una URL per ogni commento.

### Archivi autore

```
Disallow: /author/
Disallow: /autore/
```

Su un e-commerce non hanno valore SEO e duplicano gli elenchi di articoli.
**Da verificare quale dei due slug esista davvero**; quello inesistente
resta inerte ma innocuo.

### Ricerca interna

```
Disallow: /*?s=
Disallow: /*&s=
Disallow: /search/
Disallow: /ricerca/
```

La ricerca interna genera URL potenzialmente infinite, tutte con contenuto
derivato. `/*?s=` copre la ricerca da qualunque percorso, non solo dalla
home come nella bozza. `/*&s=` copre il caso
`?post_type=product&s=lampada`, che è la forma della ricerca prodotti di
WooCommerce ed è proprio quella che la bozza lasciava passare.

### Carrello, checkout, account

```
Disallow: /carrello/    /cart/    /checkout/    /pagamento/
Disallow: /il-mio-account/    /mio-account/    /account/    /my-account/
Disallow: /lista-dei-desideri/    /wishlist/    /confronta/    /compare/
```

Pagine funzionali, spesso con contenuto per-sessione. Sono elencate sia in
italiano sia in inglese perché **non è verificato** quali slug siano attivi:
le righe inutili sono inerti e innocue. Wishlist e confronta (YITH) sono
aggiunte rispetto alla bozza: generano URL per-utente.

### Azioni WooCommerce sul carrello

```
Disallow: /*add-to-cart=
Disallow: /*removed_item=
Disallow: /*remove_item=
Disallow: /*undo_item=
Disallow: /*?wc-ajax=
Disallow: /*?wc-api=
```

Questo è il blocco che nella bozza non funzionava affatto (4 righe su 4
inerti). La forma `/*add-to-cart=` intercetta il parametro in qualunque
posizione.

Da sapere: **i link normali ai prodotti non sono toccati.** `add-to-cart` è
un parametro aggiuntivo; il link al prodotto è `/prodotto/slug/` e non
combacia con nessuna di queste regole. Verificato sul campione: 0 URL utili
bloccate.

`wc-ajax` è il canale AJAX di WooCommerce (per esempio
`?wc-ajax=get_refreshed_fragments`): non produce pagine, solo frammenti.

### Ordinamento e densità di risultati

```
Disallow: /*?orderby=
Disallow: /*&orderby=
Disallow: /*products-per-page=
Disallow: /*?per_page=
Disallow: /*&per_page=
```

Ogni ordinamento genera una variante della stessa categoria con gli stessi
prodotti in ordine diverso: duplicato per definizione. Il canonical dovrebbe
già puntare alla versione pulita; il blocco serve a non spendere scansioni
per arrivare a quella conclusione.

### Filtri (WooCommerce layered nav + YITH)

```
Disallow: /*filter_
Disallow: /*query_type_
Disallow: /*?filtering=
Disallow: /*&filtering=
Disallow: /*yith_wcan
Disallow: /*min_price=
Disallow: /*max_price=
Disallow: /*rating_filter=
Disallow: /*?product_visibility=
Disallow: /*?on_sale=
Disallow: /*?instock=
Disallow: /*?stock_status=
```

È il blocco con il maggior potenziale di spreco: le combinazioni di filtro
crescono in modo combinatorio. Con 4 attributi da 5 valori ciascuno le
combinazioni sono già oltre 1.200 per categoria, ognuna con la propria
paginazione e i propri ordinamenti.

`query_type_` è il parametro che YITH/WooCommerce aggiunge per la logica
AND/OR fra i valori di un attributo: moltiplica ogni combinazione.

**Se in futuro alcune combinazioni diventano landing SEO intenzionali**, si
sbloccano singolarmente con un `Allow` più lungo del `Disallow`:

```
Allow: /categoria-prodotto/lampadine/?filter_colore=bianco
```

**Da verificare** con `analizza_log.py --scopri`: i nomi dei parametri qui
sopra sono quelli tipici, ma contano quelli reali. Se compaiono parametri
non presenti in questa lista, vanno aggiunti.

### Parametri di tracciamento

```
Disallow: /*?utm_    /*&utm_
Disallow: /*?gclid=    /*?fbclid=    /*?msclkid=    /*?srsltid=
```

Creano duplicati esatti delle pagine utili. `srsltid` è aggiunto da Google
Shopping e su molti store WooCommerce è una fonte di duplicati consistente.

> Questi sono il caso in cui il blocco va valutato: il canonical li gestisce
> già sul piano dell'indice, e se una campagna porta link con `utm_`, il
> blocco impedisce a Google di leggere quella pagina. Sono inclusi perché
> sul piano del crawl budget il guadagno è netto, ma è la prima regola da
> rimuovere se si vuole essere prudenti.

### Anteprime

```
Disallow: /*?preview=    /*?preview_id=
Disallow: /*?customize_changeset_uuid=    /*?elementor-preview=
```

Contenuti non pubblicati, a volte linkati per errore.

### Risorse di rendering

```
Allow: /wp-content/uploads/    /wp-content/cache/
Allow: /wp-content/plugins/    /wp-content/themes/
Allow: /*.js$  /*.css$  /*.png$  /*.jpg$  ...
```

Non c'è **nessun** `Disallow` su `/wp-content/plugins/` o
`/wp-content/themes/`. Gli `Allow` sono lì per rendere l'intenzione
esplicita e per proteggere da future aggiunte incaute.

I pattern sono corretti nella forma `/*.js$`. Nota che `$` àncora alla fine
della URL: un file richiesto come `style.css?ver=6.4` non combacia con
`/*.css$` — ma non serve che combaci, perché non c'è alcun `Disallow` da cui
salvarlo.

### Cosa NON è bloccato, deliberatamente

| Tipo | Motivo |
|---|---|
| prodotti | obiettivo primario: scansione libera |
| categorie e sottocategorie | percorso di scoperta dei prodotti |
| marchi | valore SEO proprio |
| pagine e articoli | contenuto utile |
| **paginazione** (`/page/2/`, `?paged=`) | **è il modo in cui Google scopre i prodotti oltre la prima pagina di categoria: bloccarla è l'errore più costoso possibile rispetto all'obiettivo** |
| CSS, JS, immagini di tema e plugin | necessari al rendering |

---

## Tre cose che il robots.txt non può fare

Vanno tenute distinte, altrimenti si usa lo strumento sbagliato.

**1. Il robots.txt non deindicizza.** Al contrario: se una URL è già
indicizzata e la si blocca, Google non può più leggerne il `noindex` e la
URL può restare in indice come *"Indicizzata, ma bloccata da robots.txt"*.

Ordine corretto per togliere dall'indice URL già indicizzate:

1. `noindex` sulla URL, **lasciandola scansionabile**
2. attendere che Google la rilevi e la escluda
3. **solo dopo** bloccarla in robots.txt per risparmiare scansioni

Per URL **non ancora indicizzate** il blocco immediato va benissimo ed è
l'obiettivo di questo file.

**2. Il robots.txt non aumenta l'indicizzazione dei prodotti.** Libera
capacità di scansione, che è utile solo se la scansione era il collo di
bottiglia. Se i prodotti risultano *"Scansionata, attualmente non
indicizzata"*, Google li ha già letti e ha deciso di non indicizzarli: la
causa è contenuto scarso o duplicato, non il crawl budget. In quel caso
nessuna modifica al robots.txt cambia il risultato.

I casi in cui il robots.txt aiuta davvero i prodotti sono: *"Rilevata,
attualmente non indicizzata"* in quantità elevata (Google conosce le URL ma
non arriva a scansionarle) e crawl budget verificabilmente assorbito da URL
tecniche.

**3. Il robots.txt e la sitemap non devono contradirsi.** Una URL in sitemap
e insieme bloccata è un segnale incoerente. Verificabile con
`audit_sitemap.py --robots`.

---

## Verifiche obbligatorie prima di pubblicare

```bash
cd seo/analisi

# 1. nessuna regola inerte
python3 robots_matcher.py ../robots/robots_proposto.txt

# 2. gli slug in config.json corrispondono al sito reale
python3 analizza_log.py '/var/log/nginx/access.log*' --scopri

# 3. confronto con l'attuale su URL reali.
#    Esce con codice 2 se qualche URL utile risulterebbe bloccata.
python3 analizza_log.py '/var/log/nginx/access.log*' --esporta-url url.txt
python3 robots_check.py --robots ../../robots_attuale.txt \
                        --confronta ../robots/robots_proposto.txt \
                        --urls url.txt

# 4. nessuna URL di sitemap bloccata dalla proposta
python3 audit_sitemap.py https://www.tuttoluce.com/sitemap_index.xml \
                         --robots ../robots/robots_proposto.txt

# 5. filtri YITH: query string o pretty URL? (raccolta_dati.md, punto 6)
```

Dopo la pubblicazione, in Search Console:

- **Impostazioni → robots.txt**: verificare che Google legga la versione nuova
- **Controllo URL** su 3 prodotti, 2 categorie e 1 marchio: devono risultare
  scansionabili
- **Controllo URL → Visualizza pagina sottoposta a scansione** su una pagina
  categoria: verificare che non compaiano risorse bloccate
- **Statistiche di scansione** dopo 2–3 settimane: la quota di richieste verso
  URL con parametri deve scendere, quella verso prodotti salire
