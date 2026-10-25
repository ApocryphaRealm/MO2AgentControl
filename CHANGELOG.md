# Changelog - MO2 Agent Control

Versions are issued by the project's version gate. Written as the change happens (rule 61).

## 1.0.0 - 2026-10-24 - untested - first public release

### Added
* An MO2 plugin that opens a command channel on 127.0.0.1 only, with a new random token each session, written to
  `plugins\data\ApocryphaAgentControl\channel.json` in the instance.
* Reads: `info`, `profiles`, `mods`, `plugins`, `overwrite`, `executables`, `backups`. Writes: `select_profile`,
  `set_mods`, `set_plugins`, `refresh`, `run` (through MO2's virtual file system, returns the pid at once), `call`
  (commands other MO2 plugins register) and `mm` (MO2 Modlist Manager's short form).
* The in-use check: changes are refused while MO2's window is in front and the keyboard or mouse was used within the
  last few minutes, unless the request carries a `confirm` note. Three settings: on/off (default on), minutes
  (default 5), and an optional activity file from a tool that can tell a person's input from a script's.
* `modlist.txt`, `plugins.txt` and `loadorder.txt` are backed up before every command that changes the profile.
* Follows MO2 2.5.2's own code where it touches it (MO2-REFERENCE.md): the profile switch goes through MO2's profile box
  handler, `run` closes the process handle MO2 hands over, `set_plugins` refuses the game's primary plugins (MO2 never
  changes or lists them), and the settings' descriptions are translated even though MO2 reads them before `init()`.
* `mo2_ctl.py`, a standalone client (Python 3.8+, standard library only; the `mo2-ctl` command once installed), and
  `docs\PROTOCOL.md`, the protocol reference with a minimal client example. `tools\mo2-ctl.py` runs the same file for
  anything that still calls the client at that path.
* `mo2_mcp.py`, a Model Context Protocol server (stdio; the `mo2-mcp` command once installed) built on the same client:
  twelve tools - `info`, `profiles`, `mods`, `plugins`, `executables`, `overwrite`, `backups`, `set_mods`, `set_plugins`,
  `select_profile`, `refresh`, `run`. The plugin's in-use refusal reaches the agent word for word as the tool's error,
  and every write tool has a required `confirm` argument the server never fills in itself. MO2 not running, the plugin
  missing or a stale channel file each give a plain error saying so. Logs to stderr; `--log-level debug` logs every
  request. `docs\MCP.md`: ready-to-paste configuration for Claude Desktop, Claude Code and Cursor, the tools, the errors.
* A pip package, `mo2-agent-control` (`pyproject.toml`; Python 3.10+, depends on `mcp`), holding the client and the
  server as the `mo2-ctl` and `mo2-mcp` commands; the plugin itself is still copied into MO2.
* `tests\test_mo2_ctl_and_mcp.py`: the client and the server against the plugin's core behind a real loopback server
  (45 checks, among them the refusal, the confirm note, the missing-channel errors and a full stdio round trip);
  `tools\mcp_call.py`, which calls one tool through a real stdio session from the command line (to try the server before
  adding it to a client, and for live tests); and `tools\make_release.py`, which builds the release zip and its notes
  from the CHANGELOG into `out\`.
* The plugin's own texts (its description, menu entry, settings and status window) in English, Japanese, Korean,
  Chinese, Russian, German, French, Spanish, Italian, Polish and Czech. Command replies, mo2-ctl's output and the MCP
  tools' texts stay English: tools read them. The product name is "MO2 Agent Control" everywhere a user sees it - the
  plugin list, the Tools menu entry and the status window in every language (a name is not translated), the READMEs,
  the page, the pip package's description and the release notes.

### Development history before 1.0.0
* 2026-10-24: built as "Apocrypha Agent Control" inside the project's own scripts (commits 4e62ff0 and e661987 of the
  `.MD` repository) so the project's agents could operate MO2 without screen control; proven on a scratch instance
  (request e591), including `set_plugins` writing plugins.txt itself because MO2 writes it late.
* 2026-10-24: made a public release (the project owner: "an actual mod with a mod page on Nexus and modding tools for
  anyone who wants to use it"). Renamed MO2 Agent Control; the in-use check, which read the project's own presence
  file, became a setting with Windows' idle clock as the default; `owner_ok` became `confirm` (the old name is still
  read); `call`, `backups` and the version / protocol fields in `info` and `channel.json` added; translations added.
