"""Part 6: which evidence applies to the aircraft the question is about?

Much of this collection applies to one model or one aircraft: a section of the type certificate
data sheet, an aircraft's AD compliance record, a row of the fleet register. A passage about the
172R is the right answer to a different question. So the question's situation (which aircraft,
or which model) filters every search, and evidence for anything else is never a candidate.

The situation is read by code, not by a model. Registrations ("CN-TFE"), serial numbers, and model
designators ("172S") have fixed shapes, and each is checked against the fleet register or the
models the type certificate names: an unknown one is ignored, not guessed.

    "CN-TFE's switch"           that aircraft, and its model
    "the Cessna 172S"           that model: records of other models' aircraft are left out
    "our 172S"                  one of our aircraft, of that model; if several match and the
                                evidence differs from one aircraft to the next, ask which
    "which of our aircraft"     the whole fleet: nothing to filter
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from anfa.chunking import Chunk
from anfa.convert import StructuredDocument

REGISTRATION = re.compile(r"\bCN-[A-Z]{3}\b")
# A lettered designator. A bare "172" usually means the family, not the 1956 Model 172.
MODEL = re.compile(r"\b172[A-Z]\b")
# "our 172S" or "my aircraft" names one airplane; "which of our aircraft" asks about all of them.
ONE_OF_OURS = re.compile(r"(?<!of )\b(?:our|my) (?:Cessna )?(?:172[A-Z]|aircraft|airplane|plane)\b", re.IGNORECASE)


@dataclass(frozen=True)
class Aircraft:
    registration: str
    model: str
    serial: str


@dataclass
class Situation:
    # The aircraft the evidence may be about; None when the question doesn't narrow it.
    aircraft: list[Aircraft] | None = None
    model: str | None = None
    named: bool = False  # the question identifies the aircraft itself
    one_of_ours: bool = False
    candidates: list[Aircraft] = field(default_factory=list)  # when one of ours, unnamed

    @property
    def registrations(self) -> list[str] | None:
        return None if self.aircraft is None else [a.registration for a in self.aircraft]

    def facts(self) -> str:
        """What the question established, for the prompt."""
        if self.named and len(self.aircraft) == 1:
            a = self.aircraft[0]
            return f"The question is about {a.registration}, a Cessna {a.model}, serial number {a.serial}."
        if self.model:
            return f"The question is about the Cessna {self.model}."
        return ""


def situation_from(question: str, fleet: list[Aircraft], models: set[str]) -> Situation:
    named = [a for a in fleet if a.registration in REGISTRATION.findall(question)
             or re.search(rf"\b{re.escape(a.serial)}\b", question)]
    if named:
        named_models = {a.model for a in named}
        return Situation(named, named_models.pop() if len(named_models) == 1 else None, named=True)

    model = next((m for m in MODEL.findall(question) if m in models), None)
    ours = bool(ONE_OF_OURS.search(question))
    matching = [a for a in fleet if a.model == model] if model else list(fleet)
    if ours and len(matching) == 1:
        return Situation(matching, matching[0].model, named=True)
    if ours:
        return Situation(matching, model, one_of_ours=True, candidates=matching)
    if model:
        return Situation(matching, model)
    return Situation()


def which_aircraft(situation: Situation, hits: list[Chunk]) -> list[Aircraft]:
    """The aircraft to choose from, when the answer depends on which one and the question doesn't say.

    The evidence decides: a directive applies by serial number and installed equipment, and a
    record belongs to one aircraft. A type certificate section is the same for every 172S."""
    if not situation.one_of_ours or len(situation.candidates) < 2 or not hits:
        return []
    best = hits[0].meta
    if best.get("doc_type") == "airworthiness directive" or best.get("aircraft"):
        return situation.candidates
    return []


def fleet_from(documents: list[StructuredDocument]) -> list[Aircraft]:
    """The aircraft we maintain: the fleet register's table of registrations, models, and serial numbers."""
    for doc in documents:
        if doc.meta.get("doc_type") != "fleet register":
            continue
        for section in doc.sections:
            for element in section.elements:
                header = (element.data.get("header") or []) if element.kind == "table" else []
                if {"Registration", "Model", "Serial number"} <= set(header):
                    return [Aircraft(r[header.index("Registration")], r[header.index("Model")],
                                     r[header.index("Serial number")]) for r in element.data["rows"]]
    return []
