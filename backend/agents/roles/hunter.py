from backend.agents.base import BaseAgent, AgentAction
from backend.core.models import Role, AgentDecision


class HunterAgent(BaseAgent):
    def __init__(self, player_id, name):
        super().__init__(player_id, name, Role.HUNTER)
        self.has_shot = False

    def get_system_prompt(self):
        return """你是一个专业的狼人杀玩家，你的身份是【猎人】。

你的目标：
1. 帮助好人阵营找出狼人并获胜
2. 如果你死亡，可以开枪带走一名玩家
3. 可以选择跳身份来威慑狼人

你的技能：
- 当你死亡时（被狼人杀死或被公投出局），可以开枪带走一名玩家
- 但如果你是被女巫毒死的，则不能开枪

重要规则：
- 可以根据局势决定是否跳猎人身份
- 绝对禁止自称预言家或女巫；猎人没有查验、银水或毒药信息
- 如果跳身份，可以威慑狼人不敢轻易杀你
- 死亡时，优先带走你认为最可能是狼人的玩家
- 发言要有逻辑，分析场上局势"""

    async def make_night_action(self, game_state):
        return AgentDecision(
            decision_type="no_action",
            reasoning="猎人没有夜间行动",
            raw_output=""
        )

    async def make_shot(self, game_state):
        alive_players = self._get_alive_players(game_state)
        
        self.add_private_knowledge(f"已开枪：{self.has_shot}")
        
        if not alive_players:
            return AgentDecision(
                decision_type="shot",
                target_id=None,
                reasoning="没有可开枪的目标",
                raw_output=""
            )
        
        extra_instructions = f"""你死了，现在可以开枪带走一名玩家。
可选目标：{[p['name'] + ' (ID: ' + p['player_id'] + ')' for p in alive_players]}
请选择你认为最可能是狼人的玩家带走。
在speech字段填写开枪理由，在target_id字段填写目标玩家ID。"""
        
        action = await self._call_llm_for_action(game_state, "death_shot", extra_instructions)
        
        target_id = action.target_id
        if target_id not in [p["player_id"] for p in alive_players]:
            target_id = alive_players[0]["player_id"]
        
        self.has_shot = True
        
        return AgentDecision(
            decision_type="shot",
            target_id=target_id,
            reasoning=action.reasoning,
            raw_output=action.speech
        )

    async def make_speech(self, game_state):
        self.add_private_knowledge(f"已开枪：{self.has_shot}")
        
        extra_instructions = """现在是白天发言阶段。
请根据场上局势发言。
可以选择跳猎人身份来威慑狼人，也可以隐藏身份。
禁止跳预言家，禁止编造查验、金水或查杀。
发言要有逻辑，不要太简短，至少3句话。"""
        
        action = await self._call_llm_for_action(game_state, "day_speech", extra_instructions)
        
        return AgentDecision(
            decision_type="speech",
            reasoning=action.reasoning,
            raw_output=action.speech
        )

    async def make_vote(self, game_state):
        alive_players = self._get_alive_players(game_state)
        
        self.add_private_knowledge(f"已开枪：{self.has_shot}")
        
        extra_instructions = f"""现在是投票阶段。
可选目标：{[p['name'] + ' (ID: ' + p['player_id'] + ')' for p in alive_players]}
请投票给最可疑的狼人玩家。
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
