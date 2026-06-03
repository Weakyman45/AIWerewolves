
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

### 后端启动
```bash
# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # macOS/Linux

# 安装依赖
pip install -r requirements.txt

# 复制配置文件
cp .env.example .env
# 编辑 .env，填入API Key

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

## 开发进度

- ✅ 项目骨架搭建
- ⏳ 基础数据模型
- ⏳ 信息隔离机制
- ⏳ 5种角色Agent
- ⏳ 对局引擎
- ⏳ 前端UI
- ⏳ 自进化系统

