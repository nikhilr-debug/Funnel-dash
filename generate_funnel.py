import streamlit as st
import pandas as pd
import requests
from datetime import date, timedelta

# --- Page Optimization Configuration ---
st.set_page_config(page_title="Vahan Live Funnel Optimization Architecture", layout="wide")

# --- 1. Live Redash API Ingestion Engine ---
@st.cache_data(ttl=1800)  # Cached for 30 minutes to manage live API rate limits
def pull_vahan_funnel_data():
    endpoint_url = "https://redash.vahan.link/api/queries/17631/results.json"
    query_auth_token = "4aFm2iOoyx8I91svQccdeZr0jmaiUsMFSRinZcmu"
    
    try:
        api_response = requests.get(endpoint_url, params={"api_key": query_auth_token}, timeout=45)
        api_response.raise_for_status()
        payload = api_response.json()
        raw_records = payload["query_result"]["data"]["rows"]
        
        # Build strict typed execution dataframe
        df_processed = pd.DataFrame(raw_records)
        df_processed['day'] = pd.to_datetime(df_processed['day']).dt.date
        df_processed['week'] = pd.to_datetime(df_processed['week']).dt.date
        
        # Enforce analytical column types safely
        for metric_col in ['ls', 'uniq', 'ob', 'ft']:
            if metric_col in df_processed.columns:
                df_processed[metric_col] = pd.to_numeric(df_processed[metric_col], errors='coerce').fillna(0).astype(int)
        return df_processed
    except Exception as api_error:
        st.error(f"Critical Ingestion Pipeline Failure: {api_error}")
        return pd.DataFrame()

df_raw = pull_vahan_funnel_data()

if df_raw.empty:
    st.error("Data pipeline empty. Verify query compilation status or Redash API availability.")
    st.stop()

# --- 2. Advanced Temporal Partitioning Engine ---
st.sidebar.header("⏱️ Temporal Slicing Controls")
timeframe_mode = st.sidebar.radio("Time Aggregation Scope", ["MTD (Month-to-Date)", "WTD (Week-to-Date)"])
exclude_active_week = st.sidebar.checkbox("Exclude trailing incomplete week metrics", value=False)

# Grounding processing clock to execution window matrix
operational_today = date(2026, 6, 22)

if exclude_active_week:
    current_week_offset = operational_today.weekday() + 1
    ground_reference_date = operational_today - timedelta(days=current_week_offset)
else:
    ground_reference_date = operational_today

# Compute exact boundaries for apples-to-apples baseline delta comparison
if timeframe_mode == "MTD (Month-to-Date)":
    current_start = ground_reference_date.replace(day=1)
    current_end = ground_reference_date
    
    # Calculate previous month match matrices
    prev_month = 12 if current_start.month == 1 else current_start.month - 1
    prev_year = current_start.year - 1 if current_start.month == 1 else current_start.year
    previous_start = date(prev_year, prev_month, 1)
    try:
        previous_end = date(prev_year, prev_month, ground_reference_date.day)
    except ValueError:
        # Graceful calendar month-end overflow correction (e.g., March 31 match to Feb 28)
        previous_end = (date(prev_year, prev_month + 1, 1) - timedelta(days=1))
else:
    # WTD Tracking Matrix
    current_start = ground_reference_date - timedelta(days=ground_reference_date.weekday())
    current_end = ground_reference_date
    previous_start = current_start - timedelta(days=7)
    previous_end = current_end - timedelta(days=7)

# Segregate absolute operational data frames
df_current_window = df_raw[(df_raw['day'] >= current_start) & (df_raw['day'] <= current_end)]
df_previous_window = df_raw[(df_raw['day'] >= previous_start) & (df_raw['day'] <= previous_end)]

# --- 3. Strict Scientific Metric Compilers ---
def compute_funnel_aggregates(dataframe):
    if dataframe.empty:
        return {"ls": 0, "uniq": 0, "ob": 0, "ft": 0}
    return {
        "ls": int(dataframe['ls'].sum()),
        "uniq": int(dataframe['uniq'].sum()),
        "ob": int(dataframe['ob'].sum()),
        "ft": int(dataframe['ft'].sum())
    }

totals_current = compute_funnel_aggregates(df_current_window)
totals_previous = compute_funnel_aggregates(df_previous_window)

# Formatting Utility Methods
def format_metric_value(number):
    absolute_val = abs(number)
    if absolute_val >= 1e6:
        return f"{number / 1e6:.2f}M"
    if absolute_val >= 1e3:
        return f"{number / 1e3:.1f}K"
    return str(number)

def generate_delta_string(curr, prev, is_percentage=False, suffix=""):
    diff = curr - prev
    sign = "+" if diff >= 0 else ""
    if is_percentage:
        return f"{sign}{diff:.2f}{suffix}"
    return f"{sign}{format_metric_value(diff)}{suffix}"

# --- 4. Main Interface Architecture ---
tab_funnel, tab_ai_rca = st.tabs(["📊 Replicated Funnel View", "✨ Automated AI RCA Summary"])

# ==========================================
# TAB: CORE FUNNEL DATA cuts REPLICATION
# ==========================================
with tab_funnel:
    st.markdown(f"### Overall Funnel Performance Matrix: `{current_start}` to `{current_end}` vs Baseline: `{previous_start}` to `{previous_end}`")
    
    # 4-Stage Absolute KPIs Block
    kpi_cols = st.columns(4)
    stages = [
        ("Lead Submissions (LS)", totals_current['ls'], totals_previous['ls']),
        ("Uniqueness (Uniq)", totals_current['uniq'], totals_previous['uniq']),
        ("Onboarded (OB)", totals_current['ob'], totals_previous['ob']),
        ("First Trips (FT)", totals_current['ft'], totals_previous['ft'])
    ]
    for idx, (label, curr_val, prev_val) in enumerate(stages):
        pct_variance = ((curr_val - prev_val) / prev_val * 100) if prev_val > 0 else 0.0
        delta_label = f"{generate_delta_string(curr_val, prev_val)} ({pct_variance:+.1f}%)"
        kpi_cols[idx].metric(label, f"{curr_val:,}", delta_label)
        
    st.markdown("---")
    st.markdown("#### Funnel Micro-Conversion Layer Efficiency Checkpoints")
    
    # Conversion rates calculation formulas matching HTML framework logic
    ls_to_uniq_curr = (totals_current['uniq'] / totals_current['ls'] * 100) if totals_current['ls'] else 0.0
    ls_to_uniq_prev = (totals_previous['uniq'] / totals_previous['ls'] * 100) if totals_previous['ls'] else 0.0
    
    uniq_to_ob_curr = (totals_current['ob'] / totals_current['uniq'] * 100) if totals_current['uniq'] else 0.0
    uniq_to_ob_prev = (totals_previous['ob'] / totals_previous['uniq'] * 100) if totals_previous['uniq'] else 0.0
    
    ob_to_ft_curr = (totals_current['ft'] / totals_current['ob'] * 100) if totals_current['ob'] else 0.0
    ob_to_ft_prev = (totals_previous['ft'] / totals_previous['ob'] * 100) if totals_previous['ob'] else 0.0
    
    ls_to_ft_curr = (totals_current['ft'] / totals_current['ls'] * 100) if totals_current['ls'] else 0.0
    ls_to_ft_prev = (totals_previous['ft'] / totals_previous['ls'] * 100) if totals_previous['ls'] else 0.0

    conv_cols = st.columns(4)
    conv_cols[0].metric("LS ➔ Uniqueness Rate", f"{ls_to_uniq_curr:.2f}%", generate_delta_string(ls_to_uniq_curr, ls_to_uniq_prev, True, "pp"))
    conv_cols[1].metric("Unique ➔ OB Rate", f"{uniq_to_ob_curr:.2f}%", generate_delta_string(uniq_to_ob_curr, uniq_to_ob_prev, True, "pp"))
    conv_cols[2].metric("OB ➔ FT Rate", f"{ob_to_ft_curr:.2f}%", generate_delta_string(ob_to_ft_curr, ob_to_ft_prev, True, "pp"))
    conv_cols[3].metric("LS ➔ FT Conversion", f"{ls_to_ft_curr:.2f}%", generate_delta_string(ls_to_ft_curr, ls_to_ft_prev, True, "pp"))

    st.markdown("---")
    
    # Core Global Unified Aggregator Pipeline
    def master_funnel_compiler(df_c, df_p, group_dimensions):
        pivot_curr = df_c.groupby(group_dimensions)[['ls', 'uniq', 'ob', 'ft']].sum()
        pivot_prev = df_p.groupby(group_dimensions)[['ls', 'uniq', 'ob', 'ft']].sum()
        
        merged_set = pivot_curr.join(pivot_prev, lsuffix='_curr', rsuffix='_prev', how='outer').fillna(0).astype(int)
        
        # Process delta mutations
        merged_set['LS Drop'] = merged_set['ls_curr'] - merged_set['ls_prev']
        merged_set['Uniq Drop'] = merged_set['uniq_curr'] - merged_set['uniq_prev']
        merged_set['OB Drop'] = merged_set['ob_curr'] - merged_set['ob_prev']
        merged_set['FT Drop'] = merged_set['ft_curr'] - merged_set['ft_prev']
        
        # Process performance conversions
        merged_set['Uniq % (Jun)'] = (merged_set['uniq_curr'] / merged_set['ls_curr'] * 100).round(2).fillna(0)
        merged_set['Uniq Δpp'] = ((merged_set['uniq_curr'] / merged_set['ls_curr'] * 100) - (merged_set['uniq_prev'] / merged_set['ls_prev'] * 100)).round(2).fillna(0)
        
        merged_set['OB % (Jun)'] = (merged_set['ob_curr'] / merged_set['uniq_curr'] * 100).round(2).fillna(0)
        merged_set['OB Δpp'] = ((merged_set['ob_curr'] / merged_set['uniq_curr'] * 100) - (merged_set['ob_prev'] / merged_set['uniq_prev'] * 100)).round(2).fillna(0)
        
        merged_set['FT/OB % (Jun)'] = (merged_set['ft_curr'] / merged_set['ob_curr'] * 100).round(2).fillna(0)
        merged_set['FT/OB Δpp'] = ((merged_set['ft_curr'] / merged_set['ob_curr'] * 100) - (merged_set['ft_prev'] / merged_set['ob_prev'] * 100)).round(2).fillna(0)
        
        return merged_set.sort_values(by='ft_curr', ascending=False)

    # Replicating Cross Cuts UI blocks explicitly
    st.markdown("### 🗂️ Strategic Funnel Cross-Cuts")
    
    # Cut 1: Client Cross Cut
    st.markdown("#### S1: Client Cut")
    st.dataframe(master_funnel_compiler(df_current_window, df_previous_window, ['client']), use_container_width=True)
    
    # Cut 2: Product Source Cut
    st.markdown("#### S2: Product Source Cut")
    if 'lead_referral_type' in df_current_window.columns:
        st.dataframe(master_funnel_compiler(df_current_window, df_previous_window, ['lead_referral_type']), use_container_width=True)
        
    # Cut 4: Region Cut
    st.markdown("#### S4: Region Cut")
    st.dataframe(master_funnel_compiler(df_current_window, df_previous_window, ['region']), use_container_width=True)

    # Cut 5: Comprehensive Vendor Lead Cut (With Dynamic Top-N filter parameters built-in)
    st.markdown("#### S5: Vendor Lead (VL Cut) Configuration Matrix")
    top_n_vl = st.slider("Configure display window size for Top-N constraints", min_value=5, max_value=100, value=20)
    vl_performance_set = master_funnel_compiler(df_current_window, df_previous_window, ['vl_name'])
    st.dataframe(vl_performance_set.head(top_n_vl), use_container_width=True)

    # Cut 6-9: Double Layered Nested Analytical Drilldowns
    st.markdown("#### S6: Intersected Matrix Cut — Client × Product Source Split")
    if 'lead_referral_type' in df_current_window.columns:
        st.dataframe(master_funnel_compiler(df_current_window, df_previous_window, ['client', 'lead_referral_type']), use_container_width=True)

    st.markdown("#### S8: Intersected Matrix Cut — Client × Regional Footprint")
    st.dataframe(master_funnel_compiler(df_current_window, df_previous_window, ['client', 'region']), use_container_width=True)

    st.markdown("#### S9: Intersected Matrix Cut — Client × Vendor Lead (VL Grain)")
    st.dataframe(master_funnel_compiler(df_current_window, df_previous_window, ['client', 'vl_name']), use_container_width=True)


# ==========================================
# TAB: PRIORITIZED AI SUMMARY VIEW (RCA)
# ==========================================
with tab_ai_rca:
    st.markdown("### 🤖 Prioritized Funnel Leakage Root Cause Analysis (RCA)")
    
    # Complete backward validation pipeline tracking volume-weighted drops
    macro_ft_drop = totals_current['ft'] - totals_previous['ft']
    
    st.markdown("#### A. Microscopic Systemic Funnel Overview (P0 Constraints)")
    if macro_ft_drop < 0:
        st.error(f"🚨 **P0 Global Systemic Alert:** Total First Trips decreased by **{abs(macro_ft_drop):,}** relative to the matching historical target framework baseline.")
        
        # Compute conversion variances for step backward tracing checks
        ft_ob_variance = ob_to_ft_curr - ob_to_ft_prev
        ob_uniq_variance = uniq_to_ob_curr - uniq_to_ob_prev
        uniq_ls_variance = ls_to_uniq_curr - ls_to_uniq_prev
        
        # Step 1 backward evaluation checks: Activation Step Execution
        if ft_ob_variance < 0:
            st.markdown(f"❌ **P0 Bottleneck Located (OB ➔ FT Layer Collapse):** Systemic Conversion Efficiency decreased by **{abs(ft_ob_variance):.2f}pp**. Drivers complete profile activation configurations but default before the initial assignment trip run.")
        # Step 2 backward evaluation checks: Ingestion Filtering Layer
        if ob_uniq_variance < 0:
            st.markdown(f"❌ **P1 Bottleneck Located (Unique ➔ OB Profile Processing Delay):** Registration pipelines dropped by **{abs(ob_uniq_variance):.2f}pp** system-wide.")
        # Step 3 backward evaluation checks: Core Sourcing Quality Control
        if uniq_ls_variance < 0:
            st.markdown(f"❌ **P2 Bottleneck Located (LS ➔ Uniqueness Invalidation Shift):** Organic clean unique records degraded by **{abs(uniq_ls_variance):.2f}pp** indicating duplicate lead generation decay.")
        # Step 4 backward evaluation checks: Source Allocation Cap Ingress
        if totals_current['ls'] < totals_previous['ls']:
            st.markdown(f"❌ **P3 Bottleneck Located (Top-Of-Funnel Lead Volume Contraction):** Lead entry pool dropped by **{totals_previous['ls'] - totals_current['ls']:,}** records.")
    else:
        st.success(f"💚 **Global Ingress Metrics Healthy:** Placements changed by **+{macro_ft_drop:,}** over matching period boundaries.")

    st.markdown("---")
    st.markdown("#### B. Granular Segment Matrix Attribution (Client x Vendor Cut)")
    
    # Compile multi-indexed baseline frames for variance sorting arrays
    account_variance_set = master_funnel_compiler(df_current_window, df_previous_window, ['client'])
    underperforming_segments = account_variance_set[account_variance_set['FT Drop'] < 0].sort_values(by='FT Drop')
    
    if underperforming_segments.empty:
        st.info("No primary commercial business segments are demonstrating net system decay during this operational matrix segment.")
    else:
        for corporate_client, segment_data in underperforming_segments.iterrows():
            with st.expander(f"🔴 Deficit Vector - Client: {str(corporate_client).upper()} | Net Drop: {segment_data['FT Drop']:,} FT Placements", expanded=True):
                
                # Check for explicit micro-leakage patterns inside the client data bounds
                st.markdown("**Local Processing Failure Checkpoints:**")
                if segment_data['FT/OB Δpp'] < -2.0:
                    st.warning(f"⚠️ **OB ➔ FT Deployment Layer Leak:** Profile-to-Trip verification velocity dropped by **{segment_data['FT/OB Δpp']:.2f}pp** within this account's bounds.")
                if segment_data['OB Δpp'] < -2.0:
                    st.warning(f"⚠️ **Unique ➔ OB Verification Velocity Slowdown:** System onboarding processing efficiency shrank by **{segment_data['OB Δpp']:.2f}pp**.")
                if segment_data['LS Drop'] < 0:
                    st.warning(f"⚠️ **Ingress Pool Deficit:** Input lead source allocation contracted by **{abs(segment_data['LS Drop']):,}** entries.")
                
                # Attribute drop directly down to specific underperforming Vendor Lead (VL grain) entities
                st.markdown("**Primary Vendor Attribution Core (Underperforming VL Network Targets):**")
                vl_drill_frame = master_funnel_compiler(
                    df_current_window[df_current_window['client'] == corporate_client], 
                    df_previous_window[df_previous_window['client'] == corporate_client], 
                    ['vl_name']
                )
                top_laggard_vls = vl_drill_frame[vl_drill_frame['FT Drop'] < 0].sort_values(by='FT Drop').head(3)
                
                if not top_laggard_vls.empty:
                    for vl_identity, vl_metrics in top_laggard_vls.iterrows():
                        st.markdown(f"- **{vl_identity}**: Contributed a variance drop of **{vl_metrics['FT Drop']} FT** (Active: {vl_metrics['ft_curr']:,} vs Baseline: {vl_metrics['ft_prev']:,})")
                else:
                    st.caption("Friction parameters evenly normalized across vendor structures; no single operational outlier detected.")
