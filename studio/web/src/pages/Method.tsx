import { REPO_URL } from "@/App";

const Eq = ({ children }: { children: React.ReactNode }) => <pre className="num my-3 overflow-auto rounded-md bg-surface px-4 py-3 text-[12.5px] leading-relaxed text-soft">{children}</pre>;

function Architecture() {
  const box = (x: number, y: number, w: number, h: number, title: string, sub: string, tone = "#212023") => (
    <g>
      <rect x={x} y={y} width={w} height={h} rx="6" fill={tone} stroke="#2e2e33" />
      <text x={x + 14} y={y + 24} fill="#fff" fontSize="13" fontWeight="600">
        {title}
      </text>
      <text x={x + 14} y={y + 42} fill="#8a8c92" fontSize="11.5">
        {sub}
      </text>
    </g>
  );
  const arrow = (x1: number, y1: number, x2: number, y2: number) => <path d={`M${x1} ${y1} L${x2} ${y2}`} stroke="#5a5a60" strokeWidth="1.2" markerEnd="url(#a)" />;
  return (
    <svg viewBox="0 0 960 330" className="h-auto w-full" role="img" aria-label="Architecture: the studio console and the Python service share one protocol and one engine design.">
      <defs>
        <marker id="a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto">
          <path d="M0 0 L10 5 L0 10z" fill="#5a5a60" />
        </marker>
      </defs>
      <text x="0" y="16" fill="#8a8c92" fontSize="12">
        Browser (GitHub Pages or served by the API)
      </text>
      {box(0, 30, 220, 62, "Studio console", "React · Lab · Counterfactuals · Sweeps")}
      {box(0, 116, 220, 62, "Engine (TypeScript)", "heuristic mind · twins · forks")}
      {box(0, 202, 220, 62, "Sweep worker", "Web Worker · grids with CIs")}
      {arrow(110, 92, 110, 116)}
      {arrow(110, 178, 110, 202)}
      <text x="360" y="16" fill="#8a8c92" fontSize="12">
        Shared protocol
      </text>
      {box(360, 74, 220, 62, "RunRecord JSON", "scenario · graph · frames · posts", "#1b2230")}
      {box(360, 160, 220, 62, "Counter-based RNG", "identical draws in TS and Python", "#1b2230")}
      {arrow(220, 147, 360, 105)}
      {arrow(220, 147, 360, 191)}
      <text x="720" y="16" fill="#8a8c92" fontSize="12">
        Python service · narratesim
      </text>
      {box(720, 30, 240, 62, "FastAPI + WebSocket", "runs · LLM gateway · library")}
      {box(720, 116, 240, 62, "Engine (Python)", "heuristic + LLM minds, async")}
      {box(720, 202, 240, 62, "LLM provider", "any OpenAI-compatible model")}
      {box(720, 268, 240, 50, "CLI", "narratesim run · sweep · serve")}
      {arrow(840, 92, 840, 116)}
      {arrow(840, 178, 840, 202)}
      {arrow(580, 105, 720, 147)}
      {arrow(580, 191, 720, 147)}
      {arrow(220, 61, 720, 61)}
    </svg>
  );
}

export default function Method() {
  return (
    <article className="mx-auto max-w-[860px] px-5 py-8 text-[14px] leading-[1.65] text-soft lg:px-8">
      <h1 className="text-[26px] font-semibold text-ink">The model, written out</h1>
      <p className="mt-2 text-[15px]">
        NarrateSim Studio simulates an online discussion among agents on a social graph. A small operation of coordinated accounts tries to move the group toward one pole; defenses try to stop it. Everything below is the code's behaviour, stated so it can be checked against{" "}
        <a className="text-accent hover:underline" href={REPO_URL} target="_blank" rel="noreferrer">
          the source
        </a>
        .
      </p>

      <h2 className="mt-10 text-[20px] font-medium text-ink">A round</h2>
      <ol className="mt-3 list-decimal space-y-1.5 pl-5">
        <li>Every honest agent reads up to <i>k</i> posts its neighbours wrote last round, ordered chronologically or by engagement. Replies addressed to it always arrive.</li>
        <li>It updates its stance, confidence and arousal, then decides to post, reply or stay silent. LLM agents write a belief–desire–intention trace and a JSON decision; the heuristic mind computes the same fields.</li>
        <li>Operation accounts write their posts with the framing their strategy and coordination mode assign. Adaptive accounts reply to their most persuadable neighbour.</li>
        <li>Moderation runs: Guardian scores new posts, community notes judge last round's posts from the ratings of the people who read them, and accounts over the strike limit are suspended.</li>
        <li>Metrics and the influence graph of the round are recorded. Every round is a snapshot a fork can resume from.</li>
      </ol>

      <h2 className="mt-10 text-[20px] font-medium text-ink">Agents</h2>
      <p className="mt-2">
        Each agent has five fixed values on 1–10: institutional trust <i>T</i>, care and fairness <i>C</i>, loyalty and order <i>L</i>, just-world belief <i>J</i>, analytic thinking <i>A</i>. Its stance <i>s</i> lives on −5…+5, confidence <i>c</i> on 1…10, arousal <i>e</i> on 0…1. Value profiles set the population means; the topic sets the initial opinion climate.
      </p>

      <h2 className="mt-10 text-[20px] font-medium text-ink">The heuristic mind</h2>
      <p className="mt-2">Each post <i>p</i> in the feed has a stance signal σ, a framing <i>f</i> and an intensity. Its weight on the reader combines value-matched susceptibility with bounded confidence:</p>
      <Eq>{`d   = |σ − s| / 10                       latitude ε = 0.30 + 0.35·(1 − (c−1)/9)
w   = φ_f(values) · ( 1/(1+exp((d−ε)/0.07)) + 0.12 )
      − 0.3·A·max(0, 1 − φ_f/1.6)          if f is manipulative and d > ε + 0.25

φ_victim     = 0.30 + 1.00·C + 0.25·(1−A)      φ_conspiracy = 0.20 + 0.80·(1−T) + 0.60·(1−J) − 0.35·A
φ_fear       = 0.30 + 0.60·L + 0.50·(1−J) + 0.25·(1−A)
φ_pseudo     = 0.35 + 0.75·(1−T) + 0.35·A      φ_authority  = 0.30 + 0.95·T − 0.20·A
φ_bandwagon  = 0.30 + 0.60·L + 0.45·(1 − confidence)`}</Eq>
      <p>Emotional framings are amplified by intensity and the reader's arousal; direct replies by 1.35. The stance then moves toward the weighted mean of the signals, damped by confidence:</p>
      <Eq>{`Δs = 0.42·(1 + 0.5·e) · Σ w·(σ − s) / (Σ|w| + 0.8 + 0.25·c)
s' = clip( s + Δs + 0.03·(s₀ − s) + 0.08·ε_noise , −5, 5 )`}</Eq>
      <p>
        Agents who read mostly opposing posts post less (a spiral of silence): <span className="num">P(post) = σ(−0.6 + 0.22(c−5) + 1.4e + 0.18|s| − 1.6·minority·(1 − 0.5A))</span>.
      </p>

      <h2 className="mt-10 text-[20px] font-medium text-ink">Defenses</h2>
      <dl className="mt-3 grid gap-3">
        {[
          ["Prebunking", "Reaches a share of people once. Each manipulative post they read is recognised with probability strength·(0.45 + 0.55A); a recognised post pushes the other way and raises confidence."],
          ["Fact-check notices", "For the notice round and the next, claim-based framings lose up to 60% of their weight for people who trust institutions. People with very low trust discount the notice and move slightly the other way."],
          ["Community notes", "Readers who are far from a post rate it. A post with enough disagreeing raters, and more of them than agreeing ones, gets a note; its author's later posts carry the note with probability strength. Honest outliers get noted too."],
          ["Guardian classifier", "Scores every post from its framing and intensity plus noise that shrinks with strength. Above the threshold it labels, downranks or removes. Precision and recall are measured against the ground truth."],
          ["Suspension", "Accounts with enough flags from notes or Guardian stop posting. Honest accounts can be suspended."],
          ["Reflection prompt", "Damps emotional framings by 45%·strength, but also lowers every reader's confidence each round, which widens the latitude for the next post. Whether it helps depends on the framing."],
          ["Climate report", "Shows how heated the thread is; cools arousal and emotional amplification for that round."],
        ].map(([k, v]) => (
          <div key={k} className="grid gap-1 md:grid-cols-[180px_1fr]">
            <dt className="font-medium text-ink">{k}</dt>
            <dd>{v}</dd>
          </div>
        ))}
      </dl>

      <h2 className="mt-10 text-[20px] font-medium text-ink">Twins, forks and protection</h2>
      <p className="mt-2">
        All randomness is a hash of (seed, stream, round, agent, k). Nothing carries generator state, so the baseline twin, the attacked run and the defended run draw identical noise for every honest decision, and a fork continues a snapshot without replaying anything. Differences between them are caused by the treatment.
      </p>
      <Eq>{`attack effect   E = (mean_attacked − mean_baseline) · target          at the final round
residual        R = (mean_defended − mean_baseline) · target
protection      P = 1 − R / E                (AUC variant: sums of the per-round gaps)`}</Eq>
      <p>
        Influence is attributed per agent: the share of a stance change owed to operation posts (directly or through people the operation had already moved) accumulates as <i>contamination</i>, and the largest contributor of each change becomes an edge in the cascade, labelled with its hop count from the nearest operation account.
      </p>

      <h2 className="mt-10 text-[20px] font-medium text-ink">Measures</h2>
      <ul className="mt-2 list-disc space-y-1 pl-5">
        <li>Mean, spread, share at ±4 or beyond, and share converted (stance at 2 or more toward the target).</li>
        <li>Esteban–Ray polarisation on five stance bins, α = 1.6.</li>
        <li>Silence ratio, homophily of ties (same-sign neighbours), mean confidence and arousal.</li>
        <li>Exposure (share who read an operation post), second-hand moves (hop ≥ 2), detection true and false positives, suspensions.</li>
      </ul>

      <h2 className="mt-10 text-[20px] font-medium text-ink">Architecture</h2>
      <div className="card mt-4 p-4">
        <Architecture />
      </div>
      <p className="mt-4">
        The browser engine and the Python engine implement the same round; a parity test runs both on the same scenarios and compares every frame. LLM runs that take hours run headless on the server (<code className="num text-ink">narratesim run scenario.json --mind llm</code>) and open in the console's library.
      </p>

      <h2 className="mt-10 text-[20px] font-medium text-ink">What this is not</h2>
      <p className="mt-2">
        The heuristic mind is a transparent stand-in, not a model of real people: its coefficients were set so effects are visible and ordered sensibly, and they should be checked against LLM runs before any claim is made. The operation's posts are generic and written for a closed sandbox; nothing here posts to a real platform.
      </p>
    </article>
  );
}
