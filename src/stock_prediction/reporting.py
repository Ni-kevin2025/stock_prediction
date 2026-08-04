"""Markdown reporting for research results."""

from __future__ import annotations

from stock_prediction.analysis import AnalysisResult
from stock_prediction.backtest import BacktestResult
from stock_prediction.strategy import Decision
from stock_prediction.validation import ValidationResult
from stock_prediction.screening import Candidate
from stock_prediction.portfolio import PortfolioProposal
from stock_prediction.optimization import OptimisationResult
from stock_prediction.fundamentals import FundamentalSnapshot
from stock_prediction.daily import DailyBrief


def render_markdown(result: AnalysisResult) -> str:
    """Render an auditable report with the observation date and warnings."""

    metric_rows = [
        ("收盘价", f"{result.close:.2f}"),
        ("20 日均线", _format_optional(result.sma_20)),
        ("60 日均线", _format_optional(result.sma_60)),
        ("RSI(14)", _format_optional(result.rsi_14)),
        ("MACD", _format_optional(result.macd)),
        ("MACD 信号线", _format_optional(result.macd_signal)),
        ("量比（20 日均量）", _format_optional(result.volume_ratio_20)),
        ("趋势", result.trend),
        ("动量", result.momentum),
    ]
    lines = [
        f"# {result.symbol} 研究快照",
        "",
        f"数据截至：{result.as_of.strftime('%Y-%m-%d')}",
        "",
        "| 指标 | 数值 |",
        "| --- | --- |",
        *[f"| {name} | {value} |" for name, value in metric_rows],
        "",
        "## 观察",
        "",
        *[f"- {observation}" for observation in result.observations],
        "",
        "## 风险提示",
        "",
        *[f"- {warning}" for warning in result.warnings],
        "",
    ]
    return "\n".join(lines)


def _format_optional(value: float | None) -> str:
    return "数据不足" if value is None else f"{value:.2f}"


def render_decision_markdown(decision: Decision) -> str:
    """Render the latest decision with explicit position and risk boundaries."""

    stop = "不适用" if decision.stop_loss_price is None else f"{decision.stop_loss_price:.2f}"
    lines = [
        f"# {decision.symbol} 策略决策",
        "",
        f"数据截至：{decision.as_of.strftime('%Y-%m-%d')}",
        "",
        f"- 建议动作：`{decision.action.value}`",
        f"- 目标仓位上限：{decision.target_position_fraction:.0%}",
        f"- 初始止损参考价：{stop}",
        f"- 置信度：{decision.confidence}",
        "",
        "## 依据",
        "",
        *[f"- {reason}" for reason in decision.reasons],
        "",
        "## 风控",
        "",
        *[f"- {note}" for note in decision.risk_notes],
        "",
    ]
    return "\n".join(lines)


def render_backtest_markdown(symbol: str, result: BacktestResult) -> str:
    """Render performance metrics and caveats for a backtest."""

    lines = [
        f"# {symbol.upper()} 策略回测",
        "",
        "| 指标 | 结果 |",
        "| --- | --- |",
        f"| 初始资金 | {result.initial_cash:,.2f} |",
        f"| 期末权益 | {result.final_equity:,.2f} |",
        f"| 总收益率 | {result.total_return:.2%} |",
        f"| 年化收益率 | {_format_percent(result.annualised_return)} |",
        f"| 最大回撤 | {result.max_drawdown:.2%} |",
        f"| 夏普比率 | {_format_optional(result.sharpe_ratio)} |",
        f"| 已完成交易胜率 | {_format_percent(result.win_rate)} |",
        f"| 已执行交易次数 | {len(result.trades)} |",
        "",
        "## 回测边界",
        "",
        "- 信号使用当日收盘数据，统一在下一个交易日开盘执行，避免使用未来数据。",
        "- 结果已计入默认单边 5 个基点手续费；未包含滑点、税费、停牌、涨跌停与流动性约束。",
        "- 历史回测不能保证未来收益，使用模拟盘验证后才应考虑任何实盘操作。",
        "",
    ]
    return "\n".join(lines)


def _format_percent(value: float | None) -> str:
    return "数据不足" if value is None else f"{value:.2%}"


def render_validation_markdown(symbol: str, result: ValidationResult) -> str:
    """Render chronological test results beside the same-period benchmark."""

    status = "通过" if result.passed_benchmark else "未通过"
    lines = [
        f"# {symbol.upper()} 样本外验证",
        "",
        f"测试段开始：{result.split_date.strftime('%Y-%m-%d')}",
        "",
        "| 指标 | 训练段策略 | 样本外策略 | 样本外买入持有基准 |",
        "| --- | --- | --- | --- |",
        f"| 总收益率 | {result.train.total_return:.2%} | {result.test.total_return:.2%} | {result.benchmark.total_return:.2%} |",
        f"| 最大回撤 | {result.train.max_drawdown:.2%} | {result.test.max_drawdown:.2%} | {result.benchmark.max_drawdown:.2%} |",
        f"| 夏普比率 | {_format_optional(result.train.sharpe_ratio)} | {_format_optional(result.test.sharpe_ratio)} | {_format_optional(result.benchmark.sharpe_ratio)} |",
        "",
        f"- 相对样本外基准超额收益：{result.strategy_excess_return:.2%}",
        f"- 策略门槛（样本外收益跑赢基准）：**{status}**",
        "",
        "## 使用说明",
        "",
        "- 训练段与测试段严格按时间先后划分，测试段不参与策略参数选择。",
        "- 未通过门槛的规则不能作为候选实盘策略；需要继续改进或淘汰。",
        "- 单一股票和单一时间段不足以证明有效性，应在多个股票、市场状态中重复验证。",
        "",
    ]
    return "\n".join(lines)


def render_screening_markdown(candidates: list[Candidate], failures: dict[str, str]) -> str:
    """Render a ranked stock-universe view and retrieval failures separately."""

    lines = [
        "# 股票池候选筛选",
        "",
        "| 排名 | 股票 | 分数 | 动作 | 收盘价 | RSI |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for rank, candidate in enumerate(candidates, start=1):
        rsi = "数据不足" if candidate.rsi is None else f"{candidate.rsi:.1f}"
        lines.append(
            f"| {rank} | {candidate.symbol} | {candidate.score} | {candidate.decision.action.value} | {candidate.close:.2f} | {rsi} |"
        )
    lines.extend([
        "",
        "## 筛选边界",
        "",
        "- 排名是规则评分，不代表预测收益；候选股票仍须通过样本外验证后才可进入模拟盘观察。",
        "- 本筛选不包含基本面、新闻、行业相关性或流动性约束，它们将在后续 Agent 中纳入。",
    ])
    if failures:
        lines.extend(["", "## 未获取的数据", ""])
        lines.extend(f"- {symbol}: {message}" for symbol, message in failures.items())
    lines.append("")
    return "\n".join(lines)


def render_portfolio_markdown(proposal: PortfolioProposal) -> str:
    """Render a paper portfolio proposal, including rejected candidates."""

    lines = [
        "# 模拟组合建议",
        "",
        f"初始模拟资金：{proposal.initial_capital:,.2f}",
        "",
        "| 股票 | 评分 | 资金占比 | 模拟资金 | 止损参考价 |",
        "| --- | --- | --- | --- | --- |",
    ]
    lines.extend(
        f"| {item.symbol} | {item.score} | {item.weight:.0%} | {item.capital:,.2f} | {item.stop_loss_price:.2f} |"
        for item in proposal.allocations
    )
    if not proposal.allocations:
        lines.append("| — | — | 0% | 0.00 | — |")
    lines.extend([
        "",
        f"未分配现金：{proposal.unallocated_cash:,.2f}",
        "",
        "## 排除原因",
        "",
        *[f"- {reason}" for reason in proposal.excluded],
        "",
        "## 执行边界",
        "",
        "- 这是模拟组合建议，不能连接券商或创建真实订单。",
        "- 只纳入同时通过策略、评分和样本外验证的股票；现金是有效的风险控制结果。",
        "- 建仓前仍须人工复核实时价格、停牌、涨跌停、流动性和重大事件。",
        "",
    ])
    return "\n".join(lines)


def render_optimisation_markdown(symbol: str, result: OptimisationResult) -> str:
    """Report strategy selection separately from untouched test performance."""

    selected = result.selected.config
    lines = [
        f"# {symbol.upper()} 策略选择与样本外测试",
        "",
        f"样本外测试开始：{result.split_date.strftime('%Y-%m-%d')}",
        "",
        "## 训练段选择结果",
        "",
        "| 快均线 | 慢均线 | RSI 下限 | 训练收益 | 训练最大回撤 | 选择分数 |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    lines.extend(
        f"| {item.config.fast_window} | {item.config.slow_window} | {item.config.buy_rsi_min:.0f} | "
        f"{item.result.total_return:.2%} | {item.result.max_drawdown:.2%} | {item.score:.2%} |"
        for item in result.training_evaluations
    )
    lines.extend([
        "",
        f"选定规则：{selected.fast_window}/{selected.slow_window} 日均线，RSI 下限 {selected.buy_rsi_min:.0f}。",
        "",
        "## 未参与选择的测试段",
        "",
        f"- 策略收益：{result.test_result.total_return:.2%}",
        f"- 策略最大回撤：{result.test_result.max_drawdown:.2%}",
        f"- 买入持有基准收益：{result.benchmark.total_return:.2%}",
        f"- 相对基准超额收益：{result.test_excess_return:.2%}",
        "",
        "测试期表现只用于评估，不会用于重新选择本轮参数。单次测试不能证明策略有效，应在更多股票和滚动时间窗上重复验证。",
        "",
    ])
    return "\n".join(lines)


def render_fundamentals_markdown(snapshot: FundamentalSnapshot) -> str:
    """Render the fundamental Agent output with its reporting-date limitation."""

    def metric(value: float | None, suffix: str = "") -> str:
        return "数据缺失" if value is None else f"{value:.2f}{suffix}"

    lines = [
        f"# {snapshot.symbol} 基本面快照",
        "",
        f"最新财务报告期：{snapshot.as_of.strftime('%Y-%m-%d')}",
        "",
        "| 指标 | 数值 |",
        "| --- | --- |",
        f"| 基本面评分 | {snapshot.score}/100 |",
        f"| 净资产收益率 | {metric(snapshot.roe, '%')} |",
        f"| 营收增长率 | {metric(snapshot.revenue_growth, '%')} |",
        f"| 净利润增长率 | {metric(snapshot.profit_growth, '%')} |",
        f"| 资产负债率 | {metric(snapshot.debt_ratio, '%')} |",
        f"| 每股经营现金流 | {metric(snapshot.operating_cash_per_share, ' 元')} |",
        "",
        "## 观察",
        "",
        *[f"- {item}" for item in snapshot.observations],
        "",
        "## 风险提示",
        "",
        *[f"- {item}" for item in snapshot.risk_notes],
        "",
    ]
    return "\n".join(lines)


def render_daily_brief_markdown(brief: DailyBrief) -> str:
    """Render the unified daily research view without hiding failed gates."""

    lines = [
        "# 每日决策简报",
        "",
        "| 股票 | 技术评分 | 当前动作 | 基本面评分 | 样本外超额收益 | 资格 |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for candidate in brief.candidates:
        fundamental = brief.fundamentals.get(candidate.symbol)
        validation = brief.validations.get(candidate.symbol)
        fundamental_score = "缺失" if fundamental is None else str(fundamental.score)
        excess = "未验证" if validation is None else f"{validation.strategy_excess_return:.2%}"
        qualified = any(item.symbol == candidate.symbol for item in brief.portfolio.allocations)
        lines.append(
            f"| {candidate.symbol} | {candidate.score} | {candidate.decision.action.value} | {fundamental_score} | {excess} | {'通过' if qualified else '不通过'} |"
        )
    lines.extend(["", "## 模拟组合", ""])
    lines.extend(
        f"- {item.symbol}：{item.weight:.0%}，模拟资金 {item.capital:,.2f}，止损参考价 {item.stop_loss_price:.2f}。"
        for item in brief.portfolio.allocations
    )
    if not brief.portfolio.allocations:
        lines.append(f"- 当前无合格标的，保留现金 {brief.portfolio.unallocated_cash:,.2f}。")
    lines.extend(["", "## 不通过/排除原因", "", *[f"- {reason}" for reason in brief.portfolio.excluded]])
    if brief.issues:
        lines.extend(["", "## 数据问题", "", *[f"- {symbol}: {message}" for symbol, message in brief.issues.items()]])
    lines.extend(["", "本简报为研究和模拟用途，不构成投资建议或真实交易指令。"])
    return "\n".join(lines)
