r"""mo2_ctl.py and mo2_mcp.py against a fake MO2: the plugin's own core (plugins\ApocryphaAgentControl\core.py) behind a
real loopback server, exactly as the plugin's socket drives it - no MO2, no Qt. Python 3.10+, the mcp package installed.

  python tests\test_mo2_ctl_and_mcp.py

  1  mo2_ctl.py end to end over 127.0.0.1 (and through the tools\mo2-ctl.py launcher): info; key=value and --json args;
     a refusal exits 3; --confirm reaches the core; a stale token exits 3; a channel file naming another host, a dead MO2
     pid and no channel file exit 4
  2  the MCP server in-process: the twelve tools and their schemas (every write tool requires `confirm`); reads work
     while MO2 is in use; a write is refused then, word for word, and goes through with confirm (logged by the core);
     the core's own errors come back as errors; run needs executable or binary; a missing channel and a missing
     instance are clear errors
  3  the MCP server over stdio, as a client starts it: initialize, list_tools, info, a refused write (isError)
"""
import asyncio
import importlib.util
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
import mo2_ctl  # noqa: E402
import mo2_mcp  # noqa: E402
ToolError = mo2_mcp.ToolError      # the SDK's class, whichever line (1.x or 2.x) is installed

spec = importlib.util.spec_from_file_location("agent_core", os.path.join(REPO, "plugins", "ApocryphaAgentControl", "core.py"))
core = importlib.util.module_from_spec(spec)
spec.loader.exec_module(core)

CTL = os.path.join(REPO, "mo2_ctl.py")
LAUNCHER = os.path.join(REPO, "tools", "mo2-ctl.py")
MCP = os.path.join(REPO, "mo2_mcp.py")
T = os.path.join(tempfile.gettempdir(), "mo2-agent-control-test")
shutil.rmtree(T, ignore_errors=True)
n = 0


def ok(cond, what, detail=""):
    global n
    n += 1
    print(("PASS" if cond else "FAIL"), n, what)
    if not cond:
        print(detail)
        sys.exit(1)


class FakeOrg:
    """What core.Dispatcher needs from MO2, with in-memory state (mirrors the plugin's Mo2 adapter in __init__.py)."""

    def __init__(self, root):
        self.root = root
        self.prof = "Default"
        self.mod_state = {"A": True, "B": False, "Sep_separator": False}
        self.plugin_state = {"A.esp": True, "B.esp": False}
        self.calls = []
        for p in ("Default", "Test"):
            os.makedirs(os.path.join(root, "profiles", p), exist_ok=True)
            for f in ("modlist.txt", "plugins.txt", "loadorder.txt"):
                open(os.path.join(root, "profiles", p, f), "w").write("%s of %s\n" % (f, p))
        os.makedirs(os.path.join(root, "overwrite", "SKSE"), exist_ok=True)
        open(os.path.join(root, "overwrite", "SKSE", "x.log"), "w").write("x")

    def base_path(self): return self.root
    def profile_name(self): return self.prof
    def profile_dir(self): return os.path.join(self.root, "profiles", self.prof)
    def game_name(self): return "Skyrim Special Edition"
    def profiles(self): return ["Default", "Test"]
    def mods(self): return [{"name": k, "active": v, "separator": k.endswith("_separator")} for k, v in self.mod_state.items()]
    def plugins(self): return [{"name": k, "active": v, "origin": "data"} for k, v in self.plugin_state.items()]
    def overwrite_path(self): return os.path.join(self.root, "overwrite")
    def executables(self): return [{"title": "SKSE", "binary": "skse64_loader.exe"}]
    def select_profile(self, name): self.prof = name

    def set_mods(self, names, active):
        self.calls.append(("set_mods", names, active))
        for x in names:
            self.mod_state[x] = active

    def set_plugins(self, names, active):
        self.calls.append(("set_plugins", names, active))
        for x in names:
            self.plugin_state[x] = active

    def refresh(self, save): self.calls.append(("refresh", save))

    def run(self, target, args, cwd, profile):
        self.calls.append(("run", target, args, profile))
        return {"started": target, "pid": 4242}

    def extensions(self): return []
    def call_plugin(self, plugin, action, args): return {"plugin": plugin, "action": action}


INST = os.path.join(T, "inst")
org = FakeOrg(INST)
busy = {"v": False}
logged = []
d = core.Dispatcher(org, "tok123", os.path.join(INST, "plugins", "data", "ApocryphaAgentControl", "backups"),
                    lambda: (busy["v"], "MO2 is in front and the last input was 0.5 min ago (Windows' idle clock)"),
                    logged.append, "1.0.0")

# the loopback server: one line in, one line out, the way the plugin's QTcpServer does it
srv = socket.socket()
srv.bind(("127.0.0.1", 0))
srv.listen(5)
PORT = srv.getsockname()[1]


def serve():
    while True:
        try:
            c, _ = srv.accept()
        except OSError:
            return
        buf = b""
        while b"\n" not in buf:
            part = c.recv(65536)
            if not part:
                break
            buf += part
        c.sendall((json.dumps(d.handle(buf.split(b"\n")[0])) + "\n").encode())
        c.close()


threading.Thread(target=serve, daemon=True).start()
CHDIR = os.path.join(INST, "plugins", "data", "ApocryphaAgentControl")
os.makedirs(CHDIR, exist_ok=True)
CH = os.path.join(CHDIR, "channel.json")


def write_channel(**kw):
    c = {"host": "127.0.0.1", "port": PORT, "token": "tok123", "pid": os.getpid(), "instance": INST, "version": "1.0.0",
         "protocol": 1}
    c.update(kw)
    json.dump(c, open(CH, "w"))


def ctl(*args, script=CTL):
    r = subprocess.run([sys.executable, script, "--instance", INST, *args], capture_output=True, text=True, encoding="utf-8")
    return r.returncode, r.stdout + r.stderr


# ---- 1  mo2_ctl.py end to end -----------------------------------------------------------------------------------------------
write_channel()
c, o = ctl("info")
ok(c == 0 and '"profile": "Default"' in o and '"protocol": 1' in o, "mo2_ctl info over 127.0.0.1", o)
c, o = ctl("info", script=LAUNCHER)
ok(c == 0 and '"profile": "Default"' in o, "tools\\mo2-ctl.py (the launcher) runs the same client", o)
c, o = ctl("set_mods", 'names=["A"]', "active=false")
ok(c == 0 and org.mod_state["A"] is False, "key=value args are read as JSON (a list, a boolean)", o)
c, o = ctl("--json", '{"names": ["A"], "active": true}', "set_mods")
ok(c == 0 and org.mod_state["A"] is True, "--json args", o)
busy["v"] = True
c, o = ctl("set_mods", 'names=["A"]', "active=false")
ok(c == 3 and org.mod_state["A"] is True and "MO2 is in use" in o, "a refusal exits 3, nothing written", o)
c, o = ctl("--confirm", "the user, in chat", "set_mods", 'names=["A"]', "active=false")
ok(c == 0 and org.mod_state["A"] is False and any("confirm: the user, in chat" in x for x in logged), "--confirm reaches the core and is logged", o)
busy["v"] = False
org.mod_state["A"] = True
c, o = ctl("set_mods", 'names=["A"]', "active=false", script=LAUNCHER)
ok(c == 0 and org.mod_state["A"] is False, "the launcher passes arguments and exit codes through", o)
org.mod_state["A"] = True
write_channel(token="stale")
c, o = ctl("info")
ok(c == 3 and "token" in o, "a stale token (an MO2 restarted since) is refused, exit 3", o)
write_channel(host="0.0.0.0")
c, o = ctl("info")
ok(c == 4 and "only ever connects to 127.0.0.1" in o, "a channel file naming another host is refused, exit 4", o)
write_channel(pid=999999)
c, o = ctl("info")
ok(c == 4 and "not running" in o, "a channel file whose MO2 is gone: exit 4", o)
os.remove(CH)
c, o = ctl("info")
ok(c == 4 and "no channel file" in o, "no channel file: exit 4", o)
write_channel()


# ---- 2  the MCP server in-process -------------------------------------------------------------------------------------------
def call(name, args=None):
    """Call a tool the way the MCP layer does; returns the reply dict, or the error's text prefixed 'ERROR '.
    SDK 1.x raises ToolError and returns content blocks or a dict; 2.x returns a CallToolResult (isError, content,
    structuredContent). The text the agent would read is the same either way."""
    try:
        r = asyncio.run(mo2_mcp.server.call_tool(name, args or {}))
    except ToolError as exc:
        # SDK 1.x wraps a tool's error as "Error executing tool <name>: <text>"
        return "ERROR " + re.sub(r"^Error executing tool \w+: ", "", str(exc))
    if isinstance(r, dict):
        return r
    if isinstance(r, tuple):        # (content blocks, structured) in some 1.x versions
        return r[1] if isinstance(r[1], dict) else json.loads(r[0][0].text)
    if hasattr(r, "content"):       # 2.x CallToolResult
        if attr(r, "isError", "is_error"):
            return "ERROR " + re.sub(r"^Error executing tool \w+: ", "", r.content[0].text)
        sc = attr(r, "structuredContent", "structured_content")
        return sc if isinstance(sc, dict) else json.loads(r.content[0].text)
    return json.loads(r[0].text)


def attr(obj, *names):
    """The SDK's models are camelCase in 1.x (inputSchema, serverInfo, isError) and snake_case in 2.x."""
    for n in names:
        if hasattr(obj, n):
            return getattr(obj, n)
    raise AttributeError(names)


def schema(tool):
    return attr(tool, "inputSchema", "input_schema")


tools = {t.name: t for t in asyncio.run(mo2_mcp.server.list_tools())}
READS = {"info", "profiles", "mods", "plugins", "executables", "overwrite", "backups"}
WRITES = {"set_mods", "set_plugins", "select_profile", "refresh", "run"}
ok(set(tools) == READS | WRITES, "the twelve tools: seven reads, five writes", sorted(tools))
ok(all("confirm" in (schema(tools[w]).get("required") or []) for w in WRITES), "every write tool requires `confirm`",
   {w: schema(tools[w]).get("required") for w in WRITES})
ok(not any("confirm" in schema(tools[r]).get("properties", {}) for r in READS), "no read tool takes confirm")
ok(all(tools[t].description for t in tools), "every tool has a description")

mo2_mcp.SETTINGS["instance"] = INST
r = call("info")
ok(isinstance(r, dict) and r["profile"] == "Default" and r["version"] == "1.0.0" and r["in_use"] is False,
   "info returns the plugin's reply as structured data", r)
r = call("mods", {"active_only": True})
ok(isinstance(r, dict) and [m["name"] for m in r["mods"]] == ["A"], "mods active_only", r)
r = call("plugins")
ok(isinstance(r, dict) and len(r["plugins"]) == 2, "plugins", r)
r = call("profiles")
ok(isinstance(r, dict) and r["profiles"] == ["Default", "Test"] and r["current"] == "Default", "profiles", r)
r = call("executables")
ok(isinstance(r, dict) and r["executables"][0]["title"] == "SKSE", "executables", r)
r = call("overwrite", {"limit": 10})
ok(isinstance(r, dict) and r["files"] == [os.path.join("SKSE", "x.log")] and r["truncated"] is False, "overwrite", r)

busy["v"] = True
r = call("mods")
ok(isinstance(r, dict) and len(r["mods"]) == 3, "reads work while MO2 is in use", r)
r = call("info")
ok(isinstance(r, dict) and r["in_use"] is True and "in front" in r["in_use_why"], "info reports in_use and why", r)
r = call("set_mods", {"names": ["B"], "active": True, "confirm": ""})
ok(isinstance(r, str) and r.startswith("ERROR refused: MO2 is in use") and "send confirm" in r and org.mod_state["B"] is False,
   "a write with empty confirm is refused while MO2 is in use - the plugin's words, nothing written", r)
ok(any("refused set_mods" in x for x in logged), "... and the core logged the refusal", logged[-3:])
r = call("set_plugins", {"names": ["B.esp"], "active": True, "confirm": ""})
ok(isinstance(r, str) and "refused" in r and org.plugin_state["B.esp"] is False, "set_plugins refused the same way", r)
r = call("select_profile", {"name": "Test", "confirm": ""})
ok(isinstance(r, str) and "refused" in r and org.prof == "Default", "select_profile refused the same way", r)
r = call("refresh", {"save": False, "confirm": ""})
ok(isinstance(r, str) and "refused" in r, "refresh refused the same way", r)
r = call("run", {"executable": "SKSE", "confirm": ""})
ok(isinstance(r, str) and "refused" in r and not any(c[0] == "run" for c in org.calls), "run refused the same way", r)
r = call("set_mods", {"names": ["B"], "active": True, "confirm": "the user, in chat"})
ok(isinstance(r, dict) and r["set"] == ["B"] and org.mod_state["B"] is True and os.path.isdir(r["backup"]),
   "with confirm the write goes through and names its backup folder", r)
ok(any("set_mods" in x and "confirm: the user, in chat" in x for x in logged), "... and the core logged the confirm note", logged[-3:])
busy["v"] = False

r = call("set_mods", {"names": ["Nope"], "active": True, "confirm": ""})
ok(isinstance(r, str) and r.startswith("ERROR MO2 answered with an error") and "not in this profile" in r,
   "the core's own error (an unknown name) comes back as an error, in its words", r)
r = call("set_plugins", {"names": ["B.esp"], "active": True, "confirm": ""})
bk = r.get("backup") if isinstance(r, dict) else ""
ok(isinstance(r, dict) and org.plugin_state["B.esp"] is True and os.path.isfile(os.path.join(bk, "plugins.txt")),
   "set_plugins while idle: no confirm needed, list files backed up", r)
r = call("select_profile", {"name": "Test", "confirm": ""})
ok(isinstance(r, dict) and r["profile"] == "Test" and org.prof == "Test", "select_profile while idle", r)
r = call("refresh", {"save": True, "confirm": ""})
ok(isinstance(r, dict) and r["refreshed"] is True and org.calls[-1] == ("refresh", True), "refresh save=true", r)
r = call("run", {"confirm": ""})
ok(isinstance(r, str) and "needs executable" in r and not any(c[0] == "run" for c in org.calls), "run without executable or binary is an error before anything is sent", r)
r = call("run", {"executable": "SKSE", "profile": "Test", "args": ["-x"], "confirm": ""})
ok(isinstance(r, dict) and r["pid"] == 4242 and org.calls[-1] == ("run", "SKSE", ["-x"], "Test"), "run starts through MO2 and returns the pid", r)
r = call("backups")
ok(isinstance(r, dict) and len(r["backups"]) >= 3 and all("plugins.txt" in b["files"] for b in r["backups"]), "backups lists the folders the writes made", r)

write_channel(pid=999999)
r = call("info")
ok(isinstance(r, str) and r.startswith("ERROR MO2 is not reachable") and "not running" in r, "a dead MO2 pid is a clear error", r)
os.remove(CH)
r = call("info")
ok(isinstance(r, str) and "MO2 is not reachable" in r and "is MO2 running with the MO2 Agent Control plugin installed" in r,
   "no channel file is a clear error", r)
write_channel()
mo2_mcp.SETTINGS["instance"] = ""
saved = os.environ.pop("MO2_INSTANCE", None)
cwd = os.getcwd()
os.chdir(T)      # no ModOrganizer.exe here
r = call("info")
os.chdir(cwd)
if saved is not None:
    os.environ["MO2_INSTANCE"] = saved
ok(isinstance(r, str) and r.startswith("ERROR no MO2 instance") and "--instance" in r and "MO2_INSTANCE" in r, "no instance at all is a clear error", r)
mo2_mcp.SETTINGS["instance"] = INST


# ---- 3  over stdio, as a client starts it --------------------------------------------------------------------------------------
async def over_stdio():
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    params = StdioServerParameters(command=sys.executable, args=[MCP, "--instance", INST, "--log-level", "debug"])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as s:
            init = await s.initialize()
            names = sorted(t.name for t in (await s.list_tools()).tools)
            info_r = await s.call_tool("info", {})
            busy["v"] = True
            refused = await s.call_tool("set_mods", {"names": ["A"], "active": False, "confirm": ""})
            busy["v"] = False
            return init, names, info_r, refused


init, names, info_r, refused = asyncio.run(over_stdio())
server_info = attr(init, "serverInfo", "server_info")
ok(server_info.name == "MO2 Agent Control", "stdio: initialize names the server", server_info)
ok(names == sorted(READS | WRITES), "stdio: list_tools shows the twelve tools", names)
text = json.loads(info_r.content[0].text)
ok(not attr(info_r, "isError", "is_error") and text["profile"] == "Test" and text["protocol"] == 1, "stdio: info round trip", info_r)
ok(attr(refused, "isError", "is_error") and "refused: MO2 is in use" in refused.content[0].text and org.mod_state["A"] is True,
   "stdio: a refused write is an error result carrying the plugin's words", refused)

srv.close()
shutil.rmtree(T, ignore_errors=True)
print("ALL PASS", n)
