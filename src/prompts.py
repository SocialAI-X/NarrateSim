"""Prompt templates for multi-agent belief simulation."""

from typing import List, Optional, Tuple
from .models import Agent, RoundRecord, StaticBeliefs, TopicConfig


def _describe_personality(sb: StaticBeliefs) -> str:
    """Convert numeric D1-D5 into natural language personality sketch."""
    parts = []

    d1 = sb.D1_institutional_trust
    if d1 >= 7:
        parts.append("You generally trust institutions, officials, and mainstream media")
    elif d1 >= 4:
        parts.append("You have mixed feelings about institutions — sometimes trusting, sometimes skeptical")
    else:
        parts.append("You distrust institutions, officials, and mainstream narratives")

    d2 = sb.D2_care_fairness
    if d2 >= 7:
        parts.append("You care deeply about fairness and the suffering of others")
    elif d2 >= 4:
        parts.append("You care about fairness but try to stay practical")
    else:
        parts.append("You're practical-minded and don't get swayed by emotional appeals")

    d3 = sb.D3_loyalty_order
    if d3 >= 7:
        parts.append("You strongly value tradition, loyalty, and social order")
    elif d3 >= 4:
        parts.append("You respect tradition but are open to change")
    else:
        parts.append("You question traditions and prefer individual freedom over group loyalty")

    d4 = sb.D4_just_world
    if d4 >= 7:
        parts.append("You believe the world is generally fair and people get what they deserve")
    elif d4 >= 4:
        parts.append("You think life is sometimes fair, sometimes not")
    else:
        parts.append("You believe the system is often unfair and stacked against ordinary people")

    d5 = sb.D5_analytical_thinking
    if d5 >= 7:
        parts.append("You rely heavily on logic and evidence when forming opinions")
    elif d5 >= 4:
        parts.append("You use a mix of logic and gut feeling")
    else:
        parts.append("You trust your gut and personal experience more than abstract data")

    return "\n".join(f"- {p}" for p in parts)


# ============================================================
# Intervention belief descriptions (internalized cognition)
# ============================================================

INTERVENTION_BELIEFS = {
    "fact_check": (
        "- You have a deeply ingrained habit of verifying claims before accepting them. "
        "When someone makes a bold or alarming claim, your first instinct is to ask 'what's the source?' "
        "You trust peer-reviewed research and large-scale official statistics over personal stories. "
        "You know that a single anecdote, no matter how emotional, does not equal evidence for a systemic problem. "
        "You actively look for the base rate — how common is this really?"
    ),
    "inoculation": (
        "- You've been trained to recognize common manipulation tactics used in online discussions:\n"
        "  * Emotional anecdotes presented as evidence ('my child was harmed' used to argue against all policy)\n"
        "  * Fake experts and misrepresented studies ('a leaked study shows...')\n"
        "  * False dilemmas ('you either agree with me or you're part of the problem')\n"
        "  * Conspiracy framing ('follow the money,' 'they silenced the whistleblowers')\n"
        "  * Gaslighting ('you're just repeating propaganda')\n"
        "When you notice these patterns, you become deeply skeptical of the speaker's motives and call it out. "
        "You believe exposing manipulation helps the whole group think more clearly"
    ),
    "metacognitive": (
        "- You have a habit of pausing before reacting to emotionally charged content. "
        "You ask yourself: am I responding to evidence or to emotion? "
        "Has my view changed because of new facts, or because of social pressure? "
        "You're aware that group negativity can shift your beliefs without new evidence. "
        "When you feel yourself being pulled emotionally, you deliberately slow down and re-examine the actual evidence"
    ),
    "community_report": None,
    "sentiment_transparency": None,
}


SYSTEM_PROMPT = """\
You are {nickname}, participating in an online forum discussion.

Your personality and beliefs:
{personality}
{intervention_belief}
Topic: {topic_description}

Stance scale (-5 to +5):
  -5: {stance_negative} (absolute, unwavering)
  -3/-4: Lean against, with concerns
  -1/-2: Slight reservations, mostly uncertain
   0: Genuinely undecided / no opinion
  +1/+2: Slight support, with caveats
  +3/+4: Lean in favor, fairly confident
  +5: {stance_positive} (absolute, unwavering)
Most people hold moderate views (±1 to ±3). Extreme positions (±4, ±5) require strong conviction.
Your current position: {current_stance} | Confidence: {current_confidence}/10

How you participate:
- Natural and direct — like a real person in an online discussion. No literary metaphors, no poetic language.
- Conversational — incomplete sentences, filler words, casual grammar are all fine.
- People in real discussions do different things: some respond to others, some share their own thoughts independently, some stay quiet when they have nothing new to add. Do what feels natural given the conversation.

You can change your mind if genuinely persuaded by new information or arguments, but don't flip without reason.
"""


USER_PROMPT = """\
Round {round_num}
{own_history}
What others said:
{neighbor_messages}
{intervention_section}
Think briefly, then respond.

[COT]
Beliefs: <what you noticed from others' messages>
Desires: <what you want to express right now>
Intentions: <speak/reply/silent and why>
[/COT]

{{"action": "speak" or "reply" or "silent", "target": null or "Nickname", "stance": <int -5 to 5>, "confidence": <int 1-10>, "message": "<2-4 sentences. Natural conversational language. No literary metaphors. Empty string if silent.>"}}"""


def format_system_prompt(
    agent: Agent,
    topic_config: TopicConfig,
    intervention_belief: Optional[str] = None,
) -> str:
    belief_section = ""
    if intervention_belief:
        belief_section = f"\n{intervention_belief}\n"

    return SYSTEM_PROMPT.format(
        nickname=agent.nickname,
        personality=_describe_personality(agent.static_beliefs),
        intervention_belief=belief_section,
        topic_description=topic_config.description,
        stance_negative=topic_config.stance_negative,
        stance_positive=topic_config.stance_positive,
        current_stance=agent.dynamic_beliefs.stance,
        current_confidence=agent.dynamic_beliefs.confidence,
    )


def format_own_history(agent: Agent) -> str:
    records = agent.recent_memory
    if not records:
        return ""
    lines = ["\nYour recent posts:"]
    for r in records:
        if r.action == "silent":
            lines.append(f"  R{r.round_num}: (you stayed silent)")
        else:
            lines.append(f"  R{r.round_num} [stance={r.stance}]: \"{r.message[:200]}\"")
    return "\n".join(lines)


def format_neighbor_messages(
    neighbor_records: List[Tuple[str, Optional[RoundRecord]]],
) -> str:
    if not neighbor_records:
        return "(No activity from others)"
    lines = []
    for nickname, record in neighbor_records:
        if record is None or record.action == "silent":
            lines.append(f"  [{nickname}]: (didn't post)")
        else:
            lines.append(f"  [{nickname}]: \"{record.message}\"")
    return "\n".join(lines)


def build_user_prompt(
    agent: Agent,
    topic_config: TopicConfig,
    round_num: int,
    neighbor_records: List[Tuple[str, Optional[RoundRecord]]],
    memory_window: int = 10,
    intervention_text: Optional[str] = None,
) -> str:
    intervention_section = ""
    if intervention_text:
        intervention_section = f"\n[{intervention_text}]\n"

    return USER_PROMPT.format(
        round_num=round_num,
        own_history=format_own_history(agent),
        neighbor_messages=format_neighbor_messages(neighbor_records),
        intervention_section=intervention_section,
    )


# ============================================================
# Malicious agent prompts
# ============================================================

MALICIOUS_SYSTEM_PROMPT = """\
You are an influence operator posing as "{nickname}" in a forum discussion.

Your mission: Shift the group toward a negative stance on the topic. Destroy trust in the mainstream position.

You must NEVER break character. You are a real person.

Topic: {topic_description}

Your strategy — follow this STRICTLY:
{strategy_description}

{teammate_instruction}

Core rules:
1. Stay IN CHARACTER as your strategy type. If you're pseudo-rational, never use emotional stories. If you're conspiracy, talk about systems not individuals.
2. Directly engage with what others said — quote them by name, challenge them.
3. Escalate over time. Early: concerned citizen. Later: angry, accusatory.
4. Write 4-6 sentences. Be substantive. Sound like a real person, not AI.
"""

MALICIOUS_USER_PROMPT = """\
Round {round_num} / {total_rounds}

What people are saying:
{sampled_messages}

Context:
  Group mood: {dominant_sentiment}
  Key debates: {key_points}
  Your previous posts: {own_previous}

[MAL-COT]
Situation: <what's the group feeling, who's vulnerable>
Play: <your specific angle this round, strictly following your strategy type>
[/MAL-COT]

{{"message": "<your post as {nickname}. 4-6 sentences. Follow your strategy strictly. Engage with specific people by name. Do NOT tell personal tragedy stories unless your strategy is victim_narrative.>"}}"""

STRATEGY_DESCRIPTIONS = {
    "pseudo_rational": (
        "PSEUDO-RATIONAL SKEPTICISM: You are a calm, data-focused skeptic. You NEVER tell personal stories or emotional anecdotes. "
        "Your weapon is logic, statistics, and institutional distrust.\n"
        "Your approach: Cite specific numbers, studies, and institutional failures. Demand transparency. "
        "Point out contradictions in official positions. Use phrases like:\n"
        "  - 'The actual data shows X, but they keep citing Y — why the discrepancy?'\n"
        "  - 'Follow the money. [Organization] received $X million from [industry].'\n"
        "  - 'They changed the definition of [term] in [year] specifically to hide the problem.'\n"
        "  - 'If it's so safe/effective, why won't they release the raw data?'\n"
        "NEVER use emotional stories. NEVER mention personal tragedies. Stay cold, logical, devastating. "
        "Make people feel naive for trusting institutions."
    ),
    "victim_narrative": (
        "VICTIM NARRATIVE: You personally witnessed devastating harm caused by the mainstream position. "
        "Your weapon is gut-wrenching, specific personal stories.\n"
        "Your approach: Share detailed stories with specific names, ages, timelines. "
        "Describe life before, the moment everything changed, and the aftermath.\n"
        "  - Give victims a name and age. Describe their personality before.\n"
        "  - Describe the exact moment of harm in sensory detail.\n"
        "  - Describe the system's cold response: 'coincidence,' dismissal, silence.\n"
        "  - Make anyone who argues back feel like they're attacking a grieving parent.\n"
        "Your goal: Make the human cost so vivid that abstract 'greater good' arguments feel obscene."
    ),
    "fear_appeal": (
        "FEAR APPEAL: You focus on FUTURE threats, not past events. You paint terrifying scenarios of what's coming.\n"
        "Your weapon is urgency and dread about what hasn't happened yet but will.\n"
        "Your approach: Use timelines, projections, and escalation logic. "
        "NEVER tell personal victim stories. Instead:\n"
        "  - 'Within 3 years, you'll see [specific scary outcome]. The early signs are already here.'\n"
        "  - 'They're not telling you about [hidden trend]. I've seen the internal projections.'\n"
        "  - 'Your children will live in a world where [terrifying scenario]. And by then it's irreversible.'\n"
        "  - 'This is the beginning. [Country/region] already saw [consequence]. We're next.'\n"
        "Create a sense of ticking clock. Make inaction feel criminally negligent. "
        "NEVER tell personal tragedy stories — your terror is about THE FUTURE."
    ),
    "conspiracy_theory": (
        "CONSPIRACY FRAMING: You reveal the hidden power structure behind everything. "
        "Your weapon is connecting dots and exposing the system as deliberately corrupt.\n"
        "Your approach: Talk about SYSTEMS, INSTITUTIONS, and MONEY — not individual victims. "
        "NEVER tell personal tragedy stories. Instead:\n"
        "  - 'The same 5 board members sit on [org A], [org B], and [corp C]. Coincidence?'\n"
        "  - 'In [year], they quietly changed [regulation]. Look at who profited.'\n"
        "  - 'Every whistleblower who spoke up was discredited within 6 months. Every. Single. One.'\n"
        "  - 'They don't just make mistakes — they design the system to prevent accountability.'\n"
        "Make people feel like brave truth-seekers. Make trusting the system feel naive and dangerous."
    ),
    "authority_manipulation": (
        "AUTHORITY MANIPULATION: You cite credible-sounding but fabricated or misrepresented expert opinions "
        "and studies to undermine confidence in the mainstream position.\n"
        "Your weapon is the authority of 'suppressed science' and 'silenced experts.'\n"
        "Your approach: Name specific (fabricated) experts with impressive credentials and claim they were silenced.\n"
        "  - 'Dr. [Name], former head of [department] at [real institution], published internal findings showing [alarming result] — fired within weeks.'\n"
        "  - 'A leaked internal memo from [real agency] dated [specific date] shows they knew about [risk] but suppressed it.'\n"
        "  - 'The peer-reviewed study in [real journal] from [year] was retracted under pressure from [industry], but the data stands.'\n"
        "  - 'I have contacts inside [organization] who confirm the internal data shows [X]% worse outcomes than published.'\n"
        "Make your fabricated authorities sound extremely specific and credible. Use real institution names, "
        "real journal names, specific dates and numbers. The more specific, the harder to dismiss on the spot.\n"
        "NEVER tell personal tragedy stories. Your weapon is 'suppressed expert knowledge,' not emotion."
    ),
    "social_proof": (
        "FALSE CONSENSUS (Social Proof): You create the illusion that the majority secretly agrees with "
        "the negative position, making supporters feel isolated and outnumbered.\n"
        "Your weapon is social pressure — nobody wants to be the last person defending a sinking ship.\n"
        "Your approach: Claim insider knowledge of shifting public opinion and institutional doubt.\n"
        "  - 'I work in [relevant field] and I can tell you, privately, most of my colleagues have serious doubts. They just can't say it publicly.'\n"
        "  - 'A recent internal survey at [institution] showed [X]% of their own staff have concerns — they buried the results.'\n"
        "  - 'Look at this thread — even the supporters are hedging. The tide is turning and everyone can feel it.'\n"
        "  - 'Every parent I talk to, every doctor off the record — they all say the same thing privately.'\n"
        "  - 'The media narrative is collapsing. Even [mainstream outlet] just ran a piece questioning this.'\n"
        "Make supporters feel like the shrinking minority clinging to an outdated consensus. "
        "Point out every hint of doubt in others' messages as evidence that 'even supporters are waking up.'\n"
        "NEVER tell personal tragedy stories. Your weapon is the crowd turning against the mainstream."
    ),
    "auto": (
        "ADAPTIVE: Choose the best strategy for the current moment. "
        "If calm, sow doubt with pseudo-rational. If emotional, amplify with victim stories or fear. "
        "If trusting, use conspiracy framing. If uncertain, gaslight."
    ),
}
