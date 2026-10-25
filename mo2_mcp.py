r"""mo2-mcp - the MO2 Agent Control plugin as a Model Context Protocol server (stdio), so an AI agent can operate MO2 as a tool.

Claude Desktop, Claude Code, Cursor and any other MCP client start this program and talk JSON-RPC to it over stdin and
stdout; every tool below is one command of the plugin's protocol (docs\PROTOCOL.md), sent through the same client the
mo2-ctl command uses (mo2_ctl.py - imported, not copied). Nothing here talks to anything but the running MO2 on
127.0.0.1. docs\MCP.md has the ready-to-paste configuration for each client.

  mo2_mcp.py [--instance DIR] [--timeout SECONDS] [--log-level debug|info|warning]
  The instance is --instance, else the MO2_INSTANCE environment variable, else the current folder when it holds
  ModOrganizer.exe. After `pip install mo2-agent-control` the same program is the `mo2-mcp` command.

The plugin's two safety rules carry through unchanged:
  - reads always work; a WRITE is refused while MO2 is in use (its window in front and keyboard or mouse input in the
    last few minutes), and the refusal comes back to the agent as the tool's error, word for word;
  - every write tool takes a `confirm` argument - the note the plugin logs, saying who approved a change made while MO2
    is in use. The agent must pass it explicitly; this server never fills it in. An empty string means "no one has
    approved it": the write goes through only while MO2 is idle.
When MO2 is not running, the plugin is not installed, or the channel file is stale, the tool's error says exactly that.

Logging goes to stderr (stdout is the protocol channel); the first line names the level in force.
"""
import argparse
import json
import logging
import os
import sys

try:                                                    # the mcp SDK 2.x
    from mcp.server.mcpserver import MCPServer as Server
    from mcp.server.mcpserver.exceptions import ToolError
except ImportError:                                     # the mcp SDK 1.x (FastMCP was renamed MCPServer in 2.0)
    from mcp.server.fastmcp import FastMCP as Server
    from mcp.server.fastmcp.exceptions import ToolError

import mo2_ctl

__version__ = mo2_ctl.__version__      # one number for the client and the server (mo2_ctl.py holds it)
log = logging.getLogger("mo2-mcp")

SETTINGS = {"instance": "", "timeout": 600.0}     # filled by main(); the tools read them at call time

INSTRUCTIONS = """Operate the user's running Mod Organizer 2 through the MO2 Agent Control plugin.
Reads (info, profiles, mods, plugins, executables, overwrite, backups) always work.
Writes (set_mods, set_plugins, select_profile, refresh, run) are refused by MO2 while the user is using it - its window
in front and keyboard or mouse input in the last few minutes. If a write is refused, tell the user what you want to
change and ask whether to go ahead; only after they agree, call it again with `confirm` set to a short note saying who
approved it (for example "the user, in chat"). Never fill in confirm on your own.
Names passed to set_mods / set_plugins must match exactly (case included) what mods / plugins return.
Every write that changes the profile backs up modlist.txt, plugins.txt and loadorder.txt first; the reply names the folder.
run starts a program through MO2's virtual file system and returns at once with its process id; it never waits."""

server = Server("MO2 Agent Control", instructions=INSTRUCTIONS)


# ---- one request to the plugin --------------------------------------------------------------------------------------------
def request(cmd, args=None, confirm=""):
    """Send one command through mo2_ctl's client and return the plugin's reply (a dict). A reply with ok:false becomes a
    ToolError whose text is the plugin's own, prefixed 'refused:' when the plugin refused it; no channel is an error too."""
    instance = mo2_ctl.find_instance(SETTINGS["instance"])
    if not instance:
        raise ToolError("no MO2 instance: start mo2-mcp with --instance <folder holding ModOrganizer.exe>, or set the "
                        "MO2_INSTANCE environment variable")
    ch, why = mo2_ctl.channel(instance)
    if not ch:
        log.info("%s: no channel (%s)", cmd, why)
        raise ToolError("MO2 is not reachable: %s" % why)
    req = {"token": ch["token"], "cmd": cmd, "args": args or {}}
    if confirm:
        req["confirm"] = confirm
    log.debug("-> %s %s%s", cmd, json.dumps(args or {}, ensure_ascii=False), " (confirm: %s)" % confirm if confirm else "")
    try:
        resp = mo2_ctl.send(ch, req, SETTINGS["timeout"])
    except OSError as exc:
        log.info("%s: nothing answered on 127.0.0.1:%s (%s)", cmd, ch.get("port"), exc)
        raise ToolError("MO2 is not reachable: nothing answered on 127.0.0.1:%s (%s) - the channel file is stale or MO2 "
                        "is closing" % (ch.get("port"), exc))
    if not isinstance(resp, dict):
        raise ToolError("MO2 sent an unreadable reply")
    if resp.get("ok"):
        log.debug("<- %s ok", cmd)
        return resp
    if resp.get("refused"):
        log.info("%s refused: %s", cmd, resp.get("error"))
        raise ToolError("refused: %s" % resp.get("error"))
    log.info("%s error: %s", cmd, resp.get("error"))
    raise ToolError("MO2 answered with an error: %s" % resp.get("error"))


# ---- reads ----------------------------------------------------------------------------------------------------------------
@server.tool()
def info() -> dict:
    """What MO2 is running: instance folder, current profile, game, plugin version and protocol, the commands it
    accepts, and whether MO2 is in use right now (in_use, in_use_why) - check this before a write if you want to know
    whether it will be refused."""
    return request("info")


@server.tool()
def profiles() -> dict:
    """The MO2 profiles (names) and which one is current."""
    return request("profiles")


@server.tool()
def mods(active_only: bool = False) -> dict:
    """The mods of the current profile in the left pane's order: name, active, separator. active_only leaves out the
    unticked ones."""
    return request("mods", {"active_only": bool(active_only)})


@server.tool()
def plugins() -> dict:
    """The plugins (esp, esm, esl) of the current profile in load order: name, active, origin (the mod that provides
    the file)."""
    return request("plugins")


@server.tool()
def executables() -> dict:
    """The executables MO2's Run list offers (title, binary); a title is what the run tool takes."""
    return request("executables")


@server.tool()
def overwrite(limit: int = 500) -> dict:
    """The files currently in MO2's Overwrite folder (paths relative to it), at most `limit`; truncated says whether
    there were more."""
    return request("overwrite", {"limit": int(limit)})


@server.tool()
def backups() -> dict:
    """The profile backups the plugin made before writes (newest first): name, path, files. To go back, close MO2 and
    copy the three files from a backup into profiles\\<profile>."""
    return request("backups")


# ---- writes: refused while MO2 is in use unless confirm names who approved ------------------------------------------------
@server.tool()
def set_mods(names: list[str], active: bool, confirm: str) -> dict:
    """Tick (active=true) or untick (active=false) mods in the current profile. names must match exactly what the mods
    tool returns; one unknown name fails the whole call before anything changes. confirm: who approved this while MO2
    is in use (ask the user first; "" when no one has, and the write then goes through only while MO2 is idle).
    The profile's list files are backed up first; the reply names the folder."""
    return request("set_mods", {"names": list(names), "active": bool(active)}, confirm)


@server.tool()
def set_plugins(names: list[str], active: bool, confirm: str) -> dict:
    """Tick or untick plugins (esp, esm, esl) in the current profile; plugins.txt is written at once. names must match
    exactly what the plugins tool returns. The game's own primary plugins cannot be changed. confirm: who approved
    this while MO2 is in use (ask the user first; "" when no one has). The profile's list files are backed up first."""
    return request("set_plugins", {"names": list(names), "active": bool(active)}, confirm)


@server.tool()
def select_profile(name: str, confirm: str) -> dict:
    """Switch MO2 to another profile (a name from the profiles tool), through MO2's own profile box. confirm: who
    approved this while MO2 is in use (ask the user first; "" when no one has). The profile being left is backed up."""
    return request("select_profile", {"name": name}, confirm)


@server.tool()
def refresh(save: bool, confirm: str) -> dict:
    """MO2's Refresh (re-read the mods and plugins from disk). save=true writes modlist.txt first. confirm: who approved
    this while MO2 is in use (ask the user first; "" when no one has)."""
    return request("refresh", {"save": bool(save)}, confirm)


@server.tool()
def run(confirm: str, executable: str = "", binary: str = "", args: list[str] = [], cwd: str = "",
        profile: str = "") -> dict:
    """Start a program through MO2's virtual file system, like pressing Run: either executable (a title from the
    executables tool) or binary (a path to an exe), optional args, cwd and profile. Replies at once with started and pid;
    it never waits for the program to close (poll the pid if you need to know). confirm: who approved this while MO2
    is in use (ask the user first; "" when no one has)."""
    if not executable and not binary:
        raise ToolError("run needs executable (a title from the executables tool) or binary (a path)")
    a: dict = {"args": list(args or [])}
    if executable:
        a["executable"] = executable
    if binary:
        a["binary"] = binary
    if cwd:
        a["cwd"] = cwd
    if profile:
        a["profile"] = profile
    return request("run", a, confirm)


# ---- start ----------------------------------------------------------------------------------------------------------------
def configure(argv):
    p = argparse.ArgumentParser(prog="mo2-mcp", description=__doc__.split("\n\n")[0],
                                formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    p.add_argument("--instance", default="", help="the MO2 instance folder (else MO2_INSTANCE, else the current folder)")
    p.add_argument("--timeout", type=float, default=600.0, help="seconds to wait for MO2's answer (default 600)")
    p.add_argument("--log-level", default=os.environ.get("MO2_MCP_LOG", "info"),
                   choices=["debug", "info", "warning", "error"], help="stderr log level (default info, or MO2_MCP_LOG)")
    p.add_argument("--version", action="version", version="mo2-mcp " + __version__)
    a = p.parse_args(argv)
    SETTINGS["instance"] = a.instance
    SETTINGS["timeout"] = a.timeout
    level = getattr(logging, a.log_level.upper())
    # force: the MCP SDK already put its own handler on the root logger when the server object was built above
    logging.basicConfig(stream=sys.stderr, level=level, format="%(asctime)s %(name)s %(levelname)s %(message)s", force=True)
    log.log(level, "mo2-mcp %s: log level %s (%s); instance %s; timeout %.0fs", __version__, a.log_level,
            "every request and reply is logged" if level <= logging.DEBUG else "refusals and errors only - "
            "--log-level debug or MO2_MCP_LOG=debug for every request", mo2_ctl.find_instance(a.instance) or "(none yet)",
            a.timeout)
    return a


def main(argv=None):
    """The `mo2-mcp` console command (pyproject.toml) and `python mo2_mcp.py` both end here: serve on stdio."""
    configure(sys.argv[1:] if argv is None else argv)
    server.run("stdio")


if __name__ == "__main__":
    main()
