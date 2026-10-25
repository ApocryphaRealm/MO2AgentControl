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
* `tools\mo2-ctl.py`, a standalone client (Python 3.8+, standard library only), and `docs\PROTOCOL.md`, the protocol
  reference with a minimal client example.
* The plugin's own texts (its description, menu entry, settings and status window) in English, Japanese, Korean,
  Chinese, Russian, German, French, Spanish, Italian, Polish and Czech. Command replies stay English: tools read them.

### Development history before 1.0.0
* 2026-10-24: built as "Apocrypha Agent Control" inside the project's own scripts (commits 4e62ff0 and e661987 of the
  `.MD` repository) so the project's agents could operate MO2 without screen control; proven on a scratch instance
  (request e591), including `set_plugins` writing plugins.txt itself because MO2 writes it late.
* 2026-10-24: made a public release (the project owner: "an actual mod with a mod page on Nexus and modding tools for
  anyone who wants to use it"). Renamed MO2 Agent Control; the in-use check, which read the project's own presence
  file, became a setting with Windows' idle clock as the default; `owner_ok` became `confirm` (the old name is still
  read); `call`, `backups` and the version / protocol fields in `info` and `channel.json` added; translations added.
