"""Day-by-day paper trading over fake markets."""

from __future__ import annotations

import random
from collections import defaultdict
from dataclasses import dataclass, field

from .markets import Market, MarketConfig, MarketFactory
from .strategy import NothingEverHappens, StrategyConfig


@dataclass
class SimConfig:
    days: int = 365
    starting_bankroll: float = 1000.0
    # Paid on top of the quoted NO price when buying (half the bid/ask spread
    # plus slippage), in dollars per share.
    spread: float = 0.01
    # Taker fee as a fraction of the amount spent.
    fee_rate: float = 0.0


@dataclass
class Trade:
    market: Market
    day_opened: int
    stake: float      # dollars spent on shares, excluding fees
    fee: float
    price: float      # paid per NO share
    shares: float
    pnl: float | None = None
    day_closed: int | None = None

    @property
    def won(self) -> bool:
        return self.pnl is not None and self.pnl > 0


@dataclass
class SimResult:
    trades: list[Trade]
    equity_curve: list[float]   # end-of-day equity, open positions at cost
    starting_bankroll: float
    markets_seen: int
    days: int

    @property
    def final_equity(self) -> float:
        return self.equity_curve[-1]

    @property
    def total_return(self) -> float:
        return self.final_equity / self.starting_bankroll - 1.0

    @property
    def closed(self) -> list[Trade]:
        return [t for t in self.trades if t.pnl is not None]

    @property
    def max_drawdown(self) -> float:
        peak, worst = self.equity_curve[0], 0.0
        for e in self.equity_curve:
            peak = max(peak, e)
            worst = max(worst, 1.0 - e / peak)
        return worst


def run(sim: SimConfig, mkt: MarketConfig, strat: StrategyConfig,
        seed: int | None = None) -> SimResult:
    rng = random.Random(seed)
    factory = MarketFactory(mkt, rng)
    bot = NothingEverHappens(strat)

    cash = sim.starting_bankroll
    open_trades: dict[int, list[Trade]] = defaultdict(list)  # by resolution day
    exposure_by_cat: dict[str, float] = defaultdict(float)
    total_exposure = 0.0
    trades: list[Trade] = []
    curve = [cash]
    seen = 0

    for day in range(sim.days):
        # 1. Settle everything resolving today.
        for t in open_trades.pop(day, []):
            payout = 0.0 if t.market.resolved_yes else t.shares
            cash += payout
            t.pnl = payout - t.stake - t.fee
            t.day_closed = day
            exposure_by_cat[t.market.category] -= t.stake + t.fee
            total_exposure -= t.stake + t.fee

        # 2. Look at newly listed markets and place bets.
        for m in factory.new_markets(day):
            seen += 1
            factory.resolve(m)  # outcome is hidden from the bot until settlement
            if not bot.wants(m, day):
                continue
            price = min(m.no_price + sim.spread, 0.999)
            equity = cash + total_exposure
            budget = bot.stake(m, equity, cash, total_exposure,
                               exposure_by_cat[m.category])
            if budget <= 0:
                continue
            stake = budget / (1.0 + sim.fee_rate)
            fee = budget - stake
            t = Trade(m, day, stake, fee, price, stake / price)
            cash -= budget
            total_exposure += budget
            exposure_by_cat[m.category] += budget
            open_trades[m.resolution_day].append(t)
            trades.append(t)

        curve.append(cash + total_exposure)

    return SimResult(trades, curve, sim.starting_bankroll, seen, sim.days)
