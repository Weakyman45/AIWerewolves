from typing import Dict, List, Any, Optional
from collections import defaultdict


class Analyzer:
    def __init__(self):
        pass

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
        return {
            "duration_rounds": metrics.get("duration_rounds", 0),
            "key_moments": metrics.get("key_moments", []),
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
        
        for event in events:
            mistake = self._check_event_for_mistake(event)
            if mistake:
                mistakes.append(mistake)
        
        return mistakes

    def _check_event_for_mistake(self, event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        event_type = event.get("type")
        
        if event_type == "night_action":
            action = event.get("action", {})
            if action.get("action") in ["kill", "poison"]:
                return {
                    "type": "night_action_mistake",
                    "action": action,
                    "severity": "medium",
                }
        
        return None

    def _assess_kill_accuracy(self, game_data: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "score": 0.5,
            "reasoning": "需要完整的玩家角色数据进行评估",
        }

    def _assess_hiding_ability(self, game_data: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "score": 0.5,
            "reasoning": "需要完整的玩家存活数据进行评估",
        }

    def _assess_vote_strategy(self, game_data: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "score": 0.5,
            "reasoning": "需要完整的投票数据进行评估",
        }

    def _assess_check_accuracy(self, game_data: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "score": 0.5,
            "reasoning": "需要完整的查验结果数据进行评估",
        }

    def _assess_reveal_timing(self, game_data: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "score": 0.5,
            "reasoning": "需要完整的发言数据进行评估",
        }

    def _assess_save_usage(self, game_data: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "score": 0.5,
            "reasoning": "需要完整的解药使用数据进行评估",
        }

    def _assess_poison_usage(self, game_data: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "score": 0.5,
            "reasoning": "需要完整的毒药使用数据进行评估",
        }

    def _assess_shot_timing(self, game_data: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "score": 0.5,
            "reasoning": "需要完整的猎人开枪数据进行评估",
        }

    def _assess_villager_vote(self, game_data: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "score": 0.5,
            "reasoning": "需要完整的村民投票数据进行评估",
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
        role_analysis = defaultdict(lambda: {"count": 0, "total_score": 0.0})
        
        for analysis in all_analyses:
            for role in ["werewolf", "seer", "witch", "hunter", "villager"]:
                role_data = analysis.get(role, {})
                for key, value in role_data.items():
                    if isinstance(value, dict) and "score" in value:
                        role_analysis[f"{role}_{key}"]["count"] += 1
                        role_analysis[f"{role}_{key}"]["total_score"] += value["score"]
        
        result = {}
        for key, data in role_analysis.items():
            if data["count"] > 0:
                result[key] = {
                    "average_score": data["total_score"] / data["count"],
                    "sample_size": data["count"],
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
        
        win_rate = aggregate_analysis.get("werewolf_win_rate", 0.5)
        
        if win_rate < 0.5:
            suggestions.append({
                "target": "werewolf",
                "type": "win_rate",
                "priority": "high",
                "suggestion": "狼人胜率偏低，需要优化首刀策略和隐藏能力",
            })
        elif win_rate > 0.7:
            suggestions.append({
                "target": "villager",
                "type": "win_rate",
                "priority": "high",
                "suggestion": "狼人胜率过高，需要优化好人阵营的分析和投票策略",
            })
        
        suggestions.append({
            "target": "all",
            "type": "general",
            "priority": "medium",
            "suggestion": "基于历史对局数据分析，优化各角色的Prompt和决策逻辑",
        })
        
        return suggestions
