MO2 Agent Control
=================
Version 1.0.0

A Mod Organizer 2 plugin that lets scripts, tools and AI agents operate a running MO2 - list and tick
mods and plugins, switch profiles, refresh, run an executable through MO2's virtual file system -
without clicking on its window. Comes with mo2-ctl, a command-line client, mo2-mcp, an MCP server
that gives AI agents (Claude Desktop, Claude Code, Cursor) the same commands as tools, and a
documented JSON protocol (docs\PROTOCOL.md) for writing your own.

THIS IS NOT A MOD. Do not install it with the mod manager.

REQUIREMENTS
------------
Mod Organizer 2 2.5 or newer. mo2_ctl.py needs Python 3.8 or newer (standard library only); the MCP
server needs Python 3.10 or newer and the "mcp" package (pip install mcp), or install both with
pipx install mo2-agent-control.

INSTALLATION
------------
Copy the folder plugins\ApocryphaAgentControl into your MO2 folder's "plugins" folder, next to the
other plugins, and restart MO2. Tools -> MO2 Agent Control shows whether it is listening.
Copy mo2_ctl.py (and mo2_mcp.py, if you want the MCP server) anywhere convenient - or
pipx install mo2-agent-control for the mo2-ctl and mo2-mcp commands. (If pip finds no such package,
the PyPI upload has not happened yet: pipx install the .whl file from the GitHub release instead.)
To remove it, delete the plugins\ApocryphaAgentControl folder.

USE
---
  python mo2_ctl.py --instance "D:\MO2" info
  python mo2_ctl.py --instance "D:\MO2" mods active_only=true
  python mo2_ctl.py --instance "D:\MO2" set_mods names='["My Patch"]' active=true
  python mo2_ctl.py --instance "D:\MO2" set_plugins names='["MyPatch.esp"]' active=false
  python mo2_ctl.py --instance "D:\MO2" select_profile name="Testing"
  python mo2_ctl.py --instance "D:\MO2" run executable="SKSE"
  python mo2_ctl.py --help        (every command)

AI AGENTS (MCP)
---------------
  python mo2_mcp.py --instance "D:\MO2"      (or: mo2-mcp --instance "D:\MO2")
Add it to Claude Desktop, Claude Code or Cursor with the snippets in docs\MCP.md. The agent gets the
twelve commands as tools; a change it tries while you are using MO2 is refused, and it has to ask you
before passing a confirm note.

SAFETY
------
- Listens on 127.0.0.1 only, with a new secret token each time MO2 starts.
- While MO2's window is in front and you used keyboard or mouse in the last 5 minutes, commands that
  change anything are refused (reading still works). --confirm "<note>" lets a tool that asked you
  go ahead; the check can be turned off in Settings -> Plugins -> MO2 Agent Control.
- modlist.txt, plugins.txt and loadorder.txt are backed up before every change
  (plugins\data\ApocryphaAgentControl\backups).

DEBUGGING
---------
<your MO2 folder>\plugins\data\ApocryphaAgentControl\log.txt - one line per change or refusal.
Send it with any bug report.

LICENCE
-------
GPL-3.0-or-later. Copyright (C) 2026 ApocryphaRealm. See LICENSE and NOTICE.md.
Source: https://github.com/ApocryphaRealm/MO2AgentControl
