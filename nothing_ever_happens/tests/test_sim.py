import random
import unittest

from nothing_ever_happens.markets import MarketConfig, MarketFactory
from nothing_ever_happens.simulator import SimConfig, run
from nothing_ever_happens.strategy import StrategyConfig


def _markets(cfg: MarketConfig, days: int = 2000, seed: int = 0):
    f = MarketFactory(cfg, random.Random(seed))
    out = []
    for d in range(days):
        for m in f.new_markets(d):
            f.resolve(m)
            out.append(m)
    return out


class MarketTests(unittest.TestCase):
    def test_outcomes_match_true_probability(self):
        # Correlation must cluster outcomes without changing how often YES happens.
        for scale in (0.0, 1.0):
            ms = _markets(MarketConfig(correlation_scale=scale))
            expected = sum(m.true_p for m in ms) / len(ms)
            actual = sum(m.resolved_yes for m in ms) / len(ms)
            self.assertAlmostEqual(actual, expected, delta=0.01, msg=f"scale={scale}")

    def test_hype_premium_shifts_prices(self):
        ms = _markets(MarketConfig(hype_premium=0.03, price_noise=0.0), days=300)
        unclipped = [m for m in ms if 0.005 < m.yes_price < 0.60]
        avg = sum(m.mispricing for m in unclipped) / len(unclipped)
        self.assertAlmostEqual(avg, 0.03, delta=0.002)

    def test_yes_resolves_within_window(self):
        for m in _markets(MarketConfig(), days=200):
            self.assertGreater(m.resolution_day, m.listed_day)
            self.assertLessEqual(m.resolution_day, m.deadline_day)
            if not m.resolved_yes:
                self.assertEqual(m.resolution_day, m.deadline_day)


class SimulatorTests(unittest.TestCase):
    def test_same_seed_same_result(self):
        a = run(SimConfig(), MarketConfig(), StrategyConfig(), seed=7)
        b = run(SimConfig(), MarketConfig(), StrategyConfig(), seed=7)
        self.assertEqual(a.equity_curve, b.equity_curve)

    def test_equity_equals_bankroll_plus_realised_pnl(self):
        # Open positions are carried at cost, so they don't move equity.
        r = run(SimConfig(fee_rate=0.02), MarketConfig(), StrategyConfig(), seed=3)
        self.assertTrue(r.closed)
        realised = sum(t.pnl for t in r.closed)
        self.assertAlmostEqual(r.final_equity, r.starting_bankroll + realised, places=6)

    def test_trade_payoffs(self):
        r = run(SimConfig(fee_rate=0.01), MarketConfig(), StrategyConfig(), seed=5)
        for t in r.closed:
            if t.market.resolved_yes:
                self.assertAlmostEqual(t.pnl, -(t.stake + t.fee))
            else:
                self.assertAlmostEqual(t.pnl, t.shares - t.stake - t.fee)

    def test_bot_respects_filters(self):
        strat = StrategyConfig(min_yes_price=0.05, max_yes_price=0.10,
                               max_days_to_deadline=30, categories=("politics",))
        r = run(SimConfig(), MarketConfig(), strat, seed=1)
        self.assertTrue(r.trades)
        for t in r.trades:
            self.assertEqual(t.market.category, "politics")
            self.assertTrue(0.05 <= t.market.yes_price <= 0.10)
            self.assertLessEqual(t.market.deadline_day - t.day_opened, 30)

    def test_no_edge_no_profit(self):
        # With fair prices, no spread and no fees, the bot should break even on average.
        sim, mkt = SimConfig(spread=0.0), MarketConfig(hype_premium=0.0, price_noise=0.0)
        rets = [run(sim, mkt, StrategyConfig(), seed=s).total_return for s in range(60)]
        self.assertAlmostEqual(sum(rets) / len(rets), 0.0, delta=0.03)


if __name__ == "__main__":
    unittest.main()
