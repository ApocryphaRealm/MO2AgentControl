# MO2 Agent Control - the protocol (version 1)

Everything a client needs to talk to the plugin. `mo2_ctl.py` is one such client, and a small one; read it alongside
this page. `mo2_mcp.py` wraps that client as a Model Context Protocol server for AI agents ([MCP.md](MCP.md)).

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
| `ui_tree` | `window`, `path`, `kinds`, `labels`, `limit` | the windows, the open modal dialog and the controls - section 6 |

### Writes - refused while MO2 is in use (section 4)

| cmd | args | what it does |
|---|---|---|
| `select_profile` | `name` | switches profile through MO2's own profile box |
| `set_mods` | `names` (list), `active` (bool) | ticks or unticks mods in the left pane |
| `set_plugins` | `names` (list), `active` (bool) | ticks or unticks plugins; plugins.txt is written at once (MO2 itself writes it late) |
| `refresh` | `save` (bool, default false) | MO2's Refresh; `save: true` writes modlist.txt first (MO2's own refresh saves nothing else) |
| `run` | `executable` (a title from `executables`) or `binary` (a path); `args` (list), `cwd`, `profile` | starts the program through MO2's virtual file system - like pressing Run - and replies at once with `started` and `pid`. It never waits: MO2's own wait locks its window. Poll the pid. |
| `call` | `plugin`, `action`, `args` | hands `action` and `args` to another MO2 plugin's handler (section 5); the reply's `result` is what it returned |
| `mm` | `action`, `args` | short for `call` with `plugin: "MO2ModlistManager"` |
| `ui_click`, `ui_answer_modal`, `ui_set` | section 6 | press a button, answer the open dialog, set a control - in any MO2 window, without the mouse |

Names in `names` must match exactly (case included) what `mods` / `plugins` return; an unknown name fails the whole
request before anything is changed.

**Backups.** Before `select_profile`, `set_mods`, `set_plugins`, `call`, `mm`, `ui_click` and `ui_answer_modal`, the plugin copies the current profile's
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

## 6. Window commands: MO2's windows and dialogs, without the mouse (since 1.1.0)

For what the commands of section 3 cannot do: a plugin's own window, a settings dialog, a question that is waiting for an
answer. Each command calls the widget's own method on MO2's GUI thread - `click()`, `setText()` and so on. No mouse or
keyboard input is sent and no window is moved or raised, so it works with MO2 minimised or behind other windows.
`info` lists the four names in `reads` / `writes`; a plugin older than 1.1.0 answers `unknown command`.

| cmd | kind | args | reply |
|---|---|---|---|
| `ui_tree` | read | `window`, `path`, `kinds` (list), `labels` (bool), `hidden` (bool), `limit` (default 300) | `windows`: every visible window `{"title", "name", "class", "modal", "active"}`; `modal`: the open modal dialog or `null`; `window`: the one listed; `controls`; `truncated` |
| `ui_click` | write | a locator; `wait_ms` | `clicked` (the control), `returned`, `modal` |
| `ui_answer_modal` | write | `role` or `text`; `expect`; `wait_ms` | `answered` (the dialog as it was), `pressed`, `closed`, `returned`, `modal` |
| `ui_set` | write | a locator; `value`; `wait_ms` | `set` (the control as it was), `asked`, `value` (read back), `applied`, `returned`, `modal` |

**Controls.** `kind` is `button`, `checkbox`, `radio`, `edit`, `text` (a multi-line box), `combo`, `spin`, `tabs`, or
`label` (only with `labels: true`). Each has `name` (the widget's objectName, often empty), `class`, `enabled`,
`visible`, `where` (the group boxes, tabs and named containers it sits in, outermost first) and, by kind, `text`,
`checked`, `value`, `items`, `index`, `min` / `max`, `read_only`. A button's `text` has no `&` shortcut mark. An edit,
combo or spin box has `text` when a label names it. With no `window` given, `ui_tree` lists the open modal dialog's
controls, or every window's when no dialog is open.

**The modal dialog.** `modal` is `{"title", "name", "class", "buttons": [{"text", "role", "enabled", "default",
"escape"}]}`, plus `text`, `informative` and `detailed` for a message box. `role` is `accept`, `reject`, `yes`, `no`,
`apply`, `destructive`, `action`, `help`, `reset`, or empty for a dialog that does not declare roles.

**A locator** names exactly one control: `name` and/or `text` (both exact, as `ui_tree` shows them), optionally `kind`,
`window` (a window's title or objectName) and `path` (`"Outer > Inner"`: each part a window title, an objectName, a
group box's title or a tab's text, each inside the one before). A locator that matches more than one control **fails
and lists the candidates - nothing is pressed**; add `window`, `path`, or `index` (0-based, in `ui_tree`'s order). Hidden
and disabled controls cannot be acted on. While a modal dialog is open, only that dialog's controls can be acted on
(reads may still name another window).

**`ui_answer_modal`** presses a button of the open modal dialog by `role` or by `text` - one of them. Two buttons with
the same role make `role` ambiguous: it fails and lists the texts. `expect` is a piece of the dialog's title or text
that must be present, so a script never answers a different dialog from the one it meant to.

**`ui_set`** takes `true` / `false` for a checkbox, radio button or checkable button; text for an edit or text box; an
item's text or its index for a combo box (any text for an editable one); a number inside the range for a spin box; a
tab's text or index for a tab bar. The change is made the way a person's would be seen by the program (a checkbox is
clicked; an edit also emits `textEdited` and `editingFinished`; a combo also emits `activated`), and `value` is what the
control holds afterwards.

**When the reply comes.** Requests are answered while a modal dialog is open: a dialog runs its own event loop on the
GUI thread, and that loop serves the channel like any other. But the press that OPENS a dialog does not return until
the dialog is closed. So every window write runs just after its request has been read, and the reply is sent when the
action returns (`"returned": true`) - or after `wait_ms` (default 400, at most 60000) if it has not, with
`"returned": false` and `modal` describing the dialog it is waiting in. Answer that dialog with `ui_answer_modal` on a
new connection:

```json
{"cmd": "ui_click", "args": {"window": "MO2 Modlist Manager", "text": "Apply"}}
{"ok": true, "clicked": {"kind": "button", "text": "Apply"}, "returned": false,
 "modal": {"title": "Apply", "text": "...", "buttons": [{"text": "Apply and switch them off", "role": "accept"},
           {"text": "Apply, leave plugins as they are", "role": "accept"}, {"text": "Cancel", "role": "reject"}]}}
{"cmd": "ui_answer_modal", "args": {"text": "Apply, leave plugins as they are", "expect": "Apply"}}
{"ok": true, "pressed": "Apply, leave plugins as they are", "closed": true, "returned": true, "modal": null}
```

An action that runs long without opening a dialog answers when it is done, so allow the client a generous timeout.
`ui_click` and `ui_answer_modal` back the profile's list files up first, like the other profile-changing writes
(`backup` in the reply); all three are refused while MO2 is in use unless `confirm` is given (section 4). A dialog that
is not Qt's own (a Windows file picker) is not reached by these commands.

## 7. Writing a client

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
