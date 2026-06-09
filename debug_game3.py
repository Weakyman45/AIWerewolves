#!/usr/bin/env python3
import asyncio
import sys
import os
import time
import traceback

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.engine.game import WerewolfGame
from backend.core.logger import GameLogger
from backend.core.config import settings

async def test_llm():
    """测试LLM连接"""
    from langchain_openai import ChatOpenAI
    
    print(f"[{time.strftime('%H:%M:%S')}] Testing LLM connection...")
    
    llm = ChatOpenAI(
        api_key=settings.DOUBAO_API_KEY,
        base_url=settings.DOUBAO_BASE_URL,
        model=settings.DOUBAO_MODEL,
        temperature=0.8
    )
    
    try:
        result = await llm.ainvoke('Hello, how are you?')
        print(f"[{time.strftime('%H:%M:%S')}] LLM response: {result.content[:50]}...")
        return True
    except Exception as e:
        print(f"[{time.strftime('%H:%M:%S')}] LLM error: {e}")
        traceback.print_exc()
        return False

async def test_game_step_by_step():
    """逐步测试游戏"""
    player_names = ['Alice', 'Bob', 'Charlie', 'David', 'Eve', 'Frank']
    logger = GameLogger()
    game = WerewolfGame(player_names, logger)
    
    print(f"[{time.strftime('%H:%M:%S')}] Game initialized")
    print(f"[{time.strftime('%H:%M:%S')}] Players: {list(game.players.keys())}")
    
    for pid, agent in game.players.items():
        print(f"  - {pid}: {agent.name}, role: {agent.role}")
    
    print(f"[{time.strftime('%H:%M:%S')}] Starting first round...")
    
    # 创建round_record
    from backend.core.models import RoundRecord, GamePhase
    round_record = RoundRecord(
        round_number=game.state.current_round,
        phase=GamePhase.NIGHT
    )
    
    # 测试夜间阶段
    print(f"[{time.strftime('%H:%M:%S')}] Running night phase...")
    try:
        await game._run_night_phase(round_record)
        print(f"[{time.strftime('%H:%M:%S')}] Night phase completed")
    except Exception as e:
        print(f"[{time.strftime('%H:%M:%S')}] Night phase error: {e}")
        traceback.print_exc()
        return
    
    print(f"[{time.strftime('%H:%M:%S')}] Night actions: {len(round_record.night_actions)}")
    
    # 测试警长竞选
    print(f"[{time.strftime('%H:%M:%S')}] Running sheriff election...")
    try:
        await game._run_sheriff_election(round_record)
        print(f"[{time.strftime('%H:%M:%S')}] Sheriff election completed")
        print(f"[{time.strftime('%H:%M:%S')}] Sheriff: {game.state.sheriff_id}")
    except Exception as e:
        print(f"[{time.strftime('%H:%M:%S')}] Sheriff election error: {e}")
        traceback.print_exc()
        return

async def main():
    # 首先测试LLM
    llm_ok = await test_llm()
    if not llm_ok:
        print(f"[{time.strftime('%H:%M:%S')}] LLM test failed, exiting")
        return
    
    print()
    
    # 然后测试游戏逐步执行
    await test_game_step_by_step()

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        result = loop.run_until_complete(asyncio.wait_for(main(), timeout=300))
    except asyncio.TimeoutError:
        print(f"[{time.strftime('%H:%M:%S')}] Timeout after 300 seconds")
    except Exception as e:
        print(f"[{time.strftime('%H:%M:%S')}] Error: {e}")
        traceback.print_exc()
    finally:
        loop.close()
