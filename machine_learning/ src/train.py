"""Run grouped model comparison or hyperparameter tuning after labels are verified."""
from __future__ import annotations

import argparse
from pathlib import Path

from .model_training import run


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]), help="machine_learning folder")
    parser.add_argument("--phase", choices=["compare", "tune"], default="compare")
    args = parser.parse_args()
    complete = run(args.root, args.phase)
    print("Workflow completed." if complete else "Workflow blocked safely; see reports and model metadata.")


if __name__ == "__main__":
    main()
