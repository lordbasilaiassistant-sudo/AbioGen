"""web/build_site.py — embed real checkpoints into a single static index.html.

Reads ``results.json`` (from ``pot.experiment``) and, if present,
``sweep_results.json`` (from ``pot.sweep``), and writes a fully self-contained
``web/index.html``: no build step, no external assets, no localStorage, GitHub
Pages ready. Every number on the page is embedded from a real run — nothing is
hand-written into the figures.

Usage:
    python web/build_site.py                # reads ./results.json (+ sweep)
    python web/build_site.py --results r.json --sweep s.json --out web/index.html
"""

from __future__ import annotations

import argparse
import json
import os


def _load(path):
    if path and os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def build(results_path="results.json", sweep_path="sweep_results.json",
          out_path="web/index.html"):
    results = _load(results_path)
    sweep = _load(sweep_path)
    if results is None and sweep is None:
        raise SystemExit("No results.json or sweep_results.json found — run "
                         "`python -m pot.experiment` first.")

    payload = {
        "results": results,
        "sweep": sweep,
        "generated_from": {
            "results": os.path.basename(results_path) if results else None,
            "sweep": os.path.basename(sweep_path) if sweep else None,
        },
    }
    data_json = json.dumps(payload, separators=(",", ":"))

    html = _TEMPLATE.replace("/*__DATA__*/", data_json)
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[build_site] wrote {out_path} "
          f"({len(html)//1024} KB, self-contained)")
    return out_path


# The page is one file. Data is injected at /*__DATA__*/ and read by the JS.
_TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>the-pot — order out of noise, or not</title>
<style>
:root{
  --ground:#070b0d; --panel:#0c1417; --panel-2:#0f1b1f; --edge:#1b2d31;
  --ink:#dce7e3; --muted:#7d938e; --faint:#4b5f5b;
  --phosphor:#46e6a4; --phosphor-dim:#2b8f68; --amber:#e8b34a; --void:#ff5c6a;
  --font-mono: ui-monospace,"JetBrains Mono","Cascadia Code","SF Mono",Menlo,Consolas,monospace;
  --font-sans: -apple-system,BlinkMacSystemFont,"Segoe UI",system-ui,Roboto,sans-serif;
  --grid: color-mix(in oklab, var(--edge) 70%, transparent);
}
@media (prefers-color-scheme: light){
  :root{
    --ground:#e9efec; --panel:#f6faf8; --panel-2:#eef4f1; --edge:#cbd8d3;
    --ink:#0f1a17; --muted:#4d635e; --faint:#93a8a2;
    --phosphor:#0f9d63; --phosphor-dim:#5cc79b; --amber:#a5711a; --void:#c8324a;
  }
}
:root[data-theme="dark"]{
  --ground:#070b0d; --panel:#0c1417; --panel-2:#0f1b1f; --edge:#1b2d31;
  --ink:#dce7e3; --muted:#7d938e; --faint:#4b5f5b;
  --phosphor:#46e6a4; --phosphor-dim:#2b8f68; --amber:#e8b34a; --void:#ff5c6a;
}
:root[data-theme="light"]{
  --ground:#e9efec; --panel:#f6faf8; --panel-2:#eef4f1; --edge:#cbd8d3;
  --ink:#0f1a17; --muted:#4d635e; --faint:#93a8a2;
  --phosphor:#0f9d63; --phosphor-dim:#5cc79b; --amber:#a5711a; --void:#c8324a;
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{
  margin:0;background:var(--ground);color:var(--ink);
  font-family:var(--font-sans);line-height:1.6;
  font-size:16px;-webkit-font-smoothing:antialiased;
  background-image:
    radial-gradient(120% 80% at 50% -10%, color-mix(in oklab,var(--phosphor) 8%,transparent), transparent 60%);
}
.wrap{max-width:940px;margin:0 auto;padding:0 22px}
h1,h2,h3{text-wrap:balance;margin:0}
.mono{font-family:var(--font-mono)}
.eyebrow{font-family:var(--font-mono);font-size:12px;letter-spacing:.22em;
  text-transform:uppercase;color:var(--muted)}
a{color:var(--phosphor)}

/* ---- top ledger strip ---- */
.ledger{position:sticky;top:0;z-index:20;backdrop-filter:blur(8px);
  background:color-mix(in oklab,var(--ground) 82%,transparent);
  border-bottom:1px solid var(--edge)}
.ledger .wrap{display:flex;align-items:center;gap:16px;height:46px;
  font-family:var(--font-mono);font-size:12px;color:var(--muted)}
.ledger b{color:var(--ink);font-weight:600}
.ledger .sp{flex:1}
.dot{width:8px;height:8px;border-radius:50%;display:inline-block;
  background:var(--phosphor);box-shadow:0 0 8px var(--phosphor)}
.themebtn{font:inherit;color:var(--muted);background:transparent;border:1px solid var(--edge);
  border-radius:6px;padding:3px 9px;cursor:pointer}
.themebtn:hover{color:var(--ink);border-color:var(--phosphor-dim)}

/* ---- hero ---- */
.hero{position:relative;min-height:clamp(420px,62vh,600px);
  display:flex;align-items:flex-end;overflow:hidden;
  border-bottom:1px solid var(--edge)}
#soup{position:absolute;inset:0;width:100%;height:100%;display:block}
.hero-veil{position:absolute;inset:0;pointer-events:none;
  background:linear-gradient(180deg,transparent 30%,color-mix(in oklab,var(--ground) 92%,transparent) 96%)}
.hero-inner{position:relative;z-index:2;width:100%;padding:0 22px 42px}
.hero h1{font-family:var(--font-mono);font-weight:600;letter-spacing:-.01em;
  font-size:clamp(30px,6.2vw,58px);line-height:1.02;margin:.35em 0 .28em}
.hero h1 .q{color:var(--phosphor)}
.hero p.lede{max-width:60ch;color:var(--ink);opacity:.86;font-size:clamp(15px,1.8vw,18px)}
.badge{display:inline-flex;align-items:center;gap:9px;font-family:var(--font-mono);
  font-size:13px;padding:6px 12px;border-radius:999px;border:1px solid var(--edge);
  background:var(--panel);letter-spacing:.04em}
.badge .k{color:var(--muted)}
.badge .v{font-weight:600}
.v-FEATURE{color:var(--phosphor)} .v-BUG{color:var(--amber)}
.v-UNRESOLVED{color:var(--ink)} .v-VOID{color:var(--void)} .v-ANCHORED{color:var(--phosphor)}

/* ---- sections ---- */
section{padding:56px 0}
.sechead{display:flex;align-items:baseline;gap:14px;margin-bottom:8px}
.sechead .n{font-family:var(--font-mono);font-size:12px;color:var(--phosphor-dim)}
h2{font-family:var(--font-mono);font-weight:600;font-size:clamp(19px,3vw,26px);
  letter-spacing:-.01em}
.sub{color:var(--muted);max-width:66ch;margin:.5em 0 26px}
.panel{background:linear-gradient(180deg,var(--panel),var(--panel-2));
  border:1px solid var(--edge);border-radius:14px;padding:20px 20px 16px;
  box-shadow:0 1px 0 color-mix(in oklab,var(--phosphor) 6%,transparent) inset,
             0 18px 40px -30px #000}
.panel + .panel{margin-top:18px}
.chart-wrap{position:relative;width:100%;overflow-x:auto}
canvas.chart{display:block;width:100%;height:auto}
.legend{display:flex;flex-wrap:wrap;gap:14px 20px;margin-top:12px;
  font-family:var(--font-mono);font-size:12px;color:var(--muted)}
.legend i{display:inline-block;width:20px;height:0;border-top:2px solid;
  vertical-align:middle;margin-right:7px}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:18px}
@media (max-width:720px){.grid2{grid-template-columns:1fr}}

/* verdict readout */
.verdict{display:grid;grid-template-columns:auto 1fr;gap:22px;align-items:center}
@media (max-width:620px){.verdict{grid-template-columns:1fr}}
.verdict .disc{width:132px;height:132px;border-radius:50%;position:relative;
  display:grid;place-items:center;text-align:center;
  background:radial-gradient(circle at 50% 40%,var(--panel-2),var(--ground));
  border:1px solid var(--edge)}
.verdict .disc .lbl{font-family:var(--font-mono);font-size:11px;color:var(--muted);
  letter-spacing:.15em}
.verdict .disc .big{font-family:var(--font-mono);font-weight:700;font-size:19px;margin-top:2px}
.verdict .statement{font-size:17px}
.verdict .conf{color:var(--muted);font-size:13px;font-family:var(--font-mono);margin-top:8px}

/* stat row */
.stats{display:flex;flex-wrap:wrap;gap:10px;margin-top:14px}
.stat{flex:1 1 130px;background:var(--panel-2);border:1px solid var(--edge);
  border-radius:10px;padding:11px 13px}
.stat .k{font-family:var(--font-mono);font-size:11px;color:var(--muted);letter-spacing:.05em}
.stat .v{font-family:var(--font-mono);font-size:21px;font-weight:600;
  font-variant-numeric:tabular-nums;margin-top:3px}

/* control comparison table */
table.cmp{width:100%;border-collapse:collapse;font-family:var(--font-mono);font-size:13px}
table.cmp th,table.cmp td{text-align:right;padding:8px 10px;border-bottom:1px solid var(--edge);
  font-variant-numeric:tabular-nums}
table.cmp th:first-child,table.cmp td:first-child{text-align:left;color:var(--muted)}
table.cmp thead th{color:var(--muted);font-weight:500;border-bottom:1px solid var(--phosphor-dim)}
.pill{font-family:var(--font-mono);font-size:11px;padding:2px 8px;border-radius:999px;
  border:1px solid var(--edge)}
.pill.ok{color:var(--phosphor);border-color:var(--phosphor-dim)}
.pill.warn{color:var(--amber);border-color:color-mix(in oklab,var(--amber) 50%,var(--edge))}

/* sweep grid */
.fires{display:grid;gap:4px;margin-top:6px;overflow-x:auto}
.firecell{font-family:var(--font-mono);font-size:11px;padding:8px 6px;border-radius:6px;
  border:1px solid var(--edge);text-align:center;min-width:78px}
.firehead{color:var(--muted);border:none;background:transparent}

/* genomes */
.genome{font-family:var(--font-mono);font-size:12px;white-space:pre;overflow-x:auto;
  background:var(--ground);border:1px solid var(--edge);border-radius:8px;
  padding:9px 11px;margin-top:8px;color:var(--phosphor);letter-spacing:.02em}
.genome .meta{color:var(--muted)}

/* caveats */
.caveats li{margin:10px 0;color:var(--ink);opacity:.9}
.caveats li b{color:var(--amber);font-family:var(--font-mono);font-weight:600;font-size:13px}

footer{border-top:1px solid var(--edge);padding:30px 0 60px;color:var(--muted);
  font-family:var(--font-mono);font-size:12px}
.reveal{opacity:0;transform:translateY(14px);transition:opacity .7s ease,transform .7s ease}
.reveal.in{opacity:1;transform:none}
@media (prefers-reduced-motion:reduce){.reveal{opacity:1;transform:none;transition:none}}
</style>
</head>
<body>
<div class="ledger"><div class="wrap">
  <span class="dot"></span><b>the-pot</b>
  <span>substrate physics only · seeded from pure noise · no goal, no fitness</span>
  <span class="sp"></span>
  <span id="ledger-engine">engine —</span>
  <button class="themebtn" id="themebtn" aria-label="toggle theme">theme</button>
</div></div>

<header class="hero">
  <canvas id="soup" aria-hidden="true"></canvas>
  <div class="hero-veil"></div>
  <div class="hero-inner wrap">
    <div class="eyebrow">an accelerated origin-of-intelligence engine</div>
    <h1>Does order crawl out of noise <span class="q">reliably</span>,<br>
        or only as a <span class="q">fluke</span>?</h1>
    <p class="lede">We built only the substrate. The soup is seeded with pure
      randomness — no fitness function, no goal, no replicator we authored.
      Whatever order appears has to be earned from the data, next to a scrambled
      control that must stay silent. Here is what actually ran.</p>
    <div style="margin-top:18px;display:flex;gap:10px;flex-wrap:wrap">
      <span class="badge"><span class="k">soup verdict</span>
        <span class="v" id="badge-soup">—</span></span>
      <span class="badge"><span class="k">extinction anchor</span>
        <span class="v" id="badge-anchor">—</span></span>
    </div>
  </div>
</header>

<main class="wrap">

  <section id="verdict">
    <div class="sechead"><span class="n">01</span><h2>The verdict, earned from the data</h2></div>
    <p class="sub">Three outcomes are allowed, none hardcoded. <b>Feature</b>: order
      emerges reliably across seeds. <b>Bug</b>: only under knife-edge tuning.
      <b>Unresolved</b>: no convergence within the budget we could afford.</p>
    <div class="panel reveal">
      <div class="verdict">
        <div class="disc"><div><div class="lbl">SOUP</div>
          <div class="big" id="disc-soup">—</div></div></div>
        <div>
          <div class="statement" id="verdict-statement">—</div>
          <div class="conf" id="verdict-conf"></div>
          <div class="stats" id="verdict-stats"></div>
        </div>
      </div>
    </div>
  </section>

  <section id="trajectory">
    <div class="sechead"><span class="n">02</span><h2>Emergence trajectory</h2></div>
    <p class="sub" id="traj-sub">The longest real run we could afford, on the
      oscilloscope. A replicator sweeping would show as <span class="mono">repl_rate</span>
      lifting off zero while diversity (<span class="mono">unique_ratio</span>)
      collapses. Watch whether it does.</p>
    <div class="panel reveal">
      <div class="chart-wrap"><canvas id="chart-traj" class="chart"></canvas></div>
      <div class="legend" id="legend-traj"></div>
    </div>
  </section>

  <section id="control">
    <div class="sechead"><span class="n">03</span><h2>The scrambled control — is it signal or artifact?</h2></div>
    <p class="sub">Every real run is paired with an identical run whose structure
      is destroyed each epoch (byte histogram preserved). A metric only counts as
      emergence if the real run beats this control. <span class="mono">near_repl</span>
      is deliberately excluded from firing — real dynamics create correlation
      even with no replicator, so it is a <em>watch</em> line, never a verdict.</p>
    <div class="panel reveal">
      <div class="chart-wrap"><table class="cmp" id="cmp-table"></table></div>
    </div>
  </section>

  <section id="sweep">
    <div class="sechead"><span class="n">04</span><h2>Parameter sweep — where, if anywhere</h2></div>
    <p class="sub" id="sweep-sub">Fire fraction across seeds for each regime we
      swept. Green would mean a replicator emerged reliably there; every cell here
      is judged against its own scrambled control.</p>
    <div class="panel reveal" id="sweep-panel">
      <div class="fires" id="fires"></div>
    </div>
  </section>

  <section id="anchor">
    <div class="sechead"><span class="n">05</span><h2>The extinction anchor</h2></div>
    <p class="sub">The honesty visual. In the closed baseline the structured world
      is learnable and should adapt; the <b>null</b> world has nothing to learn and
      <b>must go extinct</b>. If a structureless world ever sustained life, the
      harness would be leaking structure and the whole run would be void.</p>
    <div class="panel reveal">
      <div class="chart-wrap"><canvas id="chart-anchor" class="chart"></canvas></div>
      <div class="legend" id="legend-anchor"></div>
    </div>
  </section>

  <section id="genomes">
    <div class="sechead"><span class="n">06</span><h2>Dominant genomes</h2></div>
    <p class="sub">The most common tapes at the end of the headline run, as BFF
      source (non-instruction bytes shown as <span class="mono">·</span>). In a
      cold run these are just the survivors of drift, not replicators.</p>
    <div class="panel reveal" id="genome-panel"></div>
  </section>

  <section id="caveats">
    <div class="sechead"><span class="n">07</span><h2>What this does <em>not</em> settle</h2></div>
    <div class="panel reveal">
      <ul class="caveats">
        <li><b>NARROW</b> This engine can say whether a replicator emerges in the
          regimes it can afford to sweep. It cannot decide whether intelligence is
          a feature of physics in general.</li>
        <li><b>ANCHOR</b> The closed baseline is a sanity check with a known
          optimum, not a discovery. Its only jobs are to prove the metrics can see
          adaptation and to force a structureless world extinct.</li>
        <li><b>CONFOUND</b> <span class="mono">near_repl</span> is elevated in real
          soups by ordinary autocorrelation the scrambled control destroys — it is
          an early warning to watch, never counted as emergence.</li>
        <li><b>BUDGET</b> An <span class="mono">UNRESOLVED</span> result is bounded
          by compute, not by evidence of absence. Longer runs and wider sweeps can
          still move it.</li>
        <li><b>OPEN</b> The cosmic-scale question — is order a feature of a
          well-designed substrate — stays open. This is one honest instrument, not
          a proof.</li>
      </ul>
    </div>
  </section>
</main>

<footer><div class="wrap">
  <div id="foot-provenance">every figure regenerates from a checkpoint · seeded · deterministic</div>
</div></footer>

<script id="data" type="application/json">/*__DATA__*/</script>
<script>
const DATA = JSON.parse(document.getElementById('data').textContent);
const R = DATA.results, S = DATA.sweep;
const css = k => getComputedStyle(document.documentElement).getPropertyValue(k).trim();

/* ---------- theme ---------- */
(function(){
  const btn = document.getElementById('themebtn');
  btn.addEventListener('click',()=>{
    const cur = document.documentElement.getAttribute('data-theme')
      || (matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light');
    document.documentElement.setAttribute('data-theme', cur==='dark'?'light':'dark');
    drawAll();
  });
})();

/* ---------- helpers ---------- */
function dpr(){return Math.min(2, window.devicePixelRatio||1);}
function sizeCanvas(cv,h){
  const w = cv.parentElement.clientWidth;
  const r = dpr(); cv.width=w*r; cv.height=h*r;
  cv.style.height=h+'px';
  const ctx=cv.getContext('2d'); ctx.setTransform(r,0,0,r,0,0);
  return {ctx,w,h};
}
function fmt(x,d=3){return (x==null||isNaN(x))?'—':Number(x).toFixed(d);}

/* ---------- line chart ---------- */
function lineChart(cv, series, opts){
  opts=opts||{};
  const {ctx,w,h}=sizeCanvas(cv, opts.height||300);
  ctx.clearRect(0,0,w,h);
  const padL=48,padR=14,padT=14,padB=34;
  const x0=padL,x1=w-padR,y0=h-padB,y1=padT;
  const allx=series.flatMap(s=>s.pts.map(p=>p.x));
  const xmin=opts.xmin!=null?opts.xmin:Math.min(...allx);
  const xmax=opts.xmax!=null?opts.xmax:Math.max(...allx,1);
  const ymin=opts.ymin!=null?opts.ymin:0;
  const ymax=opts.ymax!=null?opts.ymax:1;
  const X=v=>x0+(x1-x0)*((v-xmin)/((xmax-xmin)||1));
  const Y=v=>y0+(y1-y0)*((v-ymin)/((ymax-ymin)||1));
  // grid
  ctx.strokeStyle=css('--grid');ctx.lineWidth=1;ctx.fillStyle=css('--muted');
  ctx.font='11px '+css('--font-mono');ctx.textBaseline='middle';
  const yticks=opts.yticks||5;
  for(let i=0;i<=yticks;i++){
    const v=ymin+(ymax-ymin)*i/yticks,y=Y(v);
    ctx.globalAlpha=.5;ctx.beginPath();ctx.moveTo(x0,y);ctx.lineTo(x1,y);ctx.stroke();
    ctx.globalAlpha=1;ctx.textAlign='right';
    ctx.fillText((opts.yfmt?opts.yfmt(v):v.toFixed(2)), x0-8, y);
  }
  // x labels
  ctx.textAlign='center';ctx.textBaseline='top';
  const xt=opts.xticks||5;
  for(let i=0;i<=xt;i++){
    const v=xmin+(xmax-xmin)*i/xt;
    ctx.fillText(opts.xfmt?opts.xfmt(v):Math.round(v), X(v), y0+8);
  }
  ctx.fillStyle=css('--faint');ctx.textAlign='right';ctx.textBaseline='bottom';
  ctx.fillText(opts.xlabel||'', x1, h-2);
  // series
  series.forEach(s=>{
    if(!s.pts.length) return;
    ctx.beginPath();
    s.pts.forEach((p,i)=>{const x=X(p.x),y=Y(p.y);i?ctx.lineTo(x,y):ctx.moveTo(x,y);});
    ctx.strokeStyle=s.color;ctx.lineWidth=s.width||2;
    if(s.dash)ctx.setLineDash(s.dash);else ctx.setLineDash([]);
    ctx.shadowColor=s.glow?s.color:'transparent';ctx.shadowBlur=s.glow?8:0;
    ctx.stroke();ctx.shadowBlur=0;ctx.setLineDash([]);
    if(s.fill){
      ctx.lineTo(X(s.pts[s.pts.length-1].x),Y(ymin));
      ctx.lineTo(X(s.pts[0].x),Y(ymin));ctx.closePath();
      ctx.fillStyle=s.fill;ctx.globalAlpha=.14;ctx.fill();ctx.globalAlpha=1;
    }
    if(s.mark){const p=s.pts[s.pts.length-1];
      ctx.fillStyle=s.color;ctx.beginPath();ctx.arc(X(p.x),Y(p.y),3,0,7);ctx.fill();}
  });
}
function legend(el, items){
  el.innerHTML=items.map(i=>`<span><i style="border-color:${i.color}"></i>${i.name}</span>`).join('');
}

/* ---------- pick the headline soup run ---------- */
function headlineRun(){
  if(S && S.headline) return {
    real:S.headline.real_trajectory, ctrl:S.headline.control_trajectory,
    dominant:S.headline.dominant, cell:S.headline.cell,
    epochs:S.epochs, rs:S.headline.real, ks:S.headline.control};
  if(R && R.soup && R.soup.records && R.soup.records.length){
    // choose the record with the highest max_top_share (most ordered)
    let best=R.soup.records[0];
    R.soup.records.forEach(r=>{if(r.real.max_top_share>best.real.max_top_share)best=r;});
    return {real:best.real_trajectory, ctrl:best.control_trajectory,
      dominant:best.dominant, cell:R.soup_config, epochs:R.soup_config.epochs,
      rs:best.real, ks:best.control};
  }
  return null;
}

/* ---------- populate ---------- */
function fillVerdict(){
  const sv = (S&&S.verdict) || (R&&R.soup&&R.soup.verdict);
  const anchor = R&&R.baseline;
  const v = sv? sv.verdict : '—';
  document.getElementById('badge-soup').textContent=v;
  document.getElementById('badge-soup').className='v v-'+v;
  document.getElementById('disc-soup').textContent=v;
  document.getElementById('disc-soup').className='big v-'+v;
  document.getElementById('verdict-statement').textContent = sv? sv.statement : '';
  document.getElementById('verdict-conf').textContent =
    sv&&sv.confidence? ('confidence: '+sv.confidence) : '';
  if(anchor){
    document.getElementById('badge-anchor').textContent=anchor.verdict;
    document.getElementById('badge-anchor').className='v v-'+anchor.verdict;
  }
  // stats
  const st=[];
  if(S){
    st.push(['regimes swept', S.cell_table? S.cell_table.length : '—']);
    st.push(['runs', S.total_runs]);
    st.push(['epochs / run', S.epochs.toLocaleString()]);
    st.push(['runs that fired', S.total_fired]);
  } else if(R&&R.soup&&R.soup.verdict){
    st.push(['seeds', R.soup.verdict.seeds]);
    st.push(['seeds fired', R.soup.verdict.seeds_fired]);
    st.push(['epochs / run', (R.soup_config.epochs||0).toLocaleString()]);
  }
  document.getElementById('verdict-stats').innerHTML =
    st.map(([k,v])=>`<div class="stat"><div class="k">${k}</div><div class="v">${v}</div></div>`).join('');
  const eng = (R&&R.have_rust)||(S)? 'engine · rust interpreter' : 'engine · python fallback';
  document.getElementById('ledger-engine').textContent = eng;
}

function fillTrajectory(){
  const hr=headlineRun();
  if(!hr){document.getElementById('trajectory').style.display='none';return;}
  const t=hr.real;
  const mk=(key)=>t.map(c=>({x:c.epoch,y:c[key]}));
  const series=[
    {name:'unique_ratio',color:css('--muted'),pts:mk('unique_ratio'),width:1.6,dash:[4,3]},
    {name:'top_share',color:css('--amber'),pts:mk('top_share'),width:1.8},
    {name:'near_repl_max (watch)',color:css('--phosphor-dim'),pts:mk('near_repl_max'),width:1.4,dash:[2,3]},
    {name:'repl_rate',color:css('--phosphor'),pts:mk('repl_rate'),width:2.4,glow:true,mark:true,fill:css('--phosphor')},
  ];
  window._traj={cv:document.getElementById('chart-traj'),series,
    opts:{height:320,ymin:0,ymax:1,xmax:hr.epochs,
      xfmt:v=>v>=1000?(v/1000)+'k':v, xlabel:'epochs →', yfmt:v=>v.toFixed(1)}};
  legend(document.getElementById('legend-traj'),series);
  const cellStr = hr.cell? Object.entries(hr.cell)
    .filter(([k])=>['tape_len','max_steps','mut_per_tape','soup_size'].includes(k))
    .map(([k,v])=>k+'='+v).join('  ') : '';
  document.getElementById('traj-sub').innerHTML +=
    cellStr? `<br><span class="mono" style="color:var(--faint)">headline regime: ${cellStr} · ${hr.epochs.toLocaleString()} epochs</span>`:'';
}

function fillControl(){
  const hr=headlineRun();
  if(!hr){document.getElementById('control').style.display='none';return;}
  const rows=[
    ['peak_repl_rate','real vs control — the exact self-copy signal'],
    ['max_top_share','a lineage sweeping the soup'],
    ['min_unique_ratio','diversity crash (lower = more collapse)'],
    ['peak_near_repl','early-warning only — excluded from firing'],
    ['final_entropy','byte-entropy of the soup at the end'],
  ];
  const fired = hr.rs && hr.ks;
  let html='<thead><tr><th>metric</th><th>real</th><th>scrambled control</th><th>read</th></tr></thead><tbody>';
  rows.forEach(([k,desc])=>{
    const rv=hr.rs[k], kv=hr.ks[k];
    const watch = k==='peak_near_repl';
    const beats = k==='min_unique_ratio' ? (rv<kv-0.1) : (rv>kv+ (k==='peak_repl_rate'?0.02:0.1));
    const tag = watch? '<span class="pill warn">watch</span>'
      : beats? '<span class="pill ok">real&gt;ctrl</span>'
      : '<span class="pill">no gap</span>';
    html+=`<tr><td title="${desc}">${k}</td><td>${fmt(rv,3)}</td><td>${fmt(kv,3)}</td><td style="text-align:center">${tag}</td></tr>`;
  });
  html+='</tbody>';
  document.getElementById('cmp-table').innerHTML=html;
}

function fillSweep(){
  if(!S || !S.cell_table){document.getElementById('sweep').style.display='none';return;}
  const cells=S.cell_table.slice().sort((a,b)=>
    (a.cell.tape_len-b.cell.tape_len)||(a.cell.max_steps-b.cell.max_steps)||
    (a.cell.mut_per_tape-b.cell.mut_per_tape));
  const wrap=document.getElementById('fires');
  wrap.style.gridTemplateColumns=`repeat(auto-fill,minmax(120px,1fr))`;
  wrap.innerHTML=cells.map(c=>{
    const f=c.fire_fraction;
    const bg = f<=0? 'var(--panel-2)' :
      `color-mix(in oklab, var(--phosphor) ${Math.round(f*100)}%, var(--panel-2))`;
    const col = f>0.4? 'var(--ground)':'var(--ink)';
    return `<div class="firecell" style="background:${bg};color:${col}">
      <div style="font-weight:600">${c.n_fired}/${c.n_seeds} fired</div>
      <div style="color:var(--muted);margin-top:4px">L${c.cell.tape_len}·s${c.cell.max_steps}·m${c.cell.mut_per_tape}</div>
    </div>`;
  }).join('');
  document.getElementById('sweep-sub').innerHTML +=
    `<br><span class="mono" style="color:var(--faint)">${S.total_fired}/${S.total_runs} runs fired · swept in ${Math.round(S.elapsed_sec)}s</span>`;
}

function fillAnchor(){
  const b=R&&R.baseline;
  if(!b){document.getElementById('anchor').style.display='none';return;}
  const struct=b.structured[0], nul=b.null[0];
  const chance=b.chance||0.25;
  const sPts=struct.trajectory.map(g=>({x:g.gen,y:g.capture}));
  const nPts=nul.trajectory.map(g=>({x:g.gen,y:g.capture}));
  const gens=Math.max(struct.trajectory.length, ...b.structured.map(s=>s.trajectory.length));
  const series=[
    {name:'chance',color:css('--faint'),pts:[{x:0,y:chance},{x:gens,y:chance}],width:1,dash:[3,4]},
    {name:'structured — capture',color:css('--phosphor'),pts:sPts,width:2.4,glow:true,mark:true,fill:css('--phosphor')},
    {name:'null — capture (→ extinct)',color:css('--void'),pts:nPts,width:2.2,mark:true},
  ];
  window._anchor={cv:document.getElementById('chart-anchor'),series,
    opts:{height:300,ymin:0,ymax:Math.max(0.6,...sPts.map(p=>p.y))+0.05,xmax:gens,
      xfmt:v=>Math.round(v),xlabel:'generations →',yfmt:v=>v.toFixed(2)}};
  legend(document.getElementById('legend-anchor'),series.concat(
    nul.extinct?[{name:`null extinct @ gen ${nul.extinct_gen}`,color:css('--void')}]:[]));
}

function fillGenomes(){
  const hr=headlineRun();
  const dom = hr && hr.dominant;
  const panel=document.getElementById('genome-panel');
  if(!dom||!dom.length){document.getElementById('genomes').style.display='none';return;}
  panel.innerHTML=dom.slice(0,6).map(d=>{
    const src = d.ascii || d.genome;
    return `<div class="genome"><span class="meta">×${d.count}  </span>${(src||'').replace(/</g,'&lt;')}</div>`;
  }).join('');
}

/* ---------- animated soup hero ---------- */
function heroSoup(){
  const cv=document.getElementById('soup');
  const glyphs='><}{+-.,[]'.split('');
  const colorFor=g=>{
    if('.,'.includes(g))return css('--phosphor');
    if('+-'.includes(g))return css('--phosphor-dim');
    if('[]'.includes(g))return css('--amber');
    return css('--muted');
  };
  // coherence: how ordered the field looks. Drive from the real verdict so the
  // visual never overstates the data — a cold run stays noisy.
  const sv=(S&&S.verdict)||(R&&R.soup&&R.soup.verdict);
  const v = sv?sv.verdict:'UNRESOLVED';
  const coherence = v==='FEATURE'?0.85 : v==='BUG'?0.4 : 0.08;
  let cols,rows,cell,grid,ctx,W,H;
  const reduce=matchMedia('(prefers-reduced-motion:reduce)').matches;
  function init(){
    const r=dpr();W=cv.clientWidth;H=cv.clientHeight;
    cv.width=W*r;cv.height=H*r;ctx=cv.getContext('2d');ctx.setTransform(r,0,0,r,0,0);
    cell=16;cols=Math.ceil(W/cell);rows=Math.ceil(H/cell);
    grid=new Array(cols*rows);
    for(let i=0;i<grid.length;i++)grid[i]={g:glyphs[(Math.random()*glyphs.length)|0],
      a:Math.random()*0.5+0.2,vx:(Math.random()-0.5)*0.2};
  }
  function frame(t){
    ctx.clearRect(0,0,W,H);
    ctx.font='13px '+css('--font-mono');ctx.textBaseline='top';
    for(let y=0;y<rows;y++)for(let x=0;x<cols;x++){
      const i=y*cols+x,c=grid[i];
      // ordered patches: sample a slow noise; where high & coherent, align glyph
      const n=Math.sin((x*0.35)+(t*0.0004))*Math.cos((y*0.4)-(t*0.0003));
      if(coherence>Math.random()*1.6 && n>0.6){c.g='.';}
      else if(Math.random()<0.02+0.06*(1-coherence))c.g=glyphs[(Math.random()*glyphs.length)|0];
      const flick=reduce?0:0.12*Math.sin(t*0.002+i);
      ctx.globalAlpha=Math.max(0.05,Math.min(0.9,c.a+flick));
      ctx.fillStyle=colorFor(c.g);
      ctx.fillText(c.g, x*cell+3, y*cell+2);
    }
    ctx.globalAlpha=1;
    if(!reduce)requestAnimationFrame(frame);
  }
  init();
  if(reduce)frame(0); else requestAnimationFrame(frame);
  addEventListener('resize',()=>{clearTimeout(window._rz);
    window._rz=setTimeout(()=>{init();if(reduce)frame(0);},200);});
}

/* ---------- draw all charts (also on theme change) ---------- */
function drawAll(){
  if(window._traj)lineChart(window._traj.cv,window._traj.series,window._traj.opts);
  if(window._anchor)lineChart(window._anchor.cv,window._anchor.series,window._anchor.opts);
}
addEventListener('resize',()=>{clearTimeout(window._rz2);
  window._rz2=setTimeout(drawAll,180);});

/* ---------- reveal on scroll ---------- */
const io=new IntersectionObserver(es=>es.forEach(e=>{
  if(e.isIntersecting){e.target.classList.add('in');
    if(e.target.querySelector&&e.target===document.activeElement){}
    io.unobserve(e.target);}
}),{threshold:.12});
document.querySelectorAll('.reveal').forEach(el=>io.observe(el));

/* ---------- go ---------- */
fillVerdict();fillTrajectory();fillControl();fillSweep();fillAnchor();fillGenomes();
drawAll();heroSoup();
document.getElementById('foot-provenance').textContent +=
  DATA.generated_from&&DATA.generated_from.sweep? '  ·  data: '+DATA.generated_from.sweep : '';
</script>
</body>
</html>
"""


def main():
    ap = argparse.ArgumentParser(description="build the-pot static site")
    ap.add_argument("--results", default="results.json")
    ap.add_argument("--sweep", default="sweep_results.json")
    ap.add_argument("--out", default="web/index.html")
    args = ap.parse_args()
    build(args.results, args.sweep, args.out)


if __name__ == "__main__":
    main()
