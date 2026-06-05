from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field
from backend.core.models import Role, AgentDecision
from backend.core.config import settings


class AgentAction(BaseModel):
    decision_type: Optional[str] = Field(default=None, description="动作类型，例如run/stay/retreat/vote等")
    target_id: Optional[str] = Field(default=None, description="目标玩家ID，如果没有则为null")
    reasoning: str = Field(description="决策推理过程")
    speech: str = Field(description="发言内容")
    will_retreat: Optional[bool] = Field(default=False, description="是否退水（仅警长竞选阶段）")
    speak_direction: Optional[str] = Field(default="left", description="发言方向（left/right，仅警长）")


class BaseAgent(ABC):
    def __init__(self, player_id: str, name: str, role: Role):
        self.player_id = player_id
        self.name = name
        self.role = role
        self.system_prompt_override: Optional[str] = None
        self.llm = ChatOpenAI(
            api_key=settings.DOUBAO_API_KEY,
            base_url=settings.DOUBAO_BASE_URL,
            model=settings.DOUBAO_MODEL,
            temperature=0.8,
            timeout=settings.LLM_TIMEOUT,
            max_retries=settings.LLM_MAX_RETRIES,
            max_tokens=settings.LLM_MAX_TOKENS,
        )
        self.conversation_history: List[Dict[str, str]] = []
        self.private_knowledge: List[str] = []

    @abstractmethod
    def get_system_prompt(self) -> str:
        pass

    def set_system_prompt_override(self, prompt: Optional[str]):
        self.system_prompt_override = prompt

    def get_effective_system_prompt(self) -> str:
        return self.system_prompt_override or self.get_system_prompt()

    @abstractmethod
    async def make_night_action(self, game_state: Dict[str, Any]) -> AgentDecision:
        pass

    @abstractmethod
    async def make_speech(self, game_state: Dict[str, Any]) -> AgentDecision:
        pass

    @abstractmethod
    async def make_vote(self, game_state: Dict[str, Any]) -> AgentDecision:
        pass

    async def make_sheriff_election(self, game_state: Dict[str, Any]) -> AgentDecision:
        """决定是否上警"""
        extra_instructions = """现在是警长竞选阶段。
请决定是否要上警竞选警长。
返回结果中：
- decision_type="run" 表示上警
- decision_type="stay" 表示不上警
在speech字段填写你的内心独白。"""
        
        action = await self._call_llm_for_action(game_state, "sheriff_election", extra_instructions)
        
        explicit_decision = (action.decision_type or "").lower()
        if explicit_decision in {"run", "stay"}:
            decision_type = explicit_decision
        else:
            decision_text = f"{action.reasoning} {action.speech}".lower()
            if any(phrase in decision_text for phrase in ["不上警", "不 上警", "不竞选警长", "不参与竞选", "留警下", "待在警下"]):
                decision_type = "stay"
            elif "run" in decision_text or "上警" in decision_text or "竞选警长" in decision_text:
                decision_type = "run"
            else:
                decision_type = "stay"

        if decision_type == "run":
            return AgentDecision(
                decision_type="run",
                target_id=None,
                reasoning=action.reasoning,
                raw_output=action.speech
            )
        else:
            return AgentDecision(
                decision_type="stay",
                target_id=None,
                reasoning=action.reasoning,
                raw_output=action.speech
            )

    async def make_sheriff_speech(self, game_state: Dict[str, Any]) -> AgentDecision:
        """警上发言"""
        extra_instructions = """现在是警上发言阶段。
你在警上竞选警长，请发表竞选宣言。
发言要有说服力，争取警下玩家的投票。
发言要有逻辑，不要太简短，至少3句话。"""
        
        action = await self._call_llm_for_action(game_state, "sheriff_speech", extra_instructions)
        
        return AgentDecision(
            decision_type="speech",
            reasoning=action.reasoning,
            raw_output=action.speech
        )

    async def make_retreat(self, game_state: Dict[str, Any]) -> AgentDecision:
        """决定是否退水"""
        extra_instructions = """警上发言结束，现在是退水阶段。
请决定是否继续留在警上竞选警长，还是退水。
返回结果中：
- decision_type="stay" 表示继续留在警上
- decision_type="retreat" 表示退水
在speech字段填写你的内心独白。"""
        
        action = await self._call_llm_for_action(game_state, "sheriff_retreat", extra_instructions)
        
        explicit_decision = (action.decision_type or "").lower()
        if explicit_decision in {"retreat", "stay"}:
            decision_type = explicit_decision
        else:
            decision_text = f"{action.reasoning} {action.speech}".lower()
            if any(phrase in decision_text for phrase in ["不退水", "不 退水", "不选择退水", "继续留", "留在警上"]):
                decision_type = "stay"
            elif "retreat" in decision_text or "退水" in decision_text:
                decision_type = "retreat"
            else:
                decision_type = "stay"

        if decision_type == "retreat":
            return AgentDecision(
                decision_type="retreat",
                target_id=None,
                reasoning=action.reasoning,
                raw_output=action.speech
            )
        else:
            return AgentDecision(
                decision_type="stay",
                target_id=None,
                reasoning=action.reasoning,
                raw_output=action.speech
            )

    async def make_sheriff_vote(self, game_state: Dict[str, Any]) -> AgentDecision:
        """警下投票"""
        alive_players = self._get_alive_players(game_state)
        
        candidates = [p for p in alive_players if game_state.get("players", {}).get(p["player_id"], {}).get("in_sheriff_election")]
        
        if not candidates:
            return AgentDecision(
                decision_type="abstain",
                target_id=None,
                reasoning="没有候选人",
                raw_output="弃权"
            )
        
        extra_instructions = f"""现在是警长投票阶段。
你在警下，需要投票给警上的玩家。
可选候选人：{[p['name'] + ' (ID: ' + p['player_id'] + ')' for p in candidates]}
请投票给你认为最适合当警长的玩家。
在speech字段填写投票理由，在target_id字段填写目标玩家ID。"""
        
        action = await self._call_llm_for_action(game_state, "sheriff_vote", extra_instructions)
        
        target_id = action.target_id
        if target_id not in [p["player_id"] for p in candidates]:
            target_id = candidates[0]["player_id"]
        
        return AgentDecision(
            decision_type="vote",
            target_id=target_id,
            reasoning=action.reasoning,
            raw_output=action.speech
        )

    async def make_pk_speech(self, game_state: Dict[str, Any]) -> AgentDecision:
        """PK发言"""
        extra_instructions = """现在是PK发言阶段。
你和其他玩家平票，需要进行PK发言争取更多选票。
请发表有说服力的PK发言。
发言要有逻辑，不要太简短，至少3句话。"""
        
        action = await self._call_llm_for_action(game_state, "pk_speech", extra_instructions)
        
        return AgentDecision(
            decision_type="speech",
            reasoning=action.reasoning,
            raw_output=action.speech
        )

    async def make_speak_direction(self, game_state: Dict[str, Any]) -> AgentDecision:
        """警长决定发言方向"""
        extra_instructions = """你是警长，现在需要决定发言方向。
请选择从你的左边还是右边开始发言。
返回结果中：
- decision_type="left" 表示从左边开始
- decision_type="right" 表示从右边开始
在speech字段填写你的理由。"""
        
        action = await self._call_llm_for_action(game_state, "speak_direction", extra_instructions)
        
        decision_type = action.reasoning.lower()
        if "right" in decision_type or "右边" in action.speech:
            return AgentDecision(
                decision_type="right",
                target_id=None,
                reasoning=action.reasoning,
                raw_output=action.speech
            )
        else:
            return AgentDecision(
                decision_type="left",
                target_id=None,
                reasoning=action.reasoning,
                raw_output=action.speech
            )
    
    async def make_last_words(self, game_state: Dict[str, Any]) -> AgentDecision:
        """遗言阶段发言"""
        extra_instructions = """你已经死了，现在是遗言阶段。
请发表你的遗言，不要再提投票、警徽流这些游戏过程中的内容，因为游戏已经到了你的遗言时刻。
遗言可以聊聊你的身份，或者给场上玩家一些建议和分析。"""
        
        action = await self._call_llm_for_action(game_state, "last_words", extra_instructions)
        
        return AgentDecision(
            decision_type="speech",
            reasoning=action.reasoning,
            raw_output=action.speech
        )

    async def make_sheriff_death_decision(self, game_state: Dict[str, Any]) -> AgentDecision:
        """警长死亡时处理警徽"""
        alive_players = self._get_alive_players(game_state)
        
        if not alive_players:
            return AgentDecision(
                decision_type="destroy",
                target_id=None,
                reasoning="没有存活玩家可以移交警徽",
                raw_output="撕掉警徽"
            )
        
        extra_instructions = f"""你是警长，现在你死了，需要决定如何处理警徽。
你可以选择：
1. 将警徽移交给任意一名存活玩家
2. 撕掉警徽，本局不再有警长

可选移交目标：{[p['name'] + ' (ID: ' + p['player_id'] + ')' for p in alive_players]}
如果选择移交，target_id填写目标玩家ID，decision_type填"pass"
如果选择撕掉警徽，target_id填null，decision_type填"destroy"
在speech字段填写你的决定理由。"""
        
        action = await self._call_llm_for_action(game_state, "sheriff_death", extra_instructions)
        
        target_id = action.target_id
        if target_id and target_id not in [p["player_id"] for p in alive_players]:
            target_id = alive_players[0]["player_id"]
        
        # 从 reasoning 中推断 decision_type
        decision_type = "destroy"
        if action.reasoning and "pass" in action.reasoning.lower() and target_id:
            decision_type = "pass"
        
        return AgentDecision(
            decision_type=decision_type,
            target_id=target_id,
            reasoning=action.reasoning,
            raw_output=action.speech
        )

    def add_private_knowledge(self, knowledge: str):
        self.private_knowledge.append(knowledge)

    def add_conversation(self, role: str, content: str):
        self.conversation_history.append({"role": role, "content": content})

    def _get_alive_players(self, game_state: Dict[str, Any]) -> List[Dict[str, Any]]:
        players = game_state.get("players", {})
        alive = []
        for pid, p in players.items():
            if p.get("is_alive") and pid != self.player_id:
                alive.append({
                    "player_id": pid,
                    "name": p.get("name"),
                    "role": p.get("role")
                })
        return alive

    def _format_game_state(self, game_state: Dict[str, Any]) -> str:
        players = game_state.get("players", {})
        player_list = []
        for pid, p in players.items():
            status = "存活" if p.get("is_alive") else "死亡"
            role_info = f" (角色: {p.get('role')})" if p.get("role") else ""
            sheriff_info = " [警长]" if p.get("is_sheriff") else ""
            in_election = " [警上]" if p.get("in_sheriff_election") else ""
            player_list.append(f"- {p.get('name')} (ID: {pid}): {status}{role_info}{sheriff_info}{in_election}")
        
        history_str = "\n".join([f"{msg['role']}: {msg['content']}" for msg in self.conversation_history[-30:]])
        
        private_knowledge_str = "\n".join(self.private_knowledge) if self.private_knowledge else "无"
        
        sheriff_info = f"当前警长: {game_state.get('sheriff_id', '无')}" if game_state.get('sheriff_id') else "当前警长: 无"
        
        phase_description = ""
        phase = game_state.get('current_phase', '')
        if phase == 'night':
            phase_description = "（夜晚阶段，夜间行动中）"
        elif phase == 'sheriff_election':
            phase_description = "（警长竞选阶段，决定是否上警）"
        elif phase == 'sheriff_speech':
            phase_description = "（警上发言阶段）"
        elif phase == 'sheriff_retreat':
            phase_description = "（退水阶段）"
        elif phase == 'sheriff_vote':
            phase_description = "（警长投票阶段）"
        elif phase == 'sheriff_pk':
            phase_description = "（PK发言阶段）"
        elif phase == 'day':
            phase_description = "（白天发言阶段，请注意这是普通的白天发言，不是警上发言！）"
        elif phase == 'voting':
            phase_description = "（放逐投票阶段）"
        elif phase == 'defense':
            phase_description = "（遗言阶段）"
        elif phase == 'game_over':
            phase_description = "（游戏结束）"
        
        return f"""游戏状态：
当前回合: {game_state.get('current_round', 1)}
当前阶段: {game_state.get('current_phase')} {phase_description}
{sheriff_info}
玩家列表：
{chr(10).join(player_list)}

对话历史（最近30条）：
{history_str}

你的私人信息：
{private_knowledge_str}"""

    async def _call_llm_for_action(self, game_state: Dict[str, Any], action_type: str, extra_instructions: str = "") -> AgentAction:
        parser = JsonOutputParser(pydantic_object=AgentAction)
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", self.get_effective_system_prompt()),
            ("system", "你需要根据游戏状态做出决策。请以JSON格式输出，格式如下：\n{format_instructions}"),
            ("system", "回答必须简短，只输出JSON对象；reasoning和speech都控制在80个中文字符以内。"),
            ("user", "{game_state}\n\n当前需要做出的决策类型：{action_type}\n{extra_instructions}")
        ])
        
        chain = prompt | self.llm | parser
        
        try:
            result = await chain.ainvoke({
                "game_state": self._format_game_state(game_state),
                "action_type": action_type,
                "extra_instructions": extra_instructions,
                "format_instructions": parser.get_format_instructions()
            })
            return AgentAction(**result)
        except Exception as e:
            print(f"LLM调用失败: {e}")
            return AgentAction(
                target_id=None,
                reasoning="LLM调用失败，使用默认策略",
                speech="我是好人",
                will_retreat=False,
                speak_direction="left"
            )
