"""Command-line entry point for the verified-label training pipeline."""
from __future__ import annotations

import argparse
from pathlib import Path

from .model_training import run


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    args = parser.parse_args()
    run(Path(args.root))


if __name__ == "__main__":
    main()
