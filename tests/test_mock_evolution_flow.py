import asyncio

from backend.evolution.controller import EvolutionController


def test_mock_evolution_flow_accepts_better_candidate(tmp_path):
    controller = EvolutionController(
        num_games_per_iteration=1,
        ab_games=4,
        win_rate_threshold=0.0,
        fallback_only=True,
        game_runner="mock",
        strategy_dir=str(tmp_path / "strategies"),
        log_dir=str(tmp_path / "logs"),
    )
    controller.initialize()

    result = asyncio.run(controller.start_evolution(max_iterations=1))

    iteration_result = result["history"][0]["result"]
    ab_result = iteration_result["ab_result"]

    assert result["success"] is True
    assert result["final_version"] == "v0.0.2"
    assert iteration_result["accepted"] is True
    assert iteration_result["old_version"] == "v0.0.1"
    assert iteration_result["new_version"] == "v0.0.2"
    assert ab_result["successful_games"] == 4
    assert ab_result["b_win_rate"] == 1.0
    assert controller.version_control.get_latest_pointer() == "v0.0.2"
