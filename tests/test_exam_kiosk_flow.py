"""Contract regression tests for v2.1.7 candidate exam kiosk."""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
HTML=(ROOT/'android-wrapper/app/src/main/assets/demo.html').read_text(encoding='utf-8')
JAVA=(ROOT/'android-wrapper/app/src/main/java/ir/mizmosahabe/accounting/MainActivity.java').read_text(encoding='utf-8')

class ExamKioskFlowTests(unittest.TestCase):
    def test_timer_starts_only_after_laws_accepted(self):
        self.assertIn('function instructionPage()',HTML)
        self.assertIn('function beginConfirmedExam()',HTML)
        self.assertIn("state.profile=profile;go('instructions')",HTML)
        self.assertIn("case 'startConfirmed':beginConfirmedExam()",HTML)
        self.assertIn('deadline:start+DEFAULT_MINUTES*60000,minutes:DEFAULT_MINUTES',HTML)
        self.assertIn('DEFAULT_MINUTES=20',HTML)

    def test_no_manual_navigation_or_submission(self):
        for old in ('data-act="next"','data-act="prev"','data-act="submit"',"case 'next':","case 'prev':","case 'submit':"):
            self.assertNotIn(old,HTML)
        self.assertIn('function chooseAnswer(index)',HTML)
        self.assertIn('advanceQuestion()',HTML)
        self.assertIn('function skipQuestion()',HTML)
        self.assertIn('data-act="skip"',HTML)
        self.assertIn('if(state.idx+1>=N){complete(false);return}',HTML)

    def test_no_scroll_and_two_by_two_options(self):
        self.assertIn('html.exam-active, body.exam-active{height:100%;overflow:hidden',HTML)
        self.assertIn('grid-template-columns:repeat(2,minmax(0,1fr))',HTML)
        self.assertIn('grid-template-rows:repeat(2,minmax(0,1fr))',HTML)
        self.assertIn('exam-viewport',HTML)
        self.assertIn('class="exam-option"',HTML)

    def test_exit_security_and_reports(self):
        self.assertIn('function asanOnBackground()',HTML)
        self.assertIn('window.asanOnBackground=asanOnBackground',HTML)
        self.assertIn("document.addEventListener('visibilitychange'",HTML)
        self.assertIn("window.addEventListener('pagehide',asanOnBackground)",HTML)
        self.assertIn("endedByExit:reason==='background'",HTML)
        self.assertIn('پایان به‌دلیل خروج از برنامه',HTML)
        self.assertIn('onPause()',JAVA)
        self.assertIn('onResume()',JAVA)
        self.assertIn('demoWasBackgrounded',JAVA)
        self.assertIn('result -> finish()',JAVA)

    def test_preserve_existing_results_and_admin(self):
        self.assertIn("K_RECORDS='asan:records:v214'",HTML)
        self.assertIn("K_PIN='asan:pin:v214'",HTML)
        self.assertIn('function statsPage(all)',HTML)
        self.assertIn('function detailPage(r)',HTML)
        self.assertIn('if(!state.adminOK)',HTML)

if __name__=='__main__': unittest.main()