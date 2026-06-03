from backend.agents.base import BaseAgent, AgentAction
from backend.core.models import Role, AgentDecision


class SeerAgent(BaseAgent):
    def __init__(self, player_id, name):
        super().__init__(player_id, name, Role.SEER)
        self.check_results = {}

    def get_system_prompt(self):
        return """你是一个专业的狼人杀玩家，你的身份是【预言家】。

你的目标：
1. 每晚查验一个人的身份，找出狼人
2. 在合适的时机跳身份，报出你的查验结果
3. 带领好人阵营投票把狼人公投出局
4. 保护好自己，不要被狼人提前杀死

你的技能：
- 每晚可以查验一名玩家的身份（狼人/好人）
- 查验结果只有你自己知道

重要规则：
- 第一晚可以随机查验，之后优先查验发言可疑的人
- 可以选择在适当时机跳预言家身份，报出查杀或金水
- 如果已经查出狼人，要优先把狼人投出去
- 发言要有逻辑，分析场上局势"""

    async def make_night_action(self, game_state):
        alive_players = self._get_alive_players(game_state)
        
        unchecked = [p for p in alive_players if p["player_id"] not in self.check_results]
        if not unchecked:
            unchecked = alive_players
        
        check_str = "\n".join([f"- {pid}: {'狼人' if is_wolf else '好人'}" for pid, is_wolf in self.check_results.items()])
        if check_str:
            self.add_private_knowledge(f"已查验结果：\n{check_str}")
        
        extra_instructions = f"""你需要选择一名玩家进行查验。
已查验过的玩家：{list(self.check_results.keys())}
可选目标：{[p['name'] + ' (ID: ' + p['player_id'] + ')' for p in unchecked]}
请选择一个你最想查验身份的玩家，优先选择发言可疑的人。
在speech字段填写你的内心独白，在target_id字段填写目标玩家ID。"""
        
        action = await self._call_llm_for_action(game_state, "night_check", extra_instructions)
        
        target_id = action.target_id
        if target_id not in [p["player_id"] for p in unchecked]:
            target_id = unchecked[0]["player_id"]
        
        return AgentDecision(
            decision_type="check",
            target_id=target_id,
            reasoning=action.reasoning,
            raw_output=f"查验 {target_id}"
        )

    def add_check_result(self, player_id, is_werewolf):
        self.check_results[player_id] = is_werewolf
        result = "狼人" if is_werewolf else "好人"
        self.add_private_knowledge(f"查验结果：玩家 {player_id} 是 {result}")

    async def make_speech(self, game_state):
        check_str = "\n".join([f"- {pid}: {'狼人' if is_wolf else '好人'}" for pid, is_wolf in self.check_results.items()])
        if check_str:
            self.add_private_knowledge(f"已查验结果：\n{check_str}")
        
        extra_instructions = """现在是白天发言阶段。
请根据你的查验结果和场上局势发言。
如果有查杀，可以考虑跳预言家报查杀；如果有金水，可以报金水保护好人。
如果觉得时机不成熟，也可以先隐藏身份，观察局势。
发言要有逻辑，不要太简短，至少3句话。"""
        
        action = await self._call_llm_for_action(game_state, "day_speech", extra_instructions)
        
        return AgentDecision(
            decision_type="speech",
            reasoning=action.reasoning,
            raw_output=action.speech
        )

    async def make_vote(self, game_state):
        alive_players = self._get_alive_players(game_state)
        
        known_wolves = [p for p in alive_players if self.check_results.get(p["player_id"]) is True]
        targets = alive_players
        
        check_str = "\n".join([f"- {pid}: {'狼人' if is_wolf else '好人'}" for pid, is_wolf in self.check_results.items()])
        if check_str:
            self.add_private_knowledge(f"已查验结果：\n{check_str}")
        
        extra_instructions = f"""现在是投票阶段。
已确认的狼人：{[p['name'] for p in known_wolves]}
可选目标：{[p['name'] + ' (ID: ' + p['player_id'] + ')' for p in targets]}
如果有已确认的狼人，优先投票给狼人；否则投票给最可疑的人。
在speech字段填写投票理由，在target_id字段填写目标玩家ID。"""
        
        action = await self._call_llm_for_action(game_state, "vote", extra_instructions)
        
        target_id = action.target_id
        
        if known_wolves:
            if target_id not in [p["player_id"] for p in known_wolves]:
                target_id = known_wolves[0]["player_id"]
        else:
            if target_id not in [p["player_id"] for p in targets]:
                target_id = targets[0]["player_id"]
        
        return AgentDecision(
            decision_type="vote",
            target_id=target_id,
            reasoning=action.reasoning,
            raw_output=action.speech
        )
