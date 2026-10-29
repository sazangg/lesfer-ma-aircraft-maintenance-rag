"""Build the evaluation set: about a hundred questions with reference answers and the evidence they need.

cases/cases.json holds 15 regression cases, one or two per part, each aimed at one known gap. This
file is for measuring: enough questions per type that a percentage means something, split into a
tuning set and a held-out set that nothing is tuned on.

Answers about the fleet are computed from anfa_history.py and the fleet register's data, the same
source the documents are written from. Answers about the regulations and guidance quote passages that
were checked against corpus/parsed/. Nothing here is written by a model.

Each question has:
    evidence          groups of source ids; a group is satisfied when any one of its sources reaches the model
    reference_answer  what a correct answer says
    verdict           yes or no, for questions that have one
    must_include      strings a correct answer contains (exact figures, registrations, dates)
    expected_status   answered, refused (the asker may not read the source), or not_in_documents

    uv run python scripts/build_eval.py
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import anfa_history as history  # noqa: E402
from build_anfa import EQUIPMENT, FLEET, TIME_CONTROLLED  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "cases" / "eval.json"
TODAY = history.END
ORDERS = history.work_orders()
CURRENT = {reg: hours for reg, _, _, _, hours, *_ in FLEET}
QUESTIONS: list[dict] = []


def ask(category: str, question: str, answer: str, evidence: list[list[str]], *, verdict: str | None = None,
        must: list[str] | None = None, status: str = "answered") -> None:
    item = {"category": category, "question": question, "reference_answer": answer, "evidence": evidence,
            "expected_status": status}
    if verdict:
        item["verdict"] = verdict
    if must:
        item["must_include"] = must
    QUESTIONS.append(item)


def h(value: float) -> str:
    return f"{value:,.1f}"


def long_date(day: date) -> str:
    return f"{day.day} {day.strftime('%B %Y')}"


def orders(reg: str, *kinds: str) -> list:
    return [o for o in ORDERS if o.reg == reg and (not kinds or o.kind in kinds)]


def record(o) -> list[str]:
    """A work order is found in the work order itself or in the aircraft's logbook extract."""
    return [o.source_id, f"LOG-{o.reg}"]


# --- Does this AD apply to this aircraft? -----------------------------------------------------------

APPLICABILITY_PAIRS = [
    ("2012-02-02", "CN-TFA"), ("2012-02-02", "CN-TFB"), ("2004-15-18", "CN-TFD"), ("2004-15-18", "CN-TFE"),
    ("2013-11-11", "CN-TFC"), ("2013-11-11", "CN-TFD"), ("2009-24-10", "CN-TFG"), ("2011-06-02", "CN-TFG"),
    ("2020-16-08", "CN-TFE"), ("2019-01-02", "CN-TFE"), ("2007-08-03", "CN-TFB"), ("2007-08-03", "CN-TFD"),
    ("2005-13-10", "CN-TFA"), ("2012-22-01", "CN-TFA"), ("2012-22-01", "CN-TFE"), ("2018-02-04", "CN-TFC"),
    ("2008-05-09", "CN-TFD"), ("2008-26-10", "CN-TFF"),
]
for ad, reg in APPLICABILITY_PAIRS:
    ok, reason = history.applies(ad, reg)
    model, serial = next((m, s) for r, m, s, *_ in FLEET if r == reg)
    why = reason.split(": ", 1)[1]
    answer = f"{'Yes' if ok else 'No'}. {reg} is a {model}, serial number {serial}. {why[0].upper()}{why[1:]}"
    if (ad, reg) == ("2013-11-11", "CN-TFC"):
        answer += (" Anfa applies the same 3,000-hour switch limit anyway (procedures manual 3.2). CN-TFC's AD compliance "
                   "record wrongly marks the AD as applicable.")
    evidence = [[f"AD-{ad.replace(' ', '-')}"], ["FLEET-2026-10", f"ADREC-{reg}"]]
    ask("applicability", f"Does AD {ad} apply to {reg}?", answer, evidence, verdict="yes" if ok else "no")

# --- Records ------------------------------------------------------------------------------------------

for reg in ("CN-TFA", "CN-TFC", "CN-TFE", "CN-TFG"):
    last = orders(reg, "100-hour", "annual")[-1]
    ask("records", f"When did {reg} last have a 100-hour or annual inspection, and at what airframe hours?",
        f"{last.kind.capitalize()} inspection on {long_date(last.day)}, at {h(last.hours)} airframe hours, work order {last.number}.",
        [record(last)], must=[h(last.hours)])

for reg in ("CN-TFA", "CN-TFD", "CN-TFB"):
    o = orders(reg, "engine overhaul")[0]
    ask("records", f"Who signed the return to service after {reg}'s engine overhaul, and when was it?",
        f"{o.inspector} (licence {history.INSPECTORS[o.inspector]}), on {long_date(o.day)}, work order {o.number}, "
        f"at {h(o.hours)} airframe hours.", [record(o)], must=[o.inspector])

UNSCHEDULED_QUESTIONS = [
    ("CN-TFC", date(2025, 1, 14), "What was done about CN-TFC's noisy starter?"),
    ("CN-TFE", date(2025, 6, 24), "Which work order fixed CN-TFE's pitot heat, and what was replaced?"),
    ("CN-TFB", date(2025, 2, 25), "Was the bird strike damage on CN-TFB repaired?"),
    ("CN-TFG", date(2024, 11, 5), "What caused the FADEC caution on CN-TFG in November 2024?"),
    ("CN-TFA", date(2026, 7, 14), "Was anything found after CN-TFA's hard landing?"),
    ("CN-TFD", date(2026, 9, 8), "Why was there water in CN-TFD's right tank?"),
]
for reg, day, question in UNSCHEDULED_QUESTIONS:
    o = next(o for o in orders(reg, "unscheduled") if o.day == day)
    ask("records", question, f"Work order {o.number}, {long_date(o.day)}: {' '.join(o.lines)}", [record(o)], must=[o.number])

switch = orders("CN-TFD", "oil pressure switch")[0]
ask("records", "How many hours did CN-TFD's previous oil pressure switch have when it was removed?",
    f"2,951.3 hours since installation, removed on {long_date(switch.day)} (work order {switch.number}).",
    [record(switch)], must=["2,951.3"])
ask("records", "Who approved CN-TFE's oil pressure switch replacement in 2021?",
    "A. Tazi, on the paper work order WO-2021-0544 of 30 August 2021.", [["WO-SCAN"]], must=["Tazi"])
ask("records", "When were CN-TFA's and CN-TFF's mufflers replaced under AD 2018-02-04?",
    "CN-TFA: 12 March 2018, after an inspection on 22 February 2018 found no leak, with A1754001-25 S/N 39274. "
    "CN-TFF: 23 February 2018, replaced in lieu of the inspection with A1754001-25 S/N 39281.",
    [["ADREC-CN-TFA"], ["ADREC-CN-TFF"]], must=["39274", "39281"])

# --- Calculations ---------------------------------------------------------------------------------

installed = {reg: hours for reg, part, *_, hours, _, _ in TIME_CONTROLLED if part == "Engine oil pressure switch"}
for reg in ("CN-TFA", "CN-TFB", "CN-TFC", "CN-TFD", "CN-TFF"):
    used = round(CURRENT[reg] - installed[reg], 1)
    source = "the procedures manual (3.2), since the serial number is outside AD 2013-11-11" if reg in ("CN-TFC", "CN-TFF") \
        else "AD 2013-11-11"
    evidence = [["FLEET-2026-10"]] + ([["PROC-R7"]] if reg in ("CN-TFC", "CN-TFF") else [])
    ask("calculation", f"How many hours remain before {reg}'s engine oil pressure switch reaches its limit?",
        f"{h(3000 - used)} hours: the 3,000-hour limit, from {source}, minus {h(used)} hours used "
        f"({h(CURRENT[reg])} now minus {h(installed[reg])} at installation).", evidence, must=[h(3000 - used)])

for reg in ("CN-TFB", "CN-TFD", "CN-TFF"):
    last = orders(reg, "100-hour", "annual")[-1]
    ask("calculation", f"At what airframe hours is {reg}'s next 100-hour inspection due?",
        f"{h(last.hours + 100)} hours: the last inspection ({last.kind}, {last.number}, {long_date(last.day)}) was at "
        f"{h(last.hours)} hours. 14 CFR 91.409(b) allows up to 10 hours more only while en route to the place of inspection.",
        [record(last)], must=[h(last.hours + 100)])

battery = history.FADEC_BATTERY[-1]
battery_order = next(o for o in orders("CN-TFG", "fadec battery") if o.day == battery)
ask("calculation", "When is CN-TFG's next FADEC backup battery replacement due?",
    f"By {long_date(history.add_calendar_months(battery, 12))}: AD 2011-06-02 requires replacement every 12 calendar months, "
    f"and the last one was on {long_date(battery)} ({battery_order.number}).",
    [record(battery_order) + ["ADREC-CN-TFG"]], must=[str(history.add_calendar_months(battery, 12).year)])

for reg in ("CN-TFG", "CN-TFE", "CN-TFC"):
    last = history.TRANSPONDER_TESTS[reg][-1]
    o = next(o for o in orders(reg, "transponder") if o.day == last)
    due = history.add_calendar_months(last, 24)
    ask("calculation", f"When are {reg}'s altimeter, static system, and transponder tests next due?",
        f"By {long_date(due)}: 14 CFR 91.411 and 91.413 require them within the preceding 24 calendar months, and they were "
        f"last done on {long_date(last)} ({o.number})." + (" That is this week." if due < date(2026, 11, 1) else ""),
        [record(o)], must=[long_date(due).split(" ", 1)[1]])

for reg in ("CN-TFE", "CN-TFA"):
    day = next(date.fromisoformat(d) for r, part, _, _, d, *_ in TIME_CONTROLLED if r == reg and part == "ELT battery")
    due = date(day.year + 6, day.month, day.day)
    ask("calculation", f"When does {reg}'s ELT battery need replacing?",
        f"By {long_date(due)}: installed {long_date(day)}, with a 6-year limit from the ELT manufacturer.",
        [["FLEET-2026-10"]], must=[long_date(due)])

annual = orders("CN-TFE", "annual")[-1]
ask("calculation", "When is CN-TFE's next annual inspection due?",
    f"By {long_date(history.add_calendar_months(annual.day, 12))}: the last annual was on {long_date(annual.day)} ({annual.number}), "
    "and 14 CFR 91.409(a) requires one within the preceding 12 calendar months.", [record(annual)],
    must=[long_date(history.add_calendar_months(annual.day, 12))])

ask("calculation", "How many hours has CN-TFD's engine run since its overhaul?",
    f"1,370.4 hours: it was overhauled at {h(history.OVERHAULS['CN-TFD'][1])} airframe hours on "
    f"{long_date(history.OVERHAULS['CN-TFD'][0])}, and the airframe is at 11,870.4 hours.",
    [["FLEET-2026-10"]], must=["1,370.4"])

# --- Lists and counts --------------------------------------------------------------------------------


def equipment_with(text: str) -> list[str]:
    return sorted({reg for reg, item, maker, model, *_ in EQUIPMENT if text in f"{item} {maker} {model}"})


kap = equipment_with("KAP 140")
ask("aggregation", "Which of our aircraft have a KAP 140 autopilot?", f"{' and '.join(kap)}.", [["FLEET-2026-10"]], must=kap)
gtx = equipment_with("GTX 330")
ask("aggregation", "Which aircraft have a Garmin GTX 330 transponder?", f"{', '.join(gtx)}.", [["FLEET-2026-10"]], must=gtx)
beni = sorted(reg for reg, *_, base, _ in FLEET if base == "Beni Mellal")
ask("aggregation", "Which aircraft are based in Beni Mellal?", f"{', '.join(beni)}.", [["FLEET-2026-10"]], must=beni)

overhauled = [o for o in ORDERS if o.kind == "engine overhaul" and o.day.year == 2025]
ask("aggregation", "Which aircraft had an engine overhaul in 2025?",
    "; ".join(f"{o.reg} ({long_date(o.day)}, {o.number})" for o in overhauled) + ".",
    [record(o) for o in overhauled], must=[o.reg for o in overhauled])

tfd_2025 = [o for o in orders("CN-TFD", "100-hour", "annual") if o.day.year == 2025]
ask("aggregation", "How many 100-hour and annual inspections did CN-TFD have in 2025?",
    f"{len(tfd_2025)}: " + ", ".join(o.number for o in tfd_2025) + ".",
    [record(o) for o in tfd_2025], must=[str(len(tfd_2025))])

for reg in ("CN-TFB", "CN-TFE"):
    applicable = [ad for ad, _ in history.ad_list() if history.applies(ad, reg)[0]]
    ask("aggregation", f"List the airworthiness directives that apply to {reg}.",
        f"{len(applicable)} directives: " + ", ".join(f"AD {ad}" for ad in applicable) + ".",
        [[f"ADREC-{reg}"]] + [[f"AD-{ad.replace(' ', '-')}"] for ad in applicable], must=applicable)

oil = [reg for reg in CURRENT if reg != "CN-TFG" and history.applies("2013-11-11", reg)[0]]
ask("aggregation", "Which of our aircraft fall under AD 2013-11-11?",
    f"{', '.join(oil)}. CN-TFC and CN-TFF are 172S above the serial number range; Anfa applies the same limit to them "
    "through the procedures manual. CN-TFG is a 172N.", [["AD-2013-11-11"], ["FLEET-2026-10"]], must=oil)

soon = sorted(reg for reg in installed if CURRENT[reg] - installed[reg] > 2900)
ask("aggregation", "Which aircraft have an oil pressure switch within 100 hours of its limit?",
    ", ".join(f"{reg} ({h(3000 - (CURRENT[reg] - installed[reg]))} hours left)" for reg in soon) + ". "
    "The procedures manual (3.2) says to plan the replacement at 2,900 hours. CN-TFE's figure uses the fleet register's "
    "installation hours, the lower of the two recorded (procedures manual 3.3).", [["FLEET-2026-10"], ["PROC-R7"]], must=soon)

tires = [o for o in ORDERS if o.day.year == 2025 and any(desc == "Main wheel tire" for _, desc, *_ in o.parts)]
ask("aggregation", "List every main wheel tire replacement in 2025, with its aircraft and work order.",
    "; ".join(f"{o.reg} ({o.number}, {long_date(o.day)})" for o in tires) + ".",
    [record(o) for o in tires], must=[o.number for o in tires])

fassi = [o for o in ORDERS if o.inspector == "R. El Fassi" and o.day.year == 2025]
ask("aggregation", "How many work orders did R. El Fassi sign for return to service in 2025?", f"{len(fassi)}.",
    [record(o) for o in fassi], must=[str(len(fassi))])

muffler = [reg for reg in CURRENT if history.applies("2018-02-04", reg)[0]]
ask("aggregation", "Which of our aircraft are affected by AD 2018-02-04?",
    "CN-TFA and CN-TFF had mufflers listed in figure 1; both were replaced in February and March 2018. CN-TFC's muffler, "
    "A1754001-23 S/N 34729, is one above the range 34721 to 34728. The fleet register still lists CN-TFF's old muffler.",
    [["AD-2018-02-04"], ["FLEET-2026-10"], ["ADREC-CN-TFA", "ADREC-CN-TFF"]], must=muffler)

# --- Regulations and guidance -----------------------------------------------------------------------

FACTS = [
    ("What happens if someone operates an aircraft that doesn't meet an applicable AD?",
     "Under 14 CFR 39.7, anyone who operates a product that does not meet the requirements of an applicable airworthiness "
     "directive is in violation of that section.", ["CFR-14-39"], ["39.7"]),
    ("Can we fly an aircraft to a repair facility when an AD has not been done yet?",
     "Possibly: under 14 CFR 39.23 the FAA may issue a special flight permit unless the AD states otherwise, and may add "
     "requirements or decline. 39.25: apply following 14 CFR 21.199.", ["CFR-14-39"], ["special flight permit"]),
    ("If an AD conflicts with the service bulletin it references, which one do we follow?",
     "The AD (14 CFR 39.27).", ["CFR-14-39"], ["39.27"]),
    ("Who can approve an alternative method of compliance with an AD?",
     "The office identified in the AD (14 CFR 39.19 and 39.21); proposals go through the principal inspector where there is one.",
     ["CFR-14-39"], []),
    ("Does a flight school aircraft need 100-hour inspections, and can the 100 hours be exceeded?",
     "Yes, under 14 CFR 91.409(b) for flight instruction for hire in an aircraft the instructor provides. The limit may be "
     "exceeded by not more than 10 hours while en route to a place where the inspection can be done, and the excess counts "
     "toward the next 100 hours.", ["CFR-14-91E"], ["10 hours"]),
    ("How often must the altimeter and static system be tested for IFR flight?",
     "Within the preceding 24 calendar months, to 14 CFR Part 43 appendices E and F (14 CFR 91.411).", ["CFR-14-91E"], ["24 calendar months"]),
    ("How long must the record of a 100-hour inspection be kept?",
     "Until the work is repeated or superseded by other work, or for 1 year after the work is performed (14 CFR 91.417(b)(1)).",
     ["CFR-14-91E"], ["1 year"]),
    ("How long must a repair station keep its work records?",
     "At least 2 years from the date the article was approved for return to service (14 CFR 145.219(c)).", ["CFR-14-145"], ["2 years"]),
    ("What does AC 39-7D say about recurring ADs and their intervals?",
     "Some ADs require repetitive inspections; an AD may allow the interval to be adjusted to coincide with Part 91 "
     "inspections, under conditions stated in the AD. Any other change goes through the AMOC process.", ["AC-39-7D"], ["AMOC"]),
    ("Can AC 43.13-2B be used as approved data for a major alteration?",
     "Yes, for non-pressurized areas of aircraft of 12,500 lbs gross weight or less, when the AC chapter, page, and paragraph are "
     "listed in block 8 of FAA Form 337 and the user has determined the conditions the AC lists are met.", ["AC-43.13-2B"], ["Form 337"]),
    ("Can a mechanic without an inspection authorization sign off an annual inspection?",
     "No. An annual inspection is performed by a mechanic holding an Inspection Authorization (IA), who may also approve "
     "major repairs and alterations for return to service.", ["AMTH-CH13"], ["Inspection Authorization"]),
    ("When is FAA Form 337 used?",
     "To document a major repair or major alteration, with supporting approved data. A Part 145 repair station may instead give "
     "a signed copy of the work order with a maintenance release for a major repair.", ["AMTH-CH2"], ["major"]),
    ("What engine and rated power does the Cessna 172S have?",
     "Lycoming IO-360-L2A, rated 180 horsepower at 2,700 rpm (type certificate data sheet 3A12, section XII).", ["TCDS-3A12"], ["180"]),
    ("What must a maintenance record entry contain?",
     "Under 14 CFR 43.9(a): a description of the work, the date it was completed, the name of the person who did it, and, if "
     "the work was approved for return to service, the signature, certificate number, and kind of certificate of the person "
     "approving it.", ["CFR-14-43"], ["43.9"]),
]
for question, answer, sources, must in FACTS:
    ask("regulation", question, answer, [sources], must=must)

# --- Exact identifiers ---------------------------------------------------------------------------------

ask("identifier", "Which AD covers AWI muffler P/N A1754001-23?",
    "AD 2018-02-04, for listed serial numbers of P/N A1754001-23 and A1754001-25.", [["AD-2018-02-04"]], must=["2018-02-04"])
ask("identifier", "What part is P/N 83278?",
    "The engine oil pressure switch, limited to 3,000 hours by AD 2013-11-11.", [["AD-2013-11-11", "FLEET-2026-10", "PROC-R7"]],
    must=["oil pressure switch"])
ask("identifier", "What is AD 2011-06-02 about?",
    "Cessna 172 airplanes modified by STC SA01303WI (Thielert diesel): install a FADEC backup battery, replace the AFM "
    "supplement, and replace the battery every 12 calendar months.", [["AD-2011-06-02"]], must=["FADEC"])
for o in (orders("CN-TFF", "unscheduled")[0], orders("CN-TFG", "unscheduled")[1], orders("CN-TFB", "transponder")[-1]):
    ask("identifier", f"What was work order {o.number}?",
        f"{o.reg}, {long_date(o.day)}, at {h(o.hours)} airframe hours: {' '.join(o.lines)}", [[o.source_id]], must=[o.reg])

# --- Access ------------------------------------------------------------------------------------------

for question in ("What do we charge a customer for an oil pressure switch?",
                 "What is Anfa's hourly labour rate for the flight school?",
                 "What does a KAP 140 exchange unit cost us?"):
    ask("access", question, "A mechanic may not read the price list (management only): the assistant says it can't answer.",
        [], status="refused")

# --- Not in the documents ----------------------------------------------------------------------------

for question in ("What is the propeller overhaul interval on CN-TFA?",
                 "Which airworthiness directives apply to a Piper PA-28-161?",
                 "When is CN-TFH's next inspection due?",
                 "What torque do the propeller bolts on a 172S take?",
                 "What did the quality manager decide about CN-TFE's switch installation hours?",
                 "How many landings does CN-TFB have?"):
    ask("unanswerable", question, "The documents don't say: the assistant says so instead of guessing.", [],
        status="not_in_documents")

# --- Records that disagree ----------------------------------------------------------------------------

ask("discrepancy", "At what airframe hours was CN-TFE's current oil pressure switch installed?",
    "The records disagree: the fleet register says 10,560.2 hours; the work order WO-2021-0544 and the AD compliance record "
    "say 10,650.2. The procedures manual (3.3) says to use the lower figure until the quality manager resolves it.",
    [["FLEET-2026-10"], ["WO-SCAN", "ADREC-CN-TFE"]], must=["10,560.2", "10,650.2"])
ask("discrepancy", "Does CN-TFF still have an affected AWI muffler installed?",
    "The records disagree: the fleet register lists muffler A1754001-25 S/N 38190, which AD 2018-02-04 covers; the AD "
    "compliance record says it was replaced on 23 February 2018 with S/N 39281. Check the aircraft and correct the register.",
    [["FLEET-2026-10"], ["ADREC-CN-TFF"]], must=["38190", "39281"])
ask("discrepancy", "Is CN-TFC's AD compliance record right about AD 2013-11-11?",
    "No. It marks the AD as applicable, but CN-TFC's serial number 172S11290 is above the AD's 172S range (to 172S11256). "
    "The 3,000-hour switch limit applies through the procedures manual (3.2), not the AD.",
    [["ADREC-CN-TFC"], ["AD-2013-11-11"], ["FLEET-2026-10"]], verdict="no", must=["172S11290"])

# --- What replaced what ----------------------------------------------------------------------------------

for old, new in (("2000-04-01", "2013-11-11"), ("2008-03-02", "2012-02-02"), ("2004-10-15", "2005-01-19")):
    ask("superseded", f"Is AD {old} still in effect?", f"No: AD {new} superseded it.", [[f"AD-{new}", f"AD-{old}"]],
        verdict="no", must=[new])
ask("superseded", "Which advisory circular on maintenance records is current, AC 43-9C or AC 43-9D?",
    "AC 43-9D. AC 43-9C was cancelled on 22 September 2025.", [["AC-43-9D", "AC-43-9C"]], must=["43-9D"])


def main() -> None:
    by_category: Counter = Counter()
    for n, item in enumerate(QUESTIONS, 1):
        index = by_category[item["category"]]
        by_category[item["category"]] += 1
        item["id"] = f"E{n:03d}"
        item["split"] = "holdout" if index % 5 in (1, 3) else "tune"  # 40% of each category held out
    out = {"about": __doc__.split("\n\n")[0] + " See scripts/build_eval.py.",
           "as_of": TODAY.isoformat(),
           "questions": [{"id": q.pop("id"), "split": q.pop("split"), **q} for q in QUESTIONS]}
    OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    splits = Counter(q["split"] for q in out["questions"])
    print(f"{len(QUESTIONS)} questions ({splits['tune']} tune, {splits['holdout']} held out) -> {OUT.relative_to(ROOT).as_posix()}")
    for category, count in by_category.items():
        print(f"  {category:14} {count}")


if __name__ == "__main__":
    main()
