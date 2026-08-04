"""Command-line entry points for research, validation, and paper proposals."""

from __future__ import annotations

import argparse
from pathlib import Path

from stock_prediction.analysis import analyse_price_history
from stock_prediction.backtest import run_backtest
from stock_prediction.paper import PaperLedger
from stock_prediction.portfolio import propose_portfolio
from stock_prediction.providers import fetch_history
from stock_prediction.reporting import render_backtest_markdown, render_decision_markdown, render_markdown
from stock_prediction.screening import rank_candidates
from stock_prediction.strategy import decide
from stock_prediction.validation import validate_out_of_sample
from stock_prediction.optimization import optimise_out_of_sample
from stock_prediction.fundamentals import analyse_fundamentals, fetch_fundamental_indicators
from stock_prediction.daily import build_daily_brief


def _write_or_print(content: str, output: Path | None) -> None:
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(content, encoding="utf-8")
        print(f"Report written to: {output}")
    else:
        print(content)


def _add_symbol_command(parser: argparse.ArgumentParser, command: str, help_text: str) -> None:
    command_parser = parser.add_parser(command, help=help_text)
    command_parser.add_argument("symbol", help="Example: AAPL, 600519.SS, or 000001.SZ")
    command_parser.add_argument("--period", default="1y", help="Yahoo Finance period; default: 1y")
    command_parser.add_argument("--provider", choices=["auto", "yahoo", "akshare"], default="auto")
    command_parser.add_argument("--output", type=Path, help="Optional Markdown output path")


def _add_universe_command(parser: argparse.ArgumentParser, command: str, help_text: str) -> None:
    command_parser = parser.add_parser(command, help=help_text)
    command_parser.add_argument("symbols", nargs="+", help="Example: 600519.SS 000858.SZ 601318.SS")
    command_parser.add_argument("--period", default="5y", help="Yahoo Finance period; default: 5y")
    command_parser.add_argument("--provider", choices=["auto", "yahoo", "akshare"], default="auto")
    command_parser.add_argument("--output", type=Path, help="Optional Markdown output path")


def _load_universe(symbols: list[str], period: str, provider: str) -> tuple[dict[str, object], dict[str, str]]:
    histories = {}
    failures = {}
    for symbol in symbols:
        try:
            histories[symbol] = fetch_history(symbol, period, provider)
        except (ValueError, OSError) as exc:
            failures[symbol] = str(exc)
    return histories, failures


def _render_proposal(candidates: list, histories: dict, failures: dict[str, str], initial_cash: float, ledger: PaperLedger | None = None) -> str:
    validation_passes = {
        symbol.upper(): validate_out_of_sample(history).passed_benchmark for symbol, history in histories.items()
    }
    proposal = propose_portfolio(candidates, validation_passes, initial_capital=initial_cash)
    from stock_prediction.reporting import render_portfolio_markdown

    content = render_portfolio_markdown(proposal)
    if ledger is not None:
        orders = ledger.record_proposal(proposal)
        content += "\n## Paper order queue\n\n"
        if orders:
            content += "\n".join(
                f"- Proposed order #{order.id}: {order.symbol}, quantity {order.quantity:.2f}. "
                "Use `paper-approve` to mark it approved; no real trade is sent."
                for order in orders
            ) + "\n"
        else:
            content += "- No paper orders created because no stock passed all entry gates.\n"
    if failures:
        content += "\n## Data retrieval failures\n\n" + "\n".join(f"- {symbol}: {message}" for symbol, message in failures.items()) + "\n"
    return content


def main() -> None:
    parser = argparse.ArgumentParser(description="Stock research and paper-trading assistant; no broker connection.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command, help_text in [
        ("research", "Generate a technical research snapshot"),
        ("decision", "Generate a rule-based decision"),
        ("backtest", "Backtest the strategy"),
        ("validate", "Run chronological out-of-sample validation"),
        ("optimize", "Select a predefined strategy on training data and test it later"),
    ]:
        _add_symbol_command(subparsers, command, help_text)
    for command in ("backtest", "validate", "optimize"):
        subparsers.choices[command].add_argument("--initial-cash", type=float, default=100_000.0)

    _add_universe_command(subparsers, "screen", "Screen a supplied stock universe")
    _add_universe_command(subparsers, "portfolio", "Build a validated paper portfolio")
    _add_universe_command(subparsers, "paper-propose", "Write validated paper orders to a local queue")
    _add_universe_command(subparsers, "daily", "Generate a combined technical and fundamental daily brief")
    for command in ("portfolio", "paper-propose"):
        subparsers.choices[command].add_argument("--initial-cash", type=float, default=100_000.0)
    subparsers.choices["paper-propose"].add_argument("--database", type=Path, default=Path("data/paper_ledger.sqlite"))

    orders_parser = subparsers.add_parser("paper-orders", help="List local paper orders")
    orders_parser.add_argument("--database", type=Path, default=Path("data/paper_ledger.sqlite"))
    approve_parser = subparsers.add_parser("paper-approve", help="Manually approve one paper order; it will not execute")
    approve_parser.add_argument("order_id", type=int)
    approve_parser.add_argument("--database", type=Path, default=Path("data/paper_ledger.sqlite"))
    fundamentals_parser = subparsers.add_parser("fundamentals", help="Analyse public A-share financial indicators")
    fundamentals_parser.add_argument("symbol", help="Six-digit A-share code, for example 600519")
    fundamentals_parser.add_argument("--start-year", default="2020")
    fundamentals_parser.add_argument("--output", type=Path, help="Optional Markdown output path")

    args = parser.parse_args()
    if args.command == "paper-orders":
        orders = PaperLedger(args.database).list_orders()
        print("No paper orders." if not orders else "\n".join(
            f"#{order.id} {order.status} {order.side} {order.symbol} {order.quantity:.2f} @ {order.reference_price:.2f}"
            for order in orders
        ))
        return
    if args.command == "paper-approve":
        order = PaperLedger(args.database).approve(args.order_id)
        print(f"Paper order #{order.id} approved locally. No real order was sent.")
        return
    if args.command == "fundamentals":
        from stock_prediction.reporting import render_fundamentals_markdown

        content = render_fundamentals_markdown(
            analyse_fundamentals(args.symbol, fetch_fundamental_indicators(args.symbol, args.start_year))
        )
        _write_or_print(content, args.output)
        return
    if args.command in {"screen", "portfolio", "paper-propose", "daily"}:
        histories, failures = _load_universe(args.symbols, args.period, args.provider)
        candidates = rank_candidates(histories)
        if args.command == "screen":
            from stock_prediction.reporting import render_screening_markdown

            content = render_screening_markdown(candidates, failures)
        elif args.command == "daily":
            fundamentals = {}
            for symbol in histories:
                try:
                    fundamentals[symbol.upper()] = analyse_fundamentals(
                        symbol, fetch_fundamental_indicators(symbol)
                    )
                except ValueError as exc:
                    fundamentals[symbol.upper()] = None
                    failures[f"{symbol}（基本面）"] = str(exc)
            from stock_prediction.reporting import render_daily_brief_markdown

            content = render_daily_brief_markdown(build_daily_brief(histories, fundamentals, failures))
        else:
            ledger = PaperLedger(args.database) if args.command == "paper-propose" else None
            content = _render_proposal(candidates, histories, failures, args.initial_cash, ledger)
        _write_or_print(content, args.output)
        return

    history = fetch_history(args.symbol, args.period, args.provider)
    if args.command == "research":
        content = render_markdown(analyse_price_history(args.symbol, history))
    elif args.command == "decision":
        content = render_decision_markdown(decide(args.symbol, history))
    elif args.command == "backtest":
        content = render_backtest_markdown(args.symbol, run_backtest(history, initial_cash=args.initial_cash))
    elif args.command == "validate":
        from stock_prediction.reporting import render_validation_markdown

        content = render_validation_markdown(args.symbol, validate_out_of_sample(history, initial_cash=args.initial_cash))
    else:
        from stock_prediction.reporting import render_optimisation_markdown

        content = render_optimisation_markdown(args.symbol, optimise_out_of_sample(history, initial_cash=args.initial_cash))
    _write_or_print(content, args.output)


if __name__ == "__main__":
    main()
