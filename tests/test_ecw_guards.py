#!/usr/bin/env python3
"""Checks for the two eCW guard jobs. Run from the repo root: python3 tests/test_ecw_guards.py

WHAT IS PROVEN HERE.

  - ecw_boot_guard.sh runs the session guard ONCE per new start and is silent
    otherwise: a matching marker is a no-op, a changed browser id is a new start,
    and a browser that is not answering yet is not a new start. The marker is
    written before the guard runs, so a guard that fails is not retried every few
    minutes -- that retry loop is how a clinical account gets locked.
  - ecw_guard.sh reads `ecw where` by its EXIT CODE as well as its first word. A
    shell whose session has gone still sits on the in-the-app address, so the word
    alone says "in-the-app" on a dead session; this guard used to skip the restore
    on that word and then save the dead cookie jar over the good one (PUL-217).
  - the sign-in budget belongs to the seat: the guard sets none of its own, and
    reads a number only from the seat's attempt-budget file.
  - two guards on the same tick (05:45 and the boot job) spend at most one
    password between them.

NOT PROVEN HERE: the browser. The window step needs Chromium and Playwright and
is allowed to fail on a machine without them; the stand-in `ecw` below records
what the guard asked of it instead.
"""
import json
import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BOOT = ROOT / "scripts" / "ecw_boot_guard.sh"
GUARD = ROOT / "scripts" / "ecw_guard.sh"


def write_exec(path: Path, body: str) -> Path:
    path.write_text(body)
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return path


class BootGuard(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.state = self.tmp / "state"
        self.calls = self.tmp / "guard-calls"
        self.guard = write_exec(self.tmp / "guard.sh",
                                f'#!/bin/bash\necho run >> "{self.calls}"\necho "guard ran"\n')
        self.version = self.tmp / "json" / "version"
        self.version.parent.mkdir()

    def browser(self, uuid):
        self.version.write_text(json.dumps(
            {"webSocketDebuggerUrl": f"ws://127.0.0.1:9222/devtools/browser/{uuid}"}, indent=3))

    def run_boot(self, cdp=None):
        env = dict(os.environ, ECW_STATE_DIR=str(self.state), ECW_GUARD=str(self.guard),
                   BROWSER_CDP_URL=cdp or f"file://{self.tmp}")
        return subprocess.run(["bash", str(BOOT)], env=env, capture_output=True, text=True, timeout=60)

    def runs(self):
        return len(self.calls.read_text().splitlines()) if self.calls.exists() else 0

    def test_first_look_runs_the_guard_once_then_goes_quiet(self):
        self.browser("8d7d9314-73c8-4784-9dea-23058ad84013")
        first = self.run_boot()
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(self.runs(), 1)
        self.assertIn("a new start", first.stdout)
        again = self.run_boot()
        self.assertEqual(again.returncode, 0, again.stderr)
        self.assertEqual(self.runs(), 1, "a start already seen must not run the guard again")
        self.assertEqual(again.stdout, "", "a quiet tick must print nothing, or every tick is a message")

    def test_a_new_browser_alone_is_a_new_start(self):
        # 14 Sep: the sidecar exited on its own while the pod stayed up.
        self.browser("8d7d9314-73c8-4784-9dea-23058ad84013")
        self.run_boot()
        self.browser("b1783753-1877-4160-94d0-73ada6d9988c")
        self.run_boot()
        self.assertEqual(self.runs(), 2)
        self.assertIn("b1783753-1877-4160-94d0-73ada6d9988c", (self.state / "boot.id").read_text())

    def test_no_browser_yet_is_not_a_new_start(self):
        out = self.run_boot(cdp="http://127.0.0.1:9")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(self.runs(), 0)
        self.assertEqual(out.stdout, "")
        self.assertFalse((self.state / "boot.id").exists(),
                         "a marker written before the browser answered would hide the real start")

    @unittest.skipIf(os.geteuid() == 0, "root writes through a read-only folder")
    def test_a_marker_that_cannot_be_written_runs_nothing(self):
        self.browser("8d7d9314-73c8-4784-9dea-23058ad84013")
        self.state.mkdir()
        self.state.chmod(0o500)
        try:
            for _ in range(3):
                self.assertEqual(self.run_boot().returncode, 0)
        finally:
            self.state.chmod(0o700)
        self.assertEqual(self.runs(), 0, "an unrecorded start would run the guard on every tick")

    def test_marker_is_written_before_the_guard_runs(self):
        self.browser("8d7d9314-73c8-4784-9dea-23058ad84013")
        write_exec(self.guard, f'#!/bin/bash\ncat "{self.state}/boot.id" > "{self.calls}"\nexit 1\n')
        self.run_boot()
        self.assertIn("8d7d9314", self.calls.read_text())
        self.calls.unlink()
        self.run_boot()
        self.assertFalse(self.calls.exists(), "a failed guard must not be retried on the next tick")


class SessionGuard(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.log = self.tmp / "ecw-calls"
        self.lane = self.tmp / "lane.env"
        self.lane.write_text("ECW_WEB_BASE=https://practice.example.test\n")

    def fake_ecw(self, where_word, where_rc, after_restore_rc=None, signin_works=False):
        """A stand-in `ecw` that says `where_word` and exits `where_rc`; after a
        restore it exits `after_restore_rc` instead, and after a sign-in that
        works it exits 0."""
        after = where_rc if after_restore_rc is None else after_restore_rc
        flag = self.tmp / "signed-in"
        return write_exec(self.tmp / "ecw", f"""#!/bin/bash
echo "$*" >> "{self.log}"
case "$1" in
  where)
    [ -f "{flag}" ] && {{ echo in-the-app; exit 0; }}
    echo "{where_word}"
    if grep -q "^session restore" "{self.log}"; then exit {after}; fi
    exit {where_rc} ;;
  session) [ "$2" = save ] && echo "5 cookie(s), 2 key(s)"; exit 0 ;;
  signin)
    echo "budget=${{ECW_ATTEMPT_BUDGET:-unset}}" >> "{self.log}"
    sleep 3
    {"touch '" + str(flag) + "'; exit 0" if signin_works else "exit 2"} ;;
esac
""")

    def guard_env(self, ecw):
        # The window step needs Chromium; a stand-in interpreter records when it was asked.
        python = write_exec(self.tmp / "python", f'#!/bin/bash\ncat >/dev/null\necho "widen $3" >> "{self.log}"\n')
        env = dict(os.environ, ECW_BIN=str(ecw), ECW_LANE_ENV=str(self.lane), ECW_PYTHON=str(python),
                   ECW_BROWSER_LOCK=str(self.tmp / "lock"), ECW_STATE_DIR=str(self.tmp / "state"))
        env.pop("ECW_ATTEMPT_BUDGET", None)
        return env

    def run_guard(self, ecw):
        return subprocess.run(["bash", str(GUARD)], env=self.guard_env(ecw),
                              capture_output=True, text=True, timeout=120)

    def calls(self):
        return self.log.read_text().splitlines() if self.log.exists() else []

    def test_a_live_session_is_saved_and_nothing_else(self):
        out = self.run_guard(self.fake_ecw("in-the-app", 0))
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual([c for c in self.calls() if c != "where" and not c.startswith("widen")],
                         ["session save"])

    def test_the_window_is_widened_after_the_restore_opens_the_page(self):
        # On a cold start there is no eCW page until the restore opens one (15 Sep, 17:45Z).
        self.run_guard(self.fake_ecw("elsewhere", 2, after_restore_rc=0))
        calls = self.calls()
        self.assertIn("widen after restore", calls)
        self.assertGreater(calls.index("widen after restore"), calls.index("session restore"))

    def test_the_window_is_widened_before_a_password_is_submitted(self):
        self.run_guard(self.fake_ecw("refused", 2))
        calls = self.calls()
        self.assertLess(calls.index("widen before sign-in"), calls.index("signin"))

    def test_a_dead_session_gets_a_fresh_page_before_the_restore(self):
        # 15 Sep, 05:46: widened, restored and signed in on the STALE login page, still signed
        # out. 06:03, by hand: old pages closed, one fresh page, same credential, first try.
        self.run_guard(self.fake_ecw("refused", 2, after_restore_rc=0))
        calls = self.calls()
        self.assertIn("widen fresh page", calls)
        self.assertLess(calls.index("widen fresh page"), calls.index("session restore"))
        self.assertEqual(calls.count("widen fresh page"), 1)

    def test_a_live_session_keeps_its_pages(self):
        # Closing a working session's pages and putting the saved file back over live cookies
        # could turn a good session into a dead one, and then spend a password on it.
        self.run_guard(self.fake_ecw("in-the-app", 0))
        self.assertNotIn("widen fresh page", self.calls())

    def test_the_word_alone_on_a_dead_shell_does_not_pass(self):
        # `ecw where` says in-the-app and exits 2: the address, not a working screen.
        out = self.run_guard(self.fake_ecw("in-the-app", 2, after_restore_rc=0))
        self.assertIn("session restore", self.calls(), out.stdout + out.stderr)
        self.assertNotIn("signin", self.calls(), "the restore worked, so no password is spent")
        self.assertIn("session save", self.calls())

    def test_a_dead_session_that_will_not_come_back_is_never_saved(self):
        out = self.run_guard(self.fake_ecw("in-the-app", 2))
        self.assertIn("signin", self.calls())
        self.assertNotIn("session save", self.calls(),
                         "saving here would write the dead jar over the good one")
        self.assertIn("STILL SIGNED OUT", out.stdout)

    def test_the_guard_sets_no_budget_of_its_own(self):
        self.run_guard(self.fake_ecw("refused", 2))
        self.assertIn("budget=unset", self.calls(), "the skill's own default of 2 must apply")

    def test_the_seat_budget_file_is_read(self):
        (self.tmp / "state").mkdir()
        (self.tmp / "state" / "attempt-budget").write_text("6\n")
        self.run_guard(self.fake_ecw("refused", 2))
        self.assertIn("budget=6", self.calls())

    def test_two_guards_on_one_tick_spend_one_password(self):
        ecw = self.fake_ecw("refused", 2, signin_works=True)
        # Each run gets its own browser lock, so only the guard lock can keep them apart:
        # the browser lock is checked and then written, and two runs on one tick can both
        # pass the check.
        procs = [subprocess.Popen(["bash", str(GUARD)],
                                  env=dict(self.guard_env(ecw), ECW_BROWSER_LOCK=str(self.tmp / f"lock{i}")),
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                 for i in range(2)]
        for proc in procs:
            proc.communicate(timeout=120)
            self.assertEqual(proc.returncode, 0)
        self.assertEqual(self.calls().count("signin"), 1)

    def test_the_lock_is_released(self):
        self.run_guard(self.fake_ecw("in-the-app", 0))
        self.assertFalse((self.tmp / "lock").exists())


if __name__ == "__main__":
    unittest.main(verbosity=1)
