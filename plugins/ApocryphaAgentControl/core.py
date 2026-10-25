r"""MO2 Agent Control - the command core (no mobase, no Qt, so it can be tested without MO2 with a fake organizer).

The plugin (__init__.py) owns the loopback socket and MO2's API; this decides what a request may do:
  - every request carries the session token (compared in constant time); a wrong or missing one is refused;
  - only the commands below exist;
  - a WRITE is refused while MO2 is in use - its window in front and keyboard or mouse input within the last few
    minutes (the plugin's settings say whether the check is on, and for how many minutes) - unless the request carries
    `confirm`, a note saying who approved it; the refusal and the note are logged;
  - before a write that changes the profile, its modlist.txt / plugins.txt / loadorder.txt are copied to
    plugins\data\ApocryphaAgentControl\backups\<time>-<command>\.

Commands (args in a JSON object; docs\PROTOCOL.md is the full reference):
  READ   info | profiles | mods [active_only] | plugins | overwrite [limit] | executables | backups
  WRITE  select_profile name | set_mods names[] active | set_plugins names[] active | refresh [save]
         run (executable title | binary) [args] [cwd] [profile] | call plugin action [args] | mm action [args]
         (run starts the program through MO2's virtual file system and returns its pid at once; it never waits,
         because MO2's own wait blocks its window - poll the pid)

Replies are English whatever MO2's language is: tools read them, and a script's checks must not change with the
user's language.
"""
import hmac
import json
import os
import shutil
import time

PROTOCOL = 1
READS = {"info", "profiles", "mods", "plugins", "overwrite", "executables", "backups"}
WRITES = {"select_profile", "set_mods", "set_plugins", "refresh", "run", "call", "mm"}
BACKED_UP = {"select_profile", "set_mods", "set_plugins", "call", "mm"}
PROFILE_FILES = ("modlist.txt", "plugins.txt", "loadorder.txt")


class Refused(Exception):
    pass


def check_token(given, expected):
    return isinstance(given, str) and bool(expected) and hmac.compare_digest(given.encode(), expected.encode())


def backup_profile(profile_dir, backups_root, label, now=None):
    """Copies the profile's list files into backups_root\\<time>-<label>\\; returns that folder."""
    stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime(now or time.time()))
    dest = os.path.join(backups_root, "%s-%s" % (stamp, label))
    k = 2
    while os.path.exists(dest):
        dest = os.path.join(backups_root, "%s-%s-%d" % (stamp, label, k))
        k += 1
    os.makedirs(dest)
    for name in PROFILE_FILES:
        src = os.path.join(profile_dir, name)
        if os.path.isfile(src):
            shutil.copy2(src, dest)
    return dest


class Dispatcher:
    """org: the adapter (see FakeOrganizer in the tests for the methods it needs). presence(): (in_use, why).
    log(text): one line to the plugin's log. version: the plugin's version text, reported by info."""

    def __init__(self, org, token, backups_root, presence, log=lambda s: None, version=""):
        self.org, self.token, self.backups_root, self.presence, self.log = org, token, backups_root, presence, log
        self.version = version

    def handle(self, raw):
        """raw: one request line (bytes or str). Returns the response dict."""
        try:
            req = json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
            if not isinstance(req, dict):
                raise ValueError("a request is a JSON object")
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": "bad request: %s" % exc}
        if not check_token(req.get("token"), self.token):
            self.log("refused: wrong or missing token")
            return {"ok": False, "refused": True, "error": "wrong or missing token"}
        cmd, args = req.get("cmd"), req.get("args") or {}
        if cmd not in READS | WRITES:
            return {"ok": False, "error": "unknown command %r - %s" % (cmd, ", ".join(sorted(READS | WRITES)))}
        try:
            backup = None
            if cmd in WRITES:
                busy, why = self.presence()
                # "owner_ok" is the field's name before 1.0.0, still read so older clients keep working
                confirm = str(req.get("confirm") or req.get("owner_ok") or "").strip()
                if busy and not confirm:
                    self.log("refused %s: %s" % (cmd, why))
                    raise Refused("MO2 is in use (%s) - send confirm with a note saying who approved this, or turn off "
                                  "the plugin's in-use check" % why)
                self.log("%s %s%s" % (cmd, json.dumps(args, ensure_ascii=False), (" (confirm: %s)" % confirm) if confirm else ""))
                if cmd in BACKED_UP:
                    backup = backup_profile(self.org.profile_dir(), self.backups_root, cmd)
            out = getattr(self, "c_" + cmd)(args)
            if backup:
                out["backup"] = backup
            return dict(ok=True, **out)
        except Refused as exc:
            return {"ok": False, "refused": True, "error": str(exc)}
        except Exception as exc:  # noqa: BLE001
            self.log("error in %s: %r" % (cmd, exc))
            return {"ok": False, "error": "%s: %s" % (type(exc).__name__, exc)}

    # ---- reads
    def c_info(self, a):
        busy, why = self.presence()
        return {"instance": self.org.base_path(), "profile": self.org.profile_name(), "game": self.org.game_name(),
                "pid": os.getpid(), "version": self.version, "protocol": PROTOCOL,
                "reads": sorted(READS), "writes": sorted(WRITES), "in_use": busy, "in_use_why": why,
                "extensions": sorted(self.org.extensions())}

    def c_profiles(self, a):
        return {"profiles": self.org.profiles(), "current": self.org.profile_name()}

    def c_mods(self, a):
        mods = self.org.mods()
        if a.get("active_only"):
            mods = [m for m in mods if m["active"]]
        return {"mods": mods}

    def c_plugins(self, a):
        return {"plugins": self.org.plugins()}

    def c_overwrite(self, a):
        limit = int(a.get("limit", 500))
        root = self.org.overwrite_path()
        files = []
        for d, _dirs, names in os.walk(root):
            for n in names:
                files.append(os.path.relpath(os.path.join(d, n), root))
                if len(files) >= limit:
                    return {"overwrite": root, "files": files, "truncated": True}
        return {"overwrite": root, "files": files, "truncated": False}

    def c_executables(self, a):
        return {"executables": self.org.executables()}

    def c_backups(self, a):
        out = []
        if os.path.isdir(self.backups_root):
            for name in sorted(os.listdir(self.backups_root), reverse=True):
                d = os.path.join(self.backups_root, name)
                if os.path.isdir(d):
                    out.append({"name": name, "path": d, "files": sorted(os.listdir(d))})
        return {"backups": out, "root": self.backups_root}

    # ---- writes
    def c_select_profile(self, a):
        name = a.get("name")
        if name not in self.org.profiles():
            raise ValueError("no profile %r (profiles lists them)" % name)
        self.org.select_profile(name)
        return {"profile": self.org.profile_name()}

    def _names(self, a, known):
        names = a.get("names")
        if not isinstance(names, list) or not names or not all(isinstance(n, str) for n in names):
            raise ValueError("names must be a non-empty list of names")
        missing = [n for n in names if n not in known]
        if missing:
            raise ValueError("not in this profile: %s" % ", ".join(missing[:10]))
        if not isinstance(a.get("active"), bool):
            raise ValueError("active must be true or false")
        return names

    def c_set_mods(self, a):
        names = self._names(a, {m["name"] for m in self.org.mods()})
        self.org.set_mods(names, a["active"])
        return {"set": names, "active": a["active"]}

    def c_set_plugins(self, a):
        names = self._names(a, {p["name"] for p in self.org.plugins()})
        self.org.set_plugins(names, a["active"])
        return {"set": names, "active": a["active"]}

    def c_refresh(self, a):
        self.org.refresh(bool(a.get("save", False)))
        return {"refreshed": True}

    def c_run(self, a):
        target = a.get("executable") or a.get("binary")
        if not target:
            raise ValueError("run needs executable (a title from executables) or binary")
        if a.get("wait"):
            raise ValueError("run does not wait (MO2's own wait blocks its window) - poll the pid it returns")
        return self.org.run(target, a.get("args") or [], a.get("cwd") or "", a.get("profile") or "")

    def c_call(self, a):
        plugin = a.get("plugin")
        if not isinstance(plugin, str) or not plugin:
            raise ValueError("call needs plugin (a name from info's extensions)")
        return {"plugin": plugin, "result": self.org.call_plugin(plugin, a.get("action"), a.get("args") or {})}

    def c_mm(self, a):
        # MO2 Modlist Manager's own short form, kept from before `call` existed
        return {"mm": self.org.call_plugin("MO2ModlistManager", a.get("action"), a.get("args") or {})}
