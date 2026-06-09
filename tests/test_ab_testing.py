import asyncio

from backend.core.logger import GameLogger
from backend.core.models import Role, Team
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


def test_run_single_game_reports_timeout(tmp_path, monkeypatch):
    ab_testing = ABTesting.__new__(ABTesting)
    ab_testing.game_timeout = 0.01
    ab_testing.version_control = type(
        "FakeVersionControl",
        (),
        {"get_prompt": lambda self, version, role: None},
    )()

    async def slow_run(self):
        await asyncio.sleep(1)

    monkeypatch.setattr(
        "backend.evolution.ab_testing.GameLogger",
        lambda log_dir="./logs": GameLogger(log_dir=str(tmp_path)),
    )
    monkeypatch.setattr("backend.engine.game.WerewolfGame.run", slow_run)

    result = asyncio.run(
        ab_testing._run_single_game(
            "v0.0.1",
            "v0.0.2",
            ["Alice", "Bob", "Charlie", "David", "Eve", "Frank"],
        )
    )

    assert result["success"] is False
    assert result["winner"] is None
    assert result["error_type"] == "TimeoutError"


def test_run_single_game_uses_mock_runner(tmp_path):
    ab_testing = ABTesting(
        strategy_dir=str(tmp_path / "strategies"),
        game_runner="mock",
        log_dir=str(tmp_path / "logs"),
    )

    result = asyncio.run(
        ab_testing._run_single_game(
            "v0.0.1",
            "v0.0.2",
            ["Alice", "Bob", "Charlie", "David", "Eve", "Frank"],
        )
    )

    assert result["success"] is True
    assert result["winner"] in {"werewolves", "villagers"}
    assert result["runner"] == "mock"


def test_run_single_game_uses_live_fast_options(tmp_path, monkeypatch):
    captured = {}

    class FakeWerewolfGame:
        def __init__(self, player_names, logger, **kwargs):
            captured["player_names"] = player_names
            captured["logger"] = logger
            captured["kwargs"] = kwargs
            self.game_id = "fake-game"

        async def run(self):
            return Team.VILLAGERS

    ab_testing = ABTesting(
        strategy_dir=str(tmp_path / "strategies"),
        game_runner="live-fast",
        log_dir=str(tmp_path / "logs"),
    )
    ab_testing.version_control = type(
        "FakeVersionControl",
        (),
        {"get_prompt": lambda self, version, role: f"{version}:{role}"},
    )()
    monkeypatch.setattr("backend.engine.game.WerewolfGame", FakeWerewolfGame)

    result = asyncio.run(
        ab_testing._run_single_game(
            "v0.0.1",
            "v0.0.2",
            ["Alice", "Bob", "Charlie", "David", "Eve", "Frank"],
        )
    )

    assert result["success"] is True
    assert result["winner"] == "villagers"
    assert result["runner"] == "live-fast"
    assert captured["kwargs"]["skip_sheriff"] is True
    assert captured["kwargs"]["max_rounds"] == 1
    assert captured["kwargs"]["sleep_scale"] == 0.0
    assert captured["kwargs"]["skip_last_words"] is True
    assert captured["kwargs"]["parallel_decisions"] is False
    assert captured["kwargs"]["decision_delay"] == 2.0
    assert captured["kwargs"]["strategy_prompts"]["werewolf"] == "v0.0.1:werewolf"


def test_run_single_game_can_override_live_fast_decision_pacing(tmp_path, monkeypatch):
    captured = {}

    class FakeWerewolfGame:
        def __init__(self, player_names, logger, **kwargs):
            captured["kwargs"] = kwargs
            self.game_id = "fake-game"

        async def run(self):
            return Team.VILLAGERS

    ab_testing = ABTesting(
        strategy_dir=str(tmp_path / "strategies"),
        game_runner="live-fast",
        log_dir=str(tmp_path / "logs"),
        parallel_decisions=True,
        decision_delay=0.0,
    )
    ab_testing.version_control = type(
        "FakeVersionControl",
        (),
        {"get_prompt": lambda self, version, role: None},
    )()
    monkeypatch.setattr("backend.engine.game.WerewolfGame", FakeWerewolfGame)

    asyncio.run(
        ab_testing._run_single_game(
            "v0.0.1",
            "v0.0.2",
            ["Alice", "Bob", "Charlie", "David", "Eve", "Frank"],
        )
    )

    assert captured["kwargs"]["parallel_decisions"] is True
    assert captured["kwargs"]["decision_delay"] == 0.0


def test_run_single_game_marks_llm_fallback_as_failed(tmp_path, monkeypatch):
    class FallbackAgent:
        role = Role.SEER
        llm_failure_count = 2
        llm_failure_errors = ["RateLimitError: 429", "TimeoutError: timed out"]

    class FakeWerewolfGame:
        def __init__(self, player_names, logger, **kwargs):
            self.game_id = "fallback-game"
            self.players = {"player_1": FallbackAgent()}

        async def run(self):
            return Team.VILLAGERS

    ab_testing = ABTesting(
        strategy_dir=str(tmp_path / "strategies"),
        game_runner="live-fast",
        log_dir=str(tmp_path / "logs"),
    )
    ab_testing.version_control = type(
        "FakeVersionControl",
        (),
        {"get_prompt": lambda self, version, role: None},
    )()
    monkeypatch.setattr("backend.engine.game.WerewolfGame", FakeWerewolfGame)

    result = asyncio.run(
        ab_testing._run_single_game(
            "v0.0.1",
            "v0.0.2",
            ["Alice", "Bob", "Charlie", "David", "Eve", "Frank"],
        )
    )

    assert result["success"] is False
    assert result["winner"] is None
    assert result["observed_winner"] == "villagers"
    assert result["error_type"] == "LLMFallbackUsed"
    assert result["llm_failures"] == [
        {
            "player_id": "player_1",
            "role": "seer",
            "count": 2,
            "errors": ["RateLimitError: 429", "TimeoutError: timed out"],
        }
    ]


def test_statistical_significance_uses_exact_binomial_p_value():
    ab_testing = ABTesting.__new__(ABTesting)

    result = ab_testing.calculate_statistical_significance(
        {"a_wins": 0, "b_wins": 4}
    )

    assert result["p_value"] == 0.125
    assert result["significant"] is False
