#!/usr/bin/env python3
from pathlib import Path
from datetime import datetime, timezone
import hashlib, os, re, shutil, subprocess, tempfile

BASE = Path('/home/storage/781/4477781/user/webapp')
PKG = BASE / 'envs/openwebui/lib/python3.11/site-packages/open_webui'
FRONTEND = PKG / 'frontend'
FSTATIC = FRONTEND / 'static'
SSTATIC = PKG / 'static'
INDEX = FRONTEND / 'index.html'
BACKUPS = BASE / 'runtime-domains/pwa-repair-agent/backups'

STAMP = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
BACKUP = BACKUPS / f'pre-orb-beam-reintro-{STAMP}'
GEN = '20260930.1'
MARKER = 'owui-postmount-orb-beam-v20260930.1'
HERO_MARKER = 'continuity-landing-hero-150-v20260930.1'

JS_HASH = '71fab45c74489a147a3184044574da6d29051684f7848b59c3bb5627d58badc7'
CSS_HASH = '6d71e7327a98c6c72904de25e0e379a96d78bf450ec8825978db201343a06e63'
HIST_ROOT = PKG / 'orb-backups-v1-4-5-hierarchy-20260923T054733Z'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def atomic_write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = data.encode() if isinstance(data, str) else data
    fd, tmp = tempfile.mkstemp(prefix=path.name+'.', dir=str(path.parent))
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(raw); f.flush(); os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        try: os.unlink(tmp)
        except FileNotFoundError: pass

def find_exact(name, want):
    # Search only bounded historical UI locations. The previous revision incorrectly
    # assumed the accepted v1.4.5 bytes would be either in the pre-v1.4.5 backup or
    # the later PWA-repair backup tree. Direct-host orb iterations used their own
    # sibling orb-backups-* directories under the OpenWebUI package.
    roots = [HIST_ROOT]
    roots += sorted(PKG.glob('orb-backups-*'), reverse=True)
    roots += sorted(PKG.glob('frontend.pre-*'), reverse=True)
    roots += sorted(BASE.glob('frontend.pre-*'), reverse=True)
    roots += [BACKUPS]

    seen = set()
    candidates = []
    for root in roots:
        if not root.exists():
            continue
        try:
            files = [root] if root.is_file() else root.rglob(name)
        except Exception:
            continue
        for p in files:
            if not p.is_file():
                continue
            try:
                rp = p.resolve()
            except Exception:
                rp = p
            if rp in seen:
                continue
            seen.add(rp)
            try:
                got = sha(p)
            except Exception:
                continue
            candidates.append((str(p), got))
            if got == want:
                print(f'EXACT_HISTORICAL_SOURCE_{name}={p}')
                return p

    print(f'EXACT_HISTORICAL_SOURCE_{name}=NOT_FOUND')
    print(f'CANDIDATE_COUNT_{name}={len(candidates)}')
    for path, got in candidates[:80]:
        print(f'CANDIDATE_{name}={got} {path}')
    raise SystemExit(f'ERROR exact historical asset missing after bounded orb-history scan: {name} sha256={want}')

def backup_file(path, rel):
    if path.exists():
        dst = BACKUP / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dst)

if not INDEX.is_file():
    raise SystemExit('ERROR index missing')

# Protected baseline invariants from accepted UI/voice checkpoint.
if (FSTATIC/'loader.js').read_bytes() != b'':
    raise SystemExit('ERROR stock loader.js no longer empty')
if (FSTATIC/'custom.css').read_bytes() != b'':
    raise SystemExit('ERROR stock custom.css no longer empty')

index = INDEX.read_text()
if 'owui-postmount-ui-voice-v20260929.1' not in index:
    raise SystemExit('ERROR accepted UI/voice layer marker missing')
if MARKER in index:
    print('ORB_BEAM_REINTRO=ALREADY_APPLIED')
    raise SystemExit(0)

# Verify stock immutable app generation still coherent.
preloads = sorted(set(re.findall(r'/_app/immutable/entry/(app\.[A-Za-z0-9_-]+\.js)', index)))
imports = sorted(set(Path(x).name for x in re.findall(
    r'import\(["\']/(_app/immutable/entry/app\.[A-Za-z0-9_-]+\.js)["\']\)', index
)))
if len(preloads) != 1 or preloads != imports:
    raise SystemExit(f'ERROR stock frontend coherence lost: preload={preloads} import={imports}')
if not (FRONTEND/'_app/immutable/entry'/preloads[0]).is_file():
    raise SystemExit('ERROR stock immutable app entry missing')

src_js = find_exact('owui-orb-v1.js', JS_HASH)
src_css = find_exact('owui-orb-v1.css', CSS_HASH)

js_text = src_js.read_text()
css_text = src_css.read_text()

if not re.search(r"ORB_VERSION\s*=\s*['\"]1\.4\.5['\"]", js_text):
    raise SystemExit('ERROR v1.4.5 JS version marker missing despite exact hash match')
if 'owui-border-beam-v1' not in js_text:
    raise SystemExit('ERROR Border Beam JS marker missing')
if 'owui-thinking-orb-v1' not in js_text:
    raise SystemExit('ERROR thinking-orb host marker missing')
if '[data-surface="landing"]' not in css_text:
    raise SystemExit('ERROR accepted v1.4.5 landing selector missing')
if 'dataset.surface' not in js_text and 'setAttribute("data-surface"' not in js_text and "setAttribute('data-surface'" not in js_text:
    raise SystemExit('ERROR route-aware surface marker missing from v1.4.5 JS')

# Presentation-only derivative requested after v1.4.5 acceptance:
# enlarge the landing hero by 50% while leaving compact chat telemetry and
# Border Beam state behavior unchanged. Mobile width is viewport-capped to
# avoid horizontal overflow, while height/orb scale remain 150%.
hero_override = f"""
/* {HERO_MARKER}
   Base accepted v1.4.5 landing hero: ~410x108, orb ~82.
   Requested derivative: 150% => 615x162, orb 123.
   Mobile base: ~326x94, orb ~74 => 489x141, orb 111.
   Width is capped to the viewport on narrow screens. */
#owui-thinking-orb-v1[data-surface="landing"] {{
  width: min(615px, calc(100vw - 24px)) !important;
  min-height: 162px !important;
}}
#owui-thinking-orb-v1[data-surface="landing"] canvas {{
  width: 123px !important;
  height: 123px !important;
}}
@media (max-width: 420px) {{
  #owui-thinking-orb-v1[data-surface="landing"] {{
    width: min(489px, calc(100vw - 16px)) !important;
    min-height: 141px !important;
  }}
  #owui-thinking-orb-v1[data-surface="landing"] canvas {{
    width: 111px !important;
    height: 111px !important;
  }}
}}
"""
css_text = css_text.rstrip() + "\n\n" + hero_override.strip() + "\n"

# Qualify the exact historical JS before use.
node_candidates = [
    BASE/'.local/node22-glibc217/bin/node',
    BASE/'.local/node22-el7/bin/node',
]
node = next((p for p in node_candidates if p.is_file() and os.access(p, os.X_OK)), None)
if not node:
    raise SystemExit('ERROR Node runtime unavailable for JS syntax check')
proc = subprocess.run([str(node), '--check', str(src_js)],
                      stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
if proc.returncode:
    print(proc.stderr[-3000:])
    raise SystemExit('ERROR historical orb JS syntax check failed')

bootstrap = """(() => {
'use strict';
const VERSION='20260930.1';
if(window.__CONTINUITY_ORB_BEAM_POSTMOUNT__) return;
window.__CONTINUITY_ORB_BEAM_POSTMOUNT__={version:VERSION,state:'waiting-stock-mount'};

const mounted=()=>!document.getElementById('splash-screen');
const css=href=>new Promise((ok,no)=>{
  const l=document.createElement('link');
  l.rel='stylesheet'; l.href=href; l.dataset.continuityOrbBeam='css';
  l.onload=ok; l.onerror=()=>no(new Error('orb css load failed'));
  document.head.appendChild(l);
});
const js=src=>new Promise((ok,no)=>{
  const s=document.createElement('script');
  s.src=src; s.defer=true; s.dataset.continuityOrbBeam='js';
  s.onload=ok; s.onerror=()=>no(new Error('orb js load failed'));
  document.head.appendChild(s);
});
async function start(){
  if(!mounted()) return;
  try{
    window.__CONTINUITY_ORB_BEAM_POSTMOUNT__.state='loading';
    await css('/static/owui-orb-v1.css?v='+VERSION);
    await js('/static/owui-orb-v1.js?v='+VERSION);
    window.__CONTINUITY_ORB_BEAM_POSTMOUNT__.state='ready';
    window.dispatchEvent(new CustomEvent('continuity-orb-beam:ready',{detail:{version:VERSION}}));
  }catch(error){
    window.__CONTINUITY_ORB_BEAM_POSTMOUNT__.state='error';
    window.__CONTINUITY_ORB_BEAM_POSTMOUNT__.error=String(error);
    console.error('[Continuity orb/beam post-mount]',error);
  }
}
if(mounted()){requestAnimationFrame(()=>requestAnimationFrame(start));return}
const o=new MutationObserver(()=>{
  if(!mounted()) return;
  o.disconnect();
  requestAnimationFrame(()=>requestAnimationFrame(start));
});
o.observe(document.documentElement,{childList:true,subtree:true});
})();"""

# Syntax-check generated bootstrap too.
fd,tmp = tempfile.mkstemp(prefix='orb-beam-postmount-',suffix='.js',dir=str(BASE))
os.close(fd); tmp_path=Path(tmp)
try:
    tmp_path.write_text(bootstrap)
    proc = subprocess.run([str(node),'--check',str(tmp_path)],
                          stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    if proc.returncode:
        print(proc.stderr[-3000:])
        raise SystemExit('ERROR telemetry bootstrap syntax failed')
finally:
    try: tmp_path.unlink()
    except FileNotFoundError: pass

BACKUP.mkdir(parents=True, exist_ok=False)
backup_file(INDEX,'frontend/index.html')
for name in ('owui-orb-v1.js','owui-orb-v1.css','continuity-orb-beam-postmount.js'):
    backup_file(FSTATIC/name,'frontend/static/'+name)
    backup_file(SSTATIC/name,'served/static/'+name)

try:
    atomic_write(FSTATIC/'owui-orb-v1.js', js_text)
    atomic_write(FSTATIC/'owui-orb-v1.css', css_text)
    atomic_write(FSTATIC/'continuity-orb-beam-postmount.js', bootstrap)
    atomic_write(SSTATIC/'owui-orb-v1.js', js_text)
    atomic_write(SSTATIC/'owui-orb-v1.css', css_text)
    atomic_write(SSTATIC/'continuity-orb-beam-postmount.js', bootstrap)

    tag=f'<script src="/static/continuity-orb-beam-postmount.js?v={GEN}" defer crossorigin="use-credentials" data-continuity-layer="orb-beam-v145"></script>'
    if '</head>' not in index:
        raise RuntimeError('index head anchor missing')
    index=index.replace('</head>',f'\n\t\t<!-- {MARKER} -->\n\t\t{tag}\n\t</head>',1)
    atomic_write(INDEX,index)

    written=INDEX.read_text()
    if MARKER not in written or tag not in written:
        raise RuntimeError('index telemetry injection verification failed')
    if '/static/owui-orb-v1.js' in written or '/static/owui-orb-v1.css' in written:
        raise RuntimeError('orb assets referenced directly instead of post-mount bootstrap')
    if (FSTATIC/'loader.js').read_bytes()!=b'' or (FSTATIC/'custom.css').read_bytes()!=b'':
        raise RuntimeError('stock bootstrap extension points changed')
    if sha(FSTATIC/'owui-orb-v1.js') != JS_HASH:
        raise RuntimeError('orb JS hash drift after write')
    if HERO_MARKER not in (FSTATIC/'owui-orb-v1.css').read_text():
        raise RuntimeError('landing hero 150% marker missing after write')
except Exception:
    shutil.copy2(BACKUP/'frontend/index.html', INDEX)
    print('ORB_BEAM_REINTRO=ROLLBACK_AUTO_RESTORED')
    raise

print('ORB_BEAM_REINTRO=STAGED_ON_DISK_PASS')
print('LAYER=POSTMOUNT_ORB_BORDERBEAM_V145_PLUS_LANDING_HERO_150')
print('ORB_SOURCE_VERSION=1.4.5')
print('LANDING_HERO_SCALE=1.5')
print('LANDING_DESKTOP_TARGET=615x162_ORB123')
print('LANDING_MOBILE_TARGET=489x141_ORB111_VIEWPORT_CAPPED')
print('ORB_JS_SHA256='+sha(FSTATIC/'owui-orb-v1.js'))
print('ORB_CSS_BASE_SHA256='+CSS_HASH)
print('ORB_CSS_DERIVED_SHA256='+sha(FSTATIC/'owui-orb-v1.css'))
print('SOURCE_JS='+str(src_js))
print('SOURCE_CSS='+str(src_css))
print('STOCK_LOADER_BYTES='+str((FSTATIC/'loader.js').stat().st_size))
print('STOCK_CUSTOM_CSS_BYTES='+str((FSTATIC/'custom.css').stat().st_size))
print('UI_VOICE_LAYER=PRESERVED')
print('BACKUP='+str(BACKUP))
