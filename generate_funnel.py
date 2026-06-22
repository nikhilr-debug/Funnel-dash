import streamlit as st
import pandas as pd
import requests
import json
from datetime import date, timedelta

# --- Executive Dashboard Configuration ---
st.set_page_config(page_title="Executive Funnel Review & Conversion Insights", layout="wide")

# Global High-Contrast Styling Tokens (Guarantees absolute text visibility across light and dark user themes)
st.markdown("""
<style>
    .up { color: #4a9e2f !important; font-weight: 600; }
    .dn { color: #e05252 !important; font-weight: 600; }
    .fl { color: #888888 !important; }
    .bold { font-weight: 600; }
    .pill { display: inline-flex; align-items: center; padding: 2px 7px; border-radius: 20px; font-size: 11px; font-weight: 600; }
    .pg { background-color: rgba(74,158,47,0.15); color: #4a9e2f; }
    .pa { background-color: rgba(212,137,26,0.15); color: #d4891a; }
    .pr { background-color: rgba(224,82,82,0.15); color: #e05252; }
    .pb { background-color: rgba(47,125,212,0.15); color: #2f7dd4; }
</style>
""", unsafe_allow_html=True)

# --- 1. Live API Data Fetching Engine ---
@st.cache_data(ttl=1800)  # 30-minute cache to safeguard Redash endpoint performance
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
    st.error("Data pipeline is empty. Please verify query execution state on Redash.")
    st.stop()

# Force clean, concrete numeric types across core funnel indicators
df_raw['day'] = pd.to_datetime(df_raw['day']).dt.date
df_raw['week'] = pd.to_datetime(df_raw['week']).dt.date
for col in ['ls', 'uniq', 'ob', 'ft']:
    if col in df_raw.columns:
        df_raw[col] = pd.to_numeric(df_raw[col], errors='coerce').fillna(0).astype(int)

# --- 2. Global Filter Dimension Definitions ---
allClients = sorted(list(df_raw['client'].dropna().unique()))
allRegions = sorted(list(df_raw['region'].dropna().unique()))
allVLs = sorted(list(df_raw['vl_name'].dropna().unique()))
allCLs = sorted(list(df_raw['cl'].dropna().unique()))
allAMs = sorted(list(df_raw['am_name'].dropna().unique()))
allWeeks = sorted(list(df_raw['week'].dropna().unique()))

# --- 3. Sidebar Filter Panel Architecture ---
st.sidebar.header("⏱️ Operational Scope")
view_mode = st.sidebar.radio("Time Aggregation Scope", ["MTD (Month-to-Date)", "WTD (Week-to-Date)"])
exclude_incomplete = st.sidebar.checkbox("Exclude trailing incomplete week metrics", value=False)

# Grounding processing clock to 2026 analytical target frame context
operational_today = date(2026, 6, 22)

if exclude_incomplete:
    days_to_subtract = operational_today.weekday() + 1
    reference_date = operational_today - timedelta(days=days_to_subtract)
else:
    reference_date = operational_today

# Replicate exact apples-to-apples baseline boundaries
if view_mode == "MTD (Month-to-Date)":
    curr_start = reference_date.replace(day=1)
    curr_end = reference_date
    
    prev_month = 12 if curr_start.month == 1 else curr_start.month - 1
    prev_year = curr_start.year - 1 if curr_start.month == 1 else curr_start.year
    prev_start = date(prev_year, prev_month, 1)
    try:
        prev_end = date(prev_year, prev_month, reference_date.day)
    except ValueError:
        prev_end = (date(prev_year, prev_month + 1, 1) - timedelta(days=1))
else:
    curr_start = reference_date - timedelta(days=reference_date.weekday())
    curr_end = reference_date
    prev_start = curr_start - timedelta(days=7)
    prev_end = curr_end - timedelta(days=7)

# --- Sidebar Multi-Select Slicers Suite ---
st.sidebar.markdown("---")
st.sidebar.subheader("🔍 Funnel Filters")

selected_weeks = st.sidebar.multiselect("Filter by Specific Week", options=["All"] + allWeeks, default=["All"])
selected_clients = st.sidebar.multiselect("Filter by Client", options=["All"] + allClients, default=["All"])
selected_regions = st.sidebar.multiselect("Filter by Region", options=["All"] + allRegions, default=["All"])
selected_vls = st.sidebar.multiselect("Filter by Vahan Leader (VL)", options=["All"] + allVLs, default=["All"])
selected_cls = st.sidebar.multiselect("Filter by Core Leader (CL)", options=["All"] + allCLs, default=["All"])
selected_ams = st.sidebar.multiselect("Filter by Account Manager (AM)", options=["All"] + allAMs, default=["All"])

# Optional Free Tier Gemini API Key Input
st.sidebar.markdown("---")
st.sidebar.subheader("🤖 Free AI Integration")
gemini_api_key = st.sidebar.text_input("Enter Free Gemini API Key", type="password", help="Get a completely free API key from Google AI Studio.")

# Generate segmented baseline dataframes
df_curr = df_raw[(df_raw['day'] >= curr_start) & (df_raw['day'] <= curr_end)]
df_prev = df_raw[(df_raw['day'] >= prev_start) & (df_raw['day'] <= prev_end)]

def apply_dimensional_filters(target_df):
    if not target_df.empty:
        if selected_weeks and "All" not in selected_weeks:
            target_df = target_df[target_df['week'].isin(selected_weeks)]
        if selected_clients and "All" not in selected_clients:
            target_df = target_df[target_df['client'].isin(selected_clients)]
        if selected_regions and "All" not in selected_regions:
            target_df = target_df[target_df['region'].isin(selected_regions)]
        if selected_vls and "All" not in selected_vls:
            target_df = target_df[target_df['vl_name'].isin(selected_vls)]
        if selected_cls wilderness and "All" not in selected_cls:
            target_df = target_df[target_df['cl'].isin(selected_cls)]
        if selected_ams and "All" not in selected_ams:
            target_df = target_df[target_df['am_name'].isin(selected_ams)]
    return target_df

df_curr = apply_dimensional_filters(df_curr)
df_prev = apply_dimensional_filters(df_prev)

# --- 4. Executive Top-Banner Component ---
st.info(f"📅 **Active Constraints Matrix Window** | **Current Scope:** `{curr_start}` to `{curr_end}` vs **Matching Historical Baseline:** `{prev_start}` to `{prev_end}`")

# --- 5. Global Core Data Sorters & Tables Formatting Engines ---
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
            "LS (Lead Share) Jun": vj["ls"], "LS (Lead Share) May": vm["ls"], "LS Δ": vj["ls"] - vm["ls"], "LS Δ%": round(((vj["ls"] - vm["ls"]) / vm["ls"] * 100), 1) if vm["ls"] > 0 else None,
            "Unique Jun": vj["uniqueness"], "Unique May": vm["uniqueness"], "Unique Δ": vj["uniqueness"] - vm["uniqueness"],
            "Uniq%": up_j, "Uniq Δpp": round(up_j - up_m, 2),
            "OB (Onboarded) Jun": vj["ob"], "OB (Onboarded) May": vm["ob"], "OB Δ": vj["ob"] - vm["ob"],
            "OB%": op_j, "OB Δpp": round(op_j - op_m, 2),
            "FT (First Trip) Jun": vj["ft"], "FT (First Trip) May": vm["ft"], "FT Δ": vj["ft"] - vm["ft"], "FT Δ%": round(((vj["ft"] - vm["ft"]) / vm["ft"] * 100), 1) if vm["ft"] > 0 else None,
            "FT/OB%": fp_j, "FT/OB Δpp": round(fp_j - fp_m, 2)
        })
    return pd.DataFrame(processed)

def display_replicated_table(df, key_prefix):
    if df.empty:
        st.write("No metrics matching active filter states.")
        return
        
    ordered_cols = [
        "Dimension", "LS (Lead Share) Jun", "LS (Lead Share) May", "LS Δ", "LS Δ%", "Unique Jun", "Unique May", "Unique Δ",
        "Uniq%", "Uniq Δpp", "OB (Onboarded) Jun", "OB (Onboarded) May", "OB Δ", "OB%", "OB Δpp", "FT (First Trip) Jun", "FT (First Trip) May",
        "FT Δ", "FT Δ%", "FT/OB%", "FT/OB Δpp"
    ]
    df = df[ordered_cols].copy()
    
    formatted_html = f"<table id='table_{key_prefix}'><thead><tr>" + "".join([f"<th>{col} ↕</th>" for col in ordered_cols]) + "</tr></thead><tbody>"
    
    for _, r in df.iterrows():
        formatted_html += "<tr>"
        formatted_html += f"<td class='bold'>{r['Dimension']}</td>"
        formatted_html += f"<td>{r['LS (Lead Share) Jun']:,}</td>"
        formatted_html += f"<td class='fl'>{r['LS (Lead Share) May']:,}</td>"
        formatted_html += f"<td>{get_colored_delta(r['LS Δ'])}</td>"
        formatted_html += f"<td>{get_colored_delta(r['LS Δ%'], '%')}</td>"
        formatted_html += f"<td>{r['Unique Jun']:,}</td>"
        formatted_html += f"<td class='fl'>{r['Unique May']:,}</td>"
        formatted_html += f"<td>{get_colored_delta(r['Unique Δ'])}</td>"
        formatted_html += f"<td>{get_pill_pct(r['Uniq%'], 'uniq')}</td>"
        formatted_html += f"<td>{get_colored_delta(r['Uniq Δpp'], 'pp')}</td>"
        formatted_html += f"<td>{r['OB (Onboarded) Jun']:,}</td>"
        formatted_html += f"<td class='fl'>{r['OB (Onboarded) May']:,}</td>"
        formatted_html += f"<td>{get_colored_delta(r['OB Δ'])}</td>"
        formatted_html += f"<td>{get_pill_pct(r['OB%'], 'ob')}</td>"
        formatted_html += f"<td>{get_colored_delta(r['OB Δpp'], 'pp')}</td>"
        formatted_html += f"<td class='bold'>{r['FT (First Trip) Jun']:,}</td>"
        formatted_html += f"<td class='fl'>{r['FT (First Trip) May']:,}</td>"
        formatted_html += f"<td>{get_colored_delta(r['FT Δ'])}</td>"
        formatted_html += f"<td>{get_colored_delta(r['FT Δ%'], '%')}</td>"
        formatted_html += f"<td>{get_pill_pct(r['FT/OB%'], 'ft')}</td>"
        formatted_html += f"<td>{get_colored_delta(r['FT/OB Δpp'], 'pp')}</td>"
        formatted_html += "</tr>"
        
    formatted_html += "</tbody></table>"
    
    st.iframe(f"""
    <style>
        body {{ background-color: #ffffff !important; color: #111111 !important; margin: 0; padding: 0; }}
        table {{ width: 100%; border-collapse: collapse; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; font-size: 12px; color: #111111 !important; }}
        th {{ text-align: left; background: #f7f6f3 !important; padding: 6px 8px; border-bottom: 1px solid #eceae4; font-size: 11px; color: #666666 !important; white-space: nowrap; cursor: pointer; user-select: none; }}
        th:hover {{ background: #eceae4 !important; color: #111111 !important; }}
        td {{ padding: 6px 8px; border-bottom: 0.5px solid rgba(0,0,0,0.08); white-space: nowrap; color: #111111 !important; }}
        tr:hover td {{ background: #f7f6f3 !important; }}
        .bold {{ font-weight: 600; color: #111111 !important; }}
        .fl {{ color: #888888 !important; }}
        .up {{ color: #4a9e2f !important; font-weight: 600; }}
        .dn {{ color: #e05252 !important; font-weight: 600; }}
        .pill {{ display: inline-block; padding: 2px 6px; border-radius: 12px; font-size: 10px; font-weight: 600; }}
        .pg {{ background: rgba(74,158,47,0.15); color: #4a9e2f; }}
        .pa {{ background: rgba(212,137,26,0.15); color: #d4891a; }}
        .pr {{ background: rgba(224,82,82,0.15); color: #e05252; }}
    </style>
    {formatted_html}
    <script>
    document.querySelectorAll('th').forEach(th => th.addEventListener('click', (() => {{
        const table = th.closest('table');
        const tbody = table.querySelector('tbody');
        const rows = Array.from(tbody.querySelectorAll('tr'));
        const index = Array.from(th.parentNode.children).indexOf(th);
        const asc = th.dataset.asc = !th.dataset.asc;
        
        rows.sort((rowA, rowB) => {{
            let cellA = rowA.children[index].innerText.replace(/[%|,|pp|M|K|+|↕]/g, '').trim();
            let cellB = rowB.children[index].innerText.replace(/[%|,|pp|M|K|+|↕]/g, '').trim();
            const numA = parseFloat(cellA);
            const numB = parseFloat(cellB);
            if (!isNaN(numA) && !isNaN(numB)) return asc ? numA - numB : numB - numA;
            return asc ? cellA.localeCompare(cellB) : cellB.localeCompare(cellA);
        }});
        tbody.append(...rows);
    }})));
    </script>
    """, height=max(140, len(df)*32 + 50))

# --- 8. Metrics Object Payload Compiler ---
def build_html_metric_payload(df_c, df_p):
    compiled = {}
    def get_pct(a, b): return round((a / b * 100), 2) if b > 0 else 0.0
    def get_pp(a, b): return round(a - b, 2)

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
        c_grp = df_w_c.groupby(dim_key)[['ls', 'uniq', 'ob', 'ft']].sum()
        p_grp = df_w_p.groupby(dim_key)[['ls', 'uniq', 'ob', 'ft']].sum()
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

# --- 9. Layout Nav Tabs Initialization (Fixed Parse Sequence) ---
tab_ui, tab_rca = st.tabs(["📊 Funnel view", "✨ AI Summary"])

# ==========================================
# RENDER TAB: EXECUTIVE REPLICATED FUNNEL
# ==========================================
with tab_ui:
    st.markdown("### Executive Summary — Macro Funnel Conversion Checkpoints")
    fo = payload["overall_funnel"]
    
    st.iframe(f"""
    <style>
        body {{ background-color: transparent; margin: 0; padding: 0; font-family: -apple-system, sans-serif; }}
        .row {{ display: flex; gap: 8px; }}
        .card {{ flex: 1; background: #ffffff !important; color: #111111 !important; border: 0.5px solid rgba(0,0,0,0.08); border-radius: 8px; padding: 12px; text-align: center; box-shadow: 0 1px 3px rgba(0,0,0,0.02); }}
        .val {{ font-size: 22px; font-weight: 600; color: #111111 !important; }}
        .lbl {{ font-size: 10px; color: #666666 !important; text-transform: uppercase; margin: 3px 0; letter-spacing: 0.05em; }}
        .sub {{ font-size: 11px; color: #888888 !important; }}
        .up {{ color: #4a9e2f; font-weight: 600; }} .dn {{ color: #e05252; font-weight: 600; }}
    </style>
    <div class="row">
        <div class="card"><div class="val">{fo['ls_j']:,}</div><div class="lbl">Lead Share (LS)</div><div class="sub">Prior: {fo['ls_m']:,}</div><div><span class="{ 'up' if fo['ls_delta']>=0 else 'dn' }">{fo['ls_delta']:+,}</span></div></div>
        <div class="card"><div class="val">{fo['uniq_j']:,}</div><div class="lbl">Unique to Client</div><div class="sub">Prior: {fo['uniq_m']:,}</div><div><span class="{ 'up' if fo['uniq_delta']>=0 else 'dn' }">{fo['uniq_delta']:+,}</span></div></div>
        <div class="card"><div class="val">{fo['ob_j']:,}</div><div class="lbl">Onboarded (OB)</div><div class="sub">Prior: {fo['ob_m']:,}</div><div><span class="{ 'up' if fo['ob_delta']>=0 else 'dn' }">{fo['ob_delta']:+,}</span></div></div>
        <div class="card"><div class="val">{fo['ft_j']:,}</div><div class="lbl">First Trips (FT)</div><div class="sub">Prior: {fo['ft_m']:,}</div><div><span class="{ 'up' if fo['ft_delta']>=0 else 'dn' }">{fo['ft_delta']:+,}</span></div></div>
    </div>
    """, height=115)

    st.markdown("#### Client cut")
    display_replicated_table(transform_to_replicated_dataframe(payload["by_client"]), "s1")

    st.markdown("#### Product type cut")
    display_replicated_table(transform_to_replicated_dataframe(payload["by_product"]), "s2")

    st.markdown("#### Region cut")
    display_replicated_table(transform_to_replicated_dataframe(payload["by_region"]), "s4")

    st.markdown("#### VL cut — Configurable Volume Scan")
    top_n_vl = st.slider("Select Display Window Scale (S5 Cut)", min_value=5, max_value=100, value=20)
    display_replicated_table(transform_to_replicated_dataframe(payload["by_vl"]).head(top_n_vl), "s5")

    st.markdown("#### Client × VL Matrix Drilldown")
    active_drill_list = sorted(list(df_curr['client'].dropna().unique()))
    selected_client_drill = st.selectbox("Isolate Specific Corporate Partner Focus", ["All Clients"] + active_drill_list)
    top_n_drill_s9 = st.slider("Select Display Window Scale (S9 Drilldown)", min_value=5, max_value=100, value=20)
    
    if selected_client_drill != "All Clients":
        drilled_rows = payload["funnel_drill"].get(selected_client_drill, {}).get("by_vl", [])
    else:
        drilled_rows = []
        for c, data in payload["funnel_drill"].items():
            for row in data["by_vl"]:
                drilled_rows.append({**row, "dim": f"{c} · {row['dim']}"})
                
    display_replicated_table(transform_to_replicated_dataframe(drilled_rows).head(top_n_drill_s9), "s9")


# ==========================================
# RENDER SCOPE: CONTEXTUAL RCA GENERATOR
# ==========================================
with tab_rca:
    st.markdown("## ⚙️ Blue-Collar Funnel Conversion Insights Briefing")
    st.caption("Reviewing the conversion paths of blue-collar workers referred to our clients (Lead Share) who were verified as unique to the client's database (Uniqueness), successfully completed onboarding activation (OB), and executed their first baseline shift run (FT).")
    
    filter_col1, filter_col2 = st.columns(2)
    with filter_col1:
        rca_client_filter = st.multiselect("Isolate Executive Account Segments", options=["All"] + allClients, default=["All"], key="rca_c")
    with filter_col2:
        rca_region_filter = st.multiselect("Isolate Geo-Spatial Territory Boundaries", options=["All"] + allRegions, default=["All"], key="rca_r")
        
    df_rca_curr = df_curr.copy()
    df_rca_prev = df_prev.copy()
    
    if rca_client_filter and "All" not in rca_client_filter:
        df_rca_curr = df_rca_curr[df_rca_curr['client'].isin(rca_client_filter)]
        df_rca_prev = df_rca_prev[df_rca_prev['client'].isin(rca_client_filter)]
    if rca_region_filter and "All" not in rca_region_filter:
        df_rca_curr = df_rca_curr[df_rca_curr['region'].isin(rca_region_filter)]
        df_rca_prev = df_rca_prev[df_rca_prev['region'].isin(rca_region_filter)]
        
    payload_rca = build_html_metric_payload(df_rca_curr, df_rca_prev)
    fo_rca = payload_rca["overall_funnel"]
    
    st.markdown("### A. Overall Funnel Summary")
    
    # Check if a free Gemini key was supplied to override the rule-based output with live LLM intelligence
    if gemini_api_key:
        with st.spinner("🧠 Querying free Gemini Flash layer to generate corporate analysis briefing..."):
            try:
                endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={gemini_api_key}"
                prompt_payload = {
                    "contents": [{
                        "parts": [{
                            "text": f"You are a Senior Data Analyst reporting directly to the CEO. Write a clean, professional, concise metric briefing based on this funnel performance data: {json.dumps(fo_rca)}. "
                                    f"Terminology rules: LS is Lead Share. Uniqueness means new to the client's database. OB means Onboarding/Activation. FT means completed First Trip. "
                                    f"Do not use complex technical terms like 'conversion velocity friction'. Keep it clear, insight-focused, and direct."
                        }]
                    }]
                }
                headers = {'Content-Type': 'application/json'}
                llm_response = requests.post(endpoint, headers=headers, json=prompt_payload, timeout=15)
                
                if llm_response.status_code == 200:
                    ai_text = llm_response.json()["candidates"][0]["content"]["parts"][0]["text"]
                    st.markdown(ai_text)
                else:
                    st.warning("Failed to fetch custom Gemini text payload. Defaulting to strict analytical engine.")
                    gemini_api_key = None
            except Exception:
                gemini_api_key = None

    # Deterministic Analytical Engine Fallback
    if not gemini_api_key:
        if fo_rca["ft_delta"] < 0:
            st.error(f"🔴 **Conversion Deficit:** Total First Trips (FT) dropped by **{abs(fo_rca['ft_delta']):,}** compared to the baseline period.")
            
            rca_bullets = []
            if fo_rca["fp_dp"] < 0:
                rca_bullets.append(f"<li><strong>P0 First Trip Invalidation (OB ➔ FT Rate Drop):</strong> Onboarding-to-First Trip conversion efficiency dropped by <strong>{abs(fo_rca['fp_dp'])}pp</strong> (from {fo_rca['fp_m']}% down to {fo_rca['fp_j']}%). Workers successfully completed client activation profiles but dropped out before executing their first trip.</li>")
            if fo_rca["op_dp"] < 0:
                rca_bullets.append(f"<li><strong>P1 Onboarding Disruption (Unique ➔ OB Rate Drop):</strong> Conversion from verified unique leads to successful onboarding dropped by <strong>{abs(fo_rca['op_dp'])}pp</strong>.</li>")
            if fo_rca["up_dp"] < 0:
                rca_bullets.append(f"<li><strong>P2 Lead Penetration Loss (LS ➔ Unique Uniqueness Drop):</strong> The percentage of shared leads new to the client dropped by <strong>{abs(fo_rca['up_dp'])}pp</strong>, indicating a shrinking pool of fresh worker profiles.</li>")
            if fo_rca["ls_delta"] < 0:
                rca_bullets.append(f"<li><strong>P3 Volume Contraction (Gross Lead Share Volume Drop):</strong> Total raw leads shared with the client decreased by <strong>{abs(fo_rca['ls_delta']):,} profiles</strong>.</li>")
                
            st.markdown(f"<ul>{''.join(rca_bullets)}</ul>", unsafe_allow_html=True)
        else:
            st.success(f"🟢 **Conversion Pipeline Stable:** Target funnel configuration shows expansion of **+{fo_rca['ft_delta']:,} Completed First Trips** vs. prior period baseline parameters.")

    st.markdown("---")
    st.markdown("### B. Drill-down Summary")
    
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
        
        # Volume-weighted calculations
        uniq_impact = round(up_dp * vj["ls"] / 100)
        ob_impact = round(op_dp * vj["uniqueness"] / 100) if vj["uniqueness"] > 0 else round(op_dp * vj["ls"] / 100)
        ft_impact = round(fp_dp * vj["ob"] / 100)

        b_tags = []
        if (vj["ls"] - vm["ls"]) < 0 and abs(vj["ls"] - vm["ls"]) > (vm["ls"] * 0.1):
            b_tags.append({"metric": "Lead Share (LS) volume", "delta": vj["ls"] - vm["ls"], "pct": round((vj["ls"] - vm["ls"])/vm["ls"]*100, 1) if vm["ls"]>0 else 0, "severity": "high"})
        if up_dp <= -2.0:
            b_tags.append({"metric": "Uniqueness conversion rate", "delta_pp": up_dp, "impact": uniq_impact, "severity": "high" if up_dp <= -5.0 else "medium"})
        if op_dp <= -2.0:
            b_tags.append({"metric": "Onboarding (OB) activation rate", "delta_pp": op_dp, "impact": ob_impact, "severity": "high" if op_dp <= -5.0 else "medium"})
        if fp_dp <= -2.0:
            b_tags.append({"metric": "First Trip (FT) conversion rate", "delta_pp": fp_dp, "impact": ft_impact, "severity": "high" if fp_dp <= -5.0 else "medium"})

        client_funnels_compiled.append({
            "name": c_name, "ft_abs": ft_delta, "ls_j": vj["ls"], "ls_delta": vj["ls"] - vm["ls"],
            "up_j": up_j, "up_dp": up_dp, "op_j": op_j, "op_dp": op_dp, "fp_j": fp_j, "fp_dp": fp_dp,
            "uniq_impact": uniq_impact, "ob_impact": ob_impact, "ft_impact": ft_impact, "bottlenecks": b_tags
        })

    laggard_accounts = [a for a in client_funnels_compiled if a["ft_abs"] < 0]
    laggard_accounts.sort(key=lambda x: x["ft_abs"])
    
    if not laggard_accounts:
        st.info("No deficit vectors logged across business channels matching current tracking parameters.")
    else:
        for account in laggard_accounts:
            st.markdown(f"""
            <div style='background: #ffffff !important; border: 0.5px solid rgba(0,0,0,0.08); border-left: 4px solid #e05252; border-radius: 8px; padding: 12px; margin-bottom: 12px;'>
                <div style='display:flex; justify-content: space-between; align-items: center;'>
                    <span style='font-size:13px; font-weight:600; color: #111111 !important;'>{account['name'].upper()}</span>
                    <span style='color: #e05252 !important; font-weight: 600;'>{account['ft_abs']:,} First Trips (FT) Variance Loss</span>
                </div>
            </div>
            """, unsafe_allow_html=True)  # <-- Fixed unsafe_allow_html applied correctly
            
            if account["bottlenecks"]:
                st.markdown("**Primary Operational Bottlenecks:**")
                for b in account["bottlenecks"]:
                    icon = "🔴 **P0 CRITICAL**" if b["severity"] == "high" else "🟡 **P1 WARNING**"
                    if b["metric"] == "Lead Share (LS) volume":
                        st.markdown(f"{icon} **{b['metric']}:** Shared pool shrunk by **{abs(b['delta']):,} worker profiles**.")
                    else:
                        st.markdown(f"{icon} **{b['metric']}:** Conversion efficiency drifted by **{b['delta_pp']}%**, causing a net leakage of **{abs(b['impact']):,} potential conversions** inside this account's workflow.")
            
            # Re-scoping sub-aggregates to locate contributing Vahan Leader (VL) anomalies
            st.markdown("**VL Attrition Matrix (Top-3 Contributing Laggard VLs):**")
            vl_drill_source = payload_rca["funnel_drill"].get(account["name"], {}).get("by_vl", [])
            
            vl_analysis_frame = transform_to_replicated_dataframe(vl_drill_source)
            if not vl_analysis_frame.empty and "FT Δ" in vl_analysis_frame.columns:
                worst_performing_vls = vl_analysis_frame[vl_analysis_frame["FT Δ"] < 0].sort_values(by="FT Δ").head(3)
                
                if not worst_performing_vls.empty:
                    for _, v_row in worst_performing_vls.iterrows():
                        st.markdown(f"- 📉 CL/AM Field Laggard **{v_row['Dimension']}**: Net Deficit of **{v_row['FT Δ']} Completed First Trips** (Jun: {v_row['FT (First Trip) Jun']} vs Baseline: {v_row['FT (First Trip) May']})")  # <-- Fixed exact column key matches here
                else:
                    st.caption("Friction normalized across channels; no distinct field leader anomalies registered.")
            else:
                st.caption("No operational VL network tags mapped to this filtered data space footprint.")
