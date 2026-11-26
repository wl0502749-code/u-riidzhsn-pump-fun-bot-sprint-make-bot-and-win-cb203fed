"""Momentum paper-trading bot for the pump.fun replay (agent-fun/replay/v2).

Paper money only: this bot never touches real SOL, real tokens or any chain.
It reads the replay's bonding-curve events and trades a simulated 10 SOL
bankroll against them. The grader runs it as ``python3 -P -s /bot/main.py``
with ``PYTHONHASHSEED=0``; the bot is fully deterministic (no clock, no
randomness, no environment reads, insertion-ordered iteration only).

Strategy -- ride early momentum, cut losers fast, let winners run:
  * Watch every new coin from its CreateEvent and remember its creation
    price (virtual quote / virtual token reserves).
  * Buy once a coin has proven demand: price up >= 10% from creation with
    at least 3 trades, and the size cap allows a >= 0.01 SOL order. One
    buy per coin, 0.05 SOL stake (or the cap, if smaller).
  * Drop a candidate if its price fades back below creation, if its curve
    completes, or after 40 trades without triggering.
  * Exit a holding on whichever comes first:
      - take profit at +15% over the entry price,
      - stop loss at -7% under the entry price,
      - trailing stop: once the peak is >= +10%, sell on an 8% pullback
        from the peak,
      - max hold of 800 slots (~5 min) to free the slot for fresh coins.
  * At most 5 open positions (the harness cap); orders respect the
    per-batch order cap and the free-cash check.

Prices are compared with integer cross-multiplication on the raw reserve
pairs, so no floating point ever enters a decision.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor"))

import makefun_bot  # noqa: E402  (after the sys.path line: -P leaves the script directory off sys.path)

STAKE_LAMPORTS = makefun_bot.LAMPORTS_PER_SOL // 20  # 0.05 SOL per coin
MIN_BUY_LAMPORTS = makefun_bot.LAMPORTS_PER_SOL // 100  # 0.01 SOL, the round-trip bar
MAX_SLIPPAGE_BPS = 1000  # 10%: wide enough for fast memecoin moves, not wide open

MOMENTUM_TRADES = 3        # trades seen before a coin can trigger
MOMENTUM_NUM = 11          # buy when price >= creation * 11/10 (+10%)
MOMENTUM_DEN = 10
FADE_NUM = 49              # drop a candidate below creation * 49/50 (-2%)
FADE_DEN = 50
MAX_CANDIDATE_TRADES = 40  # momentum window: give up after this many trades

TAKE_PROFIT_NUM = 23       # sell at entry * 23/20 (+15%)
TAKE_PROFIT_DEN = 20
STOP_LOSS_NUM = 93         # sell at entry * 93/100 (-7%)
STOP_LOSS_DEN = 100
TRAIL_PEAK_NUM = 11        # trailing stop arms once peak >= entry * 11/10 (+10%)
TRAIL_PEAK_DEN = 10
TRAIL_DROP_NUM = 23        # ... then sell on an 8% pullback from the peak
TRAIL_DROP_DEN = 25
MAX_HOLD_SLOTS = 800       # ~5 min: sell whatever is left, free the slot


def _price(curve):
    """(virtual_quote, virtual_token) pair; price = quote / token."""
    return (curve.virtual_quote_reserves, curve.virtual_token_reserves)


def _above(price, ref, num, den):
    """True when price >= ref * num / den, in exact integer math."""
    return price[0] * ref[1] * den >= ref[0] * price[1] * num


def _below(price, ref, num, den):
    """True when price <= ref * num / den, in exact integer math."""
    return price[0] * ref[1] * den <= ref[0] * price[1] * num


# mint -> (creation quote, creation token) at the CreateEvent batch.
creation_price = {}
# mint -> number of TradeEvents seen since creation.
candidate_trades = {}
# mint -> {"entry": (q, t), "peak": (q, t), "slot": entry slot} for open buys.
open_trades = {}


def on_batch(state, batch):
    caps = state.hello["caps"]
    tx = state.tx_fee_lamports()
    free = state.free_cash_lamports()
    slots = caps["max_open_positions"] - state.committed_position_count()
    orders = []

    # Mints with a sell already in flight: never double-sell them.
    selling = set()
    for pending in state.pending.values():
        if pending.order["side"] == "sell":
            selling.add(pending.order["mint"])

    # --- exits first: free slots (and cash) before looking for new buys.
    for mint in list(state.positions):
        if mint in selling:
            continue
        holding = state.positions[mint]
        info = open_trades.get(mint)
        curve = state.curves.get(mint)
        if curve is None or curve.complete:
            continue
        price = _price(curve)
        if info is None:
            # A holding we did not open (e.g. a harness close in flight):
            # track it from here at the current price so exits still work.
            info = {"entry": price, "peak": price, "slot": state.slot}
            open_trades[mint] = info
        if _above(price, info["peak"], 1, 1):
            info["peak"] = price
        entry = info["entry"]
        peak = info["peak"]
        sell = False
        if _above(price, entry, TAKE_PROFIT_NUM, TAKE_PROFIT_DEN):
            sell = True  # take profit +80%
        elif _below(price, entry, STOP_LOSS_NUM, STOP_LOSS_DEN):
            sell = True  # stop loss -30%
        elif _above(peak, entry, TRAIL_PEAK_NUM, TRAIL_PEAK_DEN) and _below(
            price, peak, TRAIL_DROP_NUM, TRAIL_DROP_DEN
        ):
            sell = True  # trailing stop: 25% off the peak
        elif state.slot - info["slot"] >= MAX_HOLD_SLOTS:
            sell = True  # max hold: free the slot
        if sell:
            if len(orders) >= caps["max_orders_per_batch"]:
                continue
            orders.append(
                {
                    "side": "sell",
                    "mint": mint,
                    "token_amount": holding.token_amount,
                    "max_slippage_bps": MAX_SLIPPAGE_BPS,
                }
            )
            open_trades.pop(mint, None)
            # No slots increment here: the slot frees only when the sell
            # fills (a later batch); counting it now could over-commit.

    # --- entries: one buy per coin, in batch event order.
    for e in batch["events"]:
        mint = e["mint"]
        if e["event"] == "CreateEvent":
            curve = state.curves.get(mint)
            if curve is not None:
                creation_price[mint] = _price(curve)
                candidate_trades[mint] = 0
            continue
        if e["event"] == "TradeEvent" and mint in candidate_trades:
            candidate_trades[mint] += 1
        if mint not in creation_price:
            continue
        if mint in state.positions or mint in open_trades:
            creation_price.pop(mint, None)
            candidate_trades.pop(mint, None)
            continue
        curve = state.curves.get(mint)
        if curve is None or curve.complete:
            creation_price.pop(mint, None)
            candidate_trades.pop(mint, None)
            continue
        price = _price(curve)
        created = creation_price[mint]
        if _below(price, created, FADE_NUM, FADE_DEN):
            creation_price.pop(mint, None)  # momentum faded
            candidate_trades.pop(mint, None)
            continue
        if candidate_trades.get(mint, 0) > MAX_CANDIDATE_TRADES:
            creation_price.pop(mint, None)  # window passed without triggering
            candidate_trades.pop(mint, None)
            continue
        if candidate_trades.get(mint, 0) < MOMENTUM_TRADES:
            continue
        if not _above(price, created, MOMENTUM_NUM, MOMENTUM_DEN):
            continue
        cap = state.max_buy_lamports(mint)
        if cap < MIN_BUY_LAMPORTS:
            continue
        amount = cap if cap < STAKE_LAMPORTS else STAKE_LAMPORTS
        if len(orders) >= caps["max_orders_per_batch"] or slots <= 0:
            continue
        if free < amount + tx:
            continue
        orders.append(
            {
                "side": "buy",
                "mint": mint,
                "quote_lamports": amount,
                "max_slippage_bps": MAX_SLIPPAGE_BPS,
            }
        )
        open_trades[mint] = {"entry": price, "peak": price, "slot": state.slot}
        creation_price.pop(mint, None)
        candidate_trades.pop(mint, None)
        free -= amount + tx
        slots -= 1

    # Forget candidates whose curve completed without us noticing.
    for mint in list(creation_price):
        curve = state.curves.get(mint)
        if curve is not None and curve.complete:
            creation_price.pop(mint, None)
            candidate_trades.pop(mint, None)

    return orders


if __name__ == "__main__":
    makefun_bot.run(on_batch)
