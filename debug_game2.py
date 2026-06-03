#!/usr/bin/env python3
import asyncio
import sys
import os
import time
import traceback

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.engine.game import WerewolfGame
from backend.core.logger import GameLogger

async def test_game():
    player_names = ['Alice', 'Bob', 'Charlie', 'David', 'Eve', 'Frank']
    logger = GameLogger()
    game = WerewolfGame(player_names, logger)
    
    print(f"[{time.strftime('%H:%M:%S')}] Starting game...")
    
    try:
        winner = await game.run()
        print(f"[{time.strftime('%H:%M:%S')}] Game finished! Winner: {winner}")
    except Exception as e:
        print(f"[{time.strftime('%H:%M:%S')}] Game error: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    # 设置超时
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        # 180秒超时
        result = loop.run_until_complete(asyncio.wait_for(test_game(), timeout=180))
    except asyncio.TimeoutError:
        print(f"[{time.strftime('%H:%M:%S')}] Game timeout after 180 seconds")
    except Exception as e:
        print(f"[{time.strftime('%H:%M:%S')}] Error: {e}")
        traceback.print_exc()
    finally:
        loop.close()
