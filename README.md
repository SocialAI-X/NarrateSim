<div align="center">

# NarrateSim

### *How Malicious Agents Disrupt Online Discussion*

**Simulating Narrative Attacks in LLM-Based Social Networks**

<br>

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)](requirements.txt)
[![License: MIT](https://img.shields.io/badge/license-MIT-green?style=for-the-badge)](LICENSE)
[![Paper](https://img.shields.io/badge/paper-EMNLP%20submission-8B5CF6?style=for-the-badge)](latex_paper/main.tex)

<br>

[Quick Start](#-quick-start) · [Experiments](#-experiments) · [Results](#-results) · [Paper](#-paper) · [中文](README_zh.md)

</div>

---

> **NarrateSim** is a multi-agent simulation platform where LLM agents reason via a **Belief–Desire–Intention (BDI)** process, interact over a **scale-free social network**, and face **prompt-driven narrative attackers** — enabling controlled study of how strategic narratives take hold in online discussion.

<table>
<tr>
<td width="50%">

### Attack side
Even a handful of malicious agents can shift group opinion away from baseline. Evidence-based and credential-based strategies reshape **stance** most strongly; victim-style storytelling raises **emotional temperature**.

</td>
<td width="50%">

### Defence side
**Pre-bunking** outperforms reactive correction. But timing matters — once emotions run high, even self-reflection prompts can amplify rather than reduce the attack.

</td>
</tr>
</table>

---

## Architecture

```
                    ┌─────────────────────────────────────┐
                    │         NarrateSim Engine           │
                    │                                     │
  Config ──────────►│  BA Network  →  BDI Agents  →  LLM   │
                    │       ↑              ↑              │
                    │  Malicious      Emotion &           │
                    │  Strategies     Stance Metrics      │
                    └─────────────────────────────────────┘
                                      │
                                      ▼
                         results/  ·  paper figures
```

| Module | File | Role |
|--------|------|------|
| Simulation core | `src/simulation.py` | Round-based multi-agent dialogue |
| Malicious agents | `src/malicious_agents.py` | 6 narrative attack strategies |
| BDI reasoning | `src/prompts.py` | Agent belief–desire–intention prompts |
| Metrics | `src/metrics.py` | Stance shift, polarization, flip rate |
| Emotion | `src/emotion_analysis.py` | Plutchik 8-category labeling |

---

## Quick Start

### 1. Install

```bash
git clone https://github.com/SocialAI-X/NarrateSim.git
cd NarrateSim
pip install -r requirements.txt
```

### 2. Configure API

```bash
cp .env.example .env
# Edit .env — set SILICONFLOW_API_KEY or OPENAI_API_KEY
```

NarrateSim uses any **OpenAI-compatible** endpoint. The default configuration targets [SiliconFlow](https://siliconflow.cn/) with DeepSeek-V3.2.

### 3. Run a single experiment

```bash
python run_experiment.py examples/vaccine_baseline.json
```

> Paper experiments generate configs inline — see `run_all_experiments.py` below.

---

## Experiments

The paper evaluates **64 controlled runs** across four study groups:

| Study | Focus | Conditions |
|:-----:|-------|------------|
| **1** | Strategy × Topic | 4 topics × 6 strategies + baseline |
| **2** | Population matching | Audience traits × strategy fit |
| **3** | Interventions | Pre-bunking, fact-check, metacognitive |
| **4** | Robustness | Dose-response, network topology, scale |

### Reproduce paper results

```bash
# Step 1: Run all 64 main experiments (~hours, requires API credits)
python run_all_experiments.py

# Step 2: Supplementary scale experiments (200–5000 agents)
python run_supplement.py --task scale

# Step 3: Post-hoc emotion analysis
python run_emotions.py

# Step 4: Regenerate paper figures
python scripts/figures/generate_fig1_main.py
python scripts/figures/generate_study2_v3_final.py
python scripts/figures/generate_network_evolution.py
python scripts/figures/generate_scale5000_network.py
```

---

## Results

Pre-computed **summary metrics** are included for all paper experiments:

```
results/
├── full_study_20260521_v3/     # 64 main experiments
│   ├── manifest.json           # Full config snapshot
│   ├── all_summaries.json      # Aggregated metrics
│   └── <experiment>/
│       ├── summary.json        # Stance & polarization metrics
│       ├── emotion_analysis.json
│       └── config.json
└── supplement_20260522/
    └── scale_experiments/      # N = 200, 500, 1k, 2k, 5k
```

> Raw dialogue logs (`results.json`, ~100+ MB each) are **not** included in this repository. Contact the authors for full transcripts.

---

## Paper

The LaTeX source and compiled figures are in [`latex_paper/`](latex_paper/). A Chinese translation is available in [`latex_paper_cn/`](latex_paper_cn/).

| Figure | Description |
|--------|-------------|
| `fig_study1_trajectories` | Stance & emotion trajectories across 4 topics |
| `fig_study2_ranking` | Population–strategy interaction ranking |
| `fig_network_topology` | Network structure amplifies attack reach |
| `fig_scale5k_evolution` | 5,000-agent scale validation |
| `fig_micro_case` | Qualitative agent trajectory case study |

```bash
cd latex_paper && latexmk -pdf main.tex
```

---

## Citation

```bibtex
@inproceedings{narratesim2025,
  title={How Malicious Agents Disrupt Online Discussion:
         Simulating Narrative Attacks in LLM-Based Social Networks},
  author={Anonymous},
  booktitle={EMNLP},
  year={2025}
}
```

---

## Project Structure

```
NarrateSim/
├── src/                    # Core simulation engine
├── run_experiment.py       # Single-config runner
├── run_all_experiments.py  # Paper experiment suite (64 runs)
├── run_supplement.py       # Scale & supplementary experiments
├── run_emotions.py         # Batch emotion analysis
├── scripts/figures/        # Paper figure generators
├── results/                # Pre-computed summaries
├── latex_paper/            # English paper source
└── latex_paper_cn/         # Chinese translation
```

---

<div align="center">

*Shifting narrative-attack research from post-hoc detection to dynamic mechanism analysis.*

</div>
