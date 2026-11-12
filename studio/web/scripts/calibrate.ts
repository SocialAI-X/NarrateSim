// Prints attack effects across framing x value profile, placement, dose and topology (heuristic mind).
// Used to check the heuristic mind orders effects sensibly:  npx tsx scripts/calibrate.ts
import { Simulation, variantOf, triadSummary } from "../src/engine/engine";
import { defaultScenario } from "../src/engine/presets";
const strategies = ["pseudo_rational","victim_narrative","fear_appeal","conspiracy","fake_authority","bandwagon"] as const;
const eff = (mut:(s:any)=>void, seeds=[1,2,3]) => {
  let tot=0; for (const seed of seeds){ const s=defaultScenario(); s.seed=seed; mut(s);
  const b=new Simulation(variantOf(s,"baseline")).runSync().record(); const a=new Simulation(variantOf(s,"attacked")).runSync().record();
  tot+=triadSummary(b,a).attack_effect;} return (tot/seeds.length).toFixed(2);
};
for (const pop of ["representative","trusting","distrustful","analytical","polarized"]) {
  console.log(pop.padEnd(15), strategies.map(st=>st.slice(0,8)+" "+eff(s=>{s.society.population=pop; s.adversary.strategy=st;})).join("  "));
}
for (const pl of ["hub","bridge","random","periphery"]) console.log(pl, eff(s=>{s.adversary.placement=pl}));
for (const n of [1,2,4,8]) console.log("n", n, eff(s=>{s.adversary.n_attackers=n}));
for (const k of ["scale_free","small_world","random","communities"]) console.log(k, eff(s=>{s.network.kind=k}));
