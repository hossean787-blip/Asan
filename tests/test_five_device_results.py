# -*- coding: utf-8 -*-
"""Verify five independent interview clients share one server-side results store."""
import json
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from http.client import HTTPConnection
from pathlib import Path
import server


class FiveDeviceResultsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        server.open_db(Path(self.tmp.name) / "shared.sqlite3")
        self.httpd = server.ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=3)
        server.CONN.close()
        server.CONN = None
        self.tmp.cleanup()

    def request(self, method, route, payload=None, token=None, code=None):
        conn = HTTPConnection("127.0.0.1", self.httpd.server_port, timeout=15)
        headers = {}
        body = None
        if payload is not None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if token:
            headers["Cookie"] = "miz_admin=" + token
        if code:
            headers["X-Exam-Code"] = code
        conn.request(method, route, body=body, headers=headers)
        response = conn.getresponse()
        raw = response.read()
        status = response.status
        cookie = response.getheader("Set-Cookie")
        conn.close()
        return status, json.loads(raw.decode("utf-8")), cookie

    def test_five_distinct_clients_appear_in_one_admin_panel(self):
        self.assertEqual(self.request("POST", "/api/admin/setup", {"password": "test-password-strong-2026"})[0], 201)
        status, _, cookie = self.request("POST", "/api/admin/login", {"password": "test-password-strong-2026"})
        self.assertEqual(status, 200)
        token = cookie.split(";", 1)[0].split("=", 1)[1]
        sessions = []
        for number in range(5):
            status, exam, _ = self.request("POST", "/api/admin/exams", {
                "candidate": "Candidate " + str(number + 1),
                "role": ("intern", "assistant", "accountant")[number % 3],
            }, token=token)
            self.assertEqual(status, 201)
            sessions.append(exam)

        def answer_on_device(session):
            status, current, _ = self.request("GET", "/api/candidate/current", code=session["code"])
            if status != 200 or current["answered"] != 0 or "correct_index" in str(current):
                raise AssertionError("candidate API exposes restricted data or wrong state")
            status, answer, _ = self.request("POST", "/api/candidate/answer", {"choice": 0}, code=session["code"])
            if status != 200 or answer["answered"] != 1 or "is_correct" in answer:
                raise AssertionError("invalid candidate answer response")
            return session["id"]

        with ThreadPoolExecutor(max_workers=5) as pool:
            ids = list(pool.map(answer_on_device, sessions))
        self.assertEqual(len(set(ids)), 5)
        status, exams, _ = self.request("GET", "/api/admin/exams", token=token)
        self.assertEqual(status, 200)
        self.assertEqual(len(exams), 5)
        self.assertEqual({entry["id"] for entry in exams}, set(ids))
        self.assertTrue(all(entry["answered"] == 1 for entry in exams))
        for exam_id in ids:
            self.assertEqual(self.request("GET", "/api/admin/reports/" + exam_id)[0], 403)
            status, report, _ = self.request("GET", "/api/admin/reports/" + exam_id, token=token)
            self.assertEqual(status, 200)
            self.assertEqual(report["answered"], 1)
            self.assertEqual(len(report["details"]), 1)


if __name__ == "__main__":
    unittest.main()
