import asyncio
from typing import Dict, List, Any, Optional, Callable
from collections import defaultdict
from backend.core.logger import GameLogger
from backend.evolution.version_control import VersionControl


class ABTesting:
    def __init__(
        self,
        strategy_dir: Optional[str] = None,
        game_timeout: Optional[float] = None,
        game_runner: str = "live",
        log_dir: Optional[str] = None,
    ):
        self.results = []
        self.version_control = VersionControl(strategy_dir)
        self.game_timeout = game_timeout
        self.game_runner = game_runner
        self.log_dir = log_dir

    async def run_comparison(self, version_a: str, version_b: str, 
                         num_games: int = 10,
                         player_names: Optional[List[str]] = None,
                         progress_callback: Optional[Callable] = None) -> Dict[str, Any]:
        if player_names is None:
            player_names = ["Alice", "Bob", "Charlie", "David", "Eve", "Frank"]
        
        results_a_wins = 0
        results_b_wins = 0
        game_results = []
        
        print(f"  A/B测试: 开始 {num_games} 局测试...")
        
        for i in range(num_games):
            if progress_callback:
                progress_callback(i + 1, num_games)
            
            print(f"    游戏 {i+1}/{num_games} 开始...")
            
            a_as_werewolves = i % 2 == 0
            if a_as_werewolves:
                game_result = await self._run_single_game(version_a, version_b, player_names)
                werewolf_version = version_a
                villager_version = version_b
            else:
                game_result = await self._run_single_game(version_b, version_a, player_names)
                werewolf_version = version_b
                villager_version = version_a
            
            game_result.update({
                "game_number": i + 1,
                "a_as_werewolves": a_as_werewolves,
                "werewolf_version": werewolf_version,
                "villager_version": villager_version,
            })
            game_results.append(game_result)

            if not game_result["success"]:
                print(f"    游戏 {i+1}/{num_games} 失败: {game_result['error']}")
                continue

            winner = game_result["winner"]
            if winner == "werewolves":
                if a_as_werewolves:
                    results_a_wins += 1
                else:
                    results_b_wins += 1
            else:
                if a_as_werewolves:
                    results_b_wins += 1
                else:
                    results_a_wins += 1
            
            print(f"    游戏 {i+1}/{num_games} 完成: {winner} 获胜")
        
        successful_games = len([result for result in game_results if result["success"]])
        failed_games = len(game_results) - successful_games
        analysis = {
            "version_a": version_a,
            "version_b": version_b,
            "total_games": len(game_results),
            "successful_games": successful_games,
            "failed_games": failed_games,
            "a_wins": results_a_wins,
            "b_wins": results_b_wins,
            "a_win_rate": results_a_wins / successful_games if successful_games > 0 else 0,
            "b_win_rate": results_b_wins / successful_games if successful_games > 0 else 0,
            "game_results": game_results,
            "better_version": self._determine_better_version(results_a_wins, results_b_wins, version_a, version_b),
        }
        
        self.results.append(analysis)
        return analysis

    async def _run_single_game(self, werewolf_version: str, other_version: str,
                          player_names: List[str]) -> Dict[str, Any]:
        if getattr(self, "game_runner", "live") == "live":
            from backend.engine.game import WerewolfGame
        else:
            from backend.evolution.mock_game import MockGameRunner

        logger = GameLogger(log_dir=getattr(self, "log_dir", None) or "./logs")
        if getattr(self, "game_runner", "live") == "live":
            strategy_prompts = self._build_strategy_prompts(werewolf_version, other_version)
            game = WerewolfGame(player_names, logger, strategy_prompts=strategy_prompts)
        else:
            game_index = getattr(self, "_mock_game_counter", 0) + 1
            self._mock_game_counter = game_index
            game = MockGameRunner(
                player_names,
                logger,
                seed_key=f"ab:{werewolf_version}:{other_version}:{game_index}",
                werewolf_version=werewolf_version,
                other_version=other_version,
            )
        
        try:
            if self.game_timeout:
                winner = await asyncio.wait_for(game.run(), timeout=self.game_timeout)
            else:
                winner = await game.run()
            return {
                "success": True,
                "game_id": game.game_id,
                "winner": winner.value if hasattr(winner, "value") else winner,
                "error": None,
                "runner": getattr(self, "game_runner", "live"),
            }
        except Exception as e:
            print(f"游戏运行出错: {e}")
            return {
                "success": False,
                "game_id": game.game_id,
                "winner": None,
                "error": str(e),
                "error_type": type(e).__name__,
                "runner": getattr(self, "game_runner", "live"),
            }

    def _build_strategy_prompts(self, werewolf_version: str, other_version: str) -> Dict[str, str]:
        prompts = {}
        werewolf_prompt = self.version_control.get_prompt(werewolf_version, "werewolf")
        if werewolf_prompt:
            prompts["werewolf"] = werewolf_prompt

        for role in ["seer", "witch", "hunter", "villager"]:
            prompt = self.version_control.get_prompt(other_version, role)
            if prompt:
                prompts[role] = prompt
        return prompts

    def _determine_better_version(self, a_wins: int, b_wins: int, 
                              version_a: str, version_b: str) -> Optional[str]:
        if a_wins > b_wins:
            return version_a
        elif b_wins > a_wins:
            return version_b
        else:
            return None

    def run_rollout_test(self, version: str, num_games: int = 20,
                    player_names: Optional[List[str]] = None) -> Dict[str, Any]:
        from backend.engine.game import WerewolfGame

        if player_names is None:
            player_names = ["Alice", "Bob", "Charlie", "David", "Eve", "Frank"]
        
        results = []
        werewolf_wins = 0
        villager_wins = 0
        
        for i in range(num_games):
            logger = GameLogger()
            game = WerewolfGame(player_names, logger)
            
            winner = asyncio.run(game.run())
            
            results.append({
                "game_number": i + 1,
                "winner": winner,
            })
            
            if winner == "werewolves":
                werewolf_wins += 1
            else:
                villager_wins += 1
        
        total = len(results)
        return {
            "version": version,
            "total_games": total,
            "werewolf_wins": werewolf_wins,
            "villager_wins": villager_wins,
            "werewolf_win_rate": werewolf_wins / total if total > 0 else 0,
            "villager_win_rate": villager_wins / total if total > 0 else 0,
            "results": results,
        }

    def compare_multiple_versions(self, versions: List[str], num_games: int = 5) -> Dict[str, Any]:
        comparisons = []
        win_rates = defaultdict(int)
        
        for i in range(len(versions)):
            for j in range(i + 1, len(versions)):
                version_a = versions[i]
                version_b = versions[j]
                
                comparison = asyncio.run(
                    self.run_comparison(version_a, version_b, num_games)
                )
                
                comparisons.append(comparison)
                
                if comparison.get("better_version") == version_a:
                    win_rates[version_a] += 1
                elif comparison.get("better_version") == version_b:
                    win_rates[version_b] += 1
        
        sorted_versions = sorted(
            win_rates.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        return {
            "comparisons": comparisons,
            "leaderboard": sorted_versions,
        }

    def calculate_statistical_significance(self, result: Dict[str, Any]) -> Dict[str, Any]:
        a_wins = result.get("a_wins", 0)
        b_wins = result.get("b_wins", 0)
        total = a_wins + b_wins
        
        if total == 0:
            return {"significant": False, "p_value": 1.0}
        
        observed_diff = abs(a_wins - b_wins) / total
        expected_diff = 0
        
        p_value = self._calculate_p_value(a_wins, b_wins, total)
        
        return {
            "significant": p_value < 0.05,
            "p_value": p_value,
            "confidence_95": self._calculate_confidence_interval(a_wins, b_wins, 0.95),
        }

    def _calculate_p_value(self, a_wins: int, b_wins: int, total: int) -> float:
        import math

        if total <= 0:
            return 1.0

        smaller_side_wins = min(a_wins, b_wins)
        one_tail = sum(
            math.comb(total, wins) * (0.5 ** total)
            for wins in range(smaller_side_wins + 1)
        )
        p_value = 2 * one_tail

        return max(0.0, min(1.0, p_value))

    def _normal_cdf(self, x: float) -> float:
        import math
        
        a1 = 0.254829592
        a2 = -0.284496736
        a3 = 1.421413741
        a4 = -1.453152027
        a5 = 1.061405429
        p = 0.3275911
        
        sign = 1 if x >= 0 else -1
        x = abs(x)
        
        t = 1.0 / (1.0 + p * x)
        y = ((((a5 * t + a4) * t + a3) * t + a2) * t + a1) * t
        
        return 0.5 * sign * y + 0.5

    def _calculate_confidence_interval(self, a_wins: int, b_wins: int, 
                                 confidence: float) -> Dict[str, float]:
        import math
        
        total = a_wins + b_wins
        if total == 0:
            return {"lower": 0, "upper": 0}
        
        p = a_wins / total
        z = 1.96 if confidence == 0.95 else 2.576
        
        margin = z * math.sqrt(p * (1 - p) / total)
        
        return {
            "lower": max(0, p - margin),
            "upper": min(1, p + margin),
        }
