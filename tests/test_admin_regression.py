"""Asan interviewer management 2.1.8 regression contracts (no external dependencies)."""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
HTML=(ROOT/'android-wrapper/app/src/main/assets/demo.html').read_text(encoding='utf-8')

class EmployerManagementTests(unittest.TestCase):
    def test_brand_dashboard_and_tabs(self):
        for s in ['function adminOverview()', 'function candidateListPage()', 'function adminFrame(', 'function adminMetric(', 'مرکز مدیریت استخدام', 'function statsPage(all)', '#50C787', 'function tabButtons()']:
            self.assertIn(s,HTML)
        self.assertIn("state.adminTab==='list'",HTML)

    def test_candidate_search_filters_and_sort(self):
        for s in ['id="adminSearch"', 'id="adminRoleFilter"', 'id="adminStatusFilter"', 'id="adminSort"', 'function adminRecordsFiltered()', "state.adminQuery=e.target.value", 'refreshCandidateRows()', 'data-report=', 'score_desc', 'score_asc']:
            self.assertIn(s,HTML)

    def test_interviewer_private_manual_stage_notes(self):
        for s in ["K_REVIEWS='asan:reviews:v218'", 'function saveReview(form)', 'function reviewOf(id)', 'id="reviewForm"', 'id="reviewStatus"', 'id="reviewNote"', 'data-act="logout"', "if(!state.adminOK)", "if(e.target.id==='reviewForm')", 'STATUS_LABELS']:
            self.assertIn(s,HTML)
        self.assertIn('note=form.querySelector',HTML)
        self.assertIn('maxlength="1000"',HTML)

    def test_original_candidate_timing_preserved(self):
        for s in ["DEFAULT_MINUTES=20", 'function instructionPage()', 'function examPage()', 'function complete(timedOut,reason)', 'window.asanOnBackground=asanOnBackground', "K_RECORDS='asan:records:v214'", "K_ACTIVE='asan:active:v214'", "K_PIN='asan:pin:v214'", 'function detailPage(r)', 'پاسخ صحیح:']:
            self.assertIn(s,HTML)

    def test_no_persistent_auto_hiring_decision(self):
        self.assertIn('تصمیم نهایی فقط با مسئول استخدام است',HTML)
        self.assertNotIn('window.localStorage.clear()',HTML)

if __name__=='__main__': unittest.main()