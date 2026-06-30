# Signal Validation Snapshot — 5/15/26
**Run date:** 2026-05-15  
**Script:** `signal_validation.generate` + `signal_validation.component_lead_correlation`

---

## Coverage

| Metric | Value |
|---|---|
| Active pairs (generate, top 8 by snap_days) | 8 |
| Active pairs (component test, min_snaps=30) | 19 scanned / 19 evaluated |
| Max n observations | 40 (AIG, MSFT, EQR, INVH) |
| Metrics evaluated | 16 |

---

## Component Lead Correlation Ranking (Test 1) — FAIL

Ranked by median |r_lead| at ld=1 across all qualifying pairs (min 30 snapshots).

| Rank | Component | Median r_lead | Median abs r_lead | % pairs \|r\|>0.2 | n pairs |
|---|---|---:|---:|---:|---:|
| 1 | Polarization | -0.033 | **0.149** | 26.3% | 19 |
| 2 | Source Authority | -0.138 | **0.138** | 33.3% | 18 |
| 3 | Velocity | -0.031 | 0.133 | 42.1% | 19 |
| 4 | Cohesion | -0.054 | 0.118 | 31.6% | 19 |
| 5 | Entropy | +0.032 | 0.061 | 22.2% | 18 |
| 6 | Intent Weight | -0.014 | 0.052 | 27.8% | 18 |
| 7 | Centrality | -0.001 | 0.050 | 16.7% | 18 |

**Gate: FAIL** — 0 components with median |r_lead| > 0.15 (need ≥ 2).  
Polarization (0.149) and Source Authority (0.138) are close but don't clear the bar.

---

## All 16 Metrics — r_same and r_lead by Pair

### Summary table (highest-signal entries only)

**Strong same-day (r_same) — contemporaneous, not predictive:**

| Metric | Narrative | Ticker | r_same | r_lead | Signal |
|---|---|---|---:|---:|---|
| Sentiment Mean | Housing Market (Bifurcation) | INVH | -0.952 | +0.075 | WEAK |
| Sentiment Mean | Housing Market (Bifurcation) | EQR | -0.938 | +0.086 | WEAK |
| Sentiment Variance | Housing Market (Bifurcation) | INVH | -0.934 | +0.127 | WEAK |
| Sentiment Variance | Housing Market (Bifurcation) | EQR | -0.917 | +0.134 | WEAK |
| Doc Count | Insider Share Sales | ESS | +0.940 | -0.122 | WEAK |
| Doc Count | Housing Market (Bifurcation) | INVH | +0.947 | +0.009 | WEAK |
| Doc Count | Housing Market (Bifurcation) | EQR | +0.933 | +0.059 | WEAK |
| Sentiment Mean | Insider Share Sales (Sentiment) | ESS | +0.852 | -0.066 | WEAK |
| Burst Ratio | AI Tech / Risk Management | AIG | +0.678 | -0.146 | WEAK |
| Entropy | Housing Market (Bifurcation) | EQR | -0.758 | +0.007 | WEAK |
| Entropy | Housing Market (Bifurcation) | INVH | -0.730 | +0.065 | WEAK |

The housing narratives have extremely high r_same for sentiment and doc_count — but r_lead near zero. These track concurrent market conditions, not lead them.

**INVERSE lead signals (r_lead < -0.3) — ITW cluster:**

| Metric | Narrative | Ticker | n | r_same | r_lead |
|---|---|---|---:|---:|---:|
| Weighted Source Score | Insider Share Sales | ITW | 15 | +0.112 | **-0.685** |
| Weighted Source Score | Arm's Chip Shift | ITW | 15 | +0.065 | **-0.647** |
| Sentiment Variance | Insider Share Sales | ITW | 31 | -0.172 | **-0.522** |
| Sentiment Mean | Insider Share Sales | ITW | 31 | -0.505 | **-0.470** |
| Source Count | Insider Share Sales | ITW | 31 | -0.183 | **-0.450** |
| Intent Weight | Insider Share Sales | ITW | 31 | +0.126 | **-0.415** |
| Cross-Source | Arm's Chip Shift | ITW | 34 | +0.149 | **-0.375** |
| Cross-Source | Insider Share Sales | ITW | 31 | +0.294 | **-0.357** |
| Polarization | Insider Share Sales | ITW | 31 | -0.073 | **-0.355** |

**Pattern:** ITW is consistently the strongest (inverted) lead target. However, ITW is a loose mapping — both "Insider Share Sales" and "Arm's Chip Shift" map to ITW (an industrial tooling company), which is thematically disconnected. These INVERSE reads may be spurious from mapping noise rather than a real inverse signal.

---

## Full Metric Tables (all 8 pairs)

### Velocity
| Narrative | Ticker | n | r_same | r_lead | Signal |
|---|---|---:|---:|---:|---|
| AI Tech / Risk Mgmt | AIG | 40 | +0.398 | +0.046 | WEAK |
| Oil Supply Disruption | MSFT | 40 | +0.026 | +0.203 | WEAK |
| Housing Bifurcation | EQR | 39 | +0.136 | -0.133 | WEAK |
| Housing Bifurcation | INVH | 39 | +0.116 | -0.050 | WEAK |
| Obesity/ADHD Competition | AMGN | 36 | +0.377 | -0.108 | WEAK |
| Arm's Chip Shift | ITW | 34 | -0.133 | +0.093 | WEAK |
| Insider Share Sales | ITW | 31 | +0.455 | -0.048 | WEAK |
| Insider Share Sales | ESS | 31 | +0.145 | -0.204 | WEAK |

### NS Score
| Narrative | Ticker | n | r_same | r_lead | Signal |
|---|---|---:|---:|---:|---|
| AI Tech / Risk Mgmt | AIG | 40 | -0.116 | -0.154 | WEAK |
| Oil Supply Disruption | MSFT | 40 | -0.269 | -0.262 | WEAK |
| Housing Bifurcation | EQR | 39 | +0.381 | -0.109 | WEAK |
| Housing Bifurcation | INVH | 39 | +0.387 | -0.131 | WEAK |
| Obesity/ADHD Competition | AMGN | 36 | +0.376 | -0.141 | WEAK |
| Arm's Chip Shift | ITW | 34 | +0.474 | -0.120 | WEAK |
| Insider Share Sales | ITW | 31 | +0.340 | -0.216 | WEAK |
| Insider Share Sales | ESS | 31 | +0.295 | -0.152 | WEAK |

### Burst Ratio
| Narrative | Ticker | n | r_same | r_lead | Signal |
|---|---|---:|---:|---:|---|
| AI Tech / Risk Mgmt | AIG | 35 | +0.678 | -0.146 | WEAK |
| Oil Supply Disruption | MSFT | 35 | +0.261 | +0.153 | WEAK |
| Housing Bifurcation | EQR | 35 | -0.069 | -0.132 | WEAK |
| Housing Bifurcation | INVH | 35 | -0.079 | -0.058 | WEAK |
| Obesity/ADHD Competition | AMGN | 35 | +0.304 | +0.120 | WEAK |
| Arm's Chip Shift | ITW | 34 | +0.175 | -0.137 | WEAK |
| Insider Share Sales | ITW | 31 | +0.189 | +0.155 | WEAK |
| Insider Share Sales | ESS | 31 | -0.008 | +0.012 | WEAK |

### Cohesion
| Narrative | Ticker | n | r_same | r_lead | Signal |
|---|---|---:|---:|---:|---|
| AI Tech / Risk Mgmt | AIG | 40 | +0.213 | -0.020 | WEAK |
| Oil Supply Disruption | MSFT | 40 | +0.313 | -0.124 | WEAK |
| Housing Bifurcation | EQR | 39 | +0.230 | -0.114 | WEAK |
| Housing Bifurcation | INVH | 39 | +0.178 | -0.115 | WEAK |
| Obesity/ADHD Competition | AMGN | 36 | -0.298 | -0.110 | WEAK |
| Arm's Chip Shift | ITW | 34 | -0.132 | -0.285 | WEAK |
| Insider Share Sales | ITW | 31 | -0.129 | +0.220 | WEAK |
| Insider Share Sales | ESS | 31 | -0.615 | +0.203 | WEAK |

### Entropy
| Narrative | Ticker | n | r_same | r_lead | Signal |
|---|---|---:|---:|---:|---|
| AI Tech / Risk Mgmt | AIG | 39 | -0.245 | +0.203 | WEAK |
| Oil Supply Disruption | MSFT | 40 | -0.636 | -0.070 | WEAK |
| Housing Bifurcation | EQR | 39 | -0.758 | +0.007 | WEAK |
| Housing Bifurcation | INVH | 39 | -0.730 | +0.065 | WEAK |
| Obesity/ADHD Competition | AMGN | 36 | +0.762 | +0.030 | WEAK |
| Arm's Chip Shift | ITW | 34 | +0.512 | +0.017 | WEAK |
| Insider Share Sales | ITW | 31 | +0.458 | +0.108 | WEAK |
| Insider Share Sales | ESS | 31 | -0.770 | +0.035 | WEAK |

### Polarization
| Narrative | Ticker | n | r_same | r_lead | Signal |
|---|---|---:|---:|---:|---|
| AI Tech / Risk Mgmt | AIG | 40 | -0.130 | -0.223 | WEAK |
| Oil Supply Disruption | MSFT | 40 | -0.254 | -0.169 | WEAK |
| Housing Bifurcation | EQR | 39 | -0.367 | +0.149 | WEAK |
| Housing Bifurcation | INVH | 39 | -0.402 | +0.146 | WEAK |
| Obesity/ADHD Competition | AMGN | 36 | +0.220 | +0.044 | WEAK |
| Arm's Chip Shift | ITW | 34 | +0.190 | -0.190 | WEAK |
| Insider Share Sales | ITW | 31 | -0.073 | -0.355 | INVERSE |
| Insider Share Sales | ESS | 31 | +0.451 | -0.048 | WEAK |

### Sentiment Mean
| Narrative | Ticker | n | r_same | r_lead | Signal |
|---|---|---:|---:|---:|---|
| AI Tech / Risk Mgmt | AIG | 35 | -0.112 | +0.026 | WEAK |
| Oil Supply Disruption | MSFT | 35 | -0.625 | -0.040 | WEAK |
| Housing Bifurcation | EQR | 35 | -0.938 | +0.086 | WEAK |
| Housing Bifurcation | INVH | 35 | -0.952 | +0.075 | WEAK |
| Obesity/ADHD Competition | AMGN | 35 | +0.273 | -0.007 | WEAK |
| Arm's Chip Shift | ITW | 34 | +0.773 | +0.198 | WEAK |
| Insider Share Sales | ITW | 31 | -0.505 | -0.470 | INVERSE |
| Insider Share Sales | ESS | 31 | +0.852 | -0.066 | WEAK |

### Sentiment Variance
| Narrative | Ticker | n | r_same | r_lead | Signal |
|---|---|---:|---:|---:|---|
| AI Tech / Risk Mgmt | AIG | 35 | -0.258 | +0.079 | WEAK |
| Oil Supply Disruption | MSFT | 35 | -0.311 | -0.019 | WEAK |
| Housing Bifurcation | EQR | 35 | -0.917 | +0.134 | WEAK |
| Housing Bifurcation | INVH | 35 | -0.934 | +0.127 | WEAK |
| Obesity/ADHD Competition | AMGN | 35 | +0.697 | -0.109 | WEAK |
| Arm's Chip Shift | ITW | 34 | +0.491 | -0.091 | WEAK |
| Insider Share Sales | ITW | 31 | -0.172 | -0.522 | INVERSE |
| Insider Share Sales | ESS | 31 | +0.775 | -0.108 | WEAK |

### Document Count
| Narrative | Ticker | n | r_same | r_lead | Signal |
|---|---|---:|---:|---:|---|
| AI Tech / Risk Mgmt | AIG | 40 | +0.201 | +0.067 | WEAK |
| Oil Supply Disruption | MSFT | 40 | +0.655 | +0.206 | WEAK |
| Housing Bifurcation | EQR | 39 | +0.933 | +0.059 | WEAK |
| Housing Bifurcation | INVH | 39 | +0.947 | +0.009 | WEAK |
| Obesity/ADHD Competition | AMGN | 36 | -0.679 | -0.079 | WEAK |
| Arm's Chip Shift | ITW | 34 | -0.689 | -0.146 | WEAK |
| Insider Share Sales | ITW | 31 | -0.626 | -0.291 | WEAK |
| Insider Share Sales | ESS | 31 | +0.940 | -0.122 | WEAK |

### Source Count
| Narrative | Ticker | n | r_same | r_lead | Signal |
|---|---|---:|---:|---:|---|
| AI Tech / Risk Mgmt | AIG | 35 | -0.001 | +0.041 | WEAK |
| Oil Supply Disruption | MSFT | 35 | +0.319 | +0.000 | WEAK |
| Housing Bifurcation | EQR | 35 | +0.769 | -0.031 | WEAK |
| Housing Bifurcation | INVH | 35 | +0.793 | -0.072 | WEAK |
| Obesity/ADHD Competition | AMGN | 35 | -0.555 | -0.068 | WEAK |
| Arm's Chip Shift | ITW | 34 | -0.359 | -0.312 | INVERSE |
| Insider Share Sales | ITW | 31 | -0.183 | -0.450 | INVERSE |
| Insider Share Sales | ESS | 31 | +0.835 | -0.124 | WEAK |

### Intent Weight
| Narrative | Ticker | n | r_same | r_lead | Signal |
|---|---|---:|---:|---:|---|
| AI Tech / Risk Mgmt | AIG | 35 | +0.039 | -0.146 | WEAK |
| Oil Supply Disruption | MSFT | 35 | +0.149 | +0.047 | WEAK |
| Housing Bifurcation | EQR | 35 | +0.628 | +0.008 | WEAK |
| Housing Bifurcation | INVH | 35 | +0.637 | -0.054 | WEAK |
| Obesity/ADHD Competition | AMGN | 35 | N/A | N/A | NO DATA |
| Arm's Chip Shift | ITW | 34 | -0.666 | -0.111 | WEAK |
| Insider Share Sales | ITW | 31 | +0.126 | -0.415 | INVERSE |
| Insider Share Sales | ESS | 31 | +0.409 | -0.288 | WEAK |

### Cross-Source Score
| Narrative | Ticker | n | r_same | r_lead | Signal |
|---|---|---:|---:|---:|---|
| AI Tech / Risk Mgmt | AIG | 35 | +0.052 | -0.257 | WEAK |
| Oil Supply Disruption | MSFT | 35 | +0.013 | -0.120 | WEAK |
| Housing Bifurcation | EQR | 35 | +0.470 | -0.094 | WEAK |
| Housing Bifurcation | INVH | 35 | +0.546 | -0.138 | WEAK |
| Obesity/ADHD Competition | AMGN | 35 | -0.015 | -0.081 | WEAK |
| Arm's Chip Shift | ITW | 34 | +0.149 | -0.375 | INVERSE |
| Insider Share Sales | ITW | 31 | +0.294 | -0.357 | INVERSE |
| Insider Share Sales | ESS | 31 | +0.482 | -0.169 | WEAK |

### Weighted Source Score
| Narrative | Ticker | n | r_same | r_lead | Signal |
|---|---|---:|---:|---:|---|
| AI Tech / Risk Mgmt | AIG | 15 | -0.587 | +0.128 | WEAK |
| Oil Supply Disruption | MSFT | 15 | +0.316 | -0.114 | WEAK |
| Housing Bifurcation | EQR | 15 | -0.359 | +0.132 | WEAK |
| Housing Bifurcation | INVH | 15 | -0.272 | +0.066 | WEAK |
| Obesity/ADHD Competition | AMGN | 15 | +0.378 | -0.109 | WEAK |
| Arm's Chip Shift | ITW | 15 | +0.065 | -0.647 | INVERSE |
| Insider Share Sales | ITW | 15 | +0.112 | -0.685 | INVERSE |
| Insider Share Sales | ESS | 15 | +0.000 | +0.028 | WEAK |

Note: Weighted Source Score only has 15 observations — below the MIN_SNAPSHOTS=30 threshold; these results are indicative only.

### Centrality
| Narrative | Ticker | n | r_same | r_lead | Signal |
|---|---|---:|---:|---:|---|
| AI Tech / Risk Mgmt | AIG | 35 | -0.178 | +0.048 | WEAK |
| Oil Supply Disruption | MSFT | 35 | -0.511 | -0.002 | WEAK |
| Housing Bifurcation | EQR | 35 | +0.350 | +0.062 | WEAK |
| Housing Bifurcation | INVH | 35 | +0.378 | +0.033 | WEAK |
| Obesity/ADHD Competition | AMGN | 35 | +0.311 | -0.029 | WEAK |
| Arm's Chip Shift | ITW | 34 | +0.652 | +0.012 | WEAK |
| Insider Share Sales | ITW | 31 | +0.201 | -0.043 | WEAK |
| Insider Share Sales | ESS | 31 | +0.180 | -0.040 | WEAK |

### Windowed Velocity
| Narrative | Ticker | n | r_same | r_lead | Signal |
|---|---|---:|---:|---:|---|
| AI Tech / Risk Mgmt | AIG | 35 | +0.540 | -0.201 | WEAK |
| Oil Supply Disruption | MSFT | 35 | +0.090 | +0.085 | WEAK |
| Housing Bifurcation | EQR | 35 | +0.198 | -0.226 | WEAK |
| Housing Bifurcation | INVH | 35 | +0.199 | -0.054 | WEAK |
| Obesity/ADHD Competition | AMGN | 35 | +0.485 | -0.011 | WEAK |
| Arm's Chip Shift | ITW | 34 | -0.267 | -0.226 | WEAK |
| Insider Share Sales | ITW | 31 | +0.389 | -0.091 | WEAK |
| Insider Share Sales | ESS | 31 | +0.242 | -0.169 | WEAK |

### Public Interest
| Narrative | Ticker | n | r_same | r_lead | Signal |
|---|---|---:|---:|---:|---|
| AI Tech / Risk Mgmt | AIG | 35 | +0.195 | -0.117 | WEAK |
| Oil Supply Disruption | MSFT | 35 | -0.030 | +0.197 | WEAK |
| Housing Bifurcation | EQR | 35 | +0.045 | -0.104 | WEAK |
| Housing Bifurcation | INVH | 35 | +0.021 | +0.029 | WEAK |
| Obesity/ADHD Competition | AMGN | 35 | -0.115 | -0.010 | WEAK |
| Arm's Chip Shift | ITW | 34 | +0.175 | -0.251 | WEAK |
| Insider Share Sales | ITW | 31 | +0.131 | +0.005 | WEAK |
| Insider Share Sales | ESS | 31 | -0.020 | -0.091 | WEAK |

---

## Delta vs. 5/7 snapshot

| Dimension | 5/7 | 5/15 | Change |
|---|---|---|---|
| Max n (top pairs) | ~34 | 40 | +6 obs |
| Strict PROMISING signals (r_lead > 0.3) | 0 | 0 | — |
| INVERSE signals (r_lead < -0.3) | — | 9 (all ITW) | New — mapping noise likely |
| Best r_same anchor | BKR +0.734 | INVH doc_count +0.947 | Different pairs visible |
| Component test gate | N/A (not run) | FAIL (0/2) | — |
| Polarization median abs r_lead | — | 0.149 | Closest to gate |
| Source Authority median abs r_lead | — | 0.138 | #2 |

---

## Analysis

### Same-day vs. lead gap
The housing REITs (EQR, INVH) show extremely high contemporaneous correlation on sentiment and doc_count (r_same up to -0.952 / +0.947). This confirms the pipeline is capturing real narrative-market co-movement — but these signals don't carry forward even one day. They appear to be coincident, not leading.

### ITW INVERSE cluster
Nine INVERSE signals (r_lead < -0.3) cluster on ITW. Both narratives mapping there ("Insider Share Sales" and "Arm's Chip Shift") have thematically weak connections to ITW (an industrial tooling company). This is the same FAISS mapping noise flagged on 5/7. The INVERSE reads are almost certainly spurious. Priority: audit FAISS mapping before chasing these.

### n-volume still the binding constraint
At n=40 for top pairs, the 5-day lead test from 5/7 (which needed n≥30 at ld=5) would now pass for the top pairs. However, this generate run uses ld=1 (next-day), not ld=5. At ld=1, no signal clears 0.3. The 5/7 conclusion that ld=5 is the dominant lag remains relevant — this run does not re-test that hypothesis.

---

## Gate decision

| Metric | Value |
|---|---|
| Component test gate (need ≥2 at \|r_lead\|>0.15) | **FAIL (0/2)** |
| Closest components | Polarization 0.149, Source Authority 0.138 |
| PROMISING signals at ld=1 | **0** |
| INVERSE signals | 9 (ITW mapping noise) |
| Best contemporaneous signal | INVH doc_count r_same=+0.947 |

**VERDICT: DEFER** — same conclusion as 5/7. Data volume is not the blocker at ld=1; the signal at ld=1 is genuinely weak. The ld=5 lag identified on 5/7 was not re-tested here. Before next run, recommend:

1. Re-run the ld=5 sweep (phase0 script) with current n=40 — BKR and AMGN from 5/7 may now clear n≥30 at ld=5
2. Audit ITW ticker mappings — FAISS is assigning thematically disconnected narratives
3. Polarization and Source Authority are the components closest to the gate; watch these

**Next re-run: ~2026-05-28** (per original 5/7 plan — ~3 weeks from that run).
