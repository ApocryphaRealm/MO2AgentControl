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
import difflib
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


def _quoted(names, limit=3):
    """'a', 'b', 'c' - the first few names, for a message."""
    return ", ".join("'%s'" % n for n in names[:limit])


class Dispatcher:
    """org: the adapter (see FakeOrganizer in the tests for the methods it needs; mods_path() is the instance's mods
    folder). presence(): (in_use, why). log(text): one line to the plugin's log. version: the plugin's version text,
    reported by info."""

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
                if cmd in ("set_mods", "set_plugins"):
                    # names are checked before a backup is made: a request that cannot be carried out changes nothing,
                    # so it should not leave an empty backup folder behind either
                    if not isinstance(args, dict):
                        raise ValueError("args must be a JSON object")
                    args = dict(args)
                    args["names"] = self._check_names(cmd, args)
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
        plugins = self.org.plugins()
        if not a.get("include_unlisted"):
            return {"plugins": plugins}
        listed = {p["name"].lower() for p in plugins}
        active = {m["name"]: m["active"] for m in self.org.mods()}
        out = [dict(p, in_profile=True, mod_active=active.get(p.get("origin"), True)) for p in plugins]
        extra = []
        for lower, providers in self._installed_plugins().items():
            if lower in listed:
                continue
            for name, mod, mod_active in providers:
                extra.append({"name": name, "active": False, "origin": mod, "in_profile": False,
                              "mod_active": mod_active})
        extra.sort(key=lambda p: (p["name"].lower(), str(p.get("origin")).lower()))
        return {"plugins": out + extra}

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

    def _known(self, cmd):
        """The names the profile has for cmd: the mods of the left pane, or the plugins in load order."""
        return [m["name"] for m in self.org.mods()] if cmd == "set_mods" else [p["name"] for p in self.org.plugins()]

    def _check_names(self, cmd, a):
        """The names of a set_mods / set_plugins request, spelled the way the profile spells them: an exact match first,
        then a case-insensitive one (MO2 runs on Windows, where a name's case is not part of its identity). The names
        the profile does not have become one error that says where each one is, if anywhere (_missing); nothing is
        changed in that case."""
        if not isinstance(a.get("active"), bool):
            raise ValueError("active must be true or false")
        names = a.get("names")
        if not isinstance(names, list) or not names or not all(isinstance(n, str) for n in names):
            raise ValueError("names must be a non-empty list of names")
        known = self._known(cmd)
        by_lower = {}
        for k in known:
            by_lower.setdefault(k.lower(), k)
        found, missing = [], []
        for n in names:
            if n in known:
                found.append(n)
            elif n.lower() in by_lower:
                found.append(by_lower[n.lower()])
            else:
                missing.append(n)
        if missing:
            raise ValueError(self._missing(cmd, missing, known))
        return found

    def _missing(self, cmd, missing, known):
        """One error for the names a request has and the profile does not: for a plugin, the mod folder that holds the
        file and whether that mod is ticked (a plugin of an unticked mod is not in the profile at all - the mod's files
        are not mounted), or the closest name the profile does have; for a mod, the closest mod name."""
        head = "not in this profile: "
        installed = self._installed_plugins() if cmd == "set_plugins" else {}
        parts, unticked = [], []
        for n in missing[:10]:
            providers = installed.get(n.lower()) or []
            if cmd == "set_plugins" and providers:
                ticked = [m for name, m, on in providers if on]
                if ticked:
                    parts.append("%s (the mod %s is ticked but MO2 has not listed this plugin yet - run refresh, then "
                                 "try again)" % (n, _quoted(ticked)))
                else:
                    mods = [m for name, m, on in providers]
                    unticked.extend(mods)
                    parts.append("%s (provided by the inactive mod %s)" % (n, _quoted(mods)))
                continue
            bits = []
            if cmd == "set_plugins":
                bits.append("no mod folder in this instance has a file of that name")
            close = difflib.get_close_matches(n, known, n=1, cutoff=0.7)
            if close:
                bits.append("closest in this profile: '%s'" % close[0])
            parts.append("%s (%s)" % (n, "; ".join(bits)) if bits else n)
        text = head + ", ".join(parts)
        if len(missing) > 10:
            text += ", and %d more" % (len(missing) - 10)
        if unticked:
            # said once, after the names: the same reason on six names is six times the noise
            text += ("; tick %s first - an unticked mod's files are not mounted, so its plugins are not in the profile"
                     % ("that mod" if len(set(unticked)) == 1 else "those mods"))
        return text + "; nothing was changed"

    def _installed_plugins(self):
        """{lower-case file name: [(real name, mod, the mod is ticked)]} for the plugin files at the root of every mod
        folder. A mod folder is a data root: a plugin nested deeper is not loaded by the game, and MO2 does not list it
        either. Read-only, about 40 ms for 1400 mods; read only when a name is missing from the profile, or for
        plugins with include_unlisted."""
        by_mod = {m["name"]: m["active"] for m in self.org.mods()}
        out = {}
        root = self.org.mods_path()
        try:
            mods = os.listdir(root)
        except OSError:
            return out
        for mod in mods:
            path = os.path.join(root, mod)
            if mod not in by_mod or not os.path.isdir(path):
                continue
            try:
                files = os.listdir(path)
            except OSError:
                continue
            for name in files:
                if name.lower().endswith((".esp", ".esm", ".esl")):
                    out.setdefault(name.lower(), []).append((name, mod, by_mod[mod]))
        return out

    def c_set_mods(self, a):
        names = self._check_names("set_mods", a)
        self.org.set_mods(names, a["active"])
        return {"set": names, "active": a["active"]}

    def c_set_plugins(self, a):
        names = self._check_names("set_plugins", a)
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
