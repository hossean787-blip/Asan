"""Public sample exam contract: not appropriate as secret production assessment."""
import json, re, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
HTML=(ROOT/'android-wrapper/app/src/main/assets/demo.html').read_text(encoding='utf-8')
JAVA=(ROOT/'android-wrapper/app/src/main/java/ir/mizmosahabe/accounting/MainActivity.java').read_text(encoding='utf-8')
class OfflineDemoTests(unittest.TestCase):
    def test_bank_has_enough_questions_for_100_item_practice(self):
        match=re.search(r'const QUESTION_BANK = (\[.*?\]);\s*const roles',HTML,re.S)
        self.assertIsNotNone(match)
        q=json.loads(match.group(1))
        self.assertGreaterEqual(len(q),100)
        self.assertEqual(len({x['id'] for x in q}),len(q))
        self.assertGreaterEqual(len({x['topic'] for x in q}),25)
    def test_demo_has_no_remote_access(self):
        for t in ['setAllowFileAccess(false)','setAllowContentAccess(false)','demoMode = true','new ByteArrayInputStream(new byte[0])','showDemo();','getAssets().open("demo.html")']:
            self.assertIn(t,JAVA)
        self.assertNotIn('https://server.example.com',HTML)
        self.assertNotIn('fetch(',HTML)
        self.assertNotIn('XMLHttpRequest',HTML)
    def test_candidate_and_employer_flow(self):
        for t in ['#50C787','آسان','آزمون آزمایشی','بانک سؤالات نمونه عمومی','data-act="server"','data-act="admin"','function personalPage()','function examPage()','function detailPage(r)','DEFAULT_MINUTES=90','const N=100']:
            self.assertIn(t,HTML)
if __name__=='__main__':unittest.main()