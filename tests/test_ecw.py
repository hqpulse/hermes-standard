#!/usr/bin/env python3
"""Checks for the ecw command. Run from the repo root: python3 tests/test_ecw.py

WHAT IS PROVEN HERE, and what deliberately is not.

This suite runs with no browser and no network beyond loopback, so it can run
in CI on a machine that has neither Chromium nor the Playwright client. What it
covers is everything that decides an OUTCOME on a live clinical account:

  - classify(), the skill's central recognition rule. After a CORRECT password
    eCW bounces to newLogin.jsp?error=6 and that page renders no error element
    at all, so a door that reads the page reports a failure on a login that
    plainly succeeded and then retries, and a retry loop locks a clinician out.
    Every landing shape is pinned here, including the two that are a STOP.
  - the preflight, against a stand-in login page on an ephemeral port: the
    three flags read out of server-rendered JavaScript, each one truthy in
    turn, and the desktop user agent actually on the request -- a non-browser
    one answers HTTP 400 on a URL that answers 200 in Chrome, and the stand-in
    enforces that, so a command that forgets the header fails here.
  - the sign-in budget, which lives on DISK because a fresh session does not
    remember: two, then a refusal, and the window that ages an old one out.
  - the host rule: no default, https only, nothing but a host.
  - the controller door: the token on ONE unredirected header, no environment
    proxy, a redirect refused outright, and 404 answered as "no mailbox".
  - the file modes: 0700 on the directory, 0600 on anything written.
  - the shape of the file itself: executable, stdlib shebang, and no import at
    module scope that a pod might not have. Playwright is imported inside
    connect() and nowhere else.

NOT PROVEN HERE, and it needs a browser: everything that drives a page. The
isolated context, the real key events, the viewport raise, the dialog clearing
and session save/restore were each measured against a local Chromium launched
with the sidecar's exact flags. That run is not runnable in CI and its output
is in the lane note, not in this file.

Standard library only.
"""
import ast
import glob
import http.server
import shutil
import ssl
import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "skills" / "ecw" / "scripts" / "ecw"
SKILL_MD = ROOT / "skills" / "ecw" / "SKILL.md"

# The stand-in login page. Every selector and variable name is from
# skills/ecw/references/login.md, which was read off a live V12.0.3 practice.
# The page body is written here; no practice was contacted to build it.
LOGIN_PAGE = """<html><head><title>Web EMR Login Page</title><script>
 var newLoginStep_isUserSoftLockOut = %(soft)s;
 var newLogin_bBlocked = %(blocked)s;
 var newLogin_bCaptcha = %(captcha)s;
</script></head><body><input id="doctorID"><input id="nextStep" type="button"></body></html>"""


def load(name="ecwcmd"):
    """Import the command as a module. It has no .py suffix, by design: the
    assistant runs it by path with the terminal tool."""
    import importlib.machinery
    import importlib.util
    loader = importlib.machinery.SourceFileLoader(name, str(SCRIPT))
    spec = importlib.util.spec_from_loader(name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


CERT_DIR = None


def loopback_cert():
    """A self-signed certificate for 127.0.0.1, made once per run.

    The command refuses anything but https, because a plaintext chart system is
    not a thing to make room for, and that rule is not softened for a test. So
    the stand-in speaks TLS and the child process is pointed at this
    certificate with SSL_CERT_FILE, which Python's default context honors.
    """
    global CERT_DIR
    if CERT_DIR is None:
        if not shutil.which("openssl"):
            return None
        CERT_DIR = tempfile.mkdtemp()
        subprocess.run(
            ["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
             "-keyout", os.path.join(CERT_DIR, "key.pem"),
             "-out", os.path.join(CERT_DIR, "cert.pem"), "-days", "1",
             "-subj", "/CN=127.0.0.1", "-addext", "subjectAltName=IP:127.0.0.1"],
            capture_output=True, check=True, timeout=60)
    return CERT_DIR


class StandInSite(threading.Thread):
    """A login page on loopback, plus a record of what was asked for."""

    daemon = True

    def __init__(self, flags=None, status=200):
        super().__init__()
        self.flags = dict({"soft": "false", "blocked": "false", "captcha": "false"},
                          **(flags or {}))
        self.status = status
        self.seen = []
        self.port = free_port()
        site = self

        class Handler(http.server.BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.0"

            def log_message(self, *a):
                pass

            def do_GET(self):
                site.seen.append((self.path, self.headers.get("User-Agent", "")))
                if "Mozilla" not in self.headers.get("User-Agent", ""):
                    body = b"<h1>Error/Under Maintenance</h1>"
                    code = 400
                else:
                    body = (LOGIN_PAGE % site.flags).encode()
                    code = site.status
                self.send_response(code)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        self.server = http.server.HTTPServer(("127.0.0.1", self.port), Handler)
        where = loopback_cert()
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(os.path.join(where, "cert.pem"),
                                os.path.join(where, "key.pem"))
        self.server.socket = context.wrap_socket(self.server.socket, server_side=True)

    def run(self):
        self.server.serve_forever()

    def stop(self):
        self.server.shutdown()

    @property
    def base(self):
        return f"https://127.0.0.1:{self.port}"

    @property
    def trust(self):
        return os.path.join(loopback_cert(), "cert.pem")


class StandInDoor(threading.Thread):
    """The controller door, and a record of every header it was sent."""

    daemon = True

    def __init__(self, code=200, payload=None, detail=None, location=None):
        super().__init__()
        self.code, self.payload, self.detail, self.location = code, payload, detail, location
        self.seen = []
        self.port = free_port()
        door = self

        class Handler(http.server.BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.0"

            def log_message(self, *a):
                pass

            def do_POST(self):
                length = int(self.headers.get("Content-Length") or 0)
                self.rfile.read(length)
                door.seen.append((self.path, self.headers.get("Authorization", "")))
                if door.location:
                    self.send_response(302)
                    self.send_header("Location", door.location)
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                body = json.dumps(door.payload if door.payload is not None
                                  else {"detail": door.detail or ""}).encode()
                self.send_response(door.code)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        self.server = http.server.HTTPServer(("127.0.0.1", self.port), Handler)

    def run(self):
        self.server.serve_forever()

    def stop(self):
        self.server.shutdown()

    @property
    def base(self):
        return f"http://127.0.0.1:{self.port}"


class Recognition(unittest.TestCase):
    """The rule the whole door hangs off: match on the query string, never the page."""

    def setUp(self):
        self.ecw = load()

    def test_a_successful_login_bounced_by_the_plug_in_nag_is_signed_in(self):
        self.assertEqual(self.ecw.classify(
            "https://practice.example/mobiledoc/jsp/webemr/login/"
            "newLogin.jsp?error=6&reminderPluginPopupStatus=1"), "signed-in")

    def test_the_same_page_with_no_error_six_is_a_refusal(self):
        for url in ("https://practice.example/mobiledoc/jsp/webemr/login/newLogin.jsp",
                    "https://practice.example/mobiledoc/jsp/webemr/login/newLogin.jsp?error=2"):
            self.assertEqual(self.ecw.classify(url), "refused", url)

    def test_the_two_stops_are_recognized_by_path(self):
        self.assertEqual(self.ecw.classify(
            "https://practice.example/mobiledoc/jsp/webemr/login/SecurityImage.jsp"),
            "security-image")
        self.assertEqual(self.ecw.classify(
            "https://practice.example/mobiledoc/jsp/webemr/login/changePasswordOnLogin.jsp"),
            "password-change")

    def test_the_mailed_confirmation_link_is_its_own_verdict(self):
        self.assertEqual(self.ecw.classify(
            "https://practice.example/mobiledoc/jsp/webemr/login/OTPVerification.jsp"),
            "confirm-link")

    def test_anything_off_the_login_path_is_the_application(self):
        self.assertEqual(self.ecw.classify(
            "https://practice.example/mobiledoc/jsp/webemr/index.jsp"), "in-the-app")

    def test_every_verdict_has_a_sentence_a_person_can_be_told(self):
        for verdict in ("security-image", "password-change", "confirm-link",
                        "signed-in", "in-the-app", "refused"):
            self.assertIn(verdict, self.ecw.WHAT_IT_MEANS)
            self.assertTrue(self.ecw.WHAT_IT_MEANS[verdict].strip())

    def test_a_stop_says_stop_in_the_first_word(self):
        for verdict in ("security-image", "password-change"):
            self.assertTrue(self.ecw.WHAT_IT_MEANS[verdict].startswith("STOP."), verdict)


class Preflight(unittest.TestCase):
    """Credential-free, spends nothing, and it is the cheapest safeguard we own."""

    def setUp(self):
        if loopback_cert() is None:
            self.skipTest("openssl is not on this machine, so no https stand-in can "
                          "be made; these three checks did NOT run")

    def run_it(self, site, **env):
        environment = dict(os.environ, ECW_BASE_URL=site.base,
                           SSL_CERT_FILE=site.trust, **env)
        return subprocess.run([sys.executable, str(SCRIPT), "preflight"],
                              capture_output=True, env=environment, timeout=60)

    def test_all_three_flags_false_is_clear(self):
        site = StandInSite()
        site.start()
        try:
            done = self.run_it(site)
        finally:
            site.stop()
        self.assertEqual(done.returncode, 0, done.stderr.decode())
        self.assertIn("newLogin_bBlocked=false", done.stdout.decode())

    def test_each_flag_on_its_own_stops_the_sign_in(self):
        for flag in ("soft", "blocked", "captcha"):
            site = StandInSite({flag: "true"})
            site.start()
            try:
                done = self.run_it(site)
            finally:
                site.stop()
            self.assertEqual(done.returncode, 2, f"{flag}: {done.stderr.decode()}")
            self.assertIn("Tell a person", done.stderr.decode())

    def test_it_sends_a_desktop_user_agent(self):
        """A non-browser user agent answers 400 on a URL that answers 200 in
        Chrome, and the stand-in enforces it. A green run here is the proof."""
        site = StandInSite()
        site.start()
        try:
            done = self.run_it(site)
        finally:
            site.stop()
        self.assertEqual(done.returncode, 0, done.stderr.decode())
        self.assertEqual(len(site.seen), 1)
        path, agent = site.seen[0]
        self.assertEqual(path, self.ecw_login_path())
        self.assertIn("Mozilla", agent)

    def ecw_login_path(self):
        return load().LOGIN_PATH

    def test_a_flag_that_is_not_on_the_page_is_absent_not_an_error(self):
        module = load()
        self.assertIn("absent", module.CLEAR_VALUES)


class TheHostRule(unittest.TestCase):
    """A default host is one practice's live chart system opened by every setup
    that forgot to name its own."""

    def run_it(self, **env):
        environment = {k: v for k, v in os.environ.items() if k != "ECW_BASE_URL"}
        environment.update(env)
        return subprocess.run([sys.executable, str(SCRIPT), "url"],
                              capture_output=True, env=environment, timeout=60)

    def test_no_host_configured_opens_nothing(self):
        done = self.run_it()
        self.assertEqual(done.returncode, 3)
        self.assertIn("has no default host", done.stderr.decode())

    def test_plain_http_is_refused(self):
        done = self.run_it(ECW_BASE_URL="http://practice.example")
        self.assertEqual(done.returncode, 3)
        self.assertIn("must be an https host", done.stderr.decode())

    def test_a_host_with_a_path_on_it_is_refused(self):
        done = self.run_it(ECW_BASE_URL="https://practice.example/mobiledoc")
        self.assertEqual(done.returncode, 3)
        self.assertIn("must be an https host", done.stderr.decode())

    def test_no_browser_configured_is_a_plain_sentence_not_a_workaround(self):
        environment = {k: v for k, v in os.environ.items() if k != "BROWSER_CDP_URL"}
        environment["ECW_BASE_URL"] = "https://practice.example"
        done = subprocess.run([sys.executable, str(SCRIPT), "url"],
                              capture_output=True, env=environment, timeout=60)
        self.assertEqual(done.returncode, 3)
        self.assertIn("no browser here", done.stderr.decode())


class TheBudget(unittest.TestCase):
    """SKILL.md rule 7, on disk, because a fresh session does not remember."""

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        os.environ["ECW_STATE_DIR"] = self.dir
        self.ecw = load()
        self.ecw.attempts_clear()

    def test_two_then_a_refusal(self):
        self.ecw.attempts_spend()
        self.ecw.attempts_spend()
        with self.assertRaises(SystemExit) as caught:
            self.ecw.attempts_spend()
        self.assertEqual(caught.exception.code, 2)

    def test_a_successful_entry_clears_it(self):
        self.ecw.attempts_spend()
        self.ecw.attempts_spend()
        self.ecw.attempts_clear()
        self.ecw.attempts_spend()   # no raise

    def test_an_attempt_older_than_the_window_no_longer_counts(self):
        old = time.time() - self.ecw.ATTEMPT_WINDOW_S - 60
        self.ecw.write_private(self.ecw.attempts_file(), json.dumps([old, old]))
        self.assertEqual(self.ecw.attempts_read(), [])
        self.ecw.attempts_spend()   # no raise

    def test_a_junk_state_file_is_not_a_free_pass_and_not_a_crash(self):
        self.ecw.attempts_file().write_text("{not json")
        self.assertEqual(self.ecw.attempts_read(), [])

    def test_the_directory_is_0700_and_what_it_writes_is_0600(self):
        self.ecw.attempts_spend()
        self.assertEqual(oct(os.stat(self.dir).st_mode)[-3:], "700")
        self.assertEqual(oct(os.stat(self.ecw.attempts_file()).st_mode)[-3:], "600")


class TheDoor(unittest.TestCase):
    """The controller doors, and where the token is allowed to go."""

    def setUp(self):
        self.ecw = load()

    def call(self, door, token="test-token-not-a-real-one"):
        os.environ["HERMES_FLEET_URL"] = door.base
        os.environ["HERMES_LOGINS_TOKEN"] = token
        return self.ecw.door("/v1/email/microsoft/access-token")

    def test_the_token_rides_one_header_to_the_door(self):
        door = StandInDoor(payload={"access_token": "a", "expires_in": 3600})
        door.start()
        try:
            answer = self.call(door)
        finally:
            door.stop()
        self.assertEqual(answer["access_token"], "a")
        self.assertEqual(door.seen[0][1], "Bearer test-token-not-a-real-one")

    def test_a_redirect_is_refused_outright_so_the_token_cannot_follow_it(self):
        catcher = StandInDoor(payload={"access_token": "leaked"})
        catcher.start()
        door = StandInDoor(location=catcher.base + "/v1/email/microsoft/access-token")
        door.start()
        try:
            with self.assertRaises(SystemExit):
                self.call(door)
        finally:
            door.stop()
            catcher.stop()
        self.assertEqual(catcher.seen, [], "the token followed a redirect")

    def test_no_mailbox_is_its_own_sentence_and_not_something_to_retry(self):
        door = StandInDoor(code=404, detail="no mailbox")
        door.start()
        try:
            with self.assertRaises(SystemExit) as caught:
                self.call(door)
        finally:
            door.stop()
        self.assertEqual(caught.exception.code, 2)

    def test_no_key_on_the_pod_is_a_fleet_fault_not_an_empty_answer(self):
        os.environ["HERMES_LOGINS_TOKEN"] = ""
        with self.assertRaises(SystemExit) as caught:
            self.ecw.door("/v1/email/microsoft/access-token")
        self.assertEqual(caught.exception.code, 3)


class TheFileItself(unittest.TestCase):

    def setUp(self):
        self.source = SCRIPT.read_text()
        self.tree = ast.parse(self.source)

    def test_it_is_executable_with_the_stdlib_shebang(self):
        self.assertTrue(os.access(SCRIPT, os.X_OK),
                        "ecw must be executable, and the mode must be committed")
        self.assertTrue(self.source.startswith("#!/usr/bin/env python3\n"))

    def test_nothing_but_the_standard_library_is_imported_at_module_scope(self):
        stdlib = {"ast", "contextlib", "datetime", "json", "os", "re", "socket",
                  "subprocess", "sys", "time", "urllib", "pathlib", "importlib",
                  "__future__"}
        for node in self.tree.body:
            if isinstance(node, ast.Import):
                for alias in node.names:
                    self.assertIn(alias.name.split(".")[0], stdlib, alias.name)
            elif isinstance(node, ast.ImportFrom):
                self.assertIn((node.module or "").split(".")[0], stdlib, node.module)

    def test_playwright_is_imported_inside_connect_and_nowhere_else(self):
        """The pack ships no dependencies. The client is unpacked onto the pod by
        the browser image's init container, so it is a lazy import behind a plain
        refusal, and every other subcommand must still run without it."""
        holders = []
        for node in ast.walk(self.tree):
            if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("playwright"):
                holders.append(node.lineno)
        self.assertEqual(len(holders), 1, "playwright is imported more than once")
        connect = next(n for n in self.tree.body
                       if isinstance(n, ast.FunctionDef) and n.name == "connect")
        self.assertTrue(connect.lineno < holders[0] < connect.end_lineno)

    def test_it_never_closes_the_browser(self):
        """browser.close() would take Chromium down for whoever calls next,
        including this assistant's own browser_* tools. Only a CONTEXT is closed."""
        closes = [n for n in ast.walk(self.tree)
                  if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                  and n.func.attr == "close" and isinstance(n.func.value, ast.Name)
                  and n.func.value.id == "browser"]
        self.assertEqual(closes, [], "browser.close() is called somewhere in this file")
        self.assertIn("fresh.close()", self.source)

    def test_the_refusals_it_compiles_in_are_all_there(self):
        for path_or_control in ("SecurityImage.jsp", "changePasswordOnLogin.jsp"):
            self.assertIn(path_or_control, self.source)
        for never in ("logout.jsp", "home.jsp", "btnVerifyEmail",
                      "saveAndSubmitBtn", "showMessageCheck"):
            self.assertNotIn(f'"{never}"', self.source,
                             f"{never} must never be a target in this file")

    def test_it_visits_only_the_two_paths_it_declares(self):
        module = load()
        self.assertEqual(module.LOGIN_PATH,
                         "/mobiledoc/jsp/webemr/login/newLogin.jsp")
        self.assertEqual(module.SHELL_PATH, "/mobiledoc/jsp/webemr/index.jsp")

    def test_the_skill_sends_the_assistant_here_rather_than_free_hand(self):
        """A ban with nowhere to send the assistant is a ban the assistant walks
        around. SKILL.md keeps rules 5 and 6 and names this file as the one
        exception."""
        skill = SKILL_MD.read_text()
        self.assertIn("scripts/ecw", skill)
        self.assertIn("Never `browser_cdp` and never `browser_exec`", skill)
        self.assertIn("No Playwright script against this application", skill)


class SmallThings(unittest.TestCase):

    def setUp(self):
        self.ecw = load()

    def test_a_cookie_domain_never_carries_the_port(self):
        self.assertTrue(self.ecw.for_host("a.example.com", ".example.com"))
        self.assertTrue(self.ecw.for_host("practice.example", "practice.example"))
        # the cookie spec's own domain-match: the host, or a child of it. These
        # come out of the browser's jar, validated at set time, so the spec
        # algorithm is the right filter here.
        self.assertTrue(self.ecw.for_host("practice.example", ".example"))
        self.assertFalse(self.ecw.for_host("practice.example", "actice.example"))
        self.assertFalse(self.ecw.for_host("practice.example", ""))

    def test_a_long_url_is_bounded_and_keeps_its_query(self):
        short = self.ecw.short("https://x.example/a?error=6")
        self.assertTrue(short.endswith("error=6"))
        self.assertLessEqual(len(self.ecw.short("https://x.example/" + "a" * 500)), 120)


class TheRunFolder(unittest.TestCase):
    """The screenshots the sign-in keeps (PLAN B10, B10-02): where, named how, and never what."""

    class Page:
        def __init__(self, blob=b"\x89PNG stand-in"):
            self.blob = blob
            self.shots = 0

        def screenshot(self, path, full_page=False):
            self.shots += 1
            with open(path, "wb") as fh:
                fh.write(self.blob)

    def setUp(self):
        self.ecw = load()
        self.dir = tempfile.mkdtemp()
        self.saved = {k: os.environ.get(k) for k in ("HERMES_REPLAY_DIR", "ISTA_WORK_RUN", "ISTA_WORK_TASK")}
        for k in self.saved:
            os.environ.pop(k, None)

    def tearDown(self):
        for k, v in self.saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(self.dir, ignore_errors=True)

    def rows(self, run):
        with open(os.path.join(run, "index.jsonl"), encoding="utf-8") as fh:
            return [json.loads(l) for l in fh if l.strip()]

    def test_no_dir_means_no_shot_anywhere(self):
        page = self.Page()
        self.assertIsNone(self.ecw.replay_shot(page, "signed-in"))
        self.assertEqual(page.shots, 0)
        self.assertEqual(os.listdir(self.dir), [])

    def test_the_three_labels_land_in_the_run_folder_with_an_index(self):
        os.environ["HERMES_REPLAY_DIR"] = self.dir
        os.environ["ISTA_WORK_RUN"] = "boot-20260913T173000Z"
        os.environ["ISTA_WORK_TASK"] = "task-1"
        page = self.Page()
        paths = [self.ecw.replay_shot(page, "signed-in"), self.ecw.replay_shot(page, "dialog"),
                 self.ecw.replay_shot(page, "confirm", op="ecw.confirm")]
        run = os.path.join(self.dir, "boot-20260913T173000Z")
        self.assertEqual(oct(os.stat(run).st_mode)[-3:], "700")
        self.assertEqual([os.path.basename(p) for p in paths],
                         ["01-ecw.signin-signed-in.png", "02-ecw.signin-dialog.png", "03-ecw.confirm-confirm.png"])
        for p in paths:
            self.assertEqual(oct(os.stat(p).st_mode)[-3:], "600")
        rows = self.rows(run)
        self.assertEqual([r["seq"] for r in rows], [1, 2, 3])
        self.assertEqual([r["label"] for r in rows], ["signed-in", "dialog", "confirm"])
        for r in rows:
            self.assertEqual(set(r), {"seq", "t", "op", "label", "kind", "file", "sha256", "bytes", "task_id", "bucket", "object", "uploaded_at"})
            self.assertEqual(r["kind"], "frame")
            self.assertEqual(r["task_id"], "task-1")
            self.assertEqual(r["bytes"], len(page.blob))
            self.assertEqual(len(r["sha256"]), 64)
            self.assertIsNone(r["bucket"])

    def test_the_counter_is_the_folders_so_a_second_run_never_overwrites(self):
        os.environ["HERMES_REPLAY_DIR"] = self.dir
        os.environ["ISTA_WORK_RUN"] = "boot-1"
        self.ecw.replay_shot(self.Page(), "signed-in")
        # a plugin door wrote two rows into the same folder in between
        with open(os.path.join(self.dir, "boot-1", "index.jsonl"), "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"seq": 2, "file": "02-resident.prechart-resident-search.png"}) + "\n")
            fh.write(json.dumps({"seq": 3, "file": "03-resident.prechart-prechart-page.png"}) + "\n")
        p = self.ecw.replay_shot(self.Page(), "signed-in")
        self.assertEqual(os.path.basename(p), "04-ecw.signin-signed-in.png")

    def test_the_credential_form_and_the_code_page_are_never_shot(self):
        os.environ["HERMES_REPLAY_DIR"] = self.dir
        page = self.Page()
        for label in ("login", "login-username", "login-password", "code-submitted", "2fa", "password"):
            self.assertIsNone(self.ecw.replay_shot(page, label), label)
        self.assertEqual(page.shots, 0)
        self.assertFalse(glob.glob(os.path.join(self.dir, "*", "*.png")))

    def test_a_shot_that_cannot_be_written_is_a_note_never_a_failure(self):
        os.environ["HERMES_REPLAY_DIR"] = self.dir

        class Broken:
            def screenshot(self, path, full_page=False):
                raise RuntimeError("the page went away")
        self.assertIsNone(self.ecw.replay_shot(Broken(), "signed-in"))

    def test_signin_dialogs_and_confirm_each_call_it(self):
        """The three call sites, by reading the source: after the shell painted, before each
        dialog control is pressed, and on the confirmation page before "Yes, it's me"."""
        src = SCRIPT.read_text(encoding="utf-8")
        for needle in ('replay_shot(page, "signed-in")', 'replay_shot(page, "dialog"', 'replay_shot(tab, "confirm"'):
            self.assertIn(needle, src)


if __name__ == "__main__":
    unittest.main(verbosity=2)
