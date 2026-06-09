#!/usr/bin/env python3
import asyncio
import sys
import os
import time
import random

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.engine.game import WerewolfGame
from backend.core.logger import GameLogger

async def run_single_game(game_num: int):
    """运行一局游戏并返回结果，带重试逻辑"""
    player_names = ["Alice", "Bob", "Charlie", "David", "Eve", "Frank", "Grace", "Henry", "Ivy"]
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            logger = GameLogger()
            game = WerewolfGame(player_names, logger)
            
            winner = await game.run()
            
            return {
                "game_id": game.game_id,
                "winner": winner,
                "success": True,
                "attempt": attempt + 1
            }
        except Exception as e:
            print(f"  游戏 {game_num} 尝试 {attempt+1}/{max_retries} 出错: {e}")
            if attempt < max_retries - 1:
                wait_time = (attempt + 1) * 30  # 递增等待时间
                print(f"  等待 {wait_time} 秒后重试...")
                await asyncio.sleep(wait_time)
    
    return {
        "game_id": None,
        "winner": None,
        "success": False,
        "error": "所有重试都失败"
    }

async def run_games_slow(num_games: int, delay_between: int = 60):
    """安全地慢慢运行游戏，避免API限流"""
    print("=" * 80)
    print(f"AI 狼人杀 - 批量生成游戏数据 ({num_games} 局)")
    print(f"每局间隔: {delay_between} 秒")
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
            print(f"  ✓ 游戏ID: {game_id_short}...")
            print(f"  ✓ 胜者: {winner}")
            print(f"  ✓ 尝试次数: {result.get('attempt', 1)}")
            
            if winner == "werewolves":
                wolf_wins += 1
            else:
                villager_wins += 1
        else:
            failed += 1
            print(f"  ✗ 游戏失败")
        
        # 只在不是最后一局时延时
        if i < num_games - 1:
            print(f"\n  ⏱️  等待 {delay_between} 秒... (避免限流)")
            await asyncio.sleep(delay_between)
    
    print("\n" + "=" * 80)
    print("批量游戏完成！")
    print("=" * 80)
    total_successful = wolf_wins + villager_wins
    print(f"\n成功游戏数: {total_successful}")
    print(f"失败游戏数: {failed}")
    if total_successful > 0:
        print(f"狼人胜利: {wolf_wins} ({wolf_wins/total_successful*100:.1f}%)")
        print(f"好人胜利: {villager_wins} ({villager_wins/total_successful*100:.1f}%)")
    print(f"\n日志已保存到 logs/ 目录")

if __name__ == "__main__":
    # 慢节奏运行：5局，每局之间延时2分钟
    asyncio.run(run_games_slow(5, delay_between=120))
