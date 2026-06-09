import asyncio

from backend.agents.roles.werewolf import WerewolfAgent
from backend.evolution.controller import EvolutionController
from backend.evolution.version_control import VersionControl


class FakeAdapter:
    def optimize_prompt(self, original_prompt, role, analysis):
        return {
            "optimized": f"{original_prompt}\noptimized for {role}",
            "reasoning": f"{role} reasoning",
            "key_changes": [f"{role} change"],
        }


def test_initial_and_runtime_werewolf_prompts_share_identity_boundary():
    controller_prompt = EvolutionController.__new__(EvolutionController)._get_initial_prompts()["werewolf"]
    runtime_prompt = WerewolfAgent("player_0", "Alice").get_system_prompt()

    for prompt in [controller_prompt, runtime_prompt]:
        assert "只有被游戏引擎指定为本局唯一悍跳狼时，才允许悍跳预言家" in prompt
        assert "绝对禁止自称预言家、女巫或猎人" in prompt
        assert "可以适当跳预言家或其他神职来搅局" not in prompt


def test_optimize_strategy_stores_role_metadata(tmp_path):
    version_control = VersionControl(strategy_dir=str(tmp_path))
    version_control.create_version(
        "v0.0.1",
        prompts={
            "werewolf": "werewolf prompt",
            "seer": "seer prompt",
            "witch": "witch prompt",
            "hunter": "hunter prompt",
            "villager": "villager prompt",
        },
        changes=["initial"],
    )

    controller = EvolutionController.__new__(EvolutionController)
    controller.current_version = "v0.0.1"
    controller.version_control = version_control
    controller.adapter = FakeAdapter()

    new_version = asyncio.run(
        controller._optimize_strategy(
            {
                "aggregate": {
                    "total_games": 5,
                    "werewolf_win_rate": 0.2,
                    "villager_win_rate": 0.8,
                    "average_rounds": 2.0,
                    "role_analysis": {
                        "werewolf_hiding_ability": {
                            "average_score": 0.1,
                            "sample_size": 10,
                        }
                    },
                    "common_mistakes": {"counts": {}, "total": 0},
                },
                "suggestions": [
                    {
                        "suggestion": "global suggestion",
                    }
                ],
                "training_summary": {
                    "requested": 3,
                    "total_attempted": 3,
                    "completed": 1,
                    "timed_out": 1,
                    "failed": 1,
                    "failed_by_type": {"TimeoutError": 1, "RuntimeError": 1},
                },
            }
        )
    )

    metadata = version_control.get_metadata(new_version)

    assert new_version == "v0.0.2"
    assert metadata["analysis_summary"]["total_games"] == 5
    assert metadata["training_summary"]["completed"] == 1
    assert metadata["training_summary"]["timed_out"] == 1
    assert metadata["training_summary"]["failed_by_type"]["RuntimeError"] == 1
    assert metadata["analysis_summary"]["role_analysis"]["werewolf_hiding_ability"]["average_score"] == 0.1
    assert metadata["role_optimizations"]["werewolf"] == {
        "reasoning": "werewolf reasoning",
        "key_changes": ["werewolf change"],
    }
    assert "global suggestion" in metadata["changes"]
    assert "werewolf: werewolf change" in metadata["changes"]
    assert version_control.get_prompt(new_version, "seer").endswith("optimized for seer")


def test_controller_dry_run_skips_training_and_ab(tmp_path):
    version_control = VersionControl(strategy_dir=str(tmp_path))
    version_control.create_version(
        "v0.0.1",
        prompts={
            "werewolf": "werewolf prompt",
            "seer": "seer prompt",
            "witch": "witch prompt",
            "hunter": "hunter prompt",
            "villager": "villager prompt",
        },
    )

    controller = EvolutionController(
        initial_version="v0.0.1",
        strategy_dir=str(tmp_path),
        log_dir=str(tmp_path / "logs"),
        dry_run=True,
    )
    controller.adapter = FakeAdapter()

    result = asyncio.run(controller._run_evolution_iteration(1))

    assert result["new_version"] == "v0.0.2"
    assert result["accepted"] is False
    assert result["ab_result"]["skipped"] is True
    assert result["ab_result"]["reason"] == "dry-run"
    assert result["analysis"]["game_count"] == 0
    assert controller.version_control.get_latest_pointer() == "v0.0.1"


def test_controller_passes_fallback_only_to_adapter(tmp_path):
    controller = EvolutionController(
        initial_version="v0.0.1",
        strategy_dir=str(tmp_path),
        log_dir=str(tmp_path / "logs"),
        dry_run=True,
        fallback_only=True,
    )

    assert controller.fallback_only is True
    assert controller.adapter.fallback_only is True
    assert controller.adapter.llm is None


def test_controller_skip_ab_creates_unaccepted_candidate(tmp_path):
    version_control = VersionControl(strategy_dir=str(tmp_path))
    version_control.create_version(
        "v0.0.1",
        prompts={
            "werewolf": "werewolf prompt",
            "seer": "seer prompt",
            "witch": "witch prompt",
            "hunter": "hunter prompt",
            "villager": "villager prompt",
        },
    )

    controller = EvolutionController(
        initial_version="v0.0.1",
        num_games_per_iteration=0,
        strategy_dir=str(tmp_path),
        log_dir=str(tmp_path / "logs"),
        skip_ab=True,
    )
    controller.adapter = FakeAdapter()

    result = asyncio.run(controller._run_evolution_iteration(1))

    assert result["new_version"] == "v0.0.2"
    assert result["accepted"] is False
    assert result["ab_result"]["skipped"] is True
    assert result["ab_result"]["reason"] == "skip_ab"
    assert controller.version_control.get_latest_pointer() == "v0.0.1"


def test_controller_mock_runner_generates_completed_training_game(tmp_path):
    version_control = VersionControl(strategy_dir=str(tmp_path / "strategies"))
    version_control.create_version(
        "v0.0.1",
        prompts={
            "werewolf": "werewolf prompt",
            "seer": "seer prompt",
            "witch": "witch prompt",
            "hunter": "hunter prompt",
            "villager": "villager prompt",
        },
    )

    controller = EvolutionController(
        initial_version="v0.0.1",
        num_games_per_iteration=1,
        strategy_dir=str(tmp_path / "strategies"),
        log_dir=str(tmp_path / "logs"),
        skip_ab=True,
        fallback_only=True,
        game_runner="mock",
    )

    result = asyncio.run(controller._run_evolution_iteration(1))

    assert result["analysis"]["game_count"] == 1
    assert result["analysis"]["training_summary"]["completed"] == 1
    assert result["analysis"]["training_summary"]["failed"] == 0
    assert controller.version_control.get_latest_pointer() == "v0.0.1"


def test_controller_uses_next_available_candidate_version(tmp_path):
    version_control = VersionControl(strategy_dir=str(tmp_path))
    prompts = {
        "werewolf": "werewolf prompt",
        "seer": "seer prompt",
        "witch": "witch prompt",
        "hunter": "hunter prompt",
        "villager": "villager prompt",
    }
    version_control.create_version("v0.0.1", prompts=prompts)
    version_control.create_version("v0.0.2", parent_version="v0.0.1", prompts=prompts)

    controller = EvolutionController.__new__(EvolutionController)
    controller.current_version = "v0.0.1"
    controller.version_control = version_control
    controller.adapter = FakeAdapter()

    new_version = asyncio.run(
        controller._optimize_strategy(
            {
                "aggregate": {
                    "total_games": 0,
                    "werewolf_win_rate": 0,
                    "villager_win_rate": 0,
                    "average_rounds": 0,
                    "role_analysis": {},
                    "common_mistakes": {},
                },
                "suggestions": [],
                "training_summary": {},
            }
        )
    )

    assert new_version == "v0.0.3"
    assert version_control.version_exists("v0.0.3")


def test_controller_analyzes_only_completed_games_and_summarizes_failures():
    controller = EvolutionController.__new__(EvolutionController)
    controller.num_games_per_iteration = 3
    controller.parser = type(
        "FakeParser",
        (),
        {
            "parse_all_games": lambda self: [
                {"game_id": "complete", "winner": "werewolves", "metrics": {}, "raw_events": []},
                {"game_id": "incomplete", "winner": None, "metrics": {}, "raw_events": []},
            ],
            "parse_game": lambda self, game_id: {
                "game_id": "new_complete",
                "winner": "villagers",
                "metrics": {},
                "raw_events": [],
            } if game_id == "new_complete" else None,
        },
    )()
    controller.analyzer = EvolutionController().analyzer

    analysis = controller._analyze_game_results(
        [
            {"game_id": "new_complete", "winner": "villagers", "status": "completed"},
            {
                "game_id": "timed_out",
                "winner": None,
                "status": "timed_out",
                "error_type": "TimeoutError",
            },
            {
                "game_id": "failed",
                "winner": None,
                "status": "failed",
                "error_type": "RuntimeError",
            },
        ]
    )

    assert analysis["aggregate"]["total_games"] == 2
    assert analysis["aggregate"]["werewolf_win_rate"] == 0.5
    assert analysis["game_count"] == 1
    assert analysis["training_summary"] == {
        "requested": 3,
        "total_attempted": 3,
        "completed": 1,
        "timed_out": 1,
        "failed": 1,
        "failed_by_type": {"TimeoutError": 1, "RuntimeError": 1},
    }
