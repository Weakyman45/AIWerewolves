import asyncio
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime
from backend.evolution.parser import LogParser
from backend.evolution.version_control import VersionControl
from backend.evolution.analyzer import Analyzer
from backend.evolution.adapter import Adapter
from backend.evolution.ab_testing import ABTesting
from backend.core.logger import GameLogger


class EvolutionController:
    def __init__(self, initial_version: Optional[str] = None,
                 num_games_per_iteration: int = 20,
                 ab_games: int = 10,
                 win_rate_threshold: float = 0.05,
                 skip_ab: bool = False,
                 dry_run: bool = False,
                 fallback_only: bool = False,
                 game_runner: str = "live",
                 game_timeout: Optional[float] = None,
                 strategy_dir: Optional[str] = None,
                 log_dir: Optional[str] = None):
        self.parser = LogParser(log_dir)
        self.version_control = VersionControl(strategy_dir)
        self.analyzer = Analyzer()
        self.adapter = Adapter(fallback_only=fallback_only)
        self.ab_testing = ABTesting(
            strategy_dir,
            game_timeout=game_timeout,
            game_runner=game_runner,
            log_dir=log_dir,
        )

        self.current_version = initial_version or self.version_control.get_latest_version()
        self.num_games_per_iteration = num_games_per_iteration
        self.ab_games = ab_games
        self.win_rate_threshold = win_rate_threshold
        self.skip_ab = skip_ab
        self.dry_run = dry_run
        self.fallback_only = fallback_only
        self.game_runner = game_runner
        self.game_timeout = game_timeout
        
        self.evolution_history = []
        self.is_running = False

    def initialize(self, force: bool = False) -> bool:
        if self.current_version and not force:
            return True
        
        initial_version = "v0.0.1"
        
        if not self.version_control.version_exists(initial_version):
            prompts = self._get_initial_prompts()
            self.version_control.create_version(
                version=initial_version,
                parent_version=None,
                prompts=prompts,
                changes=["初始版本，基础Prompt"]
            )
        
        self.current_version = initial_version
        return True

    async def start_evolution(self, max_iterations: int = 10,
                        progress_callback: Optional[Callable] = None) -> Dict[str, Any]:
        if self.is_running:
            return {"error": "进化已经在运行中"}
        
        self.is_running = True
        
        try:
            if not self.current_version:
                self.initialize()
            
            for iteration in range(max_iterations):
                if not self.is_running:
                    break
                
                if progress_callback:
                    progress_callback(iteration + 1, max_iterations, "starting")
                
                result = await self._run_evolution_iteration(iteration + 1)
                
                self.evolution_history.append({
                    "iteration": iteration + 1,
                    "timestamp": datetime.now().isoformat(),
                    "result": result,
                })
                
                if progress_callback:
                    progress_callback(iteration + 1, max_iterations, "completed", result)
            
            final_result = {
                "success": True,
                "total_iterations": len(self.evolution_history),
                "final_version": self.current_version,
                "history": self.evolution_history,
            }
            
            return final_result
            
        finally:
            self.is_running = False

    def stop_evolution(self):
        self.is_running = False

    async def _run_evolution_iteration(self, iteration: int) -> Dict[str, Any]:
        print(f"\n=== 进化迭代 {iteration} ===")
        print(f"当前版本: {self.current_version}")
        old_version = self.current_version
        
        if self.dry_run:
            print("1. 生成训练对局... 跳过（dry-run）")
            game_results = []
        else:
            print("1. 生成训练对局...")
            game_results = await self._generate_training_games()
        
        print("2. 分析对局数据...")
        analysis = self._analyze_game_results(game_results)
        
        print("3. 优化策略...")
        new_version = await self._optimize_strategy(analysis)
        
        if self.skip_ab or self.dry_run:
            print("4. A/B测试验证... 跳过")
            ab_result = {
                "skipped": True,
                "reason": "dry-run" if self.dry_run else "skip_ab",
                "a_win_rate": 0,
                "b_win_rate": 0,
                "statistics": {"significant": False, "p_value": 1.0},
            }
            accepted = False
        else:
            print("4. A/B测试验证...")
            ab_result = await self._run_ab_test(new_version)
            
            print("5. 判断是否接受新版本...")
            accepted = self._decide_acceptance(ab_result)

        improvement = ab_result.get("b_win_rate", 0) - ab_result.get("a_win_rate", 0)
        self._record_candidate_validation(
            new_version,
            old_version,
            accepted,
            ab_result,
            improvement,
        )
        
        if accepted:
            print(f"✓ 接受新版本 {new_version}")
            self.current_version = new_version
            self.version_control.promote_version(new_version)
        else:
            print(f"✗ 拒绝新版本，保留 {self.current_version}")
            if old_version:
                self.current_version = old_version
                self.version_control.rollback(old_version)
        
        return {
            "iteration": iteration,
            "old_version": old_version,
            "new_version": new_version,
            "accepted": accepted,
            "improvement": improvement,
            "analysis": analysis,
            "ab_result": ab_result,
        }

    async def _generate_training_games(self) -> List[Dict[str, Any]]:
        if self.game_runner in {"live", "live-fast"}:
            from backend.engine.game import WerewolfGame
        else:
            from backend.evolution.mock_game import MockGameRunner

        player_names = ["Alice", "Bob", "Charlie", "David", "Eve", "Frank"]
        results = []
        
        print(f"    开始生成 {self.num_games_per_iteration} 局训练对局...")
        
        for i in range(self.num_games_per_iteration):
            print(f"    游戏 {i+1}/{self.num_games_per_iteration} 开始...")
            logger = GameLogger(log_dir=self.parser.log_dir)
            if self.game_runner in {"live", "live-fast"}:
                game_kwargs = {
                    "strategy_prompts": self._load_all_role_prompts(self.current_version),
                }
                if self.game_runner == "live-fast":
                    game_kwargs.update({
                        "skip_sheriff": True,
                        "max_rounds": 1,
                        "sleep_scale": 0.0,
                        "skip_last_words": True,
                    })
                game = WerewolfGame(player_names, logger, **game_kwargs)
            else:
                game = MockGameRunner(
                    player_names,
                    logger,
                    seed_key=f"train:{self.current_version}:{i + 1}",
                    werewolf_version=self.current_version,
                    other_version=self.current_version,
                )
            
            try:
                print(f"    游戏 {i+1}: 正在运行...")
                if self.game_timeout:
                    winner = await asyncio.wait_for(game.run(), timeout=self.game_timeout)
                else:
                    winner = await game.run()
                print(f"    游戏 {i+1}: 运行完成")
                winner_value = winner.value if hasattr(winner, "value") else winner
                
                game_data = {
                    "game_id": game.game_id,
                    "winner": winner_value,
                    "status": "completed",
                    "error": None,
                    "error_type": None,
                    "runner": self.game_runner,
                    "timestamp": datetime.now().isoformat(),
                }
                
                results.append(game_data)
                
                self.version_control.add_game_result(
                    self.current_version,
                    game_data
                )
                
                print(f"    游戏 {i+1}/{self.num_games_per_iteration}: {winner_value} 获胜")
                
            except asyncio.TimeoutError as e:
                game_data = self._build_failed_game_result(game, e, "timed_out")
                results.append(game_data)
                print(f"    游戏 {i+1}/{self.num_games_per_iteration}: 超时（{self.game_timeout}秒）")
            except Exception as e:
                game_data = self._build_failed_game_result(game, e, "failed")
                results.append(game_data)
                print(f"    游戏 {i+1}/{self.num_games_per_iteration}: 失败（{type(e).__name__}: {e}）")

        summary = self._summarize_training_results(results)
        print(
            "    训练对局生成完成："
            f"完成 {summary['completed']} 局，"
            f"超时 {summary['timed_out']} 局，"
            f"失败 {summary['failed']} 局"
        )
        return results

    def _analyze_game_results(self, game_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        all_games = [
            game for game in self.parser.parse_all_games()
            if game.get("winner") in {"werewolves", "villagers"}
        ]
        
        completed_results = [
            result for result in game_results
            if result.get("status") in {None, "completed"}
        ]

        for game_result in completed_results:
            game_id = game_result.get("game_id")
            parsed_game = self.parser.parse_game(game_id)
            if (
                parsed_game
                and parsed_game.get("winner") in {"werewolves", "villagers"}
                and game_id not in [g.get("game_id") for g in all_games]
            ):
                all_games.append(parsed_game)
        
        aggregate_analysis = self.analyzer.analyze_multiple_games(all_games)
        
        suggestions = self.analyzer.generate_optimization_suggestions(aggregate_analysis)
        
        return {
            "aggregate": aggregate_analysis,
            "suggestions": suggestions,
            "game_count": len(completed_results),
            "training_summary": self._summarize_training_results(game_results),
        }

    async def _optimize_strategy(self, analysis: Dict[str, Any]) -> str:
        old_version = self.current_version
        new_version = self._get_next_available_version(old_version)
        
        print(f"  优化策略: {old_version} -> {new_version}")
        
        prompts = {}
        role_optimizations = {}
        for role in ["werewolf", "seer", "witch", "hunter", "villager"]:
            original_prompt = self.version_control.get_prompt(old_version, role)
            if original_prompt:
                optimization = self.adapter.optimize_prompt(
                    original_prompt, role, analysis["aggregate"]
                )
                prompts[role] = optimization["optimized"]
                role_optimizations[role] = {
                    "reasoning": optimization.get("reasoning", ""),
                    "key_changes": optimization.get("key_changes", []),
                }
        
        changes = []
        for suggestion in analysis["suggestions"]:
            changes.append(suggestion.get("suggestion", ""))
        for role, optimization in role_optimizations.items():
            for change in optimization.get("key_changes", []):
                changes.append(f"{role}: {change}")
        changes = list(dict.fromkeys(change for change in changes if change))

        aggregate = analysis["aggregate"]
        metadata_extra = {
            "status": "candidate",
            "accepted": None,
            "candidate_from": old_version,
            "analysis_summary": {
                "total_games": aggregate.get("total_games", 0),
                "werewolf_win_rate": aggregate.get("werewolf_win_rate", 0),
                "villager_win_rate": aggregate.get("villager_win_rate", 0),
                "average_rounds": aggregate.get("average_rounds", 0),
                "role_analysis": aggregate.get("role_analysis", {}),
                "common_mistakes": aggregate.get("common_mistakes", {}),
                "quality_metrics": aggregate.get("quality_metrics", {}),
            },
            "training_summary": analysis.get("training_summary", {}),
            "role_optimizations": role_optimizations,
        }
        
        self.version_control.create_version(
            version=new_version,
            parent_version=old_version,
            prompts=prompts,
            changes=changes,
            metadata_extra=metadata_extra,
            update_latest=False,
        )
        
        return new_version

    def _load_all_role_prompts(self, version: Optional[str]) -> Dict[str, str]:
        if not version:
            return {}
        prompts = {}
        for role in ["werewolf", "seer", "witch", "hunter", "villager"]:
            prompt = self.version_control.get_prompt(version, role)
            if prompt:
                prompts[role] = prompt
        return prompts

    def _record_candidate_validation(
        self,
        version: str,
        parent_version: Optional[str],
        accepted: bool,
        ab_result: Dict[str, Any],
        improvement: float,
    ) -> None:
        metadata = self.version_control.get_metadata(version) or {}
        metadata.update({
            "status": "accepted" if accepted else "rejected",
            "accepted": accepted,
            "validated_at": datetime.now().isoformat(),
            "parent": metadata.get("parent") or parent_version,
            "ab_result": {
                "version_a": ab_result.get("version_a"),
                "version_b": ab_result.get("version_b"),
                "total_games": ab_result.get("total_games", 0),
                "successful_games": ab_result.get("successful_games", 0),
                "failed_games": ab_result.get("failed_games", 0),
                "a_wins": ab_result.get("a_wins", 0),
                "b_wins": ab_result.get("b_wins", 0),
                "a_win_rate": ab_result.get("a_win_rate", 0),
                "b_win_rate": ab_result.get("b_win_rate", 0),
                "better_version": ab_result.get("better_version"),
                "statistics": ab_result.get("statistics", {}),
                "skipped": ab_result.get("skipped", False),
                "reason": ab_result.get("reason"),
            },
            "improvement": improvement,
            "promotion_summary": (
                f"A/B 通过，候选胜率提升 {improvement:+.1%}，已晋级为当前上场版本。"
                if accepted
                else f"A/B 未通过，候选胜率变化 {improvement:+.1%}，保留 {parent_version}。"
            ),
        })
        self.version_control.update_metadata(version, metadata)

    def _get_next_available_version(self, base_version: Optional[str]) -> str:
        next_version = self.version_control.get_next_version(base_version)
        while self.version_control.version_exists(next_version):
            next_version = self.version_control.get_next_version(next_version)
        return next_version

    async def _run_ab_test(self, new_version: str) -> Dict[str, Any]:
        old_version = self.current_version
        
        print(f"  A/B测试: {old_version} vs {new_version}")
        
        result = await self.ab_testing.run_comparison(
            old_version, new_version, num_games=self.ab_games
        )
        
        stats = self.ab_testing.calculate_statistical_significance(result)
        result["statistics"] = stats
        
        return result

    def _decide_acceptance(self, ab_result: Dict[str, Any]) -> bool:
        a_win_rate = ab_result.get("a_win_rate", 0.5)
        b_win_rate = ab_result.get("b_win_rate", 0.5)
        
        improvement = b_win_rate - a_win_rate
        
        stats = ab_result.get("statistics", {})
        significant = stats.get("significant", False)
        
        print(f"  胜率变化: {a_win_rate:.2%} -> {b_win_rate:.2%} (改进: {improvement:+.2%})")
        print(f"  统计显著性: {'显著' if significant else '不显著'}")
        
        if improvement > 0 and (significant or improvement >= self.win_rate_threshold):
            return True
        
        return False

    def _get_previous_version(self, version: str) -> Optional[str]:
        metadata = self.version_control.get_metadata(version)
        if metadata:
            return metadata.get("parent")
        return None

    def _build_failed_game_result(
        self,
        game: Any,
        error: Exception,
        status: str,
    ) -> Dict[str, Any]:
        return {
            "game_id": game.game_id,
            "winner": None,
            "status": status,
            "error": str(error),
            "error_type": type(error).__name__,
            "timestamp": datetime.now().isoformat(),
        }

    def _summarize_training_results(self, game_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        summary = {
            "requested": getattr(self, "num_games_per_iteration", len(game_results)),
            "total_attempted": len(game_results),
            "completed": 0,
            "timed_out": 0,
            "failed": 0,
            "failed_by_type": {},
        }

        for result in game_results:
            status = result.get("status") or "completed"
            if status == "completed":
                summary["completed"] += 1
            elif status == "timed_out":
                summary["timed_out"] += 1
            else:
                summary["failed"] += 1

            if status != "completed":
                error_type = result.get("error_type") or "UnknownError"
                summary["failed_by_type"][error_type] = (
                    summary["failed_by_type"].get(error_type, 0) + 1
                )

        return summary

    def _get_initial_prompts(self) -> Dict[str, str]:
        return {
            "werewolf": """你是一个专业的狼人杀玩家，你的身份是【狼人】。

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
- 你可以在白天发言阶段选择自爆，自爆后你会直接死亡，当前白天立即结束进入黑夜，你没有遗言""",
            
            "seer": """你是一个专业的狼人杀玩家，你的身份是【预言家】。

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
- 发言要有逻辑，分析场上局势""",
            
            "witch": """你是一个专业的狼人杀玩家，你的身份是【女巫】。

你的目标：
1. 用好解药和毒药，帮助好人阵营获胜
2. 解药可以救起被狼人杀死的玩家
3. 毒药可以毒死一名玩家
4. 隐藏自己的身份，避免被狼人提前杀死

你的技能：
- 一瓶解药（只能使用一次）
- 一瓶毒药（只能使用一次）

重要规则：
- 解药优先考虑救预言家
- 毒药要用于毒杀你认为的狼人
- 可以在适当时机跳身份，带队投票
- 每剂药只能使用一次！""",
            
            "hunter": """你是一个专业的狼人杀玩家，你的身份是【猎人】。

你的目标：
1. 帮助好人阵营找出狼人并公投出局
2. 如果被杀死或公投出局，可以开枪带走一名玩家
3. 隐藏自己的身份，避免被狼人提前杀死

你的技能：
- 死亡时可以开枪带走一名玩家

重要规则：
- 只有在死亡时才能开枪
- 尽量选择你认为的狼人开枪
- 可以在适当时机跳身份自证""",
            
            "villager": """你是一个专业的狼人杀玩家，你的身份是【村民】。

你的目标：
1. 帮助好人阵营找出狼人并公投出局
2. 分析场上局势，投出你认为的狼人
3. 保护好自己，不要被狼人提前杀死

重要规则：
- 没有特殊技能
- 仔细听发言，分析谁是狼人
- 投票要谨慎，不要投错好人
- 可以跳民身份，避免被抗推""",
        }

    def get_status(self) -> Dict[str, Any]:
        return {
            "is_running": self.is_running,
            "current_version": self.current_version,
            "evolution_count": len(self.evolution_history),
            "latest_evolution": self.evolution_history[-1] if self.evolution_history else None,
        }

    def get_history(self) -> List[Dict[str, Any]]:
        return self.evolution_history

    def rollback_to_version(self, version: str) -> bool:
        if self.version_control.version_exists(version):
            self.current_version = version
            self.version_control.rollback(version)
            return True
        return False
