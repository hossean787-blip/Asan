"""Branding, employer report and statistics smoke contracts for Asan 2.1.5 beta."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "android-wrapper/app/src/main/assets/demo.html"
ICON = ROOT / "android-wrapper/app/src/main/res/drawable/ic_launcher.xml"
BUILD = ROOT / "android-wrapper/app/build.gradle"

class InterviewerAnalyticsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = HTML.read_text(encoding="utf-8")
        cls.icon = ICON.read_text(encoding="utf-8")
        cls.gradle = BUILD.read_text(encoding="utf-8")

    def test_asans_exact_brand_identity(self):
        self.assertIn("data:image/webp;base64,", self.html)
        self.assertIn('class="brand-icon"', self.html)
        self.assertIn('class="welcome-brand"', self.html)
        self.assertIn("#50C787", self.icon)
        self.assertIn("versionCode 11", self.gradle)
        self.assertIn("versionName '2.1.8-beta'", self.gradle)

    def test_interviewer_stats_locked_to_admin(self):
        self.assertIn("function statsPage(all)", self.html)
        self.assertIn("function detailPage(r)", self.html)
        self.assertIn("if(state.adminOK){state.adminTab='stats'", self.html)
        self.assertIn("if(statRole&&state.adminOK)", self.html)
        self.assertIn("if(e.target.id==='questionStatSelect'&&state.adminOK)", self.html)
        self.assertIn("if(af&&state.adminOK)", self.html)

    def test_each_option_and_per_topic_results(self):
        self.assertIn("آمار انتخاب گزینه‌های هر سؤال", self.html)
        self.assertIn("پاسخنامه مخصوص مصاحبه‌گر", self.html)
        self.assertIn("توزیع نمره داوطلبان", self.html)
        self.assertIn("تحلیل حوزه‌های حسابداری", self.html)
        self.assertIn("انتخاب داوطلب", self.html)
        self.assertIn("بدون پاسخ", self.html)
        self.assertIn("data-answer-filter=", self.html)

    def test_pilot_data_keys_not_reset(self):
        for key in ("asan:records:v214", "asan:active:v214", "asan:pin:v214"):
            self.assertIn(key, self.html)
        self.assertIn("بانک سؤالات نمونه عمومی", self.html)

if __name__ == "__main__":
    unittest.main()
