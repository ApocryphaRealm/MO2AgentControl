r"""Live check on a SCRATCH Mod Organizer 2: the list and menu commands (ui_items, ui_item, ui_menus, ui_menu) against
MO2's own mod list, plugin list, Data tab and menus. No mouse and no keyboard: everything goes through mo2_ctl.py.

    python tools\live_lists_menus.py --instance "<scratch MO2 folder>" [--profile Default]

MO2 must be running on the instance with MO2 Agent Control 1.1.0 (the build with ui_items) installed. The check
compares what the lists show with what MO2's own API says (`mods`, `plugins`), unticks and re-ticks ONE mod through
the list's model, selects a row, opens a folder of the Data tab, lists the menus and opens one entry that shows a
window (closed again at once). It leaves the profile as it found it and says so (byte comparison of the three lists).
Exit 0 = every step passed. It stops at the first failed step.
"""
import argparse, hashlib, importlib.util, json, os, sys, time

FILES = ("modlist.txt", "plugins.txt", "loadorder.txt")
steps = []


class Stop(Exception):
    pass


def step(name, ok, detail=""):
    steps.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + name + " - " + json.dumps(detail, ensure_ascii=False, default=str)[:420], flush=True)
    if not ok:
        raise Stop(name)


def main(argv):
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--instance", required=True)
    p.add_argument("--profile", default="Default")
    a = p.parse_args(argv)
    low = os.path.normcase(os.path.abspath(a.instance))
    if "scratch" not in low and "_work" not in low:
        print("refused: this unticks a mod. Run it on a scratch instance (a path holding 'scratch' or '_work').")
        return 2
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    spec = importlib.util.spec_from_file_location("mo2_ctl", os.path.join(here, "mo2_ctl.py"))
    ctl = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ctl)

    def call(cmd, **args):
        ch, why = ctl.channel(a.instance)
        if not ch:
            raise SystemExit("no channel: " + why)
        return ctl.send(ch, {"token": ch["token"], "cmd": cmd, "args": args}, 120)

    prof = os.path.join(a.instance, "profiles", a.profile)

    def digest():
        return {f: hashlib.sha256(open(os.path.join(prof, f), "rb").read()).hexdigest()[:16] for f in FILES}

    try:
        call("refresh", save=True)          # MO2's own save first, so the files are what it holds
        time.sleep(2.5)
        pre = digest()
        info = call("info")
        step("the plugin has the list and menu commands", info.get("ok") and {"ui_items", "ui_menus"} <= set(info.get("reads", []))
             and {"ui_item", "ui_menu"} <= set(info.get("writes", [])), {"version": info.get("version"), "reads": info.get("reads")})
        t = call("ui_tree", kinds=["view"])
        views = {c["name"]: c for c in t.get("controls", []) if c.get("name")}
        step("ui_tree lists MO2's lists as views", t.get("ok") and "modList" in views and "espList" in views,
             {n: (v["class"], v["rows"], v["columns"]) for n, v in views.items()})

        mods = [m for m in call("mods")["mods"]]
        r = call("ui_items", name="modList", limit=1000)
        col0 = [x["cells"][0] for x in r.get("rows", [])]
        api = {m["name"]: m["active"] for m in mods}
        shown = {x["cells"][0]: x.get("checked") for x in r.get("rows", []) if x["cells"][0] in api}
        step("the mod list's rows are MO2's mods", r.get("ok") and len(shown) >= max(1, len([m for m in mods if not m["separator"]]) // 2),
             {"rows": r.get("total"), "columns": [c["title"] for c in r.get("columns", [])], "first": col0[:6], "api_mods": len(mods)})
        can_tick = {x["cells"][0] for x in r.get("rows", []) if x.get("checkable", True)}
        ticked = {n: v for n, v in shown.items() if isinstance(v, bool)}
        step("each row's tick is the mod's enabled state", bool(ticked) and all(api[n] == v for n, v in ticked.items()),
             {n: (v, api[n]) for n, v in list(ticked.items())[:6]})

        victim = next((n for n, v in ticked.items() if v and col0.count(n) == 1 and n in can_tick), None)
        step("an enabled mod to untick was found", bool(victim), victim)
        r = call("ui_item", name="modList", match=victim, action="uncheck")
        step("untick it through the list's model", r.get("ok") and r.get("applied") is True and r["row"].get("checked") is False
             and bool(r.get("backup")), {k: r.get(k) for k in ("ok", "applied", "row", "returned", "error", "backup")})
        time.sleep(1.0)
        now = {m["name"]: m["active"] for m in call("mods")["mods"]}
        step("MO2 itself now holds the mod as disabled", now.get(victim) is False, {victim: now.get(victim)})
        r = call("ui_item", name="modList", match=victim, action="check")
        time.sleep(1.0)
        now = {m["name"]: m["active"] for m in call("mods")["mods"]}
        step("tick it again: enabled in MO2", r.get("ok") and r.get("applied") is True and now.get(victim) is True,
             {"applied": r.get("applied"), victim: now.get(victim), "error": r.get("error")})

        r = call("ui_item", name="modList", match=victim, action="select")
        back = call("ui_items", name="modList", find=victim)
        step("select a row: the list shows it selected", r.get("ok") and r.get("applied") is True
             and any(x.get("selected") for x in back.get("rows", []) if x["cells"][0] == victim), r.get("row"))
        r = call("ui_item", name="modList", match="no such mod in this list", action="select")
        step("a row that is not there is an error, not a guess", not r.get("ok") and "no row has" in str(r.get("error")), r.get("error"))

        plugs = call("plugins")["plugins"]
        r = call("ui_items", name="espList", limit=1000)
        names = [x["cells"][0] for x in r.get("rows", [])]
        api_p = {p_["name"]: p_["active"] for p_ in plugs}
        both = [n for n in names if n in api_p]
        step("the plugin list's rows are MO2's plugins", r.get("ok") and len(both) >= max(1, len(plugs) // 2),
             {"rows": r.get("total"), "first": names[:5], "api_plugins": len(plugs)})
        fixed = [x["cells"][0] for x in r.get("rows", []) if x.get("checkable") is False]
        step("the game's own masters say their box cannot be ticked", any(n.lower() == "skyrim.esm" for n in fixed), fixed[:6])
        r = call("ui_item", name="espList", match=fixed[0], action="uncheck")
        step("... and ticking one is refused", not r.get("ok") and "no box to tick" in str(r.get("error")), r.get("error"))

        tabs = next((c for c in call("ui_tree", kinds=["tabs"]).get("controls", []) if "Data" in (c.get("items") or [])), None)
        step("the right pane's tab bar is there", bool(tabs), tabs and tabs.get("items"))
        was_tab = tabs["value"]
        r = call("ui_set", kind="tabs", name=tabs["name"], value="Data") if tabs.get("name") else {"ok": False}
        step("switch to the Data tab", r.get("ok") and r.get("applied") is True, {k: r.get(k) for k in ("ok", "applied", "value", "error")})
        time.sleep(1.5)
        t = call("ui_tree", kinds=["view"])
        data_view = next((c for c in t.get("controls", []) if c.get("tree") and c.get("name") not in ("modList", "espList")
                          and c.get("rows")), None)
        step("the Data tab's tree is listed", bool(data_view), [(c["name"], c["class"], c["rows"]) for c in t.get("controls", [])])
        r = call("ui_items", name=data_view["name"], limit=40)
        folder = next((x for x in r.get("rows", []) if x.get("children")), None)
        step("its rows are the virtual Data folder", r.get("ok") and r.get("total", 0) > 0, {"total": r.get("total"),
             "first": [x["cells"][0] for x in r.get("rows", [])[:6]]})
        if folder:
            r = call("ui_items", name=data_view["name"], parent=[folder["row"]], limit=10)
            step("the rows under a folder are read (loaded on demand)", r.get("ok") and r.get("total", 0) > 0,
                 {"folder": folder["cells"][0], "total": r.get("total"), "first": [x["cells"][0] for x in r.get("rows", [])[:4]]})
            r = call("ui_item", name=data_view["name"], row=folder["row"], action="expand")
            step("open that folder in the tree", r.get("ok") and r.get("applied") is True, r.get("row"))
            r = call("ui_item", name=data_view["name"], row=folder["row"], action="collapse")
            step("close it again", r.get("ok") and r.get("applied") is True, r.get("row"))
        r = call("ui_set", kind="tabs", name=tabs["name"], value=was_tab)
        step("back to the tab it was on", r.get("ok") and r.get("value") == was_tab, r.get("value"))

        m = call("ui_menus")
        paths = [e["path"] for e in m.get("entries", [])]
        step("ui_menus lists the menu bar and tool bar entries", m.get("ok") and len(paths) >= 5,
             {"total": m.get("total"), "sample": paths[:14]})
        mm = next((e for e in m.get("entries", []) if "Modlist Manager" in e["path"] and not e.get("menu") and e.get("enabled")), None)
        if mm:
            r = call("ui_menu", path=mm["path"])
            step("choose an entry that opens a window: the reply describes it", r.get("ok") and r.get("returned") is False
                 and (r.get("modal") or {}).get("title") == "MO2 Modlist Manager", {"path": mm["path"], "modal": (r.get("modal") or {}).get("title")})
            r = call("ui_menus")
            step("with the window open, only its own (no) menus are listed", r.get("ok") and r.get("total") == 0,
                 {"entries_listed": r.get("total")})
            r = call("ui_menu", path=mm["path"])
            step("... and choosing one is refused", not r.get("ok") and "modal dialog is open" in str(r.get("error")), r.get("error"))
            r = call("ui_click", text="Close")
            step("close that window", r.get("ok") and r.get("returned") is True and r.get("modal") is None, {k: r.get(k) for k in ("ok", "returned")})
        else:
            step("an entry to open (Modlist Manager) was found in the menus", False, paths[:30])
        r = call("ui_menu", path="No > Such > Entry")
        step("an unknown menu entry is an error", not r.get("ok") and "no menu entry" in str(r.get("error")), r.get("error"))

        call("refresh", save=True)
        time.sleep(2.5)
        step("the profile's three list files are byte-identical to the start", digest() == pre, {"before": pre, "after": digest()})
        t = call("ui_tree")
        step("nothing modal is left open", t.get("ok") and t.get("modal") is None, t.get("modal"))
    except Stop:
        pass
    ok = bool(steps) and all(steps)
    print(("PASS" if ok else "FAIL") + f": {sum(steps)}/{len(steps)} steps")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
