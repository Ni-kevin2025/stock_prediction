# Stock Prediction Agent

面向股票研究的可追溯多 Agent 项目。第一阶段聚焦于盘后数据整理、指标分析和研究报告，暂不执行真实交易。

## 本地环境

本项目使用 Conda 环境 `stock-agent-py311`（Python 3.11）。

```powershell
conda activate stock-agent-py311
pip install -e ".[analysis,api,ml,dev]"
```

## 私密配置

首次使用时复制 `.env.example` 为 `.env`，再填写自己的密钥：

```powershell
Copy-Item .env.example .env
```

`.env`、本地数据库、原始数据、模型和日志都被 `.gitignore` 排除，不能提交到远程仓库。

## 目录约定

```text
src/stock_prediction/  应用源码
tests/                 自动化测试
data/                  本地数据（不提交）
models/                模型产物（不提交）
logs/                  运行日志（不提交）
reports/generated/     自动生成的报告（不提交）
```

## 验证

```powershell
python -m pytest
```

## 本地仪表盘

```powershell
$env:PYTHONPATH = "src"
streamlit run src/stock_prediction/dashboard.py
```

仪表盘只显示研究结果、样本外验证和模拟组合；不连接任何券商，也不会下单。

若普通权限下无法在线获取行情，请双击项目根目录的 `启动交易计划Agent_管理员.bat` 并在 UAC 提示中确认。该启动器仅以管理员权限运行本地 Streamlit 服务，以适配本机网络策略；不会读取平安证券/同花顺账户或发出交易指令。

## 同花顺手工交易计划

新版仪表盘面向平安证券/同花顺的手动下单流程。请在左侧输入可用现金、实际持仓数量与成本，点击“生成今日交易计划”。系统会输出计划买卖数量、限价区间和止损参考价；买入数量按 A 股 100 股整手、单笔风险、单股仓位与可用现金共同计算。

账户资料只保存到本地 `data/trading_profile.json`，该文件被 Git 忽略。下单前必须在同花顺核对实时价格、涨跌停、停牌和实际可用资金；本项目不连接或控制券商账户。

## 第一阶段：研究快照

当前原型可从 Yahoo Finance 获取日线数据，计算均线、RSI、MACD 与成交量比，并生成带数据日期和风险提示的 Markdown 研究报告：

```powershell
python -m stock_prediction research 600519.SS --period 1y --output reports/generated/600519.SS.md
```

默认 `auto` 数据源支持 A 股六位代码（通过 AkShare，例如 `600519`、`000858`）和 Yahoo 后缀代码（例如 `600519.SS`）。也可通过 `--provider akshare` 或 `--provider yahoo` 强制指定数据源。该命令只生成研究信息，不会发出交易指令或连接交易账户。

## 第二阶段：策略决策与回测

策略决策 Agent 使用固定、可审计的规则：收盘价与 20/60 日均线构成趋势过滤，RSI 与 MACD 进行动量确认；单只股票的目标仓位上限为总资金的 20%，初始止损为进场价的 8%。所有规则都可以在 `StrategyConfig` 中调整。

```powershell
# 当前规则信号：buy / hold / sell / wait
python -m stock_prediction decision 600519.SS --period 1y --output reports/generated/600519-decision.md

# 历史回测：信号在下一个交易日开盘执行，避免未来函数
python -m stock_prediction backtest 600519.SS --period 5y --initial-cash 100000 --output reports/generated/600519-backtest.md

# 按时间分割训练段/测试段，并与买入持有基准比较
python -m stock_prediction validate 600519.SS --period 5y --initial-cash 100000 --output reports/generated/600519-validation.md

# 只在训练段选择预定义策略，再用之后的样本外时段评估
python -m stock_prediction optimize 600519.SS --period 5y --initial-cash 100000 --output reports/generated/600519-optimisation.md

# 提取并评估公开的 A 股财务指标
python -m stock_prediction fundamentals 600519 --start-year 2020 --output reports/generated/600519-fundamentals.md

# 汇总技术、样本外验证、基本面与模拟组合资格
python -m stock_prediction daily 600519 000858 601318 --period 5y --output reports/generated/daily-brief.md

# 对自定义股票池做透明的趋势/动量筛选
python -m stock_prediction screen 600519.SS 000858.SZ 601318.SS --period 1y --output reports/generated/candidates.md

# 仅将同时通过信号、评分和样本外验证的股票纳入模拟组合
python -m stock_prediction portfolio 600519.SS 000858.SZ 601318.SS --period 5y --initial-cash 100000 --output reports/generated/portfolio.md
```

回测已纳入单边 5 个基点手续费，但尚未模拟滑点、税费、涨跌停、停牌和流动性。样本外验证必须跑赢同区间买入持有基准，才有资格进入模拟盘观察。它用于筛选与验证策略，不能证明未来收益，也不应直接替代模拟盘或人工决策。
