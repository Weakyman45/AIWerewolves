#!/usr/bin/env python3
import asyncio
import sys
import os
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.engine.game import WerewolfGame
from backend.core.logger import GameLogger

async def run_single_game(game_num: int):
    """运行一局游戏并返回结果"""
    player_names = ["Alice", "Bob", "Charlie", "David", "Eve", "Frank", "Grace", "Henry", "Ivy"]
    
    try:
        logger = GameLogger()
        game = WerewolfGame(player_names, logger)
        
        winner = await game.run()
        
        return {
            "game_id": game.game_id,
            "winner": winner,
            "success": True
        }
    except Exception as e:
        print(f"  游戏 {game_num} 出错: {e}")
        return {
            "game_id": None,
            "winner": None,
            "success": False,
            "error": str(e)
        }

async def run_games_safe(num_games: int):
    """安全地运行多个游戏，避免API限流"""
    print("=" * 80)
    print(f"AI 狼人杀 - 批量生成游戏数据 ({num_games} 局, 串行运行)")
    print("=" * 80)
    
    wolf_wins = 0
    villager_wins = 0
    failed = 0
    
    for i in range(num_games):
        print(f"\n--- 游戏 {i+1}/{num_games} ---")
        
        result = await run_single_game(i+1)
        
        if result["success"]:
            winner = result["winner"]
            game_id_short = result["game_id"][:12] if result["game_id"] else "N/A"
            print(f"  游戏ID: {game_id_short}...")
            print(f"  胜者: {winner}")
            
            if winner == "werewolves":
                wolf_wins += 1
            else:
                villager_wins += 1
        else:
            failed += 1
        
        # 在游戏之间加一点延时，避免API限流
        if i < num_games - 1:
            print(f"  等待 5 秒...")
            await asyncio.sleep(5)
    
    print("\n" + "=" * 80)
    print("批量游戏完成！")
    print("=" * 80)
    total_successful = wolf_wins + villager_wins
    print(f"\n成功游戏数: {total_successful}")
    print(f"失败游戏数: {failed}")
    print(f"狼人胜利: {wolf_wins} ({wolf_wins/total_successful*100:.1f}%)")
    print(f"好人胜利: {villager_wins} ({villager_wins/total_successful*100:.1f}%)")
    print(f"\n日志已保存到 logs/ 目录")

if __name__ == "__main__":
    # 串行运行，每局之间延时5秒，避免限流
    asyncio.run(run_games_safe(10))
