"""Part 6: the question's situation, when to ask which aircraft, and citation labels. No model is called."""

from __future__ import annotations

from anfa.chunking import Chunk
from anfa.convert import convert, load_corrections
from anfa.corpus import load_corpus
from anfa.evidence import evidence_units
from anfa.pipeline import resolve_citations
from anfa.situation import Aircraft, fleet_from, situation_from, which_aircraft

FLEET = [Aircraft("CN-TFA", "172S", "172S9488"), Aircraft("CN-TFC", "172S", "172S11290"),
         Aircraft("CN-TFE", "172R", "17280744")]
MODELS = {"172N", "172R", "172S"}


def test_a_registration_names_the_aircraft_and_its_model():
    s = situation_from("When is CN-TFE's next annual?", FLEET, MODELS)
    assert s.registrations == ["CN-TFE"] and s.model == "172R" and s.named


def test_an_unknown_registration_is_ignored_not_guessed():
    s = situation_from("When is CN-TXZ's next annual?", FLEET, MODELS)
    assert s.registrations is None and not s.named


def test_a_model_leaves_out_records_of_other_models():
    s = situation_from("What engine does the Cessna 172S have?", FLEET, MODELS)
    assert s.registrations == ["CN-TFA", "CN-TFC"] and s.model == "172S" and not s.one_of_ours


def test_our_model_is_one_of_ours_but_the_whole_fleet_is_not():
    assert situation_from("Does the AD apply to our 172S?", FLEET, MODELS).one_of_ours
    assert not situation_from("Which of our aircraft are affected by AD 2018-02-04?", FLEET, MODELS).one_of_ours


def test_our_model_with_one_match_is_that_aircraft():
    s = situation_from("Does the AD apply to our 172R?", FLEET, MODELS)
    assert s.registrations == ["CN-TFE"] and s.named


def test_ask_which_aircraft_when_the_best_evidence_is_a_directive():
    s = situation_from("Does the oil pressure switch AD apply to our 172S?", FLEET, MODELS)
    directive = Chunk("ad", "", "AD-2013-11-11", "", {"doc_type": "airworthiness directive"})
    assert [a.registration for a in which_aircraft(s, [directive])] == ["CN-TFA", "CN-TFC"]


def test_no_question_back_when_the_evidence_is_the_same_for_every_172S():
    s = situation_from("What engine does our 172S have?", FLEET, MODELS)
    section = Chunk("tcds", "", "TCDS-3A12-R89", "XII", {"doc_type": "type certificate data sheet", "models": ["172S"]})
    assert which_aircraft(s, [section]) == []


def test_a_known_label_becomes_its_source():
    answer, unknown = resolve_citations("3,000 hours [S1]. Next due 13,650.2 h [S1, S2].",
                                        {"S1": "AD-2013-11-11#(g)", "S2": "ADREC-CN-TFE#"})
    assert answer == ("3,000 hours [AD-2013-11-11, section (g)]. "
                      "Next due 13,650.2 h [AD-2013-11-11, section (g); ADREC-CN-TFE].")
    assert unknown == []


def test_a_label_in_parentheses_is_checked_too():
    answer, unknown = resolve_citations("Replaced at 10,650.2 h (S1); see (S5).", {"S1": "ADREC-CN-TFE#"})
    assert answer.startswith("Replaced at 10,650.2 h [ADREC-CN-TFE];") and unknown == ["S5"]


def test_an_unknown_label_is_reported():
    _, unknown = resolve_citations("3,000 hours [S4].", {"S1": "AD-2013-11-11#(g)"})
    assert unknown == ["S4"]


def test_the_fleet_comes_from_the_register_and_records_are_tagged():
    docs = {d.source_id: d for d in load_corpus()}
    corrections = load_corrections()
    fleet = fleet_from([convert(docs["FLEET-2026-10"], None, corrections)])
    assert Aircraft("CN-TFE", "172R", "17280744") in fleet and len(fleet) == 7

    tcds, _ = evidence_units(convert(docs["TCDS-3A12-R89"], None, corrections))
    assert all(c.meta["models"] == ["172S"] for c in tcds if "IO-360-L2A, Rated" in c.text and c.section == "XII")

    scan, _ = evidence_units(convert(docs["WO-SCAN"], None, corrections))
    switch = [c.meta["aircraft"] for c in scan if c.text.startswith("Replaced engine oil pressure switch")]
    assert switch == ["CN-TFE", "CN-TFA"]
