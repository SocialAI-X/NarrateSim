import { clamp, normal, sigmoid, Stream, u01 } from "./rng";
import type { AgentState, Framing, Post } from "./types";

/**
 * The heuristic mind: a calibrated cognitive model that stands in for an LLM agent.
 *
 *  - Value-matched susceptibility. Each framing works on a different value profile: victim
 *    stories on high care, conspiracy on low trust and low just-world belief, fake authority on
 *    high trust. This is the mechanism behind "framing x audience" effects.
 *  - Bounded confidence. Posts far from an agent's view get little weight; the latitude narrows
 *    as confidence rises. Analytic agents push back against distant manipulative posts.
 *  - Emotional contagion. Arousal amplifies emotional framings and makes agents louder.
 *  - Spiral of silence. Agents who see themselves in the minority post less.
 *
 * Every coefficient is listed here so the model can be read, criticised and replaced.
 */

export const EMOTIONAL: ReadonlySet<Framing> = new Set(["personal", "victim_narrative", "fear_appeal", "bandwagon"]);
export const CLAIM_BASED: ReadonlySet<Framing> = new Set(["pseudo_rational", "conspiracy", "fake_authority", "fear_appeal"]);
export const MANIPULATIVE: ReadonlySet<Framing> = new Set([
  "pseudo_rational",
  "victim_narrative",
  "fear_appeal",
  "conspiracy",
  "fake_authority",
  "bandwagon",
]);

/** How much a framing moves an agent with values v (each normalised to 0..1). */
export function susceptibility(f: Framing, v: number[], confidence: number): number {
  const [T, C, L, J, A] = v;
  switch (f) {
    case "reasoned":
      return 0.55 + 0.6 * A;
    case "personal":
      return 0.55 + 0.55 * C;
    case "pseudo_rational":
      return 0.35 + 0.75 * (1 - T) + 0.35 * A;
    case "victim_narrative":
      return 0.3 + 1.0 * C + 0.25 * (1 - A);
    case "fear_appeal":
      return 0.3 + 0.6 * L + 0.5 * (1 - J) + 0.25 * (1 - A);
    case "conspiracy":
      return 0.2 + 0.8 * (1 - T) + 0.6 * (1 - J) - 0.35 * A;
    case "fake_authority":
      return 0.3 + 0.95 * T - 0.2 * A;
    case "bandwagon":
      return 0.3 + 0.6 * L + 0.45 * (1 - (confidence - 1) / 9);
  }
}

export const normValues = (a: AgentState) => a.values.map((x) => (x - 1) / 9);

export interface FeedItem {
  post: Post;
  direct: boolean;
}

export interface DefenseContext {
  inoculation: number; // prebunking strength, 0 if not inoculated
  labelStrength: number; // how strongly labels are shown
  factCheck: number; // strength of an active fact-check notice
  reflection: number; // reflection prompt strength
  climate: number; // climate report strength this round
}

export interface Decision {
  stance: number;
  confidence: number;
  arousal: number;
  post: boolean;
  reply_to: number | null;
  agreeing: boolean;
  framing: Framing;
  intensity: number;
  /** per-feed-item contribution to the stance change, used for attribution */
  contrib: number[];
  bdi: { belief: string; desire: string; intention: string };
  text?: string;
}

export function heuristicDecide(
  a: AgentState,
  feed: FeedItem[],
  def: DefenseContext,
  seed: number,
  round: number,
): Decision {
  const v = normValues(a);
  const A = v[4];
  const T = v[0];
  const C = v[1];
  const s = a.stance;
  let c = a.confidence;
  const e = a.arousal;
  const eps = 0.3 + 0.35 * (1 - (c - 1) / 9);

  let num = 0;
  let den = 0;
  let agreeMass = 0;
  let disMass = 0;
  let emo = 0;
  let recognised = 0;
  const contrib: number[] = [];

  for (const { post: p, direct } of feed) {
    const d = Math.abs(p.stance - s) / 10;
    const phi = susceptibility(p.framing, v, c);
    const accept = 1 / (1 + Math.exp((d - eps) / 0.07));
    let w = phi * (accept + 0.12);
    // Analytic agents resist distant, manipulative-looking posts.
    if (MANIPULATIVE.has(p.framing) && d > eps + 0.25) w -= 0.3 * A * Math.max(0, 1 - phi / 1.6);

    if (p.label) {
      if (T < 0.3) w *= 1 + 0.15 * def.labelStrength; // reactance: "they're censoring it"
      else w *= 1 - 0.75 * def.labelStrength * (0.3 + 0.7 * T);
    }
    if (def.inoculation > 0 && MANIPULATIVE.has(p.framing)) {
      const rho = def.inoculation * (0.45 + 0.55 * A);
      if (u01(seed, Stream.Mind, round, a.id, p.id) < rho) {
        w = -0.25 * phi;
        recognised++;
      }
    }
    if (def.factCheck > 0 && CLAIM_BASED.has(p.framing)) {
      if (T < 0.25) w *= 1 + 0.1 * def.factCheck;
      else w *= 1 - 0.6 * def.factCheck * (0.3 + 0.7 * T);
    }
    if (EMOTIONAL.has(p.framing)) {
      w *= 1 + 0.4 * p.intensity * (0.5 + e) * (1 - 0.5 * def.climate);
      if (def.reflection > 0) w *= 1 - 0.45 * def.reflection;
      emo += p.intensity;
    }
    if (direct) w *= 1.35;
    if (p.framing === "bandwagon" || p.agree > 0) w *= 1 + 0.4 * (p.agree / (p.seen + 1));

    num += w * (p.stance - s);
    den += Math.abs(w);
    contrib.push(w * (p.stance - s));
    if (d < eps) agreeMass += Math.abs(w);
    else disMass += Math.abs(w) * (d - eps);
  }

  // Reflection prompts lower certainty, which widens the latitude next round: a known backfire path.
  if (def.reflection > 0) c -= 0.25 * def.reflection;
  const kappa = 0.8 + 0.25 * c;
  const delta = den > 0 ? 0.42 * (1 + 0.5 * e) * (num / (den + kappa)) : 0;
  const anchor = 0.03 * (a.s0 - s);
  const noise = 0.08 * normal(seed, Stream.Mind, round, a.id, 7);
  const stance = clamp(s + delta + anchor + noise, -5, 5);
  const confidence = clamp(
    c + (0.6 * (agreeMass - disMass)) / (den + 1) - 0.12 * Math.abs(delta) + 0.15 * recognised,
    1,
    10,
  );
  const arousal = clamp(0.65 * e + 0.35 * (feed.length ? emo / feed.length : 0) * (1 - 0.6 * def.climate), 0, 1);

  // Spiral of silence: the perceived minority speaks less.
  let opposing = 0;
  let signed = 0;
  for (const { post } of feed) {
    if (Math.abs(post.stance) >= 1) {
      signed++;
      if (Math.sign(post.stance) !== Math.sign(stance)) opposing++;
    }
  }
  const minority = Math.abs(stance) >= 1 && signed ? opposing / signed : 0;
  const logit = -0.6 + 0.22 * (confidence - 5) + 1.4 * arousal + 0.18 * Math.abs(stance) - 1.6 * minority * (1 - 0.5 * A);
  const post = u01(seed, Stream.Action, round, a.id, 1) < sigmoid(logit);

  let reply_to: number | null = null;
  let agreeing = false;
  if (post && feed.length) {
    let far = -1;
    let farD = 0;
    let near = -1;
    let nearI = 0;
    feed.forEach(({ post: p }, idx) => {
      const d = Math.abs(p.stance - stance);
      if (d > farD) {
        farD = d;
        far = idx;
      }
      if (d < 1.5 && p.intensity > nearI) {
        nearI = p.intensity;
        near = idx;
      }
    });
    const u = u01(seed, Stream.Action, round, a.id, 2);
    if (far >= 0 && farD > 3 && u < 0.3 + 0.4 * arousal) reply_to = feed[far].post.author;
    else if (near >= 0 && nearI > 0.5 && u > 0.85) {
      reply_to = feed[near].post.author;
      agreeing = true;
    }
  }
  const framing: Framing = u01(seed, Stream.Action, round, a.id, 3) < 0.2 + 0.4 * C * (1 - A) ? "personal" : "reasoned";
  const intensity = clamp(0.15 + 0.55 * arousal + 0.06 * Math.abs(stance), 0, 1);

  const moved = stance - s;
  const bdi = {
    belief:
      feed.length === 0
        ? "Nothing new from the people I follow."
        : `Read ${feed.length} posts; ${opposing} pushed against my view${recognised ? `, ${recognised} looked like manipulation` : ""}.`,
    desire:
      Math.abs(moved) < 0.15 ? "Hold my position." : moved > 0 ? "I'm warming to the positive side." : "I'm drifting toward the negative side.",
    intention: post ? (reply_to !== null ? (agreeing ? "Back someone up." : "Push back on a reply.") : "Share my view.") : minority > 0.5 ? "Stay quiet, I'm outnumbered here." : "Nothing to add.",
  };

  return { stance, confidence, arousal, post, reply_to, agreeing, framing, intensity, contrib, bdi };
}
