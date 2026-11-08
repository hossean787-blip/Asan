# -*- coding: utf-8 -*-
"""Visual/UI test with actual UI code and *mocked API* (Chromium policy blocks localhost)."""
from pathlib import Path
from playwright.sync_api import sync_playwright
import sys,json
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from bank_source import all_questions
import server
HERE=Path(__file__).resolve().parents[1]
PREVIEW=HERE/'previews';PREVIEW.mkdir(exist_ok=True)
html=(HERE/'static/index.html').read_text(encoding='utf-8').replace('<link rel="stylesheet" href="/static/styles.css" />','').replace('<link rel="stylesheet" href="/static/theme-green.css" />','').replace('<script src="/static/app.js" defer></script>','')
style=(HERE/'static/styles.css').read_text(encoding='utf-8')+'\n'+(HERE/'static/theme-green.css').read_text(encoding='utf-8')
js=(HERE/'static/app.js').read_text(encoding='utf-8')
with sync_playwright() as p:
 b=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox','--no-proxy-server'])
 roles=['intern','assistant','accountant']
 exams=[dict(id='test001',candidate='داوطلب نمونه',role='assistant',role_title='کمک‌حسابدار',created_at='2026-11-08T00:00:00+00:00',status='active',answered=23),
  dict(id='test002',candidate='نمونه دوم',role='accountant',role_title='حسابدار',created_at='2026-11-07T00:00:00+00:00',status='completed',answered=100)]
 cat=server.bank_summary()
 question=all_questions()[25]
 cand={'candidate':'داوطلب نمونه','role':'assistant','role_title':'کمک‌حسابدار','answered':0,'total':100,'status':'active',
       'question':{k:question[k] for k in ('id','category','category_id','difficulty','stem','options')}}
 cand['question'].update({'number':1,'phase':'anchor'})
 mock={'/api/meta':{'initialized':True,'total_questions':200,'target_questions':3000,'categories':25,'exam_length':100,'version':'2.1.2-beta'},
       '/api/admin/me':{'authenticated':True},'/api/admin/exams':exams,
       '/api/admin/bank':cat,'/api/admin/questions':server.admin_question_list(),
       '/api/candidate/current':cand}
 def create(width,height,is_candidate=False):
  ctx=b.new_context(viewport={'width':width,'height':height},device_scale_factor=1)
  pg=ctx.new_page()
  errors=[]
  pg.on('pageerror',lambda e:errors.append(str(e)))
  pg.set_content(html)
  pg.add_style_tag(content=style)
  pg.evaluate('''(responses)=>{const mem={};Object.defineProperty(window,'sessionStorage',{value:{getItem:(k)=>mem[k]||null,setItem:(k,v)=>mem[k]=v,removeItem:(k)=>delete mem[k]}});window.fetch=async(path,opts)=>{
   if(path.startsWith('/api/admin/reviews?')) return {ok:true,json:async()=>([])};
   if(path==='/api/admin/review') return {ok:true,json:async()=>({review_status:'approved'})};
   if(path==='/api/admin/exams'&&opts?.method==='POST') return {ok:true,json:async()=>({code:'0011223344556677',candidate:'داوطلب جدید',role:'assistant'})};
   if(path==='/api/candidate/answer') return {ok:true,json:async()=>({accepted:true,answered:1,total:100,finished:false})};
   return {ok: !!responses[path], json: async()=> responses[path] || {error:'no mock'} };
  };}''',mock)
  if is_candidate:
   candidate_js=js.replace("candidateMode:location.pathname==='/candidate'","candidateMode:true")
   pg.evaluate("sessionStorage.setItem('miz_candidate_code','0011223344556677')")
   pg.add_script_tag(content=candidate_js)
  else:pg.add_script_tag(content=js)
  return pg,errors,ctx
 desk,errs,ctx=create(1440,900)
 desk.get_by_text('انتخاب یک حسابدار خوب',exact=False).wait_for(timeout=4000)
 assert desk.locator('.hero').evaluate("e=>getComputedStyle(e).backgroundImage.includes('linear-gradient')")
 assert desk.locator('.stat-card').first.evaluate("e=>getComputedStyle(e).backgroundColor") == 'rgb(255, 255, 255)'
 assert desk.locator('.btn-primary').first.evaluate("e=>getComputedStyle(e).color") == 'rgb(255, 255, 255)' # hero button readable white on dark green
 desk.screenshot(path=str(PREVIEW/'dashboard-desktop-mock.png'),full_page=True)
 desk.locator('[data-view="bank"]').click()
 desk.get_by_text('مدیریت سؤالات').wait_for(timeout=4000)
 desk.screenshot(path=str(PREVIEW/'bank-desktop-mock.png'),full_page=True)
 desk.locator('[data-action="review-question"]').first.click()
 desk.locator('#question-review-form').wait_for(timeout=4000)
 desk.screenshot(path=str(PREVIEW/'review-workflow-desktop-mock.png'),full_page=False)
 desk.locator('[data-action="cancel-review"]').click()
 desk.locator('#bank-search').fill('بیمه')
 print('BANK filtered previews:',desk.locator('.review-question').count())
 desk.locator('[data-view="create"]').click()
 desk.get_by_text('آزمون استخدامی جدید').wait_for(timeout=4000)
 desk.screenshot(path=str(PREVIEW/'new-exam-desktop-mock.png'),full_page=True)
 desk.locator('#candidate-name').fill('داوطلب جدید')
 desk.locator('#new-exam-form button[type=submit]').click()
 desk.locator('#exam-code').wait_for(timeout=4000)
 print('Created code:',desk.locator('#exam-code').inner_text())
 mob,errm,ctxm=create(390,844)
 mob.get_by_text('انتخاب یک حسابدار خوب',exact=False).wait_for(timeout=4000)
 mob.screenshot(path=str(PREVIEW/'dashboard-mobile-mock.png'),full_page=True)
 assert mob.locator('.mobile-menu').is_visible()
 mob.locator('.mobile-menu').click()
 assert mob.locator('.sidebar').evaluate("e=>e.classList.contains('open')")
 mob.locator('.sidebar [data-view="bank"]').click()
 mob.get_by_text('مدیریت سؤالات').wait_for(timeout=4000)
 cand_page,errc,ctxc=create(390,844,True)
 cand_page.get_by_text('سؤال ۱ از ۱۰۰').wait_for(timeout=4000)
 cand_page.screenshot(path=str(PREVIEW/'candidate-mobile-mock.png'),full_page=True)
 cand_page.locator('[data-action="select-answer"]').first.click()
 assert 'is-selected' in cand_page.locator('[data-action="select-answer"]').first.get_attribute('class')
 print('JS errors:',errs+errm+errc)
 assert not (errs+errm+errc)
 print('Created 6 UI screenshots (mock API):',PREVIEW)
 b.close()