import os, sys, tempfile, subprocess, time, json, urllib.request, urllib.error
from pathlib import Path
root=Path(__file__).resolve().parents[1]
tmp=tempfile.TemporaryDirectory();env={**os.environ,'DB_PATH':tmp.name+'/vault.sqlite3','PORT':'16099'}
subprocess.run([sys.executable,'manage.py','init-admin','--password-stdin'],input='very-long-test-password\n',text=True,cwd=root,env=env,check=True,capture_output=True)
key_out=subprocess.check_output([sys.executable,'manage.py','create-key','--name','test','--scopes','games:read,games:write,chapters:read,chapters:write,entries:read,entries:write'],cwd=root,env=env,text=True)
token=[x[10:] for x in key_out.splitlines() if x.startswith('API_TOKEN=')][0]
proc=subprocess.Popen([sys.executable,'server.py'],cwd=root,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
base='http://127.0.0.1:16099'
def request(method,path,data=None,token_=token,expected=200):
    headers={'Authorization':'Bearer '+token_,'Content-Type':'application/json'} if token_ else {'Content-Type':'application/json'}
    req=urllib.request.Request(base+path,data=json.dumps(data).encode() if data is not None else None,headers=headers,method=method)
    try:
        with urllib.request.urlopen(req,timeout=5) as r:code=r.status;body=json.loads(r.read())
    except urllib.error.HTTPError as e:code=e.code;body=json.loads(e.read())
    assert code==expected,(path,code,body,expected)
    return body
try:
    for i in range(30):
        try:request('GET','/api/v1/health',token_=None);break
        except Exception:time.sleep(.1)
    request('GET','/api/v1/games',token_=None,expected=401)
    game=request('POST','/api/v1/games',{'title':'测试游戏','genre':'悬疑'},expected=201)
    assert len(request('GET','/api/v1/games')['items'])==1
    ch=request('POST','/api/v1/chapters',{'game_id':game['id'],'number':1,'title':'第一章','overview':'秘密内容'},expected=201)
    ent=request('POST','/api/v1/entries',{'chapter_id':ch['id'],'kind':'evidence','title':'隐藏证据','body':'隐藏的内容'},expected=201)
    assert len(request('GET','/api/v1/entries?chapter_id='+ch['id'])['items'])==1
    # cookie based admin: login, check locked access
    opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor())
    req=urllib.request.Request(base+'/api/v1/auth/login',data=json.dumps({'password':'very-long-test-password'}).encode(),headers={'Content-Type':'application/json','Origin':base},method='POST')
    with opener.open(req) as r:login=json.loads(r.read())
    def admin(method,path,data=None,expected=200):
        req=urllib.request.Request(base+path,data=json.dumps(data).encode() if data is not None else None,headers={'Content-Type':'application/json','Origin':base,'X-CSRF-Token':login['csrf']},method=method)
        try:
            with opener.open(req) as r:code=r.status;body=json.loads(r.read())
        except urllib.error.HTTPError as e:code=e.code;body=json.loads(e.read())
        assert code==expected,(path,code,body)
        return body
    assert admin('GET','/api/v1/chapters/'+ch['id'])['unlocked']==0
    admin('GET','/api/v1/entries?chapter_id='+ch['id'],expected=423)
    admin('POST','/api/v1/chapters/'+ch['id']+'/unlock',{'confirmation':'EP2'},expected=400)
    admin('POST','/api/v1/chapters/'+ch['id']+'/unlock',{'confirmation':'EP1'})
    assert len(admin('GET','/api/v1/entries?chapter_id='+ch['id'])['items'])==1
    request('PATCH','/api/v1/entries/'+ent['id'],{'body':'更新后'},expected=200)
    request('DELETE','/api/v1/entries/'+ent['id'])
    assert not request('GET','/api/v1/entries?chapter_id='+ch['id'])['items']
    # SQL/XSS payload stored as plain text
    x=request('POST','/api/v1/entries',{'chapter_id':ch['id'],'kind':'note','title':'<script>alert(1)</script>','body':'text'},expected=201)
    assert x['title']=='<script>alert(1)</script>'
    print('PASS: health, authentication, CRUD, locked-content 423, explicit unlock, content escaping fixture')
finally:
    proc.terminate();proc.wait(timeout=5);tmp.cleanup()
