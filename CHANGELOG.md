# Changelog - MO2 Agent Control

Versions are issued by the project's version gate. Written as the change happens (rule 61).

## 1.0.1 - 2026-11-02 - untested - runtime mod ordering through `call`, and a plugin name that is not in the profile now says where the file is

The version gate is not in this checkout: 1.0.1 is stamped here for the build and the gate can re-issue the number.

### Fixed
* `set_plugins` refused a name whose plugin file belongs to a mod that is not ticked with a bare "not in this profile":
  an unticked mod's files are not mounted, so its plugins are not in MO2's plugin list at all. The error now says which
  mod provides the file and that the mod must be ticked first; a mod that is ticked but not yet in the list gets "run
  refresh, then try again"; a name no mod has gets the closest name the profile does have. `set_mods` gets the closest
  mod name the same way.
* `set_mods` and `set_plugins` match names case-insensitively and change them under the profile's own spelling (MO2 runs
  on Windows, where a name's case is not part of its identity), so "my patch.esp" now finds "My Patch.esp".
* A request whose names are not all in the profile no longer leaves a backup folder behind: the names are checked
  before the profile files are copied, and a request that changes nothing leaves nothing.

### Added
* The MCP server exposes the plugin's `call` command as a `call` tool: it hands an action and its args to another MO2
  plugin's command handler (`info`'s `extensions` lists the ones loaded in this MO2), which is how a mod-order plugin
  such as `MO2PriorityControl` moves a mod up or down while MO2 is running - the server does not wrap those actions
  itself. It is a write: refused while MO2 is in use without `confirm`, and the profile's list files are backed up first.
* `plugins` takes `include_unlisted` (default false): the reply then lists the plugin files the profile does not have -
  from mods that are not ticked, or from a mod MO2 has not refreshed yet - each with `in_profile` and `mod_active`, so a
  client can see whether a plugin exists while its mod is off. The MCP `plugins` tool takes the same argument.
* `docs\PROTOCOL.md` and `docs\MCP.md`: the plugin-list scope (an unticked mod has no plugins in the profile), the new
  fields, the new error texts, and that names are matched case-insensitively.

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
