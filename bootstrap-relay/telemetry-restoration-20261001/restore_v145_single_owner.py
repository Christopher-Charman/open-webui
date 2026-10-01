#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json,re,shutil,time,urllib.request
from pathlib import Path

BASE=Path("/home/storage/781/4477781/user/webapp")
PKG=BASE/"envs/openwebui/lib/python3.11/site-packages/open_webui"
FSTATIC=PKG/"frontend/static"
SSTATIC=PKG/"static"
INDEX=PKG/"frontend/index.html"
EXPECTED={
 "index":"e95f8b57ecfeb71acd34649659f8654ccd23ac42626c3c61b7a2b0e17279ee0c",
 "post":"b4c090f0a7a5ea55a4fdf6dbe2867b6e68cdba12346d9ab0bb9fd5c34035b992",
 "orb_js":"71fab45c74489a147a3184044574da6d29051684f7848b59c3bb5627d58badc7",
 "orb_css_current":"a6e0249c2e57cac05d14246aeaf04d031c337ddd46e8a44b51680d9d99607b08",
 "orb_css_accepted":"6d71e7327a98c6c72904de25e0e379a96d78bf450ec8825978db201343a06e63",
 "neural_js":"3ef6fdd776980d18ed02bf784b3138fc85cae805e4cf114106de03259a5f1aaf",
 "neural_css":"5ab1a6fc2fcd46e0c2d7e07eeb655f8e5a2bce87df596d3bea0f82d59d3f983c",
 "stable_js":"e6ae52ea2910e28cd48ab7b45cfedb36c103eb71a685d74fa1f3752e4b3ebbe8",
 "stable_css":"e2cb37336716a2b4765f2fc965d873690869d5550d65278ee0b9ac32daf9c68d",
 "voice":"73e40dfa272dcd5e5aafe60bfa045bda4dcbbe690c6ebc38596c0b314835555b"
}
def sha(p):
    h=hashlib.sha256()
    with p.open("rb") as f:
        for c in iter(lambda:f.read(1024*1024),b""): h.update(c)
    return h.hexdigest()
def fail(msg): raise SystemExit("V145_BASELINE_RESTORE=FAIL "+msg)
def fetch(url):
    req=urllib.request.Request(url,headers={"Cache-Control":"no-cache","Pragma":"no-cache","User-Agent":"continuity-v145-restore/1"})
    with urllib.request.urlopen(req,timeout=20) as r: return r.read()

files={
 "index":INDEX,
 "post":SSTATIC/"continuity-orb-beam-postmount.js",
 "orb_js":SSTATIC/"owui-orb-v1.js",
 "orb_css_current":SSTATIC/"owui-orb-v1.css",
 "neural_js":SSTATIC/"continuity-neural-material.js",
 "neural_css":SSTATIC/"continuity-neural-material.css",
 "stable_js":SSTATIC/"continuity-theme-stable-binder.js",
 "stable_css":SSTATIC/"continuity-theme-stable-binder.css",
 "voice":SSTATIC/"pwa-voice-bridge.js"
}
for k,p in files.items():
    if not p.is_file(): fail("missing:"+k)
    got=sha(p)
    if got!=EXPECTED[k]: fail(f"drift:{k}:{got}")
for root in (SSTATIC,FSTATIC):
    for n in ("loader.js","custom.css"):
        p=root/n
        if not p.is_file() or p.stat().st_size!=0: fail("stock_bootstrap:"+str(p))

# Resolve an exact accepted v1.4.5 CSS survivor by cryptographic identity.
accepted=None
for p in PKG.glob("**/owui-orb-v1.css"):
    try:
        if p.resolve() in {(SSTATIC/"owui-orb-v1.css").resolve(),(FSTATIC/"owui-orb-v1.css").resolve()}: continue
        if sha(p)==EXPECTED["orb_css_accepted"]:
            accepted=p
            break
    except OSError:
        pass
if accepted is None: fail("accepted_css_survivor_not_found")

stamp=time.strftime("%Y%m%dT%H%M%SZ",time.gmtime())
backup=BASE/"runtime-domains/pwa-repair-agent/backups"/f"pre-v145-single-owner-{stamp}"
(backup/"served").mkdir(parents=True)
(backup/"frontend").mkdir(parents=True)
shutil.copy2(INDEX,backup/"index.html")
for n in ("continuity-orb-beam-postmount.js","owui-orb-v1.css"):
    shutil.copy2(SSTATIC/n,backup/"served"/n)
    shutil.copy2(FSTATIC/n,backup/"frontend"/n)

# Restore exact browser-accepted v1.4.5 stylesheet to both static roots.
shutil.copy2(accepted,SSTATIC/"owui-orb-v1.css")
shutil.copy2(accepted,FSTATIC/"owui-orb-v1.css")

# Reduce post-mount ownership to the accepted orb/beam only.
post=(SSTATIC/"continuity-orb-beam-postmount.js").read_text()
post=post.replace("const VERSION='20260930.1';","const VERSION='20261001.2-v145-single-owner';")
for line in (
 "    await css('/static/continuity-neural-material.css?v=20260930.2');\n",
 "    await js('/static/continuity-neural-material.js?v=20260930.2');\n",
 "    await css('/static/continuity-theme-stable-binder.css?v=20261001.1');\n",
 "    await js('/static/continuity-theme-stable-binder.js?v=20261001.1');\n",
):
    if line not in post: fail("postmount_anchor_missing:"+line.strip())
    post=post.replace(line,"")
(SSTATIC/"continuity-orb-beam-postmount.js").write_text(post)
(FSTATIC/"continuity-orb-beam-postmount.js").write_text(post)

# Cache-bust the post-mount loader without touching stock loader/custom.css.
idx=INDEX.read_text()
pat=re.compile(r'/static/continuity-orb-beam-postmount\.js\?v=[^"\']+')
idx2,n=pat.subn('/static/continuity-orb-beam-postmount.js?v=20261001.2-v145-single-owner',idx,count=1)
if n!=1: fail("index_postmount_ref_count:"+str(n))
INDEX.write_text(idx2)

try:
    if sha(SSTATIC/"owui-orb-v1.js")!=EXPECTED["orb_js"]: raise RuntimeError("orb_js_changed")
    if sha(SSTATIC/"owui-orb-v1.css")!=EXPECTED["orb_css_accepted"]: raise RuntimeError("orb_css_not_exact_v145")
    ptxt=(SSTATIC/"continuity-orb-beam-postmount.js").read_text()
    if "continuity-neural-material" in ptxt or "continuity-theme-stable-binder" in ptxt: raise RuntimeError("duplicate_owner_survived")
    if "20261001.2-v145-single-owner" not in ptxt: raise RuntimeError("postmount_version_missing")
    for root in (SSTATIC,FSTATIC):
        if sha(root/"owui-orb-v1.css")!=EXPECTED["orb_css_accepted"]: raise RuntimeError("css_roots_diverged")
        if sha(root/"continuity-orb-beam-postmount.js")!=sha(SSTATIC/"continuity-orb-beam-postmount.js"): raise RuntimeError("post_roots_diverged")
        if (root/"loader.js").stat().st_size or (root/"custom.css").stat().st_size: raise RuntimeError("stock_bootstrap_changed")
    if sha(SSTATIC/"pwa-voice-bridge.js")!=EXPECTED["voice"]: raise RuntimeError("voice_changed")

    cb=str(int(time.time()))
    public=fetch(f"https://powerpc-darwin.org/?__v145_single_owner={cb}").decode("utf-8","replace")
    if "/static/continuity-orb-beam-postmount.js?v=20261001.2-v145-single-owner" not in public:
        raise RuntimeError("public_index_cache_ref_missing")
    pubpost=fetch(f"https://powerpc-darwin.org/static/continuity-orb-beam-postmount.js?cb={cb}").decode()
    if "continuity-neural-material" in pubpost or "continuity-theme-stable-binder" in pubpost:
        raise RuntimeError("public_duplicate_owner_survived")
    pubcss=fetch(f"https://powerpc-darwin.org/static/owui-orb-v1.css?cb={cb}")
    pubjs=fetch(f"https://powerpc-darwin.org/static/owui-orb-v1.js?cb={cb}")
    if hashlib.sha256(pubcss).hexdigest()!=EXPECTED["orb_css_accepted"]: raise RuntimeError("public_css_not_exact_v145")
    if hashlib.sha256(pubjs).hexdigest()!=EXPECTED["orb_js"]: raise RuntimeError("public_js_not_exact_v145")
except Exception:
    shutil.copy2(backup/"index.html",INDEX)
    for n in ("continuity-orb-beam-postmount.js","owui-orb-v1.css"):
        shutil.copy2(backup/"served"/n,SSTATIC/n)
        shutil.copy2(backup/"frontend"/n,FSTATIC/n)
    raise

out={
 "schema":"openwebui-v145-single-owner-restore-v1",
 "mutation":"RESTORE_EXACT_V145_PRESENTATION_OWNER",
 "status":"PUBLIC_PASS",
 "orb_js_sha256":EXPECTED["orb_js"],
 "orb_css_sha256":EXPECTED["orb_css_accepted"],
 "accepted_css_source":str(accepted),
 "duplicate_neural_material_mount":"REMOVED",
 "duplicate_stable_binder_mount":"REMOVED",
 "theme_assets":"RETAINED_DORMANT",
 "voice":"UNCHANGED",
 "stock_loader_bytes":0,
 "stock_custom_css_bytes":0,
 "passenger_restart":"NONE",
 "rollback":str(backup),
 "next":"DEVICE_VALIDATE_LANDING_CHAT_SETTINGS_AND_CHAT_ROUTE_STABILITY"
}
print(json.dumps(out,sort_keys=True,separators=(",",":")))
