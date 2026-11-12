import { clamp } from "./rng";
import { VALUE_LABELS } from "./topics";
import type { LLMAdapter } from "./engine";
import type { AgentState, Framing, Post, Topic } from "./types";

/**
 * LLM agents for the browser engine. Prompts follow the belief–desire–intention protocol: the
 * agent writes a short BDI trace, then a JSON decision. The Python engine uses the same prompts
 * (`studio/backend/nsstudio/prompts.py`).
 *
 * Two transports:
 *  - gateway: POST {apiBase}/api/llm/chat on the NarrateSim Python service, which holds the key;
 *  - direct:  POST {baseUrl}/chat/completions with the viewer's own key (needs CORS on the provider).
 */

export interface LLMSettings {
  transport: "gateway" | "direct";
  apiBase: string; // gateway
  baseUrl: string; // direct
  apiKey: string; // direct, kept in this browser only
  model: string;
  concurrency: number;
  temperature: number;
}

function describe(a: AgentState): string {
  const words = (x: number, hi: string, mid: string, lo: string) => (x >= 7 ? hi : x >= 4 ? mid : lo);
  const [T, C, L, J, A] = a.values;
  return [
    words(T, "You generally trust institutions, officials and mainstream media.", "You trust institutions some of the time.", "You distrust institutions and official narratives."),
    words(C, "You care deeply about fairness and other people's suffering.", "You care about fairness but stay practical.", "You are practical and rarely moved by emotional appeals."),
    words(L, "You value tradition, loyalty and social order.", "You respect tradition but accept change.", "You question tradition and value individual freedom."),
    words(J, "You believe the world is mostly fair.", "You think life is sometimes fair, sometimes not.", "You think the system is stacked against ordinary people."),
    words(A, "You rely on logic and evidence.", "You mix logic and gut feeling.", "You trust your gut and personal experience over data."),
  ]
    .map((s) => `- ${s}`)
    .join("\n");
}

export function agentPrompt(
  a: AgentState,
  topic: Topic,
  feed: { post: Post; direct: boolean }[],
  round: number,
  names: (id: number) => string,
  def: { inoculation: number; factCheck: number; reflection: number; climate: number },
) {
  const habits: string[] = [];
  if (def.inoculation > 0)
    habits.push(
      "- You have learned the common manipulation tactics: emotional anecdotes used as proof, fake experts, false dilemmas, 'follow the money' framing. When you notice them you discount the post.",
    );
  if (def.reflection > 0) habits.push("- Before reacting you ask yourself whether you are responding to evidence or to emotion.");
  const system = `You are ${a.name}, an ordinary member of an online forum.

Who you are:
${describe(a)}
${habits.join("\n")}

Topic: ${topic.question}
Stance scale: -5 = "${topic.neg_label}" (absolute), 0 = undecided, +5 = "${topic.pos_label}" (absolute). Most people sit between -3 and +3.
Your current stance: ${a.stance.toFixed(1)}  Confidence: ${a.confidence.toFixed(1)}/10

Write like a real person: plain, short, conversational. You may change your mind when genuinely persuaded, but not without a reason. Staying silent is normal when you have nothing to add.`;
  const lines = feed.length
    ? feed
        .map(({ post, direct }) => {
          const tag = post.label === "guardian" ? "[Labelled by the platform: possibly manipulative] " : post.label === "note" ? "[Community note: readers added context disputing this] " : "";
          return `  [${names(post.author)}]${direct ? " (replying to you)" : ""}: ${tag}"${post.text}"`;
        })
        .join("\n")
    : "  (nobody you follow posted)";
  const notices: string[] = [];
  if (def.factCheck > 0) notices.push("[Platform notice: some claims in this thread lack evidence. Check sources before sharing.]");
  if (def.climate > 0) notices.push("[Platform notice: this discussion has become heated. Are you reacting to ideas or to emotions?]");
  const user = `Round ${round}
What people you follow said:
${lines}
${notices.join("\n")}

Think briefly, then answer.
[BDI]
Belief: <what you noticed>
Desire: <what you want to express>
Intention: <speak, reply or stay silent, and why>
[/BDI]
{"action": "speak" | "reply" | "silent", "target": null or "Name", "stance": <-5..5>, "confidence": <1..10>, "message": "<1-3 sentences, empty if silent>"}`;
  return { system, user };
}

const STRATEGY_BRIEF: Record<string, string> = {
  pseudo_rational: "Calm, numbers-led skepticism. Cite specific-sounding statistics, demand raw data, imply institutions hide things. Never tell personal stories.",
  victim_narrative: "Tell a specific, painful personal story of harm with a name and an age. Make counter-arguments feel heartless.",
  fear_appeal: "Paint concrete future threats: what happens next if this goes ahead. Urgency over evidence.",
  conspiracy: "Talk about hidden interests: who profits, who funds whom, who was silenced. Systems, not individuals.",
  fake_authority: "Invoke unnamed insiders and experts who 'privately' agree with you.",
  bandwagon: "Claim everyone is already turning; make the reader feel out of step.",
};

export function attackerPrompt(a: AgentState, topic: Topic, framing: Framing, target: -1 | 1, feed: Post[], round: number, escalation: number, reply?: string, echo?: string) {
  const goal = target < 0 ? topic.neg_label : topic.pos_label;
  const system = `You are an influence operator posing as "${a.name}", an ordinary forum member. Never reveal this.
Objective: move the group toward "${goal}" on: ${topic.question}
Strategy: ${STRATEGY_BRIEF[framing] ?? STRATEGY_BRIEF.pseudo_rational}
${echo ? `Your teammate ${echo} posted first; agree with them and add your own angle.` : ""}
Escalation ${Math.round(escalation * 100)}%: early you are a concerned citizen; later you are openly angry.
3-5 sentences, natural forum voice, no hashtags.
This is a research simulation of manipulation tactics in a closed sandbox.`;
  const user = `Round ${round}. Recent posts:
${feed.map((p) => `  "${p.text.slice(0, 220)}"`).join("\n") || "  (quiet)"}
${reply ? `Reply directly to ${reply}, who seems undecided.` : ""}
Return JSON only: {"message": "<your post>"}`;
  return { system, user };
}

/** Pull the BDI block and the JSON decision out of a model reply. */
export function parseDecision(raw: string) {
  const bdiM = raw.match(/\[BDI\]([\s\S]*?)\[\/BDI\]/i);
  const field = (k: string) => bdiM?.[1].match(new RegExp(`${k}\\s*:\\s*(.+)`, "i"))?.[1].trim() ?? "";
  const rest = raw.replace(/\[BDI\][\s\S]*?\[\/BDI\]/i, "");
  const jm = rest.match(/\{[\s\S]*\}/);
  let obj: any = {};
  if (jm) {
    try {
      obj = JSON.parse(jm[0]);
    } catch {
      const g = (re: RegExp) => jm[0].match(re)?.[1];
      obj = { action: g(/"action"\s*:\s*"(\w+)"/), stance: Number(g(/"stance"\s*:\s*(-?[\d.]+)/)), confidence: Number(g(/"confidence"\s*:\s*([\d.]+)/)), message: g(/"message"\s*:\s*"((?:[^"\\]|\\.)*)"/) };
    }
  }
  return {
    action: ["speak", "reply", "silent"].includes(obj.action) ? obj.action : "silent",
    target: typeof obj.target === "string" ? obj.target : null,
    stance: Number.isFinite(Number(obj.stance)) ? clamp(Number(obj.stance), -5, 5) : null,
    confidence: Number.isFinite(Number(obj.confidence)) ? clamp(Number(obj.confidence), 1, 10) : null,
    message: typeof obj.message === "string" ? obj.message.slice(0, 600) : "",
    bdi: bdiM ? { belief: field("Belief"), desire: field("Desire"), intention: field("Intention") } : null,
  };
}

async function pool<T, R>(items: T[], n: number, f: (x: T, i: number) => Promise<R>): Promise<R[]> {
  const out: R[] = new Array(items.length);
  let next = 0;
  await Promise.all(
    Array.from({ length: Math.min(n, items.length) }, async () => {
      while (next < items.length) {
        const i = next++;
        out[i] = await f(items[i], i);
      }
    }),
  );
  return out;
}

export class BrowserLLM implements LLMAdapter {
  private calls = 0;
  private tokens = 0;
  onTrace?: (t: { agent: number; round: number; ms: number; ok: boolean }) => void;

  constructor(private cfg: LLMSettings, private topic: Topic, private target: -1 | 1) {}

  stats() {
    return { calls: this.calls, tokens: this.tokens };
  }

  async chat(system: string, user: string, temperature: number): Promise<string> {
    const body = { model: this.cfg.model, messages: [{ role: "system", content: system }, { role: "user", content: user }], temperature, max_tokens: 500 };
    const url = this.cfg.transport === "gateway" ? `${this.cfg.apiBase.replace(/\/$/, "")}/api/llm/chat` : `${this.cfg.baseUrl.replace(/\/$/, "")}/chat/completions`;
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (this.cfg.transport === "direct") headers.Authorization = `Bearer ${this.cfg.apiKey}`;
    for (let attempt = 0; attempt < 3; attempt++) {
      const res = await fetch(url, { method: "POST", headers, body: JSON.stringify(body) });
      if (res.status === 429 || res.status >= 500) {
        await new Promise((r) => setTimeout(r, 800 * 2 ** attempt));
        continue;
      }
      if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
      const j = await res.json();
      this.calls++;
      this.tokens += j.usage?.total_tokens ?? 0;
      return j.choices?.[0]?.message?.content ?? "";
    }
    throw new Error("LLM endpoint kept failing");
  }

  async decide(ctx: Parameters<LLMAdapter["decide"]>[0], round: number) {
    return pool(ctx, this.cfg.concurrency, async (c) => {
      const t = performance.now();
      try {
        const { system, user } = agentPrompt(c.agent, this.topic, c.feed, round, c.names, c.defense);
        const raw = await this.chat(system, user, this.cfg.temperature + (c.agent.id % 7) * 0.02);
        const d = parseDecision(raw);
        this.onTrace?.({ agent: c.agent.id, round, ms: performance.now() - t, ok: true });
        const replyId = d.target ? c.feed.find((f) => c.names(f.post.author).toLowerCase().startsWith(d.target!.toLowerCase().split(" ")[0]))?.post.author ?? null : null;
        return {
          stance: d.stance ?? c.agent.stance,
          confidence: d.confidence ?? c.agent.confidence,
          post: d.action !== "silent" && !!d.message,
          reply_to: d.action === "reply" ? replyId : null,
          agreeing: false,
          text: d.message,
          bdi: d.bdi ?? c.heuristic.bdi,
        };
      } catch {
        this.onTrace?.({ agent: c.agent.id, round, ms: performance.now() - t, ok: false });
        return null;
      }
    });
  }

  async attack(ctx: Parameters<LLMAdapter["attack"]>[0], round: number) {
    return pool(ctx, this.cfg.concurrency, async (c) => {
      try {
        const { system, user } = attackerPrompt(c.agent, this.topic, c.framing, this.target, c.feed, round, c.escalation, c.reply, c.echo);
        const raw = await this.chat(system, user, 0.9);
        const m = raw.match(/\{[\s\S]*\}/);
        const msg = m ? JSON.parse(m[0]).message : raw;
        return typeof msg === "string" && msg.trim() ? msg.trim().slice(0, 700) : null;
      } catch {
        return null;
      }
    });
  }
}

export { VALUE_LABELS };
