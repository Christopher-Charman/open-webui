#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

BASE="/home/storage/781/4477781/user/webapp"
PKG="$BASE/envs/openwebui/lib/python3.11/site-packages/open_webui"
FRONTEND="$PKG/frontend"
FSTATIC="$FRONTEND/static"
SSTATIC="$PKG/static"
INDEX="$FRONTEND/index.html"
POST="$FSTATIC/continuity-orb-beam-postmount.js"
SPOST="$SSTATIC/continuity-orb-beam-postmount.js"
RESTART="$BASE/restart-openwebui-via-passenger.sh"
VERSION="20261001.1"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP="$BASE/runtime-domains/pwa-repair-agent/backups/pre-theme-stable-binder-$STAMP"
CSS="$FSTATIC/continuity-theme-stable-binder.css"
JS="$FSTATIC/continuity-theme-stable-binder.js"
SCSS="$SSTATIC/continuity-theme-stable-binder.css"
SJS="$SSTATIC/continuity-theme-stable-binder.js"

fail(){ echo "THEME_STABLE_BINDER_V1=FAIL $*"; exit 2; }

[ -f "$INDEX" ] || fail index_missing
[ -f "$POST" ] || fail postmount_missing
[ -x "$RESTART" ] || fail restart_script_missing
[ "$(wc -c < "$FSTATIC/loader.js" | tr -d ' ')" = "0" ] || fail stock_loader_not_empty
[ "$(wc -c < "$FSTATIC/custom.css" | tr -d ' ')" = "0" ] || fail stock_custom_css_not_empty
grep -Fq 'owui-postmount-ui-voice-v20260929.1' "$INDEX" || fail ui_voice_marker_missing
grep -Fq 'owui-postmount-orb-beam-v20260930.1' "$INDEX" || fail orb_marker_missing
grep -Fq "1.3.4-nowarm" "$FSTATIC/pwa-voice-bridge.js" || fail voice_boundary_missing
grep -Fq "ORB_VERSION = '1.4.5'" "$FSTATIC/owui-orb-v1.js" || fail orb_v145_missing
grep -Fq 'continuity-landing-hero-150-v20260930.1' "$FSTATIC/owui-orb-v1.css" || fail landing_hero_150_missing

OLD_CSS="await css('/static/continuity-neural-parity-v3.css?v=20260930.3');"
OLD_JS="await js('/static/continuity-neural-parity-v3.js?v=20260930.3');"
NEW_CSS="await css('/static/continuity-theme-stable-binder.css?v=$VERSION');"
NEW_JS="await js('/static/continuity-theme-stable-binder.js?v=$VERSION');"

grep -Fq "$OLD_CSS" "$POST" || { grep -Fq "$NEW_CSS" "$POST" || fail parity_v3_mount_anchor_missing; }
grep -Fq "$OLD_JS" "$POST" || { grep -Fq "$NEW_JS" "$POST" || fail parity_v3_js_anchor_missing; }

mkdir -p "$BACKUP/frontend/static" "$BACKUP/served/static"
cp -p "$INDEX" "$BACKUP/frontend/index.html"
cp -p "$POST" "$BACKUP/frontend/static/continuity-orb-beam-postmount.js"
[ ! -f "$SPOST" ] || cp -p "$SPOST" "$BACKUP/served/static/continuity-orb-beam-postmount.js"
for n in continuity-theme-stable-binder.css continuity-theme-stable-binder.js; do
  [ ! -f "$FSTATIC/$n" ] || cp -p "$FSTATIC/$n" "$BACKUP/frontend/static/$n"
  [ ! -f "$SSTATIC/$n" ] || cp -p "$SSTATIC/$n" "$BACKUP/served/static/$n"
done

rollback(){
  echo "=== AUTO ROLLBACK THEME STABLE BINDER V1 ==="
  cp -p "$BACKUP/frontend/index.html" "$INDEX" || true
  cp -p "$BACKUP/frontend/static/continuity-orb-beam-postmount.js" "$POST" || true
  if [ -f "$BACKUP/served/static/continuity-orb-beam-postmount.js" ]; then
    cp -p "$BACKUP/served/static/continuity-orb-beam-postmount.js" "$SPOST" || true
  else
    cp -p "$POST" "$SPOST" || true
  fi
  for n in continuity-theme-stable-binder.css continuity-theme-stable-binder.js; do
    if [ -f "$BACKUP/frontend/static/$n" ]; then cp -p "$BACKUP/frontend/static/$n" "$FSTATIC/$n"; else rm -f "$FSTATIC/$n"; fi
    if [ -f "$BACKUP/served/static/$n" ]; then cp -p "$BACKUP/served/static/$n" "$SSTATIC/$n"; else rm -f "$SSTATIC/$n"; fi
  done
  "$RESTART" >/dev/null 2>&1 || true
  echo "THEME_STABLE_BINDER_V1=ROLLBACK_AUTO_RESTORED"
}
trap 'rc=$?; if [ $rc -ne 0 ]; then rollback; fi; exit $rc' EXIT

cat > "$CSS" <<'CSS'
/* continuity-theme-stable-binder-v20261001.1
   Stable-selector presentation binder for the protected OpenWebUI 0.11.3 shell.
   No loader, audio, model, auth, settings-DOM, or routing ownership. */

#owui-thinking-orb-v1[data-surface="landing"]::before,
#owui-thinking-orb-v1[data-surface="landing"]::after {
  content: none !important;
  display: none !important;
}

#owui-thinking-orb-v1[data-surface="chat"].continuity-chat-standalone {
  width: 42px !important;
  min-width: 42px !important;
  max-width: 42px !important;
  height: 42px !important;
  min-height: 42px !important;
  max-height: 42px !important;
  padding: 0 !important;
  margin: 8px auto 12px !important;
  border: 0 !important;
  border-radius: 50% !important;
  background: transparent !important;
  box-shadow:
    0 0 12px rgba(62,183,255,.30),
    0 0 22px rgba(193,68,255,.20) !important;
  overflow: visible !important;
  display: grid !important;
  place-items: center !important;
}

#owui-thinking-orb-v1[data-surface="chat"].continuity-chat-standalone canvas {
  width: 42px !important;
  height: 42px !important;
  max-width: 42px !important;
  max-height: 42px !important;
  border-radius: 50% !important;
}

/* The neural-material overlay has its own beam. Keep only the accepted v1.4.5 Border Beam. */
.continuity-material-composer-beam {
  display: none !important;
}

#owui-border-beam-v1 {
  opacity: .92 !important;
  filter:
    drop-shadow(0 0 5px rgba(57,180,255,.34))
    drop-shadow(0 0 8px rgba(194,67,255,.25))
    drop-shadow(0 0 10px rgba(255,102,145,.14)) !important;
}

/* Auth stays native and Continuity-owned controls stay out of that surface. */
html.continuity-auth-native #continuity-control-host {
  display: none !important;
}

CSS

cat > "$JS" <<'JS'
(() => {
  'use strict';

  const VERSION = '20261001.1';
  if (window.__CONTINUITY_THEME_STABLE_BINDER__) return;
  const runtime = window.__CONTINUITY_THEME_STABLE_BINDER__ = {
    version: VERSION,
    state: 'booting',
    surface: 'none'
  };

  const LEGACY_PARITY_CLASSES = [
    'continuity-parity-hide',
    'continuity-parity-round-control',
    'continuity-parity-footer'
  ];

  function isAuthSurface() {
    return /^\/auth(?:\/|$)/.test(location.pathname);
  }

  function cleanupLegacyParityClasses() {
    document.querySelectorAll(
      '.continuity-parity-hide,.continuity-parity-round-control,.continuity-parity-footer'
    ).forEach((el) => el.classList.remove(...LEGACY_PARITY_CLASSES));
  }

  function syncAuthBoundary() {
    const auth = isAuthSurface();
    document.documentElement.classList.toggle('continuity-auth-native', auth);
    const controls = document.getElementById('continuity-control-host');
    if (controls) controls.style.display = auth ? 'none' : '';
    return auth;
  }

  function bindComposer() {
    const composer = document.getElementById('message-input-container');
    if (!composer) return;
    composer.classList.add('custom-shell-prompt', 'custom-shell-controls');
  }

  function restoreLandingOwnedDom(landing) {
    landing.classList.remove('continuity-chat-standalone', 'orb-slot');
    landing.querySelectorAll('.continuity-neural-hero,.continuity-neural-hero *').forEach((el) => {
      if (el.style.display === 'none') el.style.removeProperty('display');
    });
  }

  function bindLanding(landing, chatPane) {
    restoreLandingOwnedDom(landing);
    if (chatPane) chatPane.classList.add('custom-shell-landing');

    landing.querySelectorAll('.continuity-neural-svg').forEach((el) => {
      el.classList.add('hero-network', 'chat-landing-network');
    });
    landing.querySelectorAll('.continuity-neural-sphere-wrap').forEach((el) => {
      el.classList.add('hero-aura', 'chat-landing-aura');
    });
  }

  function collapseChatTelemetry(chatOrb) {
    chatOrb.classList.add('continuity-chat-standalone', 'orb-slot');

    chatOrb.querySelectorAll('.hero-network,.chat-landing-network').forEach((el) => {
      el.classList.remove('hero-network', 'chat-landing-network');
    });
    chatOrb.querySelectorAll('.hero-aura,.chat-landing-aura').forEach((el) => {
      el.classList.remove('hero-aura', 'chat-landing-aura');
    });

    const canvas = chatOrb.querySelector('canvas');
    if (!canvas) return;

    let keep = canvas;
    while (keep.parentElement && keep.parentElement !== chatOrb) keep = keep.parentElement;

    Array.from(chatOrb.children).forEach((child) => {
      if (child === keep || child.contains(canvas)) {
        child.style.display = '';
        child.querySelectorAll('*').forEach((el) => {
          if (el === canvas || el.contains(canvas)) {
            if (el !== canvas) el.style.display = '';
          } else {
            el.style.display = 'none';
          }
        });
      } else {
        child.style.display = 'none';
      }
    });
  }

  function apply() {
    cleanupLegacyParityClasses();

    const chatPane = document.getElementById('chat-pane');
    if (syncAuthBoundary()) {
      if (chatPane) chatPane.classList.remove('custom-shell-landing');
      runtime.state = 'auth-native';
      runtime.surface = 'auth';
      return;
    }

    bindComposer();

    const landing = document.querySelector('#owui-thinking-orb-v1[data-surface="landing"]');
    const chatOrb = document.querySelector('#owui-thinking-orb-v1[data-surface="chat"]');

    if (landing) {
      bindLanding(landing, chatPane);
      runtime.surface = 'landing';
    } else {
      if (chatPane) chatPane.classList.remove('custom-shell-landing');
      if (chatOrb) {
        collapseChatTelemetry(chatOrb);
        runtime.surface = 'chat';
      } else {
        runtime.surface = 'none';
      }
    }

    runtime.state = 'ready';
  }

  let raf = 0;
  function schedule() {
    if (raf) return;
    raf = requestAnimationFrame(() => {
      raf = 0;
      apply();
    });
  }

  const observer = new MutationObserver(schedule);
  observer.observe(document.documentElement, {
    childList: true,
    subtree: true,
    attributes: true,
    attributeFilter: ['data-surface']
  });

  window.addEventListener('popstate', schedule);
  window.addEventListener('continuity-postmount:ready', schedule);
  window.addEventListener('continuity-orb-beam:ready', schedule);
  schedule();
})();

JS

cp -p "$CSS" "$SCSS"
cp -p "$JS" "$SJS"

NODE="$BASE/.local/node22-glibc217/bin/node"
[ -x "$NODE" ] || NODE="$BASE/.local/node22-el7/bin/node"
[ -x "$NODE" ] || fail node_runtime_missing
"$NODE" --check "$JS" >/dev/null || fail binder_js_syntax

python3 - "$POST" "$VERSION" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1]); version=sys.argv[2]; s=p.read_text()
old=("    await css('/static/continuity-neural-parity-v3.css?v=20260930.3');\n"
     "    await js('/static/continuity-neural-parity-v3.js?v=20260930.3');")
new=(f"    await css('/static/continuity-theme-stable-binder.css?v={version}');\n"
     f"    await js('/static/continuity-theme-stable-binder.js?v={version}');")
if old in s:
    if s.count(old) != 1:
        raise SystemExit('THEME_STABLE_BINDER_V1=FAIL parity_v3_mount_not_unique')
    s=s.replace(old,new,1)
elif new not in s:
    raise SystemExit('THEME_STABLE_BINDER_V1=FAIL postmount_replacement_anchor_missing')
p.write_text(s)
PY
cp -p "$POST" "$SPOST"
"$NODE" --check "$POST" >/dev/null || fail postmount_syntax

python3 - "$INDEX" "$VERSION" <<'PY'
from pathlib import Path
import re,sys
p=Path(sys.argv[1]); version=sys.argv[2]; s=p.read_text()
pat=r'/static/continuity-orb-beam-postmount\.js\?v=[^"\']+'
new=f'/static/continuity-orb-beam-postmount.js?v={version}'
if new not in s:
    s,n=re.subn(pat,new,s,count=1)
    if n != 1:
        raise SystemExit('THEME_STABLE_BINDER_V1=FAIL index_postmount_cache_anchor_missing')
p.write_text(s)
PY

"$RESTART"
[ "$(curl -sS -o /dev/null -w '%{http_code}' --max-time 10 http://127.0.0.1:18080/health || true)" = "200" ] || fail openwebui_health

stamp="$(date +%s)"
PUB="$(mktemp)"
curl -fsSL --retry 3 --connect-timeout 10 --max-time 25 -H 'Cache-Control: no-cache' -H 'Pragma: no-cache' \
  "https://powerpc-darwin.org/?__theme_stable_binder_v1=$stamp" -o "$PUB"

grep -Fq 'owui-postmount-ui-voice-v20260929.1' "$PUB" || fail ui_voice_marker_lost
grep -Fq 'owui-postmount-orb-beam-v20260930.1' "$PUB" || fail orb_marker_lost
grep -Fq "/static/continuity-orb-beam-postmount.js?v=$VERSION" "$PUB" || fail postmount_cache_generation_not_advanced

loader="$(curl -fsSL "https://powerpc-darwin.org/static/loader.js?cb=$stamp" | wc -c | tr -d ' ')"
custom="$(curl -fsSL "https://powerpc-darwin.org/static/custom.css?cb=$stamp" | wc -c | tr -d ' ')"
[ "$loader" = "0" ] || fail public_stock_loader_changed
[ "$custom" = "0" ] || fail public_stock_custom_css_changed

PUBPOST="$(curl -fsSL "https://powerpc-darwin.org/static/continuity-orb-beam-postmount.js?cb=$stamp")"
printf '%s' "$PUBPOST" | grep -Fq "continuity-theme-stable-binder.css?v=$VERSION" || fail binder_css_not_postmounted
printf '%s' "$PUBPOST" | grep -Fq "continuity-theme-stable-binder.js?v=$VERSION" || fail binder_js_not_postmounted
if printf '%s' "$PUBPOST" | grep -Fq 'continuity-neural-parity-v3'; then fail parity_v3_still_mounted; fi
if printf '%s' "$PUBPOST" | grep -Fq 'continuity-shell-lkg-mapper'; then fail lkg_mapper_reintroduced; fi

PUBJS="$(curl -fsSL "https://powerpc-darwin.org/static/continuity-theme-stable-binder.js?cb=$stamp")"
PUBCSS="$(curl -fsSL "https://powerpc-darwin.org/static/continuity-theme-stable-binder.css?cb=$stamp")"
printf '%s' "$PUBJS" | grep -Fq "const VERSION = '$VERSION'" || fail binder_js_marker_missing
printf '%s' "$PUBCSS" | grep -Fq 'continuity-theme-stable-binder-v20261001.1' || fail binder_css_marker_missing

if printf '%s' "$PUBJS" | grep -Eqi 'getBoundingClientRect|createTreeWalker|innerText|querySelectorAll\([^)]*img|textContent|innerHTML'; then
  fail forbidden_heuristic_or_text_scan_present
fi
if printf '%s\n%s' "$PUBJS" "$PUBCSS" | grep -Eqi '/api/v1/audio/local-voice/warm|local-voice/warm|warmSelectedVoice|pwa-client-runtime|speechSynthesis|AudioContext|webkitAudioContext'; then
  fail forbidden_audio_or_client_runtime_reference
fi

VOICE="$(curl -fsSL "https://powerpc-darwin.org/static/pwa-voice-bridge.js?cb=$stamp")"
printf '%s' "$VOICE" | grep -Fq '1.3.4-nowarm' || fail voice_bridge_changed
if printf '%s' "$VOICE" | grep -Eq 'warmSelectedVoice|/api/v1/audio/local-voice/warm|observer\.observe'; then
  fail voice_boundary_regressed
fi

ORBJS="$(curl -fsSL "https://powerpc-darwin.org/static/owui-orb-v1.js?cb=$stamp")"
ORBCSS="$(curl -fsSL "https://powerpc-darwin.org/static/owui-orb-v1.css?cb=$stamp")"
printf '%s' "$ORBJS" | grep -Fq "ORB_VERSION = '1.4.5'" || fail orb_version_changed
printf '%s' "$ORBCSS" | grep -Fq 'continuity-landing-hero-150-v20260930.1' || fail landing_hero_150_changed

rm -f "$PUB"
trap - EXIT

echo "THEME_STABLE_BINDER_V1=PUBLIC_PASS"
echo "semantic_binding=STABLE_IDS_AND_DATA_SURFACE_ONLY"
echo "composer_binding=RESTORED"
echo "landing_binding=RESTORED"
echo "neural_theme_aliases=LANDING_SCOPED"
echo "chat_telemetry=STANDALONE_42PX"
echo "route_transition_restore=OWNED_NEURAL_DOM_ONLY"
echo "heuristic_avatar_scan=ABSENT"
echo "heuristic_top_control_scan=ABSENT"
echo "footer_rewrite=ABSENT"
echo "native_settings_dom_mutation=ABSENT"
echo "accepted_border_beam=RETAINED"
echo "voice_bridge=1.3.4-nowarm"
echo "stock_loader_bytes=$loader"
echo "stock_custom_css_bytes=$custom"
echo "rollback=$BACKUP"
echo "NEXT=DEVICE_VISUAL_VALIDATION"
