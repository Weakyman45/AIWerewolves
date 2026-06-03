from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict
import re


class Analyzer:
    GOD_ROLES = {"seer", "witch", "hunter"}
    VILLAGER_TEAM_ROLES = {"seer", "witch", "hunter", "villager"}

    def analyze_game(self, game_data: Dict[str, Any]) -> Dict[str, Any]:
        analysis = {
            "game_id": game_data.get("game_id"),
            "winner": game_data.get("winner"),
            "overall": self._analyze_overall(game_data),
            "werewolf": self._analyze_werewolf(game_data),
            "seer": self._analyze_seer(game_data),
            "witch": self._analyze_witch(game_data),
            "hunter": self._analyze_hunter(game_data),
            "villager": self._analyze_villager(game_data),
            "mistakes": self._find_mistakes(game_data),
        }
        return analysis

    def analyze_multiple_games(self, games_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not games_data:
            return {}

        all_analyses = [self.analyze_game(game) for game in games_data]
        
        aggregate = {
            "total_games": len(games_data),
            "werewolf_win_rate": self._calculate_win_rate(games_data, "werewolves"),
            "villager_win_rate": self._calculate_win_rate(games_data, "villagers"),
            "average_rounds": self._calculate_average_rounds(games_data),
            "role_analysis": self._aggregate_role_analysis(all_analyses),
            "common_mistakes": self._aggregate_mistakes(all_analyses),
        }
        return aggregate

    def _analyze_overall(self, game_data: Dict[str, Any]) -> Dict[str, Any]:
        metrics = game_data.get("metrics", {})
        events = game_data.get("raw_events", [])
        return {
            "duration_rounds": metrics.get("duration_rounds", 0),
            "key_moments": metrics.get("key_moments", []),
            "sheriff_elected": any(event.get("type") == "sheriff_elected" for event in events),
            "death_count": len([event for event in events if event.get("type") == "death"]),
            "vote_rounds": len([event for event in events if event.get("type") == "vote_result"]),
        }

    def _analyze_werewolf(self, game_data: Dict[str, Any]) -> Dict[str, Any]:
        metrics = game_data.get("metrics", {})
        first_kill = metrics.get("first_night_kill")
        
        analysis = {
            "first_night_kill": first_kill,
            "kill_accuracy": self._assess_kill_accuracy(game_data),
            "hiding_ability": self._assess_hiding_ability(game_data),
            "vote_strategy": self._assess_vote_strategy(game_data),
        }
        return analysis

    def _analyze_seer(self, game_data: Dict[str, Any]) -> Dict[str, Any]:
        metrics = game_data.get("metrics", {})
        first_check = metrics.get("first_check")
        
        analysis = {
            "first_check": first_check,
            "check_accuracy": self._assess_check_accuracy(game_data),
            "reveal_timing": self._assess_reveal_timing(game_data),
        }
        return analysis

    def _analyze_witch(self, game_data: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "save_usage": self._assess_save_usage(game_data),
            "poison_usage": self._assess_poison_usage(game_data),
        }

    def _analyze_hunter(self, game_data: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "shot_timing": self._assess_shot_timing(game_data),
        }

    def _analyze_villager(self, game_data: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "vote_accuracy": self._assess_villager_vote(game_data),
        }

    def _find_mistakes(self, game_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        mistakes = []
        events = game_data.get("raw_events", [])
        players = game_data.get("players", {})
        
        for event in events:
            mistake = self._check_event_for_mistake(event, players)
            if mistake:
                mistakes.append(mistake)
        
        return mistakes

    def _check_event_for_mistake(self, event: Dict[str, Any], players: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        event_type = event.get("type")
        
        if event_type == "night_action":
            action = event.get("action", {})
            action_type = action.get("action")
            target_id = action.get("target")
            target_role = self._role_of(players, target_id)
            if action_type == "kill" and target_role == "werewolf":
                return {
                    "type": "werewolf_team_kill",
                    "action": action,
                    "severity": "high",
                }
            if action_type == "poison" and target_role != "werewolf":
                return {
                    "type": "witch_poisoned_villager_team",
                    "action": action,
                    "severity": "high",
                }
        
        return None

    def _assess_kill_accuracy(self, game_data: Dict[str, Any]) -> Dict[str, Any]:
        players = game_data.get("players", {})
        kills = self._night_actions(game_data, "kill")
        god_kills = [action for action in kills if self._role_of(players, action.get("target")) in self.GOD_ROLES]
        villager_team_kills = [
            action for action in kills
            if self._role_of(players, action.get("target")) in self.VILLAGER_TEAM_ROLES
        ]
        score = self._ratio(len(god_kills), len(kills))
        first_target = kills[0].get("target") if kills else None
        return {
            "score": score,
            "sample_size": len(kills),
            "god_kills": len(god_kills),
            "villager_team_kills": len(villager_team_kills),
            "first_target_role": self._role_of(players, first_target),
            "reasoning": f"狼人夜刀命中神职 {len(god_kills)}/{len(kills)} 次",
        }

    def _assess_hiding_ability(self, game_data: Dict[str, Any]) -> Dict[str, Any]:
        players = game_data.get("players", {})
        final_players = self._final_players(game_data)
        wolf_ids = [pid for pid, player in players.items() if player.get("role") == "werewolf"]
        surviving_wolves = [
            pid for pid in wolf_ids
            if final_players.get(pid, players.get(pid, {})).get("is_alive", True)
        ]
        wolf_deaths = [
            event for event in game_data.get("raw_events", [])
            if event.get("type") == "death" and event.get("player_id") in wolf_ids
        ]
        score = self._ratio(len(surviving_wolves), len(wolf_ids))
        return {
            "score": score,
            "sample_size": len(wolf_ids),
            "surviving_wolves": len(surviving_wolves),
            "wolf_deaths": len(wolf_deaths),
            "reasoning": f"终局存活狼人 {len(surviving_wolves)}/{len(wolf_ids)}",
        }

    def _assess_vote_strategy(self, game_data: Dict[str, Any]) -> Dict[str, Any]:
        players = game_data.get("players", {})
        wolf_votes = []
        anti_villager_votes = 0
        wolf_on_wolf_votes = 0
        for voter_id, target_id in self._day_votes(game_data):
            if self._role_of(players, voter_id) != "werewolf" or not target_id:
                continue
            wolf_votes.append((voter_id, target_id))
            if self._role_of(players, target_id) == "werewolf":
                wolf_on_wolf_votes += 1
            elif self._role_of(players, target_id) in self.VILLAGER_TEAM_ROLES:
                anti_villager_votes += 1
        score = self._ratio(anti_villager_votes, len(wolf_votes))
        return {
            "score": score,
            "sample_size": len(wolf_votes),
            "anti_villager_votes": anti_villager_votes,
            "wolf_on_wolf_votes": wolf_on_wolf_votes,
            "reasoning": f"狼人白天投向好人阵营 {anti_villager_votes}/{len(wolf_votes)} 票",
        }

    def _assess_check_accuracy(self, game_data: Dict[str, Any]) -> Dict[str, Any]:
        checks = self._night_actions(game_data, "check")
        wolf_checks = [action for action in checks if action.get("result") == "werewolf"]
        score = self._ratio(len(wolf_checks), len(checks))
        return {
            "score": score,
            "sample_size": len(checks),
            "wolf_checks": len(wolf_checks),
            "villager_checks": len(checks) - len(wolf_checks),
            "reasoning": f"预言家查验命中狼人 {len(wolf_checks)}/{len(checks)} 次",
        }

    def _assess_reveal_timing(self, game_data: Dict[str, Any]) -> Dict[str, Any]:
        players = game_data.get("players", {})
        seer_ids = {pid for pid, player in players.items() if player.get("role") == "seer"}
        reveal_keywords = ["预言家", "查验", "查杀", "金水", "验"]
        reveal_event = None
        for event in game_data.get("raw_events", []):
            if event.get("type") not in {"speech", "sheriff_speech", "pk_speech"}:
                continue
            if event.get("player_id") not in seer_ids:
                continue
            content = event.get("content", "")
            if any(keyword in content for keyword in reveal_keywords):
                reveal_event = event
                break

        if not reveal_event:
            return {
                "score": 0.0,
                "sample_size": len(seer_ids),
                "first_reveal_round": None,
                "reasoning": "未发现预言家明确报验人或身份信息的发言",
            }

        round_number = self._round_for_event(game_data, reveal_event)
        if round_number <= 1:
            score = 1.0
        elif round_number == 2:
            score = 0.7
        else:
            score = 0.4
        return {
            "score": score,
            "sample_size": 1,
            "first_reveal_round": round_number,
            "reasoning": f"预言家首次明确报信息发生在第 {round_number} 回合",
        }

    def _assess_save_usage(self, game_data: Dict[str, Any]) -> Dict[str, Any]:
        players = game_data.get("players", {})
        saves = self._night_actions(game_data, "save")
        villager_team_saves = [
            action for action in saves
            if self._role_of(players, action.get("target")) in self.VILLAGER_TEAM_ROLES
        ]
        god_saves = [action for action in saves if self._role_of(players, action.get("target")) in self.GOD_ROLES]
        score = self._ratio(len(villager_team_saves), len(saves))
        return {
            "score": score,
            "sample_size": len(saves),
            "villager_team_saves": len(villager_team_saves),
            "god_saves": len(god_saves),
            "reasoning": f"女巫解药救到好人阵营 {len(villager_team_saves)}/{len(saves)} 次",
        }

    def _assess_poison_usage(self, game_data: Dict[str, Any]) -> Dict[str, Any]:
        players = game_data.get("players", {})
        poisons = self._night_actions(game_data, "poison")
        wolf_poisons = [action for action in poisons if self._role_of(players, action.get("target")) == "werewolf"]
        score = self._ratio(len(wolf_poisons), len(poisons))
        return {
            "score": score,
            "sample_size": len(poisons),
            "wolf_poisons": len(wolf_poisons),
            "friendly_poisons": len(poisons) - len(wolf_poisons),
            "reasoning": f"女巫毒药命中狼人 {len(wolf_poisons)}/{len(poisons)} 次",
        }

    def _assess_shot_timing(self, game_data: Dict[str, Any]) -> Dict[str, Any]:
        players = game_data.get("players", {})
        hunter_shots = [
            event for event in game_data.get("raw_events", [])
            if event.get("type") == "death" and event.get("cause") == "hunter_shot"
        ]
        wolf_shots = [
            event for event in hunter_shots
            if self._role_of(players, event.get("player_id")) == "werewolf"
        ]
        score = self._ratio(len(wolf_shots), len(hunter_shots))
        return {
            "score": score,
            "sample_size": len(hunter_shots),
            "wolf_shots": len(wolf_shots),
            "friendly_shots": len(hunter_shots) - len(wolf_shots),
            "reasoning": f"猎人开枪带走狼人 {len(wolf_shots)}/{len(hunter_shots)} 次",
        }

    def _assess_villager_vote(self, game_data: Dict[str, Any]) -> Dict[str, Any]:
        players = game_data.get("players", {})
        villager_votes = []
        wolf_targets = 0
        for voter_id, target_id in self._day_votes(game_data):
            if self._role_of(players, voter_id) != "villager" or not target_id:
                continue
            villager_votes.append((voter_id, target_id))
            if self._role_of(players, target_id) == "werewolf":
                wolf_targets += 1
        score = self._ratio(wolf_targets, len(villager_votes))
        return {
            "score": score,
            "sample_size": len(villager_votes),
            "wolf_targets": wolf_targets,
            "friendly_targets": len(villager_votes) - wolf_targets,
            "reasoning": f"村民投票命中狼人 {wolf_targets}/{len(villager_votes)} 票",
        }

    def _calculate_win_rate(self, games_data: List[Dict[str, Any]], team: str) -> float:
        total = len(games_data)
        if total == 0:
            return 0.0
        wins = sum(1 for game in games_data if game.get("winner") == team)
        return wins / total

    def _calculate_average_rounds(self, games_data: List[Dict[str, Any]]) -> float:
        total = len(games_data)
        if total == 0:
            return 0.0
        rounds_sum = sum(game.get("metrics", {}).get("duration_rounds", 0) for game in games_data)
        return rounds_sum / total

    def _aggregate_role_analysis(self, all_analyses: List[Dict[str, Any]]) -> Dict[str, Any]:
        role_analysis = defaultdict(lambda: {"count": 0, "total_score": 0.0, "total_samples": 0})
        
        for analysis in all_analyses:
            for role in ["werewolf", "seer", "witch", "hunter", "villager"]:
                role_data = analysis.get(role, {})
                for key, value in role_data.items():
                    if isinstance(value, dict) and "score" in value:
                        sample_size = value.get("sample_size", 0)
                        if sample_size == 0:
                            continue
                        role_analysis[f"{role}_{key}"]["count"] += 1
                        role_analysis[f"{role}_{key}"]["total_score"] += value["score"]
                        role_analysis[f"{role}_{key}"]["total_samples"] += sample_size
        
        result = {}
        for key, data in role_analysis.items():
            if data["count"] > 0:
                result[key] = {
                    "average_score": data["total_score"] / data["count"],
                    "sample_size": data["total_samples"],
                    "game_count": data["count"],
                }
        return result

    def _aggregate_mistakes(self, all_analyses: List[Dict[str, Any]]) -> Dict[str, Any]:
        mistake_counts = defaultdict(int)
        
        for analysis in all_analyses:
            for mistake in analysis.get("mistakes", []):
                mistake_type = mistake.get("type", "unknown")
                mistake_counts[mistake_type] += 1
        
        return {
            "counts": dict(mistake_counts),
            "total": sum(mistake_counts.values()),
        }

    def generate_optimization_suggestions(self, aggregate_analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        suggestions = []
        role_analysis = aggregate_analysis.get("role_analysis", {})
        
        win_rate = aggregate_analysis.get("werewolf_win_rate", 0.5)
        
        if win_rate < 0.5:
            suggestions.append({
                "target": "werewolf",
                "type": "win_rate",
                "priority": "high",
                "suggestion": "狼人胜率偏低，需要优化首刀策略、白天抗推和隐藏能力",
            })
        elif win_rate > 0.7:
            suggestions.append({
                "target": "villager",
                "type": "win_rate",
                "priority": "high",
                "suggestion": "狼人胜率过高，需要优化好人阵营的分析和投票策略",
            })
        
        kill_score = self._aggregate_score(role_analysis, "werewolf_kill_accuracy")
        if kill_score is not None and kill_score < 0.6:
            suggestions.append({
                "target": "werewolf",
                "type": "night_kill",
                "priority": "high",
                "suggestion": "狼人夜刀命中神职比例偏低，应加强根据发言识别预言家、女巫、猎人的策略",
            })

        wolf_vote_score = self._aggregate_score(role_analysis, "werewolf_vote_strategy")
        if wolf_vote_score is not None and wolf_vote_score < 0.8:
            suggestions.append({
                "target": "werewolf",
                "type": "vote_strategy",
                "priority": "medium",
                "suggestion": "狼人白天投票没有稳定压向好人阵营，需要减少无意义倒钩和分票",
            })

        seer_score = self._aggregate_score(role_analysis, "seer_check_accuracy")
        if seer_score is not None and seer_score < 0.35:
            suggestions.append({
                "target": "seer",
                "type": "night_check",
                "priority": "medium",
                "suggestion": "预言家查验命中狼人比例偏低，应优先查验发言冲锋、站边异常和投票行为可疑的玩家",
            })

        villager_vote_score = self._aggregate_score(role_analysis, "villager_vote_accuracy")
        if villager_vote_score is not None and villager_vote_score < 0.35:
            suggestions.append({
                "target": "villager",
                "type": "vote_accuracy",
                "priority": "medium",
                "suggestion": "村民投票命中狼人比例偏低，应减少跟风票，强化基于警徽流、票型和发言矛盾的判断",
            })
        
        suggestions.append({
            "target": "all",
            "type": "general",
            "priority": "medium",
            "suggestion": "基于历史对局数据分析，优化各角色的Prompt和决策逻辑",
        })
        
        return suggestions

    def _night_actions(self, game_data: Dict[str, Any], action_type: str) -> List[Dict[str, Any]]:
        actions = []
        for event in game_data.get("raw_events", []):
            if event.get("type") != "night_action":
                continue
            action = event.get("action", {})
            if action.get("action") == action_type:
                actions.append(action)
        return actions

    def _day_votes(self, game_data: Dict[str, Any]) -> List[Tuple[Optional[str], Optional[str]]]:
        players = game_data.get("players", {})
        votes = []
        for event in game_data.get("raw_events", []):
            if event.get("type") != "vote_result":
                continue
            content = event.get("content", "")
            if not content.startswith("投票结果:"):
                continue
            votes.extend(self._parse_vote_content(content, players))
        return votes

    def _parse_vote_content(self, content: str, players: Dict[str, Any]) -> List[Tuple[Optional[str], Optional[str]]]:
        name_to_id = {player.get("name"): pid for pid, player in players.items()}
        raw_votes = content.replace("投票结果:", "", 1).strip()
        if not raw_votes:
            return []
        parsed = []
        for item in raw_votes.split(" | "):
            if ":" not in item:
                continue
            voter_name, target_name = [part.strip() for part in item.split(":", 1)]
            voter_name = re.sub(r"\s*\[警长\]$", "", voter_name).strip()
            voter_id = name_to_id.get(voter_name)
            target_id = None if target_name == "弃票" else name_to_id.get(target_name)
            parsed.append((voter_id, target_id))
        return parsed

    def _final_players(self, game_data: Dict[str, Any]) -> Dict[str, Any]:
        for event in reversed(game_data.get("raw_events", [])):
            if event.get("type") == "game_end":
                return event.get("game_state", {}).get("players", {})
        return {}

    def _round_for_event(self, game_data: Dict[str, Any], target_event: Dict[str, Any]) -> int:
        current_round = 1
        for event in game_data.get("raw_events", []):
            if event.get("type") == "phase_change" and event.get("round_number"):
                current_round = event["round_number"]
            if event is target_event:
                return current_round
        return current_round

    def _role_of(self, players: Dict[str, Any], player_id: Optional[str]) -> Optional[str]:
        if not player_id:
            return None
        return players.get(player_id, {}).get("role")

    def _ratio(self, numerator: int, denominator: int) -> float:
        if denominator <= 0:
            return 0.0
        return numerator / denominator

    def _aggregate_score(self, role_analysis: Dict[str, Any], key: str) -> Optional[float]:
        metric = role_analysis.get(key)
        if not metric:
            return None
        return metric.get("average_score")
