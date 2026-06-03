# AI 狼人杀 - 自进化系统使用指南

## 概述

自进化系统是AI狼人杀项目的核心功能，它可以让Agent通过大量对局不断学习和优化自己的策略，提升游戏水平。

## 系统架构

```
┌─────────────────────────────────────────────────────────┐
│              进化控制中心 (Controller)                  │
│                                                          │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────┐  │
│  │  对局生成    │───▶│  策略分析    │───▶│ 策略优化 │  │
│  │  (Game)     │    │  (Analyzer)  │    │ (Adapter)│  │
│  └──────────────┘    └──────────────┘    └──────────┘  │
│         │                   │                   │       │
│         └───────────────────┴───────────────────┘       │
│                             │                           │
│                    ┌────────▼────────┐                  │
│                    │  版本管理系统   │                  │
│                    │ (VersionControl)│                  │
│                    └─────────────────┘                  │
│                             │                           │
│                    ┌────────▼────────┐                  │
│                    │   A/B 对战验证  │                  │
│                    │   (ABTesting)   │                  │
│                    └─────────────────┘                  │
└─────────────────────────────────────────────────────────┘
```

## 核心模块

### 1. LogParser (日志解析器)
- 解析历史对局的JSONL日志
- 提取游戏数据用于分析

### 2. VersionControl (版本管理)
- 管理策略版本的创建、更新、回滚
- 存储每个版本的Prompt和对战数据

### 3. Analyzer (策略分析)
- 分析对局数据，评估各角色表现
- 识别关键失误和改进点
- 生成优化建议

### 4. Adapter (策略优化)
- 基于分析结果优化Prompt
- 使用LLM自动生成改进的策略
- 提供战术模板库

### 5. ABTesting (A/B对战)
- 新版本与旧版本的对比测试
- 统计显著性检验
- 胜率验证

### 6. EvolutionController (进化控制中心)
- 完整的进化闭环管理
- 自动运行多轮进化
- 进度跟踪和结果汇总

## 快速开始

### 1. 初始化系统

```python
import asyncio
from backend.evolution import EvolutionController

controller = EvolutionController(
    num_games_per_iteration=20,  # 每轮进化的对局数
    win_rate_threshold=0.05      # 接受新版本的胜率提升阈值
)

controller.initialize()  # 创建初始版本v0.0.1
```

### 2. 运行进化循环

```python
async def main():
    controller = EvolutionController()
    controller.initialize()
    
    # 运行3次进化迭代
    result = await controller.start_evolution(
        max_iterations=3,
        progress_callback=lambda i, t, p, r: print(f"迭代 {i}/{t} - {p}")
    )
    
    print(f"进化完成！最终版本: {result['final_version']}")

asyncio.run(main())
```

### 3. 运行简单测试

```bash
# 测试基础功能
python test_evolution.py

# 运行完整进化循环
python run_evolution.py
```

## 目录结构

```
strategies/
├── v0.0.1/              # 策略版本目录
│   ├── werewolf.txt     # 狼人Prompt
│   ├── seer.txt         # 预言家Prompt
│   ├── witch.txt        # 女巫Prompt
│   ├── hunter.txt       # 猎人Prompt
│   ├── villager.txt     # 村民Prompt
│   ├── metadata.json    # 版本元数据
│   └── stats.json       # 对战统计
├── v0.0.2/              # 进化后的版本
│   └── ...
└── latest.json          # 最新版本指针

logs/                    # 对局日志目录
```

## 自定义配置

### 调整进化参数

```python
controller = EvolutionController(
    num_games_per_iteration=50,   # 更多对局 = 更稳定的统计
    win_rate_threshold=0.03       # 更低的阈值 = 更容易接受新版本
)
```

### 查看进化历史

```python
history = controller.get_history()
for item in history:
    print(f"迭代 {item['iteration']}: 接受={item['result']['accepted']}")
```

### 回滚到旧版本

```python
controller.rollback_to_version("v0.0.1")
```

## 工作流程

1. **生成对局** - 用当前策略运行N局游戏
2. **分析数据** - 解析日志，分析表现
3. **优化策略** - 基于分析结果优化Prompt
4. **A/B测试** - 新版本与旧版本对战
5. **判断接受** - 如果胜率显著提升则接受新版本
6. **重复循环** - 回到步骤1

## 进阶用法

### 手动A/B测试

```python
from backend.evolution import ABTesting

ab_test = ABTesting()

result = asyncio.run(
    ab_test.run_comparison("v0.0.1", "v0.0.2", num_games=20)
)

print(f"A胜率: {result['a_win_rate']:.2%}")
print(f"B胜率: {result['b_win_rate']:.2%}")
print(f"更好版本: {result['better_version']}")
```

### 自定义Prompt优化

```python
from backend.evolution import Adapter

adapter = Adapter()

optimized = adapter.optimize_prompt(
    original_prompt="你是狼人...",
    role="werewolf",
    analysis={"werewolf_win_rate": 0.4}
)

print(f"优化后Prompt: {optimized['optimized']}")
```

## 注意事项

1. **时间消耗** - 完整的进化过程可能需要较长时间
2. **API成本** - 大量对局会消耗较多的API调用
3. **统计显著性** - 确保有足够的对局数来得出可靠结论
4. **回滚能力** - 保留旧版本以便回滚

## 下一步

- 运行完整的进化循环 (`python run_evolution.py`)
- 查看策略版本的对战数据
- 分析进化效果，调整参数
