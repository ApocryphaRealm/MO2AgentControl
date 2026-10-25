r"""mo2-ctl - operate a running Mod Organizer 2 from the command line, through the MO2 Agent Control plugin.

The plugin, running inside that MO2, writes plugins\data\ApocryphaAgentControl\channel.json in the instance: the
loopback port and this session's token. mo2-ctl reads it and sends one JSON request (docs\PROTOCOL.md). Only 127.0.0.1
is ever contacted. Python 3.8 or newer, standard library only.

  mo2-ctl.py --instance DIR CMD [key=value ...] [--json '{...}'] [--confirm "<who approved>"]
    reads   info | profiles | mods [active_only=true] | plugins | overwrite [limit=N] | executables | backups
    writes  select_profile name=P | set_mods names=["A","B"] active=true | set_plugins names=[...] active=false
            refresh [save=true] | run executable="SKSE" [args=[...]] [profile=P]
            call plugin=<extension> action=<name> [args={...}]
  A value is read as JSON when it parses (true, 5, ["a"], {...}), else as text.
  --instance can be left out when the MO2_INSTANCE environment variable names the instance, or when the current folder
  is the instance (it holds ModOrganizer.exe).

  Examples
    mo2-ctl.py --instance "D:\MO2" mods active_only=true
    mo2-ctl.py --instance "D:\MO2" set_mods names='["My Patch"]' active=true
    mo2-ctl.py --instance "D:\MO2" set_plugins --json "{\"names\": [\"MyPatch.esp\"], \"active\": false}"
    mo2-ctl.py --instance "D:\MO2" run executable="SKSE"

  While you are using MO2 (its window in front, input in the last few minutes) the plugin refuses commands that change
  anything, unless --confirm gives a note saying who approved it; the plugin's settings can turn this check off. Every
  write that changes the profile backs up modlist.txt, plugins.txt and loadorder.txt first (the reply names the folder;
  `backups` lists them).

Exit codes: 0 done, 1 MO2 answered with an error, 2 usage, 3 refused (wrong token, or MO2 in use), 4 no running MO2 with
the plugin (no channel file, its MO2 is gone, or nothing listens).
"""
import argparse
import ctypes
import json
import os
import socket
import sys

__version__ = "1.0.0"    # issued by version-gate.ps1; never typed by hand
CHANNEL = os.path.join("plugins", "data", "ApocryphaAgentControl", "channel.json")


def value(text):
    try:
        return json.loads(text)
    except ValueError:
        return text


def pid_alive(pid):
    if not pid:
        return False
    if os.name != "nt":
        return True     # the channel's MO2 runs on Windows; elsewhere (Wine, a test) trust the socket
    h = ctypes.windll.kernel32.OpenProcess(0x1000, False, int(pid))     # PROCESS_QUERY_LIMITED_INFORMATION
    if not h:
        return False
    code = ctypes.c_ulong()
    ok = ctypes.windll.kernel32.GetExitCodeProcess(h, ctypes.byref(code))
    ctypes.windll.kernel32.CloseHandle(h)
    return bool(ok) and code.value == 259                                   # STILL_ACTIVE


def find_instance(given):
    if given:
        return given
    env = os.environ.get("MO2_INSTANCE", "").strip()
    if env:
        return env
    if os.path.isfile(os.path.join(os.getcwd(), "ModOrganizer.exe")):
        return os.getcwd()
    return ""


def channel(instance):
    path = os.path.join(instance, CHANNEL)
    try:
        with open(path, encoding="utf-8") as f:
            ch = json.load(f)
    except (OSError, ValueError):
        return None, "no channel file %s - is MO2 running with the MO2 Agent Control plugin installed?" % path
    if ch.get("host") != "127.0.0.1":
        return None, "the channel file names host %r - mo2-ctl only ever connects to 127.0.0.1" % ch.get("host")
    if not pid_alive(ch.get("pid")):
        return None, "the MO2 that wrote %s (pid %s) is not running" % (path, ch.get("pid"))
    return ch, ""


def send(ch, request, timeout):
    with socket.create_connection(("127.0.0.1", int(ch["port"])), timeout=timeout) as s:
        s.sendall((json.dumps(request) + "\n").encode("utf-8"))
        buf = b""
        while b"\n" not in buf:
            part = s.recv(65536)
            if not part:
                break
            buf += part
    return json.loads(buf.split(b"\n", 1)[0].decode("utf-8"))


def main(argv):
    p = argparse.ArgumentParser(prog="mo2-ctl", description=__doc__.split("\n\n")[0],
                                formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    p.add_argument("--instance", help="the MO2 instance folder (the one holding ModOrganizer.exe)")
    p.add_argument("--confirm", help="who approved a change while MO2 is in use (logged by the plugin)")
    p.add_argument("--owner-ok", dest="confirm", help=argparse.SUPPRESS)     # the flag's name before 1.0.0
    p.add_argument("--json", help="the args as one JSON object (instead of key=value)")
    p.add_argument("--timeout", type=float, default=600.0, help="seconds to wait for MO2's answer (default 600)")
    p.add_argument("--version", action="version", version="mo2-ctl " + __version__)
    p.add_argument("cmd")
    p.add_argument("kv", nargs="*")
    try:
        a = p.parse_args(argv)
    except SystemExit as e:
        return 2 if e.code else 0
    args = {}
    if a.json:
        try:
            args = json.loads(a.json)
        except ValueError as e:
            print("mo2-ctl: --json is not JSON: %s" % e)
            return 2
        if not isinstance(args, dict):
            print("mo2-ctl: --json must be a JSON object")
            return 2
    for kv in a.kv:
        if "=" not in kv:
            print("mo2-ctl: '%s' is not key=value" % kv)
            return 2
        k, v = kv.split("=", 1)
        args[k] = value(v)
    instance = find_instance(a.instance)
    if not instance:
        print("mo2-ctl: give --instance (or set MO2_INSTANCE, or run it from the instance folder)")
        return 2
    ch, why = channel(instance)
    if not ch:
        print("mo2-ctl: %s" % why)
        return 4
    req = {"token": ch["token"], "cmd": a.cmd, "args": args}
    if a.confirm:
        req["confirm"] = a.confirm
    try:
        resp = send(ch, req, a.timeout)
    except OSError as e:
        print("mo2-ctl: nothing answered on 127.0.0.1:%s (%s)" % (ch.get("port"), e))
        return 4
    print(json.dumps(resp, indent=1, ensure_ascii=False))
    if resp.get("ok"):
        return 0
    return 3 if resp.get("refused") else 1


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    sys.exit(main(sys.argv[1:]))
