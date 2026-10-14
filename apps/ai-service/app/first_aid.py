"""Built-in first-aid responder behind POST /ai/ask (contract from Mediflow-Doc/AI.md).

General first-aid education only. It never diagnoses, never gives medication
doses, and always escalates emergency warning signs. Guidance mirrors the tips
in the MediFlow-AI frontend so the two never contradict each other.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Topic:
    name: str
    keywords: tuple[str, ...]
    answer: str
    emergency: bool = False



# Checked in order; the first match wins, so more specific topics come first.
TOPICS: tuple[Topic, ...] = (
    Topic("unresponsive", ("unresponsive", "unconscious", "not breathing", "no pulse", "cpr", "collapsed"),
          "Check for a response and normal breathing. If they are not breathing normally, call emergency "
          "services, start CPR if you are trained, and send someone for an AED. Turn the AED on and follow "
          "its spoken prompts.", emergency=True),
    Topic("choking", ("choking", "choke", "can't breathe", "cannot breathe"),
          "If the person can cough, encourage them to keep coughing. If they cannot cough, speak or breathe, "
          "call emergency services and give back blows and abdominal thrusts if you are trained. If they "
          "become unresponsive, start CPR.", emergency=True),
    Topic("severe_bleeding", ("severe bleeding", "heavy bleeding", "won't stop bleeding", "spurting"),
          "Apply firm, direct pressure with a clean cloth or gauze and keep it there. If blood soaks through, "
          "add more layers without removing the first. Call emergency services.", emergency=True),
    Topic("allergic_reaction", ("anaphylaxis", "allergic reaction", "swelling of the throat", "epipen",
                                "epinephrine"),
          "Call emergency services if there is any breathing difficulty or swelling of the face or throat. "
          "Help the person use their own prescribed adrenaline (epinephrine) auto-injector if they have one.",
          emergency=True),
    Topic("seizure", ("seizure", "convulsion", "convulsing", "having a fit", "had a fit", "epilepsy", "epileptic"),
          "Clear hazards around them, cushion their head, and time the seizure. Never hold them down or put "
          "anything in their mouth. Afterwards, place them on their side. Call emergency services if it lasts "
          "more than 5 minutes, they are injured, or it is their first seizure."),
    Topic("chest_pain", ("chest pain", "heart attack", "chest tightness"),
          "Chest pain can be a heart attack. Call emergency services now, keep the person seated and calm, and "
          "do not let them walk or drive to the clinic.", emergency=True),
    Topic("stroke", ("stroke", "face drooping", "slurred speech", "arm weakness"),
          "Think FAST: Face drooping, Arm weakness, Speech difficulty, Time to call emergency services. Note "
          "the time symptoms started.", emergency=True),
    Topic("poisoning", ("poison", "overdose", "swallowed"),
          "Do not make the person vomit. Keep the product container, call emergency services or poison "
          "control, and stay with them.", emergency=True),
    Topic("burn", ("burn", "scald"),
          "Cool the burn under clean, cool running water for 20 minutes. Do not use ice, butter, or creams. "
          "Cover loosely with a clean non-fluffy dressing. Seek care for large, deep, or facial burns, or "
          "burns on the hands, feet, or genitals."),
    Topic("nosebleed", ("nosebleed", "nose bleed", "nose bleeding"),
          "Sit upright, lean slightly forward, and pinch the soft part of the nose for 10 to 15 minutes. Seek "
          "care if bleeding continues after 20 minutes or follows a head injury."),
    Topic("cut", ("cut", "wound", "graze", "scrape", "bleeding"),
          "Wash your hands, apply pressure to stop the bleeding, rinse the wound with clean running water, "
          "then cover it with a clean dressing. Seek care if it is deep, gaping, dirty, or from an animal bite."),
    Topic("fainting", ("faint", "fainted", "passed out", "dizzy"),
          "Lay the person flat and, if there is no injury, raise their legs. Check that they are breathing. "
          "Call for help if they do not wake quickly, were injured, or have chest pain."),
    Topic("sprain", ("sprain", "strain", "twisted ankle", "twisted"),
          "Rest the area and apply a wrapped cold pack for short periods. Seek care if you cannot bear weight "
          "or the pain or swelling is severe."),
    Topic("fracture", ("fracture", "broken bone", "broken arm", "broken leg"),
          "Keep the injured area still in the position you found it. Do not try to straighten it. Get urgent "
          "medical help."),
    Topic("heat", ("heat stroke", "heat exhaustion", "overheated", "too hot"),
          "Move to a cool place, loosen clothing, and sip water if fully alert. Confusion, fainting, or hot skin "
          "is an emergency: call emergency services and keep cooling the person while you wait."),
    Topic("head_injury", ("head injury", "hit my head", "hit their head", "concussion"),
          "Rest and monitor after a minor bump. Repeated vomiting, worsening headache, confusion, or loss of "
          "consciousness needs urgent care."),
    Topic("asthma", ("asthma", "inhaler", "wheezing"),
          "Help the person sit upright and use their own prescribed reliever inhaler. Get urgent help if their "
          "breathing does not improve quickly."),
)

# Questions the responder must not answer (doses, diagnosis, prescribing).
OUT_OF_SCOPE = re.compile(
    r"\b(how (much|many) (mg|ml|tablets?|pills?)|dosage|dose|\d+\s?mg|prescribe|diagnos\w*|do i have)\b",
    re.IGNORECASE,
)


def _contains(text: str, phrase: str) -> bool:
    return re.search(rf"(?<![a-z]){re.escape(phrase)}(?![a-z])", text) is not None


def answer_question(question: str, emergency_number: str) -> tuple[str, str, bool]:
    """Return (answer, topic, emergency)."""
    text = " ".join(question.lower().split())
    for topic in TOPICS:
        if any(_contains(text, keyword) for keyword in topic.keywords):
            answer = topic.answer
            if topic.emergency:
                answer = f"This may be an emergency. Call {emergency_number} now. {answer}"
            return answer, topic.name, topic.emergency

    if OUT_OF_SCOPE.search(text):
        return ("I can't advise on diagnoses or medication doses. Please speak to a doctor or pharmacist at the "
                "health centre.", "out_of_scope", False)

    return ("I can only give general first-aid guidance, for example on cuts, burns, choking, fainting or "
            "nosebleeds. For anything else, please contact the health centre. If someone is seriously unwell, "
            f"call {emergency_number}.", "unknown", False)
