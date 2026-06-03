from backend.core.logger import GameLogger
from backend.core.models import Role
from backend.engine.game import WerewolfGame
from backend.evolution.ab_testing import ABTesting
from backend.evolution.version_control import VersionControl


def test_game_injects_strategy_prompts_by_role(tmp_path, monkeypatch):
    monkeypatch.setattr(
        WerewolfGame,
        "_assign_roles",
        lambda self, count: [
            Role.WEREWOLF,
            Role.WEREWOLF,
            Role.SEER,
            Role.WITCH,
            Role.HUNTER,
            Role.VILLAGER,
        ],
    )

    game = WerewolfGame(
        ["Alice", "Bob", "Charlie", "David", "Eve", "Frank"],
        GameLogger(log_dir=str(tmp_path)),
        strategy_prompts={
            "werewolf": "custom werewolf prompt",
            "seer": "custom seer prompt",
        },
    )

    assert game.players["player_0"].get_effective_system_prompt() == "custom werewolf prompt"
    assert game.players["player_1"].get_effective_system_prompt() == "custom werewolf prompt"
    assert game.players["player_2"].get_effective_system_prompt() == "custom seer prompt"
    assert game.players["player_3"].get_effective_system_prompt() != "custom seer prompt"


def test_ab_testing_builds_prompts_from_competing_versions(tmp_path):
    version_control = VersionControl(strategy_dir=str(tmp_path))
    version_control.create_version(
        "v0.0.1",
        prompts={
            "werewolf": "old wolf",
            "seer": "old seer",
            "witch": "old witch",
            "hunter": "old hunter",
            "villager": "old villager",
        },
    )
    version_control.create_version(
        "v0.0.2",
        prompts={
            "werewolf": "new wolf",
            "seer": "new seer",
            "witch": "new witch",
            "hunter": "new hunter",
            "villager": "new villager",
        },
    )

    ab_testing = ABTesting(strategy_dir=str(tmp_path))
    prompts = ab_testing._build_strategy_prompts("v0.0.2", "v0.0.1")

    assert prompts == {
        "werewolf": "new wolf",
        "seer": "old seer",
        "witch": "old witch",
        "hunter": "old hunter",
        "villager": "old villager",
    }
