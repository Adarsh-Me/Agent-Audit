"""Generate the 20 persona JSON files — verbatim from SCHEMA §3.2 (normative).

Run once: python backend/scripts/gen_personas.py
The null-plausible set {P04, P09, P10, P20} is fixed; changing it invalidates the
coverage metric's design and requires a doc version bump.
"""
import json
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "app" / "engine" / "personas"

PERSONAS = [
    ("P01", "Budget Student", "Watches every rupee; function over frills.",
     "cheapest decent water bottle for daily college use", 300, False),
    ("P02", "Gift Buyer", "Wants a safe gift that lands well.",
     "gift for a runner friend", 2000, False),
    ("P03", "Spec Hound", "Compares specs methodically; battery life decides.",
     "best battery-life earbuds", 3500, False),
    ("P04", "Eco Buyer", "Sustainability-first; walks away rather than compromise.",
     "most sustainably made bottle; price secondary", None, True),
    ("P05", "Commuter", "Needs laptop + gym in one bag, daily.",
     'backpack fitting 15" laptop + gym gear', 3000, False),
    ("P06", "Premium Seeker", "Buys the best; budget is a formality.",
     "best headphones in the store, budget flexible", 15000, False),
    ("P07", "Deal Hunter", "Researches, trusts value signals.",
     "best value-for-money item in this store", None, False),
    ("P08", "Urgent Buyer", "Speed over perfection, needs it now.",
     "any reasonable water bottle, fastest delivery", 1000, False),
    ("P09", "Brand Loyalist", "Sticks to recognizable names only.",
     "prefer well-known brands", 5000, True),
    ("P10", "Minimalist", "Plain and understated only.",
     "plain, understated design, nothing flashy", 2500, True),
    ("P11", "Fitness Newcomer", "Wants simple starter gear, no jargon.",
     "starter fitness gear", 1500, False),
    ("P12", "Parent", "Buys for a 12-year-old; durability first.",
     "durable backpack for a 12-year-old", 1200, False),
    ("P13", "Podcast Listener", "Comfort over 4h+ sessions decides.",
     "comfortable headphones for 4h+ listening sessions", 4000, False),
    ("P14", "Gym Regular", "Daily-use, practical, replaceable.",
     "shaker/gym bottle for daily use", 800, False),
    ("P15", "Trekker", "Day-hike capacity and weight matter.",
     "hydration setup for day hikes", 2000, False),
    ("P16", "WFH Professional", "Mic quality and all-day comfort.",
     "headphones for long video calls", 5000, False),
    ("P17", "Gift-Card Spender", "Maximizes value within a fixed card.",
     "spend a ₹1,000 gift card well", 1000, False),
    ("P18", "Comparison Shopper", "Cross-category value hunter.",
     "single best overall value across all categories", None, False),
    ("P19", "Trend Follower", "Goes with popularity and ratings.",
     "whatever's most popular / best-rated", 3000, False),
    ("P20", "Skeptic", "Buys only with clear warranty/returns.",
     "only products with clear warranty or return info", 4000, True),
]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for pid, name, summary, task, budget, null_plausible in PERSONAS:
        payload = {
            "id": pid,
            "name": name,
            "profile_summary": summary,
            "task": task,
            "budget_inr": budget,
            "null_plausible": null_plausible,
        }
        (OUT / f"{pid}.json").write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    print(f"wrote {len(PERSONAS)} persona files to {OUT}")


if __name__ == "__main__":
    main()
