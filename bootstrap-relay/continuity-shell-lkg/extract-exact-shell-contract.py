#!/usr/bin/env python3
from pathlib import Path
import hashlib, re, json

BASE=Path("/home/storage/781/4477781/user/webapp")
PKG=BASE/"envs/openwebui/lib/python3.11/site-packages/open_webui"
BACK=BASE/"runtime-domains/pwa-repair-agent/backups"

TARGET_JS="dec1bad28a2ead02e0f6e752c36d786234ee446fbde71c2eba31083f8c4dd779d"
TARGET_CUSTOM="258772ad82f3a57516a646c5d42edd6d008f0409e442dc557c32e617915147fc"
TARGET_LCARS="f4b49ce2f075fcf7e2c408e8448d86c4a99d82ae7fb4671cde084b126c1caf77"

def sha(p):
    h=hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""):
            h.update(b)
    return h.hexdigest()

def find_hash(name, want):
    out=[]
    roots=[PKG, BACK]
    for root in roots:
        if not root.exists(): continue
        for p in root.rglob(name):
            if not p.is_file(): continue
            try:
                if sha(p)==want: out.append(p)
            except Exception:
                pass
    return out

def ctx(text, needle, before=1400, after=3600):
    i=text.find(needle)
    if i<0: return None
    return text[max(0,i-before):min(len(text),i+after)]

def compact(s, limit=6500):
    return re.sub(r"\s+"," ",s).strip()[:limit]

def css_rules(text, needle):
    rules=[]
    pos=0
    while True:
        i=text.find(needle,pos)
        if i<0: break
        # selector begins after prior close brace/comment newline.
        s=max(text.rfind("}",0,i), text.rfind("\n",0,i), 0)
        if s>0: s+=1
        o=text.find("{",i)
        if o<0: break
        depth=0; e=None
        for j in range(o,len(text)):
            c=text[j]
            if c=="{": depth+=1
            elif c=="}":
                depth-=1
                if depth==0:
                    e=j+1; break
        if e:
            rule=text[s:e].strip()
            if rule not in rules: rules.append(rule)
            pos=e
        else: break
    return rules

print("EXACT_SHELL_CONTRACT_EXTRACT=BEGIN")
print("mode=READ_ONLY")

js_hits=find_hash("BkrUj_hp.js",TARGET_JS)
custom_hits=find_hash("custom.css",TARGET_CUSTOM)
lcars_hits=find_hash("lcars-theme.css",TARGET_LCARS)

print(f"historical_writer_matches={len(js_hits)}")
for p in js_hits: print(f"  JS={p}")
print(f"late_custom_matches={len(custom_hits)}")
for p in custom_hits[:10]: print(f"  CUSTOM={p}")
print(f"late_lcars_matches={len(lcars_hits)}")
for p in lcars_hits[:10]: print(f"  LCARS={p}")

if not js_hits:
    print("FAIL=historical_writer_hash_not_found")
    raise SystemExit(2)

p=js_hits[0]
t=p.read_text(errors="ignore")
print(f"\nWRITER_PATH={p}")
print(f"WRITER_SHA256={sha(p)}")
print(f"WRITER_BYTES={p.stat().st_size}")

print("\n=== WRITER IMPORT PREFIX ===")
print(compact(t[:6500],6500))

needles=[
    "resolveShellVisualState",
    "custom-shell-landing",
    "custom-shell-landing-prompt",
    "hero-network",
    "hero-aura",
    "chat-landing-network",
    "chat-landing-aura",
    "chat-telemetry",
    "orb-slot",
    "custom-shell-prompt",
    "custom-shell-footer",
]
for needle in needles:
    print(f"\n=== WRITER_CONTEXT {needle} ===")
    c=ctx(t,needle)
    print(compact(c,6500) if c else "ABSENT")

# Extract HTML template literals containing shell classes.
print("\n=== SHELL TEMPLATE LITERALS ===")
templates=[]
for m in re.finditer(r"""W\((['"])(.*?)\1\)""",t,re.S):
    raw=m.group(2)
    if any(k in raw for k in ("custom-shell","chat-telemetry","orb-slot","hero-network","hero-aura")):
        val=raw.replace("\\n"," ").replace("\\t"," ")
        if val not in templates: templates.append(val)
for i,x in enumerate(templates[:30],1):
    print(f"TEMPLATE_{i}={compact(x,5000)}")

# State string inventory around telemetry.
print("\n=== TELEMETRY STATE TOKENS ===")
for token in ["ready","thinking","listening","processing","generating","speaking","tool","warning","error","showDetail","phase","detail","engineSize","displaySize"]:
    print(f"{token}={'YES' if token in t else 'NO'}")

# CSS contract from exact late assets.
for label,hits in (("CUSTOM",custom_hits),("LCARS",lcars_hits)):
    if not hits: continue
    cp=hits[0]; cs=cp.read_text(errors="ignore")
    print(f"\n=== {label}_CSS_CONTRACT path={cp} sha256={sha(cp)} ===")
    for needle in [
        ".custom-shell-landing",
        ".custom-shell-landing-prompt",
        ".hero-network",
        ".hero-aura",
        ".chat-landing-network",
        ".chat-landing-aura",
        ".chat-telemetry",
        ".orb-slot",
        ".custom-shell-prompt",
        ".custom-shell-sidebar",
        ".custom-shell-footer",
        "WORLD BETWEEN WORLDS",
        "COMPUTER CORE",
        "INPUT",
    ]:
        rs=css_rules(cs,needle)
        if rs:
            print(f"\nCSS[{needle}] rules={len(rs)}")
            for rule in rs[:12]:
                print(compact(rule,2600))

# Current post-mount implementation for compatibility mapping, inspection only.
print("\n=== CURRENT_POSTMOUNT_INSPECTION ===")
for root in [PKG/"frontend/static",PKG/"static"]:
    if not root.exists(): continue
    for p in root.glob("*postmount*.js"):
        try:
            s=p.read_text(errors="ignore")
        except Exception:
            continue
        print(f"POSTMOUNT={p} sha256={sha(p)} bytes={p.stat().st_size}")
        for needle in [
            "continuity-neural-sphere-wrap","continuity-neural-svg",
            "owui-thinking-orb-v1","data-surface","message-input-container",
            "chat","landing"
        ]:
            print(f"  {needle}={'YES' if needle in s else 'NO'}")
        for needle in ["continuity-neural-sphere-wrap","owui-thinking-orb-v1","message-input-container"]:
            c=ctx(s,needle,700,1800)
            if c: print(f"  CTX[{needle}]={compact(c,2600)}")

print("\n=== DECISION BOUNDARY ===")
print("historical_loader=DO_NOT_RESTORE")
print("historical_voice_bridge=DO_NOT_RESTORE")
print("client_runtime=DO_NOT_RESTORE")
print("stock_loader=KEEP_ZERO_BYTES")
print("stock_custom_css=KEEP_ZERO_BYTES")
print("next=BUILD_EXACT_POSTMOUNT_PRESENTATION_ADAPTER_FROM_THIS_CONTRACT")
print("EXACT_SHELL_CONTRACT_EXTRACT=END")
print("RUNTIME_MUTATION=NONE")
