from dataclasses import dataclass
from typing import List, Optional

@dataclass
class Slide:
    key: str
    title: Optional[str] = None      # main line (h3)
    subtitle: Optional[str] = None   # kicker/eyebrow (h1)
    notes: Optional[str] = None
    body: Optional[str] = None
    layout: str = "center"    

def get_slides() -> List[Slide]:
    return [
        Slide(
            key="intro",
            subtitle="It’s that time of year again…",
            title="Are you ready to see the damage?",
            body="Life moves fast—luckily, we took notes."
        ),
        Slide(
            key="finished",
            subtitle="It’s not a competition… but nice work.",
            title="You finished <b>{full_books}</b> books this year.",
            body="And <b>{novellas}</b> novellas! That’s more than <b>{percentile}%</b> of readers.",
            notes="""Based on data from <a href="https://today.yougov.com/entertainment/articles/48239-54-percent-of-americans-read-a-book-this-year">YouGov 2023</a>."""
        ),
    
        Slide(
            key="totals",
            subtitle="Speaking of dedication...",
            title="You spent <b>{listening_hours}</b> hours listening.<br>" \
                    "That's <b>{listening_hours_days}</b> days straight!",
            body="""Well, really only <b>{real_hours}</b> hours — we know you love that <b>{speedup_factor}×</b> speed button.<br><br>""",
        ),
        Slide(
            key="monthly",
            subtitle="Your ears worked overtime",
            title="""Your biggest month was <b>{biggest_month}</b>, with <b>{biggest_month_hours}</b> hours.""",
            body="Keep the momentum going!"
        ),
        Slide(
            key="top_books",
            subtitle="Couldn’t hit pause, could you?",
            title="Your fastest listen was <b>{fastest_title}</b>, which took you only <b>{fastest_hours}</b> hours!",
            body="No judgement here..."
        ),
        Slide(
            key="top_books_2",
            subtitle="Great job keeping it moving! ",
            title="Your fastest reads this year were:",
            body="{fastest_top3_str}",
            notes="Calculated by Libby checkout time to time marked in database as 'finished'."
        ),
        Slide(
            key="authors_1",
            title="You listened to <b>{authors_count}</b> different authors this year, but one really caught your ear.",
            body="Hint: you finished <b>{top_author_books}</b> books by them..."
        ),
        Slide(
            key="authors_2",
            title="You spent <b>{top_author_minutes}</b> minutes with <b>{top_author}</b> this year",
            body="Let me remind you, they wrote <b>{top_author_book_title_1}</b> and <b>{top_author_book_title_2}</b>"
        ),
        Slide(
            key="genres",
            subtitle="You contain multitudes",
            title="You explored <b>{genres_count}</b> genres – but you mostly stuck with <b>{top_genre}</b>.",
            body="Let’s try to branch out more next year."
        ),
        Slide(
            key="dnfs",
            subtitle="Not every book was a hit.",
            title="You picked up <b>{books_checked_out}</b> books this year, and DNF’d <b>{dnfs}</b> of them.",
            body="That's okay—life’s too short to read bad books."
        ),
        Slide(
            key="library_savings",
            subtitle="Look at you supporting local libraries.",
            title="You saved <b>${savings}</b> by borrowing from Libby.",
            body="Your wallet says thank you!"
        ),
        Slide(
            key="library_savings_2",
            subtitle="All the stories, none of the receipts.",
            title="Buying every book would’ve cost <b>${savings_finished}</b>—<br>plus another <b>${savings_dnf}</b> for your DNFs.",
            notes="Estimates based on average paperback prices from Barnes & Noble."
        ),
        Slide(
            key="goodbye",
            subtitle="Until next year.",
            title="Same time, same TBR?",
            body="Thanks for reading & listening 💖"
        ),
        Slide(
            key="shareable",
            subtitle="Make it internet official.",
            title="Tap to export a shareable post.",
        ),
    ]
