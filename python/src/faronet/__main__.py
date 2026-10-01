"""Allow `python -m faronet` to use the same CLI as the installed command."""

from faronet.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
