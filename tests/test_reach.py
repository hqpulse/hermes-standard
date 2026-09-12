#!/usr/bin/env python3
"""Checks for the reach skill. Run from the repo root: python3 tests/test_reach.py

What is proven here, against a fake bridge on an ephemeral port (reached
through a temporary HERMES_HOME whose config.yaml carries bridge_port) and a
fake door reached through HERMES_FLEET_URL:

  - `principal` and `everything` are refused before any request, exit 2, the
    owner line; a missing --key is refused before any request, exit 2, the
    her-own-word line; a bridge 403 is that same line and exit 2;
  - 404 and 409 map to their lines; a bridge that is not there, or a 5xx, is
    the try-again line, exit 1;
  - allow, deny, leave, remove and auto each hit the right bridge route with
    the right body, then GET /reach, then POST the door body (platform,
    entries stripped of the bridge's own keys, a number-less person held
    back, auto as two booleans) with the Bearer header, then POST
    /reach/synced with the door's reach_version; the stdout line is the one
    the skill expects;
  - a 302 from the door is not followed, an environment proxy is ignored, a
    door that is down, refuses, or has no token means "; will record later"
    and exit 0, and the door's owner refusal is the owner line and exit 2;
  - the token appears in no output on success or on any failure, and no
    output ever carries a group's address;
  - `reach list` prints the tab rows, entries then waiting, and the empty
    line when there is nothing;
  - the port comes from config.yaml (PyYAML and the text fallback) and is
    3300 when the file is absent;
  - the script is executable, has the stdlib shebang, imports nothing but the
    standard library, and neither the skill, nor any string the script can
    print, nor the two sentences added to other skills carries a word from the
    forbidden list;
  - CHANGELOG.md has 0.9.0 and distribution.yaml lists both files.

Standard library only.
"""
import ast
import http.server
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import unittest
from importlib.machinery import SourceFileLoader
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "skills" / "reach" / "scripts" / "reach"
SKILL_MD = ROOT / "skills" / "reach" / "SKILL.md"
STANDARD_MD = ROOT / "skills" / "assistant-standard" / "SKILL.md"
KEEPER_MD = ROOT / "skills" / "policy-keeper" / "SKILL.md"
TOKEN = "test-token-not-a-real-one"
KEY = "k7f3q9"

NEEDS_HER_WORD = "That needs her own word in this chat; I can't act on it from here."
NOT_AN_OWNER = "Making someone a full owner isn't something I can do from here."
UNKNOWN = "I don't know who that is. Run reach list."
AMBIGUOUS = "Two groups are called that. Use the ref from reach list."
NOT_NOW = "I can't change that just now. Try again in a minute."
NOBODY = "Nobody is waiting and nobody has been added from chat."

# The words that never reach a person, as whole words, any case. An env
# variable name such as HERMES_FLEET_URL is one word to this pattern (the
# underscore is a word character), which is the point: it is a name the
# terminal reads, never a word the assistant says.
FORBIDDEN = re.compile(
    r"\b(?:hermes|pulse|the team|tickets?|settings?|switch(?:es)?|allowlists?|access|levels?"
    r"|approved|restarts?|sessions?|process(?:es)?)\b|@g\.us", re.I)

STANDARD_ADDITION = (
    "The one other thing that arrives unprompted is a short question about someone new: "
    "a group you were added to, a number that wrote first, or a reply to something you sent for them. "
    "Those questions are sent in fixed words before you see anything; when the answer comes to you, "
    "the reach skill says what to run, and your reply is one line at rung 2.")
KEEPER_ADDITION = "- Who may reach you (groups, replies)."

# The em dash and the en dash, by code point, so this file carries neither.
DASHES = (chr(0x2014), chr(0x2013))

GROUP_ID = "120363429319914066@g.us"

STATUS = {
    "reach_version": "2026-09-11T13:02:11Z", "home_chat_set": True, "principals": ["17329951700"],
    "auto": {"groups_added_by_principal": False, "replies": True, "synced": False},
    "pending": [
        {"id": "a1", "ref": "g5", "kind": "group", "name": "Sparkle ER", "event": 1,
         "at": "2026-09-11T08:39:10Z", "held": 2},
        {"id": "a2", "ref": "p6", "kind": "person", "name": "", "event": 2,
         "at": "2026-09-11T01:08:00Z", "held": 1},
    ],
    "unsynced": [
        {"client_id": "e1", "ref": "g3", "kind": "group", "id": GROUP_ID, "name": "Simcha Invites",
         "level": "working", "decided": "allow", "by": "principal-word",
         "at": "2026-09-11T08:41:02Z", "synced": False},
        {"client_id": "e2", "ref": "p4", "kind": "person", "id": "17326641498", "phone": "17326641498",
         "lid": "69551234567890", "name": "Moe", "scope": "guest", "decided": "allow",
         "by": "principal-model", "at": "2026-09-11T08:44:10Z", "synced": False},
        # Known by a linked identity only: stays on the pod until a number is known.
        {"client_id": "e3", "ref": "p7", "kind": "person", "id": "8811223344556", "phone": None,
         "lid": "8811223344556", "name": "Unknown", "scope": "guest", "decided": "allow",
         "by": "principal-model", "at": "2026-09-11T09:00:00Z", "synced": False},
    ],
    "counts": {"entries": 3, "pending": 2, "held": 3},
}

DOOR_BODY = {
    "platform": "whatsapp",
    "entries": [
        {"client_id": "e1", "kind": "group", "id": GROUP_ID, "name": "Simcha Invites",
         "level": "working", "decided": "allow", "by": "principal-word", "at": "2026-09-11T08:41:02Z"},
        {"client_id": "e2", "kind": "person", "id": "17326641498", "phone": "17326641498",
         "name": "Moe", "scope": "guest", "decided": "allow", "by": "principal-model",
         "at": "2026-09-11T08:44:10Z"},
    ],
    "auto": {"groups_added_by_principal": False, "replies": True},
}
DOOR_VERSION = "2026-09-11T08:44:11Z"

GROUP_NAMES = {"g3", "simcha invites"}
PERSON_NAMES = {"p4", "17326641498", "moe"}


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
            self.wfile.write(b'{"synced": ["caught"], "reach_version": "caught"}')

        do_GET = do_POST = _any

    server = http.server.HTTPServer(("127.0.0.1", 0), Catch)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, Catch


class Bridge(http.server.BaseHTTPRequestHandler):
    """The reach routes of the bridge on loopback, plus a mode the test sets."""
    mode = "ok"
    status = STATUS
    seen = []            # (method, path, body)

    def log_message(self, *args):
        pass

    def _send(self, code, payload):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        Bridge.seen.append(("GET", self.path, None))
        if self.path != "/reach":
            self._send(404, {"error": "no such route"}); return
        if Bridge.mode == "status-500":
            self._send(500, {"error": "boom"}); return
        self._send(200, Bridge.status)

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(length) or "{}")
        Bridge.seen.append(("POST", self.path, body))
        if self.path == "/reach/synced":
            self._send(200, {"ok": True, "remaining": 0}); return
        if self.path not in ("/reach/allow", "/reach/deny", "/reach/leave", "/reach/remove", "/reach/auto"):
            self._send(404, {"error": "no such route"}); return
        m = Bridge.mode
        if m == "403":
            self._send(403, {"error": "no live key"}); return
        if m == "403-late":
            self._send(403, {"error": "that one arrived after her message; ask again"}); return
        if m == "422":
            self._send(422, {"error": "making someone a full owner is not done from here"}); return
        if m == "500":
            self._send(500, {"error": "boom"}); return
        if m == "not-ok":
            self._send(200, {"ok": False}); return
        if self.path == "/reach/auto":
            auto = dict(STATUS["auto"])
            auto["groups_added_by_principal" if body.get("which") == "groups" else "replies"] = body.get("on")
            self._send(200, {"ok": True, "auto": auto}); return
        target = str(body.get("target") or "").lower()
        if target == "board":
            self._send(409, {"error": "two groups are called that; use the ref from reach list"}); return
        if target in GROUP_NAMES:
            answer = {"ok": True, "ref": "g3", "kind": "group", "name": "Simcha Invites", "client_id": "e1"}
            if self.path == "/reach/allow":
                answer.update({"level": body.get("level"), "released": 2})
            if self.path == "/reach/leave":
                answer["left"] = True
            self._send(200, answer); return
        if target in PERSON_NAMES:
            answer = {"ok": True, "ref": "p4", "kind": "person", "name": "Moe", "client_id": "e2"}
            if self.path == "/reach/allow":
                answer.update({"scope": body.get("scope"), "released": 0})
            self._send(200, answer); return
        self._send(404, {"error": "I don't know who that is; run reach list"})


class Door(http.server.BaseHTTPRequestHandler):
    """POST /v1/reach on the controller, plus whatever the test set as the mode."""
    mode = "ok"
    redirect_to = ""
    seen = []            # (method, path, authorization, body)

    def log_message(self, *args):
        pass

    def _send(self, code, payload):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        Door.seen.append(("GET", self.path, self.headers.get("Authorization"), None))
        self._send(404, {"detail": "no such door"})

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(length) or "{}")
        Door.seen.append(("POST", self.path, self.headers.get("Authorization"), body))
        m = Door.mode
        if m == "302":
            self.send_response(302)
            self.send_header("Location", Door.redirect_to + self.path)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if m == "500":
            self._send(500, {"detail": "the cluster is not answering"}); return
        if m == "401":
            self._send(401, {"detail": "unknown token"}); return
        if m == "422-owner":
            self._send(422, {"detail": "making someone a full owner is not done from here"}); return
        if m == "422-other":
            self._send(422, {"detail": "a number is 7 to 15 digits"}); return
        if self.path != "/v1/reach":
            self._send(404, {"detail": "no such door"}); return
        synced = [e["client_id"] for e in body.get("entries", []) if isinstance(e, dict)]
        self._send(200, {"synced": synced, "reach_version": DOOR_VERSION})


def load_module():
    """The script as a module, for the pure functions."""
    loader = SourceFileLoader("reach_script", str(SCRIPT))
    spec = importlib.util.spec_from_loader("reach_script", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


class ReachScript(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bridge = http.server.HTTPServer(("127.0.0.1", 0), Bridge)
        cls.bridge_port = cls.bridge.server_address[1]
        threading.Thread(target=cls.bridge.serve_forever, daemon=True).start()
        cls.door = http.server.HTTPServer(("127.0.0.1", 0), Door)
        cls.door_base = "http://127.0.0.1:%d" % cls.door.server_address[1]
        threading.Thread(target=cls.door.serve_forever, daemon=True).start()
        cls.tmp = tempfile.TemporaryDirectory()
        cls.home = Path(cls.tmp.name)
        (cls.home / "config.yaml").write_text(
            "platforms:\n  telegram:\n    enabled: false\n  whatsapp:\n"
            "    require_mention: true\n    extra:\n      bridge_script: /x/bridge.js\n"
            "      bridge_port: %d\n      send_read_receipts: true\n" % cls.bridge_port,
            encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        cls.bridge.shutdown(); cls.bridge.server_close()
        cls.door.shutdown(); cls.door.server_close()
        cls.tmp.cleanup()

    def setUp(self):
        Bridge.mode = "ok"
        Bridge.status = STATUS
        Bridge.seen = []
        Door.mode = "ok"
        Door.seen = []

    def run_reach(self, *args, token=TOKEN, door=None, home=None, extra_env=None):
        env = dict(os.environ)
        env.pop("HERMES_LOGINS_TOKEN", None)
        if token is not None:
            env["HERMES_LOGINS_TOKEN"] = token
        env["HERMES_FLEET_URL"] = self.door_base if door is None else door
        env["HERMES_HOME"] = str(self.home if home is None else home)
        env["TZ"] = "UTC"
        env.update(extra_env or {})
        r = subprocess.run([sys.executable, str(SCRIPT), *args],
                           env=env, capture_output=True, text=True, timeout=30)
        # Every run, whatever happened: the token is in no output, no output
        # carries a group's address, and no output carries a forbidden word.
        self.assertNotIn(TOKEN, r.stdout + r.stderr, args)
        self.assertNotIn("@g.us", r.stdout + r.stderr, args)
        self.assertIsNone(FORBIDDEN.search(r.stdout + r.stderr), (args, r.stdout, r.stderr))
        return r

    def bridge_calls(self):
        return [(m, p) for m, p, _ in Bridge.seen]

    def bridge_body(self, path):
        return next(b for m, p, b in Bridge.seen if p == path)

    # --- refused before any request ------------------------------------------
    def test_principal_and_everything_are_refused_before_any_request(self):
        for args in (("allow", "person", "p4", "principal", "--key", KEY),
                     ("allow", "person", "p4", "everything", "--key", KEY),
                     ("allow", "group", "g3", "principal", "--key", KEY),
                     ("allow", "person", "principal", "--key", KEY),
                     ("allow", "person", "p4", "Principal"),
                     ("remove", "person", "everything", "--key", KEY)):
            r = self.run_reach(*args)
            self.assertEqual((r.returncode, r.stderr.strip(), r.stdout), (2, NOT_AN_OWNER, ""), args)
            self.assertEqual(Bridge.seen, [], args)
            self.assertEqual(Door.seen, [], args)

    def test_no_key_is_refused_before_any_request(self):
        for args in (("allow", "group", "g3"), ("deny", "person", "p4"), ("leave", "group", "g3"),
                     ("remove", "person", "p4"), ("auto", "groups", "on"), ("allow", "group", "g3", "--key", "")):
            r = self.run_reach(*args)
            self.assertEqual((r.returncode, r.stderr.strip(), r.stdout), (2, NEEDS_HER_WORD, ""), args)
            self.assertEqual(Bridge.seen, [], args)

    # --- the bridge's refusals -----------------------------------------------
    def test_a_bridge_403_is_the_her_own_word_line(self):
        Bridge.mode = "403"
        r = self.run_reach("allow", "group", "g3", "--key", KEY)
        self.assertEqual((r.returncode, r.stderr.strip(), r.stdout), (2, NEEDS_HER_WORD, ""))
        self.assertEqual(self.bridge_calls(), [("POST", "/reach/allow")])
        self.assertEqual(Door.seen, [])

    def test_a_question_newer_than_the_key_says_ask_again(self):
        Bridge.mode = "403-late"
        r = self.run_reach("allow", "group", "g3", "--key", KEY)
        self.assertEqual(r.returncode, 2)
        self.assertEqual(r.stderr.strip(), "That question arrived after her message; ask her to say it again.")

    def test_a_bridge_422_is_the_owner_line(self):
        Bridge.mode = "422"
        r = self.run_reach("allow", "person", "p4", "--key", KEY)
        self.assertEqual((r.returncode, r.stderr.strip()), (2, NOT_AN_OWNER))

    def test_404_is_the_unknown_line(self):
        r = self.run_reach("allow", "group", "nobody", "--key", KEY)
        self.assertEqual((r.returncode, r.stderr.strip(), r.stdout), (1, UNKNOWN, ""))
        self.assertEqual(Door.seen, [])

    def test_409_is_the_ambiguous_line(self):
        r = self.run_reach("allow", "group", "Board", "--key", KEY)
        self.assertEqual((r.returncode, r.stderr.strip(), r.stdout), (1, AMBIGUOUS, ""))

    def test_a_bridge_that_is_not_there_is_the_try_again_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            (home / "config.yaml").write_text(
                "platforms:\n  whatsapp:\n    extra:\n      bridge_port: 9\n", encoding="utf-8")
            for args in (("allow", "group", "g3", "--key", KEY), ("list",)):
                r = self.run_reach(*args, home=home)
                self.assertEqual((r.returncode, r.stderr.strip(), r.stdout), (1, NOT_NOW, ""), args)
        self.assertEqual(Door.seen, [])

    def test_a_bridge_5xx_or_a_not_ok_is_the_try_again_line(self):
        for mode in ("500", "not-ok"):
            Bridge.mode = mode
            r = self.run_reach("deny", "group", "g3", "--key", KEY)
            self.assertEqual((r.returncode, r.stderr.strip(), r.stdout), (1, NOT_NOW, ""), mode)
            self.assertEqual(Door.seen, [], mode)

    # --- each command: the route, the body, then the record --------------------
    def assert_recorded(self):
        """After a bridge yes: GET /reach, the door body with the Bearer, then /reach/synced."""
        calls = self.bridge_calls()
        self.assertEqual(calls[1:], [("GET", "/reach"), ("POST", "/reach/synced")], calls)
        self.assertEqual(Door.seen, [("POST", "/v1/reach", "Bearer " + TOKEN, DOOR_BODY)])
        self.assertEqual(self.bridge_body("/reach/synced"),
                         {"client_ids": ["e1", "e2"], "reach_version": DOOR_VERSION})

    def test_allow_group_defaults_to_working(self):
        r = self.run_reach("allow", "group", "g3", "--key", KEY)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, "allowed group g3 Simcha Invites (working); 2 held released; recorded\n")
        self.assertEqual(r.stderr, "")
        self.assertEqual(self.bridge_calls()[0], ("POST", "/reach/allow"))
        self.assertEqual(self.bridge_body("/reach/allow"),
                         {"kind": "group", "target": "g3", "level": "working", "key": KEY})
        self.assert_recorded()

    def test_allow_group_by_a_name_of_several_words_and_a_room_word(self):
        r = self.run_reach("allow", "group", "Simcha", "Invites", "inner", "--key", KEY)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, "allowed group g3 Simcha Invites (inner); 2 held released; recorded\n")
        self.assertEqual(self.bridge_body("/reach/allow"),
                         {"kind": "group", "target": "Simcha Invites", "level": "inner", "key": KEY})
        Bridge.seen = []; Door.seen = []
        r = self.run_reach("allow", "group", "Simcha Invites", "outside", "--key=" + KEY)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.bridge_body("/reach/allow")["level"], "outside")

    def test_allow_person_defaults_to_guest_and_can_be_delegate(self):
        r = self.run_reach("allow", "person", "p4", "--key", KEY)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, "allowed person p4 Moe (guest); recorded\n")
        self.assertEqual(self.bridge_body("/reach/allow"),
                         {"kind": "person", "target": "p4", "scope": "guest", "key": KEY})
        self.assert_recorded()
        Bridge.seen = []; Door.seen = []
        r = self.run_reach("allow", "person", "+1 732 664 1498", "delegate", "--key", KEY)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, "allowed person p4 Moe (delegate); recorded\n")
        self.assertEqual(self.bridge_body("/reach/allow"),
                         {"kind": "person", "target": "17326641498", "scope": "delegate", "key": KEY})

    def test_deny_group_and_person(self):
        r = self.run_reach("deny", "group", "g3", "--key", KEY)
        self.assertEqual((r.returncode, r.stdout), (0, "denied group g3 Simcha Invites; recorded\n"), r.stderr)
        self.assertEqual(self.bridge_body("/reach/deny"), {"kind": "group", "target": "g3", "key": KEY})
        self.assert_recorded()
        Bridge.seen = []; Door.seen = []
        r = self.run_reach("deny", "person", "17326641498", "--key", KEY)
        self.assertEqual((r.returncode, r.stdout), (0, "denied person p4 Moe; recorded\n"), r.stderr)
        self.assertEqual(self.bridge_body("/reach/deny"),
                         {"kind": "person", "target": "17326641498", "key": KEY})
        self.assert_recorded()

    def test_leave_group_and_remove_group_is_its_alias(self):
        r = self.run_reach("leave", "group", "g3", "--key", KEY)
        self.assertEqual((r.returncode, r.stdout), (0, "left group g3 Simcha Invites; recorded\n"), r.stderr)
        self.assertEqual(self.bridge_calls()[0], ("POST", "/reach/leave"))
        self.assertEqual(self.bridge_body("/reach/leave"), {"target": "g3", "key": KEY})
        self.assert_recorded()
        Bridge.seen = []; Door.seen = []
        r = self.run_reach("remove", "group", "Simcha Invites", "--key", KEY)
        self.assertEqual((r.returncode, r.stdout), (0, "left group g3 Simcha Invites; recorded\n"), r.stderr)
        self.assertEqual(self.bridge_calls()[0], ("POST", "/reach/leave"))
        self.assertEqual(self.bridge_body("/reach/leave"), {"target": "Simcha Invites", "key": KEY})

    def test_remove_person(self):
        r = self.run_reach("remove", "person", "p4", "--key", KEY)
        self.assertEqual((r.returncode, r.stdout), (0, "removed person p4 Moe; recorded\n"), r.stderr)
        self.assertEqual(self.bridge_calls()[0], ("POST", "/reach/remove"))
        self.assertEqual(self.bridge_body("/reach/remove"), {"kind": "person", "target": "p4", "key": KEY})
        self.assert_recorded()

    def test_auto_groups_and_replies(self):
        r = self.run_reach("auto", "groups", "on", "--key", KEY)
        self.assertEqual((r.returncode, r.stdout), (0, "auto groups on; recorded\n"), r.stderr)
        self.assertEqual(self.bridge_calls()[0], ("POST", "/reach/auto"))
        self.assertEqual(self.bridge_body("/reach/auto"), {"which": "groups", "on": True, "key": KEY})
        self.assert_recorded()
        Bridge.seen = []; Door.seen = []
        r = self.run_reach("auto", "replies", "off", "--key", KEY)
        self.assertEqual((r.returncode, r.stdout), (0, "auto replies off; recorded\n"), r.stderr)
        self.assertEqual(self.bridge_body("/reach/auto"), {"which": "replies", "on": False, "key": KEY})

    # --- the door: second, and never in the way ---------------------------------
    def test_a_redirect_from_the_door_is_not_followed_and_it_records_later(self):
        other, Catch = catcher()
        try:
            Door.mode = "302"
            Door.redirect_to = "http://127.0.0.1:%d" % other.server_address[1]
            r = self.run_reach("allow", "group", "g3", "--key", KEY)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(r.stdout, "allowed group g3 Simcha Invites (working); 2 held released; will record later\n")
            self.assertEqual(Catch.seen, [], "the redirect target was reached")
            self.assertNotIn(("POST", "/reach/synced"), self.bridge_calls())
            self.assertEqual([s[:3] for s in Door.seen], [("POST", "/v1/reach", "Bearer " + TOKEN)])
        finally:
            other.shutdown(); other.server_close()

    def test_an_environment_proxy_is_ignored(self):
        proxy, Catch = catcher()
        try:
            url = "http://127.0.0.1:%d" % proxy.server_address[1]
            env = {"http_proxy": url, "HTTP_PROXY": url, "no_proxy": "", "NO_PROXY": ""}
            r = self.run_reach("allow", "group", "g3", "--key", KEY, extra_env=env)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertTrue(r.stdout.endswith("; recorded\n"), r.stdout)
            self.assertEqual(Catch.seen, [], "a request went through the proxy")
        finally:
            proxy.shutdown(); proxy.server_close()

    def test_a_door_that_is_down_or_refuses_means_record_later(self):
        cases = [("down", dict(door="http://127.0.0.1:9")), ("500", {}), ("401", {}), ("422-other", {})]
        for mode, kwargs in cases:
            Bridge.seen = []; Door.seen = []
            Door.mode = mode if mode != "down" else "ok"
            r = self.run_reach("allow", "person", "p4", "--key", KEY, **kwargs)
            self.assertEqual(r.returncode, 0, (mode, r.stderr))
            self.assertEqual(r.stdout, "allowed person p4 Moe (guest); will record later\n", mode)
            self.assertEqual(r.stderr, "", mode)
            self.assertNotIn(("POST", "/reach/synced"), self.bridge_calls(), mode)

    def test_no_token_means_record_later_without_touching_the_door(self):
        for token in (None, ""):
            Bridge.seen = []; Door.seen = []
            r = self.run_reach("auto", "replies", "on", "--key", KEY, token=token)
            self.assertEqual((r.returncode, r.stdout), (0, "auto replies on; will record later\n"), r.stderr)
            self.assertEqual(Door.seen, [])
            self.assertEqual(self.bridge_calls(), [("POST", "/reach/auto"), ("GET", "/reach")])

    def test_a_status_the_bridge_cannot_give_means_record_later(self):
        Bridge.mode = "status-500"
        r = self.run_reach("deny", "person", "p4", "--key", KEY)
        self.assertEqual((r.returncode, r.stdout), (0, "denied person p4 Moe; will record later\n"), r.stderr)
        self.assertEqual(Door.seen, [])

    def test_the_doors_owner_refusal_is_the_owner_line(self):
        Door.mode = "422-owner"
        r = self.run_reach("allow", "person", "p4", "--key", KEY)
        self.assertEqual((r.returncode, r.stderr.strip(), r.stdout), (2, NOT_AN_OWNER, ""))

    # --- reach list ------------------------------------------------------------
    def test_list_prints_the_tab_rows_entries_then_waiting(self):
        r = self.run_reach("list")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.splitlines(), [
            "g3\tgroup\tSimcha Invites\tanswering when asked (working)\tsince 11 Sep 08:41",
            "p4\tperson\tMoe +1 732 664 1498\tguest\tsince 11 Sep 08:44",
            "p7\tperson\tUnknown\tguest\tsince 11 Sep 09:00",
            "a1\twaiting\tgroup\tSparkle ER\tasked 08:39",
            "a2\twaiting\tperson\tp6\tasked 01:08",
        ])
        self.assertEqual(self.bridge_calls(), [("GET", "/reach")])
        self.assertEqual(Door.seen, [])

    def test_list_says_when_nobody_is_waiting(self):
        Bridge.status = dict(STATUS, pending=[], unsynced=[], counts={"entries": 0, "pending": 0, "held": 0})
        r = self.run_reach("list")
        self.assertEqual((r.returncode, r.stdout), (0, NOBODY + "\n"), r.stderr)

    def test_list_takes_no_key_and_no_arguments(self):
        r = self.run_reach("list", "extra")
        self.assertEqual(r.returncode, 1)
        self.assertTrue(r.stderr.startswith("usage: reach"), r.stderr)
        self.assertEqual(Bridge.seen, [])

    # --- the command line ---------------------------------------------------------
    def test_a_bad_command_line_is_the_usage_block(self):
        for args in ((), ("wat",), ("allow",), ("allow", "room", "g3", "--key", KEY),
                     ("allow", "person", "p4", "owner", "--key", KEY),
                     ("allow", "person", "p4", "guest", "extra", "--key", KEY),
                     ("deny", "person", "p4", "extra", "--key", KEY),
                     ("leave", "person", "p4", "--key", KEY),
                     ("auto", "groups", "maybe", "--key", KEY),
                     ("auto", "strangers", "on", "--key", KEY),
                     ("--key", KEY)):
            r = self.run_reach(*args)
            self.assertEqual(r.returncode, 1, args)
            self.assertTrue(r.stderr.startswith("usage: reach"), (args, r.stderr))
            self.assertEqual(Bridge.seen, [], args)
        self.assertEqual(Door.seen, [])

    # --- where the bridge is ------------------------------------------------------
    def test_the_port_comes_from_config_yaml_and_falls_back_to_3300(self):
        module = load_module()
        self.assertEqual(module.bridge_base(self.home), "http://127.0.0.1:%d" % self.bridge_port)
        with tempfile.TemporaryDirectory() as tmp:
            empty = Path(tmp)
            self.assertEqual(module.bridge_base(empty), "http://127.0.0.1:3300")
            (empty / "config.yaml").write_text("platforms:\n  whatsapp:\n    extra: {}\n", encoding="utf-8")
            self.assertEqual(module.bridge_base(empty), "http://127.0.0.1:3300")
        # The text fallback, with PyYAML made unimportable.
        saved = sys.modules.get("yaml")
        sys.modules["yaml"] = None
        try:
            self.assertEqual(module.bridge_port(self.home), self.bridge_port)
        finally:
            if saved is None:
                sys.modules.pop("yaml", None)
            else:
                sys.modules["yaml"] = saved

    def test_home_defaults_to_the_pack_root(self):
        module = load_module()
        saved = os.environ.pop("HERMES_HOME", None)
        try:
            self.assertEqual(module.profile_home(), ROOT)
        finally:
            if saved is not None:
                os.environ["HERMES_HOME"] = saved

    def test_number_formatting(self):
        module = load_module()
        self.assertEqual(module.format_number("17326641498"), "+1 732 664 1498")
        self.assertEqual(module.format_number("447700900123"), "+447700900123")
        self.assertEqual(module.format_number(""), "")

    # --- the file itself ----------------------------------------------------------
    def test_executable_with_the_stdlib_shebang(self):
        self.assertTrue(os.access(SCRIPT, os.X_OK), "reach must be executable")
        self.assertEqual(SCRIPT.read_text().splitlines()[0], "#!/usr/bin/env python3")

    def test_imports_nothing_but_the_standard_library(self):
        allowed = {"json", "os", "re", "sys", "urllib", "urllib.error", "urllib.request",
                   "datetime", "pathlib", "__future__", "yaml"}
        for node in ast.walk(ast.parse(SCRIPT.read_text())):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    self.assertIn(alias.name, allowed, alias.name)
            elif isinstance(node, ast.ImportFrom):
                self.assertIn(node.module, allowed, node.module)
        # yaml is the one optional import, and it is guarded.
        source = SCRIPT.read_text()
        self.assertIn("import yaml", source)
        self.assertLess(source.index("try:\n        import yaml"), source.index("except Exception"))

    def test_no_forbidden_word_in_the_skill(self):
        text = SKILL_MD.read_text()
        hits = sorted({m.group(0).lower() for m in FORBIDDEN.finditer(text)})
        self.assertEqual(hits, [], hits)
        for dash in DASHES:
            self.assertNotIn(dash, text)

    def test_no_forbidden_word_in_any_string_the_script_can_print(self):
        # Every string literal is checked, docstring and usage included, except
        # the field names of the wire (a key in a dict literal, or the argument
        # of a .get): the bridge and the door name a room's privacy "level" and
        # the script must read and write that field, but it never prints it.
        tree = ast.parse(SCRIPT.read_text())
        wire_keys = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Dict):
                for key in node.keys:
                    if isinstance(key, ast.Constant) and isinstance(key.value, str):
                        wire_keys.add(id(key))
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "get" and node.args
                    and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str)):
                wire_keys.add(id(node.args[0]))
        hits = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in wire_keys:
                for m in FORBIDDEN.finditer(node.value):
                    hits.append((node.lineno, m.group(0)))
        self.assertEqual(hits, [], hits)
        for dash in DASHES:
            self.assertNotIn(dash, SCRIPT.read_text())

    def test_the_two_additions_are_present_and_clean(self):
        standard = STANDARD_MD.read_text()
        self.assertIn(STANDARD_ADDITION, standard)
        self.assertIsNone(FORBIDDEN.search(STANDARD_ADDITION))
        keeper = KEEPER_MD.read_text()
        self.assertIn(KEEPER_ADDITION + "\n", keeper)
        self.assertIsNone(FORBIDDEN.search(KEEPER_ADDITION))
        # The bullet is the last of its list.
        i = keeper.index(KEEPER_ADDITION)
        self.assertEqual(keeper[i + len(KEEPER_ADDITION):i + len(KEEPER_ADDITION) + 2], "\n\n")

    def test_the_skill_names_every_command_and_every_after_line(self):
        text = SKILL_MD.read_text()
        for command in ("reach list", "reach allow group", "reach allow person", "reach deny group",
                        "reach deny person", "reach leave group", "reach remove person",
                        "reach auto groups", "reach auto replies"):
            self.assertIn(command, text, command)
        for line in (
            "Done. I'll answer in {G} when someone asks me, and keep anything private out of it.",
            "OK. In {G} I'll only answer you.\\n\\nSay 'leave' if you'd rather I wasn't in there at all.",
            "Done. I've left {G}.",
            "Done. I'll answer {N}, take a message and keep anything of yours out of it.\\n\\nSay \"they can ask about my diary\" if you want them to have more.",
            "OK. I won't answer {N}.",
            "Done. {N} can ask me about your calendar and errands, nothing private.",
            "Done. I'll carry on with {N} and keep it to what you sent.",
            "OK. I'll pass on what {N} said and leave it there.",
            "Done. Any group you add me to, I'll answer in when someone asks me, and keep anything private out of it.",
            "Done. Anyone I write to for you can write back, and I'll carry on with them.",
            "Done. I won't answer {N} any more.",
            "Making someone a full owner isn't something I can do from here.",
            "Want me to say hello in there so they know who I am?",
        ):
            self.assertIn(line, text, line)
        for refusal in (NEEDS_HER_WORD, UNKNOWN, AMBIGUOUS, NOT_NOW):
            self.assertIn(refusal, text, refusal)
        self.assertIn("Do without asking", text)

    def test_changelog_and_manifest(self):
        self.assertIn("## 0.9.0", (ROOT / "CHANGELOG.md").read_text())
        manifest = (ROOT / "distribution.yaml").read_text()
        self.assertIn("version: 0.9.0\n", manifest)
        self.assertIn("  - skills/reach/SKILL.md\n", manifest)
        self.assertIn("  - skills/reach/scripts/reach\n", manifest)


if __name__ == "__main__":
    sys.dont_write_bytecode = True
    unittest.main(verbosity=2)
