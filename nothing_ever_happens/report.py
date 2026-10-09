"""Turn simulation results into terminal output."""

from __future__ import annotations

import csv
from collections import defaultdict
from statistics import mean, median

from .simulator import SimResult

_BARS = "▁▂▃▄▅▆▇█"


def sparkline(values: list[float], width: int = 60) -> str:
    if len(values) > width:
        step = len(values) / width
        values = [values[int(i * step)] for i in range(width)] + [values[-1]]
    lo, hi = min(values), max(values)
    span = (hi - lo) or 1.0
    return "".join(_BARS[int((v - lo) / span * (len(_BARS) - 1))] for v in values)


def _pct(x: float) -> str:
    return f"{x * 100:+.1f}%"


def single_run(r: SimResult, show_trades: int = 15) -> str:
    closed = r.closed
    wins = [t for t in closed if t.won]
    losses = [t for t in closed if not t.won]
    lines = [
        f"Simulated {r.days} days, {r.markets_seen} fake markets listed, "
        f"{len(r.trades)} bets placed ({len(r.trades) - len(closed)} still open at the end).",
        "",
        f"  Bankroll:      ${r.starting_bankroll:,.2f} -> ${r.final_equity:,.2f}  "
        f"({_pct(r.total_return)})",
        f"  Max drawdown:  {r.max_drawdown * 100:.1f}%",
    ]
    if closed:
        lines += [
            f"  Win rate:      {len(wins)}/{len(closed)} ({len(wins) / len(closed) * 100:.1f}%)",
            f"  Avg win:       ${mean(t.pnl for t in wins):,.2f}" if wins else "  Avg win:       -",
            f"  Avg loss:      ${mean(t.pnl for t in losses):,.2f}" if losses else "  Avg loss:      -",
            f"  Worst loss:    ${min(t.pnl for t in closed):,.2f}",
            f"  Losing streak: {_longest_losing_streak(r)} bets in a row",
        ]
    lines += ["", "  Equity: " + sparkline(r.equity_curve), ""]

    by_cat: dict[str, list] = defaultdict(list)
    for t in closed:
        by_cat[t.market.category].append(t)
    if by_cat:
        lines.append(f"  {'category':<12} {'bets':>5} {'lost':>5} {'pnl':>10}")
        for cat, ts in sorted(by_cat.items(), key=lambda kv: -sum(t.pnl for t in kv[1])):
            lost = sum(1 for t in ts if not t.won)
            lines.append(f"  {cat:<12} {len(ts):>5} {lost:>5} {sum(t.pnl for t in ts):>10,.2f}")
        lines.append("")

    if show_trades and r.trades:
        # Show every loss (that's where the story is) plus some wins for flavour.
        sample = [t for t in r.trades if t.pnl is not None and not t.won]
        sample += [t for t in r.trades if t.won][: max(0, show_trades - len(sample))]
        sample.sort(key=lambda t: t.day_opened)
        lines.append(f"  Sample bets (all {len(losses)} losses + some wins):")
        for t in sample[:max(show_trades, len(losses))]:
            outcome = "YES happened" if t.market.resolved_yes else "nothing"
            lines.append(
                f"   d{t.day_opened:>3} NO @{t.price:.3f} ${t.stake:>7.2f}  "
                f"{outcome:<12} {t.pnl:>+8.2f}  {t.market.title}"
            )
    return "\n".join(lines)


def _longest_losing_streak(r: SimResult) -> int:
    best = cur = 0
    for t in sorted(r.closed, key=lambda t: t.day_closed):
        cur = 0 if t.won else cur + 1
        best = max(best, cur)
    return best


def _percentile(sorted_vals: list[float], q: float) -> float:
    i = min(int(q * len(sorted_vals)), len(sorted_vals) - 1)
    return sorted_vals[i]


def monte_carlo(label: str, results: list[SimResult]) -> str:
    rets = sorted(r.total_return for r in results)
    dds = sorted(r.max_drawdown for r in results)
    n = len(results)
    return (
        f"{label:<22} median {_pct(median(rets)):>8}  "
        f"p5 {_pct(_percentile(rets, 0.05)):>8}  p95 {_pct(_percentile(rets, 0.95)):>8}  "
        f"P(loss) {sum(x < 0 for x in rets) / n * 100:5.1f}%  "
        f"P(-25%+) {sum(x <= -0.25 for x in rets) / n * 100:5.1f}%  "
        f"median DD {median(dds) * 100:4.1f}%  worst DD {dds[-1] * 100:4.1f}%"
    )


def write_trades_csv(r: SimResult, path: str) -> None:
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["market_id", "title", "category", "day_opened", "deadline_day",
                    "day_closed", "yes_price", "true_p", "no_price_paid", "stake",
                    "fee", "shares", "resolved_yes", "pnl"])
        for t in r.trades:
            m = t.market
            w.writerow([m.id, m.title, m.category, t.day_opened, m.deadline_day,
                        t.day_closed, m.yes_price, round(m.true_p, 4), round(t.price, 4),
                        round(t.stake, 2), round(t.fee, 2), round(t.shares, 2),
                        m.resolved_yes if t.pnl is not None else "",
                        "" if t.pnl is None else round(t.pnl, 2)])
