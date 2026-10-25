r"""mo2-ctl lives one folder up, as mo2_ctl.py (an importable module since the MCP server arrived). This launcher keeps
the old path working for anything that still calls tools\mo2-ctl.py; it runs that file unchanged, with the same
arguments and exit codes. New scripts should call mo2_ctl.py (or the `mo2-ctl` command after `pip install
mo2-agent-control`) directly.
"""
import os
import runpy
import sys

CLIENT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "mo2_ctl.py"))

if __name__ == "__main__":
    if not os.path.isfile(CLIENT):
        print("mo2-ctl: %s is missing - this launcher belongs beside the mo2_ctl.py it runs" % CLIENT)
        sys.exit(2)
    sys.argv[0] = CLIENT
    runpy.run_path(CLIENT, run_name="__main__")
