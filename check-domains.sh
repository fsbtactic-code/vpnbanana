#!/bin/bash
# ============================================
# REALITY Domain Scanner
# Run on your VPS to find best SNI domains
# Usage: bash check-domains.sh
# ============================================

DOMAINS=(
  gosuslugi.ru nalog.ru cbr.ru mos.ru sberbank.ru tinkoff.ru vtb.ru
  alfabank.ru gazprombank.ru raiffeisen.ru rshb.ru otkritie.ru
  rosbank.ru mtsbank.ru pochtabank.ru sovcombank.ru mkb.ru
  gazprom.ru lukoil.ru rosneft.ru rosatom.ru rostelecom.ru
  rzd.ru aeroflot.ru s7.ru nornickel.ru sibur.ru tatneft.ru
  mts.ru megafon.ru beeline.ru tele2.ru yota.ru rt.ru
  rbc.ru kommersant.ru vedomosti.ru ria.ru tass.ru interfax.ru
  iz.ru rg.ru 1tv.ru ntv.ru ren.tv sportbox.ru
  yandex.ru mail.ru vk.com ok.ru rambler.ru lenta.ru
  habr.com vc.ru pikabu.ru 2gis.ru avito.ru hh.ru
  ozon.ru wildberries.ru lamoda.ru mvideo.ru eldorado.ru
  dns-shop.ru citilink.ru kaspersky.ru drweb.ru
  msu.ru hse.ru mipt.ru skoltech.ru stepik.org
  invitro.ru gemotest.ru helix.ru medsi.ru
  consultant.ru garant.ru kinopoisk.ru ivi.ru okko.tv
  qiwi.ru yoomoney.ru sbermegamarket.ru
  kremlin.ru government.ru mvd.ru minzdrav.gov.ru
  pfr.gov.ru rosreestr.gov.ru zakupki.gov.ru
)

PERFECT=(); GOOD=(); OK_LIST=()
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'

echo "=============================="
echo "  REALITY Domain Scanner"
echo "  Server: $(curl -4 -s ifconfig.me)"
echo "=============================="
echo ""

for domain in "${DOMAINS[@]}"; do
  result=$(curl -so /dev/null --max-time 5 --connect-timeout 4 --tlsv1.3 \
    -w "%{http_version}|%{time_total}" "https://${domain}/" 2>/dev/null)

  if [ $? -eq 0 ] && [ -n "$result" ]; then
    http_ver=$(echo "$result" | cut -d'|' -f1)
    time_ms=$(echo "$result" | cut -d'|' -f2 | awk '{printf "%d", $1*1000}')
    if [ "$http_ver" = "2" ]; then
      echo -e "${GREEN}[PERFECT]${NC} TLS1.3 | H2:YES | ${time_ms}ms | $domain"
      PERFECT+=("$domain|$time_ms")
    else
      echo -e "${YELLOW}[GOOD   ]${NC} TLS1.3 | H2:NO  | ${time_ms}ms | $domain"
      GOOD+=("$domain|$time_ms")
    fi
  else
    result2=$(curl -so /dev/null --max-time 5 --connect-timeout 4 \
      -w "%{http_version}|%{time_total}" "https://${domain}/" 2>/dev/null)
    if [ $? -eq 0 ] && [ -n "$result2" ]; then
      time_ms2=$(echo "$result2" | cut -d'|' -f2 | awk '{printf "%d", $1*1000}')
      echo -e "${CYAN}[OK     ]${NC} TLS1.2 | H2:?   | ${time_ms2}ms | $domain"
      OK_LIST+=("$domain|$time_ms2")
    fi
  fi
done

echo ""
echo "=============================="
echo "  TOP RESULTS"
echo "=============================="

echo -e "\n${GREEN}=== PERFECT (TLS1.3 + H2) ===${NC}"
for d in "${PERFECT[@]}"; do
  echo "  $(echo $d | cut -d'|' -f1)  [$(echo $d | cut -d'|' -f2)ms]"
done

echo -e "\n${YELLOW}=== GOOD (TLS1.3 only) ===${NC}"
for d in "${GOOD[@]}"; do
  echo "  $(echo $d | cut -d'|' -f1)  [$(echo $d | cut -d'|' -f2)ms]"
done

echo -e "\n=== TOP-5 FOR REALITY CONFIG ==="
ALL=("${PERFECT[@]}" "${GOOD[@]}")
count=0
for d in "${ALL[@]}"; do
  [ $count -ge 5 ] && break
  domain=$(echo $d | cut -d'|' -f1)
  ms=$(echo $d | cut -d'|' -f2)
  echo -e "  ${GREEN}dest: ${domain}:443   [${ms}ms]${NC}"
  count=$((count+1))
done
