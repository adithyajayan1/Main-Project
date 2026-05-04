"""
Seed script — creates demo accounts with varied workout history.
Run once: python seed.py
Safe to re-run: skips accounts that already exist.
"""

import random
from datetime import datetime, timedelta
from models import SessionLocal, User, Session

# ── Demo accounts ─────────────────────────────────────────────────────────────
ACCOUNTS = [
    {
        "name": "Alex Rivera",
        "email": "alex@demo.com",
        "password": "demo1234",
        "profile": "heavy",       # 50–70 sessions, long streaks
    },
    {
        "name": "Jordan Kim",
        "email": "jordan@demo.com",
        "password": "demo1234",
        "profile": "moderate",    # 25–35 sessions, consistent
    },
    {
        "name": "Sam Patel",
        "email": "sam@demo.com",
        "password": "demo1234",
        "profile": "light",       # 10–15 sessions, sporadic
    },
    {
        "name": "Casey Morgan",
        "email": "casey@demo.com",
        "password": "demo1234",
        "profile": "specialist",  # ~30 sessions, mostly squats + planks
    },
    {
        "name": "Taylor Nguyen",
        "email": "taylor@demo.com",
        "password": "demo1234",
        "profile": "beginner",    # 5–8 sessions, all recent (last 2 weeks)
    },
    {
        "name": "Sahiba",
        "email": "sahiba@demo.com",
        "password": "demo1234",
        "profile": "heavy",
    },
    {
        "name": "Adithya",
        "email": "adithya@demo.com",
        "password": "demo1234",
        "profile": "moderate",
    },
    {
        "name": "Ann",
        "email": "ann@demo.com",
        "password": "demo1234",
        "profile": "specialist",
    },
    {
        "name": "Sheez",
        "email": "sheez@demo.com",
        "password": "demo1234",
        "profile": "light",
    },
]

# ── Exercise config ───────────────────────────────────────────────────────────
EXERCISES = ["pushup", "squat", "lunges", "plank"]

EXERCISE_REPS = {
    "pushup": (8,  30),   # min/max reps
    "squat":  (10, 25),
    "lunges": (8,  20),
    "plank":  (20, 90),   # seconds
}

PROFILE_CONFIG = {
    "heavy":      {"days": 90, "sessions_per_active_day": (2, 4), "active_day_chance": 0.75, "exercise_weights": [3, 3, 2, 2]},
    "moderate":   {"days": 60, "sessions_per_active_day": (1, 2), "active_day_chance": 0.55, "exercise_weights": [2, 3, 2, 3]},
    "light":      {"days": 60, "sessions_per_active_day": (1, 2), "active_day_chance": 0.25, "exercise_weights": [3, 2, 2, 1]},
    "specialist": {"days": 60, "sessions_per_active_day": (1, 3), "active_day_chance": 0.55, "exercise_weights": [1, 4, 1, 4]},
    "beginner":   {"days": 14, "sessions_per_active_day": (1, 1), "active_day_chance": 0.55, "exercise_weights": [2, 2, 1, 1]},
}

def make_sessions(profile_key):
    cfg = PROFILE_CONFIG[profile_key]
    sessions = []
    today = datetime.now().date()

    for days_ago in range(cfg["days"], -1, -1):
        if random.random() > cfg["active_day_chance"]:
            continue
        day = today - timedelta(days=days_ago)
        n = random.randint(*cfg["sessions_per_active_day"])
        for _ in range(n):
            exercise = random.choices(EXERCISES, weights=cfg["exercise_weights"])[0]
            lo, hi = EXERCISE_REPS[exercise]
            rep_count = random.randint(lo, hi)
            duration = rep_count if exercise == "plank" else rep_count * 3
            # Spread sessions across the day
            hour = random.randint(6, 21)
            minute = random.randint(0, 59)
            created_at = datetime.combine(day, datetime.min.time()).replace(hour=hour, minute=minute)
            sessions.append({
                "exercise": exercise,
                "rep_count": rep_count,
                "duration": duration,
                "created_at": created_at,
            })
    return sessions

# ── Main ──────────────────────────────────────────────────────────────────────
def seed():
    db = SessionLocal()
    total_sessions = 0

    try:
        for account in ACCOUNTS:
            existing = db.query(User).filter(User.email == account["email"]).first()
            if existing:
                print(f"  SKIP  {account['email']} (already exists)")
                continue

            user = User(email=account["email"], name=account["name"])
            user.set_password(account["password"])
            db.add(user)
            db.flush()  # get user.id before committing

            sessions = make_sessions(account["profile"])
            for s in sessions:
                db.add(Session(
                    user_id=user.id,
                    exercise=s["exercise"],
                    rep_count=s["rep_count"],
                    duration=s["duration"],
                    created_at=s["created_at"],
                ))
            db.commit()
            total_sessions += len(sessions)
            print(f"  CREATED  {account['email']}  ({account['profile']}, {len(sessions)} sessions)")

    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()

    print(f"\nDone. {total_sessions} sessions seeded across {len(ACCOUNTS)} accounts.")
    print("\nLogin credentials (all passwords: demo1234):")
    for a in ACCOUNTS:
        print(f"  {a['email']:30s}  {a['name']}")

if __name__ == "__main__":
    seed()
