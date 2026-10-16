"""PyInstaller entry point for the AIMES console application."""
from aimes_cli.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
