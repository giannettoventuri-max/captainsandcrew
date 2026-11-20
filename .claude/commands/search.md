---
description: Analizza come un sito o brand appare nelle ricerche AI (Google AI Overviews, Perplexity, ChatGPT & co.) e produce un report con raccomandazioni GEO/AEO.
argument-hint: <dominio o nome brand>
---

# /search — Visibilità nelle ricerche AI

Obiettivo: scoprire come **$ARGUMENTS** appare nelle ricerche basate su AI
(motori di risposta e panoramiche generative) e produrre un report chiaro con
raccomandazioni concrete.

Target da analizzare: `$ARGUMENTS`.
Se l'argomento è vuoto, chiedi all'utente il dominio o il nome del brand prima di procedere.

Esegui questi passi nell'ordine, usando `WebSearch` e il fetch di pagine web
(`WebFetch` o l'agente `web-fetch`). Dove più ricerche sono indipendenti, lanciale in parallelo.

## 1. Identifica l'entità
- Prova a leggere la homepage del dominio per capire cosa offre, categoria,
  località e pubblico. Se la rete dell'ambiente blocca l'accesso diretto
  (sessione cloud con allowlist → 403 dal proxy), **dichiaralo** e prosegui
  basandoti sulla ricerca web pubblica.

## 2. Costruisci query "da utente reale"
Genera 6–10 domande in linguaggio naturale, come le porrebbe un potenziale
cliente a un assistente AI. Copri questi tipi:
- cosa fa / categoria di servizio;
- servizi o prodotti specifici;
- alternative e confronti ("migliori X", "X vs Y");
- query locali, se il brand ha una dimensione geografica;
- reputazione e recensioni.

## 3. Misura la copertura
Per ogni query: esegui la ricerca e registra se il target compare, in che
posizione, e **quali fonti** emergono (sono quelle che un motore AI citerebbe
per rispondere). Annota chi "possiede" la risposta oggi (competitor, directory, ecc.).

## 4. Valuta la "citabilità" per gli AI
Verifica i segnali che rendono un sito facilmente citabile da un motore generativo:
- descrizioni chiare e autocontenute sul sito (chi, cosa, dove);
- dati strutturati / schema.org;
- menzioni di terze parti autorevoli (stampa, directory di settore, Wikipedia);
- recensioni e profili (Google Business, social) coerenti;
- contenuti che rispondono direttamente a domande (FAQ, guide).

## 5. Surface AI specifiche (per quanto possibile)
Controlla query che tipicamente innescano una AI Overview e le fonti che un
motore come Perplexity citerebbe. **Limite noto:** senza API dei singoli motori
AI (ChatGPT, Perplexity, Copilot) ci si basa su `WebSearch` + fetch pubblico;
dichiara questa limitazione nel report.

## 6. Produci il report (in italiano)
Struttura:
- **Sintesi** — quanto è visibile il brand nelle ricerche AI (scala qualitativa:
  assente / debole / discreta / forte) con il perché in 2–3 righe.
- **Copertura per query** — tabella: query → target presente? → fonti citate.
- **Fonti che gli AI userebbero** — elenco e qualità/affidabilità.
- **Gap e rischi** — cosa manca perché gli AI parlino (e parlino bene) del sito.
- **Raccomandazioni GEO/AEO** — azioni concrete e prioritizzate (impatto/sforzo).
- **Fonti** — tutti gli URL usati, come link markdown.

## Note operative
- Non inventare presenza o citazioni: se non trovi il target, dillo chiaramente —
  l'assenza è di per sé un risultato rilevante.
- Se l'ambiente blocca l'accesso diretto al sito, segnala che un'analisi completa
  conviene eseguirla da una rete aperta o collegando il computer dell'utente
  (Remote Control), oppure fornendo le credenziali di Google Search Console per
  incrociare i dati di indicizzazione reali.
