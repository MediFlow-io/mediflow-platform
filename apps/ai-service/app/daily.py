"""Daily health check-in: a few answers in, personal tips and "should I come in?" out.

Rule-based and conservative: anything that sounds serious points to the clinic. The core API adds what it
knows (current medicines, long-term conditions, recent diagnoses); no names or record numbers come here.
"""
from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

MODEL_VERSION = "daily-check-2026.11"
DISCLAIMER = "General wellbeing advice, not a diagnosis. If you feel very unwell, come to the clinic or call for help."

Symptom = Literal["fever", "cough", "sore_throat", "headache", "body_aches", "diarrhoea", "vomiting", "rash",
                  "chest_pain", "breathless", "dizzy", "stomach_pain"]


class DailyCheckRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    feeling: int = Field(..., ge=1, le=5, description="1 = very unwell, 5 = great")
    sleep_hours: float | None = Field(None, ge=0, le=24)
    water_glasses: int | None = Field(None, ge=0, le=40)
    stress: int | None = Field(None, ge=1, le=5, description="1 = calm, 5 = very stressed")
    symptoms: list[Symptom] = Field(default_factory=list, max_length=12)
    medicines: list[str] = Field(default_factory=list, max_length=20)
    chronic_conditions: list[str] = Field(default_factory=list, max_length=20)
    recent_diagnoses: list[str] = Field(default_factory=list, max_length=10)
    day: date | None = None


class Tip(BaseModel):
    topic: str
    text: str


class DailyCheckResponse(BaseModel):
    status: Literal["good", "watch", "see_clinic", "urgent"]
    headline: str
    tips: list[Tip]
    disclaimer: str = DISCLAIMER
    model_version: str = MODEL_VERSION


GENERAL_TIPS = (
    ("Prevention", "Sleep under an insecticide-treated net every night: it is the best protection against malaria."),
    ("Hygiene", "Wash your hands with soap before eating and after using the toilet."),
    ("Food", "Add fruit or vegetables to at least two meals today."),
    ("Movement", "Aim for 30 minutes of walking or other activity today."),
    ("Water", "Drink clean, safe water. If you're not sure of a source, choose sachet or bottled water from a sealed pack."),
    ("Rest", "Take short breaks from screens: every hour, look away and stretch for a minute."),
    ("Food", "Eat breakfast; it helps concentration through morning lectures and shifts."),
)
ANTIMICROBIAL = ("artemether", "lumefantrine", "artesunate", "amoxicillin", "azithromycin", "ciprofloxacin",
                 "doxycycline", "nitrofurantoin", "metronidazole", "cefuroxime", "augmentin")


def check(req: DailyCheckRequest) -> DailyCheckResponse:
    symptoms = set(req.symptoms)
    tips: list[Tip] = []
    status = "good"

    def at_least(level: str) -> None:
        nonlocal status
        order = ["good", "watch", "see_clinic", "urgent"]
        if order.index(level) > order.index(status):
            status = level

    conditions = " ".join(req.chronic_conditions).lower()
    diagnoses = " ".join(req.recent_diagnoses).lower()

    if symptoms & {"chest_pain", "breathless"}:
        at_least("urgent")
        tips.append(Tip(topic="Get help now", text="Chest pain or trouble breathing needs a clinician today. "
                        "Go to the clinic now, or call for emergency help if it is severe."))
    if "fever" in symptoms:
        at_least("see_clinic")
        if "malaria" in diagnoses:
            tips.append(Tip(topic="Fever", text="You were treated for malaria recently. A fever now should be checked at the clinic."))
        else:
            tips.append(Tip(topic="Fever", text="Fever is often malaria here. Come to the clinic for a quick test rather than "
                            "self-treating. Paracetamol can ease it meanwhile."))
    if "sickle" in conditions and (symptoms & {"fever", "body_aches", "breathless"}):
        at_least("see_clinic")
        tips.append(Tip(topic="Sickle cell", text="With sickle cell disease, fever or pain can start a crisis: "
                        "drink plenty of water and come to the clinic today."))
    if {"diarrhoea", "vomiting"} <= symptoms:
        at_least("see_clinic")
        tips.append(Tip(topic="Fluids", text="Diarrhoea with vomiting can dehydrate you quickly. Sip oral rehydration "
                        "solution and come to the clinic."))
    elif symptoms & {"diarrhoea", "vomiting"}:
        at_least("watch")
        tips.append(Tip(topic="Fluids", text="Drink oral rehydration solution (ORS) after each loose stool or vomit. "
                        "Come in if there is blood, or it lasts more than 2 days."))
    if symptoms & {"cough", "sore_throat"}:
        at_least("watch")
        tips.append(Tip(topic="Cough and throat", text="Warm drinks and rest help. Come in if it lasts more than a week, "
                        "you cough blood, or you get a fever."))
    if symptoms & {"headache", "dizzy"}:
        at_least("watch")
        tips.append(Tip(topic="Headache", text="Drink water, eat something and rest away from screens. A sudden, severe "
                        "headache or one with a stiff neck needs the clinic."))
    if "rash" in symptoms:
        at_least("watch")
        tips.append(Tip(topic="Rash", text="Note when it started and anything new you've used. A rash with fever or "
                        "swelling of the face or lips needs the clinic."))
    if "stomach_pain" in symptoms:
        at_least("watch")
        tips.append(Tip(topic="Stomach", text="Eat small, plain meals. Severe or worsening pain needs the clinic."))
    if req.feeling <= 2 and status in ("good", "watch"):
        at_least("watch")
        tips.append(Tip(topic="Feeling low", text="Sorry you're not feeling well. If it doesn't improve by tomorrow, "
                        "book a visit through the app."))

    taking = [m for m in req.medicines if any(word in m.lower() for word in ANTIMICROBIAL)]
    if taking:
        tips.append(Tip(topic="Your medicine", text=f"Keep taking {taking[0]} exactly as prescribed and finish the "
                        "course, even if you feel better."))
    elif req.medicines:
        tips.append(Tip(topic="Your medicine", text=f"Remember today's {req.medicines[0]} as prescribed."))

    if "asthma" in conditions:
        tips.append(Tip(topic="Asthma", text="Keep your reliever inhaler with you. Smoke, dust and cold air can set it off."))
    if "sickle" in conditions and not any(t.topic == "Sickle cell" for t in tips):
        tips.append(Tip(topic="Sickle cell", text="Drink plenty of water through the day and avoid getting very hot or cold."))
    if "hypertension" in conditions or "blood pressure" in conditions:
        tips.append(Tip(topic="Blood pressure", text="Take your blood pressure medicine at the same time each day and go easy on salt."))
    if "diabetes" in conditions:
        tips.append(Tip(topic="Diabetes", text="Keep regular meal times with your medicine, and carry a sweet snack in case of a low."))
    if "malaria" in diagnoses and "fever" not in symptoms:
        tips.append(Tip(topic="Malaria", text="Sleep under a treated net to avoid getting malaria again."))

    if req.sleep_hours is not None and req.sleep_hours < 6:
        tips.append(Tip(topic="Sleep", text=f"{req.sleep_hours:g} hours is short. Most adults need 7-9: try a fixed "
                        "bedtime and put the phone away 30 minutes before."))
    if req.water_glasses is not None and req.water_glasses < 6:
        tips.append(Tip(topic="Water", text="Aim for 8 glasses of water a day, more in the heat or after exercise."))
    if req.stress is not None and req.stress >= 4:
        tips.append(Tip(topic="Stress", text="Feeling under pressure is common, especially around exams. Short breaks, "
                        "a walk and talking to someone help. The student counselling unit is there for you too."))

    if len(tips) < 3:
        day = req.day or date.today()
        topic, text = GENERAL_TIPS[day.toordinal() % len(GENERAL_TIPS)]
        tips.append(Tip(topic=topic, text=text))

    headline = {
        "urgent": "Please get help now.",
        "see_clinic": "Please come to the clinic today.",
        "watch": "Take it easy today and keep an eye on how you feel.",
        "good": "You're doing well today. Keep it up!",
    }[status]
    return DailyCheckResponse(status=status, headline=headline, tips=tips[:6])
