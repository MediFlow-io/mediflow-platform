"""Drug suggestions for a diagnosis: decision support for the doctor writing a prescription.

A small formulary of conditions common in a campus clinic, with usual adult regimens (Nigeria Standard
Treatment Guidelines / WHO essential medicines style). The doctor always decides: suggestions are filtered
against the patient's allergies and flagged for pregnancy and long-term conditions, never prescribed here.
Children under 12 get no suggestions: their doses depend on weight.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from pydantic import BaseModel, ConfigDict, Field

MODEL_VERSION = "formulary-2026.11"
DISCLAIMER = ("Suggestions only, for adults and adolescents 12 and over. Check the dose, interactions and the "
              "patient's history before prescribing. The prescribing doctor is responsible for every prescription.")


class DrugSuggestionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    diagnoses: list[str] = Field(..., min_length=1, max_length=10, description="diagnosis text and/or ICD-10 codes")
    allergies: str = Field("", max_length=500)
    chronic_conditions: list[str] = Field(default_factory=list, max_length=20)
    age_years: int | None = Field(None, ge=0, le=120)
    sex: str | None = Field(None, max_length=10)
    pregnant: bool = False


class Suggestion(BaseModel):
    drug: str
    dose: str
    route: str
    frequency: str
    duration: str
    instructions: str
    for_condition: str
    first_line: bool
    cautions: list[str]


class Excluded(BaseModel):
    drug: str
    reason: str


class DrugSuggestionResponse(BaseModel):
    matched_conditions: list[str]
    suggestions: list[Suggestion]
    excluded: list[Excluded]
    notes: list[str]
    disclaimer: str = DISCLAIMER
    model_version: str = MODEL_VERSION


@dataclass(frozen=True)
class Drug:
    name: str
    dose: str
    route: str
    frequency: str
    duration: str
    instructions: str
    classes: tuple[str, ...] = ()
    avoid_in_pregnancy: bool = False
    pregnancy_caution: str = ""


@dataclass(frozen=True)
class Condition:
    name: str
    keywords: tuple[str, ...]
    icd_prefixes: tuple[str, ...]
    first_line: tuple[Drug, ...]
    alternatives: tuple[Drug, ...] = ()   # used when a first-line drug is excluded (allergy, pregnancy)
    supportive: tuple[Drug, ...] = ()
    note: str = ""


PARACETAMOL = Drug("Paracetamol", "1 g", "oral", "every 6-8 hours when needed (max 4 g a day)", "up to 3 days",
                   "For fever or pain. Do not take with other paracetamol-containing medicines.")
IBUPROFEN = Drug("Ibuprofen", "400 mg", "oral", "three times a day", "up to 3 days", "Take with or after food.",
                 classes=("nsaid",), pregnancy_caution="Avoid NSAIDs in pregnancy, especially from 20 weeks.")
AZITHROMYCIN_3D = Drug("Azithromycin", "500 mg", "oral", "once a day", "3 days", "Take at the same time each day.",
                       classes=("macrolide",))

FORMULARY: tuple[Condition, ...] = (
    Condition(
        "Uncomplicated malaria", ("malaria",), ("B50", "B51", "B52", "B53", "B54"),
        first_line=(Drug("Artemether-lumefantrine 20/120 mg", "4 tablets", "oral",
                         "twice a day (second dose 8 hours after the first)", "3 days (6 doses)",
                         "Take with food or milk; finish all 6 doses even if you feel better.",
                         classes=("artemisinin",),
                         pregnancy_caution="First trimester: follow current national malaria guidance."),),
        alternatives=(Drug("Artesunate-amodiaquine 100/270 mg", "2 tablets", "oral", "once a day", "3 days",
                           "Finish all doses even if you feel better.", classes=("artemisinin",)),),
        supportive=(PARACETAMOL,),
        note="Adult regimen for 35 kg and over. Confirm with an RDT or microscopy; severe malaria needs IV artesunate and referral.",
    ),
    Condition(
        "Typhoid (enteric) fever", ("typhoid", "enteric fever"), ("A01",),
        first_line=(Drug("Azithromycin", "500 mg", "oral", "once a day", "7 days", "Take at the same time each day.",
                         classes=("macrolide",)),),
        alternatives=(Drug("Ciprofloxacin", "500 mg", "oral", "twice a day", "7 days",
                           "Do not take with milk or antacids at the same time.", classes=("quinolone",),
                           avoid_in_pregnancy=True),),
        supportive=(PARACETAMOL,),
        note="Widal tests are unreliable; prefer blood culture where available.",
    ),
    Condition(
        "Upper respiratory tract infection", ("common cold", "upper respiratory", "urti", "catarrh", "coryza", "flu"),
        ("J00", "J06", "J11"),
        first_line=(PARACETAMOL,),
        note="Usually viral: antibiotics are not recommended.",
    ),
    Condition(
        "Bacterial tonsillitis / pharyngitis", ("tonsillitis", "pharyngitis", "strep throat"), ("J02", "J03"),
        first_line=(Drug("Amoxicillin", "500 mg", "oral", "three times a day", "10 days", "Finish the course.",
                         classes=("penicillin",)),),
        alternatives=(AZITHROMYCIN_3D,),
        supportive=(PARACETAMOL,),
    ),
    Condition(
        "Community-acquired pneumonia (mild)", ("pneumonia",), ("J13", "J14", "J15", "J18"),
        first_line=(Drug("Amoxicillin", "500 mg", "oral", "three times a day", "5 days", "Finish the course.",
                         classes=("penicillin",)),),
        alternatives=(Drug("Doxycycline", "200 mg on day 1, then 100 mg", "oral", "once a day", "5 days in total",
                           "Take upright with a full glass of water; avoid strong sunlight.", classes=("tetracycline",),
                           avoid_in_pregnancy=True),),
        supportive=(PARACETAMOL,),
        note="Check severity (CRB-65). Refer if breathless, confused or SpO2 under 94%.",
    ),
    Condition(
        "Uncomplicated urinary tract infection", ("urinary tract infection", "uti", "cystitis"), ("N30", "N39.0"),
        first_line=(Drug("Nitrofurantoin (modified release)", "100 mg", "oral", "twice a day", "5 days",
                         "Take with food. Urine may turn dark yellow or brown.", classes=("nitrofuran",),
                         pregnancy_caution="Avoid at term (36 weeks or later)."),),
        note="For non-pregnant women this course can be 3 days. Men and recurrent infections: send a urine culture.",
    ),
    Condition(
        "Dyspepsia / peptic ulcer disease", ("dyspepsia", "peptic ulcer", "gastric ulcer", "duodenal ulcer", "gastritis", "pud"), ("K25", "K26", "K27", "K29", "K30"),
        first_line=(Drug("Omeprazole", "20 mg", "oral", "once a day, before breakfast", "4 weeks",
                         "Swallow whole. Avoid NSAIDs like ibuprofen and aspirin."),),
        note="Consider H. pylori testing; refer urgently for weight loss, vomiting blood or black stools.",
    ),
    Condition(
        "Acute gastroenteritis / diarrhoea", ("gastroenteritis", "diarrhoea", "diarrhea", "food poisoning"), ("A09",),
        first_line=(Drug("Oral rehydration salts (low-osmolarity)", "200-400 mL", "oral", "after each loose stool",
                         "until the diarrhoea stops", "Dissolve one sachet in the stated amount of clean water."),),
        note="Antibiotics are not routinely needed. Look for dehydration and blood in the stool.",
    ),
    Condition(
        "Tension-type headache", ("tension headache", "tension-type headache", "headache"), ("G44.2", "R51"),
        first_line=(PARACETAMOL,),
        alternatives=(IBUPROFEN,),
        note="Red flags (sudden severe headache, fever with neck stiffness, neurological signs) need urgent review.",
    ),
    Condition(
        "Primary dysmenorrhoea", ("dysmenorrhoea", "dysmenorrhea", "period pain", "menstrual cramp"), ("N94.4", "N94.5", "N94.6"),
        first_line=(IBUPROFEN,),
        alternatives=(PARACETAMOL,),
    ),
    Condition(
        "Allergic rhinitis / urticaria", ("allergic rhinitis", "hay fever", "urticaria", "hives"), ("J30", "L50"),
        first_line=(Drug("Cetirizine", "10 mg", "oral", "once a day", "7 days, then as needed",
                         "May cause drowsiness in some people."),),
        alternatives=(Drug("Loratadine", "10 mg", "oral", "once a day", "7 days, then as needed", ""),),
    ),
    Condition(
        "Bacterial conjunctivitis", ("conjunctivitis", "apollo"), ("H10",),
        first_line=(Drug("Chloramphenicol 0.5% eye drops", "1 drop", "eye",
                         "every 2 hours for 2 days, then four times a day", "5 days in total",
                         "Wash hands before and after; do not share towels."),),
    ),
    Condition(
        "Superficial fungal skin infection", ("tinea", "ringworm", "fungal skin", "athlete's foot"), ("B35", "B36"),
        first_line=(Drug("Clotrimazole 1% cream", "thin layer", "skin", "twice a day", "2-4 weeks",
                         "Continue for 2 weeks after the rash clears.", classes=("azole",)),),
    ),
    Condition(
        "Asthma (reliever)", ("asthma",), ("J45", "J46"),
        first_line=(Drug("Salbutamol inhaler 100 micrograms/puff", "2 puffs", "inhaled", "when needed, up to 4 times a day",
                         "ongoing", "Use a spacer if available. Needing it more than twice a week means asthma is not controlled."),),
        note="Severe attack (can't complete sentences, SpO2 under 92%): emergency treatment, not this list.",
    ),
    Condition(
        "Hypertension (new)", ("hypertension", "high blood pressure"), ("I10",),
        first_line=(Drug("Amlodipine", "5 mg", "oral", "once a day", "ongoing; review in 2-4 weeks",
                         "May cause ankle swelling. Keep taking it unless your doctor says to stop."),),
        note="Confirm with repeated readings before starting; check kidney function and urine.",
    ),
)

# What a patient's allergy text may say, and the drug classes it rules out.
ALLERGY_CLASSES = {
    "penicillin": ("penicillin", "amoxicillin", "ampicillin", "augmentin", "amoxiclav", "flucloxacillin", "cloxacillin"),
    "nsaid": ("nsaid", "ibuprofen", "aspirin", "diclofenac", "naproxen", "piroxicam"),
    "macrolide": ("macrolide", "azithromycin", "erythromycin", "clarithromycin"),
    "quinolone": ("quinolone", "ciprofloxacin", "levofloxacin", "ofloxacin"),
    "tetracycline": ("tetracycline", "doxycycline"),
    "artemisinin": ("artemether", "lumefantrine", "coartem", "artesunate", "artemisinin"),
    "nitrofuran": ("nitrofurantoin",),
    "azole": ("clotrimazole", "fluconazole", "azole"),
}
NSAID_RISK = ("peptic ulcer", "ulcer", "kidney", "renal", "sickle cell")


def _words(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower())


def _match(diagnosis: str) -> list[Condition]:
    text, code = _words(diagnosis), diagnosis.strip().upper()
    found = []
    for condition in FORMULARY:
        by_code = any(code.startswith(prefix) or f"({prefix}" in diagnosis.upper() for prefix in condition.icd_prefixes)
        by_word = any(re.search(rf"\b{re.escape(k)}\b", text) for k in condition.keywords)
        if by_code or by_word:
            found.append(condition)
    return found


def _allergic_to(drug: Drug, allergies: str) -> str | None:
    text = _words(allergies)
    if not text.strip() or text.strip() in ("none", "nil", "nkda", "no known allergies"):
        return None
    first_word = drug.name.lower().split()[0].split("-")[0]
    if re.search(rf"\b{re.escape(first_word)}", text):
        return f"Allergy recorded: {allergies.strip()}"
    for cls in drug.classes:
        if any(re.search(rf"\b{re.escape(word)}", text) for word in ALLERGY_CLASSES.get(cls, ())):
            return f"Allergy to the {cls} class recorded: {allergies.strip()}"
    return None


@dataclass
class _Plan:
    suggestions: list[Suggestion] = field(default_factory=list)
    excluded: list[Excluded] = field(default_factory=list)
    names: set[str] = field(default_factory=set)


def _consider(plan: _Plan, drug: Drug, condition: Condition, first_line: bool, req: DrugSuggestionRequest) -> bool:
    """Adds the drug unless it's ruled out. Returns whether it was added."""
    if drug.name in plan.names:
        return True
    conditions = _words(" ".join(req.chronic_conditions))
    reason = _allergic_to(drug, req.allergies)
    if not reason and req.pregnant and drug.avoid_in_pregnancy:
        reason = "Not for use in pregnancy."
    if not reason and "nsaid" in drug.classes and any(risk in conditions for risk in NSAID_RISK):
        reason = "NSAIDs are unsafe with the patient's long-term condition."
    if reason:
        plan.excluded.append(Excluded(drug=drug.name, reason=reason))
        return False
    cautions = []
    if req.pregnant and drug.pregnancy_caution:
        cautions.append(drug.pregnancy_caution)
    if "nsaid" in drug.classes and "asthma" in conditions:
        cautions.append("Asthma: NSAIDs can trigger bronchospasm in some patients.")
    plan.names.add(drug.name)
    plan.suggestions.append(Suggestion(
        drug=drug.name, dose=drug.dose, route=drug.route, frequency=drug.frequency, duration=drug.duration,
        instructions=drug.instructions, for_condition=condition.name, first_line=first_line, cautions=cautions))
    return True


def suggest(req: DrugSuggestionRequest) -> DrugSuggestionResponse:
    if req.age_years is not None and req.age_years < 12:
        return DrugSuggestionResponse(matched_conditions=[], suggestions=[], excluded=[],
                                      notes=["No suggestions for children under 12: doses must be calculated by weight."])
    conditions: list[Condition] = []
    for diagnosis in req.diagnoses:
        for condition in _match(diagnosis):
            if condition not in conditions:
                conditions.append(condition)
    plan = _Plan()
    notes = []
    for condition in conditions:
        lost_first_line = [d for d in condition.first_line if not _consider(plan, d, condition, True, req)]
        if lost_first_line or not condition.first_line:
            for alternative in condition.alternatives:
                _consider(plan, alternative, condition, False, req)
        for drug in condition.supportive:
            _consider(plan, drug, condition, False, req)
        if not any(s.for_condition == condition.name for s in plan.suggestions):
            notes.append(f"{condition.name}: every listed option is ruled out for this patient. Choose another treatment.")
        if condition.note:
            notes.append(f"{condition.name}: {condition.note}")
    if not conditions:
        notes.append("No suggestions for this diagnosis yet. Prescribe as usual.")
    return DrugSuggestionResponse(matched_conditions=[c.name for c in conditions], suggestions=plan.suggestions,
                                  excluded=plan.excluded, notes=notes)
