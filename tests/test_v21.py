# -*- coding: utf-8 -*-
"""Release-gate checks for moderation, bank freezing, revocation, and backups."""
import http.client
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import server
from backup_database import backup_database

class V21DataTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.db=Path(self.temp.name)/'running.sqlite3'
        server.open_db(self.db)
    def tearDown(self):
        if server.CONN:server.CONN.close()
        server.CONN=None
        self.temp.cleanup()

    def test_review_audit_persistence(self):
        qid=server.SEED_QUESTIONS[0]['id']
        self.assertEqual(server.BY_ID[qid]['review_status'],'draft')
        with self.assertRaises(ValueError):server.review_question(qid,'approved','کارشناس','کوتاه')
        result=server.review_question(qid,'approved','کارشناس مالی','متن، گزینه‌ها و راه‌حل با مدارک داخلی بررسی شد.')
        self.assertEqual(result['review_status'],'approved')
        self.assertEqual(server.bank_summary()['reviewed'],1)
        server.review_question(qid,'rejected','کارشناس دوم','سؤال برای استفاده استخدامی نیازمند اصلاح علمی است.')
        history=server.review_history(qid)
        self.assertEqual([x['review_status'] for x in history],['approved','rejected'])
        server.open_db(self.db)
        self.assertEqual(server.BY_ID[qid]['review_status'],'rejected')
        self.assertEqual(server.bank_summary()['rejected'],1)
        self.assertEqual(server.bank_summary()['draft'],199)

    def test_production_approval_gate_and_snapshot(self):
        with patch.dict(os.environ,{'MIZ_REQUIRE_APPROVED':'1'}):
            with self.assertRaises(ValueError):server.create_exam('داوطلب','intern')
            for cat in server.CAT_IDS:
                pool=[q for q in server.QUESTIONS if q['category_id']==cat]
                selected=[]
                for level in ('easy','medium','hard'):
                    selected.append(next(q for q in pool if q['difficulty']==level))
                selected.append(next(q for q in pool if q['difficulty']=='medium' and q not in selected))
                for q in selected:
                    server.review_question(q['id'],'approved','کارشناس نمونه','کنترل نمونه‌ای محاسبه و گزینه‌های سؤال انجام شد.')
            self.assertEqual(server.bank_summary()['reviewed'],100)
            exam=server.create_exam('داوطلب آزمایشی','accountant')
            pool_row=server.CONN.execute('SELECT question_ids_json FROM exam_question_pool WHERE exam_id=?',(exam['id'],)).fetchone()
            pool_ids=set(json.loads(pool_row[0]))
            self.assertEqual(len(pool_ids),100)
            for n in range(100):
                q=server.candidate_current(exam['code'])['question']
                self.assertIn(q['id'],pool_ids)
                self.assertNotIn('correct_index',q)
                server.answer_exam(exam['code'],None)
            self.assertEqual(server.candidate_current(exam['code'])['status'],'completed')
            self.assertEqual(server.report(exam['id'])['answered'],100)
        self.assertEqual(server.bank_summary()['require_approved'],False)

    def test_revoke_retains_history(self):
        exam=server.create_exam('داوطلب','assistant')
        server.answer_exam(exam['code'],0)
        self.assertEqual(server.revoke_exam(exam['id'])['status'],'revoked')
        self.assertEqual(server.report(exam['id'])['answered'],1)
        with self.assertRaises(PermissionError):server.candidate_current(exam['code'])
        with self.assertRaises(ValueError):server.answer_exam(exam['code'],0)
        with self.assertRaises(ValueError):server.revoke_exam(exam['id'])

    def test_csv_injection_protection(self):
        for text in ('=SUM(1,2)','+cmd','-2+3','@bad','  =HYPERLINK'):
            self.assertTrue(server.csv_safe(text).startswith("'"))
        self.assertEqual(server.csv_safe('حسابداری'),'حسابداری')

    def test_online_backup_and_restore_integrity(self):
        server.setup_admin('strong-pilot-password')
        exam=server.create_exam('آزمایش پشتیبان','intern')
        server.answer_exam(exam['code'],1)
        destination=Path(self.temp.name)/'backups'/'snapshot.sqlite3'
        result=backup_database(self.db,destination)
        self.assertEqual(result['integrity'],'ok')
        self.assertEqual(result['rows']['exams'],1)
        self.assertEqual(result['rows']['responses'],1)
        db=sqlite3.connect(str(destination))
        try:
            self.assertEqual(db.execute('SELECT count(*) FROM responses').fetchone()[0],1)
            self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0],'ok')
        finally:db.close()
        with self.assertRaises(FileExistsError):backup_database(self.db,destination)

class V21HTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        server.open_db(Path(self.temp.name)/'db.sqlite3')
        self.srv=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
        self.worker=threading.Thread(target=self.srv.serve_forever,daemon=True)
        self.worker.start()
    def tearDown(self):
        self.srv.shutdown();self.srv.server_close();self.worker.join(2)
        server.CONN.close();server.CONN=None
        self.temp.cleanup()
    def req(self,method,path,payload=None,token=None,code=None):
        conn=http.client.HTTPConnection('127.0.0.1',self.srv.server_port,timeout=5)
        headers={}
        if token:headers['Cookie']='miz_admin='+token
        if code:headers['X-Exam-Code']=code
        if payload is not None:
            headers['Content-Type']='application/json'
            payload=json.dumps(payload,ensure_ascii=False).encode('utf8')
        conn.request(method,path,body=payload,headers=headers)
        r=conn.getresponse();raw=r.read();hdr=dict(r.getheaders());conn.close()
        return r.status,json.loads(raw),hdr
    def test_review_and_revoke_require_admin(self):
        qid=server.SEED_QUESTIONS[0]['id']
        record={'question_id':qid,'status':'approved','reviewer':'بازبین مالی','note':'منبع پاسخ و هر چهار گزینه به صورت نمونه‌ای بررسی شده است.'}
        status,_,_=self.req('POST','/api/admin/review',record)
        self.assertEqual(status,403)
        self.req('POST','/api/admin/setup',{'password':'a-strong-password-123'})
        _,_,hdr=self.req('POST','/api/admin/login',{'password':'a-strong-password-123'})
        token=hdr['Set-Cookie'].split(';')[0].split('=')[1]
        s,_,_=self.req('POST','/api/admin/review',record,token)
        self.assertEqual(s,200)
        status,body,_=self.req('GET','/api/admin/reviews?id='+qid,token=token)
        self.assertEqual(status,200);self.assertEqual(len(body),1)
        s,body,_=self.req('GET','/api/admin/questions')
        self.assertEqual(s,403)
        s,body,_=self.req('POST','/api/admin/exams',{'candidate':'کاربر آزمایشی','role':'intern'},token)
        self.assertEqual(s,201)
        code,eid=body['code'],body['id']
        s,_,_=self.req('POST','/api/admin/exams/revoke',{'id':eid})
        self.assertEqual(s,403)
        s,_,_=self.req('POST','/api/admin/exams/revoke',{'id':eid},token)
        self.assertEqual(s,200)
        s,body,_=self.req('GET','/api/candidate/current',code=code)
        self.assertEqual(s,403)
        self.assertNotIn('correct_index',str(body))

if __name__=='__main__':unittest.main()

# Note: tests discover classes by module import; this class is intentionally
# declared after the optional direct-invocation guard above.
class LegacyCompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        server.open_db(Path(self.temp.name)/'legacy.sqlite3')
    def tearDown(self):
        server.CONN.close();server.CONN=None
        self.temp.cleanup()
    def test_v2_exam_without_new_pool_remains_on_original_seed(self):
        exam=server.create_exam('داوطلب قدیمی','assistant')
        server.CONN.execute('DELETE FROM exam_question_pool WHERE exam_id=?',(exam['id'],))
        for i in range(100):
            current=server.candidate_current(exam['code'])
            if i>=50:
                self.assertIn(current['question']['id'],server.LEGACY_SEED_IDS)
            server.answer_exam(exam['code'],None)
        self.assertEqual(server.report(exam['id'])['answered'],100)