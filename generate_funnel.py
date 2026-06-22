import streamlit as st
import pandas as pd
import requests
from datetime import date, timedelta

# --- Page Setup ---
st.set_page_config(page_title="Vahan Funnel Analytics & AI RCA", layout="wide")

# --- 1. Live Data Fetching from Redash ---
@st.cache_data(ttl=3600)  # Cache data for 1 hour to prevent redundant API spam
def fetch_redash_data():
    api_url = "https://redash.vahan.link/api/queries/17631/results.json"
    api_key = "4aFm2iOoyx8I91svQccdeZr0jmaiUsMFSRinZcmu"
    
    try:
        response = requests.get(api_url, params={"api_key": api_key}, timeout=30)
        response.raise_for_status()
        json_data = response.json()
        
        # Extract rows from Redash standard JSON payload schema
        rows = json_data["query_result"]["data"]["rows"]
        df_raw = pd.DataFrame(rows)
        
        # Ensure date mapping formats are correct
        df_raw['day'] = pd.to_datetime(df_raw['day']).dt.date
        df_raw['week'] = pd.to_datetime(df_raw['week']).dt.date
        
        # Typecasting metrics explicitly
        for col in ['ls', 'uniq', 'ob', 'ft']:
            if col in df_raw.columns:
                df_raw[col] = pd.to_numeric(df_raw[col], errors='coerce').fillna(0).astype(int)
        return df_raw
    except Exception as e:
        st.error(f"Failed to fetch data from Redash API: {e}")
        return pd.DataFrame()

df = fetch_redash_data()

if df.empty:
    st.stop()

# --- 2. Sidebar Timeframe Slicing Engine ---
st.sidebar.header("⏱️ Control Panel")

view_mode = st.sidebar.radio("Time Aggregation", ["MTD (Month-to-Date)", "WTD (Week-to-Date)"])
exclude_incomplete = st.sidebar.checkbox("Exclude current incomplete week's data", value=False)

# Track today's running date safely contextually
today_dt = date.today()

# Handle incomplete data stripping if selected
if exclude_incomplete:
    # Look back to the closest completed Sunday
    days_to_subtract = today_dt.weekday() + 1
    reference_date = today_dt - timedelta(days=days_to_subtract)
else:
    reference_date = today_dt

# Target structural date buckets initialization
curr_start = curr_end = prev_start = prev_end = None

if view_mode == "MTD (Month-to-Date)":
    # Current MTD: From 1st of current month up to running reference date
    curr_start = reference_date.replace(day=1)
    curr_end = reference_date
    
    # Prior Period MTD (Apples-to-Apples): Same calendar span offset by exactly 1 month
    prev_month = 12 if curr_start.month == 1 else curr_start.month - 1
    prev_year = curr_start.year - 1 if curr_start.month == 1 else curr_start.year
    prev_start = date(prev_year, prev_month, 1)
    
    try:
        prev_end = date(prev_year, prev_month, reference_date.day)
    except ValueError:
        # Gracefully handle varying month length overflows (e.g. March 31 -> Feb 28/29)
        prev_end = (date(prev_year, prev_month + 1, 1) - timedelta(days=1))

else:
    # WTD: Monday of running week up to reference date
    curr_start = reference_date - timedelta(days=reference_date.weekday())
    curr_end = reference_date
    
    # Prior Period WTD: Exactly matching days shifted back by 1 week
    prev_start = curr_start - timedelta(days=7)
    prev_end = curr_end - timedelta(days=7)

# Print active date constraints
st.sidebar.markdown("---")
st.sidebar.subheader("📅 Active Comparison Matrix")
st.sidebar.caption(f"**Current Range ({view_mode.split()[0]}):**\n{curr_start} ➔ {curr_end}")
st.sidebar.caption(f"**Previous Range (Apples-to-Apples):**\n{prev_start} ➔ {prev_end}")

# Slice DataFrames using mapped constraints
df_curr = df[(df['day'] >= curr_start) & (df['day'] <= curr_end)]
df_prev = df[(df['day'] >= prev_start) & (df['day'] <= prev_end)]

# Helper aggregator to extract sums across specified data blocks
def rollup_metrics(dataframe):
    if dataframe.empty:
        return {"ls": 0, "uniq": 0, "ob": 0, "ft": 0}
    return {
        "ls": int(dataframe['ls'].sum()),
        "uniq": int(dataframe['uniq'].sum()),
        "ob": int(dataframe['ob'].sum()),
        "ft": int(dataframe['ft'].sum()),
    }

tot_curr = rollup_metrics(df_curr)
tot_prev = rollup_metrics(df_prev)

# --- 3. Dashboard Interface Architecture ---
tabs = st.tabs(["📊 Funnel Dashboard", "🤖 Prioritized AI RCA Summary"])

# TAB 1: Core Funnel Metrics Grid
with tabs[0]:
    st.markdown("### Functional Funnel Progression Summary")
    
    c1, col_un, c2, c3 = st.columns(4)
    c1.metric("Lead Submissions (LS)", f"{tot_curr['ls']:,}", f"{tot_curr['ls'] - tot_prev['ls']:,} MoM")
    col_un.metric("Unique Leads", f"{tot_curr['uniq']:,}", f"{tot_curr['uniq'] - tot_prev['uniq']:,} MoM")
    c2.metric("Onboardings (OB)", f"{tot_curr['ob']:,}", f"{tot_curr['ob'] - tot_prev['ob']:,} MoM")
    c3.metric("First Trips (FT)", f"{tot_curr['ft']:,}", f"{tot_curr['ft'] - tot_prev['ft']:,} MoM")
    
    st.markdown("---")
    st.markdown("### Conversion Rate Efficiency Checkpoints")
    
    # Calculate performance conversions
    u_ls_curr = (tot_curr['uniq'] / tot_curr['ls'] * 100) if tot_curr['ls'] else 0
    u_ls_prev = (tot_prev['uniq'] / tot_prev['ls'] * 100) if tot_prev['ls'] else 0
    
    ob_u_curr = (tot_curr['ob'] / tot_curr['uniq'] * 100) if tot_curr['uniq'] else 0
    ob_u_prev = (tot_prev['ob'] / tot_prev['uniq'] * 100) if tot_prev['uniq'] else 0
    
    ft_ob_curr = (tot_curr['ft'] / tot_curr['ob'] * 100) if tot_curr['ob'] else 0
    ft_ob_prev = (tot_prev['ft'] / tot_prev['ob'] * 100) if tot_prev['ob'] else 0
    
    cc1, cc2, cc3 = st.columns(3)
    cc1.metric("LS ➔ Uniqueness Rate", f"{u_ls_curr:.1f}%", f"{u_ls_curr - u_ls_prev:+.1f} pp")
    cc2.metric("Unique ➔ OB Activation Rate", f"{ob_u_curr:.1f}%", f"{ob_u_curr - ob_u_prev:+.1f} pp")
    cc3.metric("OB ➔ FT Conversion Rate", f"{ft_ob_curr:.1f}%", f"{ft_ob_curr - ft_ob_prev:+.1f} pp")

    st.markdown("---")
    st.markdown("### Client Breakdown")
    client_pivot = df_curr.groupby('client')[['ls', 'uniq', 'ob', 'ft']].sum().sort_values(by='ft', ascending=False)
    st.dataframe(client_pivot, use_container_width=True)

# TAB 2: AI Root Cause Analysis Summary
with tabs[1]:
    st.markdown("### 🔍 Root Cause Analysis (RCA)")
    
    # Calculate macroscopic shift across First Trips
    macro_ft_delta = tot_curr['ft'] - tot_prev['ft']
    
    # ── OVERVIEW A: OVERALL VIEW ──
    st.markdown("#### A. Overall View (Macro Funnel Leakage)")
    
    if macro_ft_delta < 0:
        st.error(f"🔴 **P0 Overall Signal:** First Trips dipped by **{abs(macro_ft_delta):,}** overall compared to the matching prior frame.")
        
        # Trace backward step-by-step up the funnel pipe to tag P0 leak sources
        if (ft_ob_curr - ft_ob_prev) < 0:
            st.markdown(f"👉 **P0 Bottleneck Found (OB ➔ FT Conversion Drop):** The deployment layer collapsed by **{abs(ft_ob_curr - ft_ob_prev):.1f}pp**. Drivers are completing profiles but skipping initialization runs.")
        if (ob_u_curr - ob_u_prev) < 0:
            st.markdown(f"👉 **P0 Bottleneck Found (Unique ➔ OB Activation Drop):** The conversion pipeline rate contracted by **{abs(ob_u_curr - ob_u_prev):.1f}pp**.")
        if (u_ls_curr - u_ls_prev) < 0:
            st.markdown(f"👉 **P0 Bottleneck Found (LS ➔ Unique Drop):** Lead quality or formatting dropped; uniqueness fell by **{abs(u_ls_curr - u_ls_prev):.1f}pp**.")
        if tot_curr['ls'] < tot_prev['ls']:
            st.markdown(f"👉 **P0 Bottleneck Found (Top-of-Funnel Volume Collapse):** Raw lead ingress volume slipped by **{tot_prev['ls'] - tot_curr['ls']:,}** records.")
    else:
        st.success(f"🟢 **Overall Signal:** First Trips improved by **{macro_ft_delta:+,}** across the current timeframe. Pipe performance remains healthy.")

    # ── OVERVIEW B: CLIENT LEVEL VIEW ──
    st.markdown("---")
    st.markdown("#### B. Client-Level Micro Drift & Vendor Attribution")
    
    # Group and compare metrics for clients
    c_curr_grp = df_curr.groupby('client')[['ls', 'uniq', 'ob', 'ft']].sum()
    c_prev_grp = df_prev.groupby('client')[['ls', 'uniq', 'ob', 'ft']].sum()
    
    combined_clients = c_curr_grp.join(c_prev_grp, lsuffix='_curr', rsuffix='_prev', how='outer').fillna(0)
    combined_clients['ft_delta'] = combined_clients['ft_curr'] - combined_clients['ft_prev']
    
    # Filter to trailing vectors and prioritize by absolute severity of drop
    laggard_clients = combined_clients[combined_clients['ft_delta'] < 0].sort_values(by='ft_delta')
    
    if laggard_clients.empty:
        st.info("No individual business account dropped in total output volume over this comparison matrix window.")
    else:
        for client_name, row in laggard_clients.iterrows():
            with st.expander(f"⚠️ Account: **{client_name.upper()}** | Deficit: **{int(row['ft_delta']):,} FT**", expanded=True):
                
                # Sift client conversion rates to pinpoint the bottleneck stage
                c_ft_ob_c = (row['ft_curr'] / row['ob_curr'] * 100) if row['ob_curr'] else 0
                c_ft_ob_p = (row['ft_prev'] / row['ob_prev'] * 100) if row['ob_prev'] else 0
                c_ft_ob_diff = c_ft_ob_c - c_ft_ob_p
                
                c_ob_u_c = (row['ob_curr'] / row['uniq_curr'] * 100) if row['uniq_curr'] else 0
                c_ob_u_p = (row['ob_prev'] / row['uniq_prev'] * 100) if row['uniq_prev'] else 0
                c_ob_u_diff = c_ob_u_c - c_ob_u_p
                
                # Classify the specific bottleneck for this client
                st.markdown("**Primary Funnel Leakage Layer:**")
                if c_ft_ob_diff <= -3:
                    st.warning(f"🚨 **OB ➔ FT Conversion Drop:** Conversion rate down by **{abs(c_ft_ob_diff):.1f}pp** ({c_ft_ob_p:.1f}% ➔ {c_ft_ob_c:.1f}%).")
                if c_ob_u_diff <= -3:
                    st.warning(f"🚨 **Unique ➔ OB Activation Drop:** Onboarding velocity compressed by **{abs(c_ob_u_diff):.1f}pp** ({c_ob_u_p:.1f}% ➔ {c_ob_u_c:.1f}%).")
                if row['ls_curr'] < row['ls_prev']:
                    st.warning(f"🚨 **LS Ingress Collapse:** Raw lead intake dropped by **{int(row['ls_prev'] - row['ls_curr']):,}** tokens.")
                
                # Trace leakage down to specific Vendor Leads (VLs)
                st.markdown("**Top Laggard Vendor Attribution (VL Grain):**")
                vl_curr = df_curr[df_curr['client'] == client_name].groupby('vl_name')['ft'].sum()
                vl_prev = df_prev[df_prev['client'] == client_name].groupby('vl_name')['ft'].sum()
                
                vl_comb = pd.DataFrame({'curr': vl_curr, 'prev': vl_prev}).fillna(0)
                vl_comb['delta'] = vl_comb['curr'] - vl_comb['prev']
                top_offending_vls = vl_comb[vl_comb['delta'] < 0].sort_values(by='delta').head(3)
                
                if not top_offending_vls.empty:
                    for vl_label, vrow in top_offending_vls.iterrows():
                        st.markdown(f"- 📉 Vendor **{vl_label}**: Contributed a drop of **{int(vrow['delta'])} FT** (Jun: {int(vrow['curr'])} vs May: {int(vrow['prev'])})")
                else:
                    st.caption("Drop evenly distributed across vendor network; no distinct statistical outliers found.")
