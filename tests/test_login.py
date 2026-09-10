#!/usr/bin/env python3
"""Checks for the logins skill. Run from the repo root: python3 tests/test_login.py

What is proven here, against a fake door on an ephemeral port reached through
HERMES_FLEET_URL:

  - `list` prints title, username and site, one login per line, and no password;
  - `show` prints the site then the username; `password` and `otp` print the
    value alone, with nothing else on stdout, so a caller can pipe it;
  - a missing HERMES_LOGINS_TOKEN never touches the network and exits 2 with the
    sentence the assistant is meant to say;
  - an empty vault is the no-logins line too;
  - 401 exits 1 with the wrong-key line, 404 for the vault exits 2 with the
    no-logins line, 404 for an unknown title keeps the door's own reason;
  - any other refusal carries the door's plain `detail`;
  - the door saw the bearer token, and the token appears in no output;
  - the script is executable, has the stdlib shebang, and imports nothing but
    the standard library.

Standard library only.
"""
import ast
import http.server
import json
import os
import subprocess
import sys
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "skills" / "logins" / "scripts" / "login"
SKILL_MD = ROOT / "skills" / "logins" / "SKILL.md"
TOKEN = "test-token-not-a-real-one"

ITEMS = [
    {"id": "1", "title": "Northgate Dashboard", "url": "https://dash.northgate.example",
     "username": "assistant@northgate.example", "has_totp": True},
    {"id": "2", "title": "Ilford Portal", "url": "https://portal.ilford.example",
     "username": "pulse.assistant", "has_totp": False},
]
VALUES = {
    ("Northgate Dashboard", "url"): "https://dash.northgate.example",
    ("Northgate Dashboard", "username"): "assistant@northgate.example",
    ("Northgate Dashboard", "password"): "correct horse battery staple",
    ("Northgate Dashboard", "otp"): "418902",
}


class Door(http.server.BaseHTTPRequestHandler):
    """The two endpoints of the pod door, plus whatever refusal the test asked for."""
    mode = "ok"          # set per test
    seen = []            # (method, path, authorization)

    def log_message(self, *args):
        pass

    def _send(self, code, payload):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _refusal(self):
        if Door.mode == "401":
            self._send(401, {"detail": "unknown token"}); return True
        if Door.mode == "404-vault":
            self._send(404, {"detail": "no vault for this assistant"}); return True
        if Door.mode == "404-bare":
            self._send(404, {}); return True
        if Door.mode == "500":
            self._send(500, {"detail": "1Password is not answering right now"}); return True
        return False

    def do_GET(self):
        Door.seen.append(("GET", self.path, self.headers.get("Authorization")))
        if self._refusal():
            return
        if self.path == "/v1/logins":
            self._send(200, {"items": [] if Door.mode == "empty" else ITEMS})
        else:
            self._send(404, {"detail": "no such door"})

    def do_POST(self):
        Door.seen.append(("POST", self.path, self.headers.get("Authorization")))
        length = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(length) or "{}")
        if self._refusal():
            return
        if self.path != "/v1/logins/read":
            self._send(404, {"detail": "no such door"}); return
        key = (body.get("title"), body.get("field"))
        if body.get("field") not in ("username", "password", "otp", "url"):
            self._send(422, {"detail": "field must be username, password, otp or url"}); return
        if key not in VALUES:
            self._send(404, {"detail": f"no login called {body.get('title')!r}"}); return
        self._send(200, {"value": VALUES[key]})


class LoginScript(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = http.server.HTTPServer(("127.0.0.1", 0), Door)
        cls.base = "http://127.0.0.1:%d" % cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        Door.mode = "ok"
        Door.seen = []

    def run_login(self, *args, token=TOKEN, base=None):
        env = dict(os.environ)
        env.pop("HERMES_LOGINS_TOKEN", None)
        if token is not None:
            env["HERMES_LOGINS_TOKEN"] = token
        env["HERMES_FLEET_URL"] = self.base if base is None else base
        return subprocess.run([sys.executable, str(SCRIPT), *args],
                              env=env, capture_output=True, text=True, timeout=30)

    # --- the happy path ---------------------------------------------------
    def test_list_prints_a_line_per_login_and_no_password(self):
        r = self.run_login("list")
        self.assertEqual(r.returncode, 0, r.stderr)
        lines = r.stdout.strip().splitlines()
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[0].split("\t"),
                         ["Northgate Dashboard", "assistant@northgate.example",
                          "https://dash.northgate.example"])
        self.assertNotIn("battery", r.stdout)
        self.assertNotIn("418902", r.stdout)

    def test_show_prints_site_then_username(self):
        r = self.run_login("show", "Northgate Dashboard")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, "https://dash.northgate.example\nassistant@northgate.example\n")

    def test_password_prints_the_value_alone(self):
        r = self.run_login("password", "Northgate Dashboard")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, "correct horse battery staple\n")
        self.assertEqual(r.stderr, "")

    def test_otp_prints_the_code_alone(self):
        r = self.run_login("otp", "Northgate Dashboard")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, "418902\n")

    def test_the_door_is_asked_with_the_bearer_token_and_never_prints_it(self):
        r = self.run_login("otp", "Northgate Dashboard")
        self.assertEqual(Door.seen[-1][:2], ("POST", "/v1/logins/read"))
        self.assertEqual(Door.seen[-1][2], "Bearer " + TOKEN)
        self.assertNotIn(TOKEN, r.stdout + r.stderr)

    # --- refusals ---------------------------------------------------------
    def test_missing_token_exits_2_without_touching_the_door(self):
        r = self.run_login("list", token=None)
        self.assertEqual(r.returncode, 2)
        self.assertEqual(r.stderr.strip(),
                         "this assistant has no logins yet; ask the Pulse team to add one")
        self.assertEqual(r.stdout, "")
        self.assertEqual(Door.seen, [])

    def test_an_empty_vault_is_the_no_logins_sentence(self):
        Door.mode = "empty"
        r = self.run_login("list")
        self.assertEqual(r.returncode, 2)
        self.assertIn("no logins yet", r.stderr)

    def test_401_says_the_key_is_not_accepted(self):
        Door.mode = "401"
        r = self.run_login("list")
        self.assertEqual(r.returncode, 1)
        self.assertEqual(r.stderr.strip(),
                         "this assistant's login key is not accepted; tell the Pulse team")

    def test_404_for_the_vault_is_the_no_logins_sentence(self):
        Door.mode = "404-vault"
        r = self.run_login("list")
        self.assertEqual(r.returncode, 2)
        self.assertEqual(r.stderr.strip(),
                         "this assistant has no logins yet; ask the Pulse team to add one")

    def test_404_with_no_detail_is_also_the_no_logins_sentence(self):
        Door.mode = "404-bare"
        r = self.run_login("list")
        self.assertEqual(r.returncode, 2)
        self.assertIn("no logins yet", r.stderr)

    def test_404_for_an_unknown_title_keeps_the_doors_reason(self):
        r = self.run_login("password", "Nowhere Ltd")
        self.assertEqual(r.returncode, 1)
        self.assertIn("no login called", r.stderr)
        self.assertNotIn("no logins yet", r.stderr)

    def test_any_other_refusal_carries_the_doors_detail(self):
        Door.mode = "500"
        r = self.run_login("list")
        self.assertEqual(r.returncode, 1)
        self.assertEqual(r.stderr.strip(), "1Password is not answering right now")

    def test_a_door_that_is_not_there_is_one_plain_line(self):
        r = self.run_login("list", base="http://127.0.0.1:9")
        self.assertEqual(r.returncode, 1)
        self.assertEqual(r.stderr.strip(), "the logins service is not reachable right now")

    def test_a_bad_command_line_is_the_usage_line(self):
        for args in (("list", "extra"), ("password",), ("wat",), ()):
            r = self.run_login(*args)
            self.assertEqual(r.returncode, 1, args)
            self.assertTrue(r.stderr.startswith("usage: login"), (args, r.stderr))

    # --- the file itself --------------------------------------------------
    def test_executable_with_the_stdlib_shebang(self):
        self.assertTrue(os.access(SCRIPT, os.X_OK), "login must be executable")
        self.assertEqual(SCRIPT.read_text().splitlines()[0], "#!/usr/bin/env python3")

    def test_imports_nothing_but_the_standard_library(self):
        allowed = {"json", "os", "sys", "urllib", "urllib.error", "urllib.request", "__future__"}
        tree = ast.parse(SCRIPT.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    self.assertIn(alias.name, allowed, alias.name)
            elif isinstance(node, ast.ImportFrom):
                self.assertIn(node.module, allowed, node.module)

    def test_the_skill_names_every_command(self):
        text = SKILL_MD.read_text()
        for command in ("login list", "login show", "login password", "login otp"):
            self.assertIn(command, text)


if __name__ == "__main__":
    sys.dont_write_bytecode = True
    unittest.main(verbosity=2)
