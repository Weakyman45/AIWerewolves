
import asyncio
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.engine.game import WerewolfGame
from backend.core.logger import GameLogger


async def main():
    print("=" * 60)
    print("AI 狼人杀 - 测试局")
    print("=" * 60)
    
    player_names = ["Alice", "Bob", "Charlie", "David", "Eve", "Frank"]
    
    logger = GameLogger()
    game = WerewolfGame(player_names, logger)
    
    print(f"\n游戏ID: {game.game_id}")
    print(f"玩家数量: {len(player_names)}")
    print("\n玩家角色分配:")
    for pid, ps in game.player_states.items():
        print(f"  {ps.name}: {ps.role.value}")
    
    print("\n" + "=" * 60)
    print("游戏开始!")
    print("=" * 60)
    
    winner = await game.run()
    
    print("\n" + "=" * 60)
    print(f"游戏结束! 获胜方: {winner.value}")
    print("=" * 60)
    
    print("\n最终角色信息:")
    for pid, ps in game.player_states.items():
        status = "存活" if ps.is_alive else "死亡"
        print(f"  {ps.name}: {ps.role.value} - {status}")
    
    print(f"\n游戏日志已保存至: logs/game_{game.game_id}.jsonl")


if __name__ == "__main__":
    asyncio.run(main())
