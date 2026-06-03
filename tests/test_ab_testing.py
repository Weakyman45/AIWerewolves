import asyncio

from backend.evolution.ab_testing import ABTesting


def test_run_comparison_excludes_failed_games_from_win_rates(monkeypatch):
    ab_testing = ABTesting.__new__(ABTesting)
    ab_testing.results = []

    results = [
        {"success": True, "game_id": "game-1", "winner": "werewolves", "error": None},
        {
            "success": False,
            "game_id": "game-2",
            "winner": None,
            "error": "simulated failure",
            "error_type": "RuntimeError",
        },
        {"success": True, "game_id": "game-3", "winner": "werewolves", "error": None},
    ]

    async def fake_run_single_game(werewolf_version, other_version, player_names):
        return results.pop(0)

    monkeypatch.setattr(ab_testing, "_run_single_game", fake_run_single_game)

    result = asyncio.run(
        ab_testing.run_comparison(
            "v0.0.1",
            "v0.0.2",
            num_games=3,
            player_names=["Alice", "Bob", "Charlie", "David", "Eve", "Frank"],
        )
    )

    assert result["total_games"] == 3
    assert result["successful_games"] == 2
    assert result["failed_games"] == 1
    assert result["a_wins"] == 2
    assert result["b_wins"] == 0
    assert result["a_win_rate"] == 1.0
    assert result["b_win_rate"] == 0.0
    assert result["better_version"] == "v0.0.1"
    assert result["game_results"][1]["success"] is False
    assert result["game_results"][1]["error"] == "simulated failure"


def test_run_comparison_records_side_assignments(monkeypatch):
    ab_testing = ABTesting.__new__(ABTesting)
    ab_testing.results = []

    async def fake_run_single_game(werewolf_version, other_version, player_names):
        return {"success": True, "game_id": werewolf_version, "winner": "werewolves", "error": None}

    monkeypatch.setattr(ab_testing, "_run_single_game", fake_run_single_game)

    result = asyncio.run(
        ab_testing.run_comparison(
            "version-a",
            "version-b",
            num_games=2,
            player_names=["Alice", "Bob", "Charlie", "David", "Eve", "Frank"],
        )
    )

    assert result["game_results"][0]["a_as_werewolves"] is True
    assert result["game_results"][0]["werewolf_version"] == "version-a"
    assert result["game_results"][0]["villager_version"] == "version-b"
    assert result["game_results"][1]["a_as_werewolves"] is False
    assert result["game_results"][1]["werewolf_version"] == "version-b"
    assert result["game_results"][1]["villager_version"] == "version-a"
