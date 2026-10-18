#!/usr/bin/env python3
import argparse, hashlib, json, secrets, sys, getpass
from db import connect, init, now

def hash_password(password, salt=None):
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(),salt=salt,n=2**14,r=8,p=1,dklen=32)
    return salt.hex()+':'+digest.hex()

def main():
    p=argparse.ArgumentParser(description='个人视觉小说档案馆管理工具')
    sub=p.add_subparsers(dest='command',required=True)
    a=sub.add_parser('init-admin',help='设置/重置管理密码')
    a.add_argument('--password-stdin',action='store_true')
    k=sub.add_parser('create-key',help='创建 Codex/自动化 API 密钥')
    k.add_argument('--name',required=True)
    k.add_argument('--scopes',default='games:read,games:write,chapters:read,chapters:write,entries:read,entries:write,characters:read,characters:write,links:read,links:write,theories:read,theories:write,progress:write')
    r=sub.add_parser('revoke-key',help='撤销 API 密钥'); r.add_argument('id')
    sub.add_parser('list-keys',help='列出密钥元信息，不显示密钥')
    sub.add_parser('seed-demo',help='创建可删除的 EP1 演示资料')
    args=p.parse_args(); init()
    with connect() as db:
        if args.command=='init-admin':
            pw=sys.stdin.readline().rstrip('\r\n') if args.password_stdin else getpass.getpass('设置管理密码：')
            if len(pw)<12: raise SystemExit('密码至少12个字符')
            db.execute('INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',('admin_password',hash_password(pw)))
            db.execute('DELETE FROM sessions')
            print('管理密码已设置，旧登录会话已失效。')
        elif args.command=='create-key':
            allowed={'games:read','games:write','chapters:read','chapters:write','entries:read','entries:write','characters:read','characters:write','links:read','links:write','theories:read','theories:write','progress:write'}
            scopes=set(s.strip() for s in args.scopes.split(','))
            if not scopes or not scopes.issubset(allowed): raise SystemExit('无效权限范围')
            kid='key_'+secrets.token_hex(6); token='vnv_'+secrets.token_urlsafe(32)
            db.execute('INSERT INTO api_keys(id,name,token_hash,scopes,created_at) VALUES(?,?,?,?,?)',(kid,args.name,hashlib.sha256(token.encode()).hexdigest(),','.join(sorted(scopes)),now()))
            print('KEY_ID='+kid+'\nAPI_TOKEN='+token+'\n请立即保存密钥：之后无法再次显示。')
        elif args.command=='revoke-key':
            db.execute('UPDATE api_keys SET revoked=1 WHERE id=?',(args.id,)); print('已撤销（若存在）。')
        elif args.command=='list-keys':
            for row in db.execute('SELECT id,name,scopes,created_at,revoked FROM api_keys ORDER BY created_at DESC'): print(dict(row))
        elif args.command=='seed-demo':
            if db.execute("SELECT 1 FROM games WHERE id='demo-umineko'").fetchone(): print('演示已存在'); return
            db.execute("INSERT INTO games(id,title,description,genre,created_at,updated_at) VALUES(?,?,?,?,?,?)",('demo-umineko','海猫鸣泣之时','仅包含你已经完成的 EP1 示例；其余章节由你逐步建立。','悬疑 · 推理',now(),now()))
            db.execute('INSERT INTO chapters(id,game_id,number,title,overview,caution,unlocked,updated_at) VALUES(?,?,?,?,?,?,?,?)',('demo-ep1','demo-umineko',1,'EP1 · 黄金魔女的传说','六轩岛家族会议与连续事件的调查档案。','区分人物证言与已验证的事实。',1,now()))
            for i,(kind,title,body) in enumerate([('summary','调查概览','右代宫家族齐聚六轩岛，围绕遗产展开争论。'),('event','魔女来信','署名贝阿朵莉切的信件出现。'),('evidence','碑文','记录碑文与事件的对应关系，暂不认定因果。'),('tip','推理提示','把目击、转述、猜想分开标注。')]):
                db.execute('INSERT INTO entries(id,chapter_id,kind,title,body,position,updated_at) VALUES(?,?,?,?,?,?,?)',(f'demo-entry-{i}','demo-ep1',kind,title,body,i,now()))
            print('EP1 示例已创建，可在界面删除或修改。')
if __name__=='__main__':main()
