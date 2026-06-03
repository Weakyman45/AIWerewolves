#!/usr/bin/env python3
import asyncio
import sys
import os
import time
import json
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.engine.game import WerewolfGame
from backend.core.logger import GameLogger

# 配置
CONFIG = {
    "total_games": 30,              # 总共运行多少局
    "max_retries": 5,               # 每局最多重试几次
    "delay_between_games": 180,     # 每局之间等待多少秒（3分钟）
    "retry_delay": 60,              # 失败后等待多久重试（1分钟）
    "long_retry_delay": 300,        # 遇到限流后等待多久（5分钟）
    "progress_file": "auto_run_progress.json"  # 进度记录文件
}

def load_progress():
    """加载进度"""
    if os.path.exists(CONFIG["progress_file"]):
        with open(CONFIG["progress_file"], "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "completed_games": 0,
        "wolf_wins": 0,
        "villager_wins": 0,
        "failed_games": 0,
        "start_time": datetime.now().isoformat()
    }

def save_progress(progress):
    """保存进度"""
    with open(CONFIG["progress_file"], "w", encoding="utf-8") as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)

def print_header():
    """打印头部"""
    print("=" * 100)
    print("AI 狼人杀 - 自动化后台数据生成".center(100))
    print("=" * 100)

def print_progress(progress, game_num):
    """打印进度"""
    print(f"\n[进度] 第 {game_num}/{CONFIG['total_games']} 局")
    print(f"      已完成: {progress['completed_games']} 局")
    print(f"      狼人胜: {progress['wolf_wins']} 局")
    print(f"      好人胜: {progress['villager_wins']} 局")
    print(f"      失败: {progress['failed_games']} 局")
    print(f"      开始时间: {progress['start_time']}")
    print(f"      当前时间: {datetime.now().isoformat()}")

async def run_single_game_with_retry(game_num, progress):
    """带重试的运行单局游戏"""
    player_names = ["Alice", "Bob", "Charlie", "David", "Eve", "Frank"]
    
    for attempt in range(1, CONFIG["max_retries"] + 1):
        try:
            logger = GameLogger()
            game = WerewolfGame(player_names, logger)
            
            print(f"\n[游戏 {game_num}] 尝试 {attempt}/{CONFIG['max_retries']}")
            print(f"         游戏ID: {game.game_id[:12]}...")
            
            winner = await game.run()
            
            print(f"         ✅ 成功完成！胜者: {winner}")
            
            # 更新进度
            if winner == "werewolves":
                progress["wolf_wins"] += 1
            else:
                progress["villager_wins"] += 1
            progress["completed_games"] += 1
            
            return True, winner
            
        except Exception as e:
            error_msg = str(e)
            
            if "RateLimitExceeded" in error_msg or "429" in error_msg:
                print(f"         ⚠️  API限流！等待 {CONFIG['long_retry_delay']} 秒...")
                delay = CONFIG["long_retry_delay"]
            else:
                print(f"         ❌ 错误: {error_msg}")
                delay = CONFIG["retry_delay"]
            
            if attempt < CONFIG["max_retries"]:
                print(f"         等待 {delay} 秒后重试...")
                await asyncio.sleep(delay)
            else:
                print(f"         所有尝试都失败！")
                progress["failed_games"] += 1
                return False, None

async def main():
    """主函数"""
    print_header()
    
    progress = load_progress()
    save_progress(progress)
    
    print(f"\n当前状态:")
    print(f"  已完成: {progress['completed_games']} 局")
    print(f"  目标: {CONFIG['total_games']} 局")
    print(f"  剩余: {CONFIG['total_games'] - progress['completed_games']} 局")
    
    if progress["completed_games"] >= CONFIG["total_games"]:
        print("\n✅ 目标已完成！")
        return
    
    start_game_num = progress["completed_games"] + 1
    
    for game_num in range(start_game_num, CONFIG["total_games"] + 1):
        print_progress(progress, game_num)
        
        # 运行游戏
        success, winner = await run_single_game_with_retry(game_num, progress)
        
        # 保存进度
        save_progress(progress)
        
        # 不是最后一局的话等待一下
        if game_num < CONFIG["total_games"]:
            print(f"\n[等待] 等待 {CONFIG['delay_between_games']} 秒...")
            await asyncio.sleep(CONFIG["delay_between_games"])
    
    print("\n" + "=" * 100)
    print("🎉 完成！".center(100))
    print("=" * 100)
    print(f"\n最终统计:")
    print(f"  完成: {progress['completed_games']} 局")
    print(f"  狼人胜: {progress['wolf_wins']} 局")
    print(f"  好人胜: {progress['villager_wins']} 局")
    print(f"  失败: {progress['failed_games']} 局")
    total = progress["wolf_wins"] + progress["villager_wins"]
    if total > 0:
        print(f"  狼人胜率: {progress['wolf_wins']/total*100:.1f}%")
        print(f"  好人胜率: {progress['villager_wins']/total*100:.1f}%")
    print(f"\n开始时间: {progress['start_time']}")
    print(f"结束时间: {datetime.now().isoformat()}")

if __name__ == "__main__":
    asyncio.run(main())
