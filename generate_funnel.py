import streamlit as st
import pandas as pd
import numpy as np
import requests
import json
import time
import io
import zipfile
from datetime import date, timedelta

# --- Executive Dashboard Configuration ---
st.set_page_config(page_title="Executive Funnel Review & Conversion Insights", layout="wide")

# Global High-Contrast Styling Tokens
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
    .cntrb { color: #666666 !important; font-weight: 700; background-color: #f0f0f0; padding: 2px 5px; border-radius: 4px;}
</style>
""", unsafe_allow_html=True)

# --- 1. Live API Data Fetching Engine ---
@st.cache_data(ttl=1800)
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
allWeeks = sorted(list(df_raw['week'].dropna().unique()), reverse=True)

# --- 3. Sidebar Filter Panel Architecture ---
st.sidebar.header("⏱️ Operational Scope")

# Force Data Refresh Button
if st.sidebar.button("🔄 Force Live Data Refresh", help="Clear the 30-minute cache and pull the latest numbers from the database.", use_container_width=True):
    fetch_and_compile_data.clear()
    st.rerun()

anchor_week = st.sidebar.selectbox("📅 Master Week Slicer", options=allWeeks, help="Select a week to act as 'Present Day'. Both MTD and WTD scopes will calculate accurately based on this anchor.")
operational_today = df_raw[df_raw['week'] == anchor_week]['day'].max()

view_mode = st.sidebar.radio("Time Aggregation Scope", ["MTD (Month-to-Date)", "WTD (Week-to-Date)", "Custom Date Range"])

reference_date = operational_today

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
    LBL_CURR = curr_start.strftime('%b')
    LBL_PREV = prev_start.strftime('%b')
elif view_mode == "WTD (Week-to-Date)":
    curr_start = reference_date - timedelta(days=reference_date.weekday())
    curr_end = reference_date
    prev_start = curr_start - timedelta(days=7)
    prev_end = curr_end - timedelta(days=7)
    LBL_CURR = curr_start.strftime('%d %b')
    LBL_PREV = prev_start.strftime('%d %b')
else:
    # Custom Date Range Logic
    st.sidebar.markdown("**🗓️ Custom Date Selection**")
    default_curr_start = reference_date - timedelta(days=6)
    default_curr_end = reference_date
    default_prev_start = default_curr_start - timedelta(days=7)
    default_prev_end = default_curr_end - timedelta(days=7)
    
    curr_dates = st.sidebar.date_input("Current Period (Start - End)", value=(default_curr_start, default_curr_end))
    prev_dates = st.sidebar.date_input("Baseline Period (Start - End)", value=(default_prev_start, default_prev_end))
    
    curr_start = curr_dates[0] if isinstance(curr_dates, tuple) and len(curr_dates) > 0 else curr_dates
    curr_end = curr_dates[1] if isinstance(curr_dates, tuple) and len(curr_dates) > 1 else curr_start
    
    prev_start = prev_dates[0] if isinstance(prev_dates, tuple) and len(prev_dates) > 0 else prev_dates
    prev_end = prev_dates[1] if isinstance(prev_dates, tuple) and len(prev_dates) > 1 else prev_start
    LBL_CURR = "Cur"
    LBL_PREV = "Prv"

# --- Dynamic Sort Mapping Engine ---
sort_metrics_map = {
    "FT Δ": "FT Δ", "LS Δ": "LS Δ", "Uniq Δ": "Unique Δ", "OB Δ": "OB Δ",
    "LS Δ Cntrb%": "LS Δ Cntrb%", "Uniq Δ Cntrb%": "Uniq Δ Cntrb%", "OB Δ Cntrb%": "OB Δ Cntrb%", "FT Δ Cntrb%": "FT Δ Cntrb%",
    "Uniq% Δpp": "Uniq Δpp", "OB% Δpp": "OB Δpp", "FT/OB% Δpp": "FT/OB Δpp",
    "OB/LS% Δpp": "OB/LS Δpp", "FT/LS% Δpp": "FT/LS Δpp",
    "LS Δ%": "LS Δ%", "FT Δ%": "FT Δ%", 
    f"FT {LBL_CURR}": f"FT (First Trip) {LBL_CURR}",
    f"LS {LBL_CURR}": f"LS (Lead Share) {LBL_CURR}", 
    f"Uniq% {LBL_CURR}": "Uniq%", 
    f"OB% {LBL_CURR}": "OB%", 
    f"FT/OB% {LBL_CURR}": "FT/OB%",
    f"OB/LS% {LBL_CURR}": "OB/LS%", 
    f"FT/LS% {LBL_CURR}": "FT/LS%"
}

# --- Sidebar Multi-Select Slicers Suite ---
st.sidebar.markdown("---")
st.sidebar.subheader("🔍 Funnel Filters")
st.caption("Filters isolated segments within your selected timeframe.")

selected_clients = st.sidebar.multiselect("Filter by Client", options=["All"] + allClients, default=["All"])
selected_regions = st.sidebar.multiselect("Filter by Region", options=["All"] + allRegions, default=["All"])
selected_vls = st.sidebar.multiselect("Filter by Vahan Leader (VL)", options=["All"] + allVLs, default=["All"])
selected_cls = st.sidebar.multiselect("Filter by Core Leader (CL)", options=["All"] + allCLs, default=["All"])
selected_ams = st.sidebar.multiselect("Filter by Account Manager (AM)", options=["All"] + allAMs, default=["All"])

# --- Secured Gemini API Key Vault ---
st.sidebar.markdown("---")
st.sidebar.subheader("🤖 AI Integration Active")
try:
    gemini_api_key = st.secrets["GEMINI_API_KEY"]
    st.sidebar.success("Gemini Assistant is online (Secured via st.secrets).")
except KeyError:
    st.sidebar.error("API Key not found in st.secrets. AI features disabled.")
    gemini_api_key = None

def apply_dimensional_filters(target_df):
    if not target_df.empty:
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

df_curr = apply_dimensional_filters(df_raw[(df_raw['day'] >= curr_start) & (df_raw['day'] <= curr_end)])
df_prev = apply_dimensional_filters(df_raw[(df_raw['day'] >= prev_start) & (df_raw['day'] <= prev_end)])

st.info(f"📅 **Active Constraints Matrix Window** | **Current Scope:** `{curr_start}` to `{curr_end}` vs **Matching Historical Baseline:** `{prev_start}` to `{prev_end}`")

# --- ZIP Downloader Helper Engine ---
def create_zip_download(file_dict):
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for file_name, df in file_dict.items():
            if df is not None and not df.empty:
                zip_file.writestr(f"{file_name}.csv", df.to_csv(index=False))
    return zip_buffer.getvalue()

# --- 5. Global Core Data Sorters & Tables Formatting Engines ---
def get_colored_delta(v, suffix=""):
    if v is None or pd.isna(v): return "—"
    if v == 0: return f"0{suffix}"
    cl = "up" if v > 0 else "dn"
    sign = "+" if v > 0 else ""
    if suffix in ["pp", "%"]: return f'<span class="{cl}">{sign}{abs(v):.2f}{suffix}</span>'
    val = abs(v)
    if val >= 1e6: f_val = f"{val/1e6:.1f}M"
    elif val >= 1e3: f_val = f"{val:,.0f}"
    else: f_val = str(val)
    return f'<span class="{cl}">{sign}{f_val}</span>'

def get_pill_pct(p, metric_type):
    if p is None or pd.isna(p): return "—"
    v = round(p)
    if metric_type == 'uniq': cl = 'pg' if v >= 40 else ('pa' if v >= 20 else 'pr')
    elif metric_type == 'ob': cl = 'pg' if v >= 5 else ('pa' if v >= 1 else 'pr')
    elif metric_type == 'ls_ob': cl = 'pg' if v >= 10 else ('pa' if v >= 3 else 'pr')
    elif metric_type == 'ls_ft': cl = 'pg' if v >= 5 else ('pa' if v >= 1 else 'pr')
    else: cl = 'pg' if v >= 60 else ('pa' if v >= 40 else 'pr')
    return f'<span class="pill {cl}">{v}%</span>'

def transform_to_replicated_dataframe(rows_list):
    processed = []
    
    # Calculate Total Variances for Contribution (Mix %)
    tot_ls_d = sum((r["curr"]["ls"] - r["prev"]["ls"]) for r in rows_list)
    tot_uq_d = sum((r["curr"]["uniqueness"] - r["prev"]["uniqueness"]) for r in rows_list)
    tot_ob_d = sum((r["curr"]["ob"] - r["prev"]["ob"]) for r in rows_list)
    tot_ft_d = sum((r["curr"]["ft"] - r["prev"]["ft"]) for r in rows_list)
    
    for r in rows_list:
        vc, vp = r["curr"], r["prev"]
        
        ls_d = vc["ls"] - vp["ls"]
        uq_d = vc["uniqueness"] - vp["uniqueness"]
        ob_d = vc["ob"] - vp["ob"]
        ft_d = vc["ft"] - vp["ft"]
        
        ls_cntrb = round((ls_d / tot_ls_d * 100), 1) if tot_ls_d != 0 else 0.0
        uq_cntrb = round((uq_d / tot_uq_d * 100), 1) if tot_uq_d != 0 else 0.0
        ob_cntrb = round((ob_d / tot_ob_d * 100), 1) if tot_ob_d != 0 else 0.0
        ft_cntrb = round((ft_d / tot_ft_d * 100), 1) if tot_ft_d != 0 else 0.0
        
        up_curr = round((vc["uniqueness"] / vc["ls"] * 100), 2) if vc["ls"] > 0 else 0.0
        up_prev = round((vp["uniqueness"] / vp["ls"] * 100), 2) if vp["ls"] > 0 else 0.0
        op_curr = round((vc["ob"] / vc["uniqueness"] * 100), 2) if vc["uniqueness"] > 0 else (round((vc["ob"] / vc["ls"] * 100), 2) if vc["ls"] > 0 else 0.0)
        const_base_p = vp["uniqueness"] if vp["uniqueness"] > 0 else vp["ls"]
        op_prev = round((vp["ob"] / const_base_p * 100), 2) if const_base_p > 0 else 0.0
        fp_curr = round((vc["ft"] / vc["ob"] * 100), 2) if vc["ob"] > 0 else 0.0
        fp_prev = round((vp["ft"] / vp["ob"] * 100), 2) if vp["ob"] > 0 else 0.0
        
        ob_ls_curr = round((vc["ob"] / vc["ls"] * 100), 2) if vc["ls"] > 0 else 0.0
        ob_ls_prev = round((vp["ob"] / vp["ls"] * 100), 2) if vp["ls"] > 0 else 0.0
        ft_ls_curr = round((vc["ft"] / vc["ls"] * 100), 2) if vc["ls"] > 0 else 0.0
        ft_ls_prev = round((vp["ft"] / vp["ls"] * 100), 2) if vp["ls"] > 0 else 0.0

        processed.append({
            "Dimension": r["dim"],
            f"LS (Lead Share) {LBL_CURR}": vc["ls"], f"LS (Lead Share) {LBL_PREV}": vp["ls"], "LS Δ": ls_d, "LS Δ%": round((ls_d / vp["ls"] * 100), 1) if vp["ls"] > 0 else None, "LS Δ Cntrb%": ls_cntrb,
            f"Unique {LBL_CURR}": vc["uniqueness"], f"Unique {LBL_PREV}": vp["uniqueness"], "Unique Δ": uq_d, "Uniq Δ Cntrb%": uq_cntrb,
            "Uniq%": up_curr, "Uniq Δpp": round(up_curr - up_prev, 2),
            f"OB (Onboarded) {LBL_CURR}": vc["ob"], f"OB (Onboarded) {LBL_PREV}": vp["ob"], "OB Δ": ob_d, "OB Δ Cntrb%": ob_cntrb,
            "OB%": op_curr, "OB Δpp": round(op_curr - op_prev, 2),
            f"FT (First Trip) {LBL_CURR}": vc["ft"], f"FT (First Trip) {LBL_PREV}": vp["ft"], "FT Δ": ft_d, "FT Δ%": round((ft_d / vp["ft"] * 100), 1) if vp["ft"] > 0 else None, "FT Δ Cntrb%": ft_cntrb,
            "FT/OB%": fp_curr, "FT/OB Δpp": round(fp_curr - fp_prev, 2),
            "OB/LS%": ob_ls_curr, "OB/LS Δpp": round(ob_ls_curr - ob_ls_prev, 2),
            "FT/LS%": ft_ls_curr, "FT/LS Δpp": round(ft_ls_curr - ft_ls_prev, 2)
        })
    return pd.DataFrame(processed)

def display_replicated_table(df, key_prefix):
    if df.empty:
        st.write("No metrics matching active filter states.")
        return
    ordered_cols = [
        "Dimension", 
        f"LS (Lead Share) {LBL_CURR}", f"LS (Lead Share) {LBL_PREV}", "LS Δ", "LS Δ%", "LS Δ Cntrb%",
        f"Unique {LBL_CURR}", f"Unique {LBL_PREV}", "Unique Δ", "Uniq Δ Cntrb%", "Uniq%", "Uniq Δpp", 
        f"OB (Onboarded) {LBL_CURR}", f"OB (Onboarded) {LBL_PREV}", "OB Δ", "OB Δ Cntrb%", "OB%", "OB Δpp", 
        f"FT (First Trip) {LBL_CURR}", f"FT (First Trip) {LBL_PREV}", "FT Δ", "FT Δ%", "FT Δ Cntrb%", 
        "FT/OB%", "FT/OB Δpp", "OB/LS%", "OB/LS Δpp", "FT/LS%", "FT/LS Δpp"
    ]
    df = df[ordered_cols].copy()
    formatted_html = f"<table id='table_{key_prefix}'><thead><tr>" + "".join([f"<th>{col} ↕</th>" for col in ordered_cols]) + "</tr></thead><tbody>"
    for _, r in df.iterrows():
        ls_class = "up" if r["LS Δ"] > 0 else ("dn" if r["LS Δ"] < 0 else "")
        uniq_class = "up" if r["Unique Δ"] > 0 else ("dn" if r["Unique Δ"] < 0 else "")
        ob_class = "up" if r["OB Δ"] > 0 else ("dn" if r["OB Δ"] < 0 else "")
        ft_class = "up" if r["FT Δ"] > 0 else ("dn" if r["FT Δ"] < 0 else "")
        formatted_html += "<tr>"
        formatted_html += f"<td class='bold sticky-col'>{r['Dimension']}</td>"
        formatted_html += f"<td><span class='{ls_class}'>{r[f'LS (Lead Share) {LBL_CURR}']:,}</span></td>"
        formatted_html += f"<td class='fl'>{r[f'LS (Lead Share) {LBL_PREV}']:,}</td>"
        formatted_html += f"<td>{get_colored_delta(r['LS Δ'])}</td>"
        formatted_html += f"<td>{get_colored_delta(r['LS Δ%'], '%')}</td>"
        formatted_html += f"<td><span class='cntrb'>{r['LS Δ Cntrb%']:.1f}%</span></td>"
        
        formatted_html += f"<td><span class='{uniq_class}'>{r[f'Unique {LBL_CURR}']:,}</span></td>"
        formatted_html += f"<td><span class='fl'>{r[f'Unique {LBL_PREV}']:,}</span></td>"
        formatted_html += f"<td>{get_colored_delta(r['Unique Δ'])}</td>"
        formatted_html += f"<td><span class='cntrb'>{r['Uniq Δ Cntrb%']:.1f}%</span></td>"
        formatted_html += f"<td>{get_pill_pct(r['Uniq%'], 'uniq')}</td>"
        formatted_html += f"<td>{get_colored_delta(r['Uniq Δpp'], 'pp')}</td>"
        
        formatted_html += f"<td><span class='{ob_class}'>{r[f'OB (Onboarded) {LBL_CURR}']:,}</span></td>"
        formatted_html += f"<td class='fl'>{r[f'OB (Onboarded) {LBL_PREV}']:,}</td>"
        formatted_html += f"<td>{get_colored_delta(r['OB Δ'])}</td>"
        formatted_html += f"<td><span class='cntrb'>{r['OB Δ Cntrb%']:.1f}%</span></td>"
        formatted_html += f"<td>{get_pill_pct(r['OB%'], 'ob')}</td>"
        formatted_html += f"<td>{get_colored_delta(r['OB Δpp'], 'pp')}</td>"
        
        formatted_html += f"<td class='bold'><span class='{ft_class}'>{r[f'FT (First Trip) {LBL_CURR}']:,}</span></td>"
        formatted_html += f"<td class='fl'>{r[f'FT (First Trip) {LBL_PREV}']:,}</td>"
        formatted_html += f"<td>{get_colored_delta(r['FT Δ'])}</td>"
        formatted_html += f"<td>{get_colored_delta(r['FT Δ%'], '%')}</td>"
        formatted_html += f"<td><span class='cntrb'>{r['FT Δ Cntrb%']:.1f}%</span></td>"
        
        formatted_html += f"<td>{get_pill_pct(r['FT/OB%'], 'ft')}</td>"
        formatted_html += f"<td>{get_colored_delta(r['FT/OB Δpp'], 'pp')}</td>"
        formatted_html += f"<td>{get_pill_pct(r['OB/LS%'], 'ls_ob')}</td>"
        formatted_html += f"<td>{get_colored_delta(r['OB/LS Δpp'], 'pp')}</td>"
        formatted_html += f"<td>{get_pill_pct(r['FT/LS%'], 'ls_ft')}</td>"
        formatted_html += f"<td>{get_colored_delta(r['FT/LS Δpp'], 'pp')}</td>"
        formatted_html += "</tr>"
    formatted_html += "</tbody></table>"
    
    st.iframe(f"""
    <style>
        body {{ background-color: #ffffff !important; color: #111111 !important; margin: 0; padding: 0; }}
        .table-container {{ width: 100%; height: 100vh; overflow: auto; position: relative; }}
        table {{ width: 100%; border-collapse: collapse; font-family: -apple-system, sans-serif; font-size: 12px; }}
        th {{ position: sticky; top: 0; z-index: 2; text-align: left; background: #f7f6f3 !important; padding: 6px 8px; border-bottom: 1px solid #eceae4; font-size: 11px; color: #666666 !important; white-space: nowrap; cursor: pointer; user-select: none; box-shadow: 0 1px 0 #eceae4; }}
        td {{ padding: 6px 8px; border-bottom: 0.5px solid rgba(0,0,0,0.08); white-space: nowrap; color: #111111 !important; background-color: #ffffff; }}
        tr:hover td {{ background-color: #f7f6f3 !important; }}
        td:first-child, th:first-child {{ position: sticky; left: 0; z-index: 1; border-right: 1px solid rgba(0,0,0,0.08); }}
        td:first-child {{ background-color: #ffffff; }}
        tr:hover td:first-child {{ background-color: #f7f6f3 !important; }}
        th:first-child {{ z-index: 3; background-color: #f7f6f3 !important; border-right: 1px solid #eceae4; }}
        .bold {{ font-weight: 600; color: #111111 !important; }}
        .fl {{ color: #888888 !important; }}
        .up {{ color: #4a9e2f !important; font-weight: 600; }}
        .dn {{ color: #e05252 !important; font-weight: 600; }}
        .cntrb {{ color: #666666 !important; font-weight: 700; background-color: #f0f0f0; padding: 2px 5px; border-radius: 4px;}}
        .pill {{ display: inline-block; padding: 2px 6px; border-radius: 12px; font-size: 10px; font-weight: 600; }}
        .pg {{ background: rgba(74,158,47,0.15); color: #4a9e2f; }}
        .pa {{ background: rgba(212,137,26,0.15); color: #d4891a; }}
        .pr {{ background: rgba(224,82,82,0.15); color: #e05252; }}
    </style>
    <div class="table-container">{formatted_html}</div>
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
            const numA = parseFloat(cellA); const numB = parseFloat(cellB);
            if (!isNaN(numA) && !isNaN(numB)) return asc ? numA - numB : numB - numA;
            return asc ? cellA.localeCompare(cellB) : cellB.localeCompare(cellA);
        }});
        tbody.append(...rows);
    }})));
    </script>
    """, height=max(140, min(550, len(df)*32 + 50)))

# --- Dedicated HTML Renderer for Rolling Trends Table ---
def get_trend_dataframe(df_trend, group_cols, dimension_order=None):
    if df_trend.empty:
        return pd.DataFrame()
        
    grp = df_trend.groupby(group_cols)[['ls', 'uniq', 'ob', 'ft']].sum().reset_index()
    grp['Uniq%'] = grp.apply(lambda r: round(r['uniq']/r['ls']*100, 1) if r['ls']>0 else 0.0, axis=1)
    grp['OB%'] = grp.apply(lambda r: round(r['ob']/r['uniq']*100, 1) if r['uniq']>0 else (round(r['ob']/r['ls']*100, 1) if r['ls']>0 else 0.0), axis=1)
    grp['FT/OB%'] = grp.apply(lambda r: round(r['ft']/r['ob']*100, 1) if r['ob']>0 else 0.0, axis=1)
    
    grp['OB/LS%'] = grp.apply(lambda r: round(r['ob']/r['ls']*100, 1) if r['ls']>0 else 0.0, axis=1)
    grp['FT/LS%'] = grp.apply(lambda r: round(r['ft']/r['ls']*100, 1) if r['ls']>0 else 0.0, axis=1)

    primary_dim = group_cols[0] if len(group_cols) > 1 else None
    
    if primary_dim:
        grp = grp.sort_values(by=[primary_dim, 'week'], ascending=[True, True])
        grp['LS Δ'] = grp.groupby(primary_dim)['ls'].diff()
        grp['LS Δ%'] = grp.groupby(primary_dim)['ls'].pct_change() * 100
        grp['Uniq Δ'] = grp.groupby(primary_dim)['uniq'].diff()
        grp['Uniq Δ%'] = grp.groupby(primary_dim)['uniq'].pct_change() * 100
        grp['Uniq% Δpp'] = grp.groupby(primary_dim)['Uniq%'].diff()
        grp['OB Δ'] = grp.groupby(primary_dim)['ob'].diff()
        grp['OB Δ%'] = grp.groupby(primary_dim)['ob'].pct_change() * 100
        grp['OB% Δpp'] = grp.groupby(primary_dim)['OB%'].diff()
        grp['FT Δ'] = grp.groupby(primary_dim)['ft'].diff()
        grp['FT Δ%'] = grp.groupby(primary_dim)['ft'].pct_change() * 100
        grp['FT/OB% Δpp'] = grp.groupby(primary_dim)['FT/OB%'].diff()
        
        grp['OB/LS% Δpp'] = grp.groupby(primary_dim)['OB/LS%'].diff()
        grp['FT/LS% Δpp'] = grp.groupby(primary_dim)['FT/LS%'].diff()

        # Weekly Variance Contribution
        tot_ls_d_wk = grp.groupby('week')['LS Δ'].transform('sum')
        tot_uq_d_wk = grp.groupby('week')['Uniq Δ'].transform('sum')
        tot_ob_d_wk = grp.groupby('week')['OB Δ'].transform('sum')
        tot_ft_d_wk = grp.groupby('week')['FT Δ'].transform('sum')
        
        grp['LS Δ Cntrb%'] = np.where(tot_ls_d_wk != 0, (grp['LS Δ'] / tot_ls_d_wk * 100).round(1), 0.0)
        grp['Uniq Δ Cntrb%'] = np.where(tot_uq_d_wk != 0, (grp['Uniq Δ'] / tot_uq_d_wk * 100).round(1), 0.0)
        grp['OB Δ Cntrb%'] = np.where(tot_ob_d_wk != 0, (grp['OB Δ'] / tot_ob_d_wk * 100).round(1), 0.0)
        grp['FT Δ Cntrb%'] = np.where(tot_ft_d_wk != 0, (grp['FT Δ'] / tot_ft_d_wk * 100).round(1), 0.0)

        if dimension_order:
            grp['_rank'] = grp[primary_dim].map({v: i for i, v in enumerate(dimension_order)})
            grp = grp.sort_values(by=['_rank', 'week'], ascending=[True, False]).drop(columns=['_rank'])
        else:
            grp = grp.sort_values(by=[primary_dim, 'week'], ascending=[True, False])
    else:
        grp = grp.sort_values(by=['week'], ascending=[True])
        grp['LS Δ'] = grp['ls'].diff()
        grp['LS Δ%'] = grp['ls'].pct_change() * 100
        grp['Uniq Δ'] = grp['uniq'].diff()
        grp['Uniq Δ%'] = grp['uniq'].pct_change() * 100
        grp['Uniq% Δpp'] = grp['Uniq%'].diff()
        grp['OB Δ'] = grp['ob'].diff()
        grp['OB Δ%'] = grp['ob'].pct_change() * 100
        grp['OB% Δpp'] = grp['OB%'].diff()
        grp['FT Δ'] = grp['ft'].diff()
        grp['FT Δ%'] = grp['ft'].pct_change() * 100
        grp['FT/OB% Δpp'] = grp['FT/OB%'].diff()
        
        grp['OB/LS% Δpp'] = grp['OB/LS%'].diff()
        grp['FT/LS% Δpp'] = grp['FT/LS%'].diff()
        
        grp['LS Δ Cntrb%'] = 100.0
        grp['Uniq Δ Cntrb%'] = 100.0
        grp['OB Δ Cntrb%'] = 100.0
        grp['FT Δ Cntrb%'] = 100.0
        
        grp = grp.sort_values(by=['week'], ascending=[False])

    grp = grp.replace([np.inf, -np.inf], np.nan)
    return grp.where(pd.notnull(grp), None)

def display_trend_html(grp, group_cols, key_prefix):
    if grp is None or grp.empty:
        st.write("No trend data available for selected parameters.")
        return
        
    headers = [col.replace('_', ' ').title() for col in group_cols] + [
        "LS", "LS Δ", "LS Δ%", "LS Δ Cntrb%", "Unique", "Uniq Δ", "Uniq Δ%", "Uniq Δ Cntrb%", "Uniq%", "Uniq% Δpp", 
        "OB", "OB Δ", "OB Δ%", "OB Δ Cntrb%", "OB%", "OB% Δpp", "FT", "FT Δ", "FT Δ%", "FT Δ Cntrb%", "FT/OB%", "FT/OB% Δpp",
        "OB/LS%", "OB/LS% Δpp", "FT/LS%", "FT/LS% Δpp"
    ]
    
    html = f"<table id='trend_{key_prefix}'><thead><tr>"
    for h in headers: html += f"<th>{h}</th>"
    html += "</tr></thead><tbody>"
    
    for _, r in grp.iterrows():
        html += "<tr>"
        for idx, col in enumerate(group_cols):
            css_class = "bold sticky-col" if idx == 0 else "bold"
            html += f"<td class='{css_class}'>{r[col]}</td>"
        html += f"<td>{int(r['ls']) if r['ls'] is not None else 0:,}</td><td>{get_colored_delta(r['LS Δ'])}</td><td>{get_colored_delta(r['LS Δ%'], '%')}</td><td><span class='cntrb'>{r['LS Δ Cntrb%'] if pd.notnull(r['LS Δ Cntrb%']) else 0.0:.1f}%</span></td>"
        html += f"<td>{int(r['uniq']) if r['uniq'] is not None else 0:,}</td><td>{get_colored_delta(r['Uniq Δ'])}</td><td>{get_colored_delta(r['Uniq Δ%'], '%')}</td><td><span class='cntrb'>{r['Uniq Δ Cntrb%'] if pd.notnull(r['Uniq Δ Cntrb%']) else 0.0:.1f}%</span></td>"
        html += f"<td>{get_pill_pct(r['Uniq%'], 'uniq')}</td><td>{get_colored_delta(r['Uniq% Δpp'], 'pp')}</td>"
        html += f"<td>{int(r['ob']) if r['ob'] is not None else 0:,}</td><td>{get_colored_delta(r['OB Δ'])}</td><td>{get_colored_delta(r['OB Δ%'], '%')}</td><td><span class='cntrb'>{r['OB Δ Cntrb%'] if pd.notnull(r['OB Δ Cntrb%']) else 0.0:.1f}%</span></td>"
        html += f"<td>{get_pill_pct(r['OB%'], 'ob')}</td><td>{get_colored_delta(r['OB% Δpp'], 'pp')}</td>"
        html += f"<td class='bold'>{int(r['ft']) if r['ft'] is not None else 0:,}</td><td>{get_colored_delta(r['FT Δ'])}</td><td>{get_colored_delta(r['FT Δ%'], '%')}</td><td><span class='cntrb'>{r['FT Δ Cntrb%'] if pd.notnull(r['FT Δ Cntrb%']) else 0.0:.1f}%</span></td>"
        html += f"<td>{get_pill_pct(r['FT/OB%'], 'ft')}</td><td>{get_colored_delta(r['FT/OB% Δpp'], 'pp')}</td>"
        html += f"<td>{get_pill_pct(r['OB/LS%'], 'ls_ob')}</td><td>{get_colored_delta(r['OB/LS% Δpp'], 'pp')}</td>"
        html += f"<td>{get_pill_pct(r['FT/LS%'], 'ls_ft')}</td><td>{get_colored_delta(r['FT/LS% Δpp'], 'pp')}</td></tr>"
    html += "</tbody></table>"
    
    st.iframe(f"""
    <style>
        body {{ background-color: #ffffff !important; color: #111111 !important; margin: 0; padding: 0; }}
        .table-container {{ width: 100%; height: 100vh; overflow: auto; position: relative; }}
        table {{ width: 100%; border-collapse: collapse; font-family: -apple-system, sans-serif; font-size: 12px; }}
        th {{ position: sticky; top: 0; z-index: 2; text-align: left; background: #f7f6f3 !important; padding: 6px 8px; border-bottom: 1px solid #eceae4; font-size: 11px; color: #666666 !important; white-space: nowrap; box-shadow: 0 1px 0 #eceae4; }}
        td {{ padding: 6px 8px; border-bottom: 0.5px solid rgba(0,0,0,0.08); white-space: nowrap; color: #111111 !important; background-color: #ffffff; }}
        tr:hover td {{ background-color: #f7f6f3 !important; }}
        td:first-child, th:first-child {{ position: sticky; left: 0; z-index: 1; border-right: 1px solid rgba(0,0,0,0.08); }}
        td:first-child {{ background-color: #ffffff; }}
        tr:hover td:first-child {{ background-color: #f7f6f3 !important; }}
        th:first-child {{ z-index: 3; background-color: #f7f6f3 !important; border-right: 1px solid #eceae4; }}
        .bold {{ font-weight: 600; color: #111111 !important; }}
        .fl {{ color: #888888 !important; }}
        .up {{ color: #4a9e2f !important; font-weight: 600; }}
        .dn {{ color: #e05252 !important; font-weight: 600; }}
        .cntrb {{ color: #666666 !important; font-weight: 700; background-color: #f0f0f0; padding: 2px 5px; border-radius: 4px;}}
        .pill {{ display: inline-block; padding: 2px 6px; border-radius: 12px; font-size: 10px; font-weight: 600; }}
        .pg {{ background: rgba(74,158,47,0.15); color: #4a9e2f; }}
        .pa {{ background: rgba(212,137,26,0.15); color: #d4891a; }}
        .pr {{ background: rgba(224,82,82,0.15); color: #e05252; }}
    </style>
    <div class="table-container">{html}</div>
    """, height=max(140, min(550, len(grp)*32 + 50)))

# --- Token-Optimized API Retry Engine for 429 Failover ---
def call_gemini_with_retries(api_key, payload, max_retries=4):
    models_to_try = ["gemini-2.5-flash", "gemini-2.5-flash-lite"]
    headers = {'Content-Type': 'application/json'}
    
    last_error = None
    for model in models_to_try:
        endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        for attempt in range(max_retries):
            try:
                resp = requests.post(endpoint, headers=headers, json=payload, timeout=45)
                if resp.status_code == 200:
                    return {"status": "success", "data": resp.json()}
                elif resp.status_code == 401:
                    return {"status": "error", "message": "Invalid API Key. Verify your Gemini key in Google AI Studio."}
                elif resp.status_code == 404:
                    last_error = f"Model {model} deprecated (404)."
                    break 
                elif resp.status_code in [429, 503]:  
                    last_error = f"Model {model} rate limited (Status {resp.status_code})."
                    if attempt < max_retries - 1:
                        time.sleep((2 ** attempt) * 4)
                        continue
                    break 
                else:
                    return {"status": "error", "message": f"Status {resp.status_code}: {resp.text[:200]}"}
            except requests.exceptions.Timeout:
                last_error = f"Connection to {model} Timed Out."
                if attempt < max_retries - 1:
                    time.sleep((2 ** attempt) * 4)
                    continue
                break
            except requests.exceptions.RequestException as e:
                last_error = f"Network Exception on {model}: {str(e)}"
                if attempt < max_retries - 1:
                    time.sleep((2 ** attempt) * 4)
                    continue
                break
    return {"status": "error", "message": last_error}

def build_html_metric_payload(df_c, df_p):
    compiled = {}
    def get_pct(a, b): return round((a / b * 100), 2) if b > 0 else 0.0
    def get_pp(a, b): return round(a - b, 2)

    fc = {"ls": int(df_c['ls'].sum()), "uniqueness": int(df_c['uniq'].sum()), "ob": int(df_c['ob'].sum()), "ft": int(df_c['ft'].sum())}
    fp = {"ls": int(df_p['ls'].sum()), "uniqueness": int(df_p['uniq'].sum()), "ob": int(df_p['ob'].sum()), "ft": int(df_p['ft'].sum())}
    
    compiled["overall_funnel"] = {
        "ls_curr": fc["ls"], "ls_prev": fp["ls"], "ls_delta": fc["ls"] - fp["ls"],
        "uniq_curr": fc["uniqueness"], "uniq_prev": fp["uniqueness"], "uniq_delta": fc["uniqueness"] - fp["uniqueness"],
        "up_curr": get_pct(fc["uniqueness"], fc["ls"]), "up_prev": get_pct(fp["uniqueness"], fp["ls"]), "up_dp": get_pp(get_pct(fc["uniqueness"], fc["ls"]), get_pct(fp["uniqueness"], fp["ls"])),
        "ob_curr": fc["ob"], "ob_prev": fp["ob"], "ob_delta": fc["ob"] - fp["ob"],
        "op_curr": get_pct(fc["ob"], fc["uniqueness"]), "op_prev": get_pct(fp["ob"], fp["uniqueness"]), "op_dp": get_pp(get_pct(fc["ob"], fc["uniqueness"]), get_pct(fp["ob"], fp["uniqueness"])),
        "ft_curr": fc["ft"], "ft_prev": fp["ft"], "ft_delta": fc["ft"] - fp["ft"],
        "fp_curr": get_pct(fc["ft"], fc["ob"]), "fp_prev": get_pct(fp["ft"], fp["ob"]), "fp_dp": get_pp(get_pct(fc["ft"], fc["ob"]), get_pct(fp["ft"], fp["ob"]))
    }

    def roll_dim(df_w_c, df_w_p, dim_key):
        c_grp = df_w_c.groupby(dim_key)[['ls', 'uniq', 'ob', 'ft']].sum()
        p_grp = df_w_p.groupby(dim_key)[['ls', 'uniq', 'ob', 'ft']].sum()
        m = c_grp.join(p_grp, lsuffix='_c', rsuffix='_p', how='outer').fillna(0)
        res = []
        for d, r in m.iterrows():
            res.append({
                "dim": str(d),
                "curr": {"ls": int(r['ls_c']), "uniqueness": int(r['uniq_c']), "ob": int(r['ob_c']), "ft": int(r['ft_c'])},
                "prev": {"ls": int(r['ls_p']), "uniqueness": int(r['uniq_p']), "ob": int(r['ob_p']), "ft": int(r['ft_p'])}
            })
        return res

    compiled["by_client"] = roll_dim(df_c, df_p, 'client')
    compiled["by_product"] = roll_dim(df_c, df_p, 'lead_referral_type') if 'lead_referral_type' in df_c.columns else roll_dim(df_c, df_p, 'client').copy()
    compiled["by_region"] = roll_dim(df_c, df_p, 'region')
    compiled["by_vl"] = roll_dim(df_c, df_p, 'vl_name')
    compiled["by_cl"] = roll_dim(df_c, df_p, 'cl')
    compiled["by_am"] = roll_dim(df_c, df_p, 'am_name')
    
    compiled["funnel_drill"] = {}
    for cl in df_c['client'].unique():
        sub_c = df_c[df_c['client'] == cl]
        sub_p = df_p[df_p['client'] == cl]
        compiled["funnel_drill"][cl] = {
            "by_product": roll_dim(sub_c, sub_p, 'lead_referral_type') if 'lead_referral_type' in df_c.columns else [],
            "by_region": roll_dim(sub_c, sub_p, 'region'),
            "by_vl": roll_dim(sub_c, sub_p, 'vl_name')
        }

    compiled["region_drill"] = {}
    for rg in df_c['region'].unique():
        sub_rg = df_c[df_c['region'] == rg]
        sub_rg_p = df_p[df_p['region'] == rg]
        compiled["region_drill"][rg] = {
            "by_vl": roll_dim(sub_rg, sub_rg_p, 'vl_name')
        }

    return compiled

payload = build_html_metric_payload(df_curr, df_prev)

# --- 7. Layout Nav Tabs Initialization ---
tab_ui, tab_trends, tab_rca, tab_chat = st.tabs(["📊 Funnel view", "📈 Rolling Trends", "✨ AI Summary", "💬 Ask AI"])

# ==========================================
# RENDER TAB: EXECUTIVE REPLICATED FUNNEL
# ==========================================
with tab_ui:
    df_client_full = transform_to_replicated_dataframe(payload["by_client"])
    df_product_full = transform_to_replicated_dataframe(payload["by_product"])
    df_region_full = transform_to_replicated_dataframe(payload["by_region"])
    df_vl_full = transform_to_replicated_dataframe(payload["by_vl"])
    
    all_drill_vl, all_drill_reg, all_drill_prod = [], [], []
    for c, data in payload["funnel_drill"].items():
        for row in data.get("by_vl", []): all_drill_vl.append({**row, "dim": f"{c} · {row['dim']}"})
        for row in data.get("by_region", []): all_drill_reg.append({**row, "dim": f"{c} · {row['dim']}"})
        for row in data.get("by_product", []): all_drill_prod.append({**row, "dim": f"{c} · {row['dim']}"})

    all_reg_vl = []
    for r, data in payload["region_drill"].items():
        for row in data.get("by_vl", []): all_reg_vl.append({**row, "dim": f"{r} · {row['dim']}"})

    df_client_vl_full = transform_to_replicated_dataframe(all_drill_vl)
    df_client_reg_full = transform_to_replicated_dataframe(all_drill_reg)
    df_client_prod_full = transform_to_replicated_dataframe(all_drill_prod)
    df_reg_vl_full = transform_to_replicated_dataframe(all_reg_vl)

    tab1_dfs = {
        "Client_Cut": df_client_full, "Product_Cut": df_product_full, "Region_Cut": df_region_full, "VL_Cut": df_vl_full,
        "Client_VL_Drilldown": df_client_vl_full, "Client_Region_Drilldown": df_client_reg_full, "Client_Product_Drilldown": df_client_prod_full, "Region_VL_Drilldown": df_reg_vl_full
    }

    col_hdr, col_dl = st.columns([8, 2])
    with col_hdr: st.markdown("### Executive Summary — Macro Funnel Conversion Checkpoints")
    with col_dl:
        st.download_button(
            label="📥 Download All Tab Data (.zip)", data=create_zip_download(tab1_dfs),
            file_name=f"Funnel_View_Data_{curr_end}.zip", mime="application/zip", key="dl_tab_1"
        )
    
    fo = payload["overall_funnel"]
    st.iframe(f"""
    <style>
        body {{ background-color: transparent; margin: 0; padding: 0; font-family: -apple-system, sans-serif; }}
        .row {{ display: flex; gap: 8px; }}
        .card {{ flex: 1; background: #ffffff !important; border: 0.5px solid rgba(0,0,0,0.08); border-radius: 8px; padding: 12px; text-align: center; }}
        .val {{ font-size: 22px; font-weight: 600; color: #111111 !important; }}
        .lbl {{ font-size: 10px; color: #666666 !important; text-transform: uppercase; margin: 3px 0; letter-spacing: 0.05em; }}
        .sub {{ font-size: 11px; color: #888888 !important; }}
        .up {{ color: #4a9e2f; font-weight: 600; }} .dn {{ color: #e05252; font-weight: 600; }}
    </style>
    <div class="row">
        <div class="card"><div class="val">{fo['ls_curr']:,}</div><div class="lbl">Lead Share (LS)</div><div class="sub">Prior: {fo['ls_prev']:,}</div><div><span class="{ 'up' if fo['ls_delta']>=0 else 'dn' }">{fo['ls_delta']:+,}</span></div></div>
        <div class="card"><div class="val">{fo['uniq_curr']:,}</div><div class="lbl">Unique to Client</div><div class="sub">Prior: {fo['uniq_prev']:,}</div><div><span class="{ 'up' if fo['uniq_delta']>=0 else 'dn' }">{fo['uniq_delta']:+,}</span></div></div>
        <div class="card"><div class="val">{fo['ob_curr']:,}</div><div class="lbl">Onboarded (OB)</div><div class="sub">Prior: {fo['ob_prev']:,}</div><div><span class="{ 'up' if fo['ob_delta']>=0 else 'dn' }">{fo['ob_delta']:+,}</span></div></div>
        <div class="card"><div class="val">{fo['ft_curr']:,}</div><div class="lbl">First Trips (FT)</div><div class="sub">Prior: {fo['ft_prev']:,}</div><div><span class="{ 'up' if fo['ft_delta']>=0 else 'dn' }">{fo['ft_delta']:+,}</span></div></div>
    </div>
    """, height=115)

    st.markdown("#### Client Cut")
    display_replicated_table(df_client_full, "s1")

    st.markdown("#### Region Cut")
    display_replicated_table(df_region_full, "s4")

    st.markdown("#### VL Cut — Configurable Volume Scan")
    col1, col2, col3 = st.columns([2, 1, 1])
    top_n_vl = col1.slider("Select Display Window Scale (S5 Cut)", min_value=5, max_value=100, value=20, key="s5_slider")
    sort_vl = col2.selectbox("Sort Priority By:", list(sort_metrics_map.keys()), index=0, key="s5_sort")
    order_vl = col3.selectbox("Trend View:", ["Top Performers (Growing)", "Bottom Performers (Degrowing)"], key="s5_order")
    if not df_vl_full.empty: 
        df_vl_view = df_vl_full.sort_values(by=sort_metrics_map[sort_vl], ascending=(order_vl == "Bottom Performers (Degrowing)"))
        display_replicated_table(df_vl_view.head(top_n_vl), "s5")
    else: display_replicated_table(df_vl_full, "s5")

    st.markdown("#### Client × VL Matrix Drilldown")
    active_drill_list = sorted(list(df_raw['client'].dropna().unique()))
    selected_client_drill = st.multiselect("Isolate Specific Corporate Partner Focus (Client × VL)", options=["All"] + active_drill_list, default=["All"], key="s9_drill_select")
    col1, col2, col3 = st.columns([2, 1, 1])
    top_n_drill_s9 = col1.slider("Select Display Window Scale (S9 Drilldown)", min_value=5, max_value=100, value=20, key="s9_slider")
    sort_s9 = col2.selectbox("Sort Priority By:", list(sort_metrics_map.keys()), index=0, key="s9_sort")
    order_s9 = col3.selectbox("Trend View:", ["Top Performers (Growing)", "Bottom Performers (Degrowing)"], key="s9_order")
    
    df_s9_view = df_client_vl_full.copy()
    if selected_client_drill and "All" not in selected_client_drill: df_s9_view = df_s9_view[df_s9_view['Dimension'].str.split(' · ').str[0].isin(selected_client_drill)]
    if not df_s9_view.empty: df_s9_view = df_s9_view.sort_values(by=sort_metrics_map[sort_s9], ascending=(order_s9 == "Bottom Performers (Degrowing)"))
    display_replicated_table(df_s9_view.head(top_n_drill_s9), "s9")

    st.markdown("#### Client × Region Drilldown")
    selected_client_region = st.multiselect("Isolate Specific Corporate Partner Focus (Client × Region)", options=["All"] + active_drill_list, default=["All"], key="s8_drill_select")
    col1, col2, col3 = st.columns([2, 1, 1])
    top_n_drill_s8 = col1.slider("Select Display Window Scale (Client × Region)", min_value=5, max_value=100, value=20, key="s8_slider")
    sort_s8 = col2.selectbox("Sort Priority By:", list(sort_metrics_map.keys()), index=0, key="s8_sort")
    order_s8 = col3.selectbox("Trend View:", ["Top Performers (Growing)", "Bottom Performers (Degrowing)"], key="s8_order")
    
    df_s8_view = df_client_reg_full.copy()
    if selected_client_region and "All" not in selected_client_region: df_s8_view = df_s8_view[df_s8_view['Dimension'].str.split(' · ').str[0].isin(selected_client_region)]
    if not df_s8_view.empty: df_s8_view = df_s8_view.sort_values(by=sort_metrics_map[sort_s8], ascending=(order_s8 == "Bottom Performers (Degrowing)"))
    display_replicated_table(df_s8_view.head(top_n_drill_s8), "s8")

    st.markdown("#### Region × VL Drilldown")
    active_region_list = sorted(list(df_curr['region'].dropna().unique()))
    selected_region_vl = st.multiselect("Isolate Specific Region Focus (Region × VL)", options=["All"] + active_region_list, default=["All"], key="s11_drill_select")
    col1, col2, col3 = st.columns([2, 1, 1])
    top_n_drill_s11 = col1.slider("Select Display Window Scale (Region × VL)", min_value=5, max_value=100, value=20, key="s11_slider")
    sort_s11 = col2.selectbox("Sort Priority By:", list(sort_metrics_map.keys()), index=0, key="s11_sort")
    order_s11 = col3.selectbox("Trend View:", ["Top Performers (Growing)", "Bottom Performers (Degrowing)"], key="s11_order")
    
    df_s11_view = df_reg_vl_full.copy()
    if selected_region_vl and "All" not in selected_region_vl: df_s11_view = df_s11_view[df_s11_view['Dimension'].str.split(' · ').str[0].isin(selected_region_vl)]
    if not df_s11_view.empty: df_s11_view = df_s11_view.sort_values(by=sort_metrics_map[sort_s11], ascending=(order_s11 == "Bottom Performers (Degrowing)"))
    display_replicated_table(df_s11_view.head(top_n_drill_s11), "s11")

    st.markdown("#### Product Type Cut")
    st.markdown("*(Note: Moved to bottom of rendering queue)*")
    display_replicated_table(df_product_full, "s2")

# ==========================================
# RENDER TAB: ROLLING TRENDS
# ==========================================
with tab_trends:
    rolling_n = st.slider("Select Configurable N Weeks for Download & View", min_value=2, max_value=12, value=5, help="Number of historical weeks to pull.")
    trend_target_weeks = [w for w in allWeeks if w <= anchor_week][:rolling_n]
    df_trend_raw = apply_dimensional_filters(df_raw[df_raw['week'].isin(trend_target_weeks)])
    
    # Pre-Compile Trend Dataframes for Download Engine
    df_overall_trend = get_trend_dataframe(df_trend_raw, ['week'])
    df_client_trend = get_trend_dataframe(df_trend_raw, ['client', 'week'])
    df_vl_trend_full = get_trend_dataframe(df_trend_raw, ['vl_name', 'week'])
    
    df_trend_raw_cvl = df_trend_raw.copy()
    df_trend_raw_cvl['Client · VL'] = df_trend_raw_cvl['client'] + ' · ' + df_trend_raw_cvl['vl_name']
    df_cvl_trend_full = get_trend_dataframe(df_trend_raw_cvl, ['Client · VL', 'week'])
    
    tab2_dfs = {
        "Overall_Trends": df_overall_trend, 
        "Client_Trends": df_client_trend, 
        "VL_Trends": df_vl_trend_full,
        "Client_VL_Trends": df_cvl_trend_full
    }

    col_hdr2, col_dl2 = st.columns([8, 2])
    with col_hdr2: st.markdown("## 📈 Rolling Week-on-Week Performance")
    with col_dl2:
        st.download_button(
            label="📥 Download All Tab Data (.zip)", data=create_zip_download(tab2_dfs),
            file_name=f"Rolling_Trends_Data_{curr_end}.zip", mime="application/zip", key="dl_tab_2"
        )
    st.caption("Review historical funnel metrics leading up to the selected Master Week Slicer anchor.")
    
    st.markdown("#### 1. Overall Pipeline Trend")
    display_trend_html(df_overall_trend, ['week'], "overall_trend")
    
    st.markdown("#### 2. Client × Week Breakdown")
    display_trend_html(df_client_trend, ['client', 'week'], "client_trend")
    
    st.markdown("#### 3. VL × Week Breakdown (Filtered by Client)")
    active_trend_clients = sorted(list(df_trend_raw['client'].dropna().unique()))
    trend_client_filter = st.multiselect("Isolate Specific Corporate Partner Focus (Client)", options=["All"] + active_trend_clients, default=["All"], key="trend_vl_client_filter")
    
    col1, col2, col3 = st.columns([2, 1, 1])
    top_n_trend_vl = col1.slider("Select Display Window Scale (VL Trend)", min_value=5, max_value=100, value=20, key="trend_vl_slider")
    sort_trend_vl = col2.selectbox("Sort Priority By:", list(sort_metrics_map.keys()), index=0, key="trend_vl_sort")
    order_trend_vl = col3.selectbox("Trend View:", ["Top Performers (Growing)", "Bottom Performers (Degrowing)"], key="trend_vl_order")

    df_vl_trend_view = df_trend_raw.copy()
    
    # --- DYNAMIC ROLLING RANKING SYSTEM ENGINE ---
    week_newest = trend_target_weeks[0]
    week_oldest = trend_target_weeks[-1]
    
    df_rank_newest = df_trend_raw[df_trend_raw['week'] == week_newest]
    df_rank_oldest = df_trend_raw[df_trend_raw['week'] == week_oldest]

    if "All" not in trend_client_filter and trend_client_filter:
        df_vl_trend_view = df_vl_trend_view[df_vl_trend_view['client'].isin(trend_client_filter)]
        df_rank_newest = df_rank_newest[df_rank_newest['client'].isin(trend_client_filter)]
        df_rank_oldest = df_rank_oldest[df_rank_oldest['client'].isin(trend_client_filter)]

    vl_trend_payload = build_html_metric_payload(df_rank_newest, df_rank_oldest)["by_vl"]
    df_vl_ranking = transform_to_replicated_dataframe(vl_trend_payload)
    
    top_vls_list = None
    if not df_vl_ranking.empty:
        df_vl_ranking = df_vl_ranking.sort_values(by=sort_metrics_map[sort_trend_vl], ascending=(order_trend_vl == "Bottom Performers (Degrowing)"))
        top_vls_list = df_vl_ranking.head(top_n_trend_vl)["Dimension"].tolist()
        df_vl_trend_view = df_vl_trend_view[df_vl_trend_view['vl_name'].isin(top_vls_list)]
        
    df_final_vl_render = get_trend_dataframe(df_vl_trend_view, ['vl_name', 'week'], dimension_order=top_vls_list)
    display_trend_html(df_final_vl_render, ['vl_name', 'week'], "vl_trend")

    st.markdown("#### 4. Client × VL Matrix Drilldown × Week")
    active_trend_clients_cvl = sorted(list(df_trend_raw['client'].dropna().unique()))
    trend_cvl_client_filter = st.multiselect("Isolate Specific Corporate Partner Focus (Client × VL)", options=["All"] + active_trend_clients_cvl, default=["All"], key="trend_cvl_client_filter")
    
    col1, col2, col3 = st.columns([2, 1, 1])
    top_n_trend_cvl = col1.slider("Select Display Window Scale (Client × VL Trend)", min_value=5, max_value=100, value=20, key="trend_cvl_slider")
    sort_trend_cvl = col2.selectbox("Sort Priority By:", list(sort_metrics_map.keys()), index=0, key="trend_cvl_sort")
    order_trend_cvl = col3.selectbox("Trend View:", ["Top Performers (Growing)", "Bottom Performers (Degrowing)"], key="trend_cvl_order")

    df_cvl_trend_view = df_trend_raw_cvl.copy()
    
    df_rank_newest_cvl = df_trend_raw[df_trend_raw['week'] == week_newest]
    df_rank_oldest_cvl = df_trend_raw[df_trend_raw['week'] == week_oldest]

    if "All" not in trend_cvl_client_filter and trend_cvl_client_filter:
        df_cvl_trend_view = df_cvl_trend_view[df_cvl_trend_view['client'].isin(trend_cvl_client_filter)]
        df_rank_newest_cvl = df_rank_newest_cvl[df_rank_newest_cvl['client'].isin(trend_cvl_client_filter)]
        df_rank_oldest_cvl = df_rank_oldest_cvl[df_rank_oldest_cvl['client'].isin(trend_cvl_client_filter)]

    cvl_trend_payload = build_html_metric_payload(df_rank_newest_cvl, df_rank_oldest_cvl)
    
    drilled_rows_cvl = []
    for c, data in cvl_trend_payload["funnel_drill"].items():
        for row in data.get("by_vl", []): 
            drilled_rows_cvl.append({**row, "dim": f"{c} · {row['dim']}"})
            
    df_cvl_ranking = transform_to_replicated_dataframe(drilled_rows_cvl)
    
    top_cvl_list = None
    if not df_cvl_ranking.empty:
        df_cvl_ranking = df_cvl_ranking.sort_values(by=sort_metrics_map[sort_trend_cvl], ascending=(order_trend_cvl == "Bottom Performers (Degrowing)"))
        top_cvl_list = df_cvl_ranking.head(top_n_trend_cvl)["Dimension"].tolist()
        df_cvl_trend_view = df_cvl_trend_view[df_cvl_trend_view['Client · VL'].isin(top_cvl_list)]
        
    df_final_cvl_render = get_trend_dataframe(df_cvl_trend_view, ['Client · VL', 'week'], dimension_order=top_cvl_list)
    display_trend_html(df_final_cvl_render, ['Client · VL', 'week'], "cvl_trend")


# ==========================================
# RENDER SCOPE: CONTEXTUAL RCA GENERATOR
# ==========================================
with tab_rca:
    st.markdown("## ⚙️ Funnel Conversion Insights Briefing")
    st.caption("Reviewing conversion paths across Lead Share (LS), Uniqueness, Onboarding (OB), and First Trips (FT).")
    
    filter_col1, filter_col2 = st.columns(2)
    with filter_col1: rca_client_filter = st.multiselect("Isolate Executive Client Segments", options=["All"] + allClients, default=["All"], key="rca_c")
    with filter_col2: rca_region_filter = st.multiselect("Isolate Geo-Spatial Territory Boundaries", options=["All"] + allRegions, default=["All"], key="rca_r")
        
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
    
    client_funnels_compiled = []
    for c_obj in payload_rca["by_client"]:
        c_name = c_obj["dim"]
        vc, vp = c_obj["curr"], c_obj["prev"]
        ft_delta = vc["ft"] - vp["ft"]
        up_curr = (vc["uniqueness"] / vc["ls"] * 100) if vc["ls"] > 0 else 0.0
        up_prev = (vp["uniqueness"] / vp["ls"] * 100) if vp["ls"] > 0 else 0.0
        op_curr = (vc["ob"] / vc["uniqueness"] * 100) if vc["uniqueness"] > 0 else 0.0
        op_prev = (vp["ob"] / vp["uniqueness"] * 100) if vp["uniqueness"] > 0 else 0.0
        fp_curr = (vc["ft"] / vc["ob"] * 100) if vc["ob"] > 0 else 0.0
        fp_prev = (vp["ft"] / vp["ob"] * 100) if vp["ob"] > 0 else 0.0
        client_funnels_compiled.append({
            "name": c_name, "ft_abs": ft_delta, "ls_curr": vc["ls"], "ls_delta": vc["ls"] - vp["ls"], "ls_prev": vp["ls"],
            "up_curr": up_curr, "up_prev": up_prev, "up_dp": round(up_curr - up_prev, 2), "op_curr": op_curr, "op_prev": op_prev, "op_dp": round(op_curr - op_prev, 2), 
            "fp_curr": fp_curr, "fp_prev": fp_prev, "fp_dp": round(fp_curr - fp_prev, 2)
        })

    laggard_clients = [a for a in client_funnels_compiled if a["ft_abs"] < 0]
    laggard_clients.sort(key=lambda x: x["ft_abs"])

    vl_rca_c = df_rca_curr.groupby('vl_name')['ft'].sum()
    vl_rca_p = df_rca_prev.groupby('vl_name')['ft'].sum()
    vl_rca_m = pd.DataFrame({'curr': vl_rca_c, 'prev': vl_rca_p}).fillna(0)
    vl_rca_m['delta'] = vl_rca_m['curr'] - vl_rca_m['prev']
    
    top_growing_vls = vl_rca_m.sort_values(by='delta', ascending=False).head(5)
    top_degrowing_vls = vl_rca_m.sort_values(by='delta', ascending=True).head(5)

    def generate_ceo_download_report():
        ls_drop_pct = abs(round((fo_rca["ls_delta"] / fo_rca["ls_prev"] * 100), 1)) if fo_rca["ls_prev"] > 0 else 0
        client_ls_drops = []
        for c in client_funnels_compiled:
            if c["ls_delta"] < 0: client_ls_drops.append((c["name"], abs(c["ls_delta"])))
        client_ls_drops.sort(key=lambda x: x[1], reverse=True)
        top_offenders = [f"{name} - {val/100000:.1f}L" for name, val in client_ls_drops[:3]]
        report_lines = [
            f"=== VAHAN EXECUTIVE FUNNEL PERFORMANCE MATRIX ===", f"Reporting Range: {curr_start} to {curr_end} vs Baseline: {prev_start} to {prev_end}", f"",
            f"1. OVERALL FUNNEL SUMMARY", f"• {fo_rca['ls_curr']/100000:.1f}L leads uploaded (Lead Share) this period down from {fo_rca['ls_prev']/100000:.1f}L; {ls_drop_pct}% ▼",
            f"• Largest drop comes from ({', '.join(top_offenders)})", f"• Uniqueness has dropped by {abs(fo_rca['up_dp'])}pp from {fo_rca['up_prev']:.1f}% down to {fo_rca['up_curr']:.1f}% (meaning fewer fresh leads new to client databases)."
        ]
        return "\n".join(report_lines)

    st.markdown("### A. Overall Funnel Summary")
    
    ai_rendered_successfully = False
    if gemini_api_key:
        with st.spinner("🧠 Querying Gemini AI block engine to compile corporate conversion summary narrative..."):
            gemini_api_key_clean = gemini_api_key.strip()
            minified_text_block = (
                f"Funnel Overall: LS_Cur={fo_rca['ls_curr']}, LS_Pr={fo_rca['ls_prev']}, Uniq_Cur={fo_rca['uniq_curr']}, Uniq_Pr={fo_rca['uniq_prev']}, "
                f"OB_Cur={fo_rca['ob_curr']}, OB_Pr={fo_rca['ob_prev']}, FT_Cur={fo_rca['ft_curr']}, FT_Pr={fo_rca['ft_prev']}. "
                f"Grown VLs: {', '.join([f'{k}(+{int(v)})' for k, v in top_growing_vls['delta'].items() if v > 0])}. "
                f"Dropped VLs: {', '.join([f'{k}({int(v)})' for k, v in top_degrowing_vls['delta'].items() if v < 0])}."
            )
            
            prompt_payload = {
                "contents": [{
                    "parts": [{
                        "text": f"Write an executive metric narrative summary for the CEO using this data stream: {minified_text_block}. "
                                f"Terminology criteria: LS is Lead Share pool. Uniqueness means entry database entry. OB means Onboarding. FT is First Trip. "
                                f"Explain performance shifts directly and completely drop any greetings, introductions, corporate salutations, dates, or memo headers (To, From, Subject). Jump straight into outputting only raw analytics paragraphs."
                    }]
                }]
            }
            llm_response = call_gemini_with_retries(gemini_api_key_clean, prompt_payload)
            if llm_response["status"] == "success":
                st.markdown(llm_response["data"]["candidates"][0]["content"]["parts"][0]["text"])
                ai_rendered_successfully = True

    if not ai_rendered_successfully:
        if fo_rca["ft_delta"] < 0:
            st.markdown(f"#### Pipeline Summary (Deterministic Standby Layer Active)")
            st.markdown(f"Our core operation logged a net conversion deficit of **{fo_rca['ft_delta']:,} First Trips (FT)** compared directly to the historical matching baseline period parameters.")
            rca_bullets = []
            if fo_rca["fp_dp"] < 0: rca_bullets.append(f"<li><strong>First Trip Drop Layer (OB ➔ FT):</strong> Target final activation slipped by <span class='dn'>{abs(fo_rca['fp_dp'])}pp</span>.</li>")
            if fo_rca["op_dp"] < 0: rca_bullets.append(f"<li><strong>Onboarding Drop Layer (Unique ➔ OB):</strong> Operational activation velocity slipped by <span class='dn'>{abs(fo_rca['op_dp'])}pp</span>.</li>")
            if fo_rca["up_dp"] < 0: rca_bullets.append(f"<li><strong>Lead Penetration Loss Layer (LS ➔ Unique):</strong> Fresh leads entry volume dipped by <span class='dn'>{abs(fo_rca['up_dp'])}pp</span>.</li>")
            if fo_rca["ls_delta"] < 0: rca_bullets.append(f"<li><strong>Volume Contraction Layer (Lead Share Ingress):</strong> Raw source referral ingress declined by <span class='dn'>{abs(fo_rca['ls_delta']):,} source files</span>.</li>")
            st.markdown(f"<ul>{''.join(rca_bullets)}</ul>", unsafe_allow_html=True)
        else:
            st.markdown(f"### :green[Conversion Pipeline Stable:] Funnel expansion parameters tracking at **+{fo_rca['ft_delta']:,} Completed First Trips** vs prior matching periods.")

    st.download_button(label="📥 Download Executive Briefing (.txt)", data=generate_ceo_download_report(), file_name=f"Vahan_CEO_Funnel_Review_{curr_end}.txt", mime="text/plain")

    st.markdown("---")
    st.markdown("### Vahan Leader (VL Grain) Performance Standouts")
    growth_col1, growth_col2 = st.columns(2)
    with growth_col1:
        st.markdown("#### Top 5 Growing VLs (Absolute Increase)")
        for vl_name, row in top_growing_vls.iterrows():
            if row['delta'] > 0: st.markdown(f"- 🟢 **{vl_name}**: Added :green[+{int(row['delta'])}] First Trips ({LBL_CURR}: {int(row['curr'])} vs {LBL_PREV}: {int(row['prev'])})")
    with growth_col2:
        st.markdown("#### Top 5 Degrowing VLs (Absolute Decrease)")
        for vl_name, row in top_degrowing_vls.iterrows():
            if row['delta'] < 0: st.markdown(f"- 🔴 **{vl_name}**: Dropped :red[{int(row['delta'])}] First Trips ({LBL_CURR}: {int(row['curr'])} vs {LBL_PREV}: {int(row['prev'])})")

    st.markdown("---")
    st.markdown("### B. Drill-down Summary")
    if not laggard_clients:
        st.info("No corporate enterprises logged conversion variances matching active scope filters.")
    else:
        for client in laggard_clients:
            st.markdown(f"""
            <div style='background: #ffffff !important; border: 0.5px solid rgba(0,0,0,0.08); border-left: 4px solid #e05252; border-radius: 8px; padding: 12px; margin-bottom: 12px;'>
                <div style='display:flex; justify-content: space-between; align-items: center;'>
                    <span style='font-size:13px; font-weight:600; color: #111111 !important;'>{client['name'].upper()}</span>
                    <span style='color: #e05252 !important; font-weight: 600;'>{client['ft_abs']:,} First Trips (FT) Variance Loss</span>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            client_bullets = []
            if client["fp_dp"] < 0: client_bullets.append(f"<li><strong>First Trip Drop Layer (OB ➔ FT):</strong> Conversion dropped by <span class='dn'>{abs(client['fp_dp'])}pp</span> (from {client['fp_prev']:.1f}% to {client['fp_curr']:.1f}%).</li>")
            if client["op_dp"] < 0: client_bullets.append(f"<li><strong>Onboarding Drop Layer (Unique ➔ OB):</strong> Conversion dropped by <span class='dn'>{abs(client['op_dp'])}pp</span> (from {client['op_prev']:.1f}% to {client['op_curr']:.1f}%).</li>")
            if client["up_dp"] < 0: client_bullets.append(f"<li><strong>Lead Penetration Loss Layer (LS ➔ Unique):</strong> Uniqueness penetration dropped by <span class='dn'>{abs(client['up_dp'])}pp</span> (from {client['up_prev']:.1f}% to {client['up_curr']:.1f}%).</li>")
            if client["ls_delta"] < 0: client_bullets.append(f"<li><strong>Volume Contraction Layer (Lead Share Ingress):</strong> Total raw leads shared decreased by <span class='dn'>{abs(client['ls_delta']):,} leads</span>.</li>")
            if client_bullets: st.markdown(f"<ul>{''.join(client_bullets)}</ul>", unsafe_allow_html=True)
            
            df_vl_c = df_curr[df_curr['client'] == client['name']].groupby('vl_name')[['ls', 'uniq', 'ob', 'ft']].sum()
            df_vl_p = df_prev[df_prev['client'] == client['name']].groupby('vl_name')[['ls', 'uniq', 'ob', 'ft']].sum()
            df_matrix = df_vl_c.join(df_vl_p, lsuffix='_c', rsuffix='_p', how='outer').fillna(0)
            
            df_matrix['ft_diff'] = df_matrix['ft_c'] - df_matrix['ft_p']
            df_matrix['ob_diff'] = df_matrix['ob_c'] - df_matrix['ob_p']
            df_matrix['uniq_diff'] = df_matrix['uniq_c'] - df_matrix['uniq_p']
            df_matrix['ls_diff'] = df_matrix['ls_c'] - df_matrix['ls_p']
            
            col_d1, col_d2, col_d3, col_d4 = st.columns(4)
            with col_d1:
                st.caption("📉 Top-3 Laggard VLs: **FT Deficit**")
                for v, r in df_matrix[df_matrix['ft_diff'] < 0].sort_values(by='ft_diff').head(3).iterrows(): st.markdown(f"- **{v}**: `{int(r['ft_diff'])}` FT")
            with col_d2:
                st.caption("📉 Top-3 Laggard VLs: **OB Deficit**")
                for v, r in df_matrix[df_matrix['ob_diff'] < 0].sort_values(by='ob_diff').head(3).iterrows(): st.markdown(f"- **{v}**: `{int(r['ob_diff'])}` OB")
            with col_d3:
                st.caption("📉 Top-3 Laggard VLs: **Uniqueness Deficit**")
                for v, r in df_matrix[df_matrix['uniq_diff'] < 0].sort_values(by='uniq_diff').head(3).iterrows(): st.markdown(f"- **{v}**: `{int(r['uniq_diff'])}` Uniq")
            with col_d4:
                st.caption("📉 Top-3 Laggard VLs: **LS Volume Deficit**")
                for v, r in df_matrix[df_matrix['ls_diff'] < 0].sort_values(by='ls_diff').head(3).iterrows(): st.markdown(f"- **{v}**: `{int(r['ls_diff'])}` LS")
            st.markdown("<br>", unsafe_allow_html=True)

# ==========================================
# RENDER SCOPE: AI CHATBOT INTERFACE (SMART CONTEXT PRUNING)
# ==========================================
with tab_chat:
    st.markdown("## 💬 Executive AI Assistant")
    st.caption("Ask questions about funnel drops, top performing VLs, or client-specific drill-down attribution metrics.")

    if "chat_history" not in st.session_state: st.session_state.chat_history = []

    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]): st.markdown(msg["content"])

    if prompt := st.chat_input("Ask a question about the funnel performance..."):
        if not gemini_api_key:
            st.warning("Please configure your st.secrets file to activate the AI Chatbot.")
        else:
            st.session_state.chat_history.append({"role": "user", "content": prompt})
            with st.chat_message("user"): st.markdown(prompt)

            with st.chat_message("assistant"):
                message_placeholder = st.empty()
                with st.spinner("Isolating timeline anomalies and running compression layer..."):
                    chat_target_weeks = [w for w in allWeeks if w <= anchor_week][:5]
                    df_chat_raw = apply_dimensional_filters(df_raw[df_raw['week'].isin(chat_target_weeks)])
                    df_chat_weeks = df_chat_raw.groupby(['client', 'vl_name', 'week'])[['ls', 'uniq', 'ob', 'ft']].sum().reset_index()
                    
                    df_w_first = df_chat_raw[df_chat_raw['week'] == chat_target_weeks[-1]].groupby(['client', 'vl_name'])['ft'].sum()
                    df_w_last = df_chat_raw[df_chat_raw['week'] == chat_target_weeks[0]].groupby(['client', 'vl_name'])['ft'].sum()
                    vl_deltas = (df_w_last - df_w_first).reset_index(name='delta')
                    
                    significant_vls = pd.concat([
                        vl_deltas.sort_values(by='delta', ascending=False).head(20),
                        vl_deltas.sort_values(by='delta', ascending=True).head(20)
                    ]).drop_duplicates(subset=['client', 'vl_name'])
                    
                    df_chat_weeks_pruned = df_chat_weeks[df_chat_weeks.set_index(['client', 'vl_name']).index.isin(significant_vls.set_index(['client', 'vl_name']).index)]
                    csv_context = df_chat_weeks_pruned.to_csv(index=False)
                    
                    system_guideline = (
                        "You are an expert Executive Operations Data Analyst reporting directly to the CEO.\n"
                        "CRITICAL STRUCTURAL RULES FOR THE BUSINESS TAXONOMY:\n"
                        "1. CLIENTS are purchasing enterprises (e.g., Swiggy, Blinkit, Zomato). Never call them vendors.\n"
                        "2. VAHAN LEADERS (VLs) are third-party manpower sourcing vendors who recruit and supply workers TO clients.\n"
                        "3. NEVER confuse a Client with a VL.\n\n"
                        "ROOT CAUSE ANALYSIS (RCA) EXECUTION MATRIX:\n"
                        "You have been provided with a prioritized anomaly CSV representing rows with the largest variance across the last 5 rolling weeks of data. "
                        "When analyzing fluctuations, execute a BACKWARD funnel evaluation: First Trips (FT) ➔ Onboarding (OB) ➔ Uniqueness (uniq) ➔ Lead Share (ls). "
                        "Identify the exact week and exact VL driving the client's drop."
                    )
                    
                    gemini_history = [{"role": "user", "parts": [{"text": system_guideline}]}]
                    for m in st.session_state.chat_history[:-1]:
                        gemini_role = "user" if m["role"] == "user" else "model"
                        gemini_history.append({"role": gemini_role, "parts": [{"text": m["content"]}]})
                    
                    current_prompt_with_context = f"MACRO SUMMARY Aggregates:\n{json.dumps(fo_rca)}\n\nPRUNED ANOMALY HISTORICAL DATA TREE (CSV):\n{csv_context}\n\nUser Operational Question: {prompt}"
                    gemini_history.append({"role": "user", "parts": [{"text": current_prompt_with_context}]})
                    
                    gemini_api_key_clean = gemini_api_key.strip()
                    payload_chat = {"contents": gemini_history}
                    
                    llm_chat_resp = call_gemini_with_retries(gemini_api_key_clean, payload_chat)
                    if llm_chat_resp["status"] == "success":
                        ai_response = llm_chat_resp["data"]["candidates"][0]["content"]["parts"][0]["text"]
                        message_placeholder.markdown(ai_response)
                        st.session_state.chat_history.append({"role": "assistant", "content": ai_response})
                    else: message_placeholder.error(f"Chatbot Layer Connection Alert: {llm_chat_resp['message']}")
