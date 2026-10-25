r"""make_release - build the GitHub Release zip and its notes for the version the repo carries, into out\.

  python tools\make_release.py [--out DIR] [--unpack DIR]

Writes (nothing is uploaded or tagged - publishing is a separate, deliberate step):
  out\MO2AgentControl-<version>.zip      plugins\ApocryphaAgentControl (no caches or runtime data), mo2_ctl.py,
                                         mo2_mcp.py, pyproject.toml, tools\, docs\, tests\, README.md, README.txt,
                                         CHANGELOG.md, LICENSE, NOTICE.md - the layout a user unzips and uses in place
  out\RELEASE-NOTES-<version>.md         the CHANGELOG's entry for that version, as the release's text
  --unpack DIR                           the same files unpacked into DIR (the test-build package IS the zip, unpacked)
(out\, not dist\: in this project a repo's dist\ folder means "what the mod ships", and the package gate checks it.
The wheel and sdist go there too: python -m build --outdir out)
The version is read from mo2_ctl.py (the one the version gate stamps); the zip is listed and read back afterwards so a
missing file fails here, not after posting. Entry names use forward slashes (a Windows zip tool's backslashes break
other unzippers). Exit 0 built, 1 something is missing or disagrees.
"""
import argparse
import os
import re
import shutil
import sys
import zipfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILES = ["mo2_ctl.py", "mo2_mcp.py", "pyproject.toml", "tools/mo2-ctl.py", "tools/mcp_call.py", "README.md", "README.txt",
         "CHANGELOG.md", "LICENSE", "NOTICE.md", "docs/PROTOCOL.md", "docs/MCP.md", "tests/test_mo2_ctl_and_mcp.py"]
PLUGIN = "plugins/ApocryphaAgentControl"
SKIP_DIRS = {"__pycache__", "data"}


def version():
    with open(os.path.join(REPO, "mo2_ctl.py"), encoding="utf-8") as f:
        m = re.search(r'(?m)^__version__\s*=\s*"(\d+\.\d+\.\d+)"', f.read())
    if not m:
        sys.exit("make_release: no __version__ in mo2_ctl.py")
    return m.group(1)


def changelog_entry(ver):
    with open(os.path.join(REPO, "CHANGELOG.md"), encoding="utf-8") as f:
        text = f.read()
    m = re.search(r"(?ms)^## %s\b.*?(?=^## |\Z)" % re.escape(ver), text)
    if not m:
        sys.exit("make_release: CHANGELOG.md has no '## %s' entry" % ver)
    return m.group(0).strip() + "\n"


def plugin_files():
    out = []
    for d, dirs, names in os.walk(os.path.join(REPO, PLUGIN)):
        dirs[:] = [x for x in dirs if x not in SKIP_DIRS]
        for n in names:
            if n.endswith(".pyc"):
                continue
            out.append(os.path.relpath(os.path.join(d, n), REPO).replace(os.sep, "/"))
    return sorted(out)


def main(argv):
    p = argparse.ArgumentParser(prog="make_release", description=__doc__.split("\n\n")[0])
    p.add_argument("--out", default=os.path.join(REPO, "out"), help="output folder (default out\\ in the repo)")
    p.add_argument("--unpack", help="also unpack the zip into this folder (the test-build package: it is the zip, unpacked); "
                                    "the folder is replaced")
    a = p.parse_args(argv)
    ver = version()
    for rel, want in (("plugins/ApocryphaAgentControl/__init__.py", '__version__ = "%s"' % ver),):
        with open(os.path.join(REPO, rel), encoding="utf-8") as f:
            if want not in f.read():
                sys.exit("make_release: %s does not carry %s - run the version gate's stamp" % (rel, ver))
    files = FILES + plugin_files()
    missing = [f for f in files if not os.path.isfile(os.path.join(REPO, f))]
    if missing:
        sys.exit("make_release: missing from the repo: %s" % ", ".join(missing))
    notes = changelog_entry(ver)
    os.makedirs(a.out, exist_ok=True)
    zpath = os.path.join(a.out, "MO2AgentControl-%s.zip" % ver)
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for f in files:
            z.write(os.path.join(REPO, f), f)       # forward slashes: f already is
    with zipfile.ZipFile(zpath) as z:
        bad = z.testzip()
        names = sorted(z.namelist())
    if bad or names != sorted(files):
        sys.exit("make_release: the zip does not read back as written (%s)" % (bad or "entry list differs"))
    npath = os.path.join(a.out, "RELEASE-NOTES-%s.md" % ver)
    with open(npath, "w", encoding="utf-8", newline="\n") as f:
        f.write(notes)
    print("built %s (%d files, %d bytes)" % (zpath, len(names), os.path.getsize(zpath)))
    for n in names:
        print("  " + n)
    print("notes %s" % npath)
    if a.unpack:
        if os.path.isdir(a.unpack):
            shutil.rmtree(a.unpack)
        os.makedirs(a.unpack)
        with zipfile.ZipFile(zpath) as z:
            z.extractall(a.unpack)
        got = sorted(os.path.relpath(os.path.join(d, n), a.unpack).replace(os.sep, "/")
                     for d, _dirs, ns in os.walk(a.unpack) for n in ns)
        if got != sorted(files):
            sys.exit("make_release: the unpacked folder does not hold the zip's files")
        print("unpacked into %s (%d files)" % (a.unpack, len(got)))
    print("to publish (a separate step, after the Nexus post): gh release create v%s \"%s\" --title \"MO2 Agent Control %s\" --notes-file \"%s\""
          % (ver, zpath, ver, npath))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
