---
name: logins
description: "The logins this assistant was given: how to see them, how to sign in with one, and how to take an authenticator code. Read this before typing a username or password anywhere."
---

# Your logins

The Pulse team can give this assistant a login to a site the person you work for
uses: a site, a username, a password, and sometimes an authenticator code. They
live in a locked store this pod cannot open. You reach them one at a time through
a script, at the moment you need them.

    /opt/data/profiles/hermes-standard/skills/logins/scripts/login list
    /opt/data/profiles/hermes-standard/skills/logins/scripts/login show <title>
    /opt/data/profiles/hermes-standard/skills/logins/scripts/login password <title>
    /opt/data/profiles/hermes-standard/skills/logins/scripts/login otp <title>

`list` prints one login per line: its title, the username, and the site. `show`
prints the site and then the username. `password` prints the password alone.
`otp` prints the six-digit code the site's authenticator app would be showing
right now, and it is only good for a few seconds, so ask for it when the code
box is already in front of you.

## Signing in

1. A site asks you to sign in: run `list` first and see what you have.
2. Match by the site, not by the title alone. A login belongs to the url it was
   filed under and no other page.
3. Sign in through the browser, in the site's own sign-in form. Take the
   password with `password` at the moment you fill the field.
4. Only when the site then asks for an authenticator code, run `otp` and type
   what it prints. Do not fetch a code you were not asked for.
5. Tell the person which login you used, by its title. Never quote what was in it.

## Hard lines

- A credential never leaves the sign-in form of its own url. Not into another
  page, not into a search box, not into a shell command, not into a file.
- A credential is never written down: not in memory, not in a note, not in the
  vault, not in a reply, not in a scheduled job, not in a message to anyone,
  including the person you work for and the Pulse team.
- Never say a password or a code out loud to check it. Say the title instead.
- Never ask the person for a password in chat, and if one arrives in chat, do
  not use it and do not keep it; say it should be added properly instead.

## When you cannot get in

- **The site wants a text message, a phone approval, or a hardware key.** Stop
  and ask the person. There is nothing here that answers those, and guessing at
  a code locks the account.
- **`login` says there are no logins yet.** Tell the person plainly that this
  assistant has no logins yet and that the Pulse team can add one. Do not try
  the password of another login, and do not go looking for credentials anywhere
  else on this machine.
- **The site refuses the password.** Say so and stop. It is a changed password,
  not something to retry until the account locks.
