"""Regression checks for the fixed 20-minute candidate exam in Asan.

The employer's legacy duration preference must not extend new examinations.
Already-started exams keep their originally persisted deadline.
"""
import unittest
from pathlib import Path

HTML = (Path(__file__).resolve().parents[1] / "android-wrapper/app/src/main/assets/demo.html")

class FixedTwentyMinuteExamTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = HTML.read_text(encoding="utf-8")

    def test_fixed_default_and_visible_duration(self):
        self.assertIn("const N=100, DEFAULT_MINUTES=20,", self.html)
        self.assertIn("زمان ثابت هر آزمون جدید", self.html)
        self.assertIn("۲۰ دقیقه", self.html)
        self.assertNotIn("DEFAULT_MINUTES=90", self.html)

    def test_new_attempts_ignore_old_saved_duration(self):
        self.assertIn("function setting(){return {minutes:DEFAULT_MINUTES}}", self.html)
        self.assertIn("deadline:start+DEFAULT_MINUTES*60000,minutes:DEFAULT_MINUTES,", self.html)
        self.assertNotIn("deadline:start+setting().minutes*60000", self.html)
        self.assertNotIn("getJSON(K_CONFIG,{minutes:DEFAULT_MINUTES})", self.html)

    def test_timer_remains_auto_submitted_and_persisted(self):
        self.assertIn("function remaining()", self.html)
        self.assertIn("state.exam.deadline-Date.now()", self.html)
        self.assertIn("if(remaining()<=0){complete(true);return}", self.html)
        self.assertIn("setInterval(tick,1000)", self.html)
        self.assertIn("function saveActive()", self.html)
        self.assertIn("K_RECORDS='asan:records:v214'", self.html)

    def test_no_duration_editing_remains(self):
        self.assertNotIn('id="duration"', self.html)
        self.assertNotIn('data-act="saveDuration"', self.html)
        self.assertNotIn("case 'saveDuration'", self.html)

if __name__ == "__main__":
    unittest.main()
