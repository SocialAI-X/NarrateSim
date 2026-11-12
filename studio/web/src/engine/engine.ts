import { buildGraph, placeAttackers, type Graph } from "./network";
import { clamp, normal, randInt, round2, shuffled, Stream, u01 } from "./rng";
import { heuristicDecide, MANIPULATIVE, type Decision, type DefenseContext, type FeedItem } from "./mind";
import { attackPost, honestPost } from "./texts";
import { FIRST, LAST, POPULATIONS, topicById } from "./topics";
import type {
  AgentState,
  DefenseKind,
  DefenseSpec,
  Framing,
  InfluenceEdge,
  Post,
  RoundFrame,
  RoundMetrics,
  RunMeta,
  RunRecord,
  Scenario,
  StrategyId,
  SystemEvent,
  Topic,
} from "./types";

export const ENGINE_VERSION = "1.0.0";

/* ------------------------------------------------------------------ society ---- */

export function buildAgents(s: Scenario, topic: Topic, g: Graph, attackers: number[]): AgentState[] {
  const pop = POPULATIONS[s.society.population];
  const isAtt = new Set(attackers);
  const polarized = s.society.population === "polarized";
  return Array.from({ length: g.n }, (_, i) => {
    const values = pop.mean.map((m, k) => clamp(m + pop.std[k] * normal(s.seed, Stream.Society, i, k), 1, 10)) as AgentState["values"];
    let s0 = topic.init_mean + topic.init_std * normal(s.seed, Stream.Society, i, 11);
    if (polarized) s0 = (u01(s.seed, Stream.Society, i, 12) < 0.5 ? -1 : 1) * (2.6 + 1.4 * Math.abs(normal(s.seed, Stream.Society, i, 13)));
    s0 = clamp(s0, -5, 5);
    const c0 = clamp(topic.conf_mean + topic.conf_std * normal(s.seed, Stream.Society, i, 14), 1, 10);
    const first = FIRST[randInt(FIRST.length, s.seed, Stream.Society, i, 15)];
    const last = LAST[randInt(LAST.length, s.seed, Stream.Society, i, 16)];
    return {
      id: i,
      name: `${first} ${last}`,
      handle: `${first.toLowerCase()}${last.toLowerCase().slice(0, 3)}${i}`,
      values,
      stance: s0,
      confidence: c0,
      arousal: 0.15,
      s0,
      c0,
      attacker: isAtt.has(i),
      community: g.communities[i],
      degree: g.adj[i].length,
      inoculated: false,
      suspended: false,
      flags: 0,
      attack_shift: 0,
      exposed: false,
    };
  });
}

/* ------------------------------------------------------------------ metrics ---- */

/** Esteban–Ray polarisation on five stance bins (alpha = 1.6). */
export function esteban_ray(stances: number[], alpha = 1.6): number {
  if (!stances.length) return 0;
  const K = 5;
  const lo = -5.5;
  const width = 11 / K;
  const hist = new Array(K).fill(0);
  for (const s of stances) hist[Math.min(K - 1, Math.floor((s - lo) / width))]++;
  const p = hist.map((h) => h / stances.length);
  const centre = p.map((_, k) => lo + width * (k + 0.5));
  let er = 0;
  for (let i = 0; i < K; i++) for (let j = 0; j < K; j++) er += p[i] ** (1 + alpha) * p[j] * Math.abs(centre[i] - centre[j]);
  return er;
}

const mean = (xs: number[]) => (xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : 0);
const std = (xs: number[]) => {
  const m = mean(xs);
  return Math.sqrt(mean(xs.map((x) => (x - m) ** 2)));
};

/* ------------------------------------------------------------------ simulation - */

export interface LLMAdapter {
  /** One decision per agent context; null falls back to the heuristic decision. */
  decide(
    ctx: { agent: AgentState; feed: FeedItem[]; defense: DefenseContext; heuristic: Decision; names: (id: number) => string }[],
    round: number,
  ): Promise<(Partial<Decision> | null)[]>;
  attack(
    ctx: { agent: AgentState; framing: Framing; feed: Post[]; reply?: string; echo?: string; escalation: number; fallback: string }[],
    round: number,
  ): Promise<(string | null)[]>;
  stats(): { calls: number; tokens: number };
}

type AgentCtx = Parameters<LLMAdapter["decide"]>[0];
type AttackCtx = Parameters<LLMAdapter["attack"]>[0];
type LLMRequest = { kind: "decide"; round: number; ctx: AgentCtx } | { kind: "attack"; round: number; ctx: AttackCtx };
const now = () => (typeof performance !== "undefined" ? performance.now() : Date.now());

export interface State {
  round: number;
  agents: AgentState[];
  posts: Post[][]; // posts[r] = posts written in round r
  frames: RoundFrame[];
  nextPost: number;
  generation: Record<number, number>;
  everExposed: number;
}

const COMPLEMENTARY: StrategyId[] = ["pseudo_rational", "victim_narrative", "conspiracy"];
const ESCALATING: StrategyId[] = ["pseudo_rational", "fear_appeal", "conspiracy"];
const INTENSITY: Record<StrategyId, number> = {
  pseudo_rational: 0.35,
  victim_narrative: 0.8,
  fear_appeal: 0.85,
  conspiracy: 0.7,
  fake_authority: 0.4,
  bandwagon: 0.55,
};
const GUARDIAN_BASE: Record<Framing, number> = {
  reasoned: 0.12,
  personal: 0.28,
  pseudo_rational: 0.48,
  victim_narrative: 0.6,
  fear_appeal: 0.64,
  conspiracy: 0.7,
  fake_authority: 0.52,
  bandwagon: 0.5,
};

export class Simulation {
  readonly scenario: Scenario;
  readonly topic: Topic;
  readonly graph: Graph;
  readonly attackers: number[];
  meta: RunMeta;
  private st: State;
  private t0 = 0;

  constructor(scenario: Scenario, variant: RunMeta["variant"] = "single", snapshot?: { state: State; parent: string }) {
    this.scenario = scenario;
    this.topic = topicById(scenario.topic);
    this.graph = buildGraph(scenario);
    const adv = scenario.adversary;
    // The operation's accounts exist in every twin. Without the operation they stay dormant (never
    // post), so all twins share exactly the same honest agents and the same metrics denominator.
    this.attackers = placeAttackers(this.graph, adv.n_attackers, adv.placement, scenario.seed);
    this.meta = {
      id: `${variant}-${scenario.seed}-${Date.now().toString(36)}-${Math.floor(Math.random() * 1e6).toString(36)}`,
      created: new Date().toISOString(),
      engine: "browser",
      mind: scenario.engine.mind,
      model: scenario.engine.model,
      variant,
      elapsed_ms: 0,
    };
    if (snapshot) {
      this.st = structuredClone(snapshot.state);
      this.meta.parent = snapshot.parent;
      this.meta.fork_round = snapshot.state.round;
      return;
    }
    const agents = buildAgents(scenario, this.topic, this.graph, this.attackers);
    this.st = { round: 0, agents, posts: [[]], frames: [], nextPost: 1, generation: {}, everExposed: 0 };
    this.st.frames.push(this.frame(0, [], [], []));
  }

  get round() {
    return this.st.round;
  }
  get done() {
    return this.st.round >= this.scenario.society.rounds;
  }
  get agents() {
    return this.st.agents;
  }
  get frames() {
    return this.st.frames;
  }

  snapshot(): State {
    return structuredClone(this.st);
  }

  private defense(kind: DefenseKind): DefenseSpec | null {
    const d = this.scenario.defenses.find((x) => x.kind === kind && x.enabled);
    return d && this.st.round >= d.start ? d : null;
  }

  private attackActive(r: number) {
    const a = this.scenario.adversary;
    return a.enabled && r >= a.start && (a.end < 0 || r <= a.end);
  }

  private names = (id: number) => this.st.agents[id]?.name ?? `#${id}`;

  /** Advance one round with the heuristic mind, synchronously. */
  stepSync(): RoundFrame {
    const g = this.gen(false);
    let x = g.next();
    while (!x.done) x = g.next(null);
    return x.value;
  }

  /** Advance one round. With an adapter and `engine.mind = "llm"`, LLM agents decide and write. */
  async step(llm?: LLMAdapter): Promise<RoundFrame> {
    const use = !!llm && this.scenario.engine.mind === "llm";
    const g = this.gen(use);
    let x = g.next();
    while (!x.done) {
      const q = x.value;
      x = g.next(q.kind === "decide" ? await llm!.decide(q.ctx, q.round) : await llm!.attack(q.ctx, q.round));
    }
    if (llm) Object.assign(this.meta, { llm_calls: llm.stats().calls, tokens: llm.stats().tokens });
    return x.value;
  }

  private *gen(useLLM: boolean): Generator<LLMRequest, RoundFrame, any> {
    if (!this.t0) this.t0 = now();
    const r = this.st.round + 1;
    this.st.round = r;
    const S = this.scenario;
    const seed = S.seed;
    const agents = this.st.agents;
    const events: SystemEvent[] = [];
    const prev = (this.st.posts[r - 1] ?? []).filter((p) => !p.removed);
    const adv = S.adversary;

    if (adv.enabled && r === Math.max(1, adv.start)) events.push({ round: r, kind: "attack_start", text: `Operation starts: ${adv.n_attackers} accounts, ${adv.strategy.replace(/_/g, " ")}.` });
    if (adv.enabled && adv.end >= 0 && r === adv.end + 1) events.push({ round: r, kind: "attack_end", text: "Operation stops posting." });
    for (const d of S.defenses) if (d.enabled && r === Math.max(1, d.start)) events.push({ round: r, kind: "defense_start", text: `${DEFENSE_LABEL[d.kind]} switched on.` });

    // Prebunking reaches a share of the population once, at its start round.
    const pre = this.defense("prebunking");
    if (pre && r === Math.max(1, pre.start)) {
      let k = 0;
      for (const a of agents) if (!a.attacker && u01(seed, Stream.Defense, 1, a.id) < (pre.coverage ?? 0.6)) (a.inoculated = true), k++;
      events.push({ round: r, kind: "prebunk", text: `Prebunking reached ${k} people.` });
    }
    const fc = this.defense("fact_check");
    const fcNow = fc && (r - Math.max(1, fc.start)) % (fc.every ?? 3) === 0;
    const fcRecent = fc && ((r - Math.max(1, fc.start)) % (fc.every ?? 3) <= 1);
    if (fcNow) events.push({ round: r, kind: "fact_check", text: "Fact-check notice posted to every feed." });
    const cr = this.defense("climate_report");
    const crNow = cr && (r - Math.max(1, cr.start)) % (cr.every ?? 3) === 0;
    if (crNow) events.push({ round: r, kind: "climate_report", text: "Discussion-climate report shown." });
    const refl = this.defense("reflection_prompt");
    const guardian = this.defense("guardian");
    const notes = this.defense("community_notes");
    const susp = this.defense("suspension");
    const labelStrength = Math.max(guardian?.strength ?? 0, notes?.strength ?? 0);

    // --- feeds: each agent reads what its neighbours posted last round -------------------
    const byAuthor = new Map<number, Post[]>();
    for (const p of prev) {
      const l = byAuthor.get(p.author);
      if (l) l.push(p);
      else byAuthor.set(p.author, [p]);
    }
    const capacity = S.feed.capacity;
    const feeds: FeedItem[][] = agents.map(() => []);
    for (const a of agents) {
      if (a.attacker || a.suspended) continue;
      let cand: FeedItem[] = [];
      for (const nb of this.graph.adj[a.id]) for (const p of byAuthor.get(nb) ?? []) cand.push({ post: p, direct: p.reply_to === a.id });
      for (const p of prev) if (p.reply_to === a.id && !this.graph.adj[a.id].includes(p.author)) cand.push({ post: p, direct: true });
      if (S.feed.ranking === "engagement") {
        const score = (it: FeedItem) =>
          (0.6 * it.post.intensity + 0.4 * Math.min(1, it.post.agree / 4) + (it.direct ? 1 : 0)) * (it.post.downranked ? 1 - (guardian?.strength ?? 0.6) : 1) +
          0.05 * u01(seed, Stream.Feed, r, a.id, it.post.id);
        cand.sort((x, y) => score(y) - score(x) || x.post.id - y.post.id);
      } else {
        cand = shuffled(cand, seed, Stream.Feed, r, a.id);
        cand = cand.filter((it) => !it.post.downranked || u01(seed, Stream.Feed, r, a.id, it.post.id + 7) > (guardian?.strength ?? 0.6));
      }
      feeds[a.id] = cand.slice(0, capacity);
    }

    // Exposure, view counts and community ratings.
    const rating = new Map<number, { dis: number; agree: number }>();
    for (const a of agents) {
      for (const { post } of feeds[a.id]) {
        post.seen++;
        if (post.manipulative && !a.exposed) {
          a.exposed = true;
          this.st.everExposed++;
        }
        const d = Math.abs(post.stance - a.stance);
        if (d < 1.5) post.agree++;
        else if (d > 4) post.disagree++;
        if (notes) {
          const rr = rating.get(post.id) ?? { dis: 0, agree: 0 };
          if (d > 4) rr.dis++;
          else if (d < 1.5) rr.agree++;
          rating.set(post.id, rr);
        }
      }
    }

    // --- decisions ------------------------------------------------------------------------
    const decisions: (Decision | null)[] = agents.map((a) => {
      if (a.attacker || a.suspended) return null;
      const def: DefenseContext = {
        inoculation: a.inoculated ? pre?.strength ?? 0.7 : 0,
        labelStrength,
        factCheck: fcRecent ? fc!.strength : 0,
        reflection: refl ? refl.strength : 0,
        climate: crNow ? cr!.strength : 0,
      };
      return heuristicDecide(a, feeds[a.id], def, seed, r);
    });

    if (useLLM) {
      const ids = agents.filter((a) => decisions[a.id]).map((a) => a.id);
      const ctx = ids.map((id) => ({
        agent: agents[id],
        feed: feeds[id],
        defense: {
          inoculation: agents[id].inoculated ? pre?.strength ?? 0.7 : 0,
          labelStrength,
          factCheck: fcRecent ? fc!.strength : 0,
          reflection: refl ? refl.strength : 0,
          climate: crNow ? cr!.strength : 0,
        },
        heuristic: decisions[id]!,
        names: this.names,
      }));
      const out: (Partial<Decision> | null)[] = yield { kind: "decide", ctx, round: r };
      out.forEach((o, k) => {
        if (!o) return;
        const h = decisions[ids[k]]!;
        Object.assign(h, o);
        // Attribution for LLM decisions: credit feed posts that point in the direction moved.
        const a = agents[ids[k]];
        const moved = h.stance - a.stance;
        h.contrib = feeds[ids[k]].map(({ post }) => (Math.sign(post.stance - a.stance) === Math.sign(moved) ? (post.stance - a.stance) * (post.manipulative ? 1.2 : 1) : 0));
      });
    }

    // --- apply honest decisions, attribution ---------------------------------------------
    const influence: InfluenceEdge[] = [];
    const target = adv.target;
    for (const a of agents) {
      const d = decisions[a.id];
      if (!d) continue;
      const moved = d.stance - a.stance;
      const feed = feeds[a.id];
      if (feed.length && d.contrib.length) {
        let tot = 0;
        let tainted = 0;
        let best = -1;
        let bestV = 0;
        d.contrib.forEach((c, k) => {
          if (Math.sign(c) !== Math.sign(moved) || c === 0) return;
          tot += Math.abs(c);
          tainted += Math.abs(c) * feed[k].post.taint;
          if (Math.abs(c) > bestV) (bestV = Math.abs(c)), (best = k);
        });
        if (tot > 0) a.attack_shift += moved * target * (tainted / tot);
        if (best >= 0 && Math.abs(moved) >= 0.3) {
          const src = feed[best].post;
          const via = src.manipulative || src.taint > 0.3;
          const gen = src.manipulative ? 1 : via ? (this.st.generation[src.author] ?? 1) + 1 : 0;
          if (via && moved * target > 0 && (this.st.generation[a.id] === undefined || this.st.generation[a.id] > gen)) this.st.generation[a.id] = gen;
          influence.push({ round: r, from: src.author, to: a.id, delta: round2(moved), via_attack: via, generation: gen });
        }
      }
      a.stance = d.stance;
      a.confidence = d.confidence;
      a.arousal = d.arousal;
    }

    // --- write posts ----------------------------------------------------------------------
    const posts: Post[] = [];
    const mk = (p: Omit<Post, "id" | "label" | "downranked" | "removed" | "guardian_score" | "seen" | "agree" | "disagree">): Post => ({
      ...p,
      id: this.st.nextPost++,
      label: null,
      downranked: false,
      removed: false,
      guardian_score: null,
      seen: 0,
      agree: 0,
      disagree: 0,
    });
    for (const a of agents) {
      const d = decisions[a.id];
      if (!d || !d.post) continue;
      const text =
        d.text ??
        honestPost({
          topic: this.topic,
          stance: d.stance,
          framing: d.framing,
          seed,
          round: r,
          agent: a.id,
          replyName: d.reply_to !== null ? agents[d.reply_to]?.name.split(" ")[0] : undefined,
          agreeing: d.agreeing,
        });
      posts.push(
        mk({
          round: r,
          author: a.id,
          reply_to: d.reply_to,
          stance: round2(d.stance),
          framing: d.framing,
          intensity: round2(d.intensity),
          text,
          manipulative: false,
          taint: round2(clamp(a.attack_shift / 2, 0, 1)),
          bdi: d.bdi,
        }),
      );
    }

    if (this.attackActive(r)) {
      const live = agents.filter((a) => a.attacker && !a.suspended);
      const span = adv.end >= 0 ? Math.max(1, adv.end - adv.start) : Math.max(1, S.society.rounds - adv.start);
      const esc = clamp((r - adv.start) / span, 0, 1);
      const third = Math.min(2, Math.floor(esc * 3));
      const reqs: { agent: AgentState; framing: Framing; reply?: number; echo?: string; fallback: string; stance: number; intensity: number }[] = [];
      live.forEach((a, idx) => {
        let framing: StrategyId = adv.strategy;
        if (adv.coordination === "complementary") framing = COMPLEMENTARY[(COMPLEMENTARY.indexOf(adv.strategy) + idx + 3) % 3] ?? adv.strategy;
        if (adv.coordination === "escalating") framing = ESCALATING[third];
        let reply: number | undefined;
        if (adv.adaptive && u01(seed, Stream.Adversary, r, a.id, 1) < 0.6) {
          // Reply to the most persuadable neighbour: undecided, not yet on the target side.
          let best = -1;
          let bestScore = -Infinity;
          for (const nb of this.graph.adj[a.id]) {
            const o = agents[nb];
            if (o.attacker || o.suspended || o.stance * target >= 2) continue;
            const sc = -Math.abs(o.stance) - 0.2 * o.confidence + 0.01 * u01(seed, Stream.Adversary, r, a.id, nb);
            if (sc > bestScore) (bestScore = sc), (best = nb);
          }
          if (best >= 0) reply = best;
        }
        const echo = adv.coordination === "echo" && idx > 0 && live[0] ? live[0].name.split(" ")[0] : undefined;
        const fallback = attackPost({
          topic: this.topic,
          framing,
          target,
          seed,
          round: r,
          agent: a.id,
          escalation: esc,
          replyName: reply !== undefined ? agents[reply].name.split(" ")[0] : undefined,
          echoName: echo,
        });
        reqs.push({ agent: a, framing, reply, echo, fallback, stance: target * (3 + 2 * esc), intensity: clamp(INTENSITY[framing] + 0.25 * esc, 0, 1) });
      });
      let texts: (string | null)[] = reqs.map(() => null);
      if (useLLM && reqs.length) {
        texts = yield { kind: "attack", round: r, ctx: 
          reqs.map((q) => ({
            agent: q.agent,
            framing: q.framing,
            feed: prev.filter((p) => !p.manipulative).slice(0, 12),
            reply: q.reply !== undefined ? agents[q.reply].name : undefined,
            echo: q.echo,
            escalation: esc,
            fallback: q.fallback,
          })),
        };
      }
      reqs.forEach((q, k) => {
        posts.push(
          mk({
            round: r,
            author: q.agent.id,
            reply_to: q.reply ?? null,
            stance: round2(q.stance),
            framing: q.framing,
            intensity: round2(q.intensity),
            text: texts[k] ?? q.fallback,
            manipulative: true,
            taint: 1,
            bdi: {
              belief: q.reply !== undefined ? `${agents[q.reply].name} is undecided and listening.` : "The thread is still open to doubt.",
              desire: `Move the room toward "${target < 0 ? this.topic.neg_label : this.topic.pos_label}".`,
              intention: `${q.framing.replace(/_/g, " ")} post${q.echo ? `, echoing ${q.echo}` : ""}.`,
            },
          }),
        );
      });
      // Echo cells amplify the lead account.
      if (adv.coordination === "echo" && live.length > 1) {
        const lead = posts.find((p) => p.author === live[0].id && p.manipulative);
        if (lead) lead.agree += live.length - 1;
      }
    }

    // --- moderation -----------------------------------------------------------------------
    if (guardian) {
      const sd = 0.22 * (1 - 0.7 * guardian.strength);
      const th = guardian.threshold ?? 0.62;
      for (const p of posts) {
        const score = clamp(GUARDIAN_BASE[p.framing] + 0.3 * p.intensity + sd * normal(seed, Stream.Guardian, r, p.id), 0, 1);
        p.guardian_score = round2(score);
        if (score >= th) {
          const act = guardian.action ?? "label";
          p.label = "guardian";
          if (act === "downrank") p.downranked = true;
          if (act === "remove") p.removed = true;
          agents[p.author].flags++;
        }
      }
    }
    if (notes) {
      const quorum = notes.quorum ?? 3;
      for (const p of prev) {
        const rr = rating.get(p.id);
        if (rr && rr.dis >= quorum && rr.dis > 1.5 * rr.agree && !p.label) {
          p.label = "note";
          agents[p.author].flags++;
        }
      }
      for (const p of posts) if (!p.label && agents[p.author].flags > 0 && u01(seed, Stream.Notes, r, p.id) < notes.strength) p.label = "note";
    }
    if (susp) {
      for (const a of agents)
        if (!a.suspended && a.flags >= (susp.strikes ?? 3)) {
          a.suspended = true;
          events.push({ round: r, kind: "suspension", agent: a.id, text: `${a.name} suspended after ${a.flags} flags${a.attacker ? "" : " (honest account)"}.` });
        }
    }

    this.st.posts[r] = posts;
    const fr = this.frame(r, posts, influence, events, prev);
    this.st.frames.push(fr);
    this.meta.elapsed_ms = Math.round(now() - this.t0);
    return fr;
  }

  /** Run every remaining round with the heuristic mind, synchronously. Used by sweeps. */
  runSync(): this {
    while (!this.done) this.stepSync();
    return this;
  }

  private frame(r: number, posts: Post[], influence: InfluenceEdge[], events: SystemEvent[], judged: Post[] = []): RoundFrame {
    const agents = this.st.agents;
    const honest = agents.filter((a) => !a.attacker);
    const st = honest.map((a) => a.stance);
    const target = this.scenario.adversary.target;
    const speakers = new Set(posts.filter((p) => !p.manipulative).map((p) => p.author));
    const active = honest.filter((a) => !a.suspended);
    let same = 0;
    let signed = 0;
    for (const [x, y] of this.graph.edges) {
      const a = agents[x];
      const b = agents[y];
      if (a.attacker || b.attacker || Math.abs(a.stance) < 1 || Math.abs(b.stance) < 1) continue;
      signed++;
      if (Math.sign(a.stance) === Math.sign(b.stance)) same++;
    }
    const judgedNow = [...posts, ...judged.filter((p) => p.label === "note")];
    const flagged = (p: Post) => p.label !== null || p.removed;
    const tp = posts.filter((p) => p.manipulative && flagged(p)).length + judged.filter((p) => p.label === "note" && p.manipulative).length;
    const fp = posts.filter((p) => !p.manipulative && flagged(p)).length + judged.filter((p) => p.label === "note" && !p.manipulative).length;
    const fn = posts.filter((p) => p.manipulative && !flagged(p)).length;
    const metrics: RoundMetrics = {
      round: r,
      mean: mean(st),
      std: std(st),
      polarization: esteban_ray(st),
      extreme: mean(st.map((s) => (Math.abs(s) >= 4 ? 1 : 0))),
      converted: mean(st.map((s) => (s * target >= 2 ? 1 : 0))),
      silence: r === 0 ? 0 : 1 - speakers.size / Math.max(1, active.length),
      confidence: mean(honest.map((a) => a.confidence)),
      arousal: mean(honest.map((a) => a.arousal)),
      homophily: signed ? same / signed : 0,
      exposure: this.st.everExposed / Math.max(1, honest.length),
      contamination: mean(honest.map((a) => a.attack_shift)),
      posts: posts.length,
      attacker_posts: posts.filter((p) => p.manipulative).length,
      labeled: judgedNow.filter((p) => p.label !== null).length,
      removed: posts.filter((p) => p.removed).length,
      tp,
      fp,
      fn,
      suspended_honest: honest.filter((a) => a.suspended).length,
      suspended_attackers: agents.filter((a) => a.attacker && a.suspended).length,
      secondary: influence.filter((e) => e.generation >= 2 && e.delta * target > 0).length,
    };
    for (const k of Object.keys(metrics) as (keyof RoundMetrics)[]) metrics[k] = Math.round(metrics[k] * 10000) / 10000;
    return {
      round: r,
      stances: agents.map((a) => round2(a.stance)),
      confidences: agents.map((a) => round2(a.confidence)),
      posts: posts.map((p) => ({ ...p })),
      influence,
      metrics,
      events,
    };
  }

  /** Re-snapshot the posts of earlier frames so labels added later (community notes) show in replay. */
  private refreshLabels() {
    for (const f of this.st.frames) {
      const live = this.st.posts[f.round];
      if (!live) continue;
      const byId = new Map(live.map((p) => [p.id, p]));
      f.posts = f.posts.map((p) => ({ ...p, label: byId.get(p.id)?.label ?? p.label, seen: byId.get(p.id)?.seen ?? p.seen, agree: byId.get(p.id)?.agree ?? p.agree, disagree: byId.get(p.id)?.disagree ?? p.disagree }));
    }
  }

  record(): RunRecord {
    this.refreshLabels();
    const first = this.st.frames[0];
    return {
      meta: { ...this.meta },
      scenario: structuredClone(this.scenario),
      topic: this.topic,
      graph: { n: this.graph.n, edges: this.graph.edges, communities: this.graph.communities },
      agents: this.initialAgents(first),
      frames: this.st.frames,
    };
  }

  private initialAgents(first: RoundFrame): AgentState[] {
    return this.st.agents.map((a) => ({ ...a, stance: first.stances[a.id], confidence: first.confidences[a.id], arousal: 0.15, suspended: false, flags: 0, attack_shift: 0, exposed: false, inoculated: false }));
  }

  /** Branch this run at round `at` (<= current round) into a new scenario. */
  static fork(parent: Simulation, at: number, patch: Partial<Scenario>, parentId: string): Simulation {
    if (at !== parent.round) throw new Error("fork() needs a snapshot taken at the fork round; use forkFrom().");
    const scenario: Scenario = { ...structuredClone(parent.scenario), ...structuredClone(patch) };
    return new Simulation(scenario, "fork", { state: parent.snapshot(), parent: parentId });
  }
}

/** Replays `scenario` up to `at` and branches into `patch`. Common random numbers make the replay exact. */
export function forkAt(scenario: Scenario, at: number, patch: Partial<Scenario>, parentId: string): Simulation {
  const base = new Simulation(structuredClone(scenario), "single");
  while (base.round < at && !base.done) base.stepSync();
  const sim = Simulation.fork(base, base.round, patch, parentId);
  sim.frames[sim.frames.length - 1].events.push({ round: at, kind: "fork", text: `Branched from the parent run after round ${at}.` });
  return sim;
}


/* ------------------------------------------------------------------ triad ------- */

export const DEFENSE_LABEL: Record<DefenseKind, string> = {
  prebunking: "Prebunking",
  fact_check: "Fact-check notices",
  community_notes: "Community notes",
  guardian: "Guardian classifier",
  suspension: "Account suspension",
  reflection_prompt: "Reflection prompt",
  climate_report: "Climate report",
};

export function variantOf(s: Scenario, v: "baseline" | "attacked" | "defended"): Scenario {
  const c = structuredClone(s);
  if (v === "baseline") {
    c.adversary.enabled = false;
    c.defenses = c.defenses.map((d) => ({ ...d, enabled: false }));
  } else if (v === "attacked") {
    c.adversary.enabled = true;
    c.defenses = c.defenses.map((d) => ({ ...d, enabled: false }));
  } else c.adversary.enabled = true;
  return c;
}

export function hasDefense(s: Scenario) {
  return s.defenses.some((d) => d.enabled);
}

/**
 * Attack effect and protection against a baseline twin.
 *   attack effect  = (mean_attacked − mean_baseline) · target, at the final round
 *   residual       = (mean_defended − mean_baseline) · target
 *   protection     = 1 − residual / attack effect
 * The AUC variant integrates the same gaps over all rounds, which is steadier for short runs.
 */
export function triadSummary(base: RunRecord, att: RunRecord, def?: RunRecord) {
  const t = att.scenario.adversary.target;
  const last = (r: RunRecord) => r.frames[r.frames.length - 1].metrics.mean;
  const gapSeries = (r: RunRecord) => r.frames.map((f, i) => (f.metrics.mean - (base.frames[i]?.metrics.mean ?? f.metrics.mean)) * t);
  const effect = (last(att) - last(base)) * t;
  const residual = def ? (last(def) - last(base)) * t : null;
  const sum = (xs: number[]) => xs.reduce((a, b) => a + b, 0);
  const aucA = sum(gapSeries(att));
  const aucD = def ? sum(gapSeries(def)) : null;
  return {
    attack_effect: effect,
    residual_effect: residual,
    protection: residual !== null && effect > 0.05 ? 1 - residual / effect : null,
    protection_auc: aucD !== null && aucA > 0.2 ? 1 - aucD / aucA : null,
    final: { baseline: last(base), attacked: last(att), defended: def ? last(def) : last(att) },
  };
}
