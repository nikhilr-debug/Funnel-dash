import streamlit as st
import pandas as pd
import requests
from datetime import date, timedelta

# --- Page Optimization Configuration ---
st.set_page_config(page_title="Vahan June Review — Live Funnel", layout="wide")

# Custom CSS styling to mimic the design tokens of the original HTML dashboard
st.markdown("""
<style>
    .up { color: #4a9e2f !important; font-weight: 600; }
    .dn { color: #e05252 !important; font-weight: 600; }
    .fl { color: #666666 !important; }
    .bold { font-weight: 600; }
    .pill { display: inline-flex; align-items: center; padding: 2px 7px; border-radius: 20px; font-size: 11px; font-weight: 600; }
    .pg { background-color: rgba(74,158,47,0.15); color: #4a9e2f; }
    .pa { background-color: rgba(212,137,26,0.15); color: #d4891a; }
    .pr { background-color: rgba(224,82,82,0.15); color: #e05252; }
    .pb { background-color: rgba(47,125,212,0.15); color: #2f7dd4; }
</style>
""", unsafe_allow_html=True)

# --- 1. Live API Data Fetching Engine ---
@st.cache_data(ttl=1800)  # Cached for 30 minutes to manage live API rate limits
def fetch_and_compile_data():
    api_url = "https://redash.vahan.link/api/queries/17631/results.json"
    api_key = "4aFm2iOoyx8I91svQccdeZr0jmaiUsMFSRinZcmu"
    
    try:
        response = requests.get(api_url, params={"api_key": api_key}, timeout=45)
        response.raise_for_status()
        rows = response.json()["query_result"]["data"]["rows"]
        return pd.DataFrame(rows)
    except Exception as e:
        st.error(f"Critical Ingestion Pipeline Failure: {e}")
        return pd.DataFrame()

df_raw = fetch_and_compile_data()

if df_raw.empty:
    st.error("Data pipeline empty. Verify query compilation status or Redash API availability.")
    st.stop()

# Format dates and metrics cleanly
df_raw['day'] = pd.to_datetime(df_raw['day']).dt.date
df_raw['week'] = pd.to_datetime(df_raw['week']).dt.date
for col in ['ls', 'uniq', 'ob', 'ft']:
    if col in df_raw.columns:
        df_raw[col] = pd.to_numeric(df_raw[col], errors='coerce').fillna(0).astype(int)

# --- 2. Global Dimension Definitions ---
allClients = sorted(list(df_raw['client'].dropna().unique()))
allRegions = sorted(list(df_raw['region'].dropna().unique()))

# --- 3. Sidebar Date Math & Apples-to-Apples Configuration ---
st.sidebar.header("⏱️ Filters & Timeframe")
view_mode = st.sidebar.radio("Time Aggregation Scope", ["MTD (Month-to-Date)", "WTD (Week-to-Date)"])
exclude_incomplete = st.sidebar.checkbox("Exclude trailing incomplete week metrics", value=False)

# Grounding processing clock to execution window matrix (June 2026 Context)
operational_today = date(2026, 6, 22)

if exclude_incomplete:
    days_to_subtract = operational_today.weekday() + 1
    reference_date = operational_today - timedelta(days=days_to_subtract)
else:
    reference_date = operational_today

# Target structural date buckets initialization matching your strict apples-to-apples logic
if view_mode == "MTD (Month-to-Date)":
    curr_start = reference_date.replace(day=1)
    curr_end = reference_date
    
    prev_month = 12 if curr_start.month == 1 else curr_start.month - 1
    prev_year = curr_start.year - 1 if curr_start.month == 1 else curr_start.year
    prev_start = date(prev_year, prev_month, 1)
    try:
        prev_end = date(prev_year, prev_month, reference_date.day)
    except ValueError:
        # Catch month length differences safely (e.g. March 31 ➔ Feb 28)
        prev_end = (date(prev_year, prev_month + 1, 1) - timedelta(days=1))
else:
    curr_start = reference_date - timedelta(days=reference_date.weekday())
    curr_end = reference_date
    prev_start = curr_start - timedelta(days=7)
    prev_end = curr_end - timedelta(days=7)

st.sidebar.markdown("---")
st.sidebar.subheader("📅 Active Comparison Matrix")
st.sidebar.caption(f"**Current Scope:**\n`{curr_start}` ➔ `{curr_end}`")
st.sidebar.caption(f"**Previous Scope:**\n`{prev_start}` ➔ `{prev_end}`")

# Slice functional DataFrames
df_curr = df_raw[(df_raw['day'] >= curr_start) & (df_raw['day'] <= curr_end)]
df_prev = df_raw[(df_raw['day'] >= prev_start) & (df_raw['day'] <= prev_end)]

# --- 4. Dynamic HTML Object Compiler ---
def build_html_metric_payload(df_c, df_p):
    compiled = {}
    
    def get_pct(a, b): return round((a / b * 100), 2) if b > 0 else 0.0
    def get_pp(a, b): return round(a - b, 2)

    # Core Macro Totals
    fj = {"ls": int(df_c['ls'].sum()), "uniqueness": int(df_c['uniq'].sum()), "ob": int(df_c['ob'].sum()), "ft": int(df_c['ft'].sum())}
    fm = {"ls": int(df_p['ls'].sum()), "uniqueness": int(df_p['uniq'].sum()), "ob": int(df_p['ob'].sum()), "ft": int(df_p['ft'].sum())}
    
    compiled["overall_funnel"] = {
        "ls_j": fj["ls"], "ls_m": fm["ls"], "ls_delta": fj["ls"] - fm["ls"],
        "uniq_j": fj["uniqueness"], "uniq_m": fm["uniqueness"], "uniq_delta": fj["uniqueness"] - fm["uniqueness"],
        "up_j": get_pct(fj["uniqueness"], fj["ls"]), "up_m": get_pct(fm["uniqueness"], fm["ls"]), "up_dp": get_pp(get_pct(fj["uniqueness"], fj["ls"]), get_pct(fm["uniqueness"], fm["ls"])),
        "ob_j": fj["ob"], "ob_m": fm["ob"], "ob_delta": fj["ob"] - fm["ob"],
        "op_j": get_pct(fj["ob"], fj["uniqueness"]), "op_m": get_pct(fm["ob"], fm["uniqueness"]), "op_dp": get_pp(get_pct(fj["ob"], fj["uniqueness"]), get_pct(fm["ob"], fm["uniqueness"])),
        "ft_j": fj["ft"], "ft_m": fm["ft"], "ft_delta": fj["ft"] - fm["ft"],
        "fp_j": get_pct(fj["ft"], fj["ob"]), "fp_m": get_pct(fm["ft"], fm["ob"]), "fp_dp": get_pp(get_pct(fj["ft"], fj["ob"]), get_pct(fm["ft"], fm["ob"]))
    }

    def roll_dim(df_w_c, df_w_p, dim_key):
        c_grp = df_w_c.groupby(dim_key).sum()
        p_grp = df_w_p.groupby(dim_key).sum()
        m = c_grp.join(p_grp, lsuffix='_c', rsuffix='_p', how='outer').fillna(0)
        res = []
        for d, r in m.iterrows():
            res.append({
                "dim": str(d),
                "jun": {"ls": int(r['ls_c']), "uniqueness": int(r['uniq_c']), "ob": int(r['ob_c']), "ft": int(r['ft_c'])},
                "may": {"ls": int(r['ls_p']), "uniqueness": int(r['uniq_p']), "ob": int(r['ob_p']), "ft": int(r['ft_p'])}
            })
        return res

    compiled["by_client"] = roll_dim(df_c, df_p, 'client')
    compiled["by_product"] = roll_dim(df_c, df_p, 'lead_referral_type') if 'lead_referral_type' in df_c.columns else roll_dim(df_c, df_p, 'client').copy()
    compiled["by_region"] = roll_dim(df_c, df_p, 'region')
    compiled["by_vl"] = roll_dim(df_c, df_p, 'vl_name')
    
    compiled["funnel_drill"] = {}
    for cl in df_c['client'].unique():
        sub_c = df_c[df_c['client'] == cl]
        sub_p = df_p[df_p['client'] == cl]
        compiled["funnel_drill"][cl] = {
            "by_product": roll_dim(sub_c, sub_p, 'lead_referral_type') if 'lead_referral_type' in df_c.columns else [],
            "by_region": roll_dim(sub_c, sub_p, 'region'),
            "by_vl": roll_dim(sub_c, sub_p, 'vl_name')
        }

    return compiled

payload = build_html_metric_payload(df_curr, df_prev)

# --- 5. Column & Cell Render Pipeline ---
def get_colored_delta(v, suffix=""):
    if v is None: return "—"
    if v == 0: return f"0{suffix}"
    cl = "up" if v > 0 else "dn"
    sign = "+" if v > 0 else ""
    if suffix in ["pp", "%"]:
        return f'<span class="{cl}">{sign}{abs(v):.2f}{suffix}</span>'
    
    val = abs(v)
    if val >= 1e6: f_val = f"{val/1e6:.1f}M"
    elif val >= 1e3: f_val = f"{val:,.0f}"
    else: f_val = str(val)
    return f'<span class="{cl}">{sign}{f_val}</span>'

def get_pill_pct(p, metric_type):
    v = round(p)
    if metric_type == 'uniq':
        cl = 'pg' if v >= 40 else ('pa' if v >= 20 else 'pr')
    elif metric_type == 'ob':
        cl = 'pg' if v >= 5 else ('pa' if v >= 1 else 'pr')
    else:
        cl = 'pg' if v >= 60 else ('pa' if v >= 40 else 'pr')
    return f'<span class="pill {cl}">{v}%</span>'

def transform_to_replicated_dataframe(rows_list):
    processed = []
    for r in rows_list:
        vj, vm = r["jun"], r["may"]
        
        up_j = round((vj["uniqueness"] / vj["ls"] * 100), 2) if vj["ls"] > 0 else 0.0
        up_m = round((vm["uniqueness"] / vm["ls"] * 100), 2) if vm["ls"] > 0 else 0.0
        
        op_j = round((vj["ob"] / vj["uniqueness"] * 100), 2) if vj["uniqueness"] > 0 else (round((vj["ob"] / vj["ls"] * 100), 2) if vj["ls"] > 0 else 0.0)
        const_base_p = vm["uniqueness"] if vm["uniqueness"] > 0 else vm["ls"]
        op_m = round((vm["ob"] / const_base_p * 100), 2) if const_base_p > 0 else 0.0
        
        fp_j = round((vj["ft"] / vj["ob"] * 100), 2) if vj["ob"] > 0 else 0.0
        fp_m = round((vm["ft"] / vm["ob"] * 100), 2) if vm["ob"] > 0 else 0.0

        processed.append({
            "Dimension": r["dim"],
            "LS Jun": vj["ls"], "LS May": vm["ls"], "LS Δ": vj["ls"] - vm["ls"], "LS Δ%": round(((vj["ls"] - vm["ls"]) / vm["ls"] * 100), 1) if vm["ls"] > 0 else None,
            "Uniq Jun": vj["uniqueness"], "Uniq May": vm["uniqueness"], "Uniq Δ": vj["uniqueness"] - vm["uniqueness"],
            "Uniq%": up_j, "Uniq Δpp": round(up_j - up_m, 2),
            "OB Jun": vj["ob"], "OB May": vm["ob"], "OB Δ": vj["ob"] - vm["ob"],
            "OB%": op_j, "OB Δpp": round(op_j - op_m, 2),
            "FT Jun": vj["ft"], "FT May": vm["ft"], "FT Δ": vj["ft"] - vm["ft"], "FT Δ%": round(((vj["ft"] - vm["ft"]) / vm["ft"] * 100), 1) if vm["ft"] > 0 else None,
            "FT/OB%": fp_j, "FT/OB Δpp": round(fp_j - fp_m, 2)
        })
    return pd.DataFrame(processed)

def display_replicated_table(df, key_prefix):
    if df.empty:
        st.write("No matching entries found.")
        return
        
    ordered_cols = [
        "Dimension", "LS Jun", "LS May", "LS Δ", "LS Δ%", "Uniq Jun", "Uniq May", "Uniq Δ",
        "Uniq%", "Uniq Δpp", "OB Jun", "OB May", "OB Δ", "OB%", "OB Δpp", "FT Jun", "FT May",
        "FT Δ", "FT Δ%", "FT/OB%", "FT/OB Δpp"
    ]
    df = df[ordered_cols].copy()
    
    formatted_html = "<table><thead><tr>" + "".join([f"<th>{col}</th>" for col in ordered_cols]) + "</tr></thead><tbody>"
    
    for _, r in df.iterrows():
        formatted_html += "<tr>"
        formatted_html += f"<td class='bold'>{r['Dimension']}</td>"
        formatted_html += f"<td>{r['LS Jun']:,}</td>"
        formatted_html += f"<td class='fl'>{r['LS May']:,}</td>"
        formatted_html += f"<td>{get_colored_delta(r['LS Δ'])}</td>"
        formatted_html += f"<td>{get_colored_delta(r['LS Δ%'], '%')}</td>"
        formatted_html += f"<td>{r['Uniq Jun']:,}</td>"
        formatted_html += f"<td class='fl'>{r['Uniq May']:,}</td>"
        formatted_html += f"<td>{get_colored_delta(r['Uniq Δ'])}</td>"
        formatted_html += f"<td>{get_pill_pct(r['Uniq%'], 'uniq')}</td>"
        formatted_html += f"<td>{get_colored_delta(r['Uniq Δpp'], 'pp')}</td>"
        formatted_html += f"<td>{r['OB Jun']:,}</td>"
        formatted_html += f"<td class='fl'>{r['OB May']:,}</td>"
        formatted_html += f"<td>{get_colored_delta(r['OB Δ'])}</td>"
        formatted_html += f"<td>{get_pill_pct(r['OB%'], 'ob')}</td>"
        formatted_html += f"<td>{get_colored_delta(r['OB Δpp'], 'pp')}</td>"
        formatted_html += f"<td class='bold'>{r['FT Jun']:,}</td>"
        formatted_html += f"<td class='fl'>{r['FT May']:,}</td>"
        formatted_html += f"<td>{get_colored_delta(r['FT Δ'])}</td>"
        formatted_html += f"<td>{get_colored_delta(r['FT Δ%'], '%')}</td>"
        formatted_html += f"<td>{get_pill_pct(r['FT/OB%'], 'ft')}</td>"
        formatted_html += f"<td>{get_colored_delta(r['FT/OB Δpp'], 'pp')}</td>"
        formatted_html += "</tr>"
        
    formatted_html += "</tbody></table>"
    st.components.v1.html(f"""
    <style>
        table {{ width: 100%; border-collapse: collapse; font-family: -apple-system, sans-serif; font-size: 12px; }}
        th {{ text-align: left; background: #f7f6f3; padding: 6px 8px; border-bottom: 1px solid #eceae4; font-size: 11px; color: #666; white-space: nowrap; }}
        td {{ padding: 6px 8px; border-bottom: 0.5px solid rgba(0,0,0,0.08); white-space: nowrap; }}
        tr:hover td {{ background: #f7f6f3; }}
        .bold {{ font-weight: 600; }}
        .fl {{ color: #aaa; }}
        .up {{ color: #4a9e2f; font-weight: 600; }}
        .dn {{ color: #e05252; font-weight: 600; }}
        .pill {{ inline-block; padding: 2px 6px; border-radius: 12px; font-size: 10px; font-weight: 600; }}
        .pg {{ background: rgba(74,158,47,0.15); color: #4a9e2f; }}
        .pa {{ background: rgba(212,137,26,0.15); color: #d4891a; }}
        .pr {{ background: rgba(224,82,82,0.15); color: #e05252; }}
    </style>
    {formatted_html}
    """, height=max(120, len(df)*32 + 50), scrolling=True)

# --- 6. Nav Tabs Core Implementation ---
tab_ui, tab_rca = st.tabs(["📊 Funnel view", "✨ AI Summary"])

# ==========================================
# RENDER SCOPE: REPLICATED FUNNEL ENGINE
# ==========================================
with tab_ui:
    st.markdown("### Overall funnel — Jun vs May")
    fo = payload["overall_funnel"]
    
    st.components.v1.html(f"""
    <style>
        .row {{ display: flex; gap: 8px; font-family: -apple-system, sans-serif; }}
        .card {{ flex: 1; background: #fff; border: 0.5px solid rgba(0,0,0,0.08); border-radius: 8px; padding: 12px; text-align: center; }}
        .val {{ font-size: 20px; font-weight: 500; }}
        .lbl {{ font-size: 10px; color: #666; text-transform: uppercase; margin: 3px 0; }}
        .sub {{ font-size: 11px; color: #aaa; }}
        .up {{ color: #4a9e2f; font-weight: 600; }} .dn {{ color: #e05252; font-weight: 600; }}
    </style>
    <div class="row">
        <div class="card"><div class="val">{fo['ls_j']:,}</div><div class="lbl">LS</div><div class="sub">May: {fo['ls_m']:,}</div><div><span class="{ 'up' if fo['ls_delta']>=0 else 'dn' }">{fo['ls_delta']:+,}</div></div>
        <div class="card"><div class="val">{fo['uniq_j']:,}</div><div class="lbl">Unique</div><div class="sub">May: {fo['uniq_m']:,}</div><div><span class="{ 'up' if fo['uniq_delta']>=0 else 'dn' }">{fo['uniq_delta']:+,}</div></div>
        <div class="card"><div class="val">{fo['ob_j']:,}</div><div class="lbl">OB</div><div class="sub">May: {fo['ob_m']:,}</div><div><span class="{ 'up' if fo['ob_delta']>=0 else 'dn' }">{fo['ob_delta']:+,}</div></div>
        <div class="card"><div class="val">{fo['ft_j']:,}</div><div class="lbl">FT</div><div class="sub">May: {fo['ft_m']:,}</div><div><span class="{ 'up' if fo['ft_delta']>=0 else 'dn' }">{fo['ft_delta']:+,}</div></div>
    </div>
    """, height=110)

    st.markdown("#### Client cut")
    display_replicated_table(transform_to_replicated_dataframe(payload["by_client"]), "s1")

    st.markdown("#### Product type cut")
    display_replicated_table(transform_to_replicated_dataframe(payload["by_product"]), "s2")

    st.markdown("#### Region cut")
    display_replicated_table(transform_to_replicated_dataframe(payload["by_region"]), "s4")

    st.markdown("#### VL cut — configurable top N")
    top_n_vl = st.slider("Select display window matrix sizing constraints", min_value=5, max_value=100, value=20)
    display_replicated_table(transform_to_replicated_dataframe(payload["by_vl"]).head(top_n_vl), "s5")

    st.markdown("#### Client × VL Matrix Drilldown")
    selected_client_drill = st.selectbox("Isolate Account Filter", ["All Clients"] + allClients)
    
    if selected_client_drill != "All Clients":
        drilled_rows = payload["funnel_drill"].get(selected_client_drill, {}).get("by_vl", [])
    else:
        drilled_rows = []
        for c, data in payload["funnel_drill"].items():
            for row in data["by_vl"]:
                drilled_rows.append({**row, "dim": f"{c} · {row['dim']}"})
                
    display_replicated_table(transform_to_replicated_dataframe(drilled_rows), "s9")


# ==========================================
# RENDER SCOPE: CONFIGURABLE AI SUMMARY VIEW
# ==========================================
with tab_rca:
    st.markdown("## ✨ Automated Prioritized Funnel RCA Summary")
    
    # ── CONTEXT INTERACTIVE SELECTORS ──
    filter_col1, filter_col2 = st.columns(2)
    with filter_col1:
        rca_client_filter = st.selectbox("Investigate Specific Account Portfolio", ["All Accounts"] + allClients)
    with filter_col2:
        rca_region_filter = st.selectbox("Isolate Geo-Spatial Territory", ["All Regions"] + allRegions)
        
    # Contextual Slicing Engine dedicated completely to RCA calculations
    df_rca_curr = df_curr.copy()
    df_rca_prev = df_prev.copy()
    
    if rca_client_filter != "All Accounts":
        df_rca_curr = df_rca_curr[df_rca_curr['client'] == rca_client_filter]
        df_rca_prev = df_rca_prev[df_rca_prev['client'] == rca_client_filter]
    if rca_region_filter != "All Regions":
        df_rca_curr = df_rca_curr[df_rca_curr['region'] == rca_region_filter]
        df_rca_prev = df_rca_prev[df_rca_prev['region'] == rca_region_filter]
        
    # Compile dynamic contextual metrics
    payload_rca = build_html_metric_payload(df_rca_curr, df_rca_prev)
    fo_rca = payload_rca["overall_funnel"]
    
    # ── OVERVIEW A: OVERALL VIEW ──
    st.markdown("### A. Overall view")
    if fo_rca["ft_delta"] < 0:
        st.error(f"🔴 **System Performance Bottleneck:** First Trips dropped by **{abs(fo_rca['ft_delta']):,} FT** inside the configured filter parameters.")
        
        rca_bullets = []
        if fo_rca["fp_dp"] < 0:
            rca_bullets.append(f"<li><strong>P0 Bottleneck Found (OB ➔ FT Rate Decay):</strong> Onboarding deployment conversion down by <strong>{abs(fo_rca['fp_dp'])}pp</strong> (falling from {fo_funnel['fp_m']}% to {fo_funnel['fp_j']}%). Drivers finish structural profile validation maps but drop before executing initial runs.</li>")
        if fo_rca["op_dp"] < 0:
            rca_bullets.append(f"<li><strong>P1 Bottleneck Found (Unique ➔ OB Rate Decay):</strong> Onboarding velocity shifted downwards by <strong>{abs(fo_rca['op_dp'])}pp</strong>.</li>")
        if fo_rca["up_dp"] < 0:
            rca_bullets.append(f"<li><strong>P2 Bottleneck Found (LS ➔ Unique Conversion Drop):</strong> Ingress lead uniqueness rates degraded by <strong>{abs(fo_rca['up_dp'])}pp</strong> indicating record duplication.</li>")
        if fo_rca["ls_delta"] < 0:
            rca_bullets.append(f"<li><strong>P3 Bottleneck Found (Top-of-Funnel Lead Shortfall):</strong> Baseline sourcing ingress contracted by <strong>{abs(fo_rca['ls_delta']):,} raw items</strong>.</li>")
            
        st.markdown(f"<ul>{''.join(rca_bullets)}</ul>", unsafe_wrap_html=True)
    else:
        st.success(f"🟢 **Operational Balance Intact:** Selected scope shows expansion of **+{fo_rca['ft_delta']:,} FT** over the matched historical timeline pipeline bounds.")

    st.markdown("---")
    
    # ── OVERVIEW B: CLIENT LEVEL VIEW ──
    st.markdown("### B. Client level view")
    
    client_funnels_compiled = []
    for c_obj in payload_rca["by_client"]:
        c_name = c_obj["dim"]
        vj, vm = c_obj["jun"], c_obj["may"]
        ft_delta = vj["ft"] - vm["ft"]
        
        up_j = (vj["uniqueness"] / vj["ls"] * 100) if vj["ls"] > 0 else 0.0
        up_m = (vm["uniqueness"] / vm["ls"] * 100) if vm["ls"] > 0 else 0.0
        
        op_j = (vj["ob"] / vj["uniqueness"] * 100) if vj["uniqueness"] > 0 else 0.0
        op_m = (vm["ob"] / vm["uniqueness"] * 100) if vm["uniqueness"] > 0 else 0.0
        
        fp_j = (vj["ft"] / vj["ob"] * 100) if vj["ob"] > 0 else 0.0
        fp_m = (vm["ft"] / vm["ob"] * 100) if vm["ob"] > 0 else 0.0
        
        up_dp = round(up_j - up_m, 2)
        op_dp = round(op_j - op_m, 2)
        fp_dp = round(fp_j - fp_m, 2)
        
        # Exact volume weight equation matrices implementation
        uniq_impact = round(up_dp * vj["ls"] / 100)
        ob_impact = round(op_dp * vj["uniqueness"] / 100) if vj["uniqueness"] > 0 else round(op_dp * vj["ls"] / 100)
        ft_impact = round(fp_dp * vj["ob"] / 100)

        b_tags = []
        if (vj["ls"] - vm["ls"]) < 0 and abs(vj["ls"] - vm["ls"]) > (vm["ls"] * 0.1):
            b_tags.append({"metric": "LS volume", "delta": vj["ls"] - vm["ls"], "pct": round((vj["ls"] - vm["ls"])/vm["ls"]*100, 1) if vm["ls"]>0 else 0, "severity": "high"})
        if up_dp <= -2.0:
            b_tags.append({"metric": "Uniqueness rate", "delta_pp": up_dp, "impact": uniq_impact, "severity": "high" if up_dp <= -5.0 else "medium"})
        if op_dp <= -2.0:
            b_tags.append({"metric": "OB activation rate", "delta_pp": op_dp, "impact": ob_impact, "severity": "high" if op_dp <= -5.0 else "medium"})
        if fp_dp <= -2.0:
            b_tags.append({"metric": "FT/OB conversion rate", "delta_pp": fp_dp, "impact": ft_impact, "severity": "high" if fp_dp <= -5.0 else "medium"})

        client_funnels_compiled.append({
            "name": c_name, "ft_abs": ft_delta, "ls_j": vj["ls"], "ls_delta": vj["ls"] - vm["ls"],
            "up_j": up_j, "up_dp": up_dp, "op_j": op_j, "op_dp": op_dp, "fp_j": fp_j, "fp_dp": fp_dp,
            "uniq_impact": uniq_impact, "ob_impact": ob_impact, "ft_impact": ft_impact, "bottlenecks": b_tags
        })

    laggard_accounts = [a for a in client_funnels_compiled if a["ft_abs"] < 0]
    laggard_accounts.sort(key=lambda x: x["ft_abs"])
    
    if not laggard_accounts:
        st.info("No drops encountered across localized client channels matching specified parameter matrix boundaries.")
    else:
        for account in laggard_accounts:
            st.markdown(f"""
            <div style='background: #fff; border: 0.5px solid rgba(0,0,0,0.08); border-left: 4px solid #e05252; border-radius: 8px; padding: 12px; margin-bottom: 12px;'>
                <div style='display:flex; justify-content: space-between; align-items: center;'>
                    <span style='font-size:13px; font-weight:600;'>{account['name'].upper()}</span>
                    <span class='dn'>{account['ft_abs']:,} Placements Drop</span>
                </div>
            </div>
            """, unsafe_wrap_html=True)
            
            if account["bottlenecks"]:
                st.markdown("**Prioritized Pipeline Failure Layers:**")
                for b in account["bottlenecks"]:
                    icon = "🔴 P0" if b["severity"] == "high" else "🟡 P1"
                    if b["metric"] == "LS volume":
                        st.markdown(f"{icon} **{b['metric']}:** Volume contracted by **{abs(b['delta']):,}** drivers.")
                    else:
                        st.markdown(f"{icon} **{b['metric']}:** Efficiency drifted by **{b['delta_pp']}%**, causing an absolute downstream leakage of **{abs(b['impact']):,} candidates** inside this segment path.")
            
            # Direct multi-filter linked Vendor Attribution extraction loop
            st.markdown("**Underperforming Network Vendor Slices (VL Cut):**")
            vl_drill_source = payload_rca["funnel_drill"].get(account["name"], {}).get("by_vl", [])
            
            vl_analysis_frame = transform_to_replicated_dataframe(vl_drill_source)
            if not vl_analysis_frame.empty and "FT Δ" in vl_analysis_frame.columns:
                worst_performing_vls = vl_analysis_frame[vl_analysis_frame["FT Δ"] < 0].sort_values(by="FT Δ").head(3)
                
                if not worst_performing_vls.empty:
                    for _, v_row in worst_performing_vls.iterrows():
                        st.markdown(f"- 📉 Vendor **{v_row['Dimension']}**: Account Drop Contribution of **{v_row['FT Δ']} FT** (Jun: {v_row['FT Jun']} vs Baseline: {v_row['FT May']})")
                else:
                    st.caption("Friction balanced across vendor metrics; no distinct statistical laggard anomalies registered.")
            else:
                st.caption("No operational vendor data discovered for this current filter footprint layout configuration.")
