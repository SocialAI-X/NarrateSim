<div align="center">

# NarrateSim

### *恶意智能体如何扰乱在线讨论*

**基于 LLM 社交网络的叙事攻击模拟研究**

<br>

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)](requirements.txt)
[![论文](https://img.shields.io/badge/论文-EMNLP%20投稿-8B5CF6?style=for-the-badge)](latex_paper_cn/main.tex)
[![English](https://img.shields.io/badge/English-README-2563EB?style=for-the-badge)](README.md)

<br>

[快速开始](#-快速开始) · [实验设计](#-实验设计) · [结果数据](#-结果数据) · [论文](#-论文)

</div>

---

> **NarrateSim** 是一个多智能体模拟平台：LLM 智能体通过 **信念–愿望–意图（BDI）** 推理，在 **无标度社交网络** 上交互，并面对 **提示驱动的叙事攻击者**——让我们能在受控条件下研究策略性叙事如何在在线讨论中扎根蔓延。

---

## 核心发现

<table>
<tr>
<td align="center" width="33%">

### 攻击侧

少量恶意智能体即可将群体观点推离基线。证据型和权威型策略对 **立场** 影响最大；受害者叙事则显著抬升 **情绪温度**。

</td>
<td align="center" width="33%">

### 受众匹配

相同攻击内容在不同受众中产生截然不同的效果——**策略与受众的匹配** 决定了攻击成败。

</td>
<td align="center" width="33%">

### 防御侧

**预接种（pre-bunking）** 优于事后纠正。但时机至关重要——情绪一旦升温，连元认知提示也可能适得其反。

</td>
</tr>
</table>

---

## 系统架构

```
  实验配置 ──►  BA 无标度网络  ──►  BDI 智能体推理  ──►  LLM 生成发言
                    │                    │
                    ▼                    ▼
              恶意策略注入         立场 / 情绪 / 极化度量
                    │                    │
                    └──────►  results/  ·  论文图表  ◄──────┘
```

| 模块 | 文件 | 功能 |
|------|------|------|
| 模拟引擎 | `src/simulation.py` | 多轮同步对话模拟 |
| 恶意智能体 | `src/malicious_agents.py` | 6 种叙事攻击策略 |
| BDI 推理 | `src/prompts.py` | 信念–愿望–意图提示词 |
| 度量指标 | `src/metrics.py` | 立场偏移、极化、翻转率 |
| 情绪分析 | `src/emotion_analysis.py` | Plutchik 八类情绪标注 |

### 六种叙事攻击策略

| 策略 | 机制 |
|------|------|
| 伪理性论证 | 用选择性数据构建"理性"外观 |
| 受害者叙事 | 情感化个人故事引发共情 |
| 恐惧诉求 | 放大威胁感知 |
| 权威操纵 | 伪造专家背书与机构信誉 |
| 社会认同 | 虚构"大多数人"的共识 |
| 阴谋论 | 构建隐藏势力叙事框架 |

---

## 快速开始

### 安装依赖

```bash
git clone https://github.com/SocialAI-X/NarrateSim.git
cd NarrateSim
pip install -r requirements.txt
```

### 配置 API

```bash
cp .env.example .env
# 编辑 .env，填入 SILICONFLOW_API_KEY 或 OPENAI_API_KEY
```

支持任何 **OpenAI 兼容** 的 API 端点，默认使用 SiliconFlow + DeepSeek-V3.2。

### 运行单个实验

```bash
python run_experiment.py examples/vaccine_baseline.json
```

---

## 实验设计

论文共包含 **64 组受控实验**，覆盖四大研究维度：

| 研究 | 内容 | 条件数 |
|:----:|------|:------:|
| **Study 1** | 策略 × 话题 | 4 话题 × 6 策略 + 基线 |
| **Study 2** | 受众–策略匹配 | 不同人口特征 × 策略 |
| **Study 3** | 干预措施 | 预接种、事实核查、元认知 |
| **Study 4** | 鲁棒性 | 剂量响应、网络拓扑、规模扩展 |

### 复现论文结果

```bash
# 第一步：运行 64 组主实验（需数小时 + API 额度）
python run_all_experiments.py

# 第二步：补充规模实验（200–5000 智能体）
python run_supplement.py --task scale

# 第三步：批量情绪分析
python run_emotions.py

# 第四步：重新生成论文图表
python scripts/figures/generate_fig1_main.py
python scripts/figures/generate_study2_v3_final.py
python scripts/figures/generate_network_evolution.py
python scripts/figures/generate_scale5000_network.py
```

---

## 结果数据

仓库中包含所有论文实验的 **汇总指标**（不含原始对话日志）：

```
results/
├── full_study_20260521_v3/     # 64 组主实验
│   ├── manifest.json           # 完整配置快照
│   ├── all_summaries.json      # 聚合指标
│   └── <实验名>/
│       ├── summary.json        # 立场与极化指标
│       ├── emotion_analysis.json
│       └── config.json
└── supplement_20260522/
    └── scale_experiments/      # N = 200 ~ 5000
```

> 原始对话数据（`results.json`，每组约 100+ MB）未包含在仓库中。如需完整对话记录，请联系作者。

---

## 论文

- 英文原文：[`latex_paper/`](latex_paper/)
- 中文翻译：[`latex_paper_cn/`](latex_paper_cn/)

| 图表 | 内容 |
|------|------|
| `fig_study1_trajectories` | 四话题立场与情绪轨迹 |
| `fig_study2_ranking` | 受众–策略交互排序 |
| `fig_network_topology` | 网络结构放大攻击影响 |
| `fig_scale5k_evolution` | 5000 智能体规模验证 |
| `fig_micro_case` | 个体智能体轨迹案例分析 |

```bash
cd latex_paper_cn && xelatex main.tex
```

---

## 引用

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

## 目录结构

```
NarrateSim/
├── src/                    # 核心模拟引擎
├── run_experiment.py       # 单实验运行器
├── run_all_experiments.py  # 论文实验套件（64 组）
├── run_supplement.py       # 规模与补充实验
├── run_emotions.py         # 批量情绪分析
├── scripts/figures/        # 论文图表生成
├── results/                # 预计算汇总指标
├── latex_paper/            # 英文论文
└── latex_paper_cn/         # 中文翻译
```

---

<div align="center">

**将叙事攻击研究从「事后检测」推进到「动态机制分析」**

<br>

[English README](README.md) · [GitHub](https://github.com/SocialAI-X/NarrateSim)

</div>
