# Getting in to eClinicalWorks

Read off a live V12.0.3 hosted practice on 10 and 11 September 2026. Every selector on
this page was seen on the real screen. Where something was not seen, the line says so.

**Nothing on this page is an authorization.** `SKILL.md`'s numbered refusals hold over
every word here. A screen described below is described so it can be RECOGNIZED, not so it
can be driven; where a section names a form, naming it is the whole of the permission.

No password, no username, no host and no person appears in this file. The address of
the practice and the title of the login both come from configuration, never from here.

## 0. Before the first character is typed

**The host has no default and must never be given one.** A practice reaches eCW at its
own host name. A default host written into a tool is one practice's live chart system
being opened by every setup that forgot to name its own, and what is read there comes
back looking like this practice's own chart. If the address is not configured, nothing
is opened, and that is the correct outcome.

**The window must be at least 1600 x 1000.** The application warns below 1600 x 900 and
lays its screens out for a desktop. A narrower window is a different page, and a door
reading a different page reads a different answer.

`browser_cdp` would set it, and `SKILL.md` rule 5 forbids `browser_cdp` on this
application, so this is not something to fix from inside the session. Read the viewport
(`window.innerWidth` is a permitted read under rule 4). If it is under 1600 x 1000, say so
and stop: the browser sidecar's window size is a configuration fact, and a person sets it
once.

**Send a real desktop browser.** A non-browser user agent on the login URL answers
**HTTP 400** with an "Error/Under Maintenance" page on a URL that answers 200 in
Chrome. That bites a command-line probe, not the browser sidecar, but it is why a curl
check of "is eCW up" reports an outage that is not there.

## 1. The sign-in, screen by screen

Everything lives under `/mobiledoc/`. That word is not a mobile API. It is the URL
namespace of the whole Web EMR.

### The login page

```
GET  /mobiledoc/jsp/webemr/login/newLogin.jsp                      200 text/html
GET  /mobiledoc/jsp/webemr/login/authenticate/getRsaPublicKey      200 {publicKey}
POST /mobiledoc/jsp/webemr/login/authenticate/setAESKey?action=1043
POST /mobiledoc/jsp/webemr/login/authenticate/setSessionAttributes
GET  /mobiledoc/jsp/webemr/login/authenticate/getEncJS.js
```

Page title "Web EMR Login Page". The version string is printed on it. The page carries
a Spring CSRF pair as `<meta name="_csrf">` and `<meta name="_csrf_header">`.

### Screen one, the username

| | |
|---|---|
| field | `input#doctorID` |
| button | `input#nextStep` ("Next") |
| what the click runs | `validateStep1Form()`, which AES-encrypts the username into a hidden field |
| the request | `POST /mobiledoc/jsp/webemr/login/authenticate/verifyUname`, a 302 |
| what follows | `GET /mobiledoc/jsp/webemr/login/authenticate/getPwdPage`, the password screen |

**The trap on this screen is real.** Screen one also renders a **hidden password
input**. Anything that fills by id alone types the password into screen one and submits
it there. Wait for a **visible** `input#passwordField` before you type a password.

Working through the accessibility tree makes this mostly free, because a hidden input
does not appear in a snapshot, so there is no ref to hit by accident. Treat that as a
convenience and not a guarantee: check that the field you are about to fill is the one
the snapshot shows on the password screen.

**A username the server does not know never reaches a password screen.** No password is
submitted, so it spends no password attempt. Whether eCW counts a failed username step
toward its own lockout was **never measured** — nobody has deliberately failed a login on
this practice — so this is a single check before a sign-in, never a probe you repeat.

### Screen two, the password

| | |
|---|---|
| field | `input#passwordField`, with a "Show" eye toggle beside it |
| button | `input#Login` ("Log In") |
| also on the screen | "Sign in with a different account", "Forgot password?", and once enrolled a "VERIFY YOUR SECURITY IMAGE" panel showing the chosen picture |
| what the click runs | `validateForm()`, which computes `hex_sha1(MD5(password))` and then AES-encrypts that |
| the request | `POST /mobiledoc/jsp/webemr/login/authenticate/processLoginRequest`, a 302 |
| what follows | `GET /mobiledoc/jsp/webemr/login/loginSuccess.jsp`, a 302 to one of three places |

The password never crosses the wire in the clear and never crosses it as a plain hash
either. Both screens encrypt their field with an AES key the browser negotiated against
an RSA public key it fetched from the server. That is done by the page's own JavaScript,
so typing into the real field is the whole of it. Nothing here needs to be reproduced.

### Where `loginSuccess.jsp` sends you

| destination | what it means |
|---|---|
| `/mobiledoc/jsp/webemr/login/SecurityImage.jsp` | first sign-in on this account, the picture is not enrolled. Section 4. |
| `/mobiledoc/jsp/webemr/login/changePasswordOnLogin.jsp` | the password is temporary or expired, forced change. Section 5. |
| `/mobiledoc/jsp/webemr/login/newLogin.jsp?error=6&reminderPluginPopupStatus=1` | **you are signed in**, and the plug-in nag bounced you. Section 2. |

### Signing out, which this skill does not do

**Do not sign out.** `SKILL.md` rule 8: the session is the expensive thing, because every
sign-in spends one of the four remaining verification skips (section 6). Finish by parking
the browser on a blank page.

The address is recorded here for the one case that is not this skill's own tidying up: a
person asks for it. `/mobiledoc/jsp/webemr/logout.jsp`, read out of the security image
page's own `logout()` function, so it is evidenced rather than guessed. Every unknown
address on this host answers 302 to the login page, which means a wrong sign-out address
looks exactly like a working one, so if a person does ask, use this path and no other.

## 2. The plug-in nag, and the single nastiest recognition problem on this door

After a **correct** password, eCW redirects to

```
/mobiledoc/jsp/webemr/login/newLogin.jsp?error=6&reminderPluginPopupStatus=1
```

The account is authenticated. eCW is complaining that its own browser plug-in is not
installed. The page it lands on **renders the ordinary username screen with no error
box, no banner, no red text and nothing else to see.** The only plug-in element is a
small "Download Plug-in" button at the bottom left of the login column, which is on the
plain login page too.

So anything that decides "am I signed in?" by looking at the page, or by the rule "still
on a `/webemr/login/` path means refused", reports that a login failed when it plainly
succeeded, and then retries, and a retry loop on a live clinical account is a lockout.

**Match on the query string. Never on the page.** `error=6` on `newLogin.jsp` means
authenticated and bounced.

### The procedure, exactly

```
1. Click input#Login.
2. Let the navigation settle.
3. Read the landing URL.

   path has SecurityImage.jsp           -> STOP. Not enrolled. Section 4. Tell a person.
                                           Do not pick a picture, do not press Save, and
                                           do not press the X or Logout: both sign out.
   path has changePasswordOnLogin.jsp   -> STOP. Credential expired. Section 5. Tell a
                                           person. Do not fill the form.
   query has error=6                    -> SIGNED IN. Do not treat this as a refusal.
        4. Navigate to /mobiledoc/jsp/webemr/index.jsp
        5. Clear the three entry dialogs (section 3).
        6. Assert on a real control, never on a status code.
   newLogin.jsp with any other error code, or with no query at all
                                        -> refused. Stop. The session budget is two
                                           sign-in attempts in total (SKILL.md rule 7);
                                           if one is left, spend it, then a person hears
                                           about it.
   anything off /webemr/login/          -> already in the app, carry on.
```

**Never navigate to `/mobiledoc/jsp/webemr/home.jsp`.** It answers **HTTP 412
Precondition Failed** with an almost empty body. That is a known-bad address, not a
session problem, and reading it as "signed out" sends you round the loop again.

### `index.jsp` was proved, and the phrasing matters

`/mobiledoc/jsp/webemr/index.jsp` answers **HTTP 200 and the Web EMR shell. Three runs of
the recording session logged that status** (runs 3, 7 and 8; run 6 failed at the sign-in
before it got there, and two earlier runs kept no log), with the assertion pinned to a
real control rather than to a status code. An older note claiming a 412 there was a
mistaken reading of a probe that never checked status and screenshotted a later candidate
in its list.

But 200 is not the same as ready:

> **`index.jsp` paints a loading frame first.** Left alone it shows a blue page reading
> **"Building your user experience"** with a spinner, behind up to three stacked
> dialogs. It was held there for sixty seconds and it never cleared on its own. The
> shell only finishes initializing after the dialogs in section 3 are dismissed.

An agent that navigates, sees 200, and starts looking for the schedule finds a blue
splash and concludes the application is empty. **The sequence is the skill, not the
URL.**

### The anchor, the thing that proves you are in

Pin the assertion to the Office Visits jellybean in the top bar. Present, visible and
interactive on every clean shell that was recorded:

```
selector seen live : a#jellybean-panelLink22
its href           : #/mobiledoc/jsp/webemr/jellybean/officevisit/officeVisits.jsp
its text           : "S 0"   (a letter, then the count of items waiting)
its box            : x=1451 y=0 w=70 h=41  at 1920x1080
why it counts      : clicking it opened the Office Visits grid
```

Two cautions:

1. **Do not anchor on the text.** It reads `S 0` only because the queue is empty. It
   reads `S 7` on a busy morning.
2. **The `jellybean-panelLinkNN` numbers are assigned per user layout.** They were
   stable across four sessions on one account, but the durable form is the href:
   `a[href$="jellybean/officevisit/officeVisits.jsp"]`. **That selector is derived from
   the recorded DOM and was not separately click-tested.** Verify it on the first run
   and keep the numeric id as the fallback.

A cheaper anchor for a snapshot-based tool: once the shell is up, the page title is
`eCW (<Last>, <First> ) Production` and the body carries the module words
`Favorites Menu Practice Registry Referrals Messages Documents Billing Analytics`. The
loading frame's body says `Building your user experience` instead. Either is a fine "am
I in" test. The jellybean is the one that also proves the page is **interactive**.

## 3. The three entry dialogs

Between `index.jsp` and a usable application there are three stacked dialogs. Top of the
stack first:

| # | dialog | anchor | the control to press | what pressing it means |
|---|---|---|---|---|
| 1 | **CPT Copyright**, the AMA notice | `div#showCPTCopyRightModal`, z-index 10000001 | `input#okBtn` ("OK") | acknowledge a copyright notice. Every user does this at the start of every session. **Leave `input#showMessageCheck` ("Do not show this message again") alone.** Ticking it changes a setting. |
| 2 | **data loading error** | `div.bootbox`, z-index 9999999, text "The system encountered a data loading error. Please try to refresh this window." | `.bootbox button.btn` ("OK") | dismiss an error box. See the caveat below. |
| 3 | **Security Verification** | `div#verificationMethodPopup`, z-index 1999 | `button#showCloseBtnOnHeader`, the header X | skip the practice's mandatory email verification for this session. **Never press `button#btnVerifyEmail` ("Verify") or `button#saveAndSubmitBtn` ("Save").** Those enroll and mail a code. |

What is true about this stack:

- **It fires once per SIGN-IN, not per page load.** Reloading `index.jsp` inside a live
  session brought back neither the CPT notice nor the Security Verification popup. Only
  the data-loading error box came back.
- **It blocks everything underneath it.** With the dialogs up, a real click on any shell
  control times out, because the backdrop intercepts the pointer. Every navigation
  attempt in the run that skipped this step failed on a locator that was present and
  reported visible. **An agent that reports "the control is there but I cannot click it"
  is looking at a modal backdrop.**
- Order matters only in that the CPT notice sits on top. Clear it first.

**Caveat on dialog 2.** The data loading error appeared on every page load in headless
Chromium with the eCW browser plug-in absent. Whether a person on an ordinary desktop
sees it is not known. Treat it as "dismiss it if it is there", never as "wait for it".

## 4. The Security Image, and why it is not two-factor

**Where this section came from.** Both this screen and section 5 were seen during the
10 September account-onboarding session, not during the 11 September recorded runs, so
there is no log line or screenshot for either one in the recording set. Everything below
is a description written to be RECOGNIZED, and rule 11 is the whole of what to do with it.

On a brand-new account, `loginSuccess.jsp` sends you to
`/mobiledoc/jsp/webemr/login/SecurityImage.jsp`, titled "Web EMR- Security Image". It is
a SiteKey-style anti-phishing picture.

```html
<form action="/mobiledoc/jsp/webemr/login/SecurityImage.jsp" method="post" ...>
  <input type="hidden" name="TrUserId" value="...">
  <input type="hidden" name="picId" id="picId" value="-1">
  <img class="propicsel" src=".../login/img/avatars/propic-img25.jpg" id="25" ...>
  <input type="submit" value="Save">
</form>
```

- Three tabs: Monuments, Animals, Landscapes.
- Clicking a picture sets `#picId` to that picture's id. The `id` attribute is a bare
  number, so match it as an attribute, `img.propicsel[id="25"]`, never as a CSS `#25`.
- The form refuses to submit while `picId` is below 1, and shows a modal reading "Please
  Choose a Picture for your Profile."
- The dialog is `modal({backdrop:'static', keyboard:false})`. **It cannot be dismissed.**
  The top-right X and the Logout button both call `logout()`.

**There is no skip path, and this assistant is not the one who takes it.** Enrollment is
one Save, and a Save writes a permanent account-level setting on a real clinician-facing
account. `SKILL.md` rule 2 has no exceptions and rule 11 names this screen by URL:
**recognize it, stop, tell a person.**

There is **no Save anywhere in this skill that this assistant may press** — not here, not
on a note, not on a setting. If you meet this screen, say the account has never been
enrolled and that somebody at the practice has to choose a picture once. Do not click a
picture. Do not press Save. Do not press the X and do not press Logout either: both call
`logout()` and end the session, which spends a verification skip on the way back in.

The form is documented above so the screen can be told apart from a refusal at a glance,
and for nothing else.

**It is not a second factor.** After enrollment the picture is *displayed* on the
password screen so a human can tell a real eCW from a phishing clone. It is never
re-selected, it is not a code, and it does not gate the POST. It is account-level, not
device-level: nothing in the page, the flow or the cookies is bound to a machine, so a
fresh browser lands straight on the password screen with the picture shown.

The whole login flow was searched for otp, mfa, 2fa, verification-code and authenticator
markers, and the only hits were inside allow-list host names. **This tenant has no
second factor at sign-in.** Section 6 is a different thing that happens after you are
already in, and it is worth reading before anybody calls this door unattended.

## 5. A temporary password, and its forced change

**This section is recognition only. Read it to know what the screen is. Do not fill it.**
Like section 4, it was seen on 10 September during account onboarding and not during the
11 September recorded runs, so no log line or screenshot of it exists in the recording set.

Client-issued passwords are temporary. The first sign-in lands on
`/mobiledoc/jsp/webemr/login/changePasswordOnLogin.jsp`, after an acknowledgement that
wants an **OK** click first. It is an orange "Change Password" modal carrying Old
Password, New Password, Confirm Password, a strength meter, and a CAPTCHA image of about
five distorted characters with "Try another text" and "Play audio" beside it.

**What to do: nothing, and say so.** `SKILL.md` rule 10. The credential this assistant
holds has expired or was issued temporary. Name the login by its title, say it needs to be
changed and re-filed by whoever manages it, and stop.

**Why it is a stop rather than a task, in one sentence you can repeat if asked:** the
credential door is read-only — `skills/logins` offers `list`, `show`, `password` and `otp`
and has no write of any kind, and its own hard line forbids writing a credential down
anywhere — so a password changed on this screen would exist in no store, no file and no
message, eCW signs you out the moment it is accepted, and the clinician's own account is
then unusable until a practice admin resets it. Changing it is also a write to a live
clinical system, which rule 2 forbids on its own.

**And do not read the CAPTCHA.** Reading it has exactly one use, submitting the form, and
the form is not submitted.

The real password rules live behind a blue information icon beside New Password.
**UNRECORDED. Nobody has clicked it.** It is a ten-second read on a page with no patient
data on it, and it is worth somebody doing once — a person, in an operator session, not an
assistant mid-task.

## 6. The email verification, and the countdown that is already running

This is not a login challenge. You are already authenticated when it appears.

> **Security Verification.** "A mandatory verification has been enabled by the practice
> admin. You can come back to this window on your own time by going to User Initials >
> Gear Icon > User Profile > Verify." One field, `input#uemail`, prefilled with the
> user's own practice mailbox address, a `Verify` button, and the line "**N skips
> remaining before required verification**".

What was observed, and this is the part that decides the design:

- It appears **once per sign-in**, on the shell, immediately after `index.jsp`.
- **The counter goes down on every sign-in whether or not anybody touches the popup.**
  Across five sign-ins it was read at Eight, then Seven, then Six, then **not read on
  the fourth**, then Four, and it was not clicked in the first two. So it is **per login,
  not per device**, and a trusted machine does not buy a pass. The gap is a reading that
  was missed, not a sign-in that was free: Eight, Seven and Six fall one apart, and the
  Four two below Six is what the unread fourth sign-in leaves behind.
- Closing it leaves you fully in the application.
- On the account that was recorded, **four skips remain.**

**What that means.** When the skips run out, the account is stuck at an email code and
the assistant stops. The fix is a person completing the verification once, deliberately,
from the practice mailbox. Not the assistant: pressing `Verify` sends mail and `Save`
writes a profile setting, and both are on the never list.

Whether the verification is once-forever or repeats on a schedule is **not known** and is
worth one question to the practice, because the answer decides whether an assistant ever
needs a readable mailbox of its own.

Until it is done, **every automated sign-in spends a skip.** That is the whole reason
this skill reuses a session instead of signing in per task.

## 7. There is no usable internal API, and here is why

Do not spend a day building an API client. It cannot be done, and the reason is
specific rather than a shrug.

eCW ships a script, `getEncJS.js`, that installs a global jQuery `ajaxSetup` whose
`beforeSend` **rewrites the URL of every in-app AJAX call into ciphertext**:

```js
var jCryptedData = window.top.encryptDataWithAES(url, encKey, encIv);
this.url = '/mobiledoc/encreq/bflcontroller?qpqg19=' + encodeURIComponent(jCryptedData) + '&endq=yes';
```

The key is negotiated at page load: the client fetches a 2048-bit RSA public key from
`/mobiledoc/jsp/webemr/login/authenticate/getRsaPublicKey`, generates an AES key per
usage string, wraps it with RSA, registers it at
`/mobiledoc/jsp/webemr/login/authenticate/setAESKey`, and caches the key and IV in both
`localStorage` and `sessionStorage` under `crypto_aesKey_<usage>` and
`crypto_aesIv_<usage>`. The usage that matters is `requestEnc`. Two cipher shapes are in
play, AES-GCM framed as `iv || ciphertext || tag`, and an AES-CBC with a hand-rolled
space padding and Latin1 key parsing.

To talk to eCW without a browser you would have to reimplement, and keep matching across
vendor releases: the RSA fetch, the PKCS#1 wrapping, two AES modes, the Latin1 key
parsing, the space-padding quirk, the per-usage registration handshake, the
`hex_sha1(MD5(password))` pre-hash, the CSRF pair, **and** the URL encryption, with no
stable path to replay, because the address of every data call is itself ciphertext.

Supporting negatives, all checked: there is no `/api/` or `/rest/` base anywhere in the
login bundles; the vendor's FHIR door needs an app registration a practice has to issue
and this one has not; and a non-browser user agent gets HTTP 400 on a URL that answers
200 in Chrome.

Auth is a `JSESSIONID` cookie (Path=/mobiledoc, Secure, SameSite=Strict, HttpOnly) plus
a CSRF header. There is no bearer token and no JSON login response.

**Browser only, always.** A side effect worth knowing: anything that clears browser
storage mid-session breaks in-app AJAX without touching the cookie, because the AES key
lives in `localStorage`.

## 8. Every failure seen, and the only tell that separates it from the others

Ranked by how likely it is to be misread as something else.

| # | failure | how the page looks | the ONLY reliable tell | what to do |
|---|---|---|---|---|
| 1 | plug-in nag after a **successful** login | identical to a fresh login page, no error text anywhere | URL query `error=6&reminderPluginPopupStatus=1` on `newLogin.jsp` | you are signed in. Go to `index.jsp`. Never retry the password. |
| 2 | credentials refused | a login page | back on `newLogin.jsp` with no `error=6`. **This practice renders no error box at all.** | stop. Spend a sign-in attempt from the session budget of two (SKILL.md rule 7) only if one is left, then a person. Repeated failures lock a live clinical account. |
| 3 | username not known | screen one never advances | a visible `input#passwordField` never appears after `input#nextStep` | stop. Costs no login attempt, so it is the cheapest pre-check there is. |
| 4 | security image not enrolled | a modal picture grid | URL is `.../login/SecurityImage.jsp` | **stop, tell a person** (section 4). Never click through: the X and Logout both sign you out. |
| 5 | temporary or expired password | an orange "Change Password" modal with a CAPTCHA | URL is `.../login/changePasswordOnLogin.jsp` | **stop, tell a person** (section 5). Do not fill the form. |
| 6 | wrong in-app address | a bare "HTTP Status 412 Precondition Failed" | HTTP 412 with an almost empty body | a known-bad address, not a session problem. Do not read it as signed out. |
| 7 | unknown address | the login page | a 302 to the login page, which eCW does for **every** address it does not know | assert on the page, never on the status. This is why a wrong chart address reads back as "no such chart" for a patient who is on file. |
| 8 | non-browser user agent | "Error/Under Maintenance" | HTTP 400 on a URL that answers 200 in Chrome | **not reachable from inside a session** — the user agent is the sidecar browser's, and rule 5 refuses `browser_cdp`. If you are seeing this you are not looking at the sidecar. It is why a `curl` check of "is eCW up" reports an outage that is not there. |
| 9 | session expired | a login page | back on a `/webemr/login/` path mid-read | **Not** a credential failure — but you cannot prove that, see below. Sign in again **only if the session budget of two attempts (SKILL.md rule 7) has not been spent.** It has no separate allowance: a bounce and a refusal are the same page. |
| 10 | second concurrent session | UNRECORDED on a real practice | unknown | never force it. A live session may have a real person on the other end. |
| 11 | window too narrow | a different, re-laid-out page | none. It silently renders differently. | read `window.innerWidth` and `window.innerHeight` (rule 4). Under 1600 x 1000, **say so and stop** — you cannot set it from here, because `browser_cdp` is what would and rule 5 refuses it. The sidecar's window size is a configuration fact a person sets once (section 0). |
| 12 | CAPTCHA misread | the change-password modal redisplays | the form does not advance | **you cannot be here.** Rule 10 forbids filling this form, so there is no CAPTCHA of yours to re-read. Stop and tell a person. A retry loop on this screen is the account-lockout path this skill exists to prevent. |

### The refused-credentials selector, and the stronger statement that replaces it

Nobody has deliberately failed a login on this practice. One sign-in did fail naturally,
on a reused browser profile carrying a logged-out session: the username step posted and
**bounced straight back to `newLogin.jsp` with the plain username screen, no password
field in the DOM, and zero error elements.** The selectors `.error`, `.alert`,
`.errorMsg`, `[class*=error]`, `[id*=error]` and `.text-danger` were all enumerated and
the result was an empty list.

So there is no error selector to record, and the recording says something stronger than
a selector would have:

> **This practice's login page renders no error element at all.** `.error`, `.alert`,
> `.errorMsg`, `[class*=error]`, `[id*=error]` and `.text-danger` were every one of them
> enumerated on a naturally failed sign-in and every one came back an empty list. A
> refusal looks exactly like a fresh login page. So recognition must be **state-based** —
> did the password field appear, does the URL carry `error=6` — and **never text-based**.
> And because **a bounce is indistinguishable from a refusal**, the sign-in budget is
> load-bearing rather than a nicety: **that indistinguishability is the reason for it.**
> An agent that treats row 9 as free re-signs in as many times as the session drops, each
> time believing it is not retrying, and a stale session turns into a lockout on a real
> clinician's account. Hence one budget of two attempts for the whole working session,
> across every cause (`SKILL.md` rule 7), and every attempt also spends one of the four
> remaining verification skips.

## 9. What is still unmeasured

Say so rather than guessing, and close these with one live session when somebody has
authority to run it.

- **Session lifetime.** No idle timeout, no absolute timeout, and no answer to whether a
  second sign-in kicks the first. Until it is measured, treat "back on a `/webemr/login/`
  path" as "session gone" rather than "the credentials are wrong" — but note you cannot
  actually tell the two apart on this practice (see the box above), so it still spends from
  the session budget of two sign-in attempts (`SKILL.md` rule 7) and it stops when that is
  gone.
- **The real password rules** behind the information icon on the forced-change screen
  (section 5). A person's ten-second read, not an assistant's.
- **Whether the email verification is once-forever or recurring** (section 6).
- **Whether an accessibility snapshot crosses same-origin frames on this shell.** The
  Web EMR is frame-heavy and `browser_snapshot` reports a frame tree, so the question is
  whether that tree reaches into every frame. This needs one live check by a person, not a
  workaround from inside a session: `browser_cdp` takes a `frame_id` and would answer it,
  and `browser_cdp` is refused on this application (`SKILL.md` rule 5). If a frame's
  contents do not appear in a snapshot, say so and stop.
