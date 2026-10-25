# Progress - MO2 Agent Control

## 1.0.0 - recorded working 2026-10-25

Tests, in order:
* **e591** (2026-10-24) - the pre-public build ("Apocrypha Agent Control", inside the project's `.MD` scripts) on a
  scratch MO2 instance: PASS, including `set_plugins` writing plugins.txt itself because MO2 writes it late.
* **0714** (2026-10-24) - first request for the public 1.0.0; replaced by 0cc8 before it ran, once the MCP server was
  added.
* **0cc8** (2026-10-24 23:52-23:57, combined run batch B-20261024-235238-a877) - PASS. Every command through
  `mo2_ctl.py` and through a real MCP stdio session, on the scratch instance, with no screen control; the live in-use
  refusal on both paths; confirm notes logged. Evidence: `4. plans\combined-run-2026-10-24e\0cc8\` in the project.

After 0cc8 only README.md, README.txt and docs\MCP.md changed (install steps from the release zip, the Claude Code and
Cursor snippets spelled out, the pip-before-PyPI note); the plugin, client and server files are byte-identical to the
ones tested. Recorded working in the version ledger on that basis.
