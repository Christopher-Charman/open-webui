#!/home/storage/781/4477781/user/webapp/miniconda/bin/python3
import base64, hashlib, hmac, json, os, subprocess, threading, time, urllib.parse
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

BASE="/home/storage/781/4477781/user/webapp"
CAP="O4k2rOOgzzYHQxi4HKKKPTrqouXFUwme"
SECRET=bytes.fromhex("3a0ccf054832059f6824f0b1d2343122cd8b7ed5d651decf6205313011dfbe2f")
EXPIRES=1790686800
SEEN=set()
LOCK=threading.Lock()
SAFE_ENV={"HOME":BASE,"PATH":BASE+"/.local/node22-glibc217/bin:"+BASE+"/miniconda/bin:/usr/local/bin:/usr/bin:/bin","LANG":"C.UTF-8"}

def b64d(s):
    s += "=" * (-len(s)%4)
    return base64.urlsafe_b64decode(s.encode()).decode("utf-8","replace")

def ok_sig(t,n,p,s):
    try:
        ti=int(t)
    except Exception:
        return False
    if abs(int(time.time())-ti)>300 or len(n)>80:
        return False
    msg=(t+"\n"+n+"\n"+p).encode()
    exp=hmac.new(SECRET,msg,hashlib.sha256).hexdigest()
    if not hmac.compare_digest(exp,s):
        return False
    with LOCK:
        if n in SEEN:
            return False
        SEEN.add(n)
    return True

class H(BaseHTTPRequestHandler):
    server_version="cgpt-bootstrap/2"
    def log_message(self,*args):
        pass
    def sendj(self,code,obj):
        data=json.dumps(obj,separators=(",",":")).encode()
        self.send_response(code)
        self.send_header("Content-Type","application/json")
        self.send_header("Cache-Control","no-store")
        self.send_header("Content-Length",str(len(data)))
        self.end_headers()
        self.wfile.write(data)
    def do_GET(self):
        if time.time()>EXPIRES:
            return self.sendj(410,{"ok":False,"error":"expired"})
        u=urllib.parse.urlparse(self.path)
        pref="/"+CAP+"/"
        if not u.path.startswith(pref):
            return self.sendj(404,{"ok":False})
        action=u.path[len(pref):]
        if action=="status":
            return self.sendj(200,{"ok":True,"base":BASE,"expires":EXPIRES})
        q=urllib.parse.parse_qs(u.query,keep_blank_values=True)
        t=q.get("t",[""])[0]; n=q.get("n",[""])[0]; p=q.get("p",[""])[0]; s=q.get("s",[""])[0]
        if not ok_sig(t,n,p,s):
            return self.sendj(403,{"ok":False,"error":"bad_signature_or_replay"})
        if action!="exec":
            return self.sendj(404,{"ok":False,"error":"unknown_action"})
        try:
            cmd=b64d(p)
            if len(cmd)>8192 or "\x00" in cmd:
                raise ValueError("command_rejected")
            deny=("rm -rf /","mkfs","shutdown","reboot","poweroff","halt",":(){")
            if any(x in cmd for x in deny):
                raise ValueError("destructive_command_rejected")
            cp=subprocess.run(["/bin/bash","-lc",cmd],cwd=BASE,env=SAFE_ENV,capture_output=True,text=True,timeout=45)
            return self.sendj(200,{"ok":cp.returncode==0,"rc":cp.returncode,"stdout":cp.stdout[-60000:],"stderr":cp.stderr[-30000:]})
        except subprocess.TimeoutExpired as e:
            return self.sendj(408,{"ok":False,"error":"timeout","stdout":(e.stdout or "")[-8000:],"stderr":(e.stderr or "")[-8000:]})
        except Exception as e:
            return self.sendj(400,{"ok":False,"error":str(e)[:500]})

ThreadingHTTPServer(("127.0.0.1",18765),H).serve_forever()
