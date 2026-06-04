#!/usr/bin/env python3
import argparse
import asyncio
import os
from datetime import datetime

from backend.evolution.evaluation import render_evaluation_report, run_evolution_evaluation
from backend.evolution.version_control import VersionControl


def parse_args():
    parser = argparse.ArgumentParser(description="Evaluate whether a candidate strategy really evolved.")
    parser.add_argument("--baseline", required=True, help="Baseline strategy version.")
    parser.add_argument("--candidate", default=None, help="Candidate strategy version. Defaults to latest pointer.")
    parser.add_argument("--games", type=int, default=20, help="Number of A/B games to run.")
    parser.add_argument("--min-successful-games", type=int, default=None, help="Minimum successful games required for a conclusive result.")
    parser.add_argument("--improvement-threshold", type=float, default=0.0, help="Minimum candidate win-rate improvement required.")
    parser.add_argument("--game-runner", choices=["live", "mock"], default="live", help="Game runner to use for A/B games.")
    parser.add_argument("--game-timeout", type=float, default=300, help="Timeout in seconds for each game.")
    parser.add_argument("--strategy-dir", default=None, help="Strategy directory.")
    parser.add_argument("--log-dir", default=None, help="Log directory.")
    parser.add_argument("--output", default=None, help="Markdown report output path.")
    return parser.parse_args()


async def main():
    args = parse_args()
    version_control = VersionControl(args.strategy_dir)
    candidate = args.candidate or version_control.get_latest_pointer() or version_control.get_latest_version()

    if not version_control.version_exists(args.baseline):
        raise SystemExit(f"Baseline version does not exist: {args.baseline}")
    if not candidate or not version_control.version_exists(candidate):
        raise SystemExit(f"Candidate version does not exist: {candidate}")
    if args.baseline == candidate:
        raise SystemExit("Baseline and candidate must be different versions.")

    evaluation = await run_evolution_evaluation(
        baseline_version=args.baseline,
        candidate_version=candidate,
        num_games=args.games,
        game_runner=args.game_runner,
        game_timeout=args.game_timeout,
        strategy_dir=args.strategy_dir,
        log_dir=args.log_dir,
        min_successful_games=args.min_successful_games,
        improvement_threshold=args.improvement_threshold,
    )
    report = render_evaluation_report(evaluation)

    output_path = args.output
    if not output_path:
        os.makedirs("reports", exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = os.path.join("reports", f"evolution_{args.baseline}_vs_{candidate}_{timestamp}.md")

    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)

    summary = evaluation["summary"]
    print(report)
    print(f"Report written to: {output_path}")
    if summary["conclusion"] == "FAILED":
        raise SystemExit(1)
    if summary["conclusion"] == "INCONCLUSIVE":
        raise SystemExit(2)


if __name__ == "__main__":
    asyncio.run(main())
