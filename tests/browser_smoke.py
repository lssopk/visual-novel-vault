import os,sys,tempfile,subprocess,time
from pathlib import Path
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1]
tmp=tempfile.TemporaryDirectory();env={**os.environ,'DB_PATH':tmp.name+'/db.sqlite3','PORT':'16100'}
subprocess.run([sys.executable,'manage.py','init-admin','--password-stdin'],input='testing-password-1234\n',text=True,cwd=root,env=env,check=True,capture_output=True)
subprocess.run([sys.executable,'manage.py','seed-demo'],cwd=root,env=env,check=True,capture_output=True)
p=subprocess.Popen([sys.executable,'server.py'],cwd=root,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
try:
 with sync_playwright() as pw:
  browser=pw.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox'])
  for name,viewport in [('desktop',{'width':1440,'height':900}),('mobile',{'width':390,'height':844})]:
   page=browser.new_page(viewport=viewport,device_scale_factor=1)
   page.goto('http://127.0.0.1:16100/',wait_until='networkidle')
   page.locator('#password').fill('testing-password-1234')
   page.locator('#loginForm button[type=submit]').click()
   page.get_by_text('海猫鸣泣之时').first.wait_for(timeout=5000)
   page.locator('[data-chapter="demo-ep1"]').click()
   page.get_by_text('章节概览与阅读提示').wait_for(timeout=5000)
   if name=='mobile':
    page.locator('.mobile-tabs [data-tab="timeline"]').click()
    page.get_by_text('事件时间线').first.wait_for(timeout=5000)
    page.locator('.mobile-tabs [data-tab="characters"]').click()
   else:
    page.locator('.tabbar [data-tab="timeline"]').click()
    page.get_by_text('魔女来信').wait_for(timeout=5000)
   page.screenshot(path=str(root/'docs'/f'{name}.png'),full_page=True)
   print(name,'PASS', 'overflow',page.evaluate('document.documentElement.scrollWidth > window.innerWidth'))
   page.close()
  browser.close()
finally:
 p.terminate();p.wait(timeout=5);tmp.cleanup()
