"""Builds data/benchmark.json: 50 hand-written posts for the fictional brand Nourish Daily.
15 clean posts, 27 posts with planted issues the rules are designed to catch, and 8 posts with paraphrased
or Hinglish issues that only the optional AI layer can catch (kept on purpose to report real weak spots)."""
import json
from pathlib import Path

LONG = ("We are very happy to share with all of our friends and followers that our new oat bar is now available at "
        "every campus stall this week.")
rows = []


def add(text, planted=None, channel="Instagram post", has_image=False, alt=""):
    rows.append({"channel": channel, "text": text, "has_image": has_image, "alt_text": alt, "planted": planted or []})


def P(rule, cat, quote="", layer="rules"):
    return {"rule_ids": [rule] if rule else [], "category": cat, "quote": quote, "layer": layer}


# --- clean (15)
for t, ch in [("Meet the Nourish Daily oat bar. Each bar has 8 g of protein and costs Rs 49.", "Instagram post"),
              ("Made with whole oats and no added preservatives. A calm, tasty start to your morning.", "Instagram post"),
              ("Nourish Daily was founded in 2019 by a small team that loves simple food.", "Website"),
              ("Each bar has 190 kcal. Pair it with fruit for a light snack. #HealthySnacks", "Instagram post"),
              ("Our weekend market stall is open from 10 am. Come and say hello.", "Instagram post"),
              ("Thank you for one year of kind messages. We read every one of them.", "Instagram post"),
              ("Aaj ka snack simple rakhiye. Nourish Daily oat bar, whole oats se bana.", "Instagram post"),
              ("Partnered with a local gym for our launch week. #ad", "Influencer post"),
              ("Our oat bar is made with whole oats. Read the ingredient list on the pack for details.", "Website"),
              ("Hello everyone, our new flavour is coming soon. We will share the details next week.", "Email"),
              ("One bar costs Rs 49. Ask us about bulk orders for college events.", "Email"),
              ("No added preservatives. The lab report is available on request.", "Website"),
              ("Tired of heavy breakfasts? Try a light oat bar with 8 g of protein.", "Instagram post"),
              ("Our team tasted six flavours before choosing this one. Tell us what you think.", "Instagram post"),
              ("Nourish Daily is open on Sundays too. See you at the stall.", "Instagram post")]:
    add(t, channel=ch)

# --- planted, catchable by rules (27)
add("Cheap and tasty oat bars for students.", [P("T-1", "terminology", "Cheap")])
add("Try NourishDaily today. Each bar has 8 g of protein.", [P("T-2", "terminology", "NourishDaily")])
add("Hey guys, our new oat bar is here.", [P("T-3", "terminology", "guys")])
add("The best oat bar in town. Made with whole oats.", [P("C-1", "claims", "best")])
add("#1 snack for students.", [P("C-1", "claims", "#1")])
add("Guaranteed to keep you full. Each bar has 8 g of protein.", [P("C-2", "claims", "Guaranteed")])
add("100% natural ingredients in every bar.", [P("C-2", "claims", "100% natural")])
add("Risk-free trial pack this week.", [P("C-2", "claims", "Risk-free")])
add("This bar helps you lose weight fast.", [P("C-3", "claims", "lose weight")])
add("Clinically proven to boost your energy.", [P("C-3", "claims", "Clinically proven")])
add("Each bar has 12 g of protein.", [P("F-1", "facts", "12 g of protein")])
add("One bar costs Rs 59.", [P("F-2", "facts", "Rs 59")])
add("Nourish Daily was founded in 2017.", [P("F-3", "facts", "founded in 2017")])
add("Only 150 calories per bar.", [P("F-5", "facts", "150 calories")])
add("Diwali special: flat 20% off on all bars.", [P("F-4", "facts", "Diwali special")])
add("Our Diwali offer is back this week.", [P("F-4", "facts", "Diwali offer")])
add("98% of customers love us.", [P("V-1", "facts", "98%")])
add("4 out of 5 students prefer our bar.", [P("V-1", "facts", "4 out of 5")])
add("Partnered with a fitness creator for our launch. Each bar has 8 g of protein.", [P("D-1", "disclosure", "Partnered with")], "Influencer post")
add("Gifted bars to our favourite creators this week.", [P("D-1", "disclosure", "Gifted")], "Influencer post")
add("Our new bar is here!!! Each bar has 8 g of protein.", [P("TN-2", "tone", "!!!")])
add("An amazing bar for your morning.", [P("TN-1", "tone", "amazing")])
add("FRESHLY baked oat bars at the stall today.", [P("TN-3", "tone", "FRESHLY")])
add("Snack smart with #healthysnacksforyou today.", [P("AC-1", "accessibility", "#healthysnacksforyou")])
add(LONG, [P("AC-2", "accessibility", "We are very happy")])
add("Meet our new oat bar.", [P("AC-3", "accessibility")], has_image=True, alt="")
add("Our stall at the college fest.", [P("AC-3", "accessibility")], has_image=True, alt="bar")

# --- planted, paraphrased or Hinglish: expected to need the AI layer (8)
add("Nothing else on the shelf even comes close to our oat bar.", [P(None, "claims", "Nothing else on the shelf even comes close", "ai")])
add("Ekdum zabardast bar, sabse badhiya snack in town.", [P(None, "claims", "sabse badhiya snack in town", "ai")])
add("Eat one every morning and watch the belly fat disappear.", [P(None, "claims", "watch the belly fat disappear", "ai")])
add("Doctors recommend it to every patient.", [P(None, "claims", "Doctors recommend it to every patient", "ai")])
add("Packed with double the protein of any other bar.", [P(None, "facts", "double the protein of any other bar", "ai")])
add("Honestly, you will lose your mind over how good this tastes.", [P(None, "tone", "you will lose your mind", "ai")])
add("Festival season bonanza: 20 percent off until 15 Nov 2025.", [P("F-4", "facts", "20 percent off until 15 Nov 2025", "ai")])
add("Bhai, yeh bar khaoge toh pagal ho jaoge, kya mast cheez hai.", [P(None, "tone", "pagal ho jaoge", "ai")])

assert len(rows) == 50, len(rows)
items = []
for i, r in enumerate(rows, 1):
    r = dict(r, id="B-%02d" % i, clean=not r["planted"])
    items.append(r)
out = Path(__file__).resolve().parent.parent / "data" / "benchmark.json"
out.write_text(json.dumps({"brand": "Nourish Daily (fictional)", "items": items}, ensure_ascii=False, indent=1), encoding="utf-8")
print("wrote", out, len(items), "items;", sum(i["clean"] for i in items), "clean")
