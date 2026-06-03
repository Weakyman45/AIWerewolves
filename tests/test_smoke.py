import asyncio
import json
from collections import Counter

import pytest
from fastapi.testclient import TestClient

from backend.api import routes
from backend.core.logger import GameLogger
from backend.core.models import Role
from backend.engine.game import WerewolfGame
from backend.evolution.parser import LogParser
from backend.main import app


def test_six_player_role_assignment(tmp_path):
    game = WerewolfGame(
        ["Alice", "Bob", "Charlie", "David", "Eve", "Frank"],
        GameLogger(log_dir=str(tmp_path)),
    )

    role_counts = Counter(player.role for player in game.player_states.values())

    assert role_counts[Role.WEREWOLF] == 2
    assert role_counts[Role.SEER] == 1
    assert role_counts[Role.WITCH] == 1
    assert role_counts[Role.HUNTER] == 1
    assert role_counts[Role.VILLAGER] == 1


def test_api_can_create_game_and_read_status(tmp_path, monkeypatch):
    routes.active_games.clear()
    monkeypatch.setattr(routes, "GameLogger", lambda: GameLogger(log_dir=str(tmp_path)))
    client = TestClient(app)

    response = client.post(
        "/api/game/start",
        json={"player_names": ["Alice", "Bob", "Charlie", "David", "Eve", "Frank"]},
    )

    assert response.status_code == 200
    game_id = response.json()["game_id"]

    status_response = client.get(f"/api/game/{game_id}/status")

    assert status_response.status_code == 200
    status = status_response.json()
    assert status["status"] == "ready"
    assert status["current_phase"] == "night"
    assert len(status["players"]) == 6


def test_game_run_logs_errors(tmp_path, monkeypatch):
    game = WerewolfGame(
        ["Alice", "Bob", "Charlie", "David", "Eve", "Frank"],
        GameLogger(log_dir=str(tmp_path)),
    )

    async def fail_round():
        raise RuntimeError("simulated failure")

    monkeypatch.setattr(game, "_run_round", fail_round)

    with pytest.raises(RuntimeError, match="simulated failure"):
        asyncio.run(game.run())

    log_path = tmp_path / f"game_{game.game_id}.jsonl"
    events = [
        json.loads(line)
        for line in log_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    assert events[-1]["type"] == "game_error"
    assert events[-1]["error_type"] == "RuntimeError"
    assert events[-1]["error"] == "simulated failure"


def test_log_parser_extracts_complete_game(tmp_path):
    game_id = "sample-game"
    log_path = tmp_path / f"game_{game_id}.jsonl"
    events = [
        {
            "timestamp": "2026-06-03T10:00:00",
            "type": "game_start",
            "game_state": {
                "game_id": game_id,
                "players": {
                    "player_0": {"name": "Alice", "role": "werewolf"},
                    "player_1": {"name": "Bob", "role": "seer"},
                },
            },
        },
        {
            "timestamp": "2026-06-03T10:01:00",
            "type": "phase_change",
            "round_number": 1,
            "phase": "夜晚",
        },
        {
            "timestamp": "2026-06-03T10:02:00",
            "type": "game_end",
            "winner": "villagers",
        },
    ]

    log_path.write_text(
        "\n".join(json.dumps(event, ensure_ascii=False) for event in events),
        encoding="utf-8",
    )

    parsed_games = LogParser(log_dir=str(tmp_path)).parse_all_games()

    assert len(parsed_games) == 1
    parsed = parsed_games[0]
    assert parsed["game_id"] == game_id
    assert parsed["winner"] == "villagers"
    assert parsed["players"]["player_0"]["team"] == "werewolves"
    assert parsed["metrics"]["villager_win"] is True
