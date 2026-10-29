"""Anfa's maintenance history for the Tadla fleet: the one source the records and the evaluation answers come from.

Each aircraft's airframe hours follow straight lines between fixed points (delivery, the dates the fleet
register and the scanned work orders already state, and 26 October 2026). Everything else is derived
from those lines: 100-hour and annual inspections, engine overhauls, recurring tests, unscheduled
repairs, the work order numbers, the logbook entries, and each aircraft's AD compliance record.

build_anfa.py writes the documents from this module; build_eval.py computes the evaluation answers
from it. Neither writes a number by hand that this module can compute.

Three disagreements between records are deliberate, as in a real shop's files. They are listed here
for the reader of this script and never stated in the documents:

    D1  CN-TFE's oil pressure switch: the fleet register says 10,560.2 airframe hours at installation;
        the scanned work order WO-2021-0544 and the AD compliance record say 10,650.2.
    D2  CN-TFF's muffler: the AD compliance record says the affected muffler (S/N 38190) was replaced
        in February 2018; the fleet register still lists S/N 38190.
    D3  CN-TFC's AD compliance record marks AD 2013-11-11 as applicable. It isn't: the serial number is
        above the directive's range. The 3,000-hour limit applies through the procedures manual (3.2).
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
START, END = date(2024, 1, 1), date(2026, 10, 26)  # work orders and logbook extracts cover this window

# --- Airframe hours ---------------------------------------------------------------------------

# Engine overhauls in the window: (date, airframe hours). The hours follow from the fleet register's
# engine time since overhaul: airframe total time minus time since overhaul.
OVERHAULS = {
    "CN-TFE": (date(2024, 10, 21), 12400.0), "CN-TFA": (date(2025, 4, 23), 8500.0), "CN-TFG": (date(2025, 8, 24), 14350.0),
    "CN-TFD": (date(2025, 8, 25), 10500.0), "CN-TFB": (date(2026, 3, 17), 8000.0),
}
OVERHAUL_SHOP = "Souss Engine Overhaul, Agadir"

# (date, airframe hours). The first point is delivery; the others are figures the documents state.
ANCHORS = {
    "CN-TFA": [(date(2003, 6, 16), 0.0), (date(2021, 1, 19), 4755.3), (date(2024, 2, 14), 7210.4), (END, 10140.6)],
    "CN-TFB": [(date(2006, 4, 20), 0.0), (date(2023, 5, 9), 5880.0), (END, 8455.1)],
    "CN-TFC": [(date(2013, 9, 10), 0.0), (date(2022, 11, 21), 3350.7), (date(2026, 10, 6), 6184.9), (END, 6210.3)],
    "CN-TFD": [(date(2003, 11, 5), 0.0), (date(2024, 1, 1), 8905.6), (date(2025, 3, 3), 9940.2), (END, 11870.4)],
    "CN-TFE": [(date(1999, 8, 12), 0.0), (date(2020, 11, 25), 9810.0), (date(2021, 8, 30), 10650.2), (END, 13520.8)],
    "CN-TFF": [(date(2017, 5, 30), 0.0), (date(2022, 7, 18), 2410.5), (END, 3980.0)],
    "CN-TFG": [(date(1978, 4, 3), 0.0), (date(2011, 3, 15), 9870.0), (date(2024, 1, 1), 13494.0), (END, 14960.2)],
}
for _reg, _point in OVERHAULS.items():
    ANCHORS[_reg] = sorted(ANCHORS[_reg] + [_point])
LYCOMING = {"CN-TFA", "CN-TFB", "CN-TFC", "CN-TFD", "CN-TFE", "CN-TFF"}
ANNUAL_MONTH = {"CN-TFA": 3, "CN-TFB": 6, "CN-TFC": 9, "CN-TFD": 1, "CN-TFE": 11, "CN-TFF": 5, "CN-TFG": 7}


def hours_at(reg: str, day: date) -> float:
    points = ANCHORS[reg]
    for (d0, h0), (d1, h1) in zip(points, points[1:]):
        if d0 <= day <= d1:
            return round(h0 + (h1 - h0) * (day - d0).days / (d1 - d0).days, 1)
    raise ValueError(f"{reg}: no hours for {day}")


def date_at(reg: str, hours: float) -> date:
    """The last day on which the airframe had not yet passed these hours."""
    points = ANCHORS[reg]
    for (d0, h0), (d1, h1) in zip(points, points[1:]):
        if h0 <= hours <= h1:
            return d0 + timedelta(days=int((hours - h0) / (h1 - h0) * (d1 - d0).days))
    raise ValueError(f"{reg}: never at {hours} hours")


# --- People and tools -------------------------------------------------------------------------

MECHANICS = ["Y. Alaoui", "S. Idrissi", "H. Ouazzani", "M. Chraibi", "N. Berrada"]
INSPECTORS = {"A. Tazi": "MA-B1-0457", "K. Bennani": "MA-B1-0212", "R. El Fassi": "MA-B1-0618"}
WRENCHES = ["T-014", "T-022", "T-031", "T-037"]
STATION = {"CN-TFC": "Beni Mellal", "CN-TFF": "Beni Mellal", "CN-TFG": "Beni Mellal"}  # the others: Casablanca

# --- Work orders --------------------------------------------------------------------------------


@dataclass
class WorkOrder:
    reg: str
    day: date
    kind: str            # 100-hour, annual, oil pressure switch, engine overhaul, fadec battery, transponder, unscheduled
    request: str
    lines: list[str]
    parts: list[tuple[str, str, int, str]] = field(default_factory=list)  # part number, description, quantity, serial number
    number: str = ""
    hours: float = 0.0
    mechanic: str = ""
    inspector: str = ""
    scanned: bool = False  # paper only: in work-orders-scanned.pdf, not printed from the system

    @property
    def source_id(self) -> str:
        return "WO-SCAN" if self.scanned else self.number


# The three paper work orders of work-orders-scanned.pdf, as build_anfa.py draws them.
SCANNED = [
    ("WO-2021-0544", "CN-TFE", date(2021, 8, 30), "oil pressure switch", "Y. Alaoui", "A. Tazi"),
    ("WO-2024-0071", "CN-TFA", date(2024, 2, 14), "oil pressure switch", "S. Idrissi", "A. Tazi"),
    ("WO-2026-0388", "CN-TFC", date(2026, 10, 6), "unscheduled", "Y. Alaoui", "K. Bennani"),
]

# Discrepancies an inspection can find: (finding, corrective action, parts). Lycoming-only ones are marked.
FINDINGS = [
    ("Left main tire worn to the wear limit.", "Replaced left main tire.", [("6.00-6-6PLY", "Main wheel tire", 1, "")], False),
    ("Right main tire worn to the wear limit.", "Replaced right main tire.", [("6.00-6-6PLY", "Main wheel tire", 1, "")], False),
    ("Left brake linings at minimum thickness.", "Replaced left brake linings.", [], False),
    ("Spark plugs eroded.", "Cleaned, gapped, and rotated all eight spark plugs.", [], True),
    ("Spark plugs worn beyond limits.", "Replaced all eight spark plugs.", [("REM37BY", "Spark plug", 8, "")], True),
    ("Nose strut extension low.", "Serviced nose strut with hydraulic fluid and air.", [], False),
    ("Alternator belt tension low.", "Adjusted alternator belt tension per maintenance manual.", [], True),
    ("Left cabin door seal torn.", "Replaced left cabin door seal.", [], False),
    ("Exhaust gasket leaking at cylinder 3.", "Replaced exhaust gasket at cylinder 3.", [], True),
    ("Induction air filter dirty.", "Replaced induction air filter.", [], False),
    ("Elevator trim tab free play at the limit.", "Replaced trim tab actuator rod end bearings; free play within limits.", [], False),
    ("Corrosion on battery box.", "Removed corrosion, treated and painted battery box; neutralized battery area.", [], False),
]

# Repairs between inspections: (registration, date, request, work performed, parts).
UNSCHEDULED = [
    ("CN-TFD", date(2024, 3, 12), "Nose wheel shimmy on landing roll.",
     ["Shimmy damper worn. Replaced shimmy damper; nose gear torque links checked for free play."], []),
    ("CN-TFB", date(2024, 4, 9), "Ammeter shows a discharge in cruise.",
     ["Alternator belt worn and glazed. Replaced alternator belt; tension set per maintenance manual.",
      "Ground run: charging normal."], []),
    ("CN-TFE", date(2024, 5, 28), "Autopilot disconnects in turbulence.",
     ["Found a loose pin in the KAP 140 roll servo connector. Repaired connector.",
      "Ground test of the autopilot satisfactory."], []),
    ("CN-TFA", date(2024, 6, 21), "Left magneto drop 220 rpm at run-up.",
     ["Found left magneto timing at 22 degrees before top dead centre. Retimed to 25 degrees per engine data plate.",
      "Run-up: left magneto drop 80 rpm, within limits."], []),
    ("CN-TFC", date(2024, 7, 30), "Right brake soft.",
     ["Bled right brake system. Replaced right brake linings."], []),
    ("CN-TFF", date(2024, 9, 17), "Avionics cooling fan noisy.",
     ["Replaced avionics cooling fan. G1000 NXi system test satisfactory."], []),
    ("CN-TFG", date(2024, 11, 5), "FADEC caution lamp on during run-up.",
     ["Downloaded FADEC data: intermittent signal from rail pressure sensor B.",
      "Cleaned and secured connector. FADEC test passed. Data sent to Technify."], []),
    ("CN-TFA", date(2024, 12, 2), "Left fuel quantity indication erratic.",
     ["Cleaned and secured the connector at the left fuel quantity sender. Indication checked at full and empty."], []),
    ("CN-TFC", date(2025, 1, 14), "Starter engages noisily.",
     ["Replaced starter with exchange unit. Ground run satisfactory."], [("LW-15472", "Starter (exchange)", 1, "")]),
    ("CN-TFB", date(2025, 2, 25), "Bird strike on the left wing leading edge, outboard.",
     ["Inspected leading edge: dent 30 mm across, no cracks, within the structural repair manual's limits.",
      "No repair required."], []),
    ("CN-TFG", date(2025, 3, 26), "Gearbox oil level low at preflight.",
     ["Found a seep at the gearbox drain plug. Replaced sealing ring; topped up gearbox oil. Leak check satisfactory."], []),
    ("CN-TFD", date(2025, 5, 20), "Oil leak at cylinder 2 rocker cover.",
     ["Replaced rocker cover gasket, cylinder 2. Torque per maintenance manual. Wrench T-031."], []),
    ("CN-TFE", date(2025, 6, 24), "Pitot heat inoperative.",
     ["Pitot heater element open circuit. Replaced pitot tube assembly. Pitot heat check satisfactory."], []),
    ("CN-TFF", date(2025, 7, 8), "Left main tire flat-spotted after hard braking.",
     ["Replaced left main tire and tube."], [("6.00-6-6PLY", "Main wheel tire", 1, "")]),
    ("CN-TFA", date(2025, 9, 30), "Cabin heat not working.",
     ["Cabin heat control cable disconnected at the heater valve. Reconnected and safetied; checked full travel."], []),
    ("CN-TFC", date(2025, 11, 18), "Landing light inoperative.", ["Replaced landing light lamp."], []),
    ("CN-TFD", date(2025, 12, 9), "Static wick missing on the left aileron.", ["Installed new static wick."], []),
    ("CN-TFE", date(2026, 1, 20), "Right cabin door hard to latch.", ["Adjusted and lubricated right door latch."], []),
    ("CN-TFF", date(2026, 2, 10), "Left front seat belt webbing frayed.", ["Replaced left front seat belt."], []),
    ("CN-TFB", date(2026, 4, 16), "Oil seep at oil cooler hose after engine reinstallation.",
     ["Tightened oil cooler hose fitting. Torque per maintenance manual. Wrench T-022. Leak check satisfactory."], []),
    ("CN-TFG", date(2026, 6, 2), "Engine load display 92% in climb, below normal.",
     ["Induction air filter partly blocked by debris. Replaced air filter. Load check satisfactory."], []),
    ("CN-TFA", date(2026, 7, 14), "Hard landing reported by the instructor.",
     ["Hard landing inspection per maintenance manual: main gear legs, attach fittings, firewall, and nose gear checked.",
      "No damage found."], []),
    ("CN-TFD", date(2026, 9, 8), "Water found in the right tank sump at preflight.",
     ["Right fuel cap gasket cracked. Replaced gasket; drained sumps until clear."], []),
]

# Altimeter, static system, and transponder tests (14 CFR 91.411 and 91.413): every 24 calendar months.
TRANSPONDER_TESTS = {
    "CN-TFA": [date(2022, 5, 17), date(2024, 5, 14), date(2026, 5, 12)],
    "CN-TFB": [date(2022, 9, 8), date(2024, 9, 3), date(2026, 8, 25)],
    "CN-TFC": [date(2023, 3, 21), date(2025, 3, 18)],
    "CN-TFD": [date(2023, 11, 7), date(2025, 11, 4)],
    "CN-TFE": [date(2022, 12, 6), date(2024, 12, 3)],
    "CN-TFF": [date(2023, 6, 13), date(2025, 6, 10)],
    "CN-TFG": [date(2022, 10, 11), date(2024, 10, 8)],  # the next one is due by 31 October 2026
}

# FADEC backup battery on CN-TFG (AD 2011-06-02): replaced every 12 calendar months.
FADEC_BATTERY = [date(2023, 9, 5), date(2024, 8, 27), date(2025, 8, 19), date(2026, 8, 11)]

# Oil pressure switch replacements printed from the system (the others are on paper, or before the window).
SWITCH_REPLACEMENTS = {"CN-TFD": (date(2025, 3, 3), 2951.3)}  # date, hours on the switch removed


def end_of_month(year: int, month: int) -> date:
    first_next = date(year + (month == 12), month % 12 + 1, 1)
    return first_next - timedelta(days=1)


def add_calendar_months(day: date, months: int) -> date:
    """Due date of a calendar-month interval: the last day of the month, `months` later."""
    index = day.month - 1 + months
    return end_of_month(day.year + index // 12, index % 12 + 1)


def _inspection(reg: str, day: date, annual: bool, rng: random.Random, recent: list[str]) -> WorkOrder:
    lines = []
    if annual:
        lines.append("Annual inspection per 14 CFR 91.409(a) and the scope and detail of 14 CFR Part 43 Appendix D, "
                     "using the Cessna 172 inspection checklist.")
        lines.append("ELT inspected per 14 CFR 91.207(d): installation, battery date, operation, and radiated signal.")
    else:
        lines.append("100-hour inspection per 14 CFR 91.409(b), using the Cessna 172 inspection checklist.")
    parts = []
    if reg in LYCOMING:
        compression = ", ".join(f"{rng.randint(70, 78)}/80" for _ in range(4))
        lines.append(f"Changed engine oil and filter. Compression check, cylinders 1 to 4: {compression}.")
        parts.append(("CH48110-1", "Oil filter", 1, ""))
    else:
        lines.append("Changed engine oil and filter per the Technify maintenance manual. Gearbox oil level checked.")
    pool = [f for f in FINDINGS if (reg in LYCOMING or not f[3]) and f[0] not in recent]
    for finding, action, used, _ in rng.sample(pool, rng.choice([0, 1, 1, 2, 2, 3])):
        lines.append(f"Discrepancy: {finding} Corrective action: {action}")
        parts.extend(used)
        recent[:] = (recent + [finding])[-6:]  # the same wear doesn't come back at the next few inspections
    lines.append("Aircraft found airworthy after correction of the discrepancies listed." if len(lines) > 3
                 else "No discrepancies found. Aircraft found airworthy.")
    kind = "annual" if annual else "100-hour"
    request = "Annual inspection." if annual else "100-hour inspection."
    return WorkOrder(reg, day, kind, request, lines, parts)


def _inspections(reg: str, rng: random.Random) -> list[WorkOrder]:
    orders, recent = [], []
    last = hours_at(reg, START) - rng.uniform(10, 85)
    year = START.year
    annual = date(year, ANNUAL_MONTH[reg], rng.randint(5, 25))
    while True:
        due = last + rng.uniform(91, 99.5)
        if due > ANCHORS[reg][-1][1]:
            hundred = END + timedelta(days=1)
        else:
            hundred = date_at(reg, due)
        if annual <= hundred + timedelta(days=20):  # an annual due soon is done instead of the 100-hour
            annual = min(annual, hundred)
            if annual >= END:
                break
            orders.append(_inspection(reg, annual, True, rng, recent))
            last = hours_at(reg, annual)
            year += 1
            annual = date(year, ANNUAL_MONTH[reg], rng.randint(5, 25))
        else:
            if hundred >= END:
                break
            orders.append(_inspection(reg, hundred, False, rng, recent))
            last = hours_at(reg, hundred)
    return orders


def _scheduled() -> list[WorkOrder]:
    orders = []
    for reg, (day, _) in OVERHAULS.items():
        orders.append(WorkOrder(reg, day, "engine overhaul", "Engine due for overhaul.", [
            "Removed engine for overhaul. Engine sent to the Technify factory for overhaul." if reg == "CN-TFG"
            else f"Removed engine for overhaul. Engine sent to {OVERHAUL_SHOP}.",
            "Reinstalled the overhauled engine, same serial number. Engine time since overhaul reset to 0.0.",
            "Ground run and leak check satisfactory. Engine logbook updated.",
        ]))
    for reg, tests in TRANSPONDER_TESTS.items():
        for day in tests:
            if START <= day < END:
                orders.append(WorkOrder(reg, day, "transponder", "Altimeter, static system, and transponder tests due.", [
                    "Static system test and altimeter test per 14 CFR 91.411 and Part 43 Appendix E.",
                    "Transponder test per 14 CFR 91.413 and Part 43 Appendix F.",
                    "All tests within limits. Next tests due within 24 calendar months.",
                ]))
    for day in FADEC_BATTERY:
        if START <= day < END:
            orders.append(WorkOrder("CN-TFG", day, "fadec battery", "FADEC backup battery due (AD 2011-06-02).", [
                "Replaced FADEC backup battery per AD 2011-06-02. Battery test satisfactory.",
                "Next replacement due within 12 calendar months.",
            ]))
    for reg, (day, removed_at) in SWITCH_REPLACEMENTS.items():
        orders.append(WorkOrder(reg, day, "oil pressure switch", "Engine oil pressure switch at its limit.", [
            "Replaced engine oil pressure switch with new, zero-time switch P/N 83278, per AD 2013-11-11.",
            f"Removed switch P/N 83278 at {removed_at:,.1f} hours since installation.",
            "Ground run: oil pressure indication normal, no leaks. Torque per maintenance manual. Wrench T-037.",
        ], [("83278", "Engine oil pressure switch", 1, "")]))
    for reg, day, request, lines, parts in UNSCHEDULED:
        orders.append(WorkOrder(reg, day, "unscheduled", request, lines, parts))
    return orders


def _number(orders: list[WorkOrder], rng: random.Random) -> None:
    """System numbers run per year over the whole shop; the fleet's work orders are a share of them."""
    per_day = {2024: 1.55, 2025: 1.5, 2026: 1.36}
    fixed = {(reg, day): number for number, reg, day, *_ in SCANNED}
    last = {}
    for order in sorted(orders, key=lambda o: (o.day, o.reg)):
        key = (order.reg, order.day)
        if order.scanned:
            order.number = fixed[key]
        else:
            n = max(last.get(order.day.year, 0) + 1, round(order.day.timetuple().tm_yday * per_day[order.day.year]) + rng.randint(0, 2))
            order.number = f"WO-{order.day.year}-{n:04d}"
        n = int(order.number[-4:])
        assert n > last.get(order.day.year, 0), order.number
        last[order.day.year] = n


def work_orders() -> list[WorkOrder]:
    """Every work order in the window, digital and scanned, in date order."""
    rng = random.Random(2026)
    orders = [o for reg in ANCHORS for o in _inspections(reg, random.Random(f"{reg}-inspections"))]
    orders += _scheduled()
    for number, reg, day, kind, mechanic, inspector in SCANNED:
        if START <= day < END:
            orders.append(WorkOrder(reg, day, kind, "", [], number=number, mechanic=mechanic, inspector=inspector, scanned=True))
    orders.sort(key=lambda o: (o.day, o.reg, o.kind))
    for order in orders:
        order.hours = hours_at(order.reg, order.day)
        if not order.scanned:
            order.mechanic = rng.choice(MECHANICS)
            order.inspector = rng.choice(list(INSPECTORS))
    _number(orders, rng)
    return orders


# --- Logbook entries ----------------------------------------------------------------------------

SCANNED_ENTRIES = {
    "WO-2024-0071": "Replaced engine oil pressure switch, new zero-time P/N 83278, per AD 2013-11-11 (g)(6). Ground run satisfactory.",
    "WO-2026-0388": "Muffler AWI P/N A1754001-23 S/N 34729 inspected for cracks after a carbon monoxide alert: none found. "
                    "CO detector card replaced.",
}


def logbook_entry(order: WorkOrder) -> str:
    if order.scanned:
        return SCANNED_ENTRIES[order.number]
    if order.kind in ("100-hour", "annual"):
        first = order.lines[0].split(", using")[0]
        fixes = [l.split("Corrective action: ")[1] for l in order.lines if l.startswith("Discrepancy:")]
        return " ".join([first + ".", *fixes, "Oil and filter changed."]).replace("..", ".")
    return " ".join(order.lines)


# --- AD applicability and compliance ------------------------------------------------------------

SUBJECTS = {
    "97-12-06": "Gascolator and tailpipe clearance to the cowling",
    "98-01-01": "Alternate static air source placards and valve",
    "98-02-05": "Aeroquip engine exhaust muffler",
    "98-13-41": "Aileron control cable routing in the center console",
    "98-14-07": "Lower forward doorpost bulkhead rivets",
    "98-25-03": "Right wing wiring routing (airplanes without autopilot)",
    "99-18-14": "Elevator control system, modification kit MK172-27-01",
    "2000-04-01": "Engine oil pressure switch P/N 77041",
    "2001-06-17": "Engine idle speed and fuel mixture setting",
    "2003-24-13": "KAP 140 autopilot software",
    "2004-10-15": "Garmin GTX 330 transponder software",
    "2004-15-18": "KAP 140 autopilot software",
    "2005-01-19": "Garmin GTX 33 and GTX 330 transponder software",
    "2005-05-53 R1": "Flight control system inspection",
    "2005-13-10": "Main electrical power junction box 40-amp circuit breakers",
    "2006-17-04": "Engine compartment fuel hose end fitting torque",
    "2007-05-10": "Crew seat back cylinder lock assemblies",
    "2007-08-03": "Engine compartment fuel hose end fitting torque",
    "2008-02-18": "BRS parachute system",
    "2008-03-02": "Fuel return line chafing",
    "2008-05-09": "Crew seat base and back attach brackets",
    "2008-10-02": "Alternate static air source selector valve P/N 2013142-18",
    "2008-26-10": "Alternate static air source selector valve placard",
    "2009-24-10": "TAE 125-01 engines",
    "2010-04-06": "TAE 125-01 engines",
    "2011-06-02": "FADEC backup battery, airplanes modified by STC SA01303WI",
    "2012-02-02": "Fuel return line chafing",
    "2012-22-01": "Fuel return line chafing (airplanes with SB04-28-03)",
    "2013-03-15": "Fuel return line support clamps",
    "2013-11-11": "Engine oil pressure switch, 3,000-hour limit",
    "2018-02-04": "AWI mufflers P/N A1754001-23 and A1754001-25",
    "2019-01-02": "Aspen EFD software 2.9 with FIS-B weather",
    "2020-16-08": "Aspen EFD1000 software 2.10 and 2.10.1 without independent backup instruments",
}

SUPERSEDED = {"2000-04-01": "2013-11-11", "2003-24-13": "2004-15-18", "2004-10-15": "2005-01-19",
              "2006-17-04": "2007-08-03", "2008-03-02": "2012-02-02"}

# Why each AD does or doesn't apply: {ad: {registration: reason}}. A reason starting with "Yes" applies.
# Any registration not listed gets the AD's default (the "*" entry).
APPLICABILITY = {
    "97-12-06": {"*": "No: 172R serial numbers 17280001 to 17280081 only."},
    "98-01-01": {"*": "No: 172R serial numbers up to 17280301 and 182S only."},
    "98-02-05": {"*": "No: 172R serial numbers up to 17280305 with an Aeroquip muffler only."},
    "98-13-41": {"*": "No: 172R serial numbers up to 17280475, and 17280506, only."},
    "98-14-07": {"*": "No: listed 172R serial numbers up to 17280138 only."},
    "98-25-03": {"*": "No: five listed 172R serial numbers only."},
    "99-18-14": {"*": "No: listed 172R serial numbers up to 17280096 only."},
    "2001-06-17": {"*": "Yes: all 172R and 172S.", "CN-TFG": "No: 172R and 172S only; CN-TFG is a 172N."},
    "2004-15-18": {"*": "No: no KAP 140 autopilot installed.",
                   "CN-TFE": "Yes: KAP 140 P/N 065-00176-5402, serial number 17280744 in range.",
                   "CN-TFD": "No: KAP 140 P/N 065-00176-7702 installed, but serial number 17281201 is above the 172R range (to 17281130)."},
    "2005-01-19": {"*": "No: G1000 transponder delivered with software later than the affected versions.",
                   "CN-TFA": "Yes: GTX 330.", "CN-TFD": "Yes: GTX 330.", "CN-TFG": "Yes: GTX 330.",
                   "CN-TFE": "No: no GTX 33 or GTX 330 installed."},
    "2005-05-53 R1": {"*": "No: three 172R and listed 172S serial numbers 172S9774 to 172S9793 only."},
    "2005-13-10": {"*": "No: serial number outside 172R 17281186 to 17281232 and 172S 172S9476 to 172S9770.",
                   "CN-TFA": "Yes: serial number 172S9488 in range.", "CN-TFD": "Yes: serial number 17281201 in range.",
                   "CN-TFG": "No: 172R and 172S only."},
    "2007-05-10": {"*": "No: serial number outside 172R 17280001 to 17281262 and 172S 172S8001 to 172S9994.",
                   "CN-TFA": "Yes: serial number in range.", "CN-TFD": "Yes: serial number in range.",
                   "CN-TFE": "Yes: serial number in range.", "CN-TFG": "No: 172R and 172S only."},
    "2007-08-03": {"*": "No: serial number outside the listed 172R and 172S ranges.",
                   "CN-TFB": "Yes: serial number 172S10237 in range (172S9809 to 172S10349).",
                   "CN-TFG": "No: 172R and 172S only."},
    "2008-02-18": {"*": "No: no BRS parachute system installed."},
    "2008-05-09": {"*": "No: serial number outside the listed 172R and 172S ranges.",
                   "CN-TFB": "Yes: serial number 172S10237 in range (172S9621 to 172S10310).",
                   "CN-TFD": "No: serial number 17281201 is below the 172R range (from 17281211).",
                   "CN-TFG": "No: 172R and 172S only."},
    "2008-10-02": {"*": "No: no P/N 2013142-18 selector valve installed."},
    "2008-26-10": {"*": "Yes: delivered between 1 January 1993 and 31 March 2008.",
                   "CN-TFC": "No: delivered after 31 March 2008; no replacement P/N 2013142-18 installed.",
                   "CN-TFF": "No: delivered after 31 March 2008; no replacement P/N 2013142-18 installed.",
                   "CN-TFG": "No: delivered before 1 January 1993; no replacement P/N 2013142-18 installed."},
    "2009-24-10": {"*": "No: Lycoming engine.", "CN-TFG": "No: engine is a TAE 125-02-99, not a TAE 125-01."},
    "2010-04-06": {"*": "No: Lycoming engine.", "CN-TFG": "No: engine is a TAE 125-02-99, not a TAE 125-01."},
    "2011-06-02": {"*": "No: not modified by STC SA01303WI.", "CN-TFG": "Yes: 172N modified by STC SA01303WI, TAE 125-02-99."},
    "2012-02-02": {"*": "No: serial number outside the four groups.",
                   "CN-TFB": "Yes: serial number 172S10237 in group 2 (172S9491 to 172S10489).",
                   "CN-TFD": "Yes: serial number 17281201 in group 1 (17281188 to 17281390).",
                   "CN-TFA": "No: serial number 172S9488 is below group 2 (from 172S9491).",
                   "CN-TFG": "No: 172R and 172S only."},
    "2012-22-01": {"*": "No: serial number outside 172R 17280001 to 17281187 and 172S 172S8001 to 172S9490.",
                   "CN-TFA": "Yes: serial number 172S9488 in range, SB04-28-03 and kit MK172-28-01 incorporated in 2005.",
                   "CN-TFE": "No: serial number in range, but SB04-28-03 and kit MK172-28-01 not incorporated.",
                   "CN-TFG": "No: 172R and 172S only."},
    "2013-03-15": {"*": "No: serial number outside 172R 17281573 to 17281616 and 172S 172S11074 to 172S11193.",
                   "CN-TFG": "No: 172R and 172S only."},
    "2013-11-11": {"*": "Yes: serial number in range.",
                   "CN-TFC": "No: serial number 172S11290 is above the 172S range (to 172S11256).",
                   "CN-TFF": "No: serial number 172S11845 is above the 172S range (to 172S11256).",
                   "CN-TFG": "No: 172R and 172S only."},
    "2018-02-04": {"*": "No: no affected AWI muffler installed.",
                   "CN-TFA": "Yes: muffler A1754001-25 S/N 34640 in figure 1.",
                   "CN-TFF": "Yes: muffler A1754001-25 S/N 38190 in figure 1.",
                   "CN-TFC": "No: muffler A1754001-23 S/N 34729 is not in figure 1 (range 34721 to 34728)."},
    "2019-01-02": {"*": "No: no Aspen display installed.", "CN-TFE": "No: Aspen EFD1000 software 2.10.1, not 2.9."},
    "2020-16-08": {"*": "No: no Aspen display installed.",
                   "CN-TFE": "Yes: EFD1000 PFD P/N 910-00001-011, software 2.10.1, no standby attitude indicator."},
}

# How each applicable AD was met: (registration or "*", date, method, recurring, next due).
# Dates before 2016 come from the previous operators' records.
COMPLIANCE = {
    ("2001-06-17", "*"): ("delivery", "Idle speed and mixture checked and set; POH procedures inserted.", None),
    ("2001-06-17", "CN-TFA"): ("delivery", "Idle speed and mixture checked and set; POH procedures inserted.", None),
    ("2001-06-17", "CN-TFE"): (date(2001, 5, 14), "Idle speed and mixture checked and set; POH procedures inserted.", None),
    ("2004-15-18", "CN-TFE"): (date(2004, 10, 6), "KAP 140 software updated to SW MOD 03/01; part number sticker and M decal attached.", None),
    ("2005-01-19", "CN-TFA"): (date(2005, 3, 22), "GTX 330 software upgraded from 3.04 to 3.06.", None),
    ("2005-01-19", "CN-TFD"): (date(2005, 4, 12), "GTX 330 software upgraded to 3.06.", None),
    ("2005-01-19", "CN-TFG"): (date(2011, 3, 15), "GTX 330 installed with software 3.06.", None),
    ("2005-13-10", "*"): (date(2005, 9, 20), "Junction box circuit breakers checked: correct 40-amp breakers installed.", None),
    ("2007-05-10", "*"): (date(2007, 6, 5), "Modification kit MK172-25-10C installed on both crew seats.", None),
    ("2007-08-03", "CN-TFB"): (date(2007, 6, 12), "Fuel hose end fittings checked for torque: within limits.", None),
    ("2008-05-09", "CN-TFB"): (date(2008, 5, 27), "Crew seat base and back attach brackets modified.", None),
    ("2008-26-10", "*"): (date(2009, 2, 10), "Selector valve inspected: placard does not obstruct the port.", None),
    ("2011-06-02", "CN-TFG"): (date(2011, 6, 20), "FADEC backup battery installed; AFM supplement replaced.", "battery"),
    ("2012-02-02", "*"): (date(2012, 4, 17), "Fuel return line inspected: no chafing; clearances checked and adjusted.", None),
    ("2012-22-01", "CN-TFA"): (date(2013, 1, 22), "Fuel return line inspected: no chafing; clearances checked.", None),
    ("2013-11-11", "*"): (None, "Replaced with new, zero-time P/N 83278 switch.", "switch"),
    ("2018-02-04", "CN-TFA"): (date(2018, 3, 12), "Inspected 22 February 2018, no leak. Replaced with A1754001-25 S/N 39274, not in figure 1.", None),
    ("2018-02-04", "CN-TFF"): (date(2018, 2, 23), "Replaced in lieu of inspection with A1754001-25 S/N 39281, not in figure 1.", None),
    ("2020-16-08", "CN-TFE"): (date(2020, 8, 20), "AFM limitations revised: day VFR only (copy of the AD inserted in the AFM).", None),
}

# The last oil pressure switch replacement before 26 October 2026, as the compliance record states it.
SWITCH_INSTALLED = {
    "CN-TFA": (date(2024, 2, 14), 7210.4), "CN-TFB": (date(2023, 5, 9), 5880.0), "CN-TFC": (date(2022, 11, 21), 3350.7),
    "CN-TFD": (date(2025, 3, 3), 9940.2), "CN-TFE": (date(2021, 8, 30), 10650.2), "CN-TFF": (date(2022, 7, 18), 2410.5),
}


def ad_list() -> list[tuple[str, str]]:
    """(AD number, effective date) for every AD in the corpus, oldest first; corrections are not separate ADs."""
    catalog = json.loads((ROOT / "corpus" / "source" / "catalog.json").read_text(encoding="utf-8"))["documents"]
    ads = {d["meta"]["ad_number"]: d["meta"]["effective"] for d in catalog
           if d["meta"].get("ad_number") and "correction" not in d["meta"].get("action", "")}
    return sorted(ads.items(), key=lambda item: item[1])


def applies(ad: str, reg: str) -> tuple[bool, str]:
    """Whether the AD applies, and why. Superseded ADs are reported as not applicable, with the AD that replaced them."""
    if ad in SUPERSEDED:
        return False, f"Superseded by AD {SUPERSEDED[ad]}."
    rule = APPLICABILITY[ad]
    reason = rule.get(reg, rule["*"])
    return reason.startswith("Yes"), reason


def ad_record(reg: str) -> list[dict]:
    """The rows of the aircraft's AD compliance record, as Anfa keeps it (with deliberate error D3)."""
    delivered = ANCHORS[reg][0][0]
    rows = []
    for ad, effective in ad_list():
        ok, reason = applies(ad, reg)
        if reg == "CN-TFC" and ad == "2013-11-11":  # D3
            ok, reason = True, "Yes: oil pressure switch P/N 83278 installed."
        note = reason.removeprefix("Yes: ").removeprefix("No: ")
        row = {"ad": ad, "effective": effective, "subject": SUBJECTS[ad], "applies": "Yes" if ok else "No",
               "notes": note[0].upper() + note[1:], "method": "", "date": "", "hours": "",
               "recurring": "", "next_due": "", "signed": ""}
        if ok:
            day, method, recurring = COMPLIANCE.get((ad, reg)) or COMPLIANCE[(ad, "*")]
            if recurring == "switch":
                day, hours = SWITCH_INSTALLED[reg]
                row.update(recurring="Every 3,000 h", next_due=f"{hours + 3000:,.1f} h")
            elif recurring == "battery":
                day = FADEC_BATTERY[-1]
                row.update(recurring="Every 12 calendar months", next_due=add_calendar_months(day, 12).isoformat())
            if day == "delivery":
                day, method = delivered + timedelta(days=12), f"At delivery: {method[0].lower()}{method[1:]}"
            day = max(day, delivered + timedelta(days=12))
            row.update(method=method, date=day.isoformat(), hours=f"{hours_at(reg, day):,.1f}" if recurring != "switch" else f"{hours:,.1f}",
                       signed="K. Bennani" if day >= date(2016, 1, 1) else "Previous operator's records")
        rows.append(row)
    return rows
