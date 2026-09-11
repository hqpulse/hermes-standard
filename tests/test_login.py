#!/usr/bin/env python3
"""Checks for the logins skill. Run from the repo root: python3 tests/test_login.py

What is proven here, against a fake door on an ephemeral port reached through
HERMES_FLEET_URL, speaking the door's fixed contract:

  - `list` prints title, username and site, one login per line, and no password;
    rows that are not objects are skipped;
  - `show` prints the site then the username, from the list row, with no read;
  - `password` and `otp` print the value alone, with nothing else on stdout;
  - no logins at all is exit 2 with the sentence the assistant is meant to say:
    a missing HERMES_LOGINS_TOKEN (no network call), an empty list, and a read
    refused with exactly "no vault for this assistant";
  - every other 404 is exit 1 carrying the door's own detail, including a title
    with "Vault" in it, a detail that mentions a vault but is not the contract
    string, and a 404 with no detail at all;
  - 401 is the wrong-key line; 429 and other refusals carry the door's detail;
  - a 200 whose body is not JSON, and a value that is not a non-empty string,
    each get their own plain line;
  - the token reaches the door, never a host a 302 points at, never an
    environment proxy, and never any output;
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
NO_LOGINS = "this assistant has no logins yet; ask the Pulse team to add one"

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


def catcher():
    """A second server that records every request it gets: a redirect target, or a proxy."""
    class Catch(http.server.BaseHTTPRequestHandler):
        seen = []

        def log_message(self, *args):
            pass

        def _any(self):
            Catch.seen.append((self.command, self.path, self.headers.get("Authorization")))
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"items": [], "value": "caught"}')

        do_GET = do_POST = _any

    server = http.server.HTTPServer(("127.0.0.1", 0), Catch)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, Catch


class Door(http.server.BaseHTTPRequestHandler):
    """The two endpoints of the pod door, plus whatever the test set as the mode."""
    mode = "ok"
    redirect_to = ""
    seen = []            # (method, path, authorization)

    def log_message(self, *args):
        pass

    def _send(self, code, payload, raw=None):
        body = raw if raw is not None else json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _common(self):
        m = Door.mode
        if m == "302":
            self.send_response(302)
            self.send_header("Location", Door.redirect_to + self.path)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return True
        if m == "401":
            self._send(401, {"detail": "unknown token"}); return True
        if m == "429":
            self._send(429, {"detail": "too many reads; wait a minute"}); return True
        if m == "500":
            self._send(500, {"detail": "1Password is not answering right now"}); return True
        if m == "404-bare":
            self._send(404, {}); return True
        if m == "404-vaultish":
            self._send(404, {"detail": "vault is locked for maintenance"}); return True
        if m == "not-json":
            self._send(200, None, raw=b"<html>hello</html>"); return True
        return False

    def do_GET(self):
        Door.seen.append(("GET", self.path, self.headers.get("Authorization")))
        if self._common():
            return
        if self.path != "/v1/logins":
            self._send(404, {"detail": "no such door"}); return
        if Door.mode == "no-vault":
            self._send(200, {"items": []}); return
        if Door.mode == "junk-rows":
            self._send(200, {"items": ["stray", None, 7, ITEMS[1]]}); return
        self._send(200, {"items": ITEMS})

    def do_POST(self):
        Door.seen.append(("POST", self.path, self.headers.get("Authorization")))
        length = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(length) or "{}")
        if self._common():
            return
        if self.path != "/v1/logins/read":
            self._send(404, {"detail": "no such door"}); return
        if Door.mode == "no-vault":
            self._send(404, {"detail": "no vault for this assistant"}); return
        if Door.mode == "empty-value":
            self._send(200, {"value": ""}); return
        if Door.mode == "number-value":
            self._send(200, {"value": 418902}); return
        if body.get("field") not in ("username", "password", "otp", "url"):
            self._send(422, {"detail": "field must be username, password, otp or url"}); return
        key = (body.get("title"), body.get("field"))
        if key not in VALUES:
            self._send(404, {"detail": "no login with that title"}); return
        self._send(200, {"value": VALUES[key]})


class LoginScript(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = http.server.HTTPServer(("127.0.0.1", 0), Door)
        cls.base = "http://127.0.0.1:%d" % cls.server.server_address[1]
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        Door.mode = "ok"
        Door.seen = []

    def run_login(self, *args, token=TOKEN, base=None, extra_env=None):
        env = dict(os.environ)
        env.pop("HERMES_LOGINS_TOKEN", None)
        if token is not None:
            env["HERMES_LOGINS_TOKEN"] = token
        env["HERMES_FLEET_URL"] = self.base if base is None else base
        env.update(extra_env or {})
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

    def test_a_missing_key_is_a_fault_not_an_empty_list(self):
        # 11 Sep 2026: the engine scrubbed the key from the terminal and every
        # assistant told its person it had no logins while its vault held one.
        r = self.run_login("list", token="")
        self.assertEqual(r.returncode, 3, r.stderr)
        self.assertIn("no login key", r.stderr)
        self.assertNotIn("no logins yet", r.stderr)

    def test_list_skips_rows_that_are_not_objects(self):
        Door.mode = "junk-rows"
        r = self.run_login("list")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, "Ilford Portal\tpulse.assistant\thttps://portal.ilford.example\n")

    def test_show_prints_site_then_username_from_the_list(self):
        r = self.run_login("show", "Northgate Dashboard")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, "https://dash.northgate.example\nassistant@northgate.example\n")
        self.assertEqual([s[:2] for s in Door.seen], [("GET", "/v1/logins")])

    def test_show_an_unknown_title(self):
        r = self.run_login("show", "Nowhere Ltd")
        self.assertEqual(r.returncode, 1)
        self.assertEqual(r.stderr.strip(), "no login with that title")

    def test_password_prints_the_value_alone(self):
        r = self.run_login("password", "Northgate Dashboard")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, "correct horse battery staple\n")
        self.assertEqual(r.stderr, "")

    def test_otp_prints_the_code_alone(self):
        r = self.run_login("otp", "Northgate Dashboard")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, "418902\n")

    def test_the_door_gets_the_bearer_token_and_no_output_carries_it(self):
        r = self.run_login("otp", "Northgate Dashboard")
        self.assertEqual(Door.seen[-1], ("POST", "/v1/logins/read", "Bearer " + TOKEN))
        self.assertNotIn(TOKEN, r.stdout + r.stderr)

    # --- no logins: exit 2 ------------------------------------------------
    def test_missing_token_exits_3_without_touching_the_door(self):
        r = self.run_login("list", token=None)
        self.assertEqual((r.returncode, r.stdout), (3, ""))
        self.assertIn("no login key", r.stderr)
        self.assertEqual(Door.seen, [])

    def test_no_vault_list_is_an_empty_list_and_exit_2(self):
        Door.mode = "no-vault"
        r = self.run_login("list")
        self.assertEqual((r.returncode, r.stderr.strip()), (2, NO_LOGINS))

    def test_no_vault_read_is_exit_2(self):
        Door.mode = "no-vault"
        r = self.run_login("password", "Northgate Dashboard")
        self.assertEqual((r.returncode, r.stderr.strip(), r.stdout), (2, NO_LOGINS, ""))

    # --- every other 404: exit 1 with the door's detail -------------------
    def test_unknown_title_keeps_the_doors_reason(self):
        r = self.run_login("password", "Nowhere Ltd")
        self.assertEqual((r.returncode, r.stderr.strip()), (1, "no login with that title"))

    def test_a_title_with_vault_in_it_is_still_an_unknown_title(self):
        r = self.run_login("password", "Bank Vault")
        self.assertEqual((r.returncode, r.stderr.strip()), (1, "no login with that title"))

    def test_a_detail_that_mentions_a_vault_is_not_the_no_vault_answer(self):
        Door.mode = "404-vaultish"
        r = self.run_login("password", "Northgate Dashboard")
        self.assertEqual((r.returncode, r.stderr.strip()), (1, "vault is locked for maintenance"))

    def test_a_404_with_no_detail_is_exit_1(self):
        Door.mode = "404-bare"
        r = self.run_login("password", "Northgate Dashboard")
        self.assertEqual(r.returncode, 1)
        self.assertNotIn("no logins yet", r.stderr)

    # --- other refusals ---------------------------------------------------
    def test_401_says_the_key_is_not_accepted(self):
        Door.mode = "401"
        r = self.run_login("list")
        self.assertEqual((r.returncode, r.stderr.strip()),
                         (1, "this assistant's login key is not accepted; tell the Pulse team"))

    def test_429_carries_the_doors_detail(self):
        Door.mode = "429"
        r = self.run_login("otp", "Northgate Dashboard")
        self.assertEqual((r.returncode, r.stderr.strip()), (1, "too many reads; wait a minute"))

    def test_any_other_refusal_carries_the_doors_detail(self):
        Door.mode = "500"
        r = self.run_login("list")
        self.assertEqual((r.returncode, r.stderr.strip()), (1, "1Password is not answering right now"))

    def test_a_door_that_is_not_there_is_one_plain_line(self):
        r = self.run_login("list", base="http://127.0.0.1:9")
        self.assertEqual((r.returncode, r.stderr.strip()),
                         (1, "the logins service is not reachable right now"))

    def test_a_200_that_is_not_json_has_its_own_line(self):
        Door.mode = "not-json"
        r = self.run_login("list")
        self.assertEqual(r.returncode, 1)
        self.assertIn("cannot read", r.stderr)
        self.assertNotIn("not reachable", r.stderr)

    def test_a_value_that_is_not_a_non_empty_string_is_refused(self):
        for mode in ("empty-value", "number-value"):
            Door.mode = mode
            r = self.run_login("otp", "Northgate Dashboard")
            self.assertEqual(r.returncode, 1, mode)
            self.assertEqual(r.stdout, "", mode)
            self.assertIn("returned no otp", r.stderr, mode)

    def test_a_bad_command_line_is_the_usage_line(self):
        for args in (("list", "extra"), ("password",), ("wat",), ()):
            r = self.run_login(*args)
            self.assertEqual(r.returncode, 1, args)
            self.assertTrue(r.stderr.startswith("usage: login"), (args, r.stderr))

    # --- the token goes to the door and nowhere else ----------------------
    def test_a_redirect_to_another_host_never_receives_the_token(self):
        other, Catch = catcher()
        try:
            Door.mode = "302"
            Door.redirect_to = "http://127.0.0.1:%d" % other.server_address[1]
            for args in (("list",), ("password", "Northgate Dashboard")):
                Catch.seen = []
                r = self.run_login(*args)
                self.assertEqual(r.returncode, 1, args)
                self.assertIn("refused", r.stderr)
                self.assertEqual(Catch.seen, [], "the redirect target was reached")
                self.assertNotIn("caught", r.stdout)
        finally:
            other.shutdown(); other.server_close()

    def test_an_environment_proxy_is_ignored(self):
        proxy, Catch = catcher()
        try:
            Catch.seen = []
            url = "http://127.0.0.1:%d" % proxy.server_address[1]
            env = {"http_proxy": url, "HTTP_PROXY": url, "no_proxy": "", "NO_PROXY": ""}
            r = self.run_login("list", extra_env=env)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(Catch.seen, [], "the request went through the proxy")
        finally:
            proxy.shutdown(); proxy.server_close()

    # --- the file itself --------------------------------------------------
    def test_executable_with_the_stdlib_shebang(self):
        self.assertTrue(os.access(SCRIPT, os.X_OK), "login must be executable")
        self.assertEqual(SCRIPT.read_text().splitlines()[0], "#!/usr/bin/env python3")

    def test_imports_nothing_but_the_standard_library(self):
        allowed = {"json", "os", "sys", "urllib", "urllib.error", "urllib.request", "__future__"}
        for node in ast.walk(ast.parse(SCRIPT.read_text())):
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
