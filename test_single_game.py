#!/usr/bin/env python3
import asyncio
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.engine.game import WerewolfGame
from backend.core.logger import GameLogger

async def test_single_game():
    """测试运行一局游戏"""
    print("=" * 80)
    print("测试运行一局狼人杀游戏")
    print("=" * 80)
    
    player_names = ["Alice", "Bob", "Charlie", "David", "Eve", "Frank"]
    
    try:
        logger = GameLogger()
        game = WerewolfGame(player_names, logger)
        
        print(f"游戏ID: {game.game_id}")
        print(f"玩家数: {len(player_names)}")
        print("\n玩家角色分配:")
        for pid, ps in game.player_states.items():
            print(f"  {ps.name}: {ps.role.value}")
        
        print("\n" + "=" * 80)
        print("开始游戏...")
        print("=" * 80)
        
        winner = await game.run()
        
        print("\n" + "=" * 80)
        print(f"游戏结束！胜者: {winner}")
        print("=" * 80)
        
        return True, winner
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        print(f"堆栈: {traceback.format_exc()}")
        return False, None

if __name__ == "__main__":
    asyncio.run(test_single_game())
