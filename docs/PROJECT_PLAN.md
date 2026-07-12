# ApexMind Project Plan

**Version:** 0.1
**Date:** 12 July 2026
**Status:** Planning

## 1. Outcome

ApexMind v1 is an **offline counterfactual F1 strategy research system**. Given a replayed race state, it ranks a small, legal set of tactical options and explains the evidence, assumptions, uncertainty, and relevant regulation behind each option.

The first deliverable is a defensible research prototype, not a real-time team decision system.

### Research question

Can a probabilistic simulator built from public F1 signals produce better-calibrated and lower-regret strategy alternatives than fixed-strategy heuristics under changing traffic, weather, and Safety Car conditions?

## 2. Scope

### In scope for v1

- Offline replay of selected historical races
- Public timing, telemetry, weather, tyre, pit, position, and race-control data
- Tyre degradation, clean-air pace, traffic loss, pit loss, weather, and Safety Car models
- Monte Carlo scenario simulation and constrained strategy search
- FIA-rule checks for each candidate strategy
- Evidence-grounded natural-language explanation

### Explicitly out of scope for v1

- Live race advice or automated pit-wall operation
- CFD, a full vehicle digital twin, or real aerodynamic load prediction
- Claiming to observe battery state of charge, engine maps, tyre temperature, or active-aero state
- Reinforcement learning before the simulator is validated
- Broadcast-video computer vision as a required dependency
- Private team data or an implied affiliation with any team or partner

## 3. Evidence contract

| Class | Examples | Treatment |
|---|---|---|
| Observed | lap and sector time, tyre compound/age, pit stop, location, speed, weather, flags | Stored with source, session ID, and timestamp |
| Inferred | clean-air pace, latent tyre state, traffic penalty | Estimated with uncertainty intervals |
| Simulated | energy availability scenario, aero effect, rival reaction | Declared assumptions; never presented as observed fact |

The user interface and generated reports must preserve this distinction.

## 4. Initial architecture

```text
Public F1 data + versioned FIA regulations
                  |
           replay/state builder
                  |
    pace & tyre model  ---  event/traffic model
                  |                 |
            Monte Carlo race simulator
                  |
        constrained candidate-strategy search
                  |
  ranked actions + uncertainty + cited explanation
```

The LLM/SLM sits only in the last layer. It may summarise validated calculations and retrieve cited rules; it must not directly choose a strategy or invent numerical inputs.

## 5. Data policy

1. Begin with OpenF1 and FastF1; cache processed derivatives locally, not credentials.
2. Record the source, collection time, schema version, and session identifier for every dataset.
3. Keep raw and derived data out of Git. Commit only code, schemas, small fixtures, and documentation.
4. Re-check source terms before public release, live use, or any commercial use.
5. Maintain a versioned copy or hash of each FIA regulation excerpt used by the rule checker.

## 6. Modelling sequence

1. **Baselines:** fixed tyre-age threshold, historical average pace loss, and simple pit-loss rule.
2. **Probabilistic pace/tyre model:** Bayesian or state-space model with stint resets and weather/traffic covariates.
3. **Race simulator:** stochastic rival behaviour, Safety Car timing, pit loss, and weather scenarios.
4. **Optimiser:** constrained beam search or dynamic programming over legal candidate plans.
5. **Energy/aero scenario layer:** low, medium, and high availability assumptions. This is a sensitivity analysis layer, not a claim to infer real PU or aero state.
6. **Explanation layer:** retrieve FIA rule excerpts and emit structured, source-backed summaries of optimiser output.

## 7. Evaluation

No real team's historical strategy is treated as the global optimum.

| Area | Metric |
|---|---|
| Pace/tyre prediction | MAE/RMSE, CRPS, calibration curve, coverage of prediction intervals |
| Strategy | expected race-time delta and dynamic regret versus baselines in held-out simulations |
| Robustness | performance across dry, Safety Car, and changing-weather races; sensitivity analysis |
| Compliance | zero rule-violating candidate plans |
| Explanation | complete evidence links, correct rule version, and refusal when evidence is missing |

## 8. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Public data omits critical car state | use explicit scenario ranges and uncertainty; never imply secret telemetry |
| Pre-2026 patterns do not transfer to the 2026 era | use older data for generic race dynamics only; treat energy/aero as a separate scenario model until enough 2026 observations exist |
| Simulator produces unjustified counterfactual certainty | report conditional outputs, run stress tests, and preserve assumptions with every result |
| RL exploits simulator defects | defer RL; use transparent baselines and external validation first |
| LLM hallucinates rules or numbers | require retrieved evidence and schema-validated tool outputs; the optimiser remains authoritative |
| Scope grows through CV/CFD/live features | enforce the v1 non-goals and gated roadmap |
| Licence, brand, or data-use ambiguity | retain source attribution, publish only after terms review, and use an independence disclaimer |
| Sensitive credentials or private data leak | do not commit credentials; use environment variables or a secret manager; no private data in v1 |

## 9. Project gates

- **Gate A — data fidelity:** replay accurately reconstructs stint, pit, tyre, timing, and race-control state for three selected races.
- **Gate B — predictive validity:** the probabilistic pace/tyre model beats or matches simple baselines and its intervals are calibrated.
- **Gate C — simulation validity:** simulator produces plausible pit, traffic, and Safety Car behaviour under documented scenarios.
- **Gate D — strategy value:** constrained search improves expected outcome over baselines in hold-out simulations with confidence intervals.
- **Gate E — explanation safety:** every answer is evidence-backed or explicitly abstains.

Failure at Gate B or C triggers a pivot to an F1 Decision Forensics product rather than adding optimiser complexity.

## 10. Reference starting points

- [FIA 2026 F1 regulations archive](https://www.fia.com/regulation/category/110)
- [FIA: 2026 new era overview](https://www.fia.com/news/f1s-new-era-everything-you-need-know-about-how-fia-making-formula-1-more-competitive-more)
- [OpenF1 API](https://openf1.org/)
- [FastF1](https://github.com/theOehrly/Fast-F1)
- [Cappello & Hoegh (2026): state-space tyre degradation](https://journals.sagepub.com/doi/full/10.1177/22150218261446170)
- [Thomas et al. (2026): race strategy reinforcement learning](https://link.springer.com/article/10.1007/s10994-026-07081-3)
- [Aston Martin Aramco and Cohere announcement](https://www.astonmartinf1.com/en-GB/news/announcement/cohere-joins-aston-martin-aramco-as-official-generative-ai-partner)
