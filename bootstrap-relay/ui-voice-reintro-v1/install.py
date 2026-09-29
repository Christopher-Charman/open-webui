#!/usr/bin/env python3
from pathlib import Path
from datetime import datetime, timezone
import hashlib, os, re, shutil, subprocess, tempfile, urllib.request

BASE = Path('/home/storage/781/4477781/user/webapp')
PKG = BASE / 'envs/openwebui/lib/python3.11/site-packages/open_webui'
FRONTEND = PKG / 'frontend'
FRONT_STATIC = FRONTEND / 'static'
SERVED_STATIC = PKG / 'static'
INDEX = FRONTEND / 'index.html'
BACKUPS = BASE / 'runtime-domains/pwa-repair-agent/backups'

CORE_REF = '3a3cf459a8f46dc53a63b59ea1792196ec77dc69'
CONTROL_REF = 'cbc4456d6b1368b268dec24e591bd1dcf33f9dca'
REPO_RAW = 'https://raw.githubusercontent.com/Christopher-Charman/repository-prime'
SRC_ROOT = 'projects/hosting.fasthosts.webapp/continuity-shell/static'

GEN = '20260929.1'
MARKER = 'owui-postmount-ui-voice-v20260929.1'
STAMP = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
BACKUP = BACKUPS / f'pre-ui-voice-reintro-{STAMP}'

FILES = {
    'continuity-theme-overlay.css': (CONTROL_REF, 'custom.css'),
    'lcars-theme.css': (CORE_REF, 'lcars-theme.css'),
    'lcars-runtime.js': (CORE_REF, 'lcars-runtime.js'),
    'continuity-controls.js': (CONTROL_REF, 'continuity-controls.js'),
    'pwa-voice-bridge.js': (CORE_REF, 'pwa-voice-bridge.js'),
}

FOOTER = re.compile(r'\n?\[executed on device:[^\]]+\]\s*$')

def fetch(ref, name):
    url = f'{REPO_RAW}/{ref}/{SRC_ROOT}/{name}'
    req = urllib.request.Request(url, headers={'User-Agent':'owui-ui-voice-reintro/1'})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode()

def clean_source(text):
    return FOOTER.sub('', text)

def atomic_write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = data.encode() if isinstance(data, str) else data
    fd, tmp = tempfile.mkstemp(prefix=path.name + '.', dir=str(path.parent))
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(raw); f.flush(); os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        try: os.unlink(tmp)
        except FileNotFoundError: pass

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def backup_file(path, rel):
    if path.exists():
        dst = BACKUP / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dst)

if not INDEX.is_file():
    raise SystemExit('ERROR index missing')

# Protected stock recovery baseline must still be intact.
if (FRONT_STATIC/'loader.js').read_bytes() != b'':
    raise SystemExit('ERROR stock loader.js is no longer empty; refuse layered reintroduction')
if (FRONT_STATIC/'custom.css').read_bytes() != b'':
    raise SystemExit('ERROR stock custom.css is no longer empty; refuse layered reintroduction')

index = INDEX.read_text()
if MARKER in index:
    print('UI_VOICE_REINTRO=ALREADY_APPLIED')
    raise SystemExit(0)

# Verify stock Svelte app entry remains coherent before adding any layer.
preloads = sorted(set(re.findall(r'/_app/immutable/entry/(app\.[A-Za-z0-9_-]+\.js)', index)))
imports = sorted(set(Path(x).name for x in re.findall(
    r'import\(["\']/(_app/immutable/entry/app\.[A-Za-z0-9_-]+\.js)["\']\)', index
)))
if len(preloads) != 1 or preloads != imports:
    raise SystemExit(f'ERROR stock frontend coherence lost before reintroduction: preload={preloads} import={imports}')
if not (FRONTEND/'_app/immutable/entry'/preloads[0]).is_file():
    raise SystemExit('ERROR stock immutable app entry missing before reintroduction')

assets = {}
for dst, (ref, src) in FILES.items():
    assets[dst] = clean_source(fetch(ref, src))

# Latest chronological voice bridge, corrected only at known-bad boundaries.
voice = assets['pwa-voice-bridge.js']
if "const VERSION = '1.3.3';" not in voice:
    raise SystemExit('ERROR expected voice bridge 1.3.3 source not found')
voice = voice.replace("const VERSION = '1.3.3';", "const VERSION = '1.3.4-nowarm';", 1)

# Remove automatic warm calls.
for call in (
    "    warmSelectedVoice(state.voice).catch(() => {});\n",
    "      warmSelectedVoice(voice).catch(() => {});\n",
):
    if call not in voice:
        raise SystemExit('ERROR expected historical warm call missing; source drifted')
    voice = voice.replace(call, '', 1)

# Remove the dedicated warm helper entirely.
warm_pat = re.compile(
    r"\n  const warmSelectedVoice = async \(voice\) => \{.*?\n  \};\n\n  const splitForStreaming",
    re.S,
)
voice, n = warm_pat.subn("\n  const splitForStreaming", voice, count=1)
if n != 1:
    raise SystemExit('ERROR failed to remove warmSelectedVoice helper')

# Remove known dangling observer invocation from the historical bridge.
obs = "    observer.observe(document.documentElement, { childList: true, subtree: true });\n"
if obs not in voice:
    raise SystemExit('ERROR expected dangling observer call missing; source drifted')
voice = voice.replace(obs, '', 1)

if '/api/v1/audio/local-voice/warm' in voice or 'warmSelectedVoice' in voice:
    raise SystemExit('ERROR warm behavior remains in voice bridge')
if 'observer.observe' in voice:
    raise SystemExit('ERROR dangling observer behavior remains')
assets['pwa-voice-bridge.js'] = voice

# Build a clean registry from the latest chronological theme/voice taxonomy while
# correcting the historical World Between Worlds internal key to OpenWebUI's "her".
registry = r"""(() => {
  'use strict';
  const VERSION='0.3.0';
  const BUILD='20260929.1';
  const THEME_KEY='continuity.theme';
  const r=document.documentElement;
  const THEMES=Object.freeze({
    system:{label:'System',native:'system'},
    dark:{label:'Dark',native:'dark'},
    oled:{label:'OLED Dark',native:'oled-dark'},
    wbw:{label:'World Between Worlds',native:'her'},
    lcars:{label:'LCARS',owned:true}
  });
  const VOICES=Object.freeze({
    'ahsoka-pocket-hybrid-ep':{label:'Ahsoka Hybrid'},
    ahsoka:{label:'Ahsoka Piper (reference)',reference:true},
    cortana:{label:'Cortana'},
    'majel-computer':{label:'Majel Computer'}
  });
  const meta=()=>document.querySelector('meta[name="theme-color"]');
  const applyNative=(id)=>{
    const v=THEMES[id]?.native;
    if(!v) return false;
    window.OWUILCARS?.disable?.();
    localStorage.setItem('theme',v);
    for(const k of ['--color-gray-800','--color-gray-850','--color-gray-900','--color-gray-950']) r.style.removeProperty(k);
    r.classList.remove('her','light');
    if(v==='system'){
      const dark=matchMedia('(prefers-color-scheme: dark)').matches;
      r.classList.toggle('dark',dark);
      r.classList.toggle('light',!dark);
      meta()?.setAttribute('content',dark?'#171717':'#ffffff');
    }else if(v==='dark'){
      r.classList.add('dark');
      meta()?.setAttribute('content','#171717');
    }else if(v==='oled-dark'){
      r.classList.add('dark');
      r.style.setProperty('--color-gray-800','#101010');
      r.style.setProperty('--color-gray-850','#050505');
      r.style.setProperty('--color-gray-900','#000000');
      r.style.setProperty('--color-gray-950','#000000');
      meta()?.setAttribute('content','#000000');
    }else if(v==='her'){
      r.classList.add('dark','her');
      meta()?.setAttribute('content','#061326');
    }
    localStorage.setItem(THEME_KEY,id);
    r.dataset.continuityTheme=id;
    window.dispatchEvent(new StorageEvent('storage',{key:'theme',newValue:v}));
    window.dispatchEvent(new CustomEvent('continuity-shell:theme',{detail:{id}}));
    return true;
  };
  const derive=()=>{
    if(r.classList.contains('lcars')) return 'lcars';
    const t=localStorage.getItem('theme')||'system';
    if(t==='her') return 'wbw';
    if(t==='oled-dark') return 'oled';
    if(t==='dark') return 'dark';
    return 'system';
  };
  const api={
    version:VERSION,build:BUILD,themes:THEMES,voices:VOICES,
    setTheme(id){
      if(!THEMES[id]) throw Error('Unknown theme: '+id);
      if(id==='lcars'){
        if(!window.OWUILCARS) throw Error('LCARS runtime unavailable');
        window.OWUILCARS.enable();
        localStorage.setItem(THEME_KEY,'lcars');
        r.dataset.continuityTheme='lcars';
        window.dispatchEvent(new CustomEvent('continuity-shell:theme',{detail:{id:'lcars'}}));
        return 'lcars';
      }
      applyNative(id);
      return id;
    },
    theme(){return derive();},
    setVoice(id){
      if(!VOICES[id]) throw Error('Unknown voice: '+id);
      return window.OWUIClientVoice?.setVoice(id)??false;
    },
    voice(){return window.OWUIClientVoice?.status?.().voice||null}
  };
  // LCARS is explicit-only; never auto-restore it at login.
  if(localStorage.getItem(THEME_KEY)==='lcars') localStorage.setItem(THEME_KEY,derive());
  window.ContinuityShell=Object.freeze(api);
  r.dataset.continuityTheme=api.theme();
  window.dispatchEvent(new CustomEvent('continuity-shell:ready',{detail:{version:VERSION,build:BUILD}}));
})();"""
assets['continuity-shell-registry.js'] = registry

# The only document-time custom code is this inert post-mount loader.
bootstrap = r"""(() => {
  'use strict';
  const VERSION='20260929.1';
  if(window.__CONTINUITY_POSTMOUNT_V1__) return;
  window.__CONTINUITY_POSTMOUNT_V1__={version:VERSION,state:'waiting-stock-mount'};

  const addCss=(href)=>new Promise((resolve,reject)=>{
    if(document.querySelector('link[data-continuity-postmount="'+href+'"]')) return resolve();
    const l=document.createElement('link');
    l.rel='stylesheet'; l.href=href; l.dataset.continuityPostmount=href;
    l.onload=resolve; l.onerror=()=>reject(new Error('CSS load failed: '+href));
    document.head.appendChild(l);
  });
  const addJs=(src)=>new Promise((resolve,reject)=>{
    if(document.querySelector('script[data-continuity-postmount="'+src+'"]')) return resolve();
    const s=document.createElement('script');
    s.src=src; s.defer=true; s.dataset.continuityPostmount=src;
    s.onload=resolve; s.onerror=()=>reject(new Error('JS load failed: '+src));
    document.head.appendChild(s);
  });

  const mounted=()=>!document.getElementById('splash-screen');
  const start=async()=>{
    if(!mounted()) return false;
    try{
      window.__CONTINUITY_POSTMOUNT_V1__.state='loading';
      await addCss('/static/continuity-theme-overlay.css?v='+VERSION);
      await addJs('/static/pwa-voice-bridge.js?v='+VERSION);
      await addJs('/static/lcars-runtime.js?v='+VERSION);
      await addJs('/static/continuity-shell-registry.js?v='+VERSION);
      await addJs('/static/continuity-controls.js?v='+VERSION);
      window.__CONTINUITY_POSTMOUNT_V1__.state='ready';
      window.dispatchEvent(new CustomEvent('continuity-postmount:ready',{detail:{version:VERSION}}));
      return true;
    }catch(error){
      window.__CONTINUITY_POSTMOUNT_V1__.state='error';
      window.__CONTINUITY_POSTMOUNT_V1__.error=String(error);
      console.error('[Continuity post-mount]',error);
      return false;
    }
  };

  if(mounted()){ queueMicrotask(start); return; }
  const observer=new MutationObserver(()=>{
    if(!mounted()) return;
    observer.disconnect();
    requestAnimationFrame(()=>requestAnimationFrame(start));
  });
  observer.observe(document.documentElement,{childList:true,subtree:true});
})();"""
assets['continuity-postmount-bootstrap.js'] = bootstrap

# First-layer exclusions.
for forbidden in ('pwa-client-runtime.js','continuity-settings.js'):
    if forbidden in bootstrap:
        raise SystemExit('ERROR forbidden first-layer module referenced: '+forbidden)

# Syntax-qualify JS before touching live files.
node_candidates=[
    BASE/'.local/node22-glibc217/bin/node',
    BASE/'.local/node22-el7/bin/node',
]
node=next((p for p in node_candidates if p.is_file() and os.access(p,os.X_OK)),None)
if not node:
    raise SystemExit('ERROR Node runtime required for JS qualification')
for name,text in assets.items():
    if not name.endswith('.js'): continue
    fd,tmp=tempfile.mkstemp(prefix='owui-ui-voice-check-',suffix='.js',dir=str(BASE))
    os.close(fd); p=Path(tmp)
    try:
        p.write_text(text)
        q=subprocess.run([str(node),'--check',str(p)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        if q.returncode:
            print(q.stderr[-3000:])
            raise SystemExit('ERROR JS syntax failed: '+name)
    finally:
        try:p.unlink()
        except FileNotFoundError:pass

# Snapshot exact touched surface.
BACKUP.mkdir(parents=True, exist_ok=False)
backup_file(INDEX,'frontend/index.html')
for name in assets:
    backup_file(FRONT_STATIC/name,'frontend/static/'+name)
    backup_file(SERVED_STATIC/name,'served/static/'+name)
(BACKUP/'ROLLBACK.txt').write_text(
    'Restore frontend/index.html from this directory, remove newly-created first-layer assets where no prior copy exists, then restart OpenWebUI.\n'
)

try:
    for name,text in assets.items():
        atomic_write(FRONT_STATIC/name,text)
        # Mirror now; canonical restart will recopy frontend/static to served static.
        atomic_write(SERVED_STATIC/name,text)

    tag=f'<script src="/static/continuity-postmount-bootstrap.js?v={GEN}" defer crossorigin="use-credentials" data-continuity-layer="ui-voice-v1"></script>'
    if '</head>' not in index:
        raise RuntimeError('index </head> anchor missing')
    index=index.replace('</head>',f'\n\t\t<!-- {MARKER} -->\n\t\t{tag}\n\t</head>',1)
    atomic_write(INDEX,index)

    written=INDEX.read_text()
    if tag not in written or MARKER not in written:
        raise RuntimeError('index injection verification failed')
    if '/static/pwa-client-runtime.js' in written:
        raise RuntimeError('client runtime unexpectedly referenced directly')
    if (FRONT_STATIC/'loader.js').read_bytes()!=b'' or (FRONT_STATIC/'custom.css').read_bytes()!=b'':
        raise RuntimeError('stock bootstrap extension points were altered')
except Exception:
    shutil.copy2(BACKUP/'frontend/index.html',INDEX)
    print('UI_VOICE_REINTRO=ROLLBACK_AUTO_RESTORED')
    raise

print('UI_VOICE_REINTRO=STAGED_ON_DISK_PASS')
print('LAYER=POSTMOUNT_THEMES_AND_SERVER_VOICES_ONLY')
print('THEMES=System|Dark|OLED Dark|World Between Worlds|LCARS')
print('VOICES=Ahsoka Hybrid|Ahsoka Piper (reference)|Cortana|Majel Computer')
print('VOICE_BRIDGE_VERSION=1.3.4-nowarm')
print('MODEL_CLIENT_RUNTIME=ABSENT')
print('VOICE_WARM_CALLS=ABSENT')
print('NATIVE_SETTINGS_DOM_INJECTION=ABSENT')
print('LOADER_BYTES='+str((FRONT_STATIC/'loader.js').stat().st_size))
print('CUSTOM_CSS_BYTES='+str((FRONT_STATIC/'custom.css').stat().st_size))
print('BACKUP='+str(BACKUP))
for name in sorted(assets):
    print(name+'_sha256='+sha(FRONT_STATIC/name))
