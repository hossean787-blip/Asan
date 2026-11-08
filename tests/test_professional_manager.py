"""Contract tests for the dedicated Asan employer workspace (2.1.8 beta)."""
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
HTML=(ROOT/"android-wrapper/app/src/main/assets/demo.html").read_text(encoding="utf-8")
BUILD=(ROOT/"android-wrapper/app/build.gradle").read_text(encoding="utf-8")

class ProfessionalManagerContractTests(unittest.TestCase):
    def test_standalone_employer_workspace(self):
        for text in ("function adminOverview()","function candidateListPage()","function statsPage(all)",
                     "function adminList()","admin-shell","admin-nav","admin-metric","data-admin-tab=",
                     "مرکز مدیریت استخدام"):
            self.assertIn(text,HTML)
        self.assertIn("versionCode 11",BUILD)
        self.assertIn("versionName '2.1.8-beta'",BUILD)

    def test_filter_search_sort_and_review(self):
        for text in ("id=\"adminSearch\"","id=\"adminRoleFilter\"","id=\"adminStatusFilter\"",
                     "id=\"adminSort\"","id=\"reviewStatus\"","id=\"reviewNote\"",
                     "id=\"reviewForm\"","function saveReview(form)","function reviews()"):
            self.assertIn(text,HTML)

    def test_review_is_stored_separately_and_admin_gated(self):
        self.assertIn("K_REVIEWS='asan:reviews:v218'",HTML)
        self.assertIn("if(!state.adminOK||!state.selectedId)return",HTML)
        self.assertIn("K_RECORDS='asan:records:v214'",HTML)
        self.assertIn("K_PIN='asan:pin:v214'",HTML)
        self.assertIn("if(!state.adminOK)",HTML)

    def test_candidate_exam_unmodified(self):
        for text in ("DEFAULT_MINUTES=20","const N=100","function instructionPage()",
                     "function examPage()","function skipQuestion()",
                     "window.asanOnBackground","function complete(timedOut,reason)"):
            self.assertIn(text,HTML)
        self.assertIn("#50C787",HTML)

if __name__=="__main__":
    unittest.main()
