#!/usr/bin/env python3
import json
import os

# 查看一个完整的日志文件
log_path = "logs/game_3bcbb04a-de2d-4919-bc45-14f997626bd6.jsonl"
if os.path.exists(log_path):
    with open(log_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
        print(f"总共有 {len(lines)} 行")
        print("\n最后 5 行:")
        for line in lines[-5:]:
            print(line.strip())

        print("\n所有事件类型:")
        types = set()
        for line in lines:
            if line.strip():
                try:
                    data = json.loads(line)
                    types.add(data.get("type", "unknown"))
                except:
                    pass
        print(types)
