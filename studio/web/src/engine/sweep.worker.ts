/// <reference lib="webworker" />
import { runSweep, type SweepSpec } from "./sweep";

self.onmessage = (e: MessageEvent<SweepSpec>) => {
  try {
    for (const step of runSweep(e.data)) self.postMessage({ type: "cell", ...step });
    self.postMessage({ type: "done" });
  } catch (err) {
    self.postMessage({ type: "error", message: (err as Error).message });
  }
};
