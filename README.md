# FormFlex — Exercise Posture Correction

Real-time posture correction and rep counting using your webcam.

---

## Requirements

- Python 3.10.13
- Node.js 18+
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
python -m venv venv
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

Open **http://localhost:3000** in your browser.

---

## Exercises

Push Up · Squat · Lunges · Plank

> Place camera to your **side** for all exercises. Make sure your full body is visible.

---

## Notes

- Allow camera permissions when the browser asks
- Use **Chrome** for best voice feedback support
- If you see "No pose detected" — move back so your full body is in frame
