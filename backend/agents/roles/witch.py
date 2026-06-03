from backend.agents.base import BaseAgent, AgentAction
from backend.core.models import Role, AgentDecision


class WitchAgent(BaseAgent):
    def __init__(self, player_id, name):
        super().__init__(player_id, name, Role.WITCH)
        self.has_used_save = False
        self.has_used_poison = False
        self.last_night_kill = None

    def get_system_prompt(self):
        return """你是一个专业的狼人杀玩家，你的身份是【女巫】。

你的目标：
1. 利用解药和毒药帮助好人阵营获胜
2. 解药可以救起被狼人杀死的玩家
3. 毒药可以毒死一名玩家
4. 在合适的时机跳身份，带领好人阵营

你的技能：
- 一瓶解药：可以救起被狼人杀死的玩家（包括自己）
- 一瓶毒药：可以毒死一名玩家
- 你知道每晚狼人杀了谁
- 解药和毒药各只能使用一次

重要规则：
- 解药优先救自己或明显的好人
- 毒药留给确认的狼人
- 不要轻易使用毒药，避免误杀好人
- 可以根据局势决定是否跳身份
- 发言要有逻辑，分析场上局势"""

    def set_night_kill(self, victim_id):
        self.last_night_kill = victim_id
        if victim_id:
            self.add_private_knowledge(f"今晚狼人要杀的玩家是：{victim_id}")

    async def make_night_action(self, game_state):
        alive_players = self._get_alive_players(game_state)
        
        self.add_private_knowledge(f"解药已使用：{self.has_used_save}")
        self.add_private_knowledge(f"毒药已使用：{self.has_used_poison}")
        
        if not self.has_used_save and self.last_night_kill:
            victim_name = next((p["name"] for p in game_state.get("players", {}).values() if p.get("player_id") == self.last_night_kill), self.last_night_kill)
            extra_instructions = f"""今晚狼人要杀的玩家是：{victim_name} (ID: {self.last_night_kill})
你的解药还没有使用，你可以选择救他，也可以选择不救。
可选操作：
1. 使用解药救人：decision_type="save", target_id={self.last_night_kill}
2. 不使用解药，选择用毒药（如果毒药还在）：decision_type="poison", target_id=某个玩家
3. 什么都不做：decision_type="do_nothing", target_id=null
请根据局势做出决策。
在speech字段填写你的内心独白，在target_id字段填写目标玩家ID（如果需要）。
在reasoning字段说明你的决策类型（save/poison/do_nothing）。"""
            
            action = await self._call_llm_for_action(game_state, "night_action", extra_instructions)
            
            decision_type = action.reasoning.lower()
            
            if "save" in decision_type and self.last_night_kill:
                return AgentDecision(
                    decision_type="save",
                    target_id=self.last_night_kill,
                    reasoning=action.reasoning,
                    raw_output=f"救 {self.last_night_kill}"
                )
            elif "poison" in decision_type and not self.has_used_poison and action.target_id:
                if action.target_id in [p["player_id"] for p in alive_players]:
                    return AgentDecision(
                        decision_type="poison",
                        target_id=action.target_id,
                        reasoning=action.reasoning,
                        raw_output=f"毒 {action.target_id}"
                    )
        
        if not self.has_used_poison and alive_players:
            extra_instructions = f"""你的毒药还没有使用，你可以选择毒死一名玩家。
可选目标：{[p['name'] + ' (ID: ' + p['player_id'] + ')' for p in alive_players]}
也可以选择什么都不做，保留毒药。
请根据局势做出决策。
在speech字段填写你的内心独白，在target_id字段填写目标玩家ID（如果需要）。
在reasoning字段说明你的决策类型（poison/do_nothing）。"""
            
            action = await self._call_llm_for_action(game_state, "night_poison", extra_instructions)
            
            decision_type = action.reasoning.lower()
            
            if "poison" in decision_type and action.target_id:
                if action.target_id in [p["player_id"] for p in alive_players]:
                    return AgentDecision(
                        decision_type="poison",
                        target_id=action.target_id,
                        reasoning=action.reasoning,
                        raw_output=f"毒 {action.target_id}"
                    )
        
        return AgentDecision(
            decision_type="do_nothing",
            target_id=None,
            reasoning="不使用任何技能",
            raw_output=""
        )

    def use_save(self):
        self.has_used_save = True
        self.add_private_knowledge("已使用解药")

    def use_poison(self):
        self.has_used_poison = True
        self.add_private_knowledge("已使用毒药")

    async def make_speech(self, game_state):
        self.add_private_knowledge(f"解药已使用：{self.has_used_save}")
        self.add_private_knowledge(f"毒药已使用：{self.has_used_poison}")
        
        extra_instructions = """现在是白天发言阶段。
请根据场上局势发言。
可以选择跳女巫身份，也可以隐藏身份。
发言要有逻辑，不要太简短，至少3句话。"""
        
        action = await self._call_llm_for_action(game_state, "day_speech", extra_instructions)
        
        return AgentDecision(
            decision_type="speech",
            reasoning=action.reasoning,
            raw_output=action.speech
        )

    async def make_vote(self, game_state):
        alive_players = self._get_alive_players(game_state)
        
        self.add_private_knowledge(f"解药已使用：{self.has_used_save}")
        self.add_private_knowledge(f"毒药已使用：{self.has_used_poison}")
        
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
