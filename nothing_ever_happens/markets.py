"""Fake Polymarket-style markets.

Every market asks "Will <dramatic thing> happen by <deadline>?". Each one has a
hidden *true* probability of YES and a *quoted* YES price. The gap between them
is the "hype premium": how much the crowd overpays for drama. The premium is the
whole bet behind "nothing ever happens", so it is a parameter you choose rather
than something the simulator assumes.

Outcomes within a category and time window are correlated through a one-factor
Gaussian copula: when one war breaks out, the other war markets get more likely
too. Each market's own odds stay the same, but the losses arrive together.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from statistics import NormalDist

_STD_NORMAL = NormalDist()

PLACES = ["Veldoria", "Ostrava Republic", "Karsk", "the Meridian Union", "Tarvos",
          "New Halvard", "Brennic Isles", "Zemlany", "Corvath", "Sulmar"]
LEADERS = ["President Arlen Voss", "PM Dalia Renko", "Chancellor Ivo Marek",
           "Premier Sana Oduya", "President Teodor Kell", "PM Lucan Brisk"]
FIRMS = ["Helix AI", "Northwind Bank", "Quanta Motors", "Orbis Social",
         "Lumen Pharma", "Kestrel Exchange"]
COINS = ["BTC", "ETH", "SOL"]


@dataclass(frozen=True)
class Category:
    name: str
    templates: tuple[str, ...]
    # Beta(a, b) for the true YES probability. Mean = a / (a + b).
    alpha: float
    beta: float
    # Correlation of outcomes within the same category and time window.
    rho: float
    weight: float  # How often this category gets listed.


CATEGORIES: tuple[Category, ...] = (
    Category("geopolitics", (
        "Will {place} invade {place2} by {deadline}?",
        "Will {place} and {place2} sign a ceasefire by {deadline}?",
        "Will a nuclear weapon be detonated by {deadline}?",
        "Will {place} declare martial law by {deadline}?",
    ), alpha=1.0, beta=14.0, rho=0.35, weight=3.0),
    Category("politics", (
        "Will {leader} resign by {deadline}?",
        "Will {leader} be impeached by {deadline}?",
        "Will {place} hold a snap election by {deadline}?",
        "Will there be a coup in {place} by {deadline}?",
    ), alpha=1.2, beta=12.0, rho=0.20, weight=3.0),
    Category("legal", (
        "Will {leader} be indicted by {deadline}?",
        "Will {firm} CEO be arrested by {deadline}?",
        "Will {firm} be broken up by regulators by {deadline}?",
    ), alpha=1.0, beta=10.0, rho=0.10, weight=1.5),
    Category("markets", (
        "Will {coin} drop 50% by {deadline}?",
        "Will {firm} file for bankruptcy by {deadline}?",
        "Will there be a bank run on {firm} by {deadline}?",
    ), alpha=1.0, beta=16.0, rho=0.45, weight=1.5),
    Category("weird", (
        "Will aliens be confirmed by {deadline}?",
        "Will {firm} announce AGI by {deadline}?",
        "Will {leader} be seen in public with a llama by {deadline}?",
    ), alpha=0.6, beta=30.0, rho=0.05, weight=1.0),
)


@dataclass
class Market:
    id: int
    title: str
    category: str
    listed_day: int
    deadline_day: int
    true_p: float        # hidden real chance of YES
    yes_price: float     # what the crowd quotes for YES
    # Filled in when the market resolves.
    resolved_yes: bool | None = None
    resolution_day: int | None = None
    _latent: float = field(default=0.0, repr=False)

    @property
    def no_price(self) -> float:
        return 1.0 - self.yes_price

    @property
    def mispricing(self) -> float:
        """How much YES is overpriced (positive means fading it has an edge)."""
        return self.yes_price - self.true_p


@dataclass
class MarketConfig:
    markets_per_day: float = 4.0
    min_days: int = 7
    max_days: int = 120
    # Average overpricing of YES, in probability points (0.02 = 2 cents).
    # Zero means the crowd is right on average; negative means it underprices drama.
    hype_premium: float = 0.02
    # Per-market pricing error around the premium.
    price_noise: float = 0.015
    min_price: float = 0.005
    max_price: float = 0.60
    # Length of a correlation window in days. Markets in the same category whose
    # deadlines fall in the same window share a common shock.
    shock_window_days: int = 30
    # Multiplies every category's rho. 0 = independent outcomes.
    correlation_scale: float = 1.0


class MarketFactory:
    """Generates fake markets and decides how they resolve."""

    def __init__(self, cfg: MarketConfig, rng: random.Random):
        self.cfg = cfg
        self.rng = rng
        self._next_id = 0
        self._shocks: dict[tuple[str, int], float] = {}
        self._weights = [c.weight for c in CATEGORIES]

    def _shock(self, category: str, deadline_day: int) -> float:
        key = (category, deadline_day // self.cfg.shock_window_days)
        if key not in self._shocks:
            self._shocks[key] = self.rng.gauss(0.0, 1.0)
        return self._shocks[key]

    def _title(self, cat: Category, deadline_day: int) -> str:
        place, place2 = self.rng.sample(PLACES, 2)
        return self.rng.choice(cat.templates).format(
            place=place, place2=place2, leader=self.rng.choice(LEADERS),
            firm=self.rng.choice(FIRMS), coin=self.rng.choice(COINS),
            deadline=f"day {deadline_day}",
        )

    def _poisson(self, lam: float) -> int:
        # Knuth's method; fine for small lambdas.
        threshold, k, p = math.exp(-lam), 0, 1.0
        while True:
            p *= self.rng.random()
            if p <= threshold:
                return k
            k += 1

    def new_markets(self, day: int) -> list[Market]:
        cfg = self.cfg
        out = []
        for _ in range(self._poisson(cfg.markets_per_day)):
            cat = self.rng.choices(CATEGORIES, weights=self._weights)[0]
            duration = self.rng.randint(cfg.min_days, cfg.max_days)
            deadline = day + duration
            # Longer windows give more time for something to happen.
            base = self.rng.betavariate(cat.alpha, cat.beta)
            true_p = 1.0 - (1.0 - base) ** (duration / 60.0)
            quoted = true_p + cfg.hype_premium + self.rng.gauss(0.0, cfg.price_noise)
            yes_price = round(min(max(quoted, cfg.min_price), cfg.max_price), 3)

            rho = min(cat.rho * cfg.correlation_scale, 0.99)
            z = self._shock(cat.name, deadline)
            latent = math.sqrt(rho) * z + math.sqrt(1.0 - rho) * self.rng.gauss(0.0, 1.0)

            out.append(Market(
                id=self._next_id, title=self._title(cat, deadline), category=cat.name,
                listed_day=day, deadline_day=deadline, true_p=true_p,
                yes_price=yes_price, _latent=latent,
            ))
            self._next_id += 1
        return out

    def resolve(self, m: Market) -> None:
        """Decide the outcome. YES events happen at a random point before the deadline."""
        threshold = _STD_NORMAL.inv_cdf(min(max(m.true_p, 1e-9), 1 - 1e-9))
        m.resolved_yes = m._latent < threshold
        if m.resolved_yes:
            m.resolution_day = self.rng.randint(m.listed_day + 1, m.deadline_day)
        else:
            m.resolution_day = m.deadline_day
