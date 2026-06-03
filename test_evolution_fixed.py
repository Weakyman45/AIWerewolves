#!/usr/bin/env python3
import asyncio
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.evolution import LogParser, Analyzer

def main():
    print("=" * 80)
    print("AI 狼人杀 - 测试日志解析和分析")
    print("=" * 80)

    # 测试日志解析
    print("\n[1/4] 解析日志...")
    parser = LogParser()
    all_games = parser.parse_all_games()
    
    # 只使用有winner的游戏
    complete_games = [g for g in all_games if g.get("winner") is not None]
    print(f"  ✓ 共找到 {len(all_games)} 个日志文件")
    print(f"  ✓ 其中 {len(complete_games)} 个完整游戏")

    if not complete_games:
        print("  ✗ 没有找到完整的游戏日志！")
        return

    # 显示每个完整游戏的winner
    print("\n[2/4] 完整游戏统计:")
    wolf_wins = 0
    villager_wins = 0
    for i, game in enumerate(complete_games):
        winner = game.get("winner")
        if winner == "werewolves":
            wolf_wins += 1
        elif winner == "villagers":
            villager_wins += 1
        print(f"  游戏 {i+1}: {game.get('game_id')[:8]}... - 胜者: {winner}")

    print(f"\n[3/4] 胜率统计:")
    total = len(complete_games)
    print(f"  总游戏数: {total}")
    print(f"  狼人胜利: {wolf_wins} ({wolf_wins/total*100:.1f}%)")
    print(f"  好人胜利: {villager_wins} ({villager_wins/total*100:.1f}%)")

    # 测试分析器
    print(f"\n[4/4] 分析所有游戏...")
    analyzer = Analyzer()
    result = analyzer.analyze_multiple_games(complete_games)
    
    print(f"\n分析结果:")
    print(f"  总游戏数: {result.get('total_games')}")
    print(f"  狼人胜率: {result.get('werewolf_win_rate')*100:.1f}%")
    print(f"  好人胜率: {result.get('villager_win_rate')*100:.1f}%")
    print(f"  平均回合数: {result.get('average_rounds'):.1f}")

    # 生成优化建议
    suggestions = analyzer.generate_optimization_suggestions(result)
    print(f"\n优化建议:")
    for i, s in enumerate(suggestions):
        print(f"  {i+1}. [{s.get('priority')}] {s.get('suggestion')}")

    print("\n" + "=" * 80)
    print("测试完成！")
    print("=" * 80)

if __name__ == "__main__":
    main()
