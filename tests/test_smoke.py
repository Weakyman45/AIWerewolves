import asyncio
import json
from collections import Counter

import pytest
from fastapi.testclient import TestClient

from backend.api import routes
from backend.agents.roles.hunter import HunterAgent
from backend.core.logger import GameLogger
from backend.core.models import AgentDecision, GamePhase, NightAction, NightActionRecord, Role, RoundRecord, Team
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


def test_evolution_status_includes_rubric_summary(monkeypatch):
    class FakeVersionControl:
        def list_versions(self):
            return ["v0.0.1", "v0.0.2"]

        def get_latest_pointer(self):
            return "v0.0.2"

        def get_metadata(self, version):
            if version == "v0.0.1":
                return {
                    "version": version,
                    "created_at": "2026-06-01T00:00:00",
                    "changes": ["initial"],
                    "status": "accepted",
                    "accepted": True,
                }
            return {
                "version": version,
                "parent": "v0.0.1",
                "created_at": "2026-06-02T00:00:00",
                "changes": ["身份边界修正"],
                "status": "accepted",
                "accepted": True,
                "analysis_summary": {
                    "total_games": 4,
                    "werewolf_win_rate": 0.75,
                    "villager_win_rate": 0.25,
                    "average_rounds": 2.0,
                    "quality_metrics": {
                        "counts": {
                            "nonseer_claim_repairs": 1,
                            "llm_fallbacks": 2,
                            "unauthorized_werewolf_fake_seer_blocks": 3,
                            "public_claim_consistency_repairs": 4,
                        }
                    },
                },
                "training_summary": {
                    "completed": 3,
                    "timed_out": 1,
                    "failed": 0,
                },
                "ab_result": {
                    "version_a": "v0.0.1",
                    "version_b": "v0.0.2",
                    "total_games": 4,
                    "successful_games": 4,
                    "a_wins": 1,
                    "b_wins": 3,
                    "a_win_rate": 0.25,
                    "b_win_rate": 0.75,
                    "skipped": False,
                },
            }

        def get_stats(self, _version):
            return {"metrics": {"total_games": 4}}

    monkeypatch.setattr(routes, "VersionControl", FakeVersionControl)
    routes.evolution_state.update({
        "status": "idle",
        "active_run": None,
        "latest_result": None,
        "history": [],
        "error": None,
    })

    status = routes._build_evolution_status()

    assert status["rubric_summary"]["loop_stage"] == "ab_validated"
    assert status["rubric_summary"]["current_promoted_by_ab"] is True
    assert status["rubric_summary"]["rollback_version_count"] == 1
    assert status["rubric_summary"]["training_health"] == {
        "completed": 3,
        "timed_out": 1,
        "failed": 0,
        "has_runtime_issues": True,
    }
    assert status["rubric_summary"]["bad_case_summary"]["unauthorized_werewolf_fake_seer_blocks"] == 3


def test_run_game_is_idempotent_while_task_is_running():
    routes.active_games.clear()

    class FakeGame:
        def __init__(self):
            self.run_calls = 0
            self.started = asyncio.Event()
            self.release = asyncio.Event()

        async def run(self):
            self.run_calls += 1
            self.started.set()
            await self.release.wait()
            return Team.VILLAGERS

    async def exercise():
        game = FakeGame()
        routes.active_games["game_1"] = {
            "game": game,
            "task": None,
            "status": "ready",
        }

        first = await routes.run_game("game_1")
        first_task = routes.active_games["game_1"]["task"]
        await game.started.wait()

        second = await routes.run_game("game_1")
        second_task = routes.active_games["game_1"]["task"]

        assert first["message"] == "Game started"
        assert second["message"] == "Game already running"
        assert first_task is second_task
        assert game.run_calls == 1

        game.release.set()
        await first_task

    asyncio.run(exercise())


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


def test_hunter_shot_resolves_before_winner_check(tmp_path):
    game = WerewolfGame(
        ["Hunter", "Wolf", "Villager"],
        GameLogger(log_dir=str(tmp_path)),
    )
    game.players["player_0"] = HunterAgent("player_0", "Hunter")
    game.player_states["player_0"].role = Role.HUNTER
    game.player_states["player_1"].role = Role.WEREWOLF
    game.player_states["player_2"].role = Role.VILLAGER

    async def shoot_wolf(_game_state):
        return AgentDecision(
            decision_type="shot",
            target_id="player_1",
            reasoning="confirmed wolf",
            raw_output="shoot wolf",
        )

    game.players["player_0"].make_shot = shoot_wolf
    game.death_queue.append(("player_0", "voted_out"))
    round_record = RoundRecord(round_number=1, phase=GamePhase.DAY)

    asyncio.run(game._process_deaths(round_record))

    assert round_record.deaths == ["player_0", "player_1"]
    assert game.player_states["player_1"].is_alive is False
    assert game.state.winner == Team.VILLAGERS


def test_first_night_deaths_are_logged_after_sheriff_election(tmp_path, monkeypatch):
    game = WerewolfGame(
        ["Alice", "Bob", "Charlie", "David", "Eve", "Frank"],
        GameLogger(log_dir=str(tmp_path)),
    )

    async def fake_night(round_record):
        game.death_queue.append(("player_1", "wolf_kill"))

    async def fake_sheriff(_round_record):
        game.logger.log_phase_change(game.game_id, game.state.current_round, "警长竞选")

    async def fake_day(_round_record):
        return None

    monkeypatch.setattr(game, "_run_night_phase", fake_night)
    monkeypatch.setattr(game, "_run_sheriff_election", fake_sheriff)
    monkeypatch.setattr(game, "_run_day_phase", fake_day)

    asyncio.run(game._run_round())

    log_path = tmp_path / f"game_{game.game_id}.jsonl"
    events = [
        json.loads(line)
        for line in log_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    death_index = next(index for index, event in enumerate(events) if event["type"] == "death")
    sheriff_index = next(index for index, event in enumerate(events) if event.get("phase") == "警长竞选")

    assert sheriff_index < death_index


def test_saved_wolf_kill_target_is_not_queued_for_death(tmp_path, monkeypatch):
    game = WerewolfGame(
        ["Alice", "Bob", "Charlie", "David", "Eve", "Frank"],
        GameLogger(log_dir=str(tmp_path)),
    )
    round_record = RoundRecord(round_number=1, phase=GamePhase.NIGHT)

    async def fake_wolf_kill(_round_record):
        return "player_1"

    async def fake_seer_check(_round_record):
        return None

    async def fake_witch_action(round_record_arg, kill_victim):
        round_record_arg.night_actions.append(NightActionRecord(
            actor_id="player_4",
            action=NightAction.SAVE,
            target_id=kill_victim,
            success=True,
        ))

    async def no_sleep(_seconds):
        return None

    monkeypatch.setattr(game, "_process_wolf_kill", fake_wolf_kill)
    monkeypatch.setattr(game, "_process_seer_check", fake_seer_check)
    monkeypatch.setattr(game, "_process_witch_action", fake_witch_action)
    monkeypatch.setattr(game, "_sleep", no_sleep)

    asyncio.run(game._run_night_phase(round_record))

    assert game.last_wolf_kill_target_id == "player_1"
    assert game.last_wolf_kill_was_saved is True
    assert game.death_queue == []


def test_nonseer_nonwolf_sheriff_candidates_use_seventy_percent_random_gate(tmp_path, monkeypatch):
    game = WerewolfGame(
        ["Alice", "Bob", "Charlie", "David", "Eve", "Frank"],
        GameLogger(log_dir=str(tmp_path)),
    )
    fixed_roles = {
        "player_0": Role.SEER,
        "player_1": Role.WEREWOLF,
        "player_2": Role.WEREWOLF,
        "player_3": Role.WITCH,
        "player_4": Role.HUNTER,
        "player_5": Role.VILLAGER,
    }
    for player_id, role in fixed_roles.items():
        game.player_states[player_id].role = role
        game.players[player_id].role = role

        async def stay(_game_state):
            return AgentDecision(decision_type="stay", reasoning="test", raw_output="stay")

        game.players[player_id].make_sheriff_election = stay

    game._assign_fake_seer_wolf()

    random_values = iter([0.69, 0.70, 0.10])
    captured = {}

    async def no_sleep(_seconds):
        return None

    async def capture_candidates(candidates, _round_record):
        captured["candidates"] = list(candidates)
        game.state.winner = Team.VILLAGERS

    monkeypatch.setattr("backend.engine.game.random.choice", lambda items: items[0])
    monkeypatch.setattr("backend.engine.game.random.random", lambda: next(random_values))
    monkeypatch.setattr(game, "_sleep", no_sleep)
    monkeypatch.setattr(game, "_run_sheriff_speeches", capture_candidates)

    asyncio.run(game._run_sheriff_election(RoundRecord(round_number=1, phase=GamePhase.SHERIFF_ELECTION)))

    assert captured["candidates"] == ["player_0", "player_1", "player_3", "player_5"]


def test_collect_decisions_can_run_serially(tmp_path):
    game = WerewolfGame(
        ["Alice", "Bob", "Charlie", "David", "Eve", "Frank"],
        GameLogger(log_dir=str(tmp_path)),
        parallel_decisions=False,
    )
    call_order = []

    async def decide(player_id):
        call_order.append(player_id)
        return player_id, AgentDecision(
            decision_type="vote",
            target_id=None,
            reasoning="serial",
            raw_output="serial",
        )

    player_ids = ["player_2", "player_0", "player_1"]
    results = asyncio.run(game._collect_decisions(player_ids, decide))

    assert call_order == player_ids
    assert [player_id for player_id, _decision in results] == player_ids


def test_wolf_visible_state_includes_saved_kill_target_only_for_wolves(tmp_path):
    game = WerewolfGame(
        ["Alice", "Bob", "Charlie", "David", "Eve", "Frank"],
        GameLogger(log_dir=str(tmp_path)),
    )
    game.player_states["player_0"].role = Role.WEREWOLF
    game.player_states["player_1"].role = Role.WEREWOLF
    game.player_states["player_2"].role = Role.VILLAGER
    game.last_wolf_kill_target_id = "player_2"
    game.last_wolf_kill_was_saved = True

    wolf_state = game._get_agent_visible_state("player_0")
    villager_state = game._get_agent_visible_state("player_2")

    assert wolf_state["wolf_last_kill_target_id"] == "player_2"
    assert wolf_state["wolf_last_kill_saved"] is True
    assert "wolf_last_kill_target_id" not in villager_state
    assert "wolf_last_kill_saved" not in villager_state


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
