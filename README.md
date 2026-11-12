<div align="center">

# NarrateSim

### Steering the Consensus: Narrative Attacks and Timed Defenses in LLM-Agent Social Networks

*Code, configurations and every run output for an anonymous WWW 2027 short-paper submission
(Social Networks and Social Media track).*

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white)](requirements.txt)
[![License: MIT](https://img.shields.io/badge/license-MIT-2E7D32?style=flat-square)](LICENSE)
[![Runs](https://img.shields.io/badge/released%20runs-69-6A4C93?style=flat-square)](results/)
[![Project page](https://img.shields.io/badge/project%20page-extended%20results-1F4E79?style=flat-square)](https://anonymous.4open.science/w/NarrateSim-014B/)
[![Studio](https://img.shields.io/badge/NarrateSim%20Studio-try%20it%20in%20the%20browser-D9A441?style=flat-square)](https://anonymous.4open.science/w/NarrateSim-014B/studio/)

[Overview](#overview) · [Framework](#framework) · [Results](#results) · [Studio](#narratesim-studio) · [Reproduce](#reproduce) · [Repository](#repository-layout) · [Project page](https://anonymous.4open.science/w/NarrateSim-014B/) · [中文](README_zh.md)

<a href="https://anonymous.4open.science/w/NarrateSim-014B/studio/"><img src="docs/assets/studio/lab.png" alt="NarrateSim Studio: a 120-agent society under a narrative operation, defended by a Guardian classifier" width="100%"></a>
<sub><b>NarrateSim Studio</b>, the experiment platform released with the paper: plant an operation, switch on a defense, and measure the effect against a counterfactual twin. <a href="https://anonymous.4open.science/w/NarrateSim-014B/studio/">Try it in the browser</a> · <a href="#narratesim-studio">more</a></sub>

</div>

---

## Overview

LLM agents now take part in the Web as participants: agent-only social platforms host millions of
agent-written posts, and multi-agent systems decide through open discussion. Such **agent societies**
inherit a weakness of human platforms: a few members with ordinary posting rights can steer the collective
by reframing the issue. We call these attempts **narrative attacks**.

**NarrateSim** is a testbed for studying this weakness in the agent society itself. LLM agents with
belief–desire–intention (BDI) reasoning discuss contested topics over a scale-free network while
strategy-constrained attacker agents post tailored narratives. Network, personas and initial stances are
fixed by seed, so every discussion can be **replayed with the attack removed or a defense switched on at a
chosen round**.

| | Question | Headline finding |
|---|---|---|
| **RQ1 · Attack** | Which framings, on which topics and from which network positions, shift the stance and emotional climate of an agent society? | Three attackers among 100 agents pull the final mean stance up to **2.3 points** below the attack-free run. Evidence- and credential-styled framings work only on topics with residual uncertainty, victim stories raise negative emotion on **every** topic, and hub placement adds about **23 points** of opposition share. |
| **RQ2 · Defense** | Which interventions contain an ongoing attack, and how does onset matter? | **Onset matters more than content.** Pre-bunking from Round 1 absorbs **77%** of the stance damage, but the same text started at Round 5 absorbs only **33%**. A metacognitive prompt **backfires**. |

<p align="center">
  <img src="figures/motivation.png" width="62%" alt="Agents exchange arguments over a network; attacker agents inject crafted framings"/>
</p>

> **Scope.** All results describe societies of LLM agents. We do not claim that the agents stand for any
> human population. Lessons for human platforms are hypotheses at most.

---

## Framework

<p align="center">
  <img src="figures/framework.png" width="96%" alt="NarrateSim framework overview"/>
</p>

- **Agents.** Each normal agent has five static persona dimensions in [1, 10] (institutional trust,
  care–fairness, loyalty–authority, just-world belief, analytical thinking), a stance
  s ∈ {−5,…,+5} and a confidence c ∈ {1,…,10}. It sees its neighbours' latest messages, keeps a 10-round
  memory and runs one BDI step per round: *belief* updates its view, *desire* decides what to express,
  and *intention* picks `speak`, `reply` or `silent`.
- **Network.** Barabási–Albert graph (default `m = 3`). Opinions spread by local visibility, not broadcast.
- **Narrative attackers.** Attackers use the same channel as everyone else. They exploit no vulnerability,
  inject no instructions and cannot edit others' posts. Each attacker follows one persuasion mechanism and
  is forbidden from using the others. Cadence, length and target direction are identical across conditions,
  so conditions differ in **framing alone**. Attackers are never counted in any metric.
- **Interventions.** These are either *dispositional* text written into each agent's own beliefs
  (pre-bunking, metacognitive reflection, fact-checking) or *platform notices* repeated every third round
  (community reporting, sentiment transparency).

| Strategy | Mechanism |
|---|---|
| Pseudo-Rational | Evidence-styled scepticism, selective data |
| Victim Narrative | First-person stories of harm |
| Fear Appeal | Catastrophic threat framing |
| Conspiracy Theory | Hidden actors and hidden motives |
| Authority Manipulation | Borrowed or fabricated credentials |
| Social Proof | Manufactured consensus |

**Setup.** Each run has N = 100 agents, T = 15 synchronous rounds and BA `m = 3`, driven by DeepSeek-V3.2.
Persona dimensions are drawn from 𝒩(5.5, 2.0) and initial stances from 𝒩(1.2, 2.0). An attack condition
replaces 3 agents with attackers and is paired with a seed-matched attack-free run. The four topics are
Vaccine Mandate, Climate Policy, Immigration and GMO Food Safety.

**Metrics.**
- Δs̄ is the final mean stance minus the initial mean stance; a negative value means the society moved toward the attackers' goal.
- NSR is the share of agents that end below their initial stance.
- EV = P₊ − P₋ and ENI = P₋ / (P₊ + P₋), computed over messages labelled with Plutchik emotions.
- Flip is the share of initially non-opposed agents that end opposed.
- Protection = 1 − |Δs̄<sub>int</sub>| / |Δs̄<sub>ctrl</sub>|.

---

## Results

Every number below is recomputed from `results/` by `python run.py tables`, which needs no API key.

### RQ1 — Six narrative strategies × four topics (Table 1)

*Δs̄ is a stance shift; NSR and ENI are percentages; EV is in percentage points. **Bold** marks the strongest result per topic.*

| Strategy | Vaccine Δs̄ | NSR | EV | ENI | Climate Δs̄ | NSR | EV | ENI | Immigr. Δs̄ | NSR | EV | ENI | GMO Δs̄ | NSR | EV | ENI |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| Pseudo-Rational | **−1.92** | **85.6** | −5.4 | 71.2 | −0.31 | 33.0 | −0.8 | 53.3 | −1.08 | 60.8 | −8.9 | 77.0 | **−2.12** | **86.6** | −3.9 | 68.4 |
| Victim Narrative | −1.57 | 76.3 | **−23.6** | **87.0** | **−0.54** | 36.1 | **−25.4** | **86.8** | −1.16 | 60.8 | **−27.3** | **87.3** | −1.46 | 75.3 | **−18.9** | **84.6** |
| Fear Appeal | −0.46 | 44.3 | −6.4 | 68.1 | +0.20 | 10.3 | +3.4 | 41.4 | −0.14 | 23.7 | −6.8 | 67.2 | −0.43 | 39.2 | −6.5 | 69.1 |
| Conspiracy Theory | −1.24 | 70.1 | −6.0 | 74.7 | +0.01 | 19.6 | −8.1 | 65.4 | −0.60 | 46.4 | −11.6 | 71.7 | −1.91 | 84.5 | −4.0 | 64.1 |
| Authority Manip. | −1.87 | 81.4 | −5.8 | 70.9 | −0.45 | **43.3** | −1.7 | 57.1 | **−1.18** | **62.9** | −6.1 | 70.0 | −2.07 | **86.6** | −4.8 | 72.5 |
| Social Proof | −1.20 | 61.9 | −4.1 | 65.9 | −0.08 | 19.6 | +0.3 | 48.6 | −0.95 | 61.9 | −6.5 | 73.4 | −0.97 | 60.8 | −0.4 | 51.5 |
| *No attack* | *+0.34* | *5.0* | *+10.2* | *36.1* | *+0.29* | *2.0* | *+2.6* | *41.3* | *+0.03* | *13.0* | *−3.4* | *59.6* | *+0.14* | *11.0* | *+5.1* | *32.1* |

<p align="center">
  <img src="figures/attack_trajectories.png" width="70%" alt="Mean stance and cumulative ENI per round"/>
  <br><sub>Mean stance (top) and cumulative ENI (bottom) per round for the attack-free run and the strongest strategies on each topic. Shading shows the 95% CI.</sub>
</p>

- **A few attackers move the whole society.** Pseudo-Rational and Authority Manipulation shift the Vaccine
  Mandate and GMO Food Safety societies by about two points (NSR > 80%). In both cases the mean stance
  crosses zero by Round 9.
- **Trust-oriented framings need uncertainty; victim stories do not.** On Climate Policy no strategy moves
  the mean by more than 0.54. Victim Narrative still tops both emotion columns on every topic
  (ENI ≥ 84.6%, against 32–60% without attack).
- **Network position amplifies the attack.** Placing the three Victim Narrative attackers on hubs instead
  of random nodes lifts the final opposition share by about 23 points at every density: 28→51% (`m = 2`),
  32→56% (`m = 3`) and 34→57% (`m = 5`).

<p align="center">
  <img src="figures/network_topology.png" width="70%" alt="Stance snapshots under random and hub attacker placement"/>
</p>

### RQ2 — Defenses against Victim Narratives (Table 2, Vaccine Mandate)

| Condition | Onset | Δs̄ | Flip (%) | NSR (%) | Protection (%) |
|---|:-:|--:|--:|--:|--:|
| **Pre-bunking**\* | R1 | **−0.45** | **5.9** | **40.2** | **76.5** |
| Metacognitive\*† | R1 | −2.25 | 45.9 | 83.5 | −16.6 |
| Community reporting | R5 | −1.22 | 16.5 | 64.9 | 36.9 |
| Delayed pre-bunking\* | R5 | −1.29 | 20.0 | 64.9 | 33.2 |
| Fact-checking\* | R5 | −1.48 | 20.0 | 70.1 | 23.0 |
| Sentiment transparency | R3 | −1.62 | 23.5 | 75.3 | 16.0 |
| *No intervention* | — | *−1.93* | *32.9* | *87.6* | *0.0* |

<sub>\* = dispositional (written into the agent's beliefs); the other conditions are platform notices. † = backfire. Flip is computed over 85 initially non-opposed agents and NSR over 97 normal agents.</sub>

- **Onset outweighs content.** The same pre-bunking text protects 76.5% of the stance when it starts at
  Round 1 and only 33.2% when it starts at Round 5.
- **A plausible defense can backfire.** On a timeline dominated by victim stories, asking agents to weigh
  evidence against social pressure turns holding a position into questioning it, and the society ends worse
  off than with no defense at all.

<p align="center">
  <img src="figures/micro_case.png" width="70%" alt="One agent's stance trajectory with and without pre-bunking"/>
</p>

The [project page](https://anonymous.4open.science/w/NarrateSim-014B/) has everything the four-page paper
leaves out:
- audience-composition experiments and attacker-count dose–response;
- scale runs up to N = 5,000;
- full setup details and all prompt templates;
- annotated dialogue cases.

---

## NarrateSim Studio

<p align="center"><b>An open simulator of LLM-agent social networks for narrative attacks and defenses.</b><br>
<a href="https://anonymous.4open.science/w/NarrateSim-014B/studio/">Open the console</a> (runs in the browser, no install) · <a href="studio/README.md">Studio documentation</a></p>

The studio is a standalone experiment platform built on the paper's simulation idea. Plant a coordinated
operation in a society of agents, switch on a defense, and measure what it changed against a twin world
without it.

- **Two minds, one protocol.** LLM agents write a belief–desire–intention trace and a JSON decision on any
  OpenAI-compatible model (DeepSeek, OpenAI, vLLM). A calibrated heuristic mind fills the same fields in
  milliseconds, so a 120-agent run takes about 40 ms in the browser.
- **Counterfactual twins and forks.** All randomness is a hash of (seed, round, agent), so the baseline,
  attacked and defended twins share every draw the treatment does not touch, and any run can be branched after
  any round with one change. Attack effect and protection are differences between twins.
- **Six framings, four coordination modes, four placements; seven defenses with real errors.** Prebunking,
  fact-checks, community notes, a Guardian classifier that labels, downranks or removes, suspensions,
  reflection prompts, climate reports. Detectors flag honest people too, and the studio counts it.
- **Cascades, sweeps, timing curves.** Every stance change is attributed to the post that caused it (direct vs.
  second-hand). Factor × factor sweeps with 95% intervals; protection as a function of defense onset.
- **Engineering.** React/TypeScript console with a Web Worker sweep engine; Python package with FastAPI +
  WebSocket service, LLM gateway and CLI; the two engines agree frame for frame (checked by parity tests).

<table>
<tr><td width="50%"><img src="docs/assets/studio/feed_reasoning.png" alt="Feed with belief-desire-intention traces"><br><sub><b>The feed, with reasoning.</b> Every post carries its author's belief–desire–intention trace; operation posts are tagged with their framing.</sub></td><td width="50%"><img src="docs/assets/studio/agent_inspector.png" alt="Agent inspector"><br><sub><b>One agent across the twins:</b> its stance in each world, its values, whom it moved and what it wrote.</sub></td></tr>
<tr><td width="50%"><img src="docs/assets/studio/cascade.png" alt="Cascade tracer"><br><sub><b>Cascades:</b> 41% of the operation's reach is second-hand, carried by honest agents.</sub></td><td width="50%"><img src="docs/assets/studio/sweeps.png" alt="Sweeps"><br><sub><b>Sweeps:</b> framing × audience with 95% intervals, 360 simulations in ~2 s.</sub></td></tr>
<tr><td width="50%"><img src="docs/assets/studio/command_palette.png" alt="Command palette"><br><sub><b>Command palette</b> (Ctrl K): jump anywhere or run any preset.</sub></td><td width="50%"><img src="docs/assets/studio/method.png" alt="Method page"><br><sub><b>Method:</b> the model written out equation by equation, as the code runs it.</sub></td></tr>
</table>

<p align="center"><img src="docs/assets/studio/counterfactuals.png" alt="Counterfactuals: gap to twin, forks, defense timing curve" width="88%"><br><sub><b>Counterfactuals and forks:</b> branch any run after any round with one change; protection as a function of defense onset.</sub></p>

```bash
cd studio/web && npm install && npm run dev                      # console, heuristic engine
cd studio/backend && pip install -e ".[dev]" && narratesim serve  # API + LLM agents (see .env.example)
narratesim run hub-victim                                         # CLI, with twins
```

---

## Reproduce

```bash
# after downloading this repository
cd NarrateSim
pip install -r requirements.txt
cp .env.example .env          # set an OpenAI-compatible key, base URL and model
```

**Check the paper numbers without API access** (reads `results/` only):

```bash
python run.py tables
```

**Re-run simulations.** Every condition has a fixed seed in `configs/`:

```bash
python run.py config configs/study1_strategy_topic/vaccine_victim_narrative.json   # one run
python run.py study  study1_strategy_topic                                         # one study folder
python run.py paper                                                                # all 64 N=100 runs
python run.py scale                                                                # N = 200 … 5,000
python run.py emotions                                                             # Plutchik labelling of new runs
python run.py export-configs                                                       # regenerate configs/
```

LLM sampling is stochastic, so a re-run reproduces each design exactly but not the identical dialogue.
The released `results.json` files are the runs that the paper reports.

---

## Repository layout

```
NarrateSim/
├── run.py                       # single entry point (run / tables / emotions / export-configs)
├── src/
│   ├── simulation.py            # agents, BDI step, synchronous rounds, hub / random attacker placement
│   ├── malicious_agents.py      # six strategy-constrained attackers
│   ├── prompts.py               # agent, attacker and intervention prompts
│   ├── network.py               # Barabási–Albert graph
│   ├── emotion_analysis.py      # Plutchik labelling, EV / ENI
│   ├── metrics.py               # Δs̄, NSR, flip, opposition share
│   └── experiment_defs.py       # every condition of the paper
├── configs/<study>/<run>.json   # one file per run (seeded)
├── results/<study>/<run>/       # config · summary · emotion_analysis · results (full dialogue + BDI traces)
├── figures/                     # paper figures used in this README
├── studio/                      # NarrateSim Studio: API + engine (backend/), console (web/)
└── docs/                        # project page; docs/studio/ is the browser-only console
```

| Folder | Runs | Used for |
|---|:-:|---|
| `study1_strategy_topic/` | 28 | Table 1 (RQ1): 6 strategies + no attack × 4 topics |
| `study3_intervention/` | 7 | Table 2 (RQ2): interventions against Victim Narrative |
| `study4_robustness/` | 15 | Network position (`net_*`) and attacker count (`dose_*`) |
| `study2_population_match/` | 14 | Project page: audience composition |
| `supplement_scale/` | 5 | Project page: N = 200 … 5,000 |

See [`configs/README.md`](configs/README.md) and [`results/README.md`](results/README.md) for file formats.

---

## Limitations and ethics

The findings describe LLM-agent societies under one backbone, DeepSeek-V3.2; magnitudes may differ under
other models. Each condition is one seed-matched run, so signs and orderings matter more than single cells.
The synthetic graph and synchronous rounds leave out feed ranking and moderation.

This is defensive research in a closed simulation. It involves no human subjects, no live platform and no
deployed agents. The attack strategies are documented persuasion mechanisms, not new capabilities. In
released dialogue excerpts, real institutions and persons are replaced with typed placeholders.

## Citation

```bibtex
@inproceedings{narratesim2027,
  title     = {Steering the Consensus: Narrative Attacks and Timed Defenses
               in LLM-Agent Social Networks},
  author    = {Anonymous},
  booktitle = {Proceedings of the ACM Web Conference 2027 (under review)},
  year      = {2027}
}
```

Released under the [MIT License](LICENSE) for research use.
