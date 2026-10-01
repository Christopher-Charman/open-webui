#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json,re,shutil,time,urllib.request
from pathlib import Path

SCHEMA="openwebui-telemetry-retire-v1"
EXPECTED={
 "index":"84f1f48df3ff71cfbe35cbb7adbdd89c0dc3438c3b2e3794f69075759d81452b",
 "hero_js":"057541772b8a6100da7101e7dbfd0a5eb8987fea0a560ded21eebf49b6e9f885",
 "hero_css":"e90f322e756c1c8024ec9e57eac008fbeab25298cd8c5ab658f81a999e6b9d77",
 "orb_js":"71fab45c74489a147a3184044574da6d29051684f7848b59c3bb5627d58badc7",
 "orb_css":"a6e0249c2e57cac05d14246aeaf04d031c337ddd46e8a44b51680d9d99607b08",
 "stable_js":"e6ae52ea2910e28cd48ab7b45cfedb36c103eb71a685d74fa1f3752e4b3ebbe8",
 "stable_css":"e2cb37336716a2b4765f2fc965d873690869d5550d65278ee0b9ac32daf9c68d",
 "postmount_js":"b4c090f0a7a5ea55a4fdf6dbe2867b6e68cdba12346d9ab0bb9fd5c34035b992",
 "semantic_js":"28323668a349f2d52b1c73a307239a1fcf46abfa408be9e9e0ec2c1e8b2a0f99",
 "semantic_css":"042abfc5336fee16b2f7fe0f333ff938ac78c0c3e50968583366eaac2459a644",
 "voice":"73e40dfa272dcd5e5aafe60bfa045bda4dcbbe690c6ebc38596c0b314835555b",
}
def h(p:Path)->str:
    x=hashlib.sha256()
    with p.open("rb") as f:
        for c in iter(lambda:f.read(1024*1024),b""):x.update(c)
    return x.hexdigest()
def fetch(url:str)->bytes:
    req=urllib.request.Request(url,headers={"Cache-Control":"no-cache","Pragma":"no-cache","User-Agent":"continuity-shell-retire/1"})
    with urllib.request.urlopen(req,timeout=20) as r:
        if getattr(r,"status",200)!=200: raise RuntimeError(f"http_{r.status}")
        return r.read()

base=Path("/home/storage/781/4477781/user/webapp")
pkg=base/"envs/openwebui/lib/python3.11/site-packages/open_webui"
front=pkg/"frontend"; static=pkg/"static"; fstatic=front/"static"; index=front/"index.html"
paths={
 "index":index,
 "hero_js":static/"continuity-shell-hero-presenter.js",
 "hero_css":static/"continuity-shell-hero-presenter.css",
 "orb_js":static/"owui-orb-v1.js",
 "orb_css":static/"owui-orb-v1.css",
 "stable_js":static/"continuity-theme-stable-binder.js",
 "stable_css":static/"continuity-theme-stable-binder.css",
 "postmount_js":static/"continuity-orb-beam-postmount.js",
 "semantic_js":static/"continuity-shell-semantic-binder.js",
 "semantic_css":static/"continuity-shell-semantic-binder.css",
 "voice":static/"pwa-voice-bridge.js",
}
for k,p in paths.items():
    if not p.is_file(): raise SystemExit(f"RETIRE_FAIL missing:{k}")
    got=h(p)
    if got!=EXPECTED[k]: raise SystemExit(f"RETIRE_FAIL drift:{k}:{got}")
for p in (static/"loader.js",static/"custom.css",fstatic/"loader.js",fstatic/"custom.css"):
    if not p.is_file() or p.stat().st_size!=0: raise SystemExit(f"RETIRE_FAIL stock_bootstrap:{p}")

s=index.read_text()
for marker in ("owui-postmount-ui-voice-v20260929.1","owui-postmount-orb-beam-v20260930.1","continuity-shell-semantic-binder-v20260930.2","continuity-shell-landing-hero-presenter-v20260930.4"):
    if marker not in s: raise SystemExit(f"RETIRE_FAIL marker_missing:{marker}")
if "ORB_VERSION = '1.4.5'" not in (static/"owui-orb-v1.js").read_text(errors="replace"):
    raise SystemExit("RETIRE_FAIL orb_version")
if "continuity-landing-hero-150-v20260930.1" not in (static/"owui-orb-v1.css").read_text(errors="replace"):
    raise SystemExit("RETIRE_FAIL landing_hero_150")
if "continuity-theme-stable-binder-v20261001.1" not in (static/"continuity-theme-stable-binder.css").read_text(errors="replace"):
    raise SystemExit("RETIRE_FAIL stable_binder_marker")

stamp=time.strftime("%Y%m%dT%H%M%SZ",time.gmtime())
backup=base/"runtime-domains/pwa-repair-agent/backups"/f"pre-retire-fixed-hero-{stamp}"
backup.mkdir(parents=True,exist_ok=False)
shutil.copy2(index,backup/"index.html")

pat=re.compile(
 r'\n?<!-- continuity-shell-landing-hero-presenter-v20260930\.4 -->.*?'
 r'<!-- /continuity-shell-landing-hero-presenter-v20260930\.4 -->\n?',
 re.S
)
new,n=pat.subn("\n",s)
if n!=1:
    shutil.copy2(backup/"index.html",index)
    raise SystemExit(f"RETIRE_FAIL hero_block_count:{n}")
index.write_text(new)

try:
    if "continuity-shell-landing-hero-presenter-v20260930.4" in index.read_text():
        raise RuntimeError("hero_marker_survived")
    for k,p in paths.items():
        if k=="index": continue
        if h(p)!=EXPECTED[k]: raise RuntimeError(f"protected_changed:{k}")
    for p in (static/"loader.js",static/"custom.css",fstatic/"loader.js",fstatic/"custom.css"):
        if p.stat().st_size!=0: raise RuntimeError(f"stock_bootstrap_changed:{p}")

    cb=str(int(time.time()))
    public=fetch(f"https://powerpc-darwin.org/?__retire_fixed_hero={cb}").decode("utf-8","replace")
    if "continuity-shell-landing-hero-presenter-v20260930.4" in public or "/static/continuity-shell-hero-presenter." in public:
        raise RuntimeError("public_hero_presenter_survived")
    for marker in ("owui-postmount-ui-voice-v20260929.1","owui-postmount-orb-beam-v20260930.1","continuity-shell-semantic-binder-v20260930.2"):
        if marker not in public: raise RuntimeError(f"public_marker_lost:{marker}")
    pub_orb=fetch(f"https://powerpc-darwin.org/static/owui-orb-v1.js?cb={cb}")
    if hashlib.sha256(pub_orb).hexdigest()!=EXPECTED["orb_js"]: raise RuntimeError("public_orb_changed")
    pub_stable=fetch(f"https://powerpc-darwin.org/static/continuity-theme-stable-binder.js?cb={cb}")
    if hashlib.sha256(pub_stable).hexdigest()!=EXPECTED["stable_js"]: raise RuntimeError("public_stable_binder_changed")
except Exception:
    shutil.copy2(backup/"index.html",index)
    raise

out={
 "schema":SCHEMA,
 "mutation":"INDEX_ONLY_REMOVE_FIXED_BODY_PRESENTER",
 "status":"PUBLIC_PASS",
 "removed_blocks":n,
 "index_before":EXPECTED["index"],
 "index_after":h(index),
 "historical_orb_js":"1.4.5",
 "stable_theme_binder":"20261001.1",
 "hero_assets":"RETAINED_DORMANT",
 "protected_assets":"UNCHANGED",
 "stock_loader_bytes":0,
 "stock_custom_css_bytes":0,
 "passenger_restart":"NONE",
 "rollback":str(backup),
 "next":"DEVICE_VALIDATE_SYSTEM_WBW_LCARS_LANDING_AND_ACTIVE_CHAT"
}
print(json.dumps(out,sort_keys=True,separators=(",",":")))
