"""Evaluate a candidate once on the reserved grouped test set."""
from __future__ import annotations

import argparse
from pathlib import Path

from .model_training import evaluate_final


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]), help="machine_learning folder")
    args = parser.parse_args()
    complete = evaluate_final(args.root)
    print("Evaluation complete; review reliability before release." if complete else "Evaluation blocked or already performed; see report.")


if __name__ == "__main__":
    main()
