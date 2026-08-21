"""Demo store generator — the controlled 40-product world (TECHSPEC §5, SCHEMA §5.3).

Deterministic under seed 42. Produces:
  demo-store/products.json          canonical fixture (wrapper: base_url, products, baseline_order)
  demo-store/site/catalog.json      canonical array (served statically)
  demo-store/site/p/{sku}.html      product pages (JSON-LD for rich/medium; absent for starved)
  demo-store/site/img/{sku}.svg     placeholder art
  demo-store/site/llms.txt          catalog index + agent guidance
  demo-store/site/index.html        storefront index

Normative constraints enforced here (generator fails loudly if violated):
  - 40 products, 4 categories x 10, tiers exactly 10 rich / 20 medium / 10 starved
  - baseline order = [rich, medium, starved, medium] x 10; intra-tier shuffle seed 42
  - anchors: sku_007 rich/bottles (modal) - sku_017 rich/bottles (schema example, verbatim copy)
    - sku_023 starved/backpacks at baseline position 19 (invisible hero)
  - starved products sit at category price-ladder deciles 5-7 (price never explains invisibility)
"""
from __future__ import annotations

import argparse
import html
import json
import random
from pathlib import Path

DEMO_ROOT = Path(__file__).resolve().parent
SITE_DIR = DEMO_ROOT / "site"
SEED = 42
TIER_BLOCK = ["rich", "medium", "starved", "medium"]

DEFAULT_BASE_URL = "https://demo.agentaudit.dev"

# ---------------------------------------------------------------------------
# Catalog definition (invented brands only). Field legend:
#   sku, title (listing title agents see), display_name (UI header name),
#   price_inr, description, category, tier,
#   tq/dq (title_quality / description_quality fixtures)
# ---------------------------------------------------------------------------
P = []


def p(sku, title, display_name, price, description, category, tier, tq, dq):
    P.append(
        {
            "id": sku,
            "title": title,
            "display_name": display_name,
            "price_inr": price,
            "description": description,
            "category": category,
            "tier": tier,
            "tq": tq,
            "dq": dq,
        }
    )


# --- bottles (10): 3 rich / 4 medium / 3 starved; ladder Rs.199-1499; starved at deciles 5-7 ---
p("sku_001", "CampusSip 650ml Sipper Bottle", "CampusSip 650ml", 199,
  "Lightweight 650ml sipper bottle for everyday college use. Leak-resistant flip cap, "
  "translucent body with volume markings, fits backpack side pockets.",
  "bottles", "medium", 0.58, 0.47)
p("sku_002", "FlexFuel 700ml Squeeze Bottle", "FlexFuel 700ml", 299,
  "Flexible squeeze bottle with fast-flow nozzle for workouts. 700ml capacity, easy-grip "
  "body, dishwasher-safe, available in multiple colours.",
  "bottles", "medium", 0.55, 0.45)
p("sku_003", "TrailSip 800ml Steel Sipper Bottle", "TrailSip 800ml", 449,
  "Sturdy steel sipper bottle for daily hydration. 800ml, rust-resistant interior, screw "
  "cap with carry loop, simple and reliable.",
  "bottles", "medium", 0.56, 0.46)
p("sku_004", "BrewMate 500ml Flask Bottle", "BrewMate 500ml", 599,
  "Compact 500ml flask that keeps coffee warm for hours. Screw lid, slim profile, "
  "stainless exterior, good for commutes.",
  "bottles", "medium", 0.54, 0.44)
p("sku_005", "Water Bottle", "Water Bottle", 649,
  "Good quality water bottle.", "bottles", "starved", 0.10, 0.08)
p("sku_017", "AquaSteel Pro 1L Insulated Bottle — Matte Black", "AquaSteel Pro 1L", 749,
  "Double-walled 18/8 steel; 24h cold, 12h hot; 290g; leak-proof cap; BPA-free.",
  "bottles", "rich", 0.90, 0.85)  # canonical schema example — copy pinned verbatim by docs
p("sku_006", "Steel Bottle", "Steel Bottle", 679,
  "Stainless steel bottle.", "bottles", "starved", 0.09, 0.07)
p("sku_008", "Insulated Bottle", "Insulated Bottle", 699,
  "Keeps water hot and cold.", "bottles", "starved", 0.11, 0.09)
p("sku_007", "HydroMax Elite 750ml Insulated Bottle — 24h Cold Vacuum Steel, Leak-Proof",
  "HydroMax Elite 750ml", 999,
  "Double-wall vacuum-insulated 750ml bottle in 18/8 food-grade steel keeps drinks cold "
  "for 24 hours and hot for 12. Powder-coated matte finish resists scratches and sweat; "
  "leak-proof twist cap with carry loop; 310g; BPA-free; fits standard car cup holders; "
  "lifetime warranty on insulation.",
  "bottles", "rich", 0.94, 0.88)  # the modal product
p("sku_009", "PeakChill 1.2L Insulated Jug — Wide-Mouth Handle, Condensation-Free",
  "PeakChill 1.2L", 1199,
  "Wide-mouth 1.2L insulated jug with soft-grip handle pours cleanly and keeps water cold "
  "through long summer sessions and team practices. 18/8 stainless liner, powder-coat "
  "exterior, silicone-sealed leak-proof lid, 1.1kg; condensation-free double-wall build; "
  "dishwasher-safe lid; ideal for courtside, campsites, and construction sites alike.",
  "bottles", "rich", 0.87, 0.84)

# --- headphones (10): 2 rich / 6 medium / 2 starved; ladder Rs.499-14999; starved at deciles 6-7 ---
p("sku_010", "BassBud Z2 Wired Earphones", "BassBud Z2", 499,
  "Wired earphones with punchy bass and inline mic. Three-button remote, tangle-flat "
  "cable, three ear-tip sizes in box.",
  "headphones", "medium", 0.57, 0.46)
p("sku_011", "AirDuet Buds TWS Earbuds", "AirDuet Buds", 899,
  "True wireless earbuds with charging case. Touch controls, decent battery life, "
  "Bluetooth 5.0, IPX4 splash resistance for workouts.",
  "headphones", "medium", 0.59, 0.48)
p("sku_012", "ThumpPods On-Ear Bluetooth Headphones", "ThumpPods", 1299,
  "On-ear Bluetooth headphones with deep bass. Foldable design, cushioned pads, aux "
  "fallback, up to 20 hours playback.",
  "headphones", "medium", 0.56, 0.45)
p("sku_013", "HushTone ANC Earbuds", "HushTone ANC", 1999,
  "ANC earbuds that cut bus and metro noise. Four mics, low-latency mode, wireless "
  "charging case, comfortable fit.",
  "headphones", "medium", 0.61, 0.49)
p("sku_014", "VoxPace Wireless Headset with Mic", "VoxPace Headset", 3499,
  "Wireless headset with boom mic for calls and classes. Mute button, USB dongle plus "
  "Bluetooth, padded headband.",
  "headphones", "medium", 0.58, 0.47)
p("sku_015", "ClarityLab M50 Wired Monitoring Headphones", "ClarityLab M50", 4999,
  "Wired monitoring headphones with neutral sound for studio work. Coiled cable, "
  "replaceable pads, robust build, 40mm drivers.",
  "headphones", "medium", 0.62, 0.51)
p("sku_016", "Wireless Headphones", "Wireless Headphones", 2499,
  "Wireless headphones with good sound.", "headphones", "starved", 0.10, 0.08)
p("sku_018", "Bluetooth Earbuds", "Bluetooth Earbuds", 2999,
  "Earbuds with charging case.", "headphones", "starved", 0.08, 0.07)
p("sku_019", "SkySilence Pro ANC Headphones — 40h Battery, LDAC, Multipoint",
  "SkySilence Pro", 8999,
  "Over-ear active noise-cancelling headphones tuned for long-haul focus. Hybrid ANC "
  "attenuates cabin and office noise; 40-hour battery with USB-C fast charge; multipoint "
  "Bluetooth 5.3 with LDAC; memory-foam earcups; foldable aluminium yokes; includes flight "
  "adapter and hard case; wear detection pauses playback the moment you take them off.",
  "headphones", "rich", 0.92, 0.86)
p("sku_020", "ApexResonance X1 Reference Headphones — Planar Magnetic, Open-Back",
  "ApexResonance X1", 12999,
  "Reference-grade planar-magnetic over-ear headphones with 98mm drivers, 15Hz-50kHz "
  "response, and low-distortion double-sided magnet arrays. Open-back design images widely; "
  "detachable balanced 2.5mm and 3.5mm cables; magnesium alloy frame; velour and "
  "protein-leather pads included; 320g without cable; scales beautifully with desktop amps.",
  "headphones", "rich", 0.91, 0.89)

# --- backpacks (10): 3 rich / 4 medium / 3 starved; ladder Rs.699-3999; starved at deciles 5-7 ---
p("sku_021", "UrbanTote 15L Daypack", "UrbanTote 15L", 699,
  "Simple 15L daypack for city errands. Water-resistant fabric, front zip pocket, padded "
  "shoulder straps, laptop sleeve up to 14 inches.",
  "backpacks", "medium", 0.57, 0.46)
p("sku_022", "CampusCarry 25L College Backpack", "CampusCarry 25L", 999,
  "25L college backpack with organiser panel. Fits notebooks, charger bricks, and a "
  "15-inch laptop; reinforced base; bottle pockets.",
  "backpacks", "medium", 0.58, 0.47)
p("sku_023", "Daypack", "TrailBuddy Daypack 22L", 1899,
  "Durable daypack for daily use.", "backpacks", "starved", 0.10, 0.09)  # invisible hero @ pos 19
p("sku_024", "TrailPack Lite 18L Hiking Daypack", "TrailPack Lite 18L", 1299,
  "Featherweight 18L hiking daypack for short trails. Breathable back panel, hip belt, "
  "trekking-pole loops, emergency whistle on chest strap.",
  "backpacks", "medium", 0.60, 0.49)
p("sku_025", "CommutePro 20L Laptop Backpack", "CommutePro 20L", 1599,
  "20L commuter backpack with quick-access top pocket. Water-repellent shell, luggage "
  "strap, reflective accents, padded 15.6-inch laptop bay.",
  "backpacks", "medium", 0.59, 0.48)
p("sku_026", "Backpack", "Backpack", 1699,
  "Spacious backpack for everyday use.", "backpacks", "starved", 0.09, 0.08)
p("sku_028", "Rucksack", "Rucksack", 2099,
  "Large rucksack for travel.", "backpacks", "starved", 0.08, 0.07)
p("sku_029", "RidgeLine 30L Trek Backpack — Rain Cover, Hydration-Ready, Ventilated Back",
  "RidgeLine 30L", 2499,
  "Trek-ready 30L backpack in ripstop nylon with rain cover stowed in the base pocket. "
  "Padded 16-inch laptop sleeve, hydration bladder sleeve with exit port, trekking-pole "
  "attachment, ventilated air-mesh back panel; 980g; whistle-buckle sternum strap; "
  "load-lifter straps pull weight off your shoulders on steep ascents; lifetime stitching "
  "guarantee.",
  "backpacks", "rich", 0.93, 0.87)
p("sku_030", "NomadVault 35L Travel Backpack — Anti-Theft Zips, USB Pass-Through",
  "NomadVault 35L", 2999,
  "Anti-theft travel backpack with lockable YKK zippers, hidden rear pocket, and RFID-safe "
  "valuables pouch. 35L clamshell opens flat for packing cubes; external USB pass-through "
  "(powerbank not included); water-repellent 900D shell; luggage pass-through strap; 1.25kg; "
  "fits 17-inch laptops; rear handle slides over suitcase trolleys for airport runs.",
  "backpacks", "rich", 0.90, 0.88)
p("sku_031", "SummitForge 45L Expedition Pack — Internal Frame, Rain Cover",
  "SummitForge 45L", 3499,
  "Expedition pack with adjustable internal frame, load-lifter straps, and ventilated hip "
  "belt transferring weight off shoulders. 45L main compartment with divider and "
  "sleeping-bag access; six compression straps; ice-tool loop; 1.6kg; rain cover included; "
  "hydration sleeve accepts 2L reservoirs; sized for week-long treks.",
  "backpacks", "rich", 0.89, 0.85)

# --- fitness (10): 2 rich / 6 medium / 2 starved; ladder Rs.299-2999; starved at deciles 5-6 ---
p("sku_027", "GripFlex Training Gloves", "GripFlex Gloves", 299,
  "Training gloves with padded palm and wrist wrap. Machine-washable, breathable back, "
  "sizes S-XL, good pull-up grip.",
  "fitness", "medium", 0.55, 0.45)
p("sku_032", "CoreFit Yoga Mat 6mm", "CoreFit Mat", 499,
  "6mm yoga mat with anti-slip texture. 183x61cm, carry strap included, cushions knees "
  "and wrists on hard floors.",
  "fitness", "medium", 0.56, 0.46)
p("sku_033", "PulseBand Fabric Resistance Band Set", "PulseBand Set", 699,
  "Set of five fabric resistance bands from light to extra-heavy. Non-roll design, door "
  "anchor included, colour-coded, workout guide inside.",
  "fitness", "medium", 0.58, 0.48)
p("sku_034", "FlexCage Mesh Gym Bag", "FlexCage Bag", 899,
  "Ventilated mesh gym bag with shoe compartment. 25L, water-resistant base, adjustable "
  "strap, zip pockets for kit.",
  "fitness", "medium", 0.54, 0.44)
p("sku_035", "Fitness Kit", "Fitness Kit", 1099,
  "Complete fitness kit for home.", "fitness", "starved", 0.09, 0.08)
p("sku_036", "Workout Set", "Workout Set", 1299,
  "Everything needed for workouts.", "fitness", "starved", 0.08, 0.07)
p("sku_037", "StrideTrack Skipping Rope with Counter", "StrideTrack Rope", 1499,
  "Skipping rope with built-in digital jump counter for daily cardio. Adjustable length, "
  "soft foam grips, smooth ball-bearing spin, batteries included in the box.",
  "fitness", "medium", 0.57, 0.47)
p("sku_038", "IronGrip Adjustable Dumbbell Pair 10kg", "IronGrip Dumbbells", 1799,
  "Adjustable dumbbell pair from 2-10kg each. Dial-a-weight plates, knurled handles, "
  "storage trays, floor-friendly rubber coating.",
  "fitness", "medium", 0.61, 0.50)
p("sku_039", "VitalStride Smart Jump Rope — App Sync, Rep Counting, 30-Day Battery",
  "VitalStride Smart Rope", 2199,
  "Smart skipping rope with bearing-smooth ballast handles that counts jumps, calories, "
  "and intervals in the VitalStride app over Bluetooth. Knurled aluminium handles; 3m "
  "adjustable steel-core rope, user-replaceable; 30-day battery life; offline mode stores "
  "sessions; supports family profiles and weekly goals.",
  "fitness", "rich", 0.90, 0.86)
p("sku_040", "ForgeMaster Home Gym Kit — 5-70kg Stackable Bands, Door Anchor",
  "ForgeMaster Gym Kit", 2699,
  "Complete doorway resistance system: stackable latex bands from 5-70kg, door anchor, "
  "ankle straps, and padded handles for 100+ exercises. Progressive-overload chart included; "
  "latex tested to 50,000 pulls; mesh travel bag included; replaces a full rack of dumbbells "
  "in a small hostel room.",
  "fitness", "rich", 0.88, 0.85)


# ---------------------------------------------------------------------------
def structured_data(item: dict) -> dict:
    tier = item["tier"]
    if tier == "rich":
        return {
            "jsonld_present": True,
            "fields_present": ["name", "price", "availability", "image", "brand", "aggregateRating"],
            "price_fresh": True,
            "title_quality": item["tq"],
            "description_quality": item["dq"],
        }
    if tier == "medium":
        return {
            "jsonld_present": True,
            "fields_present": ["name", "price"],
            "price_fresh": False,  # stale structured price per tier matrix
            "title_quality": item["tq"],
            "description_quality": item["dq"],
        }
    return {  # starved
        "jsonld_present": False,
        "fields_present": [],
        "price_fresh": None,
        "title_quality": item["tq"],
        "description_quality": item["dq"],
    }


def canonical(item: dict, base_url: str) -> dict:
    return {
        "id": item["id"],
        "title": item["title"],
        "display_name": item["display_name"],
        "category": item["category"],
        "price_inr": item["price_inr"],
        "description": item["description"],
        "image_url": None if item["tier"] == "starved" else f"{base_url}/img/{item['id']}.svg",
        "page_url": f"{base_url}/p/{item['id']}",
        "tier": item["tier"],
        "structured_data": structured_data(item),
    }


def build_baseline_order(products: list[dict]) -> list[str]:
    """Tier-block placement with intra-tier shuffle (seed 42), then anchor fixes."""
    rng = random.Random(SEED)
    by_tier: dict[str, list[str]] = {"rich": [], "medium": [], "starved": []}
    # iterate in stable sku order so the shuffle consumes deterministically
    for item in sorted(products, key=lambda x: x["id"]):
        by_tier[item["tier"]].append(item["id"])

    slots: dict[str, list[int]] = {"rich": [], "medium": [], "starved": []}
    for pos in range(1, 41):
        slots[TIER_BLOCK[(pos - 1) % 4]].append(pos)

    order: list[str | None] = [None] * 41  # 1-indexed
    for tier in ("rich", "medium", "starved"):
        ids = by_tier[tier][:]
        rng.shuffle(ids)
        for pos, sku in zip(slots[tier], ids):
            order[pos] = sku

    # Anchor: sku_023 must sit at baseline position 19 (a starved slot)
    hero = "sku_023"
    if hero not in by_tier["starved"]:
        raise AssertionError("anchor sku_023 must be starved tier")
    pos_hero = order.index(hero)
    if pos_hero != 19:
        order[pos_hero], order[19] = order[19], order[pos_hero]
    return order[1:]


def svg_for(item: dict) -> str:
    palette = {
        "bottles": ("#0ea5e9", "#0c4a6e"),
        "headphones": ("#8b5cf6", "#3b0764"),
        "backpacks": ("#f59e0b", "#78350f"),
        "fitness": ("#10b981", "#064e3b"),
    }
    c1, c2 = palette[item["category"]]
    label = html.escape(item["display_name"][:28])
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="480" height="480">'
        f'<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">'
        f'<stop offset="0%" stop-color="{c1}"/><stop offset="100%" stop-color="{c2}"/>'
        f"</linearGradient></defs>"
        f'<rect width="480" height="480" fill="url(#g)"/>'
        f'<text x="240" y="230" font-family="Arial" font-size="26" fill="#ffffff" '
        f'text-anchor="middle">{label}</text>'
        f'<text x="240" y="270" font-family="Arial" font-size="18" fill="#e2e8f0" '
        f'text-anchor="middle">{item["id"]} - {html.escape(item["category"])}</text>'
        f"</svg>"
    )


def jsonld_for(item: dict, base_url: str) -> str:
    """Rich: 6-field Product schema. Medium: name + price only. Starved: none."""
    data: dict
    if item["tier"] == "rich":
        data = {
            "@context": "https://schema.org",
            "@type": "Product",
            "name": item["title"],
            "image": f"{base_url}/img/{item['id']}.svg",
            "brand": {"@type": "Brand", "name": item["display_name"].split()[0]},
            "aggregateRating": {"@type": "AggregateRating", "ratingValue": "4.4", "reviewCount": "127"},
            "offers": {
                "@type": "Offer",
                "priceCurrency": "INR",
                "price": str(item["price_inr"]),
                "availability": "https://schema.org/InStock",
            },
        }
    elif item["tier"] == "medium":
        data = {
            "@context": "https://schema.org",
            "@type": "Product",
            "name": item["title"],
            "offers": {"@type": "Offer", "priceCurrency": "INR", "price": str(item["price_inr"])},
        }
    else:
        return ""
    return '<script type="application/ld+json">' + json.dumps(data) + "</script>"


def page_html(item: dict, base_url: str) -> str:
    price_line = f"₹{item['price_inr']:,}".replace(",", ",")
    img = (
        f'<img src="../img/{item["id"]}.svg" alt="{html.escape(item["title"])}" width="320">'
        if item["tier"] != "starved"
        else ""
    )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>{html.escape(item['title'])}</title>
{jsonld_for(item, base_url)}
<style>body{{font-family:system-ui;margin:2rem auto;max-width:640px;color:#111}} .price{{font-size:1.4rem;font-weight:600}}</style>
</head><body>
<p><a href="../index.html">← Store</a></p>
<h1>{html.escape(item['title'])}</h1>
{img}
<p class="price">Price: {price_line}</p>
<p>{html.escape(item['description'])}</p>
</body></html>"""


LLMS_TXT = """# AgentAudit Demo Store

A 40-product storefront (bottles, headphones, backpacks, fitness) built as a controlled
audit environment. Listings deliberately vary in data completeness.

## For autonomous agents
- Canonical machine-readable catalog: GET /catalog.json (array of products, prices in INR integers).
- Human/product pages live under /p/{sku}.
- Some listings expose complete structured data (schema.org JSON-LD) including price and
  availability; others expose less or none. Where structured price is absent, treat the
  listing as "price on request".
- Select exactly one product per task, or decline if nothing genuinely fits.
"""


def generate(base_url: str) -> dict:
    # ---- integrity assertions (fail loudly, never ship a broken fixture) ----
    assert len(P) == 40, f"expected 40 products, got {len(P)}"
    assert len({x['id'] for x in P}) == 40, "duplicate sku ids"
    for cat in ("bottles", "headphones", "backpacks", "fitness"):
        n = sum(1 for x in P if x["category"] == cat)
        assert n == 10, f"category {cat} has {n} products"
    tiers = [x["tier"] for x in P]
    assert tiers.count("rich") == 10 and tiers.count("medium") == 20 and tiers.count("starved") == 10

    by_id = {x["id"]: x for x in P}
    assert by_id["sku_007"]["tier"] == "rich" and by_id["sku_007"]["category"] == "bottles"
    assert by_id["sku_017"]["tier"] == "rich" and by_id["sku_017"]["category"] == "bottles"
    assert by_id["sku_023"]["tier"] == "starved" and by_id["sku_023"]["category"] == "backpacks"
    assert by_id["sku_023"]["price_inr"] == 1899

    # starved price-rank rule: within its category, starved sorts to deciles 5-7
    for cat in ("bottles", "headphones", "backpacks", "fitness"):
        ranked = sorted((x for x in P if x["category"] == cat), key=lambda x: x["price_inr"])
        for idx, item in enumerate(ranked, start=1):
            if item["tier"] == "starved":
                assert idx in (5, 6, 7), f"{item['id']} starved at decile {idx} in {cat}"

    baseline_order = build_baseline_order(P)
    assert len(baseline_order) == 40 and len(set(baseline_order)) == 40
    assert baseline_order[18] == "sku_023", "hero must sit at baseline position 19"
    for pos, sku in enumerate(baseline_order, start=1):
        assert by_id[sku]["tier"] == TIER_BLOCK[(pos - 1) % 4], f"block broken at {pos}"

    # ---- write outputs ----
    canon = [canonical(x, base_url) for x in sorted(P, key=lambda x: x["id"])]
    SITE_DIR.mkdir(parents=True, exist_ok=True)
    (SITE_DIR / "p").mkdir(exist_ok=True)
    (SITE_DIR / "img").mkdir(exist_ok=True)

    (SITE_DIR / "catalog.json").write_text(json.dumps(canon, indent=2), encoding="utf-8")
    (DEMO_ROOT / "products.json").write_text(
        json.dumps({"seed": SEED, "base_url": base_url, "products": canon,
                    "baseline_order": baseline_order}, indent=2),
        encoding="utf-8",
    )
    (SITE_DIR / "llms.txt").write_text(LLMS_TXT, encoding="utf-8")

    for item in P:
        (SITE_DIR / "img" / f"{item['id']}.svg").write_text(svg_for(item), encoding="utf-8")
        (SITE_DIR / "p" / f"{item['id']}.html").write_text(
            page_html(item, base_url), encoding="utf-8"
        )

    rows = "".join(
        f'<li><a href="p/{x["id"]}.html">{html.escape(x["title"])}</a> — '
        f'₹{x["price_inr"]:,} ({x["tier"]})</li>'.replace(",000,", ",000,")
        for x in sorted(P, key=lambda x: x["id"])
    )
    (SITE_DIR / "index.html").write_text(
        f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>AgentAudit Demo Store</title><style>body{{font-family:system-ui;max-width:720px;margin:2rem auto}}</style>
</head><body><h1>AgentAudit Demo Store</h1>
<p>40 products across bottles, headphones, backpacks, fitness. Machine-readable catalog:
<a href="catalog.json">catalog.json</a> · agent guidance: <a href="llms.txt">llms.txt</a></p>
<ul>{rows}</ul></body></html>""",
        encoding="utf-8",
    )
    return {"products": len(P), "baseline_first10": baseline_order[:10]}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Generate the AgentAudit demo store")
    ap.add_argument("--base-url", default=DEFAULT_BASE_URL)
    args = ap.parse_args()
    summary = generate(args.base_url)
    print(f"demo store generated: {summary['products']} products")
    print("baseline first 10:", " ".join(summary["baseline_first10"]))
