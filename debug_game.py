#!/usr/bin/env python3
import asyncio
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.engine.game import WerewolfGame
from backend.core.logger import GameLogger
import time

async def test_game():
    player_names = ['Alice', 'Bob', 'Charlie', 'David', 'Eve', 'Frank']
    logger = GameLogger()
    game = WerewolfGame(player_names, logger)
    
    print(f"[{time.strftime('%H:%M:%S')}] Starting game...")
    
    # 手动运行游戏的各个阶段来调试
    while game.state.winner is None:
        print(f"[{time.strftime('%H:%M:%S')}] Current phase: {game.state.current_phase}")
        
        if game.state.current_phase.name == 'NIGHT':
            print(f"[{time.strftime('%H:%M:%S')}] Running night phase...")
            round_record = await game._run_night_phase(None)
            print(f"[{time.strftime('%H:%M:%S')}] Night phase done")
            
        elif game.state.current_phase.name == 'SHERIFF_ELECTION':
            print(f"[{time.strftime('%H:%M:%S')}] Running sheriff election...")
            round_record = type('RoundRecord', (), {'night_actions': [], 'deaths': [], 'messages': [], 'votes': []})()
            await game._run_sheriff_election(round_record)
            print(f"[{time.strftime('%H:%M:%S')}] Sheriff election done")
            
        elif game.state.current_phase.name == 'DAY':
            print(f"[{time.strftime('%H:%M:%S')}] Running day phase...")
            round_record = type('RoundRecord', (), {'night_actions': [], 'deaths': [], 'messages': [], 'votes': []})()
            await game._run_day_phase(round_record)
            print(f"[{time.strftime('%H:%M:%S')}] Day phase done")
        
        if game.state.winner:
            break
            
        await asyncio.sleep(0.5)
    
    print(f"[{time.strftime('%H:%M:%S')}] Game finished! Winner: {game.state.winner}")

if __name__ == "__main__":
    asyncio.run(test_game())
