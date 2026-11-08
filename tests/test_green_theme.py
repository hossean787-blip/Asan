# -*- coding: utf-8 -*-
"""Regression checks for the green/white UI skin and public static assets."""
import json
from pathlib import Path
import tempfile
import unittest
import http.client
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import server

BASE=Path(__file__).resolve().parents[1]

def luminance(color):
    value=[int(color[i:i+2],16)/255 for i in (1,3,5)]
    linear=[c/12.92 if c<=.04045 else ((c+.055)/1.055)**2.4 for c in value]
    return sum(v*w for v,w in zip(linear,(.2126,.7152,.0722)))

def contrast(first,second):
    bright,dim=sorted((luminance(first),luminance(second)),reverse=True)
    return (bright+.05)/(dim+.05)

class GreenThemeTests(unittest.TestCase):
    def test_theme_is_green_and_white_and_referenced(self):
        html=(BASE/'static/index.html').read_text(encoding='utf8')
        css=(BASE/'static/theme-green.css').read_text(encoding='utf8')
        self.assertIn('/static/theme-green.css',html)
        self.assertIn('#50C787',css)
        self.assertIn('#FFFFFF',css)
        manifest=json.loads((BASE/'static/manifest.webmanifest').read_text(encoding='utf8'))
        self.assertEqual(manifest['theme_color'],'#50C787')
        self.assertEqual(manifest['background_color'],'#FFFFFF')
        self.assertGreaterEqual(contrast('#093D29','#50C787'),4.5)
        self.assertGreaterEqual(contrast('#FFFFFF','#187B4D'),4.5)

    def test_theme_is_served_by_application(self):
        # The server allowlists static assets; the new sheet must not return 404.
        with tempfile.TemporaryDirectory() as tmp:
            server.open_db(Path(tmp)/'test.sqlite3')
            from threading import Thread
            srv=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
            t=Thread(target=srv.serve_forever,daemon=True);t.start()
            try:
                conn=http.client.HTTPConnection('127.0.0.1',srv.server_port,timeout=4)
                conn.request('GET','/static/theme-green.css')
                resp=conn.getresponse()
                content=resp.read().decode('utf8')
                self.assertEqual(resp.status,200)
                self.assertIn('text/css',resp.getheader('Content-Type',''))
                self.assertIn('--brand: #50C787',content)
                conn.close()
            finally:
                srv.shutdown();srv.server_close();t.join(2)
                if server.CONN:server.CONN.close()
                server.CONN=None

if __name__=='__main__':unittest.main()