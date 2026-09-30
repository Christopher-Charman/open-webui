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

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP="$BASE/runtime-domains/pwa-repair-agent/backups/pre-neural-parity-v3-$STAMP"
VERSION="20260930.3"
CSS="$FSTATIC/continuity-neural-parity-v3.css"
JS="$FSTATIC/continuity-neural-parity-v3.js"
SCSS="$SSTATIC/continuity-neural-parity-v3.css"
SJS="$SSTATIC/continuity-neural-parity-v3.js"

mkdir -p "$BACKUP/frontend/static" "$BACKUP/served/static"

fail(){ echo "NEURAL_PARITY_V3=FAIL $*"; exit 2; }

[ -f "$INDEX" ] || fail index_missing
[ -f "$POST" ] || fail postmount_missing
[ "$(wc -c < "$FSTATIC/loader.js" | tr -d ' ')" = "0" ] || fail stock_loader_not_empty
[ "$(wc -c < "$FSTATIC/custom.css" | tr -d ' ')" = "0" ] || fail stock_custom_css_not_empty
grep -Fq 'owui-postmount-ui-voice-v20260929.1' "$INDEX" || fail ui_voice_marker_missing
grep -Fq 'owui-postmount-orb-beam-v20260930.1' "$INDEX" || fail orb_marker_missing
grep -Fq "1.3.4-nowarm" "$FSTATIC/pwa-voice-bridge.js" || fail voice_boundary_missing

cp -p "$INDEX" "$BACKUP/frontend/index.html"
cp -p "$POST" "$BACKUP/frontend/static/continuity-orb-beam-postmount.js"
[ ! -f "$SPOST" ] || cp -p "$SPOST" "$BACKUP/served/static/continuity-orb-beam-postmount.js"
for n in continuity-neural-parity-v3.css continuity-neural-parity-v3.js; do
  [ ! -f "$FSTATIC/$n" ] || cp -p "$FSTATIC/$n" "$BACKUP/frontend/static/$n"
  [ ! -f "$SSTATIC/$n" ] || cp -p "$SSTATIC/$n" "$BACKUP/served/static/$n"
done

rollback(){
  echo "=== AUTO ROLLBACK NEURAL PARITY V3 ==="
  cp -p "$BACKUP/frontend/index.html" "$INDEX" || true
  cp -p "$BACKUP/frontend/static/continuity-orb-beam-postmount.js" "$POST" || true
  if [ -f "$BACKUP/served/static/continuity-orb-beam-postmount.js" ]; then
    cp -p "$BACKUP/served/static/continuity-orb-beam-postmount.js" "$SPOST"
  else
    cp -p "$POST" "$SPOST" || true
  fi
  for n in continuity-neural-parity-v3.css continuity-neural-parity-v3.js; do
    if [ -f "$BACKUP/frontend/static/$n" ]; then cp -p "$BACKUP/frontend/static/$n" "$FSTATIC/$n"; else rm -f "$FSTATIC/$n"; fi
    if [ -f "$BACKUP/served/static/$n" ]; then cp -p "$BACKUP/served/static/$n" "$SSTATIC/$n"; else rm -f "$SSTATIC/$n"; fi
  done
  "$RESTART" >/dev/null 2>&1 || true
  echo "NEURAL_PARITY_V3=ROLLBACK_AUTO_RESTORED"
}
trap 'rc=$?; if [ $rc -ne 0 ]; then rollback; fi; exit $rc' EXIT

cat > "$CSS" <<'CSS'
/* continuity-neural-parity-v3-20260930.3
   Visual-only parity refinement. No loader/audio/model/auth ownership. */

/* Keep the requested 150% neural hero, but remove inherited capsule/pseudo material. */
#owui-thinking-orb-v1[data-surface="landing"]::before,
#owui-thinking-orb-v1[data-surface="landing"]::after {
  content: none !important;
  display: none !important;
}

/* Historical settled chat telemetry: standalone ~42px thinking orb, no pill. */
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

/* Remove the duplicate beam added by the first neural overlay.
   Retain and strengthen the accepted v1.4.5 Border Beam primitive. */
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

/* Material circular presentation for native top-level controls only. */
.continuity-parity-round-control {
  border-radius: 999px !important;
  border: 1px solid rgba(188,202,225,.18) !important;
  background: linear-gradient(145deg,rgba(31,33,39,.62),rgba(11,13,18,.52)) !important;
  box-shadow:
    inset 0 1px 0 rgba(255,255,255,.055),
    0 7px 22px rgba(0,0,0,.20) !important;
  backdrop-filter: blur(12px) saturate(1.12) !important;
  -webkit-backdrop-filter: blur(12px) saturate(1.12) !important;
}

/* Landing-only stock avatar/model identity remnant. */
.continuity-parity-hide {
  display: none !important;
}

.continuity-parity-footer {
  letter-spacing: .075em !important;
  opacity: .74 !important;
}

/* Auth surface remains native OpenWebUI; Continuity controls stay out. */
html.continuity-auth-native #continuity-control-host {
  display: none !important;
}
CSS

cat > "$JS" <<'JS'
(() => {
  'use strict';
  const VERSION='20260930.3';
  if(window.__CONTINUITY_NEURAL_PARITY_V3__) return;
  window.__CONTINUITY_NEURAL_PARITY_V3__={version:VERSION,state:'booting'};

  function isAuthSurface(){
    if(/^\/auth(?:\/|$)/.test(location.pathname)) return true;
    const text=(document.body&&document.body.innerText)||'';
    return /Sign in to Open WebUI/i.test(text) && /Enter Your Password/i.test(text);
  }

  function syncAuthSurface(){
    const auth=isAuthSurface();
    document.documentElement.classList.toggle('continuity-auth-native',auth);
    const host=document.getElementById('continuity-control-host');
    if(host) host.style.display=auth?'none':'';
    return auth;
  }

  function collapseChatTelemetry(){
    const host=document.querySelector('#owui-thinking-orb-v1[data-surface="chat"]');
    if(!host) return;
    host.classList.add('continuity-chat-standalone');

    const canvas=host.querySelector('canvas');
    if(!canvas) return;

    let keep=canvas;
    while(keep.parentElement && keep.parentElement!==host) keep=keep.parentElement;

    Array.from(host.children).forEach(function(ch){
      if(ch===keep || ch.contains(canvas)){
        ch.style.display='';
        ch.querySelectorAll('*').forEach(function(el){
          if(el===canvas || el.contains(canvas)){
            if(el!==canvas) el.style.display='';
          }else{
            el.style.display='none';
          }
        });
      }else{
        ch.style.display='none';
      }
    });
  }

  function hideLandingAvatar(){
    const landing=document.querySelector('#owui-thinking-orb-v1[data-surface="landing"]');
    const composer=document.querySelector('#message-input-container');
    if(!landing || !composer) return;

    const lr=landing.getBoundingClientRect();
    const cr=composer.getBoundingClientRect();

    document.querySelectorAll('img').forEach(function(img){
      if(composer.contains(img) || landing.contains(img)) return;
      const r=img.getBoundingClientRect();
      if(r.width<24 || r.height<24 || r.width>100 || r.height>100) return;
      if(r.top < lr.bottom-20 || r.bottom > cr.top+16) return;

      let target=img;
      let p=img.parentElement;
      for(let i=0;i<3 && p;i++,p=p.parentElement){
        const pr=p.getBoundingClientRect();
        if(pr.width<=140 && pr.height<=140 && !composer.contains(p)){
          target=p;
        }else break;
      }
      target.classList.add('continuity-parity-hide');
    });
  }

  function rewriteFooter(){
    if(!document.body) return;
    const walker=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);
    const nodes=[];
    while(walker.nextNode()) nodes.push(walker.currentNode);
    nodes.forEach(function(node){
      const t=(node.nodeValue||'').trim();
      if(/^Open WebUI\s*·\s*v0\.11\.3$/i.test(t)){
        node.nodeValue='Continuity Shell · Open WebUI · v0.11.3';
        if(node.parentElement) node.parentElement.classList.add('continuity-parity-footer');
      }
    });
  }

  function roundTopControls(){
    if(!document.querySelector('#owui-thinking-orb-v1[data-surface="landing"]')) return;
    const w=window.innerWidth;
    const h=window.innerHeight;
    const candidates=document.querySelectorAll('button,a,[role="button"]');

    candidates.forEach(function(el){
      if(el.closest('#message-input-container')) return;
      if(el.closest('#continuity-control-host')) return;

      const r=el.getBoundingClientRect();
      if(r.width<28 || r.height<28 || r.width>92 || r.height>92) return;
      if(r.top<20 || r.top>Math.min(260,h*.26)) return;
      if(!(r.left<150 || r.right>w-150)) return;

      const label=((el.getAttribute('aria-label')||'')+' '+(el.textContent||'')).trim();
      if(label.length>40) return;
      if(!el.querySelector('svg') && !el.querySelector('img') && label.length>3) return;

      el.classList.add('continuity-parity-round-control');
    });
  }

  function apply(){
    const auth=syncAuthSurface();
    if(auth){
      window.__CONTINUITY_NEURAL_PARITY_V3__.state='auth-native';
      return;
    }
    collapseChatTelemetry();
    hideLandingAvatar();
    rewriteFooter();
    roundTopControls();
    window.__CONTINUITY_NEURAL_PARITY_V3__.state='ready';
  }

  let raf=0;
  function schedule(){
    if(raf) return;
    raf=requestAnimationFrame(function(){raf=0;apply();});
  }

  const observer=new MutationObserver(schedule);
  observer.observe(document.documentElement,{childList:true,subtree:true,attributes:true,attributeFilter:['data-surface']});
  window.addEventListener('popstate',schedule);
  window.addEventListener('resize',schedule,{passive:true});
  window.addEventListener('continuity-orb-beam:ready',schedule);
  schedule();
})();
JS

cp -p "$CSS" "$SCSS"
cp -p "$JS" "$SJS"

NODE="$BASE/.local/node22-glibc217/bin/node"
[ -x "$NODE" ] || NODE="$BASE/.local/node22-el7/bin/node"
[ -x "$NODE" ] || fail node_runtime_missing
"$NODE" --check "$JS" >/dev/null || fail parity_js_syntax

python3 - "$POST" "$VERSION" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1]); version=sys.argv[2]; s=p.read_text()
if "continuity-neural-parity-v3.css" in s or "continuity-neural-parity-v3.js" in s:
    raise SystemExit("NEURAL_PARITY_V3=FAIL already_referenced")
anchor="await js('/static/continuity-neural-material.js?v=20260930.2');"
if anchor not in s:
    raise SystemExit("NEURAL_PARITY_V3=FAIL neural_material_anchor_missing")
insert=anchor + "\n    await css('/static/continuity-neural-parity-v3.css?v=" + version + "');\n    await js('/static/continuity-neural-parity-v3.js?v=" + version + "');"
p.write_text(s.replace(anchor,insert,1))
PY
cp -p "$POST" "$SPOST"
"$NODE" --check "$POST" >/dev/null || fail postmount_syntax

# Bust only the post-mount bootstrap URL. Stock loader remains untouched.
python3 - "$INDEX" <<'PY'
from pathlib import Path
p=Path(__import__('sys').argv[1]); s=p.read_text()
old='/static/continuity-orb-beam-postmount.js?v=20260930.1'
new='/static/continuity-orb-beam-postmount.js?v=20260930.2'
if old in s:
    s=s.replace(old,new,1)
elif new not in s:
    raise SystemExit("NEURAL_PARITY_V3=FAIL index_postmount_cache_anchor_missing")
p.write_text(s)
PY

"$RESTART"

[ "$(curl -sS -o /dev/null -w '%{http_code}' --max-time 10 http://127.0.0.1:18080/health || true)" = "200" ] || fail openwebui_health

stamp="$(date +%s)"
PUB="$(mktemp)"
curl -fsSL --retry 3 --max-time 25 -H 'Cache-Control: no-cache' \
  "https://powerpc-darwin.org/?__neural_parity_v3=$stamp" -o "$PUB"

grep -Fq 'owui-postmount-ui-voice-v20260929.1' "$PUB" || fail ui_voice_marker_lost
grep -Fq 'owui-postmount-orb-beam-v20260930.1' "$PUB" || fail orb_marker_lost
grep -Fq 'continuity-orb-beam-postmount.js?v=20260930.2' "$PUB" || fail postmount_cache_generation_not_advanced

loader="$(curl -fsSL "https://powerpc-darwin.org/static/loader.js?cb=$stamp" | wc -c | tr -d ' ')"
custom="$(curl -fsSL "https://powerpc-darwin.org/static/custom.css?cb=$stamp" | wc -c | tr -d ' ')"
[ "$loader" = "0" ] || fail public_stock_loader_changed
[ "$custom" = "0" ] || fail public_stock_custom_css_changed

PUBPOST="$(curl -fsSL "https://powerpc-darwin.org/static/continuity-orb-beam-postmount.js?cb=$stamp")"
printf '%s' "$PUBPOST" | grep -Fq 'continuity-neural-parity-v3.css?v=20260930.3' || fail parity_css_not_postmounted
printf '%s' "$PUBPOST" | grep -Fq 'continuity-neural-parity-v3.js?v=20260930.3' || fail parity_js_not_postmounted

PUBJS="$(curl -fsSL "https://powerpc-darwin.org/static/continuity-neural-parity-v3.js?cb=$stamp")"
PUBCSS="$(curl -fsSL "https://powerpc-darwin.org/static/continuity-neural-parity-v3.css?cb=$stamp")"
printf '%s' "$PUBJS" | grep -Fq "const VERSION='20260930.3'" || fail parity_js_marker_missing
printf '%s' "$PUBCSS" | grep -Fq 'continuity-neural-parity-v3-20260930.3' || fail parity_css_marker_missing

if printf '%s\n%s' "$PUBJS" "$PUBCSS" | grep -Eqi 'local-voice/warm|warmSelectedVoice|pwa-client-runtime|audio/|speechSynthesis'; then
  fail forbidden_audio_or_client_runtime_reference
fi

VOICE2="$(curl -fsSL "https://powerpc-darwin.org/static/pwa-voice-bridge.js?cb=$stamp")"
printf '%s' "$VOICE2" | grep -Fq "1.3.4-nowarm" || fail voice_bridge_changed
if printf '%s' "$VOICE2" | grep -Eq 'warmSelectedVoice|/api/v1/audio/local-voice/warm|observer\.observe'; then
  fail voice_boundary_regressed
fi

rm -f "$PUB"
trap - EXIT

echo "NEURAL_PARITY_V3=PUBLIC_PASS"
echo "landing_avatar=SUPPRESSED"
echo "footer_identity=CONTINUITY_SHELL_OPENWEBUI"
echo "top_controls=ROUND_MATERIAL"
echo "chat_telemetry=STANDALONE_42PX_THINKING_ORB"
echo "duplicate_custom_beam=REMOVED"
echo "accepted_border_beam=RETAINED_AND_STRENGTHENED"
echo "auth_surface=STOCK_NATIVE_CONTINUITY_CONTROLS_HIDDEN"
echo "audio_changes=NONE"
echo "client_model_runtime=ABSENT"
echo "voice_bridge=1.3.4-nowarm"
echo "stock_loader_bytes=$loader"
echo "stock_custom_css_bytes=$custom"
echo "rollback=$BACKUP"
echo "NEXT=DEVICE_PARITY_TEST"
