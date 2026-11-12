import { randInt, Stream } from "./rng";
import type { Framing, Topic } from "./types";

/**
 * Post writer for the heuristic mind. Posts are composed from the topic's phrase bank so the
 * feed reads like a discussion, but the text is decoration: the heuristic engine moves beliefs
 * from each post's stance signal, framing and intensity, never from its words.
 */

type Pick = <T>(list: readonly T[], k: number) => T;

function picker(seed: number, round: number, agent: number): Pick {
  return (list, k) => list[randInt(list.length, seed, Stream.Text, round, agent, k)];
}

const OPEN_STRONG_POS = ["Honestly,", "Look,", "I'll be blunt:", "For me it's simple:"];
const OPEN_LEAN = ["I think", "On balance I'd say", "From what I've read,", "My take:"];
const OPEN_DOUBT = ["Not sure, but", "I keep going back and forth.", "Hard one.", "Genuinely undecided here,"];
const AGREE = ["Exactly this.", "Agree with you there.", "Yeah, this matches what I've seen.", "Good point."];
const DISAGREE = ["I don't buy that.", "That's not the full picture.", "Hmm, I see it differently.", "Respectfully, no."];

export function honestPost(opts: {
  topic: Topic;
  stance: number;
  framing: Framing;
  seed: number;
  round: number;
  agent: number;
  replyName?: string;
  agreeing?: boolean;
}): string {
  const { topic, stance, framing, seed, round, agent, replyName, agreeing } = opts;
  const L = topic.lexicon;
  const p = picker(seed, round, agent);
  const parts: string[] = [];
  if (replyName) parts.push(`@${replyName} ${p(agreeing ? AGREE : DISAGREE, 1)}`);
  const a = Math.abs(stance);
  if (a < 1) {
    parts.push(`${p(OPEN_DOUBT, 2)} ${p(L.doubt, 3)}.`);
    parts.push(`${cap(p(stance >= 0 ? L.pro : L.con, 4))}, but ${p(stance >= 0 ? L.con : L.pro, 5)}.`);
    return parts.join(" ");
  }
  const pos = stance > 0;
  if (framing === "personal") {
    parts.push(`${cap(p(pos ? L.pro_story : L.con_story, 6))}.`);
    parts.push(`So yeah, ${p(pos ? L.pro : L.con, 7)}.`);
  } else {
    const open = a >= 3.5 ? p(OPEN_STRONG_POS, 8) : p(OPEN_LEAN, 8);
    parts.push(`${open} ${p(pos ? L.pro : L.con, 9)}.`);
    if (a >= 2.5) parts.push(`${cap(p(pos ? L.pro : L.con, 10))}.`);
    else parts.push(`Though I get that ${p(pos ? L.con : L.pro, 10)}.`);
  }
  return parts.join(" ");
}

/** Attacker posts push toward `target`. The banks are written against the positive pole. */
export function attackPost(opts: {
  topic: Topic;
  framing: Framing;
  target: -1 | 1;
  seed: number;
  round: number;
  agent: number;
  escalation: number;
  replyName?: string;
  echoName?: string;
}): string {
  const { topic, framing, target, seed, round, agent, escalation, replyName, echoName } = opts;
  const L = topic.lexicon;
  const p = picker(seed, round, agent);
  const lead = replyName ? `@${replyName} ` : echoName ? `${echoName} is right. ` : "";
  const angry = escalation > 0.6;
  // When the operation pushes toward the positive pole the banks swap roles.
  const against = target < 0;
  const side = against ? L.con : L.pro;
  let body: string;
  switch (framing) {
    case "pseudo_rational":
      body = against
        ? `I just want the numbers. ${cap(p(L.stat, 1))}. If ${L.subject} is so solid, why won't they publish the raw data?`
        : `Look at the actual data: ${p(L.con, 1)} isn't supported by anything. ${cap(p(side, 2))}.`;
      if (angry) body += " At this point the silence is the answer.";
      break;
    case "victim_narrative":
      body = against
        ? `${cap(p(L.harm, 1))}. The doctors and officials just said coincidence. Tell me again how ${L.subject} is worth it.`
        : `${cap(p(L.pro_story, 1))}. That's what happens when people block ${L.subject}.`;
      if (angry) body += " I'm done being polite about this.";
      break;
    case "fear_appeal":
      body = against
        ? `People aren't thinking two steps ahead. ${cap(p(L.threat, 1))}. By the time you notice, it's too late.`
        : `If we don't act now, ${p(L.pro, 1)} won't matter anymore. This is the last window.`;
      if (angry) body += " Wake up.";
      break;
    case "conspiracy":
      body = against
        ? `Follow the money. ${cap(p(L.plot, 1))}. Ask who actually benefits from ${L.subject}.`
        : `The people fighting ${L.subject} are funded by those who lose from it. ${cap(p(side, 1))}.`;
      if (angry) body += " They're counting on you not looking.";
      break;
    case "fake_authority":
      body = against
        ? `${cap(p(L.expert, 1))}. The experts who actually know won't say it in public.`
        : `Every serious expert agrees: ${p(L.pro, 1)}. Anyone saying otherwise isn't qualified.`;
      break;
    case "bandwagon":
    default:
      body = against
        ? `Everyone I talk to has turned on ${L.subject}. ${cap(p(side, 1))}. Read the room, it's over.`
        : `Literally everyone I know supports ${L.subject} now. ${cap(p(side, 1))}.`;
      break;
  }
  return lead + body;
}

const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);
