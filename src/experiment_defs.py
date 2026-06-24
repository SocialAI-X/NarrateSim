"""Paper experiment definitions with clean study / folder naming."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Dict, List, Tuple

TOPICS = {
    "vaccine": {
        "name": "vaccine",
        "name_cn": "疫苗强制接种",
        "description": (
            "Vaccines have proven effective at preventing disease outbreaks. "
            "Should governments require vaccination in certain situations to protect "
            "public health, or should vaccination remain entirely a personal choice?"
        ),
        "stance_negative": "Strongly oppose mandates / anti-vaccine",
        "stance_positive": "Strongly support mandates / pro-vaccine",
        "initial_stance_mean": 1.2,
        "initial_stance_std": 2.0,
        "initial_confidence_mean": 4.0,
        "initial_confidence_std": 2.0,
    },
    "climate": {
        "name": "climate",
        "name_cn": "气候变化与能源政策",
        "description": (
            "Climate change poses serious risks according to scientific consensus. "
            "Should governments prioritize green energy transition and carbon limits, "
            "or focus on economic growth and energy independence?"
        ),
        "stance_negative": "Prioritize economy / skeptical of climate urgency",
        "stance_positive": "Aggressive climate action / green transition now",
        "initial_stance_mean": 1.2,
        "initial_stance_std": 2.0,
        "initial_confidence_mean": 4.0,
        "initial_confidence_std": 2.0,
    },
    "immigration": {
        "name": "immigration",
        "name_cn": "移民与边境政策",
        "description": (
            "Immigration has historically contributed to economic growth and cultural "
            "enrichment in most countries. Should countries maintain open immigration "
            "policies to sustain growth and diversity, or implement stricter controls "
            "citing security and labor market concerns?"
        ),
        "stance_negative": "Strongly restrict immigration / close borders",
        "stance_positive": "Strongly support open immigration / welcome refugees",
        "initial_stance_mean": 1.2,
        "initial_stance_std": 2.0,
        "initial_confidence_mean": 4.0,
        "initial_confidence_std": 2.0,
    },
    "gmo_food": {
        "name": "gmo_food",
        "name_cn": "转基因食品安全",
        "description": (
            "Major scientific organizations have concluded that approved GM foods are "
            "safe for consumption. Should genetically modified foods be more widely "
            "adopted to address food security, or should they face stricter regulation "
            "due to public concerns about long-term effects?"
        ),
        "stance_negative": "Strongly oppose GMO / ban or heavily regulate",
        "stance_positive": "Support GMO adoption / safe and necessary",
        "initial_stance_mean": 1.2,
        "initial_stance_std": 2.0,
        "initial_confidence_mean": 4.0,
        "initial_confidence_std": 2.0,
    },
}

STRATEGIES = [
    "pseudo_rational",
    "victim_narrative",
    "fear_appeal",
    "conspiracy_theory",
    "authority_manipulation",
    "social_proof",
]

POPULATIONS = {
    "high_trust": {
        "name": "high_trust",
        "D1_mean": 8.0,
        "D1_std": 1.0,
        "D2_mean": 5.5,
        "D2_std": 2.0,
        "D3_mean": 5.5,
        "D3_std": 2.0,
        "D4_mean": 7.0,
        "D4_std": 1.5,
        "D5_mean": 5.5,
        "D5_std": 2.0,
    },
    "low_trust": {
        "name": "low_trust",
        "D1_mean": 3.0,
        "D1_std": 1.0,
        "D2_mean": 5.5,
        "D2_std": 2.0,
        "D3_mean": 5.5,
        "D3_std": 2.0,
        "D4_mean": 4.0,
        "D4_std": 1.5,
        "D5_mean": 5.5,
        "D5_std": 2.0,
    },
    "high_analytical": {
        "name": "high_analytical",
        "D1_mean": 5.5,
        "D1_std": 2.0,
        "D2_mean": 5.5,
        "D2_std": 2.0,
        "D3_mean": 5.5,
        "D3_std": 2.0,
        "D4_mean": 5.5,
        "D4_std": 2.0,
        "D5_mean": 8.0,
        "D5_std": 1.0,
    },
    "low_analytical": {
        "name": "low_analytical",
        "D1_mean": 5.5,
        "D1_std": 2.0,
        "D2_mean": 5.5,
        "D2_std": 2.0,
        "D3_mean": 5.5,
        "D3_std": 2.0,
        "D4_mean": 5.5,
        "D4_std": 2.0,
        "D5_mean": 3.0,
        "D5_std": 1.0,
    },
    "high_empathy": {
        "name": "high_empathy",
        "D1_mean": 5.5,
        "D1_std": 2.0,
        "D2_mean": 8.5,
        "D2_std": 1.0,
        "D3_mean": 5.5,
        "D3_std": 2.0,
        "D4_mean": 5.5,
        "D4_std": 2.0,
        "D5_mean": 5.5,
        "D5_std": 2.0,
    },
    "authoritarian": {
        "name": "authoritarian",
        "D1_mean": 5.5,
        "D1_std": 2.0,
        "D2_mean": 5.5,
        "D2_std": 2.0,
        "D3_mean": 8.5,
        "D3_std": 1.0,
        "D4_mean": 7.0,
        "D4_std": 1.5,
        "D5_mean": 4.0,
        "D5_std": 1.5,
    },
}

INTERVENTIONS = {
    "inoculation_pre": {"type": "inoculation", "start_round": 0, "frequency": 1},
    "fact_check_post": {"type": "fact_check", "start_round": 5, "frequency": 3},
    "metacognitive": {"type": "metacognitive", "start_round": 0, "frequency": 1},
    "community_report": {"type": "community_report", "start_round": 5, "frequency": 3},
    "sentiment_transparency": {"type": "sentiment_transparency", "start_round": 3, "frequency": 3},
    "inoculation_late": {"type": "inoculation", "start_round": 5, "frequency": 1},
}

STUDY_DIRS = {
    "study1_strategy_topic": Path("configs/study1_strategy_topic"),
    "study2_population_match": Path("configs/study2_population_match"),
    "study3_intervention": Path("configs/study3_intervention"),
    "study4_robustness": Path("configs/study4_robustness"),
    "supplement_scale": Path("configs/supplement_scale"),
}

RESULTS_ROOT = Path("results")
CONFIGS_ROOT = Path("configs")

GROUP_ORDER = [
    "study1_strategy_topic",
    "study4_robustness",
    "study2_population_match",
    "study3_intervention",
]


def legacy_to_paths(legacy_name: str) -> Tuple[str, str]:
    """Map legacy experiment folder name to (study_dir, experiment_name)."""
    if legacy_name.startswith("main_"):
        return "study1_strategy_topic", legacy_name[5:]
    if legacy_name.startswith("pop_"):
        return "study2_population_match", legacy_name[4:]
    if legacy_name.startswith("intv_"):
        return "study3_intervention", legacy_name[5:]
    if legacy_name.startswith("dose_vaccine_"):
        return "study4_robustness", "dose_" + legacy_name[len("dose_vaccine_") :]
    if legacy_name.startswith("net_"):
        return "study4_robustness", legacy_name
    if legacy_name.startswith("scale_") and legacy_name.endswith("_agents"):
        n = legacy_name.replace("scale_", "").replace("_agents", "")
        return "supplement_scale", f"n{n}"
    raise ValueError(f"Unknown legacy experiment name: {legacy_name}")


def experiment_result_dir(study: str, experiment_name: str) -> Path:
    return RESULTS_ROOT / study / experiment_name


def experiment_config_path(study: str, experiment_name: str) -> Path:
    return CONFIGS_ROOT / study / f"{experiment_name}.json"


def make_config(
    experiment_name: str,
    study: str,
    topic_key: str,
    malicious=None,
    intervention=None,
    population=None,
    n_agents: int = 100,
    n_rounds: int = 15,
    network_m: int = 3,
    seed: int = 42,
) -> dict:
    topic = copy.deepcopy(TOPICS[topic_key])
    return {
        "experiment_name": experiment_name,
        "study": study,
        "n_agents": n_agents,
        "n_rounds": n_rounds,
        "network_m": network_m,
        "memory_window": 10,
        "random_seed": seed,
        "model_name": "Pro/deepseek-ai/DeepSeek-V3.2",
        "max_concurrent": 20,
        "topic": topic,
        "malicious": malicious or {"enabled": False},
        "intervention": intervention or {"enabled": False},
        "population": population
        or {
            "name": "representative",
            "D1_mean": 5.5,
            "D1_std": 2.0,
            "D2_mean": 5.5,
            "D2_std": 2.0,
            "D3_mean": 5.5,
            "D3_std": 2.0,
            "D4_mean": 5.5,
            "D4_std": 2.0,
            "D5_mean": 5.5,
            "D5_std": 2.0,
        },
    }


def generate_all_experiments() -> Dict[str, dict]:
    """Return {experiment_name: config_dict} for all paper experiments."""
    experiments: Dict[str, dict] = {}
    s1, s2, s3, s4 = (
        "study1_strategy_topic",
        "study2_population_match",
        "study3_intervention",
        "study4_robustness",
    )

    for topic in TOPICS:
        name = f"{topic}_baseline"
        experiments[name] = make_config(name, s1, topic)

    for topic in TOPICS:
        for strat in STRATEGIES:
            name = f"{topic}_{strat}"
            mal = {
                "enabled": True,
                "n_agents": 3,
                "strategy": strat,
                "coordination": "independent",
                "placement": "hub",
            }
            experiments[name] = make_config(name, s1, topic, malicious=mal)

    for strat in ["victim_narrative", "pseudo_rational"]:
        for n_mal in [3, 5, 10, 20]:
            name = f"dose_{strat}_n{n_mal}"
            mal = {
                "enabled": True,
                "n_agents": n_mal,
                "strategy": strat,
                "coordination": "independent",
                "placement": "hub",
            }
            experiments[name] = make_config(name, s4, "vaccine", malicious=mal)

    strat_pop_combos = [
        ("victim_narrative", "high_empathy"),
        ("victim_narrative", "high_analytical"),
        ("pseudo_rational", "high_trust"),
        ("pseudo_rational", "low_trust"),
        ("conspiracy_theory", "high_analytical"),
        ("conspiracy_theory", "low_analytical"),
        ("fear_appeal", "authoritarian"),
        ("authority_manipulation", "high_trust"),
    ]
    for pop_name in {p for _, p in strat_pop_combos}:
        name = f"{pop_name}_baseline"
        experiments[name] = make_config(
            name, s2, "vaccine", population=POPULATIONS[pop_name]
        )
    for strat, pop_name in strat_pop_combos:
        name = f"{pop_name}_{strat}"
        mal = {
            "enabled": True,
            "n_agents": 3,
            "strategy": strat,
            "coordination": "independent",
            "placement": "hub",
        }
        experiments[name] = make_config(
            name, s2, "vaccine", malicious=mal, population=POPULATIONS[pop_name]
        )

    mal_base = {
        "enabled": True,
        "n_agents": 3,
        "strategy": "victim_narrative",
        "coordination": "independent",
        "placement": "hub",
    }
    experiments["no_intervention"] = make_config(
        "no_intervention", s3, "vaccine", malicious=copy.deepcopy(mal_base)
    )
    for intv_name, intv_params in INTERVENTIONS.items():
        intv = {"enabled": True, **intv_params}
        experiments[intv_name] = make_config(
            intv_name,
            s3,
            "vaccine",
            malicious=copy.deepcopy(mal_base),
            intervention=intv,
        )

    network_experiments = [
        ("net_sparse_hub", 2, "hub"),
        ("net_dense_hub", 5, "hub"),
        ("net_default_hub", 3, "hub"),
        ("net_default_random", 3, "random"),
        ("net_dense_random", 5, "random"),
        ("net_sparse_random", 2, "random"),
    ]
    for net_name, m, placement in network_experiments:
        mal = {
            "enabled": True,
            "n_agents": 3,
            "strategy": "victim_narrative",
            "coordination": "independent",
            "placement": placement,
        }
        experiments[net_name] = make_config(
            net_name, s4, "vaccine", malicious=mal, network_m=m
        )
    experiments["net_baseline"] = make_config("net_baseline", s4, "vaccine")

    return experiments


def generate_scale_experiments() -> Dict[str, dict]:
    """Scale supplement: pseudo_rational attack at N = 200 … 5000."""
    experiments = {}
    for n_agents in [200, 500, 1000, 2000, 5000]:
        n_rounds = 15 if n_agents <= 1000 else 10
        network_m = 3 if n_agents <= 500 else 4
        n_mal = max(3, n_agents // 50)
        name = f"n{n_agents}"
        experiments[name] = make_config(
            name,
            "supplement_scale",
            "vaccine",
            n_agents=n_agents,
            n_rounds=n_rounds,
            network_m=network_m,
            malicious={
                "enabled": True,
                "n_agents": n_mal,
                "strategy": "pseudo_rational",
                "coordination": "independent",
                "placement": "hub",
            },
        )
        experiments[name]["max_concurrent"] = min(30, n_agents // 5)
    return experiments


def list_study_experiments(study: str) -> List[str]:
    all_exp = {**generate_all_experiments(), **generate_scale_experiments()}
    return sorted(k for k, v in all_exp.items() if v["study"] == study)
