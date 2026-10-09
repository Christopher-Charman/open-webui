#!/usr/bin/env bash
set -euo pipefail
umask 077

ACCOUNT="${PPC_ACCOUNT:-${HOME}}"
WEBAPP="$ACCOUNT/webapp"
CONTROL="$WEBAPP/bin/powerpc-control"
TAILSCALE_SERVICE="$WEBAPP/bin/tailscale-service"
STATE="$ACCOUNT/.powerpc-control-v1"
SOURCE_PIN="d1ca2801e72e39b502095209683e06fa177067b8"
CONTROL_URL="https://raw.githubusercontent.com/Christopher-Charman/open-webui/$SOURCE_PIN/bootstrap-relay/permanent-control/powerpc-control-service"
TAILSCALE_URL="https://raw.githubusercontent.com/Christopher-Charman/open-webui/$SOURCE_PIN/bootstrap-relay/gateway-tailscale/tailscale-service"

[ "$(id -u)" = "2257347" ]
[ -d "$WEBAPP/bin" ]
[ -d "$STATE" ]
cron_text="$(crontab -l 2>/dev/null || true)"
printf '%s\n' "$cron_text" | grep -q '# POWERPC_CONTROL_V1'

tmp_control="$STATE/powerpc-control.install.$$"
tmp_tailscale="$STATE/tailscale-service.install.$$"
cleanup() { rm -f "$tmp_control" "$tmp_tailscale"; }
trap cleanup EXIT

curl -fsSL --retry 4 --connect-timeout 10 "$CONTROL_URL" -o "$tmp_control"
curl -fsSL --retry 4 --connect-timeout 10 "$TAILSCALE_URL" -o "$tmp_tailscale"
sh -n "$tmp_control"
bash -n "$tmp_tailscale"
chmod 700 "$tmp_control" "$tmp_tailscale"

old_hash="$(sha256sum "$CONTROL" | awk '{print $1}')"
new_hash="$(sha256sum "$tmp_control" | awk '{print $1}')"
tailscale_hash="$(sha256sum "$tmp_tailscale" | awk '{print $1}')"
echo "CONTROL_OLD_SHA256=$old_hash"
echo "CONTROL_NEW_SHA256=$new_hash"
echo "TAILSCALE_SERVICE_SHA256=$tailscale_hash"

if [ ! -e "$STATE/powerpc-control.pre-tailscale-supervision" ]; then
  cp -p "$CONTROL" "$STATE/powerpc-control.pre-tailscale-supervision"
  chmod 700 "$STATE/powerpc-control.pre-tailscale-supervision"
fi

mv -f "$tmp_tailscale" "$TAILSCALE_SERVICE"
mv -f "$tmp_control" "$CONTROL"
trap - EXIT

"$CONTROL" ensure
"$CONTROL" status

echo "TAILSCALE_SUPERVISION_DEPLOY=PASS"
echo "WATCHDOG_CRON=EXISTING_UNCHANGED"
echo "SOURCE_PIN=$SOURCE_PIN"
echo "MUTATION=CONTROL_WATCHDOG_HOOK_PLUS_TAILSCALE_SERVICE"
