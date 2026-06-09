# Rubric Readiness

日期：2026-06-09

## 单 Agent 能力

- 角色 Prompt 已按狼人、预言家、女巫、猎人、村民拆分；狼人额外区分“唯一授权悍跳狼”和普通狼人。
- 决策日志保留 `decision_type`、目标、`reasoning` 和原始发言，前端“Agent 决策显微镜”可直接查看推理链。
- 非预言家越权报查验、未授权狼人悍跳、身份前后矛盾会被动作层守卫修正，并计入 Analyzer 的质量指标。

## 多 Agent 协作与系统设计

- 对局引擎维护公共日志、私有知识、狼人队友视野和角色技能边界；Agent 只收到自己可见的信息。
- 警长竞选、发言、投票、夜间技能、死亡结算、猎人开枪和自爆均通过统一决策接口记录。
- 本局只分配一名 `fake_seer_wolf_id`，只有该狼人和真预言家可以公开跳预言家，其他角色必须尊重底牌。

## 工程实现与完整度

- 后端提供对局、日志、自进化状态、版本时间线和回滚 API；前端展示观战日志、版本链、闭环阶段、A/B 结果和 bad case 统计。
- 自进化状态区分离线演示闭环和真实 LLM 评估：`mock` 用于稳定演示，`live-fast/live` 用于真实效果验证。
- 当前推荐验证命令：

```bash
python -m pytest
python -m compileall -q backend
cd frontend && npm run lint && npm run build
```

## 自进化 Agent

- 已实现“对局采样 -> 日志分析 -> Prompt/策略补丁 -> A/B 验证 -> 晋级或回滚”闭环。
- 候选版本默认不会直接替换当前版本；只有 A/B 通过后才更新 `latest.json`。
- 版本 metadata 记录训练样本、A/B 结果、胜率变化、角色优化理由、运行失败/超时和质量守卫指标。
- 演示闭环命令：

```bash
python run_evolution.py \
  --iterations 1 \
  --train-games 1 \
  --ab-games 4 \
  --fallback-only \
  --game-runner mock
```

## 仍需说明的限制

- `mock` 闭环证明系统机制可运行，不代表真实 LLM 胜率提升；真实效果需使用 `evaluate_evolution.py` 的 `live-fast` 或 `live` 模式扩大样本。
- `strategies/`、`logs/` 和 `reports/` 是本地运行产物，默认不提交；答辩时可现场生成或展示本地已有样本。
