import asyncio

from backend.core.logger import GameLogger
from backend.core.models import Team
from backend.evolution.analyzer import Analyzer
from backend.evolution.mock_game import MockGameRunner
from backend.evolution.parser import LogParser


def test_mock_game_writes_parseable_analyzable_log(tmp_path):
    logger = GameLogger(log_dir=str(tmp_path))
    game = MockGameRunner(
        ["Alice", "Bob", "Charlie", "David", "Eve", "Frank"],
        logger,
        seed_key="unit-test",
        werewolf_version="v0.0.2",
        other_version="v0.0.1",
    )

    winner = asyncio.run(game.run())
    parsed_game = LogParser(log_dir=str(tmp_path)).parse_game(game.game_id)
    analysis = Analyzer().analyze_game(parsed_game)

    assert winner in {Team.WEREWOLVES, Team.VILLAGERS}
    assert parsed_game["winner"] in {"werewolves", "villagers"}
    assert parsed_game["metrics"]["duration_rounds"] == 1
    assert "werewolf" in analysis
    assert "seer" in analysis
    assert parsed_game["raw_events"][0]["type"] == "game_start"
