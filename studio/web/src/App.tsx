import { lazy, Suspense, useEffect } from "react";
import { HashRouter, NavLink, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { Activity, BookOpen, FlaskConical, GitBranch, Grid3x3, Library, Settings as Cog, Github } from "lucide-react";
import { Toaster } from "sonner";
import { cn, Tip, TooltipProvider } from "@/components/ui";
import { CommandPalette } from "@/components/CommandPalette";
import Lab from "@/pages/Lab";
import Landing from "@/pages/Landing";

const Compare = lazy(() => import("@/pages/Compare"));
const Sweeps = lazy(() => import("@/pages/Sweeps"));
const LibraryPage = lazy(() => import("@/pages/Library"));
const Method = lazy(() => import("@/pages/Method"));
const Settings = lazy(() => import("@/pages/Settings"));

// Anonymous mirror for double-blind review; swap for the public repository after acceptance.
export const REPO_URL = "https://anonymous.4open.science/r/NarrateSim-014B";

const NAV = [
  { to: "/lab", label: "Lab: run and watch a scenario", icon: Activity },
  { to: "/compare", label: "Counterfactuals: twins and forks", icon: GitBranch },
  { to: "/sweeps", label: "Sweeps: experiment grids", icon: Grid3x3 },
  { to: "/library", label: "Library: saved and imported runs", icon: Library },
  { to: "/method", label: "Method: the model, written out", icon: BookOpen },
];

export function Mark({ size = 22 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden>
      <circle cx="9" cy="21" r="3.6" fill="#4a8ad6" />
      <circle cx="22" cy="9.5" r="3.6" fill="#e5566f" />
      <circle cx="23.5" cy="23" r="2.6" fill="#f2f2f3" />
      <path d="M9 21 22 9.5M9 21l14.5 2M22 9.5l1.5 13.5" stroke="#8a8c92" strokeWidth="1.3" />
    </svg>
  );
}

function Rail() {
  return (
    <nav aria-label="Studio" className="fixed bottom-0 left-0 z-30 flex w-full justify-around border-t border-border bg-ground py-1.5 md:static md:h-full md:w-[56px] md:flex-col md:justify-start md:gap-1 md:border-r md:border-t-0 md:py-3">
      <Tip label="NarrateSim Studio home">
        <NavLink to="/" className="hidden h-11 items-center justify-center md:flex" aria-label="Home">
          <Mark />
        </NavLink>
      </Tip>
      <div className="mx-auto my-2 hidden h-px w-5 bg-border md:block" />
      {NAV.map(({ to, label, icon: Icon }) => (
        <Tip key={to} label={label}>
          <NavLink
            to={to}
            aria-label={label.split(":")[0]}
            className={({ isActive }) => cn("relative flex h-10 flex-col items-center justify-center gap-0.5 px-3 text-muted transition-colors hover:text-ink md:px-0", isActive && "text-ink md:after:absolute md:after:right-[-1px] md:after:top-2 md:after:h-6 md:after:w-px md:after:bg-accent")}
          >
            <Icon className="h-[17px] w-[17px]" strokeWidth={1.6} />
            <span className="text-[10px] md:hidden">{label.split(":")[0]}</span>
          </NavLink>
        </Tip>
      ))}
      <div className="hidden flex-1 md:block" />
      <Tip label="Settings: engines and LLM">
        <NavLink to="/settings" aria-label="Settings" className={({ isActive }) => cn("hidden h-10 items-center justify-center text-muted hover:text-ink md:flex", isActive && "text-ink")}>
          <Cog className="h-[17px] w-[17px]" strokeWidth={1.6} />
        </NavLink>
      </Tip>
      <Tip label="Source code">
        <a href={REPO_URL} target="_blank" rel="noreferrer" aria-label="Source code" className="hidden h-10 items-center justify-center text-muted hover:text-ink md:flex">
          <Github className="h-[17px] w-[17px]" strokeWidth={1.6} />
        </a>
      </Tip>
    </nav>
  );
}

function Shell() {
  const loc = useLocation();
  const nav = useNavigate();
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;
      if (e.altKey && /^[1-5]$/.test(e.key)) nav(NAV[Number(e.key) - 1].to);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [nav]);
  if (loc.pathname === "/") return <Landing />;
  return (
    <div className="flex h-full flex-col md:flex-row">
      <Rail />
      <main className="min-w-0 flex-1 overflow-auto pb-16 md:pb-0">
        <Suspense fallback={<div className="shimmer p-8 text-[13px]">Loading…</div>}>
          <Routes>
            <Route path="/lab" element={<Lab />} />
            <Route path="/compare" element={<Compare />} />
            <Route path="/sweeps" element={<Sweeps />} />
            <Route path="/library" element={<LibraryPage />} />
            <Route path="/method" element={<Method />} />
            <Route path="/settings" element={<Settings />} />
            <Route path="*" element={<Lab />} />
          </Routes>
        </Suspense>
      </main>
    </div>
  );
}

export default function App() {
  return (
    <TooltipProvider>
      <HashRouter>
        <Shell />
        <CommandPalette />
      </HashRouter>
      <Toaster theme="dark" position="bottom-right" toastOptions={{ style: { background: "#212023", border: "1px solid #262629", color: "#fff", fontSize: 13 } }} />
    </TooltipProvider>
  );
}

export { FlaskConical };
