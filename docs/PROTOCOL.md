# MO2 Agent Control - the protocol (version 1)

Everything a client needs to talk to the plugin. `tools/mo2-ctl.py` is one such client, and a small one; read it
alongside this page.

## 1. Finding the channel

When MO2 starts with the plugin installed, the plugin listens on **127.0.0.1** on a random free port and writes:

```
<MO2 instance>\plugins\data\ApocryphaAgentControl\channel.json
```

```json
{"host": "127.0.0.1", "port": 50123, "token": "<64 hex characters>", "pid": 12345,
 "instance": "D:\\MO2", "started": 1761350000.0, "version": "1.0.0", "protocol": 1}
```

- `token` is new every time MO2 starts. A client that kept an old one gets `wrong or missing token` - read the file
  again.
- `pid` is MO2's process id. If that process is gone, the file is stale (MO2 closed or crashed); no one is listening.
- `host` is always `127.0.0.1`. A client should refuse a file naming any other host.

The plugin never listens on another interface and drops a connection that does not come from the loopback address.
Anyone who can read this instance's files can read the token; that is the access boundary, the same one that already
lets any program on the computer edit the instance's profile files directly.

## 2. One request, one reply

Open a TCP connection to `127.0.0.1:<port>`, send **one line** of UTF-8 JSON ending in `\n`, read one line back. The
plugin closes the connection after replying. Requests over 1 MiB are dropped.

```json
{"token": "<token>", "cmd": "set_mods", "args": {"names": ["My Patch"], "active": true}, "confirm": "optional note"}
```

| Field | Meaning |
|---|---|
| `token` | from `channel.json` - required |
| `cmd` | a command from section 3 - required |
| `args` | a JSON object; may be left out when a command takes none |
| `confirm` | optional text: who approved a change made while MO2 is in use (section 4). Logged. (`owner_ok` is read too - its name before 1.0.0) |

Every reply is a JSON object with `ok`:

```json
{"ok": true, "set": ["My Patch"], "active": true, "backup": "D:\\MO2\\plugins\\data\\ApocryphaAgentControl\\backups\\20261024-201500-set_mods"}
{"ok": false, "error": "ValueError: not in this profile: Nope"}
{"ok": false, "refused": true, "error": "MO2 is in use (MO2 is in front and the last input was 0.4 min ago (Windows' idle clock)) - send confirm ..."}
```

`refused: true` means the request was well formed but not allowed (wrong token, or MO2 in use). Reply texts are
English whatever language MO2 shows, so a script can match on them.

## 3. Commands

### Reads - always allowed

| cmd | args | reply |
|---|---|---|
| `info` | - | `instance`, `profile`, `game`, `pid`, `version`, `protocol`, `reads`, `writes`, `in_use`, `in_use_why`, `extensions` |
| `profiles` | - | `profiles` (names), `current` |
| `mods` | `active_only` (bool) | `mods`: `[{"name", "active", "separator"}]`, in the left pane's order |
| `plugins` | - | `plugins`: `[{"name", "active", "origin"}]`, in load order; `origin` is the mod that provides the file |
| `overwrite` | `limit` (default 500) | `overwrite` (folder), `files` (paths relative to it), `truncated` |
| `executables` | - | `executables`: `[{"title", "binary"}]` from MO2's executables list |
| `backups` | - | `root`, `backups`: `[{"name", "path", "files"}]`, newest first |

### Writes - refused while MO2 is in use (section 4)

| cmd | args | what it does |
|---|---|---|
| `select_profile` | `name` | switches profile through MO2's own profile box |
| `set_mods` | `names` (list), `active` (bool) | ticks or unticks mods in the left pane |
| `set_plugins` | `names` (list), `active` (bool) | ticks or unticks plugins; plugins.txt is written at once (MO2 itself writes it late) |
| `refresh` | `save` (bool, default false) | MO2's Refresh; `save: true` writes MO2's lists first |
| `run` | `executable` (a title from `executables`) or `binary` (a path); `args` (list), `cwd`, `profile` | starts the program through MO2's virtual file system - like pressing Run - and replies at once with `started` and `pid`. It never waits: MO2's own wait locks its window. Poll the pid. |
| `call` | `plugin`, `action`, `args` | hands `action` and `args` to another MO2 plugin's handler (section 5); the reply's `result` is what it returned |
| `mm` | `action`, `args` | short for `call` with `plugin: "MO2ModlistManager"` |

Names in `names` must match exactly (case included) what `mods` / `plugins` return; an unknown name fails the whole
request before anything is changed.

**Backups.** Before `select_profile`, `set_mods`, `set_plugins`, `call` and `mm`, the plugin copies the current profile's
`modlist.txt`, `plugins.txt` and `loadorder.txt` into `backups\<time>-<command>\`, and the reply names that folder in
`backup`. To go back: close MO2 and copy the three files into `profiles\<profile>\`.

## 4. The in-use check

A person clicking in MO2 and a script changing the same lists at the same moment is how lists get damaged. So by
default a **write** is refused while MO2 is in use: its window is the one in front AND the keyboard or mouse was used
within the last 5 minutes. A request with `confirm` goes through anyway (and the note is logged) - for a tool that has
asked its user first.

MO2's Settings > Plugins > MO2 Agent Control:

| Setting | Default | |
|---|---|---|
| `refuse_writes_while_in_use` | true | false turns the check off |
| `in_use_minutes` | 5 | how recent the last input must be |
| `activity_file` | empty | a JSON file `{"last_input_epoch": <unix time>, "alive_epoch": <unix time>}` kept up to date by another tool. While `alive_epoch` is under 3 minutes old it is used instead of Windows' idle clock - for setups where scripts also send input (Windows' clock cannot tell the two apart) |

`info` reports `in_use` and why, so a client can check before it tries.

## 5. Extensions: commands from other MO2 plugins

Another MO2 Python plugin can offer commands through `call` without depending on this one:

```python
import sys, types
reg = sys.modules.get("apocrypha_agent_registry")
if reg is None:
    reg = types.ModuleType("apocrypha_agent_registry")
    reg.handlers = {}
    sys.modules["apocrypha_agent_registry"] = reg
reg.handlers["MyPlugin"] = lambda action, args: {"did": action}
```

The handler runs on MO2's GUI thread, gets `action` (a string) and `args` (a dict), and returns anything JSON can
encode; raising an exception becomes `{"ok": false, "error": ...}`. `info` lists the registered names in `extensions`.
MO2 Modlist Manager registers itself this way when it is installed.

## 6. Writing a client

```python
import json, socket
ch = json.load(open(r"D:\MO2\plugins\data\ApocryphaAgentControl\channel.json", encoding="utf-8"))
with socket.create_connection(("127.0.0.1", ch["port"]), timeout=60) as s:
    s.sendall((json.dumps({"token": ch["token"], "cmd": "mods", "args": {"active_only": True}}) + "\n").encode())
    reply = b""
    while not reply.endswith(b"\n"):
        part = s.recv(65536)
        if not part:
            break
        reply += part
print(json.loads(reply))
```

The protocol number changes only when a change would break an existing client; new commands and new reply fields do
not change it.
