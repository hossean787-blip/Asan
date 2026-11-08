"""Offline candidate/employer flow source contract tests (no external dependencies)."""
import unittest, json, re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
HTML=(ROOT/'android-wrapper/app/src/main/assets/demo.html').read_text(encoding='utf-8')
MAIN=(ROOT/'android-wrapper/app/src/main/java/ir/mizmosahabe/accounting/MainActivity.java').read_text(encoding='utf-8')

def questions():
    match=re.search(r'const QUESTION_BANK = (\[.*?\]);\nconst roles=',HTML,re.S)
    if not match: raise AssertionError('QUESTION_BANK not found')
    return json.loads(match.group(1))

class CandidateFlowTests(unittest.TestCase):
    def test_100_unique_pilot_questions_and_answer_keys(self):
        data=questions()
        self.assertGreaterEqual(len(data),100)
        self.assertEqual(len(data),len({v['id'] for v in data}))
        self.assertEqual(len(data),len({v['text'] for v in data}))
        self.assertGreaterEqual(len({v['topic'] for v in data}),25)
        self.assertEqual({'easy','medium','hard'}, {v['difficulty'] for v in data})
        for v in data:
            self.assertEqual(len(v['options']),4)
            self.assertEqual(len(set(v['options'])),4)
            self.assertIn(v['answer'],range(4))

    def test_three_roles_and_required_personal_form(self):
        for label in ['کارآموز حسابداری','کمک‌حسابدار','حسابدار']:
            self.assertIn(label,HTML)
        for field in ['name','mobile','education','experience','consent']:
            self.assertRegex(HTML, fr'id=\\?"{field}\\?"')
        self.assertIn('function startExam(',HTML)

    def test_timer_autofinish_resume_and_persistence(self):
        for token in ["K_RECORDS='asan:records:v214'", "K_ACTIVE='asan:active:v214'", "K_PIN='asan:pin:v214'",'const N=100','DEFAULT_MINUTES=20','function remaining()','function complete(timedOut)','if(remaining()<=0){complete(true);return}','setInterval(tick,1000)','localStorage.removeItem(K_ACTIVE)']:
            self.assertIn(token,HTML)

    def test_only_admin_shows_answer_key_in_ui(self):
        self.assertIn('if(!state.adminOK)',HTML)
        self.assertIn('async function submitPin(',HTML)
        self.assertIn('پاسخ‌های ثبت‌شده',HTML)
        self.assertIn('پاسخ صحیح:',HTML)
        self.assertIn('data-report=',HTML)
        self.assertIn('state.adminOK=false;go(\'finished\')',HTML)

    def test_android_privacy_and_offline_persistence(self):
        for token in ['showDemo();','settings.setDomStorageEnabled(true);','setAllowFileAccess(false)','setAllowContentAccess(false)','setWebContentsDebuggingEnabled(BuildConfig.DEBUG)', 'asan-demo.invalid','getAssets().open("demo.html")', 'setAcceptThirdPartyCookies(web, false)']:
            self.assertIn(token,MAIN)
        self.assertIn('android:allowBackup="false"',(ROOT/'android-wrapper/app/src/main/AndroidManifest.xml').read_text())

if __name__=='__main__':unittest.main()