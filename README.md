# FormFlex — AI Exercise Posture Correction

Real-time posture correction and rep counting using your webcam.

---

## Requirements

- Python 3.11
- Node.js 18+
- FFmpeg (`brew install ffmpeg` on Mac)
- A webcam

---

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/adithyajayan1/Main-Project.git
cd Main-Project
```

### 2. Set up Python environment

```bash
PYENV_VERSION=3.11.14 python -m venv venv
source venv/bin/activate       # Mac/Linux
# venv\Scripts\activate        # Windows
pip install -r requirements.txt
```

### 3. Set up frontend

```bash
cd frontend
npm install
cd ..
```

---

## Run

Open **two terminals**:

**Terminal 1 — Backend**
```bash
source venv/bin/activate
uvicorn backend:app --reload --port 8000
```

**Terminal 2 — Frontend**
```bash
cd frontend
npm start
```

Open **http://localhost:3000** in your browser and create an account to get started.

---

## Exercises

Push Up · Squat · Lunges · Plank

> Place camera to your **side** for all exercises. Make sure your full body is visible.

---

## Features

- Real-time pose detection with red/green skeleton feedback (red = bad form, green = good form)
- Rep counting — only counts reps when form is correct
- Voice feedback via browser Web Speech API
- Set a target rep/time goal — a completion overlay appears when reached, letting you keep going or stop
- Session recording — saved as MP4 and downloaded to your browser on stop
- Dashboard with workout history, streak, and stats
- Reports page with session charts (week/month/year)

---

## Notes

- Allow camera permissions when the browser asks
- Use **Chrome** for best voice feedback support
- If you see "No pose detected" — move back so your full body is in frame
- Login is required to access workouts, dashboard, and reports
- The database (`gymlytics.db`) is stored locally — your data stays on your machine
