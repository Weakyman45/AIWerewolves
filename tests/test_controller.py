import asyncio

from backend.evolution.controller import EvolutionController
from backend.evolution.version_control import VersionControl


class FakeAdapter:
    def optimize_prompt(self, original_prompt, role, analysis):
        return {
            "optimized": f"{original_prompt}\noptimized for {role}",
            "reasoning": f"{role} reasoning",
            "key_changes": [f"{role} change"],
        }


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
            }
        )
    )

    metadata = version_control.get_metadata(new_version)

    assert new_version == "v0.0.2"
    assert metadata["analysis_summary"]["total_games"] == 5
    assert metadata["analysis_summary"]["role_analysis"]["werewolf_hiding_ability"]["average_score"] == 0.1
    assert metadata["role_optimizations"]["werewolf"] == {
        "reasoning": "werewolf reasoning",
        "key_changes": ["werewolf change"],
    }
    assert "global suggestion" in metadata["changes"]
    assert "werewolf: werewolf change" in metadata["changes"]
    assert version_control.get_prompt(new_version, "seer").endswith("optimized for seer")
