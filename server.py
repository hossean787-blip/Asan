# -*- coding: utf-8 -*-
"""Miz-e Mosahebe Hesabdari: dependency-free Python 3.8+ pilot server.

Candidate answers remain on the server. The 200 pilot questions are drafts;
not a calibrated employment selection instrument.
"""
import argparse
import base64
import csv
import copy
import datetime
import hashlib
import hmac
import io
import ipaddress
import json
import os
from pathlib import Path
import random
import secrets
import sqlite3
import sys
import threading
import time
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit, parse_qs

from bank_source import all_questions
from bank_expansion_v21 import extra_questions

ROOT = Path(__file__).resolve().parent
DATA_PATH = Path(os.environ.get('MIZ_DB_PATH', str(ROOT / 'private_data' / 'miz.sqlite3')))
LEGACY_SEED_IDS = {q['id'] for q in all_questions()}
SEED_QUESTIONS = all_questions() + extra_questions()
QUESTIONS = copy.deepcopy(SEED_QUESTIONS)
BY_ID = {q['id']: q for q in QUESTIONS}
CAT_IDS = sorted({q['category_id'] for q in QUESTIONS})
STATIC = ROOT / 'static'
LOCK = threading.RLock()
CONN = None
LOGIN_TRACKER = {}
ROLES = {'intern': 'کارآموز حسابداری', 'assistant': 'کمک‌حسابدار', 'accountant': 'حسابدار'}
DIFF = {'easy': 0, 'medium': 1, 'hard': 2}
REV_DIFF = ['easy', 'medium', 'hard']


def utcnow():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def open_db(path=None):
    global CONN
    if CONN is not None:
        CONN.close()
    p = Path(path or DATA_PATH)
    p.parent.mkdir(parents=True, exist_ok=True)
    if os.name != 'nt':
        p.parent.chmod(0o700)
    CONN = sqlite3.connect(str(p), check_same_thread=False, isolation_level=None)
    if os.name != 'nt':p.chmod(0o600)
    CONN.row_factory = sqlite3.Row
    CONN.execute('PRAGMA journal_mode=WAL')
    CONN.execute('PRAGMA foreign_keys=ON')
    CONN.executescript('''
    CREATE TABLE IF NOT EXISTS settings (k TEXT PRIMARY KEY,v TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS custom_questions (id TEXT PRIMARY KEY, payload TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS admin_sessions (token_hash TEXT PRIMARY KEY,created_at INTEGER NOT NULL,expires_at INTEGER NOT NULL);
    CREATE TABLE IF NOT EXISTS exams (
      id TEXT PRIMARY KEY, candidate TEXT NOT NULL, role TEXT NOT NULL,
      code_hash TEXT NOT NULL UNIQUE,created_at TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'active',completed_at TEXT,
      adaptive_plan TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS assignments (
      exam_id TEXT NOT NULL,position INTEGER NOT NULL,question_id TEXT NOT NULL,
      phase TEXT NOT NULL,PRIMARY KEY(exam_id,position),
      UNIQUE(exam_id,question_id), FOREIGN KEY(exam_id) REFERENCES exams(id) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS responses (
      exam_id TEXT NOT NULL,position INTEGER NOT NULL,choice_index INTEGER,
      is_correct INTEGER NOT NULL,answered_at TEXT NOT NULL,
      PRIMARY KEY(exam_id,position),
      FOREIGN KEY(exam_id,position) REFERENCES assignments(exam_id,position) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS question_reviews (
      question_id TEXT PRIMARY KEY, review_status TEXT NOT NULL,
      reviewer TEXT NOT NULL, note TEXT NOT NULL, reviewed_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS review_events (
      id INTEGER PRIMARY KEY AUTOINCREMENT, question_id TEXT NOT NULL,
      previous_status TEXT NOT NULL, review_status TEXT NOT NULL,
      reviewer TEXT NOT NULL, note TEXT NOT NULL, reviewed_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS exam_question_pool (
      exam_id TEXT PRIMARY KEY, question_ids_json TEXT NOT NULL,
      FOREIGN KEY(exam_id) REFERENCES exams(id) ON DELETE CASCADE
    );
    ''')
    # Restore only previously validated, append-only imported questions.
    global QUESTIONS, BY_ID
    QUESTIONS=copy.deepcopy(SEED_QUESTIONS)
    for added in CONN.execute('SELECT payload FROM custom_questions ORDER BY rowid'):
        QUESTIONS.append(json.loads(added['payload']))
    BY_ID={q['id']:q for q in QUESTIONS}
    for record in CONN.execute('SELECT question_id,review_status,reviewer,reviewed_at FROM question_reviews'):
        q=BY_ID.get(record['question_id'])
        if q:
            q['review_status']=record['review_status']
            q['reviewer_id']=record['reviewer']
            q['last_verified_on']=record['reviewed_at']
    return CONN


def setting(k):
    r = CONN.execute('SELECT v FROM settings WHERE k=?', (k,)).fetchone()
    return r['v'] if r else None


def setup_admin(password):
    if not isinstance(password,str) or len(password)<10 or len(password)>256:
        raise ValueError('گذرواژه مسئول استخدام باید دست‌کم ۱۰ نویسه باشد.')
    with LOCK:
        if setting('admin_hash'):
            raise ValueError('حساب مسئول استخدام قبلاً ساخته شده است.')
        salt=secrets.token_bytes(16)
        digest=hashlib.pbkdf2_hmac('sha256',password.encode('utf-8'),salt,310000)
        CONN.execute('INSERT INTO settings VALUES (?,?)',('admin_hash',base64.b64encode(salt+digest).decode('ascii')))


def verify_password(password):
    val=setting('admin_hash')
    if not val:return False
    raw=base64.b64decode(val)
    actual=hashlib.pbkdf2_hmac('sha256',str(password).encode('utf-8'),raw[:16],310000)
    return hmac.compare_digest(actual,raw[16:])


def login(password):
    if not verify_password(password):return None
    token=secrets.token_urlsafe(32)
    now=int(time.time())
    CONN.execute('INSERT INTO admin_sessions VALUES (?,?,?)', (hashlib.sha256(token.encode()).hexdigest(),now,now+12*3600))
    CONN.execute('DELETE FROM admin_sessions WHERE expires_at < ?', (now,))
    return token


def is_admin_token(token):
    if not token:return False
    hashed=hashlib.sha256(token.encode('utf-8')).hexdigest()
    row=CONN.execute('SELECT expires_at FROM admin_sessions WHERE token_hash=?',(hashed,)).fetchone()
    return bool(row and row['expires_at']>int(time.time()))


def logout(token):
    if token:
        CONN.execute('DELETE FROM admin_sessions WHERE token_hash=?',(hashlib.sha256(token.encode()).hexdigest(),))


def exam_for_code(code):
    if not isinstance(code,str) or len(code)<10 or len(code)>40:return None
    key=hashlib.sha256(code.strip().upper().encode('utf-8')).hexdigest()
    return CONN.execute('SELECT * FROM exams WHERE code_hash=?',(key,)).fetchone()


def require_approved():
    return os.environ.get('MIZ_REQUIRE_APPROVED', '0').lower() in ('1','yes','true')


def exam_eligible_questions():
    eligible=[q for q in QUESTIONS if not require_approved() or q['review_status']=='approved']
    for cat in CAT_IDS:
        available=[q for q in eligible if q['category_id']==cat]
        counts={d:sum(q['difficulty']==d for q in available) for d in DIFF}
        if len(available)<4 or not all(counts[d]>=1 for d in DIFF):
            raise ValueError('برای آزمون در حالت تأییدشده، حوزه %s حداقل به ۴ سؤال شامل هر سه سطح نیاز دارد.'%cat)
    return eligible


def review_question(question_id, status, reviewer, note):
    if question_id not in BY_ID:raise ValueError('شناسه سؤال پیدا نشد.')
    if status not in ('draft','approved','rejected'):
        raise ValueError('وضعیت بررسی باید پیش‌نویس، تأیید یا رد باشد.')
    reviewer=str(reviewer or '').strip();note=str(note or '').strip()
    if not 2<=len(reviewer)<=80 or not 12<=len(note)<=1000:
        raise ValueError('نام بررسی‌کننده و توضیح بررسی (حداقل ۱۲ نویسه) لازم است.')
    with LOCK:
        q=BY_ID[question_id]
        prior=q['review_status']; timestamp=utcnow()
        CONN.execute('BEGIN IMMEDIATE')
        try:
            CONN.execute('INSERT INTO question_reviews(question_id,review_status,reviewer,note,reviewed_at) VALUES (?,?,?,?,?) '
                'ON CONFLICT(question_id) DO UPDATE SET review_status=excluded.review_status,reviewer=excluded.reviewer,note=excluded.note,reviewed_at=excluded.reviewed_at',
                (question_id,status,reviewer,note,timestamp))
            CONN.execute('INSERT INTO review_events(question_id,previous_status,review_status,reviewer,note,reviewed_at) VALUES (?,?,?,?,?,?)',
                (question_id,prior,status,reviewer,note,timestamp))
            CONN.execute('COMMIT')
        except Exception:
            CONN.execute('ROLLBACK');raise
        q['review_status']=status;q['reviewer_id']=reviewer;q['last_verified_on']=timestamp
    return {'id':question_id,'review_status':status,'reviewer':reviewer,'reviewed_at':timestamp}


def review_history(question_id):
    if question_id not in BY_ID:raise ValueError('سؤال پیدا نشد.')
    return [dict(row) for row in CONN.execute('SELECT previous_status,review_status,reviewer,note,reviewed_at '
         'FROM review_events WHERE question_id=? ORDER BY id',(question_id,))]


def anchors_for_role(role, question_pool=None):
    rng=random.SystemRandom()
    res=[]
    source=question_pool if question_pool is not None else QUESTIONS
    levels=['easy','medium'] if role in ('intern','assistant') else ['medium','hard']
    for cat in CAT_IDS:
        for level in levels:
            xs=[q for q in source if q['category_id']==cat and q['difficulty']==level]
            res.append(rng.choice(xs)['id'])
    rng.shuffle(res)
    return res


def create_exam(candidate,role):
    if role not in ROLES: raise ValueError('موقعیت شغلی معتبر نیست.')
    candidate=str(candidate or '').strip()
    if len(candidate)<2 or len(candidate)>100:raise ValueError('نام داوطلب باید بین ۲ تا ۱۰۰ نویسه باشد.')
    with LOCK:
        eid=secrets.token_hex(12)
        # 12-character random code. SHA256 is stored, not the original code.
        code=secrets.token_hex(8).upper()
        pool=exam_eligible_questions()
        ids=anchors_for_role(role,pool)
        rng=random.SystemRandom()
        plan=CAT_IDS*2
        rng.shuffle(plan)
        CONN.execute('BEGIN IMMEDIATE')
        try:
            CONN.execute('INSERT INTO exams(id,candidate,role,code_hash,created_at,adaptive_plan) VALUES (?,?,?,?,?,?)',
                         (eid,candidate,role,hashlib.sha256(code.encode()).hexdigest(),utcnow(),json.dumps(plan)))
            CONN.execute('INSERT INTO exam_question_pool VALUES (?,?)', (eid,json.dumps([q['id'] for q in pool])))
            for i,qid in enumerate(ids,1):
                CONN.execute('INSERT INTO assignments VALUES (?,?,?,?)',(eid,i,qid,'anchor'))
            CONN.execute('COMMIT')
        except Exception:
            CONN.execute('ROLLBACK')
            raise
    return {'id':eid,'code':code,'candidate':candidate,'role':role,'role_title':ROLES[role]}


def responses_for(eid):
    return [dict(r) for r in CONN.execute('''
    SELECT a.position,a.question_id,a.phase,r.choice_index,r.is_correct,r.answered_at
    FROM assignments a JOIN responses r ON a.exam_id=r.exam_id AND a.position=r.position
    WHERE a.exam_id=? ORDER BY a.position''',(eid,)).fetchall()]


def assignment_count(eid):
    return CONN.execute('SELECT count(*) FROM assignments WHERE exam_id=?',(eid,)).fetchone()[0]


def adaptive_target(exam,prior,category):
    # This is an uncalibrated, explicit heuristic; not an IRT psychometric estimate.
    base={'intern':0,'assistant':1,'accountant':2}[exam['role']]
    last=prior[-8:]
    if len(last)>=4:
        rate=sum(r['is_correct'] for r in last)/len(last)
        base+= 1 if rate>=0.75 else -1 if rate<=0.35 else 0
    own=[r for r in prior if BY_ID[r['question_id']]['category_id']==category]
    if len(own)>=2:
        tail=own[-2:]
        base+= 1 if all(r['is_correct'] for r in tail) else -1 if not any(r['is_correct'] for r in tail) else 0
    return max(0,min(2,base))


def ensure_next_question(exam):
    eid=exam['id']
    prior=responses_for(eid)
    next_pos=len(prior)+1
    if next_pos>100 or exam['status']!='active':return None
    row=CONN.execute('SELECT * FROM assignments WHERE exam_id=? AND position=?',(eid,next_pos)).fetchone()
    if row:return row
    # Only the first 50 fixed anchors are pre-assigned. The rest are selected
    # as the applicant answers, with 2 adaptive items for each of 25 topics.
    if next_pos<=50:raise RuntimeError('Missing anchor question')
    plan=json.loads(exam['adaptive_plan'])
    category=plan[next_pos-51]
    used={r['question_id'] for r in CONN.execute('SELECT question_id FROM assignments WHERE exam_id=?',(eid,))}
    saved_pool=CONN.execute('SELECT question_ids_json FROM exam_question_pool WHERE exam_id=?',(eid,)).fetchone()
    allowed=set(json.loads(saved_pool['question_ids_json'])) if saved_pool else {qid for qid in BY_ID if qid in LEGACY_SEED_IDS or qid.startswith('USR-')}
    available=[q for q in QUESTIONS if q['category_id']==category and q['id'] not in used and q['id'] in allowed]
    if not available:raise RuntimeError('Question pool exhausted')
    target=adaptive_target(exam,prior,category)
    # Randomize ties to avoid predictable repetition when the pool grows.
    nearest=min(abs(DIFF[q['difficulty']]-target) for q in available)
    q=secrets.choice([q for q in available if abs(DIFF[q['difficulty']]-target)==nearest])
    CONN.execute('INSERT INTO assignments VALUES (?,?,?,?)',(eid,next_pos,q['id'],'adaptive'))
    return CONN.execute('SELECT * FROM assignments WHERE exam_id=? AND position=?',(eid,next_pos)).fetchone()


def candidate_current(code):
    with LOCK:
        exam=exam_for_code(code)
        if not exam: raise PermissionError('کد شرکت در آزمون نامعتبر است.')
        if exam['status']=='revoked':raise PermissionError('این کد آزمون توسط مسئول استخدام غیرفعال شده است.')
        prior=responses_for(exam['id'])
        result={'candidate':exam['candidate'],'role':exam['role'],'role_title':ROLES[exam['role']],
                'answered':len(prior),'total':100,'status':exam['status']}
        if exam['status']=='completed':return result
        a=ensure_next_question(exam)
        if not a:return result
        q=BY_ID[a['question_id']]
        result['question']={k:q[k] for k in ('id','category','category_id','difficulty','stem','options')}
        result['question']['phase']=a['phase']
        result['question']['number']=a['position']
        return result


def answer_exam(code,choice):
    with LOCK:
        exam=exam_for_code(code)
        if not exam:raise PermissionError('کد شرکت در آزمون نامعتبر است.')
        if exam['status']!='active':raise ValueError('آزمون قبلاً پایان یافته است.')
        prior=responses_for(exam['id'])
        pos=len(prior)+1
        if pos>100:raise ValueError('ظرفیت پاسخ تکمیل شده است.')
        a=ensure_next_question(exam)
        if choice is not None and (type(choice) is not int or not 0<=choice<4):
            raise ValueError('گزینه پاسخ معتبر نیست.')
        q=BY_ID[a['question_id']]
        correct=int(choice==q['correct_index'])
        CONN.execute('BEGIN IMMEDIATE')
        try:
            CONN.execute('INSERT INTO responses VALUES (?,?,?,?,?)',(exam['id'],pos,choice,correct,utcnow()))
            if pos==100:
                CONN.execute('UPDATE exams SET status=?,completed_at=? WHERE id=?',('completed',utcnow(),exam['id']))
            CONN.execute('COMMIT')
        except Exception:
            CONN.execute('ROLLBACK')
            raise
        # Deliberately does not reveal the answer, correctness or score.
        return {'accepted':True,'answered':pos,'total':100,'finished':pos==100}


def revoke_exam(exam_id):
    with LOCK:
        row=CONN.execute('SELECT status FROM exams WHERE id=?',(exam_id,)).fetchone()
        if row is None:raise ValueError('آزمون پیدا نشد.')
        if row['status']!='active':raise ValueError('فقط آزمون در جریان را می‌توان غیرفعال کرد.')
        CONN.execute('UPDATE exams SET status=? WHERE id=?',('revoked',exam_id))
    return {'id':exam_id,'status':'revoked'}


def all_exams():
    rows=CONN.execute('''SELECT e.id,e.candidate,e.role,e.created_at,e.completed_at,e.status,
    count(r.position) answered FROM exams e LEFT JOIN responses r ON e.id=r.exam_id
    GROUP BY e.id ORDER BY e.created_at DESC''').fetchall()
    return [{**dict(r),'role_title':ROLES[r['role']]} for r in rows]


def report(eid):
    exam=CONN.execute('SELECT * FROM exams WHERE id=?',(eid,)).fetchone()
    if not exam:raise ValueError('جلسه پیدا نشد.')
    prior=responses_for(eid)
    details=[]
    sums={c:{'category':next(q['category'] for q in QUESTIONS if q['category_id']==c),
             'answered':0,'correct':0,'weight_total':0.,'weight_correct':0.} for c in CAT_IDS}
    for r in prior:
        q=BY_ID[r['question_id']]
        item={k:q[k] for k in ('id','category','category_id','difficulty','stem','options','correct_index','rationale','review_status')}
        item.update({'position':r['position'],'choice_index':r['choice_index'],'is_correct':bool(r['is_correct']),'phase':r['phase']})
        details.append(item)
        b=sums[q['category_id']]
        weight={'easy':1.,'medium':1.5,'hard':2.}[q['difficulty']]
        b['answered']+=1;b['correct']+=r['is_correct'];b['weight_total']+=weight;b['weight_correct']+=weight*r['is_correct']
    got=sum(x['is_correct'] for x in details)
    wsum=sum(x['weight_total'] for x in sums.values())
    wgot=sum(x['weight_correct'] for x in sums.values())
    return {'id':eid,'candidate':exam['candidate'],'role':exam['role'],'role_title':ROLES[exam['role']],
        'created_at':exam['created_at'],'completed_at':exam['completed_at'],'status':exam['status'],
        'answered':len(details),'correct':got,'wrong':sum(x['choice_index'] is not None and not x['is_correct'] for x in details),
        'skipped':sum(x['choice_index'] is None for x in details),
        'raw_percent':round(got/len(details)*100,1) if details else 0,
        'weighted_percent':round(wgot/wsum*100,1) if wsum else 0,
        'areas':list(sums.values()),'details':details,'calibrated':False,'comparable_between_candidates':False,
        'warning':'نسخه پایلوت؛ دشواری و روایی سؤال‌ها توسط کارشناس مستقل و با داده آزمون‌های واقعی کالیبره نشده است.'}


def csv_safe(value):
    # Excel treats cells prefixed with these characters as executable formulas.
    val=str(value)
    return "'"+val if val.lstrip().startswith(('=','+','-','@')) else val


def csv_report(eid):
    rep=report(eid)
    f=io.StringIO()
    w=csv.writer(f)
    w.writerow(['ردیف','حوزه','سطح','سؤال','پاسخ داوطلب','پاسخ صحیح','درست؟','توضیح'])
    for q in rep['details']:
        selected=q['options'][q['choice_index']] if q['choice_index'] is not None else 'بی‌پاسخ'
        w.writerow([csv_safe(v) for v in [q['position'],q['category'],q['difficulty'],q['stem'],selected,
            q['options'][q['correct_index']],'بله' if q['is_correct'] else 'خیر',q['rationale']]])
    return ('\ufeff'+f.getvalue()).encode('utf-8')


def bank_summary():
    quotas=json.loads((ROOT/'docs'/'target_plan_3000.json').read_text(encoding='utf-8'))
    data=[]
    for c in quotas['categories']:
        counts={k:sum(q['category_id']==c['id'] and q['difficulty']==k for q in QUESTIONS) for k in REV_DIFF}
        data.append({'id':c['id'],'name':c['name'],'actual':counts,'target':c['quota']})
    statuses={status:sum(q['review_status']==status for q in QUESTIONS) for status in ('approved','draft','rejected')}
    return {'target':3000,'actual':len(QUESTIONS),'reviewed':statuses['approved'],
            'draft':statuses['draft'],'rejected':statuses['rejected'],
            'categories':data,'status':'pilot_draft','require_approved':require_approved()}


def import_questions(items):
    """Atomic append-only import. No pre-existing exam question or answer can be changed."""
    if not isinstance(items,list) or not (1<=len(items)<=200):
        raise ValueError('در هر بار باید بین ۱ تا ۲۰۰ سؤال وارد شود.')
    with LOCK:
        if len(QUESTIONS)+len(items)>3000:
            raise ValueError('ظرفیت بانک ۳٬۰۰۰ سؤالی تکمیل می‌شود.')
        fresh=[]
        quotas={c['id']:c['quota'] for c in json.loads((ROOT/'docs'/'target_plan_3000.json').read_text(encoding='utf-8'))['categories']}
        current_counts={(cat,lv):sum(q['category_id']==cat and q['difficulty']==lv for q in QUESTIONS) for cat in CAT_IDS for lv in DIFF}
        seen_stems={q['stem'].strip() for q in QUESTIONS}
        for index,q in enumerate(items,1):
            if not isinstance(q,dict):raise ValueError('قالب سؤال %s معتبر نیست.'%index)
            cat=q.get('category_id');dif=q.get('difficulty')
            stem=str(q.get('stem','')).strip()
            opts=q.get('options');correct=q.get('correct_index')
            rationale=str(q.get('rationale','')).strip()
            source=str(q.get('source_reference','')).strip()
            if cat not in CAT_IDS or dif not in DIFF:
                raise ValueError('حوزه یا سطح سختی سؤال %s نامعتبر است.'%index)
            current_counts[(cat,dif)]+=1
            if current_counts[(cat,dif)]>quotas[cat][dif]:
                raise ValueError('سهمیه مصوب این حوزه و سطح دشواری تکمیل شده است.')
            if not 20<=len(stem)<=1000 or stem in seen_stems:
                raise ValueError('متن سؤال %s تکراری یا از نظر طول نامعتبر است.'%index)
            if not isinstance(opts,list) or len(opts)!=4 or not all(isinstance(x,str) and 1<=len(x.strip())<=500 for x in opts) or len(set(x.strip() for x in opts))!=4:
                raise ValueError('چهار گزینه سؤال %s معتبر یا متمایز نیستند.'%index)
            if type(correct) is not int or correct not in range(4):
                raise ValueError('پاسخ صحیح سؤال %s باید یکی از عددهای صفر تا ۳ باشد.'%index)
            if len(rationale)<10 or len(rationale)>1500 or not 3<=len(source)<=400:
                raise ValueError('راه‌حل یا منبع سؤال %s کامل نیست.'%index)
            seen_stems.add(stem)
            fresh.append({'id':'USR-'+secrets.token_hex(8).upper(),
                'category_id':cat,
                'category':next(x['category'] for x in SEED_QUESTIONS if x['category_id']==cat),
                'subtopic':str(q.get('subtopic') or 'سؤال واردشده')[:100],
                'difficulty':dif,'skill_type':str(q.get('skill_type') or 'scenario')[:30],
                'stem':stem,'options':[x.strip() for x in opts],
                'correct_index':correct,'rationale':rationale,'source_reference':source,
                'legal_effective_from':str(q.get('legal_effective_from') or '')[:16],
                'legal_effective_to':str(q.get('legal_effective_to') or '')[:16],
                'review_status':'draft','reviewer_id':None,'last_verified_on':None,'version':1})
        CONN.execute('BEGIN IMMEDIATE')
        try:
            for q in fresh:
                CONN.execute('INSERT INTO custom_questions(id,payload) VALUES (?,?)',
                    (q['id'],json.dumps(q,ensure_ascii=False)))
            CONN.execute('COMMIT')
        except Exception:
            CONN.execute('ROLLBACK');raise
        QUESTIONS.extend(fresh)
        BY_ID.update((q['id'],q) for q in fresh)
        return {'imported':len(fresh),'bank_size':len(QUESTIONS),'review_status':'draft'}


def admin_question_list():
    # All question keys may only be retrieved from recruiter-only endpoints.
    return [{k:q.get(k) for k in ('id','category_id','category','difficulty','stem','options',
                'correct_index','rationale','review_status','source_reference','reviewer_id','last_verified_on')} for q in QUESTIONS]


class Handler(BaseHTTPRequestHandler):
    server_version='MizAccounting/2.1.2'
    def log_message(self, format, *args):
        # Strip paths/query to avoid leaking candidate codes via access logs.
        sys.stderr.write('%s [%s] %s\n'%(self.client_address[0],self.log_date_time_string(),format%args if 'error' in format.lower() else 'request'))

    def reply(self,status,body,ctype='application/json; charset=utf-8',headers=None):
        if isinstance(body,(dict,list)):
            body=json.dumps(body,ensure_ascii=False,separators=(',',':')).encode('utf-8')
        elif isinstance(body,str):body=body.encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type',ctype)
        self.send_header('Content-Length',str(len(body)))
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Referrer-Policy','no-referrer')
        self.send_header('X-Frame-Options','DENY')
        self.send_header('Content-Security-Policy',"default-src 'self'; base-uri 'none'; object-src 'none'; frame-ancestors 'none'; form-action 'self'; connect-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:")
        for k,v in (headers or {}).items():self.send_header(k,v)
        self.end_headers()
        self.wfile.write(body)

    def auth_token(self):
        try:
            cookie=SimpleCookie(self.headers.get('Cookie',''))
            return cookie['miz_admin'].value if 'miz_admin' in cookie else None
        except Exception:return None

    def is_admin(self):
        with LOCK:return is_admin_token(self.auth_token())

    def demand_admin(self):
        if not self.is_admin():raise PermissionError('برای این بخش باید به‌عنوان مسئول استخدام وارد شوید.')

    def data(self):
        if 'application/json' not in self.headers.get('Content-Type',''):
            raise ValueError('فرمت درخواست باید JSON باشد.')
        n=int(self.headers.get('Content-Length','0'))
        if n<1 or n>(1300000 if urlsplit(self.path).path=='/api/admin/import' else 20000):raise ValueError('اندازه درخواست نامعتبر است.')
        body=json.loads(self.rfile.read(n))
        if not isinstance(body,dict):raise ValueError('ساختار درخواست نامعتبر است.')
        return body

    def demand_same_origin(self):
        origin=self.headers.get('Origin')
        if origin:
            host=self.headers.get('Host')
            if origin not in ('http://'+host,'https://'+host):
                raise PermissionError('درخواست از مبدأ دیگری پذیرفته نمی‌شود.')

    def api(self,verb):
        path=urlsplit(self.path).path
        if verb=='GET':
            if path=='/api/meta':return self.reply(200,{'initialized':bool(setting('admin_hash')),'total_questions':len(QUESTIONS),'target_questions':3000,'categories':25,'exam_length':100,'version':'2.1.2-beta','require_approved':require_approved()})
            if path=='/api/admin/me':return self.reply(200,{'authenticated':self.is_admin()})
            if path=='/api/candidate/current':return self.reply(200,candidate_current(self.headers.get('X-Exam-Code','')))
            if path=='/api/admin/exams':
                self.demand_admin();return self.reply(200,all_exams())
            if path=='/api/admin/bank':
                self.demand_admin();return self.reply(200,bank_summary())
            if path=='/api/admin/questions':
                self.demand_admin();return self.reply(200,admin_question_list())
            if path=='/api/admin/reviews':
                self.demand_admin();question_id=parse_qs(urlsplit(self.path).query).get('id',[''])[0]
                return self.reply(200,review_history(question_id))
            if path.startswith('/api/admin/reports/'):
                self.demand_admin();eid=path.rsplit('/',1)[-1]
                if eid.endswith('.csv'):
                    eid=eid[:-4];b=csv_report(eid)
                    return self.reply(200,b,'text/csv; charset=utf-8',{'Content-Disposition':'attachment; filename="accounting-report.csv"'})
                return self.reply(200,report(eid))
        if verb=='POST':
            self.demand_same_origin();payload=self.data()
            if path=='/api/admin/setup':
                if not ipaddress.ip_address(self.client_address[0]).is_loopback:
                    raise PermissionError('ساخت حساب اولیه فقط از دستگاه سرور امکان‌پذیر است.')
                setup_admin(payload.get('password',''));return self.reply(201,{'ready':True})
            if path=='/api/admin/login':
                addr=self.client_address[0]
                now=time.time()
                recent=[x for x in LOGIN_TRACKER.get(addr,[]) if now-x<300]
                if len(recent)>=8: return self.reply(429,{'error':'تلاش‌های ناموفق زیاد است؛ چند دقیقه بعد دوباره وارد شوید.'})
                token=login(payload.get('password',''))
                if not token:
                    recent.append(now);LOGIN_TRACKER[addr]=recent
                    raise PermissionError('گذرواژه صحیح نیست.')
                LOGIN_TRACKER.pop(addr,None)
                cookie=f'miz_admin={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age=43200'
                if self.headers.get('X-Forwarded-Proto')=='https':
                    # Only trust reverse proxy if explicitly configured.
                    if os.environ.get('MIZ_TRUST_PROXY')=='1': cookie+='; Secure'
                return self.reply(200,{'authenticated':True},headers={'Set-Cookie':cookie})
            if path=='/api/admin/logout':
                logout(self.auth_token());return self.reply(200,{'ok':True},headers={'Set-Cookie':'miz_admin=; HttpOnly; SameSite=Strict; Max-Age=0; Path=/'})
            if path=='/api/admin/exams':
                self.demand_admin();return self.reply(201,create_exam(payload.get('candidate'),payload.get('role')))
            if path=='/api/admin/import':
                self.demand_admin();return self.reply(201,import_questions(payload.get('questions')))
            if path=='/api/admin/review':
                self.demand_admin();return self.reply(200,review_question(payload.get('question_id'),payload.get('status'),payload.get('reviewer'),payload.get('note')))
            if path=='/api/admin/exams/revoke':
                self.demand_admin();return self.reply(200,revoke_exam(payload.get('id')))
            if path=='/api/candidate/answer':
                return self.reply(200,answer_exam(self.headers.get('X-Exam-Code',''),payload.get('choice')))
        return self.reply(404,{'error':'نشانی پیدا نشد.'})

    def dispatch(self,verb):
        try:
            path=urlsplit(self.path).path
            if path.startswith('/api/'):
                with LOCK:
                    return self.api(verb)
            if verb=='GET' and path in ('/','/candidate','/admin'):
                return self.serve_static('index.html')
            if verb=='GET' and path.startswith('/static/'):
                return self.serve_static(path[len('/static/'):])
            return self.reply(404,{'error':'صفحه پیدا نشد.'})
        except PermissionError as e:return self.reply(403,{'error':str(e)})
        except (ValueError,TypeError,json.JSONDecodeError) as e:return self.reply(400,{'error':str(e)})
        except Exception as e:
            print('Unhandled server exception:',repr(e),file=sys.stderr)
            return self.reply(500,{'error':'خطای داخلی سرور؛ جزئیات در گزارش سرور ثبت شد.'})

    def serve_static(self,filename):
        allow={'index.html':'text/html; charset=utf-8','app.js':'application/javascript; charset=utf-8',
            'styles.css':'text/css; charset=utf-8','theme-green.css':'text/css; charset=utf-8','logo.svg':'image/svg+xml',
            'import-template.json':'application/json; charset=utf-8','manifest.webmanifest':'application/manifest+json; charset=utf-8','icon-192.png':'image/png','icon-512.png':'image/png'}
        if filename not in allow:return self.reply(404,{'error':'فایل وجود ندارد.'})
        p=STATIC/filename
        return self.reply(200,p.read_bytes(),allow[filename])

    def do_GET(self):return self.dispatch('GET')
    def do_POST(self):return self.dispatch('POST')


def main():
    p=argparse.ArgumentParser(description='میز مصاحبه حسابداری — سرور داخلی')
    p.add_argument('--host',default='127.0.0.1',help='Use 0.0.0.0 for LAN testing (not secure without HTTPS)')
    p.add_argument('--port',type=int,default=8765)
    p.add_argument('--db',default=None)
    args=p.parse_args()
    open_db(args.db)
    server=ThreadingHTTPServer((args.host,args.port),Handler)
    print('میز مصاحبه حسابداری: http://%s:%s'%(('localhost' if args.host=='127.0.0.1' else args.host),args.port),flush=True)
    if args.host!='127.0.0.1':print('هشدار: شبکه بدون HTTPS برای استفاده عملیاتی/عمومی ایمن نیست.',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close();CONN.close()

if __name__=='__main__':main()