#!/usr/bin/env python3
"""Poshansathi launcher.

Choose a front-end::

    python main.py            # interactive chooser
    python main.py cli        # terminal interface
    python main.py web        # browser interface (http://localhost:8000)
    python main.py seed       # load a demo profile with sample meals
"""

from __future__ import annotations

import sys


def run_cli() -> None:
    import cli
    cli.main()


def run_web() -> None:
    import webapp
    webapp.main()


def run_seed() -> None:
    from seed_demo import seed
    seed()


def interactive() -> None:
    print("\n  Poshansathi - how would you like to use it?\n")
    print("    1. Terminal interface (CLI)")
    print("    2. Browser interface (Web)")
    print("    3. Load demo data\n")
    choice = input("  Select [1]: ").strip() or "1"
    if choice == "2":
        run_web()
    elif choice == "3":
        run_seed()
    else:
        run_cli()


def main() -> None:
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command == "cli":
        run_cli()
    elif command == "web":
        sys.argv = [sys.argv[0], *sys.argv[2:]]  # let webapp parse its flags
        run_web()
    elif command in ("seed", "demo"):
        run_seed()
    elif command in ("-h", "--help", "help"):
        print(__doc__)
    else:
        interactive()


if __name__ == "__main__":
    main()