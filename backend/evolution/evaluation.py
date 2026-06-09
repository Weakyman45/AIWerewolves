from datetime import datetime
from typing import Any, Dict, Optional

from backend.evolution.ab_testing import ABTesting


async def run_evolution_evaluation(
    baseline_version: str,
    candidate_version: str,
    num_games: int = 20,
    game_runner: str = "live",
    game_timeout: Optional[float] = None,
    strategy_dir: Optional[str] = None,
    log_dir: Optional[str] = None,
    min_successful_games: Optional[int] = None,
    improvement_threshold: float = 0.0,
    parallel_decisions: Optional[bool] = None,
    decision_delay: Optional[float] = None,
) -> Dict[str, Any]:
    ab_testing = ABTesting(
        strategy_dir=strategy_dir,
        game_timeout=game_timeout,
        game_runner=game_runner,
        log_dir=log_dir,
        parallel_decisions=parallel_decisions,
        decision_delay=decision_delay,
    )
    ab_result = await ab_testing.run_comparison(
        baseline_version,
        candidate_version,
        num_games=num_games,
    )
    ab_result["statistics"] = ab_testing.calculate_statistical_significance(ab_result)

    min_games = min_successful_games if min_successful_games is not None else num_games
    summary = summarize_evaluation(
        ab_result,
        baseline_version=baseline_version,
        candidate_version=candidate_version,
        min_successful_games=min_games,
        improvement_threshold=improvement_threshold,
    )

    return {
        "generated_at": datetime.now().isoformat(),
        "baseline_version": baseline_version,
        "candidate_version": candidate_version,
        "game_runner": game_runner,
        "num_games": num_games,
        "min_successful_games": min_games,
        "improvement_threshold": improvement_threshold,
        "summary": summary,
        "ab_result": ab_result,
    }


def summarize_evaluation(
    ab_result: Dict[str, Any],
    baseline_version: str,
    candidate_version: str,
    min_successful_games: int,
    improvement_threshold: float,
) -> Dict[str, Any]:
    successful_games = ab_result.get("successful_games", 0)
    total_games = ab_result.get("total_games", 0)
    baseline_win_rate = ab_result.get("a_win_rate", 0.0)
    candidate_win_rate = ab_result.get("b_win_rate", 0.0)
    improvement = candidate_win_rate - baseline_win_rate
    better_version = ab_result.get("better_version")

    if successful_games < min_successful_games:
        conclusion = "INCONCLUSIVE"
        reason = (
            f"Only {successful_games}/{min_successful_games} required games completed; "
            "sample size is too small."
        )
    elif better_version == candidate_version and improvement >= improvement_threshold:
        conclusion = "PASSED"
        reason = "Candidate beat the baseline under the configured threshold."
    else:
        conclusion = "FAILED"
        reason = "Candidate did not beat the baseline under the configured threshold."

    return {
        "conclusion": conclusion,
        "reason": reason,
        "baseline_win_rate": baseline_win_rate,
        "candidate_win_rate": candidate_win_rate,
        "improvement": improvement,
        "successful_games": successful_games,
        "failed_games": ab_result.get("failed_games", 0),
        "total_games": total_games,
        "failure_rate": ab_result.get("failed_games", 0) / total_games if total_games else 0.0,
        "better_version": better_version,
        "p_value": ab_result.get("statistics", {}).get("p_value", 1.0),
        "significant": ab_result.get("statistics", {}).get("significant", False),
    }


def render_evaluation_report(evaluation: Dict[str, Any]) -> str:
    summary = evaluation["summary"]
    ab_result = evaluation["ab_result"]
    stats = ab_result.get("statistics", {})
    game_rows = []
    for game in ab_result.get("game_results", []):
        status = "success" if game.get("success") else "failed"
        game_rows.append(
            "| {game_number} | {status} | {winner} | {werewolf_version} | {villager_version} | {error_type} |".format(
                game_number=game.get("game_number"),
                status=status,
                winner=game.get("winner") or "-",
                werewolf_version=game.get("werewolf_version") or "-",
                villager_version=game.get("villager_version") or "-",
                error_type=game.get("error_type") or "-",
            )
        )

    return "\n".join(
        [
            "# Evolution Evaluation Report",
            "",
            f"- Generated at: {evaluation['generated_at']}",
            f"- Baseline: {evaluation['baseline_version']}",
            f"- Candidate: {evaluation['candidate_version']}",
            f"- Game runner: {evaluation['game_runner']}",
            f"- Requested games: {evaluation['num_games']}",
            f"- Minimum successful games: {evaluation['min_successful_games']}",
            f"- Improvement threshold: {evaluation['improvement_threshold']:.2%}",
            "",
            "## Conclusion",
            "",
            f"**{summary['conclusion']}** - {summary['reason']}",
            "",
            "## Scorecard",
            "",
            f"- Baseline win rate: {summary['baseline_win_rate']:.2%}",
            f"- Candidate win rate: {summary['candidate_win_rate']:.2%}",
            f"- Improvement: {summary['improvement']:+.2%}",
            f"- Successful games: {summary['successful_games']}",
            f"- Failed games: {summary['failed_games']}",
            f"- Failure rate: {summary['failure_rate']:.2%}",
            f"- Better version: {summary['better_version'] or '-'}",
            f"- p-value: {summary['p_value']:.4f}",
            f"- Statistically significant: {summary['significant']}",
            "",
            "## A/B Raw Counts",
            "",
            f"- Baseline wins: {ab_result.get('a_wins', 0)}",
            f"- Candidate wins: {ab_result.get('b_wins', 0)}",
            f"- Confidence 95: {stats.get('confidence_95', {})}",
            "",
            "## Games",
            "",
            "| # | Status | Winner | Werewolf Version | Villager Version | Error Type |",
            "| - | ------ | ------ | ---------------- | ---------------- | ---------- |",
            *game_rows,
            "",
        ]
    )
