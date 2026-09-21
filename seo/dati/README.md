# Fixture sintetiche

Dati **inventati**, generati per verificare il funzionamento degli strumenti
senza accesso al sito reale. Non contengono informazioni su Tuttoluce e non
vanno usati per trarre conclusioni.

| File | Contenuto |
|---|---|
| `finto_access.log` | Log Googlebot sintetico in formato `combined`, su due periodi (giugno e agosto 2026) con profili di crawling diversi. Serve a verificare `analizza_log.py`, incluso il confronto prima/dopo. Contiene anche traffico umano, che gli strumenti devono escludere. |
| `gsc_giugno.csv`, `gsc_settembre.csv` | Export di Search Console finti, con un aumento composto in prevalenza da prodotti. Servono a verificare `gsc_report.py`. |
| `robots_bozza_utente.txt` | La bozza di robots.txt contenuta nella richiesta, salvata per poterla analizzare. Questo file **non** è sintetico: è l'oggetto dell'analisi in `../RELAZIONE.md` (Q5). |

Per rigenerare i primi due file basta rileggere i comandi in
`../../RELAZIONE.md`; per l'uso quotidiano servono i dati reali raccolti con
`../raccolta_dati.md`.

```bash
../autotest.sh     # esegue il toolkit su queste fixture
```
