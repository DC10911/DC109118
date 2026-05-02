from __future__ import annotations

from datetime import datetime
from enum import Enum
from hashlib import sha256
from secrets import token_urlsafe
from typing import Dict, List, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

app = FastAPI(title="FitVision AI MVP", version="0.2.0")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

DB: Dict[str, Dict] = {
    "users": {},
    "profiles": {},
    "progress": {},
    "water": {},
    "sessions": {},
}


class Goal(str, Enum):
    fat_loss = "fat_loss"
    muscle_gain = "muscle_gain"
    toning = "toning"
    general_health = "general_health"


class RegisterIn(BaseModel):
    email: str
    password: str = Field(min_length=8)
    name: str


class LoginIn(BaseModel):
    email: str
    password: str


class OnboardingIn(BaseModel):
    age: int
    biological_sex: str
    height_cm: float
    current_weight_kg: float
    target_weight_kg: Optional[float] = None
    goal: Goal
    activity_level: str
    experience_level: str
    available_days: int
    minutes_per_workout: int
    location: str
    equipment: List[str]
    injuries: List[str] = []
    kosher: bool = False
    meat_dairy_wait_hours: int = 6
    allergies: List[str] = []
    disliked_foods: List[str] = []
    liked_foods: List[str] = []
    meals_per_day: int = 3
    wake_time: str = "07:00"
    sleep_time: str = "23:00"


class CoachAsk(BaseModel):
    question: str


def hash_password(password: str) -> str:
    return sha256(password.encode("utf-8")).hexdigest()


def create_session(email: str) -> str:
    token = token_urlsafe(32)
    DB["sessions"][token] = {"email": email, "created_at": datetime.utcnow().isoformat()}
    return token


def current_user(authorization: str = Header(default="")) -> str:
    # Expect: Authorization: Bearer <token>
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    session = DB["sessions"].get(token)
    if not session:
        raise HTTPException(status_code=401, detail="Invalid token")
    return session["email"]


def calc_bmr(age: int, sex: str, height_cm: float, weight_kg: float) -> float:
    s = 5 if sex.lower().startswith("m") else -161
    return 10 * weight_kg + 6.25 * height_cm - 5 * age + s


def activity_factor(level: str) -> float:
    return {
        "sedentary": 1.2,
        "light": 1.375,
        "moderate": 1.55,
        "active": 1.725,
    }.get(level, 1.375)


def build_workout(profile: dict) -> dict:
    days = max(2, min(profile["available_days"], 5))
    beginner = profile["experience_level"] == "beginner"
    base = ["Squat", "Push-up", "Hip hinge", "Row", "Plank"] if beginner else ["Bench/Push", "Squat", "Row", "Deadlift", "Core"]
    if profile["injuries"]:
        base = [e for e in base if "Deadlift" not in e]
    return {
        "days": days,
        "minutes": profile["minutes_per_workout"],
        "split": "full_body" if beginner else "upper_lower",
        "exercises": base,
    }


def build_nutrition(profile: dict) -> dict:
    bmr = calc_bmr(profile["age"], profile["biological_sex"], profile["height_cm"], profile["current_weight_kg"])
    tdee = bmr * activity_factor(profile["activity_level"])
    if profile["goal"] == Goal.fat_loss:
        calories = int(tdee * 0.85)
    elif profile["goal"] == Goal.muscle_gain:
        calories = int(tdee * 1.08)
    else:
        calories = int(tdee * 0.95)
    protein = round(profile["current_weight_kg"] * 1.8)
    return {
        "calories": calories,
        "protein_g": protein,
        "meals_per_day": profile["meals_per_day"],
        "type": "kosher" if profile["kosher"] else "standard",
        "tags": ["meat", "dairy", "parve"] if profile["kosher"] else ["mixed"],
    }


def build_hydration(profile: dict) -> dict:
    base = int(profile["current_weight_kg"] * 33)
    if profile["available_days"] >= 3:
        base += 600
    return {
        "target_ml": base,
        "wake_time": profile["wake_time"],
        "sleep_time": profile["sleep_time"],
        "quick_add": [250, 500],
    }


def safe_coach_answer(question: str) -> str:
    bad_flags = ["sharp pain", "chest pain", "faint", "dizzy", "eating disorder", "pregnan", "medication"]
    lowered = question.lower()
    if any(flag in lowered for flag in bad_flags):
        return "זה נשמע מצב שדורש איש מקצוע. אני ממליץ לפנות לרופא/דיאטן/פיזיותרפיסט מוסמך לפני המשך אימון."
    return "מעולה, הנה התאמה פרקטית להיום: שמור על עצימות בינונית (RPE 6-7), התמקד בטכניקה, ואל תשכח מים וחלבון."


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/auth/register")
def register(payload: RegisterIn):
    if payload.email in DB["users"]:
        raise HTTPException(status_code=409, detail="Email already exists")
    DB["users"][payload.email] = {"name": payload.name, "password_hash": hash_password(payload.password)}
    return {"token": create_session(payload.email)}


@app.post("/auth/login")
def login(payload: LoginIn):
    user = DB["users"].get(payload.email)
    if not user or user["password_hash"] != hash_password(payload.password):
        raise HTTPException(status_code=401, detail="Bad credentials")
    return {"token": create_session(payload.email)}


@app.post("/onboarding")
def onboarding(payload: OnboardingIn, email: str = Depends(current_user)):
    data = payload.model_dump()
    DB["profiles"][email] = data
    DB["progress"][email] = {"weights": [data["current_weight_kg"]], "workouts_completed": 0}
    DB["water"][email] = {"consumed_ml": 0}
    return {
        "workout": build_workout(data),
        "nutrition": build_nutrition(data),
        "hydration": build_hydration(data),
        "scan_disclaimer": "Camera estimates are non-medical and approximate only.",
    }


@app.get("/dashboard")
def dashboard(email: str = Depends(current_user)):
    profile = DB["profiles"].get(email)
    if not profile:
        raise HTTPException(status_code=404, detail="Complete onboarding first")
    return {
        "today_workout": build_workout(profile),
        "meal_summary": build_nutrition(profile),
        "water": {**build_hydration(profile), **DB["water"][email]},
        "ai_daily": "Consistency beats perfection. Do one action now.",
    }


@app.post("/ai/coach")
def ai_coach(payload: CoachAsk, email: str = Depends(current_user)):
    _ = email
    return {"answer": safe_coach_answer(payload.question)}
