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


class TheShellGate(unittest.TestCase):
    """The sign-in reports the application only when the application has finished loading.

    On 13 Sep it printed in-the-app on a shell that never finished: the Office Visits
    anchor was in the markup mid-paint, under the "Building your user experience"
    splash and the loading veil, and the schedule read behind it found nothing it
    could click. The gate is three facts, and it needs all three."""

    def setUp(self):
        self.ecw = load()

    def test_a_loaded_shell_is_the_anchor_on_screen_with_no_splash_and_no_veil(self):
        self.assertTrue(self.ecw.shell_loaded({"anchor": True, "splash": False, "veil": False}))

    def test_the_anchor_merely_present_is_not_enough(self):
        """The mid-paint page of 13 Sep: anchor in the markup, not on screen."""
        self.assertFalse(self.ecw.shell_loaded({"anchor": False, "splash": False, "veil": False}))

    def test_the_splash_still_up_is_not_loaded_whatever_else_is_there(self):
        self.assertFalse(self.ecw.shell_loaded({"anchor": True, "splash": True, "veil": False}))

    def test_the_veil_still_up_is_not_loaded(self):
        self.assertFalse(self.ecw.shell_loaded({"anchor": True, "splash": False, "veil": True}))

    def test_no_answer_from_the_page_is_not_loaded(self):
        self.assertFalse(self.ecw.shell_loaded({}))
        self.assertFalse(self.ecw.shell_loaded(None))

    def test_a_page_that_cannot_answer_is_not_loaded_and_says_so(self):
        class Mute:
            def evaluate(self, js):
                raise RuntimeError("execution context was destroyed")
        state = self.ecw.shell_state(Mute())
        self.assertFalse(self.ecw.shell_loaded(state))
        self.assertIn("did not answer", self.ecw.shell_why(state))

    def test_the_reason_names_what_is_still_up(self):
        self.assertIn("splash", self.ecw.shell_why({"anchor": True, "splash": True, "veil": True}))
        self.assertIn("veil", self.ecw.shell_why({"anchor": True, "splash": False, "veil": True}))
        self.assertIn("not on screen", self.ecw.shell_why({"anchor": False, "splash": False, "veil": False}))

    def test_the_wait_polls_until_loaded_and_clears_dialogs_between_reads(self):
        ecw = self.ecw
        answers = [{"anchor": True, "splash": True, "veil": False},
                   {"anchor": True, "splash": False, "veil": True},
                   {"anchor": True, "splash": False, "veil": False}]

        class Page:
            url = "https://practice.example/mobiledoc/jsp/webemr/index.jsp"
            waited = 0

            def evaluate(self, js):
                return answers.pop(0) if len(answers) > 1 else answers[0]

            def wait_for_timeout(self, ms):
                self.waited += 1

            def query_selector(self, sel):
                return None
        page = Page()
        state = ecw.wait_for_shell(page, seconds=30)
        self.assertTrue(ecw.shell_loaded(state))
        self.assertEqual(page.waited, 2, "one settle per reading that was not yet loaded")

    def test_the_wait_gives_up_on_a_shell_that_never_loads(self):
        ecw = self.ecw

        class Page:
            waited = 0

            def evaluate(self, js):
                return {"anchor": True, "splash": True, "veil": False}

            def wait_for_timeout(self, ms):
                self.waited += 1

            def query_selector(self, sel):
                return None
        page = Page()
        state = ecw.wait_for_shell(page, seconds=1)
        self.assertFalse(ecw.shell_loaded(state))
        self.assertGreaterEqual(page.waited, 1)

    def test_the_shell_facts_are_visibility_not_presence(self):
        """The JS reads a size and computed style, never a bare querySelector, and it
        never trusts offsetParent alone (null on a position:fixed veil)."""
        js = self.ecw.JS_SHELL
        for needle in ("getComputedStyle", "getBoundingClientRect", "Building your user experience",
                       "div#load", "officevisit/officeVisits.jsp"):
            self.assertIn(needle, js)
        self.assertNotIn("offsetParent", js)

    def test_every_road_to_in_the_app_stands_behind_the_gate(self):
        """Three places print in-the-app: the fresh sign-in, the already-in short cut,
        and a restored session. Each waits for the shell and dies on its reason."""
        src = SCRIPT.read_text(encoding="utf-8")
        self.assertEqual(src.count("wait_for_shell(page") - src.count("def wait_for_shell("), 3, "one wait per road")
        self.assertEqual(src.count('print("in-the-app")'), 3)
        self.assertNotIn("in_the_shell", src, "the presence-only gate is gone")


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
    """SKILL.md rule 7, on disk, because a fresh session does not remember.

    The number and the window are exactly what they were. What changed on
    14 Sep is WHEN a row is written: checking costs nothing, and only a
    submitted password is an attempt."""

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        os.environ["ECW_STATE_DIR"] = self.dir
        self.ecw = load()
        self.ecw.attempts_clear()

    def test_two_then_a_refusal(self):
        self.ecw.attempts_record()
        self.ecw.attempts_check()   # one left, no raise
        self.ecw.attempts_record()
        with self.assertRaises(SystemExit) as caught:
            self.ecw.attempts_check()
        self.assertEqual(caught.exception.code, 2)

    def test_the_check_reads_and_never_writes(self):
        """The whole point of the split: a run that only asks whether it may go
        must leave the ledger exactly as it found it, however many times it asks."""
        for _ in range(5):
            self.ecw.attempts_check()
        self.assertEqual(self.ecw.attempts_read(), [])
        self.assertEqual(self.ecw.attempts_left(), 2)

    def test_the_budget_and_the_window_are_unchanged(self):
        self.assertEqual(self.ecw.ATTEMPT_BUDGET, 2)
        self.assertEqual(self.ecw.ATTEMPT_WINDOW_S, 6 * 3600)

    def test_a_successful_entry_clears_it(self):
        self.ecw.attempts_record()
        self.ecw.attempts_record()
        self.ecw.attempts_clear()
        self.ecw.attempts_check()   # no raise

    def test_an_attempt_older_than_the_window_no_longer_counts(self):
        old = time.time() - self.ecw.ATTEMPT_WINDOW_S - 60
        self.ecw.write_private(self.ecw.attempts_file(), json.dumps([old, old]))
        self.assertEqual(self.ecw.attempts_read(), [])
        self.ecw.attempts_check()   # no raise

    def test_a_junk_state_file_is_not_a_free_pass_and_not_a_crash(self):
        self.ecw.attempts_file().write_text("{not json")
        self.assertEqual(self.ecw.attempts_read(), [])

    def test_the_directory_is_0700_and_what_it_writes_is_0600(self):
        self.ecw.attempts_record()
        self.assertEqual(oct(os.stat(self.dir).st_mode)[-3:], "700")
        self.assertEqual(oct(os.stat(self.ecw.attempts_file()).st_mode)[-3:], "600")

    def test_the_note_says_which_way_it_went(self):
        self.assertIn("untouched", self.ecw.ledger_note(False))
        self.assertIn("2 of 2", self.ecw.ledger_note(False))
        self.ecw.attempts_record()
        self.assertIn("one attempt is on the ledger", self.ecw.ledger_note(True))
        self.assertIn("1 of 2", self.ecw.ledger_note(True))


BASE = "https://practice.example"
SHELL_URL = BASE + "/mobiledoc/jsp/webemr/index.jsp"
LOGIN_URL = BASE + "/mobiledoc/jsp/webemr/login/newLogin.jsp"
READY = {"present": True, "anchor": True, "splash": False, "veil": False, "login": False}


class FakePage:
    """The one page the sign-in drives, with a log of what was done to it in order.

    No browser and no network: it answers the handful of calls the flow makes and
    records them, so a test can assert not only WHAT happened but WHEN -- that the
    window was raised before screen one, that no password was submitted, which
    control was pressed. Waits pass no real time unless a test asks them to.
    """

    def __init__(self, url="about:blank", width=780, height=441, shell=None,
                 floor=(1600, 1000), after_login=SHELL_URL, dialogs=(),
                 viewport_raises=False, mute=False, wait_real=False):
        self.url = url
        self.width, self.height = width, height
        self.shell = dict(READY) if shell is None else dict(shell)
        self.floor = floor              # below it, screen one never advances
        self.after_login = after_login
        self.dialogs = dict(dialogs)    # visible root -> its own text; none can be clicked
        self.viewport_raises = viewport_raises
        self.mute = mute                # evaluate() throws: the page cannot answer
        self.wait_real = wait_real      # waits burn the timeout they are given
        self.log = []
        self.filled = {}
        self.context = FakeContext(self)

    # what the flow calls -------------------------------------------------
    def evaluate(self, js, arg=None):
        if "window.innerWidth" in js:
            return [self.width, self.height]
        if self.mute:
            raise RuntimeError("execution context was destroyed")
        if "Building your user experience" in js:
            return dict(self.shell)
        if "innerText" in js:
            return [self.dialogs.get(root, "") for root in (arg or [])]
        return None

    def set_viewport_size(self, size):
        if self.viewport_raises:
            raise RuntimeError("this page was not created by Playwright")
        self.log.append(("viewport", size["width"], size["height"]))
        self.width, self.height = size["width"], size["height"]

    def goto(self, url, **kw):
        self.log.append(("goto", url))
        self.url = url

    def wait_for_selector(self, selector, state=None, timeout=None):
        self.log.append(("wait", selector))
        if self.wait_real and timeout:
            time.sleep(timeout / 1000.0)
        if selector == "input#passwordField:visible" and self.width < self.floor[0]:
            # The measured wall: eCW answers "Your screen resolution is 800 x 600"
            # against its own floor and screen one never advances.
            raise RuntimeError("screen one never advanced")
        return None if state == "hidden" else object()

    def fill(self, selector, value):
        self.log.append(("fill", selector))
        self.filled[selector] = value

    def click(self, selector, **kw):
        self.log.append(("click", selector))
        if selector == "input#Login":
            self.url = self.after_login
            self.shell = dict(READY)    # the login form is gone once you are in

    def wait_for_timeout(self, ms):
        if self.wait_real and ms:
            time.sleep(ms / 1000.0)

    def query_selector(self, selector):
        for root in self.dialogs:
            if selector == root or selector.startswith(root + " "):
                return FakeControl(self, timeout_ok=False)
        return None

    def screenshot(self, path, full_page=False, timeout=None):
        with open(path, "wb") as fh:
            fh.write(b"\x89PNG stand-in")

    # helpers for the tests ------------------------------------------------
    def did(self, *entry):
        return entry in self.log

    def at(self, kind, name=None):
        for i, row in enumerate(self.log):
            if row[0] == kind and (name is None or (len(row) > 1 and row[1] == name)):
                return i
        return -1


class FakeControl:
    """A dialog control that is on screen and will not be pressed, the way an
    unclickable modal behaves when the application's own JavaScript is dead."""

    def __init__(self, page, timeout_ok=False):
        self.page, self.timeout_ok = page, timeout_ok

    def is_visible(self):
        return True

    def click(self, timeout=None, force=False):
        if self.page.wait_real and timeout:
            time.sleep(timeout / 1000.0)
        if not self.timeout_ok:
            raise RuntimeError("element is not clickable: another element intercepts")


class FakeContext:
    def __init__(self, page):
        self.page = page

    def new_cdp_session(self, page):
        return FakeCDP(self.page)


class FakeCDP:
    def __init__(self, page):
        self.page = page

    def send(self, method, params):
        assert method == "Emulation.setDeviceMetricsOverride"
        self.page.log.append(("viewport", params["width"], params["height"]))
        self.page.width, self.page.height = params["width"], params["height"]


class FlowCase(unittest.TestCase):
    """A sign-in driven against FakePage, with the doors and the browser stubbed."""

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.saved = {k: os.environ.get(k) for k in
                      ("ECW_STATE_DIR", "ECW_BASE_URL", "ECW_LOGIN_TITLE", "HERMES_REPLAY_DIR")}
        os.environ["ECW_STATE_DIR"] = self.dir
        os.environ["ECW_BASE_URL"] = BASE
        os.environ["ECW_LOGIN_TITLE"] = "a login title, not a credential"
        os.environ.pop("HERMES_REPLAY_DIR", None)
        self.ecw = load()
        self.ecw.attempts_clear()

    def tearDown(self):
        for k, v in self.saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(self.dir, ignore_errors=True)

    def signin(self, page, preflight=(True, {})):
        """cmd_signin against this page. Returns (exit code, what it said)."""
        import contextlib
        import io
        ecw = self.ecw
        ecw.connect = lambda stack: object()
        ecw.pick_page = lambda browser, base, make=False: page
        ecw.preflight_state = lambda: preflight
        ecw.login_username = lambda title: "a-username"
        ecw.login_password = lambda title: "a-password-that-is-not-real"
        said = io.StringIO()
        with contextlib.redirect_stderr(said), contextlib.redirect_stdout(io.StringIO()) as out:
            try:
                code = ecw.cmd_signin([])
            except SystemExit as exit_:
                code = exit_.code
        return code, said.getvalue() + "\n[stdout] " + out.getvalue()

    def rows(self):
        return self.ecw.attempts_read()


class TheWindowBeforeScreenOne(FlowCase):
    """Defect 1, measured on 13 Sep: signin never set the viewport, so eCW's login
    page rendered "Your screen resolution is 800 x 600" against its own floor and
    screen one never advanced. The username went in correctly and no password was
    ever submitted. cmd_viewport already existed and already documented the hazard;
    the sign-in simply never called it."""

    def test_the_window_is_raised_before_screen_one_is_driven(self):
        page = FakePage(width=780, height=441)
        code, said = self.signin(page)
        self.assertEqual(code, 0, said)
        raised, login_page = page.at("viewport"), page.at("goto", LOGIN_URL)
        self.assertNotEqual(raised, -1, "the sign-in never raised the window")
        self.assertLess(raised, login_page, "the window was raised after the login page loaded")
        self.assertGreaterEqual(page.width, self.ecw.MIN_W)
        self.assertGreaterEqual(page.height, self.ecw.MIN_H)

    def test_at_the_sidecars_own_size_the_sign_in_would_not_have_got_past_screen_one(self):
        """The regression itself: with the raise taken out, this same page stops
        exactly where the real one stopped, with no password submitted."""
        page = FakePage(width=780, height=441)
        self.ecw.raise_viewport = lambda p, w=None, h=None: (p.width, p.height, False)
        code, said = self.signin(page)
        self.assertEqual(code, 2)
        self.assertNotIn(("fill", "input#passwordField"), page.log)
        self.assertEqual(self.rows(), [], "an attempt was charged for a wall it never got past")

    def test_a_window_that_will_not_rise_stops_before_the_login_page(self):
        page = FakePage(width=780, height=441)
        self.ecw.raise_viewport = lambda p, w=None, h=None: (780, 441, False)
        code, said = self.signin(page)
        self.assertEqual(code, 2)
        self.assertIn("--window-size=1920,1200", said, "it must name the one-line fix")
        self.assertNotIn(("goto", LOGIN_URL), page.log)

    def test_the_raise_falls_back_to_the_browser_setting_one_level_down(self):
        page = FakePage(width=780, height=441, viewport_raises=True)
        w, h, ok = self.ecw.raise_viewport(page)
        self.assertTrue(ok)
        self.assertEqual((w, h), (self.ecw.MIN_W, self.ecw.MIN_H))

    def test_a_window_already_over_the_floor_is_left_alone(self):
        page = FakePage(width=1920, height=1113)
        w, h, ok = self.ecw.raise_viewport(page)
        self.assertTrue(ok)
        self.assertEqual(page.log, [], "it re-set a window that was already big enough")

    def test_it_is_raised_again_at_the_shell_because_the_override_dies_with_a_session(self):
        """The override belongs to a CDP session and dies when a client detaches, so
        every leg of the flow asks for it again rather than assuming the first one held."""
        page = FakePage(width=780, height=441)
        asked = []
        real = self.ecw.raise_viewport
        self.ecw.raise_viewport = lambda p, w=None, h=None: (asked.append(len(p.log)) or
                                                             real(p, w or self.ecw.MIN_W, h or self.ecw.MIN_H))
        code, said = self.signin(page)
        self.assertEqual(code, 0, said)
        shell = page.at("goto", SHELL_URL)
        self.assertGreaterEqual(len(asked), 2, "the window was raised once and never again")
        self.assertTrue(any(at >= shell for at in asked),
                        "nothing raised the window again after the shell was loaded")

    def test_the_confirmation_road_re_raises_too(self):
        """The confirmation opens and closes a context of its own; the source is the
        proof here, because reaching that branch needs a mailbox."""
        src = SCRIPT.read_text(encoding="utf-8")
        self.assertIn('size_the_window("after the confirmation")', src)


class TheInApplicationGuard(FlowCase):
    """Defect 2: the guard read the address bar. A shell that is signed out sits on
    index.jsp exactly like a working one, and on 13 Sep signin declined to sign in
    on one of those, printing that it was already in the application."""

    def test_a_signed_out_shell_on_index_jsp_is_not_in_the_application(self):
        wedged = dict(READY, login=True)
        self.assertFalse(self.ecw.shell_loaded(wedged))
        self.assertIn("signed out", self.ecw.shell_why(wedged))

    def test_the_sign_in_runs_on_a_signed_out_shell_instead_of_refusing(self):
        page = FakePage(url=SHELL_URL, shell=dict(READY, login=True))
        code, said = self.signin(page)
        self.assertEqual(code, 0, said)
        self.assertIn(("fill", "input#passwordField"), page.log,
                      "it declined to sign in on a shell that was signed out")
        self.assertEqual(len(self.rows()), 0, "cleared on the way out of a good sign-in")

    def test_a_working_shell_is_still_a_short_cut_and_spends_nothing(self):
        page = FakePage(url=SHELL_URL, shell=dict(READY))
        code, said = self.signin(page)
        self.assertEqual(code, 0, said)
        self.assertNotIn(("goto", LOGIN_URL), page.log, "it signed in on top of a working shell")
        self.assertIn("already in the application", said)
        self.assertIn("untouched", said)
        self.assertEqual(self.rows(), [])

    def test_a_page_that_cannot_answer_says_it_cannot_tell_and_claims_nothing(self):
        page = FakePage(url=SHELL_URL, mute=True)
        self.ecw.IN_APP_WAIT_S = 1      # the grace a mid-paint shell gets, cut for the test
        code, said = self.signin(page)
        self.assertEqual(code, 2)
        self.assertIn("cannot be told apart", said)
        self.assertNotIn("already in the application", said)
        self.assertEqual(self.rows(), [], "it charged an attempt for a page it could not read")

    def test_the_guard_is_one_read_not_a_wait(self):
        """Keep it fast: a shell that answers straight away is judged on that one
        answer, with no polling loop behind it."""
        reads = []
        page = FakePage(url=SHELL_URL, shell=dict(READY))
        real = page.evaluate

        def counted(js, arg=None):
            if "Building your user experience" in js:
                reads.append(js)
            return real(js, arg)
        page.evaluate = counted
        code, said = self.signin(page)
        self.assertEqual(code, 0, said)
        self.assertEqual(len(reads), 1, "the healthy short cut read the shell more than once")

    def test_the_facts_include_a_visible_login_field(self):
        js = self.ecw.JS_SHELL
        for needle in ("input#doctorID", "input#passwordField", "login"):
            self.assertIn(needle, js)
        # visible, because screen one renders a HIDDEN password field of its own
        self.assertIn("getComputedStyle", js)

    def test_where_says_the_address_but_not_that_it_works(self):
        """`ecw where` prints what the ADDRESS means, and that word does not change.
        What changes is that it no longer answers 0 on a shell that is not working."""
        import contextlib
        import io
        page = FakePage(url=SHELL_URL, shell=dict(READY, login=True))
        self.ecw.connect = lambda stack: object()
        self.ecw.pick_page = lambda browser, base, make=False: page
        said, out = io.StringIO(), io.StringIO()
        with contextlib.redirect_stderr(said), contextlib.redirect_stdout(out):
            code = self.ecw.cmd_where([])
        self.assertEqual(out.getvalue().strip(), "in-the-app")
        self.assertEqual(code, 2)
        self.assertIn("not working", said.getvalue())


class TheDialogSweep(FlowCase):
    """Defect 3: on 13 Sep `ecw dialogs` ran 180 seconds against two stacked modals
    that could not be pressed, was killed at the tool's timeout, and had cleared
    nothing. A hang with no reason attached is the worst answer available; the real
    one was the application's own "data loading error"."""

    DEAD = (("div.bootbox",
             "The system encountered a data loading error. Please try to refresh this window."),
            ("div#showCPTCopyRightModal",
             "CPT copyright 2024 American Medical Association. All rights reserved."))

    def test_a_dialog_that_will_not_clear_comes_back_named_inside_the_deadline(self):
        page = FakePage(url=SHELL_URL, dialogs=self.DEAD, wait_real=True)
        started = time.monotonic()
        cleared, stuck = self.ecw.clear_dialogs(page, budget_s=2)
        took = time.monotonic() - started
        self.assertEqual(cleared, 0)
        self.assertLess(took, 6, f"the sweep ran {took:.1f}s against a 2s budget")
        self.assertIn("data loading error", stuck)

    def test_the_named_refusal_is_what_the_command_exits_on(self):
        import contextlib
        import io
        page = FakePage(url=SHELL_URL, dialogs=self.DEAD)
        self.ecw.connect = lambda stack: object()
        self.ecw.pick_page = lambda browser, base, make=False: page
        said = io.StringIO()
        with contextlib.redirect_stderr(said), contextlib.redirect_stdout(io.StringIO()):
            code = self.ecw.cmd_dialogs([])
        self.assertEqual(code, 2, "a sweep that cleared nothing reported success")
        self.assertIn("data loading error", said.getvalue())

    def test_the_whole_sweep_is_bounded_by_its_own_clock(self):
        """Every wait inside takes its timeout from what is LEFT, so the ceiling is
        the budget however many dialogs are stacked up."""
        page = FakePage(url=SHELL_URL, dialogs=self.DEAD, wait_real=True)
        started = time.monotonic()
        self.ecw.clear_dialogs(page, rounds=8, budget_s=3)
        self.assertLess(time.monotonic() - started, 8)

    def test_the_defaults_are_seconds_not_minutes(self):
        self.assertLessEqual(self.ecw.DIALOG_STEP_S, 10)
        self.assertLessEqual(self.ecw.DIALOG_TOTAL_S, 30)
        self.assertLessEqual(self.ecw.DIALOG_POLL_S, self.ecw.DIALOG_TOTAL_S)

    def test_no_wait_in_the_sweep_is_a_fixed_ten_seconds_any_more(self):
        src = SCRIPT.read_text(encoding="utf-8")
        body = src.split("def clear_dialogs(")[1].split("\ndef ")[0]
        self.assertNotIn("timeout=10000", body)
        self.assertNotIn("timeout=5000", body)
        self.assertIn("left_ms", body)

    def test_a_dialog_that_does_clear_reports_no_refusal(self):
        page = FakePage(url=SHELL_URL, dialogs=self.DEAD)
        page.query_selector = lambda sel: (FakeControl(page, timeout_ok=True)
                                           if any(sel.startswith(r) for r, _ in self.DEAD) else None)
        page.dialogs = {}       # they went away when they were pressed
        cleared, stuck = self.ecw.clear_dialogs(page, rounds=1)
        self.assertGreater(cleared, 0)
        self.assertEqual(stuck, "")

    def test_a_long_number_never_rides_out_on_the_quote(self):
        """SKILL.md: this application's error boxes carry an account number and a
        session id. The named refusal is the narrow exception to not quoting them,
        so it is fenced: three roots, cut short, and no long number."""
        page = FakePage(url=SHELL_URL, dialogs=(
            ("div.bootbox", "Data loading error on account 100244871, session 8f2 id 993310221."),))
        text = self.ecw.dialogs_on_screen(page)
        self.assertIn("Data loading error", text)
        self.assertNotIn("100244871", text)
        self.assertNotIn("993310221", text)
        self.assertIn("[number]", text)

    def test_only_the_three_known_roots_can_ever_be_quoted(self):
        """What it may put in a message is bounded to the entry dialogs. It is not
        a way to lift text off a chart."""
        page = FakePage(url=SHELL_URL, dialogs=(("div.bootbox", "x" * 400),))
        asked = {}
        real = page.evaluate

        def spy(js, arg=None):
            if "innerText" in js:
                asked["roots"] = arg
            return real(js, arg)
        page.evaluate = spy
        text = self.ecw.dialogs_on_screen(page)
        self.assertEqual(asked["roots"], [root for root, _ in self.ecw.DIALOGS])
        self.assertLessEqual(len(text), 320, "the quote is trimmed")


class TheLedgerCountsSubmissions(FlowCase):
    """Defect 4: both of 13 Sep's two attempts were spent and NEITHER submitted a
    password -- the first refused on the bad guard, the second died at the
    resolution wall. Only a submitted password can lock a clinician out, so only a
    submitted password is an attempt."""

    def test_a_run_that_never_reaches_the_password_leaves_the_ledger_alone(self):
        page = FakePage(width=780, height=441)
        self.ecw.raise_viewport = lambda p, w=None, h=None: (p.width, p.height, False)
        code, said = self.signin(page)
        self.assertEqual(code, 2)
        self.assertEqual(self.rows(), [])
        self.assertIn("no password was submitted", said)
        self.assertIn("untouched", said)

    def test_a_preflight_refusal_costs_nothing_and_says_so(self):
        page = FakePage()
        code, said = self.signin(page, preflight=(False, {"newLogin_bBlocked": "true"}))
        self.assertEqual(code, 2)
        self.assertEqual(self.rows(), [])
        self.assertIn("untouched", said)

    def test_a_submitted_password_is_exactly_one_row(self):
        page = FakePage(after_login=LOGIN_URL)     # bounced with no error=6: refused
        code, said = self.signin(page)
        self.assertEqual(code, 2)
        self.assertEqual(len(self.rows()), 1, "a submitted password was not counted once")
        self.assertIn("one attempt is on the ledger", said)

    def test_the_row_is_on_disk_before_the_control_is_pressed(self):
        """If the click goes through and this process then dies, the attempt must
        still be there: counting one that did not quite land is the safe direction."""
        page = FakePage(after_login=LOGIN_URL)
        seen = {}
        real = page.click

        def watch(selector, **kw):
            if selector == "input#Login":
                seen["rows"] = len(self.rows())
            return real(selector, **kw)
        page.click = watch
        self.signin(page)
        self.assertEqual(seen.get("rows"), 1)

    def test_two_submissions_and_then_it_refuses(self):
        page = FakePage(after_login=LOGIN_URL)
        self.signin(page)
        self.signin(FakePage(after_login=LOGIN_URL))
        code, said = self.signin(FakePage(after_login=LOGIN_URL))
        self.assertEqual(code, 2)
        self.assertIn("budget of two attempts", said)
        self.assertEqual(len(self.rows()), 2, "the refusal itself wrote a row")

    def test_the_refusal_lands_before_anything_is_opened(self):
        self.ecw.attempts_record()
        self.ecw.attempts_record()
        page = FakePage()
        code, said = self.signin(page)
        self.assertEqual(code, 2)
        self.assertEqual(page.log, [], "it drove the browser on a budget that was spent")

    def test_a_good_sign_in_clears_the_ledger_and_says_so(self):
        page = FakePage()
        code, said = self.signin(page)
        self.assertEqual(code, 0, said)
        self.assertEqual(self.rows(), [])
        self.assertIn("the sign-in went through", said)


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

        def screenshot(self, path, full_page=False, timeout=None):
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

    def test_without_a_run_name_the_folder_is_the_eastern_day(self):
        """What a run from the assistant's terminal gets: no ISTA_WORK_RUN, so the day, and
        the EASTERN day, the same fallback the plugin's recorder uses."""
        import datetime
        import zoneinfo
        os.environ["HERMES_REPLAY_DIR"] = self.dir
        p = self.ecw.replay_shot(self.Page(), "signed-in")
        day = datetime.datetime.now(zoneinfo.ZoneInfo("America/New_York")).strftime("day-%Y-%m-%d")
        self.assertEqual(os.path.basename(os.path.dirname(p)), day)

    def test_a_shot_that_cannot_be_written_is_a_note_never_a_failure(self):
        os.environ["HERMES_REPLAY_DIR"] = self.dir

        class Broken:
            def screenshot(self, path, full_page=False, timeout=None):
                raise RuntimeError("the page went away")
        self.assertIsNone(self.ecw.replay_shot(Broken(), "signed-in"))

    def test_signin_dialogs_and_confirm_each_call_it(self):
        """The three call sites, by reading the source: after the shell painted, before each
        dialog control is pressed, and on the confirmation page before "Yes, it's me"."""
        src = SCRIPT.read_text(encoding="utf-8")
        for needle in ('replay_shot(page, "signed-in")', 'replay_shot(page, "dialog"', 'replay_shot(tab, "confirm"'):
            self.assertIn(needle, src)
        # the dialog shot only inside the application (`ecw dialogs` runs on any page)
        self.assertIn('if classify(page.url) == "in-the-app":\n                replay_shot(page, "dialog"', src)


if __name__ == "__main__":
    unittest.main(verbosity=2)
