# Nothing Ever Happens bot (paper trading)

A Polymarket-style bot that bets **NO** on dramatic events ("Will X invade Y?",
"Will the PM resign?", "Will BTC halve?"), on the idea that the crowd overpays for drama.

All markets are **fake**. The countries, leaders and companies are made up. No money
moves and nothing talks to Polymarket. The point is to see how the strategy *might*
do before you risk anything.

Python 3.10+, standard library only.

## Run it

```bash
# One simulated year: summary, equity curve, every losing bet
python3 -m nothing_ever_happens run --seed 1

# Save every bet to a spreadsheet
python3 -m nothing_ever_happens run --seed 1 --csv bets.csv

# 300 simulated years, comparing how mispriced the crowd is
python3 -m nothing_ever_happens montecarlo --scenarios=-0.01,0,0.01,0.02,0.04

# Tests
python3 -m unittest discover -s nothing_ever_happens/tests -t .
```

Run `python3 -m nothing_ever_happens run --help` for every option.

## How the fake world works

- About 4 new markets are listed each day, in five categories: geopolitics, politics,
  legal, markets and weird. Each one lasts 7 to 120 days.
- Each market has a hidden **true probability** of YES and a **quoted price**.
  The price is the true probability plus `--hype` (the crowd's average overpricing)
  plus some noise. **`--hype` decides whether the strategy works at all.**
- Bad news comes in clusters. Markets in the same category with deadlines in the same
  30-day window share a common shock, so one war makes other war markets more likely
  to hit (`--correlation`, 0 = independent). Each market still resolves YES exactly
  as often as its true probability says (this is tested).
- If YES happens, it happens on a random day before the deadline. Otherwise the market
  resolves NO at the deadline, and your money is tied up until then.

## What the bot does

For each new market it buys NO if:
- the YES price is between `--min-yes` (3%) and `--max-yes` (20%),
- the deadline is within `--max-days` (90) days,
- and the category is allowed (`--categories`, all by default).

Each bet is `--bet` (2%) of current equity. No more than 25% of equity can sit in
one category, and no more than 80% in total. It pays `--spread` (1 cent) above the
quoted NO price plus `--fee`, and holds every bet until the market resolves.

The bot never sees the true probability. It only sees what you would see.

## Results with the defaults (200 simulated years each)

| Crowd overprices YES by | Median year | Bad year (5th pct) | Chance of losing money |
|---|---|---|---|
| −1¢ (crowd underprices drama) | −10% | −27% | 85% |
| 0¢ (crowd is right)           | −6%  | −22% | 73% |
| +1¢                           | 0%   | −17% | 51% |
| +2¢                           | +5%  | −11% | 28% |
| +4¢                           | +18% | +3%  | 4% |

What this shows:
- **You win about 96% of bets and still lose money if the crowd is priced fairly.**
  A win pays about 12¢ on 88¢. One loss wipes out about 7 wins, and the spread
  quietly costs you on every bet.
- **Break-even is about 1¢ of overpricing**, just enough to pay the 1¢ spread. Whether
  real Polymarket drama markets are overpriced by more than that is the whole question,
  and a simulation can't answer it.
- **Clustering and bet size mostly make the bad years worse.** Doubling correlation or
  raising bets to 5–10% barely moves the median, but the worst drawdowns go from
  about 24% to 30–50%.
- **One lucky run proves nothing.** `--seed 1` makes +25%, but the median for the
  same settings is +5%.

## Limitations

- Open bets are valued at what you paid until they resolve, so the drawdown figures
  understate the swings you'd watch live.
- The bot only looks at a market when it is listed. It never re-enters, sells early or
  hedges.
- Real markets have order books, liquidity limits, resolution disputes and fat tails
  that this model doesn't capture.

The natural next step is pointing the same strategy at real Polymarket data, either
by paper trading live markets or backtesting resolved ones, to measure the real hype premium.
