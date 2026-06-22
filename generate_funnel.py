import json

def load_data(filepath="funnel_data.json"):
    """Loads the funnel JSON data."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: Please ensure {filepath} exists in the directory.")
        # Returning a dummy structure for structural safety if file is missing
        return {"funnel": {"overall": {}, "by_client": [], "by_vl": []}, "funnel_drill": {}}

def calculate_funnel_metrics(jun, may):
    """Helper to calculate deltas and conversion rates."""
    metrics = {
        "ft_delta": jun.get("ft", 0) - may.get("ft", 0),
        "ob_delta": jun.get("ob", 0) - may.get("ob", 0),
        "uniq_delta": jun.get("uniqueness", 0) - may.get("uniqueness", 0),
        "ls_delta": jun.get("ls", 0) - may.get("ls", 0),
    }
    
    # Conversion rates (Percentages)
    metrics["ft_ob_j"] = (jun.get("ft", 0) / jun.get("ob", 1)) * 100 if jun.get("ob") else 0
    metrics["ft_ob_m"] = (may.get("ft", 0) / may.get("ob", 1)) * 100 if may.get("ob") else 0
    metrics["ft_ob_drop"] = metrics["ft_ob_j"] - metrics["ft_ob_m"]

    metrics["ob_uniq_j"] = (jun.get("ob", 0) / jun.get("uniqueness", 1)) * 100 if jun.get("uniqueness") else 0
    metrics["ob_uniq_m"] = (may.get("ob", 0) / may.get("uniqueness", 1)) * 100 if may.get("uniqueness") else 0
    metrics["ob_uniq_drop"] = metrics["ob_uniq_j"] - metrics["ob_uniq_m"]

    metrics["uniq_ls_j"] = (jun.get("uniqueness", 0) / jun.get("ls", 1)) * 100 if jun.get("ls") else 0
    metrics["uniq_ls_m"] = (may.get("uniqueness", 0) / may.get("ls", 1)) * 100 if may.get("ls") else 0
    metrics["uniq_ls_drop"] = metrics["uniq_ls_j"] - metrics["uniq_ls_m"]
    
    return metrics

def generate_rca_html(data):
    """Analyzes data and generates the HTML for the AI Summary tab."""
    funnel = data.get("funnel", {})
    overall_jun = funnel.get("overall", {}).get("jun", {})
    overall_may = funnel.get("overall", {}).get("may", {})
    
    overall_metrics = calculate_funnel_metrics(overall_jun, overall_may)
    
    html = ["<div style='max-width: 900px;'>"]
    
    # Overall View
    html.append("<div class='sec-ttl' style='font-size: 14px;'>A. Overall Funnel RCA</div>")
    html.append("<div style='background:var(--surface); padding: 16px; border-radius:var(--rl); border: 0.5px solid var(--br); margin-bottom: 24px;'>")
    
    if overall_metrics["ft_delta"] < 0:
        html.append(f"<h3 style='color: var(--red-b); margin-bottom: 12px;'>FT Dropped by {abs(overall_metrics['ft_delta'])}</h3>")
        html.append("<ul style='padding-left: 20px; line-height: 1.6;'>")
        
        if overall_metrics["ft_ob_drop"] < 0:
            html.append(f"<li><strong>P0 Bottleneck (Conversion):</strong> FT/OB conversion rate dropped by {abs(overall_metrics['ft_ob_drop']):.1f}pp. Candidates are activating but not doing their first trip.</li>")
        if overall_metrics["ob_uniq_drop"] < 0:
            html.append(f"<li><strong>P1 Bottleneck (Activation):</strong> OB/Unique rate dropped by {abs(overall_metrics['ob_uniq_drop']):.1f}pp.</li>")
        if overall_metrics["ls_delta"] < 0:
            html.append(f"<li><strong>P2 Bottleneck (Volume):</strong> Top-of-funnel LS volume dropped by {abs(overall_metrics['ls_delta']):,}.</li>")
        
        html.append("</ul>")
    else:
        html.append(f"<h3 style='color: var(--green-b);'>FT is Up by {overall_metrics['ft_delta']}</h3>")
        html.append("<p>Overall funnel health is positive compared to last month.</p>")
    html.append("</div>")

    # Client Level View
    html.append("<div class='sec-ttl' style='font-size: 14px;'>B. Client-Level RCA (Prioritized by FT Drop)</div>")
    
    clients = funnel.get("by_client", [])
    # Filter to clients with FT drops and sort them by the largest drop
    dropped_clients = [c for c in clients if (c["jun"].get("ft",0) - c["may"].get("ft",0)) < 0]
    dropped_clients.sort(key=lambda x: x["jun"].get("ft",0) - x["may"].get("ft",0))
    
    if not dropped_clients:
        html.append("<p style='color: var(--muted);'>No clients experienced an FT drop this month.</p>")
    
    drill_data = data.get("funnel_drill", {})
    
    for client in dropped_clients:
        c_name = client["dim"]
        c_jun = client["jun"]
        c_may = client["may"]
        c_metrics = calculate_funnel_metrics(c_jun, c_may)
        
        html.append(f"<div style='background:var(--surface); padding: 16px; border-radius:var(--r); border: 0.5px solid var(--red-b); border-left: 4px solid var(--red-b); margin-bottom: 16px;'>")
        html.append(f"<h4 style='margin-bottom: 8px;'>{c_name}: {abs(c_metrics['ft_delta'])} FT Drop</h4>")
        
        # Determine specific client bottleneck
        html.append("<div style='font-size: 13px; margin-bottom: 12px;'><strong>Root Cause:</strong> ")
        reasons = []
        if c_metrics["ft_ob_drop"] < -5:
            reasons.append(f"Severe FT/OB conversion drop ({c_metrics['ft_ob_drop']:.1f}pp)")
        elif c_metrics["ob_uniq_drop"] < -5:
            reasons.append(f"OB activation block ({c_metrics['ob_uniq_drop']:.1f}pp drop)")
        if c_metrics["ls_delta"] < 0 and abs(c_metrics["ls_delta"]) > (c_may.get("ls", 1) * 0.1):
            reasons.append(f"LS Volume plummeted by {abs(c_metrics['ls_delta']):,}")
            
        if reasons:
            html.append(" and ".join(reasons) + "</div>")
        else:
            html.append("General decay across all stages of the funnel.</div>")

        # Top VLs contributing to this client's drop
        c_drill = drill_data.get(c_name, {}).get("by_vl", [])
        dropped_vls = [v for v in c_drill if (v["jun"].get("ft",0) - v["may"].get("ft",0)) < 0]
        dropped_vls.sort(key=lambda x: x["jun"].get("ft",0) - x["may"].get("ft",0))
        
        if dropped_vls:
            html.append("<div style='font-size: 12px; color: var(--muted);'><strong>Top Laggard VLs:</strong><ul>")
            for vl in dropped_vls[:3]: # Top 3 offenders
                vl_drop = abs(vl["jun"].get("ft",0) - vl["may"].get("ft",0))
                html.append(f"<li>{vl['dim']}: -{vl_drop} FT</li>")
            html.append("</ul></div>")
            
        html.append("</div>")

    html.append("</div>")
    return "".join(html)

def generate_dashboard(data, output_file="funnel_dashboard.html"):
    """Generates the HTML dashboard."""
    rca_html = generate_rca_html(data)
    
    # Passing funnel data to frontend variables safely
    json_data = json.dumps(data)

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Vahan Funnel & AI RCA Dashboard</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.js"></script>
<style>
:root{{
  --bg:#f5f4f0;--surface:#fff;--surface2:#f7f6f3;--surface3:#eceae4;
  --br:rgba(0,0,0,0.08);--br2:rgba(0,0,0,0.15);
  --text:#111;--muted:#666;--faint:#aaa;
  --r:8px;--rl:12px;
  --red:#8B1A1A;--red-bg:#fdf0f0;--red-b:#e05252;
  --amber:#7A4B0A;--amber-bg:#fdf5e8;--amber-b:#d4891a;
  --green:#1e5c14;--green-bg:#eef6e8;--green-b:#4a9e2f;
  --blue:#0d4080;--blue-bg:#eaf3fd;--blue-b:#2f7dd4;
}}
@media(prefers-color-scheme:dark){{:root{{
  --bg:#161616;--surface:#202020;--surface2:#272727;--surface3:#1a1a1a;
  --br:rgba(255,255,255,0.07);--br2:rgba(255,255,255,0.14);
  --text:#e8e8e8;--muted:#888;--faint:#444;
  --red:#ffbdbd;--red-bg:#2a0e0e;--amber:#ffc97a;--amber-bg:#261504;
  --green:#b8e89a;--green-bg:#162208;--blue:#a8d0f8;--blue-bg:#071e38;
}}}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:var(--bg);color:var(--text);font-size:13px;line-height:1.5}}
.page{{max-width:1140px;margin:0 auto;padding:22px 16px 80px}}

.nav{{display:flex;gap:2px;background:var(--surface2);border:0.5px solid var(--br);border-radius:var(--rl);padding:3px;width:fit-content;margin-bottom:20px}}
.ntab{{padding:7px 20px;border-radius:var(--r);font-size:13px;font-weight:500;cursor:pointer;border:none;background:transparent;color:var(--muted);white-space:nowrap}}
.ntab.on{{background:var(--surface);color:var(--text);border:0.5px solid var(--br);box-shadow:0 1px 3px rgba(0,0,0,0.06)}}
.view{{display:none}}.view.on{{display:block}}

.sec{{margin-bottom:22px}}
.sec-ttl{{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.07em;color:var(--muted);margin-bottom:8px;display:flex;align-items:center;gap:8px}}
.sec-ttl-line{{flex:1;height:0.5px;background:var(--br)}}

/* Funnel specific grid classes */
.fn-stages{{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-bottom:12px}}
.fn-stg{{background:var(--surface);border:0.5px solid var(--br);border-radius:var(--r);padding:12px;text-align:center}}
.fn-val{{font-size:20px;font-weight:500;font-variant-numeric:tabular-nums}}
.fn-lbl{{font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:.05em;margin:3px 0}}
.fn-lmtd{{font-size:11px;color:var(--muted)}}
.fn-delta{{font-size:12px;font-weight:600;margin-top:3px}}

.fn-conv-row{{display:grid;grid-template-columns:repeat(5,1fr);gap:8px;margin-bottom:20px}}
.fn-conv{{background:var(--surface);border:0.5px solid var(--br);border-radius:var(--r);padding:10px;text-align:center}}
.fn-conv-val{{font-size:17px;font-weight:500}}
.fn-conv-lbl{{font-size:10px;color:var(--muted);margin:2px 0}}

.up{{color:var(--green-b)}}.dn{{color:var(--red-b)}}

.tw{{background:var(--surface);border:0.5px solid var(--br);border-radius:var(--rl);overflow:hidden;margin-bottom:12px}}
table{{width:100%;border-collapse:collapse;font-size:12px}}
th{{text-align:left;font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:.04em;padding:7px 10px;border-bottom:0.5px solid var(--br2);background:var(--surface2);white-space:nowrap;}}
td{{padding:7px 10px;border-bottom:0.5px solid var(--br);white-space:nowrap;vertical-align:middle}}
tr:last-child td{{border-bottom:none}}
.n{{text-align:right;font-variant-numeric:tabular-nums}}
.bold{{font-weight:600}}
</style>
</head>
<body>
<div class="page">
<div class="nav">
  <button class="ntab on" onclick="sv('vf',this)">Funnel View</button>
  <button class="ntab" onclick="sv('vai',this)">✨ AI RCA Summary</button>
</div>

<div id="vf" class="view on">
  <div class="sec"><div class="sec-ttl">Overall Funnel <span class="sec-ttl-line"></span></div>
    <div class="fn-stages" id="vfStages"></div>
    <div class="fn-conv-row" id="vfConv"></div>
  </div>
  
  <div class="sec"><div class="sec-ttl">Client Cut <span class="sec-ttl-line"></span></div>
    <div class="tw" style="overflow-x:auto">
      <table>
        <thead><tr><th>Client</th><th class="n">LS Jun</th><th class="n">Uniq Jun</th><th class="n">OB Jun</th><th class="n">FT Jun</th></tr></thead>
        <tbody id="bd_vf1"></tbody>
      </table>
    </div>
  </div>
</div>

<div id="vai" class="view">
  {rca_html}
</div>

</div>

<script>
// Load Data
const D = {json_data};

function sv(id,btn){{
  document.querySelectorAll('.view').forEach(v=>v.classList.remove('on'));
  document.querySelectorAll('.ntab').forEach(b=>b.classList.remove('on'));
  document.getElementById(id).classList.add('on'); btn.classList.add('on');
}}

function sn(n){{ return !n?'0':Math.abs(n)>=1e6?(n/1e6).toFixed(1)+'M':Math.abs(n)>=1e3?(n/1e3).toFixed(1)+'K':String(n); }}
function pct(a,b) {{ return b>0 ? +(a/b*100).toFixed(1) : 0; }}

// Render Funnel KPIs
(function(){{
    const fj=D.funnel.overall.jun, fm=D.funnel.overall.may;
    
    // Top Stages
    const stagesEl = document.getElementById('vfStages');
    const stages = [{{lbl:'LS', jv:fj.ls, mv:fm.ls}}, {{lbl:'Unique', jv:fj.uniqueness, mv:fm.uniqueness}}, {{lbl:'OB', jv:fj.ob, mv:fm.ob}}, {{lbl:'FT', jv:fj.ft, mv:fm.ft}}];
    
    stages.forEach(s=>{{
        const d = s.jv - s.mv;
        const cl = d >= 0 ? 'up' : 'dn';
        stagesEl.innerHTML += `<div class="fn-stg"><div class="fn-val">${{sn(s.jv)}}</div><div class="fn-lbl">${{s.lbl}}</div><div class="fn-lmtd">May: ${{sn(s.mv)}}</div><div class="fn-delta"><span class="${{cl}}">${{d>=0?'↑':'↓'}} ${{d>=0?'+':''}}${{sn(d)}}</span></div></div>`;
    }});

    // Conversions
    const convEl = document.getElementById('vfConv');
    const convs = [
        {{lbl:'LS→Unique', jv:pct(fj.uniqueness,fj.ls), mv:pct(fm.uniqueness,fm.ls)}},
        {{lbl:'Unique→OB', jv:pct(fj.ob,fj.uniqueness), mv:pct(fm.ob,fm.uniqueness)}},
        {{lbl:'OB→FT', jv:pct(fj.ft,fj.ob), mv:pct(fm.ft,fm.ob)}},
        {{lbl:'LS→FT', jv:pct(fj.ft,fj.ls), mv:pct(fm.ft,fm.ls)}}
    ];
    convs.forEach(c=>{{
        const d = +(c.jv-c.mv).toFixed(2);
        const cl = d >= 0 ? 'up' : 'dn';
        convEl.innerHTML += `<div class="fn-conv"><div class="fn-conv-val">${{c.jv}}%</div><div class="fn-conv-lbl">${{c.lbl}}</div><div class="fn-delta"><span class="${{cl}}">${{d>=0?'↑':'↓'}} ${{d>=0?'+':''}}${{d}}pp vs May</span></div></div>`;
    }});
    
    // Render Client Table
    const bd1 = document.getElementById('bd_vf1');
    D.funnel.by_client.sort((a,b)=> b.jun.ft - a.jun.ft).forEach(c=>{{
        bd1.innerHTML += `<tr><td class="bold">${{c.dim}}</td><td class="n">${{sn(c.jun.ls)}}</td><td class="n">${{sn(c.jun.uniqueness)}}</td><td class="n">${{sn(c.jun.ob)}}</td><td class="n bold">${{sn(c.jun.ft)}}</td></tr>`;
    }});
}})();
</script>
</body>
</html>
"""
    
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(html_content)
        
    print(f"Dashboard generated successfully at {output_file}")

if __name__ == "__main__":
    # Ensure you drop your specific funnel JSON in a file called 'funnel_data.json'
    # For now, executing the function directly.
    data = load_data()
    generate_dashboard(data)
