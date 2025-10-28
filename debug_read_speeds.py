from pathlib import Path
import pandas as pd
from data import load_data, compute_read_speeds  # uses your current code

BOOKS = Path("libby-export.csv")
LOANS = Path("libbytimeline-all-loans,all.csv")
YEAR  = 2025

pd.set_option("display.max_colwidth", 200)

df = load_data(BOOKS)

print("\n=== READS (raw) ===")
print(df.shape, df.columns.tolist())
print(df.head(3))

# 1) Filter to completed reads in YEAR
r = df.copy()
r["status"]   = r["status"].astype(str).str.lower().str.strip()
r["finished"] = pd.to_datetime(r["finished"], errors="coerce", infer_datetime_format=True)
r_year = r[(r["status"] == "complete") & (r["finished"].dt.year == YEAR)].copy()
print("\nCompleted in year:", len(r_year))

# 2) Show a few titles we expect to match
print("\nSample finished titles:", r_year["name"].head(10).tolist())

# 3) Peek at LOANS
loans = pd.read_csv(LOANS)
print("\n=== LOANS (raw) ===")
print(loans.shape, loans.columns.tolist())
print(loans["activity"].dropna().str.lower().value_counts().head(10))
print(loans.head(3))

# 4) Try compute_read_speeds directly
speeds = compute_read_speeds(LOANS, df, year=YEAR)
print("\n=== SPEEDS (result) ===")
print(speeds.shape)
print(speeds.head(10))

# 5) If empty, diagnose title overlap
import re
_punct = re.compile(r"[^\w\s]")
_brackets = re.compile(r"(\[.*?\]|\(.*?\))")
def canon_title(s: str) -> str:
    if not isinstance(s, str): return ""
    s = s.lower().strip()
    s = _brackets.sub("", s)
    s = s.replace("—","-").replace("–","-")
    s = re.sub(r"\breread\b.*$", "", s).strip()
    s = _punct.sub(" ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

reads_set  = set(r_year["name"].map(canon_title))
loans_set  = set(pd.Series(loans["title"]).map(canon_title))

print("\nTitle overlap count:", len(reads_set & loans_set))

# 6) Show 10 reads with no matching loan title
missing = [t for t in sorted(reads_set) if t not in loans_set][:10]
print("\nExamples with NO loans title match:", missing)

# 7) For the first missing title, show nearby loans candidates (string contains)
if missing:
    cand = loans[loans["title"].str.contains(missing[0].split(" ")[0], case=False, na=False)]
    print(f"\nLoan candidates for '{missing[0]}':")
    print(cand[["title","timestamp","activity","library"]].head(10))
