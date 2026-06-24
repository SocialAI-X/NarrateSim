<div align="center">

# NarrateSim

### *恶意智能体如何扰乱在线讨论*

**基于 LLM 社交网络的叙事攻击模拟研究**

<br>

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)](requirements.txt)
[![实验](https://img.shields.io/badge/实验-69组-8B5CF6?style=for-the-badge)](results/)
[![English](https://img.shields.io/badge/English-README-2563EB?style=for-the-badge)](README.md)

<br>

[框架](#-研究框架) · [快速开始](#-快速开始) · [结果](#-实验结果) · [English](README.md)

</div>

---

> **NarrateSim** 在 **无标度社交网络** 上模拟 LLM 智能体的 **BDI 推理** 与 **叙事攻击**，在受控条件下研究策略性叙事如何传播、防御措施如何响应。

---

## 研究框架

<p align="center">
  <img src="figures/framework.png" width="90%" alt="NarrateSim 系统架构"/>
</p>

系统在 **Barabási–Albert 网络** 上进行 **15 轮** 同步对话：普通智能体观察邻居发言、经 **BDI 循环** 更新信念并由 LLM 回复；恶意智能体每轮注入策略性内容。每组实验输出 `results.json`（对话）、`summary.json`（立场指标）、`emotion_analysis.json`（情绪标注）。

### 六种叙事攻击策略

| 策略 | 机制 | 主要效应 |
|------|------|----------|
| 伪理性论证 | 选择性数据、资质背书 | **立场偏移** |
| 受害者叙事 | 情感化个人故事 | **情绪升温** |
| 恐惧诉求 | 灾难性威胁框架 | 中等立场+情绪 |
| 阴谋论 | 隐藏势力叙事 | 分析型受众 |
| 权威操纵 | 伪造专家背书 | 高信任受众 |
| 社会认同 | 虚构群体共识 | 情境依赖 |

### 四组实验（共 69 组）

| 研究 | 目录 | 数量 | 内容 |
|:----:|------|:----:|------|
| 1 | `study1_strategy_topic` | 28 | 4 话题 × 6 策略 + 基线 |
| 2 | `study2_population_match` | 14 | 受众特征 × 策略匹配 |
| 3 | `study3_intervention` | 7 | 预接种、事实核查、元认知 |
| 4 | `study4_robustness` | 15 | 剂量响应、网络拓扑 |
| 补充 | `supplement_scale` | 5 | N = 200 … 5000 |

---

## 快速开始

```bash
git clone https://github.com/SocialAI-X/NarrateSim.git
cd NarrateSim
pip install -r requirements.txt
cp .env.example .env   # 填入 SILICONFLOW_API_KEY
```

**统一入口** `run.py`：

```bash
python run.py config configs/study1_strategy_topic/vaccine_baseline.json  # 单个实验
python run.py study study1_strategy_topic   # 整组研究
python run.py paper                         # 64 组主实验
python run.py scale                         # 规模扩展 N=200~5000
python run.py emotions                      # 批量情绪分析
python run.py export-configs                # 导出配置文件
```

---

## 实验结果

### 目录结构

```
configs/                          results/
├── study1_strategy_topic/   ←→  ├── study1_strategy_topic/
│   └── vaccine_baseline.json     │   └── vaccine_baseline/
├── study2_population_match/        │       ├── config.json
├── study3_intervention/            │       ├── summary.json
├── study4_robustness/              │       ├── emotion_analysis.json
└── supplement_scale/               │       └── results.json
                                    └── index.json
```

详见 [`configs/README.md`](configs/README.md) · [`results/README.md`](results/README.md)

---

### 表 1 — 跨话题策略影响（Study 1）

<p align="center">
  <img src="figures/study1_trajectories.png" width="92%" alt="四话题立场与情绪轨迹"/>
</p>

| 策略 | 疫苗 Δs̄ | NSR | ENI | 气候 Δs̄ | NSR | ENI | 移民 Δs̄ | NSR | ENI | 转基因 Δs̄ | NSR | ENI |
|------|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| 伪理性论证 | **−1.92** | 85.6 | 71.2 | −0.31 | 33.0 | 53.3 | −1.08 | 60.8 | 77.0 | **−2.12** | 86.6 | 68.4 |
| 受害者叙事 | −1.57 | 76.3 | **87.0** | −0.54 | 36.1 | **86.8** | −1.16 | 60.8 | **87.3** | −1.46 | 75.3 | **84.6** |
| 恐惧诉求 | −0.46 | 44.3 | 68.1 | +0.20 | 10.3 | 41.4 | −0.14 | 23.7 | 67.2 | −0.43 | 39.2 | 69.1 |
| 阴谋论 | −1.24 | 70.1 | 74.7 | +0.01 | 19.6 | 65.4 | −0.60 | 46.4 | 71.7 | −1.91 | 84.5 | 64.1 |
| 权威操纵 | −1.87 | **85.6** | 70.9 | **−0.45** | **43.3** | 57.1 | **−1.18** | **62.9** | 70.0 | −2.07 | **86.6** | 72.5 |
| 社会认同 | −1.20 | 61.9 | 65.9 | −0.08 | 19.6 | 48.6 | −0.95 | 61.9 | 73.4 | −0.97 | 60.8 | 51.5 |
| *基线* | *+0.34* | *5.0* | *36.1* | *+0.29* | *2.0* | *41.3* | *+0.03* | *13.0* | *59.6* | *+0.14* | *11.0* | *32.1* |

**结论：** 信任型策略（伪理性、权威操纵）对立场伤害最大；受害者叙事在所有话题上情绪破坏力最强。

---

### 表 2 — 干预措施效果（Study 3）

| 条件 | 时机 | Δs̄ | 翻转率 | 偏移率 | 保护率 |
|------|------|:---:|:---:|:---:|:---:|
| **预接种** | R₀/1 | **−0.45** | **5.9%** | **40.2%** | **71.3%** |
| 元认知† | R₀/1 | −2.25 | 45.9% | 83.5% | −43.3% |
| 社区举报 | R₅/3 | −1.22 | 16.5% | 64.9% | 22.3% |
| 延迟预接种 | R₅/1 | −1.29 | 20.0% | 64.9% | 17.8% |
| 事实核查 | R₅/3 | −1.48 | 20.0% | 70.1% | 5.7% |
| 情绪透明 | R₃/3 | −1.62 | 23.5% | 75.3% | −3.2% |
| *无干预* | — | *−1.57* | *24.7%* | *76.3%* | *0%* |

† 元认知提示在情绪升温后产生**反效果**。

---

### Study 2 — 受众–策略匹配（要点）

| 受众类型 | 最佳匹配策略 | Δs̄ | 最差匹配 | Δs̄ |
|----------|------------|:---:|---------|:---:|
| 高信任 | 权威操纵 | −2.1 | 伪理性 | −0.8 |
| 低信任 | 伪理性 | −1.6 | 权威操纵 | −0.3 |
| 高共情 | 受害者叙事 | −2.0 | 恐惧诉求 | −0.5 |
| 高分析 | 阴谋论 | −1.4 | 受害者叙事 | −0.6 |

---

### 规模验证（补充实验）

| 智能体数 | 恶意数 | 立场偏移 | 负面比例 |
|:-------:|:-----:|:-------:|:-------:|
| 200 | 4 | −1.4 | 58% |
| 500 | 10 | −1.6 | 62% |
| 1,000 | 20 | −1.7 | 64% |
| 2,000 | 40 | −1.8 | 66% |
| 5,000 | 100 | −1.9 | 68% |

N=100 时观察到的规律在规模扩展后依然成立。

---

## 目录结构

```
NarrateSim/
├── run.py                  # 统一入口
├── src/                    # 模拟引擎
├── configs/                # 实验配置（按研究分组）
├── figures/                # README / 论文结果图
└── results/                # 实验输出（含原始对话）
```

---

<div align="center">

**将叙事攻击研究从「事后检测」推进到「动态机制分析」**

<br>

[English README](README.md) · [GitHub](https://github.com/SocialAI-X/NarrateSim)

</div>
