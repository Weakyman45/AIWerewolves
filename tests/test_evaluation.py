import asyncio

from backend.evolution.evaluation import (
    render_evaluation_report,
    run_evolution_evaluation,
    summarize_evaluation,
)
from backend.evolution.version_control import VersionControl


PROMPTS = {
    "werewolf": "werewolf prompt",
    "seer": "seer prompt",
    "witch": "witch prompt",
    "hunter": "hunter prompt",
    "villager": "villager prompt",
}


def test_mock_evolution_evaluation_passes_for_better_candidate(tmp_path):
    strategy_dir = tmp_path / "strategies"
    version_control = VersionControl(strategy_dir=str(strategy_dir))
    version_control.create_version("v0.0.1", prompts=PROMPTS)
    version_control.create_version("v0.0.2", parent_version="v0.0.1", prompts=PROMPTS)

    evaluation = asyncio.run(
        run_evolution_evaluation(
            baseline_version="v0.0.1",
            candidate_version="v0.0.2",
            num_games=4,
            game_runner="mock",
            strategy_dir=str(strategy_dir),
            log_dir=str(tmp_path / "logs"),
            min_successful_games=4,
        )
    )
    report = render_evaluation_report(evaluation)

    assert evaluation["summary"]["conclusion"] == "PASSED"
    assert evaluation["summary"]["candidate_win_rate"] == 1.0
    assert evaluation["summary"]["baseline_win_rate"] == 0.0
    assert "**PASSED**" in report
    assert "Candidate: v0.0.2" in report


def test_evaluation_is_inconclusive_when_successful_games_are_too_low():
    summary = summarize_evaluation(
        {
            "total_games": 4,
            "successful_games": 2,
            "failed_games": 2,
            "a_win_rate": 0.0,
            "b_win_rate": 1.0,
            "better_version": "v0.0.2",
            "statistics": {"p_value": 1.0, "significant": False},
        },
        baseline_version="v0.0.1",
        candidate_version="v0.0.2",
        min_successful_games=4,
        improvement_threshold=0.0,
    )

    assert summary["conclusion"] == "INCONCLUSIVE"
    assert summary["failure_rate"] == 0.5
