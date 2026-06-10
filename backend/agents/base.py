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
            timeout=max(settings.LLM_TIMEOUT, 120),
            max_retries=max(settings.LLM_MAX_RETRIES, 1),
            max_tokens=max(settings.LLM_MAX_TOKENS, 768),
        )
        self.conversation_history: List[Dict[str, str]] = []
        self.private_knowledge: List[str] = []
        self.public_claim: Optional[str] = None
        self.can_fake_seer = False
        self.llm_failure_count = 0
        self.llm_failure_errors: List[str] = []

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

        if self.role == Role.WEREWOLF:
            if self.can_fake_seer:
                decision_type = "run"
                action.reasoning = f"{action.reasoning}；本局唯一授权悍跳狼必须上警承担对跳位"
            else:
                decision_type = "stay"
                action.reasoning = f"{action.reasoning}；本局未被授权悍跳，狼人不能上警冒充预言家"

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
        if self.role == Role.SEER:
            role_instructions = "你是预言家，必须清楚报出真实查验、首验理由和警徽流。"
        elif self.role == Role.WEREWOLF:
            if self.can_fake_seer:
                role_instructions = "你是本局唯一被授权悍跳的狼人，可以伪装预言家，但发言必须前后一致，不能冒充其他具体玩家。"
            else:
                role_instructions = (
                    "你是狼人，但本局没有被授权悍跳预言家。必须以普通好人/闭眼好人视角发言；"
                    "绝对不能自称预言家、女巫或猎人，不能编造查验、金水、银水、查杀或枪口。"
                    "如果讨论预言家，只能引用别人公开声称的查验和警徽流，不能使用第一人称查验表达。"
                )
        else:
            role_instructions = (
                "你可以上警表达警徽票标准或争取带队，但不能自称预言家，不能编造查验、金水或查杀。"
                "如果讨论预言家，只能引用别人公开声称的查验和警徽流，不能使用第一人称查验表达。"
                "重点评价前面已经发过言的玩家、预言家声称、查验力度、警徽流是否自洽；"
                "如果前面没人发言，就说明自己的警徽票判断标准和后续会重点听什么。"
            )
        extra_instructions = """现在是警上发言阶段。
你在警上竞选警长，请发表竞选宣言。
发言要有说服力，争取警下玩家的投票。
发言要有逻辑，不要太简短，至少3句话。
{role_instructions}""".format(role_instructions=role_instructions)
        
        action = await self._call_llm_for_action(game_state, "sheriff_speech", extra_instructions)
        
        return AgentDecision(
            decision_type="speech",
            reasoning=action.reasoning,
            raw_output=action.speech
        )

    async def make_retreat(self, game_state: Dict[str, Any]) -> AgentDecision:
        """决定是否退水"""
        if self.public_claim == "seer":
            return AgentDecision(
                decision_type="stay",
                target_id=None,
                reasoning="已经公开跳预言家，退水会造成身份前后矛盾",
                raw_output="我已经跳了预言家并交过验人逻辑，这里不会退水。好人继续对比我的警徽流、查验和对跳发言，把警徽票集中给真预言家。"
            )

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

        if self.public_claim == "seer" and decision_type == "retreat":
            decision_type = "stay"
            action.reasoning = f"{action.reasoning}；已公开跳预言家，禁止退水改口"
            action.speech = "我已经公开跳预言家，这里不退水。请警下继续对比我的查验、警徽流和对跳发言，把票集中给真预言家。"

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
        
        explicit_decision = (action.decision_type or "").lower()
        if explicit_decision in {"left", "right"}:
            direction = explicit_decision
        else:
            decision_text = f"{action.reasoning} {action.speech}".lower()
            if any(phrase in decision_text for phrase in ["right", "右边", "右侧", "从右"]):
                direction = "right"
            else:
                direction = "left"

        if direction == "right":
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
        
        explicit_decision = (action.decision_type or "").lower()
        decision_text = f"{action.reasoning or ''} {action.speech or ''}".lower()
        wants_destroy = any(
            keyword in decision_text
            for keyword in ["destroy", "撕掉", "撕毁", "撕警徽", "警徽流失", "不再有警长"]
        )
        wants_pass = bool(target_id) and any(
            keyword in decision_text
            for keyword in ["pass", "移交", "传给", "交给", "警徽给", "给"]
        )
        
        if target_id and (explicit_decision == "pass" or wants_pass) and not wants_destroy:
            decision_type = "pass"
        elif explicit_decision == "destroy" or wants_destroy:
            decision_type = "destroy"
        elif target_id:
            decision_type = "pass"
        else:
            decision_type = "destroy"
        
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
        if role == "user" and content.startswith(f"{self.name}:"):
            claim = self._infer_public_claim(content.split(":", 1)[1])
            if claim:
                self.public_claim = claim

    def _infer_public_claim(self, speech: str) -> Optional[str]:
        compact = speech.replace(" ", "")
        seer_claim_markers = [
            "我是预言家",
            "我是真预言家",
            "我是唯一真预言家",
            "我是全场唯一真预言家",
            "我才是预言家",
            "我才是真预言家",
            "我才是唯一真预言家",
            "我才是全场唯一真预言家",
            "我跳预言家",
            "我起跳预言家",
            "我对跳预言家",
            "底牌是预言家",
            "底牌预言家",
            "我的身份是预言家",
        ]
        if any(marker in compact for marker in seer_claim_markers):
            return "seer"
        if "女巫" in speech and any(marker in speech for marker in ["我是", "跳", "真女巫"]):
            return "witch"
        if "猎人" in speech and any(marker in speech for marker in ["我是", "跳", "真猎人"]):
            return "hunter"
        if any(marker in speech for marker in ["我是平民", "我是村民", "我是普通村民", "我是闭眼好人", "我是无信息好人", "普通好人"]):
            return "villager"
        return None

    def _is_illegal_nonseer_seer_claim(self, speech: str) -> bool:
        if self.role == Role.SEER:
            return False
        if self.role == Role.WEREWOLF and self.can_fake_seer:
            return False

        compact = speech.replace(" ", "")
        direct_seer_claim = "预言家" in compact and any(
            marker in compact
            for marker in [
                "我是预言家",
                "我才是预言家",
                "我是真预言家",
                "我才是真预言家",
                "全场唯一真预言家",
                "起跳预言家",
                "跳预言家",
                "对跳预言家",
            ]
        )
        fake_check = any(
            marker in compact
            for marker in [
                "我验了",
                "我验的",
                "我验过",
                "我昨夜验",
                "我昨晚验",
                "昨夜我验",
                "昨晚我验",
                "我的查验",
                "我查验",
            ]
        ) and any(result in compact for result in ["查杀", "金水", "狼人", "好人"])
        return direct_seer_claim or fake_check

    def _role_consistent_speech_repair(self, game_state: Dict[str, Any], action_type: str) -> str:
        focus_names = (
            self._sheriff_speech_focus_names()
            if action_type == "sheriff_speech"
            else self._fallback_focus_names(game_state)
        )
        first = focus_names[0] if focus_names else "前置位"
        if len(focus_names) > 1:
            focus_clause = f"{first}和{focus_names[1]}谁在回避预言家真假、警徽流和投票收益"
            villager_focus_clause = f"{first}和{focus_names[1]}的站边理由，尤其是谁在复述结论却不解释依据"
            witch_focus_clause = f"{first}如果只跟结论不交站边理由，需要进焦点；{focus_names[1]}也要解释票型收益"
        elif focus_names:
            focus_clause = f"{first}的站边理由和后置位回应是否围绕预言家真假、警徽流和投票收益"
            villager_focus_clause = f"{first}的站边理由和后置位回应，尤其是谁在复述结论却不解释依据"
            witch_focus_clause = f"{first}如果只跟结论不交站边理由，需要进焦点；后置位也要解释票型收益"
        else:
            focus_clause = "前置位和后置位是否围绕预言家真假、警徽流和投票收益"
            villager_focus_clause = "前后置位的站边理由，尤其是谁在复述结论却不解释依据"
            witch_focus_clause = "前置位如果只跟结论不交站边理由，需要进焦点；后置位也要解释票型收益"
        seer_claimants = [name for name in self._public_seer_claimants() if name != self.name]
        claimant_text = "、".join(seer_claimants)
        if seer_claimants:
            seer_clause = f"场上已有{claimant_text}的预言家声称，我先评价他们的查验逻辑和票型收益。"
        else:
            seer_clause = "场上预言家信息只能以公开发言和遗言为准，我不会编造查验。"

        if action_type == "sheriff_speech":
            if self.role != Role.SEER and not (self.role == Role.WEREWOLF and self.can_fake_seer):
                return self._nonseer_sheriff_speech_repair(game_state, focus_names, seer_claimants)

            phase_variants = [
                "我先把这一轮警徽票的判断标准说清楚。",
                "我这轮先按已经听到的警上发言做比较。",
                "我先从警徽流、查验心路和警下票收益三点来盘。",
            ]
            phase_clause = phase_variants[self._stable_variant_index(len(phase_variants))]
            if focus_names:
                if len(focus_names) > 1:
                    focus_clause = (
                        f"{focus_names[0]}刚才给出的警徽票标准和{focus_names[1]}的身份声称、查验心路、"
                        "警徽流能不能互相对上"
                    )
                    villager_focus_clause = (
                        f"{focus_names[0]}的警徽票标准和{focus_names[1]}的查验心路、警徽流，"
                        "尤其是谁能把警下票收益说清楚"
                    )
                    witch_focus_clause = villager_focus_clause
                else:
                    focus_clause = f"{focus_names[0]}刚才的身份声称、警徽票标准和后置位回应能不能互相对上"
                    villager_focus_clause = f"{focus_names[0]}刚才的警徽票标准、身份声称和后置位回应"
                    witch_focus_clause = villager_focus_clause
                closing_clause = "警下投票先看谁的身份声称、警徽流和查验心路更自洽，后置位如果只重复结论也要进视野。"
            else:
                seer_clause = "目前还没有足够前置发言可评价，我先给出警徽票判断标准。"
                focus_clause = "后置位是否交清身份声称、警徽流和警下票理由"
                villager_focus_clause = "后置位的身份声称、警徽流和警下票理由"
                witch_focus_clause = "后置位是否只重复结论不补警徽票逻辑"
                closing_clause = "我会重点听后置位是否交清身份声称、警徽流和警下票理由，警徽票不只看谁先起跳。"
        else:
            phase_clause = None
            closing_clause = "今天好人先统一比较预言家声称、警徽流和票型，不要被临时编信息带偏。"

        if self.role == Role.HUNTER:
            if phase_clause:
                return (
                    f"{phase_clause}"
                    f"{seer_clause}"
                    f"我重点看{focus_clause}。"
                    f"{closing_clause}"
                )
            return (
                "我不是预言家，没有夜间查验信息。"
                f"我是猎人视角，{seer_clause}"
                f"今天重点看{focus_clause}。"
                "好人不要被临时改口带散票，投票前先把身份声称和前后发言对齐。"
            )
        if self.role == Role.WITCH:
            if phase_clause:
                return (
                    f"{phase_clause}"
                    f"{seer_clause}"
                    f"{witch_focus_clause}。"
                    f"{closing_clause}"
                )
            return (
                "我不是预言家，不能报查验。"
                f"我是女巫视角，{seer_clause}"
                f"{witch_focus_clause}。"
                "今天先围绕公开身份、银水毒药信息和发言矛盾收窄狼坑。"
            )
        if phase_clause:
            return (
                f"{phase_clause}"
                f"{seer_clause}"
                f"我重点听{villager_focus_clause}。"
                f"{closing_clause}"
            )
        return (
            "我是平民，没有夜间查验，也不会跳预言家。"
            f"{seer_clause}"
            f"我现在重点听{villager_focus_clause}。"
            f"{closing_clause}"
        )

    def _nonseer_sheriff_speech_repair(
        self,
        game_state: Dict[str, Any],
        focus_names: List[str],
        seer_claimants: List[str],
    ) -> str:
        if self.role == Role.WITCH:
            opening = "我这轮上警不是跳预言家，也不会报查验，我只从女巫视角帮好人听发言。"
            role_detail = "如果后面需要拍身份，我会围绕药水信息和公开发言解释，不会编造预言家视角。"
        elif self.role == Role.HUNTER:
            opening = "我上警不是跳预言家，也没有夜间查验，我先把听发言的标准放在这里。"
            role_detail = "猎人牌更怕好人被带散票，所以我会重点盯谁在强行带节奏、谁在回避身份边界。"
        elif self.role == Role.WEREWOLF:
            opening = "我这轮按闭眼好人视角上警，不跳预言家，也不会报任何查验。"
            role_detail = "我只看公开发言和票型，不用不存在的夜间信息压人。"
        else:
            opening = "我上警不是跳预言家，也没有夜间查验，先给警下一个听发言的参考。"
            role_detail = "平民牌能做的就是把标准说清楚，后面根据公开发言更新站边。"

        if seer_claimants:
            claimant_text = "、".join(seer_claimants)
            prior_nonseer = next((name for name in focus_names if name not in seer_claimants), None)
            claimant_clause = (
                f"现在{claimant_text}已经公开声称预言家，我会听他们的首验理由、警徽安排和前后逻辑是否自洽。"
            )
            if prior_nonseer:
                focus_clause = (
                    f"{prior_nonseer}如果只是普通上警发言，就要和真正起跳位区分开；"
                    "后置位也别把评价预言家的人误当成对跳。"
                )
            else:
                focus_clause = "后置位如果要站边，就要说清为什么信这个起跳位，而不是只复述查验结论。"
            closing = "警下票先看谁的身份边界清楚、逻辑完整，再决定警徽给谁。"
        elif focus_names:
            if len(focus_names) >= 2:
                focus_clause = (
                    f"前面{focus_names[0]}和{focus_names[1]}都还没有给出硬信息，我先不急着站死边。"
                    "我会听后置位有没有明确身份边界、上警目的和投票理由。"
                )
            else:
                focus_clause = (
                    f"{focus_names[0]}前面的发言我先记下，但现在还没有真正的预言家信息。"
                    "后置位如果只喊自己能带队、不解释为什么上警，我会降低认可度。"
                )
            claimant_clause = "目前还没有明确的一人称预言家起跳，我不会空谈查验心路。"
            closing = "这轮警徽票先看发言完整度和带队责任感，不是看谁先把话说满。"
        else:
            claimant_clause = "现在前置发言还不够，我不会凭空点人，也不会编造预言家信息。"
            focus_clause = "后置位需要说清楚自己为什么上警、有没有身份边界、警下票应该看什么。"
            closing = "我会把警徽票给发言最完整、能稳定带队的位置。"

        return f"{opening}{claimant_clause}{focus_clause}{role_detail}{closing}"

    def _guard_public_speech_action(
        self,
        action: AgentAction,
        game_state: Dict[str, Any],
        action_type: str,
    ) -> AgentAction:
        if not self._needs_public_speech_repair(action, action_type):
            return action

        return AgentAction(
            decision_type=action.decision_type or "speech",
            target_id=action.target_id,
            reasoning=f"{action.reasoning}；修正非预言家越权报查验/跳预言家",
            speech=self._role_consistent_speech_repair(game_state, action_type),
            will_retreat=action.will_retreat,
            speak_direction=action.speak_direction,
        )

    def _needs_public_speech_repair(self, action: AgentAction, action_type: str) -> bool:
        if action_type not in {"sheriff_speech", "day_speech", "pk_speech", "last_words"}:
            return False
        return self._is_illegal_nonseer_seer_claim(action.speech)

    def _identity_boundary_instruction(self, action_type: str) -> str:
        if action_type not in {"sheriff_speech", "day_speech", "pk_speech", "last_words"}:
            return "严格尊重自己的底牌身份，不要输出与当前角色能力不符的信息。"
        if self.role == Role.SEER:
            return "你是预言家，只能报告你私人信息中真实存在的查验结果，不能编造额外查验。"
        if self.role == Role.WEREWOLF and self.can_fake_seer:
            return "你是本局唯一授权悍跳狼，可以伪装预言家，但必须前后一致，不能冒充其他具体玩家。"

        role_name = {
            Role.WEREWOLF: "未授权悍跳的狼人",
            Role.WITCH: "女巫",
            Role.HUNTER: "猎人",
            Role.VILLAGER: "平民",
        }.get(self.role, self.role.value)
        return (
            f"你是{role_name}，不是预言家。公开发言必须从自己的底牌视角出发："
            "绝对禁止自称预言家、真预言家、唯一预言家、起跳/对跳预言家；"
            "绝对禁止使用第一人称查验表达，例如“我验了”“昨晚我验”“我的查验”“我查验”“我给金水/查杀”；"
            "可以评价别人公开声称的查验、警徽流和站边逻辑，但必须明确这是“别人声称/公开信息”，不是你的夜间信息。"
        )

    def _public_speech_rewrite_instruction(self, action_type: str, extra_instructions: str) -> str:
        if self.role == Role.WITCH:
            role_view = "以女巫视角发言；只能谈药水状态、银水/刀口信息和公开发言逻辑，不能报查验。"
        elif self.role == Role.HUNTER:
            role_view = "以猎人视角发言；可以谈开枪威慑、投票态度和公开身份对比，不能报查验。"
        elif self.role == Role.WEREWOLF:
            role_view = (
                "以普通好人/闭眼好人视角伪装发言；你不是本局授权悍跳狼，不能跳预言家或神职。"
                if not self.can_fake_seer
                else "以授权悍跳预言家视角发言，保持对跳逻辑自洽。"
            )
        else:
            role_view = "以平民/闭眼好人视角发言；只能分析公开发言、票型和身份声称，不能报查验。"

        return (
            f"{extra_instructions}\n\n"
            "上一轮输出违反身份边界。请直接重写一段自然可展示发言，不要解释自己刚才说错了。"
            f"{role_view}"
            "如果场上有人跳预言家，只能说“某某声称预言家/某某报了查验”，再评价其逻辑；"
            "不能说“我验/我的查验/我给查杀/我给金水”。"
            "发言需要结合具体公开玩家和当前轮次，避免套话。"
        )

    def _stable_variant_index(self, modulo: int) -> int:
        if modulo <= 1:
            return 0
        suffix = self.player_id.rsplit("_", 1)[-1]
        if suffix.isdigit():
            return int(suffix) % modulo
        return sum(ord(ch) for ch in f"{self.player_id}:{self.name}") % modulo

    def _public_speeches(self) -> List[tuple[str, str]]:
        speeches = []
        for item in self.conversation_history:
            if item.get("role") != "user":
                continue
            content = item.get("content", "")
            if ":" not in content:
                continue
            speaker, speech = content.split(":", 1)
            speeches.append((speaker.strip(), speech.strip()))
        return speeches

    def _public_seer_claimants(self) -> List[str]:
        claimants = []
        for speaker, speech in self._public_speeches():
            if speaker and speaker not in claimants and self._infer_public_claim(speech) == "seer":
                claimants.append(speaker)
        return claimants

    def _sheriff_speech_focus_names(self, limit: int = 2) -> List[str]:
        names = []
        for speaker, speech in reversed(self._public_speeches()):
            if speaker == self.name or speaker in names:
                continue
            if any(word in speech for word in ["查杀", "预言家", "投", "站边", "狼", "警徽", "金水", "悍跳"]):
                names.append(speaker)
            if len(names) >= limit:
                break
        return list(reversed(names))

    def _player_name_by_id(self, game_state: Dict[str, Any], player_id: str) -> str:
        player = game_state.get("players", {}).get(player_id, {})
        return player.get("name") or player_id

    def _check_results_for_speech(self, game_state: Dict[str, Any]) -> str:
        lines = []
        for knowledge in self.private_knowledge:
            if "查验结果" not in knowledge:
                continue
            for player_id, player in game_state.get("players", {}).items():
                if player_id in knowledge:
                    result = "狼人" if "是 狼人" in knowledge or "是狼人" in knowledge else "好人"
                    lines.append(f"{player.get('name') or player_id}是{result}")
        return "，".join(dict.fromkeys(lines))

    def _fallback_focus_names(self, game_state: Dict[str, Any], limit: int = 2) -> List[str]:
        claimants = [name for name in self._public_seer_claimants() if name != self.name]
        if claimants:
            return claimants[:limit]

        names = []
        for speaker, speech in reversed(self._public_speeches()):
            if speaker == self.name or speaker in names:
                continue
            if any(word in speech for word in ["查杀", "预言家", "退水", "投", "站边", "狼", "可疑", "警徽"]):
                names.append(speaker)
            if len(names) >= limit:
                return names

        for player in game_state.get("players", {}).values():
            name = player.get("name")
            if name and name != self.name and player.get("is_alive") and name not in names:
                names.append(name)
            if len(names) >= limit:
                break
        return names

    def _sheriff_candidates(self, game_state: Dict[str, Any]) -> List[Dict[str, Any]]:
        candidates = []
        for pid, player in game_state.get("players", {}).items():
            if player.get("is_alive") and player.get("in_sheriff_election"):
                candidates.append({
                    "player_id": pid,
                    "name": player.get("name") or pid,
                    "role": player.get("role"),
                })
        return candidates

    def _claim_consistency_instruction(self) -> str:
        if self.public_claim == "seer" and (self.role == Role.SEER or (self.role == Role.WEREWOLF and self.can_fake_seer)):
            return "你已经公开跳过预言家，后续必须维持预言家身份，不能退水改口说自己是平民/闭眼好人。"
        if self.public_claim == "seer":
            return "你之前出现过不符合底牌的预言家声明，本局不允许继续维持该声明；后续必须回到自己底牌允许的发言边界，不能再报查验、金水或查杀。"
        if self.public_claim == "witch":
            return "你已经公开跳过女巫，后续必须维持女巫身份，不能改口成平民。"
        if self.public_claim == "hunter":
            return "你已经公开跳过猎人，后续必须维持猎人身份，不能改口成平民。"
        if self.public_claim == "villager":
            return "你已经公开表过平民/闭眼好人，后续不要突然改跳神职，除非是在明确解释诈身份。"
        return "发言必须和自己前面公开说过的话一致，不能前面跳神职、后面又改口成平民。"

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

    def _response_length_instruction(self, action_type: str) -> str:
        if action_type in {"sheriff_speech", "day_speech", "pk_speech", "last_words"}:
            return (
                "只输出JSON对象。reasoning控制在80个中文字符以内；"
                "speech必须是可展示发言，控制在180到260个中文字符，分成3到5句。"
                "不要只说“我是好人”，必须结合已公开的警徽流、查验、票型、身份声称或发言矛盾给出具体判断。"
            )
        return "只输出JSON对象。reasoning和speech都控制在80个中文字符以内。"

    def _fallback_action(self, game_state: Dict[str, Any], action_type: str, error: Exception) -> AgentAction:
        alive_players = self._get_alive_players(game_state)
        focus_names = self._fallback_focus_names(game_state)
        first = focus_names[0] if focus_names else "前置位"
        second = focus_names[1] if len(focus_names) > 1 else first
        phase = game_state.get("current_phase", "")

        if action_type == "sheriff_election":
            if self.role == Role.SEER:
                return AgentAction(
                    decision_type="run",
                    target_id=None,
                    reasoning="预言家需要争警徽带队",
                    speech="我是预言家视角，警徽对验人和归票都很关键，这轮必须上警争取带队。",
                )
            if self.role == Role.WEREWOLF:
                wolf_ids = [
                    pid for pid, player in sorted(game_state.get("players", {}).items())
                    if player.get("is_alive") and (pid == self.player_id or player.get("role") == "werewolf")
                ]
                if wolf_ids and self.player_id != wolf_ids[0]:
                    return AgentAction(
                        decision_type="stay",
                        target_id=None,
                        reasoning="已有狼队友更适合上警，自己留警下做票仓",
                        speech="我先留在警下听警上发言，重点看预言家声称和警徽流是否自洽，警徽票会投给逻辑更完整的位置。",
                    )
                return AgentAction(
                    decision_type="run",
                    target_id=None,
                    reasoning="狼队需要警上制造对跳压力",
                    speech="警上信息最集中，我上警观察预言家声称和站边反应，必要时制造对跳压力。",
                )
            return AgentAction(
                decision_type="stay",
                target_id=None,
                reasoning="无硬信息身份先留警下投票",
                speech="我没有夜间硬信息，先留在警下听警上发言，用警徽票判断谁更像真带队位。",
            )

        if action_type in {"sheriff_speech", "day_speech", "pk_speech"}:
            if self.public_claim == "seer" or self.role == Role.SEER:
                check_results = self._check_results_for_speech(game_state)
                result_clause = f"我的查验是{check_results}。" if check_results else "我会把警徽流和验人逻辑交清楚。"
                other_claimants = [name for name in self._public_seer_claimants() if name != self.name]
                if other_claimants:
                    focus_clause = f"现在核心就是我和{other_claimants[0]}的预言家对跳，警下只需要对比查验、警徽流和发言前后是否一致。"
                else:
                    focus_clause = "目前还没有对跳，警下先听后置是否有人起跳，不要在没有对跳前把票散到外置位。"
                speech = (
                    f"我是预言家，{result_clause}"
                    f"{focus_clause}"
                    "今天票型不要散，我会围绕对跳、查验结果和退水行为继续归票。"
                )
            elif self.role == Role.WITCH:
                speech = (
                    "我是女巫视角，今天先看谁在利用预言家对跳带节奏。"
                    f"{first}如果只跟票不解释原因，需要进狼坑；{second}的发言也要看有没有身份收益。"
                    "好人不要分票，先围绕预言家声称、银水关系和票型把焦点收窄。"
                )
            elif self.role == Role.HUNTER:
                speech = (
                    "我是猎人视角，今天不接受空泛表水。"
                    f"{first}和{second}都要交清楚站边理由，尤其是谁在回避预言家真假和警徽流。"
                    "狼最喜欢让好人分散投票，所以我建议先统一看发言矛盾最大的那一位。"
                )
            elif self.role == Role.WEREWOLF:
                seer_claimants = self._public_seer_claimants()
                if self.public_claim == "seer":
                    speech = (
                        "我维持预言家身份，不退水也不改口。"
                        f"{first}如果和我形成对跳，就必须交出完整首验心路和警徽流，不是喊一句真预就能拿警徽。"
                        "今天好人围绕预言家对跳投票，不要让票型散到外置位。"
                    )
                elif seer_claimants:
                    speech = (
                        "我是闭眼好人视角，先不再新增身份。"
                        f"现在场上已经有{seer_claimants[0]}的预言家声称，我重点看他的查验心路和后置对跳反应。"
                        f"{first}和{second}谁回避这个核心冲突，谁更像在借乱局藏身份。"
                    )
                else:
                    speech = (
                        "我是闭眼好人视角，先不抢神职身份。"
                        f"现在重点看{first}和{second}谁的站边更像后置补逻辑，谁只重复别人结论就需要进狼坑。"
                        "今天不要被单句强归带走，先把预言家声称、警徽流和投票收益放在一起判断。"
                    )
            else:
                speech = (
                    "我是平民，没有夜间信息，所以更要看公开逻辑。"
                    f"{first}如果只说立场不解释依据，我会重点怀疑；{second}的发言也要看是否跟票过快。"
                    "今天好人不要散票，先围绕预言家声称、警徽流和前后发言矛盾压缩狼坑。"
                )
            return AgentAction(
                decision_type="speech",
                target_id=None,
                reasoning=f"LLM调用失败，使用{self.role.value}展示兜底发言",
                speech=speech,
            )

        if action_type == "sheriff_vote":
            candidates = self._sheriff_candidates(game_state)
            target = candidates[0] if candidates else None
            target_id = target["player_id"] if target else None
            target_name = target["name"] if target else "无人"
            return AgentAction(
                decision_type="vote",
                target_id=target_id,
                reasoning=f"LLM调用失败，按当前警上候选发言投给{target_name}",
                speech=f"我警徽票投{target_name}，先按警上发言完整度和查验交代来选择带队位。",
            )

        if action_type == "vote":
            target_id = alive_players[0]["player_id"] if alive_players else None
            target_name = alive_players[0]["name"] if alive_players else "无人"
            return AgentAction(
                decision_type="vote",
                target_id=target_id,
                reasoning=f"LLM调用失败，优先投给当前最需要解释的位置{target_name}",
                speech=f"我先投{target_name}，因为他的公开发言需要补充站边和票型理由。",
            )

        return AgentAction(
            decision_type="do_nothing" if phase == "night" else "speech",
            target_id=None,
            reasoning=f"LLM调用失败，使用{self.role.value}默认决策",
            speech="我先保留关键技能和身份信息，继续根据公开发言、票型和站边变化更新判断。",
        )

    async def _call_llm_for_action(self, game_state: Dict[str, Any], action_type: str, extra_instructions: str = "") -> AgentAction:
        parser = JsonOutputParser(pydantic_object=AgentAction)
        response_length_instruction = self._response_length_instruction(action_type)
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", self.get_effective_system_prompt()),
            ("system", "你需要根据游戏状态做出决策。请以JSON格式输出，格式如下：\n{format_instructions}"),
            ("system", "{response_length_instruction}"),
            ("system", "{claim_consistency_instruction}"),
            ("system", "{identity_boundary_instruction}"),
            ("user", "{game_state}\n\n当前需要做出的决策类型：{action_type}\n{extra_instructions}")
        ])
        
        chain = prompt | self.llm | parser
        
        try:
            result = await chain.ainvoke({
                "game_state": self._format_game_state(game_state),
                "action_type": action_type,
                "extra_instructions": extra_instructions,
                "format_instructions": parser.get_format_instructions(),
                "response_length_instruction": response_length_instruction,
                "claim_consistency_instruction": self._claim_consistency_instruction(),
                "identity_boundary_instruction": self._identity_boundary_instruction(action_type),
            })
            action = AgentAction(**result)
            if self._needs_public_speech_repair(action, action_type):
                correction_instructions = self._public_speech_rewrite_instruction(action_type, extra_instructions)
                corrected = await chain.ainvoke({
                    "game_state": self._format_game_state(game_state),
                    "action_type": action_type,
                    "extra_instructions": correction_instructions,
                    "format_instructions": parser.get_format_instructions(),
                    "response_length_instruction": response_length_instruction,
                    "claim_consistency_instruction": self._claim_consistency_instruction(),
                    "identity_boundary_instruction": self._identity_boundary_instruction(action_type),
                })
                action = AgentAction(**corrected)
            return self._guard_public_speech_action(action, game_state, action_type)
        except Exception as e:
            self.llm_failure_count += 1
            self.llm_failure_errors.append(f"{type(e).__name__}: {e}")
            print(f"LLM调用失败: {e}")
            return self._guard_public_speech_action(self._fallback_action(game_state, action_type, e), game_state, action_type)
