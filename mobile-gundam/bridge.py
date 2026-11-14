#!/usr/bin/env python3
"""Mobile Gundam relay and Codex/agent CLI. Python 3.10+, no dependencies."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import quote, unquote, urlsplit, parse_qs
from urllib.request import Request, urlopen
from urllib.error import HTTPError

DATA = Path(os.environ.get('GUNDAM_DATA', './gundam-data')).resolve()
DB = DATA / 'relay.sqlite3'
MAX_FILE = int(os.environ.get('GUNDAM_MAX_FILE', str(256 * 1024 * 1024)))
MAX_JSON = 128 * 1024
SESSION = re.compile(r'^[0-9a-f]{24}$')
IDENT = re.compile(r'^[0-9a-f]{32}$')

def db():
    DATA.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB, timeout=30)
    con.row_factory = sqlite3.Row
    con.execute('PRAGMA busy_timeout=30000')
    return con

def initialize():
    with db() as con:
        con.executescript('''
            CREATE TABLE IF NOT EXISTS sessions(
                id TEXT PRIMARY KEY, phone_hash TEXT NOT NULL, agent_hash TEXT NOT NULL,
                created INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS events(
                id INTEGER PRIMARY KEY AUTOINCREMENT, session TEXT NOT NULL, origin TEXT NOT NULL,
                kind TEXT NOT NULL, payload TEXT NOT NULL, created INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS commands(
                id INTEGER PRIMARY KEY AUTOINCREMENT, session TEXT NOT NULL,
                kind TEXT NOT NULL, payload TEXT NOT NULL, created INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS files(
                id TEXT PRIMARY KEY, session TEXT NOT NULL, origin TEXT NOT NULL,
                name TEXT NOT NULL, sha256 TEXT NOT NULL, size INTEGER NOT NULL, created INTEGER NOT NULL);
            CREATE INDEX IF NOT EXISTS events_session_id ON events(session,id);
            CREATE INDEX IF NOT EXISTS commands_session_id ON commands(session,id);
        ''')

def sha(s):
    return hashlib.sha256(s.encode()).hexdigest()

def new_session():
    sid, phone, agent = secrets.token_hex(12), secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    with db() as con:
        con.execute('INSERT INTO sessions VALUES (?,?,?,?)', (sid,sha(phone),sha(agent),int(time.time())))
    return {'session':sid,'phone_token':phone,'agent_token':agent}

class Handler(BaseHTTPRequestHandler):
    server_version = 'MobileGundam/0.1'
    def log_message(self, fmt, *args):
        sys.stderr.write('%s %s\n' % (self.address_string(),fmt%args))
    def answer(self, status, obj):
        payload=json.dumps(obj,ensure_ascii=False,separators=(',',':')).encode()
        self.send_response(status)
        self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Content-Length',str(len(payload)))
        self.send_header('Cache-Control','no-store')
        self.end_headers()
        self.wfile.write(payload)
    def error(self,status,message):
        self.answer(status,{'error':message})
    def auth(self,sid):
        header=self.headers.get('Authorization','')
        if not header.startswith('Bearer '): return None
        token=sha(header[7:])
        with db() as con:
            record=con.execute('SELECT * FROM sessions WHERE id=?',(sid,)).fetchone()
        if not record: return None
        if secrets.compare_digest(token,record['phone_hash']): return 'phone'
        if secrets.compare_digest(token,record['agent_hash']): return 'agent'
        return None
    def body(self,limit=MAX_JSON):
        try: length=int(self.headers.get('Content-Length','-1'))
        except ValueError: return None
        if length<0 or length>limit: return None
        return self.rfile.read(length)
    def json_body(self):
        content=self.body()
        if content is None: return None
        try:
            obj=json.loads(content)
            return obj if isinstance(obj,dict) else None
        except (ValueError,UnicodeDecodeError): return None
    def route(self):
        u=urlsplit(self.path)
        parts=[unquote(x) for x in u.path.strip('/').split('/')]
        if u.path=='/health': return ('health',None,None,parse_qs(u.query))
        if u.path=='/v1/pair': return ('pair',None,None,{})
        if len(parts)<4 or parts[:2]!=['v1','s'] or not SESSION.fullmatch(parts[2]):
            return None
        sid=parts[2]
        if len(parts)==4 and parts[3] in ('events','commands','files'):
            return parts[3],sid,None,parse_qs(u.query)
        if len(parts)==5 and parts[3]=='files' and IDENT.fullmatch(parts[4]):
            return 'file',sid,parts[4],{}
        return None
    def do_GET(self):
        route=self.route()
        if not route: return self.error(404,'not found')
        resource,sid,fid,query=route
        if resource=='health': return self.answer(200,{'status':'ok'})
        role=self.auth(sid)
        if not role: return self.error(401,'unauthorized')
        if resource in ('events','commands'):
            if resource=='commands' and role!='phone':return self.error(403,'phone only')
            try: after=max(0,int(query.get('after',['0'])[0]))
            except ValueError: return self.error(400,'invalid cursor')
            with db() as con:
                rows=con.execute(f'SELECT * FROM {resource} WHERE session=? AND id>? ORDER BY id LIMIT 100',(sid,after)).fetchall()
            return self.answer(200,{'items':[dict(r) | {'payload':json.loads(r['payload'])} for r in rows]})
        if resource=='files':
            with db() as con:
                rows=con.execute('SELECT id,name,origin,sha256,size,created FROM files WHERE session=? ORDER BY created DESC LIMIT 200',(sid,)).fetchall()
            return self.answer(200,{'items':[dict(r) for r in rows]})
        if resource=='file':
            with db() as con:
                record=con.execute('SELECT * FROM files WHERE session=? AND id=?',(sid,fid)).fetchone()
            if not record:return self.error(404,'not found')
            path=DATA/'blobs'/sid/fid
            if not path.is_file():return self.error(404,'blob missing')
            self.send_response(200)
            self.send_header('Content-Type','application/octet-stream')
            self.send_header('Content-Length',str(record['size']))
            self.send_header('X-SHA256',record['sha256'])
            self.send_header('Content-Disposition',f"attachment; filename*=UTF-8''{quote(record['name'])}")
            self.send_header('Cache-Control','no-store')
            self.end_headers()
            with open(path,'rb') as source:
                while chunk:=source.read(1024*1024):self.wfile.write(chunk)
            return
        return self.error(404,'not found')
    def do_POST(self):
        route=self.route()
        if not route:return self.error(404,'not found')
        resource,sid,_,_=route
        if resource=='pair':
            expected=os.environ.get('GUNDAM_ADMIN_TOKEN')
            provided=self.headers.get('Authorization','')
            if not expected or not secrets.compare_digest(provided,'Bearer '+expected):
                return self.error(401,'admin token required')
            return self.answer(201,new_session())
        role=self.auth(sid)
        if not role:return self.error(401,'unauthorized')
        if resource in ('events','commands'):
            if resource=='commands' and role!='agent':return self.error(403,'agent only')
            payload=self.json_body()
            if payload is None:return self.error(400,'JSON object required')
            kind=payload.get('kind','message')
            if not isinstance(kind,str) or not re.fullmatch(r'[\w.-]{1,64}',kind):
                return self.error(400,'invalid kind')
            now=int(time.time())
            if resource=='events':
                with db() as con:
                    cur=con.execute('INSERT INTO events(session,origin,kind,payload,created) VALUES (?,?,?,?,?)',
                        (sid,role,kind,json.dumps(payload,ensure_ascii=False),now))
            else:
                with db() as con:
                    cur=con.execute('INSERT INTO commands(session,kind,payload,created) VALUES (?,?,?,?)',
                        (sid,kind,json.dumps(payload,ensure_ascii=False),now))
            return self.answer(201,{'id':cur.lastrowid})
        if resource=='files':
            try: length=int(self.headers.get('Content-Length','-1'))
            except ValueError: length=-1
            if length<0 or length>MAX_FILE:return self.error(413,'invalid file size')
            name=unquote(self.headers.get('X-File-Name','unnamed'))
            name=re.sub(r'[\\/\x00-\x1f]','_',name).strip()[:180] or 'unnamed'
            fid=secrets.token_hex(16)
            directory=DATA/'blobs'/sid
            directory.mkdir(parents=True,exist_ok=True)
            path=directory/fid
            checksum=hashlib.sha256()
            try:
                with path.open('xb') as out:
                    left=length
                    while left:
                        chunk=self.rfile.read(min(left,1024*1024))
                        if not chunk:raise ConnectionError('incomplete upload')
                        out.write(chunk);checksum.update(chunk);left-=len(chunk)
                with db() as con:
                    con.execute('INSERT INTO files VALUES (?,?,?,?,?,?,?)',
                        (fid,sid,role,name,checksum.hexdigest(),length,int(time.time())))
                    con.execute('INSERT INTO events(session,origin,kind,payload,created) VALUES (?,?,?,?,?)',
                        (sid,role,'file',json.dumps({'kind':'file','id':fid,'name':name,'size':length,'sha256':checksum.hexdigest()}),int(time.time())))
            except Exception:
                path.unlink(missing_ok=True)
                raise
            return self.answer(201,{'id':fid,'name':name,'size':length,'sha256':checksum.hexdigest()})
        return self.error(404,'not found')

def request(server,token,method,path,data=None,headers=None):
    h={'Authorization':'Bearer '+token}
    h.update(headers or {})
    req=Request(server.rstrip('/')+path,data=data,method=method,headers=h)
    try:
        with urlopen(req,timeout=60) as resp:
            raw=resp.read()
            if resp.headers.get('Content-Type','').startswith('application/json'):return json.loads(raw)
            return raw
    except HTTPError as e:
        raise RuntimeError(f'HTTP {e.code}: {e.read().decode(errors="replace")}') from None

def cli():
    p=argparse.ArgumentParser(description='Mobile Gundam relay and agent CLI')
    sub=p.add_subparsers(dest='cmd',required=True)
    serve=sub.add_parser('serve');serve.add_argument('--host',default='127.0.0.1');serve.add_argument('--port',type=int,default=8765)
    pair=sub.add_parser('pair');pair.add_argument('--server',required=True);pair.add_argument('--admin-token',required=True)
    for operation in ('events','commands','files','send','post','download'):
        t=sub.add_parser(operation);t.add_argument('--server',required=True);t.add_argument('--session',required=True);t.add_argument('--token',required=True)
        if operation in ('events','commands'):t.add_argument('--after',type=int,default=0)
        if operation=='send':t.add_argument('path')
        if operation=='post':t.add_argument('kind');t.add_argument('message')
        if operation=='download':t.add_argument('id');t.add_argument('output')
    a=p.parse_args()
    if a.cmd=='serve':
        initialize();http=ThreadingHTTPServer((a.host,a.port),Handler)
        print(f'Gundam relay on http://{a.host}:{a.port}; serve over HTTPS for remote use',flush=True)
        try:http.serve_forever()
        except KeyboardInterrupt:pass
        return
    if a.cmd=='pair':
        result=request(a.server,a.admin_token,'POST','/v1/pair',b'')
        print(json.dumps(result,indent=2));return
    root=f'/v1/s/{a.session}'
    if a.cmd in ('events','commands','files'):
        qs='?after='+str(a.after) if a.cmd in ('events','commands') else ''
        print(json.dumps(request(a.server,a.token,'GET',root+'/'+a.cmd+qs),indent=2,ensure_ascii=False))
    elif a.cmd=='send':
        path=Path(a.path)
        if path.stat().st_size>MAX_FILE:raise ValueError('file exceeds configured limit')
        print(json.dumps(request(a.server,a.token,'POST',root+'/files',path.read_bytes(),{'X-File-Name':quote(path.name)}),indent=2))
    elif a.cmd=='post':
        payload={'kind':a.kind,'message':a.message}
        print(json.dumps(request(a.server,a.token,'POST',root+'/events',json.dumps(payload).encode(),{'Content-Type':'application/json'})))
    elif a.cmd=='download':
        path=Path(a.output)
        if path.exists():raise FileExistsError(path)
        raw=request(a.server,a.token,'GET',root+'/files/'+a.id)
        path.write_bytes(raw)
        print(f'Wrote {path} ({len(raw)} bytes)')

if __name__=='__main__':cli()