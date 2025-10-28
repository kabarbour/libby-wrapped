"""
data.py — Data loader + computed metrics for Libby Wrapped.

What this module does:
1) Load and normalize your libby-export.csv (“reads” DB) and libbytimeline CSV (“loans”).
2) Apply sanity/cleanup helpers (column normalization, mixed-date parsing, title normalization).
3) Compute all metrics used by the app:
   - Finished counts, novella counts, percentile (based on Pew-style brackets)
   - Audiobook hours + biggest month
   - Fastest reads (borrow → created_time)
   - Authors (unique, top author, top 2 titles, minutes/hours)
   - Genres (unique, top)
   - Checkouts & DNFs from timeline (unique titles checked out this year but not completed)
   - Savings (sum of finished costs + avg finished cost × DNFs)

Assumptions:
- libbytimeline timestamps are UTC and should be displayed in LOCAL_TZ (naive local for calculations).
- “Created time” in your export is the moment you logged the finish in your DB (used as “finish time”).
- “DNF” is “checked out this year, not completed this year” (rereads/finishes in later years still count as DNF for this year, by design).
"""

from dataclasses import dataclass
from typing import Dict, Optional, List
from pathlib import Path
import pandas as pd
import re

# ──────────────────────────────────────────────────────────────────────────────
# Config
# ──────────────────────────────────────────────────────────────────────────────

LOCAL_TZ = "America/Indiana/Indianapolis"

# Default paths (overridable via function args)
CSV_PATH   = Path("libby-export.csv")
LOANS_PATH = Path("libbytimeline-all-loans,all.csv")


# ──────────────────────────────────────────────────────────────────────────────
# Metrics container
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class Metrics:
    # Checkouts & DNFs (timeline-based)
    books_checked_out: int = 0          # unique titles checked out this year
    dnfs: int = 0                        # checked out this year but not completed this year

    # Finished counts (export-based)
    total_books: int = 0                 # completed non-novellas
    novella_count: int = 0               # completed novellas
    total_finished: int = 0              # all completed items (books + novellas)
    percentile: int = 0                  # read more than X% of adults

    # Audiobooks
    finished_audiobook_length_2025: float = 0.0  # total audiobook hours (completed only)
    biggest_month: Optional[str] = None
    biggest_month_hours: float = 0.0

    # Fastest reads
    fastest_title: str = ""                          # quickest finished title (this year)
    fastest_days: float = 0.0                        # hours / 24 (compat)
    fastest_hours: float = 0.0                       # hours from borrow -> created_time
    fastest_top3: Optional[List[Dict]] = None        # [{title, author, hours_to_finish}]

    # Authors (listening)
    authors_count: int = 0
    top_author: str = ""
    top_author_books: int = 0
    top_author_minutes: float = 0.0
    top_author_hours: float = 0.0
    top_author_book_title_1: str = ""
    top_author_book_title_2: str = ""

    # Genres
    genres_count: int = 0
    top_genre: str = ""

    # Savings
    savings_finished: float = 0.0
    savings_dnf: float = 0.0
    savings_combined: float = 0.0


# ──────────────────────────────────────────────────────────────────────────────
# Helpers — normalization & parsing
# ──────────────────────────────────────────────────────────────────────────────

def _normalize_cols(df: pd.DataFrame) -> pd.DataFrame:
    """Lowercase columns, replace spaces with underscores, strip whitespace."""
    df = df.copy()
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
    return df


_punct = re.compile(r"[^\w\s]")
_brackets = re.compile(r"(\[.*?\]|\(.*?\))")

def _canon_title(s: str) -> str:
    """
    Canonicalize a title for joining:
    - lowercase, remove bracketed/parenthetical segments, strip punctuation
    - collapse spaces, remove trailing 'reread ...'
    """
    if not isinstance(s, str):
        return ""
    s = s.lower().strip()
    s = _brackets.sub("", s)
    s = s.replace("—", "-").replace("–", "-")
    s = re.sub(r"\breread\b.*$", "", s)
    s = _punct.sub(" ", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def _display_title(s: str) -> str:
    """Pretty-print a title for UI (keeps case, removes (#2), [reread], extra spaces)."""
    if not isinstance(s, str):
        return ""
    s = re.sub(r"\s*\(.*?\)", "", s)   # remove (...) parts
    s = re.sub(r"\s*\[.*?\]", "", s)   # remove [...] parts
    s = re.sub(r"\s{2,}", " ", s)      # collapse double spaces
    return s.strip()


def _parse_created_series(s: pd.Series) -> pd.Series:
    """
    Parse mixed-format 'created_time' strings into pandas Timestamps.
    Handles strings like 'April 23, 2021 8:21 PM' and ISO-like values.
    """
    s = s.astype(str).str.strip()
    alpha_mask = s.str.contains(r"[A-Za-z]", na=False)

    out = pd.Series(pd.NaT, index=s.index)

    # Parse alpha-month (e.g., April 23, 2021 8:21 PM)
    if alpha_mask.any():
        out.loc[alpha_mask] = pd.to_datetime(
            s.loc[alpha_mask], format="%B %d, %Y %I:%M %p", errors="coerce"
        )

    # Parse non-alpha (ISO-ish or numeric)
    if (~alpha_mask).any():
        out.loc[~alpha_mask] = pd.to_datetime(s.loc[~alpha_mask], errors="coerce")

    # Fallback best effort for any remaining
    missing = out.isna()
    if missing.any():
        out.loc[missing] = pd.to_datetime(s.loc[missing], errors="coerce")

    return out


# ──────────────────────────────────────────────────────────────────────────────
# Data loading + manual fixes
# ──────────────────────────────────────────────────────────────────────────────

def load_data(path: Path = CSV_PATH, persist_fixes: bool = True) -> pd.DataFrame:
    """
    Load the main export (libby-export.csv), normalize columns, apply manual timestamp fixes,
    and optionally persist the corrected CSV.
    """
    if not Path(path).exists():
        return pd.DataFrame()
    df = pd.read_csv(path)
    df = _normalize_cols(df)
    df = fix_finished_times(df)
    if persist_fixes:
        # Only rewrite if something would change (avoid toggling mtime unnecessarily).
        try:
            orig = pd.read_csv(path)
            if not _normalize_cols(orig).equals(df):
                df.to_csv(path, index=False)
        except Exception:
            # If anything goes sideways, skip persisting—keep in-memory frame sane.
            pass
    return df


def fix_finished_times(df: pd.DataFrame) -> pd.DataFrame:
    """
    Apply known manual corrections to the 'created_time' (or similar) column
    for specific titles. This helps ensure correct finish times for speed calcs.

    Edit the 'raw_fixes' mapping below to add more overrides.
    """
    raw_fixes = {
        "Mate (#2)":       "2025-10-07 23:27",
        "Onyx Storm (#3)": "2025-01-23 10:30",
    }

    out = df.copy()
    created_col = next((c for c in ["created_time", "created", "created_at"] if c in out.columns), None)
    if created_col is None:
        return out  # Nothing to fix if no created-time-like column exists.

    fixes = {_canon_title(k): pd.to_datetime(v) for k, v in raw_fixes.items()}
    out["title_norm"] = out.get("name", "").map(_canon_title)

    # Prefer fixing rows within the same year as the target timestamp.
    for canon_title, ts in fixes.items():
        mask = (
            out["title_norm"].eq(canon_title) &
            (pd.to_datetime(out[created_col], errors="coerce").dt.year == ts.year)
        )
        if not mask.any():
            mask = out["title_norm"].eq(canon_title)
        out.loc[mask, created_col] = ts

    return out.drop(columns=["title_norm"])


# ──────────────────────────────────────────────────────────────────────────────
# Read speeds (borrow → created_time)
# ──────────────────────────────────────────────────────────────────────────────

def compute_read_speeds(loans_path: Path, reads_df: pd.DataFrame, year: int = 2025) -> pd.DataFrame:
    """
    Compute hours from borrow/checkout (timeline, converted from UTC to LOCAL_TZ)
    to the 'created_time' in the export (assumed local), filtered to completions in `year`
    and to titles with >= 300 pages.

    Returns a DataFrame sorted fastest-first with:
      ['title', 'author', 'library', 'borrowed', 'created_time', 'hours_to_finish']
    """
    if not Path(loans_path).exists() or reads_df.empty:
        return pd.DataFrame()

    # Completed reads anchored on CREATED TIME
    r = reads_df.copy()
    if not {"status", "name"}.issubset(r.columns):
        return pd.DataFrame()

    created_col = next((c for c in ["created_time", "created", "created_at"] if c in r.columns), None)
    if created_col is None:
        return pd.DataFrame()

    r["status"] = r["status"].astype(str).str.lower().str.strip()
    r[created_col] = _parse_created_series(r[created_col])
    r = r[(r["status"] == "complete") & (r[created_col].dt.year == year)].copy()
    if r.empty:
        return pd.DataFrame()

    # Filter out short books
    page_col = next((c for c in ["page_count", "pages", "length_pages"] if c in r.columns), None)
    if page_col:
        r[page_col] = pd.to_numeric(r[page_col], errors="coerce")
        r = r[r[page_col] >= 300]
    if r.empty:
        return pd.DataFrame()

    r["title_norm"] = r["name"].map(_canon_title)
    r["author_read"] = r.get("author", "")

    # Timeline: only borrow/checkout, convert UTC → local (naive)
    loans = pd.read_csv(loans_path)
    loans = _normalize_cols(loans)
    if "timestamp" not in loans.columns or "title" not in loans.columns:
        return pd.DataFrame()

    ts = pd.to_datetime(loans["timestamp"], errors="coerce", utc=True)
    loans["timestamp"] = ts.dt.tz_convert(LOCAL_TZ).dt.tz_localize(None)

    loans["title_norm"] = loans["title"].map(_canon_title)
    loans["library"] = loans.get("library", "").astype(str)

    act = loans.get("activity", "")
    act = act.astype(str).str.lower()
    borrows = loans[act.str.contains("borrow|checkout", na=False)].copy()
    borrows = borrows.dropna(subset=["timestamp"]).rename(columns={"timestamp": "borrowed"})
    if borrows.empty:
        return pd.DataFrame()

    # Join reads to borrows on title; keep borrows <= created_time
    merged = r.merge(borrows[["title_norm", "library", "borrowed"]], on="title_norm", how="inner")
    merged = merged[merged["borrowed"] <= merged[created_col]].copy()
    if merged.empty:
        return pd.DataFrame()

    # Keep latest borrow before created_time
    merged_sorted = merged.sort_values(["title_norm", created_col, "borrowed"])
    idx = merged_sorted.groupby(["title_norm", created_col])["borrowed"].idxmax()
    best = merged_sorted.loc[idx].copy()

    best["hours_to_finish"] = (best[created_col] - best["borrowed"]).dt.total_seconds() / 3600.0

    out = best[["name", "author_read", "library", "borrowed", created_col, "hours_to_finish"]].rename(
        columns={"name": "title", "author_read": "author", created_col: "created_time"}
    )

    return out.sort_values("hours_to_finish", ascending=True).reset_index(drop=True)


# ──────────────────────────────────────────────────────────────────────────────
# Percentile (Pew-style brackets with light interpolation)
# ──────────────────────────────────────────────────────────────────────────────

def estimate_percentile(total_books: int) -> int:
    """
    Estimate how a reader's yearly finished-book count compares to American adults.
    Table values based on a 2023-style bracket; we linearly interpolate between brackets.
    """
    percentile_table = [
        (0, 0),
        (1, 46),
        (2, 51),
        (3, 56),
        (4, 62),
        (5, 67),
        (6, 72),
        (7, 76),
        (8, 77),
        (9, 78),
        (10, 79),
        (15, 85),
        (20, 88),
        (30, 92),
        (40, 94),
        (50, 99),
    ]
    if total_books <= 0:
        return 0
    if total_books >= 50:
        return 99

    for i in range(1, len(percentile_table)):
        lo_books, lo_pct = percentile_table[i - 1]
        hi_books, hi_pct = percentile_table[i]
        if total_books <= hi_books:
            span = max(1, hi_books - lo_books)
            frac = (total_books - lo_books) / span
            return round(lo_pct + frac * (hi_pct - lo_pct))
    return 99


# ──────────────────────────────────────────────────────────────────────────────
# Main yearly metrics
# ──────────────────────────────────────────────────────────────────────────────

def compute_metrics(df: pd.DataFrame, year: int = 2025, loans_path: Path = LOANS_PATH) -> Metrics:
    """
    Compute all metrics for the given year.
    - df: normalized export DataFrame (see `load_data`)
    - year: target year (int)
    - loans_path: path to timeline CSV (for checkouts, DNFs, fastest reads)
    """
    m = Metrics()
    if df.empty or "status" not in df.columns or "finished" not in df.columns:
        return m

    # Prep & year filter (based on 'finished' date)
    df = df.copy()
    df["status"] = df["status"].astype(str).str.strip().str.lower()
    df["finished"] = pd.to_datetime(df["finished"], errors="coerce")
    df_year = df[df["finished"].dt.year == year].copy()

    # Novella flag
    genre_col_df_year = next((c for c in ["genre", "genres", "category"] if c in df_year.columns), None)
    if genre_col_df_year:
        df_year["is_novella"] = df_year[genre_col_df_year].astype(str).str.contains("novella", case=False, na=False)
    else:
        df_year["is_novella"] = False

    # Completed only (this year)
    completed = df_year[df_year["status"] == "complete"].copy()

    # Reading counts
    m.novella_count  = int(completed["is_novella"].sum())
    m.total_books    = int((~completed["is_novella"]).sum())
    m.total_finished = int(len(completed))
    m.percentile     = estimate_percentile(m.total_finished)

    # Books & DNFs from timeline (checkouts-based)
    try:
        loans = pd.read_csv(loans_path)
        loans = _normalize_cols(loans)

        ts = pd.to_datetime(loans.get("timestamp"), errors="coerce", utc=True)
        loans["timestamp"] = ts.dt.tz_convert(LOCAL_TZ).dt.tz_localize(None)

        act = loans.get("activity", "")
        act = act.astype(str).str.lower()
        borrows = loans[act.str.contains("borrow|checkout", na=False)].copy().dropna(subset=["timestamp"])

        borrows_year = borrows[borrows["timestamp"].dt.year == year].copy()
        if not borrows_year.empty:
            borrows_year["title_norm"] = borrows_year["title"].map(_canon_title)
            checkout_titles = set(borrows_year["title_norm"].dropna())
            completed_titles = set(completed["name"].map(_canon_title).dropna())

            m.books_checked_out = int(len(checkout_titles))
            m.dnfs = int(len(checkout_titles - completed_titles))
        else:
            m.books_checked_out = 0
            m.dnfs = 0
    except Exception:
        # Fallback to export if timeline is missing/unreadable
        m.books_checked_out = int(len(df_year))
        m.dnfs = int((df_year["status"] == "dnf").sum())

    # Savings: finished sum + avg finished cost * DNFs
    try:
        if "cost" in completed.columns:
            cost_series = completed["cost"].astype(str).str.strip()
            cost_series = cost_series.replace(
                {"": None, "nan": None, "None": None, "free": None, "Free": None}
            )
            cost_series = (
                cost_series
                .str.replace(r"[,$]", "", regex=True)
                .str.replace(r"\s*USD\s*", "", regex=True)
                .str.replace(r"[^\d.]", "", regex=True)
            )
            completed["cost_num"] = pd.to_numeric(cost_series, errors="coerce")
            valid_costs = completed["cost_num"].dropna()

            if not valid_costs.empty:
                avg_cost = valid_costs.mean()
                m.savings_finished = round(valid_costs.sum(), 2)
                m.savings_dnf = round(avg_cost * m.dnfs, 2)
                m.savings_combined = round(m.savings_finished + m.savings_dnf, 2)
    except Exception:
        pass  # leave savings at defaults if anything fails

    # Audiobook metrics
    aud = completed.copy()
    if "format" in aud.columns:
        aud["format"] = aud["format"].astype(str).str.strip().str.lower()
        aud = aud[aud["format"].str.contains("audiobook", na=False)]
    else:
        aud = aud.iloc[0:0].copy()

    if not aud.empty:
        aud["ab_hours"]   = pd.to_numeric(aud.get("ab_hours", 0), errors="coerce").fillna(0)
        aud["ab_minutes"] = pd.to_numeric(aud.get("ab_minutes", 0), errors="coerce").fillna(0)

        length_col = next((c for c in aud.columns if "audiobook_length" in c and "minute" in c), None)
        if length_col:
            aud[length_col] = pd.to_numeric(aud[length_col], errors="coerce").fillna(0)
            aud.loc[aud[length_col] == 0, length_col] = aud["ab_hours"] * 60 + aud["ab_minutes"]
            total_minutes = aud[length_col].sum()
        else:
            total_minutes = (aud["ab_hours"] * 60 + aud["ab_minutes"]).sum()

        m.finished_audiobook_length_2025 = round(total_minutes / 60.0, 2)

        # Biggest month by audiobook time
        aud["month_name"] = aud["finished"].dt.strftime("%B")
        monthly_hours = (aud.groupby("month_name")["ab_hours"].sum()
                         + (aud.groupby("month_name")["ab_minutes"].sum() / 60))
        if not monthly_hours.empty:
            m.biggest_month = monthly_hours.idxmax()
            m.biggest_month_hours = round(monthly_hours.max(), 1)

    # Top author metrics (completed audiobooks only)
    if not aud.empty:
        if "minutes" not in aud.columns:
            if length_col:
                aud["minutes"] = pd.to_numeric(aud[length_col], errors="coerce").fillna(0)
            else:
                aud["minutes"] = (
                    pd.to_numeric(aud.get("ab_hours", 0), errors="coerce").fillna(0) * 60
                    + pd.to_numeric(aud.get("ab_minutes", 0), errors="coerce").fillna(0)
                )

        aud["author"] = aud.get("author", "").astype(str).str.strip()
        m.authors_count = int(aud["author"].nunique())

        if m.authors_count > 0:
            agg = (
                aud.groupby("author", dropna=False)
                   .agg(top_author_books=("name", "count"),
                        top_author_minutes=("minutes", "sum"))
                   .reset_index()
                   .sort_values(["top_author_books", "top_author_minutes"], ascending=[False, False])
            )
            top_row = agg.iloc[0]
            m.top_author = str(top_row["author"]) if pd.notna(top_row["author"]) else "—"
            m.top_author_books = int(top_row["top_author_books"])
            m.top_author_minutes = float(top_row["top_author_minutes"])
            m.top_author_hours = round(m.top_author_minutes / 60.0, 1)

            # Top 2 titles for that author (by minutes desc; fall back to recency)
            top_author_reads = aud[aud["author"] == m.top_author].copy()
            if not top_author_reads.empty:
                if top_author_reads["minutes"].isna().all():
                    top_author_reads = top_author_reads.sort_values("finished", ascending=False)
                else:
                    top_author_reads = top_author_reads.sort_values("minutes", ascending=False)
                titles = [_display_title(str(t)) for t in top_author_reads["name"].head(2).tolist()]
                m.top_author_book_title_1 = titles[0] if len(titles) > 0 else ""
                m.top_author_book_title_2 = titles[1] if len(titles) > 1 else ""

    # Fastest reads (top 3)
    try:
        speeds = compute_read_speeds(loans_path, df, year=year)
        if not speeds.empty:
            first = speeds.iloc[0]
            m.fastest_title = _display_title(str(first["title"]))
            m.fastest_hours = float(first["hours_to_finish"])
            m.fastest_days  = round(m.fastest_hours / 24.0, 2)
            m.fastest_top3 = [
                {
                    "title": _display_title(str(row["title"])),
                    "author": str(row.get("author", "")),
                    "hours_to_finish": round(float(row["hours_to_finish"]), 2),
                }
                for _, row in speeds.head(3).iterrows()
            ]
        else:
            m.fastest_top3 = []
    except Exception:
        m.fastest_top3 = []

    # Genre metrics (completed set)
    genre_col_completed = next((c for c in ["genre", "genres", "category"] if c in completed.columns), None)
    if genre_col_completed:
        genres = (
            completed[genre_col_completed]
            .astype(str)
            .str.replace(r"[\[\]\']", "", regex=True)
            .str.split(r"[,;/]")
        )
        flat = [g.strip() for sublist in genres.dropna() for g in sublist if isinstance(g, str) and g.strip()]
        if flat:
            norm = [g.title() for g in flat]
            counts = pd.Series(norm).value_counts()
            m.genres_count = int(len(counts))  # number of unique genres
            m.top_genre = counts.idxmax() if not counts.empty else "—"

    return m
