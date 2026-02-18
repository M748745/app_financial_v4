# ============================================================
# EXALIO - Financial & Revenue Intelligence Platform
# Version 3.0 | Built on app_cloudflare_v2.py
# Focus: Business value of Financial & Revenue Experience
# ============================================================

# ── Selective import of the two v2 LLM helpers we actually need ──
# We avoid "from app_cloudflare_v2 import *" because that module
# has heavy optional dependencies (networkx, GPUtil, etc.) that may
# not be installed in every environment.
import json as _json, re as _re_mod

def _safe_import_v2():
    """Try to import query_ollama / extract_json_from_response from v2."""
    try:
        import sys as _sys, os as _os, types as _types
        _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
        # Stub out heavy/missing optional dependencies so v2 can be imported
        for _mod in ['networkx', 'GPUtil', 'streamlit_autorefresh',
                     'intelligent_schema_semantics']:
            if _mod not in _sys.modules:
                _sys.modules[_mod] = _types.ModuleType(_mod)
        import app_cloudflare_v2 as _v2
        return (getattr(_v2, 'query_ollama', None),
                getattr(_v2, 'extract_json_from_response', None))
    except Exception:
        return None, None

_v2_query_ollama, _v2_extract_json = _safe_import_v2()


def query_ollama(prompt: str, model: str, url: str, timeout: int = 120,
                 auto_optimize: bool = False, verify_connection: bool = False,
                 show_spinner: bool = False) -> str:
    """Lightweight Ollama caller — delegates to v2 when available."""
    if _v2_query_ollama:
        return _v2_query_ollama(prompt, model, url, timeout=timeout,
                                auto_optimize=auto_optimize,
                                verify_connection=verify_connection,
                                show_spinner=show_spinner)
    if not model or not url:
        return ""
    try:
        import requests as _req
        resp = _req.post(
            f"{url}/api/generate",
            json={"model": model, "prompt": prompt, "stream": False},
            timeout=timeout,
        )
        if resp.status_code == 200:
            return resp.json().get("response", "")
    except Exception:
        pass
    return ""


def extract_json_from_response(text: str):
    """Extract first JSON object or array from LLM response text."""
    if _v2_extract_json:
        return _v2_extract_json(text)
    if not text:
        return None
    try:
        return _json.loads(text.strip())
    except Exception:
        pass
    for pattern in [r'\{[\s\S]*\}', r'\[[\s\S]*\]']:
        m = _re_mod.search(pattern, text)
        if m:
            try:
                return _json.loads(m.group())
            except Exception:
                pass
    return None


import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import json
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
import re

# ──────────────────────────────────────────────────────────────
# PAGE CONFIG  (overrides the one in app_cloudflare_v2)
# ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Exalio | Financial & Revenue Intelligence",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ──────────────────────────────────────────────────────────────
# THEME  – deep navy / gold / green palette
# ──────────────────────────────────────────────────────────────
THEME_CSS = """
<style>
/* ── Global ── */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
    background: #080e1a;
    color: #e8edf5;
}

.stApp { background: linear-gradient(160deg, #080e1a 0%, #0d1829 40%, #091422 100%); }

/* ── Sidebar ── */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0d1829 0%, #091220 100%);
    border-right: 1px solid rgba(245,158,11,0.15);
}

/* ── Top Hero Banner ── */
.hero-banner {
    background: linear-gradient(135deg, #0f2444 0%, #1a3a5c 50%, #0f2444 100%);
    border: 1px solid rgba(245,158,11,0.3);
    border-radius: 16px;
    padding: 28px 36px;
    margin-bottom: 24px;
    position: relative;
    overflow: hidden;
}
.hero-banner::before {
    content: '';
    position: absolute; top: 0; left: 0; right: 0; bottom: 0;
    background: radial-gradient(ellipse at 80% 50%, rgba(245,158,11,0.08) 0%, transparent 70%);
}
.hero-title {
    font-size: 2rem; font-weight: 800;
    background: linear-gradient(90deg, #f59e0b, #fbbf24, #10b981);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    margin: 0 0 6px;
}
.hero-sub { color: #94a3b8; font-size: 1rem; margin: 0; }

/* ── Financial KPI Cards ── */
.fin-kpi-card {
    background: linear-gradient(145deg, #0f1f35 0%, #162840 100%);
    border: 1px solid rgba(245,158,11,0.2);
    border-radius: 14px;
    padding: 20px 22px;
    text-align: center;
    transition: transform 0.2s, border-color 0.2s;
}
.fin-kpi-card:hover { transform: translateY(-2px); border-color: rgba(245,158,11,0.5); }
.fin-kpi-label { font-size: 0.75rem; color: #cbd5e1; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 8px; }
.fin-kpi-value { font-size: 1.9rem; font-weight: 800; color: #f59e0b; line-height: 1.1; }
.fin-kpi-delta { font-size: 0.8rem; margin-top: 6px; }
.delta-up   { color: #10b981; }
.delta-down { color: #ef4444; }
.delta-flat { color: #94a3b8; }

/* ── Section Headers ── */
.section-header {
    display: flex; align-items: center; gap: 12px;
    padding: 12px 0; margin: 8px 0 16px;
    border-bottom: 2px solid rgba(245,158,11,0.2);
}
.section-icon { font-size: 1.5rem; }
.section-title { font-size: 1.15rem; font-weight: 700; color: #f1f5f9; }
.section-badge {
    background: rgba(245,158,11,0.15); color: #f59e0b;
    font-size: 0.7rem; font-weight: 600;
    padding: 3px 10px; border-radius: 20px; border: 1px solid rgba(245,158,11,0.3);
}

/* ── Advisory Cards ── */
.advisory-card {
    background: linear-gradient(145deg, #0d1f35 0%, #132840 100%);
    border-left: 4px solid #f59e0b;
    border-radius: 0 12px 12px 0;
    padding: 18px 20px;
    margin-bottom: 12px;
}
.advisory-card.green  { border-left-color: #10b981; }
.advisory-card.red    { border-left-color: #ef4444; }
.advisory-card.blue   { border-left-color: #3b82f6; }
.advisory-card.purple { border-left-color: #8b5cf6; }
.advisory-title { font-weight: 700; font-size: 0.95rem; color: #f1f5f9; margin-bottom: 4px; }
.advisory-body  { font-size: 0.85rem; color: #e2e8f0; line-height: 1.6; }
.advisory-action {
    display: inline-block; margin-top: 10px;
    background: rgba(245,158,11,0.1); color: #f59e0b;
    font-size: 0.75rem; font-weight: 600;
    padding: 4px 12px; border-radius: 20px;
    border: 1px solid rgba(245,158,11,0.25);
}

/* ── Revenue Gauge ── */
.gauge-container { text-align: center; padding: 12px 0; }
.gauge-label { font-size: 0.8rem; color: #cbd5e1; margin-top: 6px; }

/* ── Opportunity Pills ── */
.opp-pill {
    display: inline-block;
    background: rgba(16,185,129,0.12);
    border: 1px solid rgba(16,185,129,0.3);
    color: #10b981; font-size: 0.78rem; font-weight: 600;
    padding: 4px 12px; border-radius: 20px; margin: 3px 3px;
}
.risk-pill {
    display: inline-block;
    background: rgba(239,68,68,0.12);
    border: 1px solid rgba(239,68,68,0.3);
    color: #ef4444; font-size: 0.78rem; font-weight: 600;
    padding: 4px 12px; border-radius: 20px; margin: 3px 3px;
}

/* ── Progress / Health Bar ── */
.health-bar-wrap { background: #1e293b; border-radius: 6px; height: 8px; overflow: hidden; }
.health-bar-fill { height: 8px; border-radius: 6px;
    background: linear-gradient(90deg, #10b981, #34d399); }

/* ── Tabs ── */
button[data-baseweb="tab"] {
    font-weight: 600 !important;
    color: #cbd5e1 !important;
}
button[data-baseweb="tab"][aria-selected="true"] {
    color: #f59e0b !important;
    border-bottom: 2px solid #f59e0b !important;
}

/* ── Buttons ── */
.stButton > button {
    background: linear-gradient(135deg, #b45309, #d97706) !important;
    color: #fff !important; font-weight: 700 !important;
    border: none !important; border-radius: 10px !important;
    padding: 10px 22px !important;
    box-shadow: 0 4px 15px rgba(245,158,11,0.3) !important;
    transition: all 0.2s !important;
}
.stButton > button:hover {
    transform: translateY(-1px) !important;
    box-shadow: 0 6px 20px rgba(245,158,11,0.45) !important;
}

/* ── Metrics (st.metric) ── */
[data-testid="stMetricValue"] { color: #f59e0b !important; font-weight: 800 !important; }
[data-testid="stMetricDelta"] { font-weight: 600 !important; }

/* ── Expanders ── */
details { border: 1px solid rgba(245,158,11,0.15) !important;
           border-radius: 10px !important; background: #0d1829 !important; }
summary { color: #f1f5f9 !important; font-weight: 600 !important; }

/* ── Narrative / Story styles ── */
.story-chapter {
    background: linear-gradient(145deg, #0c1a2e 0%, #112035 100%);
    border: 1px solid rgba(245,158,11,0.15);
    border-radius: 14px;
    padding: 24px 28px;
    margin-bottom: 18px;
    position: relative;
}
.story-chapter-num {
    position: absolute; top: -12px; left: 24px;
    background: linear-gradient(135deg, #b45309, #f59e0b);
    color: #fff; font-size: 0.7rem; font-weight: 800;
    padding: 3px 14px; border-radius: 20px;
    text-transform: uppercase; letter-spacing: 1px;
}
.story-chapter-title {
    font-size: 1.05rem; font-weight: 700; color: #fbbf24;
    margin: 4px 0 10px;
}
.story-chapter-body {
    font-size: 0.92rem; color: #f1f5f9; line-height: 1.8;
}
.story-highlight {
    color: #f59e0b; font-weight: 700;
}
.story-insight-box {
    background: rgba(16,185,129,0.08);
    border-left: 3px solid #10b981;
    border-radius: 0 8px 8px 0;
    padding: 10px 16px;
    margin-top: 14px;
    font-size: 0.85rem; color: #a7f3d0; font-style: italic;
}
.story-warning-box {
    background: rgba(239,68,68,0.08);
    border-left: 3px solid #ef4444;
    border-radius: 0 8px 8px 0;
    padding: 10px 16px;
    margin-top: 14px;
    font-size: 0.85rem; color: #fca5a5; font-style: italic;
}
.narrative-timeline {
    position: relative;
    padding-left: 32px;
    margin: 8px 0;
}
.narrative-timeline::before {
    content: '';
    position: absolute; left: 10px; top: 0; bottom: 0;
    width: 2px;
    background: linear-gradient(180deg, #f59e0b, rgba(245,158,11,0.1));
}
.narrative-event {
    position: relative;
    margin-bottom: 18px;
}
.narrative-event::before {
    content: '';
    position: absolute; left: -26px; top: 6px;
    width: 10px; height: 10px;
    border-radius: 50%;
    background: #f59e0b;
    box-shadow: 0 0 0 3px rgba(245,158,11,0.2);
}
.narrative-event-date {
    font-size: 0.7rem; color: #f59e0b; font-weight: 700;
    text-transform: uppercase; letter-spacing: 0.5px;
}
.narrative-event-text {
    font-size: 0.87rem; color: #e2e8f0; line-height: 1.6; margin-top: 2px;
}
.narrative-event-value {
    font-size: 0.8rem; color: #10b981; font-weight: 700; margin-top: 2px;
}

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: #0d1829; }
::-webkit-scrollbar-thumb { background: rgba(245,158,11,0.3); border-radius: 3px; }
</style>
"""

# ──────────────────────────────────────────────────────────────
# HELPER UTILITIES
# ──────────────────────────────────────────────────────────────

def _fmt(val, prefix="", suffix="", decimals=2):
    """Smart number formatter for financial values."""
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return "N/A"
    if abs(val) >= 1_000_000_000:
        return f"{prefix}{val/1_000_000_000:.{decimals}f}B{suffix}"
    if abs(val) >= 1_000_000:
        return f"{prefix}{val/1_000_000:.{decimals}f}M{suffix}"
    if abs(val) >= 1_000:
        return f"{prefix}{val/1_000:.{decimals}f}K{suffix}"
    return f"{prefix}{val:.{decimals}f}{suffix}"


def _delta_class(delta):
    if delta is None:
        return "delta-flat"
    return "delta-up" if delta >= 0 else "delta-down"


def _delta_arrow(delta):
    if delta is None:
        return ""
    return "▲" if delta >= 0 else "▼"


def _pct(num, denom):
    """Safe percentage."""
    try:
        if denom == 0:
            return 0.0
        return (num / denom) * 100
    except Exception:
        return 0.0


# ──────────────────────────────────────────────────────────────
# FINANCIAL COLUMN DETECTION
# ──────────────────────────────────────────────────────────────

# NOTE: profit/margin keywords checked BEFORE revenue/cost so that
# "Gross_Profit" is never stolen by the 'gross' substring in revenue keywords.
# Keywords matched against CANONICAL column names (after apply_universal_column_mapping).
# Priority order: most specific first so _priority_sort always picks the best column.
PROFIT_KEYWORDS    = ['gross_profit', 'net_profit', 'net_surplus', 'profit', 'margin',
                      'ebit', 'ebitda', 'net_income', 'earnings', 'operating_income',
                      'surplus', 'net_revenue']
REVENUE_KEYWORDS   = ['enrollment_tuition_amount',   # canonical for Tuition_Fee_Total
                      'total_payments_ytd',           # canonical for Total_Payments_YTD
                      'revenue', 'sales', 'income', 'turnover',
                      'net_sales', 'sale_amount', 'total_sales', 'total_revenue',
                      'tuition_fee', 'tuition_fee_total', 'tuition_amount', 'total_tuition',
                      'payments_ytd', 'total_payments', 'tuition']
COST_KEYWORDS      = ['estimated_annual_cost',        # canonical: Estimated_Annual_Cost
                      'current_term_charges',          # canonical: Current_Term_Charges
                      'rent_amount',                   # canonical: rent_amount (housing cost)
                      'annual_cost', 'cost', 'expense',
                      'cogs', 'spend', 'expenditure', 'opex', 'capex', 'charge',
                      'balance_due', 'outstanding_balance']  # last resort: balance fields
QUANTITY_KEYWORDS  = ['qty', 'quantity', 'units', 'volume', 'orders', 'transactions',
                      'num_units', 'unit_count', 'total_units', 'terms_enrolled',
                      'credits_attempted', 'credit_hours']
DATE_KEYWORDS      = ['date', 'period', 'month', 'year', 'quarter', 'week', 'day', 'time',
                      'academic_year', 'academic_term', 'cohort_term']
CUSTOMER_KEYWORDS  = ['student_id', 'studentid', 'customer_id', 'client_id',
                      'customer', 'client', 'segment', 'region', 'territory', 'channel']
PRODUCT_KEYWORDS   = ['product', 'sku', 'category', 'item', 'service', 'offering', 'brand']

# ──────────────────────────────────────────────────────────────
# ENTITY / DOMAIN TERMINOLOGY
# Auto-detected from dataset column names. Adapts all UI labels,
# KPI names, narrative text, and advisory language dynamically.
# ──────────────────────────────────────────────────────────────

ENTITY_TERMINOLOGY = {
    'student': {
        'entity_label':   'Student',
        'entity_plural':  'Students',
        'unique_count':   'enrolled students',
        'per_metric':     'Revenue per Student',
        'expansion':      'enrollment growth',
        'retention':      'student retention',
        'segments':       'student cohorts',
        'base':           'student body',
        'churn':          'attrition',
        'role_emoji':     '🎓',
        'kpi_name':       'Active Enrollment',
        'concentration':  'program/cohort concentration',
        'new_accounts':   'new enrollments',
        'accounts':       'enrolled students',
        'upsell':         'programme upgrades and fee tier expansion',
    },
    'employee': {
        'entity_label':   'Employee',
        'entity_plural':  'Employees',
        'unique_count':   'employees',
        'per_metric':     'Revenue per Employee',
        'expansion':      'workforce growth',
        'retention':      'employee retention',
        'segments':       'departments',
        'base':           'workforce',
        'churn':          'turnover',
        'role_emoji':     '👷',
        'kpi_name':       'Active Headcount',
        'concentration':  'department concentration',
        'new_accounts':   'new hires',
        'accounts':       'employees',
        'upsell':         'productivity and cost optimisation',
    },
    'patient': {
        'entity_label':   'Patient',
        'entity_plural':  'Patients',
        'unique_count':   'patients',
        'per_metric':     'Revenue per Patient',
        'expansion':      'patient volume growth',
        'retention':      'patient retention',
        'segments':       'patient cohorts',
        'base':           'patient population',
        'churn':          'patient attrition',
        'role_emoji':     '🏥',
        'kpi_name':       'Active Patients',
        'concentration':  'service line concentration',
        'new_accounts':   'new patients',
        'accounts':       'patients',
        'upsell':         'care pathway expansion and service upsell',
    },
    'customer': {
        'entity_label':   'Customer',
        'entity_plural':  'Customers',
        'unique_count':   'unique customers',
        'per_metric':     'Revenue per Customer',
        'expansion':      'customer expansion',
        'retention':      'customer retention',
        'segments':       'customer segments',
        'base':           'customer base',
        'churn':          'churn',
        'role_emoji':     '👥',
        'kpi_name':       'Active Customers',
        'concentration':  'customer/product concentration',
        'new_accounts':   'new customer acquisition',
        'accounts':       'customer accounts',
        'upsell':         'cross-sell and upsell initiatives',
    },
    'generic': {
        'entity_label':   'Entity',
        'entity_plural':  'Entities',
        'unique_count':   'unique records',
        'per_metric':     'Revenue per Record',
        'expansion':      'volume growth',
        'retention':      'record retention',
        'segments':       'segments',
        'base':           'record base',
        'churn':          'attrition',
        'role_emoji':     '📋',
        'kpi_name':       'Active Records',
        'concentration':  'concentration risk',
        'new_accounts':   'new records',
        'accounts':       'records',
        'upsell':         'expansion opportunities',
    },
}

# Column name patterns used to detect entity domain
_STUDENT_COLS  = {'student_id', 'studentid', 'student_name', 'gpa', 'cgpa', 'cumulative_gpa',
                  'enrollment_status', 'student_status', 'tuition', 'tuition_fee', 'major',
                  'academic_level', 'cohort', 'cohort_year', 'academic_standing', 'credits',
                  'credits_attempted', 'degree_progress', 'enrollment_date', 'graduation_date'}
_EMPLOYEE_COLS = {'employee_id', 'employeeid', 'emp_id', 'salary', 'department', 'hire_date',
                  'position', 'job_title', 'headcount', 'payroll', 'bonus', 'tenure'}
_PATIENT_COLS  = {'patient_id', 'patientid', 'diagnosis', 'icd', 'procedure', 'visit_date',
                  'admission', 'discharge', 'ward', 'doctor', 'physician', 'treatment',
                  'claim_amount', 'insurance'}


def detect_entity_type(df: pd.DataFrame) -> str:
    """
    Detect the entity domain of the dataset by examining column names.
    Returns one of: 'student', 'employee', 'patient', 'customer', 'generic'.
    """
    cols_lower = {c.lower() for c in df.columns}
    student_score  = len(cols_lower & _STUDENT_COLS)
    employee_score = len(cols_lower & _EMPLOYEE_COLS)
    patient_score  = len(cols_lower & _PATIENT_COLS)

    max_score = max(student_score, employee_score, patient_score)
    if max_score < 2:
        col_str = ' '.join(cols_lower)
        student_score  += sum(1 for w in ['student', 'enroll', 'gpa', 'tuition', 'cohort', 'major'] if w in col_str)
        employee_score += sum(1 for w in ['employee', 'salary', 'payroll', 'hire', 'department'] if w in col_str)
        patient_score  += sum(1 for w in ['patient', 'diagnosis', 'doctor', 'clinical', 'treatment'] if w in col_str)
        max_score = max(student_score, employee_score, patient_score)

    if max_score < 2:
        return 'customer'   # default for unrecognised / commercial datasets

    if student_score >= employee_score and student_score >= patient_score:
        return 'student'
    if employee_score >= patient_score:
        return 'employee'
    return 'patient'


def _ev(key: str, default: str = '') -> str:
    """
    Retrieve an entity vocabulary term from session state.
    Falls back to customer terminology when entity_vocab is not yet set.
    Usage: _ev('entity_plural') -> 'Students' / 'Customers' / etc.
    """
    vocab = st.session_state.get('_entity_vocab', ENTITY_TERMINOLOGY['customer'])
    return vocab.get(key, default)


def detect_financial_columns(df: pd.DataFrame) -> Dict[str, List[str]]:
    """
    Map DataFrame columns to financial roles.
    Priority order: profit → revenue → cost → quantity → date → customer → product
    Profit is checked first so 'Gross_Profit' is never stolen by revenue/cost keywords.
    Falls back to first numeric columns for revenue/cost if no keyword match found.
    """
    roles: Dict[str, List[str]] = {
        'revenue': [], 'cost': [], 'profit': [],
        'quantity': [], 'date': [], 'customer': [],
        'product': [], 'other_numeric': [], 'other_categorical': []
    }
    # Numeric roles (profit/revenue/cost/quantity) must only match NUMERIC columns.
    # Non-numeric columns can only match date, customer, product.
    NUMERIC_ROLES = {'profit', 'revenue', 'cost', 'quantity'}

    for col in df.columns:
        c = col.lower()
        dtype = df[col].dtype
        is_numeric = pd.api.types.is_numeric_dtype(dtype)
        assigned = False
        # Profit checked FIRST so 'Gross_Profit' is never stolen by revenue
        for role, kws in [
            ('profit',    PROFIT_KEYWORDS),
            ('revenue',   REVENUE_KEYWORDS),
            ('cost',      COST_KEYWORDS),
            ('quantity',  QUANTITY_KEYWORDS),
            ('date',      DATE_KEYWORDS),
            ('customer',  CUSTOMER_KEYWORDS),
            ('product',   PRODUCT_KEYWORDS),
        ]:
            if any(k in c for k in kws):
                # Revenue/cost/profit/quantity must be numeric columns
                if role in NUMERIC_ROLES and not is_numeric:
                    continue  # keyword matched but wrong dtype — keep looking
                roles[role].append(col)
                assigned = True
                break
        if not assigned:
            if is_numeric:
                roles['other_numeric'].append(col)
            else:
                roles['other_categorical'].append(col)

    # ── Numeric fallback: if revenue/cost still empty, use first unassigned numeric cols ──
    numeric_cols = [c for c in df.select_dtypes(include='number').columns]
    assigned_numeric = set(
        roles['revenue'] + roles['cost'] + roles['profit'] + roles['quantity']
    )
    unassigned_numeric = [c for c in numeric_cols if c not in assigned_numeric]

    if not roles['revenue'] and unassigned_numeric:
        # Pick the numeric column with the highest mean value as revenue proxy
        best = max(unassigned_numeric, key=lambda c: pd.to_numeric(df[c], errors='coerce').mean())
        roles['revenue'].append(best)
        unassigned_numeric.remove(best)

    if not roles['cost'] and unassigned_numeric:
        best = max(unassigned_numeric, key=lambda c: pd.to_numeric(df[c], errors='coerce').mean())
        roles['cost'].append(best)
        unassigned_numeric.remove(best)

    # ── Prefer highest-priority keyword match for revenue and cost ──
    # When multiple columns match the same role, sort by keyword priority order
    # so the most specific/accurate column is always used first.
    def _priority_sort(cols, keywords):
        def _rank(col):
            c = col.lower()
            for i, kw in enumerate(keywords):
                if kw in c:
                    return i
            return len(keywords)
        return sorted(cols, key=_rank)

    if len(roles['revenue']) > 1:
        roles['revenue'] = _priority_sort(roles['revenue'], REVENUE_KEYWORDS)
    if len(roles['cost']) > 1:
        roles['cost'] = _priority_sort(roles['cost'], COST_KEYWORDS)

    return roles


# ──────────────────────────────────────────────────────────────
# FINANCIAL KPI ENGINE
# ──────────────────────────────────────────────────────────────

def compute_financial_kpis(df: pd.DataFrame, col_roles: Dict[str, List[str]]) -> Dict[str, Any]:
    """Compute core financial KPIs from the dataset."""
    kpis: Dict[str, Any] = {}

    # ── Revenue KPIs ──
    if col_roles['revenue']:
        rev_col = col_roles['revenue'][0]
        rev_series = pd.to_numeric(df[rev_col], errors='coerce').dropna()
        kpis['total_revenue']   = rev_series.sum()
        kpis['avg_revenue']     = rev_series.mean()
        kpis['revenue_col']     = rev_col
        kpis['revenue_count']   = len(rev_series)

        # MoM / QoQ trend if date available
        if col_roles['date']:
            date_col = col_roles['date'][0]
            try:
                tmp = df[[date_col, rev_col]].copy()
                tmp[date_col] = pd.to_datetime(tmp[date_col], errors='coerce')
                tmp = tmp.dropna(subset=[date_col])
                tmp['_period'] = tmp[date_col].dt.to_period('M')
                by_period = tmp.groupby('_period')[rev_col].sum().sort_index()
                if len(by_period) >= 2:
                    kpis['revenue_trend'] = by_period
                    last  = float(by_period.iloc[-1])
                    prev  = float(by_period.iloc[-2])
                    kpis['mom_change']    = last - prev
                    kpis['mom_pct']       = _pct(last - prev, prev)
            except Exception:
                pass

    # ── Cost KPIs ──
    if col_roles['cost']:
        cost_col = col_roles['cost'][0]
        cost_series = pd.to_numeric(df[cost_col], errors='coerce').dropna()
        kpis['total_cost'] = cost_series.sum()
        kpis['avg_cost']   = cost_series.mean()
        kpis['cost_col']   = cost_col

    # ── Profit KPIs ──
    if col_roles['profit']:
        prof_col = col_roles['profit'][0]
        prof_series = pd.to_numeric(df[prof_col], errors='coerce').dropna()
        kpis['total_profit']  = prof_series.sum()
        kpis['avg_margin']    = prof_series.mean()
        kpis['profit_col']    = prof_col
    elif 'total_revenue' in kpis and 'total_cost' in kpis:
        kpis['total_profit']  = kpis['total_revenue'] - kpis['total_cost']

    # Always compute gross_margin_pct whenever we have both revenue and profit
    if 'total_profit' in kpis and 'total_revenue' in kpis and kpis.get('total_revenue', 0):
        kpis['gross_margin_pct'] = _pct(kpis['total_profit'], kpis['total_revenue'])

    # ── Transaction / Volume ──
    if col_roles['quantity']:
        qty_col = col_roles['quantity'][0]
        qty_series = pd.to_numeric(df[qty_col], errors='coerce').dropna()
        kpis['total_units']    = qty_series.sum()
        kpis['quantity_col']   = qty_col

    # Derived: Revenue per unit
    if 'total_revenue' in kpis and 'total_units' in kpis and kpis['total_units'] > 0:
        kpis['avg_revenue_per_unit'] = kpis['total_revenue'] / kpis['total_units']

    # ── Customer count ──
    if col_roles['customer']:
        cust_col = col_roles['customer'][0]
        kpis['unique_customers'] = df[cust_col].nunique()
        kpis['customer_col'] = cust_col
        if 'total_revenue' in kpis:
            kpis['revenue_per_customer'] = kpis['total_revenue'] / max(kpis['unique_customers'], 1)

    # ── Product / category ──
    if col_roles['product']:
        prod_col = col_roles['product'][0]
        kpis['unique_products'] = df[prod_col].nunique()
        kpis['product_col'] = prod_col
        if col_roles['revenue']:
            top = df.groupby(prod_col)[col_roles['revenue'][0]].sum().nlargest(5)
            kpis['top_products'] = top

    # ── Data health ──
    total_cells = df.shape[0] * df.shape[1]
    missing     = df.isnull().sum().sum()
    kpis['data_completeness_pct'] = _pct(total_cells - missing, total_cells)
    kpis['row_count']  = len(df)
    kpis['col_count']  = len(df.columns)

    # ── Catalog-driven KPI extraction ──────────────────────────────────────
    # Uses canonical column names from the universal catalog.
    # Each block is guarded: only runs if the column exists after catalog mapping.

    def _col(name):
        """Return column values if canonical name exists, else None."""
        return df[name] if name in df.columns else None

    def _num(name):
        """Return numeric series for canonical column, or None."""
        s = _col(name)
        return pd.to_numeric(s, errors='coerce').dropna() if s is not None else None

    # ── Enrollment & student population ──
    _status = _col('enrollment_enrollment_status')
    if _status is not None:
        vc = _status.value_counts()
        kpis['enrollment_status_counts'] = vc.to_dict()
        kpis['active_students']   = int(vc.get('Active', 0))
        kpis['inactive_students'] = int(vc.get('Inactive', 0))
        kpis['graduated_students']= int(vc.get('Graduated', 0))
        kpis['total_enrolled']    = int(_status.notna().sum())
        if kpis['total_enrolled'] > 0:
            kpis['active_pct'] = round(kpis['active_students'] / kpis['total_enrolled'] * 100, 1)

    # ── Financial aid ──
    _aid = _num('financial_aid_monetary_amount')
    if _aid is not None:
        kpis['total_financial_aid'] = float(_aid.sum())
        kpis['avg_financial_aid']   = float(_aid.mean())
        kpis['aid_recipients']      = int((_aid > 0).sum())
        if 'total_revenue' in kpis and kpis['total_revenue'] > 0:
            kpis['aid_as_pct_of_revenue'] = round(kpis['total_financial_aid'] / kpis['total_revenue'] * 100, 1)
        _sid = _col('student_id')
        if _sid is not None:
            mask = df['financial_aid_monetary_amount'].fillna(0) > 0 if 'financial_aid_monetary_amount' in df.columns else None
            if mask is not None:
                kpis['students_with_aid'] = int(df.loc[mask, 'student_id'].nunique()) if 'student_id' in df.columns else None

    # ── Scholarship ──
    _schol = _num('scholarship_amount')
    if _schol is not None:
        kpis['total_scholarship'] = float(_schol.sum())
        kpis['avg_scholarship']   = float(_schol.mean())

    # ── Net tuition revenue (tuition minus aid) ──
    if 'total_revenue' in kpis and 'total_financial_aid' in kpis:
        kpis['net_tuition_revenue'] = kpis['total_revenue'] - kpis['total_financial_aid']

    # ── GPA analytics ──
    _gpa = _num('cumulative_gpa')
    if _gpa is not None:
        kpis['avg_gpa']         = round(float(_gpa.mean()), 2)
        kpis['median_gpa']      = round(float(_gpa.median()), 2)
        kpis['high_performers'] = int((_gpa >= 3.5).sum())   # Dean's list range
        kpis['at_risk_gpa']     = int((_gpa < 2.0).sum())    # Academic probation
        kpis['avg_gpa_active']  = None
        if _status is not None and 'Active' in _status.values:
            active_mask = df['enrollment_enrollment_status'] == 'Active'
            _gpa_active = pd.to_numeric(df.loc[active_mask, 'cumulative_gpa'], errors='coerce').dropna()
            kpis['avg_gpa_active'] = round(float(_gpa_active.mean()), 2) if len(_gpa_active) else None

    # ── At-risk students ──
    _risk = _col('is_at_risk')
    if _risk is not None:
        _risk_s = _risk.astype(str).str.strip().str.lower()
        kpis['at_risk_count'] = int((_risk_s.isin(['yes', 'true', '1', 'high'])).sum())
        if kpis['row_count'] > 0:
            kpis['at_risk_pct'] = round(kpis['at_risk_count'] / kpis['row_count'] * 100, 1)

    # ── Retention & graduation probability ──
    _ret = _num('retention_probability')
    if _ret is not None:
        kpis['avg_retention_prob']  = round(float(_ret.mean()), 1)
        kpis['high_retention_pct']  = round(float((_ret >= 80).sum() / max(len(_ret), 1) * 100), 1)
        kpis['low_retention_count'] = int((_ret < 50).sum())

    _grad = _num('graduation_probability')
    if _grad is not None:
        kpis['avg_grad_prob']    = round(float(_grad.mean()), 1)
        kpis['on_track_grad']    = int((_grad >= 70).sum())
        kpis['off_track_grad']   = int((_grad < 50).sum())

    # ── Engagement ──
    _eng = _num('engagement_score')
    if _eng is not None:
        kpis['avg_engagement']    = round(float(_eng.mean()), 1)
        kpis['high_engagement']   = int((_eng >= 70).sum())
        kpis['low_engagement']    = int((_eng < 30).sum())

    # ── Attendance ──
    _att = _num('attendance_rate')
    if _att is not None:
        kpis['avg_attendance']    = round(float(_att.mean()), 1)
        kpis['poor_attendance']   = int((_att < 75).sum())   # Below 75% threshold

    # ── Cohort breakdown ──
    _cohort = _col('cohort_year')
    if _cohort is not None and 'total_revenue' in kpis and col_roles.get('revenue'):
        rev_col_name = col_roles['revenue'][0]
        if rev_col_name in df.columns:
            cohort_rev = df.groupby('cohort_year')[rev_col_name].sum().sort_index()
            kpis['revenue_by_cohort'] = cohort_rev.to_dict()
            kpis['cohort_count'] = int(_cohort.nunique())

    # ── Programme / major breakdown ──
    for prog_col in ['academic_program', 'major', 'college', 'department']:
        if prog_col in df.columns and col_roles.get('revenue'):
            rev_col_name = col_roles['revenue'][0]
            if rev_col_name in df.columns:
                top_prog = df.groupby(prog_col)[rev_col_name].sum().nlargest(5)
                kpis[f'top_by_{prog_col}'] = top_prog.to_dict()
                kpis[f'{prog_col}_count'] = int(df[prog_col].nunique())
            break   # use first available programme dimension

    # ── Degree progress ──
    _prog = _num('degree_progress_pct')
    if _prog is not None:
        kpis['avg_degree_progress'] = round(float(_prog.mean()), 1)
        kpis['near_graduation']     = int((_prog >= 80).sum())  # 80%+ complete

    # ── Credits ──
    _cred = _num('credits_attempted')
    if _cred is not None:
        kpis['avg_credits'] = round(float(_cred.mean()), 1)

    # ── Stop-out risk ──
    _stop = _col('stop_out_risk_flag')
    if _stop is not None:
        _stop_s = _stop.astype(str).str.strip().str.lower()
        kpis['stop_out_risk_count'] = int((_stop_s.isin(['yes', 'true', '1'])).sum())

    # ── Internship & career readiness ──
    _intern = _col('has_completed_internship')
    if _intern is not None:
        _intern_s = _intern.astype(str).str.strip().str.lower()
        kpis['internship_count'] = int((_intern_s.isin(['true', 'yes', '1'])).sum())
    _ready = _num('career_readiness_score')
    if _ready is not None:
        kpis['avg_career_readiness'] = round(float(_ready.mean()), 1)

    # ── Past-due & financial hold ──
    _pastdue = _num('past_due_balance')
    if _pastdue is not None:
        kpis['total_past_due']   = float(_pastdue.sum())
        kpis['students_past_due']= int((_pastdue > 0).sum())
    _hold = _col('financial_hold_status')
    if _hold is not None:
        _hold_s = _hold.astype(str).str.strip().str.lower()
        kpis['financial_holds'] = int((~_hold_s.isin(['none', 'no hold', 'nan', 'clear', ''])).sum())

    # ── International students ──
    _intl = _col('is_international')
    if _intl is not None:
        _intl_s = _intl.astype(str).str.strip().str.lower()
        kpis['international_count'] = int((_intl_s.isin(['yes', 'true', '1'])).sum())
        if kpis['row_count'] > 0:
            kpis['international_pct'] = round(kpis['international_count'] / kpis['row_count'] * 100, 1)

    # ── Payments YTD ──
    _pay = _num('total_payments_ytd')
    if _pay is not None:
        kpis['total_payments_ytd'] = float(_pay.sum())
        kpis['avg_payment_ytd']    = float(_pay.mean())

    return kpis


# ──────────────────────────────────────────────────────────────
# AI ADVISORY ENGINE  (uses existing query_ollama function)
# ──────────────────────────────────────────────────────────────

def generate_financial_advisory(
    df: pd.DataFrame,
    kpis: Dict[str, Any],
    col_roles: Dict[str, List[str]],
    model: str,
    url: str
) -> Dict[str, Any]:
    """
    Call the LLM to produce structured financial advisory output:
    - Executive summary
    - Revenue opportunities
    - Cost & risk flags
    - Forward guidance (next 30 / 90 days)
    - Strategic actions
    """
    # Build concise context for the LLM
    rev  = _fmt(kpis.get('total_revenue'), prefix="$")
    cost = _fmt(kpis.get('total_cost'), prefix="$")
    prof = _fmt(kpis.get('total_profit'), prefix="$")
    gm   = f"{kpis.get('gross_margin_pct', 0):.1f}%"
    mom  = f"{kpis.get('mom_pct', 0):+.1f}%"
    rows = kpis.get('row_count', 0)
    cols_list = list(df.columns[:30])

    top_prod_text = ""
    if 'top_products' in kpis:
        top_prod_text = "\n".join(
            f"  • {k}: {_fmt(v, prefix='$')}"
            for k, v in kpis['top_products'].items()
        )

    prompt = f"""You are a senior financial analyst and strategic advisor.
Analyse the following business data summary and return a JSON object.

=== DATASET SUMMARY ===
Rows: {rows:,} | Columns: {len(cols_list)}
Column names: {', '.join(cols_list)}

=== FINANCIAL KPIs ===
Total Revenue:       {rev}
Total Cost:          {cost}
Gross Profit:        {prof}
Gross Margin:        {gm}
MoM Revenue Change:  {mom}
Unique Customers:    {kpis.get('unique_customers', 'N/A')}
Revenue/Customer:    {_fmt(kpis.get('revenue_per_customer'), prefix='$')}
Avg Revenue/Unit:    {_fmt(kpis.get('avg_revenue_per_unit'), prefix='$')}

=== TOP 5 REVENUE DRIVERS ===
{top_prod_text if top_prod_text else "Product breakdown not available"}

=== TASK ===
Return ONLY valid JSON (no markdown, no explanation) with this exact structure:

{{
  "executive_summary": "2-3 sentence bottom-line assessment of financial health and momentum",
  "revenue_health": "excellent|good|caution|critical",
  "margin_health": "excellent|good|caution|critical",
  "opportunities": [
    {{"title": "...", "impact": "high|medium|low", "description": "...", "action": "..."}}
  ],
  "risks": [
    {{"title": "...", "severity": "high|medium|low", "description": "...", "mitigation": "..."}}
  ],
  "forward_guidance_30d": {{
    "revenue_outlook": "...",
    "key_actions": ["action1", "action2", "action3"],
    "watch_metrics": ["metric1", "metric2"]
  }},
  "forward_guidance_90d": {{
    "strategic_priorities": ["priority1", "priority2", "priority3"],
    "growth_levers": ["lever1", "lever2"],
    "risk_factors": ["risk1", "risk2"]
  }},
  "advisory_score": {{
    "overall": 0-100,
    "revenue_growth": 0-100,
    "profitability": 0-100,
    "data_quality": 0-100,
    "strategic_clarity": 0-100
  }},
  "cfo_memo": "One paragraph memo a CFO would write to the board"
}}"""

    try:
        is_cloudflare = "cloudflare" in url.lower() or "exalio" in url.lower()
        timeout = 480 if is_cloudflare else 120
        response = query_ollama(prompt, model, url, timeout=timeout,
                                auto_optimize=False, verify_connection=False, show_spinner=False)
        if response:
            advisory = extract_json_from_response(response)
            if advisory and isinstance(advisory, dict):
                return advisory
    except Exception:
        pass

    # Fallback rule-based advisory
    return _rule_based_advisory(kpis)


def _rule_based_advisory(kpis: Dict[str, Any]) -> Dict[str, Any]:
    """Deterministic fallback advisory when LLM unavailable."""
    rev     = kpis.get('total_revenue', 0) or 0
    cost    = kpis.get('total_cost', 0)    or 0
    profit  = kpis.get('total_profit', 0)  or 0
    gm_pct  = kpis.get('gross_margin_pct', _pct(profit, max(rev, 1)))
    mom_pct = kpis.get('mom_pct', 0) or 0

    rev_health  = "excellent" if mom_pct > 5 else "good" if mom_pct >= 0 else "caution" if mom_pct > -10 else "critical"
    margin_h    = "excellent" if gm_pct > 40 else "good" if gm_pct > 20 else "caution" if gm_pct > 0 else "critical"

    opportunities = [
        {"title": "Strengthen top-performing revenue streams", "impact": "high",
         "description": f"Direct institutional resources to the top-performing programmes and fee categories that contribute most to the {_fmt(rev, prefix='$')} total revenue base.",
         "action": "Allocate additional capacity and support to the top 3 revenue-generating programmes to sustain and grow their contribution."},
        {"title": "Improve revenue per " + _ev("entity_label", "customer").lower(), "impact": "medium",
         "description": _ev("upsell", "cross-sell and upsell initiatives").capitalize() + " can lift average revenue per " + _ev("entity_label", "customer").lower() + " without adding acquisition cost.",
         "action": "Launch targeted " + _ev("upsell", "cross-sell and upsell initiatives") + " for top 20% of accounts."},
        {"title": "Fee structure and cost efficiency review", "impact": "medium",
         "description": f"Net margin at {gm_pct:.1f}% has room to improve through fee structure review and operational cost discipline.",
         "action": "Review fee tiers and identify the top 3 cost categories for efficiency savings within the next quarter."},
    ]

    risks = [
        {"title": "Revenue concentration risk", "severity": "medium",
         "description": "If top 3 " + _ev("accounts", "customer accounts") + "/products drive >60% of revenue, any " + _ev("churn", "churn") + " creates outsized impact.",
         "mitigation": "Diversify income streams across programmes and cohorts; actively grow mid-tier " + _ev("base", "student body") + "."},
        {"title": "Cost pressure and sustainability risk",
         "severity": "high" if gm_pct < 15 else "medium",
         "description": f"Net margin of {gm_pct:.1f}% leaves limited buffer to absorb rising operational costs or enrolment volatility.",
         "mitigation": "Identify the top 3 operational cost line items and target process automation or renegotiated service agreements."},
    ]

    score_overall = min(100, max(0, int(
        (40 if rev_health == "excellent" else 30 if rev_health == "good" else 15 if rev_health == "caution" else 0) +
        (30 if margin_h  == "excellent" else 22 if margin_h  == "good" else 10 if margin_h  == "caution" else 0) +
        int(kpis.get('data_completeness_pct', 50) * 0.3)
    )))

    return {
        "executive_summary": (
            f"The institution recorded {_fmt(rev, prefix='$')} in total revenue with a "
            f"{gm_pct:.1f}% net margin. Month-over-month income is trending "
            f"{'upward' if mom_pct >= 0 else 'downward'} at {mom_pct:+.1f}%. "
            f"Priority focus areas: financial sustainability, cost efficiency, and income diversification."
        ),
        "revenue_health": rev_health,
        "margin_health": margin_h,
        "opportunities": opportunities,
        "risks": risks,
        "forward_guidance_30d": {
            "revenue_outlook": (
                "Sustain current financial trajectory through targeted enrolment and programme initiatives. "
                "Prioritise high-margin programmes and deepen engagement with the existing " + _ev("base", "student body") + "."
            ),
            "key_actions": [
                "Review fees and cost allocation for the bottom 20% margin programmes",
                "Launch targeted enrolment and re-enrolment outreach for top 10% at-risk cohorts",
                "Complete period-end financial reconciliation and flag any unbudgeted expenditure",
            ],
            "watch_metrics": ["Revenue growth rate", "Net margin %", "Enrolment conversion rate"],
        },
        "forward_guidance_90d": {
            "strategic_priorities": [
                "Expand into adjacent " + _ev("segments", "student cohorts") + " and new programme categories",
                "Automate high-volume, low-margin administrative processes to reduce operational cost",
                "Develop recurring, predictable revenue streams through continuing education and executive programmes",
            ],
            "growth_levers": [
                "Extend reach into high-demand academic and professional markets",
                "Build institutional partnerships to grow the " + _ev("base", "student body") + " and diversify income",
            ],
            "risk_factors": [
                "Macroeconomic headwinds affecting enrolment demand and funding availability",
                "Competitive pressure from alternative education providers on core programmes",
            ],
        },
        "advisory_score": {
            "overall":           score_overall,
            "revenue_growth":    min(100, max(0, 50 + int(mom_pct * 2))),
            "profitability":     min(100, max(0, int(gm_pct * 2))),
            "data_quality":      int(kpis.get('data_completeness_pct', 50)),
            "strategic_clarity": 60,
        },
        "cfo_memo": (
            f"Executive Summary: Total institutional revenue stands at {_fmt(rev, prefix='$')} with MoM movement of {mom_pct:+.1f}%. "
            f"Net margin is {gm_pct:.1f}%, which is "
            f"{'healthy and indicative of sound financial stewardship' if gm_pct > 30 else 'below target and requires a structured cost-efficiency review'}. "
            f"Recommendation: {'sustain current investment in programme quality and enrolment growth' if rev_health in ('excellent','good') else 'initiate a structured cost review and income recovery plan'} "
            f"over the next 90 days."
        ),
    }


# ──────────────────────────────────────────────────────────────
# CHART BUILDERS
# ──────────────────────────────────────────────────────────────

def _build_revenue_trend_chart(kpis: Dict[str, Any]) -> Optional[go.Figure]:
    """Monthly revenue trend with MoM annotation."""
    if 'revenue_trend' not in kpis:
        return None
    trend = kpis['revenue_trend']
    labels = [str(p) for p in trend.index]
    values = trend.values.tolist()

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=labels, y=values,
        mode='lines+markers',
        name='Revenue',
        line=dict(color='#f59e0b', width=3),
        marker=dict(size=7, color='#f59e0b'),
        fill='tozeroy',
        fillcolor='rgba(245,158,11,0.08)',
        hovertemplate='%{x}<br>Revenue: $%{y:,.0f}<extra></extra>'
    ))
    fig.update_layout(
        title=dict(text="Monthly Revenue Trend", font=dict(color='#f1f5f9', size=14)),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#94a3b8'),
        xaxis=dict(gridcolor='rgba(255,255,255,0.05)', showgrid=True),
        yaxis=dict(gridcolor='rgba(255,255,255,0.05)', showgrid=True,
                   tickprefix='$', tickformat=',.0f'),
        margin=dict(l=10, r=10, t=40, b=10),
        height=280,
    )
    return fig


def _build_product_revenue_chart(kpis: Dict[str, Any]) -> Optional[go.Figure]:
    """Horizontal bar: top products by revenue."""
    if 'top_products' not in kpis:
        return None
    top = kpis['top_products']
    fig = go.Figure(go.Bar(
        x=top.values.tolist(),
        y=[str(k) for k in top.index],
        orientation='h',
        marker=dict(
            color=top.values.tolist(),
            colorscale=[[0, '#1e3a5f'], [0.5, '#b45309'], [1, '#f59e0b']],
            showscale=False
        ),
        hovertemplate='%{y}<br>Revenue: $%{x:,.0f}<extra></extra>'
    ))
    fig.update_layout(
        title=dict(text="Top Revenue Drivers", font=dict(color='#f1f5f9', size=14)),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#94a3b8'),
        xaxis=dict(gridcolor='rgba(255,255,255,0.05)', tickprefix='$', tickformat=',.0f'),
        yaxis=dict(gridcolor='rgba(255,255,255,0.05)'),
        margin=dict(l=10, r=10, t=40, b=10),
        height=280,
    )
    return fig


def _build_margin_waterfall(kpis: Dict[str, Any]) -> Optional[go.Figure]:
    """Simple waterfall: Revenue → Cost → Profit."""
    rev   = kpis.get('total_revenue')
    cost  = kpis.get('total_cost')
    profit = kpis.get('total_profit')
    if rev is None:
        return None

    measures = ['absolute', 'relative', 'total']
    x_labels = ['Total Revenue', 'Total Cost', 'Gross Profit']
    y_vals   = [rev, -(cost or 0), profit or (rev - (cost or 0))]

    fig = go.Figure(go.Waterfall(
        orientation='v',
        measure=measures,
        x=x_labels,
        y=y_vals,
        textposition='outside',
        text=[_fmt(v, prefix='$') for v in y_vals],
        connector=dict(line=dict(color='rgba(255,255,255,0.1)')),
        increasing=dict(marker=dict(color='#10b981')),
        decreasing=dict(marker=dict(color='#ef4444')),
        totals=dict(marker=dict(color='#f59e0b')),
    ))
    fig.update_layout(
        title=dict(text="Revenue to Profit Waterfall", font=dict(color='#f1f5f9', size=14)),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#94a3b8'),
        yaxis=dict(gridcolor='rgba(255,255,255,0.05)', tickprefix='$', tickformat=',.0f'),
        margin=dict(l=10, r=10, t=40, b=10),
        height=280,
        showlegend=False,
    )
    return fig


def _build_advisory_score_radar(scores: Dict[str, int]) -> go.Figure:
    """Radar chart showing advisory health scores."""
    categories = ['Revenue\nGrowth', 'Profitability', 'Data\nQuality', 'Strategic\nClarity', 'Overall']
    vals = [
        scores.get('revenue_growth', 50),
        scores.get('profitability', 50),
        scores.get('data_quality', 50),
        scores.get('strategic_clarity', 50),
        scores.get('overall', 50),
    ]
    vals_closed = vals + [vals[0]]
    cats_closed = categories + [categories[0]]

    fig = go.Figure(go.Scatterpolar(
        r=vals_closed, theta=cats_closed,
        fill='toself',
        fillcolor='rgba(245,158,11,0.1)',
        line=dict(color='#f59e0b', width=2),
        marker=dict(size=6, color='#f59e0b'),
    ))
    fig.update_layout(
        polar=dict(
            bgcolor='rgba(0,0,0,0)',
            radialaxis=dict(visible=True, range=[0, 100],
                            gridcolor='rgba(255,255,255,0.1)',
                            tickfont=dict(color='#94a3b8', size=10)),
            angularaxis=dict(gridcolor='rgba(255,255,255,0.1)',
                             tickfont=dict(color='#94a3b8', size=10)),
        ),
        paper_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#94a3b8'),
        margin=dict(l=20, r=20, t=20, b=20),
        height=280,
        showlegend=False,
    )
    return fig


# ──────────────────────────────────────────────────────────────
# NARRATIVE ANALYSIS ENGINE
# ──────────────────────────────────────────────────────────────

def _detect_trend_events(series: pd.Series, labels: List[str]) -> List[Dict[str, Any]]:
    """
    Scan a time-indexed revenue series and flag notable events:
    - Peak month, trough month
    - Biggest single-month jump and biggest drop
    - First month above/below overall mean
    Returns list of event dicts: {period, value, event_type, description}
    """
    events = []
    if len(series) < 2:
        return events
    vals  = series.values
    mean  = float(np.mean(vals))
    peak_idx  = int(np.argmax(vals))
    trough_idx = int(np.argmin(vals))
    diffs = np.diff(vals)
    max_jump_idx = int(np.argmax(diffs))
    max_drop_idx = int(np.argmin(diffs))

    events.append({
        "period": labels[peak_idx],
        "value":  float(vals[peak_idx]),
        "event_type": "peak",
        "description": "Highest revenue month in the period",
    })
    events.append({
        "period": labels[trough_idx],
        "value":  float(vals[trough_idx]),
        "event_type": "trough",
        "description": "Lowest revenue month in the period",
    })
    if max_jump_idx + 1 < len(labels):
        pct = _pct(diffs[max_jump_idx], vals[max_jump_idx])
        events.append({
            "period": labels[max_jump_idx + 1],
            "value":  float(vals[max_jump_idx + 1]),
            "event_type": "surge",
            "description": f"Sharpest single-period revenue surge (+{pct:.1f}%)",
        })
    if max_drop_idx + 1 < len(labels):
        pct = _pct(diffs[max_drop_idx], vals[max_drop_idx])
        events.append({
            "period": labels[max_drop_idx + 1],
            "value":  float(vals[max_drop_idx + 1]),
            "event_type": "drop",
            "description": f"Sharpest single-period revenue decline ({pct:.1f}%)",
        })

    # First cross above mean
    for i, v in enumerate(vals):
        if v > mean:
            events.append({
                "period": labels[i],
                "value":  float(v),
                "event_type": "above_mean",
                "description": "First month revenue exceeded the overall average",
            })
            break

    # Sort by period
    events.sort(key=lambda e: e["period"])
    return events


def build_financial_narrative(
    df: pd.DataFrame,
    kpis: Dict[str, Any],
    col_roles: Dict[str, List[str]],
    advisory: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Rule-based narrative engine.
    Produces a 5-chapter financial story from raw KPIs + data:

    Chapter 1 – The Opening: What does this dataset represent?
    Chapter 2 – The Revenue Story: How did revenue move over time?
    Chapter 3 – The Profit Story: Where did the money go?
    Chapter 4 – The Risk & Opportunity Story: What should concern / excite leadership?
    Chapter 5 – The Forward Story: What happens next if we act?

    Returns dict with keys: chapters (list), timeline_events, key_sentences, sentiment
    """
    rev    = kpis.get('total_revenue', 0) or 0
    cost   = kpis.get('total_cost', 0)   or 0
    profit = kpis.get('total_profit', 0) or 0
    gm_pct = kpis.get('gross_margin_pct', _pct(profit, max(rev, 1)))
    mom    = kpis.get('mom_pct', 0) or 0
    rows   = kpis.get('row_count', 0)
    custs  = kpis.get('unique_customers')
    rpc    = kpis.get('revenue_per_customer')
    rev_col  = kpis.get('revenue_col', 'revenue')

    # Determine overall sentiment
    sentiment_score = 0
    if mom  >  5: sentiment_score += 2
    elif mom > 0: sentiment_score += 1
    elif mom < -10: sentiment_score -= 2
    else: sentiment_score -= 1
    if gm_pct > 40: sentiment_score += 2
    elif gm_pct > 20: sentiment_score += 1
    elif gm_pct < 10: sentiment_score -= 2
    else: sentiment_score -= 1

    sentiment = "positive" if sentiment_score >= 2 else \
                "cautious" if sentiment_score >= 0 else "concerning"

    # ── Chapter 1: The Opening ──
    num_products = kpis.get('unique_products', 0)
    product_col  = kpis.get('product_col', '')
    has_time     = bool(col_roles.get('date'))

    opening_body = (
        f"This dataset contains <span class='story-highlight'>{rows:,} records</span> "
        f"spanning {len(df.columns)} dimensions of institutional financial activity. "
    )
    if custs:
        opening_body += (
            f"It represents the financial activity associated with "
            f"<span class='story-highlight'>{custs:,} " + _ev("entity_plural", "students") + "</span>"
            f"{f', spanning {num_products} distinct programmes or categories' if num_products else ''}. "
        )
        # Enrich opening with catalog-derived context
        _active_st = kpis.get('active_students')
        _avg_gpa   = kpis.get('avg_gpa')
        _at_risk   = kpis.get('at_risk_count')
        _avg_ret   = kpis.get('avg_retention_prob')
        if _active_st is not None:
            opening_body += (
                f"Of these, <span class='story-highlight'>{_active_st:,} are currently active</span> "
                f"({kpis.get('active_pct', 0):.0f}% enrolment rate). "
            )
        if _avg_gpa is not None:
            opening_body += (
                f"The cohort maintains an average GPA of <span class='story-highlight'>{_avg_gpa:.2f}</span>, "
                f"with {kpis.get('high_performers', 0):,} students achieving 3.5 or above. "
            )
        if _at_risk is not None:
            opening_body += (
                f"<span class='story-highlight'>{_at_risk:,} students ({kpis.get('at_risk_pct',0):.1f}%) are flagged at risk</span>, "
                f"warranting targeted academic and financial intervention. "
            )
        if _avg_ret is not None:
            opening_body += (
                f"Average retention probability stands at <span class='story-highlight'>{_avg_ret:.1f}%</span>. "
            )
    if has_time:
        try:
            date_col = col_roles['date'][0]
            tmp = pd.to_datetime(df[date_col], errors='coerce').dropna()
            date_range = f"{tmp.min().strftime('%B %Y')} to {tmp.max().strftime('%B %Y')}"
            opening_body += f"The period under review runs from <span class='story-highlight'>{date_range}</span>. "
        except Exception:
            pass
    opening_body += (
        f"The total revenue recorded is "
        f"<span class='story-highlight'>{_fmt(rev, prefix='$')}</span>, "
        f"with total costs of <span class='story-highlight'>{_fmt(cost, prefix='$')}</span>, "
        f"leaving a gross profit of <span class='story-highlight'>{_fmt(profit, prefix='$')}</span> "
        f"— a margin of <span class='story-highlight'>{gm_pct:.1f}%</span>."
    )
    opening_insight = (
        "This is a financially {'active' if rows > 100 else 'focused'} dataset with "
        "{'strong' if gm_pct > 30 else 'moderate' if gm_pct > 15 else 'thin'} margin characteristics."
    )
    opening_insight = (
        f"This is a financially {'active' if rows > 100 else 'focused'} dataset with "
        f"{'strong' if gm_pct > 30 else 'moderate' if gm_pct > 15 else 'thin'} "
        f"margin characteristics, "
        f"suggesting a {'well-funded and sustainable' if gm_pct > 25 else 'cost-sensitive and efficiency-driven'} financial posture."
    )

    # ── Chapter 2: The Revenue Story ──
    trend_events = []
    timeline_events = []
    revenue_body = ""

    if 'revenue_trend' in kpis:
        trend = kpis['revenue_trend']
        labels = [str(p) for p in trend.index]
        trend_events = _detect_trend_events(trend, labels)
        timeline_events = trend_events

        # Determine arc: rising / falling / volatile / flat
        first_half  = trend.iloc[:len(trend)//2].mean()
        second_half = trend.iloc[len(trend)//2:].mean()
        half_change = _pct(second_half - first_half, first_half)

        if   half_change >  15: arc = "a strong upward trajectory"
        elif half_change >   3: arc = "a gentle upward trend"
        elif half_change < -15: arc = "a concerning downward slide"
        elif half_change <  -3: arc = "a gradual softening"
        else:                   arc = "broadly flat performance"

        peak_event   = next((e for e in trend_events if e['event_type'] == 'peak'),   None)
        trough_event = next((e for e in trend_events if e['event_type'] == 'trough'), None)
        surge_event  = next((e for e in trend_events if e['event_type'] == 'surge'),  None)
        drop_event   = next((e for e in trend_events if e['event_type'] == 'drop'),   None)

        revenue_body = (
            f"Revenue across the period tells the story of <span class='story-highlight'>{arc}</span>. "
        )
        if peak_event:
            revenue_body += (
                f"The institution recorded its highest income in "
                f"<span class='story-highlight'>{peak_event['period']}</span>, "
                f"generating <span class='story-highlight'>{_fmt(peak_event['value'], prefix='$')}</span> — "
                f"the strongest period on record. "
            )
        if trough_event:
            revenue_body += (
                f"The lowest point came in "
                f"<span class='story-highlight'>{trough_event['period']}</span> "
                f"at <span class='story-highlight'>{_fmt(trough_event['value'], prefix='$')}</span>. "
            )
        if surge_event:
            revenue_body += (
                f"A notable acceleration occurred in "
                f"<span class='story-highlight'>{surge_event['period']}</span> — "
                f"{surge_event['description'].lower()}. "
            )
        if drop_event:
            revenue_body += (
                f"However, the data also shows a sharp reversal in "
                f"<span class='story-highlight'>{drop_event['period']}</span>. "
            )
        revenue_body += (
            f"Month-over-month momentum currently stands at "
            f"<span class='story-highlight'>{mom:+.1f}%</span>."
        )
        rev_insight_type = "insight" if mom >= 0 else "warning"
        if mom >= 0:
            rev_insight = f"Positive momentum. Income is growing — sustain the institutional conditions that drove {peak_event['period'] if peak_event else 'peak'} performance."
        else:
            rev_insight = f"Negative momentum detected. Investigate what changed after {peak_event['period'] if peak_event else 'the peak'} and take corrective action before the trend compounds."
    else:
        revenue_body = (
            f"A date column was not detected in this dataset, so a time-series revenue story "
            f"cannot be constructed. Total revenue stands at "
            f"<span class='story-highlight'>{_fmt(rev, prefix='$')}</span>. "
            f"To unlock the full revenue narrative, ensure your data includes a date or period column."
        )
        rev_insight_type = "insight"
        rev_insight = "Add a date column to reveal the full revenue story over time."

    # ── Chapter 3: The Profit Story ──
    profit_body = (
        f"Of every dollar of institutional income, "
        f"<span class='story-highlight'>{gm_pct:.1f} cents</span> is retained after direct costs — the net margin. "
        + (
            f"Financial aid disbursements total <span class='story-highlight'>${kpis.get('total_financial_aid',0):,.0f}</span> "
            f"({kpis.get('aid_as_pct_of_revenue',0):.1f}% of tuition revenue), "
            f"leaving a net tuition revenue of <span class='story-highlight'>${kpis.get('net_tuition_revenue',0):,.0f}</span>. "
            if kpis.get('total_financial_aid') else ''
        )
    )
    if gm_pct > 40:
        profit_body += (
            "This is a <span class='story-highlight'>high-margin institution</span> — "
            "income substantially exceeds operational costs, reflecting strong financial management. "
        )
        profit_insight_type = "insight"
        profit_insight = "Strong margins create strategic flexibility: invest in academic quality, faculty development, and programme expansion."
    elif gm_pct > 20:
        profit_body += (
            "The margin is <span class='story-highlight'>healthy but not exceptional</span>. "
            "There is room to improve through pricing optimisation or cost reduction. "
        )
        profit_insight_type = "insight"
        profit_insight = "Target a 5–10 point margin improvement through programme mix optimisation and operational cost review."
    elif gm_pct > 0:
        profit_body += (
            "The margin is <span class='story-highlight'>thin</span>, leaving the institution "
            "exposed to rising operational costs and enrolment volatility. "
        )
        profit_insight_type = "warning"
        profit_insight = "Thin margins require immediate cost efficiency review. A 5% rise in operational costs could eliminate the surplus."
    else:
        profit_body += (
            "<span class='story-highlight'>Costs exceed income</span> — the institution is "
            "operating at a net deficit. This is a critical finding requiring urgent leadership attention."
        )
        profit_insight_type = "warning"
        profit_insight = "Deficit situation. Fee levels, enrolment volume, or cost structure must be reviewed immediately."

    if rpc:
        profit_body += (
            f" Each " + _ev("entity_label", "customer").lower() + f" generates an average of "
            f"<span class='story-highlight'>{_fmt(rpc, prefix='$')}</span> in revenue, "
        )
        if gm_pct > 0:
            implied_profit_per_cust = rpc * gm_pct / 100
            profit_body += (
                f"translating to roughly "
                f"<span class='story-highlight'>{_fmt(implied_profit_per_cust, prefix='$')}</span> "
                "in gross profit per " + _ev("entity_label", "customer").lower() + "."
            )

    # ── Chapter 4: The Risk & Opportunity Story ──
    opportunities = advisory.get('opportunities', []) if advisory else []
    risks         = advisory.get('risks', [])         if advisory else []

    if 'top_products' in kpis:
        top  = kpis['top_products']
        top1_name = list(top.index)[0]
        top1_val  = float(list(top.values)[0])
        top1_share = _pct(top1_val, rev)
        concentration_warning = top1_share > 40
        risk_opp_body = (
            f"The revenue landscape is "
            f"{'concentrated' if concentration_warning else 'diversified'}. "
            f"<span class='story-highlight'>{top1_name}</span> alone accounts for "
            f"<span class='story-highlight'>{top1_share:.1f}%</span> of total revenue "
            f"({_fmt(top1_val, prefix='$')}). "
        )
        if concentration_warning:
            risk_opp_body += (
                "This concentration is a financial risk — any disruption to this "
                "single income source would have an outsized impact on institutional sustainability. "
            )
        else:
            risk_opp_body += (
                "This healthy diversification provides financial resilience across multiple income streams. "
            )
    else:
        risk_opp_body = (
            f"The dataset does not include a product or category breakdown, "
            f"so revenue concentration analysis is not available. "
            f"Consider adding a product/segment column to unlock this insight. "
        )
        concentration_warning = False

    if opportunities:
        risk_opp_body += (
            f"The analysis has identified "
            f"<span class='story-highlight'>{len(opportunities)} financial improvement opportunities</span> "
            f"— the highest-impact being: {opportunities[0].get('title', '')}. "
        )
    if risks:
        risk_opp_body += (
            f"The primary risk flagged is: <span class='story-highlight'>{risks[0].get('title', '')}</span>."
        )

    risk_opp_insight_type = "warning" if concentration_warning else "insight"
    risk_opp_insight = (
        "Income concentration above 40% in one programme warrants a diversification plan."
        if concentration_warning else
        "Diversified income streams are an institutional strength — invest in and grow each programme."
    )

    # ── Chapter 5: The Forward Story ──
    fw30 = advisory.get('forward_guidance_30d', {}) if advisory else {}
    fw90 = advisory.get('forward_guidance_90d', {}) if advisory else {}
    actions_30 = fw30.get('key_actions', [])
    priorities_90 = fw90.get('strategic_priorities', [])

    forward_body = (
        f"Looking ahead, the institution stands at a "
        f"<span class='story-highlight'>"
        f"{'pivotal growth moment' if sentiment == 'positive' else 'critical decision point' if sentiment == 'concerning' else 'strategic crossroads'}"
        f"</span>. "
    )
    if sentiment == 'positive':
        forward_body += (
            "Strong momentum and healthy margins create a compelling case for accelerated investment in academic quality and programme expansion. "
            "The strategic question is not whether to grow, but where to focus institutional resources most effectively. "
        )
    elif sentiment == 'cautious':
        forward_body += (
            "Mixed signals — growing income but compressed margins — call for a balanced approach: "
            "protect core programmes while selectively investing in high-impact academic initiatives. "
        )
    else:
        forward_body += (
            "Declining momentum and thin margins demand immediate corrective action. "
            "The institutional priority is financial stabilisation before pursuing new programme growth. "
        )
    if actions_30:
        forward_body += (
            f"In the next 30 days, the three highest-priority actions are: "
            f"<span class='story-highlight'>{actions_30[0]}</span>, "
            f"{actions_30[1] if len(actions_30) > 1 else ''}"
            f"{', and ' + actions_30[2] if len(actions_30) > 2 else ''}. "
        )
    if priorities_90:
        forward_body += (
            f"Over the next 90 days, the strategic priority is: "
            f"<span class='story-highlight'>{priorities_90[0]}</span>."
        )

    forward_insight = (
        "The data provides a clear direction. The next step is for academic and financial leadership to translate these insights into institutional decisions."
    )

    # ── Assemble chapters ──
    chapters = [
        {
            "num": "Chapter 1", "title": "The Opening — What This Data Tells Us",
            "body": opening_body,
            "insight_type": "insight", "insight": opening_insight,
        },
        {
            "num": "Chapter 2", "title": "The Revenue Story — How the Money Moved",
            "body": revenue_body,
            "insight_type": rev_insight_type, "insight": rev_insight,
        },
        {
            "num": "Chapter 3", "title": "The Profit Story — Where the Money Went",
            "body": profit_body,
            "insight_type": profit_insight_type, "insight": profit_insight,
        },
        {
            "num": "Chapter 4", "title": "The Risk & Opportunity Story — What to Watch",
            "body": risk_opp_body,
            "insight_type": risk_opp_insight_type, "insight": risk_opp_insight,
        },
        {
            "num": "Chapter 5", "title": "The Forward Story — What Happens Next",
            "body": forward_body,
            "insight_type": "insight", "insight": forward_insight,
        },
    ]

    # ── One-line key sentences (for the hero narrative bar) ──
    key_sentences = [
        f"Revenue of {_fmt(rev, prefix='$')} with {gm_pct:.1f}% gross margin.",
        f"MoM growth: {mom:+.1f}% — momentum is {'building' if mom > 0 else 'softening'}.",
        f"{custs:,} customers averaging {_fmt(rpc, prefix='$')} each." if rpc else "",
        f"Overall financial sentiment: {sentiment.upper()}.",
    ]
    key_sentences = [s for s in key_sentences if s]

    return {
        "chapters":       chapters,
        "timeline_events": timeline_events,
        "key_sentences":  key_sentences,
        "sentiment":      sentiment,
    }


def generate_narrative_with_llm(
    narrative: Dict[str, Any],
    kpis: Dict[str, Any],
    model: str,
    url: str,
) -> str:
    """
    Ask the LLM to write a polished, continuous narrative (500–700 words)
    based on the rule-based chapter summaries.
    Returns a single rich prose string, or empty string on failure.
    """
    def _strip_html(text: str) -> str:
        import re as _re
        return _re.sub(r'<[^>]+>', '', text)

    chapter_summaries = "\n".join(
        f"[{c['num']}] {c['title']}: {_strip_html(c['body'])}"
        for c in narrative.get('chapters', [])
    )
    sentiment   = narrative.get('sentiment', 'cautious')
    key_lines   = "\n".join(f"• {s}" for s in narrative.get('key_sentences', []))

    prompt = f"""You are a world-class financial storyteller and CFO advisor.
Write a compelling, data-driven narrative for a financial report.
Use the chapter summaries below as your factual foundation.
Tone: authoritative, clear, human — like a McKinsey partner briefing a board.
Length: 400–550 words. No bullet points. Flowing prose only. No markdown headers.
Overall sentiment of the data: {sentiment}.

KEY FACTS:
{key_lines}

CHAPTER SUMMARIES:
{chapter_summaries}

Write the full narrative now:"""

    try:
        is_cloudflare = "cloudflare" in url.lower() or "exalio" in url.lower()
        timeout = 480 if is_cloudflare else 120
        response = query_ollama(prompt, model, url, timeout=timeout,
                                auto_optimize=False, verify_connection=False, show_spinner=False)
        if response and len(response.strip()) > 100:
            return response.strip()
    except Exception:
        pass
    return ""


def _build_annotated_trend_chart(kpis: Dict[str, Any], timeline_events: List[Dict]) -> Optional[go.Figure]:
    """Revenue trend chart with narrative annotation markers."""
    if 'revenue_trend' not in kpis:
        return None
    trend  = kpis['revenue_trend']
    labels = [str(p) for p in trend.index]
    values = trend.values.tolist()

    fig = go.Figure()

    # Base line
    fig.add_trace(go.Scatter(
        x=labels, y=values,
        mode='lines',
        name='Revenue',
        line=dict(color='rgba(245,158,11,0.4)', width=2),
        showlegend=False,
    ))
    # Smooth area
    fig.add_trace(go.Scatter(
        x=labels, y=values,
        mode='lines+markers',
        name='Revenue',
        line=dict(color='#f59e0b', width=3),
        marker=dict(size=5, color='#f59e0b'),
        fill='tozeroy',
        fillcolor='rgba(245,158,11,0.06)',
        hovertemplate='%{x}<br>Revenue: $%{y:,.0f}<extra></extra>',
        showlegend=False,
    ))

    # Annotation markers for events
    event_colors = {
        'peak':       '#10b981',
        'trough':     '#ef4444',
        'surge':      '#3b82f6',
        'drop':       '#f97316',
        'above_mean': '#8b5cf6',
    }
    event_symbols = {
        'peak': '▲', 'trough': '▼', 'surge': '↑', 'drop': '↓', 'above_mean': '★'
    }

    for ev in timeline_events:
        period = ev['period']
        if period not in labels:
            continue
        idx = labels.index(period)
        color = event_colors.get(ev['event_type'], '#94a3b8')
        sym   = event_symbols.get(ev['event_type'], '●')
        fig.add_trace(go.Scatter(
            x=[period],
            y=[values[idx]],
            mode='markers+text',
            marker=dict(size=14, color=color, symbol='circle',
                        line=dict(color='#fff', width=2)),
            text=[sym],
            textposition='top center',
            textfont=dict(size=10, color=color),
            hovertext=f"{ev['description']}<br>{_fmt(ev['value'], prefix='$')}",
            hoverinfo='text',
            showlegend=False,
        ))
        # Annotation
        fig.add_annotation(
            x=period,
            y=values[idx],
            text=f"<b>{ev['event_type'].upper()}</b><br>{ev['period']}",
            showarrow=True,
            arrowhead=2,
            arrowcolor=color,
            arrowsize=1,
            arrowwidth=1.5,
            ax=0, ay=-40,
            font=dict(size=9, color=color),
            bgcolor='rgba(10,20,40,0.85)',
            bordercolor=color,
            borderwidth=1,
            borderpad=4,
        )

    fig.update_layout(
        title=dict(text="Revenue Narrative Timeline — Annotated", font=dict(color='#f1f5f9', size=14)),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#94a3b8'),
        xaxis=dict(gridcolor='rgba(255,255,255,0.05)', showgrid=True),
        yaxis=dict(gridcolor='rgba(255,255,255,0.05)', showgrid=True,
                   tickprefix='$', tickformat=',.0f'),
        margin=dict(l=10, r=10, t=50, b=10),
        height=340,
        hovermode='closest',
    )
    return fig


# ──────────────────────────────────────────────────────────────
# UI COMPONENTS
# ──────────────────────────────────────────────────────────────

def render_hero():
    st.markdown("""
    <div class="hero-banner">
        <div class="hero-title">Financial & Revenue Intelligence</div>
        <p class="hero-sub">
            AI-powered advisory &amp; narrative analysis — turning your financial data into a story
            that explains what happened, why it happened, and exactly what to do next.
            &nbsp;<span style="color:#f59e0b;font-weight:600;">New: Financial Story tab with annotated timelines &amp; AI prose.</span>
        </p>
    </div>
    """, unsafe_allow_html=True)


def render_section_header(icon: str, title: str, badge: str = ""):
    badge_html = f'<span class="section-badge">{badge}</span>' if badge else ""
    st.markdown(
        f'<div class="section-header">'
        f'<span class="section-icon">{icon}</span>'
        f'<span class="section-title">{title}</span>'
        + badge_html +
        '</div>',
        unsafe_allow_html=True
    )


def render_kpi_row(kpis: Dict[str, Any]):
    """Render the top financial KPI scorecard row."""
    render_section_header("💰", "Financial Command Centre", "LIVE")

    rev   = kpis.get('total_revenue')
    cost  = kpis.get('total_cost')
    prof  = kpis.get('total_profit')
    mom   = kpis.get('mom_pct')
    gm    = kpis.get('gross_margin_pct')
    custs = kpis.get('unique_customers')
    rpc   = kpis.get('revenue_per_customer')

    cols = st.columns(5)

    cards = [
        ("Total Revenue",     _fmt(rev, prefix="$"),
         (f"{_delta_arrow(mom)} {abs(mom):.1f}% MoM" if mom is not None else ""),
         _delta_class(mom)),
        ("Gross Profit",      _fmt(prof, prefix="$"),
         (f"{gm:.1f}% margin" if gm is not None else ""),
         "delta-up" if (gm or 0) > 20 else "delta-flat"),
        ("Total Cost",        _fmt(cost, prefix="$"), "", "delta-flat"),
        (_ev("per_metric", "Revenue / Customer"), _fmt(rpc, prefix="$"), "", "delta-flat"),
        (_ev("kpi_name", "Active Customers"),     f"{custs:,}" if custs else "N/A", "", "delta-flat"),
    ]

    for col, (label, value, delta, delta_cls) in zip(cols, cards):
        with col:
            st.markdown(f"""
            <div class="fin-kpi-card">
                <div class="fin-kpi-label">{label}</div>
                <div class="fin-kpi-value">{value}</div>
                <div class="fin-kpi-delta {delta_cls}">{delta}</div>
            </div>
            """, unsafe_allow_html=True)


def render_advisory_card(title: str, body: str, action: str, color: str = ""):
    cls = f"advisory-card {color}".strip()
    st.markdown(f"""
    <div class="{cls}">
        <div class="advisory-title">{title}</div>
        <div class="advisory-body">{body}</div>
        <span class="advisory-action">{action}</span>
    </div>
    """, unsafe_allow_html=True)


def render_health_indicator(label: str, score: int, bar_width_pct: Optional[int] = None):
    w = bar_width_pct if bar_width_pct is not None else score
    color = "#10b981" if score >= 70 else "#f59e0b" if score >= 40 else "#ef4444"
    st.markdown(f"""
    <div style="margin-bottom:14px;">
        <div style="display:flex; justify-content:space-between; margin-bottom:4px;">
            <span style="font-size:0.82rem;color:#e2e8f0;">{label}</span>
            <span style="font-size:0.82rem;font-weight:700;color:{color};">{score}/100</span>
        </div>
        <div class="health-bar-wrap">
            <div class="health-bar-fill" style="width:{w}%;background:linear-gradient(90deg,{color},{color}aa);"></div>
        </div>
    </div>
    """, unsafe_allow_html=True)


def render_status_pill(label: str, status: str):
    """
    status: excellent | good | caution | critical
    """
    colors = {
        "excellent": ("#10b981", "rgba(16,185,129,0.12)"),
        "good":      ("#34d399", "rgba(52,211,153,0.1)"),
        "caution":   ("#f59e0b", "rgba(245,158,11,0.12)"),
        "critical":  ("#ef4444", "rgba(239,68,68,0.12)"),
    }
    c, bg = colors.get(status, ("#94a3b8", "rgba(148,163,184,0.1)"))
    st.markdown(f"""
    <span style="background:{bg};color:{c};border:1px solid {c}44;
                 font-size:0.78rem;font-weight:700;padding:4px 14px;
                 border-radius:20px;text-transform:uppercase;letter-spacing:0.5px;">
        {label}: {status.upper()}
    </span>&nbsp;
    """, unsafe_allow_html=True)


# ──────────────────────────────────────────────────────────────
# SIDEBAR
# ──────────────────────────────────────────────────────────────

def render_sidebar() -> Tuple[Optional[pd.DataFrame], str, str]:
    """Render sidebar; returns (dataframe, model, url)."""
    with st.sidebar:
        # Logo
        logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "exalio-logo.svg")
        try:
            st.image(logo_path, use_container_width=True)
        except Exception:
            st.markdown("### 💰 Exalio")

        st.markdown("---")
        st.markdown("### 📂 Data Source")

        df = None
        _PRELOADED_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "Student_360_View.csv")
        _preloaded_label = "Student_360_View (preloaded)"
        source = st.radio(
            "Load data from:",
            [_preloaded_label, "Upload file", "Use sample dataset"],
            index=0,
            horizontal=False,
            label_visibility="collapsed",
        )

        if source == _preloaded_label:
            # Auto-load the Student_360_View dataset on startup
            _cache_key = "fin_preloaded_df"
            if _cache_key not in st.session_state:
                try:
                    _pre_df = pd.read_csv(_PRELOADED_PATH)
                    _pre_df, _pre_log = apply_universal_column_mapping(_pre_df)
                    st.session_state[_cache_key] = _pre_df
                    st.session_state[_cache_key + "_log"] = _pre_log
                except Exception as _e:
                    st.session_state[_cache_key] = None
                    st.session_state[_cache_key + "_log"] = []
                    st.error(f"Could not load preloaded file: {_e}")
            df = st.session_state.get(_cache_key)
            if df is not None:
                _log = st.session_state.get(_cache_key + "_log", [])
                st.success(f"Student_360_View: {len(df):,} rows × {len(df.columns)} cols")
                if _log:
                    st.caption("Column mapping: " + "; ".join(_log[:3])
                               + (f" (+{len(_log)-3} more)" if len(_log) > 3 else ""))
        elif source == "Upload file":
            uploaded = st.file_uploader("Upload CSV or Excel",
                                        type=['csv', 'xlsx', 'xls'],
                                        label_visibility="collapsed")
            if uploaded:
                try:
                    if uploaded.name.endswith('.csv'):
                        df = pd.read_csv(uploaded)
                    else:
                        df = pd.read_excel(uploaded)
                    # Apply universal column mapping to standardise column names
                    df, _mapping_log = apply_universal_column_mapping(df)
                    if _mapping_log:
                        st.caption('Column mapping: ' + '; '.join(_mapping_log[:3])
                                  + (f' (+{len(_mapping_log)-3} more)' if len(_mapping_log) > 3 else ''))
                    st.success(f"Loaded {len(df):,} rows × {len(df.columns)} columns")
                except Exception as e:
                    st.error(f"Load error: {e}")
        else:
            df = _build_sample_financial_dataset()
            st.info("Using built-in financial sample dataset")

        st.markdown("---")
        st.markdown("### 🤖 AI Connection (Ollama)")

        ollama_url = st.text_input("Ollama URL",
                                   value=st.session_state.get('fin_ollama_url', 'http://localhost:11434'),
                                   key="fin_ollama_url_input")
        st.session_state['fin_ollama_url'] = ollama_url

        model = ""
        col_check, col_status = st.columns([1, 1])
        with col_check:
            check_btn = st.button("Check connection", key="fin_check_ollama")

        if check_btn or st.session_state.get('fin_ollama_connected'):
            try:
                resp = requests.get(f"{ollama_url}/api/tags", timeout=5)
                if resp.status_code == 200:
                    models_raw = resp.json().get('models', [])
                    model_names = [m.get('name', '') for m in models_raw]
                    if model_names:
                        model = st.selectbox("Select model", model_names, key="fin_model_select")
                    st.session_state['fin_ollama_connected'] = True
                    with col_status:
                        st.markdown('<span style="color:#10b981;font-weight:700;">● Connected</span>',
                                    unsafe_allow_html=True)
                else:
                    st.session_state['fin_ollama_connected'] = False
                    with col_status:
                        st.markdown('<span style="color:#ef4444;font-weight:700;">● Offline</span>',
                                    unsafe_allow_html=True)
            except Exception:
                st.session_state['fin_ollama_connected'] = False
                with col_status:
                    st.markdown('<span style="color:#f59e0b;font-weight:700;">● No response</span>',
                                unsafe_allow_html=True)
        else:
            model = st.session_state.get('fin_model_select', '')

        st.markdown("---")

        # ── Student-360 style dataset filters ──
        if df is not None and len(df) > 0:
            _has_enrollment_status = 'enrollment_enrollment_status' in df.columns
            _has_enrollment_type   = 'enrollment_type' in df.columns
            _has_cohort            = 'cohort_year' in df.columns
            _has_nationality       = 'nationality' in df.columns
            _has_gender            = 'gender' in df.columns
            _has_gpa               = 'cumulative_gpa' in df.columns
            _has_aid               = 'financial_aid_monetary_amount' in df.columns
            _has_housing           = 'room_number' in df.columns
            _has_first_gen         = 'is_first_generation' in df.columns
            _has_sid               = 'student_id' in df.columns
            _has_fname             = 'first_name_en' in df.columns
            _has_lname             = 'last_name_en' in df.columns
            _has_email             = 'email_address' in df.columns

            _any_filter_col = any([_has_enrollment_status, _has_enrollment_type,
                                   _has_nationality, _has_gender, _has_gpa, _has_aid])

            # ── Student Search (always shown when sid or name cols exist) ──
            if any([_has_sid, _has_fname, _has_lname, _has_email]):
                st.markdown("### 🔍 Filters")
                st.text_input(
                    "🔎 Search (ID / Name / Email)", value="",
                    key="fin_student_search",
                    placeholder="Type to search...")
            elif _any_filter_col:
                st.markdown("### 🔍 Filters")

            if _any_filter_col:
                # ── Enrollment ──
                if _has_enrollment_status or _has_enrollment_type or _has_cohort:
                    st.markdown("**📋 Enrollment**")
                if _has_enrollment_status:
                    _enroll_opts = df['enrollment_enrollment_status'].dropna().unique().tolist()
                    st.multiselect(
                        "Enrollment Status", options=_enroll_opts,
                        default=_enroll_opts, key="fin_enroll_status")
                if _has_enrollment_type:
                    _type_opts = df['enrollment_type'].dropna().unique().tolist()
                    st.multiselect(
                        "Enrollment Type", options=_type_opts,
                        default=_type_opts, key="fin_enroll_type")
                if _has_cohort:
                    _cohort_opts = sorted(df['cohort_year'].dropna().unique().tolist())
                    st.multiselect(
                        "Cohort Year", options=_cohort_opts, default=[],
                        key="fin_cohort_year")

                # ── Demographics ──
                if _has_nationality or _has_gender:
                    st.markdown("**👥 Demographics**")
                if _has_nationality:
                    _nat_opts = sorted(df['nationality'].dropna().unique().tolist())
                    st.multiselect(
                        "Nationality", options=_nat_opts, default=[],
                        key="fin_nationality")
                    # UAE National filter (matches student_360)
                    st.selectbox(
                        "UAE National Status",
                        options=["All Students", "UAE Nationals Only", "International Students Only"],
                        index=0, key="fin_uae_national")
                if _has_gender:
                    _gender_opts = df['gender'].dropna().unique().tolist()
                    st.multiselect(
                        "Gender", options=_gender_opts, default=_gender_opts,
                        key="fin_gender")

                # ── Academic Performance ──
                if _has_gpa:
                    st.markdown("**🎓 Academic Performance**")
                    st.slider(
                        "GPA Range", min_value=0.0, max_value=4.0,
                        value=(0.0, 4.0), step=0.1, key="fin_gpa_range")
                    # Academic Risk Level (matches student_360)
                    _risk_opts = ["High Performer (3.5+)", "Mid Performer (2.5-3.5)", "At Risk (<2.5)"]
                    st.multiselect(
                        "Academic Risk Level",
                        options=_risk_opts,
                        default=_risk_opts,
                        key="fin_risk_level")

                # ── Financial ──
                if _has_aid:
                    st.markdown("**💰 Financial**")
                    st.selectbox(
                        "Financial Aid Status",
                        options=["All Records", "With Financial Aid", "Without Financial Aid"],
                        index=0, key="fin_aid_status")
                    _max_aid = float(df['financial_aid_monetary_amount'].max() or 0)
                    if _max_aid > 0:
                        st.slider(
                            "Aid Amount Range (AED)", min_value=0.0, max_value=_max_aid,
                            value=(0.0, _max_aid), key="fin_aid_range")

                # ── Housing ──
                if _has_housing:
                    st.markdown("**🏠 Campus Housing**")
                    st.selectbox(
                        "Housing Status",
                        options=["All Students", "On-Campus", "Off-Campus"],
                        index=0, key="fin_housing_status")

                # ── Special Categories ──
                if _has_first_gen:
                    st.markdown("**⭐ Special Categories**")
                    st.selectbox(
                        "First Generation Status",
                        options=["All Students", "First Generation", "Not First Generation"],
                        index=0, key="fin_first_gen")

        # ── Data Management ──
        st.markdown("---")
        st.markdown("### 📁 Data Management")
        if st.button("🔄 Upload Different File", use_container_width=True, key="fin_reset_upload"):
            for _k in list(st.session_state.keys()):
                if _k.startswith('fin_'):
                    del st.session_state[_k]
            st.rerun()

        if df is not None:
            with st.expander("📊 Loaded Dataset Info", expanded=False):
                st.caption(f"✓ {len(df):,} rows × {len(df.columns)} columns")
                _fin_cols = [c for c in ['enrollment_tuition_amount', 'financial_aid_monetary_amount',
                                          'cumulative_gpa', 'enrollment_type', 'student_id'] if c in df.columns]
                if _fin_cols:
                    st.caption("Key columns: " + ", ".join(_fin_cols))
                _applied = apply_filters(df) if df is not None else df
                if _applied is not None and len(_applied) != len(df):
                    st.caption(f"🔍 Filtered to: {len(_applied):,} rows")

        # ── Export Report ──
        st.markdown("---")
        st.markdown("### 📄 Export Report")

        _export_placeholder = st.empty()
        if _export_placeholder.button("📊 Generate Interactive HTML Report",
                                       use_container_width=True, key="fin_gen_report"):
            _export_df = apply_filters(df) if df is not None else None
            if _export_df is not None and len(_export_df) > 0:
                # Build filter summary HTML
                _filter_items = [f"<li><strong>Total Records:</strong> {len(_export_df):,}</li>"]
                _ss = st.session_state
                _search_q = _ss.get('fin_student_search', '')
                if _search_q:
                    _filter_items.append(f"<li><strong>Search:</strong> {_search_q}</li>")

                _enroll_s = _ss.get('fin_filter_enroll_status')
                if _enroll_s and df is not None and 'enrollment_enrollment_status' in df.columns and len(_enroll_s) < len(df['enrollment_enrollment_status'].unique()):
                    _filter_items.append(f"<li><strong>Enrollment Status:</strong> {', '.join(_enroll_s)}</li>")

                _enroll_t = _ss.get('fin_filter_enroll_type')
                if _enroll_t and df is not None and 'enrollment_type' in df.columns and len(_enroll_t) < len(df['enrollment_type'].unique()):
                    _filter_items.append(f"<li><strong>Enrollment Type:</strong> {', '.join(_enroll_t)}</li>")

                _cohort_f = _ss.get('fin_filter_cohort')
                if _cohort_f:
                    _filter_items.append(f"<li><strong>Cohort Years:</strong> {', '.join(map(str, _cohort_f))}</li>")

                _nat_f = _ss.get('fin_filter_nationality')
                if _nat_f:
                    _filter_items.append(f"<li><strong>Nationalities:</strong> {', '.join(_nat_f)}</li>")

                _uae_f = _ss.get('fin_filter_uae_national', 'All Students')
                if _uae_f != 'All Students':
                    _filter_items.append(f"<li><strong>UAE National Filter:</strong> {_uae_f}</li>")

                _gender_f = _ss.get('fin_filter_gender')
                if _gender_f and df is not None and 'gender' in df.columns and len(_gender_f) < len(df['gender'].unique()):
                    _filter_items.append(f"<li><strong>Gender:</strong> {', '.join(_gender_f)}</li>")

                _gpa_f = _ss.get('fin_filter_gpa', (0.0, 4.0))
                if _gpa_f != (0.0, 4.0):
                    _filter_items.append(f"<li><strong>GPA Range:</strong> {_gpa_f[0]:.1f} – {_gpa_f[1]:.1f}</li>")

                _risk_f = _ss.get('fin_filter_risk_level', [])
                if _risk_f and len(_risk_f) < 3:
                    _filter_items.append(f"<li><strong>Risk Level:</strong> {', '.join(_risk_f)}</li>")

                _aid_sf = _ss.get('fin_filter_aid_status', 'All Records')
                if _aid_sf != 'All Records':
                    _filter_items.append(f"<li><strong>Aid Status:</strong> {_aid_sf}</li>")

                _hous_f = _ss.get('fin_filter_housing', 'All Students')
                if _hous_f != 'All Students':
                    _filter_items.append(f"<li><strong>Housing:</strong> {_hous_f}</li>")

                _fg_f = _ss.get('fin_filter_first_gen', 'All Students')
                if _fg_f != 'All Students':
                    _filter_items.append(f"<li><strong>First Generation:</strong> {_fg_f}</li>")

                if len(_filter_items) == 1:
                    _filter_items.append("<li><strong>Filters:</strong> None (showing all records)</li>")

                _filter_html = '\n'.join(_filter_items)

                with st.spinner("⏳ Generating interactive HTML report..."):
                    _html_content = generate_html_report(_export_df, _filter_html)
                    from datetime import datetime as _dt2
                    _ts = _dt2.now().strftime("%Y%m%d_%H%M%S")
                    _fname = f"Exalio_Financial_Report_{_ts}.html"
                    st.download_button(
                        label="💾 Download HTML Report",
                        data=_html_content,
                        file_name=_fname,
                        mime="text/html",
                        use_container_width=True,
                        key="fin_download_report"
                    )
                    st.success("✅ Report generated! Click Download to save.")
                    st.info("📄 Report includes:\n- Applied filter settings\n- KPIs & key insights\n- 5 interactive Plotly charts\n- Works in any browser (no Python needed)")
            else:
                st.warning("⚠️ No data loaded — please upload a file first.")

        # Advisory settings
        st.markdown("### ⚙️ Advisory Settings")
        st.toggle("Show CFO Memo",             value=True,  key="fin_cfo_memo")
        st.toggle("Show Health Radar",         value=True,  key="fin_radar")
        st.toggle("Show P&L Waterfall",        value=True,  key="fin_waterfall")
        st.toggle("Show Full Analysis (v2 mode)", value=False, key="fin_full_mode")
        st.markdown("---")
        st.caption("Exalio Financial Intelligence v3.0")
        st.caption("Powered by Generative AI + Ollama")

    return df, model, ollama_url


# ──────────────────────────────────────────────────────────────
# SAMPLE DATASET
# ──────────────────────────────────────────────────────────────

def _build_sample_financial_dataset() -> pd.DataFrame:
    """Generate a realistic multi-dimensional financial dataset."""
    rng = np.random.default_rng(42)
    n = 500

    products  = ['Enterprise Suite', 'Professional Plan', 'Starter Pack', 'Add-On Module', 'Consulting']
    segments  = ['Enterprise', 'Mid-Market', 'SMB', 'Startup']
    regions   = ['North America', 'EMEA', 'APAC', 'LATAM']
    channels  = ['Direct Sales', 'Partner', 'Digital', 'Reseller']

    start_date = datetime(2023, 1, 1)
    dates = [start_date + timedelta(days=int(d)) for d in rng.integers(0, 365, n)]

    product_arr  = rng.choice(products,  n)
    segment_arr  = rng.choice(segments,  n)
    region_arr   = rng.choice(regions,   n)
    channel_arr  = rng.choice(channels,  n)

    # Revenue with seasonality + product tiers
    base_rev = {'Enterprise Suite': 45000, 'Professional Plan': 12000,
                'Starter Pack': 3000, 'Add-On Module': 5000, 'Consulting': 20000}
    revenue = np.array([base_rev[p] * (1 + rng.normal(0, 0.25)) for p in product_arr])
    revenue = np.clip(revenue, 500, None)

    # Cost = 40–70% of revenue depending on product
    cost_ratio = {'Enterprise Suite': 0.45, 'Professional Plan': 0.55,
                  'Starter Pack': 0.65, 'Add-On Module': 0.40, 'Consulting': 0.70}
    cost = np.array([rev * cost_ratio[p] * (1 + rng.normal(0, 0.1))
                     for rev, p in zip(revenue, product_arr)])
    cost = np.clip(cost, 100, None)

    profit = revenue - cost
    quantity = rng.integers(1, 50, n)
    csat = rng.choice([1,2,3,4,5], n, p=[0.05,0.08,0.15,0.42,0.30])

    df = pd.DataFrame({
        'Order_Date':        [d.strftime('%Y-%m-%d') for d in dates],
        'Product':           product_arr,
        'Customer_Segment':  segment_arr,
        'Region':            region_arr,
        'Sales_Channel':     channel_arr,
        'Revenue':           np.round(revenue, 2),
        'Cost':              np.round(cost, 2),
        'Gross_Profit':      np.round(profit, 2),
        'Units_Sold':        quantity,
        'Customer_CSAT':     csat,
    })
    df['Customer_ID'] = [f"CUST-{rng.integers(1000,9999)}" for _ in range(n)]
    return df


# ──────────────────────────────────────────────────────────────
# MIGRATED HELPER FUNCTIONS (from student_360_full_portable_v3)
# ──────────────────────────────────────────────────────────────

def create_insight_card(title: str, text: str, icon: str = "💡"):
    """Create a styled insight card (migrated from student_360)."""
    st.markdown(f"""
    <div style="background:linear-gradient(135deg,rgba(99,102,241,0.1),rgba(16,185,129,0.1));
                border:1px solid #334155;border-left:4px solid #6366f1;
                border-radius:12px;padding:20px;margin:12px 0;">
        <div style="font-weight:700;font-size:0.95rem;color:#818cf8;margin-bottom:8px;">
            {icon} {title}
        </div>
        <div style="font-size:0.88rem;color:#cbd5e1;line-height:1.7;">{text}</div>
    </div>
    """, unsafe_allow_html=True)


def create_alert(message: str, alert_type: str = "info"):
    """Create a styled alert box (migrated from student_360)."""
    icons   = {"success": "✅", "warning": "⚠️", "danger": "🚨", "info": "ℹ️"}
    colors  = {"success": "#10b981", "warning": "#f59e0b", "danger": "#ef4444", "info": "#3b82f6"}
    icon    = icons.get(alert_type, "ℹ️")
    color   = colors.get(alert_type, "#3b82f6")
    st.markdown(f"""
    <div style="background:rgba(0,0,0,0.15);border-left:4px solid {color};
                border-radius:6px;padding:12px 16px;margin:8px 0;
                font-size:0.88rem;color:#e2e8f0;">
        {icon} {message}
    </div>
    """, unsafe_allow_html=True)


def safe_column_access(dataframe: pd.DataFrame, column_name: str, default_value=0) -> pd.Series:
    """Safely access a dataframe column; return a default Series if missing (migrated from student_360)."""
    if column_name in dataframe.columns:
        return dataframe[column_name]
    return pd.Series([default_value] * len(dataframe), index=dataframe.index)


def apply_universal_column_mapping(df: pd.DataFrame):
    """
    Apply universal column mapping to handle different CSV file formats.
    Maps various column name formats to a standardized format.
    Migrated from student_360_full_portable_v3.
    Returns (mapped_df, mapping_log).
    """
    column_mappings = {
        # ════════════════════════════════════════════════════════════════════
        # UNIVERSAL COLUMN CATALOG v2
        # Covers: Student_360_View (119 cols) + STUDENT_360_VIEW (51 cols)
        # All aliases normalised to a single canonical field name.
        # ════════════════════════════════════════════════════════════════════

        # ── Core identifiers ──────────────────────────────────────────────
        'student_id':                    ['student_id', 'Student_ID', 'StudentID', 'ID',
                                          'student_number', 'learner_id', 'person_id'],
        'emirates_id':                   ['emirates_id', 'National_ID', 'national_id',
                                          'NationalID', 'eid'],
        'passport_number':               ['passport_number', 'PassportNumber', 'passport_no'],
        'family_book_number':            ['family_book_number', 'FamilyBookNumber'],
        'assignment_id':                 ['assignment_id', 'AssignmentID'],
        'application_number':            ['application_number', 'ApplicationNumber', 'app_no'],

        # ── Personal information ───────────────────────────────────────────
        'first_name_en':                 ['first_name_en', 'first_name', 'FirstName',
                                          'first_name_english', 'fname'],
        'last_name_en':                  ['last_name_en', 'last_name', 'LastName',
                                          'last_name_english', 'lname', 'surname'],
        'first_name_ar':                 ['first_name_ar', 'first_name_arabic', 'FirstNameArabic'],
        'last_name_ar':                  ['last_name_ar', 'last_name_arabic', 'LastNameArabic'],
        'middle_name':                   ['middle_name', 'MiddleName', 'middle_name_en'],
        'gender':                        ['gender', 'Gender', 'sex', 'Sex'],
        'date_of_birth':                 ['date_of_birth', 'dob', 'DOB', 'BirthDate',
                                          'birth_date', 'birthdate'],
        'age_at_first_enrollment':       ['age_at_first_enrollment', 'age', 'Age',
                                          'age_at_admission'],
        'marital_status':                ['marital_status', 'MaritalStatus', 'civil_status'],
        'country_of_birth':              ['country_of_birth', 'birth_country', 'CountryOfBirth'],
        'permanent_address':             ['permanent_address', 'address', 'home_address',
                                          'Address'],

        # ── Contact information ────────────────────────────────────────────
        'email_address':                 ['email_address', 'university_email', 'personal_email',
                                          'email', 'Email', 'EmailAddress'],
        'phone_number':                  ['phone_number', 'phone', 'Phone', 'PhoneNumber',
                                          'mobile', 'mobile_number'],
        'emergency_contact_name':        ['emergency_contact_name', 'EmergencyContactName'],
        'emergency_contact_phone':       ['emergency_contact_phone', 'EmergencyContactPhone'],
        'emergency_contact_relationship':['emergency_contact_relationship',
                                          'EmergencyContactRelationship'],

        # ── Nationality & citizenship ──────────────────────────────────────
        'nationality':                   ['nationality', 'Nationality', 'nationality_code',
                                          'country', 'NationalityCode'],
        'home_country':                  ['home_country', 'country_of_origin', 'HomeCountry'],
        'citizenship_type':              ['Citizenship_Type', 'citizenship_type', 'citizen_type'],
        'is_international':              ['is_international', 'international_student',
                                          'IsInternational'],

        # ── Visa & immigration ─────────────────────────────────────────────
        'visa_status':                   ['visa_status', 'VisaStatus', 'visa_type', 'VisaType'],
        'visa_expiry_date':              ['visa_expiry_date', 'VisaExpiry', 'visa_expiry'],
        'visa_sponsor':                  ['visa_sponsor', 'VisaSponsor', 'sponsor'],
        'work_permit_status':            ['work_permit_status', 'WorkPermitStatus'],
        'residence_permit_number':       ['residence_permit_number', 'ResidencePermit',
                                          'residence_permit'],

        # ── Academic GPA & grades ──────────────────────────────────────────
        'cumulative_gpa':                ['cumulative_gpa', 'gpa', 'GPA', 'CGPA',
                                          'CumulativeGPA', 'cgpa'],
        'term_gpa':                      ['term_gpa', 'TermGPA', 'semester_gpa', 'SemesterGPA'],
        'major_gpa':                     ['major_gpa', 'MajorGPA'],
        'grade_point':                   ['grade_point', 'GradePoint', 'grade_points'],
        'grade_points_earned':           ['grade_points_earned', 'GradePointsEarned'],
        'quality_points':                ['quality_points', 'QualityPoints'],
        'gpa_trend':                     ['gpa_trend', 'GPATrend', 'gpa_direction'],
        'is_dfw_grade':                  ['is_dfw_grade', 'dfw_grade', 'IsDFW',
                                          'failed_or_withdrawn'],
        'is_passing_grade':              ['is_passing_grade', 'passing', 'IsPassingGrade'],

        # ── Credits & academic progress ────────────────────────────────────
        'credits_attempted':             ['credits_attempted', 'total_credits_earned', 'credits',
                                          'TotalCredits', 'credit_hours_attempted'],
        'credit_hours':                  ['credit_hours', 'CreditHours', 'credit_units'],
        'total_courses_completed':       ['total_courses_completed', 'courses_completed',
                                          'CoursesCompleted'],
        'courses_failed_count':          ['courses_failed_count', 'CoursesFailed',
                                          'failed_courses'],
        'courses_withdrawn_count':       ['courses_withdrawn_count', 'CoursesWithdrawn',
                                          'withdrawn_courses'],
        'courses_repeated_count':        ['courses_repeated_count', 'CoursesRepeated',
                                          'repeated_courses'],
        'credit_completion_rate':        ['credit_completion_rate', 'CreditCompletionRate',
                                          'completion_rate'],
        'degree_progress_pct':           ['degree_progress_pct', 'degree_progress_category',
                                          'DegreeProgress', 'progress_percentage',
                                          'degree_completion_pct'],
        'academic_standing':             ['academic_standing', 'AcademicStanding', 'standing'],
        'terms_enrolled':                ['terms_enrolled', 'TermsEnrolled', 'semesters_enrolled'],
        'time_to_degree_months':         ['time_to_degree_months', 'TimeToDegree',
                                          'months_to_degree'],
        'registered_billing_hours':      ['Registered_Billing_Hours', 'registered_billing_hours',
                                          'billing_hours', 'billing_credit_hours'],

        # ── Enrollment ────────────────────────────────────────────────────
        'enrollment_enrollment_status':  ['enrollment_enrollment_status', 'Student_Status',
                                          'student_status', 'enrollment_status', 'Status',
                                          'EnrollmentStatus', 'student_enrollment_status'],
        'enrollment_type':               ['enrollment_type', 'academic_level', 'AcademicLevel',
                                          'student_type', 'enrollment_category'],
        'enrollment_date':               ['enrollment_date', 'Admission_Date', 'admission_date',
                                          'start_date', 'EnrollmentDate'],
        'last_enrollment_term':          ['last_enrollment_term', 'LastEnrollmentTerm',
                                          'last_term', 'current_term'],
        'registration_status':           ['registration_status', 'RegistrationStatus',
                                          'reg_status'],
        'application_status':            ['application_status', 'ApplicationStatus', 'app_status'],
        'application_type':              ['application_type', 'ApplicationType', 'app_type'],

        # ── Cohort & academic calendar ────────────────────────────────────
        'cohort_year':                   ['cohort_year', 'Cohort', 'cohort', 'CohortYear',
                                          'admission_year', 'intake_year'],
        'cohort_term':                   ['cohort_term', 'cohort_semester', 'admission_term',
                                          'intake_term'],
        'academic_year':                 ['academic_year', 'AcademicYear', 'year'],
        'academic_term':                 ['academic_term', 'AcademicTerm', 'term', 'semester'],
        'section_number':                ['section_number', 'SectionNumber', 'section', 'sec'],

        # ── Academic program ──────────────────────────────────────────────
        'academic_program':              ['academic_program', 'program', 'Program',
                                          'degree_program', 'programme'],
        'major':                         ['major', 'Major', 'primary_major', 'field_of_study'],
        'minor':                         ['minor', 'Minor'],
        'concentration':                 ['Concentration', 'concentration', 'specialization',
                                          'track'],
        'college':                       ['college', 'College', 'school', 'faculty'],
        'department':                    ['department', 'Department', 'dept'],

        # ── Graduation ────────────────────────────────────────────────────
        'expected_graduation':           ['enrollment_expected_graduation_date',
                                          'expected_graduation', 'ExpectedGraduation',
                                          'graduation_target_date'],
        'actual_graduation_date':        ['enrollment_actual_graduation_date',
                                          'actual_graduation_date', 'graduation_date',
                                          'GraduationDate'],
        'graduation_honors':             ['graduation_honors', 'GraduationHonors', 'honors',
                                          'honours'],
        'graduation_probability':        ['graduation_probability', 'GraduationProbability',
                                          'grad_prob'],

        # ── Financial — tuition & fees ────────────────────────────────────
        'enrollment_tuition_amount':     ['enrollment_tuition_amount', 'Tuition_Fee_Total',
                                          'tuition_fee', 'tuition', 'TuitionAmount',
                                          'tuition_amount', 'total_tuition'],
        'current_term_charges':          ['Current_Term_Charges', 'current_term_charges',
                                          'term_charges', 'semester_charges'],
        'estimated_annual_cost':         ['Estimated_Annual_Cost', 'estimated_annual_cost',
                                          'annual_cost', 'cost_of_attendance'],
        'fee_paid':                      ['fee_paid', 'fees_paid', 'FeePaid'],

        # ── Financial — aid & scholarships ───────────────────────────────
        'financial_aid_monetary_amount': ['financial_aid_monetary_amount', 'Financial_Aid_Awarded',
                                          'Financial_Aid_Disbursed', 'aid_amount',
                                          'financial_aid', 'aid_disbursed'],
        'financial_aid_transaction_date':['financial_aid_transaction_date', 'aid_date',
                                          'FinancialAidDate'],
        'scholarship_type':              ['Scholarship_Type', 'scholarship_type', 'aid_type',
                                          'ScholarshipType'],
        'scholarship_amount':            ['Scholarship_Amount', 'scholarship_amount',
                                          'ScholarshipAmount'],
        'sponsorship_type':              ['Sponsorship_Type', 'sponsorship_type',
                                          'SponsorshipType'],
        'sponsor_name':                  ['Sponsor_Name', 'sponsor_name', 'SponsorName',
                                          'sponsoring_entity'],
        'sponsorship_coverage_pct':      ['Sponsorship_Coverage_Pct', 'sponsorship_coverage_pct',
                                          'coverage_pct', 'sponsor_coverage'],
        'unmet_financial_need':          ['Unmet_Financial_Need', 'unmet_financial_need',
                                          'unmet_need'],
        'financial_stress_indicator':    ['financial_stress_indicator', 'FinancialStress',
                                          'financial_stress'],
        'financial_hold_status':         ['Financial_Hold_Status', 'financial_hold_status',
                                          'hold_status', 'account_hold'],

        # ── Financial — payments & balances ──────────────────────────────
        'total_payments_ytd':            ['Total_Payments_YTD', 'total_payments_ytd',
                                          'payments_ytd', 'total_paid', 'YTDPayments'],
        'last_payment_date':             ['Last_Payment_Date', 'last_payment_date',
                                          'LastPaymentDate', 'payment_date'],
        'last_payment_amount':           ['Last_Payment_Amount', 'last_payment_amount',
                                          'LastPaymentAmount'],
        'payment_plan_status':           ['Payment_Plan_Status', 'payment_plan_status',
                                          'PaymentPlanStatus', 'payment_plan'],
        'payment_method_primary':        ['Payment_Method_Primary', 'payment_method_primary',
                                          'payment_method', 'PaymentMethod'],
        'account_balance':               ['Account_Balance', 'account_balance', 'AccountBalance'],
        'past_due_balance':              ['Past_Due_Balance', 'past_due_balance', 'PastDue',
                                          'overdue_balance'],
        'balance_due':                   ['balance_due', 'BalanceDue', 'outstanding_balance',
                                          'amount_due'],
        'refund_amount_pending':         ['Refund_Amount_Pending', 'refund_amount_pending',
                                          'refund_pending', 'pending_refund'],

        # ── Housing ───────────────────────────────────────────────────────
        'room_number':                   ['room_number', 'RoomNumber', 'room'],
        'rent_amount':                   ['rent_amount', 'RentAmount', 'monthly_rent'],
        'rent_paid':                     ['rent_paid', 'RentPaid', 'housing_payment'],
        'housing_status':                ['housing_status', 'occupancy_status',
                                          'has_campus_housing', 'OccupancyStatus'],
        'has_meal_plan':                 ['has_meal_plan', 'meal_plan', 'MealPlan'],

        # ── Attendance & academic activity ────────────────────────────────
        'attendance_rate':               ['attendance_rate', 'attendance_percentage',
                                          'Attendance', 'AttendanceRate'],
        'attendance_count':              ['attendance_count', 'AttendanceCount',
                                          'classes_attended'],
        'missed_classes_count':          ['missed_classes_count', 'MissedClasses',
                                          'absences', 'absent_count'],
        'assignment_submission_rate':    ['assignment_submission_rate', 'SubmissionRate',
                                          'submission_rate'],
        'last_activity_date':            ['last_activity_date', 'LastActivity',
                                          'last_active_date'],

        # ── Student success & risk ────────────────────────────────────────
        'is_at_risk':                    ['is_at_risk', 'risk_category', 'at_risk_flag',
                                          'AtRisk', 'risk_flag'],
        'stop_out_risk_flag':            ['stop_out_risk_flag', 'StopOutRisk', 'dropout_risk',
                                          'stop_out_flag'],
        'retention_probability':         ['retention_probability', 'RetentionProbability',
                                          'retention_prob'],
        'intervention_count':            ['intervention_count', 'InterventionCount',
                                          'interventions'],
        'engagement_score':              ['engagement_score', 'EngagementScore'],

        # ── Advisor & support services ────────────────────────────────────
        'advisor_meeting_count':         ['advisor_meeting_count', 'AdvisorMeetings',
                                          'advisor_meetings'],
        'last_advisor_meeting_date':     ['last_advisor_meeting_date', 'LastAdvisorMeeting',
                                          'advisor_last_visit'],
        'counseling_visits_count':       ['counseling_visits_count', 'CounselingVisits',
                                          'counseling_sessions'],
        'health_center_visits_count':    ['health_center_visits_count', 'HealthCenterVisits',
                                          'clinic_visits'],
        'health_insurance_status':       ['health_insurance_status', 'HealthInsurance',
                                          'insurance_status'],
        'career_center_visits_count':    ['career_center_visits_count', 'CareerCenterVisits'],
        'has_disability_accommodation':  ['has_disability_accommodation',
                                          'disability_accommodation', 'HasAccommodation'],
        'accommodation_types':           ['accommodation_types', 'AccommodationTypes',
                                          'disability_type'],
        'has_conduct_violation':         ['has_conduct_violation', 'conduct_violation',
                                          'HasViolation'],
        'grievance_count':               ['grievance_count', 'GrievanceCount', 'complaints'],

        # ── Engagement & campus life ──────────────────────────────────────
        'library_visits_count':          ['library_visits_count', 'LibraryVisits',
                                          'library_visits'],
        'clubs_joined_count':            ['clubs_joined_count', 'ClubsJoined', 'clubs'],
        'leadership_role':               ['leadership_role', 'LeadershipRole', 'leadership'],
        'events_attended_count':         ['events_attended_count', 'EventsAttended', 'events'],
        'recreation_center_visits':      ['recreation_center_visits', 'RecreationVisits',
                                          'gym_visits'],
        'has_campus_job':                ['has_campus_job', 'campus_job', 'HasCampusJob'],
        'transport_service_enrolled':    ['transport_service_enrolled', 'TransportEnrolled',
                                          'uses_transport'],

        # ── Career & post-graduation ──────────────────────────────────────
        'career_goal':                   ['career_goal', 'CareerGoal', 'career_interest'],
        'career_readiness_score':        ['career_readiness_score', 'CareerReadiness',
                                          'career_score'],
        'job_placement_status':          ['job_placement_status', 'JobPlacement',
                                          'employment_status', 'PlacementStatus'],
        'graduate_school_interest':      ['graduate_school_interest', 'GradSchoolInterest',
                                          'postgrad_interest'],
        'has_completed_internship':      ['has_completed_internship', 'internship_completed',
                                          'HasInternship'],
        'internship_count':              ['internship_count', 'InternshipCount', 'internships'],

        # ── First generation ──────────────────────────────────────────────
        'is_first_generation':           ['is_first_generation', 'first_generation',
                                          'FirstGeneration', 'first_gen'],
    }
    mapped_df    = df.copy()
    mapping_log  = []
    for standard_name, possible_names in column_mappings.items():
        if standard_name in mapped_df.columns:
            continue
        for variant in possible_names:
            if variant in mapped_df.columns and variant != standard_name:
                mapped_df[standard_name] = mapped_df[variant]
                mapping_log.append(f"Mapped '{variant}' → '{standard_name}'")
                break
    # Prefer university_email over personal_email for email_address
    if 'email_address' not in mapped_df.columns:
        if 'university_email' in df.columns:
            mapped_df['email_address'] = df['university_email']
            mapping_log.append("Mapped 'university_email' → 'email_address'")
        elif 'personal_email' in df.columns:
            mapped_df['email_address'] = df['personal_email']
            mapping_log.append("Mapped 'personal_email' → 'email_address'")
    return mapped_df, mapping_log


def generate_html_report(filtered_df: pd.DataFrame, filter_summary: str) -> str:
    """
    Generate a standalone interactive HTML report from the current filtered dataframe.
    Migrated from student_360_full_portable_v3. Adapted for the financial app.
    Returns the full HTML string.
    """
    from datetime import datetime as _dt

    _has_sid     = 'student_id' in filtered_df.columns
    _has_gpa     = 'cumulative_gpa' in filtered_df.columns
    _has_nat     = 'nationality' in filtered_df.columns
    _has_status  = 'enrollment_enrollment_status' in filtered_df.columns
    _has_aid     = 'financial_aid_monetary_amount' in filtered_df.columns
    _has_tuition = 'enrollment_tuition_amount' in filtered_df.columns
    _has_cohort  = 'cohort_year' in filtered_df.columns

    total_students = int(filtered_df['student_id'].nunique()) if _has_sid else len(filtered_df)
    avg_gpa        = round(filtered_df['cumulative_gpa'].mean(), 2) if _has_gpa else 0
    at_risk        = int(len(filtered_df[filtered_df['cumulative_gpa'] < 2.5])) if _has_gpa else 0
    at_risk_pct    = round(at_risk / max(len(filtered_df), 1) * 100, 1)
    uae_nationals  = int(len(filtered_df[filtered_df['nationality'] == 'AE'])) if _has_nat else 0
    uae_pct        = round(uae_nationals / max(len(filtered_df), 1) * 100, 1)
    active_st      = int(len(filtered_df[filtered_df['enrollment_enrollment_status'] == 'Active'])) if _has_status else 0
    total_aid      = float(filtered_df['financial_aid_monetary_amount'].sum()) if _has_aid else 0
    total_tuition  = float(filtered_df['enrollment_tuition_amount'].sum()) if _has_tuition else 0
    aid_pct        = round(total_aid / max(total_tuition, 1) * 100, 1)
    report_date    = _dt.now().strftime("%Y-%m-%d %H:%M:%S")

    # ── Chart 1: GPA Distribution ──
    if _has_gpa:
        import plotly.graph_objects as _go
        _fig1 = _go.Figure()
        _fig1.add_trace(_go.Histogram(x=filtered_df['cumulative_gpa'], nbinsx=30,
                                      marker=dict(color='#6366f1'), name='GPA Distribution'))
        _fig1.add_vline(x=avg_gpa, line_dash="dash", line_color="#10b981",
                        annotation_text=f"Mean: {avg_gpa:.2f}")
        _fig1.update_layout(title="GPA Distribution", xaxis_title="Cumulative GPA",
                            yaxis_title="Students", template="plotly_dark", height=400)
        _chart1_json = _fig1.to_json()
    else:
        _chart1_json = '{}'

    # ── Chart 2: Enrollment Status ──
    if _has_status:
        _enc = filtered_df['enrollment_enrollment_status'].value_counts()
        _fig2 = _go.Figure(data=[_go.Pie(labels=_enc.index, values=_enc.values, hole=0.4,
                                          marker=dict(colors=['#10b981', '#6366f1', '#f59e0b', '#ef4444']))])
        _fig2.update_layout(title="Enrollment Status Distribution", template="plotly_dark", height=400)
        _chart2_json = _fig2.to_json()
    else:
        _chart2_json = '{}'

    # ── Chart 3: Top 10 Nationalities ──
    if _has_nat:
        _nc = filtered_df['nationality'].value_counts().head(10)
        _fig3 = _go.Figure(data=[_go.Bar(x=_nc.values, y=_nc.index, orientation='h',
                                          marker=dict(color='#6366f1'))])
        _fig3.update_layout(title="Top 10 Nationalities", xaxis_title="Students",
                            template="plotly_dark", height=400)
        _chart3_json = _fig3.to_json()
    else:
        _chart3_json = '{}'

    # ── Chart 4: Financial Aid vs GPA ──
    if _has_aid and _has_gpa:
        _fig4 = _go.Figure(data=[_go.Scatter(
            x=filtered_df['financial_aid_monetary_amount'], y=filtered_df['cumulative_gpa'],
            mode='markers',
            marker=dict(size=5, color=filtered_df['cumulative_gpa'],
                        colorscale='RdYlGn', showscale=True),
            text=filtered_df['student_id'] if _has_sid else None
        )])
        _fig4.update_layout(title="Financial Aid vs GPA", xaxis_title="Aid Amount (AED)",
                            yaxis_title="Cumulative GPA", template="plotly_dark", height=400)
        _chart4_json = _fig4.to_json()
    else:
        _chart4_json = '{}'

    # ── Chart 5: Average GPA by Cohort ──
    if _has_cohort and _has_gpa:
        _cohort_gpa = filtered_df.groupby('cohort_year')['cumulative_gpa'].mean().reset_index()
        _fig5 = _go.Figure(data=[_go.Bar(
            x=_cohort_gpa['cohort_year'], y=_cohort_gpa['cumulative_gpa'],
            marker=dict(color=_cohort_gpa['cumulative_gpa'], colorscale='RdYlGn', showscale=True),
            text=[f"{v:.2f}" for v in _cohort_gpa['cumulative_gpa']], textposition='outside'
        )])
        _fig5.update_layout(title="Average GPA by Cohort Year", xaxis_title="Cohort Year",
                            yaxis_title="Avg GPA", template="plotly_dark", height=400)
        _chart5_json = _fig5.to_json()
    else:
        _chart5_json = '{}'

    high_perf_pct = round(len(filtered_df[filtered_df['cumulative_gpa'] >= 3.5]) / max(len(filtered_df), 1) * 100, 1) if _has_gpa else 0
    uae_gpa = round(filtered_df[filtered_df['nationality'] == 'AE']['cumulative_gpa'].mean(), 2) if (_has_nat and _has_gpa) else 0
    aided_count = int((filtered_df['financial_aid_monetary_amount'] > 0).sum()) if _has_aid else 0

    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Exalio Financial Intelligence - Interactive Report</title>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <style>
        body {{
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', sans-serif;
            background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 50%, #0f172a 100%);
            color: #f1f5f9; margin: 0; padding: 20px;
        }}
        .container {{ max-width: 1400px; margin: 0 auto; }}
        .header {{
            background: linear-gradient(135deg, rgba(99,102,241,0.2), rgba(16,185,129,0.2));
            border: 1px solid #334155; border-radius: 12px; padding: 30px;
            margin-bottom: 30px; text-align: center;
        }}
        .header h1 {{
            background: linear-gradient(135deg, #818cf8, #34d399);
            -webkit-background-clip: text; -webkit-text-fill-color: transparent;
            font-size: 2.2rem; margin: 0 0 10px 0;
        }}
        .header .subtitle {{ color: #94a3b8; font-size: 1rem; margin: 4px 0; }}
        .kpi-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px,1fr)); gap: 20px; margin-bottom: 30px; }}
        .kpi-card {{
            background: linear-gradient(135deg, rgba(99,102,241,0.1), rgba(16,185,129,0.1));
            border: 1px solid #334155; border-radius: 12px; padding: 20px; text-align: center;
        }}
        .kpi-value {{
            font-size: 2rem; font-weight: 700;
            background: linear-gradient(135deg, #818cf8, #34d399);
            -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 10px;
        }}
        .kpi-label {{ color: #94a3b8; font-size: 0.9rem; }}
        .section {{
            background: rgba(30,41,59,0.5); border: 1px solid #334155;
            border-radius: 12px; padding: 25px; margin-bottom: 25px;
        }}
        .section h2 {{ color: #818cf8; margin-top: 0; font-size: 1.5rem; }}
        .chart-container {{
            margin: 20px 0; background: rgba(15,23,42,0.8);
            border-radius: 8px; padding: 15px;
        }}
        .filter-info {{
            background: rgba(99,102,241,0.1); border-left: 4px solid #6366f1;
            padding: 15px; margin-bottom: 20px; border-radius: 4px;
        }}
        .filter-info h3 {{ margin-top: 0; color: #818cf8; }}
        .filter-info ul {{ margin: 10px 0; padding-left: 20px; }}
        .filter-info li {{ color: #e2e8f0; margin: 5px 0; }}
        .insight-box {{
            background: linear-gradient(135deg, rgba(16,185,129,0.1), rgba(99,102,241,0.1));
            border: 1px solid #10b981; border-radius: 8px; padding: 20px; margin: 20px 0;
        }}
        .insight-box h4 {{ color: #10b981; margin-top: 0; }}
        .insight-box p {{ color: #e2e8f0; line-height: 1.6; }}
        .footer {{
            text-align: center; color: #64748b; padding: 20px;
            margin-top: 40px; border-top: 1px solid #334155;
        }}
    </style>
</head>
<body>
<div class="container">
    <div class="header">
        <h1>💰 Exalio Financial Intelligence — Interactive Report</h1>
        <div class="subtitle">Executive Dashboard | Financial Analytics</div>
        <div class="subtitle">Generated: {report_date}</div>
    </div>

    <div class="filter-info">
        <h3>📋 Report Filters Applied</h3>
        <ul>{filter_summary}</ul>
    </div>

    <div class="section">
        <h2>🎯 Key Performance Indicators</h2>
        <div class="kpi-grid">
            <div class="kpi-card"><div class="kpi-value">{total_students:,}</div><div class="kpi-label">Total Records</div></div>
            <div class="kpi-card"><div class="kpi-value">{avg_gpa:.2f}</div><div class="kpi-label">Average GPA</div></div>
            <div class="kpi-card"><div class="kpi-value">{uae_nationals}</div><div class="kpi-label">UAE Nationals ({uae_pct:.1f}%)</div></div>
            <div class="kpi-card"><div class="kpi-value">{at_risk}</div><div class="kpi-label">At-Risk Students ({at_risk_pct:.1f}%)</div></div>
            <div class="kpi-card"><div class="kpi-value">{active_st}</div><div class="kpi-label">Active Students</div></div>
            <div class="kpi-card"><div class="kpi-value">AED {total_aid/1e6:.1f}M</div><div class="kpi-label">Total Financial Aid</div></div>
        </div>
    </div>

    <div class="section">
        <h2>💡 Key Insights</h2>
        <div class="insight-box">
            <h4>🎓 Academic Performance</h4>
            <p>The dataset maintains an average GPA of <strong>{avg_gpa:.2f}</strong>, with {high_perf_pct:.1f}% of students
            achieving high performance (GPA ≥ 3.5). {at_risk_pct:.1f}% of students are currently at risk (GPA &lt; 2.5),
            requiring targeted intervention strategies.</p>
        </div>
        <div class="insight-box">
            <h4>🇦🇪 UAE National Representation</h4>
            <p>UAE nationals represent {uae_pct:.1f}% of the dataset ({uae_nationals} students), supporting Emiratisation
            objectives. UAE students maintain an average GPA of {uae_gpa:.2f}.</p>
        </div>
        <div class="insight-box">
            <h4>💰 Financial Support Impact</h4>
            <p>The institution has invested AED {total_aid/1e6:.1f}M in financial aid, benefiting {aided_count:,} students.
            Financial aid coverage represents {aid_pct:.1f}% of total tuition revenue.</p>
        </div>
    </div>

    <div class="section">
        <h2>📈 Academic Performance Analysis</h2>
        <div class="chart-container" id="chart-gpa"></div>
    </div>
    <div class="section">
        <h2>👥 Student Demographics</h2>
        <div class="chart-container" id="chart-enrollment"></div>
        <div class="chart-container" id="chart-nationality"></div>
    </div>
    <div class="section">
        <h2>💰 Financial Aid Analysis</h2>
        <div class="chart-container" id="chart-aid"></div>
    </div>
    <div class="section">
        <h2>📊 Cohort Performance</h2>
        <div class="chart-container" id="chart-cohort"></div>
    </div>

    <div class="footer">
        <p>💰 Exalio Financial Intelligence v3.0 | Interactive Data Analytics Platform</p>
        <p>This report was generated from the Exalio Financial Intelligence application</p>
        <p>Report includes {total_students:,} records with applied filters</p>
    </div>
</div>

<script>
    var gpa_data = {_chart1_json};
    if (gpa_data && gpa_data.data) Plotly.newPlot('chart-gpa', gpa_data.data, gpa_data.layout);

    var enrollment_data = {_chart2_json};
    if (enrollment_data && enrollment_data.data) Plotly.newPlot('chart-enrollment', enrollment_data.data, enrollment_data.layout);

    var nationality_data = {_chart3_json};
    if (nationality_data && nationality_data.data) Plotly.newPlot('chart-nationality', nationality_data.data, nationality_data.layout);

    var aid_data_chart = {_chart4_json};
    if (aid_data_chart && aid_data_chart.data) Plotly.newPlot('chart-aid', aid_data_chart.data, aid_data_chart.layout);

    var cohort_data = {_chart5_json};
    if (cohort_data && cohort_data.data) Plotly.newPlot('chart-cohort', cohort_data.data, cohort_data.layout);
</script>
</body>
</html>"""
    return html


def apply_filters(df: pd.DataFrame) -> pd.DataFrame:
    """
    Apply sidebar filter session_state values to the dataframe.
    Mirrors student_360's filter application logic.
    Returns filtered dataframe (or original df if no relevant filters are set).
    """
    if df is None or len(df) == 0:
        return df

    fdf = df.copy()
    ss  = st.session_state

    # ── Student search ──
    _search = ss.get('fin_student_search', '').strip()
    if _search:
        _mask = pd.Series([False] * len(fdf), index=fdf.index)
        for _col in ['student_id', 'first_name_en', 'last_name_en', 'email_address']:
            if _col in fdf.columns:
                _mask |= fdf[_col].astype(str).str.contains(_search, case=False, na=False)
        fdf = fdf[_mask]

    # ── Enrollment status ──
    if 'enrollment_enrollment_status' in fdf.columns:
        _sel = ss.get('fin_filter_enroll_status')
        if _sel:
            fdf = fdf[fdf['enrollment_enrollment_status'].isin(_sel)]

    # ── Enrollment type ──
    if 'enrollment_type' in fdf.columns:
        _sel = ss.get('fin_filter_enroll_type')
        if _sel:
            fdf = fdf[fdf['enrollment_type'].isin(_sel)]

    # ── Cohort year ──
    if 'cohort_year' in fdf.columns:
        _sel = ss.get('fin_filter_cohort')
        if _sel:
            fdf = fdf[fdf['cohort_year'].isin(_sel)]

    # ── Nationality ──
    if 'nationality' in fdf.columns:
        _sel = ss.get('fin_filter_nationality')
        if _sel:
            fdf = fdf[fdf['nationality'].isin(_sel)]
        # UAE national filter
        _uae = ss.get('fin_filter_uae_national', 'All Students')
        if _uae == 'UAE Nationals Only':
            fdf = fdf[fdf['nationality'] == 'AE']
        elif _uae == 'International Students Only':
            fdf = fdf[fdf['nationality'] != 'AE']

    # ── Gender ──
    if 'gender' in fdf.columns:
        _sel = ss.get('fin_filter_gender')
        if _sel:
            fdf = fdf[fdf['gender'].isin(_sel)]

    # ── GPA range ──
    if 'cumulative_gpa' in fdf.columns:
        _gpa = ss.get('fin_filter_gpa', (0.0, 4.0))
        fdf = fdf[(fdf['cumulative_gpa'] >= _gpa[0]) & (fdf['cumulative_gpa'] <= _gpa[1])]

        # Academic Risk Level
        _risk = ss.get('fin_filter_risk_level',
                       ['High Performer (3.5+)', 'Mid Performer (2.5-3.5)', 'At Risk (<2.5)'])
        if _risk and len(_risk) < 3:
            _conditions = []
            if 'High Performer (3.5+)' in _risk:
                _conditions.append(fdf['cumulative_gpa'] >= 3.5)
            if 'Mid Performer (2.5-3.5)' in _risk:
                _conditions.append((fdf['cumulative_gpa'] >= 2.5) & (fdf['cumulative_gpa'] < 3.5))
            if 'At Risk (<2.5)' in _risk:
                _conditions.append(fdf['cumulative_gpa'] < 2.5)
            if _conditions:
                from functools import reduce
                import operator as _op
                fdf = fdf[reduce(_op.or_, _conditions)]

    # ── Financial aid ──
    if 'financial_aid_monetary_amount' in fdf.columns:
        _aid_s = ss.get('fin_filter_aid_status', 'All Records')
        if _aid_s == 'With Financial Aid':
            fdf = fdf[fdf['financial_aid_monetary_amount'] > 0]
        elif _aid_s == 'Without Financial Aid':
            fdf = fdf[fdf['financial_aid_monetary_amount'] == 0]
        _aid_r = ss.get('fin_filter_aid_range')
        if _aid_r:
            fdf = fdf[(fdf['financial_aid_monetary_amount'] >= _aid_r[0]) &
                      (fdf['financial_aid_monetary_amount'] <= _aid_r[1])]

    # ── Housing ──
    if 'room_number' in fdf.columns:
        _hous = ss.get('fin_filter_housing', 'All Records')
        if _hous == 'On-Campus':
            fdf = fdf[fdf['room_number'].notna()]
        elif _hous == 'Off-Campus':
            fdf = fdf[fdf['room_number'].isna()]

    # ── First generation ──
    if 'is_first_generation' in fdf.columns:
        _fg = ss.get('fin_filter_first_gen', 'All Records')
        if _fg == 'First Generation':
            fdf = fdf[fdf['is_first_generation'] == True]
        elif _fg == 'Not First Generation':
            fdf = fdf[fdf['is_first_generation'] == False]

    return fdf if len(fdf) > 0 else df  # fallback to full df if filters removed everything


# ──────────────────────────────────────────────────────────────
# MAIN TABS
# ──────────────────────────────────────────────────────────────

def render_narrative_tab(df, kpis, col_roles, advisory, narrative, model, ollama_url):
    """Tab: Financial Story — chapter-by-chapter narrative with visualizations."""

    sentiment       = narrative.get('sentiment', 'cautious')
    sent_color      = {'positive': '#10b981', 'cautious': '#f59e0b', 'concerning': '#ef4444'}.get(sentiment, '#94a3b8')
    sent_label      = {'positive': 'POSITIVE', 'cautious': 'CAUTIOUS', 'concerning': 'CONCERNING'}.get(sentiment, 'N/A')
    sent_icon       = {'positive': '📈', 'cautious': '⚠️', 'concerning': '🔴'}.get(sentiment, '📊')

    rev     = kpis.get('total_revenue', 0) or 0
    cost    = kpis.get('total_cost',    0) or 0
    profit  = kpis.get('total_profit',  0) or 0
    gm_pct  = kpis.get('gross_margin_pct', _pct(profit, max(rev, 1)))
    chapters = narrative.get('chapters', [])

    # ── HEADER BANNER ────────────────────────────────────────────────────────
    key_sents = narrative.get('key_sentences', [])
    key_html  = " &nbsp;·&nbsp; ".join(f"<span style='color:#e2e8f0;'>{s}</span>" for s in key_sents[:3])
    st.markdown(
        f'<div style="background:linear-gradient(135deg,#0a1628,#112240);'
        f'border-left:5px solid {sent_color};border-radius:0 12px 12px 0;'
        f'padding:16px 24px;margin-bottom:24px;display:flex;align-items:center;gap:16px;flex-wrap:wrap;">'
        f'<span style="font-size:2rem;">{sent_icon}</span>'
        f'<div><div style="color:{sent_color};font-size:0.7rem;font-weight:800;letter-spacing:1.5px;'
        f'text-transform:uppercase;margin-bottom:4px;">FINANCIAL OUTLOOK — {sent_label}</div>'
        f'<div style="font-size:0.88rem;color:#94a3b8;line-height:1.6;">{key_html}</div></div>'
        '</div>',
        unsafe_allow_html=True
    )

    # ── SCORECARD ROW ─────────────────────────────────────────────────────────
    _sc_metrics = []
    if rev:   _sc_metrics.append(("💰", "Total Revenue",   f"AED {rev/1e6:.1f}M",   "#10b981"))
    if cost:  _sc_metrics.append(("💸", "Total Cost",      f"AED {cost/1e6:.1f}M",  "#ef4444"))
    if profit:_sc_metrics.append(("📊", "Net Surplus",     f"AED {profit/1e6:.1f}M","#6366f1"))
    _sc_metrics.append(("📐", "Net Margin",      f"{gm_pct:.1f}%",
                         "#10b981" if gm_pct > 30 else "#f59e0b" if gm_pct > 15 else "#ef4444"))
    if kpis.get('active_students'):
        _sc_metrics.append(("🎓", "Active Students", f"{kpis['active_students']:,}", "#3b82f6"))
    if kpis.get('avg_gpa'):
        _sc_metrics.append(("📚", "Avg GPA", f"{kpis['avg_gpa']:.2f}", "#8b5cf6"))

    _sc_html = "".join([
        f'<div style="flex:1;min-width:120px;background:rgba(255,255,255,0.03);'
        f'border-top:3px solid {c};border-radius:0 0 8px 8px;padding:10px 14px;">'
        f'<div style="color:#64748b;font-size:0.68rem;font-weight:600;letter-spacing:0.5px;text-transform:uppercase;">{lbl}</div>'
        f'<div style="color:{c};font-size:1.3rem;font-weight:800;margin-top:2px;">{val}</div>'
        f'</div>'
        for icon, lbl, val, c in _sc_metrics
    ])
    st.markdown(
        f'<div style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:24px;">{_sc_html}</div>',
        unsafe_allow_html=True
    )

    st.markdown("---")
    render_section_header("📖", "The Financial Story", "5 CHAPTERS")

    # ═════════════════════════════════════════════════════════════════════════
    # CHAPTER 1 — The Opening: Who are our students?
    # ═════════════════════════════════════════════════════════════════════════
    ch1 = next((c for c in chapters if c.get('num') == 'Chapter 1'), {})
    _c1_insight = ch1.get('insight_type', 'insight')
    _c1_icon    = '💡' if _c1_insight == 'insight' else '⚠️'
    _c1_icolor  = '#6366f1' if _c1_insight == 'insight' else '#f59e0b'

    st.markdown(
        f'<div style="display:flex;align-items:center;gap:10px;margin:16px 0 8px 0;">'
        f'<div style="background:#6366f1;color:white;font-size:1.1rem;font-weight:900;'
        f'width:36px;height:36px;border-radius:50%;display:flex;align-items:center;justify-content:center;">1</div>'
        f'<div style="color:#e2e8f0;font-size:1.1rem;font-weight:700;">{ch1.get("title","Chapter 1")}</div>'
        '</div>',
        unsafe_allow_html=True
    )
    c1_left, c1_right = st.columns([1, 1])
    with c1_left:
        st.markdown(
            f'<div style="background:rgba(255,255,255,0.02);border-radius:10px;padding:16px 18px;'
            f'border-left:3px solid {_c1_icolor};line-height:1.75;color:#cbd5e1;font-size:0.9rem;">'
            + ch1.get("body", "") +
            f'<br/><br/><span style="color:{_c1_icolor};font-weight:700;">{_c1_icon} {ch1.get("insight","")}</span>'
            '</div>',
            unsafe_allow_html=True
        )
    with c1_right:
        # Enrollment status donut — who is active vs inactive
        _status_col = 'enrollment_enrollment_status'
        if _status_col in df.columns:
            _vc = df[_status_col].value_counts()
            _fig = go.Figure(go.Pie(
                labels=list(_vc.index),
                values=list(_vc.values),
                hole=0.55,
                marker=dict(
                    colors=['#10b981','#6366f1','#f59e0b','#ef4444','#3b82f6','#8b5cf6'],
                    line=dict(color='#1e293b', width=2)
                ),
                textinfo='label+percent',
                textfont=dict(size=12, color='white', family='Arial Black'),
                hovertemplate='<b>%{label}</b><br>Students: %{value:,}<br>%{percent}<extra></extra>'
            ))
            _fig.update_layout(
                title=dict(text="Student Enrolment Status", font=dict(size=14, color='white', family='Arial Black'), x=0.5, xanchor='center'),
                paper_bgcolor='rgba(0,0,0,0)', font=dict(color='white'),
                height=320, margin=dict(l=10,r=10,t=50,b=10),
                showlegend=True,
                legend=dict(font=dict(size=10,color='white'), orientation='h', y=-0.15, x=0.5, xanchor='center')
            )
            st.plotly_chart(_fig, use_container_width=True, config={'displayModeBar': False}, key="pc_story_c1a")
        elif kpis.get('avg_gpa'):
            # GPA distribution histogram
            _gpa_s = pd.to_numeric(df.get('cumulative_gpa', pd.Series(dtype=float)), errors='coerce').dropna()
            if len(_gpa_s) > 0:
                _fig = go.Figure(go.Histogram(
                    x=_gpa_s, nbinsx=20,
                    marker=dict(color='#6366f1', opacity=0.85, line=dict(color='white', width=1)),
                    hovertemplate='GPA: %{x:.2f}<br>Students: %{y}<extra></extra>'
                ))
                _fig.add_vline(x=float(_gpa_s.mean()), line_dash='dash', line_color='#f59e0b',
                               annotation_text=f"Avg: {_gpa_s.mean():.2f}", annotation_font_color='#f59e0b')
                _fig.update_layout(
                    title=dict(text="GPA Distribution", font=dict(size=14,color='white',family='Arial Black'), x=0.5, xanchor='center'),
                    paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                    font=dict(color='white'), height=320, margin=dict(l=40,r=10,t=50,b=40),
                    xaxis=dict(title='GPA', tickfont=dict(color='white')),
                    yaxis=dict(title='Students', tickfont=dict(color='white'), gridcolor='rgba(255,255,255,0.1)')
                )
                st.plotly_chart(_fig, use_container_width=True, config={'displayModeBar': False}, key="pc_story_c1b")
        else:
            # Nationality / gender mix
            _mix_col = next((c for c in ['nationality','gender','academic_college','academic_program'] if c in df.columns), None)
            if _mix_col:
                _vc2 = df[_mix_col].value_counts().head(8)
                _fig = go.Figure(go.Bar(
                    x=list(_vc2.values), y=list(_vc2.index), orientation='h',
                    marker=dict(color='#6366f1', line=dict(color='white',width=1)),
                    text=[str(v) for v in _vc2.values], textposition='outside',
                    textfont=dict(size=11, color='white')
                ))
                _fig.update_layout(
                    title=dict(text=f"Students by {_friendly_col(_mix_col)}", font=dict(size=14,color='white',family='Arial Black'), x=0.5, xanchor='center'),
                    paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                    font=dict(color='white'), height=320, margin=dict(l=10,r=60,t=50,b=10),
                    xaxis=dict(tickfont=dict(color='white'), gridcolor='rgba(255,255,255,0.08)'),
                    yaxis=dict(tickfont=dict(size=10,color='white'), autorange='reversed')
                )
                st.plotly_chart(_fig, use_container_width=True, config={'displayModeBar': False}, key="pc_story_c1c")

    st.markdown("<br>", unsafe_allow_html=True)

    # ═════════════════════════════════════════════════════════════════════════
    # CHAPTER 2 — The Revenue Story
    # ═════════════════════════════════════════════════════════════════════════
    ch2 = next((c for c in chapters if c.get('num') == 'Chapter 2'), {})
    _c2_icolor = '#10b981' if ch2.get('insight_type','insight') == 'insight' else '#f59e0b'
    _c2_icon   = '💡' if ch2.get('insight_type','insight') == 'insight' else '⚠️'

    st.markdown(
        f'<div style="display:flex;align-items:center;gap:10px;margin:16px 0 8px 0;">'
        f'<div style="background:#10b981;color:white;font-size:1.1rem;font-weight:900;'
        f'width:36px;height:36px;border-radius:50%;display:flex;align-items:center;justify-content:center;">2</div>'
        f'<div style="color:#e2e8f0;font-size:1.1rem;font-weight:700;">{ch2.get("title","Chapter 2")}</div>'
        '</div>',
        unsafe_allow_html=True
    )
    c2_left, c2_right = st.columns([1, 1])
    with c2_left:
        st.markdown(
            f'<div style="background:rgba(255,255,255,0.02);border-radius:10px;padding:16px 18px;'
            f'border-left:3px solid {_c2_icolor};line-height:1.75;color:#cbd5e1;font-size:0.9rem;">'
            + ch2.get("body", "") +
            f'<br/><br/><span style="color:{_c2_icolor};font-weight:700;">{_c2_icon} {ch2.get("insight","")}</span>'
            '</div>',
            unsafe_allow_html=True
        )
    with c2_right:
        # Tuition by enrollment type or cohort
        _tuit_col  = 'enrollment_tuition_amount'
        _etype_col = 'enrollment_type'
        _cohort_col = 'cohort_year'
        if _tuit_col in df.columns and _etype_col in df.columns:
            _t_by_e = df.groupby(_etype_col)[_tuit_col].apply(lambda x: pd.to_numeric(x, errors='coerce').sum()).sort_values(ascending=False).head(8)
            _colors_c2 = ['#10b981','#3b82f6','#6366f1','#f59e0b','#ef4444','#8b5cf6','#ec4899','#14b8a6']
            _fig = go.Figure(go.Bar(
                x=list(_t_by_e.index),
                y=[v/1e6 for v in _t_by_e.values],
                marker=dict(color=_colors_c2[:len(_t_by_e)], line=dict(color='white',width=1)),
                text=[f"AED {v/1e6:.1f}M" for v in _t_by_e.values],
                textposition='outside', textfont=dict(size=11,color='white',family='Arial Black'),
                hovertemplate='<b>%{x}</b><br>Tuition: AED %{y:.2f}M<extra></extra>'
            ))
            _fig.update_layout(
                title=dict(text="Tuition Revenue by Enrolment Type", font=dict(size=14,color='white',family='Arial Black'), x=0.5, xanchor='center'),
                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                font=dict(color='white'), height=320, margin=dict(l=40,r=10,t=50,b=60),
                xaxis=dict(tickfont=dict(size=10,color='white'), tickangle=-30),
                yaxis=dict(title='AED M', tickfont=dict(color='white'), gridcolor='rgba(255,255,255,0.1)'),
                showlegend=False
            )
            st.plotly_chart(_fig, use_container_width=True, config={'displayModeBar': False}, key="pc_story_c2a")
        elif _tuit_col in df.columns and _cohort_col in df.columns:
            _t_by_c = df.groupby(_cohort_col)[_tuit_col].apply(lambda x: pd.to_numeric(x, errors='coerce').sum()).sort_index()
            _fig = go.Figure(go.Bar(
                x=[str(k) for k in _t_by_c.index], y=[v/1e6 for v in _t_by_c.values],
                marker=dict(color='#10b981', line=dict(color='white',width=1)),
                text=[f"AED {v/1e6:.1f}M" for v in _t_by_c.values],
                textposition='outside', textfont=dict(size=11,color='white')
            ))
            _fig.update_layout(
                title=dict(text="Tuition Revenue by Cohort Year", font=dict(size=14,color='white',family='Arial Black'), x=0.5, xanchor='center'),
                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                font=dict(color='white'), height=320, margin=dict(l=40,r=10,t=50,b=40),
                xaxis=dict(tickfont=dict(color='white')), yaxis=dict(title='AED M', tickfont=dict(color='white'), gridcolor='rgba(255,255,255,0.1)'),
                showlegend=False
            )
            st.plotly_chart(_fig, use_container_width=True, config={'displayModeBar': False}, key="pc_story_c2b")
        else:
            _fig = _build_trend_chart_universal(df, kpis, col_roles)
            if _fig:
                st.plotly_chart(_fig, use_container_width=True, config={'displayModeBar': False}, key="pc_story_c2c")

    st.markdown("<br>", unsafe_allow_html=True)

    # ═════════════════════════════════════════════════════════════════════════
    # CHAPTER 3 — The Profit / Cost Story
    # ═════════════════════════════════════════════════════════════════════════
    ch3 = next((c for c in chapters if c.get('num') == 'Chapter 3'), {})
    _c3_icolor = '#6366f1' if ch3.get('insight_type','insight') == 'insight' else '#f59e0b'
    _c3_icon   = '💡' if ch3.get('insight_type','insight') == 'insight' else '⚠️'

    st.markdown(
        f'<div style="display:flex;align-items:center;gap:10px;margin:16px 0 8px 0;">'
        f'<div style="background:#6366f1;color:white;font-size:1.1rem;font-weight:900;'
        f'width:36px;height:36px;border-radius:50%;display:flex;align-items:center;justify-content:center;">3</div>'
        f'<div style="color:#e2e8f0;font-size:1.1rem;font-weight:700;">{ch3.get("title","Chapter 3")}</div>'
        '</div>',
        unsafe_allow_html=True
    )
    c3_left, c3_right = st.columns([1, 1])
    with c3_left:
        st.markdown(
            f'<div style="background:rgba(255,255,255,0.02);border-radius:10px;padding:16px 18px;'
            f'border-left:3px solid {_c3_icolor};line-height:1.75;color:#cbd5e1;font-size:0.9rem;">'
            + ch3.get("body", "") +
            f'<br/><br/><span style="color:{_c3_icolor};font-weight:700;">{_c3_icon} {ch3.get("insight","")}</span>'
            '</div>',
            unsafe_allow_html=True
        )
    with c3_right:
        # Revenue → Aid → Net Tuition waterfall
        _aid_col  = 'financial_aid_monetary_amount'
        _tuit_col = 'enrollment_tuition_amount'
        if _tuit_col in df.columns:
            _total_t = pd.to_numeric(df[_tuit_col], errors='coerce').sum()
            _total_a = pd.to_numeric(df[_aid_col], errors='coerce').sum() if _aid_col in df.columns else 0
            _net_t   = _total_t - _total_a
            _cost_v  = cost if cost else 0
            _wf_x    = ['Gross Tuition', 'Financial Aid', 'Net Tuition']
            _wf_y    = [_total_t/1e6, -_total_a/1e6, _net_t/1e6]
            _wf_m    = ['absolute','relative','total']
            if _cost_v > 0:
                _wf_x += ['Operational Cost', 'Net Surplus']
                _wf_y += [-_cost_v/1e6, (_net_t - _cost_v)/1e6]
                _wf_m += ['relative', 'total']
            _fig = go.Figure(go.Waterfall(
                orientation='v', measure=_wf_m, x=_wf_x, y=_wf_y,
                textposition='outside',
                text=[f"AED {abs(v):.1f}M" for v in _wf_y],
                textfont=dict(size=11, color='white', family='Arial Black'),
                connector=dict(line=dict(color='rgba(255,255,255,0.15)', width=1)),
                increasing=dict(marker=dict(color='#10b981', line=dict(color='white',width=1))),
                decreasing=dict(marker=dict(color='#ef4444', line=dict(color='white',width=1))),
                totals=dict(marker=dict(color='#6366f1', line=dict(color='white',width=1))),
            ))
            _fig.update_layout(
                title=dict(text="Revenue → Aid → Net Tuition Flow", font=dict(size=14,color='white',family='Arial Black'), x=0.5, xanchor='center'),
                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                font=dict(color='white'), height=320, margin=dict(l=40,r=10,t=50,b=40),
                yaxis=dict(title='AED M', tickfont=dict(color='white'), gridcolor='rgba(255,255,255,0.1)'),
                xaxis=dict(tickfont=dict(size=10,color='white'), tickangle=-20),
                showlegend=False
            )
            st.plotly_chart(_fig, use_container_width=True, config={'displayModeBar': False}, key="pc_story_c3a")
        else:
            _fig = _build_margin_waterfall_universal(df, kpis, col_roles)
            if _fig:
                st.plotly_chart(_fig, use_container_width=True, config={'displayModeBar': False}, key="pc_story_c3b")

    st.markdown("<br>", unsafe_allow_html=True)

    # ═════════════════════════════════════════════════════════════════════════
    # CHAPTER 4 — Risk & Opportunity
    # ═════════════════════════════════════════════════════════════════════════
    ch4 = next((c for c in chapters if c.get('num') == 'Chapter 4'), {})
    _c4_icolor = '#f59e0b' if ch4.get('insight_type','insight') == 'warning' else '#3b82f6'
    _c4_icon   = '⚠️' if ch4.get('insight_type','insight') == 'warning' else '💡'

    st.markdown(
        f'<div style="display:flex;align-items:center;gap:10px;margin:16px 0 8px 0;">'
        f'<div style="background:#f59e0b;color:white;font-size:1.1rem;font-weight:900;'
        f'width:36px;height:36px;border-radius:50%;display:flex;align-items:center;justify-content:center;">4</div>'
        f'<div style="color:#e2e8f0;font-size:1.1rem;font-weight:700;">{ch4.get("title","Chapter 4")}</div>'
        '</div>',
        unsafe_allow_html=True
    )
    c4_left, c4_right = st.columns([1, 1])
    with c4_left:
        st.markdown(
            f'<div style="background:rgba(255,255,255,0.02);border-radius:10px;padding:16px 18px;'
            f'border-left:3px solid {_c4_icolor};line-height:1.75;color:#cbd5e1;font-size:0.9rem;">'
            + ch4.get("body", "") +
            f'<br/><br/><span style="color:{_c4_icolor};font-weight:700;">{_c4_icon} {ch4.get("insight","")}</span>'
            '</div>',
            unsafe_allow_html=True
        )
    with c4_right:
        # At-risk vs retention probability scatter or bar
        _ret_col  = 'retention_probability'
        _gpa_col  = 'cumulative_gpa'
        _etype_c  = 'enrollment_type'
        if _ret_col in df.columns and _gpa_col in df.columns:
            _scatter = df[[_ret_col, _gpa_col]].apply(pd.to_numeric, errors='coerce').dropna()
            if len(_scatter) > 500:
                _scatter = _scatter.sample(500, random_state=42)
            _at_risk_mask = _scatter[_gpa_col] < 2.0
            _fig = go.Figure()
            _fig.add_trace(go.Scatter(
                x=_scatter[~_at_risk_mask][_ret_col], y=_scatter[~_at_risk_mask][_gpa_col],
                mode='markers', name='On Track',
                marker=dict(size=5, color='#10b981', opacity=0.6),
                hovertemplate='Retention: %{x:.0f}%<br>GPA: %{y:.2f}<extra></extra>'
            ))
            _fig.add_trace(go.Scatter(
                x=_scatter[_at_risk_mask][_ret_col], y=_scatter[_at_risk_mask][_gpa_col],
                mode='markers', name='At Risk (GPA<2.0)',
                marker=dict(size=7, color='#ef4444', opacity=0.8, symbol='diamond'),
                hovertemplate='Retention: %{x:.0f}%<br>GPA: %{y:.2f}<extra></extra>'
            ))
            _fig.add_hline(y=2.0, line_dash='dash', line_color='rgba(239,68,68,0.5)',
                           annotation_text='Risk threshold', annotation_font_color='#ef4444')
            _fig.update_layout(
                title=dict(text="Retention Probability vs GPA", font=dict(size=14,color='white',family='Arial Black'), x=0.5, xanchor='center'),
                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                font=dict(color='white'), height=320, margin=dict(l=40,r=10,t=50,b=40),
                xaxis=dict(title='Retention Probability (%)', tickfont=dict(color='white'), gridcolor='rgba(255,255,255,0.08)'),
                yaxis=dict(title='Cumulative GPA', tickfont=dict(color='white'), gridcolor='rgba(255,255,255,0.08)'),
                legend=dict(font=dict(size=10,color='white'), bgcolor='rgba(0,0,0,0.3)')
            )
            st.plotly_chart(_fig, use_container_width=True, config={'displayModeBar': False}, key="pc_story_c4a")
        elif kpis.get('at_risk_count') and _etype_c in df.columns and _gpa_col in df.columns:
            # At-risk count by enrollment type
            _ar_by = df.groupby(_etype_c).apply(
                lambda g: int((pd.to_numeric(g[_gpa_col], errors='coerce') < 2.0).sum())
            ).sort_values(ascending=False).head(8)
            _fig = go.Figure(go.Bar(
                x=list(_ar_by.index), y=list(_ar_by.values),
                marker=dict(color='#ef4444', line=dict(color='white',width=1)),
                text=list(_ar_by.values), textposition='outside',
                textfont=dict(size=12,color='white',family='Arial Black')
            ))
            _fig.update_layout(
                title=dict(text="At-Risk Students by Enrolment Type", font=dict(size=14,color='white',family='Arial Black'), x=0.5, xanchor='center'),
                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                font=dict(color='white'), height=320, margin=dict(l=10,r=10,t=50,b=60),
                xaxis=dict(tickfont=dict(size=10,color='white'), tickangle=-30),
                yaxis=dict(title='Students', tickfont=dict(color='white'), gridcolor='rgba(255,255,255,0.1)')
            )
            st.plotly_chart(_fig, use_container_width=True, config={'displayModeBar': False}, key="pc_story_c4b")
        else:
            # Past-due / financial hold risk bar
            _pd_col = 'past_due_balance'
            if _pd_col in df.columns and _etype_c in df.columns:
                _pd_by = df.groupby(_etype_c)[_pd_col].apply(lambda x: pd.to_numeric(x, errors='coerce').sum() / 1e6)
                _fig = go.Figure(go.Bar(
                    x=list(_pd_by.index), y=list(_pd_by.values),
                    marker=dict(color='#f59e0b', line=dict(color='white',width=1)),
                    text=[f"AED {v:.1f}M" for v in _pd_by.values], textposition='outside',
                    textfont=dict(size=11,color='white')
                ))
                _fig.update_layout(
                    title=dict(text="Past-Due Balance by Enrolment Type", font=dict(size=14,color='white',family='Arial Black'), x=0.5, xanchor='center'),
                    paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                    font=dict(color='white'), height=320, margin=dict(l=40,r=10,t=50,b=60),
                    xaxis=dict(tickfont=dict(size=10,color='white'), tickangle=-30),
                    yaxis=dict(title='AED M', tickfont=dict(color='white'), gridcolor='rgba(255,255,255,0.1)')
                )
                st.plotly_chart(_fig, use_container_width=True, config={'displayModeBar': False}, key="pc_story_c4c")

    st.markdown("<br>", unsafe_allow_html=True)

    # ═════════════════════════════════════════════════════════════════════════
    # CHAPTER 5 — The Forward Story
    # ═════════════════════════════════════════════════════════════════════════
    ch5 = next((c for c in chapters if c.get('num') == 'Chapter 5'), {})
    _c5_icolor = '#3b82f6' if ch5.get('insight_type','insight') == 'insight' else '#f59e0b'
    _c5_icon   = '🚀' if ch5.get('insight_type','insight') == 'insight' else '⚠️'

    st.markdown(
        f'<div style="display:flex;align-items:center;gap:10px;margin:16px 0 8px 0;">'
        f'<div style="background:#3b82f6;color:white;font-size:1.1rem;font-weight:900;'
        f'width:36px;height:36px;border-radius:50%;display:flex;align-items:center;justify-content:center;">5</div>'
        f'<div style="color:#e2e8f0;font-size:1.1rem;font-weight:700;">{ch5.get("title","Chapter 5")}</div>'
        '</div>',
        unsafe_allow_html=True
    )
    c5_left, c5_right = st.columns([1, 1])
    with c5_left:
        st.markdown(
            f'<div style="background:rgba(255,255,255,0.02);border-radius:10px;padding:16px 18px;'
            f'border-left:3px solid {_c5_icolor};line-height:1.75;color:#cbd5e1;font-size:0.9rem;">'
            + ch5.get("body", "") +
            f'<br/><br/><span style="color:{_c5_icolor};font-weight:700;">{_c5_icon} {ch5.get("insight","")}</span>'
            '</div>',
            unsafe_allow_html=True
        )
    with c5_right:
        # Graduation probability distribution or aid scenario chart
        _grad_col = 'graduation_probability'
        _ret_col2 = 'retention_probability'
        if _grad_col in df.columns:
            _grad_s = pd.to_numeric(df[_grad_col], errors='coerce').dropna()
            _ret_s2 = pd.to_numeric(df[_ret_col2], errors='coerce').dropna() if _ret_col2 in df.columns else None
            _fig = go.Figure()
            _fig.add_trace(go.Histogram(
                x=_grad_s, nbinsx=20, name='Graduation Probability',
                marker=dict(color='#3b82f6', opacity=0.8, line=dict(color='white',width=1)),
                hovertemplate='Graduation Prob: %{x:.0f}%<br>Students: %{y}<extra></extra>'
            ))
            if _ret_s2 is not None:
                _fig.add_trace(go.Histogram(
                    x=_ret_s2, nbinsx=20, name='Retention Probability',
                    marker=dict(color='#10b981', opacity=0.6, line=dict(color='white',width=1)),
                    hovertemplate='Retention Prob: %{x:.0f}%<br>Students: %{y}<extra></extra>'
                ))
            _fig.update_layout(
                title=dict(text="Graduation & Retention Probability Distribution", font=dict(size=13,color='white',family='Arial Black'), x=0.5, xanchor='center'),
                barmode='overlay',
                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                font=dict(color='white'), height=320, margin=dict(l=40,r=10,t=55,b=40),
                xaxis=dict(title='Probability (%)', tickfont=dict(color='white')),
                yaxis=dict(title='Students', tickfont=dict(color='white'), gridcolor='rgba(255,255,255,0.1)'),
                legend=dict(font=dict(size=10,color='white'), bgcolor='rgba(0,0,0,0.3)')
            )
            st.plotly_chart(_fig, use_container_width=True, config={'displayModeBar': False}, key="pc_story_c5a")
        elif rev > 0:
            # Revenue projection bars
            _proj = _compute_revenue_projection(kpis, periods=4)
            if _proj:
                _trend = kpis.get('revenue_trend')
                _hist_labels = [str(p) for p in _trend.index[-4:]] if _trend is not None else []
                _hist_vals   = list(_trend.values[-4:]) if _trend is not None else []
                _proj_labels = [p['period'] for p in _proj]
                _proj_vals   = [p['value'] for p in _proj]
                _fig = go.Figure()
                if _hist_labels:
                    _fig.add_trace(go.Bar(x=_hist_labels, y=_hist_vals, name='Historical',
                                         marker=dict(color='#10b981', line=dict(color='white',width=1))))
                _fig.add_trace(go.Bar(x=_proj_labels, y=_proj_vals, name='Projected',
                                     marker=dict(color='rgba(99,102,241,0.7)', line=dict(color='white',width=1)), opacity=0.75))
                _fig.update_layout(
                    title=dict(text="Revenue Projection", font=dict(size=14,color='white',family='Arial Black'), x=0.5, xanchor='center'),
                    paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                    font=dict(color='white'), height=320, margin=dict(l=40,r=10,t=50,b=40),
                    yaxis=dict(title='AED', tickfont=dict(color='white'), gridcolor='rgba(255,255,255,0.1)'),
                    xaxis=dict(tickfont=dict(color='white'), tickangle=-30),
                    legend=dict(font=dict(size=10,color='white'), bgcolor='rgba(0,0,0,0.3)')
                )
                st.plotly_chart(_fig, use_container_width=True, config={'displayModeBar': False}, key="pc_story_c5b")
            else:
                # Aid vs Retention scatter by program
                _fig = _build_projection_chart(kpis)
                if _fig:
                    st.plotly_chart(_fig, use_container_width=True, config={'displayModeBar': False}, key="pc_story_c5c")

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("---")

    # ── AI NARRATIVE PROSE ──────────────────────────────────────────────────
    render_section_header("✍️", "AI-Written Financial Narrative", "LLM PROSE")

    ollama_connected = st.session_state.get('fin_ollama_connected', False)
    cached_prose = st.session_state.get('fin_narrative_prose', {})
    prose_key    = f"prose-{kpis.get('row_count')}-{kpis.get('total_revenue', 0):.0f}"

    if cached_prose.get(prose_key):
        prose = cached_prose[prose_key]
        st.markdown(
            f'<div style="background:linear-gradient(145deg,#0c1826,#112035);'
            f'border:1px solid rgba(245,158,11,0.2);border-radius:14px;'
            f'padding:28px 32px;line-height:1.9;font-size:0.94rem;color:#cbd5e1;">'
            + prose.replace(chr(10), '<br>') +
            '</div>',
            unsafe_allow_html=True
        )
        if st.button("Re-generate Narrative Prose", key="fin_regen_prose"):
            del st.session_state['fin_narrative_prose']
            st.rerun()
    elif ollama_connected and model:
        if st.button("Generate AI Narrative Prose", key="fin_gen_prose", type="primary"):
            with st.spinner("Writing your financial story with AI..."):
                prose = generate_narrative_with_llm(narrative, kpis, model, ollama_url)
                if prose:
                    st.session_state['fin_narrative_prose'] = {prose_key: prose}
                    st.rerun()
                else:
                    st.warning("AI narrative generation returned empty. Check model connection.")
    else:
        st.markdown(
            '<div style="background:rgba(245,158,11,0.06);border:1px dashed rgba(245,158,11,0.3);'
            'border-radius:10px;padding:20px 24px;text-align:center;color:#94a3b8;font-size:0.9rem;">'
            'Connect to Ollama and select a model to generate a full AI-written financial narrative.'
            '<br><br>The visualized chapters above are available without AI.'
            '</div>',
            unsafe_allow_html=True
        )


def _build_trend_chart_universal(df: pd.DataFrame, kpis: Dict[str, Any], col_roles: Dict[str, List[str]]) -> Optional[go.Figure]:
    """
    Build a revenue trend chart from whatever date + numeric columns exist.
    Falls back to row-index if no date column is available.
    """
    # Prefer precomputed trend from KPIs
    if 'revenue_trend' in kpis:
        trend = kpis['revenue_trend']
        labels = [str(p) for p in trend.index]
        values = trend.values.tolist()
        title  = f"Monthly {kpis.get('revenue_col', 'Revenue')} Trend"
    else:
        # Pick any numeric column as value source
        num_cols = df.select_dtypes(include='number').columns.tolist()
        if not num_cols:
            return None
        val_col = col_roles.get('revenue', [None])[0] or num_cols[0]
        val_series = pd.to_numeric(df[val_col], errors='coerce').dropna()

        # Try date column for x-axis
        date_candidates = col_roles.get('date', [])
        if date_candidates:
            try:
                tmp = df[[date_candidates[0], val_col]].copy()
                tmp[date_candidates[0]] = pd.to_datetime(tmp[date_candidates[0]], errors='coerce')
                tmp = tmp.dropna()
                tmp['_p'] = tmp[date_candidates[0]].dt.to_period('M')
                by_p = tmp.groupby('_p')[val_col].sum().sort_index()
                labels = [str(p) for p in by_p.index]
                values = by_p.values.tolist()
                title  = f"Monthly {val_col} Trend"
            except Exception:
                labels = [str(i) for i in range(len(val_series))]
                values = val_series.values.tolist()
                title  = f"{val_col} Over Records"
        else:
            # Use rolling 20-record windows as proxy periods
            chunk = max(1, len(val_series) // 20)
            chunked = [val_series.iloc[i:i+chunk].sum() for i in range(0, len(val_series), chunk)]
            labels = [f"Batch {i+1}" for i in range(len(chunked))]
            values = chunked
            title  = f"{val_col} Across Record Batches"

    if not values:
        return None

    fig = go.Figure()
    # Colour gradient: green where above mean, amber elsewhere
    mean_v = float(np.mean(values))
    colours = ['#10b981' if v >= mean_v else '#f59e0b' for v in values]
    fig.add_trace(go.Scatter(
        x=labels, y=values,
        mode='lines+markers',
        name='Value',
        line=dict(color='#f59e0b', width=3),
        marker=dict(size=7, color=colours, line=dict(width=1, color='rgba(0,0,0,0.3)')),
        fill='tozeroy',
        fillcolor='rgba(245,158,11,0.07)',
        hovertemplate='%{x}<br>Value: $%{y:,.0f}<extra></extra>'
    ))
    # Mean reference line
    fig.add_hline(y=mean_v, line_dash='dot', line_color='rgba(148,163,184,0.4)',
                  annotation_text=f"Avg: ${mean_v:,.0f}", annotation_font_color='#94a3b8',
                  annotation_font_size=10)
    fig.update_layout(
        title=dict(text=title, font=dict(color='#f1f5f9', size=13)),
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#94a3b8'),
        xaxis=dict(gridcolor='rgba(255,255,255,0.05)', showgrid=True, tickangle=-30),
        yaxis=dict(gridcolor='rgba(255,255,255,0.05)', showgrid=True,
                   tickprefix='$', tickformat=',.0f'),
        margin=dict(l=10, r=10, t=40, b=30),
        height=300,
    )
    return fig


def _build_drivers_chart_universal(df: pd.DataFrame, kpis: Dict[str, Any], col_roles: Dict[str, List[str]]) -> Optional[go.Figure]:
    """
    Build a top-drivers chart from any categorical + numeric column pair.
    Falls back to numeric column distribution if no categorical found.
    """
    # Prefer precomputed top_products
    if 'top_products' in kpis:
        top  = kpis['top_products']
        vals = top.values.tolist()
        keys = [str(k) for k in top.index]
        title = f"Top {kpis.get('product_col','Category')} Revenue Drivers"
    else:
        cat_cols = df.select_dtypes(include='object').columns.tolist()
        num_cols = df.select_dtypes(include='number').columns.tolist()
        if not num_cols:
            return None

        val_col = col_roles.get('revenue', [None])[0] or num_cols[0]

        if cat_cols:
            # Pick a categorical column (prefer product/segment keywords)
            cat_col = (col_roles.get('product') or col_roles.get('customer') or [cat_cols[0]])[0]
            grouped = (df.groupby(cat_col)[val_col]
                         .sum()
                         .nlargest(8)
                         .sort_values(ascending=True))
            vals  = grouped.values.tolist()
            keys  = [str(k) for k in grouped.index]
            title = f"Top {cat_col} by {val_col}"
        else:
            # No categorical: show top-N records by value
            top_n = df[val_col].nlargest(8)
            vals  = top_n.values.tolist()
            keys  = [f"Row {i}" for i in top_n.index]
            title = f"Top Records by {val_col}"

    if not vals:
        return None

    n = len(vals)
    norm = [(v - min(vals)) / max(max(vals) - min(vals), 1) for v in vals]
    colours = [f'rgba({int(30+160*t)},{int(83+75*t)},{int(95-50*t)},0.9)' for t in norm]

    fig = go.Figure(go.Bar(
        x=vals, y=keys, orientation='h',
        marker=dict(color=colours),
        hovertemplate='%{y}<br>Value: $%{x:,.0f}<extra></extra>',
        text=[_fmt(v, prefix='$') for v in vals],
        textposition='outside',
        textfont=dict(color='#f59e0b', size=10),
    ))
    fig.update_layout(
        title=dict(text=title, font=dict(color='#f1f5f9', size=13)),
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#94a3b8'),
        xaxis=dict(gridcolor='rgba(255,255,255,0.05)', tickprefix='$', tickformat=',.0f'),
        yaxis=dict(gridcolor='rgba(255,255,255,0.05)'),
        margin=dict(l=10, r=10, t=40, b=10),
        height=300,
    )
    return fig


def _build_margin_waterfall_universal(df: pd.DataFrame, kpis: Dict[str, Any], col_roles: Dict[str, List[str]]) -> Optional[go.Figure]:
    """
    Build a P&L waterfall from whatever revenue/cost/profit data exists.
    Always renders something as long as there is at least one numeric column.
    """
    rev    = kpis.get('total_revenue')
    cost   = kpis.get('total_cost')
    profit = kpis.get('total_profit')

    # If we only have revenue (no cost), try to show numeric breakdown
    num_cols = df.select_dtypes(include='number').columns.tolist()
    if rev is None and num_cols:
        # Show top 5 numeric column totals as a composition waterfall
        totals = {c: pd.to_numeric(df[c], errors='coerce').sum() for c in num_cols[:6]}
        totals = {k: v for k, v in totals.items() if not np.isnan(v) and v != 0}
        if not totals:
            return None
        items  = sorted(totals.items(), key=lambda x: abs(x[1]), reverse=True)[:5]
        x_labs = [i[0] for i in items]
        y_vals = [i[1] for i in items]
        measures = ['absolute'] * len(y_vals)
        title  = "Numeric Column Totals"
    else:
        if rev is None:
            return None
        measures = ['absolute', 'relative', 'total']
        x_labs   = [kpis.get('revenue_col', 'Revenue'),
                    kpis.get('cost_col',    'Cost'),
                    kpis.get('profit_col',  'Gross Profit')]
        y_vals   = [rev, -(cost or 0), profit or (rev - (cost or 0))]
        title    = "Revenue → Cost → Profit Waterfall"

    fig = go.Figure(go.Waterfall(
        orientation='v', measure=measures,
        x=x_labs, y=y_vals,
        textposition='outside',
        text=[_fmt(v, prefix='$') for v in y_vals],
        connector=dict(line=dict(color='rgba(255,255,255,0.08)')),
        increasing=dict(marker=dict(color='#10b981')),
        decreasing=dict(marker=dict(color='#ef4444')),
        totals=dict(marker=dict(color='#f59e0b')),
    ))
    fig.update_layout(
        title=dict(text=title, font=dict(color='#f1f5f9', size=13)),
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#94a3b8'),
        yaxis=dict(gridcolor='rgba(255,255,255,0.05)', tickprefix='$', tickformat=',.0f'),
        margin=dict(l=10, r=10, t=40, b=10),
        height=300, showlegend=False,
    )
    return fig


def _build_numeric_correlation_heatmap(df: pd.DataFrame) -> Optional[go.Figure]:
    """Correlation heatmap for all numeric columns."""
    num_df = df.select_dtypes(include='number')
    if num_df.shape[1] < 2:
        return None
    # Limit to 12 cols for readability
    cols = num_df.columns[:12].tolist()
    corr = num_df[cols].corr()
    z    = corr.values
    fig = go.Figure(go.Heatmap(
        z=z, x=cols, y=cols,
        colorscale=[[0,'#ef4444'],[0.5,'#1e293b'],[1,'#10b981']],
        zmin=-1, zmax=1,
        text=[[f"{v:.2f}" for v in row] for row in z],
        texttemplate='%{text}',
        textfont=dict(size=9),
        hovertemplate='%{y} vs %{x}: %{z:.2f}<extra></extra>',
        showscale=True,
    ))
    fig.update_layout(
        title=dict(text="Numeric Column Correlations", font=dict(color='#f1f5f9', size=13)),
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#94a3b8'),
        xaxis=dict(tickangle=-40, tickfont=dict(size=9)),
        yaxis=dict(tickfont=dict(size=9)),
        margin=dict(l=10, r=10, t=40, b=60),
        height=340,
    )
    return fig


def _business_impact_box(icon: str, title: str, body: str):
    """Indigo gradient card — strategic context for executives."""
    st.markdown(f"""
    <div style="background:linear-gradient(135deg,rgba(99,102,241,0.12) 0%,rgba(59,130,246,0.10) 100%);
                padding:1.2rem 1.4rem;border-radius:10px;border-left:4px solid #6366f1;
                margin:1rem 0;">
        <div style="color:#818cf8;font-weight:700;font-size:0.95rem;margin-bottom:0.5rem;">
            {icon} {title}
        </div>
        <div style="color:#e2e8f0;font-size:0.92rem;line-height:1.75;">{body}</div>
    </div>
    """, unsafe_allow_html=True)


def _findings_box(title: str, body: str):
    """Green highlight card — detailed metrics summary with status."""
    st.markdown(f"""
    <div style="background:linear-gradient(135deg,rgba(16,185,129,0.12) 0%,rgba(5,150,105,0.10) 100%);
                padding:1.4rem 1.6rem;border-radius:10px;border:2px solid #10b981;
                margin:1.2rem 0;">
        <div style="color:#10b981;font-weight:700;font-size:1.05rem;margin-bottom:0.8rem;">
            📋 {title}
        </div>
        <div style="color:#e2e8f0;font-size:0.91rem;line-height:1.85;">{body}</div>
    </div>
    """, unsafe_allow_html=True)


def _alert_box(icon: str, title: str, body: str, color: str = "#f59e0b"):
    """Amber/red alert card for warnings or priority actions."""
    st.markdown(f"""
    <div style="background:rgba(0,0,0,0.15);padding:1rem 1.2rem;border-radius:10px;
                border-left:4px solid {color};margin:0.8rem 0;">
        <div style="color:{color};font-weight:700;font-size:0.88rem;margin-bottom:0.4rem;">
            {icon} {title}
        </div>
        <div style="color:#cbd5e1;font-size:0.86rem;line-height:1.65;">{body}</div>
    </div>
    """, unsafe_allow_html=True)


def _status_badge(label: str, value: str, status: str) -> str:
    """Return inline HTML badge. status: ok | warn | bad"""
    c = {"ok": "#10b981", "warn": "#f59e0b", "bad": "#ef4444"}.get(status, "#94a3b8")
    icon = {"ok": "✅", "warn": "⚠️", "bad": "🔴"}.get(status, "•")
    return (f"<span style='color:{c};font-weight:700;'>{icon} {label}:</span> "
            f"<span style='color:#e2e8f0;'>{value}</span>")


def render_command_centre_tab(df, kpis, col_roles):
    """Tab 1: Financial Command Centre — with insight boxes, health scoring & clear messages."""

    # ── CATALOG SNAPSHOT: Student & Institutional KPIs ───────────────────────
    # Displayed only when catalog-mapped fields are present in the dataset
    _snap_items = []
    if kpis.get('active_students') is not None:
        _snap_items.append(("🎓", "Active Students",   f"{kpis['active_students']:,}",
                            f"{kpis.get('active_pct',0):.0f}% of enrolled", "#10b981"))
    if kpis.get('avg_gpa') is not None:
        _snap_items.append(("📚", "Avg GPA",           f"{kpis['avg_gpa']:.2f}",
                            f"{kpis.get('high_performers',0):,} high performers (≥3.5)", "#6366f1"))
    if kpis.get('at_risk_count') is not None:
        _snap_items.append(("⚠️", "At-Risk Students",  f"{kpis['at_risk_count']:,}",
                            f"{kpis.get('at_risk_pct',0):.1f}% of population", "#f59e0b"))
    if kpis.get('avg_retention_prob') is not None:
        _snap_items.append(("🔄", "Avg Retention Prob",f"{kpis['avg_retention_prob']:.1f}%",
                            f"{kpis.get('low_retention_count',0):,} below 50%", "#3b82f6"))
    if kpis.get('total_financial_aid') is not None:
        _snap_items.append(("💸", "Total Aid Disbursed",f"${kpis['total_financial_aid']:,.0f}",
                            f"{kpis.get('aid_as_pct_of_revenue',0):.1f}% of tuition revenue", "#ec4899"))
    if kpis.get('avg_engagement') is not None:
        _snap_items.append(("⭐", "Avg Engagement",    f"{kpis['avg_engagement']:.1f}/100",
                            f"{kpis.get('low_engagement',0):,} disengaged students", "#f59e0b"))

    if _snap_items:
        render_section_header("🏫", "STUDENT & INSTITUTIONAL SNAPSHOT", "FROM YOUR DATASET")
        _snap_cols = st.columns(min(len(_snap_items), 3))
        for _i, (_icon, _label, _val, _sub, _col) in enumerate(_snap_items[:6]):
            with _snap_cols[_i % 3]:
                st.markdown(
                    f'<div style="background:linear-gradient(135deg,#0d1f35,#132840);border-left:4px solid {_col};'
                    f'border-radius:0 12px 12px 0;padding:14px 16px;margin-bottom:10px;">'
                    f'<div style="font-size:1.4rem;">{_icon}</div>'
                    f'<div style="font-size:0.75rem;color:#94a3b8;text-transform:uppercase;letter-spacing:1px;">{_label}</div>'
                    f'<div style="font-size:1.5rem;font-weight:800;color:#f1f5f9;">{_val}</div>'
                    f'<div style="font-size:0.75rem;color:#94a3b8;margin-top:4px;">{_sub}</div></div>',
                    unsafe_allow_html=True
                )
        st.markdown("<br>", unsafe_allow_html=True)

    # ── INSIGHT 1: Revenue, Cost & Margin Health ──────────────────────────────
    render_section_header("💰", "INSIGHT 1: Income, Cost & Financial Health", "WHO EARNS WHAT")

    render_kpi_row(kpis)
    st.markdown("<br>", unsafe_allow_html=True)

    chart_cols = st.columns([2, 2, 2])
    with chart_cols[0]:
        fig = _build_trend_chart_universal(df, kpis, col_roles)
        if fig:
            st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False}, key="pc_2997")
    with chart_cols[1]:
        fig = _build_drivers_chart_universal(df, kpis, col_roles)
        if fig:
            st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False}, key="pc_3001")
    with chart_cols[2]:
        fig = _build_margin_waterfall_universal(df, kpis, col_roles)
        if fig:
            st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False}, key="pc_3005")

    # Compute health scores for this insight
    rev   = kpis.get('total_revenue', 0) or 0
    cost  = kpis.get('total_cost', 0) or 0
    prof  = kpis.get('total_profit', 0) or 0
    gm    = kpis.get('gross_margin_pct', _pct(prof, max(rev, 1)))
    mom   = kpis.get('mom_pct', 0) or 0

    margin_status = "ok" if gm > 30 else "warn" if gm > 15 else "bad"
    trend_status  = "ok" if mom >= 0 else "warn" if mom > -10 else "bad"

    margin_label = "above target (>30%)" if gm > 30 else "near target (15-30%)" if gm > 15 else "below target — action needed"
    trend_label  = f"growing at {mom:+.1f}% MoM" if mom >= 0 else f"declining {mom:.1f}% MoM — investigate"

    _business_impact_box(
        "💼", "Institutional Impact: Income, Cost & Financial Sustainability",
        f"Total income of <strong>{_fmt(rev, prefix='$')}</strong> against costs of "
        f"<strong>{_fmt(cost, prefix='$')}</strong> yields a net surplus of "
        f"<strong>{_fmt(prof, prefix='$')}</strong> — a net margin of <strong>{gm:.1f}%</strong>. "
        f"Each 1% margin improvement on this income base represents "
        f"<strong>{_fmt(rev * 0.01, prefix='$')}</strong> in additional institutional surplus. "
        f"Monitor income concentration: if the top programme or cohort exceeds 60% of total, "
        f"income diversification becomes a strategic imperative."
    )

    findings_body = (
        f"{_status_badge('Gross Margin', f'{gm:.1f}%', margin_status)} — {margin_label}<br/>"
        f"{_status_badge('Revenue Trend', f'{mom:+.1f}% MoM', trend_status)} — {trend_label}<br/>"
        f"{_status_badge('Total Revenue', _fmt(rev, prefix='$'), 'ok')}<br/>"
        f"{_status_badge('Total Cost', _fmt(cost, prefix='$'), 'ok')}<br/>"
        f"{_status_badge('Gross Profit', _fmt(prof, prefix='$'), margin_status)}<br/><br/>"
        f"<strong>Priority Actions:</strong><br/>"
        f"{'✅ Margin is healthy — maintain cost discipline and reinvest surplus in academic quality.' if gm > 30 else '⚠️ Margin below 30% — review top cost drivers and explore fee or programme optimisation.' if gm > 15 else '🔴 Critical margin (<15%) — immediate cost audit required. Identify top 3 expense lines.'}<br/>"
        f"{'✅ Income trending up — sustain enrolment and programme investments.' if mom >= 0 else '⚠️ Income declining — run root-cause analysis on the trend drop before end of this period.'}"
    )
    _findings_box("INSIGHT 1 FINDINGS — Income & Financial Health", findings_body)

    # ── INSIGHT 2: Revenue Driver Concentration ────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    render_section_header("🏆", "INSIGHT 2: Income Source Concentration", "WHAT DRIVES THE NUMBERS")

    top_products = kpis.get('top_products')
    if top_products is not None and len(top_products) > 0:
        top_share = float(top_products.iloc[0]) / max(rev, 1) * 100
        top_name  = str(top_products.index[0])
        conc_status = "bad" if top_share > 60 else "warn" if top_share > 40 else "ok"
        conc_label  = "HIGH CONCENTRATION — diversify" if top_share > 60 else "MODERATE — monitor" if top_share > 40 else "BALANCED — healthy spread"

        drv_col, conc_col = st.columns([3, 2])
        with drv_col:
            fig2 = _build_drivers_chart_universal(df, kpis, col_roles)
            if fig2:
                st.plotly_chart(fig2, use_container_width=True, config={'displayModeBar': False}, key="pc_3058")

        with conc_col:
            st.markdown("**Income Concentration Risk**")
            # Show programme/major breakdown if available from catalog
            for _pk in ['top_by_academic_program','top_by_major','top_by_college','top_by_department']:
                _prog_data = kpis.get(_pk)
                if _prog_data:
                    _prog_label = _pk.replace('top_by_','').replace('_',' ').title()
                    st.markdown(f"**Top Income by {_prog_label}**")
                    for _pn, _pv in list(_prog_data.items())[:5]:
                        _total_r = kpis.get('total_revenue', 1) or 1
                        _pct_p = round(_pv / _total_r * 100, 1)
                        st.markdown(
                            f'<div style="display:flex;justify-content:space-between;align-items:center;'
                            f'background:#0d1f35;border-radius:6px;padding:6px 10px;margin:3px 0;">'
                            f'<span style="color:#e2e8f0;font-size:0.82rem;">{str(_pn)[:35]}</span>'
                            f'<span style="color:#6366f1;font-weight:700;font-size:0.82rem;">{_pct_p}%</span>'
                            f'</div>',
                            unsafe_allow_html=True
                        )
                    break
            for rank, (name, val) in enumerate(top_products.items(), 1):
                share = float(val) / max(rev, 1) * 100
                bar_color = "#ef4444" if share > 40 else "#f59e0b" if share > 25 else "#10b981"
                st.markdown(f"""
                <div style="margin-bottom:10px;">
                    <div style="display:flex;justify-content:space-between;margin-bottom:3px;">
                        <span style="font-size:0.8rem;color:#e2e8f0;">#{rank} {name}</span>
                        <span style="font-size:0.8rem;font-weight:700;color:{bar_color};">{share:.1f}%</span>
                    </div>
                    <div style="background:#1e293b;border-radius:4px;height:7px;">
                        <div style="width:{min(share,100):.0f}%;height:7px;border-radius:4px;
                                    background:{bar_color};"></div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

        _business_impact_box(
            "💼", "Institutional Impact: Income Source Concentration & Diversification",
            f"<strong>{top_name}</strong> contributes <strong>{top_share:.1f}%</strong> of total income. "
            f"{'A single source exceeding 60% creates high institutional risk — any disruption to this programme or cohort directly impacts financial sustainability. An immediate income diversification plan is required.' if top_share > 60 else 'Income concentration above 40% creates moderate dependency. Develop and grow mid-tier programmes and cohorts.' if top_share > 40 else 'Income is well-distributed across programmes and sources. Focus on growing the top 2-3 contributors while protecting their enrolment share.'}"
        )
        _findings_box(
            "INSIGHT 2 FINDINGS — Income Concentration Risk",
            f"{_status_badge('Top Source Share', f'{top_name}: {top_share:.1f}%', conc_status)} — {conc_label}<br/>"
            f"{_status_badge('Source Count', str(len(top_products)), 'ok')}<br/>"
            f"<strong>Target:</strong> No single programme or source should exceed 40% of income for financial resilience.<br/><br/>"
            f"<strong>Action:</strong> {'Develop 2-3 new income streams within the next 90 days.' if top_share > 60 else 'Invest in the #2 and #3 income sources to reduce concentration dependency.' if top_share > 40 else 'Maintain current income balance.'} "
            f"Review income source performance quarterly to detect early concentration shifts."
        )
    else:
        st.info("Add a product/category column to unlock revenue driver concentration analysis.")

    # ── INSIGHT 3: Correlation Intelligence ───────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    render_section_header("🔗", "INSIGHT 3: What Influences What — Data Relationship Intelligence", "PATTERNS & CONNECTIONS")

    corr_col, heat_col = st.columns([2, 3])
    pairs = _compute_strong_correlations(df, threshold=0.6)

    with heat_col:
        fig_corr = _build_numeric_correlation_heatmap(df)
        if fig_corr:
            st.plotly_chart(fig_corr, use_container_width=True, config={'displayModeBar': False}, key="pc_3104")

    with corr_col:
        st.markdown("**Key Statistical Relationships Identified**")
        if pairs:
            for p in pairs[:5]:
                dir_color = '#10b981' if p['direction'] == 'positive' else '#ef4444'
                arrow     = '▲' if p['direction'] == 'positive' else '▼'
                business_msg = (
                    f"Higher <code>{p['col_a']}</code> is statistically associated with higher <code>{p['col_b']}</code> — worth exploring causally."
                    if p['direction'] == 'positive' else
                    f"Higher <code>{p['col_a']}</code> is associated with lower <code>{p['col_b']}</code> — review whether cost control in one enables growth in the other."
                )
                st.markdown(f"""
                <div style="padding:10px 14px;margin-bottom:8px;background:rgba(255,255,255,0.03);
                            border-radius:10px;border-left:3px solid {dir_color};">
                    <div style="font-size:0.82rem;font-weight:700;color:#e2e8f0;">
                        <code>{p['col_a']}</code> {arrow} <code>{p['col_b']}</code>
                        <span style="color:{dir_color};margin-left:6px;font-size:0.75rem;">
                            r={p['r']} ({p['strength'].upper()})
                        </span>
                    </div>
                    <div style="font-size:0.76rem;color:#94a3b8;margin-top:4px;">{business_msg}</div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("No strong correlations found. Each metric appears to move independently.")

    if pairs:
        strongest = pairs[0]
        _business_impact_box(
            "💼", "Institutional Impact: Using Data Relationships for Informed Decisions",
            f"The strongest relationship in your data is between "
            f"<strong>{strongest['col_a']}</strong> and <strong>{strongest['col_b']}</strong> "
            f"(r = {strongest['r']}). A {'positive' if strongest['direction'] == 'positive' else 'negative'} "
            f"correlation this strong means these two metrics move {'together' if strongest['direction'] == 'positive' else 'in opposite directions'} "
            f"{'~' + str(int(abs(strongest['r']) * 100)) + '% of the time'}. "
            f"Use this as a predictive indicator: changes in one metric are likely to signal changes in the other "
            f"{'within the same or next reporting period.' if abs(strongest['r']) >= 0.8 else 'over 2-3 reporting periods.'}"
        )
        corr_findings = "<br/>".join(
            _status_badge(f"{p['col_a']} ↔ {p['col_b']}", f"r={p['r']}", "ok")
            for p in pairs[:4]
        )
        _findings_box(
            "INSIGHT 3 FINDINGS — Data Relationship Intelligence",
            f"<strong>{len(pairs)} strong statistical relationship(s)</strong> found (|r| ≥ 0.60):<br/><br/>"
            + "<br/>".join(
                f"• <strong>{p['col_a']} ↔ {p['col_b']}</strong>: r={p['r']} — "
                f"{'Positive association — institutional actions that grow one tend to grow the other.' if p['direction']=='positive' else 'Inverse relationship — review whether reducing one frees up capacity in the other.'}"
                for p in pairs[:4]
            ) + "<br/><br/>"
            f"<strong>Action:</strong> Use the top correlated metric pair as a predictive indicator in academic and financial planning. "
            f"Set a monitoring alert when either metric moves >5% — the other is likely to follow within the same period."
        )

    # ── INSIGHT 4: Data Quality & Readiness ───────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    render_section_header("🔍", "INSIGHT 4: Data Quality & Analysis Readiness", "CAN WE TRUST THE NUMBERS")

    total_cells   = df.shape[0] * df.shape[1]
    missing_cells = int(df.isnull().sum().sum())
    completeness  = 100 - (missing_cells / max(total_cells, 1) * 100)
    dup_rows      = int(df.duplicated().sum())
    dup_pct       = dup_rows / max(len(df), 1) * 100
    comp_status   = "ok" if completeness >= 95 else "warn" if completeness >= 85 else "bad"
    dup_status    = "ok" if dup_pct == 0 else "warn" if dup_pct < 2 else "bad"

    q_cols = st.columns(4)
    quality_items = [
        ("Data Completeness", f"{completeness:.1f}%", comp_status),
        ("Duplicate Rows",    f"{dup_rows:,} ({dup_pct:.1f}%)", dup_status),
        ("Total Records",     f"{len(df):,}", "ok"),
        ("Numeric Dimensions",f"{len(df.select_dtypes(include='number').columns)}", "ok"),
    ]
    status_colors = {"ok": "#10b981", "warn": "#f59e0b", "bad": "#ef4444"}
    for col_widget, (label, value, st_key) in zip(q_cols, quality_items):
        c = status_colors[st_key]
        with col_widget:
            st.markdown(f"""
            <div style="background:rgba(255,255,255,0.03);border-radius:10px;padding:14px 16px;
                        border-top:3px solid {c};text-align:center;">
                <div style="font-size:0.72rem;color:#94a3b8;text-transform:uppercase;letter-spacing:1px;">{label}</div>
                <div style="font-size:1.5rem;font-weight:800;color:{c};margin:6px 0;">{value}</div>
            </div>
            """, unsafe_allow_html=True)

    missing_by_col = df.isnull().sum()
    missing_by_col = missing_by_col[missing_by_col > 0].sort_values(ascending=False)

    quality_action = ""
    if completeness < 85:
        quality_action = ("🔴 Critical data gaps detected. Analysis results may be unreliable. "
                          "Resolve missing values in key financial columns before sharing insights.")
    elif completeness < 95:
        quality_action = ("⚠️ Some data gaps present. Impute or flag missing values in the "
                          f"{len(missing_by_col)} affected column(s) to improve accuracy.")
    else:
        quality_action = "✅ Data quality is high. Analysis results are reliable."

    if dup_rows > 0:
        quality_action += (f" Additionally, {dup_rows:,} duplicate rows detected — "
                           "remove duplicates to prevent double-counting in revenue totals.")

    _business_impact_box(
        "💼", "Business Impact: Data Quality Directly Impacts Decision Quality",
        f"Your dataset is <strong>{completeness:.1f}% complete</strong> across "
        f"{len(df):,} records and {len(df.columns)} dimensions. "
        f"{'At this quality level, all financial metrics are statistically reliable.' if completeness >= 95 else 'Missing data in financial columns may cause revenue and margin figures to be understated — treat KPIs as directional, not precise.' if completeness >= 85 else 'Significant data gaps mean KPIs shown above may be materially inaccurate. Prioritise data collection before making strategic decisions.'} "
        f"Every 1% improvement in data completeness reduces analytical uncertainty and increases stakeholder confidence in reported metrics."
    )

    dq_findings = (
        f"{_status_badge('Completeness', f'{completeness:.1f}%', comp_status)}<br/>"
        f"{_status_badge('Duplicates', f'{dup_rows:,} rows ({dup_pct:.1f}%)', dup_status)}<br/>"
    )
    if len(missing_by_col) > 0:
        dq_findings += "<br/><strong>Columns with Missing Data:</strong><br/>"
        for col_name, cnt in list(missing_by_col.items())[:5]:
            pct = cnt / len(df) * 100
            sev = "bad" if pct > 20 else "warn" if pct > 5 else "ok"
            dq_findings += f"• {_status_badge(col_name, f'{cnt:,} missing ({pct:.1f}%)', sev)}<br/>"
    dq_findings += f"<br/><strong>Assessment:</strong> {quality_action}"
    _findings_box("INSIGHT 4 FINDINGS — Data Quality & Readiness", dq_findings)

    # ── Column role mapping ────────────────────────────────────────────────────
    with st.expander("📋 How Exalio mapped your columns to financial roles", expanded=False):
        role_cols = st.columns(4)
        role_labels = {
            'revenue':   '💵 Revenue', 'cost': '💸 Cost',
            'profit':    '📈 Profit',  'quantity': '📦 Volume',
            'date':      '📅 Date',    'customer': _ev('role_emoji', '👥') + ' ' + _ev('entity_label', 'Customer'),
            'product':   '🏷️ Product', 'other_numeric': '🔢 Other Numeric',
        }
        items = [(k, v) for k, v in col_roles.items() if v]
        for i, (role, cols_list) in enumerate(items):
            with role_cols[i % 4]:
                st.markdown(f"**{role_labels.get(role, role)}**")
                for c in cols_list:
                    st.markdown(f"- `{c}`")


def _compute_outliers_summary(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """Detect IQR-based outliers for every numeric column. Returns summary list."""
    results = []
    for col in df.select_dtypes(include='number').columns:
        s = pd.to_numeric(df[col], errors='coerce').dropna()
        if len(s) < 4:
            continue
        q1, q3 = float(s.quantile(0.25)), float(s.quantile(0.75))
        iqr = q3 - q1
        if iqr == 0:
            continue
        lo, hi  = q1 - 1.5 * iqr, q3 + 1.5 * iqr
        outliers = s[(s < lo) | (s > hi)]
        if len(outliers) == 0:
            continue
        results.append({
            'column':       col,
            'count':        len(outliers),
            'pct':          len(outliers) / len(s) * 100,
            'min_outlier':  float(outliers.min()),
            'max_outlier':  float(outliers.max()),
            'iqr_lo':       lo,
            'iqr_hi':       hi,
        })
    results.sort(key=lambda x: x['pct'], reverse=True)
    return results



# ── Canonical column → human-readable display label (used in Story 3) ──────
_CANON_LABELS = {
    'enrollment_tuition_amount':      'Tuition Revenue',
    'financial_aid_monetary_amount':  'Financial Aid',
    'cumulative_gpa':                 'Cumulative GPA',
    'enrollment_tuition_amount':      'Tuition Revenue',
    'estimated_annual_cost':          'Annual Cost',
    'current_term_charges':           'Term Charges',
    'past_due_balance':               'Past Due Balance',
    'total_payments_ytd':             'Payments YTD',
    'retention_probability':          'Retention Probability',
    'graduation_probability':         'Graduation Probability',
    'career_readiness_score':         'Career Readiness',
    'credits_attempted':              'Credits Attempted',
    'credit_hours':                   'Credit Hours',
    'terms_enrolled':                 'Terms Enrolled',
    'attendance_count':               'Attendance Count',
    'missed_classes_count':           'Missed Classes',
    'library_visits_count':           'Library Visits',
    'clubs_joined_count':             'Clubs Joined',
    'events_attended_count':          'Events Attended',
    'internship_count':               'Internship Count',
    'advisor_meeting_count':          'Advisor Meetings',
    'health_center_visits_count':     'Health Centre Visits',
    'grievance_count':                'Grievance Count',
    'assignment_submission_rate':     'Assignment Submission Rate',
    'credit_completion_rate':         'Credit Completion Rate',
    'stop_out_risk_flag':             'Stop-Out Risk',
    'age_at_first_enrollment':        'Age at Enrolment',
    'registered_billing_hours':       'Billing Hours',
    'unmet_financial_need':           'Unmet Financial Need',
    'financial_stress_indicator':     'Financial Stress',
}

def _friendly_col(col: str) -> str:
    """Return a human-readable label for a column name."""
    if col in _CANON_LABELS:
        return _CANON_LABELS[col]
    # fallback: title-case with underscores replaced
    return col.replace('_', ' ').title()

def _compute_strong_correlations(df: pd.DataFrame, threshold: float = 0.6) -> List[Dict[str, Any]]:
    """Return pairs of numeric columns with |corr| >= threshold."""
    num_df = df.select_dtypes(include='number')
    if num_df.shape[1] < 2:
        return []
    corr = num_df.corr()
    pairs = []
    cols = list(corr.columns)
    for i in range(len(cols)):
        for j in range(i + 1, len(cols)):
            r = corr.iloc[i, j]
            if abs(r) >= threshold and not np.isnan(r):
                pairs.append({
                    'col_a': cols[i], 'col_b': cols[j],
                    'r': round(float(r), 3),
                    'direction': 'positive' if r > 0 else 'negative',
                    'strength':  'strong' if abs(r) >= 0.8 else 'moderate',
                })
    pairs.sort(key=lambda x: abs(x['r']), reverse=True)
    return pairs


def _build_scatter_matrix(df: pd.DataFrame, col_roles: Dict[str, List[str]]) -> Optional[go.Figure]:
    """Scatter matrix for the top 4 most-relevant numeric columns."""
    rev_col  = (col_roles.get('revenue') or [None])[0]
    cost_col = (col_roles.get('cost')    or [None])[0]
    prof_col = (col_roles.get('profit')  or [None])[0]
    qty_col  = (col_roles.get('quantity') or [None])[0]

    candidate = [c for c in [rev_col, cost_col, prof_col, qty_col] if c]
    # Fill remaining slots from other numerics
    for c in df.select_dtypes(include='number').columns:
        if c not in candidate:
            candidate.append(c)
        if len(candidate) >= 4:
            break

    if len(candidate) < 2:
        return None

    cols_to_use = candidate[:4]
    # Pick a colour column if categorical exists
    cat_cols = df.select_dtypes(include='object').columns.tolist()
    color_col = (col_roles.get('product') or col_roles.get('customer') or
                 ([cat_cols[0]] if cat_cols else [None]))[0]

    try:
        plot_df = df[cols_to_use + ([color_col] if color_col else [])].dropna()
        if len(plot_df) > 2000:
            plot_df = plot_df.sample(2000, random_state=42)

        if color_col:
            fig = px.scatter_matrix(plot_df, dimensions=cols_to_use, color=color_col,
                                    title="Multi-Dimensional Scatter Matrix")
        else:
            fig = px.scatter_matrix(plot_df, dimensions=cols_to_use,
                                    title="Multi-Dimensional Scatter Matrix")

        fig.update_traces(marker=dict(size=3, opacity=0.6))
        fig.update_layout(
            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
            font=dict(color='#94a3b8', size=10),
            height=420,
            margin=dict(l=20, r=20, t=40, b=20),
        )
        return fig
    except Exception:
        return None


def render_advisory_tab(df, kpis, col_roles, advisory):
    """Tab 3: Strategic Advisor — 3-story structure with quantified impact & clear actions."""
    if not advisory:
        advisory = _rule_based_advisory(kpis)

    rev   = kpis.get('total_revenue', 0) or 0
    cost  = kpis.get('total_cost', 0) or 0
    prof  = kpis.get('total_profit', 0) or 0
    gm    = kpis.get('gross_margin_pct', _pct(prof, max(rev, 1)))
    mom   = kpis.get('mom_pct', 0) or 0
    scores = advisory.get('advisory_score', {})
    overall_score = scores.get('overall', 0)

    # ── Overall health banner ──────────────────────────────────────────────────
    health_color = "#10b981" if overall_score >= 70 else "#f59e0b" if overall_score >= 45 else "#ef4444"
    health_label = "FINANCIALLY HEALTHY" if overall_score >= 70 else "NEEDS ATTENTION" if overall_score >= 45 else "CRITICAL — ACT NOW"
    health_icon  = "✅" if overall_score >= 70 else "⚠️" if overall_score >= 45 else "🔴"

    _adv_exec_summary = str(advisory.get('executive_summary', '')).replace('{', '&#123;').replace('}', '&#125;')
    st.markdown(
        f'<div style="background:linear-gradient(135deg,rgba(15,36,68,0.9),rgba(26,51,85,0.9));'
        f'border:2px solid {health_color};border-radius:14px;'
        f'padding:20px 28px;margin-bottom:20px;'
        f'display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px;">'
        f'<div>'
        f'<div style="font-size:0.72rem;color:#94a3b8;text-transform:uppercase;letter-spacing:1.5px;">'
        'Overall Financial Health'
        f'</div>'
        f'<div style="font-size:1.6rem;font-weight:800;color:{health_color};margin-top:4px;">'
        f'{health_icon} {health_label}'
        '</div>'
        '<div style="font-size:0.88rem;color:#cbd5e1;margin-top:6px;max-width:600px;line-height:1.6;">'
        + _adv_exec_summary +
        '</div></div>'
        f'<div style="text-align:center;">'
        f'<div style="font-size:3rem;font-weight:800;color:{health_color};">{overall_score}</div>'
        '<div style="font-size:0.7rem;color:#64748b;text-transform:uppercase;">/ 100 Score</div>'
        '</div></div>',
        unsafe_allow_html=True
    )

    # ── Health pills row ───────────────────────────────────────────────────────
    pill_cols = st.columns(4)
    pill_items = [
        ("Revenue Health", advisory.get('revenue_health', 'caution')),
        ("Margin Health",  advisory.get('margin_health', 'caution')),
        ("Overall Score",  "excellent" if overall_score >= 80 else "good" if overall_score >= 60 else "caution" if overall_score >= 40 else "critical"),
        ("Data Quality",   "excellent" if scores.get('data_quality', 0) >= 80 else "good" if scores.get('data_quality', 0) >= 60 else "caution"),
    ]
    for col_w, (label, status) in zip(pill_cols, pill_items):
        with col_w:
            render_status_pill(label, status)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── STORY 1: Revenue Opportunities — Ranked by Impact ─────────────────────
    render_section_header("🚀", "STORY 1: Financial & Programme Opportunities", "RANKED BY IMPACT")

    opps = advisory.get('opportunities', [])
    impact_order = {'high': 0, 'medium': 1, 'low': 2}
    opps_sorted  = sorted(opps, key=lambda x: impact_order.get(x.get('impact', 'medium'), 1))

    opp_left, opp_right = st.columns([3, 2])
    with opp_left:
        for rank, opp in enumerate(opps_sorted, 1):
            impact = opp.get('impact', 'medium')
            color_map = {'high': ('#10b981', 'green'), 'medium': ('#f59e0b', ''), 'low': ('#3b82f6', 'blue')}
            imp_color, card_color = color_map.get(impact, ('#94a3b8', ''))
            impact_value = (
                f"~{_fmt(rev * 0.05, prefix='$')} potential" if impact == 'high' else
                f"~{_fmt(rev * 0.02, prefix='$')} potential" if impact == 'medium' else
                f"~{_fmt(rev * 0.01, prefix='$')} potential"
            )
            _opp_t = str(opp.get('title','')).replace('<','&lt;').replace('>','&gt;')
            _opp_d = str(opp.get('description','')).replace('<','&lt;').replace('>','&gt;')
            _opp_a = str(opp.get('action','')).replace('<','&lt;').replace('>','&gt;')
            st.markdown(
                f'<div style="background:linear-gradient(145deg,#0d1f35,#132840);'
                f'border-left:4px solid {imp_color};border-radius:0 12px 12px 0;'
                f'padding:16px 18px;margin-bottom:12px;">'
                f'<div style="display:flex;justify-content:space-between;align-items:flex-start;">'
                f'<div style="font-weight:700;font-size:0.92rem;color:#f1f5f9;">'
                f'#{rank} ' + _opp_t +
                f'</div>'
                f'<span style="background:{imp_color}22;color:{imp_color};font-size:0.68rem;'
                f'font-weight:700;padding:2px 10px;border-radius:20px;'
                f'border:1px solid {imp_color}44;white-space:nowrap;margin-left:8px;">'
                f'{impact.upper()} IMPACT · {impact_value}'
                '</span></div>'
                '<div style="font-size:0.84rem;color:#94a3b8;line-height:1.55;margin:8px 0;">'
                + _opp_d +
                '</div>'
                '<div style="background:rgba(245,158,11,0.08);border:1px solid rgba(245,158,11,0.2);'
                'border-radius:6px;padding:6px 12px;margin-top:8px;'
                'font-size:0.78rem;color:#f59e0b;font-weight:600;">'
                '▶ ACTION: ' + _opp_a +
                '</div></div>',
                unsafe_allow_html=True
            )

    with opp_right:
        render_section_header("📡", "Health Radar")
        if scores:
            st.plotly_chart(_build_advisory_score_radar(scores),
                            use_container_width=True, config={'displayModeBar': False},
                                        key="pc_3447")
        st.markdown("<br>", unsafe_allow_html=True)
        for label, key in [("Revenue Growth","revenue_growth"), ("Profitability","profitability"),
                            ("Data Quality","data_quality"), ("Strategic Clarity","strategic_clarity")]:
            render_health_indicator(label, scores.get(key, 0))

    _business_impact_box(
        "💼", "Institutional Impact: Quantified Programme & Financial Opportunity Stack",
        f"Based on a current income base of <strong>{_fmt(rev, prefix='$')}</strong>, the identified opportunities "
        f"represent a combined improvement potential of approximately "
        f"<strong>{_fmt(rev * 0.08, prefix='$')}</strong> "
        f"(conservative estimate: 5-8% income improvement from executing all {len(opps)} actions). "
        f"High-impact items alone could deliver <strong>{_fmt(rev * 0.05, prefix='$')}</strong>. "
        f"Sequence: address opportunity #1 first as it delivers the highest return relative to implementation effort. "
        + (f"<br/><strong>Student risk context:</strong> {kpis.get('at_risk_count','N/A')} at-risk students "
           f"({kpis.get('at_risk_pct',0):.1f}% of population) represent direct retention revenue exposure. "
           f"Each retained student represents ~{_fmt(rev / max(kpis.get('unique_customers',1),1), prefix='$')} in annual income."
           if kpis.get('at_risk_count') else '')
    )
    _findings_box(
        "STORY 1 FINDINGS — Opportunity Priority Stack",
        f"<strong>{len([o for o in opps if o.get('impact')=='high'])} HIGH</strong> · "
        f"<strong>{len([o for o in opps if o.get('impact')=='medium'])} MEDIUM</strong> · "
        f"<strong>{len([o for o in opps if o.get('impact')=='low'])} LOW</strong> impact opportunities identified.<br/><br/>"
        + "<br/>".join(
            f"#{r+1} <strong>{o.get('title','')}</strong> [{o.get('impact','').upper()}] — "
            f"{o.get('action','')}"
            for r, o in enumerate(opps_sorted[:4])
        ) + "<br/><br/>"
        f"<strong>Execute in this order:</strong> High → Medium → Low. "
        f"Review outcomes after 30 days before proceeding to next tier."
    )

    # ── STORY 2: Risk Flags — Severity × Likelihood ───────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    render_section_header("⚠️", "STORY 2: Financial Risk Flags & Mitigation Plan", "SEVERITY × LIKELIHOOD")

    risks = advisory.get('risks', [])
    sev_order = {'high': 0, 'medium': 1, 'low': 2}
    risks_sorted = sorted(risks, key=lambda x: sev_order.get(x.get('severity', 'medium'), 1))

    risk_left, risk_right = st.columns([3, 2])
    with risk_left:
        for rank, risk in enumerate(risks_sorted, 1):
            sev = risk.get('severity', 'medium')
            sev_map = {'high': ('#ef4444', 'red'), 'medium': ('#8b5cf6', 'purple'), 'low': ('#3b82f6', 'blue')}
            sev_color, _ = sev_map.get(sev, ('#94a3b8', ''))
            revenue_at_risk = (
                f"~{_fmt(rev * 0.15, prefix='$')} at risk" if sev == 'high' else
                f"~{_fmt(rev * 0.07, prefix='$')} at risk" if sev == 'medium' else
                f"~{_fmt(rev * 0.02, prefix='$')} at risk"
            )
            _risk_t = str(risk.get('title','')).replace('<','&lt;').replace('>','&gt;')
            _risk_d = str(risk.get('description','')).replace('<','&lt;').replace('>','&gt;')
            _risk_m = str(risk.get('mitigation','')).replace('<','&lt;').replace('>','&gt;')
            st.markdown(
                f'<div style="background:linear-gradient(145deg,#1a0d0d,#200f0f);'
                f'border-left:4px solid {sev_color};border-radius:0 12px 12px 0;'
                f'padding:16px 18px;margin-bottom:12px;">'
                f'<div style="display:flex;justify-content:space-between;align-items:flex-start;">'
                f'<div style="font-weight:700;font-size:0.92rem;color:#f1f5f9;">'
                f'#{rank} ' + _risk_t +
                f'</div>'
                f'<span style="background:{sev_color}22;color:{sev_color};font-size:0.68rem;'
                f'font-weight:700;padding:2px 10px;border-radius:20px;'
                f'border:1px solid {sev_color}44;white-space:nowrap;margin-left:8px;">'
                f'{sev.upper()} SEVERITY · {revenue_at_risk}'
                '</span></div>'
                '<div style="font-size:0.84rem;color:#94a3b8;line-height:1.55;margin:8px 0;">'
                + _risk_d +
                '</div>'
                '<div style="background:rgba(239,68,68,0.08);border:1px solid rgba(239,68,68,0.2);'
                'border-radius:6px;padding:6px 12px;margin-top:8px;'
                'font-size:0.78rem;color:#fca5a5;font-weight:600;">'
                '🛡 MITIGATION: ' + _risk_m +
                '</div></div>',
                unsafe_allow_html=True
            )

    with risk_right:
        outliers = _compute_outliers_summary(df)
        st.markdown("**Statistical Risk Signals**")
        if outliers:
            for o in outliers[:4]:
                sev_c = '#ef4444' if o['pct'] > 10 else '#f59e0b' if o['pct'] > 5 else '#64748b'
                st.markdown(f"""
                <div style="padding:8px 12px;margin-bottom:6px;border-left:3px solid {sev_c};
                            background:rgba(255,255,255,0.02);border-radius:0 8px 8px 0;">
                    <div style="font-size:0.8rem;font-weight:700;color:#e2e8f0;">
                        <code>{o['column']}</code>
                        <span style="color:{sev_c};margin-left:6px;">{o['pct']:.1f}% outliers</span>
                    </div>
                    <div style="font-size:0.73rem;color:#64748b;margin-top:2px;">
                        Max: {_fmt(o['max_outlier'])} · IQR ceiling: {_fmt(o['iqr_hi'])}
                    </div>
                    <div style="font-size:0.73rem;color:{sev_c};margin-top:2px;">
                        {"🔴 Investigate — may signal fraud or data error" if o['pct'] > 10
                         else "⚠️ Review — unusual values detected"
                         if o['pct'] > 5 else "ℹ️ Monitor — minor anomalies"}
                    </div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.success("✅ No statistical outliers — data signals are clean.")

    _business_impact_box(
        "💼", "Institutional Impact: Financial Surplus Protected vs Surplus at Risk",
        f"Identified risks represent a potential financial exposure of up to "
        f"<strong>{_fmt(rev * 0.15, prefix='$')}</strong> if high-severity items go unaddressed. "
        f"{'High-severity income concentration risk means a single programme or cohort disruption could remove ' + _fmt(rev * 0.1, prefix='$') + ' from institutional income.' if gm < 20 else 'Current margin levels provide a buffer, but sustained risk exposure without mitigation will erode institutional financial sustainability.'} "
        f"Execute mitigation actions within <strong>14 days</strong> for high-severity items."
        + (f"<br/><strong>Financial hold alerts:</strong> {kpis.get('financial_holds',0):,} students on financial hold; "
           f"{kpis.get('students_past_due',0):,} with past-due balances totalling ${kpis.get('total_past_due',0):,.0f}."
           if kpis.get('financial_holds') or kpis.get('students_past_due') else '')
    )
    _findings_box(
        "STORY 2 FINDINGS — Risk Register & Mitigation",
        f"<strong>Risks by severity:</strong> "
        f"{len([r for r in risks if r.get('severity')=='high'])} HIGH · "
        f"{len([r for r in risks if r.get('severity')=='medium'])} MEDIUM · "
        f"{len([r for r in risks if r.get('severity')=='low'])} LOW<br/><br/>"
        + "<br/>".join(
            f"#{r+1} <strong>{rk.get('title','')}</strong> [{rk.get('severity','').upper()}] — "
            f"Mitigate by: {rk.get('mitigation','')}"
            for r, rk in enumerate(risks_sorted[:4])
        ) + "<br/><br/>"
        f"<strong>Statistical outliers:</strong> "
        f"{len(outliers)} column(s) with unusual values detected.<br/>"
        f"<strong>Action timeline:</strong> HIGH severity → this week. MEDIUM → this month. LOW → next quarter."
    )

    # ── STORY 3: Performance Decomposition ────────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    render_section_header("📈", "STORY 3: Performance Decomposition", "UNDERSTANDING THE PATTERNS")

    num_df = df.select_dtypes(include='number')
    pairs  = _compute_strong_correlations(df, threshold=0.5)

    # ── Section intro ──────────────────────────────────────────────────────
    st.markdown(
        "<p style='color:#94a3b8;font-size:0.95rem;margin-bottom:1rem;'>"
        "How are your key financial and academic metrics distributed? "
        "Where is performance consistent — and where is it volatile? "
        "Which metrics move together, and what does that mean for planning?"
        "</p>",
        unsafe_allow_html=True
    )

    # ── Row 1: Volatility Scorecards ──────────────────────────────────────
    st.markdown("#### 📊 Metric Stability Overview")
    st.caption("For each key metric: how consistent is performance across students? Green = stable, Amber = watch, Red = investigate.")

    # Pick the most meaningful numeric columns to display (catalog-priority order)
    _priority_cols = [
        'enrollment_tuition_amount', 'financial_aid_monetary_amount', 'cumulative_gpa',
        'retention_probability', 'graduation_probability', 'estimated_annual_cost',
        'past_due_balance', 'total_payments_ytd', 'career_readiness_score',
        'credit_completion_rate', 'assignment_submission_rate', 'credits_attempted',
    ]
    _display_cols = [c for c in _priority_cols if c in df.columns]
    # fill up to 8 with any remaining numerics
    for _c in num_df.columns:
        if _c not in _display_cols:
            _display_cols.append(_c)
        if len(_display_cols) >= 8:
            break
    _display_cols = _display_cols[:8]

    _vol_cards_html = ""
    _vol_data = []  # for findings box
    for _cn in _display_cols:
        _s = pd.to_numeric(df[_cn], errors='coerce').dropna()
        if len(_s) < 2:
            continue
        _mean  = float(_s.mean())
        _std   = float(_s.std())
        _min   = float(_s.min())
        _max   = float(_s.max())
        _cv    = (_std / max(abs(_mean), 1e-9)) * 100
        _label = _friendly_col(_cn)
        _pct_range = (_max - _min) / max(abs(_mean), 1e-9) * 100

        # Stability tier
        if _cv < 15:
            _tier = "Stable"; _tc = "#10b981"; _icon = "✅"; _note = "Consistent across students — reliable for planning"
        elif _cv < 35:
            _tier = "Moderate"; _tc = "#f59e0b"; _icon = "⚠️"; _note = "Some variation — monitor by cohort or programme"
        else:
            _tier = "High Variation"; _tc = "#ef4444"; _icon = "🔴"; _note = "Wide spread — investigate outlier groups"

        # Format mean nicely
        if abs(_mean) >= 1e6:
            _mean_str = f"AED {_mean/1e6:.1f}M avg"
        elif abs(_mean) >= 1000:
            _mean_str = f"AED {_mean:,.0f} avg" if any(k in _cn for k in ['amount','cost','balance','revenue','payment','charges','tuition','aid']) else f"{_mean:,.0f} avg"
        elif 0 <= _mean <= 4.5 and 'gpa' in _cn.lower():
            _mean_str = f"{_mean:.2f} avg GPA"
        elif 0 <= _mean <= 100 and any(k in _cn for k in ['rate','pct','probability','score','completion']):
            _mean_str = f"{_mean:.1f}% avg"
        else:
            _mean_str = f"{_mean:.1f} avg"

        _vol_data.append({'label': _label, 'tier': _tier, 'cv': _cv, 'mean_str': _mean_str, 'note': _note})
        _vol_cards_html += f"""
        <div style="background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);
                    border-top:3px solid {_tc};border-radius:8px;padding:10px 14px;
                    min-width:160px;flex:1;">
            <div style="color:#94a3b8;font-size:0.72rem;font-weight:600;letter-spacing:0.4px;margin-bottom:4px;">
                {_label.upper()}
            </div>
            <div style="color:#f1f5f9;font-size:1rem;font-weight:700;margin-bottom:2px;">{_mean_str}</div>
            <div style="color:{_tc};font-size:0.75rem;font-weight:700;">{_icon} {_tier}</div>
            <div style="color:#64748b;font-size:0.7rem;margin-top:3px;line-height:1.4;">{_note}</div>
        </div>"""

    if _vol_cards_html:
        st.markdown(
            f'<div style="display:flex;flex-wrap:wrap;gap:10px;margin-bottom:1.2rem;">'
            f'{_vol_cards_html}</div>',
            unsafe_allow_html=True
        )

    # ── Row 2: Correlation heatmap + Top breakdown ─────────────────────────
    s3_col1, s3_col2 = st.columns([1, 1])

    with s3_col1:
        st.markdown("#### 🔗 Metric Relationships")
        st.caption("Which metrics move together? Strong connections (dark squares) = predictive indicators you can use for early warning.")
        _heat_cols = _display_cols[:6]
        _heat_df   = df[_heat_cols].apply(pd.to_numeric, errors='coerce').dropna()
        if len(_heat_df) > 1 and len(_heat_cols) >= 2:
            _corr = _heat_df.corr().round(2)
            _labels = [_friendly_col(c) for c in _heat_cols]
            _heat_fig = go.Figure(data=go.Heatmap(
                z=_corr.values,
                x=_labels,
                y=_labels,
                colorscale=[
                    [0.0,  '#ef4444'],
                    [0.25, '#f59e0b'],
                    [0.5,  '#1e293b'],
                    [0.75, '#3b82f6'],
                    [1.0,  '#10b981'],
                ],
                zmid=0,
                zmin=-1, zmax=1,
                text=_corr.values.round(2),
                texttemplate="%{text}",
                textfont=dict(size=11, color='white', family='Arial Black'),
                hovertemplate='<b>%{y} vs %{x}</b><br>Correlation: %{z:.2f}<extra></extra>',
                showscale=True,
                colorbar=dict(
                    title=dict(text="r", font=dict(color='white', size=11)),
                    tickfont=dict(color='white', size=10),
                    thickness=12, len=0.8
                )
            ))
            _heat_fig.update_layout(
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                font=dict(color='white', size=11),
                height=380,
                margin=dict(l=10, r=10, t=20, b=10),
                xaxis=dict(tickfont=dict(size=10, color='#e2e8f0'), tickangle=-30),
                yaxis=dict(tickfont=dict(size=10, color='#e2e8f0')),
            )
            st.plotly_chart(_heat_fig, use_container_width=True, config={'displayModeBar': False}, key="pc_s3_heatmap")

            # Plain-English correlation insights
            _strong = [p for p in pairs if abs(p['r']) >= 0.6]
            _mod    = [p for p in pairs if 0.4 <= abs(p['r']) < 0.6]
            if _strong:
                for _p in _strong[:3]:
                    _dir_txt = "rise together" if _p['direction'] == 'positive' else "move in opposite directions"
                    _la = _friendly_col(_p['col_a']); _lb = _friendly_col(_p['col_b'])
                    _col_r = "#10b981" if _p['direction'] == 'positive' else "#f59e0b"
                    st.markdown(
                        f'<div style="padding:8px 12px;margin-bottom:6px;border-left:3px solid {_col_r};'
                        f'background:rgba(255,255,255,0.02);border-radius:0 6px 6px 0;">'
                        f'<span style="color:#e2e8f0;font-size:0.82rem;font-weight:700;">{_la} ↔ {_lb}</span>'
                        f'<span style="color:{_col_r};font-size:0.75rem;font-weight:600;margin-left:8px;">r={_p["r"]}</span><br/>'
                        f'<span style="color:#94a3b8;font-size:0.75rem;">These metrics {_dir_txt} — '
                        f'{"use one to predict the other in planning models." if _p["direction"]=="positive" else "improving one may put pressure on the other."}'
                        f'</span></div>',
                        unsafe_allow_html=True
                    )
            elif _mod:
                st.info(f"Moderate relationships found between {len(_mod)} metric pair(s). No single metric strongly drives another — performance is multi-factorial.")
            else:
                st.info("Metrics are largely independent — no single factor dominates performance. Use a balanced scorecard approach for monitoring.")

    with s3_col2:
        st.markdown("#### 🏫 Performance Breakdown by Segment")
        st.caption("How does performance vary across student segments? Identifies which groups need attention.")

        # Pick best categorical dimension and best numeric metric to break down
        _seg_candidates = ['academic_program', 'academic_college', 'academic_department',
                           'academic_major', 'enrollment_type', 'cohort_year',
                           'enrollment_enrollment_status', 'nationality', 'gender']
        _seg_col = next((c for c in _seg_candidates if c in df.columns), None)
        if _seg_col is None:
            _seg_col = next((c for c in df.select_dtypes(include='object').columns), None)

        _metric_candidates = ['cumulative_gpa', 'retention_probability', 'graduation_probability',
                              'enrollment_tuition_amount', 'financial_aid_monetary_amount',
                              'career_readiness_score', 'credit_completion_rate']
        _metric_col = next((c for c in _metric_candidates if c in df.columns), None)
        if _metric_col is None:
            _metric_col = num_df.columns[0] if len(num_df.columns) > 0 else None

        if _seg_col and _metric_col:
            _seg_data = (
                df.groupby(_seg_col)[_metric_col]
                .apply(lambda x: pd.to_numeric(x, errors='coerce').mean())
                .dropna()
                .sort_values(ascending=False)
                .head(10)
                .reset_index()
            )
            _seg_data.columns = ['Segment', 'Value']
            _seg_label   = _friendly_col(_seg_col)
            _metric_label= _friendly_col(_metric_col)
            _overall_avg = pd.to_numeric(df[_metric_col], errors='coerce').mean()

            # Color bars by above/below average
            _bar_colors = [
                '#10b981' if v >= _overall_avg else '#ef4444'
                for v in _seg_data['Value']
            ]

            # Format axis
            _is_money = any(k in _metric_col for k in ['amount','cost','balance','revenue','payment','charges','tuition','aid'])
            _is_pct   = any(k in _metric_col for k in ['rate','probability','score','completion'])
            if _is_money:
                _tick_fmt   = 'AED ,.0f'
                _avg_label  = f"Avg: AED {_overall_avg:,.0f}"
                _val_fmt    = lambda v: f"AED {v:,.0f}"
            elif _is_pct:
                _tick_fmt   = '.1f'
                _avg_label  = f"Avg: {_overall_avg:.1f}%"
                _val_fmt    = lambda v: f"{v:.1f}%"
            else:
                _tick_fmt   = '.2f'
                _avg_label  = f"Avg: {_overall_avg:.2f}"
                _val_fmt    = lambda v: f"{v:.2f}"

            _seg_fig = go.Figure()
            _seg_fig.add_trace(go.Bar(
                x=_seg_data['Value'],
                y=_seg_data['Segment'],
                orientation='h',
                marker=dict(color=_bar_colors, line=dict(color='rgba(255,255,255,0.2)', width=1)),
                text=[_val_fmt(v) for v in _seg_data['Value']],
                textposition='outside',
                textfont=dict(size=11, color='white', family='Arial Black'),
                hovertemplate='<b>%{y}</b><br>' + _metric_label + ': %{x:.2f}<extra></extra>',
            ))
            # Average line
            _seg_fig.add_vline(
                x=_overall_avg, line_dash='dash',
                line_color='rgba(245,158,11,0.8)', line_width=2,
                annotation_text=_avg_label,
                annotation_position='top right',
                annotation_font=dict(size=10, color='#f59e0b')
            )
            _seg_fig.update_layout(
                title=dict(
                    text=f"{_metric_label} by {_seg_label}",
                    font=dict(size=14, color='white', family='Arial Black'),
                    x=0, xanchor='left'
                ),
                xaxis=dict(
                    title=_metric_label,
                    tickfont=dict(size=10, color='#e2e8f0'),
                    gridcolor='rgba(255,255,255,0.08)',
                    title_font=dict(size=11, color='#94a3b8')
                ),
                yaxis=dict(
                    tickfont=dict(size=11, color='#e2e8f0'),
                    autorange='reversed'
                ),
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                font=dict(color='white', size=11),
                height=380,
                margin=dict(l=10, r=80, t=50, b=20),
                showlegend=False,
            )
            st.plotly_chart(_seg_fig, use_container_width=True, config={'displayModeBar': False}, key="pc_s3_seg")

            # Best and worst segment callout
            _best = _seg_data.iloc[0]
            _worst = _seg_data.iloc[-1]
            _gap   = abs(_best['Value'] - _worst['Value'])
            if _is_money:
                _gap_str = f"AED {_gap:,.0f}"
            elif _is_pct:
                _gap_str = f"{_gap:.1f} percentage points"
            else:
                _gap_str = f"{_gap:.2f}"
            st.markdown(
                f'<div style="display:flex;gap:8px;margin-top:6px;">'
                f'<div style="flex:1;padding:8px 12px;background:rgba(16,185,129,0.1);border:1px solid rgba(16,185,129,0.3);border-radius:6px;">'
                f'<div style="color:#10b981;font-size:0.72rem;font-weight:700;">🏆 TOP SEGMENT</div>'
                f'<div style="color:#f1f5f9;font-size:0.85rem;font-weight:700;margin-top:2px;">{_best["Segment"]}</div>'
                f'<div style="color:#94a3b8;font-size:0.75rem;">{_val_fmt(_best["Value"])}</div>'
                f'</div>'
                f'<div style="flex:1;padding:8px 12px;background:rgba(239,68,68,0.08);border:1px solid rgba(239,68,68,0.25);border-radius:6px;">'
                f'<div style="color:#ef4444;font-size:0.72rem;font-weight:700;">⚠️ NEEDS FOCUS</div>'
                f'<div style="color:#f1f5f9;font-size:0.85rem;font-weight:700;margin-top:2px;">{_worst["Segment"]}</div>'
                f'<div style="color:#94a3b8;font-size:0.75rem;">{_val_fmt(_worst["Value"])}</div>'
                f'</div>'
                f'</div>'
                f'<div style="color:#64748b;font-size:0.73rem;margin-top:6px;">Gap between best and worst: <strong style="color:#e2e8f0;">{_gap_str}</strong></div>',
                unsafe_allow_html=True
            )
        else:
            st.info("No categorical segment column found — breakdown unavailable.")

    # ── Business Impact ────────────────────────────────────────────────────
    _n_stable   = sum(1 for d in _vol_data if d['tier'] == 'Stable')
    _n_volatile = sum(1 for d in _vol_data if d['tier'] == 'High Variation')
    _n_watch    = sum(1 for d in _vol_data if d['tier'] == 'Moderate')
    _n_strong_pairs = len([p for p in pairs if abs(p['r']) >= 0.6])

    _business_impact_box(
        "💼", "Institutional Impact: Understanding What Drives Performance",
        f"Analysis of {len(_display_cols)} key metrics shows "
        f"{_n_stable} stable, {_n_watch} moderate, and {_n_volatile} high-variation indicator(s). "
        f"{'Stable metrics support reliable forecasting and budget planning.' if _n_stable > _n_volatile else 'High variation in key metrics requires conservative assumptions in financial projections — build in buffers.'} "
        f"{f'{_n_strong_pairs} strong metric relationship(s) detected — use these as predictive leading indicators in your reporting dashboards.' if _n_strong_pairs else 'Metrics are largely independent, reducing systemic risk but requiring separate monitoring for each dimension.'}"
    )

    # ── Findings Box ───────────────────────────────────────────────────────
    _findings_lines = []
    for _vd in _vol_data[:5]:
        _icon_f = "✅" if _vd['tier'] == 'Stable' else ("⚠️" if _vd['tier'] == 'Moderate' else "🔴")
        _findings_lines.append(
            f"&bull; <strong>{_vd['label']}</strong> — {_vd['mean_str']} &nbsp; {_icon_f} {_vd['tier']}: {_vd['note']}"
        )
    _corr_lines = []
    for _p in pairs[:3]:
        _dir_txt = "positive link" if _p['direction'] == 'positive' else "inverse link"
        _corr_lines.append(
            f"&bull; <strong>{_friendly_col(_p['col_a'])} ↔ {_friendly_col(_p['col_b'])}</strong> "
            f"(r={_p['r']}, {_dir_txt})"
        )

    _findings_box(
        "STORY 3 FINDINGS — Performance Decomposition",
        f"<strong>Metrics reviewed:</strong> {len(_display_cols)} key indicators | "
        f"<strong>Stable:</strong> {_n_stable} | <strong>Watch:</strong> {_n_watch} | <strong>High Variation:</strong> {_n_volatile}<br/><br/>"
        + "<br/>".join(_findings_lines)
        + ("<br/><br/><strong>Key Metric Relationships:</strong><br/>" + "<br/>".join(_corr_lines) if _corr_lines else "<br/><br/>No strong metric correlations above threshold.")
        + "<br/><br/><strong>Action:</strong> "
        + ("Focus remediation effort on high-variation metrics first. " if _n_volatile else "")
        + ("Use correlated metrics as early-warning indicators in dashboards. " if _corr_lines else "")
        + "Segment-level breakdown identifies which student groups need targeted interventions."
    )


def _compute_revenue_projection(kpis: Dict[str, Any], periods: int = 3) -> List[Dict[str, Any]]:
    """
    Project the next N periods based on the linear trend of the historical revenue series.
    Returns list of {period, projected_value, confidence_band_lo, confidence_band_hi}.
    """
    if 'revenue_trend' not in kpis:
        return []
    trend = kpis['revenue_trend']
    if len(trend) < 3:
        return []
    vals = trend.values.astype(float)
    x    = np.arange(len(vals))
    # Linear regression
    m, b = np.polyfit(x, vals, 1)
    residuals = vals - (m * x + b)
    std_err   = float(np.std(residuals))

    last_label = str(trend.index[-1])
    projections = []
    for i in range(1, periods + 1):
        proj_val = float(m * (len(vals) + i - 1) + b)
        projections.append({
            'period':    f"Projected +{i}",
            'value':     max(proj_val, 0),
            'lo':        max(proj_val - 1.5 * std_err, 0),
            'hi':        proj_val + 1.5 * std_err,
            'slope':     float(m),
        })
    return projections


def _build_projection_chart(kpis: Dict[str, Any]) -> Optional[go.Figure]:
    """Revenue history + 3-period linear projection with confidence band."""
    if 'revenue_trend' not in kpis:
        return None
    trend = kpis['revenue_trend']
    if len(trend) < 3:
        return None

    labels = [str(p) for p in trend.index]
    vals   = trend.values.tolist()
    projections = _compute_revenue_projection(kpis, periods=3)

    fig = go.Figure()

    # Historical line
    fig.add_trace(go.Scatter(
        x=labels, y=vals,
        mode='lines+markers', name='Historical',
        line=dict(color='#f59e0b', width=3),
        marker=dict(size=6, color='#f59e0b'),
        fill='tozeroy', fillcolor='rgba(245,158,11,0.06)',
    ))

    if projections:
        proj_labels = [p['period'] for p in projections]
        proj_vals   = [p['value']  for p in projections]
        proj_lo     = [p['lo']     for p in projections]
        proj_hi     = [p['hi']     for p in projections]

        # Confidence band
        fig.add_trace(go.Scatter(
            x=proj_labels + proj_labels[::-1],
            y=proj_hi + proj_lo[::-1],
            fill='toself', fillcolor='rgba(59,130,246,0.08)',
            line=dict(color='rgba(0,0,0,0)'),
            hoverinfo='skip', showlegend=False, name='Confidence Band',
        ))
        # Projection line
        fig.add_trace(go.Scatter(
            x=proj_labels, y=proj_vals,
            mode='lines+markers', name='Projection',
            line=dict(color='#3b82f6', width=2, dash='dash'),
            marker=dict(size=7, color='#3b82f6', symbol='diamond'),
        ))

    fig.update_layout(
        title=dict(text="Revenue History + 3-Period Projection", font=dict(color='#f1f5f9', size=13)),
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#94a3b8'),
        xaxis=dict(gridcolor='rgba(255,255,255,0.05)', tickangle=-30),
        yaxis=dict(gridcolor='rgba(255,255,255,0.05)', tickprefix='$', tickformat=',.0f'),
        legend=dict(bgcolor='rgba(0,0,0,0)', font=dict(size=10)),
        margin=dict(l=10, r=10, t=40, b=30),
        height=300,
    )
    return fig


def _build_growth_decomposition(df: pd.DataFrame, kpis: Dict[str, Any], col_roles: Dict[str, List[str]]) -> Optional[go.Figure]:
    """
    Stacked bar: revenue decomposed by top categorical dimension (product/segment/region).
    Shows month-by-month contribution per category.
    """
    if 'revenue_trend' not in kpis:
        return None
    date_cols = col_roles.get('date', [])
    rev_cols  = col_roles.get('revenue', [])
    if not date_cols or not rev_cols:
        return None

    cat_cols = col_roles.get('product') or col_roles.get('customer') or []
    if not cat_cols:
        cat_cols = df.select_dtypes(include='object').columns.tolist()
    if not cat_cols:
        return None

    date_col = date_cols[0]
    rev_col  = rev_cols[0]
    cat_col  = cat_cols[0]

    try:
        tmp = df[[date_col, cat_col, rev_col]].copy()
        tmp[date_col] = pd.to_datetime(tmp[date_col], errors='coerce')
        tmp = tmp.dropna()
        tmp['_period'] = tmp[date_col].dt.to_period('M').astype(str)

        # Keep top 5 categories
        top_cats = tmp.groupby(cat_col)[rev_col].sum().nlargest(5).index.tolist()
        tmp = tmp[tmp[cat_col].isin(top_cats)]

        pivot = tmp.pivot_table(index='_period', columns=cat_col, values=rev_col,
                                aggfunc='sum', fill_value=0)
        pivot = pivot.sort_index()

        colours = ['#f59e0b','#10b981','#3b82f6','#8b5cf6','#ef4444']
        fig = go.Figure()
        for i, cat in enumerate(pivot.columns):
            fig.add_trace(go.Bar(
                x=pivot.index.tolist(),
                y=pivot[cat].tolist(),
                name=str(cat),
                marker_color=colours[i % len(colours)],
            ))
        fig.update_layout(
            barmode='stack',
            title=dict(text=f"Revenue Stack by {cat_col}", font=dict(color='#f1f5f9', size=13)),
            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
            font=dict(color='#94a3b8'),
            xaxis=dict(gridcolor='rgba(255,255,255,0.05)', tickangle=-30),
            yaxis=dict(gridcolor='rgba(255,255,255,0.05)', tickprefix='$', tickformat=',.0f'),
            legend=dict(bgcolor='rgba(0,0,0,0)', font=dict(size=9), orientation='h',
                        yanchor='bottom', y=1.02),
            margin=dict(l=10, r=10, t=60, b=30),
            height=300,
        )
        return fig
    except Exception:
        return None


def render_forward_guidance_tab(df, kpis, col_roles, advisory):
    """Tab 4: Forward Guidance — data-driven projection + 30/90 day roadmap."""
    if not advisory:
        advisory = _rule_based_advisory(kpis)

    render_section_header("🔭", "Forward Guidance", "DATA-DRIVEN FORECAST & ROADMAP")

    # ── Pull key metrics ──
    rev        = kpis.get('total_revenue', kpis.get('avg_revenue', 0)) or 0
    gm         = kpis.get('gross_margin_pct')
    mom_pct    = kpis.get('mom_pct')
    num_df     = df.select_dtypes(include='number')
    projections = _compute_revenue_projection(kpis, periods=3)
    slope       = projections[0]['slope'] if projections else 0

    # ── Revenue sustainability score (0-100) ──
    # Based on: margin health (40pts), growth trajectory (30pts), data completeness (30pts)
    margin_score = (40 if (gm or 0) > 30 else 25 if (gm or 0) > 15 else 10) if gm is not None else 15
    growth_score = (30 if slope > 0 else 10) if projections else 15
    completeness_pct = (1 - df.isnull().sum().sum() / max(df.size, 1)) * 100
    data_score   = 30 if completeness_pct >= 95 else 20 if completeness_pct >= 80 else 10
    sustain_score = margin_score + growth_score + data_score

    sustain_label = ("Strong" if sustain_score >= 75 else
                     "Moderate" if sustain_score >= 50 else "Needs Attention")
    sustain_color = "#10b981" if sustain_score >= 75 else "#f59e0b" if sustain_score >= 50 else "#ef4444"

    # ═══════════════════════════════════════════════════════════════
    # SECTION 1: Revenue Sustainability Gauge + Projection KPIs
    # ═══════════════════════════════════════════════════════════════
    st.markdown("""
    <div style="font-size:1.1rem;font-weight:700;color:#f1f5f9;
                text-transform:uppercase;letter-spacing:1px;margin:0.5rem 0 1rem 0;
                border-bottom:2px solid rgba(99,102,241,0.4);padding-bottom:0.5rem;">
        SECTION 1: Revenue Sustainability Assessment
    </div>""", unsafe_allow_html=True)

    gauge_col, proj_col = st.columns([2, 3])

    with gauge_col:
        # Traffic-light gauge: 0-33 red | 33-66 amber | 66-100 green
        fig_gauge = go.Figure(go.Indicator(
            mode="gauge+number+delta",
            value=sustain_score,
            delta={'reference': 66, 'valueformat': '.0f',
                   'increasing': {'color': '#10b981'},
                   'decreasing': {'color': '#ef4444'}},
            title={'text': f"<b>Sustainability Score</b><br><span style='font-size:0.8em;color:{sustain_color}'>{sustain_label}</span>",
                   'font': {'color': '#f1f5f9', 'size': 13}},
            gauge={
                'axis': {'range': [0, 100], 'tickwidth': 1,
                         'tickcolor': '#64748b', 'tickfont': {'color': '#94a3b8', 'size': 9}},
                'bar': {'color': sustain_color, 'thickness': 0.25},
                'bgcolor': 'rgba(0,0,0,0)',
                'borderwidth': 0,
                'steps': [
                    {'range': [0, 33],  'color': 'rgba(239,68,68,0.15)'},
                    {'range': [33, 66], 'color': 'rgba(245,158,11,0.15)'},
                    {'range': [66, 100],'color': 'rgba(16,185,129,0.15)'},
                ],
                'threshold': {
                    'line': {'color': '#6366f1', 'width': 3},
                    'thickness': 0.75, 'value': 66
                },
            },
            number={'font': {'color': sustain_color, 'size': 40}, 'suffix': '/100'},
        ))
        fig_gauge.update_layout(
            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
            font=dict(color='#94a3b8'), height=220,
            margin=dict(l=20, r=20, t=30, b=10),
        )
        st.plotly_chart(fig_gauge, use_container_width=True, config={'displayModeBar': False}, key="pc_3864")

        # Score breakdown pills
        st.markdown(f"""
        <div style="display:flex;gap:6px;flex-wrap:wrap;justify-content:center;margin-top:-8px;">
            <div style="background:rgba(16,185,129,0.1);border:1px solid rgba(16,185,129,0.3);
                        border-radius:20px;padding:4px 12px;font-size:0.75rem;color:#10b981;">
                Margin {margin_score}/40
            </div>
            <div style="background:rgba(99,102,241,0.1);border:1px solid rgba(99,102,241,0.3);
                        border-radius:20px;padding:4px 12px;font-size:0.75rem;color:#818cf8;">
                Growth {growth_score}/30
            </div>
            <div style="background:rgba(245,158,11,0.1);border:1px solid rgba(245,158,11,0.3);
                        border-radius:20px;padding:4px 12px;font-size:0.75rem;color:#f59e0b;">
                Data {data_score}/30
            </div>
        </div>
        """, unsafe_allow_html=True)

    with proj_col:
        if projections:
            current_rev_base = kpis.get('avg_revenue', kpis.get('total_revenue', 0)) or 0
            trend_dir   = "Upward ↑" if slope > 0 else "Downward ↓"
            trend_color = "#10b981" if slope > 0 else "#ef4444"

            kpi_cols = st.columns(len(projections) + 1)
            with kpi_cols[0]:
                st.markdown(f"""
                <div class="fin-kpi-card">
                    <div class="fin-kpi-label">Revenue Trend</div>
                    <div class="fin-kpi-value" style="color:{trend_color};font-size:1.3rem;">{trend_dir}</div>
                    <div class="fin-kpi-delta" style="color:{trend_color};">
                        {_fmt(abs(slope), prefix='$')}/period
                    </div>
                </div>
                """, unsafe_allow_html=True)

            for i, p in enumerate(projections):
                delta_pct = _pct(p['value'] - current_rev_base, max(current_rev_base, 1))
                d_color = "#10b981" if delta_pct >= 0 else "#ef4444"
                with kpi_cols[i + 1]:
                    st.markdown(f"""
                    <div class="fin-kpi-card">
                        <div class="fin-kpi-label">{p['period']}</div>
                        <div class="fin-kpi-value">{_fmt(p['value'], prefix='$')}</div>
                        <div class="fin-kpi-delta" style="color:{d_color};">
                            {delta_pct:+.1f}% above current level
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
        else:
            st.info("Add a date/period column to unlock revenue projections.")

        # Live metrics row
        st.markdown("<div style='margin-top:12px;'></div>", unsafe_allow_html=True)
        live_c1, live_c2 = st.columns(2)
        with live_c1:
            if mom_pct is not None:
                mc = "#10b981" if mom_pct >= 0 else "#ef4444"
                arrow = "↑" if mom_pct >= 0 else "↓"
                st.markdown(f"""
                <div style="padding:12px 16px;background:rgba(255,255,255,0.03);
                            border-radius:10px;border-left:3px solid {mc};">
                    <div style="font-size:0.72rem;color:#94a3b8;margin-bottom:4px;">LIVE: MoM Revenue</div>
                    <div style="font-size:1.3rem;font-weight:700;color:{mc};">
                        {arrow} {abs(mom_pct):.1f}%
                    </div>
                    <div style="font-size:0.72rem;color:#64748b;">
                        {"Growing — maintain momentum" if mom_pct >= 5 else
                         "Stable — protect base" if mom_pct >= 0 else
                         "Declining — investigate drivers"}
                    </div>
                </div>
                """, unsafe_allow_html=True)
        with live_c2:
            if gm is not None:
                gc = "#10b981" if gm > 30 else "#f59e0b" if gm > 15 else "#ef4444"
                gm_label = "Healthy" if gm > 30 else "Moderate" if gm > 15 else "Critical"
                st.markdown(f"""
                <div style="padding:12px 16px;background:rgba(255,255,255,0.03);
                            border-radius:10px;border-left:3px solid {gc};">
                    <div style="font-size:0.72rem;color:#94a3b8;margin-bottom:4px;">LIVE: Gross Margin</div>
                    <div style="font-size:1.3rem;font-weight:700;color:{gc};">{gm:.1f}%</div>
                    <div style="font-size:0.72rem;color:#64748b;">
                        {gm_label} — target: &gt;30%
                    </div>
                </div>
                """, unsafe_allow_html=True)

    _business_impact_box(
        "🎯", "SECTION 1 BUSINESS IMPACT — Why Sustainability Matters",
        f"A sustainability score of <strong>{sustain_score}/100 ({sustain_label})</strong> signals "
        f"the organisation's capacity to maintain profitable growth. "
        f"{'At this level, the business is self-funding and can absorb moderate revenue shocks without structural changes.' if sustain_score >= 75 else 'Attention is needed in ' + ('margin and cost structure' if margin_score < 25 else 'revenue growth trajectory') + ' before the business can scale confidently.' if sustain_score >= 50 else 'Immediate intervention is required — the current financial structure cannot sustain itself without corrective action.'} "
        f"Every 10-point improvement in this score typically correlates with a <strong>{_fmt(rev * 0.04, prefix='$')} increase</strong> in projected annual institutional surplus and reinvestment capacity."
    )
    _findings_box(
        "SECTION 1 FINDINGS — Sustainability Scorecard",
        f"{_status_badge('Margin Score', f'{margin_score}/40', 'ok' if margin_score >= 30 else 'warn' if margin_score >= 20 else 'bad')} — "
        f"{'Net margin above 30% — institution is financially healthy and self-sustaining.' if (gm or 0) > 30 else 'Net margin needs improvement — review fee structures or operational costs.' if (gm or 0) > 15 else 'Critical — net margin below 15%. Urgent cost review required.'}<br/>"
        + (f"Avg retention probability: <strong>{kpis.get('avg_retention_prob','N/A')}%</strong> "
           f"— {kpis.get('low_retention_count',0):,} students below 50% retention threshold.<br/>"
           if kpis.get('avg_retention_prob') else '')
        + (f"Avg graduation probability: <strong>{kpis.get('avg_grad_prob','N/A')}%</strong> "
           f"— {kpis.get('off_track_grad',0):,} students off track for graduation.<br/>"
           if kpis.get('avg_grad_prob') else '')
        + (f"At-risk population: <strong>{kpis.get('at_risk_count',0):,} students</strong> "
           f"({kpis.get('at_risk_pct',0):.1f}%) — each represents ${kpis.get('revenue_per_customer',0):,.0f} income at risk.<br/>"
           if kpis.get('at_risk_count') else '')
        + f"{_status_badge('Growth Score', f'{growth_score}/30', 'ok' if growth_score >= 25 else 'warn' if growth_score >= 15 else 'bad')} — "
        + f"{'Revenue trend is upward — sustain the growth drivers.' if slope > 0 else 'Revenue trend is flat or declining — prioritise ' + _ev('retention', 'customer retention') + ' and new revenue streams.'}<br/>"
        f"{_status_badge('Data Score', f'{data_score}/30', 'ok' if data_score >= 25 else 'warn' if data_score >= 15 else 'bad')} — "
        f"Data completeness: {completeness_pct:.1f}% "
        f"{'— excellent data reliability.' if completeness_pct >= 95 else '— address missing data to improve forecast accuracy.'}<br/><br/>"
        f"<strong>Action:</strong> "
        f"{'Maintain current performance and explore expansion opportunities.' if sustain_score >= 75 else 'Focus on the lowest-scoring component first for maximum sustainability lift.' if sustain_score >= 50 else 'Convene an emergency financial review — address margin, growth, and data gaps simultaneously.'}"
    )

    st.markdown("---")

    # ═══════════════════════════════════════════════════════════════
    # SECTION 2: Scenario Analysis
    # ═══════════════════════════════════════════════════════════════
    st.markdown("""
    <div style="font-size:1.1rem;font-weight:700;color:#f1f5f9;
                text-transform:uppercase;letter-spacing:1px;margin:0.5rem 0 1rem 0;
                border-bottom:2px solid rgba(99,102,241,0.4);padding-bottom:0.5rem;">
        SECTION 2: Scenario Analysis — Revenue Forecast
    </div>""", unsafe_allow_html=True)

    # Build scenario chart (Current / Conservative / Optimal / Aggressive)
    _periods = ["Now", "Month 1", "Month 2", "Month 3", "Month 6", "Month 9", "Month 12"]
    _base    = rev if rev > 0 else 1.0
    _conservative = [_base * (1 + 0.02 * i) for i in range(7)]
    _optimal      = [_base * (1 + 0.05 * i) for i in range(7)]
    _aggressive   = [_base * (1 + 0.09 * i) for i in range(7)]
    _current_proj = [_base + slope * i for i in range(7)]

    fig_scenario = go.Figure()
    fig_scenario.add_trace(go.Scatter(
        x=_periods, y=_current_proj, name="Current Trajectory",
        mode='lines+markers', line=dict(color='#94a3b8', width=2, dash='dot'),
        marker=dict(size=6), hovertemplate="%{x}: %{y:$,.0f}<extra>Current</extra>"))
    fig_scenario.add_trace(go.Scatter(
        x=_periods, y=_conservative, name="Conservative (+2%/mo)",
        mode='lines+markers', line=dict(color='#f59e0b', width=2),
        marker=dict(size=6), hovertemplate="%{x}: %{y:$,.0f}<extra>Conservative</extra>"))
    fig_scenario.add_trace(go.Scatter(
        x=_periods, y=_optimal, name="Optimal (+5%/mo)",
        mode='lines+markers', line=dict(color='#10b981', width=2.5),
        marker=dict(size=7), hovertemplate="%{x}: %{y:$,.0f}<extra>Optimal</extra>"))
    fig_scenario.add_trace(go.Scatter(
        x=_periods, y=_aggressive, name="Aggressive (+9%/mo)",
        mode='lines+markers', line=dict(color='#6366f1', width=2, dash='dash'),
        marker=dict(size=6), hovertemplate="%{x}: %{y:$,.0f}<extra>Aggressive</extra>"))

    # Add gap annotation at Month 12
    gap_opt_cons = _optimal[-1] - _conservative[-1]
    fig_scenario.add_annotation(
        x="Month 12", y=(_optimal[-1] + _conservative[-1]) / 2,
        text=f"Growth opportunity<br>{_fmt(gap_opt_cons, prefix='$')}",
        showarrow=True, arrowhead=2, arrowcolor='#10b981',
        font=dict(color='#10b981', size=10),
        bgcolor='rgba(16,185,129,0.1)', bordercolor='#10b981', borderwidth=1)

    fig_scenario.update_layout(
        title=dict(text="12-Month Revenue Scenario Analysis",
                   font=dict(color='#f1f5f9', size=14)),
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#94a3b8', size=10),
        xaxis=dict(gridcolor='rgba(255,255,255,0.05)', tickfont=dict(size=9)),
        yaxis=dict(gridcolor='rgba(255,255,255,0.06)', tickprefix='$',
                   tickformat=',.0f', tickfont=dict(size=9)),
        legend=dict(bgcolor='rgba(0,0,0,0)', bordercolor='rgba(255,255,255,0.1)',
                    borderwidth=1, font=dict(size=9)),
        margin=dict(l=10, r=80, t=50, b=10), height=340,
    )

    scen_left, scen_right = st.columns([3, 2])
    with scen_left:
        st.plotly_chart(fig_scenario, use_container_width=True, config={'displayModeBar': False}, key="pc_4036")

    with scen_right:
        # Scenario summary cards
        scenarios = [
            ("Current Trajectory", _current_proj[-1], "#94a3b8",
             "Based on historical slope — no intervention"),
            ("Conservative", _conservative[-1], "#f59e0b",
             "+2%/mo: defend existing enrolment base, reduce attrition"),
            ("Optimal", _optimal[-1], "#10b981",
             "+5%/mo: targeted re-enrolment + new programme entry"),
            ("Aggressive", _aggressive[-1], "#6366f1",
             "+9%/mo: full enrolment drive + fee and programme expansion"),
        ]
        for s_name, s_val, s_color, s_desc in scenarios:
            uplift = s_val - _base
            st.markdown(f"""
            <div style="background:rgba(255,255,255,0.03);border-left:3px solid {s_color};
                        border-radius:8px;padding:10px 14px;margin-bottom:8px;">
                <div style="font-size:0.8rem;font-weight:700;color:{s_color};">{s_name}</div>
                <div style="font-size:1.1rem;font-weight:700;color:#f1f5f9;">{_fmt(s_val, prefix='$')}</div>
                <div style="font-size:0.72rem;color:#94a3b8;">+{_fmt(uplift, prefix='$')} above current level</div>
                <div style="font-size:0.73rem;color:#94a3b8;margin-top:3px;">{s_desc}</div>
            </div>
            """, unsafe_allow_html=True)

    # Projection chart + growth decomp below
    proj_chart_col, growth_col = st.columns(2)
    with proj_chart_col:
        fig_proj = _build_projection_chart(kpis)
        if fig_proj:
            st.plotly_chart(fig_proj, use_container_width=True, config={'displayModeBar': False}, key="pc_4067")
        else:
            st.info("Add a date column to see a statistical regression projection.")
    with growth_col:
        fig_stack = _build_growth_decomposition(df, kpis, col_roles)
        if fig_stack:
            st.plotly_chart(fig_stack, use_container_width=True, config={'displayModeBar': False}, key="pc_4073")
        else:
            st.info("Date + category columns needed for growth decomposition.")

    _business_impact_box(
        "📈", "SECTION 2 BUSINESS IMPACT — The Revenue Gap Opportunity",
        f"The difference between the <strong>Conservative</strong> and <strong>Optimal</strong> scenarios over 12 months "
        f"is <strong>{_fmt(gap_opt_cons, prefix='$')}</strong>. "
        f"This gap is achievable through focused institutional actions — strengthening enrolment retention, "
        f"expanding programme reach, and improving cost efficiency — without requiring major capital outlay. "
        f"Moving from current trajectory to the Optimal scenario requires approximately "
        f"<strong>{_fmt(gap_opt_cons * 0.15, prefix='$')} in targeted programme and enrolment investment</strong> "
        f"to generate {_fmt(gap_opt_cons, prefix='$')} in additional income — a {gap_opt_cons / max(gap_opt_cons * 0.15, 1):.0f}x return."
    )
    _findings_box(
        "SECTION 2 FINDINGS — Scenario Outcomes",
        f"<strong>Baseline (Current Trajectory):</strong> {_fmt(_current_proj[-1], prefix='$')} by Month 12 "
        f"— slope {'+' if slope >= 0 else ''}{_fmt(slope, prefix='$')}/period<br/>"
        f"<strong>Conservative target:</strong> {_fmt(_conservative[-1], prefix='$')} (+{_fmt(_conservative[-1]-_base, prefix='$')}) — achievable with enrolment attrition reduction<br/>"
        f"<strong>Optimal target:</strong> {_fmt(_optimal[-1], prefix='$')} (+{_fmt(_optimal[-1]-_base, prefix='$')}) — achievable with targeted re-enrolment and new programme expansion<br/>"
        f"<strong>Aggressive target:</strong> {_fmt(_aggressive[-1], prefix='$')} (+{_fmt(_aggressive[-1]-_base, prefix='$')}) — requires sustained enrolment growth and programme investment<br/><br/>"
        f"<strong>Recommended scenario:</strong> "
        f"{'Optimal — current data supports this trajectory with focused academic and operational execution.' if sustain_score >= 60 else 'Conservative — stabilise financial fundamentals before pursuing accelerated growth.'}<br/>"
        f"<strong>Action:</strong> Set Optimal scenario as the institutional operating target. "
        f"Review monthly against actuals and escalate to Aggressive if Month 3 performance is on track."
    )

    st.markdown("---")

    # ═══════════════════════════════════════════════════════════════
    # SECTION 3: 30-Day Tactical Plan + 90-Day Strategic Roadmap
    # ═══════════════════════════════════════════════════════════════
    st.markdown("""
    <div style="font-size:1.1rem;font-weight:700;color:#f1f5f9;
                text-transform:uppercase;letter-spacing:1px;margin:0.5rem 0 1rem 0;
                border-bottom:2px solid rgba(99,102,241,0.4);padding-bottom:0.5rem;">
        SECTION 3: 30-Day Tactical Plan &amp; 90-Day Strategic Roadmap
    </div>""", unsafe_allow_html=True)

    guidance_30 = advisory.get('forward_guidance_30d', {})
    guidance_90 = advisory.get('forward_guidance_90d', {})

    # Derive data-driven 30-day actions
    data_actions_30 = []
    if gm is not None:
        if (gm or 0) > 30:
            _act_margin = "Protect net margin above 30% — hold firm on fee waivers and ensure all cost approvals are within budget."
        elif (gm or 0) > 15:
            _act_margin = "Audit top 3 operational cost categories — target 5% cost reduction through efficiency improvements within 30 days."
        else:
            _act_margin = f"URGENT: Immediate cost freeze + pricing review — margin at {gm:.1f}% is unsustainable."
    else:
        _act_margin = "Run gross margin analysis once cost data is available."
    data_actions_30.append(_act_margin)

    if mom_pct is not None:
        if (mom_pct or 0) >= 5:
            _act_mom = f"MoM income is {mom_pct:+.1f}% — analyse what drove top-performing cohorts or programmes and replicate those conditions."
        elif (mom_pct or 0) >= 0:
            _act_mom = f"MoM income is {mom_pct:+.1f}% — investigate the reasons for stalled income growth and address the top 2 root causes."
        else:
            _act_mom = f"MoM income is {mom_pct:+.1f}% — immediate enrolment retention analysis and financial recovery plan required."
    else:
        _act_mom = "Establish monthly revenue tracking cadence."
    data_actions_30.append(_act_mom)
    data_actions_30.append(
        f"Monitor the {len(num_df.columns)} numeric KPIs daily — set automated alerts for ±5% deviation."
    )

    # Derive data-driven 90-day priorities
    data_priorities_90 = []
    data_priorities_90.append(
        f"Achieve {_fmt(_optimal[3], prefix='$')} in total income by Month 3 (Optimal scenario milestone)."
    )
    data_priorities_90.append(
        f"Improve sustainability score from {sustain_score}/100 to {min(sustain_score + 15, 100)}/100 "
        f"by addressing {'net margin and cost efficiency' if margin_score < 25 else 'income growth and enrolment trends' if growth_score < 20 else 'data completeness and reporting quality'}."
    )
    data_priorities_90.append(
        f"{'Expand into adjacent programme areas and cohort segments to reduce income concentration risk.' if slope > 0 else 'Stabilise the institutional income base before pursuing new programme expansion.'}"
    )

    col_30, col_90 = st.columns(2)

    with col_30:
        st.markdown("""
        <div style="background:linear-gradient(135deg,rgba(16,185,129,0.08) 0%,rgba(5,150,105,0.05) 100%);
                    border:1px solid rgba(16,185,129,0.3);border-radius:14px;
                    padding:20px 22px;margin-bottom:12px;">
            <div style="font-size:0.9rem;color:#10b981;font-weight:700;
                        text-transform:uppercase;letter-spacing:0.6px;margin-bottom:14px;">
                📅 30-Day Tactical Plan
            </div>
        """, unsafe_allow_html=True)

        outlook = guidance_30.get('revenue_outlook', '')
        if outlook:
            _safe_outlook = str(outlook).replace('{', '&#123;').replace('}', '&#125;')
            st.markdown(
                '<div style="font-size:0.88rem;color:#cbd5e1;margin-bottom:12px;'
                'line-height:1.7;">'
                + _safe_outlook + '</div>',
                unsafe_allow_html=True
            )

        st.markdown("**Data-Driven Immediate Actions:**")
        for idx, act in enumerate(data_actions_30, 1):
            color = "#ef4444" if "URGENT" in act else "#10b981"
            _safe_act = str(act).replace('<', '&lt;').replace('>', '&gt;')
            st.markdown(
                f'<div style="display:flex;gap:10px;margin-bottom:8px;align-items:flex-start;">'
                f'<span style="background:{color};color:#fff;border-radius:50%;'
                f'width:20px;height:20px;min-width:20px;display:flex;'
                f'align-items:center;justify-content:center;'
                f'font-size:0.7rem;font-weight:700;margin-top:1px;">{idx}</span>'
                '<span style="font-size:0.85rem;color:#e2e8f0;line-height:1.6;">'
                + _safe_act +
                '</span></div>',
                unsafe_allow_html=True
            )

        if guidance_30.get('key_actions'):
            st.markdown("**Additional LLM-Generated Actions:**")
            for action in guidance_30['key_actions']:
                _safe_action = str(action).replace('<', '&lt;').replace('>', '&gt;')
                st.markdown(
                    '<div style="font-size:0.83rem;color:#94a3b8;margin-left:8px;">• '
                    + _safe_action + '</div>',
                    unsafe_allow_html=True
                )

        # Watch metrics pills
        watch_cols = [c for c in num_df.columns[:4]]
        if watch_cols:
            pills_html = "".join(
                f'<span style="background:rgba(16,185,129,0.1);border:1px solid rgba(16,185,129,0.3);'
                f'border-radius:20px;padding:3px 10px;font-size:0.75rem;color:#10b981;margin:2px;">{c}</span>'
                for c in watch_cols)
            st.markdown(
                '<div style="margin-top:10px;"><strong style="font-size:0.8rem;">Watch These KPIs:</strong><br/>'
                '<div style="margin-top:6px;">' + pills_html + '</div></div>',
                unsafe_allow_html=True
            )

        st.markdown("</div>", unsafe_allow_html=True)

    with col_90:
        st.markdown("""
        <div style="background:linear-gradient(135deg,rgba(245,158,11,0.08) 0%,rgba(217,119,6,0.05) 100%);
                    border:1px solid rgba(245,158,11,0.3);border-radius:14px;
                    padding:20px 22px;margin-bottom:12px;">
            <div style="font-size:0.9rem;color:#f59e0b;font-weight:700;
                        text-transform:uppercase;letter-spacing:0.6px;margin-bottom:14px;">
                🗺 90-Day Strategic Roadmap
            </div>
        """, unsafe_allow_html=True)

        if guidance_90.get('strategic_priorities'):
            st.markdown("**Strategic Priorities:**")
            for p in guidance_90['strategic_priorities']:
                st.markdown(f'<div style="font-size:0.83rem;color:#e2e8f0;margin-bottom:4px;">🎯 {p}</div>',
                            unsafe_allow_html=True)

        st.markdown("**Data-Driven 90-Day Priorities:**")
        for idx, pri in enumerate(data_priorities_90, 1):
            st.markdown(f"""
            <div style="display:flex;gap:10px;margin-bottom:8px;align-items:flex-start;">
                <span style="background:#f59e0b;color:#000;border-radius:50%;
                             width:20px;height:20px;min-width:20px;display:flex;
                             align-items:center;justify-content:center;
                             font-size:0.7rem;font-weight:700;margin-top:1px;">{idx}</span>
                <span style="font-size:0.85rem;color:#e2e8f0;line-height:1.6;">{pri}</span>
            </div>
            """, unsafe_allow_html=True)

        if guidance_90.get('growth_levers'):
            st.markdown("**Growth Levers:**")
            for gl in guidance_90['growth_levers']:
                st.markdown(f'<div style="font-size:0.83rem;color:#94a3b8;margin-left:8px;">🚀 {gl}</div>',
                            unsafe_allow_html=True)

        # Risk pills
        risk_tags = []
        if (gm or 0) < 15: risk_tags.append("Margin Risk")
        if (mom_pct or 0) < 0: risk_tags.append("Revenue Decline")
        if completeness_pct < 80: risk_tags.append("Data Gaps")
        risk_tags += (guidance_90.get('risk_factors') or [])[:2]

        if risk_tags:
            pills_html = "".join(
                f'<span style="background:rgba(239,68,68,0.1);border:1px solid rgba(239,68,68,0.3);'
                f'border-radius:20px;padding:3px 10px;font-size:0.75rem;color:#ef4444;margin:2px;">{r}</span>'
                for r in risk_tags[:5])
            st.markdown(
                '<div style="margin-top:10px;"><strong style="font-size:0.8rem;">Monitor Risks:</strong><br/>'
                '<div style="margin-top:6px;">' + pills_html + '</div></div>',
                unsafe_allow_html=True
            )

        st.markdown("</div>", unsafe_allow_html=True)

    _business_impact_box(
        "🗺", "SECTION 3 BUSINESS IMPACT — From Data to Execution",
        f"The 30/90 day roadmap converts the financial data into a <strong>sequenced execution plan</strong>. "
        f"The 30-day actions focus on immediate stabilisation and quick wins, while the 90-day roadmap sets the "
        f"strategic trajectory. Executing all 30-day actions is estimated to protect "
        f"<strong>{_fmt(rev * 0.05, prefix='$')} in at-risk revenue</strong>, "
        f"while full 90-day execution can add <strong>{_fmt(_optimal[3] - _base, prefix='$')} in new revenue</strong> "
        f"by Month 3 (Optimal scenario target)."
    )
    _findings_box(
        "SECTION 3 FINDINGS — Execution Checklist",
        f"<strong>30-Day Priority:</strong> "
        f"{'Margin stabilisation (below 15% — critical)' if (gm or 0) < 15 else 'Revenue momentum maintenance (MoM: ' + (f'{mom_pct:+.1f}%)' if mom_pct is not None else 'N/A)')}<br/>"
        f"<strong>90-Day Target Revenue:</strong> {_fmt(_optimal[3], prefix='$')} (Optimal scenario, Month 3)<br/>"
        f"<strong>Sustainability Score Target:</strong> {min(sustain_score + 15, 100)}/100 "
        f"(+15 points from current {sustain_score})<br/>"
        f"<strong>Key Risk:</strong> "
        f"{'Margin erosion — every 1% drop costs ' + _fmt(rev * 0.01, prefix='$') + ' in profit' if (gm or 0) < 20 else 'Revenue growth stall — monitor MoM weekly' if (mom_pct or 0) < 5 else 'Complacency — protect margin and growth as the business scales'}<br/><br/>"
        f"<strong>Action sequence:</strong> Week 1 → cost audit | Week 2–3 → growth activation | Week 4 → review vs Optimal target | Month 2–3 → escalate or sustain"
    )

    st.markdown("---")

    # ═══════════════════════════════════════════════════════════════
    # SECTION 4: CFO Board Memo
    # ═══════════════════════════════════════════════════════════════
    st.markdown("""
    <div style="font-size:1.1rem;font-weight:700;color:#f1f5f9;
                text-transform:uppercase;letter-spacing:1px;margin:0.5rem 0 1rem 0;
                border-bottom:2px solid rgba(99,102,241,0.4);padding-bottom:0.5rem;">
        SECTION 4: CFO Board Memo
    </div>""", unsafe_allow_html=True)

    memo_llm = advisory.get('cfo_memo', '')
    # Data-derived memo (always available)
    gm_str   = f"{gm:.1f}%" if gm is not None else "N/A"
    mom_str  = f"{mom_pct:+.1f}%" if mom_pct is not None else "N/A"
    auto_memo = (
        f"<strong>TO: Board of Directors &amp; Executive Committee</strong><br/>"
        f"<strong>FROM: Chief Financial Officer</strong><br/>"
        f"<strong>RE: Financial Performance &amp; Forward Guidance</strong><br/><br/>"
        f"<strong>1. Current Financial Position</strong><br/>"
        f"Revenue base: {_fmt(rev, prefix='$')} | Gross Margin: {gm_str} "
        f"({'on target' if (gm or 0) > 30 else 'requires improvement'}) | "
        f"MoM Revenue: {mom_str} ({'growing' if (mom_pct or 0) >= 0 else 'declining'})<br/>"
        f"Sustainability Score: {sustain_score}/100 — {sustain_label}<br/><br/>"
        f"<strong>2. 12-Month Forecast</strong><br/>"
        f"Conservative: {_fmt(_conservative[-1], prefix='$')} | "
        f"Optimal: {_fmt(_optimal[-1], prefix='$')} | "
        f"Aggressive: {_fmt(_aggressive[-1], prefix='$')}<br/>"
        f"Recommended operating plan: {'Optimal' if sustain_score >= 60 else 'Conservative'} scenario.<br/><br/>"
        f"<strong>3. Immediate Actions Required</strong><br/>"
        f"{'• PRIORITY: Gross margin below 15% — cost audit and pricing review required within 14 days.<br/>' if (gm or 0) < 15 else ''}"
        f"{'• Income declining MoM — enrolment retention analysis and financial recovery plan to commence immediately.<br/>' if (mom_pct or 0) < 0 else ''}"
        f"• Sustainability score target: {min(sustain_score + 15, 100)}/100 within 90 days.<br/>"
        f"• Review against Optimal scenario trajectory at Month 1 checkpoint.<br/><br/>"
        f"<strong>4. Board Recommendation</strong><br/>"
        f"{'Approve the Optimal growth plan. Current fundamentals support disciplined expansion.' if sustain_score >= 75 else 'Hold expansion plans until margin and growth metrics stabilise. Approve Conservative plan only.' if sustain_score >= 50 else 'Declare financial recovery mode. Approve emergency cost reduction plan and Conservative scenario only.'}"
    )

    st.markdown(f"""
    <div style="background:linear-gradient(135deg,#1a1f2e 0%,#1e2a3e 100%);
                border:1px solid rgba(99,102,241,0.3);border-radius:14px;
                padding:24px 28px;line-height:1.85;font-size:0.9rem;color:#cbd5e1;">
        {memo_llm if memo_llm else auto_memo}
    </div>
    """, unsafe_allow_html=True)

    if memo_llm:
        _safe_auto_memo = str(auto_memo).replace('{', '&#123;').replace('}', '&#125;')
        st.markdown(
            '<div style="margin-top:12px;padding:14px 18px;'
            'background:linear-gradient(135deg,#1a1f2e 0%,#1e2a3e 100%);'
            'border:1px solid rgba(148,163,184,0.15);border-radius:10px;'
            'font-size:0.83rem;color:#94a3b8;line-height:1.7;">'
            '<strong style="color:#818cf8;">Data-Driven Context:</strong><br/>'
            + _safe_auto_memo +
            '</div>',
            unsafe_allow_html=True
        )

    # ── Master Forward Guidance Findings Summary ──
    st.markdown("<br/>", unsafe_allow_html=True)
    st.markdown(f"""
    <div style="background:linear-gradient(135deg,rgba(99,102,241,0.08) 0%,rgba(59,130,246,0.06) 100%);
                border:3px solid #6366f1;border-radius:16px;padding:24px 28px;">
        <div style="color:#818cf8;font-weight:700;font-size:1.1rem;margin-bottom:16px;
                    text-transform:uppercase;letter-spacing:0.5px;">
            🎯 FORWARD GUIDANCE — MASTER FINDINGS SUMMARY
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;">
            <div>
                <div style="color:#10b981;font-weight:700;font-size:0.85rem;margin-bottom:8px;">
                    SUSTAINABILITY
                </div>
                <div style="color:#e2e8f0;font-size:0.85rem;line-height:1.75;">
                    Score: <strong>{sustain_score}/100</strong> ({sustain_label})<br/>
                    Margin: <strong>{gm_str}</strong> | MoM: <strong>{mom_str}</strong><br/>
                    Data Completeness: <strong>{completeness_pct:.1f}%</strong>
                </div>
            </div>
            <div>
                <div style="color:#f59e0b;font-weight:700;font-size:0.85rem;margin-bottom:8px;">
                    12-MONTH TARGETS
                </div>
                <div style="color:#e2e8f0;font-size:0.85rem;line-height:1.75;">
                    Conservative: <strong>{_fmt(_conservative[-1], prefix='$')}</strong><br/>
                    Optimal: <strong>{_fmt(_optimal[-1], prefix='$')}</strong><br/>
                    Growth opportunity: <strong>{_fmt(gap_opt_cons, prefix='$')}</strong>
                </div>
            </div>
            <div>
                <div style="color:#6366f1;font-weight:700;font-size:0.85rem;margin-bottom:8px;">
                    30-DAY PRIORITY ACTIONS
                </div>
                <div style="color:#e2e8f0;font-size:0.85rem;line-height:1.75;">
                    {'🔴 Emergency margin review (below 15%)' if (gm or 0) < 15 else '⚠️ Margin optimisation (15–30% range)' if (gm or 0) < 30 else '✅ Margin healthy — protect and scale'}<br/>
                    {'🔴 Revenue recovery plan (MoM negative)' if (mom_pct or 0) < 0 else '⚠️ Revenue stabilisation (MoM flat)' if (mom_pct or 0) < 5 else '✅ Sustain revenue growth momentum'}<br/>
                    Monitor {len(num_df.columns)} KPIs with ±5% deviation alerts
                </div>
            </div>
            <div>
                <div style="color:#ef4444;font-weight:700;font-size:0.85rem;margin-bottom:8px;">
                    KEY RISKS
                </div>
                <div style="color:#e2e8f0;font-size:0.85rem;line-height:1.75;">
                    {'🔴 Critical margin risk' if (gm or 0) < 15 else '⚠️ Margin pressure' if (gm or 0) < 30 else '✅ Margin stable'}<br/>
                    {'🔴 Revenue decline detected' if (mom_pct or 0) < 0 else '⚠️ Growth stall risk' if (mom_pct or 0) < 5 else '✅ Revenue growing'}<br/>
                    Recommended plan: <strong>{'Optimal' if sustain_score >= 60 else 'Conservative'}</strong> scenario
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)


def _analyze_numeric_column(s: pd.Series) -> Dict[str, Any]:
    """Full distribution analysis for a numeric series."""
    s = pd.to_numeric(s, errors='coerce').dropna()
    if len(s) < 2:
        return {}
    q1, q3 = float(s.quantile(0.25)), float(s.quantile(0.75))
    iqr = q3 - q1
    outlier_count = int(((s < q1 - 1.5 * iqr) | (s > q3 + 1.5 * iqr)).sum()) if iqr > 0 else 0
    skew = float(s.skew())
    if   skew >  1:  dist_shape = "Right-skewed (high-value outliers)"
    elif skew < -1:  dist_shape = "Left-skewed (low-value outliers)"
    elif abs(skew) < 0.3: dist_shape = "Symmetric / Normal-like"
    else:            dist_shape = "Slightly skewed"
    return {
        'count':    len(s), 'mean': float(s.mean()), 'median': float(s.median()),
        'std':      float(s.std()), 'min': float(s.min()), 'max': float(s.max()),
        'q1': q1, 'q3': q3, 'iqr': iqr,
        'skew':     skew, 'kurtosis': float(s.kurtosis()),
        'outliers': outlier_count,
        'dist_shape': dist_shape,
        'cv':       float(s.std() / max(abs(s.mean()), 1e-9)) * 100,  # coefficient of variation %
    }


def _analyze_categorical_column(s: pd.Series) -> Dict[str, Any]:
    """Top-N frequency analysis for a categorical series."""
    s = s.dropna().astype(str)
    if len(s) == 0:
        return {}
    vc = s.value_counts()
    return {
        'unique':       s.nunique(),
        'top_values':   vc.head(8).to_dict(),
        'top_1_share':  float(vc.iloc[0] / len(s) * 100) if len(vc) > 0 else 0,
        'concentration': 'high' if (vc.iloc[0] / len(s)) > 0.6 else
                          'moderate' if (vc.iloc[0] / len(s)) > 0.3 else 'low',
    }


def _build_column_histogram(df: pd.DataFrame, col: str) -> go.Figure:
    """Histogram + KDE-line for a numeric column."""
    s = pd.to_numeric(df[col], errors='coerce').dropna()
    fig = go.Figure()
    fig.add_trace(go.Histogram(
        x=s, nbinsx=30, name=col,
        marker_color='rgba(245,158,11,0.6)',
        marker_line=dict(color='rgba(245,158,11,0.9)', width=1),
    ))
    fig.update_layout(
        title=dict(text=f"Distribution: {col}", font=dict(color='#f1f5f9', size=12)),
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#94a3b8'), showlegend=False,
        xaxis=dict(gridcolor='rgba(255,255,255,0.05)'),
        yaxis=dict(gridcolor='rgba(255,255,255,0.05)'),
        margin=dict(l=10, r=10, t=40, b=10), height=220,
    )
    return fig


def _build_column_bar(df: pd.DataFrame, col: str, top_n: int = 10) -> go.Figure:
    """Frequency bar chart for a categorical column."""
    vc = df[col].value_counts().head(top_n)
    total = len(df[col].dropna())
    fig = go.Figure(go.Bar(
        x=vc.values.tolist(),
        y=[str(k) for k in vc.index],
        orientation='h',
        marker_color='rgba(16,185,129,0.7)',
        text=[f"{v/total*100:.1f}%" for v in vc.values],
        textposition='outside',
        textfont=dict(color='#94a3b8', size=9),
    ))
    fig.update_layout(
        title=dict(text=f"Top Values: {col}", font=dict(color='#f1f5f9', size=12)),
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#94a3b8'), showlegend=False,
        xaxis=dict(gridcolor='rgba(255,255,255,0.05)'),
        yaxis=dict(gridcolor='rgba(255,255,255,0.05)'),
        margin=dict(l=10, r=10, t=40, b=10), height=220,
    )
    return fig


def _col_business_meaning(col: str, stats: dict, is_numeric: bool, col_roles: dict) -> str:
    """Return a business interpretation sentence for a column based on its name, role and stats."""
    col_lower = col.lower()
    # Determine role
    role = "general"
    for r, cols in col_roles.items():
        if col in cols:
            role = r
            break

    if is_numeric:
        cv   = stats.get('cv', 0)
        skew = stats.get('skew', 0)
        out  = stats.get('outliers', 0)
        n    = max(stats.get('count', 1), 1)
        out_pct = out / n * 100

        # Volatility
        vol_msg = ("highly stable — consistent performance" if cv < 20 else
                   "moderately variable — some inconsistency" if cv < 50 else
                   "highly volatile — investigate root causes")

        # Skew meaning
        skew_msg = ("with high-value premium outliers that may indicate VIP accounts or one-off transactions" if skew > 1 else
                    "with low-value outliers suggesting potential write-offs or returns" if skew < -1 else
                    "with a balanced distribution — no extreme outliers dominating the average")

        # Role-based context
        if role in ('revenue_cols', 'total_cols'):
            return (f"This is a <strong>revenue/income metric</strong> — it directly impacts top-line performance. "
                    f"Values are {vol_msg} (CV={cv:.0f}%) {skew_msg}. "
                    f"{'High volatility signals that revenue depends on irregular large deals — reduce concentration.' if cv > 50 else 'Stable revenue is a positive indicator of predictable cash flow.'}")
        elif role in ('cost_cols', 'expense_cols'):
            return (f"This is a <strong>cost/expense driver</strong> — controlling this column improves margin. "
                    f"Values are {vol_msg} (CV={cv:.0f}%). "
                    f"{'Volatility here is a risk — unpredictable costs erode margin planning.' if cv > 40 else 'Stable costs support reliable margin forecasting.'} "
                    f"Outliers ({out_pct:.1f}%): {'review high-cost events for elimination or negotiation.' if out_pct > 5 else 'within acceptable range.'}")
        elif role in ('quantity_cols',):
            _qty_base_msg = ('High variance in order sizes suggests upsell opportunity for small accounts.'
                             if cv > 40 else
                             'Consistent order volumes indicate a stable ' + _ev('base', 'customer base') + '.')
            return (f"This is a <strong>volume/quantity metric</strong> — it drives revenue scale. "
                    f"Distribution is {skew_msg}. "
                    + _qty_base_msg)
        elif role in ('price_cols',):
            return (f"This is a <strong>pricing metric</strong> — directly impacts revenue per unit. "
                    f"Coefficient of Variation: {cv:.0f}% — "
                    f"{'pricing is inconsistent, suggesting unmanaged discounting.' if cv > 30 else 'pricing is disciplined and consistent.'} "
                    f"{out_pct:.1f}% price outliers — "
                    f"{'may indicate unauthorised discounts or premium pricing — audit these transactions.' if out_pct > 3 else 'within normal range.'}")
        else:
            return (f"This numeric field is {vol_msg} (CV={cv:.0f}%). "
                    f"Distribution: {skew_msg}. "
                    f"{'⚠️ High outlier rate — investigate anomalies.' if out_pct > 10 else 'Outlier rate is within acceptable bounds.'}")
    else:
        uniq   = stats.get('unique', 0)
        top1   = stats.get('top_1_share', 0)
        conc   = stats.get('concentration', 'low')
        if role in ('category_cols', 'product_cols', 'segment_cols'):
            return (f"This is a <strong>segmentation dimension</strong> — use it to slice revenue and cost analysis. "
                    f"{uniq} unique values; top category holds {top1:.1f}% share. "
                    f"{'⚠️ High concentration: single category dominates — concentration risk.' if conc == 'high' else '✅ Healthy distribution across segments — diversified revenue base.' if conc == 'low' else '⚠️ Moderate concentration — monitor for further consolidation.'}")
        elif role in ('date_cols',):
            return (f"This is a <strong>time dimension</strong> — use it to compute MoM/YoY trends, seasonality, and projections. "
                    f"Ensure date format is consistent for time-series analysis.")
        elif role in ('id_cols',):
            return (f"This appears to be an <strong>identifier column</strong> — {uniq} unique IDs. "
                    f"Use for deduplication and record matching. "
                    f"{'⚠️ Duplicates possible if unique count < total records.' if top1 > 1 else '✅ Appears unique — suitable as a primary key.'}")
        else:
            return (f"Categorical field with {uniq} unique values. "
                    f"Top value: {top1:.1f}% share — "
                    f"{'⚠️ High concentration — this category dominates, limiting segmentation depth.' if conc == 'high' else '✅ Well distributed — good segmentation potential.' if conc == 'low' else 'Moderate spread across values.'}")


def _col_quality_action(col: str, missing_n: int, total_n: int, stats: dict,
                         is_numeric: bool) -> Tuple[str, str]:
    """Return (severity, action_text) for data quality guidance."""
    missing_pct = missing_n / max(total_n, 1) * 100
    if missing_pct > 20:
        return "bad", (f"🔴 {missing_pct:.0f}% missing — this column has severe data gaps. "
                       f"Action: {'Impute with median or flag for collection.' if is_numeric else 'Fill with Unknown category or exclude from analysis.'}")
    elif missing_pct > 5:
        return "warn", (f"⚠️ {missing_pct:.0f}% missing — moderate gaps. "
                        f"Action: {'Mean/median imputation acceptable for analysis.' if is_numeric else 'Add Unknown placeholder to preserve row count.'}")
    elif missing_pct > 0:
        return "ok", f"✅ {missing_pct:.1f}% missing — minor gaps, acceptable for analysis."
    else:
        if is_numeric and stats.get('cv', 0) > 80:
            return "warn", "⚠️ No missing values, but very high volatility (CV>80%) — check for data entry errors or outlier contamination."
        return "ok", "✅ Complete data — no missing values. Ready for analysis."


def render_data_explorer_tab(df, col_roles, kpis=None):
    """Tab 5: Data Explorer — full column-by-column analysis with business interpretation."""
    render_section_header("🔬", "Data Explorer", "COLUMN INTELLIGENCE & BUSINESS INTERPRETATION")

    if df is None:
        st.info("Load a dataset to explore.")
        return

    # ── OVERVIEW: Dataset Health Dashboard ──
    st.markdown("""
    <div style="font-size:1.1rem;font-weight:700;color:#f1f5f9;
                text-transform:uppercase;letter-spacing:1px;margin:0.5rem 0 1rem 0;
                border-bottom:2px solid rgba(99,102,241,0.4);padding-bottom:0.5rem;">
        SECTION 1: Dataset Health Overview
    </div>""", unsafe_allow_html=True)

    # ── Universal catalog coverage panel ────────────────────────────────────
    _catalog_key_fields = [
        ('enrollment_tuition_amount',    '💵', 'Tuition Revenue'),
        ('financial_aid_monetary_amount','🎓', 'Financial Aid'),
        ('cumulative_gpa',               '📚', 'GPA'),
        ('enrollment_enrollment_status', '✅', 'Enrollment Status'),
        ('student_id',                   '🔑', 'Student ID'),
        ('cohort_year',                  '📅', 'Cohort Year'),
        ('is_at_risk',                   '⚠️', 'At-Risk Flag'),
        ('retention_probability',        '🔄', 'Retention Prob.'),
        ('graduation_probability',       '🎯', 'Grad. Probability'),
        ('engagement_score',             '⭐', 'Engagement Score'),
        ('attendance_rate',              '📋', 'Attendance Rate'),
        ('estimated_annual_cost',        '💰', 'Annual Cost'),
        ('major',                        '📖', 'Major'),
        ('college',                      '🏫', 'College'),
        ('stop_out_risk_flag',           '🚨', 'Stop-Out Risk'),
        ('degree_progress_pct',          '📈', 'Degree Progress'),
        ('is_international',             '🌍', 'International'),
        ('past_due_balance',             '💳', 'Past-Due Balance'),
    ]
    _kf_present = [(col, ic, lbl) for col, ic, lbl in _catalog_key_fields if col in df.columns]
    _kf_missing = [(col, ic, lbl) for col, ic, lbl in _catalog_key_fields if col not in df.columns]
    _cov_pct_de = round(len(_kf_present) / max(len(_catalog_key_fields), 1) * 100)
    st.markdown(
        f'<div style="background:linear-gradient(135deg,#0a1628,#0d1f35);border:1px solid rgba(99,102,241,0.3);'
        f'border-radius:12px;padding:16px 20px;margin-bottom:16px;">'
        f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">'
        f'<div style="color:#f1f5f9;font-weight:700;font-size:0.95rem;">📋 Universal Column Catalog Coverage</div>'
        f'<div style="background:#10b981;color:#fff;border-radius:20px;padding:3px 12px;font-size:0.78rem;font-weight:700;">'
        f'{_cov_pct_de}% ({len(_kf_present)}/{len(_catalog_key_fields)} fields)</div></div>'
        f'<div style="display:flex;flex-wrap:wrap;gap:6px;">'
        + ''.join(
            f'<span style="background:#132840;border:1px solid #10b981;border-radius:6px;padding:3px 8px;'
            f'font-size:0.72rem;color:#10b981;">{ic} {lbl}</span>'
            for col, ic, lbl in _kf_present
        )
        + (''.join(
            f'<span style="background:#1e0a0a;border:1px solid #ef4444;border-radius:6px;padding:3px 8px;'
            f'font-size:0.72rem;color:#ef4444;opacity:0.7;">{ic} {lbl}</span>'
            for col, ic, lbl in _kf_missing
        ) if _kf_missing else '')
        + f'</div>'
        + (f'<div style="font-size:0.72rem;color:#64748b;margin-top:8px;">'
           f'🟢 Detected (drives analysis) &nbsp;|&nbsp; 🔴 Not detected (add to enable full insights)</div>'
           if _kf_missing else '')
        + '</div>',
        unsafe_allow_html=True
    )

    missing_total = int(df.isnull().sum().sum())
    missing_pct   = (missing_total / max(df.size, 1)) * 100
    num_numeric   = len(df.select_dtypes(include='number').columns)
    num_cat       = len(df.select_dtypes(include='object').columns)
    dup_rows      = int(df.duplicated().sum())
    dup_pct       = dup_rows / max(len(df), 1) * 100
    completeness  = 100 - missing_pct

    # Health score for data quality
    dq_score  = (40 if missing_pct < 2 else 25 if missing_pct < 10 else 10)
    dq_score += (30 if dup_pct < 1 else 15 if dup_pct < 5 else 5)
    dq_score += (30 if len(df) >= 500 else 20 if len(df) >= 100 else 10)
    dq_label  = "Excellent" if dq_score >= 80 else "Good" if dq_score >= 55 else "Needs Work"
    dq_color  = "#10b981" if dq_score >= 80 else "#f59e0b" if dq_score >= 55 else "#ef4444"

    ov_cols = st.columns(6)
    metrics_ov = [
        ("Total Rows",    f"{len(df):,}", "#10b981" if len(df) >= 100 else "#f59e0b"),
        ("Columns",       f"{len(df.columns):,}", "#10b981"),
        ("Completeness",  f"{completeness:.1f}%", "#10b981" if completeness >= 95 else "#f59e0b" if completeness >= 80 else "#ef4444"),
        ("Numeric Cols",  f"{num_numeric}", "#818cf8"),
        ("Category Cols", f"{num_cat}", "#818cf8"),
        ("Duplicates",    f"{dup_rows:,}", "#10b981" if dup_pct < 1 else "#f59e0b" if dup_pct < 5 else "#ef4444"),
    ]
    for idx, (label, val, color) in enumerate(metrics_ov):
        with ov_cols[idx]:
            st.markdown(f"""
            <div class="fin-kpi-card">
                <div class="fin-kpi-label">{label}</div>
                <div class="fin-kpi-value" style="color:{color};font-size:1.3rem;">{val}</div>
            </div>
            """, unsafe_allow_html=True)

    # DQ Score gauge (compact horizontal bar)
    st.markdown(f"""
    <div style="background:rgba(255,255,255,0.03);border-radius:12px;padding:16px 20px;margin:12px 0;
                border:1px solid rgba(255,255,255,0.06);">
        <div style="display:flex;align-items:center;gap:16px;">
            <div style="min-width:140px;">
                <div style="font-size:0.75rem;color:#94a3b8;text-transform:uppercase;letter-spacing:0.5px;">
                    Data Quality Score
                </div>
                <div style="font-size:1.6rem;font-weight:700;color:{dq_color};">{dq_score}/100</div>
                <div style="font-size:0.75rem;color:{dq_color};">{dq_label}</div>
            </div>
            <div style="flex:1;">
                <div style="background:rgba(255,255,255,0.08);border-radius:20px;height:12px;overflow:hidden;">
                    <div style="width:{dq_score}%;height:100%;background:{dq_color};
                                border-radius:20px;transition:width 0.5s;"></div>
                </div>
                <div style="display:flex;justify-content:space-between;margin-top:6px;font-size:0.7rem;color:#64748b;">
                    <span>Completeness {completeness:.0f}%</span>
                    <span>Duplicates {dup_pct:.1f}%</span>
                    <span>Volume: {len(df):,} rows</span>
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    _business_impact_box(
        "🗃", "SECTION 1 INSTITUTIONAL IMPACT — Why Data Quality Drives Sound Academic & Financial Decisions",
        f"A Data Quality Score of <strong>{dq_score}/100 ({dq_label})</strong> directly affects the reliability of every "
        f"insight, projection, and decision made from this dataset. "
        f"{'At this quality level, analysis results are highly reliable and can be used for board-level decisions.' if dq_score >= 80 else 'Moderate quality — findings should be treated as directional indicators, not precise figures, until data gaps are resolved.' if dq_score >= 55 else 'Poor data quality — decisions based on this data carry high risk. Prioritise data cleaning before acting on any insights.'} "
        f"Missing {missing_pct:.1f}% of data across {len(df.columns)} columns affects every downstream metric. "
        f"{'Each 1% improvement in completeness adds analytical precision equivalent to ~{len(df)//100} additional clean records.' if missing_pct > 0 else 'Complete dataset — no data quality barriers to analysis.'}"
    )
    _findings_box(
        "SECTION 1 FINDINGS — Data Quality Checklist",
        f"{_status_badge('Completeness', f'{completeness:.1f}%', 'ok' if completeness >= 95 else 'warn' if completeness >= 80 else 'bad')} — "
        f"{'Excellent — proceed with full analysis.' if completeness >= 95 else str(missing_total) + ' missing values detected — imputation or collection required before final analysis.' if completeness < 80 else 'Minor gaps — acceptable for most analyses.'}<br/>"
        f"{_status_badge('Duplicates', f'{dup_rows:,} rows ({dup_pct:.1f}%)', 'ok' if dup_pct < 1 else 'warn' if dup_pct < 5 else 'bad')} — "
        f"{'No duplicates detected — data is clean.' if dup_rows == 0 else 'Remove duplicates before revenue/KPI calculations to avoid double-counting.' if dup_pct > 1 else 'Minimal duplicates — low risk.'}<br/>"
        f"{_status_badge('Volume', f'{len(df):,} records', 'ok' if len(df) >= 500 else 'warn' if len(df) >= 100 else 'bad')} — "
        f"{'Sufficient volume for statistical analysis and trend detection.' if len(df) >= 500 else 'Moderate volume — results are directional; increase data collection for higher confidence.' if len(df) >= 100 else 'Small dataset — statistical conclusions have wide confidence intervals.'}<br/>"
        f"{_status_badge('Structure', f'{num_numeric} numeric + {num_cat} categorical', 'ok' if num_numeric >= 2 and num_cat >= 1 else 'warn')}<br/><br/>"
        f"<strong>Action:</strong> "
        f"{'Data is analysis-ready — proceed to column intelligence below.' if dq_score >= 80 else 'Address missing values and duplicates before presenting insights to leadership.' if dq_score >= 55 else 'Halt analysis — initiate data remediation process before proceeding.'}"
    )

    st.markdown("---")

    # ── SECTION 2: Column Role Mapping ──
    st.markdown("""
    <div style="font-size:1.1rem;font-weight:700;color:#f1f5f9;
                text-transform:uppercase;letter-spacing:1px;margin:0.5rem 0 1rem 0;
                border-bottom:2px solid rgba(99,102,241,0.4);padding-bottom:0.5rem;">
        SECTION 2: Column Role Map &amp; Business Classification
    </div>""", unsafe_allow_html=True)

    with st.expander("📋 View Full Column Role Mapping", expanded=False):
        role_rows = []
        for role, cols_list in col_roles.items():
            for c in cols_list:
                dtype   = str(df[c].dtype) if c in df.columns else 'unknown'
                missing = int(df[c].isnull().sum()) if c in df.columns else 0
                mpct    = missing / max(len(df), 1) * 100
                role_rows.append({
                    'Column':    c,
                    'Business Role': role.replace('_', ' ').title(),
                    'Dtype':     dtype,
                    'Missing':   missing,
                    'Missing %': f"{mpct:.1f}%",
                    'Quality':   '🔴 Critical' if mpct > 20 else '⚠️ Gaps' if mpct > 5 else '✅ Good',
                })
        if role_rows:
            st.dataframe(pd.DataFrame(role_rows), use_container_width=True, hide_index=True)
        else:
            st.info("No explicit column roles detected — analysis will use all columns.")

    # Role distribution pills
    role_pill_html = ""
    role_icons = {
        'revenue_cols': ('💰', '#10b981'), 'cost_cols': ('📉', '#ef4444'),
        'quantity_cols': ('📦', '#818cf8'), 'price_cols': ('🏷', '#f59e0b'),
        'date_cols': ('📅', '#38bdf8'), 'category_cols': ('🏷', '#a78bfa'),
        'id_cols': ('🔑', '#64748b'),
    }
    for role, cols_list in col_roles.items():
        if cols_list:
            icon, color = role_icons.get(role, ('📊', '#94a3b8'))
            role_pill_html += (
                f'<span style="background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.1);'
                f'border-radius:20px;padding:4px 12px;font-size:0.78rem;color:{color};margin:3px;display:inline-block;">'
                f'{icon} {role.replace("_cols","").replace("_"," ").title()} ({len(cols_list)})</span>'
            )
    if role_pill_html:
        st.markdown('<div style="margin:8px 0;">' + role_pill_html + '</div>', unsafe_allow_html=True)

    st.markdown("---")

    # ── SECTION 3: Column-by-Column Intelligence ──
    st.markdown("""
    <div style="font-size:1.1rem;font-weight:700;color:#f1f5f9;
                text-transform:uppercase;letter-spacing:1px;margin:0.5rem 0 1rem 0;
                border-bottom:2px solid rgba(99,102,241,0.4);padding-bottom:0.5rem;">
        SECTION 3: Column-by-Column Business Intelligence
    </div>""", unsafe_allow_html=True)

    all_cols   = list(df.columns)
    max_display = st.slider("Columns to analyse", 1, min(len(all_cols), 20),
                            min(8, len(all_cols)), key="fin_explorer_col_count")
    cols_to_show = all_cols[:max_display]

    # Collect column quality issues for master summary later
    quality_issues = []
    col_summaries  = []

    for i in range(0, len(cols_to_show), 2):
        chart_row = st.columns(2)
        for j, col in enumerate(cols_to_show[i:i+2]):
            with chart_row[j]:
                is_numeric = pd.api.types.is_numeric_dtype(df[col].dtype)
                missing_n  = int(df[col].isnull().sum())
                missing_p  = missing_n / max(len(df), 1) * 100

                if is_numeric:
                    stats = _analyze_numeric_column(df[col])
                    if not stats:
                        st.markdown(f"**`{col}`** — insufficient data")
                        continue

                    cv    = stats['cv']
                    out_p = stats['outliers'] / max(stats['count'], 1) * 100
                    vol_label = "Stable" if cv < 20 else "Moderate" if cv < 50 else "Volatile"
                    vol_color = "#10b981" if cv < 20 else "#f59e0b" if cv < 50 else "#ef4444"
                    sev, qa   = _col_quality_action(col, missing_n, len(df), stats, True)
                    biz_msg   = _col_business_meaning(col, stats, True, col_roles)

                    if missing_p > 10 or cv > 80 or out_p > 10:
                        quality_issues.append({'col': col, 'severity': sev, 'issue': qa})
                    col_summaries.append({'col': col, 'type': 'numeric', 'cv': cv, 'vol': vol_label,
                                          'outlier_pct': out_p, 'missing_pct': missing_p})

                    # Header card
                    st.markdown(f"""
                    <div style="padding:12px 16px;background:rgba(245,158,11,0.06);
                                border-radius:12px;margin-bottom:8px;
                                border-left:4px solid {vol_color};">
                        <div style="display:flex;justify-content:space-between;align-items:flex-start;">
                            <div style="font-size:0.88rem;font-weight:700;color:#fbbf24;">{col}</div>
                            <span style="background:{vol_color};color:#000;border-radius:20px;
                                         padding:2px 10px;font-size:0.7rem;font-weight:700;">{vol_label}</span>
                        </div>
                        <div style="font-size:0.75rem;color:#94a3b8;margin-top:6px;
                                    display:flex;gap:12px;flex-wrap:wrap;">
                            <span>Mean: <b style="color:#e2e8f0;">{_fmt(stats['mean'])}</b></span>
                            <span>Median: <b style="color:#e2e8f0;">{_fmt(stats['median'])}</b></span>
                            <span>CV: <b style="color:{vol_color};">{cv:.0f}%</b></span>
                            <span>Outliers: <b style="color:{'#ef4444' if out_p > 5 else '#10b981'};">{out_p:.1f}%</b></span>
                        </div>
                        <div style="font-size:0.72rem;color:#64748b;margin-top:4px;">
                            Range: {_fmt(stats['min'])} – {_fmt(stats['max'])}
                            &nbsp;|&nbsp; {stats['dist_shape']}
                        </div>
                        {"<div style='font-size:0.7rem;color:#ef4444;margin-top:4px;font-weight:700;'>" + qa + "</div>" if sev in ('bad','warn') else ""}
                    </div>
                    """, unsafe_allow_html=True)

                    # Business meaning
                    _safe_biz_msg = str(biz_msg).replace('{', '&#123;').replace('}', '&#125;')
                    st.markdown(
                        '<div style="padding:8px 12px;background:rgba(99,102,241,0.06);'
                        'border-radius:8px;margin-bottom:8px;'
                        'border-left:3px solid rgba(99,102,241,0.4);'
                        'font-size:0.78rem;color:#cbd5e1;line-height:1.7;">'
                        + _safe_biz_msg +
                        '</div>',
                        unsafe_allow_html=True
                    )

                    st.plotly_chart(_build_column_histogram(df, col),
                                    use_container_width=True, config={'displayModeBar': False},
                                    key=f"pc_hist_{col}")

                    # Benchmarks row
                    cv_bench = "✅ Low (<20%)" if cv < 20 else "⚠️ Moderate (20-50%)" if cv < 50 else "🔴 High (>50%)"
                    skew_bench = ("🔴 Right-skewed" if stats['skew'] > 1 else
                                  "🔴 Left-skewed" if stats['skew'] < -1 else "✅ Normal-like")
                    st.markdown(f"""
                    <div style="display:flex;gap:8px;margin-top:4px;margin-bottom:12px;flex-wrap:wrap;">
                        <span style="font-size:0.72rem;color:#94a3b8;">
                            Volatility: <span style="color:{vol_color};">{cv_bench}</span>
                        </span>
                        <span style="font-size:0.72rem;color:#94a3b8;"> | </span>
                        <span style="font-size:0.72rem;color:#94a3b8;">
                            Shape: {skew_bench}
                        </span>
                        <span style="font-size:0.72rem;color:#94a3b8;"> | </span>
                        <span style="font-size:0.72rem;color:#94a3b8;">
                            Missing: <span style="color:{'#ef4444' if missing_p > 10 else '#f59e0b' if missing_p > 5 else '#10b981'};">{missing_p:.1f}%</span>
                        </span>
                    </div>
                    """, unsafe_allow_html=True)

                else:
                    stats = _analyze_categorical_column(df[col])
                    if not stats:
                        st.markdown(f"**`{col}`** — insufficient data")
                        continue

                    conc      = stats.get('concentration', 'low')
                    conc_color = {'high': '#ef4444', 'moderate': '#f59e0b', 'low': '#10b981'}.get(conc, '#94a3b8')
                    sev, qa   = _col_quality_action(col, missing_n, len(df), stats, False)
                    biz_msg   = _col_business_meaning(col, stats, False, col_roles)

                    if missing_n > 0 or conc == 'high':
                        quality_issues.append({'col': col, 'severity': sev, 'issue': qa})
                    col_summaries.append({'col': col, 'type': 'categorical', 'unique': stats['unique'],
                                          'top1': stats['top_1_share'], 'conc': conc,
                                          'missing_pct': missing_n / max(len(df), 1) * 100})

                    st.markdown(f"""
                    <div style="padding:12px 16px;background:rgba(16,185,129,0.06);
                                border-radius:12px;margin-bottom:8px;
                                border-left:4px solid {conc_color};">
                        <div style="display:flex;justify-content:space-between;align-items:flex-start;">
                            <div style="font-size:0.88rem;font-weight:700;color:#34d399;">{col}</div>
                            <span style="background:{conc_color};color:#000;border-radius:20px;
                                         padding:2px 10px;font-size:0.7rem;font-weight:700;">
                                {conc.upper()} CONC
                            </span>
                        </div>
                        <div style="font-size:0.75rem;color:#94a3b8;margin-top:6px;
                                    display:flex;gap:12px;flex-wrap:wrap;">
                            <span>Unique: <b style="color:#e2e8f0;">{stats['unique']:,}</b></span>
                            <span>Top share: <b style="color:{conc_color};">{stats['top_1_share']:.1f}%</b></span>
                            <span>Missing: <b style="color:{'#ef4444' if missing_n > 0 else '#10b981'};">{missing_n}</b></span>
                        </div>
                        {"<div style='font-size:0.7rem;color:#ef4444;margin-top:4px;font-weight:700;'>" + qa + "</div>" if sev in ('bad','warn') else ""}
                    </div>
                    """, unsafe_allow_html=True)

                    # Business meaning
                    _safe_biz_msg2 = str(biz_msg).replace('{', '&#123;').replace('}', '&#125;')
                    st.markdown(
                        '<div style="padding:8px 12px;background:rgba(99,102,241,0.06);'
                        'border-radius:8px;margin-bottom:8px;'
                        'border-left:3px solid rgba(99,102,241,0.4);'
                        'font-size:0.78rem;color:#cbd5e1;line-height:1.7;">'
                        + _safe_biz_msg2 +
                        '</div>',
                        unsafe_allow_html=True
                    )

                    st.plotly_chart(_build_column_bar(df, col),
                                    use_container_width=True, config={'displayModeBar': False},
                                    key=f"pc_bar_{col}")

    st.markdown("---")

    # ── SECTION 4: Data Quality Action List ──
    st.markdown("""
    <div style="font-size:1.1rem;font-weight:700;color:#f1f5f9;
                text-transform:uppercase;letter-spacing:1px;margin:0.5rem 0 1rem 0;
                border-bottom:2px solid rgba(99,102,241,0.4);padding-bottom:0.5rem;">
        SECTION 4: Data Quality Action List
    </div>""", unsafe_allow_html=True)

    if quality_issues:
        bad_issues  = [x for x in quality_issues if x['severity'] == 'bad']
        warn_issues = [x for x in quality_issues if x['severity'] == 'warn']

        if bad_issues:
            st.markdown(f"**🔴 Critical Issues ({len(bad_issues)}) — Fix Before Analysis:**")
            for qi in bad_issues:
                st.markdown(f"""
                <div style="background:rgba(239,68,68,0.08);border-left:3px solid #ef4444;
                            border-radius:8px;padding:10px 14px;margin-bottom:6px;
                            font-size:0.84rem;color:#e2e8f0;">
                    <span style="color:#ef4444;font-weight:700;">{qi['col']}</span> — {qi['issue']}
                </div>
                """, unsafe_allow_html=True)

        if warn_issues:
            st.markdown(f"**⚠️ Warnings ({len(warn_issues)}) — Address for Higher Accuracy:**")
            for qi in warn_issues:
                st.markdown(f"""
                <div style="background:rgba(245,158,11,0.08);border-left:3px solid #f59e0b;
                            border-radius:8px;padding:10px 14px;margin-bottom:6px;
                            font-size:0.84rem;color:#e2e8f0;">
                    <span style="color:#f59e0b;font-weight:700;">{qi['col']}</span> — {qi['issue']}
                </div>
                """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div style="background:rgba(16,185,129,0.08);border:1px solid rgba(16,185,129,0.3);
                    border-radius:10px;padding:14px 18px;">
            <span style="color:#10b981;font-weight:700;">✅ No critical data quality issues detected</span>
            <span style="color:#94a3b8;font-size:0.85rem;margin-left:8px;">
                — all analysed columns are within acceptable quality thresholds.
            </span>
        </div>
        """, unsafe_allow_html=True)

    _n_critical = len([x for x in quality_issues if x['severity'] == 'bad'])
    _has_critical = _n_critical > 0
    _business_impact_box(
        "🔬", "SECTION 4 BUSINESS IMPACT — The Cost of Data Quality",
        f"Every data quality issue identified above has a direct financial cost: "
        f"missing revenue data leads to underreported KPIs; "
        f"duplicate records inflate revenue by double-counting transactions; "
        f"high-volatility columns make forecasts unreliable. "
        + (f"There are {_n_critical} critical column(s) requiring immediate remediation before this data can be used for financial decisions."
           if _has_critical else
           "All critical columns are clean — this dataset supports reliable financial analysis and forecasting.")
    )
    _findings_box(
        "SECTION 4 FINDINGS — Column Intelligence Summary",
        f"<strong>Columns analysed:</strong> {max_display} of {len(df.columns)}<br/>"
        f"<strong>Numeric columns:</strong> {len([x for x in col_summaries if x['type']=='numeric'])} "
        f"| High volatility (CV>50%): {len([x for x in col_summaries if x.get('cv',0)>50])}<br/>"
        f"<strong>Categorical columns:</strong> {len([x for x in col_summaries if x['type']=='categorical'])} "
        f"| High concentration: {len([x for x in col_summaries if x.get('conc')=='high'])}<br/>"
        f"<strong>Quality issues:</strong> {len([x for x in quality_issues if x['severity']=='bad'])} critical, "
        f"{len([x for x in quality_issues if x['severity']=='warn'])} warnings<br/><br/>"
        f"<strong>Action:</strong> "
        f"{'Resolve critical quality issues first, then proceed to Strategic Advisor for recommendations.' if any(x['severity']=='bad' for x in quality_issues) else 'Data is analysis-ready. Use the Strategic Advisor tab for prioritised action recommendations.'}"
    )

    st.markdown("---")

    # ── SECTION 5: Interactive Segment Analysis ──
    st.markdown("""
    <div style="font-size:1.1rem;font-weight:700;color:#f1f5f9;
                text-transform:uppercase;letter-spacing:1px;margin:0.5rem 0 1rem 0;
                border-bottom:2px solid rgba(99,102,241,0.4);padding-bottom:0.5rem;">
        SECTION 5: Interactive Segment Analysis
    </div>""", unsafe_allow_html=True)

    cat_cols = [c for c in df.select_dtypes(include='object').columns]
    num_cols = [c for c in df.select_dtypes(include='number').columns]

    if cat_cols and num_cols:
        seg_a_col, seg_b_col, seg_c_col = st.columns(3)
        with seg_a_col:
            group_by   = st.selectbox("Group by (Dimension)", cat_cols, key="fin_group_by")
        with seg_b_col:
            metric_col = st.selectbox("Metric (KPI)", num_cols, key="fin_metric_col")
        with seg_c_col:
            agg_fn = st.selectbox("Aggregation", ['sum', 'mean', 'count', 'median'], key="fin_agg")

        try:
            seg_df = df.groupby(group_by)[metric_col].agg(agg_fn).reset_index()
            seg_df.columns = [group_by, metric_col]
            seg_df = seg_df.sort_values(metric_col, ascending=False)

            seg_chart, seg_info = st.columns([3, 2])
            with seg_chart:
                fig = px.bar(seg_df, x=group_by, y=metric_col,
                             title=f"{agg_fn.capitalize()} of {metric_col} by {group_by}",
                             color=metric_col,
                             color_continuous_scale=[[0,'#1e3a5f'],[0.5,'#b45309'],[1,'#f59e0b']])
                fig.update_layout(
                    paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                    font=dict(color='#94a3b8'), coloraxis_showscale=False,
                    xaxis=dict(gridcolor='rgba(255,255,255,0.05)', tickangle=-30),
                    yaxis=dict(gridcolor='rgba(255,255,255,0.05)'),
                    margin=dict(l=10, r=10, t=50, b=40),
                )
                st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False}, key="pc_5001")

            with seg_info:
                if len(seg_df) >= 2:
                    top_val  = float(seg_df[metric_col].iloc[0])
                    bot_val  = float(seg_df[metric_col].iloc[-1])
                    gap_pct  = _pct(top_val - bot_val, max(abs(bot_val), 1))
                    top_name = str(seg_df[group_by].iloc[0])
                    bot_name = str(seg_df[group_by].iloc[-1])
                    total_v  = float(seg_df[metric_col].sum())
                    top3_pct = float(seg_df[metric_col].head(3).sum()) / max(total_v, 1) * 100

                    st.markdown(f"""
                    <div style="padding:16px 18px;background:rgba(245,158,11,0.06);
                                border:1px solid rgba(245,158,11,0.2);
                                border-radius:12px;margin-bottom:10px;">
                        <div style="font-size:0.8rem;color:#f59e0b;font-weight:700;margin-bottom:10px;">
                            SEGMENT INTELLIGENCE
                        </div>
                        <div style="font-size:0.83rem;color:#e2e8f0;line-height:1.8;">
                            🏆 <strong>Top:</strong> {top_name} ({_fmt(top_val)})<br/>
                            ⬇️ <strong>Bottom:</strong> {bot_name} ({_fmt(bot_val)})<br/>
                            📊 <strong>Gap:</strong> {gap_pct:.1f}% ({_fmt(top_val - bot_val)})<br/>
                            🎯 <strong>Top 3 share:</strong> {top3_pct:.1f}% of total
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                    # Business interpretation
                    conc_msg = (f"⚠️ Top 3 segments hold {top3_pct:.0f}% — concentration risk. "
                                f"Strategy: Diversify across lower-performing segments."
                                if top3_pct > 70 else
                                f"✅ Revenue well distributed across segments — healthy base. "
                                f"Strategy: Grow all segments proportionally.")
                    gap_msg  = (f"🔴 {gap_pct:.0f}% gap between top and bottom — significant underperformance in lower segments. "
                                f"Investigate why {bot_name} lags and replicate {top_name}'s success."
                                if gap_pct > 100 else
                                f"⚠️ {gap_pct:.0f}% performance gap. Review bottom segments for growth potential."
                                if gap_pct > 30 else
                                f"✅ Segments performing within {gap_pct:.0f}% of each other — consistent performance.")
                    st.markdown(f"""
                    <div style="padding:12px 16px;background:rgba(99,102,241,0.06);
                                border-left:3px solid rgba(99,102,241,0.5);
                                border-radius:8px;font-size:0.78rem;color:#cbd5e1;line-height:1.7;">
                        {conc_msg}<br/>{gap_msg}
                    </div>
                    """, unsafe_allow_html=True)

        except Exception as e:
            st.warning(f"Could not render segment analysis: {e}")
    else:
        st.info("Need at least one categorical and one numeric column for segment analysis.")

    # ── Raw data preview ──
    st.markdown("---")
    render_section_header("📄", "Data Preview", "RAW")
    max_rows = st.slider("Rows to display", 5, min(500, len(df)), 20, key="fin_preview_rows")
    st.dataframe(df.head(max_rows), use_container_width=True)


# ──────────────────────────────────────────────────────────────
# TAB: FINANCIAL INTELLIGENCE & AID IMPACT ANALYSIS
# (migrated from student_360 tab7)
# ──────────────────────────────────────────────────────────────

def render_financial_intelligence_tab(
    df: pd.DataFrame,
    kpis: Dict[str, Any] = None,
    col_roles: Dict[str, List[str]] = None,
    advisory: Dict[str, Any] = None,
    narrative: Dict[str, Any] = None,
):
    """Tab: Financial Intelligence & Aid Impact Analysis (4 Insights)."""
    kpis      = kpis      or {}
    col_roles = col_roles or {}
    advisory  = advisory  or {}
    narrative = narrative or {}

    st.markdown("## 💰 Financial Intelligence & Aid Impact Analysis")
    st.markdown("*Comprehensive financial analysis, aid distribution, and effectiveness assessment*")

    # ══════════════════════════════════════════════════════════════
    # NARRATIVE INTELLIGENCE PANEL
    # ══════════════════════════════════════════════════════════════
    _has_tuition_nip = 'enrollment_tuition_amount' in df.columns
    _has_aid_nip     = 'financial_aid_monetary_amount' in df.columns
    _has_gpa_nip     = 'cumulative_gpa' in df.columns
    _has_etype_nip   = 'enrollment_type' in df.columns
    _has_status_nip  = 'enrollment_enrollment_status' in df.columns

    # Build chart recommendation list dynamically based on available columns
    _chart_recs = []
    _kpi_recs   = []

    if _has_tuition_nip and _has_aid_nip:
        _chart_recs.append(("✅ PRIORITY", "Tuition vs Aid Waterfall", "Both tuition and aid columns present — full revenue flow analysis available"))
        _kpi_recs.append(("Aid Coverage %", "Aid as % of tuition — key sustainability KPI"))
    elif _has_tuition_nip:
        _chart_recs.append(("✅ AVAILABLE", "Revenue Treemap by Enrollment Type", "Tuition data present — breakdown by enrollment type recommended"))
        _kpi_recs.append(("Avg Tuition/Student", "Revenue per enrolled student"))
    elif _has_aid_nip:
        _chart_recs.append(("✅ AVAILABLE", "Aid Distribution Histogram", "Aid data present — distribution and coverage ratio available"))
        _kpi_recs.append(("Aid Recipients %", "Share of students receiving support"))

    if _has_gpa_nip and _has_aid_nip:
        _chart_recs.append(("✅ PRIORITY", "GPA vs Aid Scatter (OLS Trendline)", "GPA + aid columns present — ROI effectiveness analysis unlocked"))
        _kpi_recs.append(("GPA Lift", "Average GPA difference: aided vs non-aided students"))
    elif _has_gpa_nip:
        _chart_recs.append(("⚠️ PARTIAL", "GPA Distribution Only", "Add financial_aid_monetary_amount to unlock aid-vs-GPA effectiveness"))

    if _has_etype_nip and _has_tuition_nip:
        _chart_recs.append(("✅ AVAILABLE", "Tuition Treemap by Enrollment Type", "Segment revenue by program type for strategic pricing decisions"))
    if _has_status_nip:
        _chart_recs.append(("✅ AVAILABLE", "Active Rate by Aid Status", "Enrollment status enables retention comparison: aided vs non-aided"))
        _kpi_recs.append(("Retention Delta", "Aided vs non-aided active enrollment rate difference"))
    if not _has_tuition_nip:
        _chart_recs.append(("❌ BLOCKED", "Revenue Flow Waterfall", "Add enrollment_tuition_amount to enable full revenue analysis"))
    if not _has_gpa_nip:
        _chart_recs.append(("❌ BLOCKED", "Aid ROI Effectiveness", "Add cumulative_gpa to measure academic impact of aid investment"))

    # Pull narrative & advisory intelligence
    _adv_opps    = advisory.get('opportunities', [])
    _adv_risks   = advisory.get('risks', [])
    _adv_score   = (advisory.get('advisory_score') or {}).get('overall', None)
    _adv_summary = advisory.get('executive_summary', '')
    _rev_health  = advisory.get('revenue_health', '')
    _margin_h    = advisory.get('margin_health', '')
    _key_sentences = narrative.get('key_sentences', [])
    _sentiment   = narrative.get('sentiment', 'cautious')
    _sent_color  = {'positive': '#10b981', 'cautious': '#f59e0b', 'concerning': '#ef4444'}.get(_sentiment, '#94a3b8')
    _sent_icon   = {'positive': '📈', 'cautious': '⚠️', 'concerning': '🔴'}.get(_sentiment, '📊')

    with st.expander(f"{_sent_icon} Narrative Intelligence & Chart Recommendations — Click to Expand", expanded=True):
        ni_col1, ni_col2 = st.columns([2, 1])

        with ni_col1:
            if _adv_summary:
                _safe_adv_summary = str(_adv_summary).replace('{', '&#123;').replace('}', '&#125;')
                st.markdown(
                    f'<div style="background:linear-gradient(135deg,rgba(99,102,241,0.12),rgba(59,130,246,0.08));'
                    f'padding:14px 18px;border-radius:10px;border-left:4px solid {_sent_color};margin-bottom:12px;">'
                    f'<div style="color:{_sent_color};font-weight:700;font-size:0.85rem;margin-bottom:6px;letter-spacing:0.5px;">'
                    f'{_sent_icon} ADVISORY SUMMARY ({_sentiment.upper()})'
                    '</div>'
                    '<div style="color:#e2e8f0;font-size:0.88rem;line-height:1.7;">'
                    + _safe_adv_summary +
                    '</div></div>',
                    unsafe_allow_html=True
                )

            if _key_sentences:
                _ks_html = "".join([
                    "<div style='color:#f1f5f9;font-size:0.85rem;margin-bottom:6px;'>&bull; "
                    + str(s).replace('<', '&lt;').replace('>', '&gt;') + "</div>"
                    for s in _key_sentences[:4]
                ])
                st.markdown(
                    '<div style="background:rgba(15,23,42,0.5);border:1px solid rgba(255,255,255,0.08);'
                    'padding:12px 16px;border-radius:8px;margin-bottom:10px;">'
                    '<div style="color:#e2e8f0;font-size:0.8rem;font-weight:700;margin-bottom:8px;letter-spacing:0.5px;">KEY FINDINGS FROM DATA</div>'
                    + _ks_html +
                    '</div>',
                    unsafe_allow_html=True
                )

            if _adv_opps:
                _opp_html = ""
                for opp in _adv_opps[:3]:
                    _imp = opp.get('impact', 'medium')
                    _ic  = {'high': '#10b981', 'medium': '#f59e0b', 'low': '#94a3b8'}.get(_imp, '#94a3b8')
                    _opp_title  = str(opp.get('title', '')).replace('<', '&lt;').replace('>', '&gt;')
                    _opp_action = str(opp.get('action', '')).replace('<', '&lt;').replace('>', '&gt;')
                    _opp_html += (
                        f"<div style='margin-bottom:6px;padding:8px 12px;background:rgba(16,185,129,0.06);"
                        f"border-radius:6px;border-left:3px solid {_ic};'>"
                        f"<span style='color:{_ic};font-size:0.75rem;font-weight:700;'>{_imp.upper()} IMPACT</span> "
                        + '<span style="color:#e2e8f0;font-size:0.83rem;">' + _opp_title + '</span><br/>'
                        + '<span style="color:#cbd5e1;font-size:0.8rem;">' + _opp_action + '</span></div>'
                    )
                st.markdown(
                    '<div style="background:rgba(15,23,42,0.5);border:1px solid rgba(255,255,255,0.08);'
                    'padding:12px 16px;border-radius:8px;">'
                    '<div style="color:#10b981;font-size:0.78rem;font-weight:600;margin-bottom:8px;letter-spacing:0.5px;">OPPORTUNITIES FROM ADVISORY ENGINE</div>'
                    + _opp_html +
                    '</div>',
                    unsafe_allow_html=True
                )

        with ni_col2:
            if _chart_recs:
                recs_html = ""
                for status, chart_name, reason in _chart_recs:
                    _rc = '#10b981' if '✅' in status else ('#f59e0b' if '⚠️' in status else '#ef4444')
                    recs_html += (
                        f"<div style='margin-bottom:8px;padding:8px 10px;background:rgba(15,23,42,0.6);"
                        f"border-radius:6px;border-left:3px solid {_rc};'>"
                        f"<div style='color:{_rc};font-size:0.72rem;font-weight:700;'>{status}</div>"
                        f"<div style='color:#e2e8f0;font-size:0.8rem;font-weight:600;margin-top:2px;'>{chart_name}</div>"
                        f"<div style='color:#94a3b8;font-size:0.75rem;margin-top:2px;'>{reason}</div>"
                        f"</div>"
                    )
                st.markdown(
                    '<div style="background:rgba(15,23,42,0.5);border:1px solid rgba(255,255,255,0.08);'
                    'padding:12px 14px;border-radius:8px;margin-bottom:10px;">'
                    '<div style="color:#818cf8;font-size:0.78rem;font-weight:600;margin-bottom:8px;letter-spacing:0.5px;">'
                    '📊 CHART RECOMMENDATIONS FOR YOUR DATA'
                    '</div>'
                    + recs_html +
                    '</div>',
                    unsafe_allow_html=True
                )

            if _kpi_recs:
                _kpi_html = "".join([
                    f"<div style='color:#e2e8f0;font-size:0.82rem;margin-bottom:5px;'>"
                    f"<span style='color:#f59e0b;font-weight:700;'>📌 {k}</span><br/>"
                    f"<span style='color:#94a3b8;font-size:0.78rem;'>{v}</span></div>"
                    for k, v in _kpi_recs
                ])
                st.markdown(
                    '<div style="background:rgba(15,23,42,0.5);border:1px solid rgba(255,255,255,0.08);'
                    'padding:12px 14px;border-radius:8px;margin-bottom:8px;">'
                    '<div style="color:#f59e0b;font-size:0.78rem;font-weight:600;margin-bottom:8px;letter-spacing:0.5px;">'
                    '🎯 KEY KPIs FOR YOUR DATASET'
                    '</div>'
                    + _kpi_html +
                    '</div>',
                    unsafe_allow_html=True
                )

            if _adv_score is not None:
                _sc_c = '#10b981' if _adv_score >= 70 else '#f59e0b' if _adv_score >= 45 else '#ef4444'
                _safe_rev_health = str(_rev_health).replace('{', '&#123;').replace('}', '&#125;')
                _safe_margin_h   = str(_margin_h).replace('{', '&#123;').replace('}', '&#125;')
                st.markdown(
                    f'<div style="text-align:center;padding:14px;background:rgba(15,23,42,0.5);'
                    f'border:1px solid rgba(255,255,255,0.08);border-radius:8px;margin-top:4px;">'
                    '<div style="color:#e2e8f0;font-size:0.78rem;font-weight:700;letter-spacing:0.5px;">ADVISORY SCORE</div>'
                    f'<div style="color:{_sc_c};font-size:2.2rem;font-weight:900;line-height:1.2;">{_adv_score}</div>'
                    '<div style="color:#94a3b8;font-size:0.75rem;">/100 — Revenue: '
                    + _safe_rev_health + ' | Margin: ' + _safe_margin_h +
                    '</div></div>',
                    unsafe_allow_html=True
                )

    # ── Guard: need at least tuition or aid columns ──
    _has_tuition = 'enrollment_tuition_amount' in df.columns
    _has_aid     = 'financial_aid_monetary_amount' in df.columns
    _has_gpa     = 'cumulative_gpa' in df.columns
    _has_sid     = 'student_id' in df.columns
    _has_etype   = 'enrollment_type' in df.columns
    _has_status  = 'enrollment_enrollment_status' in df.columns
    _has_balance = 'past_due_balance' in df.columns or 'balance_due' in df.columns
    _has_paid    = 'total_payments_ytd' in df.columns or 'fee_paid' in df.columns
    _has_fee     = 'fee_paid' in df.columns   # legacy fallback
    _has_rent    = 'rent_paid' in df.columns  # legacy fallback
    _has_acct    = 'past_due_balance' in df.columns

    if not _has_tuition and not _has_aid:
        st.info("Upload a dataset with tuition or financial aid columns (enrollment_tuition_amount / financial_aid_monetary_amount) to view this tab.")
        return

    # ── Dynamic Data Inventory ──
    _avail = []
    _missing = []
    _col_map = {
        'enrollment_tuition_amount': ('💵', 'Tuition Revenue'),
        'financial_aid_monetary_amount': ('🎓', 'Financial Aid'),
        'cumulative_gpa': ('📚', 'GPA Data'),
        'student_id': ('🔑', 'Student IDs'),
        'enrollment_type': ('📋', 'Enrollment Type'),
        'enrollment_enrollment_status': ('✅', 'Enrollment Status'),
        'past_due_balance':    ('⚖️', 'Outstanding Balance'),
        'total_payments_ytd':  ('💳', 'Total Payments YTD'),
        'financial_hold_status': ('🔒', 'Financial Hold'),
    }
    for col, (icon, label) in _col_map.items():
        if col in df.columns:
            _avail.append(f'<span style="background:rgba(16,185,129,0.15);border:1px solid rgba(16,185,129,0.4);border-radius:16px;padding:3px 10px;font-size:0.78rem;color:#10b981;margin:3px;display:inline-block;">{icon} {label}</span>')
        else:
            _missing.append(f'<span style="background:rgba(148,163,184,0.12);border:1px solid rgba(148,163,184,0.3);border-radius:16px;padding:3px 10px;font-size:0.78rem;color:#94a3b8;margin:3px;display:inline-block;">✗ {label}</span>')

    with st.expander("📊 Dataset Column Availability — Click to Expand", expanded=False):
        st.markdown(
            f'<div style="margin-bottom:6px;font-size:0.8rem;color:#e2e8f0;font-weight:700;">AVAILABLE ({len(_avail)} columns):</div>'
            f'<div style="margin-bottom:12px;">{"".join(_avail)}</div>'
            f'<div style="margin-bottom:6px;font-size:0.8rem;color:#94a3b8;font-weight:600;">MISSING ({len(_missing)} columns — limited analysis):</div>'
            f'<div>{"".join(_missing)}</div>',
            unsafe_allow_html=True
        )

    # ── Core metrics ──
    total_tuition = df['enrollment_tuition_amount'].sum() if _has_tuition else 0
    total_aid     = df['financial_aid_monetary_amount'].sum() if _has_aid else 0
    students_with_aid = int(df[df['financial_aid_monetary_amount'] > 0]['student_id'].nunique()) if (_has_aid and _has_sid) else (int((df['financial_aid_monetary_amount'] > 0).sum()) if _has_aid else 0)
    net_tuition   = total_tuition - total_aid
    # Use unique student count so avg-per-student = total / unique students, not total / rows
    total_students = int(df['student_id'].nunique()) if _has_sid else len(df)
    total_rows     = len(df)  # for "Dataset: X records" display

    # Dynamic summary sentence
    _summary_parts = []
    if _has_tuition and total_tuition > 0:
        _summary_parts.append(f"<strong>AED {total_tuition/1e6:.1f}M total tuition revenue</strong>")
    if _has_aid and total_aid > 0:
        _summary_parts.append(f"<strong>AED {total_aid/1e6:.1f}M financial aid</strong> supporting <strong>{students_with_aid:,} students</strong>")
    if _has_gpa:
        _avg_gpa = df['cumulative_gpa'].mean()
        _summary_parts.append(f"average GPA of <strong>{_avg_gpa:.2f}</strong>")
    _summary_text = ", ".join(_summary_parts) if _summary_parts else f"<strong>{total_students:,} students</strong>"

    st.markdown(f"""
    <p style='color:white;font-size:1.1rem;'>
    Financial analysis covering {_summary_text},
    examining revenue streams, aid distribution patterns, and ROI on student support investments.
    Dataset: <strong>{total_rows:,} records</strong> &times; <strong>{len(df.columns)} columns</strong>.
    </p>
    """, unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════════
    # INSIGHT 1: REVENUE & TUITION
    # ═══════════════════════════════════════════════════════════════
    st.markdown("---")
    st.markdown("## 💵 Insight 1: Revenue & Tuition — WHO Pays What")
    st.markdown("*Tuition revenue streams, enrollment type analysis, and cash flow patterns*")

    aid_coverage  = (total_aid / total_tuition * 100) if total_tuition > 0 else 0
    avg_tuition_per_student = total_tuition / total_students if total_students > 0 else 0
    net_revenue_per_student = net_tuition / total_students if total_students > 0 else 0

    # Payments: catalog canonical 'total_payments_ytd' covers Total_Payments_YTD
    if 'total_payments_ytd' in df.columns:
        total_paid = pd.to_numeric(df['total_payments_ytd'], errors='coerce').sum()
    elif 'fee_paid' in df.columns or 'rent_paid' in df.columns:
        rent_paid_sum = pd.to_numeric(df['rent_paid'], errors='coerce').sum() if 'rent_paid' in df.columns else 0
        fee_paid_sum  = pd.to_numeric(df['fee_paid'],  errors='coerce').sum() if 'fee_paid'  in df.columns else 0
        total_paid    = rent_paid_sum + fee_paid_sum
    else:
        total_paid = 0
    # Outstanding balance: catalog canonical 'past_due_balance' covers Past_Due_Balance
    if 'past_due_balance' in df.columns:
        total_balance = pd.to_numeric(df['past_due_balance'], errors='coerce').sum()
    elif 'balance_due' in df.columns:
        total_balance = pd.to_numeric(df['balance_due'], errors='coerce').sum()
    else:
        total_balance = 0

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total Tuition",         f"AED {total_tuition/1e6:.1f}M", help="Gross tuition revenue")
    c2.metric("Net Tuition",            f"AED {net_tuition/1e6:.1f}M",
              delta=f"{(net_tuition/total_tuition*100):.1f}% of gross" if total_tuition else None)
    c3.metric("Avg Tuition/Student",    f"AED {avg_tuition_per_student:,.0f}")
    c4.metric("Total Payments",         f"AED {total_paid/1e6:.1f}M", help="Rent + fees collected")
    c5.metric("Outstanding Balance",    f"AED {total_balance/1e6:.1f}M", delta_color="inverse")

    st.markdown("#### 💰 Revenue Stream Analysis")
    col1, col2 = st.columns(2)

    with col1:
        if _has_etype and _has_tuition:
            tuition_by_type = df.groupby('enrollment_type')['enrollment_tuition_amount'].sum().reset_index()
            fig = px.treemap(tuition_by_type, path=['enrollment_type'],
                             values='enrollment_tuition_amount',
                             color='enrollment_tuition_amount',
                             color_continuous_scale='Blues')
            fig.update_layout(
                title=dict(text="Tuition Revenue by Enrollment Type",
                           font=dict(size=20, color='white', family='Arial Black'), x=0.5, xanchor='center'),
                plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(30,41,59,0.85)',
                font=dict(color='white', size=14), height=450)
            fig.update_traces(textfont=dict(size=14, color='white', family='Arial Black'),
                              marker=dict(line=dict(color='white', width=2)))
            st.plotly_chart(fig, use_container_width=True, key="pc_5359")
            top_type = tuition_by_type.loc[tuition_by_type['enrollment_tuition_amount'].idxmax()]
            st.info(f"📌 **Top Revenue Source:** {top_type['enrollment_type']} (AED {top_type['enrollment_tuition_amount']/1e6:.1f}M)")
        else:
            st.info("Enrollment type or tuition column not found — treemap unavailable.")

    with col2:
        fig = go.Figure(go.Waterfall(
            name="Financial Flow", orientation="v",
            measure=["relative", "relative", "relative", "total"],
            x=["Total Tuition", "Financial Aid", "Payments Received", "Outstanding Balance"],
            y=[total_tuition, -total_aid, -total_paid, total_balance],
            text=[f"AED {total_tuition/1e6:.1f}M", f"-AED {total_aid/1e6:.1f}M",
                  f"-AED {total_paid/1e6:.1f}M", f"AED {total_balance/1e6:.1f}M"],
            textposition="outside",
            connector={"line": {"color": "#818cf8"}},
            increasing={"marker": {"color": "#10b981"}},
            decreasing={"marker": {"color": "#ef4444"}},
            totals={"marker": {"color": "#6366f1"}}
        ))
        fig.update_layout(
            title=dict(text="Financial Flow Analysis",
                       font=dict(size=20, color='white', family='Arial Black'), x=0.5, xanchor='center'),
            plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(30,41,59,0.85)',
            font=dict(color='white', size=14), height=450,
            yaxis=dict(title=dict(text="Amount (AED)", font=dict(size=14, color='white')),
                       tickfont=dict(size=12, color='white'),
                       gridcolor='rgba(255,255,255,0.2)', showgrid=True),
            showlegend=False)
        fig.update_traces(textfont=dict(size=12, color='white', family='Arial Black'))
        st.plotly_chart(fig, use_container_width=True, key="pc_5389")

    collection_efficiency = ((total_tuition - total_balance) / total_tuition * 100) if total_tuition > 0 else 0
    _tuition_by_type_len = len(tuition_by_type) if (_has_etype and _has_tuition) else 1

    _net_pct   = (net_tuition / total_tuition * 100) if total_tuition else 0
    _bal_pct   = (total_balance / total_tuition * 100) if total_tuition else 0
    _aid_strat = "balanced" if 50 <= _net_pct <= 70 else "conservative"
    _col_eff   = "strong" if _bal_pct < 5 else "moderate"
    _rev_pos   = "healthy" if net_revenue_per_student > 40000 else "adequate" if net_revenue_per_student > 30000 else "tight"
    st.markdown(f"""
<div style='background:linear-gradient(135deg,rgba(99,102,241,0.1),rgba(59,130,246,0.1));
            padding:1.2rem;border-radius:8px;border-left:4px solid #6366f1;margin:1rem 0;'>
    <div style='color:#6366f1;font-weight:600;font-size:1rem;margin-bottom:0.5rem;'>💼 Business Impact: Revenue Optimization & Cash Flow Management</div>
    <div style='color:white;font-size:0.95rem;line-height:1.7;'>
    <strong>Tuition revenue forms institutional financial foundation and operational sustainability.</strong>
    Total tuition of AED {total_tuition/1e6:.1f}M across {total_students:,} students generates average revenue of AED {avg_tuition_per_student:,.0f} per student.
    Net tuition after financial aid represents {_net_pct:.1f}% of gross, indicating {_aid_strat} aid investment strategy.
    Outstanding balance of AED {total_balance/1e6:.1f}M ({_bal_pct:.1f}% of tuition) indicates {_col_eff} collection efficiency.
    Net revenue per student of AED {net_revenue_per_student:,.0f} supports {_rev_pos} financial position.
    </div>
</div>
""", unsafe_allow_html=True)

    _col_meets = "Meets" if collection_efficiency >= 95 else "Below"
    _div_label = "Balanced" if _tuition_by_type_len > 3 else "Concentrated"
    st.markdown(f"""
<div style='background:linear-gradient(135deg,rgba(16,185,129,0.15),rgba(5,150,105,0.15));
            padding:1.5rem;border-radius:10px;border:2px solid #10b981;margin:1.5rem 0;'>
    <div style='color:#10b981;font-weight:700;font-size:1.2rem;margin-bottom:1rem;'>📋 INSIGHT 1 FINDINGS</div>
    <div style='color:white;font-size:0.95rem;line-height:1.8;'>
    <strong>Revenue Metrics:</strong><br/>
    &bull; Total gross tuition: AED {total_tuition/1e6:.2f}M<br/>
    &bull; Net tuition (after aid): AED {net_tuition/1e6:.2f}M ({_net_pct:.1f}% of gross)<br/>
    &bull; Average tuition/student: AED {avg_tuition_per_student:,.0f}<br/>
    &bull; Net revenue/student: AED {net_revenue_per_student:,.0f}<br/><br/>
    <strong>Cash Flow:</strong><br/>
    &bull; Payments collected: AED {total_paid/1e6:.2f}M<br/>
    &bull; Outstanding balance: AED {total_balance/1e6:.2f}M ({_bal_pct:.1f}% of tuition)<br/>
    &bull; Collection efficiency: {collection_efficiency:.1f}% ({_col_meets} target of &gt;95%)<br/><br/>
    <strong>Revenue Diversification:</strong><br/>
    &bull; {_tuition_by_type_len} enrollment types analysed<br/>
    &bull; Concentration: {_div_label} across program types
    </div>
</div>
""", unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════════
    # INSIGHT 2: FINANCIAL AID DISTRIBUTION
    # ═══════════════════════════════════════════════════════════════
    if not _has_aid:
        st.info("financial_aid_monetary_amount column not found — Insights 2-4 unavailable.")
        return

    st.markdown("---")
    st.markdown("## 🎓 Insight 2: Financial Aid Distribution — WHAT Aid We Provide")
    st.markdown("*Aid allocation patterns, coverage analysis, and accessibility initiatives*")

    aid_data         = df[df['financial_aid_monetary_amount'] > 0]
    avg_aid          = aid_data['financial_aid_monetary_amount'].mean() if len(aid_data) > 0 else 0
    aid_students_pct = (students_with_aid / total_students * 100) if total_students > 0 else 0
    students_no_aid  = total_students - students_with_aid
    median_aid_val   = aid_data['financial_aid_monetary_amount'].median() if len(aid_data) > 0 else 0
    max_aid          = df['financial_aid_monetary_amount'].max() if _has_aid else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Aid Distributed", f"AED {total_aid/1e6:.1f}M", delta=f"{aid_coverage:.1f}% of tuition")
    c2.metric("Students with Aid",     f"{students_with_aid:,}",    delta=f"{aid_students_pct:.1f}% of total")
    c3.metric("Average Aid Amount",    f"AED {avg_aid:,.0f}" if not pd.isna(avg_aid) else "N/A",
              help="Average among aid recipients")
    c4.metric("Aid Coverage %",        f"{aid_coverage:.1f}%",
              delta="Strong" if aid_coverage >= 40 else "Moderate")

    st.markdown("#### 🎁 Aid Distribution Analysis")
    col1, col2 = st.columns(2)

    with col1:
        fig = go.Figure()
        fig.add_trace(go.Histogram(
            x=aid_data['financial_aid_monetary_amount'], nbinsx=25,
            marker=dict(color='#10b981', opacity=0.8, line=dict(color='white', width=1)),
            name='Aid Distribution',
            hovertemplate='<b>Aid Range:</b> %{x:,.0f}<br><b>Students:</b> %{y}<extra></extra>'
        ))
        mean_aid_val = aid_data['financial_aid_monetary_amount'].mean() if len(aid_data) > 0 else 0
        fig.add_vline(x=mean_aid_val,   line_dash="dash", line_color="#f59e0b", line_width=3,
                      annotation_text=f"Mean: AED {mean_aid_val:,.0f}", annotation_position="top")
        fig.add_vline(x=median_aid_val, line_dash="dash", line_color="#ec4899", line_width=3,
                      annotation_text=f"Median: AED {median_aid_val:,.0f}", annotation_position="top right")
        fig.update_layout(
            title=dict(text="Financial Aid Distribution",
                       font=dict(size=20, color='white', family='Arial Black'), x=0.5, xanchor='center'),
            plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(30,41,59,0.85)',
            font=dict(color='white', size=14), height=450,
            xaxis=dict(title=dict(text="Financial Aid Amount (AED)", font=dict(size=16, color='white')),
                       tickfont=dict(size=14, color='white'), gridcolor='rgba(255,255,255,0.1)'),
            yaxis=dict(title=dict(text="Number of Students", font=dict(size=16, color='white')),
                       tickfont=dict(size=14, color='white'), gridcolor='rgba(255,255,255,0.2)'))
        st.plotly_chart(fig, use_container_width=True, key="pc_5487")

    with col2:
        fig = go.Figure(data=[go.Pie(
            labels=['With Financial Aid', 'Without Aid'],
            values=[students_with_aid, students_no_aid],
            hole=0.5,
            marker=dict(colors=['#10b981', '#6366f1'], line=dict(color='white', width=3)),
            textinfo='label+percent+value',
            textfont=dict(size=14, color='white', family='Arial Black'),
            hovertemplate='<b>%{label}</b><br>Students: %{value}<br>%{percent}<extra></extra>'
        )])
        fig.update_layout(
            title=dict(text="Student Aid Coverage Distribution",
                       font=dict(size=20, color='white', family='Arial Black'), x=0.5, xanchor='center'),
            plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(30,41,59,0.85)',
            font=dict(color='white', size=14), height=450,
            legend=dict(orientation="v", yanchor="middle", y=0.5, xanchor="left", x=1.05,
                        font=dict(size=14, color='white'), bgcolor='rgba(0,0,0,0.3)',
                        bordercolor='rgba(255,255,255,0.3)', borderwidth=2))
        st.plotly_chart(fig, use_container_width=True, key="pc_5507")

    aid_per_student_overall = total_aid / total_students if total_students > 0 else 0
    low_aid  = len(aid_data[aid_data['financial_aid_monetary_amount'] <= median_aid_val]) if len(aid_data) else 0
    high_aid = len(aid_data[aid_data['financial_aid_monetary_amount'] >  median_aid_val]) if len(aid_data) else 0

    _aid_commit  = "strong" if aid_coverage >= 50 else "moderate" if aid_coverage >= 40 else "selective"
    _aid_strat2  = "inclusive" if aid_students_pct >= 60 else "targeted" if aid_students_pct >= 40 else "selective"
    _mkt_pos     = "highly accessible" if aid_coverage >= 60 else "competitive" if aid_coverage >= 40 else "selective"
    st.markdown(f"""
<div style='background:linear-gradient(135deg,rgba(99,102,241,0.1),rgba(59,130,246,0.1));
            padding:1.2rem;border-radius:8px;border-left:4px solid #6366f1;margin:1rem 0;'>
    <div style='color:#6366f1;font-weight:600;font-size:1rem;margin-bottom:0.5rem;'>💼 Business Impact: Access, Equity &amp; Strategic Enrollment</div>
    <div style='color:white;font-size:0.95rem;line-height:1.7;'>
    <strong>Financial aid investment drives accessibility, diversity, and competitive positioning.</strong>
    Total aid of AED {total_aid/1e6:.1f}M represents {aid_coverage:.1f}% tuition coverage — {_aid_commit} commitment to access.
    Supporting {students_with_aid:,} students ({aid_students_pct:.1f}% of enrollment) with average aid of AED {avg_aid:,.0f} demonstrates {_aid_strat2} strategy.
    Aid coverage of {aid_coverage:.1f}% positions the institution as {_mkt_pos} in the market (target: 40-60%).
    </div>
</div>
""", unsafe_allow_html=True)

    _aid_equity  = "Balanced" if avg_aid and abs(avg_aid - median_aid_val) / avg_aid < 0.2 else "Varied"
    _aid_status2 = "Strong" if 40 <= aid_coverage <= 60 else ("High" if aid_coverage > 60 else "Moderate")
    st.markdown(f"""
<div style='background:linear-gradient(135deg,rgba(16,185,129,0.15),rgba(5,150,105,0.15));
            padding:1.5rem;border-radius:10px;border:2px solid #10b981;margin:1.5rem 0;'>
    <div style='color:#10b981;font-weight:700;font-size:1.2rem;margin-bottom:1rem;'>📋 INSIGHT 2 FINDINGS</div>
    <div style='color:white;font-size:0.95rem;line-height:1.8;'>
    <strong>Aid Investment:</strong><br/>
    &bull; Total aid distributed: AED {total_aid/1e6:.2f}M<br/>
    &bull; Aid coverage: {aid_coverage:.1f}% of total tuition<br/>
    &bull; Students receiving aid: {students_with_aid:,} ({aid_students_pct:.1f}%)<br/>
    &bull; Students without aid: {students_no_aid:,} ({100 - aid_students_pct:.1f}%)<br/><br/>
    <strong>Distribution Analysis:</strong><br/>
    &bull; Average aid per recipient: AED {avg_aid:,.0f}<br/>
    &bull; Median aid amount: AED {median_aid_val:,.0f}<br/>
    &bull; Aid per student (overall): AED {aid_per_student_overall:,.0f}<br/>
    &bull; Maximum aid awarded: AED {max_aid:,.0f}<br/><br/>
    <strong>Distribution Pattern:</strong><br/>
    &bull; Below median: {low_aid} students | Above median: {high_aid} students<br/>
    &bull; Aid equity: {_aid_equity} (mean vs median spread)<br/>
    &bull; Status: {_aid_status2} (target 40-60%)
    </div>
</div>
""", unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════════
    # INSIGHT 3: AID EFFECTIVENESS & ROI
    # ═══════════════════════════════════════════════════════════════
    if not _has_gpa:
        st.info("cumulative_gpa column not found — Insight 3 (Aid Effectiveness) unavailable.")
    else:
        st.markdown("---")
        st.markdown("## 📈 Insight 3: Aid Effectiveness & ROI — HOW Aid Impacts Success")
        st.markdown("*Academic performance comparison, retention impact, and ROI assessment*")

        aid_comp = df.copy()
        aid_comp['has_aid'] = aid_comp['financial_aid_monetary_amount'] > 0
        _agg_cols = {'cumulative_gpa': 'mean'}
        if _has_sid:
            _agg_cols['student_id'] = 'count'
        aid_gpa = aid_comp.groupby('has_aid').agg(_agg_cols).reset_index()
        aid_gpa['has_aid'] = aid_gpa['has_aid'].map({True: 'With Financial Aid', False: 'Without Aid'})

        gpa_with_aid    = aid_gpa[aid_gpa['has_aid'] == 'With Financial Aid']['cumulative_gpa'].values[0]  if len(aid_gpa[aid_gpa['has_aid'] == 'With Financial Aid']) > 0  else 0
        gpa_without_aid = aid_gpa[aid_gpa['has_aid'] == 'Without Aid']['cumulative_gpa'].values[0]         if len(aid_gpa[aid_gpa['has_aid'] == 'Without Aid']) > 0           else 0
        gpa_diff_val    = gpa_with_aid - gpa_without_aid

        aided_active_rate     = 0
        non_aided_active_rate = 0
        if _has_status:
            _aided_mask     = df['financial_aid_monetary_amount'] > 0
            _non_aided_mask = df['financial_aid_monetary_amount'] == 0
            aided_active_rate     = (len(df[_aided_mask     & (df['enrollment_enrollment_status'] == 'Active')]) / students_with_aid * 100)     if students_with_aid > 0     else 0
            non_aided_active_rate = (len(df[_non_aided_mask & (df['enrollment_enrollment_status'] == 'Active')]) / max(students_no_aid, 1) * 100) if students_no_aid > 0 else 0

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Aided Student GPA",    f"{gpa_with_aid:.2f}",    delta=f"{gpa_diff_val:+.2f} vs non-aided")
        c2.metric("Non-Aided Student GPA", f"{gpa_without_aid:.2f}")
        c3.metric("Aided Active Rate",    f"{aided_active_rate:.1f}%", delta=f"{(aided_active_rate - non_aided_active_rate):+.1f}% vs non-aided")
        c4.metric("Non-Aided Active Rate", f"{non_aided_active_rate:.1f}%")

        st.markdown("#### 🎯 Aid Effectiveness Comparison")
        col1, col2 = st.columns(2)

        with col1:
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=aid_gpa['has_aid'], y=aid_gpa['cumulative_gpa'],
                marker=dict(color=['#10b981', '#6366f1'], line=dict(color=['#065f46', '#4338ca'], width=2)),
                text=['<b>' + f"{v:.2f}" + '</b>' for v in aid_gpa['cumulative_gpa']],
                textfont=dict(color='white', size=16, family='Arial Black'),
                textposition='outside',
                hovertemplate='<b>%{x}</b><br>Avg GPA: <b>%{y:.2f}</b><extra></extra>'
            ))
            fig.update_layout(
                title=dict(text="Academic Performance: Aid vs Non-Aid Recipients",
                           font=dict(size=20, color='white', family='Arial Black'), x=0.5, xanchor='center'),
                plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(30,41,59,0.85)',
                font=dict(color='white', size=14), height=450,
                xaxis=dict(title=dict(text="Student Category", font=dict(size=16, color='white')),
                           tickfont=dict(size=14, color='white')),
                yaxis=dict(title=dict(text="Average GPA", font=dict(size=16, color='white')),
                           tickfont=dict(size=14, color='white'),
                           gridcolor='rgba(255,255,255,0.2)', range=[0, 4.5]))
            st.plotly_chart(fig, use_container_width=True, key="pc_5613")
            if gpa_diff_val > 0.05:
                st.success(f"✅ Aid recipients outperform by {gpa_diff_val:.2f} points — effective support!")
            elif gpa_diff_val < -0.05:
                st.info(f"ℹ️ Aid recipients {abs(gpa_diff_val):.2f} points lower — may need additional support")
            else:
                st.success("✅ Comparable performance — aid levels the playing field!")

        with col2:
            aid_students_df = df[df['financial_aid_monetary_amount'] > 0].copy()
            if _has_etype and len(aid_students_df) > 1:
                _scatter_cols = ['financial_aid_monetary_amount', 'cumulative_gpa', 'enrollment_type']
                _size_col = 'credits_attempted' if 'credits_attempted' in df.columns else None
                if _size_col:
                    _scatter_cols.append(_size_col)
                _scatter_df = aid_students_df[_scatter_cols].dropna()
                fig = px.scatter(
                    _scatter_df,
                    x='financial_aid_monetary_amount',
                    y='cumulative_gpa',
                    color='enrollment_type',
                    size=_size_col if _size_col and _size_col in _scatter_df.columns else None,
                    trendline="ols",
                    color_discrete_sequence=px.colors.qualitative.Set2
                )
            else:
                _scatter_df = aid_students_df[['financial_aid_monetary_amount', 'cumulative_gpa']].dropna()
                fig = px.scatter(_scatter_df, x='financial_aid_monetary_amount', y='cumulative_gpa',
                                 trendline="ols")
            fig.update_layout(
                title=dict(text="Aid Amount vs GPA Correlation",
                           font=dict(size=20, color='white', family='Arial Black'), x=0.5, xanchor='center'),
                plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(30,41,59,0.85)',
                font=dict(color='white', size=14), height=450,
                xaxis=dict(title=dict(text="Financial Aid Amount (AED)", font=dict(size=16, color='white')),
                           tickfont=dict(size=14, color='white'), gridcolor='rgba(255,255,255,0.1)'),
                yaxis=dict(title=dict(text="Cumulative GPA", font=dict(size=16, color='white')),
                           tickfont=dict(size=14, color='white'), gridcolor='rgba(255,255,255,0.2)'),
                legend=dict(font=dict(size=12, color='white'), bgcolor='rgba(0,0,0,0.3)', borderwidth=1))
            st.plotly_chart(fig, use_container_width=True, key="pc_5652")
            _corr_df = aid_students_df[['financial_aid_monetary_amount', 'cumulative_gpa']].dropna()
            correlation = _corr_df.corr().iloc[0, 1] if len(_corr_df) > 1 else 0
            if abs(correlation) < 0.2:
                st.success(f"✅ Weak correlation ({correlation:.2f}): Aid amount doesn't predict GPA — good equity!")
            else:
                st.info(f"ℹ️ Correlation: {correlation:.2f} — {'positive' if correlation > 0 else 'negative'} relationship with GPA")

        retention_advantage = aided_active_rate - non_aided_active_rate
        roi_estimate = students_with_aid * max(retention_advantage, 0) / 100 * 70000

        aided_high_perf     = len(df[(df['financial_aid_monetary_amount'] > 0)  & (df['cumulative_gpa'] >= 3.5)])
        non_aided_high_perf = len(df[(df['financial_aid_monetary_amount'] == 0) & (df['cumulative_gpa'] >= 3.5)])
        aided_high_perf_pct     = (aided_high_perf     / students_with_aid  * 100) if students_with_aid  > 0 else 0
        non_aided_high_perf_pct = (non_aided_high_perf / max(students_no_aid, 1) * 100) if students_no_aid > 0 else 0

        _gpa_dir    = "advantage" if gpa_diff_val > 0 else "parity" if abs(gpa_diff_val) <= 0.05 else "disadvantage"
        _eff_label  = "strong" if gpa_diff_val >= -0.05 else "concerning"
        _ret_dir    = "advantage" if retention_advantage > 0 else "disadvantage"
        _corr_val   = correlation if 'correlation' in dir() else 0
        _alloc_type = "equitable" if abs(_corr_val) < 0.3 else "strategic"
        st.markdown(f"""
<div style='background:linear-gradient(135deg,rgba(99,102,241,0.1),rgba(59,130,246,0.1));
            padding:1.2rem;border-radius:8px;border-left:4px solid #6366f1;margin:1rem 0;'>
    <div style='color:#6366f1;font-weight:600;font-size:1rem;margin-bottom:0.5rem;'>💼 Business Impact: Aid ROI &amp; Strategic Value</div>
    <div style='color:white;font-size:0.95rem;line-height:1.7;'>
    <strong>Financial aid delivers measurable returns through retention, performance, and institutional reputation.</strong>
    Aid recipients demonstrate {abs(gpa_diff_val):.2f} point GPA {_gpa_dir} vs non-aided, indicating {_eff_label} support effectiveness.
    Aided students show {aided_active_rate:.1f}% active rate vs {non_aided_active_rate:.1f}% non-aided ({retention_advantage:+.1f} pp {_ret_dir}).
    Estimated retention benefit: AED {roi_estimate/1e6:.1f}M. Aid correlation with GPA of {_corr_val:.2f} indicates {_alloc_type} allocation.
    </div>
</div>
""", unsafe_allow_html=True)

        _perf_dir   = "Positive" if gpa_diff_val > 0.05 else "Neutral" if gpa_diff_val >= -0.05 else "Negative"
        _strat_act  = "Maintain" if gpa_diff_val >= -0.05 and retention_advantage >= 0 else "Optimize"
        _supp_act   = "Continue" if gpa_diff_val >= -0.05 else "Enhance"
        st.markdown(f"""
<div style='background:linear-gradient(135deg,rgba(16,185,129,0.15),rgba(5,150,105,0.15));
            padding:1.5rem;border-radius:10px;border:2px solid #10b981;margin:1.5rem 0;'>
    <div style='color:#10b981;font-weight:700;font-size:1.2rem;margin-bottom:1rem;'>📋 INSIGHT 3 FINDINGS</div>
    <div style='color:white;font-size:0.95rem;line-height:1.8;'>
    <strong>Academic Performance Impact:</strong><br/>
    &bull; Aided GPA: {gpa_with_aid:.2f} | Non-aided GPA: {gpa_without_aid:.2f}<br/>
    &bull; Performance difference: {gpa_diff_val:+.2f} points ({_perf_dir})<br/>
    &bull; Aided high performers (&ge;3.5): {aided_high_perf_pct:.1f}% ({aided_high_perf} students)<br/>
    &bull; Non-aided high performers: {non_aided_high_perf_pct:.1f}% ({non_aided_high_perf} students)<br/><br/>
    <strong>Retention Impact:</strong><br/>
    &bull; Aided active rate: {aided_active_rate:.1f}% | Non-aided: {non_aided_active_rate:.1f}%<br/>
    &bull; Retention advantage: {retention_advantage:+.1f} pp<br/>
    &bull; Estimated retention ROI: AED {roi_estimate/1e6:.1f}M<br/><br/>
    <strong>Strategic Actions:</strong><br/>
    &bull; {_strat_act} current aid allocation strategy<br/>
    &bull; {_supp_act} academic support for aided students
    </div>
</div>
""", unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════════
    # INSIGHT 4: ADVANCED FINANCIAL INTELLIGENCE
    # ═══════════════════════════════════════════════════════════════
    st.markdown("---")
    st.markdown("## 💎 Insight 4: Advanced Financial Intelligence — Deep Balance & Coverage Analytics")
    st.markdown("*Balance distribution, fee collection, and tuition-aid relationship analysis*")

    if 'past_due_balance' in df.columns or 'total_payments_ytd' in df.columns or 'balance_due' in df.columns or 'fee_paid' in df.columns:
        st.markdown("### 💳 Student Balance & Fee Collection Performance")
        col1, col2 = st.columns(2)

        with col1:
            # Use catalog canonical past_due_balance, fallback to account_balance
            _bal_col_i4 = 'past_due_balance' if 'past_due_balance' in df.columns else ('account_balance' if 'account_balance' in df.columns else None)
            if _bal_col_i4 is not None:
                balance_bins = pd.cut(df[_bal_col_i4],
                                      bins=[-0.1, 0, 1000, 5000, 10000, 50000, float('inf')],
                                      labels=['No Balance', 'AED 1-1K', 'AED 1K-5K',
                                              'AED 5K-10K', 'AED 10K-50K', 'AED 50K+'])
                balance_dist = balance_bins.value_counts().sort_index().reset_index()
                balance_dist.columns = ['Balance Range', 'Count']
                fig = go.Figure(data=[go.Bar(
                    x=balance_dist['Balance Range'], y=balance_dist['Count'],
                    marker=dict(color=['#10b981', '#3b82f6', '#f59e0b', '#ef4444', '#991b1b', '#7f1d1d'],
                                line=dict(color='white', width=2)),
                    text=['<b>' + str(v) + '</b>' for v in balance_dist['Count']],
                    textposition='outside', textfont=dict(size=13, color='white', family='Arial Black'),
                    hovertemplate='<b>%{x}</b><br>Students: %{y}<extra></extra>'
                )])
                fig.update_layout(
                    title=dict(text="Outstanding Balance Distribution by Range",
                               font=dict(size=18, color='white', family='Arial Black'), x=0.5, xanchor='center'),
                    xaxis=dict(title="Balance Range", tickfont=dict(size=10, color='white'), tickangle=-45),
                    yaxis=dict(title="Students", tickfont=dict(size=12, color='white'), gridcolor='rgba(255,255,255,0.2)'),
                    plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(30,41,59,0.85)',
                    font=dict(color='white', size=11), height=450, margin=dict(b=120))
                st.plotly_chart(fig, use_container_width=True, key="pc_5744")
            else:
                st.info("past_due_balance column not found — upload dataset with past_due_balance or account_balance.")

        with col2:
            # Use catalog canonical total_payments_ytd for fee collection, fallback to fee_paid
            _fee_col_i4 = 'total_payments_ytd' if 'total_payments_ytd' in df.columns else ('fee_paid' if 'fee_paid' in df.columns else None)
            if _fee_col_i4 is not None and _has_etype:
                fee_perf = df.groupby('enrollment_type').agg(
                    student_count=(_fee_col_i4, 'count'),
                    total_fees=(_fee_col_i4, 'sum')
                ).reset_index()
                fee_perf['Fees (AED M)']     = fee_perf['total_fees'] / 1e6
                fee_perf['Per Student (AED)'] = fee_perf['total_fees'] / fee_perf['student_count']

                fig = make_subplots(specs=[[{"secondary_y": True}]])
                fig.add_trace(go.Bar(
                    name='Total Fees Collected', x=fee_perf['enrollment_type'], y=fee_perf['Fees (AED M)'],
                    marker=dict(color='#10b981', line=dict(color='white', width=2)),
                    text=[f"<b>AED {v:.2f}M</b>" for v in fee_perf['Fees (AED M)']],
                    textposition='outside', textfont=dict(size=11, color='white', family='Arial Black')
                ), secondary_y=False)
                fig.add_trace(go.Scatter(
                    name='Per Student Average', x=fee_perf['enrollment_type'], y=fee_perf['Per Student (AED)'],
                    mode='lines+markers',
                    marker=dict(size=12, color='#f59e0b', line=dict(color='white', width=2)),
                    line=dict(width=3, color='#f59e0b'),
                    text=[f"<b>AED {v:,.0f}</b>" for v in fee_perf['Per Student (AED)']],
                    textposition='top center', textfont=dict(size=11, color='#f59e0b', family='Arial Black')
                ), secondary_y=True)
                fig.update_layout(
                    title=dict(text="Fee Collection by Enrollment Type",
                               font=dict(size=18, color='white', family='Arial Black'), x=0.5, xanchor='center'),
                    xaxis=dict(title="", tickfont=dict(size=11, color='white'), tickangle=-45),
                    plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(30,41,59,0.85)',
                    font=dict(color='white', size=11), height=450,
                    legend=dict(x=0.5, y=1.15, xanchor='center', orientation='h',
                                font=dict(size=10, color='white'), bgcolor='rgba(0,0,0,0.3)'),
                    margin=dict(b=120))
                fig.update_yaxes(title_text="Total Fees (AED M)", secondary_y=False,
                                 tickfont=dict(color='white'), title_font=dict(color='white'))
                fig.update_yaxes(title_text="Per Student (AED)", secondary_y=True,
                                 tickfont=dict(color='white'), title_font=dict(color='white'))
                st.plotly_chart(fig, use_container_width=True, key="pc_5785")
            else:
                st.info("total_payments_ytd (or fee_paid) column not found — fee collection chart unavailable.")

    if _has_tuition and _has_aid:
        st.markdown("### 💰 Tuition vs Aid Relationship Analysis")
        tuition_aid_data = df[['enrollment_tuition_amount', 'financial_aid_monetary_amount']].copy()
        if _has_gpa:
            tuition_aid_data['cumulative_gpa'] = df['cumulative_gpa']
        tuition_aid_data = tuition_aid_data.dropna()
        tuition_aid_data = tuition_aid_data[tuition_aid_data['enrollment_tuition_amount'] > 0]
        tuition_aid_data['Aid Coverage %'] = (tuition_aid_data['financial_aid_monetary_amount'] / tuition_aid_data['enrollment_tuition_amount'] * 100).clip(0, 100)

        col1, col2 = st.columns(2)
        with col1:
            coverage_bins = pd.cut(tuition_aid_data['Aid Coverage %'],
                                   bins=[0, 25, 50, 75, 100],
                                   labels=['0-25%', '25-50%', '50-75%', '75-100%'])
            coverage_dist = coverage_bins.value_counts().sort_index().reset_index()
            coverage_dist.columns = ['Coverage Range', 'Count']
            fig = go.Figure(data=[go.Bar(
                x=coverage_dist['Coverage Range'], y=coverage_dist['Count'],
                marker=dict(color=['#ef4444', '#f59e0b', '#3b82f6', '#10b981'],
                            line=dict(color='white', width=2)),
                text=['<b>' + str(v) + '</b>' for v in coverage_dist['Count']],
                textposition='outside', textfont=dict(size=14, color='white', family='Arial Black'),
                hovertemplate='<b>%{x}</b><br>Students: %{y}<extra></extra>'
            )])
            fig.update_layout(
                title=dict(text="Aid Coverage of Tuition Distribution",
                           font=dict(size=18, color='white', family='Arial Black'), x=0.5, xanchor='center'),
                xaxis=dict(title="Aid Coverage Range", tickfont=dict(size=12, color='white')),
                yaxis=dict(title="Number of Students", tickfont=dict(size=12, color='white'),
                           gridcolor='rgba(255,255,255,0.2)'),
                plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(30,41,59,0.85)',
                font=dict(color='white', size=12), height=450)
            st.plotly_chart(fig, use_container_width=True, key="pc_5821")

        with col2:
            sample_data = tuition_aid_data.sample(min(500, len(tuition_aid_data)))
            fig = go.Figure()
            scatter_marker = dict(size=8, line=dict(color='white', width=1), opacity=0.7)
            if _has_gpa and 'cumulative_gpa' in sample_data.columns:
                scatter_marker.update(dict(color=sample_data['cumulative_gpa'],
                                           colorscale='RdYlGn', cmin=2.0, cmax=4.0, showscale=True,
                                           colorbar=dict(title=dict(text="GPA", font=dict(color="white")),
                                                         tickfont=dict(color='white'))))
            fig.add_trace(go.Scatter(
                x=sample_data['enrollment_tuition_amount'] / 1000,
                y=sample_data['financial_aid_monetary_amount'] / 1000,
                mode='markers', marker=scatter_marker,
                hovertemplate='Tuition: AED %{x:.0f}K<br>Aid: AED %{y:.0f}K<extra></extra>'
            ))
            max_tuition = sample_data['enrollment_tuition_amount'].max() / 1000
            fig.add_trace(go.Scatter(
                x=[0, max_tuition], y=[0, max_tuition], mode='lines',
                line=dict(color='rgba(255,255,255,0.3)', width=2, dash='dash'),
                name='100% Coverage', hoverinfo='skip'
            ))
            fig.update_layout(
                title=dict(text="Tuition vs Aid Relationship (GPA Colored)",
                           font=dict(size=18, color='white', family='Arial Black'), x=0.5, xanchor='center'),
                xaxis=dict(title="Tuition Amount (AED K)", tickfont=dict(size=11, color='white'),
                           gridcolor='rgba(255,255,255,0.1)'),
                yaxis=dict(title="Aid Amount (AED K)", tickfont=dict(size=11, color='white'),
                           gridcolor='rgba(255,255,255,0.2)'),
                plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(30,41,59,0.85)',
                font=dict(color='white', size=11), height=450,
                legend=dict(x=0.02, y=0.98, font=dict(size=10, color='white'), bgcolor='rgba(0,0,0,0.3)'))
            st.plotly_chart(fig, use_container_width=True, key="pc_5854")

    # ── Dynamic Insight 4 Business Impact ──
    _i4_balance_str   = f"AED {total_balance/1e6:.2f}M outstanding balance ({_bal_pct:.1f}% of tuition)" if _has_balance and total_tuition > 0 else ("balance data available" if _has_balance else "no past_due_balance column")
    _fee_paid_sum_i4  = total_paid  # total_paid already uses catalog total_payments_ytd
    _i4_fee_str       = f"AED {_fee_paid_sum_i4/1e6:.2f}M in payments collected" if _fee_paid_sum_i4 > 0 else "no total_payments_ytd column in dataset"
    _i4_coverage_str  = f"{aid_coverage:.1f}% aid-to-tuition ratio ({('within' if 15 <= aid_coverage <= 35 else 'outside')} 15-35% target)" if total_tuition > 0 and _has_aid else "tuition or aid data missing for ratio"
    _i4_net_str       = f"net tuition AED {net_tuition/1e6:.2f}M after aid deduction" if total_tuition > 0 else ""

    st.markdown(f"""
<div style='background:linear-gradient(135deg,rgba(99,102,241,0.1),rgba(59,130,246,0.1));
            padding:1.2rem;border-radius:8px;border-left:4px solid #6366f1;margin:1rem 0;'>
    <div style='color:#6366f1;font-weight:600;font-size:1rem;margin-bottom:0.5rem;'>💼 Business Impact: Financial Health &amp; Collection Strategy</div>
    <div style='color:white;font-size:0.95rem;line-height:1.7;'>
    <strong>Outstanding balance analytics drive cash flow optimisation and collection strategy.</strong>
    Dataset shows {total_students:,} students: {_i4_balance_str}.
    {_i4_fee_str}. {_i4_coverage_str}.
    {("Net tuition: " + _i4_net_str + ". ") if _i4_net_str else ""}The tuition-aid relationship scatter reveals whether aid targets high-need students or serves strategic recruitment.
    Aid-to-tuition ratios inform budget sustainability — target 15-35% total aid coverage ensures access while
    maintaining fiscal health. These metrics support cash flow forecasting, collection resource allocation,
    aid budget optimisation, and pricing strategy development.
    </div>
</div>
""", unsafe_allow_html=True)


# ──────────────────────────────────────────────────────────────
# TAB: JOURNEY 2 — REVENUE & FINANCIAL STRATEGY
# (migrated from student_360 tab2 Journey 2 section)
# ──────────────────────────────────────────────────────────────

def render_journey2_tab(
    df: pd.DataFrame,
    kpis: Dict[str, Any] = None,
    col_roles: Dict[str, List[str]] = None,
    advisory: Dict[str, Any] = None,
    narrative: Dict[str, Any] = None,
):
    """Tab: Journey 2 — Revenue & Financial Strategy (4 Stories)."""
    kpis      = kpis      or {}
    col_roles = col_roles or {}
    advisory  = advisory  or {}
    narrative = narrative or {}

    st.markdown("# 💰 Journey 2: Revenue & Financial Strategy")
    st.markdown("*Understanding HOW we fund student success: Financial aid distribution, ROI, and fiscal sustainability*")

    # ══════════════════════════════════════════════════════════════
    # NARRATIVE INTELLIGENCE PANEL — Journey 2
    # ══════════════════════════════════════════════════════════════
    _j2_nip_cols = {
        'financial_aid_monetary_amount': True,
        'enrollment_tuition_amount':     False,
        'cumulative_gpa':                False,
        'enrollment_type':               False,
        'enrollment_enrollment_status':  False,
        'scholarship_type':              False,
        'sponsorship_type':              False,
    }
    _j2_present = {c: (c in df.columns) for c in _j2_nip_cols}

    # Dynamic story availability
    _story_avail = []
    _story_avail.append(("✅ Story 2.1", "Aid Investment Overview", "financial_aid_monetary_amount present"))
    if _j2_present['cumulative_gpa']:
        _story_avail.append(("✅ Story 2.2", "Aid Effectiveness & Outcomes", "cumulative_gpa present — GPA impact analysis available"))
    else:
        _story_avail.append(("❌ Story 2.2", "Aid Effectiveness (Blocked)", "Add cumulative_gpa to unlock GPA vs aid analysis"))
    if _j2_present['enrollment_tuition_amount']:
        _story_avail.append(("✅ Story 2.3", "Revenue Sustainability (Full)", "enrollment_tuition_amount present — full revenue analysis available"))
    else:
        _story_avail.append(("⚠️ Story 2.3", "Revenue Sustainability (Partial)", "Add enrollment_tuition_amount for revenue sustainability metrics"))
    if _j2_present['scholarship_type'] or _j2_present['sponsorship_type']:
        _story_avail.append(("✅ Story 2.4", "Advanced Analytics", "Scholarship/sponsorship type columns present"))
    else:
        _story_avail.append(("⚠️ Story 2.4", "Advanced Analytics (Limited)", "Add scholarship_type or sponsorship_type for programme-level analysis"))

    # Pull advisory intelligence
    _j2_adv_opps    = advisory.get('opportunities', [])
    _j2_adv_risks   = advisory.get('risks', [])
    _j2_adv_score   = (advisory.get('advisory_score') or {}).get('overall', None)
    _j2_adv_summary = advisory.get('executive_summary', '')
    _j2_rev_health  = advisory.get('revenue_health', '')
    _j2_key_sents   = narrative.get('key_sentences', [])
    _j2_sentiment   = narrative.get('sentiment', 'cautious')
    _j2_chapters    = narrative.get('chapters', [])
    _j2_sent_color  = {'positive': '#10b981', 'cautious': '#f59e0b', 'concerning': '#ef4444'}.get(_j2_sentiment, '#94a3b8')
    _j2_sent_icon   = {'positive': '📈', 'cautious': '⚠️', 'concerning': '🔴'}.get(_j2_sentiment, '📊')

    with st.expander(f"{_j2_sent_icon} Narrative Intelligence & Story Availability — Click to Expand", expanded=True):
        j2_ni_col1, j2_ni_col2 = st.columns([2, 1])

        with j2_ni_col1:
            # Advisory summary
            if _j2_adv_summary:
                _safe_j2_adv_summary = str(_j2_adv_summary).replace('{', '&#123;').replace('}', '&#125;')
                st.markdown(
                    f'<div style="background:linear-gradient(135deg,rgba(16,185,129,0.1),rgba(5,150,105,0.06));'
                    f'padding:14px 18px;border-radius:10px;border-left:4px solid {_j2_sent_color};margin-bottom:12px;">'
                    f'<div style="color:{_j2_sent_color};font-weight:700;font-size:0.85rem;margin-bottom:6px;letter-spacing:0.5px;">'
                    f'{_j2_sent_icon} FINANCIAL STRATEGY ADVISORY ({_j2_sentiment.upper()})'
                    '</div>'
                    '<div style="color:#e2e8f0;font-size:0.88rem;line-height:1.7;">'
                    + _safe_j2_adv_summary +
                    '</div></div>',
                    unsafe_allow_html=True
                )

            # Narrative chapter highlights (most relevant: profit, opening)
            _relevant_chapters = [ch for ch in _j2_chapters if ch.get('num') in ('3', '4', '5')][:2]
            if _relevant_chapters:
                _ch_html = ""
                for ch in _relevant_chapters:
                    _ch_type = ch.get('insight_type', 'insight')
                    _ch_color = '#f59e0b' if _ch_type == 'warning' else '#10b981'
                    _ch_html += (
                        f"<div style='margin-bottom:8px;padding:10px 12px;"
                        f"background:rgba(15,23,42,0.6);border-radius:6px;"
                        f"border-left:3px solid {_ch_color};'>"
                        f"<div style='color:{_ch_color};font-size:0.76rem;font-weight:700;'>CHAPTER {ch.get('num','')} — {ch.get('title','')}</div>"
                        f"<div style='color:#f1f5f9;font-size:0.84rem;margin-top:4px;line-height:1.6;'>{ch.get('insight','')}</div>"
                        f"</div>"
                    )
                st.markdown(
                    '<div style="background:rgba(15,23,42,0.5);border:1px solid rgba(255,255,255,0.08);'
                    'padding:12px 16px;border-radius:8px;margin-bottom:10px;">'
                    '<div style="color:#e2e8f0;font-size:0.8rem;font-weight:700;margin-bottom:8px;letter-spacing:0.5px;">'
                    'NARRATIVE CHAPTER INSIGHTS'
                    '</div>'
                    + _ch_html +
                    '</div>',
                    unsafe_allow_html=True
                )

            # Risks relevant to financial sustainability
            if _j2_adv_risks:
                _risk_html = ""
                for risk in _j2_adv_risks[:3]:
                    _sev = risk.get('severity', 'medium')
                    _rc  = {'high': '#ef4444', 'medium': '#f59e0b', 'low': '#94a3b8'}.get(_sev, '#94a3b8')
                    _rh_title = str(risk.get('title','')).replace('<','&lt;').replace('>','&gt;')
                    _rh_mitig = str(risk.get('mitigation','')).replace('<','&lt;').replace('>','&gt;')
                    _risk_html += (
                        f"<div style='margin-bottom:6px;padding:8px 12px;"
                        f"background:rgba(239,68,68,0.05);border-radius:6px;"
                        f"border-left:3px solid {_rc};'>"
                        f"<span style='color:{_rc};font-size:0.75rem;font-weight:700;'>{_sev.upper()} RISK</span> "
                        + '<span style="color:#e2e8f0;font-size:0.83rem;">' + _rh_title + '</span><br/>'
                        + '<span style="color:#cbd5e1;font-size:0.8rem;line-height:1.5;">' + _rh_mitig + '</span>'
                        + "</div>"
                    )
                st.markdown(
                    '<div style="background:rgba(15,23,42,0.5);border:1px solid rgba(255,255,255,0.08);'
                    'padding:12px 16px;border-radius:8px;">'
                    '<div style="color:#ef4444;font-size:0.78rem;font-weight:600;margin-bottom:8px;letter-spacing:0.5px;">'
                    'RISKS IDENTIFIED BY ADVISORY ENGINE'
                    '</div>'
                    + _risk_html +
                    '</div>',
                    unsafe_allow_html=True
                )

        with j2_ni_col2:
            # Story availability
            story_html = ""
            for status, story_name, reason in _story_avail:
                _sc = '#10b981' if '✅' in status else ('#f59e0b' if '⚠️' in status else '#ef4444')
                story_html += (
                    f"<div style='margin-bottom:8px;padding:8px 10px;"
                    f"background:rgba(15,23,42,0.6);border-radius:6px;"
                    f"border-left:3px solid {_sc};'>"
                    f"<div style='color:{_sc};font-size:0.72rem;font-weight:700;'>{status}</div>"
                    f"<div style='color:#e2e8f0;font-size:0.8rem;font-weight:600;margin-top:2px;'>{story_name}</div>"
                    f"<div style='color:#94a3b8;font-size:0.75rem;margin-top:2px;'>{reason}</div>"
                    f"</div>"
                )
            st.markdown(
                '<div style="background:rgba(15,23,42,0.5);border:1px solid rgba(255,255,255,0.08);'
                'padding:12px 14px;border-radius:8px;margin-bottom:10px;">'
                '<div style="color:#818cf8;font-size:0.78rem;font-weight:600;margin-bottom:8px;letter-spacing:0.5px;">'
                '📖 STORY AVAILABILITY FOR YOUR DATA'
                '</div>'
                + story_html +
                '</div>',
                unsafe_allow_html=True
            )

            # Advisory score + 30-day actions
            if _j2_adv_score is not None:
                _sc_c = '#10b981' if _j2_adv_score >= 70 else '#f59e0b' if _j2_adv_score >= 45 else '#ef4444'
                _safe_j2_rev_health = str(_j2_rev_health).replace('{', '&#123;').replace('}', '&#125;')
                st.markdown(
                    f'<div style="text-align:center;padding:12px;background:rgba(15,23,42,0.5);'
                    f'border:1px solid rgba(255,255,255,0.08);border-radius:8px;margin-bottom:8px;">'
                    '<div style="color:#e2e8f0;font-size:0.78rem;font-weight:700;letter-spacing:0.5px;">ADVISORY SCORE</div>'
                    f'<div style="color:{_sc_c};font-size:2rem;font-weight:900;line-height:1.2;">{_j2_adv_score}</div>'
                    '<div style="color:#94a3b8;font-size:0.75rem;">/100 — Revenue: '
                    + _safe_j2_rev_health +
                    '</div></div>',
                    unsafe_allow_html=True
                )

            # 30-day key actions
            _fwd30 = advisory.get('forward_guidance_30d', {})
            _actions30 = _fwd30.get('key_actions', [])
            if _actions30:
                _act_html = "".join([
                    f"<div style='color:#f1f5f9;font-size:0.82rem;margin-bottom:5px;'>"
                    f"<span style='color:#818cf8;font-weight:700;'>→</span> {a}</div>"
                    for a in _actions30[:3]
                ])
                st.markdown(
                    '<div style="background:rgba(15,23,42,0.5);border:1px solid rgba(255,255,255,0.08);'
                    'padding:10px 12px;border-radius:8px;">'
                    '<div style="color:#6366f1;font-size:0.75rem;font-weight:600;margin-bottom:6px;letter-spacing:0.5px;">'
                    '⚡ 30-DAY PRIORITY ACTIONS'
                    '</div>'
                    + _act_html +
                    '</div>',
                    unsafe_allow_html=True
                )

    _has_aid     = 'financial_aid_monetary_amount' in df.columns
    _has_gpa     = 'cumulative_gpa' in df.columns
    _has_etype   = 'enrollment_type' in df.columns
    _has_tuition = 'enrollment_tuition_amount' in df.columns
    _has_fee     = 'total_payments_ytd' in df.columns or 'fee_paid' in df.columns  # catalog: total_payments_ytd
    _has_rent    = 'rent_paid' in df.columns  # legacy only — use total_payments_ytd when available
    _has_status  = 'enrollment_enrollment_status' in df.columns

    if not _has_aid:
        st.info("Upload a dataset with the financial_aid_monetary_amount column to view this tab.")
        return

    # ── Dynamic Data Inventory ──
    _j2_col_map = {
        'financial_aid_monetary_amount': ('🎓', 'Financial Aid', True),
        'enrollment_tuition_amount':     ('💵', 'Tuition Revenue', False),
        'cumulative_gpa':                ('📚', 'GPA Data', False),
        'enrollment_type':               ('📋', 'Enrollment Type', False),
        'enrollment_enrollment_status':  ('✅', 'Enrollment Status', False),
        'total_payments_ytd':            ('💳', 'Payments YTD', False),
        'past_due_balance':              ('⚖️', 'Past Due Balance', False),
        'scholarship_type':              ('🏆', 'Scholarship Type', False),
        'sponsorship_type':              ('🤝', 'Sponsorship Type', False),
    }
    _j2_avail, _j2_miss = [], []
    for col, (icon, label, required) in _j2_col_map.items():
        if col in df.columns:
            _j2_avail.append(
                f'<span style="background:rgba(16,185,129,0.15);border:1px solid rgba(16,185,129,0.4);'
                f'border-radius:16px;padding:3px 10px;font-size:0.78rem;color:#10b981;margin:3px;display:inline-block;">'
                f'{icon} {label}</span>'
            )
        elif not required:
            _j2_miss.append(
                f'<span style="background:rgba(148,163,184,0.12);border:1px solid rgba(148,163,184,0.3);'
                f'border-radius:16px;padding:3px 10px;font-size:0.78rem;color:#94a3b8;margin:3px;display:inline-block;">'
                f'✗ {label}</span>'
            )

    with st.expander("📊 Dataset Column Availability for Journey 2 — Click to Expand", expanded=False):
        st.markdown(
            f'<div style="margin-bottom:6px;font-size:0.8rem;color:#e2e8f0;font-weight:700;">AVAILABLE ({len(_j2_avail)} columns):</div>'
            f'<div style="margin-bottom:12px;">{"".join(_j2_avail)}</div>'
            f'<div style="margin-bottom:6px;font-size:0.8rem;color:#94a3b8;font-weight:600;">MISSING ({len(_j2_miss)} columns — some stories limited):</div>'
            f'<div>{"".join(_j2_miss)}</div>',
            unsafe_allow_html=True
        )

    total_aid_invested  = df['financial_aid_monetary_amount'].sum()
    students_with_aid   = int((df['financial_aid_monetary_amount'] > 0).sum())
    students_without_aid = len(df) - students_with_aid
    aid_recipient_pct   = (students_with_aid / len(df) * 100) if len(df) > 0 else 0
    avg_aid_amount      = df[df['financial_aid_monetary_amount'] > 0]['financial_aid_monetary_amount'].mean() if students_with_aid > 0 else 0
    avg_aid_per_all     = total_aid_invested / len(df) if len(df) > 0 else 0

    # Additional dynamic metrics
    actual_tuition_j2   = df['enrollment_tuition_amount'].sum() if _has_tuition else 0
    _avg_gpa_j2         = df['cumulative_gpa'].mean() if _has_gpa else None
    _active_count_j2    = int((df['enrollment_enrollment_status'] == 'Active').sum()) if _has_status else None

    # Dynamic business context
    _context_parts = [f"AED {total_aid_invested/1e6:.1f}M in financial aid investments"]
    if actual_tuition_j2 > 0:
        _context_parts.append(f"against AED {actual_tuition_j2/1e6:.1f}M tuition revenue ({total_aid_invested / actual_tuition_j2 * 100:.1f}% coverage)")
    if _avg_gpa_j2 is not None:
        _context_parts.append(f"student avg GPA {_avg_gpa_j2:.2f}")
    if _active_count_j2 is not None:
        _context_parts.append(f"{_active_count_j2:,} active students")

    st.markdown(f"**Business Context:** Analysing {', '.join(_context_parts)} — optimising student outcomes and institutional sustainability.")

    # ═══════════════════════════════════════════════════════════════
    # STORY 2.1: FINANCIAL AID INVESTMENT OVERVIEW
    # ═══════════════════════════════════════════════════════════════
    st.markdown("---")
    st.markdown("## 💵 Story 2.1: Financial Aid Investment Overview")
    st.markdown("*Total investment, recipient distribution, and strategic aid allocation*")

    st.markdown(f"<p style='color:white;font-size:1.1rem;'>Our institution has allocated <strong>AED {total_aid_invested/1e6:.2f}M</strong> in financial aid, supporting <strong>{students_with_aid} students ({aid_recipient_pct:.1f}%)</strong> across various scholarship and funding programmes.</p>", unsafe_allow_html=True)

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("💰 Total Aid",        f"AED {total_aid_invested/1e6:.2f}M", help="Total financial aid distributed")
    c2.metric("👥 Recipients",       f"{students_with_aid:,}", delta=f"{aid_recipient_pct:.1f}% of students")
    c3.metric("📊 Avg Package",      f"AED {avg_aid_amount:,.0f}" if not pd.isna(avg_aid_amount) else "N/A", help="Average aid per recipient")
    c4.metric("💡 Per Student",      f"AED {avg_aid_per_all:,.0f}", help="Average aid including non-recipients")
    if actual_tuition_j2 > 0:
        _aid_of_tuition = total_aid_invested / actual_tuition_j2 * 100
        c5.metric("📈 Aid/Tuition",  f"{_aid_of_tuition:.1f}%",
                  delta="Optimal" if 15 <= _aid_of_tuition <= 35 else "Review",
                  help=f"Aid AED {total_aid_invested/1e6:.2f}M vs Tuition AED {actual_tuition_j2/1e6:.2f}M")
    else:
        c5.metric("📈 Aid/Tuition",  "N/A", help="Upload enrollment_tuition_amount for this KPI")

    st.markdown("#### 📊 Financial Aid Distribution Analysis")
    col1, col2 = st.columns(2)

    with col1:
        fig_aid_dist = go.Figure(data=[go.Pie(
            labels=['Receiving Aid', 'Self-Funded'],
            values=[students_with_aid, students_without_aid],
            hole=0.4,
            marker=dict(colors=['#10b981', '#94a3b8'], line=dict(color='white', width=2)),
            textinfo='label+percent',
            textfont=dict(size=14, color='white', family='Arial Black'),
            hovertemplate='<b>%{label}</b><br>Students: %{value:,}<br>%{percent}<extra></extra>'
        )])
        fig_aid_dist.update_layout(
            title=dict(text="Aid Recipient Distribution",
                       font=dict(size=18, color='white', family='Arial Black'), x=0.5, xanchor='center'),
            plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(30,41,59,0.85)',
            showlegend=True,
            legend=dict(font=dict(size=12, color='white'), orientation='h',
                        yanchor='bottom', y=-0.2, xanchor='center', x=0.5),
            height=400, margin=dict(l=20, r=20, t=80, b=80),
            annotations=[dict(text=f'{students_with_aid}<br>Aided', x=0.5, y=0.5,
                              font_size=16, font_color='white', font_family='Arial Black',
                              showarrow=False)]
        )
        st.plotly_chart(fig_aid_dist, use_container_width=True, key="pc_6193")

    with col2:
        aid_df = df[df['financial_aid_monetary_amount'] > 0].copy()
        tier_ranges = [
            (0, 10000,         'Low (0-10K)',      '#94a3b8'),
            (10000, 25000,     'Medium (10-25K)',   '#6366f1'),
            (25000, 50000,     'High (25-50K)',     '#10b981'),
            (50000, float('inf'), 'Very High (50K+)', '#f59e0b')
        ]
        tier_labels, tier_counts, tier_colors = [], [], []
        for lo, hi, label, color in tier_ranges:
            cnt = len(aid_df[(aid_df['financial_aid_monetary_amount'] >= lo) &
                             (aid_df['financial_aid_monetary_amount'] < hi)])
            tier_labels.append(label); tier_counts.append(cnt); tier_colors.append(color)

        fig_tiers = go.Figure()
        fig_tiers.add_trace(go.Bar(
            x=tier_labels, y=tier_counts,
            marker=dict(color=tier_colors, line=dict(color='white', width=2)),
            text=tier_counts, textposition='outside',
            textfont=dict(size=12, color='white', family='Arial Black'),
            hovertemplate='<b>%{x}</b><br>Students: %{y:,}<extra></extra>'
        ))
        fig_tiers.update_layout(
            title=dict(text="Aid Amount Distribution by Tier",
                       font=dict(size=18, color='white', family='Arial Black'), x=0.5, xanchor='center'),
            xaxis=dict(title='', tickfont=dict(size=10, color='white'), showgrid=False),
            yaxis=dict(title='Number of Students', title_font=dict(size=12, color='white'),
                       tickfont=dict(size=11, color='white'), gridcolor='rgba(255,255,255,0.1)'),
            showlegend=False, paper_bgcolor='rgba(30,41,59,0.85)', plot_bgcolor='rgba(0,0,0,0)',
            height=400, margin=dict(l=60, r=20, t=80, b=80))
        st.plotly_chart(fig_tiers, use_container_width=True, key="pc_6225")

    if _has_etype:
        st.markdown("#### 💵 Aid Distribution by Enrollment Type")
        enrollment_types = df['enrollment_type'].unique()
        aid_by_enrollment = []
        for et in enrollment_types:
            edf = df[df['enrollment_type'] == et]
            ts  = len(edf)
            ads = len(edf[edf['financial_aid_monetary_amount'] > 0])
            ta  = edf['financial_aid_monetary_amount'].sum()
            aa  = edf[edf['financial_aid_monetary_amount'] > 0]['financial_aid_monetary_amount'].mean() if ads > 0 else 0
            aid_by_enrollment.append({'Enrollment Type': et, 'Total Students': ts,
                                       'Aided Students': ads, 'Aid %': (ads / ts * 100) if ts > 0 else 0,
                                       'Total Aid (AED)': ta, 'Avg Aid (AED)': aa})
        aid_enrollment_df = pd.DataFrame(aid_by_enrollment)

        fig_enroll = go.Figure()
        fig_enroll.add_trace(go.Bar(
            name='Aided Students', x=aid_enrollment_df['Enrollment Type'],
            y=aid_enrollment_df['Aided Students'],
            marker=dict(color='#10b981', line=dict(color='white', width=2)),
            text=aid_enrollment_df['Aided Students'], textposition='inside',
            textfont=dict(size=11, color='white', family='Arial Black'),
            customdata=aid_enrollment_df['Total Aid (AED)'],
            hovertemplate='<b>%{x}</b><br>Aided: %{y:,}<br>Total Aid: AED %{customdata:,.0f}<extra></extra>'
        ))
        fig_enroll.add_trace(go.Bar(
            name='Self-Funded', x=aid_enrollment_df['Enrollment Type'],
            y=aid_enrollment_df['Total Students'] - aid_enrollment_df['Aided Students'],
            marker=dict(color='#94a3b8', line=dict(color='white', width=2)),
            text=aid_enrollment_df['Total Students'] - aid_enrollment_df['Aided Students'],
            textposition='inside', textfont=dict(size=11, color='white', family='Arial Black'),
            hovertemplate='<b>%{x}</b><br>Self-Funded: %{y:,}<extra></extra>'
        ))
        fig_enroll.update_layout(
            title=dict(text="Financial Aid Coverage by Enrollment Type",
                       font=dict(size=18, color='white', family='Arial Black'), x=0.5, xanchor='center'),
            xaxis=dict(title='', tickfont=dict(size=11, color='white'), showgrid=False),
            yaxis=dict(title='Number of Students', title_font=dict(size=12, color='white'),
                       tickfont=dict(size=11, color='white'), gridcolor='rgba(255,255,255,0.1)'),
            barmode='stack',
            legend=dict(font=dict(size=11, color='white'), orientation='h',
                        yanchor='bottom', y=-0.2, xanchor='center', x=0.5),
            paper_bgcolor='rgba(30,41,59,0.85)', plot_bgcolor='rgba(0,0,0,0)',
            height=400, margin=dict(l=60, r=20, t=80, b=100))
        st.plotly_chart(fig_enroll, use_container_width=True, key="pc_6271")

    st.markdown("""
<div style='background:linear-gradient(135deg,rgba(99,102,241,0.1),rgba(79,70,229,0.1));
            padding:1.2rem;border-radius:8px;border-left:4px solid #6366f1;margin-top:1rem;'>
    <div style='color:#6366f1;font-weight:600;font-size:1rem;margin-bottom:0.5rem;'>💼 Business Impact: Financial Aid ROI</div>
    <div style='color:white;font-size:0.95rem;line-height:1.7;'>
    <strong>Financial aid is both a revenue strategy and mission driver.</strong> Each dollar invested prevents attrition
    (saving ~AED 5-10K in replacement recruitment costs), improves graduation rates, and fulfils social responsibility.
    <strong>ROI calculation:</strong> Retention improvement of 5-10% from aid = ~AED 2-4M saved annually in recruitment.
    Optimal allocation: 25-40% of students receiving 20-35% of tuition, targeting high-need, high-potential students.
    </div>
</div>
""", unsafe_allow_html=True)

    _cov_range  = "aligns with" if 25 <= aid_recipient_pct <= 40 else "needs adjustment for"
    _pkg_range  = "aligns with" if 15000 <= avg_aid_amount <= 50000 else "exceeds"
    _rec_label  = "Maintain" if 25 <= aid_recipient_pct <= 40 else "Optimise"
    st.markdown(f"""
<div style='background:linear-gradient(135deg,rgba(16,185,129,0.15),rgba(5,150,105,0.15));
            padding:1.5rem;border-radius:10px;border:2px solid #10b981;margin:1.5rem 0;'>
    <div style='color:#10b981;font-weight:700;font-size:1.2rem;margin-bottom:1rem;'>📋 STORY 2.1 FINDINGS</div>
    <div style='color:white;font-size:0.95rem;line-height:1.8;'>
    <strong>Investment Summary:</strong><br/>
    &bull; Total aid: AED {total_aid_invested/1e6:.2f}M across {students_with_aid} recipients<br/>
    &bull; Coverage rate: {aid_recipient_pct:.1f}% of total student population<br/>
    &bull; Average package: AED {avg_aid_amount:,.0f} per aided student<br/>
    &bull; Investment per student: AED {avg_aid_per_all:,.0f} (all-student average)<br/><br/>
    <strong>Business Implications:</strong><br/>
    &bull; Coverage {_cov_range} optimal range (25-40% of students)<br/>
    &bull; Package size {_pkg_range} sustainable levels (AED 15K-50K average)<br/>
    &bull; Recommendation: {_rec_label} aid allocation for maximum impact
    </div>
</div>
""", unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════════
    # STORY 2.2: AID EFFECTIVENESS & STUDENT OUTCOMES
    # ═══════════════════════════════════════════════════════════════
    st.markdown("---")
    st.markdown("## 📈 Story 2.2: Aid Effectiveness & Student Outcomes")
    st.markdown("*Measuring the impact of financial support on academic performance and retention*")

    if not _has_gpa:
        st.info("cumulative_gpa column not found — Story 2.2 unavailable.")
    else:
        aided_students     = df[df['financial_aid_monetary_amount'] > 0].copy()
        non_aided_students = df[df['financial_aid_monetary_amount'] == 0].copy()

        aided_gpa     = aided_students['cumulative_gpa'].mean()     if len(aided_students) > 0     else 0
        non_aided_gpa = non_aided_students['cumulative_gpa'].mean() if len(non_aided_students) > 0 else 0
        gpa_diff      = aided_gpa - non_aided_gpa
        aided_success = (len(aided_students[aided_students['cumulative_gpa'] >= 3.0]) / len(aided_students) * 100) if len(aided_students) > 0 else 0

        st.markdown("#### 🎯 Performance Comparison")
        c1, c2, c3 = st.columns(3)
        c1.metric("📊 Aided GPA",    f"{aided_gpa:.2f}",     delta=f"{gpa_diff:+.2f} vs non-aided")
        c2.metric("📊 Non-Aided GPA", f"{non_aided_gpa:.2f}")
        c3.metric("✅ Success Rate",  f"{aided_success:.1f}%", delta="GPA ≥3.0")

        st.markdown("#### 📊 Academic Performance: Aided vs Non-Aided Analysis")
        col1, col2 = st.columns(2)

        with col1:
            gpa_comp = pd.DataFrame({
                'Student Group': ['Aided Students', 'Non-Aided Students'],
                'Average GPA':   [aided_gpa, non_aided_gpa],
                'Color':         ['#10b981', '#94a3b8']
            })
            fig_gpa_comp = go.Figure()
            fig_gpa_comp.add_trace(go.Bar(
                x=gpa_comp['Student Group'], y=gpa_comp['Average GPA'],
                marker=dict(color=gpa_comp['Color'], line=dict(color='white', width=2)),
                text=[f"{g:.2f}" for g in gpa_comp['Average GPA']],
                textposition='outside', textfont=dict(size=14, color='white', family='Arial Black'),
                hovertemplate='<b>%{x}</b><br>Avg GPA: %{y:.2f}<extra></extra>'
            ))
            ann_color = '#10b981' if gpa_diff >= 0 else '#ef4444'
            fig_gpa_comp.add_annotation(
                x=0.5, y=max(aided_gpa, non_aided_gpa) + 0.15,
                text=f"Difference: {gpa_diff:+.2f} points",
                showarrow=False,
                font=dict(size=12, color=ann_color, family='Arial Black'),
                bgcolor=f'rgba(16,185,129,0.2)' if gpa_diff >= 0 else 'rgba(239,68,68,0.2)',
                bordercolor=ann_color, borderwidth=2, borderpad=4
            )
            fig_gpa_comp.update_layout(
                title=dict(text="GPA Comparison: Aided vs Non-Aided",
                           font=dict(size=18, color='white', family='Arial Black'), x=0.5, xanchor='center'),
                xaxis=dict(title='', tickfont=dict(size=11, color='white'), showgrid=False),
                yaxis=dict(title='Cumulative GPA', title_font=dict(size=12, color='white'),
                           tickfont=dict(size=11, color='white'),
                           gridcolor='rgba(255,255,255,0.1)', range=[0, 4.0]),
                showlegend=False, paper_bgcolor='rgba(30,41,59,0.85)', plot_bgcolor='rgba(0,0,0,0)',
                height=400, margin=dict(l=60, r=20, t=80, b=80))
            st.plotly_chart(fig_gpa_comp, use_container_width=True, key="pc_6366")

        with col2:
            perf_cats = ['High (3.5+)', 'Good (3.0-3.5)', 'Average (2.5-3.0)', 'Low (<2.5)']
            aided_high  = len(aided_students[aided_students['cumulative_gpa'] >= 3.5])
            aided_good  = len(aided_students[(aided_students['cumulative_gpa'] >= 3.0) & (aided_students['cumulative_gpa'] < 3.5)])
            aided_avg   = len(aided_students[(aided_students['cumulative_gpa'] >= 2.5) & (aided_students['cumulative_gpa'] < 3.0)])
            aided_low   = len(aided_students[aided_students['cumulative_gpa'] < 2.5])
            na_high  = len(non_aided_students[non_aided_students['cumulative_gpa'] >= 3.5])
            na_good  = len(non_aided_students[(non_aided_students['cumulative_gpa'] >= 3.0) & (non_aided_students['cumulative_gpa'] < 3.5)])
            na_avg   = len(non_aided_students[(non_aided_students['cumulative_gpa'] >= 2.5) & (non_aided_students['cumulative_gpa'] < 3.0)])
            na_low   = len(non_aided_students[non_aided_students['cumulative_gpa'] < 2.5])

            fig_perf_dist = go.Figure()
            fig_perf_dist.add_trace(go.Bar(
                name='Aided Students', x=perf_cats,
                y=[aided_high, aided_good, aided_avg, aided_low],
                marker=dict(color='#10b981', line=dict(color='white', width=2)),
                text=[aided_high, aided_good, aided_avg, aided_low],
                textposition='outside', textfont=dict(size=11, color='white', family='Arial Black'),
                hovertemplate='<b>Aided Students</b><br>%{x}<br>Students: %{y}<extra></extra>'
            ))
            fig_perf_dist.add_trace(go.Bar(
                name='Non-Aided Students', x=perf_cats,
                y=[na_high, na_good, na_avg, na_low],
                marker=dict(color='#94a3b8', line=dict(color='white', width=2)),
                text=[na_high, na_good, na_avg, na_low],
                textposition='outside', textfont=dict(size=11, color='white', family='Arial Black'),
                hovertemplate='<b>Non-Aided</b><br>%{x}<br>Students: %{y}<extra></extra>'
            ))
            fig_perf_dist.update_layout(
                title=dict(text="Performance Distribution by Aid Status",
                           font=dict(size=18, color='white', family='Arial Black'), x=0.5, xanchor='center'),
                xaxis=dict(title='', tickfont=dict(size=10, color='white'), showgrid=False),
                yaxis=dict(title='Number of Students', title_font=dict(size=12, color='white'),
                           tickfont=dict(size=11, color='white'), gridcolor='rgba(255,255,255,0.1)'),
                barmode='group',
                legend=dict(font=dict(size=11, color='white'), orientation='h',
                            yanchor='bottom', y=-0.25, xanchor='center', x=0.5),
                paper_bgcolor='rgba(30,41,59,0.85)', plot_bgcolor='rgba(0,0,0,0)',
                height=400, margin=dict(l=60, r=20, t=80, b=100))
            st.plotly_chart(fig_perf_dist, use_container_width=True, key="pc_6407")

        # Dynamic retention metrics from actual enrollment status
        _perf_label2 = "comparable" if abs(gpa_diff) < 0.1 else "improved"
        _gpa_direction = "higher than" if gpa_diff > 0.1 else "comparable to" if abs(gpa_diff) <= 0.1 else "lower than"
        _ret_est     = int(students_with_aid * 0.1)
        # Use actual tuition per student if available for ROI calc
        _tuition_per_student_22 = (actual_tuition_j2 / max(len(df), 1)) if actual_tuition_j2 > 0 else 25000
        _retention_value = max(_tuition_per_student_22, 7500)  # at least recruitment cost
        _ret_saved   = students_with_aid * 0.1 * _retention_value / 1000
        _roi_saved22 = students_with_aid * 0.075 * _retention_value / 1000

        # Actual active rates if status available
        if _has_status:
            _aided_active22    = int((df[(df['financial_aid_monetary_amount'] > 0) & (df['enrollment_enrollment_status'] == 'Active')].shape[0]))
            _aided_active_pct22 = (_aided_active22 / max(students_with_aid, 1) * 100)
            _non_aided_active22 = int((df[(df['financial_aid_monetary_amount'] == 0) & (df['enrollment_enrollment_status'] == 'Active')].shape[0]))
            _non_aided_active_pct22 = (_non_aided_active22 / max(students_without_aid, 1) * 100)
            _ret_advantage22   = _aided_active_pct22 - _non_aided_active_pct22
            _ret_str22 = f"aided active rate {_aided_active_pct22:.1f}% vs non-aided {_non_aided_active_pct22:.1f}% ({_ret_advantage22:+.1f} pp)"
        else:
            _ret_str22 = "enrollment status data not available — upload enrollment_enrollment_status for retention metrics"
            _ret_advantage22 = 0

        st.markdown(f"""
<div style='background:linear-gradient(135deg,rgba(99,102,241,0.1),rgba(79,70,229,0.1));
            padding:1.2rem;border-radius:8px;border-left:4px solid #6366f1;margin-top:1rem;'>
    <div style='color:#6366f1;font-weight:600;font-size:1rem;'>💼 Business Impact: Retention Economics</div>
    <div style='color:white;font-size:0.95rem;line-height:1.7;'>
    Financial aid directly impacts retention rates. Aided students ({students_with_aid:,}) show GPA of <strong>{aided_gpa:.2f}</strong>,
    {_gpa_direction} non-aided students ({non_aided_gpa:.2f}), validating the investment strategy.
    Retention: {_ret_str22}.
    <strong>Cost-benefit:</strong> Using AED {_retention_value:,.0f} value per retained student,
    preventing {_ret_est} dropouts = AED {_ret_saved:,.0f}K saved annually in recruitment and onboarding costs alone.
    </div>
</div>
""", unsafe_allow_html=True)

        _match_label = "matches" if abs(gpa_diff) < 0.1 else ("exceeds" if gpa_diff > 0 else "below")
        _out_label   = "maintains" if abs(gpa_diff) < 0.1 else ("improves" if gpa_diff > 0 else "requires attention for")
        st.markdown(f"""
<div style='background:linear-gradient(135deg,rgba(16,185,129,0.15),rgba(5,150,105,0.15));
            padding:1.5rem;border-radius:10px;border:2px solid #10b981;margin:1.5rem 0;'>
    <div style='color:#10b981;font-weight:700;font-size:1.2rem;margin-bottom:1rem;'>📋 STORY 2.2 FINDINGS</div>
    <div style='color:white;font-size:0.95rem;line-height:1.8;'>
    <strong>Performance Outcomes (from {len(df):,} records):</strong><br/>
    &bull; Aided GPA: {aided_gpa:.2f} | Non-Aided GPA: {non_aided_gpa:.2f} (aid {_match_label} non-aided)<br/>
    &bull; GPA difference: {gpa_diff:+.3f} points<br/>
    &bull; Success rate (GPA &ge;3.0): {aided_success:.1f}% of aided students ({int(aided_success/100*students_with_aid):,} students)<br/><br/>
    <strong>Retention &amp; Sustainability:</strong><br/>
    &bull; {_ret_str22}<br/>
    &bull; ROI basis: AED {_retention_value:,.0f} per retained student ({"actual avg tuition" if actual_tuition_j2 > 0 else "default value — add tuition data"})<br/>
    &bull; Estimated 7.5% retention improvement = AED {_roi_saved22:,.0f}K saved<br/><br/>
    <strong>Business Implications:</strong><br/>
    &bull; Aid {_out_label} academic outcomes, validating strategy<br/>
    &bull; Recommendation: Maintain current aid levels with targeted distribution
    </div>
</div>
""", unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════════
    # STORY 2.3: REVENUE SUSTAINABILITY & BUDGET OPTIMISATION
    # ═══════════════════════════════════════════════════════════════
    st.markdown("---")
    st.markdown("## 💹 Story 2.3: Revenue Sustainability & Budget Optimisation")
    st.markdown("*Long-term financial sustainability and strategic budget allocation*")

    # ── Dynamic tuition revenue from actual data ──
    _has_tuition_23 = 'enrollment_tuition_amount' in df.columns
    _has_fee_paid   = 'total_payments_ytd' in df.columns or 'fee_paid' in df.columns  # catalog: total_payments_ytd
    _has_rent_paid  = 'rent_paid' in df.columns  # legacy only
    _has_balance    = 'past_due_balance' in df.columns or 'balance_due' in df.columns  # catalog: past_due_balance

    if _has_tuition_23:
        actual_total_tuition = df['enrollment_tuition_amount'].sum()
        _tuition_source = "actual tuition data"
        _tuition_note   = f"AED {actual_total_tuition/1e6:.2f}M from enrollment_tuition_amount column"
    else:
        actual_total_tuition = 0
        _tuition_source = "no tuition data available"
        _tuition_note   = "Upload a dataset with enrollment_tuition_amount for revenue-based metrics"

    # Additional revenue streams — use catalog canonical columns
    if 'total_payments_ytd' in df.columns:
        actual_fee_revenue = pd.to_numeric(df['total_payments_ytd'], errors='coerce').sum()
    elif 'fee_paid' in df.columns:
        actual_fee_revenue = pd.to_numeric(df['fee_paid'], errors='coerce').sum()
    else:
        actual_fee_revenue = 0
    actual_rent_revenue = pd.to_numeric(df['rent_paid'], errors='coerce').sum() if 'rent_paid' in df.columns else 0
    total_gross_revenue = actual_total_tuition + actual_fee_revenue + actual_rent_revenue
    # Outstanding balance — catalog canonical past_due_balance
    if 'past_due_balance' in df.columns:
        actual_balance_due = pd.to_numeric(df['past_due_balance'], errors='coerce').sum()
    elif 'balance_due' in df.columns:
        actual_balance_due = pd.to_numeric(df['balance_due'], errors='coerce').sum()
    else:
        actual_balance_due = 0

    # Aid sustainability metrics — use actual tuition if available
    if actual_total_tuition > 0:
        aid_as_pct_revenue  = total_aid_invested / actual_total_tuition * 100
        aid_as_pct_gross    = total_aid_invested / total_gross_revenue * 100 if total_gross_revenue > 0 else 0
        net_revenue         = actual_total_tuition - total_aid_invested
        _revenue_basis      = "actual tuition"
    else:
        aid_as_pct_revenue  = 0
        aid_as_pct_gross    = 0
        net_revenue         = 0
        _revenue_basis      = "unavailable"

    if actual_total_tuition == 0:
        st.warning(
            "enrollment_tuition_amount column not found — revenue sustainability metrics require tuition data. "
            "Aid budget metrics are still shown below based on available aid data."
        )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("💰 Aid Budget",      f"AED {total_aid_invested/1e6:.2f}M")
    c2.metric("💵 Tuition Revenue",
              f"AED {actual_total_tuition/1e6:.2f}M" if actual_total_tuition > 0 else "N/A",
              help=_tuition_note)
    if actual_total_tuition > 0:
        c3.metric("📊 Aid % of Revenue", f"{aid_as_pct_revenue:.1f}%",
                  delta="Optimal" if 15 <= aid_as_pct_revenue <= 35 else "Review needed",
                  help="Aid as % of actual tuition revenue")
        optimal_range_label = "✅ Optimal" if 15 <= aid_as_pct_revenue <= 35 else "⚠️ Review"
        c4.metric("🎯 Sustainability", optimal_range_label,
                  delta=f"Net AED {net_revenue/1e6:.1f}M" if net_revenue != 0 else None)
    else:
        c3.metric("📊 Aid % of Revenue", "N/A", help="Requires tuition data")
        optimal_range_label = "N/A"
        c4.metric("🎯 Sustainability", "No tuition data")

    st.markdown("#### 📊 Budget Sustainability & Strategic Allocation")
    col1, col2 = st.columns(2)

    with col1:
        if actual_total_tuition > 0:
            fig_gauge = go.Figure()
            fig_gauge.add_trace(go.Indicator(
                mode="gauge+number+delta",
                value=aid_as_pct_revenue,
                domain={'x': [0, 1], 'y': [0, 1]},
                title={'text': "Aid Budget as % of Tuition Revenue",
                       'font': {'size': 16, 'color': 'white', 'family': 'Arial Black'}},
                delta={'reference': 25, 'suffix': '%', 'font': {'size': 12, 'color': 'white'}},
                number={'suffix': '%', 'font': {'size': 28, 'color': 'white', 'family': 'Arial Black'}},
                gauge={
                    'axis': {'range': [0, 50], 'tickwidth': 2, 'tickcolor': 'white',
                             'tickfont': {'color': 'white', 'size': 10}},
                    'bar': {'color': '#6366f1', 'thickness': 0.75},
                    'bgcolor': 'rgba(50,50,50,0.5)',
                    'borderwidth': 2, 'bordercolor': 'white',
                    'steps': [
                        {'range': [0, 15],  'color': 'rgba(239,68,68,0.3)'},
                        {'range': [15, 35], 'color': 'rgba(16,185,129,0.3)'},
                        {'range': [35, 50], 'color': 'rgba(245,158,11,0.3)'}
                    ],
                    'threshold': {'line': {'color': 'white', 'width': 4}, 'thickness': 0.75, 'value': 25}
                }
            ))
            fig_gauge.update_layout(
                paper_bgcolor='rgba(30,41,59,0.85)', font={'color': 'white', 'family': 'Arial'},
                height=400, margin=dict(l=20, r=20, t=80, b=20))
            fig_gauge.add_annotation(
                text=f"<b>Actual Tuition Revenue: AED {actual_total_tuition/1e6:.2f}M</b><br>Target Range: 15-35% | Green zone = sustainable allocation",
                xref="paper", yref="paper", x=0.5, y=-0.05,
                showarrow=False, font=dict(size=11, color='#10b981'), xanchor='center')
            st.plotly_chart(fig_gauge, use_container_width=True, key="pc_6565")
        else:
            # Show aid-only gauge when no tuition data
            fig_gauge = go.Figure()
            fig_gauge.add_trace(go.Indicator(
                mode="number+delta",
                value=total_aid_invested / 1e6,
                title={'text': "Total Aid Budget (AED M)", 'font': {'size': 16, 'color': 'white'}},
                number={'suffix': "M AED", 'font': {'size': 28, 'color': 'white', 'family': 'Arial Black'}},
                delta={'reference': total_aid_invested / 1e6 * 0.9, 'font': {'size': 12, 'color': 'white'}}
            ))
            fig_gauge.update_layout(
                paper_bgcolor='rgba(30,41,59,0.85)', font={'color': 'white', 'family': 'Arial'},
                height=400, margin=dict(l=20, r=20, t=80, b=20))
            fig_gauge.add_annotation(
                text="<b>Add enrollment_tuition_amount column to enable % of Revenue gauge</b>",
                xref="paper", yref="paper", x=0.5, y=-0.05,
                showarrow=False, font=dict(size=11, color='#f59e0b'), xanchor='center')
            st.plotly_chart(fig_gauge, use_container_width=True, key="pc_6583")

    with col2:
        if actual_total_tuition > 0:
            # Build waterfall from real revenue columns
            _wf_categories = ['Tuition Revenue']
            _wf_amounts    = [actual_total_tuition / 1e6]
            _wf_colors     = ['#10b981']
            if actual_fee_revenue > 0:
                _wf_categories.append('Fee Revenue')
                _wf_amounts.append(actual_fee_revenue / 1e6)
                _wf_colors.append('#3b82f6')
            if actual_rent_revenue > 0:
                _wf_categories.append('Rent Revenue')
                _wf_amounts.append(actual_rent_revenue / 1e6)
                _wf_colors.append('#8b5cf6')
            _wf_categories.append('Aid Budget')
            _wf_amounts.append(-(total_aid_invested / 1e6))
            _wf_colors.append('#ef4444')
            _wf_categories.append('Net Revenue')
            _wf_amounts.append((total_gross_revenue - total_aid_invested) / 1e6)
            _wf_colors.append('#f59e0b')

            fig_waterfall = go.Figure()
            fig_waterfall.add_trace(go.Bar(
                x=_wf_categories, y=_wf_amounts,
                marker=dict(color=_wf_colors, line=dict(color='white', width=2)),
                text=[f"AED {abs(a):.1f}M" for a in _wf_amounts],
                textposition='outside', textfont=dict(size=12, color='white', family='Arial Black'),
                hovertemplate='<b>%{x}</b><br>Amount: AED %{y:.2f}M<extra></extra>'
            ))
            fig_waterfall.add_annotation(
                x='Aid Budget', y=-(total_aid_invested / 1e6) - 0.5,
                text=f"{aid_as_pct_revenue:.1f}% of Tuition",
                showarrow=True, arrowhead=2, arrowcolor='#6366f1', ax=0, ay=-30,
                font=dict(size=11, color='#6366f1', family='Arial Black'),
                bgcolor='rgba(99,102,241,0.2)', bordercolor='#6366f1', borderwidth=2, borderpad=4)
            fig_waterfall.update_layout(
                title=dict(text="Revenue Streams & Aid Budget (Actual Data)",
                           font=dict(size=18, color='white', family='Arial Black'), x=0.5, xanchor='center'),
                xaxis=dict(title='', tickfont=dict(size=10, color='white'), showgrid=False),
                yaxis=dict(title='Amount (AED Millions)', title_font=dict(size=12, color='white'),
                           tickfont=dict(size=11, color='white'), gridcolor='rgba(255,255,255,0.1)'),
                showlegend=False, paper_bgcolor='rgba(30,41,59,0.85)', plot_bgcolor='rgba(0,0,0,0)',
                height=400, margin=dict(l=60, r=20, t=80, b=80))
            st.plotly_chart(fig_waterfall, use_container_width=True, key="pc_6628")
        else:
            # Show aid-only breakdown when no tuition
            _avg_aid_safe2 = avg_aid_amount if avg_aid_amount and avg_aid_amount > 0 else 1
            _aid_low_tier  = len(df[(df['financial_aid_monetary_amount'] > 0)  & (df['financial_aid_monetary_amount'] < 10000)])
            _aid_mid_tier  = len(df[(df['financial_aid_monetary_amount'] >= 10000) & (df['financial_aid_monetary_amount'] < 30000)])
            _aid_high_tier = len(df[df['financial_aid_monetary_amount'] >= 30000])
            fig_aid_breakdown = go.Figure(data=[go.Bar(
                x=['Low Tier\n(<10K)', 'Mid Tier\n(10-30K)', 'High Tier\n(30K+)'],
                y=[_aid_low_tier, _aid_mid_tier, _aid_high_tier],
                marker=dict(color=['#6366f1', '#10b981', '#f59e0b'], line=dict(color='white', width=2)),
                text=[str(_aid_low_tier), str(_aid_mid_tier), str(_aid_high_tier)],
                textposition='outside', textfont=dict(size=14, color='white', family='Arial Black'),
                hovertemplate='<b>%{x}</b><br>Students: %{y}<extra></extra>'
            )])
            fig_aid_breakdown.update_layout(
                title=dict(text="Aid Tier Distribution (No Tuition Data)",
                           font=dict(size=18, color='white', family='Arial Black'), x=0.5, xanchor='center'),
                xaxis=dict(title='', tickfont=dict(size=11, color='white'), showgrid=False),
                yaxis=dict(title='Students', tickfont=dict(size=11, color='white'), gridcolor='rgba(255,255,255,0.1)'),
                showlegend=False, paper_bgcolor='rgba(30,41,59,0.85)', plot_bgcolor='rgba(0,0,0,0)',
                height=400, margin=dict(l=60, r=20, t=80, b=80))
            st.plotly_chart(fig_aid_breakdown, use_container_width=True, key="pc_6650")

    st.markdown("#### 💹 Sustainability Scenarios & Projections")
    if actual_total_tuition > 0:
        # Scenario analysis based on actual tuition revenue
        scenarios        = ['Current', 'Conservative\n(20% Aid)', 'Optimal\n(25% Aid)', 'Aggressive\n(30% Aid)']
        aid_pcts         = [aid_as_pct_revenue, 20, 25, 30]
        aid_budgets_sc   = [actual_total_tuition * p / 100 / 1e6 for p in aid_pcts]
        _avg_aid_safe    = avg_aid_amount if avg_aid_amount and avg_aid_amount > 0 else 1
        students_aided_s = [actual_total_tuition * p / 100 / _avg_aid_safe for p in aid_pcts]
        retention_imp    = [p * 0.3 for p in aid_pcts]
        net_benefit      = [(ri * len(df) * 7.5 - (aid_budgets_sc[i] * 1e6 - total_aid_invested)) / 1000
                            for i, ri in enumerate(retention_imp)]

        fig_scenarios = go.Figure()
        fig_scenarios.add_trace(go.Bar(
            name='Aid Budget (AED M)', x=scenarios, y=aid_budgets_sc,
            marker=dict(color='#6366f1', line=dict(color='white', width=2)),
            text=[f"AED {a:.1f}M" for a in aid_budgets_sc], textposition='outside',
            textfont=dict(size=10, color='white', family='Arial Black'),
            yaxis='y', hovertemplate='<b>%{x}</b><br>Aid Budget: AED %{y:.1f}M<extra></extra>'
        ))
        fig_scenarios.add_trace(go.Scatter(
            name='Net Benefit (AED K)', x=scenarios, y=net_benefit,
            mode='lines+markers',
            line=dict(color='#10b981', width=3),
            marker=dict(size=10, color='#10b981', line=dict(color='white', width=2)),
            yaxis='y2', hovertemplate='<b>%{x}</b><br>Net Benefit: AED %{y:.0f}K<extra></extra>'
        ))
        fig_scenarios.update_layout(
            title=dict(text=f"Aid Budget Scenarios vs Actual Revenue AED {actual_total_tuition/1e6:.1f}M",
                       font=dict(size=18, color='white', family='Arial Black'), x=0.5, xanchor='center'),
            xaxis=dict(title='', tickfont=dict(size=10, color='white'), showgrid=False),
            yaxis=dict(title='Aid Budget (AED M)', title_font=dict(size=12, color='#6366f1'),
                       tickfont=dict(size=11, color='white'), gridcolor='rgba(255,255,255,0.1)'),
            yaxis2=dict(title='Net Benefit (AED K)', title_font=dict(size=12, color='#10b981'),
                        tickfont=dict(size=11, color='white'), overlaying='y', side='right'),
            legend=dict(font=dict(size=11, color='white'), orientation='h',
                        yanchor='bottom', y=-0.25, xanchor='center', x=0.5),
            paper_bgcolor='rgba(30,41,59,0.85)', plot_bgcolor='rgba(0,0,0,0)',
            height=400, margin=dict(l=60, r=60, t=80, b=100))
        st.plotly_chart(fig_scenarios, use_container_width=True, key="pc_6691")
    else:
        # Without tuition data — show aid-per-student scenarios
        _base_aid = avg_aid_amount if avg_aid_amount > 0 else total_aid_invested / max(students_with_aid, 1)
        scen_labels  = ['Current Avg', '-10% Pkg', '+10% Pkg', '+25% Pkg']
        scen_pkgs    = [_base_aid, _base_aid * 0.9, _base_aid * 1.1, _base_aid * 1.25]
        scen_budgets = [p * students_with_aid / 1e6 for p in scen_pkgs]
        fig_scenarios = go.Figure(data=[go.Bar(
            x=scen_labels, y=scen_budgets,
            marker=dict(color=['#6366f1', '#10b981', '#f59e0b', '#ef4444'], line=dict(color='white', width=2)),
            text=[f"AED {b:.1f}M" for b in scen_budgets], textposition='outside',
            textfont=dict(size=11, color='white', family='Arial Black'),
            hovertemplate='<b>%{x}</b><br>Total Budget: AED %{y:.1f}M<extra></extra>'
        )])
        fig_scenarios.update_layout(
            title=dict(text="Aid Package Scenarios (No Tuition Data Available)",
                       font=dict(size=18, color='white', family='Arial Black'), x=0.5, xanchor='center'),
            xaxis=dict(title='', tickfont=dict(size=11, color='white'), showgrid=False),
            yaxis=dict(title='Total Aid Budget (AED M)', title_font=dict(size=12, color='white'),
                       tickfont=dict(size=11, color='white'), gridcolor='rgba(255,255,255,0.1)'),
            showlegend=False, paper_bgcolor='rgba(30,41,59,0.85)', plot_bgcolor='rgba(0,0,0,0)',
            height=400, margin=dict(l=60, r=20, t=80, b=80))
        st.plotly_chart(fig_scenarios, use_container_width=True, key="pc_6713")
        st.info("Add enrollment_tuition_amount column to unlock full revenue sustainability scenario analysis.")

    # ── Business Impact & Findings ──
    _in_range    = 15 <= aid_as_pct_revenue <= 35 if actual_total_tuition > 0 else None
    _range_label = ("within" if _in_range else "outside") if _in_range is not None else "N/A (no tuition data)"
    _health_lbl  = ("Strong" if _in_range else "Requires adjustment") if _in_range is not None else "Indeterminate — upload tuition data"
    _maint_lbl   = ("Maintain" if _in_range else "Adjust") if _in_range is not None else "Evaluate after adding tuition data"
    _reserve_k   = total_aid_invested * 0.05 / 1000
    _rec_dir     = ("Maintain" if _in_range else ("Reduce" if aid_as_pct_revenue > 35 else "Increase")) if _in_range is not None else "Evaluate"
    _adj_pct     = abs(25 - aid_as_pct_revenue) if (_in_range is not None and not _in_range) else 0
    _revenue_str = f"AED {actual_total_tuition/1e6:.2f}M ({_tuition_source})" if actual_total_tuition > 0 else "Not available — upload enrollment_tuition_amount column"
    _pct_str     = f"{aid_as_pct_revenue:.1f}% of actual tuition revenue" if actual_total_tuition > 0 else "N/A (no tuition data)"

    st.markdown(f"""
<div style='background:linear-gradient(135deg,rgba(99,102,241,0.1),rgba(79,70,229,0.1));
            padding:1.2rem;border-radius:8px;border-left:4px solid #6366f1;margin-top:1rem;'>
    <div style='color:#6366f1;font-weight:600;font-size:1rem;'>💼 Business Impact: Fiscal Sustainability</div>
    <div style='color:white;font-size:0.95rem;line-height:1.7;'>
    <strong>Financial aid must balance access with sustainability.</strong> Industry benchmark: 15-35% of tuition
    revenue allocated to aid. Current allocation: {_pct_str}. <strong>Strategic recommendations:</strong> Monitor aid ROI
    quarterly, adjust packages based on retention data, maintain emergency aid reserve (5% of budget = AED {_reserve_k:,.0f}K),
    and prioritise aid for high-potential, high-need students to maximise both mission impact and financial sustainability.
    </div>
</div>
""", unsafe_allow_html=True)

    st.markdown(f"""
<div style='background:linear-gradient(135deg,rgba(16,185,129,0.15),rgba(5,150,105,0.15));
            padding:1.5rem;border-radius:10px;border:2px solid #10b981;margin:1.5rem 0;'>
    <div style='color:#10b981;font-weight:700;font-size:1.2rem;margin-bottom:1rem;'>📋 STORY 2.3 FINDINGS</div>
    <div style='color:white;font-size:0.95rem;line-height:1.8;'>
    <strong>Sustainability Metrics:</strong><br/>
    &bull; Aid budget: AED {total_aid_invested/1e6:.2f}M ({_pct_str})<br/>
    &bull; Tuition revenue: {_revenue_str}<br/>
    &bull; Industry benchmark: 15-35% of tuition revenue<br/>
    &bull; Current status: {_range_label} target range<br/>
    &bull; Financial health: {_health_lbl} for long-term sustainability<br/><br/>
    <strong>Business Implications:</strong><br/>
    &bull; {_maint_lbl} current aid allocation strategy<br/>
    &bull; Implement quarterly ROI monitoring for aid effectiveness<br/>
    &bull; Maintain 5% emergency aid reserve (AED {_reserve_k:,.0f}K)<br/>
    &bull; Recommendation: {_rec_dir} aid budget by {_adj_pct:.1f}% to reach optimal range
    </div>
</div>
""", unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════════
    # STORY 2.4: ADVANCED FINANCIAL ANALYTICS
    # ═══════════════════════════════════════════════════════════════
    st.markdown("---")
    st.markdown("## 💎 Story 2.4: Advanced Financial Analytics & Payment Intelligence")
    st.markdown("*Deep dive into scholarship programmes, sponsorships, and collections*")

    # ── Scholarship Programme Effectiveness ──
    if 'scholarship_type' in df.columns:
        st.markdown("### 🏆 Scholarship Programme Performance Analysis")
        col1, col2 = st.columns(2)

        with col1:
            _agg = {'student_id': 'count', 'cumulative_gpa': 'mean'} if _has_gpa else {'student_id': 'count'}
            if 'scholarship_amount' in df.columns:
                _agg['scholarship_amount'] = 'sum'
            sch_analysis = df[df['scholarship_type'].notna()].groupby('scholarship_type').agg(_agg).reset_index()
            _cols = ['Scholarship Type', 'Students']
            if _has_gpa:
                _cols.append('Avg GPA')
            if 'scholarship_amount' in df.columns:
                _cols.append('Total Amount')
            sch_analysis.columns = _cols

            if 'scholarship_amount' in df.columns and 'Total Amount' in sch_analysis.columns:
                sch_analysis['Amount (AED M)'] = sch_analysis['Total Amount'] / 1e6
                fig = go.Figure()
                fig.add_trace(go.Bar(
                    name='Total Amount (AED M)', x=sch_analysis['Scholarship Type'],
                    y=sch_analysis['Amount (AED M)'],
                    marker=dict(color='#3b82f6', line=dict(color='white', width=2)),
                    text=[f"<b>AED {v:.2f}M</b>" for v in sch_analysis['Amount (AED M)']],
                    textposition='outside', textfont=dict(size=12, color='white', family='Arial Black'),
                    yaxis='y', hovertemplate='<b>%{x}</b><br>Amount: AED %{y:.2f}M<extra></extra>'
                ))
                if _has_gpa and 'Avg GPA' in sch_analysis.columns:
                    fig.add_trace(go.Scatter(
                        name='Avg GPA', x=sch_analysis['Scholarship Type'], y=sch_analysis['Avg GPA'],
                        mode='lines+markers+text',
                        marker=dict(size=12, color='#10b981', line=dict(color='white', width=2)),
                        line=dict(width=3, color='#10b981'),
                        text=[f"<b>{v:.2f}</b>" for v in sch_analysis['Avg GPA']],
                        textposition='top center', textfont=dict(size=12, color='#10b981', family='Arial Black'),
                        yaxis='y2', hovertemplate='<b>%{x}</b><br>Avg GPA: %{y:.2f}<extra></extra>'
                    ))
                fig.update_layout(
                    title=dict(text="Scholarship Investment vs Academic Performance",
                               font=dict(size=18, color='white', family='Arial Black'), x=0.5, xanchor='center'),
                    xaxis=dict(title="Scholarship Type", tickfont=dict(size=11, color='white'), tickangle=-45),
                    yaxis=dict(title="Investment (AED M)", tickfont=dict(size=11, color='white'),
                               gridcolor='rgba(255,255,255,0.2)'),
                    yaxis2=dict(title="Average GPA", tickfont=dict(size=11, color='white'),
                                overlaying='y', side='right', range=[0, 4.0]) if _has_gpa else {},
                    plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(30,41,59,0.85)',
                    font=dict(color='white', size=11), height=450,
                    legend=dict(x=0.5, y=1.15, xanchor='center', orientation='h',
                                font=dict(size=11, color='white'), bgcolor='rgba(0,0,0,0.3)'),
                    margin=dict(l=60, r=60, t=100, b=120))
                st.plotly_chart(fig, use_container_width=True, key="pc_6818")
            else:
                st.info("scholarship_amount column not found — amount chart unavailable.")

        with col2:
            if _has_gpa and 'Avg GPA' in sch_analysis.columns:
                fig = go.Figure(data=[go.Bar(
                    x=sch_analysis['Students'], y=sch_analysis['Scholarship Type'],
                    orientation='h',
                    marker=dict(color=sch_analysis['Avg GPA'], colorscale='RdYlGn',
                                cmin=2.0, cmax=4.0, showscale=True,
                                colorbar=dict(title=dict(text="Avg GPA", font=dict(color="white")),
                                              tickfont=dict(color='white')),
                                line=dict(color='white', width=2)),
                    text=[f"<b>{int(s)}</b> students" for s in sch_analysis['Students']],
                    textposition='outside', textfont=dict(size=12, color='white', family='Arial Black'),
                    hovertemplate='<b>%{y}</b><br>Students: %{x}<extra></extra>'
                )])
            else:
                fig = go.Figure(data=[go.Bar(
                    x=sch_analysis['Students'], y=sch_analysis['Scholarship Type'],
                    orientation='h',
                    marker=dict(color='#6366f1', line=dict(color='white', width=2)),
                    text=[f"<b>{int(s)}</b> students" for s in sch_analysis['Students']],
                    textposition='outside', textfont=dict(size=12, color='white', family='Arial Black')
                )])
            fig.update_layout(
                title=dict(text="Student Enrolment by Scholarship Type",
                           font=dict(size=18, color='white', family='Arial Black'), x=0.5, xanchor='center'),
                xaxis=dict(title="Number of Students", tickfont=dict(size=11, color='white'),
                           gridcolor='rgba(255,255,255,0.2)'),
                yaxis=dict(title="", tickfont=dict(size=11, color='white'), autorange='reversed'),
                plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(30,41,59,0.85)',
                font=dict(color='white', size=11), height=450)
            st.plotly_chart(fig, use_container_width=True, key="pc_6852")

    # ── Sponsorship Programme Analysis ──
    if 'sponsorship_type' in df.columns:
        st.markdown("### 🤝 Sponsorship Programme Impact & Partner Analysis")
        _agg2 = {'student_id': 'count', 'financial_aid_monetary_amount': 'mean'}
        if _has_gpa:
            _agg2['cumulative_gpa'] = 'mean'
        spon_perf = df[df['sponsorship_type'].notna()].groupby('sponsorship_type').agg(_agg2).reset_index()
        _spon_cols = ['Sponsorship Type', 'Students', 'Avg Aid']
        if _has_gpa:
            _spon_cols = ['Sponsorship Type', 'Students', 'Avg GPA', 'Avg Aid']
        spon_perf.columns = _spon_cols

        col1, col2 = st.columns(2)
        with col1:
            fig = make_subplots(specs=[[{"secondary_y": True}]])
            fig.add_trace(go.Bar(
                name='Students Enrolled', x=spon_perf['Sponsorship Type'], y=spon_perf['Students'],
                marker=dict(color='#6366f1', line=dict(color='white', width=2)),
                text=[f"<b>{int(v)}</b>" for v in spon_perf['Students']],
                textposition='outside', textfont=dict(size=12, color='white', family='Arial Black'),
                hovertemplate='<b>%{x}</b><br>Students: %{y}<extra></extra>'
            ), secondary_y=False)
            if _has_gpa and 'Avg GPA' in spon_perf.columns:
                fig.add_trace(go.Scatter(
                    name='Average GPA', x=spon_perf['Sponsorship Type'], y=spon_perf['Avg GPA'],
                    mode='lines+markers',
                    marker=dict(size=12, color='#f59e0b', line=dict(color='white', width=2)),
                    line=dict(width=3, color='#f59e0b'),
                    text=[f"<b>{v:.2f}</b>" for v in spon_perf['Avg GPA']],
                    textposition='top center', textfont=dict(size=12, color='#f59e0b', family='Arial Black'),
                    hovertemplate='<b>%{x}</b><br>Avg GPA: %{y:.2f}<extra></extra>'
                ), secondary_y=True)
            fig.update_layout(
                title=dict(text="Sponsorship Enrolment & Academic Performance",
                           font=dict(size=18, color='white', family='Arial Black'), x=0.5, xanchor='center'),
                xaxis=dict(title="Sponsorship Type", tickfont=dict(size=11, color='white'), tickangle=-45),
                plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(30,41,59,0.85)',
                font=dict(color='white', size=11), height=450,
                legend=dict(x=0.5, y=1.15, xanchor='center', orientation='h',
                            font=dict(size=11, color='white'), bgcolor='rgba(0,0,0,0.3)'),
                margin=dict(l=60, r=60, t=100, b=120))
            fig.update_yaxes(title_text="Number of Students", secondary_y=False,
                             tickfont=dict(color='white'), title_font=dict(color='white'))
            if _has_gpa:
                fig.update_yaxes(title_text="Average GPA", secondary_y=True,
                                 tickfont=dict(color='white'), title_font=dict(color='white'), range=[0, 4.0])
            st.plotly_chart(fig, use_container_width=True, key="pc_6900")

        with col2:
            _scatter_y = spon_perf['Avg GPA'] if (_has_gpa and 'Avg GPA' in spon_perf.columns) else spon_perf['Avg Aid']
            _y_title   = "Average GPA" if (_has_gpa and 'Avg GPA' in spon_perf.columns) else "Average Aid (AED)"
            fig = go.Figure(data=[go.Scatter(
                x=spon_perf['Students'], y=_scatter_y,
                mode='markers+text',
                marker=dict(
                    size=[max(s * 2, 8) for s in spon_perf['Students']],
                    color=_scatter_y, colorscale='RdYlGn',
                    cmin=2.0 if _has_gpa else None, cmax=4.0 if _has_gpa else None,
                    showscale=True,
                    colorbar=dict(title=dict(text="Avg GPA" if _has_gpa else "Aid", font=dict(color="white")),
                                  tickfont=dict(color='white')),
                    line=dict(color='white', width=2), sizemode='diameter'),
                text=spon_perf['Sponsorship Type'], textposition='top center',
                textfont=dict(size=10, color='white'),
                hovertemplate='<b>%{text}</b><br>Students: %{x}<extra></extra>'
            )])
            fig.update_layout(
                title=dict(text="Sponsorship Programme Effectiveness Matrix",
                           font=dict(size=18, color='white', family='Arial Black'), x=0.5, xanchor='center'),
                xaxis=dict(title="Number of Students", tickfont=dict(size=11, color='white'),
                           gridcolor='rgba(255,255,255,0.2)'),
                yaxis=dict(title=_y_title, tickfont=dict(size=11, color='white'),
                           gridcolor='rgba(255,255,255,0.2)', range=[0, 4.0] if _has_gpa else None),
                plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(30,41,59,0.85)',
                font=dict(color='white', size=11), height=450)
            st.plotly_chart(fig, use_container_width=True, key="pc_6929")

    # ── Payment Collection Analytics ──
    if 'past_due_balance' in df.columns or 'total_payments_ytd' in df.columns or 'balance_due' in df.columns or 'account_balance' in df.columns:
        st.markdown("### 💳 Payment Collection & Financial Operations Analytics")
        col1, col2 = st.columns(2)
        with col1:
            # Catalog canonical past_due_balance, fallback to account_balance
            _bal_col_24 = 'past_due_balance' if 'past_due_balance' in df.columns else ('account_balance' if 'account_balance' in df.columns else None)
            if _bal_col_24 is not None and 'cohort_year' in df.columns:
                bal_cohort = df.groupby('cohort_year').agg(
                    students=(_bal_col_24, 'count'),
                    outstanding=(_bal_col_24, 'sum')
                ).reset_index()
                bal_cohort['Outstanding (AED M)'] = bal_cohort['outstanding'] / 1e6
                fig = go.Figure()
                fig.add_trace(go.Bar(
                    x=bal_cohort['cohort_year'], y=bal_cohort['Outstanding (AED M)'],
                    marker=dict(color=bal_cohort['Outstanding (AED M)'], colorscale='Reds',
                                showscale=True,
                                colorbar=dict(title=dict(text="AED M", font=dict(color="white")),
                                              tickfont=dict(color='white')),
                                line=dict(color='white', width=2)),
                    text=[f"<b>AED {v:.2f}M</b>" for v in bal_cohort['Outstanding (AED M)']],
                    textposition='outside', textfont=dict(size=12, color='white', family='Arial Black'),
                    customdata=bal_cohort['students'],
                    hovertemplate='<b>Cohort %{x}</b><br>Outstanding: AED %{y:.2f}M<br>Students: %{customdata}<extra></extra>'
                ))
                fig.update_layout(
                    title=dict(text="Outstanding Balances by Cohort Year",
                               font=dict(size=18, color='white', family='Arial Black'), x=0.5, xanchor='center'),
                    xaxis=dict(title="Cohort Year", tickfont=dict(size=11, color='white')),
                    yaxis=dict(title="Outstanding Balance (AED M)", tickfont=dict(size=11, color='white'),
                               gridcolor='rgba(255,255,255,0.2)'),
                    plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(30,41,59,0.85)',
                    font=dict(color='white', size=11), height=450)
                st.plotly_chart(fig, use_container_width=True, key="pc_6963")
            else:
                st.info("account_balance or cohort_year column not found.")

        with col2:
            _has_rent = 'rent_paid' in df.columns
            _has_fee  = 'fee_paid' in df.columns
            _has_bal  = 'account_balance' in df.columns
            if _has_rent and _has_fee and _has_bal:
                payment_breakdown = pd.DataFrame({
                    'Category': ['Rent Payments', 'Fee Payments', 'Outstanding Balances'],
                    'Amount (AED M)': [df['rent_paid'].sum() / 1e6,
                                       df['fee_paid'].sum() / 1e6,
                                       df['account_balance'].sum() / 1e6],
                    'Color': ['#10b981', '#3b82f6', '#ef4444']
                })
                fig = go.Figure(data=[go.Bar(
                    x=payment_breakdown['Category'],
                    y=payment_breakdown['Amount (AED M)'],
                    marker=dict(color=payment_breakdown['Color'], line=dict(color='white', width=2)),
                    text=[f"<b>AED {v:.1f}M</b>" for v in payment_breakdown['Amount (AED M)']],
                    textposition='outside', textfont=dict(size=12, color='white', family='Arial Black'),
                    hovertemplate='<b>%{x}</b><br>Amount: AED %{y:.1f}M<extra></extra>'
                )])
                fig.update_layout(
                    title=dict(text="Payment Breakdown: Rent, Fees & Outstanding",
                               font=dict(size=18, color='white', family='Arial Black'), x=0.5, xanchor='center'),
                    xaxis=dict(title='', tickfont=dict(size=11, color='white')),
                    yaxis=dict(title='Amount (AED M)', title_font=dict(size=12, color='white'),
                               tickfont=dict(size=11, color='white'), gridcolor='rgba(255,255,255,0.1)'),
                    showlegend=False, paper_bgcolor='rgba(30,41,59,0.85)', plot_bgcolor='rgba(0,0,0,0)',
                    height=450, margin=dict(l=60, r=20, t=80, b=80))
                st.plotly_chart(fig, use_container_width=True, key="pc_6995")
            else:
                st.info("rent_paid, fee_paid, or account_balance columns not found.")


# ──────────────────────────────────────────────────────────────
# MAIN APPLICATION
# ──────────────────────────────────────────────────────────────

def main():
    st.markdown(THEME_CSS, unsafe_allow_html=True)

    # ── Sidebar & data loading ──
    df, model, ollama_url = render_sidebar()

    # ── Hero banner ──
    render_hero()

    # ── Gate: no data ──
    if df is None:
        st.markdown("""
        <div style="text-align:center;padding:60px 20px;">
            <div style="font-size:3rem;margin-bottom:16px;">📂</div>
            <div style="font-size:1.2rem;color:#94a3b8;">
                Upload a financial dataset or select the sample data from the sidebar to get started.
            </div>
        </div>
        """, unsafe_allow_html=True)
        return

    # ── Compute roles & KPIs ──
    col_roles = detect_financial_columns(df)
    kpis      = compute_financial_kpis(df, col_roles)

    # ── Detect entity/domain and store vocabulary in session state ──
    _entity_type = detect_entity_type(df)
    st.session_state['_entity_vocab'] = ENTITY_TERMINOLOGY[_entity_type]
    st.session_state['_entity_type']  = _entity_type

    # ── Advisory: generate or use cached ──
    data_sig = f"{len(df)}-{list(df.columns)}-{model}"
    cached_advisory = st.session_state.get('fin_advisory_cache', {})

    advisory = cached_advisory.get(data_sig)

    ollama_connected = st.session_state.get('fin_ollama_connected', False)

    # ── Always ensure advisory is populated immediately ──
    # All 7 tabs need advisory data. If no cached advisory exists yet,
    # generate a rule-based baseline right now so no tab ever renders empty.
    # The LLM button below upgrades it to AI-powered advisory on demand.
    if not advisory:
        advisory = _rule_based_advisory(kpis)
        cache = st.session_state.get('fin_advisory_cache', {})
        cache[data_sig] = advisory
        st.session_state['fin_advisory_cache'] = cache

    # ── Advisory action bar ──
    _is_ai_advisory = advisory.get('_source') == 'llm'
    adv_row = st.columns([3, 2])
    with adv_row[0]:
        if ollama_connected and model:
            if _is_ai_advisory:
                # Already have AI advisory — offer refresh
                if st.button("🔄 Refresh AI Advisory", key="fin_refresh_advisory"):
                    cache = st.session_state.get('fin_advisory_cache', {})
                    cache.pop(data_sig, None)
                    st.session_state['fin_advisory_cache'] = cache
                    narrative_key = f"narrative-{len(df)}-{list(df.columns)}"
                    st.session_state.pop(narrative_key, None)
                    st.session_state.pop('_last_advisory_sig', None)
                    st.rerun()
            else:
                # Rule-based advisory is showing — offer LLM upgrade
                if st.button("✨ Generate AI Advisory Report", key="fin_generate_advisory"):
                    with st.spinner("Analysing your financial data with AI..."):
                        ai_advisory = generate_financial_advisory(df, kpis, col_roles, model, ollama_url)
                        if ai_advisory and isinstance(ai_advisory, dict):
                            ai_advisory['_source'] = 'llm'
                        else:
                            ai_advisory = advisory  # keep rule-based if LLM failed
                        cache = st.session_state.get('fin_advisory_cache', {})
                        cache[data_sig] = ai_advisory
                        st.session_state['fin_advisory_cache'] = cache
                        narrative_key = f"narrative-{len(df)}-{list(df.columns)}"
                        st.session_state.pop(narrative_key, None)
                        st.session_state.pop('_last_advisory_sig', None)
                        st.rerun()
        else:
            if st.button("🔄 Refresh Advisory", key="fin_refresh_advisory_rb"):
                cache = st.session_state.get('fin_advisory_cache', {})
                cache.pop(data_sig, None)
                st.session_state['fin_advisory_cache'] = cache
                st.rerun()
    with adv_row[1]:
        _adv_source_badge = "🤖 AI Advisory" if _is_ai_advisory else "📊 Rule-Based Advisory"
        st.caption(
            f"{_adv_source_badge} — "
            f"{len(advisory.get('opportunities', []))} opportunities, "
            f"{len(advisory.get('risks', []))} risks identified"
        )

    # ── Build narrative (always rule-based; LLM prose on demand) ──
    narrative_key = f"narrative-{len(df)}-{list(df.columns)}"
    if narrative_key not in st.session_state:
        st.session_state[narrative_key] = build_financial_narrative(df, kpis, col_roles, advisory)
    narrative = st.session_state[narrative_key]

    # Refresh narrative if advisory just changed
    if advisory and st.session_state.get('_last_advisory_sig') != data_sig:
        st.session_state[narrative_key] = build_financial_narrative(df, kpis, col_roles, advisory)
        narrative = st.session_state[narrative_key]
        st.session_state['_last_advisory_sig'] = data_sig

    # ── Main tabs ──
    tabs = st.tabs([
        "💰 Command Centre",
        "📖 Financial Story",
        "🎯 Strategic Advisor",
        "🔭 Forward Guidance",
        "🔬 Data Explorer",
        "💡 Financial Intelligence",
        "🏦 Journey 2: Revenue Strategy",
    ])

    with tabs[0]:
        render_command_centre_tab(df, kpis, col_roles)

    with tabs[1]:
        render_narrative_tab(df, kpis, col_roles, advisory, narrative, model, ollama_url)

    with tabs[2]:
        render_advisory_tab(df, kpis, col_roles, advisory)

    with tabs[3]:
        render_forward_guidance_tab(df, kpis, col_roles, advisory)

    with tabs[4]:
        render_data_explorer_tab(df, col_roles, kpis)

    with tabs[5]:
        render_financial_intelligence_tab(
            apply_filters(df),
            kpis=kpis,
            col_roles=col_roles,
            advisory=advisory,
            narrative=narrative,
        )

    with tabs[6]:
        render_journey2_tab(
            apply_filters(df),
            kpis=kpis,
            col_roles=col_roles,
            advisory=advisory,
            narrative=narrative,
        )

    # ═══════════════════════════════════════════════════════════════
    # MASTER FINDINGS SUMMARY — cross-tab financial health summary
    # ═══════════════════════════════════════════════════════════════
    st.markdown("<br/>", unsafe_allow_html=True)
    _m_rev  = kpis.get('total_revenue', kpis.get('avg_revenue', 0)) or 0
    _m_gm   = kpis.get('gross_margin_pct')
    _m_mom  = kpis.get('mom_pct')
    _m_opps = advisory.get('opportunities', []) if advisory else []
    _m_risks = advisory.get('risks', []) if advisory else []
    _m_num  = len(df.select_dtypes(include='number').columns)
    _m_miss = (df.isnull().sum().sum() / max(df.size, 1)) * 100
    _m_dups = int(df.duplicated().sum())

    _m_gm_status = ("✅ Healthy" if (_m_gm or 0) > 30 else
                    "⚠️ Moderate" if (_m_gm or 0) > 15 else "🔴 Critical") if _m_gm else "N/A"
    _m_mom_status = ("✅ Growing" if (_m_mom or 0) >= 5 else
                     "⚠️ Stable" if (_m_mom or 0) >= 0 else "🔴 Declining") if _m_mom else "N/A"
    _m_data_status = "✅ Good" if _m_miss < 5 else "⚠️ Gaps" if _m_miss < 20 else "🔴 Poor"
    _m_opp_count  = len(_m_opps)
    _m_risk_count = len(_m_risks)
    _m_high_opps  = [o for o in _m_opps if o.get('impact', '').upper() == 'HIGH']
    _m_high_risks = [r for r in _m_risks if r.get('severity', '').upper() == 'HIGH']

    # ── Pre-compute all display values before building HTML ──
    _m_rev_str       = _fmt(_m_rev, prefix="$")
    _m_gm_str        = f"{_m_gm:.1f}%" if _m_gm else "N/A"
    _m_mom_str       = f"{_m_mom:+.1f}%" if _m_mom else "N/A"
    _m_quality_str   = f"{100 - _m_miss:.0f}%"
    _m_upside_str    = _fmt(_m_rev * 0.08, prefix="$")
    _m_risk_str      = _fmt(_m_rev * 0.15, prefix="$")
    _m_cat_count     = len(df.select_dtypes(include="object").columns)
    _m_complete_str  = f"{100 - _m_miss:.1f}%"
    _m_rows_str      = f"{len(df):,}"
    _m_dups_str      = f"{_m_dups:,}"

    # 30-day margin priority
    if _m_gm and (_m_gm or 0) < 15:
        _m_30d_margin = "🔴 URGENT: Gross margin below 15% — cost audit + pricing review this week."
    elif _m_gm and (_m_gm or 0) < 30:
        _m_30d_margin = "⚠️ Margin below 30% — initiate cost reduction programme."
    else:
        _m_30d_margin = "✅ Margin healthy — focus on revenue growth."

    # 30-day revenue priority
    if _m_mom and (_m_mom or 0) < 0:
        _m_30d_revenue = "🔴 Income declining — enrolment retention analysis + financial recovery plan."
    elif _m_mom and (_m_mom or 0) < 5:
        _m_30d_revenue = "⚠️ Revenue flat — activate growth levers."
    else:
        _m_30d_revenue = "✅ Revenue growing — sustain and scale."

    # 90-day trajectory
    _m_90_scenario = "Optimal (+5%/mo)" if (_m_gm or 0) > 20 else "Conservative (+2%/mo)"
    _m_90_mult     = 1.05**3 if (_m_gm or 0) > 20 else 1.02**3
    _m_90_target   = _fmt(_m_rev * _m_90_mult, prefix="$")
    if (_m_gm or 0) > 25 and (_m_mom or 0) >= 0:
        _m_90_action = "Expand into new segments — fundamentals support growth."
    elif (_m_gm or 0) > 10:
        _m_90_action = "Stabilise core metrics before expansion."
    else:
        _m_90_action = "Recovery mode — protect cash flow first."

    # Data quality note
    if _m_miss < 5 and _m_dups == 0:
        _m_data_note = "✅ Dataset analysis-ready for executive reporting."
    elif _m_miss < 20:
        _m_data_note = "⚠️ Address data gaps before executive reporting."
    else:
        _m_data_note = "🔴 Data remediation required — findings are directional only."

    # Opportunities bullet list
    if _m_high_opps:
        _m_opp_bullets = "".join(
            "<br/>&bull; " + str(o.get("title", "Opportunity")).replace("<", "&lt;").replace(">", "&gt;")
            + " [" + str(o.get("impact", "?")).upper() + "]"
            for o in _m_high_opps[:3]
        )
    else:
        _m_opp_bullets = "&bull; No high-impact opportunities flagged — run analysis for details."

    # Risks bullet list
    if _m_high_risks:
        _m_risk_bullets = "".join(
            "<br/>&bull; " + str(r.get("title", "Risk")).replace("<", "&lt;").replace(">", "&gt;")
            + " [" + str(r.get("severity", "?")).upper() + "]"
            for r in _m_high_risks[:3]
        )
    else:
        _m_risk_bullets = "&bull; No high-severity risks flagged — run analysis for details."

    # ── Build HTML cards individually ──
    _card_financial = (
        '<div style="background:rgba(16,185,129,0.07);border:1px solid rgba(16,185,129,0.25);'
        'border-radius:12px;padding:16px 18px;">'
        '<div style="color:#10b981;font-weight:700;font-size:0.82rem;margin-bottom:10px;'
        'text-transform:uppercase;">💰 FINANCIAL HEALTH</div>'
        '<div style="color:#e2e8f0;font-size:0.85rem;line-height:1.85;">'
        'Revenue: <strong>' + _m_rev_str + '</strong><br/>'
        'Gross Margin: <strong>' + _m_gm_str + '</strong> — ' + _m_gm_status + '<br/>'
        'MoM Growth: <strong>' + _m_mom_str + '</strong> — ' + _m_mom_status + '<br/>'
        'Data Quality: <strong>' + _m_quality_str + '</strong> complete — ' + _m_data_status +
        '</div></div>'
    )

    _card_opps = (
        '<div style="background:rgba(245,158,11,0.07);border:1px solid rgba(245,158,11,0.25);'
        'border-radius:12px;padding:16px 18px;">'
        '<div style="color:#f59e0b;font-weight:700;font-size:0.82rem;margin-bottom:10px;'
        'text-transform:uppercase;">🚀 OPPORTUNITIES (' + str(_m_opp_count) + ')</div>'
        '<div style="color:#e2e8f0;font-size:0.85rem;line-height:1.85;">'
        + _m_opp_bullets +
        '<br/>Total identified: ' + str(_m_opp_count) + ' | High: ' + str(len(_m_high_opps)) + '<br/>'
        'Estimated upside: <strong>~' + _m_upside_str + '</strong> (8% revenue)'
        '</div></div>'
    )

    _card_risks = (
        '<div style="background:rgba(239,68,68,0.07);border:1px solid rgba(239,68,68,0.25);'
        'border-radius:12px;padding:16px 18px;">'
        '<div style="color:#ef4444;font-weight:700;font-size:0.82rem;margin-bottom:10px;'
        'text-transform:uppercase;">⚠️ RISKS (' + str(_m_risk_count) + ')</div>'
        '<div style="color:#e2e8f0;font-size:0.85rem;line-height:1.85;">'
        + _m_risk_bullets +
        '<br/>Total identified: ' + str(_m_risk_count) + ' | High: ' + str(len(_m_high_risks)) + '<br/>'
        'Revenue at risk: <strong>~' + _m_risk_str + '</strong> (15% downside)'
        '</div></div>'
    )

    _card_30d = (
        '<div style="background:rgba(99,102,241,0.07);border:1px solid rgba(99,102,241,0.25);'
        'border-radius:12px;padding:16px 18px;">'
        '<div style="color:#818cf8;font-weight:700;font-size:0.82rem;margin-bottom:10px;'
        'text-transform:uppercase;">📅 30-DAY PRIORITIES</div>'
        '<div style="color:#e2e8f0;font-size:0.85rem;line-height:1.85;">'
        + _m_30d_margin + '<br/>'
        + _m_30d_revenue + '<br/>'
        'Monitor ' + str(_m_num) + ' KPIs with ±5% deviation alerts.'
        '</div></div>'
    )

    _card_90d = (
        '<div style="background:rgba(56,189,248,0.07);border:1px solid rgba(56,189,248,0.25);'
        'border-radius:12px;padding:16px 18px;">'
        '<div style="color:#38bdf8;font-weight:700;font-size:0.82rem;margin-bottom:10px;'
        'text-transform:uppercase;">🗺 90-DAY TRAJECTORY</div>'
        '<div style="color:#e2e8f0;font-size:0.85rem;line-height:1.85;">'
        'Target scenario: <strong>' + _m_90_scenario + '</strong><br/>'
        '3-month revenue target: <strong>' + _m_90_target + '</strong><br/>'
        + _m_90_action + '<br/>'
        'Data quality target: <strong>95%+</strong> completeness.'
        '</div></div>'
    )

    _card_data = (
        '<div style="background:rgba(167,139,250,0.07);border:1px solid rgba(167,139,250,0.25);'
        'border-radius:12px;padding:16px 18px;">'
        '<div style="color:#a78bfa;font-weight:700;font-size:0.82rem;margin-bottom:10px;'
        'text-transform:uppercase;">📊 DATA PROFILE</div>'
        '<div style="color:#e2e8f0;font-size:0.85rem;line-height:1.85;">'
        'Records: <strong>' + _m_rows_str + '</strong> | Columns: <strong>' + str(len(df.columns)) + '</strong><br/>'
        'Numeric: <strong>' + str(_m_num) + '</strong> | Categorical: <strong>' + str(_m_cat_count) + '</strong><br/>'
        'Completeness: <strong>' + _m_complete_str + '</strong> | Duplicates: <strong>' + _m_dups_str + '</strong><br/>'
        + _m_data_note +
        '</div></div>'
    )

    st.markdown(
        '<div style="background:linear-gradient(135deg,rgba(99,102,241,0.10) 0%,rgba(59,130,246,0.07) 100%);'
        'border:3px solid #6366f1;border-radius:18px;padding:28px 32px;margin:8px 0 24px 0;">'
        '<div style="color:#818cf8;font-weight:700;font-size:1.15rem;margin-bottom:20px;'
        'text-transform:uppercase;letter-spacing:0.8px;">'
        '🎯 MASTER FINANCIAL INTELLIGENCE SUMMARY'
        '</div>'
        '<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:18px;">'
        + _card_financial
        + _card_opps
        + _card_risks
        + _card_30d
        + _card_90d
        + _card_data +
        '</div></div>',
        unsafe_allow_html=True
    )

    # ── Full v2 mode (all original tabs) ──
    if st.session_state.get('fin_show_all_original', False):
        st.markdown("---")
        st.markdown("### 🔧 Full Analysis Mode (v2 features)")
        st.info(
            "Full analysis mode exposes all 277 analytical functions from the Exalio v2 engine. "
            "Switch to v2 mode by running `app_cloudflare_v2.py` directly for the complete experience."
        )


if __name__ == "__main__":
    main()
