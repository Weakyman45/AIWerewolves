import asyncio
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime
from backend.evolution.parser import LogParser
from backend.evolution.version_control import VersionControl
from backend.evolution.analyzer import Analyzer
from backend.evolution.adapter import Adapter
from backend.evolution.ab_testing import ABTesting
from backend.engine.game import WerewolfGame
from backend.core.logger import GameLogger


class EvolutionController:
    def __init__(self, initial_version: Optional[str] = None,
                 num_games_per_iteration: int = 20,
                 win_rate_threshold: float = 0.05,
                 strategy_dir: Optional[str] = None,
                 log_dir: Optional[str] = None):
        self.parser = LogParser(log_dir)
        self.version_control = VersionControl(strategy_dir)
        self.analyzer = Analyzer()
        self.adapter = Adapter()
        self.ab_testing = ABTesting()
        
        self.current_version = initial_version or self.version_control.get_latest_version()
        self.num_games_per_iteration = num_games_per_iteration
        self.win_rate_threshold = win_rate_threshold
        
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
        
        print("1. 生成训练对局...")
        game_results = await self._generate_training_games()
        
        print("2. 分析对局数据...")
        analysis = self._analyze_game_results(game_results)
        
        print("3. 优化策略...")
        new_version = await self._optimize_strategy(analysis)
        
        print("4. A/B测试验证...")
        ab_result = await self._run_ab_test(new_version)
        
        print("5. 判断是否接受新版本...")
        accepted = self._decide_acceptance(ab_result)
        
        if accepted:
            print(f"✓ 接受新版本 {new_version}")
            self.current_version = new_version
        else:
            print(f"✗ 拒绝新版本，保留 {self.current_version}")
        
        return {
            "iteration": iteration,
            "old_version": self.current_version if not accepted else self._get_previous_version(new_version),
            "new_version": new_version,
            "accepted": accepted,
            "analysis": analysis,
            "ab_result": ab_result,
        }

    async def _generate_training_games(self) -> List[Dict[str, Any]]:
        player_names = ["Alice", "Bob", "Charlie", "David", "Eve", "Frank"]
        results = []
        
        print(f"    开始生成 {self.num_games_per_iteration} 局训练对局...")
        
        for i in range(self.num_games_per_iteration):
            print(f"    游戏 {i+1}/{self.num_games_per_iteration} 开始...")
            logger = GameLogger()
            game = WerewolfGame(player_names, logger)
            
            try:
                print(f"    游戏 {i+1}: 正在运行...")
                winner = await game.run()
                print(f"    游戏 {i+1}: 运行完成")
                
                game_data = {
                    "game_id": game.game_id,
                    "winner": winner,
                    "timestamp": datetime.now().isoformat(),
                }
                
                results.append(game_data)
                
                self.version_control.add_game_result(
                    self.current_version,
                    game_data
                )
                
                print(f"    游戏 {i+1}/{self.num_games_per_iteration}: {winner} 获胜")
                
            except Exception as e:
                print(f"    游戏 {i+1} 出错: {e}")
                import traceback
                traceback.print_exc()
        
        print(f"    训练对局生成完成，共 {len(results)} 局")
        return results

    def _analyze_game_results(self, game_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        all_games = self.parser.parse_all_games()
        
        for game_result in game_results:
            game_id = game_result.get("game_id")
            parsed_game = self.parser.parse_game(game_id)
            if parsed_game and game_id not in [g.get("game_id") for g in all_games]:
                all_games.append(parsed_game)
        
        aggregate_analysis = self.analyzer.analyze_multiple_games(all_games)
        
        suggestions = self.analyzer.generate_optimization_suggestions(aggregate_analysis)
        
        return {
            "aggregate": aggregate_analysis,
            "suggestions": suggestions,
            "game_count": len(game_results),
        }

    async def _optimize_strategy(self, analysis: Dict[str, Any]) -> str:
        old_version = self.current_version
        new_version = self.version_control.get_next_version(old_version)
        
        print(f"  优化策略: {old_version} -> {new_version}")
        
        prompts = {}
        for role in ["werewolf", "seer", "witch", "hunter", "villager"]:
            original_prompt = self.version_control.get_prompt(old_version, role)
            if original_prompt:
                optimization = self.adapter.optimize_prompt(
                    original_prompt, role, analysis["aggregate"]
                )
                prompts[role] = optimization["optimized"]
        
        changes = []
        for suggestion in analysis["suggestions"]:
            changes.append(suggestion.get("suggestion", ""))
        
        self.version_control.create_version(
            version=new_version,
            parent_version=old_version,
            prompts=prompts,
            changes=changes
        )
        
        return new_version

    async def _run_ab_test(self, new_version: str) -> Dict[str, Any]:
        old_version = self.current_version
        
        print(f"  A/B测试: {old_version} vs {new_version}")
        
        result = await self.ab_testing.run_comparison(
            old_version, new_version, num_games=10
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
- 可以适当跳预言家或其他神职来搅局
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
