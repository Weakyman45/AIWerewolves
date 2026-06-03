from backend.evolution.adapter import Adapter


def test_adapter_generates_metric_based_werewolf_suggestions():
    adapter = Adapter.__new__(Adapter)
    analysis = {
        "werewolf_win_rate": 0.25,
        "role_analysis": {
            "werewolf_hiding_ability": {"average_score": 0.15},
            "werewolf_kill_accuracy": {"average_score": 0.8},
            "werewolf_vote_strategy": {"average_score": 0.6},
        },
        "common_mistakes": {"counts": {"werewolf_team_kill": 1}},
    }

    suggestions = adapter._generate_suggestions("werewolf", analysis)

    assert any("狼人胜率" in suggestion for suggestion in suggestions)
    assert any("终局存活率" in suggestion for suggestion in suggestions)
    assert any("夜刀神职命中率已达" in suggestion for suggestion in suggestions)
    assert any("减少无意义倒钩" in suggestion for suggestion in suggestions)
    assert any("误刀队友" in suggestion for suggestion in suggestions)


def test_adapter_generates_metric_based_good_team_suggestions():
    adapter = Adapter.__new__(Adapter)
    analysis = {
        "werewolf_win_rate": 0.7,
        "role_analysis": {
            "seer_check_accuracy": {"average_score": 0.3},
            "witch_poison_usage": {"average_score": 0.5},
            "hunter_shot_timing": {"average_score": 0.4},
            "villager_vote_accuracy": {"average_score": 0.3},
        },
        "common_mistakes": {"counts": {"witch_poisoned_villager_team": 2}},
    }

    assert any("查狼率" in suggestion for suggestion in adapter._generate_suggestions("seer", analysis))
    assert any("毒药命中狼人率" in suggestion for suggestion in adapter._generate_suggestions("witch", analysis))
    assert any("毒到好人阵营" in suggestion for suggestion in adapter._generate_suggestions("witch", analysis))
    assert any("开枪命中狼人率" in suggestion for suggestion in adapter._generate_suggestions("hunter", analysis))
    assert any("投票命中狼人率" in suggestion for suggestion in adapter._generate_suggestions("villager", analysis))


def test_adapter_appends_deterministic_patch_once():
    adapter = Adapter.__new__(Adapter)
    prompt = "基础角色提示"
    suggestions = ["建议一", "建议二"]

    patched = adapter._append_suggestions_patch(prompt, suggestions)
    patched_again = adapter._append_suggestions_patch(patched, ["建议三"])

    assert "## 数据驱动策略补丁" in patched
    assert "建议一" in patched
    assert "建议二" in patched
    assert patched_again.count("## 数据驱动策略补丁") == 1
    assert "建议一" not in patched_again
    assert "建议三" in patched_again


def test_evolution_summary_includes_role_metrics():
    adapter = Adapter.__new__(Adapter)
    summary = adapter.create_evolution_summary(
        "v0.0.1",
        "v0.0.2",
        ["优化狼人隐藏"],
        {
            "total_games": 10,
            "werewolf_win_rate": 0.4,
            "role_analysis": {
                "werewolf_hiding_ability": {
                    "average_score": 0.25,
                    "sample_size": 20,
                }
            },
        },
    )

    assert "werewolf_hiding_ability: 25.00% (样本 20)" in summary
