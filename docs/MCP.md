# MO2 Agent Control as an MCP server

`mo2_mcp.py` (the `mo2-mcp` command once installed) exposes the plugin's commands to any AI agent that speaks the
[Model Context Protocol](https://modelcontextprotocol.io) - Claude Desktop, Claude Code, Cursor and others. The agent
sees twelve tools; each is one command of the plugin's protocol ([PROTOCOL.md](PROTOCOL.md)), sent through the same
client `mo2-ctl` uses. The server talks to nothing but the running MO2 on 127.0.0.1.

## 1. Install

The plugin itself goes into MO2 as the README says (copy `plugins\ApocryphaAgentControl` into MO2's `plugins` folder,
restart MO2). Then, for the server, either:

**a) pip / pipx** (Python 3.10 or newer):

```
pipx install mo2-agent-control
```
(or `pip install mo2-agent-control`). This installs two commands, `mo2-mcp` and `mo2-ctl`.

**b) no install**: keep `mo2_mcp.py` and `mo2_ctl.py` together in any folder and run `python mo2_mcp.py`. The `mcp`
package is the one dependency: `pip install mcp`.

## 2. Tell the server which MO2 instance

The instance is the folder holding `ModOrganizer.exe`. Give it one of three ways, in this order:

1. `--instance "D:\MO2"` on the command line (the snippets below do this);
2. the `MO2_INSTANCE` environment variable;
3. nothing - when the server is started from inside the instance folder.

Other options: `--timeout` (seconds to wait for MO2's answer, default 600), `--log-level debug|info|warning|error`
(stderr; or the `MO2_MCP_LOG` variable). `mo2-mcp --help` lists them.

## 3. Client configuration - ready to paste

Replace `D:\MO2` with your instance folder. Keep the backslashes doubled inside JSON. If you did not install with pip,
replace `"command": "mo2-mcp"` with `"command": "python"` and put the full path of `mo2_mcp.py` first in `args`.

### Claude Desktop

File: `%APPDATA%\Claude\claude_desktop_config.json` (Settings > Developer > Edit Config). Restart Claude Desktop.

```json
{
  "mcpServers": {
    "mo2": {
      "command": "mo2-mcp",
      "args": ["--instance", "D:\\MO2"]
    }
  }
}
```

Without pip:

```json
{
  "mcpServers": {
    "mo2": {
      "command": "python",
      "args": ["C:\\Tools\\MO2AgentControl\\mo2_mcp.py", "--instance", "D:\\MO2"]
    }
  }
}
```

### Claude Code

One command, in Command Prompt or PowerShell:

```
claude mcp add mo2 -- mo2-mcp --instance "D:\MO2"
```

Or a `.mcp.json` in the project folder (shared with the project) with the same shape as Claude Desktop's file:

```json
{
  "mcpServers": {
    "mo2": {
      "command": "mo2-mcp",
      "args": ["--instance", "D:\\MO2"]
    }
  }
}
```

`claude mcp list` shows it; `/mcp` inside Claude Code shows the tools.

### Cursor

File: `.cursor\mcp.json` in the project (or `%USERPROFILE%\.cursor\mcp.json` for every project); Cursor Settings >
MCP shows the server and its tools.

```json
{
  "mcpServers": {
    "mo2": {
      "command": "mo2-mcp",
      "args": ["--instance", "D:\\MO2"]
    }
  }
}
```

### Any other MCP client

Transport: stdio. Command: `mo2-mcp --instance <folder>` (or `python mo2_mcp.py --instance <folder>`). No environment
variables are required.

## 4. The tools

| Tool | Arguments | What it does |
|---|---|---|
| `info` | - | instance, profile, game, plugin version and protocol, the commands, `in_use` and `in_use_why` |
| `profiles` | - | profile names and the current one |
| `mods` | `active_only` (default false) | the mods of the current profile, left-pane order: name, active, separator |
| `plugins` | - | the plugins in load order: name, active, origin |
| `executables` | - | MO2's Run list: title, binary |
| `overwrite` | `limit` (default 500) | the files in Overwrite |
| `backups` | - | the profile backups the plugin made, newest first |
| `set_mods` | `names`, `active`, `confirm` | tick or untick mods (names exactly as `mods` returns them) |
| `set_plugins` | `names`, `active`, `confirm` | tick or untick plugins; plugins.txt is written at once |
| `select_profile` | `name`, `confirm` | switch profile through MO2's own profile box |
| `refresh` | `save`, `confirm` | MO2's Refresh; `save: true` writes modlist.txt first |
| `run` | `executable` or `binary`, `args`, `cwd`, `profile`, `confirm` | start a program through MO2's VFS; returns `pid` at once, never waits |

Every reply is the plugin's own JSON reply (PROTOCOL.md section 3). A write that changed the profile also carries
`backup`, the folder its list files were copied to first.

## 5. The two safety rules, as the agent meets them

**Writes are refused while you are using MO2.** When MO2's window is in front and you used the keyboard or mouse in
the last few minutes (5 by default), the plugin refuses `set_mods`, `set_plugins`, `select_profile`, `refresh` and
`run`. The agent gets the refusal as the tool's error, in the plugin's words:

```
refused: MO2 is in use (MO2 is in front and the last input was 0.4 min ago (Windows' idle clock)) - send confirm with a
note saying who approved this, or turn off the plugin's in-use check
```

Reads always work, and `info` says in advance whether a write would be refused (`in_use`).

**`confirm` is the agent's word that you approved.** Every write tool has a required `confirm` argument - the note the
plugin logs beside the change (`plugins\data\ApocryphaAgentControl\log.txt`). The server never fills it in; the agent
has to pass it, and its instructions tell it to ask you first and to send an empty string when it has not. An empty
`confirm` means the write goes through only while MO2 is idle. So in a normal session: the agent tries, MO2 refuses
because you are in it, the agent asks you, you say yes, the agent sends `confirm: "the user, in chat"` and the change
is made and logged with that note.

The check can be turned off in MO2 under Settings > Plugins > MO2 Agent Control (`refuse_writes_while_in_use`), for a
machine where no one is sitting at MO2 while agents work.

## 6. Errors you may see

| Error | Meaning |
|---|---|
| `MO2 is not reachable: no channel file ... - is MO2 running with the MO2 Agent Control plugin installed?` | MO2 is not running, or the plugin is not installed in that instance, or `--instance` points at the wrong folder |
| `MO2 is not reachable: the MO2 that wrote ... (pid N) is not running` | the channel file is left over from an MO2 that has since closed; start MO2 |
| `MO2 is not reachable: nothing answered on 127.0.0.1:...` | MO2 is closing, or the port was taken over; restart MO2 |
| `no MO2 instance: start mo2-mcp with --instance ...` | the server was started without an instance (section 2) |
| `refused: wrong or missing token` | MO2 restarted since the channel file was read - the server reads the file on every call, so this clears itself |
| `MO2 answered with an error: ValueError: not in this profile: X` | a name that is not in the current profile; `mods` / `plugins` list the exact names |

## 7. Logging

The server logs to stderr, never stdout (stdout carries the protocol). At the default `info` level it logs refusals and
errors; `--log-level debug` (or `MO2_MCP_LOG=debug`) logs every request and reply. Claude Desktop keeps a server's
stderr in `%APPDATA%\Claude\logs\mcp-server-mo2.log`.
