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

# 运行完整进化循环（默认使用真实LLM对局）
python run_evolution.py --iterations 1 --train-games 1 --ab-games 1
```

## 推荐运行模式

### 1. 离线闭环模式

用于开发、回归测试、答辩演示和CI验证。该模式不创建真实Agent，不调用LLM API，而是用确定性的 mock 对局日志跑完整流程。

```bash
python run_evolution.py \
  --iterations 1 \
  --train-games 1 \
  --ab-games 4 \
  --fallback-only \
  --game-runner mock
```

适用场景：

- 验证"训练对局 -> 日志解析 -> 指标分析 -> 生成候选 -> A/B -> 接受/拒绝"闭环
- 快速排查版本管理和元数据写入问题
- 在没有API Key或网络不稳定时继续开发

注意：mock 模式证明自进化机制可运行，不代表真实 LLM Agent 的实际胜率提升。真实效果证据需要使用 `live-fast` 或 `live` 模式评估。

### 2. dry-run 候选生成

用于只读取已有日志、生成候选Prompt，不运行训练局和A/B。

```bash
python run_evolution.py \
  --iterations 1 \
  --train-games 0 \
  --dry-run \
  --fallback-only \
  --initial-version v0.0.8
```

注意：dry-run 生成的候选版本不会被接受，`latest.json` 会回滚到原版本。

### 3. 真实 LLM 模式

用于真实Agent对局和真实Prompt优化。该模式依赖 `.env` 中的模型配置，耗时和API成本都更高。

```bash
python run_evolution.py \
  --iterations 1 \
  --train-games 1 \
  --ab-games 1 \
  --game-timeout 60 \
  --initial-version v0.0.8
```

如果模型连接正常但响应较慢，可以提高单次请求和单局超时，同时降低输出长度：

```bash
LLM_TIMEOUT=60 LLM_MAX_RETRIES=0 LLM_MAX_TOKENS=160 python run_evolution.py \
  --iterations 1 \
  --train-games 1 \
  --ab-games 1 \
  --game-runner live-fast \
  --game-timeout 240
```

## 进化效果评估

`run_evolution.py` 负责训练和生成候选；`evaluate_evolution.py` 专门回答"候选版本是否真的强于基线"。

离线评估示例：

```bash
python evaluate_evolution.py \
  --baseline v0.0.1 \
  --candidate v0.0.2 \
  --games 4 \
  --min-successful-games 4 \
  --game-runner mock
```

真实评估示例：

```bash
python evaluate_evolution.py \
  --baseline v0.0.1 \
  --candidate v0.0.8 \
  --games 20 \
  --min-successful-games 16 \
  --game-runner live-fast \
  --game-timeout 240
```

报告会输出：

- `PASSED`：候选版本胜率高于基线，且成功局数达到要求
- `FAILED`：候选版本没有超过基线
- `INCONCLUSIVE`：成功样本不足，不能得出结论

默认报告写入 `reports/`，该目录不会进入Git。

退出码：

- `0`：`PASSED`
- `1`：`FAILED`
- `2`：`INCONCLUSIVE`

## CLI 参数

### `run_evolution.py`

| 参数 | 默认值 | 说明 |
| ---- | ------ | ---- |
| `--iterations` | `1` | 进化迭代次数 |
| `--train-games` | `1` | 每轮训练对局数 |
| `--ab-games` | `1` | 每轮A/B测试对局数 |
| `--win-rate-threshold` | `0.05` | 接受候选版本需要达到的胜率提升阈值 |
| `--skip-ab` | `False` | 生成候选后跳过A/B，候选不会被接受 |
| `--dry-run` | `False` | 不运行训练局和A/B，只基于已有日志生成候选 |
| `--fallback-only` | `False` | 跳过LLM Prompt优化，直接应用确定性数据补丁 |
| `--game-runner` | `live` | `live` 使用完整真实Agent，`live-fast` 使用压缩真实评估局，`mock` 使用确定性离线对局 |
| `--game-timeout` | `300` | 单局真实/模拟对局超时时间，单位秒 |
| `--initial-version` | latest | 指定起始策略版本 |

### `evaluate_evolution.py`

| 参数 | 默认值 | 说明 |
| ---- | ------ | ---- |
| `--baseline` | required | 基线策略版本 |
| `--candidate` | latest | 候选策略版本 |
| `--games` | `20` | A/B评估对局数 |
| `--min-successful-games` | `games` | 得出结论所需的最少成功局数 |
| `--improvement-threshold` | `0.0` | 候选需要超过基线的最低胜率提升 |
| `--game-runner` | `live` | `live` 使用完整真实Agent，`live-fast` 使用压缩真实评估局，`mock` 使用确定性离线对局 |
| `--game-timeout` | `300` | 单局超时时间，单位秒 |
| `--strategy-dir` | `.env`配置 | 策略目录 |
| `--log-dir` | `.env`配置 | 日志目录 |
| `--output` | `reports/*.md` | Markdown报告输出路径 |

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

## 版本元数据

每个 `strategies/v*/metadata.json` 会记录：

- `analysis_summary`：基于完成对局计算的胜率、角色指标和常见失误
- `analysis_summary.quality_metrics`：规则修正、身份边界拦截、LLM fallback 等可解释 bad case 统计
- `training_summary`：本轮训练请求数、完成数、超时数、失败数和失败类型
- `role_optimizations`：各角色的优化理由和关键变更
- `ab_result`：候选版本与父版本的 A/B 对战结果；候选只有通过后才会晋级为 `latest`

训练失败或超时不会进入胜率分析，但会进入 `training_summary`，用于区分策略表现和运行环境问题。

## 自定义配置

### 调整进化参数

```python
controller = EvolutionController(
    num_games_per_iteration=50,   # 更多对局 = 更稳定的统计
    win_rate_threshold=0.03,      # 更低的阈值 = 更容易接受新版本
    game_runner="mock",           # mock=离线确定性对局，live=真实LLM对局
    fallback_only=True            # 跳过LLM优化，使用确定性策略补丁
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

1. **时间消耗** - 真实LLM对局可能需要较长时间，开发时优先用 `--game-runner mock`
2. **API成本** - 大量真实对局会消耗较多API调用
3. **统计显著性** - 确保有足够的A/B对局数来得出可靠结论
4. **回滚能力** - 未接受的候选版本会保留文件，但 `latest.json` 会回滚到原版本
5. **失败统计** - 失败和超时训练局不会进入胜率分析，只进入 `training_summary`
6. **底牌边界** - 只有预言家本人和本局唯一授权悍跳狼可以跳预言家；其他角色越权声明会被守卫修正并进入质量指标

## 下一步

- 先运行离线闭环：`python run_evolution.py --iterations 1 --train-games 1 --ab-games 4 --fallback-only --game-runner mock`
- 再运行小规模真实对局验证API稳定性
- 查看 `strategies/v*/metadata.json`，确认 `analysis_summary` 和 `training_summary`
- 用 `evaluate_evolution.py` 扩大真实A/B对局数，评估策略效果
