# MO2 Agent Control

A Mod Organizer 2 plugin that lets scripts, tools and AI agents operate a running MO2 - list and tick mods and
plugins, switch profiles, refresh, run an executable through MO2's virtual file system - **without clicking on its
window**. It comes with `mo2-ctl`, a small command-line client, and a documented JSON protocol for anyone who wants
to write their own.

## What it is for

Automating MO2 has meant one of two things: editing `modlist.txt` and `plugins.txt` while MO2 is closed, or driving
its window with simulated clicks. The first means closing MO2 for every change; the second breaks the moment a
window moves, a dialog pops up or the theme changes, and it takes over the mouse while it runs.

This plugin gives MO2 a proper front door instead. A script asks MO2 itself to do the thing, MO2 does it through its
own API - exactly as if the box had been ticked by hand - and the script gets a plain JSON answer back.

Useful for:

- **AI coding agents** that maintain a modlist (Claude Code, and anything else that can run a command);
- **batch scripts**: turn a set of patches on for one test, back off afterwards;
- **tool authors** who want to start xEdit, LOOT, Synthesis or the game through MO2's VFS from their own tool;
- **testing**: switch profile, run the game, read what landed in Overwrite.

## Safety

- **This computer only.** The plugin listens on 127.0.0.1 and nowhere else, and drops any connection that does not
  come from the loopback address.
- **A new secret token every session**, written to a file inside the MO2 instance. Only a program that can read
  that instance's files can talk to it - and such a program could already edit the profile files directly.
- **It will not fight you for MO2.** While MO2's window is in front and you have used the keyboard or mouse in the
  last few minutes, commands that change anything are refused (reads still work). A tool that asked you first can
  pass a `--confirm` note; the setting can be turned off.
- **Backups before every change.** `modlist.txt`, `plugins.txt` and `loadorder.txt` are copied before each command
  that changes the profile; the reply says where.
- **A fixed list of commands.** Nothing outside the list in `docs/PROTOCOL.md` exists; there is no "run Python" or
  "write a file" command.

## Install

1. Copy the `plugins\ApocryphaAgentControl` folder into your MO2 folder's `plugins` folder (next to the other
   plugins), and restart MO2.
2. Optional: copy `tools\mo2-ctl.py` anywhere convenient. It needs Python 3.8 or newer and nothing else.

**Tools -> Agent Control** shows whether the channel is listening and where its channel file is.
Settings: **Settings -> Plugins -> MO2 Agent Control**.

Requires Mod Organizer 2 2.5 or newer (PyQt6); 2.4 (PyQt5) should work but is untested.

## Using mo2-ctl

```
python mo2-ctl.py --instance "D:\MO2" info
python mo2-ctl.py --instance "D:\MO2" profiles
python mo2-ctl.py --instance "D:\MO2" mods active_only=true
python mo2-ctl.py --instance "D:\MO2" plugins
python mo2-ctl.py --instance "D:\MO2" set_mods names='["My Patch","Another Mod"]' active=true
python mo2-ctl.py --instance "D:\MO2" set_plugins names='["MyPatch.esp"]' active=false
python mo2-ctl.py --instance "D:\MO2" select_profile name="Testing"
python mo2-ctl.py --instance "D:\MO2" refresh
python mo2-ctl.py --instance "D:\MO2" executables
python mo2-ctl.py --instance "D:\MO2" run executable="SKSE"
python mo2-ctl.py --instance "D:\MO2" overwrite limit=50
python mo2-ctl.py --instance "D:\MO2" backups
```

- A `key=value` value is read as JSON when it parses (`true`, `5`, `["a","b"]`, `{...}`), otherwise as text.
  `--json '{"names": ["A"], "active": true}'` passes the whole argument object at once.
- `--instance` can be left out when the `MO2_INSTANCE` environment variable names the instance, or when you run it
  from the instance folder.
- `run` replies at once with the new process id - it does not wait for the program to close (MO2's own wait would
  lock its window). Poll the pid if you need to know.
- Exit codes: `0` done, `1` MO2 answered with an error, `2` usage, `3` refused (wrong token, or MO2 in use),
  `4` no running MO2 with the plugin.

## The protocol

One line of JSON in, one line out, over a loopback TCP socket - see [docs/PROTOCOL.md](docs/PROTOCOL.md) for the
channel file, every command, the reply shapes, the in-use check and the extension hook that lets other MO2 plugins
add their own commands (`call`).

## Settings

| Setting | Default | |
|---|---|---|
| Refuse writes while in use | on | refuse changes while MO2 is in front and you used keyboard or mouse recently |
| In-use minutes | 5 | how recent "recently" is |
| Activity file | empty | optional JSON file from another tool that can tell your real input from a script's |

## Files it writes

All inside the MO2 instance, under `plugins\data\ApocryphaAgentControl\`: `channel.json` (port and token, replaced
at every start), `log.txt` (one line per change or refusal) and `backups\`.

## Licence

GPL-3.0-or-later. Copyright (C) 2026 ApocryphaRealm. See `LICENSE` and `NOTICE.md`.
