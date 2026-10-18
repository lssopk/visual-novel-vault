#!/usr/bin/env python3
import os, json, re, secrets, hashlib, hmac, mimetypes, time, threading
from pathlib import Path
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from http.cookies import SimpleCookie
from db import connect, init, now, audit

PORT=int(os.environ.get('PORT','6099'))
STATIC=Path(__file__).resolve().parent/'public'
MAX_BODY=262144
KINDS={'summary','event','evidence','note','tip'}
CONFIDENCES={'confirmed','reported','inferred','unverified'}
LIMITS={'title':180,'body':30000,'overview':30000,'description':2000,'caution':3000,'name':120,'label':120,'source':300,'happened_at':100,'claim':20000,'support':20000,'counter':20000,'bio':8000,'original_title':180,'genre':200}
FAILED={}
LOCK=threading.Lock()

def uid(prefix): return prefix+'_'+secrets.token_hex(9)
def rows(cursor): return [dict(x) for x in cursor.fetchall()]
def one(db, sql, args=()):
    r=db.execute(sql,args).fetchone()
    return dict(r) if r else None

def sanitize(body, keys):
    out={}
    for k in keys:
        if k not in body: continue
        v=body[k]
        if k in ('number','first_chapter','position'):
            if type(v)!=int or not (0<=v<=9999): raise ValueError(k+' 必须是有效整数')
        elif k=='unlocked':
            if type(v)!=bool: raise ValueError('unlocked 必须是布尔值')
            v=int(v)
        elif k in ('kind','confidence','status'):
            if not isinstance(v,str) or (k=='kind' and v not in KINDS) or (k=='confidence' and v not in CONFIDENCES) or (k=='status' and v not in {'open','supported','disputed','closed'}): raise ValueError(k+' 不合法')
        else:
            if not isinstance(v,str) or len(v)>LIMITS.get(k,1000): raise ValueError(k+' 长度或类型不合法')
            v=v.strip()
        out[k]=v
    return out

class App(BaseHTTPRequestHandler):
    server_version='NovelVault/1.0'
    def log_message(self, fmt, *args): print('%s %s'%(self.address_string(),fmt%args),flush=True)
    def headers_common(self, code=200, content_type='application/json; charset=utf-8'):
        self.send_response(code)
        self.send_header('Content-Type',content_type)
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('X-Frame-Options','DENY')
        self.send_header('Referrer-Policy','no-referrer')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
        self.send_header('Cache-Control','no-store')
    def send_json(self, obj, code=200, cookie=None):
        data=json.dumps(obj,ensure_ascii=False,separators=(',',':')).encode()
        self.headers_common(code)
        if cookie: self.send_header('Set-Cookie',cookie)
        self.send_header('Content-Length',str(len(data)))
        self.end_headers(); self.wfile.write(data)
    def err(self, code, msg): self.send_json({'error':msg},code)
    def body(self):
        size=int(self.headers.get('Content-Length','0'))
        if size<0 or size>MAX_BODY: raise ValueError('请求体超出限制')
        if self.headers.get('Content-Type','').split(';')[0]!='application/json': raise ValueError('仅接受 application/json')
        raw=self.rfile.read(size)
        obj=json.loads(raw)
        if not isinstance(obj,dict): raise ValueError('JSON 必须是对象')
        return obj
    def auth(self, db):
        bearer=self.headers.get('Authorization','')
        if bearer.startswith('Bearer vnv_'):
            token=bearer[7:]
            key=one(db,'SELECT id,name,scopes FROM api_keys WHERE token_hash=? AND revoked=0',(hashlib.sha256(token.encode()).hexdigest(),))
            if key: return {'actor':key['id'],'key':True,'scopes':set(key['scopes'].split(','))}
            return None
        cookie=SimpleCookie()
        try: cookie.load(self.headers.get('Cookie',''))
        except Exception: return None
        if 'nv_session' not in cookie:return None
        token=cookie['nv_session'].value
        session=one(db,'SELECT csrf,expires FROM sessions WHERE token_hash=?',(hashlib.sha256(token.encode()).hexdigest(),))
        if session and session['expires']>now():return {'actor':'admin','key':False,'csrf':session['csrf'],'scopes':{'*'}}
        return None
    def check(self,auth,scope): return '*' in auth['scopes'] or scope in auth['scopes']
    def csrf_ok(self,auth):
        if auth['key']:return True
        origin=self.headers.get('Origin','')
        if not origin: return False
        host=self.headers.get('Host','')
        if urlparse(origin).netloc!=host: return False
        return hmac.compare_digest(self.headers.get('X-CSRF-Token',''),auth['csrf'])
    def is_locked(self,db,auth,chapter_id):
        ch=one(db,'SELECT * FROM chapters WHERE id=?',(chapter_id,))
        if not ch:return None
        if not auth['key'] and not ch['unlocked']:return 'locked'
        return ch
    def serve_static(self, path):
        target={'/':'index.html','/api-docs':'api-docs.html'}.get(path,path.lstrip('/'))
        resolved=(STATIC/target).resolve()
        if not resolved.is_relative_to(STATIC) or not resolved.is_file():return self.err(404,'页面不存在')
        data=resolved.read_bytes()
        typ=mimetypes.guess_type(str(resolved))[0] or 'application/octet-stream'
        self.headers_common(200,typ+'; charset=utf-8' if typ.startswith('text/') or typ in ('application/javascript','application/json') else typ)
        self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
    def do_GET(self): self.handle_route('GET')
    def do_POST(self): self.handle_route('POST')
    def do_PATCH(self): self.handle_route('PATCH')
    def do_DELETE(self): self.handle_route('DELETE')
    def handle_route(self,method):
        path=urlparse(self.path).path
        if not path.startswith('/api/'):
            if method!='GET':return self.err(405,'Method not allowed')
            return self.serve_static(path)
        if path=='/api/v1/health':return self.send_json({'status':'ok','version':'1.0'})
        if path=='/api/v1/openapi.json' and method=='GET':return self.serve_static('/openapi.json')
        try:
            with connect() as db:
                if path=='/api/v1/auth/login' and method=='POST':
                    addr=self.client_address[0]
                    with LOCK:
                        state=FAILED.get(addr,(0,0))
                        if state[0]>=8 and time.time()-state[1]<900:return self.err(429,'尝试次数过多，请稍后再试')
                    body=self.body();pw=body.get('password','')
                    stored=one(db,"SELECT value FROM settings WHERE key='admin_password'")
                    if not stored:return self.err(503,'尚未初始化管理密码，请运行 ./deploy.sh')
                    salt,expected=stored['value'].split(':')
                    actual=hashlib.scrypt(str(pw).encode(),salt=bytes.fromhex(salt),n=2**14,r=8,p=1,dklen=32)
                    if not hmac.compare_digest(actual,bytes.fromhex(expected)):
                        with LOCK:FAILED[addr]=(state[0]+1,time.time())
                        return self.err(401,'密码错误')
                    with LOCK:FAILED.pop(addr,None)
                    token=secrets.token_urlsafe(32);csrf=secrets.token_urlsafe(32)
                    db.execute('INSERT INTO sessions VALUES(?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),csrf,now()+86400*7))
                    secure='; Secure' if os.environ.get('PUBLIC_HTTPS','0')=='1' else ''
                    db.commit()
                    return self.send_json({'ok':True,'csrf':csrf},cookie=f'nv_session={token}; Path=/; HttpOnly; SameSite=Strict; Max-Age=604800{secure}')
                auth=self.auth(db)
                if not auth:return self.err(401,'请先登录或提供 API Token')
                if path=='/api/v1/auth/me' and method=='GET':return self.send_json({'authenticated':True,'actor':auth['actor'],'csrf':auth.get('csrf'),'api_key':auth['key']})
                if method!='GET' and not self.csrf_ok(auth):return self.err(403,'CSRF 校验失败')
                if path=='/api/v1/auth/logout' and method=='POST':
                    if not auth['key']:
                        cookie=SimpleCookie();cookie.load(self.headers.get('Cookie',''))
                        if 'nv_session' in cookie:db.execute('DELETE FROM sessions WHERE token_hash=?',(hashlib.sha256(cookie['nv_session'].value.encode()).hexdigest(),))
                    db.commit()
                    return self.send_json({'ok':True},cookie='nv_session=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0')
                return self.route(db,auth,method,path)
        except (ValueError,KeyError,json.JSONDecodeError) as e:return self.err(400,str(e))
        except Exception as e:
            print('ERROR',type(e).__name__,str(e),flush=True)
            return self.err(500,'服务器处理失败')
    def route(self,db,auth,method,path):
        m=re.fullmatch(r'/api/v1/(games|chapters|entries|characters|links|theories)(?:/([A-Za-z0-9_-]+))?',path)
        if m:
            resource,oid=m.groups()
            scope=resource+(':read' if method=='GET' else ':write')
            if not self.check(auth,scope):return self.err(403,'缺少权限 '+scope)
            return self.resource(db,auth,method,resource,oid)
        m=re.fullmatch(r'/api/v1/chapters/([A-Za-z0-9_-]+)/unlock',path)
        if m and method=='POST':
            if not self.check(auth,'progress:write'):return self.err(403,'缺少 progress:write 权限')
            ch=one(db,'SELECT * FROM chapters WHERE id=?',(m[1],))
            if not ch:return self.err(404,'章节不存在')
            body=self.body()
            if body.get('confirmation')!=f'EP{ch["number"]}':return self.err(400,'请明确输入对应 EP 编号确认解锁')
            db.execute('UPDATE chapters SET unlocked=1,updated_at=? WHERE id=?',(now(),m[1]))
            audit(db,auth['actor'],'UNLOCK','chapters',m[1]);db.commit();return self.send_json({'ok':True})
        return self.err(404,'API 不存在')
    def resource(self,db,auth,method,r,oid):
        if method=='GET':
            if oid:
                record=one(db,f'SELECT * FROM {r} WHERE id=?',(oid,))
                if not record:return self.err(404,'不存在')
                if r in ('entries','theories') and self.is_locked(db,auth,record['chapter_id'])=='locked':return self.err(423,'该章节尚未解锁')
                if r=='chapters' and not auth['key'] and not record['unlocked']:
                    return self.send_json({'id':record['id'],'game_id':record['game_id'],'number':record['number'],'title':f'第 {record["number"]} 章','unlocked':0})
                return self.send_json(record)
            q=parse_qs(urlparse(self.path).query)
            game_id=q.get('game_id',[None])[0];chapter_id=q.get('chapter_id',[None])[0]
            if r=='games':result=rows(db.execute('SELECT * FROM games ORDER BY updated_at DESC LIMIT 100'))
            elif r=='chapters':
                if not game_id:return self.err(400,'需要 game_id')
                result=rows(db.execute('SELECT * FROM chapters WHERE game_id=? ORDER BY number LIMIT 150',(game_id,)))
                if not auth['key']:
                    result=[x if x['unlocked'] else {'id':x['id'],'game_id':x['game_id'],'number':x['number'],'title':f'第 {x["number"]} 章','unlocked':0} for x in result]
            elif r in ('entries','theories'):
                if not chapter_id:return self.err(400,'需要 chapter_id')
                ch=self.is_locked(db,auth,chapter_id)
                if ch is None:return self.err(404,'章节不存在')
                if ch=='locked':return self.err(423,'该章节尚未解锁')
                result=rows(db.execute(f'SELECT * FROM {r} WHERE chapter_id=? ORDER BY '+('position,updated_at' if r=='entries' else 'updated_at DESC')+' LIMIT 500',(chapter_id,)))
            elif r in ('characters','links'):
                if not game_id:return self.err(400,'需要 game_id')
                max_n=9999 if auth['key'] else (one(db,'SELECT COALESCE(MAX(number),0) AS n FROM chapters WHERE game_id=? AND unlocked=1',(game_id,))['n'])
                result=rows(db.execute(f'SELECT * FROM {r} WHERE game_id=? AND first_chapter<=? ORDER BY first_chapter LIMIT 500',(game_id,max_n)))
            return self.send_json({'items':result})
        schemas={
          'games':(['title'],['title','original_title','description','genre']),
          'chapters':(['game_id','number','title'],['number','title','overview','caution']),
          'entries':(['chapter_id','kind','title'],['kind','title','body','happened_at','source','confidence','position']),
          'characters':(['game_id','name'],['name','bio','first_chapter']),
          'links':(['game_id','source_id','target_id'],['source_id','target_id','label','first_chapter']),
          'theories':(['chapter_id','title'],['title','claim','support','counter','status'])}
        required,editable=schemas[r]
        if method=='DELETE':
            if not oid:return self.err(405,'不支持删除集合')
            row=one(db,f'SELECT id FROM {r} WHERE id=?',(oid,))
            if not row:return self.err(404,'不存在')
            db.execute(f'DELETE FROM {r} WHERE id=?',(oid,))
            audit(db,auth['actor'],'DELETE',r,oid);db.commit();return self.send_json({'ok':True})
        if method not in ('POST','PATCH'):return self.err(405,'不支持的方法')
        if method=='POST' and oid or method=='PATCH' and not oid:return self.err(405,'路径错误')
        body=self.body()
        if method=='POST':
            for k in required:
                if k not in body:return self.err(400,'缺少 '+k)
        data=sanitize(body,editable)
        if r=='chapters' and 'number' in data and data['number']<1:return self.err(400,'章节编号从 1 开始')
        if r in ('characters','links') and 'first_chapter' in data and data['first_chapter']<1:return self.err(400,'首次登场章节从 1 开始')
        if method=='POST' and any(not str(data.get(k,'')).strip() for k in required if k in ('title','name')):return self.err(400,'标题或名称不能为空')
        if method=='POST':
            for k in required:
                if k not in editable:
                    v=body[k]
                    if not isinstance(v,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}',v):return self.err(400,k+' 不合法')
                    data[k]=v
            if r=='chapters' and data['number']<1:return self.err(400,'章节编号从 1 开始')
            if r=='links' and (not one(db,'SELECT id FROM characters WHERE id=? AND game_id=?',(data['source_id'],data['game_id'])) or not one(db,'SELECT id FROM characters WHERE id=? AND game_id=?',(data['target_id'],data['game_id']))):return self.err(400,'关联人物不属于当前游戏')
            if r in ('entries','theories') and not one(db,'SELECT id FROM chapters WHERE id=?',(data['chapter_id'],)):return self.err(400,'章节不存在')
            if r=='chapters' and not one(db,'SELECT id FROM games WHERE id=?',(data['game_id'],)):return self.err(400,'游戏不存在')
            if r=='characters' and not one(db,'SELECT id FROM games WHERE id=?',(data['game_id'],)):return self.err(400,'游戏不存在')
            oid=uid(r[:2]);data['id']=oid
            if r in ('games','chapters','entries','characters','theories'):data['updated_at']=now()
            if r=='games':data['created_at']=now()
            cols=','.join(data);placeholders=','.join('?' for _ in data)
            try:db.execute(f'INSERT INTO {r} ({cols}) VALUES({placeholders})',tuple(data.values()))
            except Exception as e:
                if 'UNIQUE constraint failed' in str(e):return self.err(409,'章节编号已存在')
                raise
            audit(db,auth['actor'],'POST',r,oid)
            db.commit()
            return self.send_json(one(db,f'SELECT * FROM {r} WHERE id=?',(oid,)),201)
        if not one(db,f'SELECT id FROM {r} WHERE id=?',(oid,)):return self.err(404,'不存在')
        if r=='links' and any(x in data for x in ('source_id','target_id')):
            existing=one(db,'SELECT game_id,source_id,target_id FROM links WHERE id=?',(oid,))
            for key in ('source_id','target_id'):
                cid=data.get(key,existing[key])
                if not one(db,'SELECT id FROM characters WHERE id=? AND game_id=?',(cid,existing['game_id'])):return self.err(400,'人物不属于当前游戏')
        if r in ('games','chapters','entries','characters','theories'):data['updated_at']=now()
        if not data:return self.err(400,'没有可更新字段')
        db.execute(f'UPDATE {r} SET '+','.join(f'{k}=?' for k in data)+' WHERE id=?',(*data.values(),oid))
        audit(db,auth['actor'],'PATCH',r,oid)
        db.commit()
        return self.send_json(one(db,f'SELECT * FROM {r} WHERE id=?',(oid,)))

if __name__=='__main__':
    init();httpd=ThreadingHTTPServer(('0.0.0.0',PORT),App)
    print(f'Novel Vault listening on :{PORT}',flush=True)
    httpd.serve_forever()
