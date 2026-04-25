#!/usr/bin/env python
# coding: utf-8

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import uuid



def get_supabase_client():
    """Initialize Supabase client if credentials are available."""
    try:
        from supabase import create_client
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["key"]
        return create_client(url, key)
    except Exception:
        return None

def user_login():
    """Show a simple login box and return the user identifier."""
    if 'user_id' in st.session_state and st.session_state.user_id:
        return st.session_state.user_id

    st.markdown('---')
    st.subheader('👤 Track Your Progress Over Time')
    st.markdown('Enter your name or email to save your results and access your history on any device.')

    col1, col2 = st.columns([3, 1])
    with col1:
        identifier = st.text_input(
            "Your name or email (used only to retrieve your history)",
            placeholder="e.g. jane@email.com or Jane",
            key="login_input"
        )
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        login_btn = st.button("Continue →", type="primary")

    st.caption("🔒 Your identifier is only used to link your screening history. No passwords, no account required.")

    if login_btn and identifier.strip():
        st.session_state.user_id = identifier.strip().lower()
        st.rerun()
    elif login_btn and not identifier.strip():
        st.error("Please enter a name or email to continue.")

    st.stop()
    return None

def save_to_supabase(client, user_id, entry):
    """Save a screening result to Supabase."""
    try:
        data = {
            'user_id': user_id,
            'cecd_score': entry['cecd_score'],
            'cecd_tier': entry['cecd_tier'],
            'in_care_gap': bool(entry['in_care_gap']),
            'frequency': entry.get('frequency'),
            'effectiveness': entry.get('effectiveness'),
        }
        client.table('screening_results').insert(data).execute()
        return True
    except Exception as e:
        return False

def load_from_supabase(client, user_id):
    """Load all screening results for a user from Supabase."""
    try:
        response = client.table('screening_results')\
            .select('*')\
            .eq('user_id', user_id)\
            .order('date')\
            .execute()
        if response.data:
            df = pd.DataFrame(response.data)
            df['date'] = pd.to_datetime(df['date']).dt.strftime("%Y-%m-%d %H:%M")
            return df[['date', 'cecd_score', 'cecd_tier', 'in_care_gap', 
                       'frequency', 'effectiveness']].to_dict('records')
        return []
    except Exception:
        return []

# ── Page config ──────────────────────────────────────────────
st.set_page_config(
    page_title="ECS Care Gap Dashboard",
    layout="wide",
    page_icon="🌱"
)

st.title("🌱 Endocannabinoid System (ECS) Care Gap Dashboard")
st.markdown("**Based on the 2024 Canadian Cannabis Survey (n=11,666)**")
st.markdown("*Hasib, S. (2026). Chasing the High. OSF Preprints. https://doi.org/10.31235/osf.io/znrhe_v1*")

# ── FIX 1: Clearer framing — CECD as hypothesis, Care Gap defined ──
st.info("""
**About this dashboard**

The **Care Gap** refers to cannabis users who perceived a need for professional support 
but did not receive it — capturing unmet need, not a judgment about cannabis use itself.

This dashboard uses Dr. Ethan Russo's **Clinical Endocannabinoid Deficiency (CECD) hypothesis** 
as one possible lens for understanding why certain users fall into the Care Gap. 
CECD is a working hypothesis, not a clinically established diagnosis. The symptom patterns 
shown here may have biological, psychological, social, or combined explanations.

*This tool is educational only and does not constitute medical advice.*
""")

st.markdown("---")

# ── Load data ────────────────────────────────────────────────
@st.cache_data
def load_data():
    df = pd.read_csv("cannabis_dashboard_data2.csv")
    missing = [-7, -8, -9]
    df = df.replace(missing, np.nan)
    df['work_use_binary'] = df['work_use'].apply(
        lambda x: 1 if x in [1,2,3,4] else (0 if x == 5 else np.nan))
    return df

df = load_data()

# ── Subsets ──────────────────────────────────────────────────
cannabis_users = df[df['canpurpose_dv'].isin([1,2,3])].copy()

# ── CECD Score Calculation ───────────────────────────────────
cecd_symptoms = [
    'symp_anxiety_dv',
    'symp_depression_dv',
    'symp_chronicpain_dv',
    'symp_sleep_dv',
    'symp_nausea_dv',
    'symp_ptsd_dv',
    'symp_headache_dv',
    'symp_gastro_dv',
    'symp_arthritis_dv',
    'symp_spasms_dv',
]

available_cecd = [col for col in cecd_symptoms if col in cannabis_users.columns]

cannabis_users['cecd_score'] = cannabis_users[available_cecd].apply(
    lambda row: (row == 1).sum(), axis=1
)

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

cannabis_users['care_gap'] = (
    cannabis_users['help_need'].isin([2, 3]) &
    ~cannabis_users['help_receive'].isin([2, 3])
).astype(int)

# ── Sidebar filters ──────────────────────────────────────────
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
st.sidebar.metric("Avg ECS Symptom Score", f"{filtered['cecd_score'].mean():.2f}")
st.sidebar.metric("In Care Gap", f"{filtered['care_gap'].sum():,}")

# ── SECTION 1: What is CECD? ─────────────────────────────────
st.header("🧬 The Endocannabinoid System & CECD Hypothesis")

col1, col2 = st.columns([2, 1])
with col1:
    # FIX 2: Hypothesis framing throughout
    st.markdown("""
    The **endocannabinoid system (ECS)** regulates mood, pain, sleep, appetite, and immune function.

    Dr. Ethan Russo proposed the **Clinical Endocannabinoid Deficiency (CECD) hypothesis** — 
    the idea that some chronic conditions may arise when the body cannot produce sufficient 
    endocannabinoids. This is a **working hypothesis**, not a clinically established diagnosis, 
    and is one of several possible explanations for why certain people use cannabis to manage symptoms.

    Conditions Russo associated with possible ECS dysregulation include:

    - 😰 Anxiety & PTSD  
    - 😴 Sleep disorders  
    - 🤕 Migraines & chronic pain  
    - 🤢 IBS & nausea  
    - 😔 Depression  
    - 🔥 Inflammatory conditions (arthritis, spasms)

    The **Entourage Effect** (also Russo) suggests whole-plant cannabis may produce 
    different effects than isolated compounds — another hypothesis under active investigation.

    **This dashboard explores:** Are users with higher ECS symptom burden more likely to 
    fall into the Care Gap? And if so, what might explain that association?

    > *The Care Gap may reflect stigma, access barriers, biological factors, or a 
    > combination. This dashboard does not claim biology is the sole cause.*
    """)
with col2:
    score_dist = filtered['cecd_score'].value_counts().sort_index().reset_index()
    score_dist.columns = ['ECS Symptom Score', 'Count']
    fig_dist = px.bar(score_dist, x='ECS Symptom Score', y='Count',
                      title='ECS Symptom Score Distribution',
                      color='ECS Symptom Score',
                      color_continuous_scale='Greens')
    fig_dist.update_layout(plot_bgcolor='white', coloraxis_showscale=False,
                           xaxis_title='Number of ECS-linked Symptoms')
    st.plotly_chart(fig_dist, use_container_width=True)

st.markdown("---")

# ── SECTION 2: CECD Score vs Care Gap ───────────────────────
st.header("📊 ECS Symptom Burden & The Care Gap")

# FIX 3: Care Gap explicitly defined
st.markdown("""
**Care Gap Definition:** A user is in the Care Gap if they reported perceiving a need 
for professional support related to their cannabis use, but did not receive that support.
""")

col1, col2, col3 = st.columns(3)
high_cecd = filtered[filtered['cecd_score'] >= 3]
low_cecd = filtered[filtered['cecd_score'] <= 1]

col1.metric("High Symptom Burden (3+ symptoms)", f"{len(high_cecd):,}")
col2.metric("Care Gap — High Symptom group",
            f"{high_cecd['care_gap'].mean()*100:.1f}%")
col3.metric("Care Gap — Low Symptom group",
            f"{low_cecd['care_gap'].mean()*100:.1f}%")

tier_order = ['Low (0 symptoms)', 'Moderate (1-2 symptoms)',
              'High (3-4 symptoms)', 'Very High (5+ symptoms)']

gap_by_tier = filtered.groupby('cecd_tier')['care_gap'].agg(['mean', 'count']).reset_index()
gap_by_tier['mean'] = gap_by_tier['mean'] * 100
gap_by_tier.columns = ['ECS Symptom Tier', 'Care Gap %', 'Count']
gap_by_tier['ECS Symptom Tier'] = pd.Categorical(gap_by_tier['ECS Symptom Tier'],
                                           categories=tier_order, ordered=True)
gap_by_tier = gap_by_tier.sort_values('ECS Symptom Tier')

fig2 = px.bar(gap_by_tier, x='ECS Symptom Tier', y='Care Gap %',
              title='Care Gap Rate by ECS Symptom Burden',
              color='Care Gap %',
              color_continuous_scale='RdYlGn_r',
              text='Care Gap %')
fig2.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
fig2.update_layout(plot_bgcolor='white', coloraxis_showscale=False,
                   yaxis_range=[0, 80], xaxis_title='ECS Symptom Tier')
st.plotly_chart(fig2, use_container_width=True)

# FIX 4: Neutral interpretation
st.info("""
**How to interpret this:** Users with higher ECS symptom burden show higher Care Gap rates. 
This association may reflect biological factors, greater stigma among those managing complex 
symptoms, reduced capacity to navigate healthcare, or other unmeasured factors. 
Further research is needed to establish causation.
""")
st.markdown("---")

# ── SECTION 3: Symptom Heatmap ───────────────────────────────
st.header("🔥 Symptom Profile by User Type")
st.markdown("Which symptoms are most prevalent across medical, dual-purpose, and recreational users?")

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
                 title='Symptom Prevalence by Cannabis Use Type (%)',
                 color_continuous_scale='Greens',
                 text_auto='.1f',
                 aspect='auto')
fig3.update_layout(xaxis_title='User Type', yaxis_title='Symptom')
st.plotly_chart(fig3, use_container_width=True)

st.markdown("---")

# ── SECTION 4: Consumption Mode ─────────────────────────────
st.header("🌿 Consumption Mode & the Entourage Effect")
st.markdown("""
Russo's Entourage Effect hypothesis suggests whole-plant formulations may produce 
different effects than isolated compounds. Are high-symptom users gravitating toward 
different consumption methods?
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
    high_cecd_f = filtered[filtered['cecd_score'] >= 3]
    mode_high = []
    for col_name, label in mode_vars.items():
        if col_name in high_cecd_f.columns:
            pct = (high_cecd_f[col_name] == 1).mean() * 100
            mode_high.append({'Mode': label, 'Usage %': round(pct, 1)})
    mode_high_df = pd.DataFrame(mode_high).sort_values('Usage %', ascending=True)

    fig4a = px.bar(mode_high_df, x='Usage %', y='Mode', orientation='h',
                   title='High Symptom Users (3+) — Consumption Methods',
                   color='Usage %', color_continuous_scale='Greens',
                   text='Usage %')
    fig4a.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
    fig4a.update_layout(plot_bgcolor='white', coloraxis_showscale=False,
                        xaxis_range=[0, 100])
    st.plotly_chart(fig4a, use_container_width=True)

with col2:
    low_cecd_f = filtered[filtered['cecd_score'] <= 1]
    mode_low = []
    for col_name, label in mode_vars.items():
        if col_name in low_cecd_f.columns:
            pct = (low_cecd_f[col_name] == 1).mean() * 100
            mode_low.append({'Mode': label, 'Usage %': round(pct, 1)})
    mode_low_df = pd.DataFrame(mode_low).sort_values('Usage %', ascending=True)

    fig4b = px.bar(mode_low_df, x='Usage %', y='Mode', orientation='h',
                   title='Low Symptom Users (0-1) — Consumption Methods',
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
Answer the questions below to see how your profile compares to the national dataset.
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

st.subheader("Step 2: Your Cannabis Use & Patterns")

col1, col2 = st.columns(2)
with col1:
    # FIX 5: No pre-loaded defaults — None option added
    user_purpose = st.selectbox(
        "Why do you use cannabis?",
        options=[None, 1, 2, 3],
        format_func=lambda x: "Select an option" if x is None else {
            1: "Recreation only",
            2: "Both medical and recreational",
            3: "Medical only"
        }[x]
    )

    user_frequency = st.selectbox(
        "How often do you use cannabis?",
        options=[None, 1, 2, 3, 4, 5],
        format_func=lambda x: "Select an option" if x is None else {
            1: "Daily",
            2: "A few times a week",
            3: "Weekly",
            4: "Monthly",
            5: "Rarely"
        }[x]
    )

    user_duration = st.selectbox(
        "How long have you been using cannabis?",
        options=[None, 1, 2, 3, 4],
        format_func=lambda x: "Select an option" if x is None else {
            1: "Less than 1 year",
            2: "1-3 years",
            3: "3-5 years",
            4: "5+ years"
        }[x]
    )

with col2:
    user_mode = st.multiselect(
        "How do you consume cannabis?",
        options=["Smoking (flower)", "Vaping", "Oils/Tinctures",
                 "Edibles", "Topicals", "Concentrates/Dabs"]
    )

    user_time_of_day = st.multiselect(
        "When do you typically use cannabis?",
        options=["Morning", "Afternoon", "Evening",
                 "Night", "Multiple times a day"]
    )

    user_dose_change = st.selectbox(
        "Have you increased your dose over time?",
        options=[None, 1, 2, 3],
        format_func=lambda x: "Select an option" if x is None else {
            1: "Yes, increased",
            2: "No, stayed the same",
            3: "Decreased"
        }[x]
    )

st.subheader("Step 3: Motivations & Outcomes")

col1, col2 = st.columns(2)
with col1:
    user_top_symptom = st.selectbox(
        "Which symptom does cannabis help most?",
        options=[None, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11],
        format_func=lambda x: "Select an option" if x is None else {
            1: "Anxiety", 2: "Depression", 3: "Sleep",
            4: "Chronic pain", 5: "PTSD", 6: "Migraines",
            7: "Nausea / GI", 8: "Inflammation / arthritis",
            9: "Muscle spasms", 10: "Recreational / enjoyment",
            11: "Other"
        }[x]
    )

    user_effectiveness = st.selectbox(
        "Does cannabis actually help with this symptom?",
        options=[None, 1, 2, 3, 4],
        format_func=lambda x: "Select an option" if x is None else {
            1: "Yes, always", 2: "Sometimes",
            3: "Rarely", 4: "No"
        }[x]
    )

with col2:
    user_tried_pharma = st.selectbox(
        "Have you tried pharmaceutical alternatives for your symptoms?",
        options=[None, 1, 2],
        format_func=lambda x: "Select an option" if x is None else {
            1: "Yes", 2: "No"
        }[x]
    )

    user_substituted = None
    if user_tried_pharma == 1:
        user_substituted = st.selectbox(
            "Did you substitute cannabis for a medication?",
            options=[None, 1, 2, 3],
            format_func=lambda x: "Select an option" if x is None else {
                1: "Yes, completely replaced it",
                2: "Yes, reduced my dose",
                3: "No, I use both"
            }[x]
        )

    user_help_need = st.selectbox(
        "Have you ever felt you needed help related to your cannabis use?",
        options=[None, 1, 2, 3],
        format_func=lambda x: "Select an option" if x is None else {
            1: "No, never",
            2: "Yes, in the past 12 months",
            3: "Yes, but not recently"
        }[x]
    )

    user_help_receive = st.selectbox(
        "Have you received professional support for your cannabis use?",
        options=[None, 1, 2],
        format_func=lambda x: "Select an option" if x is None else {
            1: "No", 2: "Yes"
        }[x]
    )

# ── Persistent Storage Setup ──────────────────────────────────
supabase = get_supabase_client()
user_id = user_login()  # Show login prompt, stops page until user enters ID

# Load existing history — from Supabase if available, else session state
if 'tracking_history' not in st.session_state or len(st.session_state.tracking_history) == 0:
    if supabase and user_id:
        st.session_state.tracking_history = load_from_supabase(supabase, user_id)
    else:
        st.session_state.tracking_history = []

# Show user info in sidebar
st.sidebar.markdown("---")
if user_id:
    st.sidebar.markdown(f"**Logged in as:** ")
    if st.sidebar.button("🔄 Switch User"):
        del st.session_state["user_id"]
        st.session_state.tracking_history = []
        st.rerun()
if not supabase:
    st.sidebar.caption("⚠️ Persistent storage not configured. Add Supabase credentials to save history across sessions.")

if st.button("🔍 Calculate My ECS Profile", type="primary"):

    # FIX 6: Validate all fields before calculating
    required = [user_purpose, user_frequency, user_duration,
                user_dose_change, user_top_symptom, user_effectiveness,
                user_tried_pharma, user_help_need, user_help_receive]

    if any(v is None for v in required):
        st.error("⚠️ Please answer all questions before calculating your profile.")
    else:
        # Original logic preserved with original numeric values
        symptoms = [has_anxiety, has_depression, has_sleep, has_pain,
                    has_ptsd, has_migraine, has_nausea, has_ibs,
                    has_arthritis, has_spasms]
        user_cecd_score = sum(symptoms) if not has_none else 0
        user_tier = cecd_tier(user_cecd_score)
        user_in_gap = user_help_need in [2, 3] and user_help_receive == 1
        is_daily = user_frequency == 1
        is_long_term = user_duration == 4
        dose_escalating = user_dose_change == 1
        substituted = user_substituted in [1, 2] if user_substituted else False
        morning_use = "Morning" in user_time_of_day
        multi_daily = "Multiple times a day" in user_time_of_day

        # Save to tracker
        new_entry = {
            'date': datetime.now().strftime("%Y-%m-%d %H:%M"),
            'cecd_score': user_cecd_score,
            'cecd_tier': user_tier,
            'in_care_gap': user_in_gap,
            'frequency': user_frequency,
            'effectiveness': user_effectiveness,
        }
        st.session_state.tracking_history.append(new_entry)
        
        # Save to Supabase if available
        if supabase:
            saved = save_to_supabase(supabase, user_id, new_entry)
            if saved:
                st.success("✅ Your results have been saved to your Progress Tracker and stored persistently!")

        st.markdown("---")
        st.subheader("📊 Your ECS Profile")

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Your ECS Symptom Score", f"{user_cecd_score} / {len(symptoms)}")
        col2.metric("Symptom Tier", user_tier)
        col3.metric("Care Gap Status",
                    "⚠️ In Care Gap" if user_in_gap else "✅ Not in Care Gap")
        col4.metric("Use Pattern",
                    "🔴 High intensity" if (is_daily or multi_daily)
                    else "🟡 Moderate" if user_frequency <= 3
                    else "🟢 Low")

        similar = filtered.copy()
        if user_cecd_score >= 3:
            similar = similar[similar['cecd_score'] >= 3]
        elif user_cecd_score <= 1:
            similar = similar[similar['cecd_score'] <= 1]

        st.markdown(f"**{len(similar):,} people in the national dataset share a similar symptom profile.**")

        # FIX 7: Neutral language in results
        if user_cecd_score >= 3:
            st.warning(f"""
            🌱 **High ECS Symptom Burden**

            You reported {user_cecd_score} symptoms associated with possible ECS dysregulation. 
            This is consistent with profiles described in Russo's CECD hypothesis — though 
            multiple explanations exist for this pattern.

            In the national data, **{similar['care_gap'].mean()*100:.1f}%** of users with 
            similar profiles fall into the Care Gap.

            Consider speaking with a cannabis-informed healthcare provider about your symptoms.
            """)
        elif user_cecd_score > 0:
            st.info(f"""
            🌿 **Moderate ECS Symptom Burden**

            You reported {user_cecd_score} symptoms that may be associated with ECS dysregulation.
            In the national data, **{similar['care_gap'].mean()*100:.1f}%** of similar users 
            fall into the Care Gap.
            """)
        else:
            st.success("""
            ✅ **Low ECS Symptom Burden**

            You reported few or no symptoms associated with ECS dysregulation. 
            Your cannabis use appears primarily recreational in nature.
            """)

        # FIX 8: Transparent methodology
        with st.expander("📖 How is your score calculated?"):
            st.markdown(f"""
            **ECS Symptom Score:** Calculated by summing the number of symptoms you selected 
            from a list of 10 conditions associated with possible ECS dysregulation in Russo's 
            CECD hypothesis (2004, 2016). Score ranges from 0 to 10.

            **Your score: {user_cecd_score}/10**

            **Tier assignment:**
            - 0 symptoms → Low
            - 1-2 symptoms → Moderate  
            - 3-4 symptoms → High
            - 5+ symptoms → Very High

            **Care Gap:** You are in the Care Gap if you perceived a need for professional 
            support but have not received it.

            **Important:** This is a self-reported symptom checklist, not a clinical assessment.
            """)

        if dose_escalating and user_cecd_score >= 2:
            st.warning("""
            📈 **Dose Escalation Pattern**
            You've increased your dose over time alongside multiple symptoms. 
            A cannabis-informed clinician can help you find the right approach.
            """)

        if morning_use or multi_daily:
            st.warning(f"""
            🌅 **Early & Frequent Use Pattern**
            You use cannabis in the morning or multiple times daily. 
            In the national data, **{filtered['daily_dv'].mean()*100:.1f}%** report daily use.
            """)

        if substituted:
            st.info("""
            💊 **Pharmaceutical Substitution**
            You've reduced or replaced a medication with cannabis. 
            Please discuss medication changes with your prescribing physician.
            """)

        if user_effectiveness in [3, 4] and user_cecd_score >= 2:
            st.info("""
            🔄 **Low Effectiveness + High Symptom Burden**
            Cannabis doesn't seem to be fully addressing your symptoms. 
            A cannabis specialist could help identify a more effective approach.
            """)

        if user_in_gap:
            st.error("""
            ⚠️ **You Are in the Care Gap**
            You felt you needed help but haven't received it. You are not alone.

            Resources:
            - Talk to a cannabis-informed physician
            - Network of Applied Pharmacognosy (NAP): appliedpharmacognosy.org
            - Association of Cannabinoid Specialists: cannabinoidspecialists.com
            """)

        entourage_modes = ["Smoking (flower)", "Vaping", "Oils/Tinctures"]
        user_uses_entourage = any(m in entourage_modes for m in user_mode)
        if user_cecd_score >= 3 and not user_uses_entourage:
            st.info("""
            💡 **Entourage Effect Consideration**
            Users with your symptom profile tend to use whole-plant methods. 
            Consider discussing full-spectrum formulations with a healthcare provider.
            """)

        if is_long_term and dose_escalating:
            st.caption("""
            📅 You've been using cannabis for 5+ years with increasing doses. 
            Consider tracking your symptoms over time to share with a clinician.
            """)

        st.success("✅ Your results have been saved to your Progress Tracker below!")

# ── Progress Tracker ─────────────────────────────────────────
if st.session_state.tracking_history:
    st.markdown("---")
    st.subheader("📈 Your Progress Over Time")

    history_df = pd.DataFrame(st.session_state.tracking_history)

    col1, col2 = st.columns(2)
    with col1:
        fig_track = px.line(history_df, x='date', y='cecd_score',
                           title='Your ECS Symptom Score Over Time',
                           markers=True,
                           color_discrete_sequence=['#2d6a4f'])
        fig_track.update_layout(plot_bgcolor='white',
                                yaxis_range=[0, 10],
                                yaxis_title='ECS Symptom Score',
                                xaxis_title='Date')
        st.plotly_chart(fig_track, use_container_width=True)

    with col2:
        st.markdown("**Your Screening History**")
        st.dataframe(history_df[['date', 'cecd_score', 'cecd_tier', 'in_care_gap']], 
                     use_container_width=True)

    if len(history_df) > 1:
        first = history_df.iloc[0]['cecd_score']
        last = history_df.iloc[-1]['cecd_score']
        if last < first:
            st.success(f"📉 Your symptom score decreased from {first} to {last}. Progress!")
        elif last > first:
            st.warning(f"📈 Your symptom score increased from {first} to {last}. Consider speaking with a provider.")
        else:
            st.info(f"➡️ Your symptom score has remained stable at {last}.")

    if st.button("🗑️ Clear Tracking History"):
        st.session_state.tracking_history = []
        st.rerun()

st.markdown("---")
st.caption("""
⚠️ This tool is for educational and research purposes only. It is not a clinical diagnostic tool.  
CECD is a working hypothesis and is not a clinically established diagnosis.  
This does not constitute medical advice.
""")
st.caption("""
📄 Framework based on:  
Russo, E.B. (2004). Clinical Endocannabinoid Deficiency (CECD). Neuroendocrinology Letters.  
Russo, E.B. (2011). Taming THC. British Journal of Pharmacology.  
Hasib, S. (2026). Chasing the High. OSF Preprints. https://doi.org/10.31235/osf.io/znrhe_v1
""")
st.markdown("**Data source:** Statistics Canada, 2024 Canadian Cannabis Survey PUMF | "
            "**GitHub:** github.com/sunehera")
