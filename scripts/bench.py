#!/usr/bin/env python3
import sys

from floatflac.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["bench", *sys.argv[1:]]))
