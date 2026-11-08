package ir.mizmosahabe.accounting;

import android.app.Activity;
import android.app.AlertDialog;
import android.app.DownloadManager;
import android.content.Context;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Environment;
import android.print.PrintManager;
import android.view.Gravity;
import android.view.Menu;
import android.view.MenuItem;
import android.view.View;
import android.webkit.CookieManager;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.EditText;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.util.Locale;

/** Android client only; tests, candidate records and answer keys stay on company server. */
public final class MainActivity extends Activity {
    private static final String KEY_URL = "server_url";
    private static final int GREEN = Color.rgb(80, 199, 135);  // #50C787
    private static final int DARK = Color.rgb(13, 75, 50);
    private static final int INK = Color.rgb(24, 50, 40);
    private static final int MIST = Color.rgb(237, 249, 242);
    private static final int MUTED = Color.rgb(90, 113, 103);
    private static final int LINE = Color.rgb(215, 233, 221);
    private WebView web;
    private Uri serverOrigin;
    private boolean demoMode;

    private int dp(float v) {
        return Math.round(v * getResources().getDisplayMetrics().density);
    }

    private GradientDrawable background(int fill, int radius, int stroke) {
        GradientDrawable drawable = new GradientDrawable();
        drawable.setColor(fill);
        drawable.setCornerRadius(dp(radius));
        if (stroke != 0) drawable.setStroke(dp(1), stroke);
        return drawable;
    }

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        getWindow().setStatusBarColor(GREEN);
        getWindow().setNavigationBarColor(Color.WHITE);
        int flags = View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR;
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) flags |= View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR;
        getWindow().getDecorView().setSystemUiVisibility(flags);
        if (getActionBar() != null) {
            getActionBar().setTitle("آسان | استخدام حسابداری");
        }
        // Candidate-first by design: company mode is accessed only through the admin screen.
        showDemo();
    }

    private TextView label(String value, int size, boolean bold, int color) {
        TextView t = new TextView(this);
        t.setText(value);
        t.setTextColor(color);
        t.setTextSize(size);
        t.setGravity(Gravity.RIGHT);
        t.setTextDirection(View.TEXT_DIRECTION_RTL);
        if (bold) t.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        return t;
    }

    private boolean isValidUrl(String raw) {
        if (raw == null || !raw.equals(raw.trim())) return false;
        try {
            Uri uri = Uri.parse(raw);
            String scheme = uri.getScheme();
            if (scheme == null || uri.getHost() == null || uri.getHost().isEmpty()) return false;
            if (uri.getUserInfo() != null || uri.getFragment() != null || uri.getQuery() != null) return false;
            if (uri.getPort() > 65535 || uri.getPort() == 0) return false;
            if (uri.getPath() != null && !uri.getPath().isEmpty() && !"/".equals(uri.getPath())) return false;
            if (!"https".equalsIgnoreCase(scheme) && !(BuildConfig.DEBUG && "http".equalsIgnoreCase(scheme))) return false;
            return true;
        } catch (Exception ignored) {
            return false;
        }
    }

    /** Local demonstration on this single device; not a secure remote recruitment service. */
    private void showDemo() {
        demoMode = true;
        serverOrigin = null;
        if (web != null) { web.destroy(); web = null; }
        if (getActionBar() != null) getActionBar().hide();
        try (InputStream in = getAssets().open("demo.html");
             ByteArrayOutputStream buffer = new ByteArrayOutputStream()) {
            byte[] chunk = new byte[8192];
            int n;
            while ((n = in.read(chunk)) != -1) buffer.write(chunk, 0, n);
            String document = buffer.toString("UTF-8");
            web = new WebView(this);
            web.setBackgroundColor(Color.WHITE);
            WebView.setWebContentsDebuggingEnabled(BuildConfig.DEBUG);
            WebSettings settings = web.getSettings();
            settings.setJavaScriptEnabled(true);
            // Persist active timed exams and reviewed reports across app restarts.
            settings.setDomStorageEnabled(true);
            settings.setAllowFileAccess(false);
            settings.setAllowContentAccess(false);
            settings.setAllowFileAccessFromFileURLs(false);
            settings.setAllowUniversalAccessFromFileURLs(false);
            settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
            settings.setSupportMultipleWindows(false);
            settings.setJavaScriptCanOpenWindowsAutomatically(false);
            CookieManager.getInstance().setAcceptThirdPartyCookies(web, false);
            web.setWebViewClient(new WebViewClient() {
                @Override public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest req) {
                    Uri uri = req.getUrl();
                    if ("asan".equalsIgnoreCase(uri.getScheme())) {
                        if ("setup".equalsIgnoreCase(uri.getHost())) showSetup();
                        else if ("print".equalsIgnoreCase(uri.getHost())) printCurrentPage();
                    }
                    // No remote navigation, tracking or third-party resources from offline mode.
                    return true;
                }
                @Override public WebResourceResponse shouldInterceptRequest(WebView view, WebResourceRequest req) {
                    return new WebResourceResponse("text/plain", "utf-8", new ByteArrayInputStream(new byte[0]));
                }
            });
            setContentView(web);
            web.loadDataWithBaseURL("https://asan-demo.invalid/", document, "text/html", "UTF-8", null);
            invalidateOptionsMenu();
        } catch (Exception e) {
            Toast.makeText(this, "بارگذاری رابط آفلاین آسان ممکن نشد.", Toast.LENGTH_LONG).show();
            showSetup();
        }
    }

    private void printCurrentPage() {
        if (web == null) return;
        try {
            PrintManager pm = (PrintManager) getSystemService(Context.PRINT_SERVICE);
            pm.print("گزارش مصاحبه آسان", web.createPrintDocumentAdapter("گزارش مصاحبه آسان"), null);
        } catch (Exception ex) {
            Toast.makeText(this, "چاپ گزارش در دسترس نیست.", Toast.LENGTH_LONG).show();
        }
    }

    private void showSetup() {
        demoMode = false;
        if (getActionBar() != null) getActionBar().hide();
        serverOrigin = null;
        if (web != null) { web.destroy(); web = null; }
        LinearLayout content = new LinearLayout(this);
        content.setOrientation(LinearLayout.VERTICAL);
        content.setPadding(dp(22), dp(34), dp(22), dp(36));
        content.setLayoutDirection(View.LAYOUT_DIRECTION_RTL);
        content.setBackgroundColor(Color.WHITE);
        Button back = new Button(this);
        back.setAllCaps(false);
        back.setText("بازگشت به آسان ←");
        back.setTextColor(DARK);
        back.setBackground(background(MIST, 12, LINE));
        back.setOnClickListener(v -> showDemo());
        content.addView(back, new LinearLayout.LayoutParams(-1, dp(45)));

        ImageView logo = new ImageView(this);
        logo.setImageResource(R.drawable.ic_launcher);
        logo.setContentDescription("نشان میز مصاحبه");
        LinearLayout.LayoutParams logoP = new LinearLayout.LayoutParams(dp(80), dp(80));
        logoP.gravity = Gravity.RIGHT;
        content.addView(logo, logoP);
        TextView name = label("میز مصاحبه حسابداری", 25, true, DARK);
        LinearLayout.LayoutParams nP = new LinearLayout.LayoutParams(-1, -2);
        nP.topMargin = dp(14);
        content.addView(name, nP);
        TextView subtitle = label("سامانه ارزیابی استخدامی شرکت‌ها", 14, false, MUTED);
        LinearLayout.LayoutParams subP = new LinearLayout.LayoutParams(-1, -2);
        subP.topMargin = dp(8);
        content.addView(subtitle, subP);

        LinearLayout panel = new LinearLayout(this);
        panel.setOrientation(LinearLayout.VERTICAL);
        panel.setPadding(dp(18), dp(20), dp(18), dp(20));
        panel.setBackground(background(MIST, 20, LINE));
        LinearLayout.LayoutParams panelP = new LinearLayout.LayoutParams(-1, -2);
        panelP.topMargin = dp(30);
        content.addView(panel, panelP);
        panel.addView(label("اتصال امن به سرور شرکت", 17, true, INK));
        TextView hint = label("آدرس HTTPS سرور را وارد کنید. سؤالات، نتایج و پاسخنامه در سرور نگهداری می‌شوند.", 13, false, MUTED);
        LinearLayout.LayoutParams hintP = new LinearLayout.LayoutParams(-1, -2);
        hintP.topMargin = dp(9);
        panel.addView(hint, hintP);

        EditText input = new EditText(this);
        input.setSingleLine(true);
        input.setTextDirection(View.TEXT_DIRECTION_LTR);
        input.setTextSize(15);
        input.setTextColor(INK);
        input.setHintTextColor(MUTED);
        input.setHint("https://server.example.com");
        input.setInputType(android.text.InputType.TYPE_CLASS_TEXT | android.text.InputType.TYPE_TEXT_VARIATION_URI);
        input.setPadding(dp(14), 0, dp(14), 0);
        input.setBackground(background(Color.WHITE, 12, LINE));
        input.setText(getPreferences(MODE_PRIVATE).getString(KEY_URL, ""));
        LinearLayout.LayoutParams inputP = new LinearLayout.LayoutParams(-1, dp(56));
        inputP.topMargin = dp(22);
        panel.addView(input, inputP);

        Button connect = new Button(this);
        connect.setText("اتصال به سامانه");
        connect.setAllCaps(false);
        connect.setTextColor(DARK);
        connect.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        connect.setBackground(background(GREEN, 12, 0));
        LinearLayout.LayoutParams btnP = new LinearLayout.LayoutParams(-1, dp(52));
        btnP.topMargin = dp(14);
        panel.addView(connect, btnP);

        TextView notice = label(BuildConfig.DEBUG
            ? "نسخه آزمایشی: اتصال HTTP فقط در شبکه داخلیِ مورد اعتماد توصیه می‌شود."
            : "نسخه انتشار فقط اتصال رمزگذاری‌شده HTTPS را می‌پذیرد.", 12, false, MUTED);
        LinearLayout.LayoutParams noteP = new LinearLayout.LayoutParams(-1, -2);
        noteP.topMargin = dp(18);
        content.addView(notice, noteP);

        connect.setOnClickListener(v -> {
            String url = input.getText().toString().trim();
            if (url.endsWith("/")) url = url.substring(0, url.length() - 1);
            if (!isValidUrl(url)) {
                Toast.makeText(this, BuildConfig.DEBUG
                    ? "نشانی HTTP یا HTTPS معتبر بدون مسیر اضافی وارد کنید."
                    : "نشانی HTTPS معتبر بدون مسیر اضافی وارد کنید.", Toast.LENGTH_LONG).show();
                return;
            }
            getPreferences(MODE_PRIVATE).edit().putString(KEY_URL, url).apply();
            openWeb(url);
        });
        ScrollView scroll = new ScrollView(this);
        scroll.setFillViewport(true);
        scroll.addView(content);
        setContentView(scroll);
        invalidateOptionsMenu();
    }

    private int port(Uri uri) {
        if (uri.getPort() > 0) return uri.getPort();
        return "https".equalsIgnoreCase(uri.getScheme()) ? 443 : 80;
    }

    private boolean isCompanyUrl(Uri target) {
        if (target == null || serverOrigin == null) return false;
        return serverOrigin.getScheme().equalsIgnoreCase(target.getScheme())
            && serverOrigin.getHost().equalsIgnoreCase(target.getHost() == null ? "" : target.getHost())
            && port(serverOrigin) == port(target)
            && target.getUserInfo() == null;
    }

    private void openWeb(String url) {
        demoMode = false;
        if (getActionBar() != null) getActionBar().show();
        serverOrigin = Uri.parse(url);
        web = new WebView(this);
        WebView.setWebContentsDebuggingEnabled(BuildConfig.DEBUG);
        web.setBackgroundColor(Color.WHITE);
        WebSettings settings = web.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setAllowFileAccess(false);
        settings.setAllowContentAccess(false);
        settings.setAllowFileAccessFromFileURLs(false);
        settings.setAllowUniversalAccessFromFileURLs(false);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        settings.setSupportMultipleWindows(false);
        settings.setJavaScriptCanOpenWindowsAutomatically(false);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) settings.setSafeBrowsingEnabled(true);
        CookieManager.getInstance().setAcceptThirdPartyCookies(web, false);
        web.setWebViewClient(new WebViewClient() {
            @Override public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                if (isCompanyUrl(request.getUrl())) return false;
                Toast.makeText(MainActivity.this, "خروج از سرور شرکت مسدود شد.", Toast.LENGTH_SHORT).show();
                return true;
            }
            @Override public WebResourceResponse shouldInterceptRequest(WebView view, WebResourceRequest request) {
                Uri u = request.getUrl();
                String scheme = u.getScheme();
                if ("https".equalsIgnoreCase(scheme) || "http".equalsIgnoreCase(scheme)) {
                    if (!isCompanyUrl(u)) {
                        return new WebResourceResponse("text/plain", "utf-8", new ByteArrayInputStream(new byte[0]));
                    }
                }
                return null;
            }
            @Override public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) {
                if (request.isForMainFrame()) {
                    new AlertDialog.Builder(MainActivity.this)
                        .setTitle("سرور در دسترس نیست")
                        .setMessage("نشانی سرور و اتصال شبکه شرکت را بررسی کنید.")
                        .setPositiveButton("تلاش مجدد", (dialog, which) -> { if (web != null) web.reload(); })
                        .setNegativeButton("تغییر سرور", (dialog, which) -> showSetup()).show();
                }
            }
        });
        web.setDownloadListener((link, userAgent, contentDisposition, mimeType, length) -> {
            Uri target = Uri.parse(link);
            if (!isCompanyUrl(target) || target.getPath() == null
                    || !target.getPath().startsWith("/api/admin/reports/")) {
                Toast.makeText(this, "دریافت فایل از نشانی دیگر مجاز نیست.", Toast.LENGTH_LONG).show();
                return;
            }
            try {
                DownloadManager.Request req = new DownloadManager.Request(target);
                String cookie = CookieManager.getInstance().getCookie(url);
                if (cookie != null && !cookie.isEmpty()) req.addRequestHeader("Cookie", cookie);
                req.setTitle("گزارش مصاحبه حسابداری");
                req.setMimeType("text/csv");
                req.setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED);
                req.setDestinationInExternalFilesDir(this, Environment.DIRECTORY_DOWNLOADS,
                    "accounting-report-" + System.currentTimeMillis() + ".csv");
                ((DownloadManager) getSystemService(Context.DOWNLOAD_SERVICE)).enqueue(req);
                Toast.makeText(this, "گزارش در فایل‌های برنامه ذخیره می‌شود.", Toast.LENGTH_LONG).show();
            } catch (Exception e) {
                Toast.makeText(this, "خطا در ذخیره گزارش", Toast.LENGTH_LONG).show();
            }
        });
        setContentView(web);
        invalidateOptionsMenu();
        web.loadUrl(url);
    }

    @Override public boolean onCreateOptionsMenu(Menu menu) {
        menu.add(0, 1, 0, "تنظیم آدرس سرور");
        menu.add(0, 2, 1, "چاپ / PDF");
        menu.add(0, 3, 2, "بارگذاری مجدد");
        return true;
    }

    @Override public boolean onPrepareOptionsMenu(Menu menu) {
        menu.findItem(2).setEnabled(web != null);
        menu.findItem(3).setEnabled(web != null);
        return true;
    }

    @Override public boolean onOptionsItemSelected(MenuItem item) {
        if (item.getItemId() == 1) {
            showSetup(); return true;
        }
        if (item.getItemId() == 2 && web != null) {
            PrintManager pm = (PrintManager) getSystemService(Context.PRINT_SERVICE);
            pm.print("گزارش مصاحبه", web.createPrintDocumentAdapter("گزارش مصاحبه"), null);
            return true;
        }
        if (item.getItemId() == 3 && web != null) {
            web.reload(); return true;
        }
        return super.onOptionsItemSelected(item);
    }

    private boolean demoWasBackgrounded = false;
    @Override protected void onPause() {
        if (demoMode && web != null) {
            demoWasBackgrounded = true;
            // Finalize a live candidate exam before Android backgrounds this Activity.
            web.evaluateJavascript("window.asanOnBackground && window.asanOnBackground();", null);
        }
        super.onPause();
    }

    @Override protected void onResume() {
        super.onResume();
        if (demoWasBackgrounded && demoMode && web != null) {
            demoWasBackgrounded = false;
            // Recovery in case the WebView was suspended before onPause JS ran.
            web.evaluateJavascript("window.asanOnBackground && window.asanOnBackground();", null);
        }
    }

    @Override public void onBackPressed() {
        if (demoMode && web != null) {
            web.evaluateJavascript(
                "window.asanOnBackground ? window.asanOnBackground() : false",
                result -> finish()
            );
            return;
        }
        if (web != null && !demoMode && web.canGoBack()) web.goBack();
        else if (web != null && !demoMode) showDemo();
        else super.onBackPressed();
    }

    @Override protected void onDestroy() {
        if (web != null) { web.destroy(); web = null; }
        super.onDestroy();
    }
}