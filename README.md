
# AI狼人杀 - 自进化Agent

## 项目简介
一个基于多智能体系统的狼人杀游戏，支持自进化的Agent策略迭代。

## 项目结构
```
Werewolve/
├── backend/              # Python后端
│   ├── core/            # 核心模块
│   │   ├── models.py    # 数据模型
│   │   ├── information.py  # 信息隔离
│   │   ├── logger.py    # 日志系统
│   │   └── config.py    # 配置
│   ├── agents/          # Agent实现
│   │   ├── base.py      # 基础Agent
│   │   └── roles/       # 各角色Agent
│   ├── engine/          # 对局引擎
│   ├── evolution/       # 自进化系统
│   └── api/             # FastAPI接口
├── frontend/            # React前端
├── logs/                # 对局日志
├── strategies/          # 策略版本
└── tests/               # 测试用例
```

## 快速开始

### 环境配置

```bash
cp .env.example .env
```

`.env` 需要配置方舟/豆包模型：

- `DOUBAO_API_KEY`
- `DOUBAO_MODEL`
- `DOUBAO_CODE_MODEL`
- `LLM_TIMEOUT`
- `LLM_MAX_RETRIES`

### 后端启动
```bash
# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # macOS/Linux

# 安装依赖
pip install -r requirements.txt

# 启动服务
uvicorn backend.main:app --reload --port 8000
```

### 前端启动
```bash
cd frontend
npm install
npm run dev
```

## 进阶方向C：自进化Agent

核心功能：
- 自动对局→分析→调整→再对局闭环
- 策略版本管理与回滚
- A/B对战验证系统
- 胜率提升追踪
- 离线 mock 演化模式，不依赖真实 LLM/API
- 失败/超时训练局结构化统计

### 常用演化命令

离线闭环验证，不调用真实 LLM：

```bash
python run_evolution.py \
  --iterations 1 \
  --train-games 1 \
  --ab-games 4 \
  --fallback-only \
  --game-runner mock
```

只基于已有日志生成候选版本：

```bash
python run_evolution.py \
  --iterations 1 \
  --train-games 0 \
  --dry-run \
  --fallback-only
```

真实 LLM 对局运行：

```bash
python run_evolution.py \
  --iterations 1 \
  --train-games 1 \
  --ab-games 1 \
  --game-timeout 60
```

确认候选版本是否真的优于基线：

```bash
python evaluate_evolution.py \
  --baseline v0.0.1 \
  --candidate v0.0.8 \
  --games 20 \
  --min-successful-games 16 \
  --game-timeout 60
```

### 验证命令

```bash
python -m pytest
python -m compileall -q backend
cd frontend && npm run lint && npm run build
```

## 当前状态

- ✅ 项目骨架搭建
- ✅ 基础数据模型
- ✅ 信息隔离机制
- ✅ 5种角色Agent
- ✅ 对局引擎
- ✅ 前端UI基础界面
- ✅ 自进化系统
- ✅ 策略版本管理与回滚
- ✅ 数据驱动Prompt补丁
- ✅ mock 离线演化闭环测试
- ⏳ 真实 LLM 长跑稳定性与效果验证
