from backend.agents.base import BaseAgent, AgentAction
from backend.core.models import Role, AgentDecision


class VillagerAgent(BaseAgent):
    def __init__(self, player_id, name):
        super().__init__(player_id, name, Role.VILLAGER)

    def get_system_prompt(self):
        return """你是一个专业的狼人杀玩家，你的身份是【村民】。

你的目标：
1. 帮助好人阵营找出狼人并获胜
2. 通过发言和投票找出狼人
3. 保护好自己，不要被狼人杀死或被公投出局

你的技能：
- 没有特殊技能，只能通过发言和投票来游戏

重要规则：
- 仔细听取其他玩家的发言，分析谁最可能是狼人
- 绝对禁止自称预言家、女巫或猎人；你没有查验、银水、毒药、枪口等夜间信息
- 跟着好人阵营的思路投票
- 发言要有逻辑，分析场上局势，至少3句话"""

    async def make_night_action(self, game_state):
        return AgentDecision(
            decision_type="no_action",
            reasoning="村民没有夜间行动",
            raw_output=""
        )

    async def make_speech(self, game_state):
        extra_instructions = """现在是白天发言阶段。
请根据场上局势发言，分析谁最可能是狼人。
作为村民，只能以平民/闭眼好人视角发言；禁止跳预言家，禁止编造查验、金水或查杀。
发言要有逻辑，不要太简短，至少3句话。"""
        
        action = await self._call_llm_for_action(game_state, "day_speech", extra_instructions)
        
        return AgentDecision(
            decision_type="speech",
            reasoning=action.reasoning,
            raw_output=action.speech
        )

    async def make_vote(self, game_state):
        alive_players = self._get_alive_players(game_state)
        
        extra_instructions = f"""现在是投票阶段。
可选目标：{[p['name'] + ' (ID: ' + p['player_id'] + ')' for p in alive_players]}
请投票给你认为最可疑的狼人玩家。
在speech字段填写投票理由，在target_id字段填写目标玩家ID。"""
        
        action = await self._call_llm_for_action(game_state, "vote", extra_instructions)
        
        target_id = action.target_id
        if target_id not in [p["player_id"] for p in alive_players]:
            target_id = alive_players[0]["player_id"]
        
        return AgentDecision(
            decision_type="vote",
            target_id=target_id,
            reasoning=action.reasoning,
            raw_output=action.speech
        )
