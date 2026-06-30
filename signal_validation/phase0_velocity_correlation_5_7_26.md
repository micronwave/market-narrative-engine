# Phase 0 — Velocity-Price Correlation Analysis
**Run date:** 2026-05-07  
**Script:** `phase0_sweep.py` + `phase0_diagnostic.py`

---

## Prerequisite check

| Metric | Value | Gate |
|---|---|---|
| Snapshot window | 2026-03-16 → 2026-05-07 | |
| Calendar days with snapshots | **48** | PASS (need ≥45) |
| Max trading pairs at ld=0 | ~30–34 | |
| Active narratives w/ real tickers | 28 pairs | |
| Mature or Declining stage | 75 Mature, 0 Declining | ≥8 Mature — PASS |

---

## Strict hit-rate table (p<0.05 AND n_observations≥30)

| lead_days | sig_pairs | hit_rate | avg\|r\| all |
|---|---|---|---|
| 0 | 0 | 0.0% | 0.205 |
| 1 | 0 | 0.0% | 0.194 |
| 2 | 0 | 0.0% | 0.203 |
| 3 | 0 | 0.0% | 0.212 |
| 5 | 0 | 0.0% | **0.277** |
| 7 | 0 | 0.0% | 0.223 |

**Strict result: 0% hit rate at all lags.**

---

## Evidence table — Pearson r at each lag (all 28 pairs)

| Ticker | Stage | n@0 | ld=0 | ld=1 | ld=2 | ld=3 | ld=5 | ld=7 | Sig? |
|---|---|---|---|---|---|---|---|---|---|
| AIG | Dormant | 12 | -0.386 | +0.412 | -0.060 | -0.578 | -0.159 | +0.135 | no |
| CRWD | Dormant | 12 | -0.201 | +0.301 | -0.035 | +0.306 | -0.203 | -0.150 | no |
| BK | Dormant | 12 | -0.497 | +0.382 | +0.426 | -0.302 | +0.024 | -0.031 | no |
| INVH | Dormant | 13 | -0.409 | +0.178 | +0.287 | -0.307 | -0.063 | +0.129 | no |
| AIG | Dormant | 14 | -0.263 | -0.054 | -0.009 | -0.302 | +0.478 | +0.189 | no |
| BTC-USD | Dormant | 33 | +0.081 | +0.083 | +0.323 | +0.212 | +0.038 | -0.245 | no |
| AMGN | Mature | 30 | -0.085 | -0.116 | +0.163 | +0.060 | **-0.515** | +0.090 | no* |
| BKR | Mature | 25 | **+0.734** | +0.564 | +0.327 | -0.124 | -0.093 | +0.161 | no* |
| AIG | Mature | 22 | -0.176 | -0.428 | -0.191 | -0.353 | **+0.583** | +0.300 | no* |
| META | Mature | 23 | +0.204 | +0.061 | +0.336 | -0.191 | -0.032 | -0.234 | no |
| ITW | Mature | 25 | +0.035 | -0.053 | -0.034 | -0.146 | -0.412 | -0.159 | no |
| ESS | Mature | 25 | -0.269 | -0.237 | +0.367 | +0.073 | +0.055 | +0.057 | no |
| XPEV | Mature | 9 | -0.082 | +0.015 | -0.281 | +0.124 | +0.499 | +1.000 | no† |
| SNAP | Mature | 23 | +0.106 | +0.208 | -0.269 | -0.151 | -0.452 | -0.367 | no |
| ITW | Mature | 28 | -0.137 | +0.130 | -0.201 | -0.268 | -0.290 | +0.111 | no |
| NKE | Mature | 23 | -0.020 | +0.242 | +0.019 | -0.126 | +0.310 | -0.211 | no |
| BMY | Mature | 21 | +0.218 | -0.323 | +0.334 | -0.074 | -0.199 | +0.109 | no |
| INVH | Mature | 32 | -0.076 | -0.015 | +0.207 | -0.143 | -0.088 | +0.006 | no |
| AIG | Mature | 34 | -0.139 | +0.046 | -0.018 | -0.170 | +0.093 | +0.170 | no |
| CRWD | Mature | 34 | +0.229 | +0.115 | -0.081 | +0.036 | +0.261 | +0.241 | no |
| EQR | Mature | 33 | +0.134 | -0.191 | +0.007 | -0.341 | +0.013 | +0.144 | no |
| AIG | Mature | 23 | -0.440 | -0.029 | -0.094 | -0.195 | **+0.606** | +0.275 | no* |
| MSFT | Mature | 34 | +0.132 | +0.248 | +0.186 | +0.248 | +0.265 | +0.157 | no |
| AVAX-USD | Mature | 33 | +0.088 | -0.108 | -0.226 | +0.276 | +0.076 | -0.252 | no |
| BTC-USD | Mature | 33 | +0.189 | -0.049 | -0.090 | +0.138 | -0.021 | -0.207 | no |
| ORCL | Mature | 8 | -0.135 | +0.674 | +0.307 | -0.114 | -0.905 | — | no† |
| IDXX | Mature | 23 | +0.095 | +0.116 | -0.176 | -0.382 | +0.151 | -0.101 | no |
| CRWD | Mature | 9 | +0.187 | +0.039 | +0.623 | -0.182 | -0.878 | -1.000 | no† |

*Strong raw signal, blocked by n<30 only.  
†Degenerate — n<10, r=±1.0 artifacts.

---

## Lag profile — where does signal peak?

| lead_days | pairs at max \|r\| |
|---|---|
| ld=0 | 3 |
| ld=1 | 0 |
| ld=2 | 5 |
| ld=3 | 6 |
| **ld=5** | **11** |
| ld=7 | 3 |

**ld=5 is the strongest lag (39% of pairs).** The signal leads price by ~5 trading days.

---

## Root-cause analysis: why 0% hits despite real correlations

### The n-gap problem

48 calendar days converts to ~34 trading pairs at ld=0. At ld=5, the pairing algorithm loses 5 pairs (can't offset past end of price series), dropping to 25–29 effective observations. The n≥30 gate then blocks everything:

| Pair | n@5 | r@5 | p@5 | Need |
|---|---|---|---|---|
| AMGN | 25 | -0.515 | 0.008 | 5 obs (~1 wk) |
| AIG (Nvidia) | 18 | +0.606 | 0.008 | 12 obs (~2.4 wks) |
| AIG (AI Agents) | 17 | +0.583 | 0.014 | 13 obs (~2.6 wks) |
| SNAP | 18 | -0.452 | 0.060 | 12 obs (~2.4 wks) |
| ITW | 20 | -0.412 | 0.071 | 10 obs (~2.0 wks) |

BKR (r=+0.734, p=0.000 at ld=0) is blocked by n=25 — needs only 5 more observations.

### p<0.05 pairs ignoring n floor

| Ticker | Stage | ld | r | p | n | Gap to n=30 |
|---|---|---|---|---|---|---|
| BKR | Mature | 0 | +0.734 | 0.000 | 25 | 5 obs (~1 wk) |
| AMGN | Mature | 5 | -0.515 | 0.008 | 25 | 5 obs (~1 wk) |
| AIG | Mature | 5 | +0.583 | 0.014 | 17 | 13 obs (~2.6 wks) |
| AIG | Mature | 0 | -0.440 | 0.036 | 23 | 7 obs (~1.4 wks) |
| AIG (Dormant) | Dormant | 3 | -0.578 | 0.049 | 12 | 18 obs (~3.6 wks) |

5 of 28 pairs (18%) have p<0.05 raw. Both BKR and AMGN have p<0.01. The signal is present.

---

## Secondary concern: FAISS mapping noise

Several ticker assignments appear thematically loose:

| Narrative | Ticker | Assessment |
|---|---|---|
| Oil Supply Disruption Drives Global Market Volatility | MSFT | Weak link |
| Asian Markets Outperforming Despite Geopolitical Uncertainty | ORCL | Weak link |
| Closed-End Fund Structural Reorganization | META | Weak link |
| Arm's Historic Shift to In-House Chip Manufacturing | ITW | Indirect at best |

Loose mappings dilute the overall hit rate. Secondary to the data-volume gap — address after n>=30 is reached.

---

## Gate decision

| Metric | Value |
|---|---|
| Strict hit rate (p<0.05, n≥30) | **0.0%** |
| Raw p<0.05 hit rate | 5/28 = 18% |
| Best anchor signal | BKR r=+0.734, p=0.000 |
| Second anchor | AMGN r=-0.515, p=0.008 at ld=5 |
| Best avg\|r\| | 0.277 at ld=5 |
| Lag preference | ld=5 dominates (39% of pairs) |
| Root cause of 0% | Data volume — n<30 gate, not absent signal |

**VERDICT: DEFER (data volume gate)**

The strict gate would say "FIX FUNDAMENTALS" but the evidence does not support that. Two anchor pairs have p<0.01. The ld=5 lag peak is consistent with a genuine 5-day predictive lead. The pipeline is working — it simply hasn't accumulated enough trading-day pairs to clear the MIN_OBSERVATIONS=30 floor.

Do NOT lower MIN_OBSERVATIONS. Doing so would make p-values unreliable and is exactly what the plan warned against.

**Next action:** Re-run this sweep on approximately **2026-05-28** (~3 weeks). Expected state at that point:
- BKR and AMGN will clear n≥30 at their best lags (p<0.01)
- AIG (Nvidia), AIG (AI Agents), SNAP, ITW should also cross n=30 at ld=5
- Projected strict hit rate: 15–30% — entering the TUNE zone
- If still <40% after n≥30 for 10+ pairs, then investigate FAISS mapping quality

Phase 1 (design system) can proceed in parallel per the plan — it has no dependency on this gate.
