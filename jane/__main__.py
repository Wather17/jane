"""Entrypoint for `python3 -m jane`."""

import sys

from jane.cli import main

if __name__ == "__main__":
    sys.exit(main())
