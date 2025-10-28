import streamlit as st
from pathlib import Path
from slides import get_slides, Slide
from typing import Optional
from data import load_data, compute_metrics  # no need to import compute_read_speeds

# ──────────────────────────────────────────────────────────────────────────────
# Page config FIRST
# ──────────────────────────────────────────────────────────────────────────────
st.set_page_config(page_title="Libby Wrapped", page_icon="🎧", layout="wide")

st.markdown(
    '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">',
    unsafe_allow_html=True,
)


# ──────────────────────────────────────────────────────────────────────────────
# Fonts + CSS
# ──────────────────────────────────────────────────────────────────────────────
st.markdown(
    """
    <link rel="stylesheet" href="https://use.typekit.net/leb4yxw.css">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@fontsource/sf-pro-text@latest/index.css">
    """,
    unsafe_allow_html=True,
)
css = Path(__file__).with_name("styles.css").read_text()
st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)

# ──────────────────────────────────────────────────────────────────────────────
# Data (cached load + compute)
# ──────────────────────────────────────────────────────────────────────────────

CSV_PATH   = "libby-export.csv"
LOANS_PATH = "libbytimeline-all-loans,all.csv"

def format_fastest_reads(fastest_top3):
    if not fastest_top3:
        return "No completed reads found this year."
    return "<br>".join(
        f"{i}. {b['title']} by {b['author']} — {b['hours_to_finish']:.1f} hrs"
        for i, b in enumerate(fastest_top3, start=1)
    )

@st.cache_data
def load_metrics(csv_path):
    df = load_data(csv_path)
    # use the global LOANS_PATH directly
    m = compute_metrics(df, year=2025, loans_path=LOANS_PATH)
    fastest_top3_str = format_fastest_reads(m.fastest_top3)
    return m, fastest_top3_str

metrics, fastest_top3_str = load_metrics(CSV_PATH)

# ──────────────────────────────────────────────────────────────────────────────
# Slides
# ──────────────────────────────────────────────────────────────────────────────
slides = get_slides()
n = len(slides)


# ──────────────────────────────────────────────────────────────────────────────
# Context for placeholder formatting in slides.py
# ──────────────────────────────────────────────────────────────────────────────
class SafeDict(dict):
    def __missing__(self, key):
        return "{"+key+"}"

def build_context(m, fastest_top3_str):
    speedup_factor = 1.85
    return SafeDict({
        "full_books": m.total_books,
        "novellas": m.novella_count,
        "total_finished": m.total_finished,

        "books_checked_out": getattr(m, "books_checked_out", 0),
        "dnfs": getattr(m, "dnfs", 0),

        "listening_hours": int(getattr(m, "finished_audiobook_length_2025", 0)),
        "listening_hours_days": round(getattr(m, "finished_audiobook_length_2025", 0) / 24, 1),
        "speedup_factor": speedup_factor,
        "real_hours": int(getattr(m, "finished_audiobook_length_2025", 0) / speedup_factor),

        "biggest_month": m.biggest_month or "—",
        "biggest_month_hours": round(getattr(m, "biggest_month_hours", 0.0), 1),

        # fastest read metrics now come from Metrics
        "fastest_title": m.fastest_title or "—",
        "fastest_hours": round(getattr(m, "fastest_hours", 0), 1),
        "fastest_days": m.fastest_days,

        "fastest_top3": getattr(m, "fastest_top3", []) or [],
        "fastest_top3_str": fastest_top3_str,

        # placeholders you may fill later
        "percentile": m.percentile,

        # author metrics
        "authors_count": getattr(m, "authors_count", 0),
        "top_author": getattr(m, "top_author", "—"),
        "top_author_books": getattr(m, "top_author_books", 0),
        "top_author_minutes": int(getattr(m, "top_author_minutes", 0)),
        "top_author_hours": round(getattr(m, "top_author_hours", 0.0), 1),
        "top_author_book_title_1": getattr(m, "top_author_book_title_1", ""),
        "top_author_book_title_2": getattr(m, "top_author_book_title_2", ""),

        # genre metrics
        "genres_count": getattr(m, "genres_count", 0),
        "top_genre": getattr(m, "top_genre", "—"),

        "savings": round(getattr(m, "savings_combined", 0.0), 2),
        "savings_finished": round(getattr(m, "savings_finished", 0.0), 2),
        "savings_dnf": round(getattr(m, "savings_dnf", 0.0), 2),


    })

ctx = build_context(metrics, fastest_top3_str)


# ──────────────────────────────────────────────────────────────────────────────
# URL-synced navigation (chips + back/next)
# ──────────────────────────────────────────────────────────────────────────────
if "idx" not in st.session_state:
    st.session_state.idx = 0

def read_slide_param():
    try:
        raw = st.query_params.get("slide", None)  # new API
        if isinstance(raw, list): raw = raw[0]
    except Exception:
        raw = st.experimental_get_query_params().get("slide", [None])[0]
    try:
        return int(raw) if raw is not None else None
    except Exception:
        return None

q_idx = read_slide_param()
if q_idx is not None:
    st.session_state.idx = max(0, min(n - 1, q_idx))

def set_query_slide(i: int):
    i = max(0, min(n - 1, i))
    st.session_state.idx = i
    try:
        st.query_params["slide"] = str(i)
    except Exception:
        st.experimental_set_query_params(slide=i)
    st.rerun()

def go(delta: int):
    set_query_slide(st.session_state.idx + delta)

def storybar_clickable(total: int, idx: int):
    # short, centered IG-style segments; past+current = filled
    row_open = "<div class='story-chip-row'>"
    segs = []
    for i in range(total):
        fill = 100 if i <= idx else 0
        segs.append(
            f"<a class='story-chip' href='?slide={i}' target='_self'>"
            f"<span style='width:{fill}%;'></span>"
            "</a>"
        )
    st.markdown(row_open + "".join(segs) + "</div>", unsafe_allow_html=True)

# ──────────────────────────────────────────────────────────────────────────────
# Slide rendering
# ──────────────────────────────────────────────────────────────────────────────
def _nonempty(s: Optional[str]) -> bool:
    return bool(s and str(s).strip())

def render_slide(slide: Slide, ctx: dict) -> str:
    subtitle = (slide.subtitle or "").format_map(ctx)
    title    = (slide.title or "").format_map(ctx)
    notes    = (slide.notes or "").format_map(ctx)
    body     = (slide.body or "").format_map(ctx)

    parts = []
    if _nonempty(subtitle):
        parts.append(f"<h1>{subtitle}</h1>")
    if _nonempty(title):
        parts.append(f"<h3>{title}</h3>")
    if _nonempty(body):
        parts.append(f'<div class="body">{body}</div>')
    if _nonempty(notes):
        parts.append(f'<p class="small">{notes}</p>')

    classes = "slide centered" if getattr(slide, "layout", "center") == "center" else "slide"
    return f'<div class="{classes}"><div class="stack stack-lg">{"".join(parts)}</div></div>'


# ──────────────────────────────────────────────────────────────────────────────
# Header + chips
# ──────────────────────────────────────────────────────────────────────────────
left, right = st.columns([1, 2])
with left:
    st.markdown('<span class="badge">Libby Wrapped</span>', unsafe_allow_html=True)
with right:
    st.write("")

storybar_clickable(n, st.session_state.idx)

# ──────────────────────────────────────────────────────────────────────────────
# Slide content
# ──────────────────────────────────────────────────────────────────────────────
current = slides[st.session_state.idx]
st.markdown(render_slide(current, ctx), unsafe_allow_html=True)

# ──────────────────────────────────────────────────────────────────────────────
# Nav
# ──────────────────────────────────────────────────────────────────────────────

# Extra space so the fixed buttons don't overlap content on mobile
st.markdown('<div class="controls-spacer"></div>', unsafe_allow_html=True)


st.markdown('<div class="buttons">', unsafe_allow_html=True)
c1, c2 = st.columns(2)
with c1:
    if st.button("⬅️ Back", use_container_width=True, disabled=st.session_state.idx == 0):
        go(-1)
with c2:
    if st.button("Next ➡️", use_container_width=True, type="primary"):
        go(+1)
st.markdown("</div>", unsafe_allow_html=True)
