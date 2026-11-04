#!/usr/bin/env python3
"""VANTA's dependency-free SQLite and notification service."""
import json, os, sqlite3, threading, time, shutil
from contextlib import contextmanager
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
ROOT=Path(__file__).resolve().parent
def data_directory(system=None,environ=None,home=None):
    system=system or os.name
    environ=os.environ if environ is None else environ
    home=Path.home() if home is None else Path(home)
    if system == 'nt':
        return Path(environ.get('APPDATA') or home/'AppData'/'Roaming')/'VANTA'
    return Path(environ.get('XDG_DATA_HOME') or home/'.local/share')/'vanta'
DATA=data_directory()
DATA.mkdir(parents=True,exist_ok=True); DB=DATA/'vanta.sqlite3'
def connect():
    c=sqlite3.connect(DB,timeout=10);c.row_factory=sqlite3.Row;return c
@contextmanager
def db():
    c=connect()
    try:
        yield c;c.commit()
    except Exception:
        c.rollback();raise
    finally:c.close()
with db() as c:
    c.execute('''CREATE TABLE IF NOT EXISTS competitions(id TEXT PRIMARY KEY,name TEXT NOT NULL,description TEXT NOT NULL DEFAULT '',category TEXT NOT NULL,organizer TEXT NOT NULL DEFAULT '',website TEXT NOT NULL DEFAULT '',registrationUrl TEXT NOT NULL DEFAULT '',start TEXT NOT NULL,end TEXT NOT NULL DEFAULT '',deadline TEXT NOT NULL DEFAULT '',timezone TEXT NOT NULL,status TEXT NOT NULL,priority TEXT NOT NULL,notes TEXT NOT NULL DEFAULT '',created TEXT NOT NULL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS notifications(key TEXT PRIMARY KEY,sent_at TEXT NOT NULL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL)''')
    c.execute('INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)',('reminders',json.dumps({'7d':True,'3d':True,'1d':True,'1h':True,'customHours':0})))
def events():
    with db() as c:return [dict(r) for r in c.execute('SELECT * FROM competitions ORDER BY start')]
class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*a,**kw):super().__init__(*a,directory=str(ROOT/'dist' if (ROOT/'dist').exists() else ROOT),**kw)
    def log_message(self,*a):pass
    def end_headers(self):
        if urlparse(self.path).path in ('/','/index.html'):self.send_header('Cache-Control','no-store, max-age=0')
        super().end_headers()
    def send_json(self,data,status=200):
        raw=json.dumps(data).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(raw)));self.send_header('Access-Control-Allow-Origin','http://127.0.0.1:8765');self.end_headers();self.wfile.write(raw)
    def do_OPTIONS(self):self.send_response(204);self.send_header('Access-Control-Allow-Origin','http://127.0.0.1:8765');self.send_header('Access-Control-Allow-Methods','GET,POST,PUT,PATCH,DELETE,OPTIONS');self.send_header('Access-Control-Allow-Headers','Content-Type');self.end_headers()
    def do_GET(self):
        if self.path=='/api/events':return self.send_json(events())
        if self.path=='/api/settings':
            with db() as c:r=c.execute('SELECT value FROM settings WHERE key="reminders"').fetchone()
            return self.send_json(json.loads(r['value']) if r else {})
        return super().do_GET()
    def do_POST(self):
        if self.path!='/api/events':return self.send_error(404)
        try:
            e=json.loads(self.rfile.read(int(self.headers.get('Content-Length',0))));required=['id','name','category','start','timezone','status','priority','created']
            if any(not e.get(k) for k in required):return self.send_json({'error':'Missing required fields'},400)
            with db() as c:c.execute('INSERT OR REPLACE INTO competitions(id,name,description,category,organizer,website,registrationUrl,start,end,deadline,timezone,status,priority,notes,created) VALUES(:id,:name,:description,:category,:organizer,:website,:registrationUrl,:start,:end,:deadline,:timezone,:status,:priority,:notes,:created)',{k:e.get(k,'') for k in ['id','name','description','category','organizer','website','registrationUrl','start','end','deadline','timezone','status','priority','notes','created']})
            return self.send_json(e,201)
        except Exception as ex:return self.send_json({'error':str(ex)},400)
    def do_PUT(self):return self.do_POST()
    def do_PATCH(self):
        if self.path!='/api/settings':return self.send_error(404)
        try:
            prefs=json.loads(self.rfile.read(int(self.headers.get('Content-Length',0))))
            prefs={k:v for k,v in prefs.items() if k in ('7d','3d','1d','1h','customHours')}
            with db() as c:c.execute('INSERT OR REPLACE INTO settings(key,value) VALUES("reminders",?)',(json.dumps(prefs),))
            return self.send_json(prefs)
        except Exception as ex:return self.send_json({'error':str(ex)},400)
    def do_DELETE(self):
        ident=urlparse(self.path).path.removeprefix('/api/events/')
        with db() as c:c.execute('DELETE FROM competitions WHERE id=?',(ident,))
        return self.send_json({'ok':True})
def notify(title,body,key,system=None):
    if (system or os.name) == 'nt':
        try:
            from winotify import Notification
        except ImportError:
            return
        show=lambda: Notification(app_id='VANTA Competition Tracker',title=title,msg=body).show()
    else:
        command=shutil.which('notify-send')
        if not command or not os.environ.get('DBUS_SESSION_BUS_ADDRESS'):return
        import subprocess
        show=lambda: subprocess.Popen([command,'--app-name=VANTA','--icon=dialog-information',title,body],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    with db() as c:
        if c.execute('SELECT 1 FROM notifications WHERE key=?',(key,)).fetchone():return
        c.execute('INSERT INTO notifications VALUES(?,?)',(key,datetime.now(timezone.utc).isoformat()))
    show()
def notification_loop():
    # Check once per minute; keyed by event, type, and reminder window to avoid duplicates.
    while True:
        try:
            now=datetime.now(timezone.utc)
            for e in events():
                if e['status'] in ('Completed','Cancelled'):continue
                for field,label in [('start','starts'),('deadline','registration closes')]:
                    if not e[field]:continue
                    try:target=datetime.fromisoformat(e[field].replace('Z','+00:00'));target=target.replace(tzinfo=timezone.utc) if target.tzinfo is None else target.astimezone(timezone.utc)
                    except ValueError:continue
                    delta=(target-now).total_seconds()
                    with db() as c:r=c.execute('SELECT value FROM settings WHERE key="reminders"').fetchone()
                    prefs=json.loads(r['value']) if r else {}
                    windows=[(604800,'7d'),(259200,'3d'),(86400,'1d'),(3600,'1h')]
                    custom=int(prefs.get('customHours',0) or 0)
                    if custom>0:windows.append((custom*3600,f'{custom}h'))
                    for seconds,tag in windows:
                        if prefs.get(tag,tag==f'{custom}h') and seconds-60<delta<=seconds:notify(f'{e["name"]} {label}',f'{tag} remaining · {target.astimezone().strftime("%a %d %b, %H:%M")}',f'{e["id"]}:{field}:{tag}')
        except Exception as ex:print('VANTA reminder service:',ex,flush=True)
        time.sleep(60)
if __name__=='__main__':
    threading.Thread(target=notification_loop,daemon=True).start()
    print(f'VANTA local service · SQLite: {DB} · http://127.0.0.1:8765',flush=True)
    ThreadingHTTPServer(('127.0.0.1',8765),Handler).serve_forever()
