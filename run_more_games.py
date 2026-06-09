#!/usr/bin/env python3
import asyncio
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.engine.game import WerewolfGame
from backend.core.logger import GameLogger

async def run_games(num_games: int):
    print("=" * 80)
    print(f"AI 狼人杀 - 批量生成游戏数据 ({num_games} 局)")
    print("=" * 80)
    
    player_names = ["Alice", "Bob", "Charlie", "David", "Eve", "Frank", "Grace", "Henry", "Ivy"]
    
    wolf_wins = 0
    villager_wins = 0
    
    for i in range(num_games):
        print(f"\n--- 游戏 {i+1}/{num_games} ---")
        try:
            logger = GameLogger()
            game = WerewolfGame(player_names, logger)
            
            print(f"  游戏ID: {game.game_id[:12]}...")
            
            winner = await game.run()
            print(f"  胜者: {winner}")
            
            if winner == "werewolves":
                wolf_wins += 1
            else:
                villager_wins += 1
                
        except Exception as e:
            print(f"  ✗ 游戏出错: {e}")
    
    print("\n" + "=" * 80)
    print("批量游戏完成！")
    print("=" * 80)
    total = wolf_wins + villager_wins
    print(f"\n总游戏数: {total}")
    print(f"狼人胜利: {wolf_wins} ({wolf_wins/total*100:.1f}%)")
    print(f"好人胜利: {villager_wins} ({villager_wins/total*100:.1f}%)")
    print(f"\n日志已保存到 logs/ 目录")

if __name__ == "__main__":
    asyncio.run(run_games(15))  # 再运行15局，总共24局
