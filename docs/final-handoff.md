# 最终交接记录

日期：2026-06-07

## 停止点

策略迭代工作到这里停止。当前仓库保留实现改动和回归测试；本地运行产物继续由 Git 忽略。

当前策略索引：

- `strategies/latest.json` 指向 `v0.0.8`。
- 本地策略产物包含从 `v0.0.1` 到 `v0.1.20` 的实验版本。
- `logs/` 保留本轮评估产生的本地对局日志。

解释：`v0.0.8` 是当前被索引的版本。后续 `v0.1.x` 目录先作为本地实验历史和 prompt 回归证据保留，除非之后明确提升为正式版本。

## 已保留内容

- 后端决策和评估相关改动。
- 策略 prompt 回归测试。
- `strategies/` 下的本地策略版本。
- `logs/` 下的本地对局日志。
- 本地环境和依赖目录，例如 `.venv/`、`frontend/node_modules/`。

## 已清理内容

已清理可重新生成的文件：

- Python 字节码缓存：`__pycache__/`
- Pytest 缓存：`.pytest_cache/`
- macOS 元数据：`.DS_Store`
- 前端构建产物：`frontend/dist/`
- 自动运行进度文件：`auto_run_progress.json`

这些路径已经由 `.gitignore` 覆盖。

## 验证命令

提交或打包前建议运行：

```bash
python -m pytest
python -m compileall -q backend
cd frontend && npm run lint && npm run build
```

快速离线演化检查，不调用 LLM/API：

```bash
python run_evolution.py \
  --iterations 1 \
  --train-games 1 \
  --ab-games 4 \
  --fallback-only \
  --game-runner mock
```

当前索引候选版本对比：

```bash
python evaluate_evolution.py \
  --baseline v0.0.1 \
  --candidate v0.0.8 \
  --games 20 \
  --min-successful-games 16 \
  --game-runner live-fast \
  --game-timeout 240
```

## 建议提交范围

建议提交：

- `backend/` 下的源码改动。
- `evaluate_evolution.py` 的评估运行器改动。
- `tests/` 下的测试改动，包括 `tests/test_strategy_prompt_regressions.py`。
- 本交接文档。

除非明确决定归档，不建议提交被忽略的运行产物。
