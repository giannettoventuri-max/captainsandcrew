#!/usr/bin/env bash
# Esegue l'intero toolkit sulle fixture sintetiche in dati/.
# Serve a verificare che gli strumenti funzionino, non a trarre conclusioni
# sul sito reale: i dati in dati/ sono inventati.
set -uo pipefail

cd "$(dirname "$0")"
RADICE="$(pwd)"
cd analisi

fallimenti=0
sezione() { printf '\n\033[1m=== %s ===\033[0m\n' "$1"; }
verifica() {
  if [ "$1" -eq 0 ]; then printf '  OK\n'; else printf '  FALLITO (exit %s)\n' "$1"; fallimenti=$((fallimenti+1)); fi
}

sezione "1. test del motore di matching"
python3 test_matcher.py >/dev/null 2>&1; verifica $?

sezione "2. regole inerti nella bozza (atteso: 24)"
trovate=$(python3 robots_matcher.py "$RADICE/dati/robots_bozza_utente.txt" | grep -c INERTE)
echo "  rilevate: $trovate"
[ "$trovate" -eq 24 ]; verifica $?

sezione "3. regole inerti nella proposta (atteso: 0)"
trovate=$(python3 robots_matcher.py "$RADICE/robots/robots_proposto.txt" | grep -c INERTE)
echo "  rilevate: $trovate"
[ "$trovate" -eq 0 ]; verifica $?

sezione "4. analisi dei log: modalita' scoperta"
python3 analizza_log.py "$RADICE/dati/finto_access.log" --scopri >/dev/null 2>&1; verifica $?

sezione "5. analisi dei log: confronto prima/dopo"
python3 analizza_log.py "$RADICE/dati/finto_access.log" --taglio 2026-07-15 \
  --robots "$RADICE/dati/robots_bozza_utente.txt" >/dev/null 2>&1; verifica $?

sezione "6. esportazione delle URL dai log"
python3 analizza_log.py "$RADICE/dati/finto_access.log" \
  --esporta-url /tmp/autotest_url.txt >/dev/null 2>&1
righe=$(wc -l < /tmp/autotest_url.txt)
echo "  URL esportate: $righe"
[ "$righe" -gt 100 ]; verifica $?

sezione "7. la proposta non blocca URL utili (atteso exit 0)"
python3 robots_check.py --robots "$RADICE/robots/robots_proposto.txt" \
  --urls /tmp/autotest_url.txt >/dev/null 2>&1; verifica $?

sezione "8. confronto bozza -> proposta"
python3 robots_check.py --robots "$RADICE/dati/robots_bozza_utente.txt" \
  --confronta "$RADICE/robots/robots_proposto.txt" \
  --urls /tmp/autotest_url.txt >/dev/null 2>&1; verifica $?

sezione "9. report degli export GSC"
python3 gsc_report.py --file "$RADICE/dati/gsc_settembre.csv" \
  --confronta-con "$RADICE/dati/gsc_giugno.csv" >/dev/null 2>&1; verifica $?

sezione "10. audit_sitemap risponde a --help (richiede rete per l'uso reale)"
python3 audit_sitemap.py --help >/dev/null 2>&1; verifica $?

rm -f /tmp/autotest_url.txt
printf '\n'
if [ "$fallimenti" -eq 0 ]; then
  printf '\033[1mtutti i controlli superati.\033[0m\n'
else
  printf '\033[1m%s controlli FALLITI.\033[0m\n' "$fallimenti"
fi
exit "$fallimenti"
