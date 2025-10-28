# test_metrics.py
from pathlib import Path
from data import load_data, compute_metrics

BOOKS = Path("libby-export.csv")
LOANS = Path("libbytimeline-all-loans,all.csv")

df = load_data(BOOKS)

print("🔍 Columns in CSV:")
print(df.columns.tolist())

# Run metric calculation (pass loans path!)
m = compute_metrics(df, year=2025, loans_path=LOANS)

print("\n🎧 Audiobook debug info:")
print(f"TEST BIGGEST MONTH: {m.biggest_month}")
print(f"TEST BIGGEST MONTH HOURS: {m.biggest_month_hours}")
print(f"Books (non-novella): {m.total_books}")

print("\n SAVINGS:")
print("hours_to_finish:", m.savings_combined)
print("days_to_finish:", m.savings_finished)
print("top3:", m.savings_dnf)
