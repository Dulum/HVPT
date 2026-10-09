"""Command line entry point.

    python -m nothing_ever_happens run              # one simulated year, with a trade log
    python -m nothing_ever_happens montecarlo       # many years, across hype-premium scenarios
"""

from __future__ import annotations

import argparse

from . import report
from .markets import MarketConfig
from .simulator import SimConfig, run
from .strategy import StrategyConfig


def _add_common(p: argparse.ArgumentParser) -> None:
    p.add_argument("--days", type=int, default=365)
    p.add_argument("--bankroll", type=float, default=1000.0)
    p.add_argument("--hype", type=float, default=0.02,
                   help="how much the crowd overprices YES, e.g. 0.02 = 2 cents (default 0.02)")
    p.add_argument("--spread", type=float, default=0.01,
                   help="extra cost per NO share when buying (default 0.01)")
    p.add_argument("--fee", type=float, default=0.0, help="taker fee rate (default 0)")
    p.add_argument("--markets-per-day", type=float, default=4.0)
    p.add_argument("--correlation", type=float, default=1.0,
                   help="scale on how much bad news clusters; 0 = independent (default 1)")
    p.add_argument("--bet", type=float, default=0.02,
                   help="fraction of equity per bet (default 0.02)")
    p.add_argument("--min-yes", type=float, default=0.03)
    p.add_argument("--max-yes", type=float, default=0.20)
    p.add_argument("--max-days", type=int, default=90,
                   help="skip markets resolving further out than this")
    p.add_argument("--categories", type=lambda s: tuple(s.split(",")), default=None,
                   help="comma-separated list, e.g. politics,legal (default all)")


def _configs(a: argparse.Namespace, hype: float | None = None):
    sim = SimConfig(days=a.days, starting_bankroll=a.bankroll, spread=a.spread,
                    fee_rate=a.fee)
    mkt = MarketConfig(markets_per_day=a.markets_per_day,
                       hype_premium=a.hype if hype is None else hype,
                       correlation_scale=a.correlation)
    strat = StrategyConfig(min_yes_price=a.min_yes, max_yes_price=a.max_yes,
                           max_days_to_deadline=a.max_days, bet_fraction=a.bet,
                           categories=a.categories)
    return sim, mkt, strat


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="nothing_ever_happens",
                                     description="Paper-trade 'nothing ever happens' on fake markets.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_run = sub.add_parser("run", help="simulate one period and show the bets")
    _add_common(p_run)
    p_run.add_argument("--seed", type=int, default=None)
    p_run.add_argument("--show", type=int, default=15, help="sample bets to print")
    p_run.add_argument("--csv", help="write every bet to this CSV file")

    p_mc = sub.add_parser("montecarlo", help="run many simulations and summarise")
    _add_common(p_mc)
    p_mc.add_argument("--runs", type=int, default=300)
    p_mc.add_argument("--scenarios", type=lambda s: [float(x) for x in s.split(",")],
                      default=None,
                      help="comma-separated hype premiums to compare, "
                           "e.g. -0.01,0,0.01,0.02,0.04 (default: just --hype)")

    a = parser.parse_args(argv)

    if a.cmd == "run":
        result = run(*_configs(a), seed=a.seed)
        print(report.single_run(result, show_trades=a.show))
        if a.csv:
            report.write_trades_csv(result, a.csv)
            print(f"\nWrote {len(result.trades)} bets to {a.csv}")
        return

    scenarios = a.scenarios if a.scenarios is not None else [a.hype]
    print(f"{a.runs} simulated runs of {a.days} days each, starting with ${a.bankroll:,.0f}.\n")
    for hype in scenarios:
        results = [run(*_configs(a, hype), seed=i) for i in range(a.runs)]
        print(report.monte_carlo(f"hype premium {hype:+.3f}", results))


if __name__ == "__main__":
    main()
