import asyncio

from backend.agents.base import AgentAction, BaseAgent
from backend.agents.roles.hunter import HunterAgent
from backend.agents.roles.seer import SeerAgent
from backend.agents.roles.villager import VillagerAgent
from backend.agents.roles.witch import WitchAgent
from backend.agents.roles.werewolf import WerewolfAgent
from backend.core.models import AgentDecision, Role
from backend.core.logger import GameLogger
from backend.engine.game import WerewolfGame


class DummyAgent(BaseAgent):
    def get_system_prompt(self):
        return "dummy"

    async def make_night_action(self, game_state):
        return AgentDecision(decision_type="no_action", reasoning="", raw_output="")

    async def make_speech(self, game_state):
        return AgentDecision(decision_type="speech", reasoning="", raw_output="")

    async def make_vote(self, game_state):
        return AgentDecision(decision_type="vote", reasoning="", raw_output="")


def _agent_with_action(action: AgentAction) -> DummyAgent:
    agent = DummyAgent("player_0", "Alice", Role.VILLAGER)

    async def fake_action(_game_state, _action_type, _extra_instructions=""):
        return action

    agent._call_llm_for_action = fake_action
    return agent


def test_sheriff_election_does_not_treat_negative_text_as_run():
    agent = _agent_with_action(
        AgentAction(
            reasoning="隐藏身份，选择不上警",
            speech="我不上警，警下会认真投票",
        )
    )

    decision = asyncio.run(agent.make_sheriff_election({}))

    assert decision.decision_type == "stay"


def test_sheriff_election_uses_explicit_decision_type():
    agent = _agent_with_action(
        AgentAction(
            decision_type="run",
            reasoning="争夺警徽",
            speech="我上警竞选警长",
        )
    )

    decision = asyncio.run(agent.make_sheriff_election({}))

    assert decision.decision_type == "run"


def test_sheriff_retreat_does_not_treat_negative_text_as_retreat():
    agent = _agent_with_action(
        AgentAction(
            reasoning="继续留在警上",
            speech="我不退水，继续竞争警徽",
        )
    )

    decision = asyncio.run(agent.make_retreat({}))

    assert decision.decision_type == "stay"


def test_speak_direction_recognizes_right_side_wording():
    agent = _agent_with_action(
        AgentAction(
            reasoning="选右侧发言让查杀位先开口",
            speech="我选择从右侧开始发言",
        )
    )

    decision = asyncio.run(agent.make_speak_direction({}))

    assert decision.decision_type == "right"


def test_speak_direction_uses_explicit_decision_type():
    agent = _agent_with_action(
        AgentAction(
            decision_type="left",
            reasoning="从左边开始",
            speech="我选择左侧",
        )
    )

    decision = asyncio.run(agent.make_speak_direction({}))

    assert decision.decision_type == "left"


def test_sheriff_death_passes_badge_with_chinese_text():
    agent = _agent_with_action(
        AgentAction(
            decision_type="destroy",
            target_id="player_4",
            reasoning="警徽给Eve，今天全票出Frank",
            speech="我把警徽移交给Eve",
        )
    )

    decision = asyncio.run(agent.make_sheriff_death_decision({
        "players": {
            "player_0": {"name": "Alice", "is_alive": False},
            "player_4": {"name": "Eve", "is_alive": True},
        }
    }))

    assert decision.decision_type == "pass"
    assert decision.target_id == "player_4"


def test_sheriff_death_destroys_badge_with_destroy_text():
    agent = _agent_with_action(
        AgentAction(
            reasoning="我选择撕掉警徽",
            speech="警徽流失，本局不再有警长",
        )
    )

    decision = asyncio.run(agent.make_sheriff_death_decision({
        "players": {
            "player_0": {"name": "Alice", "is_alive": False},
            "player_4": {"name": "Eve", "is_alive": True},
        }
    }))

    assert decision.decision_type == "destroy"
    assert decision.target_id is None


def test_witch_uses_explicit_save_decision_type():
    witch = WitchAgent("player_0", "Alice")
    witch.set_night_kill("player_2")

    async def fake_action(_game_state, _action_type, _extra_instructions=""):
        return AgentAction(
            decision_type="save",
            reasoning="首夜刀口可能是神职，使用解药",
            speech="我救起这个刀口",
        )

    witch._call_llm_for_action = fake_action

    decision = asyncio.run(witch.make_night_action({
        "players": {
            "player_0": {"name": "Alice", "is_alive": True, "role": "witch"},
            "player_1": {"name": "Bob", "is_alive": True},
            "player_2": {"name": "Charlie", "is_alive": True},
        }
    }))

    assert decision.decision_type == "save"
    assert decision.target_id == "player_2"


def test_witch_recognizes_chinese_poison_decision_text():
    witch = WitchAgent("player_0", "Alice")
    witch.has_used_save = True

    async def fake_action(_game_state, _action_type, _extra_instructions=""):
        return AgentAction(
            target_id="player_2",
            reasoning="Charlie是推动真预出局的爆狼位，今晚用毒药处理",
            speech="我毒死Charlie",
        )

    witch._call_llm_for_action = fake_action

    decision = asyncio.run(witch.make_night_action({
        "players": {
            "player_0": {"name": "Alice", "is_alive": True, "role": "witch"},
            "player_1": {"name": "Bob", "is_alive": True},
            "player_2": {"name": "Charlie", "is_alive": True},
        }
    }))

    assert decision.decision_type == "poison"
    assert decision.target_id == "player_2"


def test_seer_excludes_current_night_kill_from_check_candidates():
    seer = SeerAgent("player_0", "Alice")
    seen_targets = {}

    async def fake_action(_game_state, _action_type, extra_instructions=""):
        seen_targets["prompt"] = extra_instructions
        return AgentAction(
            target_id="player_2",
            reasoning="查验可选目标",
            speech="查验player_2",
        )

    seer._call_llm_for_action = fake_action

    decision = asyncio.run(seer.make_night_action({
        "players": {
            "player_0": {"name": "Alice", "is_alive": True, "role": "seer"},
            "player_1": {"name": "Bob", "is_alive": True},
            "player_2": {"name": "Charlie", "is_alive": True},
        },
        "night_unavailable_target_ids": ["player_1"],
    }))

    assert "player_1" not in seen_targets["prompt"]
    assert decision.decision_type == "check"
    assert decision.target_id == "player_2"


def test_villager_public_speech_guard_rewrites_false_seer_claim():
    villager = VillagerAgent("player_7", "Ivy")
    action = AgentAction(
        reasoning="想用预言家身份带队",
        speech="我才是全场唯一真预言家，昨夜我验了Eve，是百分百查杀牌，今天全票出Eve。",
    )

    guarded = villager._guard_public_speech_action(action, {
        "players": {
            "player_7": {"name": "Ivy", "is_alive": True, "role": "villager"},
            "player_4": {"name": "Eve", "is_alive": True, "role": "werewolf"},
            "player_5": {"name": "Frank", "is_alive": True, "role": "villager"},
        }
    }, "day_speech")

    assert "修正非预言家越权" in guarded.reasoning
    assert "我是平民" in guarded.speech
    assert "没有夜间查验" in guarded.speech
    assert "我才是全场唯一真预言家" not in guarded.speech
    assert "昨夜我验" not in guarded.speech


def test_sheriff_speech_repair_avoids_duplicate_single_focus_name():
    villager = VillagerAgent("player_3", "David")
    villager.add_conversation("user", "Alice: 我是预言家，昨夜查验Frank是金水，警徽流先压Bob。")
    villager.add_conversation("user", "Eve: 我才是预言家，昨夜查验Ivy是金水，Alice是悍跳。")
    action = AgentAction(
        reasoning="误跳预言家",
        speech="我是预言家，昨晚我验了Eve是查杀，警徽给我。",
    )

    guarded = villager._guard_public_speech_action(action, {
        "players": {
            "player_0": {"name": "Alice", "is_alive": True, "role": "seer"},
            "player_3": {"name": "David", "is_alive": True, "role": "villager"},
            "player_4": {"name": "Eve", "is_alive": True, "role": "werewolf"},
        }
    }, "sheriff_speech")

    assert "Alice和Alice" not in guarded.speech


def test_unauthorized_werewolf_public_speech_guard_rewrites_false_seer_claim():
    wolf = WerewolfAgent("player_4", "Eve")
    wolf.can_fake_seer = False
    action = AgentAction(
        reasoning="想悍跳抢轮次",
        speech="我是全场唯一真预言家，昨晚查验David是查杀，今天全票出David。",
    )

    guarded = wolf._guard_public_speech_action(action, {
        "players": {
            "player_3": {"name": "David", "is_alive": True, "role": "seer"},
            "player_4": {"name": "Eve", "is_alive": True, "role": "werewolf"},
        }
    }, "day_speech")

    assert "修正非预言家越权" in guarded.reasoning
    assert "我是全场唯一真预言家" not in guarded.speech
    assert "昨晚查验" not in guarded.speech


def test_authorized_fake_seer_werewolf_can_keep_seer_claim():
    wolf = WerewolfAgent("player_4", "Eve")
    wolf.can_fake_seer = True
    action = AgentAction(
        reasoning="本局唯一悍跳狼争警徽",
        speech="我是全场唯一真预言家，昨晚查验David是查杀，今天全票出David。",
    )

    guarded = wolf._guard_public_speech_action(action, {
        "players": {
            "player_3": {"name": "David", "is_alive": True, "role": "seer"},
            "player_4": {"name": "Eve", "is_alive": True, "role": "werewolf"},
        }
    }, "day_speech")

    assert guarded.speech == action.speech


def test_game_assigns_exactly_one_fake_seer_wolf(tmp_path):
    game = WerewolfGame(
        ["Alice", "Bob", "Charlie", "David", "Eve", "Frank"],
        GameLogger(log_dir=str(tmp_path)),
    )

    wolf_ids = [
        pid for pid, state in game.player_states.items()
        if state.role == Role.WEREWOLF
    ]
    authorized_wolves = [
        pid for pid in wolf_ids
        if game.players[pid].can_fake_seer
    ]

    assert game.fake_seer_wolf_id in wolf_ids
    assert authorized_wolves == [game.fake_seer_wolf_id]


def test_nonseer_public_speech_prompt_blocks_first_person_check_claims():
    villager = VillagerAgent("player_5", "Frank")
    hunter = HunterAgent("player_6", "Grace")
    witch = WitchAgent("player_4", "Eve")
    wolf = WerewolfAgent("player_0", "Alice")

    for agent in [villager, hunter, witch, wolf]:
        instruction = agent._identity_boundary_instruction("day_speech")
        assert "不是预言家" in instruction
        assert "我验了" in instruction
        assert "我的查验" in instruction
        assert "别人声称/公开信息" in instruction


def test_day_speech_rewrite_instruction_is_role_specific_and_natural():
    witch = WitchAgent("player_4", "Eve")
    instruction = witch._public_speech_rewrite_instruction(
        "day_speech",
        "现在是白天发言阶段。",
    )

    assert "重写一段自然可展示发言" in instruction
    assert "以女巫视角发言" in instruction
    assert "不能说“我验/我的查验/我给查杀/我给金水”" in instruction
    assert "不要解释自己刚才说错了" in instruction


def test_sheriff_speech_repair_does_not_treat_villager_screening_seer_as_claim():
    villager = VillagerAgent("player_3", "David")
    villager.add_conversation(
        "user",
        "Eve: 各位好，我是警上的Eve，底牌是纯村民，这次上警就是来帮大家筛出真预言家，避免悍跳狼骗到警徽。",
    )
    villager.add_conversation(
        "user",
        "Alice: 各位好，我才是全场唯一真预言家，昨晚我摸的是警下的Charlie，是金水。",
    )
    action = AgentAction(
        reasoning="误跳预言家",
        speech="我是预言家，昨晚我验了Frank是查杀，警徽给我。",
    )

    guarded = villager._guard_public_speech_action(action, {
        "players": {
            "player_0": {"name": "Alice", "is_alive": True, "role": "seer"},
            "player_3": {"name": "David", "is_alive": True, "role": "villager"},
            "player_4": {"name": "Eve", "is_alive": True, "role": "villager"},
        }
    }, "sheriff_speech")

    assert villager._public_seer_claimants() == ["Alice"]
    assert "场上已有Alice的预言家声称" in guarded.speech
    assert "场上已有Eve、Alice的预言家声称" not in guarded.speech
    assert "Eve的警徽票标准和Alice的查验心路" in guarded.speech
    assert "Eve如果只跟结论" not in guarded.speech
    assert "我警上主要聊前置发言和警徽票标准" not in guarded.speech


def test_sheriff_speech_repair_does_not_invent_focus_without_prior_speeches():
    villager = VillagerAgent("player_4", "Eve")
    action = AgentAction(
        reasoning="误跳预言家",
        speech="我是预言家，昨晚我验了Frank是查杀，警徽给我。",
    )

    guarded = villager._guard_public_speech_action(action, {
        "players": {
            "player_0": {"name": "Alice", "is_alive": True, "role": "werewolf"},
            "player_1": {"name": "Bob", "is_alive": True, "role": "villager"},
            "player_4": {"name": "Eve", "is_alive": True, "role": "villager"},
        }
    }, "sheriff_speech")

    assert "Alice" not in guarded.speech
    assert "Bob" not in guarded.speech
    assert "前后置位" not in guarded.speech
    assert "目前还没有足够前置发言可评价" in guarded.speech
    assert "我会重点听后置位" in guarded.speech


def test_nonseer_sheriff_speech_prompt_focuses_on_previous_speeches():
    villager = VillagerAgent("player_3", "David")
    captured = {}

    async def fake_action(_game_state, action_type, extra_instructions=""):
        captured["action_type"] = action_type
        captured["extra_instructions"] = extra_instructions
        return AgentAction(
            reasoning="点评前置发言",
            speech="我警上先看前置发言，Alice的查验力度和警徽流都需要后置继续对比。",
        )

    villager._call_llm_for_action = fake_action

    decision = asyncio.run(villager.make_sheriff_speech({
        "players": {
            "player_0": {"name": "Alice", "is_alive": True, "role": "seer"},
            "player_3": {"name": "David", "is_alive": True, "role": "villager"},
        }
    }))

    assert decision.decision_type == "speech"
    assert captured["action_type"] == "sheriff_speech"
    assert "不能自称预言家" in captured["extra_instructions"]
    assert "重点评价前面已经发过言的玩家" in captured["extra_instructions"]
    assert "如果前面没人发言" in captured["extra_instructions"]


def test_hunter_public_speech_guard_rewrites_false_seer_claim():
    hunter = HunterAgent("player_6", "Henry")
    action = AgentAction(
        reasoning="跳预言家反打",
        speech="我是真预言家，昨晚我验了Ivy是查杀，大家跟我投Ivy。",
    )

    guarded = hunter._guard_public_speech_action(action, {
        "players": {
            "player_6": {"name": "Henry", "is_alive": True, "role": "hunter"},
            "player_7": {"name": "Ivy", "is_alive": True, "role": "villager"},
            "player_4": {"name": "Eve", "is_alive": True, "role": "werewolf"},
        }
    }, "day_speech")

    assert "修正非预言家越权" in guarded.reasoning
    assert "我是猎人视角" in guarded.speech
    assert "没有夜间查验" in guarded.speech
    assert "我是真预言家" not in guarded.speech


def test_public_speech_guard_allows_real_seer_claim():
    seer = SeerAgent("player_2", "Charlie")
    action = AgentAction(
        reasoning="报查验",
        speech="我是预言家，昨夜查验David是查杀，今天先出David。",
    )

    guarded = seer._guard_public_speech_action(action, {
        "players": {
            "player_2": {"name": "Charlie", "is_alive": True, "role": "seer"},
            "player_3": {"name": "David", "is_alive": True, "role": "werewolf"},
        }
    }, "day_speech")

    assert guarded.speech == action.speech
    assert guarded.reasoning == action.reasoning


def test_werewolf_vote_guard_avoids_lone_vote_on_public_seer():
    wolf = WerewolfAgent("player_0", "Alice")
    wolf.add_conversation("user", "Bob: 我是真预言家，昨夜查Charlie是金水。")
    wolf.add_conversation("user", "Charlie: David发言划水，狼面最高，今天可以归David。")

    async def fake_action(_game_state, _action_type, _extra_instructions=""):
        return AgentAction(
            target_id="player_1",
            reasoning="Bob是真预言家，对狼队威胁最大",
            speech="我投Bob",
        )

    wolf._call_llm_for_action = fake_action

    decision = asyncio.run(wolf.make_vote({
        "players": {
            "player_0": {"name": "Alice", "is_alive": True, "role": "werewolf"},
            "player_1": {"name": "Bob", "is_alive": True},
            "player_2": {"name": "Charlie", "is_alive": True},
            "player_3": {"name": "David", "is_alive": True},
        }
    }))

    assert decision.decision_type == "vote"
    assert decision.target_id == "player_3"
    assert "避免孤票公开高身份" in decision.reasoning


def test_werewolf_vote_guard_keeps_unprotected_target():
    wolf = WerewolfAgent("player_0", "Alice")
    wolf.add_conversation("user", "Bob: 我是普通村民，没有夜间信息。")

    async def fake_action(_game_state, _action_type, _extra_instructions=""):
        return AgentAction(
            target_id="player_1",
            reasoning="Bob表水弱",
            speech="我投Bob",
        )

    wolf._call_llm_for_action = fake_action

    decision = asyncio.run(wolf.make_vote({
        "players": {
            "player_0": {"name": "Alice", "is_alive": True, "role": "werewolf"},
            "player_1": {"name": "Bob", "is_alive": True},
            "player_2": {"name": "Charlie", "is_alive": True},
        }
    }))

    assert decision.target_id == "player_1"
    assert "避免孤票公开高身份" not in decision.reasoning


def test_werewolf_speech_guard_rewrites_no_info_multi_push():
    wolf = WerewolfAgent("player_0", "Alice")

    async def fake_action(_game_state, _action_type, _extra_instructions=""):
        return AgentAction(
            reasoning="前置位先打两个焦点",
            speech="我是普通村民，昨晚没信息，我重点怀疑Bob和Charlie状态怪，今天优先出他们里面一个。",
        )

    wolf._call_llm_for_action = fake_action

    decision = asyncio.run(wolf.make_speech({
        "current_round": 1,
        "players": {
            "player_0": {"name": "Alice", "is_alive": True, "role": "werewolf"},
            "player_1": {"name": "Bob", "is_alive": True},
            "player_2": {"name": "Charlie", "is_alive": True},
            "player_3": {"name": "David", "is_alive": True},
        },
    }))

    assert decision.decision_type == "speech"
    assert "现在需要看的不是谁喊得最响" in decision.raw_output
    assert "先听完整一轮发言" not in decision.raw_output
    assert "避免 D1 缺少公开共识/硬信息同时踩多人" in decision.reasoning


def test_werewolf_speech_guard_rewrites_attack_on_public_witch():
    wolf = WerewolfAgent("player_0", "Alice")
    wolf.add_conversation("user", "Bob: 我是女巫，昨晚救了Charlie。")

    async def fake_action(_game_state, _action_type, _extra_instructions=""):
        return AgentAction(
            reasoning="攻击女巫带队位",
            speech="Bob身份很差，我觉得今天可以出Bob，他明显是狼穿女巫衣服。",
        )

    wolf._call_llm_for_action = fake_action

    decision = asyncio.run(wolf.make_speech({
        "current_round": 1,
        "players": {
            "player_0": {"name": "Alice", "is_alive": True, "role": "werewolf"},
            "player_1": {"name": "Bob", "is_alive": True},
            "player_2": {"name": "Charlie", "is_alive": True},
        },
    }))

    assert "我先围绕Bob刚才的发言来盘" in decision.raw_output
    assert "先听完整一轮发言" not in decision.raw_output
    assert "避免 D1 无硬证据攻击公开高身份/水位" in decision.reasoning


def test_werewolf_round_two_maintains_public_fake_seer_claim():
    wolf = WerewolfAgent("player_0", "Alice")
    wolf.can_fake_seer = True
    wolf.public_claim = "seer"
    wolf.add_conversation("user", "Charlie: 我是真预言家，昨夜查验Alice是查杀。")

    speech, reason = wolf._guard_day_speech("我是闭眼好人，今天先看票型。", {
        "current_round": 2,
        "players": {
            "player_0": {"name": "Alice", "is_alive": True, "role": "werewolf"},
            "player_2": {"name": "Charlie", "is_alive": True, "role": "seer"},
            "player_3": {"name": "David", "is_alive": True, "role": "werewolf"},
        },
    })

    assert "我维持预言家身份" in speech
    assert "已公开悍跳预言家" in reason


def test_werewolf_round_two_blocks_unclaimed_extra_fake_seer():
    wolf = WerewolfAgent("player_4", "Eve")
    wolf.add_conversation("user", "Alice: 我是真预言家，昨夜查验Frank是金水。")

    speech, reason = wolf._guard_day_speech("我是全场唯一真预言家，昨夜我验了Ivy是查杀。", {
        "current_round": 2,
        "players": {
            "player_0": {"name": "Alice", "is_alive": True, "role": "werewolf"},
            "player_4": {"name": "Eve", "is_alive": True, "role": "werewolf"},
            "player_7": {"name": "Ivy", "is_alive": True, "role": "villager"},
            "player_5": {"name": "Frank", "is_alive": True, "role": "villager"},
        },
    })

    assert "我是全场唯一真预言家" not in speech
    assert "昨夜我验" not in speech
    assert "避免未授权" in reason


def test_werewolf_speech_guard_rewrites_unsupported_single_push():
    wolf = WerewolfAgent("player_0", "Alice")

    async def fake_action(_game_state, _action_type, _extra_instructions=""):
        return AgentAction(
            reasoning="Bob表水弱",
            speech="我是普通村民，Bob发言比较划水，我先轻压Bob，后面听完整一圈再定票。",
        )

    wolf._call_llm_for_action = fake_action

    decision = asyncio.run(wolf.make_speech({
        "current_round": 1,
        "players": {
            "player_0": {"name": "Alice", "is_alive": True, "role": "werewolf"},
            "player_1": {"name": "Bob", "is_alive": True},
            "player_2": {"name": "Charlie", "is_alive": True},
        },
    }))

    assert "现在需要看的不是谁喊得最响" in decision.raw_output
    assert "先听完整一轮发言" not in decision.raw_output
    assert "避免 D1 缺少公开共识/硬信息点名踩人" in decision.reasoning


def test_werewolf_force_fake_seer_when_enabled_and_no_public_seer():
    wolf = WerewolfAgent("player_0", "Alice")
    wolf.can_fake_seer = True
    wolf.set_system_prompt_override("狼人策略：动作层强制悍跳。")
    wolf.add_conversation("user", "Charlie: 我是普通村民，昨晚没有信息。")
    wolf.add_conversation("user", "David: 我是好人，先听后面发言。")

    async def fail_if_called(_game_state, _action_type, _extra_instructions=""):
        raise AssertionError("forced fake seer should not call LLM")

    wolf._call_llm_for_action = fail_if_called

    decision = asyncio.run(wolf.make_speech({
        "current_round": 1,
        "players": {
            "player_0": {"name": "Alice", "is_alive": True, "role": "werewolf"},
            "player_1": {"name": "Bob", "is_alive": True, "role": "werewolf"},
            "player_2": {"name": "Charlie", "is_alive": True},
            "player_3": {"name": "David", "is_alive": True},
            "player_4": {"name": "Eve", "is_alive": True},
        },
    }))

    assert decision.decision_type == "speech"
    assert "我是预言家" in decision.raw_output
    assert "查杀" in decision.raw_output
    assert "Bob" not in decision.raw_output
    assert "动作层强制悍跳" in decision.reasoning


def test_werewolf_force_fake_seer_after_one_public_speaker():
    wolf = WerewolfAgent("player_0", "Alice")
    wolf.can_fake_seer = True
    wolf.set_system_prompt_override("狼人策略：动作层强制悍跳。")
    wolf.add_conversation("user", "Charlie: 我是普通村民，昨晚没有信息。")

    async def fail_if_called(_game_state, _action_type, _extra_instructions=""):
        raise AssertionError("forced fake seer should not call LLM")

    wolf._call_llm_for_action = fail_if_called

    decision = asyncio.run(wolf.make_speech({
        "current_round": 1,
        "players": {
            "player_0": {"name": "Alice", "is_alive": True, "role": "werewolf"},
            "player_1": {"name": "Bob", "is_alive": True, "role": "werewolf"},
            "player_2": {"name": "Charlie", "is_alive": True},
            "player_3": {"name": "David", "is_alive": True},
        },
    }))

    assert "查验Charlie是查杀" in decision.raw_output
    assert "已有前置表水" in decision.reasoning


def test_werewolf_force_fake_seer_waits_for_public_speaker():
    wolf = WerewolfAgent("player_0", "Alice")
    wolf.can_fake_seer = True
    wolf.set_system_prompt_override("狼人策略：动作层强制悍跳。")
    called = {"value": False}

    async def fake_action(_game_state, _action_type, _extra_instructions=""):
        called["value"] = True
        return AgentAction(
            reasoning="首位发言不盲跳",
            speech="我是普通村民，先听完整一轮发言。",
        )

    wolf._call_llm_for_action = fake_action

    decision = asyncio.run(wolf.make_speech({
        "current_round": 1,
        "players": {
            "player_0": {"name": "Alice", "is_alive": True, "role": "werewolf"},
            "player_1": {"name": "Bob", "is_alive": True, "role": "werewolf"},
            "player_2": {"name": "Charlie", "is_alive": True},
            "player_3": {"name": "David", "is_alive": True},
        },
    }))

    assert called["value"]
    assert "我是预言家" not in decision.raw_output


def test_werewolf_force_fake_seer_prefers_low_information_villager_claim():
    wolf = WerewolfAgent("player_0", "Alice")
    wolf.can_fake_seer = True
    wolf.set_system_prompt_override("狼人策略：动作层强制悍跳。")
    wolf.add_conversation("user", "Charlie: 我是普通村民，昨晚没有信息，先听后面发言。")
    wolf.add_conversation("user", "David: 我是铁好人，会认真听预言家发言。")

    async def fail_if_called(_game_state, _action_type, _extra_instructions=""):
        raise AssertionError("forced fake seer should not call LLM")

    wolf._call_llm_for_action = fail_if_called

    decision = asyncio.run(wolf.make_speech({
        "current_round": 1,
        "players": {
            "player_0": {"name": "Alice", "is_alive": True, "role": "werewolf"},
            "player_1": {"name": "Bob", "is_alive": True, "role": "werewolf"},
            "player_2": {"name": "Charlie", "is_alive": True},
            "player_3": {"name": "David", "is_alive": True},
        },
    }))

    assert "查验Charlie是查杀" in decision.raw_output


def test_werewolf_force_fake_seer_skips_public_power_claims():
    wolf = WerewolfAgent("player_0", "Alice")
    wolf.can_fake_seer = True
    wolf.set_system_prompt_override("狼人策略：动作层强制悍跳。")
    wolf.add_conversation("user", "Charlie: 我是猎人，先不带队。")
    wolf.add_conversation("user", "David: 我是普通村民，昨晚没有信息。")

    async def fail_if_called(_game_state, _action_type, _extra_instructions=""):
        raise AssertionError("forced fake seer should not call LLM")

    wolf._call_llm_for_action = fail_if_called

    decision = asyncio.run(wolf.make_speech({
        "current_round": 1,
        "players": {
            "player_0": {"name": "Alice", "is_alive": True, "role": "werewolf"},
            "player_1": {"name": "Bob", "is_alive": True, "role": "werewolf"},
            "player_2": {"name": "Charlie", "is_alive": True},
            "player_3": {"name": "David", "is_alive": True},
        },
    }))

    assert "查验David是查杀" in decision.raw_output
    assert "Charlie" not in decision.raw_output


def test_werewolf_force_fake_seer_uses_unspeaking_target_reason_when_target_has_not_spoken():
    wolf = WerewolfAgent("player_0", "Alice")
    wolf.can_fake_seer = True
    wolf.set_system_prompt_override("狼人策略：动作层强制悍跳。")
    wolf.add_conversation("user", "David: 我是女巫，先听预言家报查验。")

    async def fail_if_called(_game_state, _action_type, _extra_instructions=""):
        raise AssertionError("forced fake seer should not call LLM")

    wolf._call_llm_for_action = fail_if_called

    decision = asyncio.run(wolf.make_speech({
        "current_round": 1,
        "players": {
            "player_0": {"name": "Alice", "is_alive": True, "role": "werewolf"},
            "player_1": {"name": "Bob", "is_alive": True, "role": "werewolf"},
            "player_2": {"name": "Charlie", "is_alive": True},
            "player_3": {"name": "David", "is_alive": True},
        },
    }))

    assert "查验Charlie是查杀" in decision.raw_output
    assert "还没有公开信息" in decision.raw_output
    assert "前置发言只表态" not in decision.raw_output
    assert "未发言" in decision.reasoning


def test_werewolf_force_fake_seer_avoids_saved_wolf_kill_target():
    wolf = WerewolfAgent("player_0", "Alice")
    wolf.can_fake_seer = True
    wolf.set_system_prompt_override("狼人策略：动作层强制悍跳。")
    wolf.add_conversation("user", "David: 我是普通村民，昨晚没有信息。")

    async def fail_if_called(_game_state, _action_type, _extra_instructions=""):
        raise AssertionError("forced fake seer should not call LLM")

    wolf._call_llm_for_action = fail_if_called

    decision = asyncio.run(wolf.make_speech({
        "current_round": 1,
        "wolf_last_kill_target_id": "player_3",
        "wolf_last_kill_saved": True,
        "players": {
            "player_0": {"name": "Alice", "is_alive": True, "role": "werewolf"},
            "player_1": {"name": "Bob", "is_alive": True, "role": "werewolf"},
            "player_2": {"name": "Charlie", "is_alive": True},
            "player_3": {"name": "David", "is_alive": True},
        },
    }))

    assert "查验Charlie是查杀" in decision.raw_output
    assert "David" not in decision.raw_output


def test_werewolf_force_fake_seer_requires_prompt_marker():
    wolf = WerewolfAgent("player_0", "Alice")
    wolf.can_fake_seer = True
    wolf.add_conversation("user", "Charlie: 我是普通村民，昨晚没有信息。")
    wolf.add_conversation("user", "David: 我是好人，先听后面发言。")
    called = {"value": False}

    async def fake_action(_game_state, _action_type, _extra_instructions=""):
        called["value"] = True
        return AgentAction(
            reasoning="无标记不强制悍跳",
            speech="我是普通村民，先听完整一轮发言。",
        )

    wolf._call_llm_for_action = fake_action

    decision = asyncio.run(wolf.make_speech({
        "current_round": 1,
        "players": {
            "player_0": {"name": "Alice", "is_alive": True, "role": "werewolf"},
            "player_1": {"name": "Bob", "is_alive": True, "role": "werewolf"},
            "player_2": {"name": "Charlie", "is_alive": True},
            "player_3": {"name": "David", "is_alive": True},
        },
    }))

    assert called["value"]
    assert "我是预言家" not in decision.raw_output


def test_werewolf_force_fake_seer_skips_when_public_seer_claim_exists():
    wolf = WerewolfAgent("player_0", "Alice")
    wolf.can_fake_seer = True
    wolf.set_system_prompt_override("狼人策略：动作层强制悍跳。")
    wolf.add_conversation("user", "Charlie: 我是普通村民，昨晚没有信息。")
    wolf.add_conversation("user", "Eve: 我是全场唯一真预言家，昨晚查David是金水。")
    called = {"value": False}

    async def fake_action(_game_state, _action_type, _extra_instructions=""):
        called["value"] = True
        return AgentAction(
            reasoning="已有预言家起跳，不强制悍跳",
            speech="我是普通村民，先听完整一轮发言。",
        )

    wolf._call_llm_for_action = fake_action

    decision = asyncio.run(wolf.make_speech({
        "current_round": 1,
        "players": {
            "player_0": {"name": "Alice", "is_alive": True, "role": "werewolf"},
            "player_1": {"name": "Bob", "is_alive": True, "role": "werewolf"},
            "player_2": {"name": "Charlie", "is_alive": True},
            "player_4": {"name": "Eve", "is_alive": True},
        },
    }))

    assert called["value"]
    assert "我是预言家" not in decision.raw_output


def test_werewolf_force_late_fake_seer_after_unique_public_seer_claim():
    wolf = WerewolfAgent("player_4", "Eve")
    wolf.can_fake_seer = True
    wolf.set_system_prompt_override("狼人策略：动作层强制悍跳。动作层后置补跳。")
    wolf.add_conversation("user", "Alice: 我是闭眼平民，首置位没信息。")
    wolf.add_conversation("user", "Charlie: 大家好，我是唯一真预言家，昨晚验了Frank是金水。")

    async def fail_if_called(_game_state, _action_type, _extra_instructions=""):
        raise AssertionError("late forced fake seer should not call LLM")

    wolf._call_llm_for_action = fail_if_called

    decision = asyncio.run(wolf.make_speech({
        "current_round": 1,
        "players": {
            "player_0": {"name": "Alice", "is_alive": True},
            "player_1": {"name": "Bob", "is_alive": True, "role": "werewolf"},
            "player_2": {"name": "Charlie", "is_alive": True},
            "player_4": {"name": "Eve", "is_alive": True, "role": "werewolf"},
            "player_5": {"name": "Frank", "is_alive": True},
        },
    }))

    assert "我对跳预言家" in decision.raw_output
    assert "查验Charlie是查杀" in decision.raw_output
    assert "动作层后置补跳" in decision.reasoning


def test_werewolf_force_late_fake_seer_does_not_treat_commentary_as_seer_claim():
    wolf = WerewolfAgent("player_4", "Eve")
    wolf.can_fake_seer = True
    wolf.set_system_prompt_override("狼人策略：动作层强制悍跳。动作层后置补跳。")
    wolf.add_conversation("user", "Charlie: 我是全场唯一真预言家，昨晚查Frank是查杀。")
    wolf.add_conversation("user", "Bob: 现在只有Charlie跳预言家，我暂时认他的预言家面更高。")

    async def fail_if_called(_game_state, _action_type, _extra_instructions=""):
        raise AssertionError("late forced fake seer should not call LLM")

    wolf._call_llm_for_action = fail_if_called

    decision = asyncio.run(wolf.make_speech({
        "current_round": 1,
        "players": {
            "player_1": {"name": "Bob", "is_alive": True},
            "player_2": {"name": "Charlie", "is_alive": True},
            "player_4": {"name": "Eve", "is_alive": True, "role": "werewolf"},
            "player_5": {"name": "Frank", "is_alive": True, "role": "werewolf"},
        },
    }))

    assert "查验Charlie是查杀" in decision.raw_output
    assert "查验Bob是查杀" not in decision.raw_output
    assert "公开预言家 Charlie" in decision.reasoning


def test_werewolf_force_late_fake_seer_defends_when_self_checkkilled():
    wolf = WerewolfAgent("player_2", "Charlie")
    wolf.can_fake_seer = True
    wolf.set_system_prompt_override("狼人策略：动作层强制悍跳。动作层后置补跳。")
    wolf.add_conversation("user", "Bob: 我是全场唯一真预言家，昨晚查杀Charlie，他是铁狼。")

    async def fail_if_called(_game_state, _action_type, _extra_instructions=""):
        raise AssertionError("late forced fake seer should not call LLM")

    wolf._call_llm_for_action = fail_if_called

    decision = asyncio.run(wolf.make_speech({
        "current_round": 1,
        "players": {
            "player_1": {"name": "Bob", "is_alive": True},
            "player_2": {"name": "Charlie", "is_alive": True, "role": "werewolf"},
            "player_4": {"name": "Eve", "is_alive": True, "role": "werewolf"},
            "player_5": {"name": "Frank", "is_alive": True},
        },
    }))

    assert "Bob给我查杀我不认" in decision.raw_output
    assert "我是好人视角" in decision.raw_output
    assert "查验Bob是查杀" in decision.raw_output
    assert "被 Bob 查杀后强防守" in decision.reasoning


def test_werewolf_force_late_fake_seer_counters_gold_water_and_bad_badge_flow():
    wolf = WerewolfAgent("player_4", "Eve")
    wolf.can_fake_seer = True
    wolf.set_system_prompt_override("狼人策略：动作层强制悍跳。动作层后置补跳。")
    wolf.add_conversation(
        "user",
        "Frank: 我是真预言家，昨晚验Bob是金水，大家别错打他。警徽流先验David再验Charlie排坑。",
    )
    wolf.add_conversation("user", "Bob: 我接Frank金水，目前暂站他边，他的警徽流没问题。")

    async def fail_if_called(_game_state, _action_type, _extra_instructions=""):
        raise AssertionError("late forced fake seer should not call LLM")

    wolf._call_llm_for_action = fail_if_called

    decision = asyncio.run(wolf.make_speech({
        "current_round": 1,
        "players": {
            "player_1": {"name": "Bob", "is_alive": True},
            "player_3": {"name": "David", "is_alive": True, "role": "werewolf"},
            "player_4": {"name": "Eve", "is_alive": True, "role": "werewolf"},
            "player_5": {"name": "Frank", "is_alive": True},
        },
    }))

    assert "查验Frank是查杀" in decision.raw_output
    assert "Frank先发金水是在做票仓" in decision.raw_output
    assert "金水本人接对身份不等于Frank是真预" in decision.raw_output
    assert "本局没有警长环节" in decision.raw_output
    assert "硬聊警徽流是在套模板" in decision.raw_output


def test_werewolf_force_late_fake_seer_skips_when_teammate_already_claimed_seer():
    wolf = WerewolfAgent("player_4", "Eve")
    wolf.set_system_prompt_override("狼人策略：动作层强制悍跳。动作层后置补跳。")
    wolf.add_conversation("user", "Bob: 我是预言家，昨晚查验David是查杀。")
    wolf.add_conversation("user", "Charlie: 我才是真预言家，昨晚验了Frank是金水。")
    called = {"value": False}

    async def fake_action(_game_state, _action_type, _extra_instructions=""):
        called["value"] = True
        return AgentAction(
            reasoning="队友已跳，不重复补跳",
            speech="我站边Bob，Charlie后置对跳有狼面。",
        )

    wolf._call_llm_for_action = fake_action

    decision = asyncio.run(wolf.make_speech({
        "current_round": 1,
        "players": {
            "player_1": {"name": "Bob", "is_alive": True, "role": "werewolf"},
            "player_2": {"name": "Charlie", "is_alive": True},
            "player_4": {"name": "Eve", "is_alive": True, "role": "werewolf"},
            "player_5": {"name": "Frank", "is_alive": True},
        },
    }))

    assert called["value"]
    assert "我对跳预言家" not in decision.raw_output


def test_werewolf_speech_guard_rewrites_attack_on_public_seer_with_intro():
    wolf = WerewolfAgent("player_0", "Alice")
    wolf.add_conversation("user", "David: 各位好，我是全场唯一真预言家，昨夜查验Charlie是好人。")

    async def fake_action(_game_state, _action_type, _extra_instructions=""):
        return AgentAction(
            reasoning="质疑唯一预言家心路",
            speech="我是好人，David跳预言家没说清首验原因，心路不全我暂不站边。",
        )

    wolf._call_llm_for_action = fake_action

    decision = asyncio.run(wolf.make_speech({
        "current_round": 1,
        "players": {
            "player_0": {"name": "Alice", "is_alive": True, "role": "werewolf"},
            "player_1": {"name": "Bob", "is_alive": True},
            "player_2": {"name": "Charlie", "is_alive": True},
            "player_3": {"name": "David", "is_alive": True},
        },
    }))

    assert "目前场上主要信息来自David" in decision.raw_output
    assert "先听完整一轮发言" not in decision.raw_output
    assert "避免 D1 无硬证据攻击公开高身份/水位" in decision.reasoning


def test_werewolf_speech_guard_rewrites_attack_on_named_gold_water():
    wolf = WerewolfAgent("player_0", "Alice")
    wolf.add_conversation("user", "Bob: 我是预言家，昨夜查验Eve（player_4）为金水。")

    async def fake_action(_game_state, _action_type, _extra_instructions=""):
        return AgentAction(
            reasoning="继续打前面踩过的目标",
            speech="我是好人，Eve刚才发言有疑点，我还是觉得她身份偏差。",
        )

    wolf._call_llm_for_action = fake_action

    decision = asyncio.run(wolf.make_speech({
        "current_round": 1,
        "players": {
            "player_0": {"name": "Alice", "is_alive": True, "role": "werewolf"},
            "player_1": {"name": "Bob", "is_alive": True},
            "player_4": {"name": "Eve", "is_alive": True},
        },
    }))

    assert "目前场上主要信息来自Bob" in decision.raw_output
    assert "先听完整一轮发言" not in decision.raw_output
    assert "避免 D1 无硬证据攻击公开高身份/水位" in decision.reasoning


def test_werewolf_speech_guard_uses_contextual_low_risk_speech():
    alice = WerewolfAgent("player_0", "Alice")
    eve = WerewolfAgent("player_4", "Eve")
    for wolf in [alice, eve]:
        wolf.add_conversation("user", "Charlie: 我是真预言家，昨晚查了David是金水。")

        async def fake_action(_game_state, _action_type, _extra_instructions=""):
            return AgentAction(
                reasoning="错误攻击公开保护位",
                speech="Charlie跳预言家没说清心路，David这个金水也不能全信。",
            )

        wolf._call_llm_for_action = fake_action

    game_state = {
        "current_round": 1,
        "players": {
            "player_0": {"name": "Alice", "is_alive": True, "role": "werewolf"},
            "player_2": {"name": "Charlie", "is_alive": True},
            "player_3": {"name": "David", "is_alive": True},
            "player_4": {"name": "Eve", "is_alive": True, "role": "werewolf"},
        },
    }

    alice_decision = asyncio.run(alice.make_speech(game_state))
    eve_decision = asyncio.run(eve.make_speech(game_state))

    assert "目前场上主要信息来自Charlie" in alice_decision.raw_output
    assert "目前场上主要信息来自Charlie" in eve_decision.raw_output
    assert "先听完整一轮发言" not in alice_decision.raw_output
    assert "先听完整一轮发言" not in eve_decision.raw_output
    assert "避免 D1 无硬证据攻击公开高身份/水位" in alice_decision.reasoning
    assert "避免 D1 无硬证据攻击公开高身份/水位" in eve_decision.reasoning


def test_werewolf_speech_guard_rewrites_passive_self_checkkill_response():
    wolf = WerewolfAgent("player_0", "Alice")
    wolf.add_conversation("user", "Eve: 我是全场唯一真预言家，昨晚查验Alice是查杀。")

    async def fake_action(_game_state, _action_type, _extra_instructions=""):
        return AgentAction(
            reasoning="被查杀后继续低风险表水",
            speech="我是普通村民，昨晚没有额外信息，先听完整一轮发言。",
        )

    wolf._call_llm_for_action = fake_action

    decision = asyncio.run(wolf.make_speech({
        "current_round": 1,
        "players": {
            "player_0": {"name": "Alice", "is_alive": True, "role": "werewolf"},
            "player_4": {"name": "Eve", "is_alive": True},
        },
    }))

    assert "Eve给我查杀我不认" in decision.raw_output
    assert "被公开查杀时必须强表水反查杀" in decision.reasoning


def test_werewolf_speech_guard_allows_self_checkkill_defense():
    wolf = WerewolfAgent("player_0", "Alice")
    wolf.add_conversation("user", "Eve: 我是全场唯一真预言家，昨晚查验Alice是查杀。")

    async def fake_action(_game_state, _action_type, _extra_instructions=""):
        return AgentAction(
            reasoning="被查杀后强表水",
            speech="Eve给我查杀我不认，她只报结果没心路，我认为她是悍跳。",
        )

    wolf._call_llm_for_action = fake_action

    decision = asyncio.run(wolf.make_speech({
        "current_round": 1,
        "players": {
            "player_0": {"name": "Alice", "is_alive": True, "role": "werewolf"},
            "player_4": {"name": "Eve", "is_alive": True},
        },
    }))

    assert decision.raw_output == "Eve给我查杀我不认，她只报结果没心路，我认为她是悍跳。"
    assert "避免 D1 无硬证据攻击公开高身份/水位" not in decision.reasoning


def test_werewolf_speech_guard_rewrites_weak_self_checkkill_counterattack():
    wolf = WerewolfAgent("player_4", "Eve")
    wolf.add_conversation("user", "David: 我是全场唯一真预言家，昨晚查验Eve为狼人。")

    async def fake_action(_game_state, _action_type, _extra_instructions=""):
        return AgentAction(
            reasoning="只反打但没有明确表水",
            speech="David你悍跳给我发查杀太明显了，今天好人都跟票出David这个悍跳狼。",
        )

    wolf._call_llm_for_action = fake_action

    decision = asyncio.run(wolf.make_speech({
        "current_round": 1,
        "players": {
            "player_2": {"name": "Charlie", "is_alive": True, "role": "werewolf"},
            "player_3": {"name": "David", "is_alive": True},
            "player_4": {"name": "Eve", "is_alive": True, "role": "werewolf"},
        },
    }))

    assert "David给我查杀我不认" in decision.raw_output
    assert "被公开查杀时必须强表水反查杀" in decision.reasoning


def test_werewolf_vote_guard_allows_vote_on_self_checkkiller():
    wolf = WerewolfAgent("player_0", "Alice")
    wolf.add_conversation("user", "Eve: 我是全场唯一真预言家，昨晚查验Alice是查杀。")
    wolf.add_conversation("user", "Bob: Frank发言划水，身份偏差。")

    async def fake_action(_game_state, _action_type, _extra_instructions=""):
        return AgentAction(
            target_id="player_4",
            reasoning="Eve给我查杀，我必须反投她自救",
            speech="我投Eve",
        )

    wolf._call_llm_for_action = fake_action

    decision = asyncio.run(wolf.make_vote({
        "players": {
            "player_0": {"name": "Alice", "is_alive": True, "role": "werewolf"},
            "player_1": {"name": "Bob", "is_alive": True},
            "player_4": {"name": "Eve", "is_alive": True},
            "player_5": {"name": "Frank", "is_alive": True},
        },
    }))

    assert decision.target_id == "player_4"
    assert "避免孤票公开高身份" not in decision.reasoning


def test_werewolf_vote_guard_allows_vote_on_self_checkkiller_with_tielang_wording():
    wolf = WerewolfAgent("player_1", "Bob")
    wolf.add_conversation("user", "Eve: 我才是真预言家！昨晚验了Bob是铁狼，今天全票出Bob。")
    wolf.add_conversation("user", "Charlie: 我是普通村民，先听票型。")

    async def fake_action(_game_state, _action_type, _extra_instructions=""):
        return AgentAction(
            target_id="player_4",
            reasoning="Eve查杀我，我必须反投她自救",
            speech="我投Eve",
        )

    wolf._call_llm_for_action = fake_action

    decision = asyncio.run(wolf.make_vote({
        "players": {
            "player_1": {"name": "Bob", "is_alive": True, "role": "werewolf"},
            "player_2": {"name": "Charlie", "is_alive": True},
            "player_4": {"name": "Eve", "is_alive": True},
        },
    }))

    assert decision.target_id == "player_4"
    assert "避免孤票公开高身份" not in decision.reasoning


def test_werewolf_vote_guard_allows_vote_on_own_fake_seer_checkkill_target():
    wolf = WerewolfAgent("player_1", "Bob")
    wolf.add_conversation("user", "Eve: 我是全场唯一真预言家，昨晚首验Frank是金水。")
    wolf.add_conversation("user", "Bob: 我对跳预言家，昨晚查验Eve是查杀。今天先出我的查杀Eve。")
    wolf.add_conversation("user", "Charlie: 我是普通村民，先听票型。")

    async def fake_action(_game_state, _action_type, _extra_instructions=""):
        return AgentAction(
            target_id="player_4",
            reasoning="Eve是我公开查杀的对跳位，必须归票她",
            speech="我投Eve",
        )

    wolf._call_llm_for_action = fake_action

    decision = asyncio.run(wolf.make_vote({
        "players": {
            "player_1": {"name": "Bob", "is_alive": True, "role": "werewolf"},
            "player_2": {"name": "Charlie", "is_alive": True},
            "player_4": {"name": "Eve", "is_alive": True},
            "player_5": {"name": "Frank", "is_alive": True},
        },
    }))

    assert decision.target_id == "player_4"
    assert "避免孤票公开高身份" not in decision.reasoning


def test_werewolf_vote_guard_allows_vote_on_teammate_checkkiller():
    wolf = WerewolfAgent("player_0", "Alice")
    wolf.add_conversation("user", "Eve: 我是全场唯一真预言家，昨晚查Bob是狼人。")
    wolf.add_conversation("user", "Charlie: Frank发言划水，身份偏差。")

    async def fake_action(_game_state, _action_type, _extra_instructions=""):
        return AgentAction(
            target_id="player_4",
            reasoning="Eve查杀我的狼队友，必须冲她救票",
            speech="我投Eve",
        )

    wolf._call_llm_for_action = fake_action

    decision = asyncio.run(wolf.make_vote({
        "players": {
            "player_0": {"name": "Alice", "is_alive": True, "role": "werewolf"},
            "player_1": {"name": "Bob", "is_alive": True, "role": "werewolf"},
            "player_2": {"name": "Charlie", "is_alive": True},
            "player_4": {"name": "Eve", "is_alive": True},
            "player_5": {"name": "Frank", "is_alive": True},
        },
    }))

    assert decision.target_id == "player_4"
    assert "避免孤票公开高身份" not in decision.reasoning


def test_werewolf_vote_guard_allows_vote_on_teammate_checkkiller_with_wei_wording():
    wolf = WerewolfAgent("player_2", "Charlie")
    wolf.add_conversation("user", "David: 我是全场唯一真预言家，昨晚查验Eve为狼人。")
    wolf.add_conversation("user", "Bob: Frank发言划水，身份偏差。")

    async def fake_action(_game_state, _action_type, _extra_instructions=""):
        return AgentAction(
            target_id="player_3",
            reasoning="David查杀我的狼队友，必须冲他救票",
            speech="我投David",
        )

    wolf._call_llm_for_action = fake_action

    decision = asyncio.run(wolf.make_vote({
        "players": {
            "player_1": {"name": "Bob", "is_alive": True},
            "player_2": {"name": "Charlie", "is_alive": True, "role": "werewolf"},
            "player_3": {"name": "David", "is_alive": True},
            "player_4": {"name": "Eve", "is_alive": True, "role": "werewolf"},
            "player_5": {"name": "Frank", "is_alive": True},
        },
    }))

    assert decision.target_id == "player_3"
    assert "避免孤票公开高身份" not in decision.reasoning


def test_werewolf_vote_guard_avoids_saved_wolf_kill_target():
    wolf = WerewolfAgent("player_0", "Alice")
    wolf.add_conversation("user", "Bob: Frank发言比较划水，身份需要再听。")

    async def fake_action(_game_state, _action_type, _extra_instructions=""):
        return AgentAction(
            target_id="player_3",
            reasoning="尝试投昨夜刀口未死位",
            speech="我投David",
        )

    wolf._call_llm_for_action = fake_action

    decision = asyncio.run(wolf.make_vote({
        "wolf_last_kill_target_id": "player_3",
        "wolf_last_kill_saved": True,
        "players": {
            "player_0": {"name": "Alice", "is_alive": True, "role": "werewolf"},
            "player_1": {"name": "Bob", "is_alive": True, "role": "werewolf"},
            "player_2": {"name": "Charlie", "is_alive": True},
            "player_3": {"name": "David", "is_alive": True},
            "player_5": {"name": "Frank", "is_alive": True},
        },
    }))

    assert decision.target_id == "player_5"
    assert "避免孤票公开高身份" in decision.reasoning


def test_werewolf_speech_guard_allows_attack_on_teammate_checkkiller():
    wolf = WerewolfAgent("player_0", "Alice")
    wolf.add_conversation("user", "Eve: 我是全场唯一真预言家，昨晚查Bob是狼人。")

    async def fake_action(_game_state, _action_type, _extra_instructions=""):
        return AgentAction(
            reasoning="救被查杀队友",
            speech="Eve给Bob发查杀太急，我觉得她有悍跳狼面，今天不能直接跟她冲票。",
        )

    wolf._call_llm_for_action = fake_action

    decision = asyncio.run(wolf.make_speech({
        "current_round": 1,
        "players": {
            "player_0": {"name": "Alice", "is_alive": True, "role": "werewolf"},
            "player_1": {"name": "Bob", "is_alive": True, "role": "werewolf"},
            "player_4": {"name": "Eve", "is_alive": True},
        },
    }))

    assert decision.raw_output == "Eve给Bob发查杀太急，我觉得她有悍跳狼面，今天不能直接跟她冲票。"
    assert "避免 D1 无硬证据攻击公开高身份/水位" not in decision.reasoning


def test_werewolf_speech_guard_allows_supporting_teammate_fake_seer_against_counterclaim():
    wolf = WerewolfAgent("player_4", "Eve")
    wolf.add_conversation("user", "Bob: 我是预言家，昨晚查验David是查杀。")
    wolf.add_conversation("user", "Frank: 我才是真预言家，昨晚首验David是金水。")

    async def fake_action(_game_state, _action_type, _extra_instructions=""):
        return AgentAction(
            reasoning="站边悍跳队友Bob，攻击Frank为对跳狼",
            speech="我是好人，我站边Bob。Frank后置对跳太急，我觉得Frank是悍跳狼，今天应该出Frank。",
        )

    wolf._call_llm_for_action = fake_action

    decision = asyncio.run(wolf.make_speech({
        "current_round": 1,
        "players": {
            "player_1": {"name": "Bob", "is_alive": True, "role": "werewolf"},
            "player_3": {"name": "David", "is_alive": True},
            "player_4": {"name": "Eve", "is_alive": True, "role": "werewolf"},
            "player_5": {"name": "Frank", "is_alive": True},
        },
    }))

    assert decision.raw_output == "我是好人，我站边Bob。Frank后置对跳太急，我觉得Frank是悍跳狼，今天应该出Frank。"
    assert "避免 D1 无硬证据攻击公开高身份/水位" not in decision.reasoning


def test_werewolf_speech_guard_rewrites_side_attacks_to_clean_teammate_fake_seer_support():
    wolf = WerewolfAgent("player_0", "Alice")
    wolf.add_conversation("user", "David: 我是女巫，昨晚救了Charlie，Charlie是银水。")
    wolf.add_conversation("user", "Frank: 我是普通村民，David女巫面高。")
    wolf.add_conversation("user", "Eve: 我是全场唯一真预言家，昨晚首验Frank是金水。")
    wolf.add_conversation("user", "Bob: 我对跳预言家，昨晚查验Eve是查杀。今天先出我的查杀Eve。")

    async def fake_action(_game_state, _action_type, _extra_instructions=""):
        return AgentAction(
            reasoning="站边悍跳队友Bob，但旁踩保护位",
            speech="我站边Bob，Eve是悍跳狼。David和Frank抱团也很可疑，今天可以一起打。",
        )

    wolf._call_llm_for_action = fake_action

    decision = asyncio.run(wolf.make_speech({
        "current_round": 1,
        "players": {
            "player_0": {"name": "Alice", "is_alive": True, "role": "werewolf"},
            "player_1": {"name": "Bob", "is_alive": True, "role": "werewolf"},
            "player_2": {"name": "Charlie", "is_alive": True},
            "player_3": {"name": "David", "is_alive": True},
            "player_4": {"name": "Eve", "is_alive": True},
            "player_5": {"name": "Frank", "is_alive": True},
        },
    }))

    assert "我站边Bob" in decision.raw_output
    assert "先出Eve" in decision.raw_output
    assert "票型不能散到外置位" in decision.raw_output
    assert "David" not in decision.raw_output
    assert "Frank" not in decision.raw_output
    assert "动作层队友支援" in decision.reasoning
    assert "避免 D1 无硬证据攻击公开高身份/水位" not in decision.reasoning


def test_werewolf_speech_guard_softens_early_teammate_fake_seer_support():
    wolf = WerewolfAgent("player_3", "David")
    wolf.add_conversation("user", "Alice: 我是全场铁好人，第一天没信息就不瞎打位置。")
    wolf.add_conversation(
        "user",
        "Charlie: 我是预言家，昨晚查验Bob是查杀。今天先在Bob和后面可能对跳的人里二选一。",
    )

    async def fake_action(_game_state, _action_type, _extra_instructions=""):
        return AgentAction(
            reasoning="队友已悍跳预言家，我站边他拉票",
            speech="我目前站边Charlie的预言家，他首验压缩灰区的逻辑没问题。今天先出查杀Bob，好人别乱分票。",
        )

    wolf._call_llm_for_action = fake_action

    decision = asyncio.run(wolf.make_speech({
        "current_round": 1,
        "players": {
            "player_1": {"name": "Bob", "is_alive": True},
            "player_2": {"name": "Charlie", "is_alive": True, "role": "werewolf"},
            "player_3": {"name": "David", "is_alive": True, "role": "werewolf"},
            "player_4": {"name": "Eve", "is_alive": True},
        },
    }))

    assert "先让Bob拍身份或者对跳" in decision.raw_output
    assert "不提前铁站边" in decision.raw_output
    assert "别散到外置位" in decision.raw_output
    assert "站边Charlie" not in decision.raw_output
    assert "动作层队友早期支援" in decision.reasoning


def test_werewolf_speech_guard_keeps_single_push_with_public_pressure():
    wolf = WerewolfAgent("player_0", "Alice")
    wolf.add_conversation("user", "Charlie: Bob发言比较划水，身份需要再听。")

    async def fake_action(_game_state, _action_type, _extra_instructions=""):
        return AgentAction(
            reasoning="跟随场上已有压力",
            speech="我是普通村民，Bob发言比较划水，我先轻压Bob，后面听完整一圈再定票。",
        )

    wolf._call_llm_for_action = fake_action

    decision = asyncio.run(wolf.make_speech({
        "current_round": 1,
        "players": {
            "player_0": {"name": "Alice", "is_alive": True, "role": "werewolf"},
            "player_1": {"name": "Bob", "is_alive": True},
            "player_2": {"name": "Charlie", "is_alive": True},
        },
    }))

    assert decision.raw_output == "我是普通村民，Bob发言比较划水，我先轻压Bob，后面听完整一圈再定票。"
    assert "避免 D1" not in decision.reasoning
