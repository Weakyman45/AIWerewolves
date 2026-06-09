from backend.evolution.analyzer import Analyzer


def test_analyzer_scores_role_actions_from_logs():
    game_data = {
        "game_id": "sample",
        "winner": "villagers",
        "players": {
            "player_0": {"name": "Alice", "role": "werewolf"},
            "player_1": {"name": "Bob", "role": "werewolf"},
            "player_2": {"name": "Charlie", "role": "seer"},
            "player_3": {"name": "David", "role": "witch"},
            "player_4": {"name": "Eve", "role": "hunter"},
            "player_5": {"name": "Frank", "role": "villager"},
        },
        "metrics": {"duration_rounds": 1},
        "raw_events": [
            {"type": "phase_change", "round_number": 1, "phase": "夜晚"},
            {
                "type": "night_action",
                "action": {"actor": "player_0", "action": "kill", "target": "player_3"},
            },
            {
                "type": "night_action",
                "action": {
                    "actor": "player_2",
                    "action": "check",
                    "target": "player_0",
                    "result": "werewolf",
                },
            },
            {
                "type": "night_action",
                "action": {"actor": "player_3", "action": "poison", "target": "player_1"},
            },
            {"type": "death", "player_id": "player_3", "cause": "wolf_kill"},
            {"type": "death", "player_id": "player_1", "cause": "witch_poison"},
            {
                "type": "speech",
                "player_id": "player_2",
                "content": "我是预言家，昨晚查验 Alice 是狼人。",
            },
            {
                "type": "vote_result",
                "content": "投票结果: Alice: Eve | Bob: Frank | Charlie: Alice | David: Bob | Eve: Alice | Frank: Alice",
            },
            {
                "type": "game_end",
                "winner": "villagers",
                "game_state": {
                    "players": {
                        "player_0": {"is_alive": True},
                        "player_1": {"is_alive": False},
                        "player_2": {"is_alive": True},
                        "player_3": {"is_alive": False},
                        "player_4": {"is_alive": True},
                        "player_5": {"is_alive": True},
                    }
                },
            },
        ],
    }

    analysis = Analyzer().analyze_game(game_data)

    assert analysis["werewolf"]["kill_accuracy"]["score"] == 1.0
    assert analysis["werewolf"]["hiding_ability"]["score"] == 0.5
    assert analysis["werewolf"]["vote_strategy"]["score"] == 1.0
    assert analysis["seer"]["check_accuracy"]["score"] == 1.0
    assert analysis["seer"]["reveal_timing"]["score"] == 1.0
    assert analysis["witch"]["poison_usage"]["score"] == 1.0
    assert analysis["villager"]["vote_accuracy"]["score"] == 1.0


def test_analyzer_flags_bad_poison_as_mistake():
    game_data = {
        "players": {
            "player_0": {"name": "Alice", "role": "werewolf"},
            "player_1": {"name": "Bob", "role": "villager"},
        },
        "raw_events": [
            {
                "type": "night_action",
                "action": {"actor": "player_1", "action": "poison", "target": "player_1"},
            }
        ],
    }

    analysis = Analyzer().analyze_game(game_data)

    assert analysis["mistakes"] == [
        {
            "type": "witch_poisoned_villager_team",
            "action": {"actor": "player_1", "action": "poison", "target": "player_1"},
            "severity": "high",
        }
    ]


def test_analyzer_aggregate_ignores_empty_samples():
    games = [
        {
            "winner": "werewolves",
            "players": {
                "player_0": {"name": "Alice", "role": "werewolf"},
                "player_1": {"name": "Bob", "role": "seer"},
            },
            "metrics": {"duration_rounds": 2},
            "raw_events": [
                {
                    "type": "night_action",
                    "action": {
                        "actor": "player_1",
                        "action": "check",
                        "target": "player_0",
                        "result": "werewolf",
                    },
                }
            ],
        },
        {
            "winner": "villagers",
            "players": {
                "player_0": {"name": "Alice", "role": "werewolf"},
                "player_1": {"name": "Bob", "role": "seer"},
            },
            "metrics": {"duration_rounds": 2},
            "raw_events": [],
        },
    ]

    aggregate = Analyzer().analyze_multiple_games(games)

    assert aggregate["total_games"] == 2
    assert aggregate["werewolf_win_rate"] == 0.5
    assert aggregate["role_analysis"]["seer_check_accuracy"] == {
        "average_score": 1.0,
        "sample_size": 1,
        "game_count": 1,
    }


def test_analyzer_tracks_rule_repairs_and_llm_fallbacks():
    game_data = {
        "winner": "villagers",
        "players": {
            "player_0": {"name": "Alice", "role": "werewolf"},
            "player_1": {"name": "Bob", "role": "villager"},
        },
        "metrics": {"duration_rounds": 1},
        "raw_events": [
            {
                "type": "agent_decision",
                "player_id": "player_1",
                "decision": {
                    "reasoning": "模型输出越界；修正非预言家越权报查验/跳预言家",
                },
            },
            {
                "type": "agent_decision",
                "player_id": "player_0",
                "decision": {
                    "reasoning": "本局未被授权悍跳，狼人不能上警冒充预言家",
                },
            },
            {
                "type": "agent_decision",
                "player_id": "player_0",
                "decision": {
                    "reasoning": "LLM调用失败，使用werewolf默认决策；已公开跳预言家，禁止退水改口",
                },
            },
        ],
    }

    analysis = Analyzer().analyze_game(game_data)
    aggregate = Analyzer().analyze_multiple_games([game_data])

    assert analysis["quality_metrics"]["nonseer_claim_repairs"] == 1
    assert analysis["quality_metrics"]["unauthorized_werewolf_fake_seer_blocks"] == 1
    assert analysis["quality_metrics"]["llm_fallbacks"] == 1
    assert analysis["quality_metrics"]["public_claim_consistency_repairs"] == 1
    assert aggregate["quality_metrics"]["counts"]["total_rule_repairs"] == 3
