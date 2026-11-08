"""Offline preview contract; demo content is public and cannot be used for hiring."""
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / 'android-wrapper/app/src/main/assets/demo.html'
JAVA = ROOT / 'android-wrapper/app/src/main/java/ir/mizmosahabe/accounting/MainActivity.java'

class OfflineDemoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = HTML.read_text(encoding='utf-8')
        cls.java = JAVA.read_text(encoding='utf-8')
        match = re.search(r'const QUESTION_BANK = (\[.*?\]);\s*const roles', cls.html, re.S)
        assert match, 'embedded demo questions not found'
        cls.questions = json.loads(match.group(1))

    def test_question_bank_integrity(self):
        q = self.questions
        self.assertEqual(len(q), 30)
        self.assertEqual(len({x['id'] for x in q}), 30)
        self.assertGreaterEqual(len({x['topic'] for x in q}), 25)
        for item in q:
            self.assertEqual(len(item['options']), 4)
            self.assertEqual(len(set(item['options'])), 4)
            self.assertIn(item['answer'], range(4))
            self.assertIn(item['difficulty'], ('easy','medium','hard'))

    def test_offline_demo_never_accesses_network(self):
        self.assertIn('setAllowFileAccess(false)', self.java)
        self.assertIn('setAllowContentAccess(false)', self.java)
        self.assertIn('demoMode = true', self.java)
        self.assertIn('new ByteArrayInputStream(new byte[0])', self.java)
        self.assertIn('showDemo();', self.java)
        self.assertIn('getAssets().open("demo.html")', self.java)
        self.assertNotIn('https://server.example.com', self.html)
        self.assertNotIn('fetch(', self.html)
        self.assertNotIn('XMLHttpRequest', self.html)

    def test_theme_and_clear_disclaimer(self):
        self.assertIn('#50C787', self.html)
        self.assertIn('آسان', self.html)
        self.assertIn('نسخه نمایشی', self.html)
        self.assertIn('مبنای تصمیم استخدامی نیست', self.html)
        self.assertIn('data-action="server"', self.html)

if __name__ == '__main__':
    unittest.main()