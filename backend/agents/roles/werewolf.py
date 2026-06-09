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
- 只有被游戏引擎指定为本局唯一悍跳狼时，才允许悍跳预言家
- 如果没有被指定为唯一悍跳狼，绝对禁止自称预言家、女巫或猎人，不能编造查验、金水、银水、查杀或枪口
- 观察其他玩家的发言，找出最可疑的人来投票
- 你可以在白天发言阶段选择自爆，自爆后你会直接死亡，当前白天立即结束进入黑夜，你没有遗言"""

    def _public_history_text(self) -> str:
        return "\n".join(
            item.get("content", "")
            for item in self.conversation_history
            if item.get("role") in {"user", "system"}
        )

    def _is_publicly_protected_target(self, player: dict) -> bool:
        name = player.get("name") or ""
        if not name:
            return False

        history = self._public_history_text()
        target_lines = [
            line for line in history.splitlines()
            if line.startswith(f"{name}:") or line.startswith(f"{name} ")
        ]
        for line in target_lines:
            if "预言家" in line and any(marker in line for marker in ["我是", "跳", "真预言家", "唯一"]):
                return True
            if "女巫" in line and any(marker in line for marker in ["我是", "跳", "真女巫"]):
                return True
            if "猎人" in line and any(marker in line for marker in ["我是", "跳", "真猎人"]):
                return True

        self_claims = [
            f"{name}: 我是女巫",
            f"{name}: 我是真女巫",
            f"{name}: 我是预言家",
            f"{name}: 我是真预言家",
            f"{name}: 我是猎人",
            f"{name}: 我是真猎人",
        ]
        protected_mentions = [
            f"{name}是我的银水",
            f"{name}是银水",
            f"{name}是我银水",
            f"{name}是我的金水",
            f"{name}是金水",
            f"{name}是我金水",
            f"验{name}是好人",
            f"查{name}是好人",
            f"查验{name}是好人",
        ]
        soft_protection_mentions = [
            f"{name}跳预言家",
            f"{name}是真预言家",
            f"{name}是唯一预言家",
            f"{name}真预言家",
        ]

        if any(claim in history for claim in self_claims + protected_mentions + soft_protection_mentions):
            return True

        return any(
            name in line and any(water in line for water in ["金水", "银水"])
            for line in history.splitlines()
        )

    def _is_private_saved_kill_target(self, player: dict, game_state: dict) -> bool:
        return (
            game_state.get("wolf_last_kill_saved") is True
            and bool(game_state.get("wolf_last_kill_target_id"))
            and player.get("player_id") == game_state.get("wolf_last_kill_target_id")
        )

    def _suspicion_score(self, player: dict) -> int:
        name = player.get("name") or ""
        if not name:
            return 0

        score = 0
        suspicious_words = ["狼", "狼面", "可疑", "身份差", "行为匪", "划水", "抗推", "归票", "投"]
        for item in self.conversation_history[-30:]:
            content = item.get("content", "")
            if name in content:
                score += 1
                if any(word in content for word in suspicious_words):
                    score += 2
        return score

    def _is_aggressive_about(self, speech: str, player: dict) -> bool:
        name = player.get("name") or ""
        if name not in speech:
            return False
        aggressive_words = [
            "狼面", "可疑", "身份差", "行为匪", "划水", "抗推", "归票",
            "投", "出", "踩", "状态怪", "状态不对", "重点怀疑", "怀疑",
            "疑点", "心路不全", "没说清", "不站边", "不像", "牵强",
            "无故", "狼坑", "匪面", "爆狼", "标狼",
        ]
        return any(word in speech for word in aggressive_words)

    def _has_public_pressure_basis(self, player: dict) -> bool:
        name = player.get("name") or ""
        if not name:
            return False

        pressure_words = [
            "狼面", "可疑", "身份差", "行为匪", "划水", "抗推", "归票",
            "踩", "状态怪", "状态不对", "怀疑", "疑点", "心路不全",
            "没说清", "不站边", "不像", "牵强", "无故", "狼坑",
            "匪面", "爆狼", "标狼", "查杀", "对跳", "悍跳",
        ]
        for item in self.conversation_history[-30:]:
            content = item.get("content", "")
            if name not in content:
                continue
            if content.startswith(f"{name}:") or content.startswith(f"{name} "):
                continue
            if any(word in content for word in pressure_words):
                return True
        return False

    def _public_checkkillers_against_player(self, player: dict) -> list[str]:
        name = player.get("name") or ""
        player_id = player.get("player_id") or ""
        if not name:
            return []

        accusers = []
        for item in self.conversation_history[-30:]:
            content = item.get("content", "")
            if name not in content:
                continue
            if "查杀" not in content and "狼人" not in content and "狼" not in content:
                continue
            if any(phrase in content for phrase in [
                f"{name}是查杀",
                f"{name}（{player_id}）是查杀",
                f"{name}是狼人",
                f"{name}为狼人",
                f"{name}是狼",
                f"{name}为狼",
                f"{name}是铁狼",
                f"{name}为铁狼",
                f"{name}（{player_id}）是狼人",
                f"{name}（{player_id}）为狼人",
                f"{name}（{player_id}）是铁狼",
                f"{name}（{player_id}）为铁狼",
                f"查杀{name}",
                f"查验{name}是查杀",
                f"查验{name}为查杀",
                f"查验{name}是狼人",
                f"查验{name}为狼人",
                f"查验{name}是狼",
                f"查验{name}为狼",
                f"查验{name}是铁狼",
                f"查验{name}为铁狼",
                f"查{name}是查杀",
                f"查{name}为查杀",
                f"查{name}是狼人",
                f"查{name}为狼人",
                f"查{name}是狼",
                f"查{name}为狼",
                f"查{name}是铁狼",
                f"查{name}为铁狼",
                f"查了{name}是查杀",
                f"查了{name}是狼人",
                f"查了{name}为狼人",
                f"查了{name}是狼",
                f"查了{name}为狼",
                f"查了{name}是铁狼",
                f"查出{name}是查杀",
                f"查出{name}是狼人",
                f"查出{name}为狼人",
                f"查出{name}是狼",
                f"查出{name}为狼",
                f"查出{name}是铁狼",
                f"验{name}是查杀",
                f"验{name}为查杀",
                f"验{name}是狼人",
                f"验{name}为狼人",
                f"验{name}是狼",
                f"验{name}为狼",
                f"验{name}是铁狼",
                f"验{name}为铁狼",
                f"验了{name}是查杀",
                f"验了{name}是狼人",
                f"验了{name}为狼人",
                f"验了{name}是狼",
                f"验了{name}为狼",
                f"验了{name}是铁狼",
                f"验出{name}是查杀",
                f"验出{name}是狼人",
                f"验出{name}为狼人",
                f"验出{name}是狼",
                f"验出{name}为狼",
                f"验出{name}是铁狼",
            ]):
                speaker = content.split(":", 1)[0].strip()
                if speaker and speaker not in accusers:
                    accusers.append(speaker)
        return accusers

    def _has_public_checkkill_by_self_against_player(self, player: dict) -> bool:
        return self.name in self._public_checkkillers_against_player(player)

    def _has_public_checkkill_by_teammate_against_player(self, player: dict, teammates: list) -> bool:
        for teammate in teammates:
            if teammate.get("player_id") == self.player_id:
                continue
            teammate_name = teammate.get("name")
            if teammate_name and teammate_name in self._public_checkkillers_against_player(player):
                return True
        return False

    def _public_checkkillers_against_self(self) -> list[str]:
        return self._public_checkkillers_against_player({
            "name": self.name,
            "player_id": self.player_id,
        })

    def _has_public_checkkill_against_self(self, player: dict) -> bool:
        name = player.get("name") or ""
        return bool(name and name in self._public_checkkillers_against_self())

    def _has_public_checkkill_against_teammate(self, player: dict, teammates: list) -> bool:
        name = player.get("name") or ""
        if not name:
            return False

        for teammate in teammates:
            if teammate.get("player_id") == self.player_id:
                continue
            if name in self._public_checkkillers_against_player(teammate):
                return True
        return False

    def _is_checkkill_defense(self, speech: str) -> bool:
        if self.name not in speech and "我" not in speech:
            return False
        denial_markers = [
            "不认",
            "我是好人",
            "我是普通好人",
            "我是闭眼好人",
            "我是平民",
            "我是村民",
            "我不是狼",
            "我不是狼人",
            "我不可能是狼",
            "我接不住这个查杀",
        ]
        return any(marker in speech for marker in denial_markers)

    def _checkkill_defense_speech(self, accuser_name: str) -> str:
        return (
            f"我是普通好人，{accuser_name}给我查杀我不认。"
            "对方只报结果但没有足够首验心路，不能因为单预就直接把我定死。"
            f"今天至少在我和{accuser_name}里二选一，先听票型和后续表态，别被强归带走。"
        )

    def _force_fake_seer_enabled(self) -> bool:
        if not self.can_fake_seer:
            return False
        prompt = self.get_effective_system_prompt()
        return "动作层强制悍跳" in prompt

    def _force_late_fake_seer_enabled(self) -> bool:
        if not self.can_fake_seer:
            return False
        prompt = self.get_effective_system_prompt()
        return "动作层后置补跳" in prompt

    def _public_speaker_names(self) -> list[str]:
        names = []
        for item in self.conversation_history:
            if item.get("role") != "user":
                continue
            content = item.get("content", "")
            if ":" not in content:
                continue
            speaker = content.split(":", 1)[0].strip()
            if speaker and speaker not in names:
                names.append(speaker)
        return names

    def _public_speech_for(self, name: str) -> str:
        speeches = []
        for item in self.conversation_history:
            if item.get("role") != "user":
                continue
            content = item.get("content", "")
            prefix = f"{name}:"
            if content.startswith(prefix):
                speeches.append(content[len(prefix):].strip())
        return "\n".join(speeches)

    def _is_seer_claim_text(self, content: str) -> bool:
        if "预言家" not in content:
            return False
        return any(marker in content for marker in [
            "我是预言家",
            "我是真预言家",
            "我才是预言家",
            "我才是真预言家",
            "我是唯一真预言家",
            "我是全场唯一真预言家",
            "我跳预言家",
            "我起跳预言家",
            "我对跳预言家",
        ])

    def _has_public_seer_claim_by(self, player: dict) -> bool:
        name = player.get("name") or ""
        if not name:
            return False

        for item in self.conversation_history:
            if item.get("role") != "user":
                continue
            content = item.get("content", "")
            if ":" not in content:
                continue
            speaker, speech = content.split(":", 1)
            if speaker.strip() == name and self._is_seer_claim_text(speech):
                return True
        return False

    def _public_seer_claimant_names(self) -> list[str]:
        names = []
        for item in self.conversation_history:
            if item.get("role") != "user":
                continue
            content = item.get("content", "")
            if ":" not in content:
                continue
            speaker, speech = content.split(":", 1)
            speaker = speaker.strip()
            if speaker and speaker not in names and self._is_seer_claim_text(speech):
                names.append(speaker)
        return names

    def _claims_low_information_villager(self, player: dict) -> bool:
        name = player.get("name") or ""
        speech = self._public_speech_for(name)
        if not speech:
            return False
        if any(word in speech for word in ["预言家", "女巫", "猎人", "金水", "银水", "查杀"]):
            return False
        villager_markers = ["村民", "平民", "闭眼", "普通好人", "无技能", "没有夜间信息", "没夜间信息"]
        return any(marker in speech for marker in villager_markers)

    def _has_public_seer_claim(self) -> bool:
        for item in self.conversation_history:
            if item.get("role") != "user":
                continue
            content = item.get("content", "")
            if ":" in content:
                content = content.split(":", 1)[1]
            if self._is_seer_claim_text(content):
                return True
        return False

    def _has_public_counter_seer_against_teammate(self, player: dict, teammates: list) -> bool:
        if not self._has_public_seer_claim_by(player):
            return False

        return any(
            teammate.get("player_id") != self.player_id
            and self._has_public_seer_claim_by(teammate)
            for teammate in teammates
        )

    def _teammate_public_seer_claimant(self, teammates: list) -> dict | None:
        for teammate in teammates:
            if teammate.get("player_id") != self.player_id and self._has_public_seer_claim_by(teammate):
                return teammate
        return None

    def _teammate_fake_seer_support_target(self, public_targets: list, teammates: list) -> dict | None:
        if not self._teammate_public_seer_claimant(teammates):
            return None

        for player in public_targets:
            if self._has_public_counter_seer_against_teammate(player, teammates):
                return player
        for player in public_targets:
            if self._has_public_checkkill_by_teammate_against_player(player, teammates):
                return player
        return None

    def _teammate_fake_seer_support_speech(self, public_targets: list, teammates: list) -> tuple[str, str] | tuple[None, None]:
        claimant = self._teammate_public_seer_claimant(teammates)
        target = self._teammate_fake_seer_support_target(public_targets, teammates)
        if not claimant or not target:
            return None, None

        claimant_name = claimant.get("name") or claimant["player_id"]
        target_name = target.get("name") or target["player_id"]
        speech = (
            f"我是好人，我站边{claimant_name}的预言家面。"
            f"{target_name}和{claimant_name}已经形成预言家冲突，今天票型不能散到外置位。"
            f"先出{target_name}，明天再根据票型和夜间信息继续排。"
        )
        return speech, f"动作层队友支援：清理旁踩保护位，集中站边 {claimant_name} 归票 {target_name}"

    def _early_teammate_fake_seer_support_speech(self, public_targets: list, teammates: list) -> tuple[str, str] | tuple[None, None]:
        claimant = self._teammate_public_seer_claimant(teammates)
        target = self._teammate_fake_seer_support_target(public_targets, teammates)
        if not claimant or not target:
            return None, None

        target_name = target.get("name") or target["player_id"]
        if target_name in self._public_speaker_names():
            return None, None

        claimant_name = claimant.get("name") or claimant["player_id"]
        speech = (
            f"{claimant_name}已经报了查杀，先让{target_name}拍身份或者对跳。"
            f"我现在不提前铁站边，但今天票型要围绕{target_name}和可能的对跳预言家，别散到外置位。"
            f"{target_name}如果拍不清楚，优先走查杀位。"
        )
        return speech, f"动作层队友早期支援：查杀位 {target_name} 未发言，避免硬站边 {claimant_name}"

    def _is_overcommitted_teammate_fake_seer_support(self, speech: str, public_targets: list, teammates: list) -> bool:
        claimant = self._teammate_public_seer_claimant(teammates)
        target = self._teammate_fake_seer_support_target(public_targets, teammates)
        if not claimant or not target:
            return False

        target_name = target.get("name") or target["player_id"]
        if target_name in self._public_speaker_names():
            return False

        claimant_name = claimant.get("name") or claimant["player_id"]
        hard_support_markers = [
            f"站边{claimant_name}",
            f"认{claimant_name}",
            f"{claimant_name}是真预",
            f"{claimant_name}才是真预",
            f"{claimant_name}是真预言家",
            f"{claimant_name}才是真预言家",
        ]
        return any(marker in speech for marker in hard_support_markers)

    def _should_force_fake_seer(self, game_state: dict) -> bool:
        if not self.can_fake_seer:
            return False
        if not self._force_fake_seer_enabled():
            return False
        if game_state.get("current_round", 1) != 1:
            return False
        if self._has_public_seer_claim():
            return False

        public_speakers = self._public_speaker_names()
        return len(public_speakers) >= 1

    def _teammate_has_public_seer_claim(self, game_state: dict) -> bool:
        for pid, player in game_state.get("players", {}).items():
            if pid == self.player_id or player.get("role") != "werewolf":
                continue
            if self._has_public_seer_claim_by(player):
                return True
        return False

    def _should_force_late_fake_seer(self, game_state: dict) -> bool:
        if not self.can_fake_seer:
            return False
        if not self._force_late_fake_seer_enabled():
            return False
        if game_state.get("current_round", 1) != 1:
            return False
        if self.name in self._public_speaker_names():
            return False
        if self._teammate_has_public_seer_claim(game_state):
            return False

        return any(name != self.name for name in self._public_seer_claimant_names())

    def _late_fake_seer_target(self, game_state: dict) -> dict | None:
        claimants = self._public_seer_claimant_names()
        for pid, player in game_state.get("players", {}).items():
            if pid == self.player_id or not player.get("is_alive"):
                continue
            if player.get("role") == "werewolf":
                continue
            if player.get("name") in claimants:
                return {
                    "player_id": pid,
                    "name": player.get("name"),
                    "role": player.get("role"),
                    "is_alive": player.get("is_alive"),
                }
        return None

    def _fake_seer_target(self, game_state: dict) -> dict | None:
        players = [
            {
                "player_id": pid,
                "name": player.get("name"),
                "role": player.get("role"),
                "is_alive": player.get("is_alive"),
            }
            for pid, player in game_state.get("players", {}).items()
            if player.get("is_alive") and pid != self.player_id and player.get("role") != "werewolf"
        ]
        if not players:
            return None

        saved_kill_target_ids = {
            player["player_id"]
            for player in players
            if self._is_private_saved_kill_target(player, game_state)
        }
        target_pool = [
            player for player in players
            if player.get("player_id") not in saved_kill_target_ids
        ] or players

        public_speakers = self._public_speaker_names()
        low_info_villager_targets = [
            player for player in target_pool
            if player.get("name") in public_speakers
            and not self._is_publicly_protected_target(player)
            and self._claims_low_information_villager(player)
        ]
        if low_info_villager_targets:
            return low_info_villager_targets[0]

        spoken_targets = [
            player for player in target_pool
            if player.get("name") in public_speakers and not self._is_publicly_protected_target(player)
        ]
        if spoken_targets:
            return spoken_targets[0]

        unprotected_targets = [
            player for player in target_pool
            if not self._is_publicly_protected_target(player)
        ]
        return unprotected_targets[0] if unprotected_targets else target_pool[0]

    def _forced_fake_seer_speech(self, game_state: dict) -> tuple[str, str]:
        target = self._fake_seer_target(game_state)
        if not target:
            return self._low_risk_day1_speech(game_state), "动作层强制悍跳触发但没有合法外置目标，改为低风险表水"

        name = target.get("name") or target["player_id"]
        has_spoken = name in self._public_speaker_names()
        check_reason = (
            f"我首验{name}是因为他前置发言只表态不压缩狼坑，容易藏狼。"
            if has_spoken else
            f"我首验{name}是因为他在外置位还没有公开信息，先验这里能最快压缩灰区。"
        )
        speech = (
            f"我是预言家，昨晚查验{name}是查杀。"
            f"{check_reason}"
            f"今天先在{name}和后面可能对跳的人里二选一，好人不要分票。"
        )
        target_state = "已发言" if has_spoken else "未发言"
        return speech, f"动作层强制悍跳：无人跳预且已有前置表水，给外置位 {name}（{target_state}）发查杀"

    def _late_fake_seer_counterpoints(self, name: str) -> str:
        speech = self._public_speech_for(name)
        points = []
        if "金水" in speech:
            points.append(
                f"{name}先发金水是在做票仓，金水本人接对身份不等于{name}是真预。"
            )
        if "警徽" in speech:
            points.append(
                f"本局没有警长环节，{name}硬聊警徽流是在套模板，不是预言家真逻辑。"
            )
        return "".join(points)

    def _late_fake_seer_speech(self, game_state: dict) -> tuple[str, str]:
        target = self._late_fake_seer_target(game_state)
        if not target:
            return self._low_risk_public_speech(game_state), "动作层后置补跳触发但没有找到公开预言家，改为低风险表水"

        name = target.get("name") or target["player_id"]
        counterpoints = self._late_fake_seer_counterpoints(name)
        self_checkkillers = self._public_checkkillers_against_self()
        if name in self_checkkillers:
            speech = (
                f"{name}给我查杀我不认，我是好人视角。"
                f"我对跳预言家，昨晚查验{name}是查杀。"
                f"{name}先给我发查杀想把我打死，但验人心路和归票理由不足。"
                f"{counterpoints}"
                f"今天就是我和{name}二选一，先出我的查杀{name}。"
            )
            return speech, f"动作层后置补跳：被 {name} 查杀后强防守并反制公开预言家"

        speech = (
            f"我对跳预言家，昨晚查验{name}是查杀。"
            f"{name}前面单边起跳想直接控场，但验人心路和归票理由不足。"
            f"{counterpoints}"
            f"今天就是我和{name}二选一，先出我的查杀{name}。"
        )
        return speech, f"动作层后置补跳：我方无人跳预，反制公开预言家 {name} 并给其发查杀"

    def _low_risk_public_speech(self, game_state: dict) -> str:
        if game_state.get("current_round", 1) == 1:
            return self._low_risk_day1_speech(game_state)
        claimants = [name for name in self._public_seer_claimant_names() if name != self.name]
        if claimants:
            return (
                "我是好人视角，先不新增身份。"
                f"现在场上核心还是{claimants[0]}的预言家声称、查验结果和前后票型是否自洽。"
                "我不会临时跳新身份带乱视角，今天先围绕公开矛盾和投票收益压缩狼坑。"
            )
        return (
            "我是好人视角，先不新增身份。"
            "现在没有必要临时编身份带节奏，重点看前后发言、夜间死讯和票型收益是否对得上。"
            "今天好人票型不要散，先从公开矛盾最大的位置开始压缩狼坑。"
        )

    def _join_names(self, names: list[str]) -> str:
        if not names:
            return "前置位"
        return "、".join(dict.fromkeys(names))

    def _low_risk_day1_speech(self, game_state: dict | None = None) -> str:
        game_state = game_state or {}
        claimants = [name for name in self._public_seer_claimant_names() if name != self.name]
        public_speakers = [name for name in self._public_speaker_names() if name != self.name]

        if len(claimants) >= 2:
            pair = self._join_names(claimants[:2])
            return (
                f"现在焦点已经不是外置位乱开坑，而是{pair}这组预言家对跳。"
                "我会先比较两边的首验理由、警徽流顺序和警长票型收益，谁只喊立场不解释收益，谁的预言家面就往下掉。"
                "今天投票不要再散到旁边位置，先把对跳里逻辑更差的一边压出去。"
            )
        if len(claimants) == 1:
            claimant = claimants[0]
            return (
                f"目前场上主要信息来自{claimant}的预言家声称。"
                f"我重点看{claimant}的查验对象、警徽流和后置回应是否能连起来，而不是单纯因为他先跳就直接认下。"
                "投票时我会跟着公开矛盾最大的焦点走，不另开和主线无关的新坑。"
            )

        focus_names = []
        for speaker, speech in reversed(self._public_speeches()):
            if speaker == self.name or speaker in focus_names:
                continue
            if any(word in speech for word in ["警徽", "投票", "站边", "查验", "身份", "狼坑", "悍跳", "金水", "查杀"]):
                focus_names.append(speaker)
            if len(focus_names) >= 2:
                break
        if not focus_names:
            focus_names = public_speakers[-2:]
        focus = self._join_names(focus_names)
        return (
            f"我先围绕{focus}刚才的发言来盘。"
            "现在需要看的不是谁喊得最响，而是谁能把站边、警徽票和投票收益解释清楚。"
            "如果后置位只复述结论不补逻辑，我会把他放进今天的优先焦点。"
        )

    def _maintain_fake_seer_speech(self, game_state: dict) -> tuple[str, str]:
        claimants = [name for name in self._public_seer_claimant_names() if name != self.name]
        opponent = claimants[0] if claimants else "对跳预言家"
        speech = (
            "我维持预言家身份，不退水也不改口。"
            f"{opponent}和我已经形成预言家对跳，今天就围绕查验、警徽流和警长票型决胜。"
            f"警下不要再分散去外置位，先对比我和{opponent}谁的逻辑更连贯，谁的票型收益更像狼。"
        )
        return speech, "已公开悍跳预言家，后续必须维持预言家身份和对跳焦点"

    def _guard_day_speech(self, speech: str, game_state: dict) -> tuple[str, str]:
        if self.public_claim == "seer":
            if not self.can_fake_seer:
                return self._low_risk_public_speech(game_state), "未授权狼人不能维持预言家声明，改为闭眼好人视角"
            if self._is_seer_claim_text(speech):
                return speech, ""
            return self._maintain_fake_seer_speech(game_state)

        players = [
            {
                "player_id": pid,
                "name": player.get("name"),
                "role": player.get("role"),
            }
            for pid, player in game_state.get("players", {}).items()
            if player.get("is_alive") and pid != self.player_id
        ]
        teammates = [player for player in players if player.get("role") == "werewolf"]
        public_targets = [player for player in players if player.get("role") != "werewolf"]

        checkkillers = self._public_checkkillers_against_self()
        if checkkillers and not self._is_checkkill_defense(speech):
            accuser = checkkillers[0]
            return self._checkkill_defense_speech(accuser), f"被公开查杀时必须强表水反查杀：{accuser}"

        if self._is_seer_claim_text(speech):
            if self.can_fake_seer:
                return speech, ""
            support_speech, support_reason = self._teammate_fake_seer_support_speech(public_targets, teammates)
            if support_speech:
                return support_speech, f"避免未授权重复跳预言家；{support_reason}"
            return self._low_risk_public_speech(game_state), "避免未授权补跳预言家导致多狼各自悍跳"

        if game_state.get("current_round", 1) != 1:
            return speech, ""

        if self._is_overcommitted_teammate_fake_seer_support(speech, public_targets, teammates):
            support_speech, support_reason = self._early_teammate_fake_seer_support_speech(public_targets, teammates)
            if support_speech:
                return support_speech, support_reason

        protected_attacks = [
            player for player in public_targets
            if (
                self._is_publicly_protected_target(player)
                or self._is_private_saved_kill_target(player, game_state)
            )
            and self._is_aggressive_about(speech, player)
            and not self._has_public_checkkill_by_self_against_player(player)
            and not self._has_public_checkkill_by_teammate_against_player(player, teammates)
            and not self._has_public_checkkill_against_self(player)
            and not self._has_public_checkkill_against_teammate(player, teammates)
            and not self._has_public_counter_seer_against_teammate(player, teammates)
        ]
        if protected_attacks:
            support_speech, support_reason = self._teammate_fake_seer_support_speech(public_targets, teammates)
            if support_speech:
                return support_speech, support_reason
            names = "、".join(player.get("name") or player["player_id"] for player in protected_attacks)
            return self._low_risk_day1_speech(game_state), f"避免 D1 无硬证据攻击公开高身份/水位：{names}"

        attacked_players = [
            player for player in public_targets
            if self._is_aggressive_about(speech, player)
        ]
        unsupported_attacks = [
            player for player in attacked_players
            if not self._has_public_pressure_basis(player)
            and not self._has_public_checkkill_by_self_against_player(player)
            and not self._has_public_checkkill_by_teammate_against_player(player, teammates)
            and not self._has_public_checkkill_against_self(player)
            and not self._has_public_checkkill_against_teammate(player, teammates)
            and not self._has_public_counter_seer_against_teammate(player, teammates)
        ]
        if unsupported_attacks:
            support_speech, support_reason = self._teammate_fake_seer_support_speech(public_targets, teammates)
            if support_speech:
                return support_speech, support_reason
            names = "、".join(player.get("name") or player["player_id"] for player in unsupported_attacks)
            if len(unsupported_attacks) >= 2:
                return self._low_risk_day1_speech(game_state), f"避免 D1 缺少公开共识/硬信息同时踩多人：{names}"
            return self._low_risk_day1_speech(game_state), f"避免 D1 缺少公开共识/硬信息点名踩人：{names}"

        return speech, ""

    def _guard_vote_target(
        self,
        preferred_target_id: str,
        targets: list,
        teammates: list | None = None,
        game_state: dict | None = None,
    ) -> tuple[str, str]:
        teammates = teammates or []
        game_state = game_state or {}
        target_ids = [p["player_id"] for p in targets]
        if preferred_target_id not in target_ids:
            return targets[0]["player_id"], "目标不在可选列表，改投第一个合法目标"

        preferred = next(p for p in targets if p["player_id"] == preferred_target_id)
        if (
            (
                not self._is_publicly_protected_target(preferred)
                and not self._is_private_saved_kill_target(preferred, game_state)
            )
            or self._has_public_checkkill_against_self(preferred)
            or self._has_public_checkkill_against_teammate(preferred, teammates)
            or self._has_public_counter_seer_against_teammate(preferred, teammates)
            or self._has_public_checkkill_by_self_against_player(preferred)
            or self._has_public_checkkill_by_teammate_against_player(preferred, teammates)
        ):
            return preferred_target_id, ""

        safe_targets = [
            p for p in targets
            if p["player_id"] != preferred_target_id
            and not self._is_publicly_protected_target(p)
            and not self._is_private_saved_kill_target(p, game_state)
        ]
        if not safe_targets:
            return preferred_target_id, ""

        replacement = max(
            safe_targets,
            key=lambda p: (self._suspicion_score(p), -target_ids.index(p["player_id"])),
        )
        return (
            replacement["player_id"],
            f"避免孤票公开高身份/水位 {preferred.get('name')}，改投更安全的 Top-2 外置位 {replacement.get('name')}",
        )

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
        if self._should_force_fake_seer(game_state):
            speech, reasoning = self._forced_fake_seer_speech(game_state)
            return AgentDecision(
                decision_type="speech",
                target_id=None,
                reasoning=reasoning,
                raw_output=speech,
            )
        if self._should_force_late_fake_seer(game_state):
            speech, reasoning = self._late_fake_seer_speech(game_state)
            return AgentDecision(
                decision_type="speech",
                target_id=None,
                reasoning=reasoning,
                raw_output=speech,
            )

        identity_boundary = (
            "你是本局唯一授权悍跳狼，允许在需要时维持或发起预言家悍跳，但不能冒充其他具体玩家。"
            if self.can_fake_seer
            else "你不是本局授权悍跳狼。你必须以普通好人/闭眼好人视角发言，绝对禁止跳预言家、女巫或猎人，不能编造查验、金水、银水、查杀或枪口。"
        )

        extra_instructions = f"""现在是白天发言阶段，轮到你发言了。
你可以选择正常发言，或者选择自爆。
如果自爆：你会直接死亡，当前白天立即结束进入黑夜，你没有遗言。
如果发言：你需要隐藏狼人身份，分析场上局势，不要暴露狼人身份。{identity_boundary}
发言要有逻辑，不要太简短，至少3句话。

返回结果：
- 如果选择自爆，decision_type填"bomb"，speech字段填"我自爆"
- 如果选择正常发言，decision_type填"speech"，speech字段填你的发言内容
在reasoning字段填写你的理由。"""
        
        action = await self._call_llm_for_action(game_state, "day_speech", extra_instructions)
        
        # 从reasoning推断decision_type
        decision_type = "speech"
        if action.reasoning and "bomb" in action.reasoning.lower():
            decision_type = "bomb"
        speech = action.speech
        reasoning = action.reasoning
        if decision_type == "speech":
            speech, guard_reason = self._guard_day_speech(speech, game_state)
            if guard_reason:
                reasoning = f"{reasoning}；{guard_reason}"
        
        return AgentDecision(
            decision_type=decision_type,
            target_id=None,
            reasoning=reasoning,
            raw_output=speech
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
        target_id, guard_reason = self._guard_vote_target(target_id, targets, teammates, game_state)
        reasoning = action.reasoning
        if guard_reason:
            reasoning = f"{reasoning}；{guard_reason}"
        
        return AgentDecision(
            decision_type="vote",
            target_id=target_id,
            reasoning=reasoning,
            raw_output=action.speech
        )
