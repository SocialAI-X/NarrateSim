import { useState } from "react";
import { toast } from "sonner";
import { CheckCircle2, CircleAlert, Plug } from "lucide-react";
import { BrowserLLM } from "@/engine/llm";
import { TOPICS } from "@/engine/topics";
import { defaultLLM, useLab } from "@/store";
import { Button, Field, Input, Segmented, Slider } from "@/components/ui";

export default function Settings() {
  const { llm, setLLM } = useLab();
  const [health, setHealth] = useState<null | { ok: boolean; text: string }>(null);
  const [test, setTest] = useState<null | { ok: boolean; text: string }>(null);
  const [busy, setBusy] = useState(false);

  const checkServer = async () => {
    try {
      const r = await fetch(`${llm.apiBase}/api/health`);
      const j = await r.json();
      setHealth({ ok: true, text: `NarrateSim ${j.version} · ${j.llm_configured ? `model ${j.model}` : "no LLM key on the server"}` });
    } catch (e) {
      setHealth({ ok: false, text: `Not reachable: ${(e as Error).message}` });
    }
  };
  const testModel = async () => {
    setBusy(true);
    try {
      const t0 = performance.now();
      const out = await new BrowserLLM(llm, TOPICS[0], -1).chat("You are a terse assistant.", 'Reply with the JSON {"ok": true} and nothing else.', 0);
      setTest({ ok: true, text: `${Math.round(performance.now() - t0)} ms · "${out.slice(0, 80)}"` });
    } catch (e) {
      setTest({ ok: false, text: (e as Error).message.slice(0, 240) });
    } finally {
      setBusy(false);
    }
  };

  const row = "grid gap-4 border-t border-border py-8 first:border-0 md:grid-cols-[minmax(0,380px)_minmax(0,1fr)]";
  return (
    <div className="mx-auto max-w-[1100px] px-5 py-6 lg:px-8">
      <h1 className="text-[24px] font-semibold">Settings</h1>
      <p className="mt-1 text-[14px] text-muted">How LLM agents are reached. The heuristic mind needs none of this.</p>

      <div className="mt-6">
        <section className={row}>
          <div>
            <h2 className="text-[16px] font-medium">Transport</h2>
            <p className="mt-1 text-[13px] leading-relaxed text-muted">
              The gateway is the NarrateSim Python service: it holds the key, pools requests and logs every call. Direct mode calls an OpenAI-compatible endpoint from this browser with your own key; it works only where the provider allows cross-origin requests.
            </p>
          </div>
          <div className="card grid gap-4 p-4">
            <Segmented value={llm.transport} onChange={(v) => setLLM({ transport: v })} options={[{ value: "gateway", label: "NarrateSim gateway" }, { value: "direct", label: "Direct, own key" }]} />
            {llm.transport === "gateway" ? (
              <>
                <Field label="Server address" hint="Leave empty when the studio is served by the server itself.">
                  <Input value={llm.apiBase} placeholder="http://localhost:8765" onChange={(e) => setLLM({ apiBase: e.target.value })} />
                </Field>
                <div className="flex items-center gap-3">
                  <Button size="sm" onClick={checkServer}>
                    <Plug className="h-3.5 w-3.5" /> Check server
                  </Button>
                  {health && (
                    <span className={`flex items-center gap-1.5 text-[12px] ${health.ok ? "text-soft" : "text-negative"}`}>
                      {health.ok ? <CheckCircle2 className="h-3.5 w-3.5 text-positive" /> : <CircleAlert className="h-3.5 w-3.5" />}
                      {health.text}
                    </span>
                  )}
                </div>
              </>
            ) : (
              <>
                <Field label="Base URL">
                  <Input value={llm.baseUrl} onChange={(e) => setLLM({ baseUrl: e.target.value })} />
                </Field>
                <Field label="API key" hint="Stored only in this browser's local storage. Never sent anywhere but the base URL above.">
                  <Input type="password" autoComplete="off" value={llm.apiKey} placeholder="sk-…" onChange={(e) => setLLM({ apiKey: e.target.value })} />
                </Field>
              </>
            )}
          </div>
        </section>

        <section className={row}>
          <div>
            <h2 className="text-[16px] font-medium">Model</h2>
            <p className="mt-1 text-[13px] leading-relaxed text-muted">Any chat model behind an OpenAI-compatible API: DeepSeek, OpenAI, or a local vLLM server.</p>
          </div>
          <div className="card grid gap-4 p-4">
            <Field label="Model name">
              <Input value={llm.model} onChange={(e) => setLLM({ model: e.target.value })} />
            </Field>
            <div className="grid gap-4 sm:grid-cols-2">
              <Slider label="Parallel requests" value={llm.concurrency} min={1} max={32} onChange={(v) => setLLM({ concurrency: v })} />
              <Slider label="Temperature" value={llm.temperature} min={0} max={1.4} step={0.05} format={(v) => v.toFixed(2)} onChange={(v) => setLLM({ temperature: v })} />
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <Button size="sm" variant="primary" onClick={testModel} disabled={busy}>
                {busy ? "Calling…" : "Send a test request"}
              </Button>
              <Button size="sm" variant="ghost" onClick={() => (setLLM(defaultLLM), toast("Settings reset"))}>
                Reset
              </Button>
              {test && <span className={`text-[12px] ${test.ok ? "text-soft" : "text-negative"}`}>{test.text}</span>}
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
