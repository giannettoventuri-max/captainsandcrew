# Raccolta dati — comandi da eseguire

Questa sessione di lavoro **non ha accesso** né al server né a Search Console
né al sito (vedi `RELAZIONE.md`, sezione "Limiti di accesso"). I comandi qui
sotto raccolgono i dati necessari. Sono tutti in **sola lettura**: nessuno
modifica il sito o la produzione.

---

## 1. robots.txt attuale

```bash
curl -s https://www.tuttoluce.com/robots.txt | tee robots_attuale.txt
```

Verificare anche **come viene servito**, perché è un errore frequente: se
esiste un file fisico, il robots.txt virtuale di WordPress/Yoast/Rank Math
viene ignorato e le modifiche fatte dal pannello non hanno effetto.

```bash
ls -la /var/www/.../public_html/robots.txt 2>/dev/null \
  && echo "FILE FISICO PRESENTE: vince sul robots.txt virtuale di WordPress" \
  || echo "nessun file fisico: lo genera WordPress o un plugin SEO"
```

## 2. Log di Googlebot

Individuare i log e capire quanto storico è disponibile:

```bash
ls -la /var/log/nginx/ /var/log/apache2/ 2>/dev/null
ls -la ~/logs/ /home/*/logs/ 2>/dev/null          # hosting condivisi
zcat -f /var/log/nginx/access.log* | head -3       # controllo del formato
```

Serve il formato `combined` (con user-agent). Se lo user-agent non c'è, i log
non sono utilizzabili per questa analisi e va cambiato `log_format`.

Quanto storico c'è (determina se il confronto prima/dopo è possibile):

```bash
zcat -f /var/log/nginx/access.log* | awk -F'[][]' '{print $2}' \
  | cut -d: -f1 | sort -u | head -1
zcat -f /var/log/nginx/access.log* | awk -F'[][]' '{print $2}' \
  | cut -d: -f1 | sort -u | tail -1
```

### Verifica rapida senza il toolkit

Quota di richieste Googlebot verso URL con parametri:

```bash
zcat -f /var/log/nginx/access.log* | grep -i googlebot | wc -l
zcat -f /var/log/nginx/access.log* | grep -i googlebot | grep -c 'add-to-cart='
zcat -f /var/log/nginx/access.log* | grep -i googlebot | grep -c 'filter_'
zcat -f /var/log/nginx/access.log* | grep -i googlebot | grep -c 'orderby='
```

I parametri realmente presenti, ordinati per frequenza — **questa è la lista
che il robots.txt deve coprire**, non quella che diamo per scontata:

```bash
zcat -f /var/log/nginx/access.log* | grep -i googlebot \
  | grep -oP '"GET \S+\?\K[^" ]+' | tr '&' '\n' \
  | cut -d= -f1 | sort | uniq -c | sort -rn | head -40
```

### Analisi completa col toolkit

```bash
# copiare la cartella seo/analisi/ sul server, poi:
cd seo/analisi

# 1. struttura reale delle URL -> compilare config.json
python3 analizza_log.py '/var/log/nginx/access.log*' --scopri

# 2. report completo
python3 analizza_log.py '/var/log/nginx/access.log*' --report --top 40

# 3. confronto prima/dopo (mettere la data della modifica al robots.txt)
python3 analizza_log.py '/var/log/nginx/access.log*' --taglio 2026-07-15

# 4. quanto spreco il robots.txt attuale NON sta bloccando
python3 analizza_log.py '/var/log/nginx/access.log*' --robots ../../robots_attuale.txt

# 5. esportare le URL per la verifica del robots.txt
python3 analizza_log.py '/var/log/nginx/access.log*' --esporta-url url_da_log.txt
```

### Googlebot falso

Una parte del traffico che si dichiara Googlebot non lo è. Per i conteggi di
crawl budget conta solo quello vero. Verifica di un IP:

```bash
host 66.249.66.1     # atteso: *.googlebot.com o *.google.com
```

## 3. Search Console

Search Console non ha API di export per il rapporto di indicizzazione: va
fatto a mano. Proprietà `www.tuttoluce.com`:

**Indicizzazione → Pagine**, esportare in CSV:

- `Indicizzate`
- `Scansionata, attualmente non indicizzata`
- `Rilevata, attualmente non indicizzata`
- `Pagina duplicata: Google ha scelto una pagina canonica diversa`
- `Pagina alternativa con tag canonico corretto`
- `Bloccata da robots.txt`
- `Pagina con reindirizzamento`

Annotare anche i **numeri del grafico** a 3 e 6 mesi (indicizzate / non
indicizzate): il grafico contiene lo storico, l'export no.

**Impostazioni → Statistiche di scansione**, annotare:

- richieste totali di scansione (andamento 3 mesi)
- suddivisione per **scopo** (rilevamento / aggiornamento)
- suddivisione per **tipo di file**
- suddivisione per **risposta** (200, 301, 302, 404, 5xx)
- tempo medio di risposta

> Le Statistiche di scansione coprono solo 90 giorni. Se la modifica al
> robots.txt è più vecchia, il confronto prima/dopo va fatto sui log del
> server, che è il motivo per cui il punto 2 conta più di questo.

Poi:

```bash
python3 gsc_report.py --file indicizzate_settembre.csv \
                      --confronta-con indicizzate_giugno.csv \
                      --robots robots_attuale.txt
```

Se non esiste un export di giugno, il confronto storico **non è
ricostruibile a posteriori**: si parte da oggi come riferimento e si usano i
log del server per il prima/dopo.

## 4. Sitemap

```bash
cd seo/analisi
python3 audit_sitemap.py https://www.tuttoluce.com/sitemap_index.xml \
    --robots ../../robots_attuale.txt \
    --campione-canonical 80 --pausa 0.5 \
    --esporta-url url_sitemap.txt
```

## 5. Conteggi prodotti (Q "PRODOTTI")

Confronto fra prodotti pubblicati, prodotti in sitemap e prodotti
indicizzati. Con WP-CLI:

```bash
wp post list --post_type=product --post_status=publish --format=count
wp post list --post_type=product --post_status=private --format=count

# prodotti esclusi dalla sitemap da Yoast (noindex a livello di singolo post)
wp db query "SELECT COUNT(*) FROM wp_postmeta m
  JOIN wp_posts p ON p.ID = m.post_id
  WHERE p.post_type='product' AND p.post_status='publish'
    AND m.meta_key='_yoast_wpseo_meta-robots-noindex' AND m.meta_value='1';"

# prodotti senza immagine o senza descrizione: candidati tipici a
# "scansionata, attualmente non indicizzata"
wp db query "SELECT COUNT(*) FROM wp_posts p
  WHERE p.post_type='product' AND p.post_status='publish'
    AND (p.post_content='' OR p.post_excerpt='');"
```

Se Rank Math sostituisce Yoast, la meta key è `rank_math_robots`.

Poi il triangolo pubblicati / in sitemap / indicizzati:

```bash
wc -l url_sitemap.txt                      # in sitemap
grep -c '/prodotto/' url_sitemap.txt       # prodotti in sitemap
grep -c '/prodotto/' indicizzate.csv       # prodotti indicizzati
```

Uno scarto grande fra **pubblicati** e **in sitemap** è un problema di
configurazione del plugin SEO. Uno scarto grande fra **in sitemap** e
**indicizzati** non si risolve col robots.txt: è qualità/duplicazione del
contenuto o profondità di link interni.

## 6. Filtri YITH: verifica decisiva

Determinare se YITH WooCommerce Ajax Navigation genera **query string** o
**URL con percorso** ("SEO friendly / pretty URLs"). È il punto che cambia
tutto: se i filtri sono percorsi, **nessuna** regola sui parametri li
intercetta.

Dal pannello: *YITH → Ajax Product Filter → Impostazioni*, cercare l'opzione
sulle URL SEO-friendly.

Dai log, cercare percorsi di filtro invece di parametri:

```bash
zcat -f /var/log/nginx/access.log* | grep -i googlebot \
  | grep -oP '"GET \K[^ ?"]+' \
  | grep -E '/(filter|filtro|filtra)[-_/]' | sort | uniq -c | sort -rn | head -30
```

Se questo comando restituisce risultati, le pretty URL sono attive e va
aggiunta al robots.txt una regola sul percorso, del tipo:

```
Disallow: /*/filtro-
```

il cui prefisso esatto va letto dall'output del comando, non indovinato.

## 7. Cosa rimandare indietro

Per completare la relazione con i dati reali bastano:

1. `robots_attuale.txt`
2. l'output di `analizza_log.py --scopri`
3. l'output di `analizza_log.py --taglio <data> --robots robots_attuale.txt`
4. l'output di `audit_sitemap.py`
5. i CSV di Search Console (o i conteggi del grafico)
6. i conteggi prodotti del punto 5
7. l'esito del punto 6 sui filtri YITH
