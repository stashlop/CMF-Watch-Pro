"""Omnitrix companion prototype for the CMF Watch Pro 1.

    python -m companion dryrun                 # build the demo plan and show the packets (sends nothing)
    python -m companion select xlr8            # dry-run: announce an alien
    python -m companion transform xlr8         # dry-run: transformation feedback
    python -m companion status                 # is K1 present? is live sending possible?

Live sending is intentionally DISABLED in this prototype: the authenticated handshake is not implemented
yet, and nothing should be sent to the watch until compatibility and a recovery path are confirmed.
"""

from __future__ import annotations

import argparse
import asyncio

from omnitrix.aliens import ALIENS, BY_KEY

from companion import auth, bridge, client


def _alien(key: str):
    if key not in BY_KEY:
        raise SystemExit(f"unknown alien '{key}'. Options: {', '.join(a.key for a in ALIENS)}")
    return BY_KEY[key]


def cmd_dryrun(args) -> int:
    for line in client.dry_run(bridge.demo_plan()):
        print(line)
    print("\nNothing was sent. This is a prototype; live sending is disabled (see companion/README.md).")
    return 0


def cmd_select(args) -> int:
    for line in client.dry_run(bridge.select_alien(_alien(args.alien))):
        print(line)
    return 0


def cmd_transform(args) -> int:
    a = _alien(args.alien)
    plan = bridge.transform(a, face_index=ALIENS.index(a) + 1)
    for line in client.dry_run(plan):
        print(line)
    return 0


def cmd_status(args) -> int:
    k1 = auth.load_k1()
    print(f"K1 loaded:            {'yes' if k1 else 'no (set $CMF_K1 or data/companion/k1.key)'}")
    print(f"allowed commands:     {', '.join(sorted(__import__('companion.commands', fromlist=['ALLOWED']).ALLOWED))}")
    print("live sending:         DISABLED in this prototype (handshake not implemented; verify first)")
    print("aliens:               " + ", ".join(a.key for a in ALIENS))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m companion", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("dryrun")
    s = sub.add_parser("select")
    s.add_argument("alien")
    t = sub.add_parser("transform")
    t.add_argument("alien")
    sub.add_parser("status")
    args = ap.parse_args(argv)
    return {"dryrun": cmd_dryrun, "select": cmd_select, "transform": cmd_transform, "status": cmd_status}[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
