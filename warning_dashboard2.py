#!/usr/bin/env python
# coding: utf-8

# In[ ]:


import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import uuid

def get_supabase_client():
    try:
        from supabase import create_client
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["key"]
        return create_client(url, key)
    except Exception:
        return None
 
def user_login_cud():
    if 'user_id' in st.session_state and st.session_state.user_id:
        return st.session_state.user_id
    st.markdown('---')
    st.subheader('👤 Track Your CHS Symptoms Over Time')
    st.markdown('Enter your name or email to save your results and track patterns across sessions.')
    col1, col2 = st.columns([3, 1])
    with col1:
        identifier = st.text_input(
            "Your name or email",
            placeholder="e.g. jane@email.com or Jane",
            key="cud_login_input"
        )
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        login_btn = st.button("Continue →", type="primary", key="cud_login_btn")
    st.caption("🔒 Used only to link your screening history. No passwords required.")
    if login_btn and identifier.strip():
        st.session_state.user_id = identifier.strip().lower()
        st.rerun()
    elif login_btn:
        st.error("Please enter a name or email.")
    st.stop()
    return None
 
def save_chs_to_supabase(client, user_id, entry):
    try:
        client.table('chs_screening').insert({
            'user_id': user_id,
            'chs_risk': entry['chs_risk'],
            'chs_score': entry['chs_score'],
            'frequency_score': entry['frequency_score'],
            'nausea_score': entry['nausea_score'],
            'shower_relief': entry['shower_relief'],
            'duration_years': entry['duration_years'],
        }).execute()
        return True
    except Exception:
        return False
 
def load_chs_from_supabase(client, user_id):
    try:
        response = client.table('chs_screening')\
            .select('*')\
            .eq('user_id', user_id)\
            .order('date')\
            .execute()
        if response.data:
            df = pd.DataFrame(response.data)
            df['date'] = pd.to_datetime(df['date']).dt.strftime("%Y-%m-%d %H:%M")
            return df.to_dict('records')
        return []
    except Exception:
        return []
 

# ── Page config ──────────────────────────────────────────────
st.set_page_config(page_title="Cannabis Public Health Dashboard",
                   layout="wide", page_icon="🌿")

st.title("🌿 Cannabis Public Health Dashboard")
st.markdown("**Based on the 2024 Canadian Cannabis Survey (n=11,666)**")
st.markdown("*Hasib, S. (2026). Chasing the High. OSF Preprints. https://doi.org/10.31235/osf.io/znrhe_v1*")
st.markdown("---")

# ── Load data ────────────────────────────────────────────────
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
saw_warnings   = cannabis_users[cannabis_users['warn_see'].isin([1,2,3])].copy()

# ── Sidebar filters ──────────────────────────────────────────
st.sidebar.header("🔍 Filter Data")

age_labels = {1:"16-19", 2:"20-24", 3:"25-34", 4:"35-44", 5:"45-54", 6:"55+"}
sex_labels  = {1:"Male", 2:"Female"}
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

# Apply filters
filtered = saw_warnings.copy()
if age_options:
    filtered = filtered[filtered['age6'].isin(age_options)]
if sex_options:
    filtered = filtered[filtered['sex'].isin(sex_options)]
if purpose_options:
    filtered = filtered[filtered['canpurpose_dv'].isin(purpose_options)]

st.sidebar.markdown("---")
st.sidebar.metric("Filtered sample", f"{len(filtered):,}")
st.sidebar.metric("Recalled warning", 
    f"{int((filtered['warn_recall_thcmh']==1).sum()):,}")

supabase = get_supabase_client()
user_id = user_login_cud()
 
if 'chs_history' not in st.session_state or len(st.session_state.chs_history) == 0:
    if supabase and user_id:
        st.session_state.chs_history = load_chs_from_supabase(supabase, user_id)
    else:
        st.session_state.chs_history = []
 
st.sidebar.markdown("---")
if user_id:
    st.sidebar.markdown(f"**Logged in as:** `{user_id}`")
    if st.sidebar.button("🔄 Switch User"):
        del st.session_state["user_id"]
        st.session_state.chs_history = []
        st.rerun()

# ── SECTION 1: Warning Label Paradox ─────────────────────────
st.header("⚠️ The Warning Label Paradox")
st.markdown("Among cannabis users who saw warning messages — does recalling the THC mental health warning reduce daily use?")

col1, col2, col3 = st.columns(3)

recalled   = filtered[filtered['warn_recall_thcmh']==1.0]
notrecalled = filtered[filtered['warn_recall_thcmh']==0.0]

daily_recalled    = recalled['daily_dv'].mean()*100 if len(recalled)>0 else 0
daily_notrecalled = notrecalled['daily_dv'].mean()*100 if len(notrecalled)>0 else 0
diff = daily_recalled - daily_notrecalled

col1.metric("Daily use — recalled warning",    f"{daily_recalled:.1f}%")
col2.metric("Daily use — did not recall",       f"{daily_notrecalled:.1f}%")
col3.metric("Difference",                       f"+{diff:.1f}%", delta_color="inverse")

warn_data = pd.DataFrame({
    'Warning Recall': ['Did not recall warning', 'Recalled THC mental health warning'],
    'Daily Use %':    [daily_notrecalled, daily_recalled]
})
fig1 = px.bar(warn_data, x='Warning Recall', y='Daily Use %',
              color='Warning Recall',
              color_discrete_map={
                  'Did not recall warning': '#2196F3',
                  'Recalled THC mental health warning': '#F44336'},
              text='Daily Use %',
              title='Non-Medical Daily Use Rate by Warning Label Recall')
fig1.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
fig1.update_layout(showlegend=False, yaxis_title="% Daily Users",
                   plot_bgcolor='white', yaxis_range=[0,40])
st.plotly_chart(fig1, use_container_width=True)

st.markdown("---")

# ── SECTION 2: Mental Health Impact ──────────────────────────
st.header("🧠 Mental Health Impact")
st.markdown("How does cannabis use affect self-reported mental health — and does it differ by warning recall?")

impact_labels = {1:'Very beneficial', 2:'Somewhat beneficial',
                 3:'No effect', 4:'Somewhat harmful', 5:'Very harmful'}

col1, col2 = st.columns(2)

with col1:
    recalled_impact = recalled['impact_mental'].dropna()
    impact_counts_r = recalled_impact.value_counts(normalize=True)*100
    impact_df_r = pd.DataFrame({
        'Impact': [impact_labels.get(i, str(i)) for i in impact_counts_r.index],
        'Percentage': impact_counts_r.values
    })
    fig2a = px.pie(impact_df_r, values='Percentage', names='Impact',
                   title='Mental Health Impact — Recalled Warning',
                   color_discrete_sequence=px.colors.sequential.RdBu)
    st.plotly_chart(fig2a, use_container_width=True)

with col2:
    notrecalled_impact = notrecalled['impact_mental'].dropna()
    impact_counts_n = notrecalled_impact.value_counts(normalize=True)*100
    impact_df_n = pd.DataFrame({
        'Impact': [impact_labels.get(i, str(i)) for i in impact_counts_n.index],
        'Percentage': impact_counts_n.values
    })
    fig2b = px.pie(impact_df_n, values='Percentage', names='Impact',
                   title='Mental Health Impact — Did Not Recall Warning',
                   color_discrete_sequence=px.colors.sequential.RdBu)
    st.plotly_chart(fig2b, use_container_width=True)

harm_recalled    = recalled['impact_mental'].isin([4,5]).mean()*100
harm_notrecalled = notrecalled['impact_mental'].isin([4,5]).mean()*100
st.info(f"**{harm_recalled:.1f}%** of warning recallers report harmful mental health impact vs **{harm_notrecalled:.1f}%** of non-recallers (p<0.001)")

st.markdown("---")

# ── SECTION 3: Pharmaceutical Substitution ──────────────────
st.header("💊 Pharmaceutical Substitution")
st.markdown("Among medical and dual-purpose users — which prescription medications have they reduced since starting cannabis?")



#use full medical/dual users - not filtered
med_users_full = cannabis_users[cannabis_users['canpurpose_dv'].isin([2,3])].copy()

med_vars = {
    'pain_opi_dv':        'Opioids (oxy, morphine)',
    'pain_nonopi_dv':     'Non-opioid pain relievers',
    'anti_inflam_dv':     'Anti-inflammatories (Advil)',
    'sedative_dv':        'Sedatives (Xanax, Valium)',
    'anti_depress_dv':    'Antidepressants (Prozac)',
    'stimulant_dv':       'Stimulants (Adderall, Ritalin)',
    'anti_convuls_dv':    'Anti-convulsants',
    'med_reduc_sleep_dv': 'Sleep medication'
}

med_counts = []
for var, label in med_vars.items():
    if var in med_users_full.columns:
        count = (med_users_full[var]==1).sum()
        pct = count/len(med_users_full)*100
        med_counts.append({
            'Medication': label,
            'Count': count,
            'Percentage': round(pct, 1)
        })


med_df = pd.DataFrame(med_counts).sort_values('Percentage', ascending=True)


fig3 = px.bar(med_df, x='Percentage', y='Medication', 
              orientation='h',
              title='% of Medical/Dual Users Who Reduced Each Medication Since Starting Cannabis (n=1,170)',
              color='Percentage', 
              color_continuous_scale='Greens',
              text='Percentage')

fig3.update_traces(texttemplate='%{text:.1f}%', textposition='outside')

fig3.update_layout(plot_bgcolor='orange', 
                   coloraxis_showscale=False,
                   xaxis_title='% of Medical/Dual Users',
                   xaxis_range=[0, 35])

st.plotly_chart(fig3, use_container_width=True)


st.metric("Reduced ANY medication since starting cannabis", 
          "45.0%", 
          help="526 of 1,170 medical/dual purpose users")

# ── SECTION 4: Demographics ───────────────────────────────────
st.header("👥 Demographics")

col1, col2 = st.columns(2)

with col1:
    age_dist = filtered['age6'].value_counts().reset_index()
    age_dist.columns = ['Age Group', 'Count']
    age_dist['Age Group'] = age_dist['Age Group'].map(age_labels)
    age_dist = age_dist.sort_values('Age Group')
    fig4a = px.bar(age_dist, x='Age Group', y='Count',
                   title='Age Distribution of Cannabis Users Who Saw Warnings',
                   color='Count', color_continuous_scale='Blues')
    fig4a.update_layout(plot_bgcolor='white', coloraxis_showscale=False)
    st.plotly_chart(fig4a, use_container_width=True)

with col2:
    daily_by_age = []
    for age_code, age_label in age_labels.items():
        age_group = filtered[filtered['age6']==age_code]
        if len(age_group) > 10:
            daily_rate = age_group['daily_dv'].mean()*100
            daily_by_age.append({'Age Group': age_label, 'Daily Use %': daily_rate})
    age_daily_df = pd.DataFrame(daily_by_age)
    fig4b = px.bar(age_daily_df, x='Age Group', y='Daily Use %',
                   title='Daily Non-Medical Use Rate by Age Group',
                   color='Daily Use %', color_continuous_scale='Reds',
                   text='Daily Use %')
    fig4b.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
    fig4b.update_layout(plot_bgcolor='white', coloraxis_showscale=False,
                        yaxis_range=[0,40])
    st.plotly_chart(fig4b, use_container_width=True)

st.markdown("---")

# ── SECTION 5: Workplace Use ──────────────────────────────────
st.header("💼 Workplace Cannabis Use")
st.markdown("Among daily users who recalled the warning — how many use cannabis at or before work?")

smoking_gun = filtered[
    (filtered['warn_recall_thcmh']==1.0) &
    (filtered['daily_dv']==1.0)
].copy()

col1, col2, col3 = st.columns(3)
col1.metric("Recalled warning + daily users", f"{len(smoking_gun):,}")
col2.metric("Use at/before work",
    f"{smoking_gun['work_use_binary'].mean()*100:.1f}%")
col3.metric("Report harmful mental health impact",
    f"{smoking_gun['impact_mental'].isin([4,5]).mean()*100:.1f}%")

work_impact = smoking_gun['impact_mental'].dropna().value_counts(normalize=True)*100
work_df = pd.DataFrame({
    'Impact': [impact_labels.get(i, str(i)) for i in work_impact.index],
    'Percentage': work_impact.values
})
fig5 = px.bar(work_df, x='Impact', y='Percentage',
              title='Mental Health Impact Among High-Risk Group\n(Recalled Warning + Daily Users)',
              color='Percentage', color_continuous_scale='RdYlGn_r',
              text='Percentage')
fig5.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
fig5.update_layout(plot_bgcolor='white', coloraxis_showscale=False)
st.plotly_chart(fig5, use_container_width=True)

st.markdown("---")

st.markdown("---")

# ── SECTION 6: CUD Profile & Treatment Gap ───────────────────

st.header("Cannabis Use Disorder Profile & Treatment Gap")
st.markdown("Identifying likely Cannabis Use Disorder candidates — daily users who report harmful mental health impact — and examining their help-seeking patterns.")

# Define CUD profile
likely_cud = filtered[
    (filtered['daily_dv'] == 1.0) &
    (filtered['impact_mental'].isin([4.0, 5.0]))
].copy()

non_cud = filtered[~filtered.index.isin(likely_cud.index)]

col1, col2, col3 = st.columns(3)
col1.metric("Likely CUD profile", f"{len(likely_cud):,}",
            help="Daily users reporting harmful mental health impact")
col2.metric("% of cannabis users",
            f"{len(likely_cud)/len(filtered)*100:.1f}%")
col3.metric("Treatment gap",
            f"{len(likely_cud[likely_cud['help_need'].isin([2,3])]) - len(likely_cud[likely_cud['help_receive'].isin([2,3])]):,} people",
            help="Needed help but didn't receive it")

st.markdown("---")

# Help seeking comparison

col1, col2 = st.columns(2)
with col1:
    needed_pct = len(likely_cud[likely_cud['help_need'].isin([2,3])])/len(likely_cud)*100
    received_pct = len(likely_cud[likely_cud['help_receive'].isin([2,3])])/len(likely_cud)*100

    gap_data = pd.DataFrame({
        'Status': ['Felt they needed help', 'Actually received help'],
        'Percentage': [needed_pct, received_pct]
    })
    fig6a = px.bar(gap_data, x='Status', y='Percentage',
                   title='Treatment Gap Among Likely CUD Profile',
                   color='Status',
                   color_discrete_map={
                       'Felt they needed help': '#FF9800',
                       'Actually received help': '#4CAF50'},
                   text='Percentage')
    fig6a.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
    fig6a.update_layout(showlegend=False, plot_bgcolor='white',
                        yaxis_range=[0, 75], yaxis_title='%')
    st.plotly_chart(fig6a, use_container_width=True)

with col2:
    cud_needed = len(likely_cud[likely_cud['help_need'].isin([2,3])])/len(likely_cud)*100
    noncud_needed = len(non_cud[non_cud['help_need'].isin([2,3])])/len(non_cud)*100

    compare_data = pd.DataFrame({
        'Group': ['Likely CUD Profile', 'Other Cannabis Users'],
        'Felt They Needed Help %': [cud_needed, noncud_needed]
    })
    fig6b = px.bar(compare_data, x='Group', y='Felt They Needed Help %',
                   title='Help-Seeking Need: CUD Profile vs Other Users',
                   color='Group',
                   color_discrete_map={
                       'Likely CUD Profile': '#F44336',
                       'Other Cannabis Users': '#2196F3'},
                   text='Felt They Needed Help %')
    fig6b.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
    fig6b.update_layout(showlegend=False, plot_bgcolor='white',
                        yaxis_range=[0, 70], yaxis_title='%')
    st.plotly_chart(fig6b, use_container_width=True)

# Age breakdown of CUD profile
st.subheader("Age Profile of Likely CUD Candidates")
age_cud = likely_cud['age6'].value_counts().reset_index()
age_cud.columns = ['Age Code', 'Count']
age_cud['Age Group'] = age_cud['Age Code'].map(age_labels)
age_cud = age_cud.sort_values('Age Code')

fig6c = px.bar(age_cud, x='Age Group', y='Count',
               title='Age Distribution — Likely CUD Profile',
               color='Count', color_continuous_scale='Oranges',
               text='Count')
fig6c.update_traces(textposition='outside')
fig6c.update_layout(plot_bgcolor='white', coloraxis_showscale=False)
st.plotly_chart(fig6c, use_container_width=True)

st.warning(
    "⚠️ **Note:** This is a behavioral proxy profile, not a clinical diagnosis. "
    "Likely CUD is defined as daily non-medical cannabis use combined with "
    "self-reported harmful mental health impact. Clinical diagnosis requires "
    "formal assessment."
)

st.info(
    f"**Key finding:** {needed_pct:.1f}% of likely CUD candidates felt they "
    f"needed professional help — but only {received_pct:.1f}% received it. "
    f"This treatment gap represents people who are motivated to change "
    f"but not accessing conventional care — a critical recruitment "
    f"population for psilocybin-assisted therapy research."
)


st.markdown("**Data source:** Statistics Canada, 2024 Canadian Cannabis Survey PUMF | "
            "**Research:** Hasib (2026), OSF Preprints | "
            "**GitHub:** github.com/sunehera/cannabis-health-outcomes-analysis")


st.markdown("---")

# ── SECTION 7: Cannabis Use Pre-Screening Tool ───────────────
st.header("🧪 Cannabis Use Self-Assessment Tool")
st.markdown("*Based on patterns from 11,666 Canadians in the 2024 Canadian Cannabis Survey*")
st.markdown("Answer a few questions to see how your cannabis use pattern compares to national data.")

col1, col2 = st.columns(2)

with col1:
    use_frequency = st.selectbox(
        "How often do you use cannabis?",
        options=[1, 2, 3, 4, 5, 6, 7],
        format_func=lambda x: {
            1: "Less than once a month",
            2: "Once a month",
            3: "2-3 times a month",
            4: "Once a week",
            5: "2-3 times a week",
            6: "4-6 times a week",
            7: "Daily or almost daily"
        }[x]
    )

    use_purpose = st.selectbox(
        "Why do you primarily use cannabis?",
        options=[1, 2, 3],
        format_func=lambda x: {
            1: "Recreation only",
            2: "Both medical and recreational",
            3: "Medical only"
        }[x]
    )

    mental_impact = st.selectbox(
        "How has cannabis affected your mental health?",
        options=[1, 2, 3, 4, 5],
        format_func=lambda x: {
            1: "Very beneficial",
            2: "Somewhat beneficial",
            3: "No effect",
            4: "Somewhat harmful",
            5: "Very harmful"
        }[x]
    )

with col2:
    recalled_warning = st.selectbox(
        "Have you seen this warning: 'Frequent cannabis use can contribute to mental health problems'?",
        options=[0, 1],
        format_func=lambda x: {
            0: "No / Not sure",
            1: "Yes, I recall seeing it"
        }[x]
    )

    sought_help = st.selectbox(
        "Have you ever felt you needed professional help for your cannabis use?",
        options=[1, 2, 3],
        format_func=lambda x: {
            1: "No, never",
            2: "Yes, in the past 12 months",
            3: "Yes, but not recently"
        }[x]
    )

    reduced_meds = st.multiselect(
        "Have you reduced any of these since starting cannabis?",
        options=["Opioids", "Antidepressants", "Sedatives (Xanax/Valium)",
                 "Stimulants (Adderall/Ritalin)", "Sleep medication",
                 "Anti-inflammatories", "None of the above"]
    )

st.markdown("---")

if st.button("🔍 See My Profile", type="primary"):
    recalled = saw_warnings[saw_warnings['warn_recall_thcmh']==1.0]
    notrecalled = saw_warnings[saw_warnings['warn_recall_thcmh']==0.0]

    # Determine daily use
    is_daily = use_frequency == 7
    is_harmful = mental_impact in [4, 5]
    is_beneficial = mental_impact in [1, 2]
    is_medical = use_purpose in [2, 3]
    needs_help = sought_help in [2, 3]
    recalled = recalled_warning == 1
    reduced_any = "None of the above" not in reduced_meds and len(reduced_meds) > 0

    st.subheader("📊 Your Cannabis Use Profile")

    # Profile cards
    col1, col2, col3 = st.columns(3)

    # Similar users in dataset
    similar = cannabis_users.copy()
    if is_daily:
        similar = similar[similar['daily_dv'] == 1.0]
    if is_medical:
        similar = similar[similar['canpurpose_dv'].isin([2, 3])]

    col1.metric("Similar users in national data", f"{len(similar):,}")
    col2.metric("Who report beneficial mental health impact",
                f"{similar['impact_mental'].isin([1,2]).mean()*100:.1f}%")
    col3.metric("Who report harmful mental health impact",
                f"{similar['impact_mental'].isin([4,5]).mean()*100:.1f}%")

    st.markdown("---")

    # Warning label paradox
    # Warning label paradox
    if recalled_warning and is_daily:
        st.error(
            "⚠️ **Warning Label Paradox Detected**\n\n"
            "You recalled the THC mental health warning and use cannabis daily. "
            "In our national sample, **29.1%** of people who recalled this warning "
            "use daily — compared to **21.9%** who did not recall it. "
            "The warning is reaching you. This pattern suggests the label alone "
            "may not be sufficient to support behavior change."
        )

    # Treatment gap
    if needs_help and is_harmful:
        st.warning(
            "🏥 **Treatment Gap Profile**\n\n"
            "You've felt you need help and report harmful mental health impact. "
            "In our national data, 54% of people with this profile felt they needed "
            "professional help — but only 27% received it. "
            "You may be a good candidate for supervised cannabis use research "
            "or clinical support programs."
        )

    # Pharmaceutical substitution
    if reduced_any and is_medical:
        st.info(
            f"💊 **Medication Reduction Profile**\n\n"
            f"You've reduced: {', '.join(reduced_meds)}. "
            "45% of medical/dual-purpose cannabis users in our national sample "
            "have reduced at least one prescription medication. "
            "This pattern highlights the importance of medical supervision "
            "when substituting cannabis for prescription drugs."
        )

    # Beneficial profile
    if is_beneficial and not is_harmful:
        st.success(
            "✅ **Beneficial Use Profile**\n\n"
            "Your cannabis use appears to be positively impacting your mental health. "
            f"In our national sample, {similar['impact_mental'].isin([1,2]).mean()*100:.1f}% "
            "of users with a similar profile report beneficial mental health outcomes."
        )

  st.markdown("---")
st.header("🌡️ CHS Digital Phenotype — Cannabinoid Hyperemesis Syndrome Screener")
st.markdown("""
**Cannabinoid Hyperemesis Syndrome (CHS)** is a condition of cyclic nausea, vomiting, 
and abdominal pain in long-term, heavy cannabis users — relieved by hot showers or baths.
 
It is frequently misdiagnosed as cyclic vomiting syndrome or functional GI disorder.
This screener helps identify behavioral and symptom patterns consistent with CHS.
 
*Educational only. Not a clinical diagnosis. If you experience severe cyclic vomiting, seek medical care.*
""")
 
st.info("""
**Why this matters:** CHS is underdiagnosed and often missed because neither patients 
nor clinicians connect symptoms to cannabis use. Early pattern recognition saves 
unnecessary hospitalizations and suffering.
""")
 
st.subheader("Step 1 — Cannabis Use Patterns")
 
col1, col2 = st.columns(2)
with col1:
    chs_frequency = st.selectbox(
        "How often do you currently use cannabis?",
        options=[None, 1, 2, 3, 4, 5],
        format_func=lambda x: "Select an option" if x is None else {
            1: "Daily or almost daily",
            2: "4-6 times a week",
            3: "2-3 times a week",
            4: "Once a week or less",
            5: "Rarely"
        }[x],
        key="chs_freq"
    )
 
    chs_duration = st.selectbox(
        "How long have you been using cannabis regularly?",
        options=[None, 1, 2, 3, 4],
        format_func=lambda x: "Select an option" if x is None else {
            1: "Less than 1 year",
            2: "1-3 years",
            3: "3-5 years",
            4: "5+ years"
        }[x],
        key="chs_dur"
    )
 
    chs_amount = st.selectbox(
        "How much cannabis do you typically use per session?",
        options=[None, 1, 2, 3],
        format_func=lambda x: "Select an option" if x is None else {
            1: "Large amount (heavy use)",
            2: "Moderate amount",
            3: "Small amount"
        }[x],
        key="chs_amount"
    )
 
with col2:
    chs_method = st.multiselect(
        "How do you consume cannabis?",
        options=["Smoking (flower)", "Vaping", "Concentrates/Dabs",
                 "Edibles", "Oils/Tinctures", "Other"],
        key="chs_method"
    )
 
    chs_tolerance = st.selectbox(
        "Has your tolerance increased significantly over time?",
        options=[None, 1, 2],
        format_func=lambda x: "Select an option" if x is None else {
            1: "Yes, I need much more to feel effects",
            2: "No, tolerance has stayed similar"
        }[x],
        key="chs_tol"
    )
 
st.subheader("Step 2 — Symptom Patterns")
 
col1, col2 = st.columns(2)
with col1:
    chs_nausea = st.selectbox(
        "Do you experience episodes of nausea or vomiting?",
        options=[None, 1, 2, 3, 4],
        format_func=lambda x: "Select an option" if x is None else {
            1: "Yes, severe cyclic episodes (recurring pattern)",
            2: "Yes, occasional nausea",
            3: "Mild nausea sometimes",
            4: "No nausea or vomiting"
        }[x],
        key="chs_nausea"
    )
 
    chs_abdominal = st.selectbox(
        "Do you experience abdominal pain or cramping?",
        options=[None, 1, 2, 3],
        format_func=lambda x: "Select an option" if x is None else {
            1: "Yes, severe and recurring",
            2: "Yes, occasional",
            3: "No"
        }[x],
        key="chs_abdom"
    )
 
    chs_timing = st.selectbox(
        "When do symptoms typically occur?",
        options=[None, 1, 2, 3, 4],
        format_func=lambda x: "Select an option" if x is None else {
            1: "Early morning / upon waking",
            2: "Throughout the day",
            3: "After using cannabis",
            4: "No pattern / no symptoms"
        }[x],
        key="chs_timing"
    )
 
with col2:
    chs_shower = st.selectbox(
        "Does a hot shower or bath relieve your nausea or abdominal pain?",
        options=[None, 1, 2, 3],
        format_func=lambda x: "Select an option" if x is None else {
            1: "Yes, significantly — I compulsively take hot showers for relief",
            2: "Yes, somewhat",
            3: "No / I haven't tried"
        }[x],
        key="chs_shower"
    )
 
    chs_hospital = st.selectbox(
        "Have you visited an ER or been hospitalized for nausea/vomiting?",
        options=[None, 1, 2, 3],
        format_func=lambda x: "Select an option" if x is None else {
            1: "Yes, multiple times",
            2: "Yes, once",
            3: "No"
        }[x],
        key="chs_hosp"
    )
 
    chs_cessation = st.selectbox(
        "Have your symptoms improved during periods when you stopped using cannabis?",
        options=[None, 1, 2, 3],
        format_func=lambda x: "Select an option" if x is None else {
            1: "Yes, symptoms resolved when I stopped",
            2: "Yes, symptoms improved somewhat",
            3: "No difference / haven't stopped",
        }[x],
        key="chs_cess"
    )
 
st.subheader("Step 3 — Diagnostic History")
 
col1, col2 = st.columns(2)
with col1:
    chs_diagnosis = st.multiselect(
        "Have you ever been diagnosed with any of these?",
        options=[
            "Cyclic Vomiting Syndrome (CVS)",
            "Functional GI Disorder",
            "IBS",
            "Gastroparesis",
            "None of the above"
        ],
        key="chs_diag"
    )
 
with col2:
    chs_told_doctor = st.selectbox(
        "Have you told your doctor about your cannabis use when reporting these symptoms?",
        options=[None, 1, 2, 3],
        format_func=lambda x: "Select an option" if x is None else {
            1: "No — I haven't mentioned it",
            2: "Yes, but they didn't connect it",
            3: "Yes, and CHS was discussed"
        }[x],
        key="chs_doctor"
    )
 
if st.button("🔍 Calculate My CHS Risk Profile", type="primary", key="chs_calc"):
 
    required_chs = [chs_frequency, chs_duration, chs_amount,
                    chs_tolerance, chs_nausea, chs_abdominal,
                    chs_shower, chs_hospital, chs_cessation, chs_told_doctor]
 
    if any(v is None for v in required_chs):
        st.error("⚠️ Please answer all questions before calculating your CHS profile.")
    else:
        # CHS Risk Scoring
        chs_score = 0
 
        # Frequency scoring
        freq_score = {1: 3, 2: 2, 3: 1, 4: 0, 5: 0}.get(chs_frequency, 0)
        chs_score += freq_score
 
        # Duration scoring
        dur_score = {1: 0, 2: 1, 3: 2, 4: 3}.get(chs_duration, 0)
        chs_score += dur_score
 
        # Nausea scoring — the strongest signal
        nausea_score = {1: 4, 2: 2, 3: 1, 4: 0}.get(chs_nausea, 0)
        chs_score += nausea_score
 
        # Hot shower relief — the pathognomonic CHS sign
        shower_score = {1: 4, 2: 2, 3: 0}.get(chs_shower, 0)
        chs_score += shower_score
 
        # Cessation relief
        cess_score = {1: 3, 2: 1, 3: 0}.get(chs_cessation, 0)
        chs_score += cess_score
 
        # Hospitalization
        hosp_score = {1: 2, 2: 1, 3: 0}.get(chs_hospital, 0)
        chs_score += hosp_score
 
        # Abdominal pain
        abdom_score = {1: 2, 2: 1, 3: 0}.get(chs_abdominal, 0)
        chs_score += abdom_score
 
        # Tolerance
        tol_score = {1: 1, 2: 0}.get(chs_tolerance, 0)
        chs_score += tol_score
 
        # Risk tier
        if chs_score >= 14:
            chs_risk = "High CHS Risk"
            chs_color = "error"
        elif chs_score >= 8:
            chs_risk = "Moderate CHS Risk"
            chs_color = "warning"
        else:
            chs_risk = "Low CHS Risk"
            chs_color = "success"
 
        st.markdown("---")
        st.subheader("🌡️ Your CHS Risk Profile")
 
        col1, col2, col3 = st.columns(3)
        col1.metric("CHS Risk Score", f"{chs_score} / 22")
        col2.metric("Risk Tier", chs_risk)
        col3.metric("Hot Shower Relief", 
                    "⚠️ Key signal" if chs_shower == 1 else 
                    "Possible signal" if chs_shower == 2 else "Not present")
 
        # Save to tracking
        new_chs_entry = {
            'date': datetime.now().strftime("%Y-%m-%d %H:%M"),
            'chs_risk': chs_risk,
            'chs_score': chs_score,
            'frequency_score': freq_score,
            'nausea_score': nausea_score,
            'shower_relief': chs_shower,
            'duration_years': chs_duration,
        }
        st.session_state.chs_history.append(new_chs_entry)
 
        if supabase:
            save_chs_to_supabase(supabase, user_id, new_chs_entry)
            st.success("✅ Your CHS profile has been saved to your tracker!")
 
        # Results
        if chs_risk == "High CHS Risk":
            st.error(f"""
            🚨 **High CHS Risk — Score: {chs_score}/22**
 
            Your symptom pattern is strongly consistent with Cannabinoid Hyperemesis Syndrome.
 
            **Key signals detected:**
            {"- ✅ Cyclic nausea/vomiting pattern" if chs_nausea == 1 else ""}
            {"- ✅ Hot shower relief — the defining CHS marker" if chs_shower == 1 else ""}
            {"- ✅ Symptom improvement with cannabis cessation" if chs_cessation == 1 else ""}
            {"- ✅ Long-term heavy daily use" if chs_frequency == 1 and chs_duration == 4 else ""}
 
            **What to do:**
            Please speak with a healthcare provider and mention your cannabis use history.
            CHS is treatable — the primary treatment is cannabis cessation.
            If you are experiencing severe vomiting, please seek emergency care.
            """)
 
        elif chs_risk == "Moderate CHS Risk":
            st.warning(f"""
            ⚠️ **Moderate CHS Risk — Score: {chs_score}/22**
 
            Some patterns in your responses are consistent with CHS.
            Monitor your symptoms and consider discussing with a healthcare provider,
            particularly if symptoms are recurring or worsening.
            """)
 
        else:
            st.success(f"""
            ✅ **Low CHS Risk — Score: {chs_score}/22**
 
            Your current pattern does not strongly suggest CHS.
            Continue monitoring if you develop new nausea or vomiting patterns.
            """)
 
        # Doctor communication
        if chs_told_doctor == 1 and chs_risk in ["High CHS Risk", "Moderate CHS Risk"]:
            st.warning("""
            💬 **Important:** You haven't told your doctor about your cannabis use.
            CHS is frequently misdiagnosed as cyclic vomiting syndrome or IBS when
            cannabis use isn't disclosed. Your doctor needs this information to help you.
            """)
 
        # Misdiagnosis flag
        misdiagnosed = [d for d in chs_diagnosis if d != "None of the above"]
        if misdiagnosed and chs_risk in ["High CHS Risk", "Moderate CHS Risk"]:
            st.info(f"""
            🔍 **Possible Misdiagnosis Flag**
            You've been diagnosed with: {', '.join(misdiagnosed)}.
            These conditions share symptoms with CHS and CHS is frequently
            misdiagnosed as one of these. Please discuss CHS specifically with your provider.
            """)
 
# ── CHS Progress Tracker ─────────────────────────────────────
if st.session_state.get('chs_history'):
    st.markdown("---")
    st.subheader("📈 Your CHS Risk Over Time")
 
    chs_hist_df = pd.DataFrame(st.session_state.chs_history)
 
    col1, col2 = st.columns(2)
    with col1:
        fig_chs = px.line(
            chs_hist_df, x='date', y='chs_score',
            title='Your CHS Risk Score Over Time',
            markers=True,
            color_discrete_sequence=['#e63946']
        )
        fig_chs.update_layout(
            plot_bgcolor='white',
            yaxis_range=[0, 22],
            yaxis_title='CHS Risk Score',
            xaxis_title='Date'
        )
        st.plotly_chart(fig_chs, use_container_width=True)
 
    with col2:
        st.markdown("**Your CHS Screening History**")
        st.dataframe(
            chs_hist_df[['date', 'chs_score', 'chs_risk']],
            use_container_width=True
        )
 
    if len(chs_hist_df) > 1:
        first = chs_hist_df.iloc[0]['chs_score']
        last = chs_hist_df.iloc[-1]['chs_score']
        if last < first:
            st.success(f"📉 Your CHS risk score decreased from {first} to {last}.")
        elif last > first:
            st.warning(f"📈 Your CHS risk score increased from {first} to {last}. Consider speaking with a provider.")
 
    if st.button("🗑️ Clear CHS History", key="clear_chs"):
        st.session_state.chs_history = []
        st.rerun()
 
st.caption("""
⚠️ This CHS screener is for educational purposes only and does not constitute medical advice.
CHS diagnosis requires clinical assessment. If you are experiencing severe symptoms, seek medical care immediately.
""")
    st.markdown("---")
    
    st.caption(
        "⚠️ This tool is for educational and research purposes only. "
        "It is not a clinical diagnostic tool. Results are based on population-level "
        "patterns from the 2024 Canadian Cannabis Survey and do not constitute "
        "medical advice. If you are concerned about your cannabis use, "
        "please speak with a healthcare professional."
    )
    st.caption(
        "📄 Based on: Hasib, S. (2026). Chasing the High. OSF Preprints. "
        "https://doi.org/10.31235/osf.io/znrhe_v1"
    )
