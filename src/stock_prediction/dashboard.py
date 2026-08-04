"""A clear, local-only dashboard for manual Tonghuashun order planning."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import sys

import pandas as pd
import streamlit as st

# Streamlit can otherwise prefer an older installed copy of this package.
PROJECT_SRC = Path(__file__).resolve().parents[1]
if str(PROJECT_SRC) not in sys.path:
    sys.path.insert(0, str(PROJECT_SRC))

from stock_prediction.account import Holding, TradingProfile, load_profile, merge_watchlist, save_profile
from stock_prediction.daily import build_daily_brief
from stock_prediction.fundamentals import analyse_fundamentals, fetch_fundamental_indicators
from stock_prediction.holding_ocr import recognise_holdings
from stock_prediction.providers import RealtimeQuote, fetch_ashare_realtime_quote, fetch_history
from stock_prediction.trade_plan import PlannedOrder, TradePlan, build_trade_plan


PROFILE_PATH = Path("data/trading_profile.json")
st.set_page_config(page_title="股票作战台", page_icon="📈", layout="wide", initial_sidebar_state="expanded")
st.markdown(
    """
<style>
    :root { --ink:#10233f; --muted:#6f7f94; --paper:#f4f7fb; --line:#e2e8f1; --blue:#2864dc; --green:#079669; --red:#db4055; --amber:#b77913; }
    .stApp { background: var(--paper); color:var(--ink); }
    .block-container { max-width:1480px; padding-top:1.35rem; padding-bottom:3rem; }
    [data-testid="stSidebar"] { background:#f7f9fc; border-right:1px solid #e2e8f1; }
    [data-testid="stSidebar"] > div:first-child { padding-top:.4rem; }
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3 { color:var(--ink); }
    [data-testid="stSidebar"] .stCaption { color:var(--muted) !important; }
    [data-testid="stSidebar"] [data-baseweb="input"] > div,
    [data-testid="stSidebar"] textarea,
    [data-testid="stSidebar"] [data-baseweb="select"] > div { background:#fff; border-color:#dbe3ef; border-radius:10px; }
    [data-testid="stSidebar"] [data-baseweb="input"] input,
    [data-testid="stSidebar"] textarea,
    [data-testid="stSidebar"] [data-baseweb="select"] * { color:var(--ink); }
    [data-testid="stSidebar"] [data-testid="stDataFrameResizable"] { border:1px solid #e2e8f1; border-radius:10px; overflow:hidden; }
    .sidebar-brand { background:linear-gradient(135deg,#173b72,#2864dc); color:#fff; border-radius:14px; padding:16px; margin:4px 0 18px; }
    .sidebar-brand h2 { color:#fff !important; font-size:1.2rem; margin:0; }.sidebar-brand p { color:#dbe9ff !important; font-size:.79rem; margin:4px 0 0; }
    .sidebar-section { color:#52647c; font-size:.72rem; font-weight:750; letter-spacing:.08em; text-transform:uppercase; margin:18px 0 7px; }
    .topline { display:flex; align-items:center; justify-content:space-between; gap:20px; background:#fff; border:1px solid var(--line); border-radius:18px; padding:20px 24px; box-shadow:0 6px 24px rgba(16,35,63,.06); }
    .topline h1 { font-size:1.65rem; margin:0; letter-spacing:-.03em; }
    .topline p { color:var(--muted); margin:.4rem 0 0; }
    .live { background:#e9faf4; color:#067554; padding:8px 12px; border-radius:99px; font-weight:650; white-space:nowrap; }
    .metric-card { background:#fff; border:1px solid var(--line); border-radius:14px; padding:14px 16px; min-height:92px; }
    .metric-label { color:var(--muted); font-size:.82rem; }.metric-value { color:var(--ink); font-size:1.45rem; font-weight:750; margin-top:5px; }
    .section-title { margin:1.6rem 0 .65rem; font-size:1.08rem; font-weight:750; }
    .order { background:#fff; border:1px solid var(--line); border-left:5px solid var(--blue); border-radius:14px; padding:16px 18px; margin-bottom:12px; box-shadow:0 3px 12px rgba(16,35,63,.035); }
    .order.buy { border-left-color:var(--red); }.order.sell { border-left-color:var(--green); }.order.hold { border-left-color:var(--amber); }.order.cash { border-left-color:#8391a3; }
    .tag { display:inline-block; border-radius:99px; padding:3px 9px; font-size:.75rem; font-weight:750; margin-left:8px; background:#edf2ff; color:#2c5fc5; }
    .buy .tag { background:#fff0f1; color:#c12f43; }.sell .tag { background:#e9faf4; color:#067554; }.hold .tag { background:#fff7e6; color:#9a6508; }.cash .tag { background:#eef1f4; color:#576676; }
    .order-title { font-size:1.08rem; font-weight:750; }.order-detail { color:#42566f; margin-top:9px; line-height:1.65; }.order-reason { color:var(--muted); font-size:.88rem; margin-top:7px; }
    .quote { background:#fff; border:1px solid var(--line); border-radius:12px; padding:12px 14px; }
    .quote-name { color:var(--muted); font-size:.8rem; }.quote-price { font-weight:750; font-size:1.15rem; margin-top:3px; }
    .gate { background:#fff; border:1px solid var(--line); border-radius:12px; padding:12px; min-height:104px; }.gate strong { display:block; margin-bottom:4px; }.pass { color:var(--green); }.fail { color:var(--red); }
</style>
    """,
    unsafe_allow_html=True,
)


def parse_holdings(frame: pd.DataFrame) -> tuple[Holding, ...]:
    holdings: list[Holding] = []
    for _, row in frame.dropna(how="all").iterrows():
        symbol = str(row.get("股票代码", "")).strip().upper()
        if not symbol:
            continue
        holdings.append(Holding(symbol, int(float(row.get("持仓股数", 0))), float(row.get("持仓成本", 0))))
    return tuple(holdings)


def fmt_price(value: float | None) -> str:
    return "—" if value is None else f"¥{value:,.2f}"


def css_action(action: str) -> str:
    return {"BUY":"buy", "SELL":"sell", "HOLD":"hold"}.get(action, "cash")


def action_name(action: str) -> str:
    return {"BUY":"计划买入", "SELL":"计划卖出", "HOLD":"继续持有", "CASH":"保持现金", "WAIT":"暂不买入", "REVIEW":"人工复核"}.get(action, action)


def order_card(order: PlannedOrder) -> None:
    price = "—" if order.limit_low is None else f"{order.limit_low:.2f} – {order.limit_high:.2f}"
    stop = "—" if order.stop_loss is None else f"¥{order.stop_loss:.2f}"
    st.markdown(
        f"<div class='order {css_action(order.action)}'><span class='order-title'>{order.symbol}</span><span class='tag'>{action_name(order.action)}</span>"
        f"<div class='order-detail'>数量 <b>{order.quantity:,} 股</b>　限价参考 <b>{price}</b>　止损参考 <b>{stop}</b>　预计金额 <b>¥{order.estimated_value:,.2f}</b></div>"
        f"<div class='order-reason'>{order.reason}</div></div>", unsafe_allow_html=True)


def candidate_blockers(brief, symbol: str) -> list[str]:
    return [text.split("：", 1)[1] for text in brief.portfolio.excluded if text.startswith(f"{symbol}：")]


def clean_watchlist(values) -> tuple[str, ...]:
    codes: list[str] = []
    for value in values:
        code = str(value).strip()
        if code.isdigit() and len(code) == 6 and code.startswith(("0", "3", "6", "9")) and code not in codes:
            codes.append(code)
    return tuple(codes)


def profile_watchlist(profile: TradingProfile) -> tuple[str, ...]:
    """Read watchlist safely while an already-running Streamlit process upgrades."""

    return tuple(getattr(profile, "watchlist", ()))


def rebuild_profile(profile: TradingProfile, *, cash: float | None = None, risk: float | None = None, position: float | None = None, holdings: tuple[Holding, ...] | None = None, watchlist: tuple[str, ...] | None = None) -> TradingProfile:
    """Create a profile without crashing if an old in-memory class remains loaded."""

    values = (cash if cash is not None else profile.available_cash, risk if risk is not None else profile.risk_per_trade, position if position is not None else profile.max_position_fraction, holdings if holdings is not None else profile.holdings)
    try:
        return TradingProfile(*values, watchlist=watchlist if watchlist is not None else profile_watchlist(profile))
    except TypeError:
        return TradingProfile(*values)


def render_watchlist(profile: TradingProfile) -> None:
    st.title("自选股票")
    st.caption("批量导入会立即保存到本地；下一次“今日计划”会直接使用这里的全部代码。")
    left, right = st.columns([2, 1])
    current = list(profile_watchlist(profile))
    with right:
        pasted = st.text_area("批量导入股票代码", placeholder="600519,000858,601318\n支持逗号、空格或换行", height=140)
        if st.button("导入并保存", type="primary", use_container_width=True):
            merged = merge_watchlist(current, pasted)
            if len(merged) == len(current):
                st.warning("没有识别到新的六码 A 股代码。")
            else:
                save_profile(PROFILE_PATH, rebuild_profile(profile, watchlist=merged))
                st.success(f"已新增 {len(merged) - len(current)} 只；股票池现有 {len(merged)} 只。")
                st.rerun()
    with left:
        keyword = st.text_input("搜索股票代码", placeholder="输入代码筛选")
        visible = [code for code in current if keyword.strip() in code]
        st.caption(f"当前显示 {len(visible)} / {len(current)} 只。编辑请在下方完整表格中进行，以免筛选时误删未显示的股票。")
        if keyword.strip():
            st.dataframe(pd.DataFrame({"搜索结果": visible}), use_container_width=True, hide_index=True, height=160)
    st.markdown("#### 全部股票池")
    edited = st.data_editor(pd.DataFrame({"股票代码": current}), num_rows="dynamic", height=480, use_container_width=True, hide_index=True, key="watchlist_editor")
    save_column, clear_column = st.columns(2)
    if save_column.button("保存表格修改", use_container_width=True):
        codes = clean_watchlist(edited["股票代码"].tolist())
        save_profile(PROFILE_PATH, rebuild_profile(profile, watchlist=codes))
        st.success(f"已保存 {len(codes)} 只自选股票。")
        st.rerun()
    if clear_column.button("一键清空全部自选股", use_container_width=True, help="清空本机保存的全部自选代码。"):
        save_profile(PROFILE_PATH, rebuild_profile(profile, watchlist=()))
        st.success("已清空全部自选股票。")
        st.rerun()


def render_account(profile: TradingProfile) -> None:
    st.title("账户与持仓")
    st.caption("持仓既可以上传截图识别，也可以手动添加；两种方式都必须由你确认后才保存。")
    settings, _ = st.columns([1, 2], gap="large")
    with settings:
        cash = st.number_input("可用现金（元）", min_value=0.0, value=float(profile.available_cash), step=10_000.0)
        risk = st.slider("单笔最大风险", .5, 3.0, float(profile.risk_per_trade * 100), .5, format="%.1f%%")
        position = st.slider("单只股票上限", 10.0, 30.0, float(profile.max_position_fraction * 100), 5.0, format="%.0f%%")
        st.caption("不会登录或控制同花顺；只保存你确认后的本地资料。")

    def save_confirmed(frame: pd.DataFrame) -> None:
        try:
            confirmed = parse_holdings(frame)
            updated = rebuild_profile(profile, cash=cash, risk=risk / 100, position=position / 100, holdings=confirmed, watchlist=profile_watchlist(profile))
            save_profile(PROFILE_PATH, updated)
            st.success("已保存。下一次生成计划会使用这些资金和持仓。")
        except (TypeError, ValueError) as exc:
            st.error(f"请核对持仓数据：{exc}")

    existing = pd.DataFrame([{"股票代码": item.symbol, "持仓股数": item.shares, "持仓成本": item.average_cost} for item in profile.holdings], columns=["股票代码", "持仓股数", "持仓成本"])
    tab_ocr, tab_manual = st.tabs(["图片识别导入", "手动添加 / 编辑"])
    with tab_ocr:
        st.markdown("#### 上传同花顺持仓截图")
        upload = st.file_uploader("上传同花顺持仓截图", type=["png", "jpg", "jpeg"])
        upload_id = f"{upload.name}:{upload.size}" if upload is not None else None
        if upload is not None and st.session_state.get("ocr_holding_upload") != upload_id:
            try:
                rows, raw = recognise_holdings(upload.getvalue())
                st.session_state["ocr_holding_draft"] = pd.DataFrame([{"股票代码": row.symbol, "持仓股数": row.shares, "持仓成本": row.average_cost} for row in rows], columns=["股票代码", "持仓股数", "持仓成本"])
                st.session_state["ocr_holding_upload"] = upload_id
                st.success(f"已识别 {len(rows)} 条候选持仓。请在下表确认或修改后保存。")
                with st.expander("查看 OCR 原始文字"):
                    st.write(" | ".join(raw))
            except Exception as exc:
                st.error(f"截图暂时无法识别：{exc}")
        ocr_frame = st.session_state.get("ocr_holding_draft", existing)
        ocr_edited = st.data_editor(ocr_frame, num_rows="dynamic", height=330, use_container_width=True, hide_index=True, key="holdings_ocr_confirm")
        if st.button("确认识别结果并保存", type="primary"):
            save_confirmed(ocr_edited)
    with tab_manual:
        st.markdown("#### 手动录入持仓")
        st.caption("点击表格底部“+”新增一行；填写股票代码、持仓股数和持仓成本。")
        manual_edited = st.data_editor(existing, num_rows="dynamic", height=380, use_container_width=True, hide_index=True, key="holdings_manual_confirm")
        if st.button("保存手动持仓", type="primary"):
            save_confirmed(manual_edited)


stored = load_profile(PROFILE_PATH)
with st.sidebar:
    st.markdown("<div class='sidebar-brand'><h2>交易作战台</h2><p>同花顺手工执行助手</p></div>", unsafe_allow_html=True)
    page = st.radio("功能", ["今日计划", "自选股票", "账户与持仓"], label_visibility="collapsed")
    st.caption(f"自选 {len(profile_watchlist(stored))} 只 · 持仓 {len(stored.holdings)} 只")

if page == "自选股票":
    render_watchlist(stored)
    st.stop()
if page == "账户与持仓":
    render_account(stored)
    st.stop()

profile = stored
st.markdown("<div class='topline'><div><h1>今日交易作战台</h1><p>平安证券 · 同花顺手工执行版　|　用在线行情生成明确、可复核的计划</p></div><div class='live'>● 在线数据模式</div></div>", unsafe_allow_html=True)
period = st.selectbox("历史验证区间", ["5y", "2y", "1y", "10y"], index=0)
run = st.button("生成今日交易计划", type="primary")
if not run:
    st.info("先在“自选股票”管理你的股票池，在“账户与持仓”确认资金和持仓；然后点击生成计划。")
    st.stop()

symbols = list(profile_watchlist(profile)) or ["600519", "000858", "601318"]
if not symbols:
    st.error("请至少输入一只六位股票代码。")
    st.stop()

histories: dict[str, pd.DataFrame] = {}
quotes: dict[str, RealtimeQuote] = {}
issues: dict[str, str] = {}
with st.spinner("正在获取在线日线、最新公开报价与基本面，并运行验证…"):
    for symbol in symbols:
        try:
            histories[symbol] = fetch_history(symbol, period, "auto")
            try:
                quotes[symbol.upper()] = fetch_ashare_realtime_quote(symbol)
            except ValueError as exc:
                issues[f"{symbol}（实时价）"] = str(exc)
        except (ValueError, OSError) as exc:
            issues[symbol] = str(exc)
if not histories:
    st.error("在线日线没有获取成功。请用“管理员启动器”启动本程序后重试，并检查网络策略或代理。")
    st.code("启动交易计划Agent_管理员.bat")
    for symbol, message in issues.items(): st.caption(f"{symbol}: {message}")
    st.stop()

fundamentals = {}
for symbol in histories:
    try:
        fundamentals[symbol.upper()] = analyse_fundamentals(symbol, fetch_fundamental_indicators(symbol))
    except ValueError as exc:
        fundamentals[symbol.upper()] = None
        issues[f"{symbol}（基本面）"] = str(exc)
brief = build_daily_brief(histories, fundamentals, issues, initial_capital=profile.available_cash)
live_prices = {symbol: quote.latest for symbol, quote in quotes.items()}
plan: TradePlan = build_trade_plan(brief, profile, live_prices)

buy_count = sum(item.action == "BUY" for item in plan.planned_orders)
sell_count = sum(item.action == "SELL" for item in plan.planned_orders)
metrics = [("计划买入", f"{buy_count} 只"), ("计划卖出/止损", f"{sell_count} 只"), ("可用现金", f"¥{profile.available_cash:,.0f}"), ("估算总资产", f"¥{plan.total_assets_estimate:,.0f}")]
for column, (label, value) in zip(st.columns(4), metrics):
    column.markdown(f"<div class='metric-card'><div class='metric-label'>{label}</div><div class='metric-value'>{value}</div></div>", unsafe_allow_html=True)

st.markdown("<div class='section-title'>最新公开报价</div>", unsafe_allow_html=True)
quote_columns = st.columns(min(4, max(1, len(histories))))
for index, symbol in enumerate(histories):
    quote = quotes.get(symbol.upper())
    if quote:
        quote_columns[index % len(quote_columns)].markdown(f"<div class='quote'><div class='quote-name'>{quote.symbol} · {quote.name}</div><div class='quote-price'>{fmt_price(quote.latest)}</div><div class='quote-name'>开 {fmt_price(quote.open)}　高 {fmt_price(quote.high)}　低 {fmt_price(quote.low)}</div></div>", unsafe_allow_html=True)
    else:
        quote_columns[index % len(quote_columns)].markdown(f"<div class='quote'><div class='quote-name'>{symbol}</div><div class='quote-price'>实时价暂不可用</div><div class='quote-name'>已用最近日线收盘价做研究</div></div>", unsafe_allow_html=True)
st.caption(f"报价请求时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}。盘中价格会变化，下单前仍须在同花顺确认。")

tab_plan, tab_why, tab_research, tab_manual = st.tabs(["今日怎么做", "为什么这样做", "研究明细", "同花顺执行"])
with tab_plan:
    st.markdown("<div class='section-title'>可执行行动</div>", unsafe_allow_html=True)
    for order in plan.planned_orders: order_card(order)
    if buy_count == 0 and sell_count == 0:
        st.info("今天没有满足全部风控门槛的新开仓标的。这不是空白结果：系统明确建议不为交易而交易，保留现金等待条件改善。")
with tab_why:
    st.markdown("<div class='section-title'>逐股资格检查</div>", unsafe_allow_html=True)
    columns = st.columns(min(3, len(brief.candidates)))
    for index, candidate in enumerate(brief.candidates):
        validation = brief.validations.get(candidate.symbol)
        fundamental = brief.fundamentals.get(candidate.symbol)
        eligible = candidate.symbol in {item.symbol for item in brief.portfolio.allocations}
        blockers = candidate_blockers(brief, candidate.symbol)
        action_ok = candidate.decision.action.value == "BUY"
        validation_ok = bool(validation and validation.passed_benchmark)
        basic_ok = bool(fundamental and fundamental.score >= 50)
        content = f"<div class='gate'><strong>{candidate.symbol}　{'可建仓' if eligible else '暂不建仓'}</strong><span class={'pass' if action_ok else 'fail'}>技术动作：{candidate.decision.action.value} / {candidate.score}分</span><br><span class={'pass' if validation_ok else 'fail'}>样本外验证：{'通过' if validation_ok else '未通过'}</span><br><span class={'pass' if basic_ok else 'fail'}>基本面：{'通过' if basic_ok else '未通过/缺失'}</span><br><small>{'；'.join(blockers) if blockers else '已通过全部资格门槛'}</small></div>"
        columns[index % len(columns)].markdown(content, unsafe_allow_html=True)
with tab_research:
    rows = []
    allocated = {item.symbol for item in brief.portfolio.allocations}
    for candidate in brief.candidates:
        validation, fundamental = brief.validations.get(candidate.symbol), brief.fundamentals.get(candidate.symbol)
        rows.append({"股票":candidate.symbol, "技术动作":candidate.decision.action.value, "技术评分":candidate.score, "日线收盘":round(candidate.close,2), "最新报价":round(live_prices.get(candidate.symbol, candidate.close),2), "基本面": "缺失" if fundamental is None else f"{fundamental.score}/100", "样本外": "未验证" if validation is None else f"{validation.strategy_excess_return:.2%}", "结论":"可建仓" if candidate.symbol in allocated else "暂不建仓"})
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    if issues:
        with st.expander("部分数据提示"):
            for symbol, message in issues.items(): st.write(f"- {symbol}: {message}")
with tab_manual:
    st.markdown("### 在同花顺执行")
    st.markdown("1. 先核对实时价、涨跌停、可用资金与已有持仓。\n2. 仅执行“计划买入/卖出”的卡片，按数量和限价参考填写。\n3. 价格明显偏离计划区间、停牌或触及涨跌停时，当天不下单，重新生成计划。\n4. 成交后将实际数量和成本填回左侧持仓并保存。")
    st.warning("本工具不登录、不读取、不控制平安证券或同花顺账户；计划仅作研究和人工决策辅助，不保证收益。")
