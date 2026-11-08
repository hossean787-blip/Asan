"""Source-level preflight checks; these are NOT an APK build or device tests."""
import unittest
from pathlib import Path
import re
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
ANDROID = ROOT / 'android-wrapper'
JAVA = ANDROID / 'app/src/main/java/ir/mizmosahabe/accounting/MainActivity.java'

class AndroidContractTests(unittest.TestCase):
    def test_package_version_and_platform(self):
        gradle = (ANDROID / 'app/build.gradle').read_text()
        for check in ["applicationId 'ir.mizmosahabe.accounting'", 'versionCode 7',
                      "versionName '2.1.4-beta'", 'minSdk 24', 'compileSdk 35', 'targetSdk 35']:
            self.assertIn(check, gradle)

    def test_manifest_security_and_debug_separation(self):
        a = '{http://schemas.android.com/apk/res/android}'
        prod = ET.parse(ANDROID / 'app/src/main/AndroidManifest.xml').getroot()
        debug = ET.parse(ANDROID / 'app/src/debug/AndroidManifest.xml').getroot()
        p = prod.find('application'); d = debug.find('application')
        self.assertEqual(p.attrib[a+'usesCleartextTraffic'], 'false')
        self.assertEqual(p.attrib[a+'allowBackup'], 'false')
        self.assertEqual(d.attrib[a+'usesCleartextTraffic'], 'true')
        self.assertEqual(prod.find('uses-permission').attrib[a+'name'], 'android.permission.INTERNET')

    def test_brand_is_consistent(self):
        j = JAVA.read_text()
        theme = (ANDROID / 'app/src/main/res/values/styles.xml').read_text()
        web_theme = (ROOT / 'static/theme-green.css').read_text()
        self.assertIn('Color.rgb(80, 199, 135)', j)
        self.assertIn('#50C787', theme)
        self.assertIn('Color.WHITE', j)
        self.assertIn('#50C787', web_theme)

    def test_origin_webview_downloads(self):
        j = JAVA.read_text()
        for token in ['isCompanyUrl(request.getUrl())', 'isCompanyUrl(u)',
                      'setAcceptThirdPartyCookies(web, false)', 'setAllowFileAccess(false)',
                      'setAllowContentAccess(false)', 'setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW)',
                      'setWebContentsDebuggingEnabled(BuildConfig.DEBUG)',
                      'BuildConfig.DEBUG && "http"', '/api/admin/reports/',
                      'System.currentTimeMillis() + ".csv"']:
            self.assertIn(token, j)
        self.assertNotRegex(j, r'(?i)password\s*=\s*"[^\"]+"')

    def test_release_workflows_are_present(self):
        c = (ROOT / '.github/workflows/build-internal-release.yml').read_text()
        s = (ROOT / '.github/workflows/build-signed-release.yml').read_text()
        self.assertIn('assembleRelease', c)
        self.assertIn('apksigner" verify', c)
        self.assertIn('retention-days: 14', c)
        self.assertIn('openssl rand -hex', c)
        self.assertIn('MIZ_KEYSTORE_BASE64', s)
        self.assertIn('assembleRelease', s)
        self.assertIn('if-no-files-found: error', s)
        self.assertNotIn('publish_release', c + s)

if __name__ == '__main__':
    unittest.main()