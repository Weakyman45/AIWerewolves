#!/usr/bin/env python3
import asyncio
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.evolution import EvolutionController


async def main():
    print("=" * 80)
    print("AI 狼人杀 - 自进化系统测试")
    print("=" * 80)
    
    controller = EvolutionController(
        num_games_per_iteration=5,
        win_rate_threshold=0.02
    )
    
    print("\n[1/4] 初始化系统...")
    controller.initialize(force=True)
    print(f"   ✓ 当前版本: {controller.current_version}")
    
    print("\n[2/4] 测试日志解析...")
    games = controller.parser.parse_all_games()
    print(f"   ✓ 找到 {len(games)} 个历史对局")
    
    print("\n[3/4] 测试版本管理...")
    versions = controller.version_control.list_versions()
    print(f"   ✓ 现有版本: {versions}")
    
    if versions:
        latest = versions[-1]
        print(f"   ✓ 最新版本: {latest}")
        metadata = controller.version_control.get_metadata(latest)
        if metadata:
            print(f"   ✓ 元数据: {metadata}")
    
    print("\n[4/4] 测试策略分析...")
    if games:
        analysis = controller.analyzer.analyze_multiple_games(games)
        print(f"   ✓ 分析结果:")
        print(f"     - 总对局数: {analysis.get('total_games', 0)}")
        print(f"     - 狼人胜率: {analysis.get('werewolf_win_rate', 0):.2%}")
        print(f"     - 好人胜率: {analysis.get('villager_win_rate', 0):.2%}")
        print(f"     - 平均回合数: {analysis.get('average_rounds', 0):.1f}")
    
    print("\n" + "=" * 80)
    print("测试完成！")
    print("=" * 80)
    
    print("\n下一步：")
    print("1. 运行完整的进化循环")
    print("2. 或者查看现有对局的分析")
    print("\n运行进化循环的代码示例：")
    print("""
    from backend.evolution import EvolutionController
    
    controller = EvolutionController()
    controller.initialize()
    
    result = asyncio.run(
        controller.start_evolution(max_iterations=3)
    )
    
    print(f"进化完成: {result}")
    """)


if __name__ == "__main__":
    asyncio.run(main())
