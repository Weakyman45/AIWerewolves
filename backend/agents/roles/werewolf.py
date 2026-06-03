from backend.agents.base import BaseAgent, AgentAction
from backend.core.models import Role, AgentDecision


class WerewolfAgent(BaseAgent):
    def __init__(self, player_id, name):
        super().__init__(player_id, name, Role.WEREWOLF)

    def get_system_prompt(self):
        return """你是一个专业的狼人杀玩家，你的身份是【狼人】。

你的目标：
1. 隐藏自己的狼人身份，伪装成好人
2. 在夜晚杀死好人阵营的玩家（预言家、女巫、猎人、村民）
3. 在白天引导投票，把好人公投出局
4. 保护你的狼人队友，不要攻击他们

你的技能：
- 每晚可以杀死一名玩家
- 你能看到其他狼人的身份

重要规则：
- 绝对不能杀死你的狼人队友！
- 优先击杀神牌（预言家、女巫、猎人）
- 白天发言要装作好人，不要暴露身份
- 绝对不能说自己是其他玩家的名字，也不能冒充其他具体玩家的身份
- 绝对不能暴露其他狼人的身份，也不要提到其他狼人的名字
- 可以适当跳预言家或其他神职来搅局
- 观察其他玩家的发言，找出最可疑的人来投票
- 你可以在白天发言阶段选择自爆，自爆后你会直接死亡，当前白天立即结束进入黑夜，你没有遗言"""

    async def make_night_action(self, game_state):
        alive_players = self._get_alive_players(game_state)
        
        teammates = [p for p in alive_players if p.get("role") == "werewolf"]
        targets = [p for p in alive_players if p.get("role") != "werewolf"]
        
        if not targets:
            return AgentDecision(
                decision_type="kill",
                target_id=None,
                reasoning="没有可击杀的目标",
                raw_output=""
            )
        
        extra_instructions = f"""你需要选择一名玩家在夜晚击杀。
你的狼人队友（绝对不能杀）：{[p['name'] for p in teammates]}
可选目标（只能从这些人中选择）：{[p['name'] + ' (ID: ' + p['player_id'] + ')' for p in targets]}
请选择一个最有可能是神牌（预言家、女巫、猎人）的目标。
在speech字段填写你的内心独白，在target_id字段填写目标玩家ID。"""
        
        action = await self._call_llm_for_action(game_state, "night_kill", extra_instructions)
        
        target_id = action.target_id
        if target_id not in [p["player_id"] for p in targets]:
            target_id = targets[0]["player_id"]
        
        return AgentDecision(
            decision_type="kill",
            target_id=target_id,
            reasoning=action.reasoning,
            raw_output=f"击杀 {target_id}"
        )

    async def make_speech(self, game_state):
        extra_instructions = """现在是白天发言阶段，轮到你发言了。
你可以选择正常发言，或者选择自爆。
如果自爆：你会直接死亡，当前白天立即结束进入黑夜，你没有遗言。
如果发言：你需要伪装成好人，分析场上局势，不要暴露狼人身份。可以适当怀疑其他人，或者跳一个神职身份来搅局。发言要有逻辑，不要太简短，至少3句话。

返回结果：
- 如果选择自爆，decision_type填"bomb"，speech字段填"我自爆"
- 如果选择正常发言，decision_type填"speech"，speech字段填你的发言内容
在reasoning字段填写你的理由。"""
        
        action = await self._call_llm_for_action(game_state, "day_speech", extra_instructions)
        
        # 从reasoning推断decision_type
        decision_type = "speech"
        if action.reasoning and "bomb" in action.reasoning.lower():
            decision_type = "bomb"
        
        return AgentDecision(
            decision_type=decision_type,
            target_id=None,
            reasoning=action.reasoning,
            raw_output=action.speech
        )

    async def make_bomb_decision(self, game_state):
        """决定是否自爆"""
        extra_instructions = """现在是白天发言阶段，你可以选择是否自爆。
如果你认为场上局势对狼人不利，或者你想保护狼队友，可以选择自爆。
自爆后你会直接死亡，当前白天立即结束进入黑夜，你没有遗言。
返回结果：
- decision_type="bomb" 表示自爆
- decision_type="no_bomb" 表示不自爆
在speech字段填写你的理由。"""
        
        action = await self._call_llm_for_action(game_state, "bomb_decision", extra_instructions)
        
        # 从reasoning推断decision_type
        decision_type = "no_bomb"
        if action.reasoning and "bomb" in action.reasoning.lower():
            decision_type = "bomb"
        
        return AgentDecision(
            decision_type=decision_type,
            target_id=None,
            reasoning=action.reasoning,
            raw_output=action.speech
        )

    async def make_vote(self, game_state):
        alive_players = self._get_alive_players(game_state)
        
        teammates = [p for p in alive_players if p.get("role") == "werewolf"]
        targets = [p for p in alive_players if p.get("role") != "werewolf"]
        
        if not targets:
            return AgentDecision(
                decision_type="vote",
                target_id=None,
                reasoning="没有可投票的目标",
                raw_output=""
            )
        
        extra_instructions = f"""现在是投票阶段。
你需要投票给一名好人玩家，把他公投出局。
你的狼人队友（绝对不能投）：{[p['name'] for p in teammates]}
可选目标（只能从这些人中选择）：{[p['name'] + ' (ID: ' + p['player_id'] + ')' for p in targets]}
请选择一个最可疑或最容易被公投出去的目标。
在speech字段填写投票理由，在target_id字段填写目标玩家ID。"""
        
        action = await self._call_llm_for_action(game_state, "vote", extra_instructions)
        
        target_id = action.target_id
        if target_id not in [p["player_id"] for p in targets]:
            target_id = targets[0]["player_id"]
        
        return AgentDecision(
            decision_type="vote",
            target_id=target_id,
            reasoning=action.reasoning,
            raw_output=action.speech
        )
