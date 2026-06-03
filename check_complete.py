#!/usr/bin/env python3
import json
import os

print("检查所有日志文件的完整性...\n")

total_files = 0
complete_games = 0
incomplete_games = 0

for filename in os.listdir("logs"):
    if filename.startswith("game_") and filename.endswith(".jsonl"):
        total_files += 1
        log_path = os.path.join("logs", filename)
        
        has_game_start = False
        has_game_end = False
        
        with open(log_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        data = json.loads(line)
                        if data.get("type") == "game_start":
                            has_game_start = True
                        if data.get("type") == "game_end":
                            has_game_end = True
                    except:
                        pass
        
        if has_game_start and has_game_end:
            complete_games += 1
            print(f"✓ {filename} - 完整游戏")
        else:
            incomplete_games += 1
            status = []
            if has_game_start:
                status.append("有 game_start")
            else:
                status.append("无 game_start")
            if has_game_end:
                status.append("有 game_end")
            else:
                status.append("无 game_end")
            print(f"✗ {filename} - 不完整 ({', '.join(status)})")

print(f"\n统计: 共 {total_files} 个日志文件")
print(f"  完整游戏: {complete_games}")
print(f"  不完整游戏: {incomplete_games}")
