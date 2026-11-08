# -*- coding: utf-8 -*-
import http.client
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import threading
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import server
from bank_source import all_questions

class BankTests(unittest.TestCase):
    def test_bank_sizes_and_question_quality(self):
        q=all_questions()
        self.assertEqual(len(q),150)
        self.assertEqual(len(set(x['id'] for x in q)),150)
        self.assertEqual(len(set(x['stem'] for x in q)),150)
        self.assertEqual(len(server.SEED_QUESTIONS),200)
        self.assertEqual(len({x['id'] for x in server.SEED_QUESTIONS}),200)
        self.assertEqual(len({x['stem'] for x in server.SEED_QUESTIONS}),200)
        self.assertEqual(len(set(x['category_id'] for x in q)),25)
        for cat in server.CAT_IDS:
            qs=[x for x in q if x['category_id']==cat]
            self.assertEqual(len(qs),6)
            self.assertEqual(sorted(x['difficulty'] for x in qs),['easy']*2+['hard']*2+['medium']*2)
            extended=[x for x in server.SEED_QUESTIONS if x['category_id']==cat]
            self.assertEqual(len(extended),8)
            self.assertEqual(sorted(x['difficulty'] for x in extended),['easy']*2+['hard']*3+['medium']*3)
        for x in q:
            self.assertEqual(len(x['options']),4)
            self.assertEqual(len(set(x['options'])),4)
            self.assertIn(x['correct_index'],range(4))
            self.assertGreaterEqual(len(x['rationale']),10)
            self.assertEqual(x['review_status'],'draft')

class ServerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        server.open_db(Path(self.tmp.name)/'db.sqlite3')
    def tearDown(self):
        server.CONN.close()
        server.CONN=None
        self.tmp.cleanup()

    def test_password_and_security(self):
        with self.assertRaises(ValueError): server.setup_admin('short')
        server.setup_admin('very-strong-password-123')
        self.assertFalse(server.verify_password('wrong'))
        self.assertTrue(server.verify_password('very-strong-password-123'))
        with self.assertRaises(ValueError):server.setup_admin('another-password-123')
        token=server.login('very-strong-password-123')
        self.assertTrue(server.is_admin_token(token))
        server.logout(token)
        self.assertFalse(server.is_admin_token(token))

    def test_100_answer_adaptive_exam(self):
        item=server.create_exam('آزمون داوطلب','assistant')
        self.assertEqual(len(item['code']),16)
        eid=item['id'];code=item['code']
        self.assertIsNone(server.exam_for_code('bogus'))
        self.assertEqual(server.assignment_count(eid),50)
        pairs=[]
        for i in range(100):
            got=server.candidate_current(code)
            self.assertEqual(got['question']['number'],i+1)
            self.assertNotIn('correct_index',got['question'])
            self.assertNotIn('rationale',got['question'])
            self.assertNotIn('is_correct',got)
            if i<50:self.assertEqual(got['question']['phase'],'anchor')
            else:self.assertEqual(got['question']['phase'],'adaptive')
            if i%9==0:choice=None
            else:choice=(server.BY_ID[got['question']['id']]['correct_index'] if i%3 else 0)
            result=server.answer_exam(code,choice)
            self.assertEqual(result['answered'],i+1)
            self.assertNotIn('is_correct',result)
            self.assertNotIn('score',result)
            pairs.append((got['question']['category_id'],got['question']['phase']))
        final=server.candidate_current(code)
        self.assertEqual(final['status'],'completed')
        self.assertNotIn('question',final)
        self.assertEqual(server.assignment_count(eid),100)
        self.assertEqual(len(server.responses_for(eid)),100)
        for c in server.CAT_IDS:
            self.assertEqual(sum(x[0]==c for x in pairs),4)
            self.assertEqual(sum(x[0]==c and x[1]=='anchor' for x in pairs),2)
            self.assertEqual(sum(x[0]==c and x[1]=='adaptive' for x in pairs),2)
        report=server.report(eid)
        self.assertEqual(report['answered'],100)
        self.assertEqual(report['correct']+report['wrong']+report['skipped'],100)
        self.assertFalse(report['calibrated'])
        self.assertEqual(len(report['details']),100)
        self.assertTrue(server.csv_report(eid).startswith('\ufeff'.encode('utf-8')))
        with self.assertRaises(ValueError):server.answer_exam(code,0)

    def test_atomic_import_recovery_and_protection(self):
        q={'category_id':'ACC-01','difficulty':'medium','stem':'فرض کنید یک خدمت در پایان سال تکمیل شده و هنوز پول آن دریافت نشده است؛ ثبت صحیح چیست؟',
           'options':['حساب‌های دریافتنی بدهکار و درآمد بستانکار','درآمد بدهکار و بانک بستانکار','بانک بدهکار و دریافتنی بستانکار','هیچ‌کدام از حساب‌ها تغییر نمی‌کند'],
           'correct_index':0,'rationale':'در مبنای تعهدی درآمد تحقق یافته است و حساب دریافتنی ثبت می‌شود.',
           'source_reference':'اصول حسابداری تعهدی؛ بازبینی لازم'}
        result=server.import_questions([q])
        self.assertEqual(result['imported'],1)
        self.assertEqual(len(server.QUESTIONS),201)
        with self.assertRaises(ValueError):server.import_questions([q])
        with self.assertRaises(ValueError):server.import_questions([dict(q,correct_index=4)])
        self.assertEqual(len(server.QUESTIONS),201)
        self.assertEqual(server.bank_summary()['actual'],201)
        server.open_db(Path(self.tmp.name)/'db.sqlite3')
        self.assertEqual(len(server.QUESTIONS),201)
        item=server.create_exam('داوطلب جدید','intern')
        self.assertEqual(server.candidate_current(item['code'])['total'],100)

    def test_resume_and_role_start(self):
        for role in server.ROLES:
            item=server.create_exam('داوطلب تست',role)
            for i in range(3):
                current=server.candidate_current(item['code'])
                server.answer_exam(item['code'],1)
            self.assertEqual(server.candidate_current(item['code'])['answered'],3)
            self.assertEqual(server.assignment_count(item['id']),50)
            anchor=server.CONN.execute('SELECT a.question_id FROM assignments a WHERE exam_id=? LIMIT 1',(item['id'],)).fetchone()[0]
            diff=server.BY_ID[anchor]['difficulty']
            self.assertIn(diff,(['easy','medium'] if role!='accountant' else ['medium','hard']))

class HttpTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        server.open_db(Path(self.tmp.name)/'db.sqlite3')
        self.httpd=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
        self.thread=threading.Thread(target=self.httpd.serve_forever,daemon=True)
        self.thread.start()
        self.port=self.httpd.server_port
    def tearDown(self):
        self.httpd.shutdown();self.httpd.server_close();self.thread.join(2)
        server.CONN.close();server.CONN=None;self.tmp.cleanup()
    def req(self,method,path,body=None,cookie=None,code=None,origin=None):
        c=http.client.HTTPConnection('127.0.0.1',self.port,timeout=10)
        headers={}
        if body is not None:
            headers['Content-Type']='application/json'
            body=json.dumps(body,ensure_ascii=False).encode('utf-8')
        if cookie:headers['Cookie']='miz_admin='+cookie
        if code:headers['X-Exam-Code']=code
        if origin:headers['Origin']=origin
        c.request(method,path,body=body,headers=headers)
        r=c.getresponse();b=r.read();status=r.status;hdr=dict(r.getheaders());c.close()
        try:b=json.loads(b)
        except:pass
        return status,b,hdr
    def test_http_permissions_and_candidates(self):
        s,b,h=self.req('GET','/api/meta');self.assertEqual(s,200)
        self.assertFalse(b['initialized'])
        s,b,h=self.req('GET','/api/admin/bank');self.assertEqual(s,403)
        s,b,h=self.req('POST','/api/admin/setup',{'password':'secure_password_123'})
        self.assertEqual(s,201)
        s,b,h=self.req('POST','/api/admin/login',{'password':'secure_password_123'})
        self.assertEqual(s,200)
        token=h['Set-Cookie'].split(';')[0].split('=')[1]
        s,b,h=self.req('POST','/api/admin/exams',{'candidate':'امین تست','role':'intern'},cookie=token)
        self.assertEqual(s,201)
        code=b['code'];eid=b['id']
        s,b,h=self.req('GET','/api/admin/reports/'+eid)
        self.assertEqual(s,403)
        s,b,h=self.req('GET','/api/admin/questions')
        self.assertEqual(s,403)
        s,b,h=self.req('GET','/api/candidate/current',code=code)
        self.assertEqual(s,200)
        self.assertEqual(len(b['question']['options']),4)
        self.assertNotIn('correct_index',str(b))
        self.assertNotIn('rationale',str(b))
        s,b,h=self.req('POST','/api/candidate/answer',{'choice':0},code=code)
        self.assertEqual(s,200)
        self.assertNotIn('is_correct',b)
        self.assertNotIn('answer',b)
        s,b,h=self.req('GET','/api/admin/reports/'+eid,cookie=token)
        self.assertEqual(s,200)
        self.assertEqual(b['answered'],1)
        s,b,h=self.req('GET','/api/admin/questions',cookie=token)
        self.assertEqual(s,200)
        self.assertEqual(len(b),200)
        s,b,h=self.req('GET','/static/../bank_source.py')
        self.assertEqual(s,404)
        s,b,h=self.req('POST','/api/admin/exams',{'candidate':'تست','role':'intern'},cookie=token,origin='https://attacker.example')
        self.assertEqual(s,403)

if __name__=='__main__':unittest.main()