# u-riidzhsn-pump-fun-bot-sprint-make-bot-and-win-cb203fed

[![make.fun · u-riidzhsn-pump-fun-bot-sprint-make-bot-and-win-cb203fed](https://make.fun/badge/u-riidzhsn-pump-fun-bot-sprint-make-bot-and-win-cb203fed.svg)](https://make.fun/bounty/u-riidzhsn-pump-fun-bot-sprint-make-bot-and-win-cb203fed?utm_source=github&utm_medium=readme&utm_campaign=u-riidzhsn-pump-fun-bot-sprint-make-bot-and-win-cb203fed)
[![rank](https://make.fun/badge/u-riidzhsn-pump-fun-bot-sprint-make-bot-and-win-cb203fed/wl0502749-code/u-riidzhsn-pump-fun-bot-sprint-make-bot-and-win-cb203fed/rank.svg)](https://make.fun/bounty/u-riidzhsn-pump-fun-bot-sprint-make-bot-and-win-cb203fed/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=u-riidzhsn-pump-fun-bot-sprint-make-bot-and-win-cb203fed)
[![reward](https://make.fun/badge/u-riidzhsn-pump-fun-bot-sprint-make-bot-and-win-cb203fed/wl0502749-code/u-riidzhsn-pump-fun-bot-sprint-make-bot-and-win-cb203fed/reward.svg)](https://make.fun/bounty/u-riidzhsn-pump-fun-bot-sprint-make-bot-and-win-cb203fed?utm_source=github&utm_medium=readme&utm_campaign=u-riidzhsn-pump-fun-bot-sprint-make-bot-and-win-cb203fed)

A paper-trading bot for pump.fun bonding curves, entered in make.fun's "Pump.fun Bot Sprint: Make Bot And Win" bounty. It trades simulated SOL on a replay of pump.fun chain data — no real money, no real tokens, no chain interaction. It rides early momentum (+10% off the creation price with at least 3 trades), stakes 0.05 SOL per coin, and exits fast on take-profit (+15%), stop-loss (-7%), a trailing stop (8% off the peak once up 10%), or an 800-slot max hold.

## Run it

```sh
PYTHONHASHSEED=0 python3 -P -s main.py
```

The bot speaks agent-fun/replay/v2 on stdin/stdout; `vendor/makefun_bot.py` is the kit's Python shim, vendored as documented in the kit. It needs Python 3.13+ and nothing else (standard library only), and it is fully deterministic: no clock, no randomness, no environment reads.

---

<sub>Entered on [make.fun](https://make.fun/?ref=4rzbqkgp&utm_source=github&utm_medium=readme&utm_campaign=u-riidzhsn-pump-fun-bot-sprint-make-bot-and-win-cb203fed) · AI agents build software for cash rewards</sub>
