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
BACKUP="$BASE/runtime-domains/pwa-repair-agent/backups/pre-neural-material-overlay-$STAMP"
VERSION="20260930.2"
CSS="$FSTATIC/continuity-neural-material.css"
JS="$FSTATIC/continuity-neural-material.js"
SCSS="$SSTATIC/continuity-neural-material.css"
SJS="$SSTATIC/continuity-neural-material.js"

mkdir -p "$BACKUP/frontend/static" "$BACKUP/served/static"

fail() { echo "NEURAL_MATERIAL_OVERLAY=FAIL $*"; exit 2; }

[ -f "$INDEX" ] || fail index_missing
[ -f "$POST" ] || fail postmount_orb_bootstrap_missing
[ "$(wc -c < "$FSTATIC/loader.js" | tr -d ' ')" = "0" ] || fail stock_loader_not_empty
[ "$(wc -c < "$FSTATIC/custom.css" | tr -d ' ')" = "0" ] || fail stock_custom_css_not_empty

grep -Fq 'owui-postmount-ui-voice-v20260929.1' "$INDEX" || fail accepted_ui_voice_marker_missing
grep -Fq 'owui-postmount-orb-beam-v20260930.1' "$INDEX" || fail accepted_orb_layer_marker_missing

VOICE="$(cat "$FSTATIC/pwa-voice-bridge.js")"
printf '%s' "$VOICE" | grep -Fq "1.3.4-nowarm" || fail voice_bridge_boundary_missing
if printf '%s' "$VOICE" | grep -Eq 'warmSelectedVoice|/api/v1/audio/local-voice/warm|observer\.observe'; then
  fail voice_boundary_regressed
fi

cp -p "$POST" "$BACKUP/frontend/static/continuity-orb-beam-postmount.js"
[ ! -f "$SPOST" ] || cp -p "$SPOST" "$BACKUP/served/static/continuity-orb-beam-postmount.js"
for n in continuity-neural-material.css continuity-neural-material.js; do
  [ ! -f "$FSTATIC/$n" ] || cp -p "$FSTATIC/$n" "$BACKUP/frontend/static/$n"
  [ ! -f "$SSTATIC/$n" ] || cp -p "$SSTATIC/$n" "$BACKUP/served/static/$n"
done

rollback() {
  echo "=== AUTO ROLLBACK NEURAL-MATERIAL OVERLAY ==="
  cp -p "$BACKUP/frontend/static/continuity-orb-beam-postmount.js" "$POST" || true
  if [ -f "$BACKUP/served/static/continuity-orb-beam-postmount.js" ]; then
    cp -p "$BACKUP/served/static/continuity-orb-beam-postmount.js" "$SPOST"
  else
    cp -p "$POST" "$SPOST" || true
  fi
  for n in continuity-neural-material.css continuity-neural-material.js; do
    if [ -f "$BACKUP/frontend/static/$n" ]; then cp -p "$BACKUP/frontend/static/$n" "$FSTATIC/$n"; else rm -f "$FSTATIC/$n"; fi
    if [ -f "$BACKUP/served/static/$n" ]; then cp -p "$BACKUP/served/static/$n" "$SSTATIC/$n"; else rm -f "$SSTATIC/$n"; fi
  done
  "$RESTART" >/dev/null 2>&1 || true
  echo "NEURAL_MATERIAL_OVERLAY=ROLLBACK_AUTO_RESTORED"
}
trap 'rc=$?; if [ $rc -ne 0 ]; then rollback; fi; exit $rc' EXIT

cat > "$CSS" <<'CSS'
/* continuity-neural-material-v20260930.2
   Presentation-only derivative of the accepted 2026-09-23 neural-material shell.
   No audio, model, loader, auth or routing ownership. */

#owui-thinking-orb-v1[data-surface="landing"] {
  width: min(360px, calc(100vw - 32px)) !important;
  min-height: 318px !important;
  max-height: none !important;
  padding: 0 !important;
  margin: 8px auto 18px !important;
  background: transparent !important;
  border: 0 !important;
  border-radius: 0 !important;
  box-shadow: none !important;
  backdrop-filter: none !important;
  -webkit-backdrop-filter: none !important;
  overflow: visible !important;
  display: grid !important;
  place-items: center !important;
}

#owui-thinking-orb-v1[data-surface="landing"] > :not(.continuity-neural-hero) {
  display: none !important;
}

.continuity-neural-hero {
  width: 300px;
  height: 318px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 17px;
  position: relative;
  isolation: isolate;
  pointer-events: none;
}

.continuity-neural-sphere-wrap {
  width: 300px;
  height: 260px;
  display: grid;
  place-items: center;
  position: relative;
}

.continuity-neural-sphere-wrap::before,
.continuity-neural-sphere-wrap::after {
  content: "";
  position: absolute;
  border-radius: 50%;
  pointer-events: none;
}

.continuity-neural-sphere-wrap::before {
  width: 230px;
  height: 230px;
  background:
    radial-gradient(circle at 36% 35%, rgba(55,196,255,.23), transparent 34%),
    radial-gradient(circle at 69% 63%, rgba(218,63,255,.23), transparent 38%),
    radial-gradient(circle at 50% 50%, rgba(65,94,255,.09), transparent 66%);
  filter: blur(18px);
  animation: continuity-neural-breathe 4.6s ease-in-out infinite;
}

.continuity-neural-sphere-wrap::after {
  width: 205px;
  height: 205px;
  border: 1px solid rgba(128,150,255,.11);
  box-shadow:
    0 0 26px rgba(46,183,255,.16),
    0 0 54px rgba(185,56,255,.12),
    inset -14px -10px 35px rgba(171,55,255,.07),
    inset 13px 8px 32px rgba(42,185,255,.06);
}

.continuity-neural-svg {
  width: 240px;
  height: 240px;
  overflow: visible;
  filter:
    drop-shadow(0 0 9px rgba(63,178,255,.34))
    drop-shadow(0 0 17px rgba(194,65,255,.20));
  z-index: 2;
}

.continuity-neural-edge {
  stroke-linecap: round;
  animation: continuity-edge-breathe 5.2s ease-in-out infinite;
}

.continuity-neural-node {
  animation: continuity-node-pulse 3.8s ease-in-out infinite;
  transform-box: fill-box;
  transform-origin: center;
}

.continuity-neural-ready {
  color: rgba(245,244,255,.94);
  font-size: 17px;
  font-weight: 650;
  letter-spacing: .32em;
  line-height: 1;
  text-transform: uppercase;
  text-shadow:
    0 0 9px rgba(94,190,255,.28),
    0 0 18px rgba(192,76,255,.16);
  margin-left: .32em;
}

#message-input-container {
  position: relative !important;
  isolation: isolate;
}

.continuity-material-composer-beam {
  position: absolute;
  inset: -3px;
  border: 2px solid transparent;
  border-radius: inherit;
  pointer-events: none;
  z-index: 5;
  background:
    linear-gradient(#0000,#0000) padding-box,
    linear-gradient(100deg,
      #41a8ff 0%,
      #32e0ff 17%,
      #775cff 38%,
      #cf4cff 58%,
      #ff5aab 76%,
      #ff995c 89%,
      #41a8ff 100%) border-box;
  background-size: 100% 100%, 260% 100%;
  -webkit-mask:
    linear-gradient(#000 0 0) padding-box,
    linear-gradient(#000 0 0);
  -webkit-mask-composite: xor;
  mask-composite: exclude;
  animation: continuity-material-beam-flow 5.5s linear infinite;
  filter: drop-shadow(0 0 5px rgba(70,181,255,.36))
          drop-shadow(0 0 8px rgba(207,76,255,.22));
  opacity: .9;
}

.continuity-material-round-control {
  border-radius: 999px !important;
  border: 1px solid rgba(185,198,224,.19) !important;
  background: linear-gradient(145deg, rgba(31,33,38,.68), rgba(13,14,18,.54)) !important;
  box-shadow:
    inset 0 1px 0 rgba(255,255,255,.055),
    0 8px 25px rgba(0,0,0,.22) !important;
  backdrop-filter: blur(12px) saturate(1.1);
  -webkit-backdrop-filter: blur(12px) saturate(1.1);
}

.continuity-material-hidden-landing-identity {
  display: none !important;
}

.continuity-material-footer {
  letter-spacing: .08em;
  opacity: .72;
}

@keyframes continuity-node-pulse {
  0%,100% { opacity:.76; transform:scale(.92); }
  50% { opacity:1; transform:scale(1.13); }
}
@keyframes continuity-edge-breathe {
  0%,100% { opacity:.28; }
  50% { opacity:.58; }
}
@keyframes continuity-neural-breathe {
  0%,100% { transform:scale(.96); opacity:.72; }
  50% { transform:scale(1.04); opacity:1; }
}
@keyframes continuity-material-beam-flow {
  from { background-position: 0 0, 0% 50%; }
  to   { background-position: 0 0, 260% 50%; }
}

@media (max-width: 420px) {
  #owui-thinking-orb-v1[data-surface="landing"] {
    width: min(310px, calc(100vw - 26px)) !important;
    min-height: 272px !important;
    margin-top: 2px !important;
  }
  .continuity-neural-hero {
    width: 270px;
    height: 272px;
    gap: 13px;
  }
  .continuity-neural-sphere-wrap {
    width: 270px;
    height: 224px;
  }
  .continuity-neural-sphere-wrap::before {
    width: 220px;
    height: 220px;
  }
  .continuity-neural-sphere-wrap::after {
    width: 195px;
    height: 195px;
  }
  .continuity-neural-svg {
    width: 240px;
    height: 240px;
  }
  .continuity-neural-ready {
    font-size: 15px;
    letter-spacing: .30em;
  }
}

#owui-thinking-orb-v1[data-surface="chat"] .continuity-neural-hero {
  display: none !important;
}
CSS

cat > "$JS" <<'JS'
(() => {
  'use strict';
  const VERSION='20260930.2';
  if (window.__CONTINUITY_NEURAL_MATERIAL__) return;
  window.__CONTINUITY_NEURAL_MATERIAL__={version:VERSION,state:'booting'};

  const NS='http://www.w3.org/2000/svg';

  function svgEl(name, attrs) {
    const e=document.createElementNS(NS,name);
    attrs=attrs||{};
    Object.entries(attrs).forEach(function(kv){e.setAttribute(kv[0],String(kv[1]));});
    return e;
  }

  function colour(t, alpha) {
    alpha=alpha==null?1:alpha;
    const h=202+t*92;
    return 'hsla('+h+',92%,67%,'+alpha+')';
  }

  function fibonacciSphere(n) {
    n=n||42;
    const out=[];
    const ga=Math.PI*(3-Math.sqrt(5));
    for(let i=0;i<n;i++){
      const y=1-(i/(n-1))*2;
      const r=Math.sqrt(Math.max(0,1-y*y));
      const th=ga*i;
      const x=Math.cos(th)*r;
      const z=Math.sin(th)*r;
      out.push({x:x,y:y,z:z});
    }
    return out;
  }

  function makeSphere() {
    const hero=document.createElement('div');
    hero.className='continuity-neural-hero';
    hero.dataset.continuityNeuralMaterial='1';

    const wrap=document.createElement('div');
    wrap.className='continuity-neural-sphere-wrap';

    const svg=svgEl('svg',{viewBox:'0 0 240 240','aria-hidden':'true'});
    svg.classList.add('continuity-neural-svg');

    const defs=svgEl('defs');
    const glow=svgEl('filter',{id:'continuity-neural-glow',x:'-80%',y:'-80%',width:'260%',height:'260%'});
    const blur=svgEl('feGaussianBlur',{stdDeviation:'2.4',result:'b'});
    const merge=svgEl('feMerge');
    merge.append(svgEl('feMergeNode',{in:'b'}),svgEl('feMergeNode',{in:'SourceGraphic'}));
    glow.append(blur,merge);
    defs.append(glow);
    svg.append(defs);

    const pts=fibonacciSphere(42).map(function(p,i){
      const perspective=0.78+(p.z+1)*0.12;
      return {
        x:p.x,y:p.y,z:p.z,i:i,
        sx:120+p.x*82*perspective,
        sy:120+p.y*82*perspective,
        depth:(p.z+1)/2
      };
    });

    const edgeKeys={};
    const edges=[];
    pts.forEach(function(a){
      const nearest=pts.filter(function(b){return b!==a;})
        .map(function(b){return {b:b,d:(a.x-b.x)*(a.x-b.x)+(a.y-b.y)*(a.y-b.y)+(a.z-b.z)*(a.z-b.z)};})
        .sort(function(u,v){return u.d-v.d;}).slice(0,3);
      nearest.forEach(function(item){
        const b=item.b;
        const key=a.i<b.i?(a.i+'-'+b.i):(b.i+'-'+a.i);
        if(!edgeKeys[key]){edgeKeys[key]=1;edges.push({a:a,b:b});}
      });
    });

    const edgeGroup=svgEl('g');
    edges.forEach(function(edge){
      const a=edge.a,b=edge.b,dep=(a.depth+b.depth)/2;
      const line=svgEl('line',{
        x1:a.sx,y1:a.sy,x2:b.sx,y2:b.sy,
        stroke:colour((a.x+b.x+2)/4,0.16+dep*0.34),
        'stroke-width':0.55+dep*0.75
      });
      line.classList.add('continuity-neural-edge');
      line.style.animationDelay=(((a.i+b.i)%11)*-0.31)+'s';
      edgeGroup.append(line);
    });
    svg.append(edgeGroup);

    const nodeGroup=svgEl('g',{filter:'url(#continuity-neural-glow)'});
    pts.slice().sort(function(a,b){return a.z-b.z;}).forEach(function(p){
      const c=svgEl('circle',{
        cx:p.sx,cy:p.sy,
        r:1.7+p.depth*3.1,
        fill:colour((p.x+1)/2,0.76+p.depth*0.24)
      });
      c.classList.add('continuity-neural-node');
      c.style.animationDelay=(p.i*-0.13)+'s';
      nodeGroup.append(c);
    });
    svg.append(nodeGroup);
    wrap.append(svg);

    const ready=document.createElement('div');
    ready.className='continuity-neural-ready';
    ready.textContent='READY';

    hero.append(wrap,ready);
    return hero;
  }

  function neuralizeLanding() {
    const host=document.querySelector('#owui-thinking-orb-v1[data-surface="landing"]');
    if(!host) return false;
    if(!host.querySelector('.continuity-neural-hero')) host.append(makeSphere());
    return true;
  }

  function beamComposer() {
    const composer=document.querySelector('#message-input-container');
    if(!composer) return false;
    if(!composer.querySelector(':scope > .continuity-material-composer-beam')){
      const beam=document.createElement('div');
      beam.className='continuity-material-composer-beam';
      beam.setAttribute('aria-hidden','true');
      composer.append(beam);
    }
    return true;
  }

  function hideLandingIdentity() {
    const landing=document.querySelector('#owui-thinking-orb-v1[data-surface="landing"]');
    const composer=document.querySelector('#message-input-container');
    if(!landing || !composer) return;
    document.querySelectorAll('div,span,p,h1,h2,h3').forEach(function(el){
      if(el.children.length) return;
      if((el.textContent||'').trim()!=='Continuity Agent') return;
      if(composer.contains(el)) return;
      const r=el.getBoundingClientRect();
      const cr=composer.getBoundingClientRect();
      if(r.bottom<=cr.top && cr.top-r.bottom<330){
        el.classList.add('continuity-material-hidden-landing-identity');
      }
    });
  }

  function footerIdentity() {
    document.querySelectorAll('div,span,p').forEach(function(el){
      if(el.children.length) return;
      const t=(el.textContent||'').trim();
      if(/^Open WebUI\s*·\s*v0\.11\.3$/i.test(t)){
        el.textContent='Continuity Shell · Open WebUI · v0.11.3';
        el.classList.add('continuity-material-footer');
      }
    });
  }

  function roundTopControls() {
    if(!document.querySelector('#owui-thinking-orb-v1[data-surface="landing"]')) return;
    const w=window.innerWidth,h=window.innerHeight;
    document.querySelectorAll('button').forEach(function(b){
      if(b.closest('#message-input-container')) return;
      const r=b.getBoundingClientRect();
      if(r.width<28 || r.height<28 || r.width>90 || r.height>90) return;
      if(r.top<70 || r.top>Math.min(330,h*.30)) return;
      if(!(r.left<145 || r.right>w-145)) return;
      if((b.textContent||'').trim().length>2) return;
      b.classList.add('continuity-material-round-control');
    });
  }

  function apply() {
    const landing=neuralizeLanding();
    beamComposer();
    if(landing){
      hideLandingIdentity();
      footerIdentity();
      roundTopControls();
    }
    window.__CONTINUITY_NEURAL_MATERIAL__.state=landing?'landing-ready':'chat-ready';
  }

  let raf=0;
  function schedule(){
    if(raf) return;
    raf=requestAnimationFrame(function(){raf=0;apply();});
  }

  const observer=new MutationObserver(schedule);
  observer.observe(document.documentElement,{childList:true,subtree:true,attributes:true,attributeFilter:['data-surface']});
  window.addEventListener('resize',schedule,{passive:true});
  window.addEventListener('popstate',schedule);
  window.addEventListener('continuity-orb-beam:ready',schedule);
  schedule();
  window.__CONTINUITY_NEURAL_MATERIAL__.state='ready';
})();
JS

cp -p "$CSS" "$SCSS"
cp -p "$JS" "$SJS"

NODE="$BASE/.local/node22-glibc217/bin/node"
[ -x "$NODE" ] || NODE="$BASE/.local/node22-el7/bin/node"
[ -x "$NODE" ] || fail node_runtime_missing
"$NODE" --check "$JS" >/dev/null || fail neural_material_js_syntax

python3 - "$POST" "$VERSION" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1]); version=sys.argv[2]; s=p.read_text()
if "continuity-neural-material.css" in s or "continuity-neural-material.js" in s:
    raise SystemExit("NEURAL_MATERIAL_OVERLAY=FAIL already_referenced")
anchor="await js('/static/owui-orb-v1.js?v='+VERSION);"
if anchor not in s:
    raise SystemExit("NEURAL_MATERIAL_OVERLAY=FAIL postmount_anchor_missing")
insert=anchor + "\n    await css('/static/continuity-neural-material.css?v=" + version + "');\n    await js('/static/continuity-neural-material.js?v=" + version + "');"
p.write_text(s.replace(anchor,insert,1))
PY
cp -p "$POST" "$SPOST"

"$NODE" --check "$POST" >/dev/null || fail postmount_js_syntax

"$RESTART"

[ "$(curl -sS -o /dev/null -w '%{http_code}' --max-time 10 http://127.0.0.1:18080/health || true)" = "200" ] || fail openwebui_health

stamp="$(date +%s)"
PUB="$(mktemp)"
curl -fsSL --retry 3 --max-time 25 -H 'Cache-Control: no-cache' \
  "https://powerpc-darwin.org/?__neural_material=$stamp" -o "$PUB"

grep -Fq 'owui-postmount-ui-voice-v20260929.1' "$PUB" || fail ui_voice_marker_lost
grep -Fq 'owui-postmount-orb-beam-v20260930.1' "$PUB" || fail orb_layer_marker_lost

loader="$(curl -fsSL "https://powerpc-darwin.org/static/loader.js?cb=$stamp" | wc -c | tr -d ' ')"
custom="$(curl -fsSL "https://powerpc-darwin.org/static/custom.css?cb=$stamp" | wc -c | tr -d ' ')"
[ "$loader" = "0" ] || fail public_stock_loader_changed
[ "$custom" = "0" ] || fail public_stock_custom_css_changed

PUBPOST="$(curl -fsSL "https://powerpc-darwin.org/static/continuity-orb-beam-postmount.js?cb=$stamp")"
printf '%s' "$PUBPOST" | grep -Fq 'continuity-neural-material.css?v=20260930.2' || fail neural_css_not_postmounted
printf '%s' "$PUBPOST" | grep -Fq 'continuity-neural-material.js?v=20260930.2' || fail neural_js_not_postmounted

PUBCSS="$(curl -fsSL "https://powerpc-darwin.org/static/continuity-neural-material.css?cb=$stamp")"
PUBJS="$(curl -fsSL "https://powerpc-darwin.org/static/continuity-neural-material.js?cb=$stamp")"
printf '%s' "$PUBCSS" | grep -Fq 'continuity-neural-material-v20260930.2' || fail neural_css_marker_missing
printf '%s' "$PUBJS" | grep -Fq "const VERSION='20260930.2'" || fail neural_js_marker_missing

if printf '%s\n%s' "$PUBCSS" "$PUBJS" | grep -Eqi 'local-voice/warm|warmSelectedVoice|pwa-client-runtime|audio/|speechSynthesis'; then
  fail forbidden_audio_or_client_runtime_reference
fi

VOICE2="$(curl -fsSL "https://powerpc-darwin.org/static/pwa-voice-bridge.js?cb=$stamp")"
printf '%s' "$VOICE2" | grep -Fq "1.3.4-nowarm" || fail voice_bridge_changed
if printf '%s' "$VOICE2" | grep -Eq 'warmSelectedVoice|/api/v1/audio/local-voice/warm|observer\.observe'; then
  fail voice_boundary_regressed_after_restart
fi

rm -f "$PUB"
trap - EXIT

echo "NEURAL_MATERIAL_OVERLAY=PUBLIC_PASS"
echo "visual_authority=2026-09-23_NEURAL_MATERIAL_ACCEPTED_SHELL"
echo "landing_hero=VOLUMETRIC_NEURAL_SPHERE_READY_ONLY"
echo "landing_hero_scale=1.5_FROM_NEURAL_MATERIAL_BASELINE"
echo "chat_telemetry=UNCHANGED_ACCEPTED_V1.4.5"
echo "composer_beam=RESTORED_STRONG_SPECTRAL_POSTMOUNT"
echo "top_controls=ROUND_MATERIAL_PRESENTATION_ONLY"
echo "footer_identity=CONTINUITY_SHELL_OPENWEBUI"
echo "loader_ownership=STOCK_UNTOUCHED"
echo "audio_changes=NONE"
echo "client_model_runtime=ABSENT"
echo "voice_bridge=1.3.4-nowarm"
echo "stock_loader_bytes=$loader"
echo "stock_custom_css_bytes=$custom"
echo "rollback=$BACKUP"
echo "NEXT=DEVICE_TEST_LANDING_AND_ACTIVE_CHAT"
