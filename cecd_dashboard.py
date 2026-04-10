#!/usr/bin/env python
# coding: utf-8

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

# ── Page config ──────────────────────────────────────────────
st.set_page_config(
    page_title="ECS Care Gap Dashboard",
    layout="wide",
    page_icon="🌱"
)

st.title("🌱 Endocannabinoid System (ECS) Care Gap Dashboard")
st.markdown("**Based on the 2024 Canadian Cannabis Survey (n=11,666)**")
st.markdown("*Hasib, S. (2026). Chasing the High. OSF Preprints. https://doi.org/10.31235/osf.io/znrhe_v1*")
st.markdown("""
> This dashboard applies Dr. Ethan Russo's theory of **Clinical Endocannabinoid Deficiency (CECD)**  
> to real-world population data, examining whether unmet biological need underlies the Care Gap —  
> the decoupling between users who perceive a need for help and those who actually receive it.
""")
st.markdown("---")

# ── Load data ────────────────────────────────────────────────
# COPY YOUR EXACT load_data() FUNCTION FROM warning_dashboard2.py HERE
@st.cache_data
def load_data():
    df = pd.read_csv("cannabis_dashboard_data.csv")
    missing = [-7, -8, -9]
    df = df.replace(missing, np.nan)
    df['work_use_binary'] = df['work_use'].apply(
        lambda x: 1 if x in [1,2,3,4] else (0 if x == 5 else np.nan))
    return df

df = load_data()

# ── Subsets ──────────────────────────────────────────────────
cannabis_users = df[df['canpurpose_dv'].isin([1,2,3])].copy()

# ── CECD Score Calculation ───────────────────────────────────
# Map symptoms to CECD-linked conditions (Russo 2004, 2016)
# These are the conditions Russo identified as likely CECD-related
cecd_symptoms = [
    'symp_anxiety_dv',       # Anxiety
    'symp_depression_dv',    # Depression
    'symp_chronicpain_dv',   # Chronic pain
    'symp_sleep_dv',         # Sleep disorders
    'symp_nausea_dv',        # Nausea/GI issues
    'symp_ptsd_dv',          # PTSD
    'symp_headache_dv',      # Migraines/headaches
    'symp_gastro_dv',        # GI/IBS
    'symp_arthritis_dv',     # Inflammatory pain
    'symp_spasms_dv',        # Muscle spasms
]

# Only use columns that exist in dataset
available_cecd = [col for col in cecd_symptoms if col in cannabis_users.columns]

# CECD score = number of CECD-linked symptoms reported (0 to max)
cannabis_users['cecd_score'] = cannabis_users[available_cecd].apply(
    lambda row: (row == 1).sum(), axis=1
)

# CECD likelihood tiers
def cecd_tier(score):
    if score == 0:
        return 'Low (0 symptoms)'
    elif score <= 2:
        return 'Moderate (1-2 symptoms)'
    elif score <= 4:
        return 'High (3-4 symptoms)'
    else:
        return 'Very High (5+ symptoms)'

cannabis_users['cecd_tier'] = cannabis_users['cecd_score'].apply(cecd_tier)

# Care Gap definition
# help_need: 2 or 3 = felt they needed help
# help_receive: 1 = did not receive help (or low receive vs need)
cannabis_users['care_gap'] = (
    cannabis_users['help_need'].isin([2, 3]) &
    ~cannabis_users['help_receive'].isin([2, 3])
).astype(int)

# ── Sidebar filters ──────────────────────────────────────────
# COPY YOUR EXACT SIDEBAR FROM warning_dashboard2.py
st.sidebar.header("🔍 Filter Data")
age_labels = {1:"16-19", 2:"20-24", 3:"25-34", 4:"35-44", 5:"45-54", 6:"55+"}
sex_labels = {1:"Male", 2:"Female"}
purpose_labels = {1:"Non-medical", 2:"Dual-purpose", 3:"Medical only"}

age_options = st.sidebar.multiselect(
    "Age Group", options=list(age_labels.keys()),
    format_func=lambda x: age_labels[x],
    default=list(age_labels.keys()))

sex_options = st.sidebar.multiselect(
    "Sex", options=list(sex_labels.keys()),
    format_func=lambda x: sex_labels[x],
    default=list(sex_labels.keys()))

purpose_options = st.sidebar.multiselect(
    "Purpose of Use", options=list(purpose_labels.keys()),
    format_func=lambda x: purpose_labels[x],
    default=list(purpose_labels.keys()))

filtered = cannabis_users.copy()
if age_options:
    filtered = filtered[filtered['age6'].isin(age_options)]
if sex_options:
    filtered = filtered[filtered['sex'].isin(sex_options)]
if purpose_options:
    filtered = filtered[filtered['canpurpose_dv'].isin(purpose_options)]

st.sidebar.markdown("---")
st.sidebar.metric("Filtered sample", f"{len(filtered):,}")
st.sidebar.metric("Avg CECD Score", f"{filtered['cecd_score'].mean():.2f}")
st.sidebar.metric("In Care Gap", f"{filtered['care_gap'].sum():,}")

# ── SECTION 1: What is CECD? ─────────────────────────────────
st.header("🧬 What is Clinical Endocannabinoid Deficiency (CECD)?")

col1, col2 = st.columns([2, 1])
with col1:
    st.markdown("""
    Dr. Ethan Russo's CECD theory proposes that certain chronic conditions arise when the body 
    cannot produce sufficient endocannabinoids to maintain homeostasis — the body's natural balance.

    Just as Parkinson's involves dopamine deficiency and depression involves serotonin dysregulation, 
    **CECD represents an endocannabinoid deficiency** that may underlie conditions like:

    - 😰 Anxiety & PTSD  
    - 😴 Sleep disorders  
    - 🤕 Migraines & chronic pain  
    - 🤢 IBS & nausea  
    - 😔 Depression  
    - 🔥 Inflammatory conditions (arthritis, spasms)

    The **Entourage Effect** (also Russo) suggests that whole-plant cannabis — cannabinoids + terpenes 
    working together — may more effectively restore this balance than any single compound alone.

    **This dashboard asks:** Are people who fall into the Care Gap doing so because of unmet biological need?
    """)
with col2:
    # CECD score distribution
    score_dist = (
        filtered['cecd_score']
        .value_counts()
        .sort_index()
        .rename_axis('CECD Score')   # ✅ ensures correct label
        .reset_index(name='Count')   # ✅ explicitly names counts
    )

    if score_dist.empty:
        st.warning("No data available for CECD score distribution.")
    else:
        fig_dist = px.bar(
            score_dist,
            x='CECD Score',
            y='Count',
            title='CECD Score Distribution',
            color='CECD Score',
            color_continuous_scale='Greens'
        )

        fig_dist.update_layout(
            plot_bgcolor='white',
            coloraxis_showscale=False,
            xaxis_title='Number of CECD-linked Symptoms'
        )

        st.plotly_chart(fig_dist, use_container_width=True)

st.markdown("---")

# ── SECTION 2: CECD Score vs Care Gap ───────────────────────
st.header("📊 CECD Score & The Care Gap")
st.markdown("Do users with higher CECD symptom burden fall into the Care Gap more often?")

col1, col2, col3 = st.columns(3)
high_cecd = filtered[filtered['cecd_score'] >= 3]
low_cecd = filtered[filtered['cecd_score'] <= 1]

col1.metric("High CECD (3+ symptoms)", f"{len(high_cecd):,}")
col2.metric("Care Gap in High CECD group",
            f"{high_cecd['care_gap'].mean()*100:.1f}%")
col3.metric("Care Gap in Low CECD group",
            f"{low_cecd['care_gap'].mean()*100:.1f}%")

# Care gap by CECD tier
tier_order = ['Low (0 symptoms)', 'Moderate (1-2 symptoms)',
              'High (3-4 symptoms)', 'Very High (5+ symptoms)']

gap_by_tier = filtered.groupby('cecd_tier')['care_gap'].agg(['mean', 'count']).reset_index()
gap_by_tier['mean'] = gap_by_tier['mean'] * 100
gap_by_tier.columns = ['CECD Tier', 'Care Gap %', 'Count']
gap_by_tier['CECD Tier'] = pd.Categorical(gap_by_tier['CECD Tier'],
                                           categories=tier_order, ordered=True)
gap_by_tier = gap_by_tier.sort_values('CECD Tier')

fig2 = px.bar(gap_by_tier, x='CECD Tier', y='Care Gap %',
              title='Care Gap Rate by CECD Symptom Burden',
              color='Care Gap %',
              color_continuous_scale='RdYlGn_r',
              text='Care Gap %')
fig2.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
fig2.update_layout(plot_bgcolor='white', coloraxis_showscale=False,
                   yaxis_range=[0, 80], xaxis_title='CECD Symptom Tier')
st.plotly_chart(fig2, use_container_width=True)

st.info("""
**Interpretation:** If users with higher CECD symptom burden show higher Care Gap rates, 
this suggests their unmet need may be biological — not just due to stigma or access barriers alone.
""")
st.markdown("---")

# ── SECTION 3: Symptom Heatmap ───────────────────────────────
st.header("🔥 CECD Symptom Profile by User Type")
st.markdown("Which CECD-linked symptoms are most prevalent across medical, dual-purpose, and recreational users?")

symptom_labels = {
    'symp_anxiety_dv': 'Anxiety',
    'symp_depression_dv': 'Depression',
    'symp_chronicpain_dv': 'Chronic Pain',
    'symp_sleep_dv': 'Sleep Disorder',
    'symp_nausea_dv': 'Nausea/GI',
    'symp_ptsd_dv': 'PTSD',
    'symp_headache_dv': 'Headache/Migraine',
    'symp_gastro_dv': 'Gastro/IBS',
    'symp_arthritis_dv': 'Arthritis',
    'symp_spasms_dv': 'Spasms',
}

heatmap_data = []
for purpose_code, purpose_name in purpose_labels.items():
    group = filtered[filtered['canpurpose_dv'] == purpose_code]
    for col, label in symptom_labels.items():
        if col in group.columns:
            pct = (group[col] == 1).mean() * 100
            heatmap_data.append({
                'User Type': purpose_name,
                'Symptom': label,
                'Prevalence %': round(pct, 1)
            })

heatmap_df = pd.DataFrame(heatmap_data)
heatmap_pivot = heatmap_df.pivot(index='Symptom', columns='User Type', values='Prevalence %')

fig3 = px.imshow(heatmap_pivot,
                 title='CECD Symptom Prevalence by Cannabis Use Type (%)',
                 color_continuous_scale='Greens',
                 text_auto='.1f',
                 aspect='auto')
fig3.update_layout(xaxis_title='User Type', yaxis_title='CECD-Linked Symptom')
st.plotly_chart(fig3, use_container_width=True)

st.markdown("---")

# ── SECTION 4: Consumption Mode & Entourage Effect ──────────
st.header("🌿 Consumption Mode & the Entourage Effect")
st.markdown("""
Russo's Entourage Effect predicts that **whole-plant formulations** (smoking, vaping flower) 
produce better therapeutic outcomes than isolated compounds. Are medical users with high CECD 
scores gravitating toward entourage-effect-rich consumption methods?
""")

mode_vars = {
    'use_modes_smoke': 'Smoking (flower)',
    'use_modes_vape': 'Vaping',
    'use_modes_oil': 'Oils/Tinctures',
    'use_modes_edible': 'Edibles',
    'use_modes_topical': 'Topicals',
    'use_modes_bev': 'Beverages',
    'use_modes_dab': 'Concentrates/Dabs',
}

col1, col2 = st.columns(2)

with col1:
    # High CECD users
    high_cecd_f = filtered[filtered['cecd_score'] >= 3]
    mode_high = []
    for col_name, label in mode_vars.items():
        if col_name in high_cecd_f.columns:
            pct = (high_cecd_f[col_name] == 1).mean() * 100
            mode_high.append({'Mode': label, 'Usage %': round(pct, 1)})
    mode_high_df = pd.DataFrame(mode_high).sort_values('Usage %', ascending=True)

    fig4a = px.bar(mode_high_df, x='Usage %', y='Mode', orientation='h',
                   title='High CECD Users (3+ symptoms) — Consumption Methods',
                   color='Usage %', color_continuous_scale='Greens',
                   text='Usage %')
    fig4a.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
    fig4a.update_layout(plot_bgcolor='white', coloraxis_showscale=False,
                        xaxis_range=[0, 100])
    st.plotly_chart(fig4a, use_container_width=True)

with col2:
    # Low CECD users
    low_cecd_f = filtered[filtered['cecd_score'] <= 1]
    mode_low = []
    for col_name, label in mode_vars.items():
        if col_name in low_cecd_f.columns:
            pct = (low_cecd_f[col_name] == 1).mean() * 100
            mode_low.append({'Mode': label, 'Usage %': round(pct, 1)})
    mode_low_df = pd.DataFrame(mode_low).sort_values('Usage %', ascending=True)

    fig4b = px.bar(mode_low_df, x='Usage %', y='Mode', orientation='h',
                   title='Low CECD Users (0-1 symptoms) — Consumption Methods',
                   color='Usage %', color_continuous_scale='Blues',
                   text='Usage %')
    fig4b.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
    fig4b.update_layout(plot_bgcolor='white', coloraxis_showscale=False,
                        xaxis_range=[0, 100])
    st.plotly_chart(fig4b, use_container_width=True)

st.markdown("---")

# ── SECTION 5: ECS Screening Tool ───────────────────────────
st.header("🧪 Personal ECS Screening Tool")
st.markdown("""
*This tool is for educational purposes only. It is not a diagnostic instrument.*  
Answer the questions below to see your estimated CECD symptom burden and what the 
population data suggests about users like you.
""")

st.subheader("Step 1: Your Symptoms")
st.markdown("Select any conditions you experience regularly:")

col1, col2, col3 = st.columns(3)
with col1:
    has_anxiety = st.checkbox("😰 Anxiety")
    has_depression = st.checkbox("😔 Depression")
    has_sleep = st.checkbox("😴 Sleep problems")
    has_pain = st.checkbox("🤕 Chronic pain")
with col2:
    has_ptsd = st.checkbox("🧠 PTSD / trauma symptoms")
    has_migraine = st.checkbox("🤯 Migraines / headaches")
    has_nausea = st.checkbox("🤢 Nausea / GI issues")
    has_ibs = st.checkbox("🫃 IBS / gut issues")
with col3:
    has_arthritis = st.checkbox("🦴 Arthritis / joint pain")
    has_spasms = st.checkbox("⚡ Muscle spasms")
    has_none = st.checkbox("✅ None of the above")

st.subheader("Step 2: Your Cannabis Use")
user_purpose = st.selectbox(
    "Why do you use cannabis?",
    options=[1, 2, 3],
    format_func=lambda x: {
        1: "Recreation only",
        2: "Both medical and recreational",
        3: "Medical only"
    }[x]
)

user_mode = st.multiselect(
    "How do you consume cannabis?",
    options=["Smoking (flower)", "Vaping", "Oils/Tinctures",
             "Edibles", "Topicals", "Concentrates/Dabs"]
)

user_help_need = st.selectbox(
    "Have you ever felt you needed help related to your cannabis use?",
    options=[1, 2, 3],
    format_func=lambda x: {
        1: "No, never",
        2: "Yes, in the past 12 months",
        3: "Yes, but not recently"
    }[x]
)

user_help_receive = st.selectbox(
    "Have you received professional support for your cannabis use?",
    options=[1, 2],
    format_func=lambda x: {
        1: "No",
        2: "Yes"
    }[x]
)

if st.button("🔍 Calculate My ECS Profile", type="primary"):
    # Calculate user CECD score
    symptoms = [has_anxiety, has_depression, has_sleep, has_pain,
                has_ptsd, has_migraine, has_nausea, has_ibs,
                has_arthritis, has_spasms]
    user_cecd_score = sum(symptoms) if not has_none else 0
    user_tier = cecd_tier(user_cecd_score)
    user_in_gap = user_help_need in [2, 3] and user_help_receive == 1

    st.markdown("---")
    st.subheader("📊 Your ECS Profile")

    col1, col2, col3 = st.columns(3)
    col1.metric("Your CECD Score", f"{user_cecd_score} / {len(symptoms)}")
    col2.metric("CECD Tier", user_tier)
    col3.metric("Care Gap Status",
                "⚠️ In Care Gap" if user_in_gap else "✅ Not in Care Gap")

    # Find similar users in dataset
    similar = filtered.copy()
    if user_cecd_score >= 3:
        similar = similar[similar['cecd_score'] >= 3]
    elif user_cecd_score <= 1:
        similar = similar[similar['cecd_score'] <= 1]

    st.markdown(f"**{len(similar):,} people in the national dataset share a similar CECD profile.**")

    if user_cecd_score >= 3:
        st.warning(f"""
        🌱 **High CECD Symptom Burden Detected**

        You reported {user_cecd_score} CECD-linked symptoms. According to Russo's theory, 
        your body may have an underlying endocannabinoid deficiency contributing to these conditions.

        In the national data, **{similar['care_gap'].mean()*100:.1f}%** of users with similar 
        symptom profiles fall into the Care Gap — meaning they felt they needed help but didn't receive it.

        **What this may mean:** Your cannabis use may be serving a genuine biological function. 
        Whole-plant formulations leveraging the Entourage Effect (flower, full-spectrum oils) 
        may be more effective than isolated compounds for your symptom profile.
        """)

    elif user_cecd_score > 0:
        st.info(f"""
        🌿 **Moderate CECD Symptom Burden**

        You reported {user_cecd_score} CECD-linked symptoms. Some biological need may be present.
        In the national data, **{similar['care_gap'].mean()*100:.1f}%** of similar users 
        fall into the Care Gap.

        Consider speaking with a cannabis-informed healthcare provider about your symptom profile.
        """)
    else:
        st.success("""
        ✅ **Low CECD Symptom Burden**

        You reported few or no CECD-linked symptoms. Your cannabis use appears to be 
        primarily recreational rather than driven by an underlying biological deficiency.

        This is valuable data — recreational users form the baseline against which 
        therapeutic patterns can be understood.
        """)

    if user_in_gap:
        st.error("""
        ⚠️ **You Are in the Care Gap**

        You felt you needed help but haven't received it. You are not alone — 
        this is one of the most common patterns in the national data.

        Resources to explore:
        - Talk to a cannabis-informed physician
        - The Network of Applied Pharmacognosy (NAP): appliedpharmacognosy.org
        - Cannabis Consumers Coalition
        """)

    # Entourage effect recommendation
    entourage_modes = ["Smoking (flower)", "Vaping", "Oils/Tinctures"]
    user_uses_entourage = any(m in entourage_modes for m in user_mode)

    if user_cecd_score >= 3 and not user_uses_entourage:
        st.info("""
        💡 **Entourage Effect Consideration**

        Users with your symptom profile in the national data tend to benefit from 
        whole-plant consumption methods. If you primarily use edibles or isolates, 
        you may not be experiencing the full synergistic effect of cannabinoids and terpenes.

        Consider discussing full-spectrum formulations with a healthcare provider.
        """)

st.markdown("---")
st.caption("""
⚠️ This tool is for educational and research purposes only. It is not a clinical diagnostic tool.  
Results are based on population-level patterns from the 2024 Canadian Cannabis Survey.  
This does not constitute medical advice. If you are concerned about your health, please speak with a healthcare professional.
""")
st.caption("""
📄 Framework based on:  
Russo, E.B. (2004). Clinical Endocannabinoid Deficiency (CECD). Neuroendocrinology Letters.  
Russo, E.B. (2011). Taming THC: potential cannabis synergy and phytocannabinoid-terpenoid entourage effects. British Journal of Pharmacology.  
Hasib, S. (2026). Chasing the High. OSF Preprints. https://doi.org/10.31235/osf.io/znrhe_v1
""")
st.markdown("**Data source:** Statistics Canada, 2024 Canadian Cannabis Survey PUMF | "
            "**GitHub:** github.com/sunehera")
