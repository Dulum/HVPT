"""The "nothing ever happens" strategy: buy NO on dramatic events.

The bot only sees what a real trader would see (title, category, price, deadline),
never the hidden true probability.
"""

from __future__ import annotations

from dataclasses import dataclass

from .markets import Market


@dataclass
class StrategyConfig:
    # Only fade markets whose YES price falls in this band. Below the floor the
    # NO payout is too small to be worth locking up capital; above the ceiling
    # something might actually be happening.
    min_yes_price: float = 0.03
    max_yes_price: float = 0.20
    max_days_to_deadline: int = 90
    # Fraction of current equity to stake per bet.
    bet_fraction: float = 0.02
    # Caps on how much of equity can be tied up at once.
    max_category_exposure: float = 0.25
    max_total_exposure: float = 0.80
    min_bet: float = 1.0
    categories: tuple[str, ...] | None = None  # None = all categories


class NothingEverHappens:
    def __init__(self, cfg: StrategyConfig):
        self.cfg = cfg

    def wants(self, m: Market, today: int) -> bool:
        c = self.cfg
        if c.categories is not None and m.category not in c.categories:
            return False
        if not c.min_yes_price <= m.yes_price <= c.max_yes_price:
            return False
        return m.deadline_day - today <= c.max_days_to_deadline

    def stake(self, m: Market, equity: float, cash: float,
              total_exposure: float, category_exposure: float) -> float:
        """Dollars to put on NO, or 0 to skip."""
        c = self.cfg
        amount = min(
            equity * c.bet_fraction,
            cash,
            equity * c.max_total_exposure - total_exposure,
            equity * c.max_category_exposure - category_exposure,
        )
        return amount if amount >= c.min_bet else 0.0
