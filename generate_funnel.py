import streamlit as st
import pandas as pd
import requests
from datetime import date, timedelta

# --- Executive Dashboard Configuration ---
st.set_page_config(page_title="Executive Funnel Review & Core RCA", layout="wide")

# Global High-Contrast Styling Tokens (Guarantees crisp visibility in both Light and Dark mode)
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
@st.cache_data(ttl=1800)  # Cached for 30 minutes to safeguard live endpoint thresholds
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
    st.error("Data pipeline empty. Please verify query compilation status or Redash API availability.")
    st.stop()

# Format dates and metrics cleanly
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

# --- 3. Sidebar Timeframe Configuration Engine ---
st.sidebar.header("⏱️ Operational Scope")
view_mode = st.sidebar.radio("Time Aggregation Scope", ["MTD (Month-to-Date)", "WTD (Week-to-Date)"])
exclude_incomplete = st.sidebar.checkbox("Exclude trailing incomplete week metrics", value=False)

# Grounding processing clock to June 2026 reporting frame context
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

# --- Dynamic Interactive Filters Suite ---
st.sidebar.markdown("---")
st.sidebar.subheader("🔍 Funnel Multi-Select Filters")

selected_weeks = st.sidebar.multiselect("Filter by Specific Week", options=["All"] + allWeeks, default=["All"])
selected_clients = st.sidebar.multiselect("Filter by Client", options=["All"] + allClients, default=["All"])
selected_regions = st.sidebar.multiselect("Filter by Region", options=["All"] + allRegions, default=["All"])
selected_vls = st.sidebar.multiselect("Filter by Vendor Lead (VL)", options=["All"] + allVLs, default=["All"])
selected_cls = st.sidebar.multiselect("Filter by Core Leader (CL)", options=["All"] + allCLs, default=["All"])
selected_ams = st.sidebar.multiselect("Filter by Account Manager (AM)", options=["All"] + allAMs, default=["All"])

# Generate segmented working boundaries
df_curr = df_raw[(df_raw['day'] >= curr_start) & (df_raw['day'] <= curr_end)]
df_prev = df_raw[(df_raw['day'] >= prev_start) & (df_raw['day'] <= prev_end)]

# Apply multi-select dimension logic evenly across both frames to protect historical comparison mapping
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
        if selected_cls and "All" not in selected_cls:
            target_df = target_df[target_df['cl'].isin(selected_cls)]
        if selected_ams and "All" not in selected_ams:
            target_df = target_df[target_df['am_name'].isin(selected_ams)]
    return target_df

df_curr = apply_dimensional_filters(df_curr)
df_prev = apply_dimensional_filters(df_prev)

# --- 4. Executive Top-Banner Component ---
st.info(f"📅 **Active Constraints Matrix Window** | **Current Scope:** `{curr_start}` to `{curr_end}` vs **Matching Historical Baseline:** `{prev_start}` to `{prev_end}`")

# --- 5. Core Metrics Analytics Processing Engine ---
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

    # Protected dimension rollup function isolating numeric targets
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

# --- 6. High-Contrast Render Pipeline (With Native JS Column Sorter) ---
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
        st.write("No rows match the specified criteria.")
        return
        
    ordered_cols = [
        "Dimension", "LS Jun", "LS May", "LS Δ", "LS Δ%", "Uniq Jun", "Uniq May", "Uniq Δ",
        "Uniq%", "Uniq Δpp", "OB Jun", "OB May", "OB Δ", "OB%", "OB Δpp", "FT Jun", "FT May",
        "FT Δ", "FT Δ%", "FT/OB%", "FT/OB Δpp"
    ]
    df = df[ordered_cols].copy()
    
    formatted_html = f"<table id='table_{key_prefix}'><thead><tr>" + "".join([f"<th>{col} ↕</th>" for col in ordered_cols]) + "</tr></thead><tbody>"
    
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
    
    # Embedded Vanilla JS Sorter script
    st.components.v1.html(f"""
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
    """, height=max(140, len(df)*32 + 50), scrolling=True)

# --- 7. Layout Nav Tabs Initialization ---
tab_ui, tab_rca = st.tabs(["📊 Funnel view", "✨ AI Summary"])

# ==========================================
# RENDER SCOPE: FUNNEL VIEW METRICS ENGINE
# ==========================================
with tab_ui:
    st.markdown("### Overall funnel — Jun vs May")
    fo = payload["overall_funnel"]
    
    st.components.v1.html(f"""
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
        <div class="card"><div class="val">{fo['ls_j']:,}</div><div class="lbl">LS</div><div class="sub">May: {fo['ls_m']:,}</div><div><span class="{ 'up' if fo['ls_delta']>=0 else 'dn' }">{fo['ls_delta']:+,}</span></div></div>
        <div class="card"><div class="val">{fo['uniq_j']:,}</div><div class="lbl">Unique</div><div class="sub">May: {fo['uniq_m']:,}</div><div><span class="{ 'up' if fo['uniq_delta']>=0 else 'dn' }">{fo['uniq_delta']:+,}</span></div></div>
        <div class="card"><div class="val">{fo['ob_j']:,}</div><div class="lbl">OB</div><div class="sub">May: {fo['ob_m']:,}</div><div><span class="{ 'up' if fo['ob_delta']>=0 else 'dn' }">{fo['ob_delta']:+,}</span></div></div>
        <div class="card"><div class="val">{fo['ft_j']:,}</div><div class="lbl">FT</div><div class="sub">May: {fo['ft_m']:,}</div><div><span class="{ 'up' if fo['ft_delta']>=0 else 'dn' }">{fo['ft_delta']:+,}</span></div></div>
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
# RENDER SCOPE: EX-SUMMARY TAB (RCA ENGINE)
# ==========================================
with tab_rca:
    st.markdown("## ⚙️ Strategic Root Cause Analysis — Volume-Weighted Impact Models")
    
    # Context Selection Engine to filter down localized accounts or geo-spaces interactive models
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
    
    st.markdown("### A. Overall view")
    if fo_rca["ft_delta"] < 0:
        st.error(f"🔴 **Operational Deficit Detected:** Full pipeline output shifted by **{fo_rca['ft_delta']:,} Net Placements (FT)** inside selected configuration boundaries.")
        
        rca_bullets = []
        if fo_rca["fp_dp"] < 0:
            rca_bullets.append(f"<li><strong>P0 Conversion Velocity Friction (OB ➔ FT):</strong> Deployment conversion efficiency contracted by <strong>{abs(fo_rca['fp_dp'])}pp</strong> (slipped from {fo_rca['fp_m']}% down to {fo_rca['fp_j']}%). Documented profiles are reaching full validation parameters but default before scheduling their first assignment.</li>")
        if fo_rca["op_dp"] < 0:
            rca_bullets.append(f"<li><strong>P1 Onboarding Pipeline Friction (Unique ➔ OB):</strong> Sourcing-to-Profile verification completion dropped by <strong>{abs(fo_rca['op_dp'])}pp</strong>.</li>")
        if fo_rca["up_dp"] < 0:
            rca_bullets.append(f"<li><strong>P2 Sourcing Invalidation Contamination (LS ➔ Unique):</strong> Unique entry verification rates degraded by <strong>{abs(fo_rca['up_dp'])}pp</strong> indicating record duplication ingress.</li>")
        if fo_rca["ls_delta"] < 0:
            rca_bullets.append(f"<li><strong>P3 Raw Intake Deficit (Top-of-Funnel Sourcing Pool):</strong> Gross pipeline acquisition pool shrank by <strong>{abs(fo_rca['ls_delta'])} raw lead submissions</strong>.</li>")
            
        st.markdown(f"<ul>{''.join(rca_bullets)}</ul>", unsafe_allow_html=True)
    else:
        st.success(f"🟢 **Funnel Conversion Velocity Optimal:** System parameters expanded by **+{fo_rca['ft_delta']:,} Net Placements** relative to comparison baseline frameworks.")

    st.markdown("---")
    st.markdown("### B. Executive Client-Level Variance Loss Attribution")
    
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
        st.info("No deficit vectors logged across business channels matching current tracking parameters.")
    else:
        for account in laggard_accounts:
            st.markdown(f"""
            <div style='background: #ffffff !important; border: 0.5px solid rgba(0,0,0,0.08); border-left: 4px solid #e05252; border-radius: 8px; padding: 12px; margin-bottom: 12px;'>
                <div style='display:flex; justify-content: space-between; align-items: center;'>
                    <span style='font-size:13px; font-weight:600; color: #111111 !important;'>{account['name'].upper()}</span>
                    <span style='color: #e05252 !important; font-weight: 600;'>{account['ft_abs']:,} Placements Variance Loss</span>
                </div>
            </div>
            """, unsafe_wrap_html=True)
            
            if account["bottlenecks"]:
                st.markdown("**Identified Local Loss Metrics:**")
                for b in account["bottlenecks"]:
                    icon = "🔴 **P0 CRITICAL**" if b["severity"] == "high" else "🟡 **P1 WARNING**"
                    if b["metric"] == "LS volume":
                        st.markdown(f"{icon} **{b['metric']}:** Intake pool contracted by **{abs(b['delta']):,} drivers**.")
                    else:
                        st.markdown(f"{icon} **{b['metric']}:** Layer conversion shifted by **{b['delta_pp']}%**, causing an calculated downstream leakage of **{abs(b['impact']):,} expected elements** inside this commercial loop branch.")
            
            # Re-scoping sub-aggregates to locate contributing Vendor Lead (VL) anomalies
            st.markdown("**Vendor Attrition Core (Top-3 Contributing Laggards):**")
            vl_drill_source = payload_rca["funnel_drill"].get(account["name"], {}).get("by_vl", [])
            
            vl_analysis_frame = transform_to_replicated_dataframe(vl_drill_source)
            if not vl_analysis_frame.empty and "FT Δ" in vl_analysis_frame.columns:
                worst_performing_vls = vl_analysis_frame[vl_analysis_frame["FT Δ"] < 0].sort_values(by="FT Δ").head(3)
                
                if not worst_performing_vls.empty:
                    for _, v_row in worst_performing_vls.iterrows():
                        st.markdown(f"- 📉 Vendor Partner **{v_row['Dimension']}**: Net Deficit of **{v_row['FT Δ']} Placements** (Jun: {v_row['FT Jun']} vs Baseline: {v_row['FT May']})")
                else:
                    st.caption("Friction normalized across channels; no structural outliers found breaking operational limits.")
            else:
                st.caption("No operational vendor network tags mapped to this filtered space parameters setup footprint configuration.")
