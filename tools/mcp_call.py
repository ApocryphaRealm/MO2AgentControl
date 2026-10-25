r"""mcp_call - call one tool of the MO2 Agent Control MCP server from the command line, through a real stdio session.

Starts mo2_mcp.py exactly as Claude Desktop, Claude Code or Cursor would (a child process, JSON-RPC over stdin and
stdout), does initialize, calls the tool, prints the result and exits. For trying the server before adding it to a
client, and for tests that must drive the MCP path rather than mo2-ctl. Needs the mcp package (pip install mcp).

  mcp_call.py [--instance DIR] TOOL [key=value ...] [--json '{...}']
  A value is read as JSON when it parses (true, 5, ["a"], {...}), else as text - the same rule as mo2-ctl.
  --server <path> runs another server file (default: mo2_mcp.py one folder up); --list prints the tools.

  Examples
    mcp_call.py --instance "D:\MO2" info
    mcp_call.py --instance "D:\MO2" mods active_only=true
    mcp_call.py --instance "D:\MO2" set_mods names='["My Patch"]' active=false confirm=""
    mcp_call.py --instance "D:\MO2" set_mods names='["My Patch"]' active=true confirm="the user, in chat"

Exit codes, like mo2-ctl's: 0 the tool answered, 1 the tool returned an error, 3 the error is a refusal (MO2 in use,
wrong token), 4 MO2 is not reachable (no channel file, MO2 gone), 2 usage.
"""
import argparse
import asyncio
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SERVER = os.path.normpath(os.path.join(HERE, "..", "mo2_mcp.py"))


def value(text):
    try:
        return json.loads(text)
    except ValueError:
        return text


def attr(obj, *names):
    for n in names:                 # the SDK's models are camelCase in 1.x and snake_case in 2.x
        if hasattr(obj, n):
            return getattr(obj, n)
    return None


async def run(server, instance, tool, args, list_only):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    argv = [server] + (["--instance", instance] if instance else [])
    async with stdio_client(StdioServerParameters(command=sys.executable, args=argv)) as (read, write):
        async with ClientSession(read, write) as s:
            await s.initialize()
            if list_only:
                tools = (await s.list_tools()).tools
                return 0, {"tools": [{"name": t.name, "required": (attr(t, "inputSchema", "input_schema") or {}).get("required", [])}
                                     for t in tools]}
            r = await s.call_tool(tool, args)
            text = "".join(getattr(c, "text", "") for c in r.content)
            text = re.sub(r"^Error executing tool \w+: ", "", text)      # the SDK's wrapper; the rest is the server's text
            if attr(r, "isError", "is_error"):
                code = 3 if "refused" in text else 4 if "not reachable" in text or "no MO2 instance" in text else 1
                return code, {"ok": False, "error": text}
            sc = attr(r, "structuredContent", "structured_content")
            return 0, sc if isinstance(sc, dict) else json.loads(text)


def main(argv):
    p = argparse.ArgumentParser(prog="mcp_call", description=__doc__.split("\n\n")[0],
                                formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    p.add_argument("--instance", default="", help="the MO2 instance folder (else the server's own rules: MO2_INSTANCE, cwd)")
    p.add_argument("--server", default=SERVER, help="the server file to start (default mo2_mcp.py beside this folder)")
    p.add_argument("--json", help="the tool's arguments as one JSON object (instead of key=value)")
    p.add_argument("--list", action="store_true", help="list the server's tools and exit")
    p.add_argument("tool", nargs="?")
    p.add_argument("kv", nargs="*")
    a = p.parse_args(argv)
    if not a.list and not a.tool:
        print("mcp_call: give a tool name (or --list)")
        return 2
    args = {}
    if a.json:
        try:
            args = json.loads(a.json)
        except ValueError as e:
            print("mcp_call: --json is not JSON: %s" % e)
            return 2
    for kv in a.kv:
        if "=" not in kv:
            print("mcp_call: '%s' is not key=value" % kv)
            return 2
        k, v = kv.split("=", 1)
        args[k] = value(v)
    if not os.path.isfile(a.server):
        print("mcp_call: no server at %s" % a.server)
        return 2
    code, out = asyncio.run(run(a.server, a.instance, a.tool, args, a.list))
    print(json.dumps(out, indent=1, ensure_ascii=False))
    return code


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    sys.exit(main(sys.argv[1:]))
