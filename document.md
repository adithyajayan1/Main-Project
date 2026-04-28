# FormFlex - Project Documentation & System Design

This document provides a comprehensive overview of the **FormFlex** application, structured to serve as the foundation for Software Requirement Specification (SRS) and System Architecture Design reports.

---

## 1. Executive Summary

**FormFlex** is a real-time, AI-powered personal fitness tracking application. It uses the device webcam and computer vision (Google MediaPipe + OpenCV) to analyse user posture, count repetitions, and provide immediate text-to-speech audio feedback during exercise. The platform includes user authentication, workout session recording (downloaded as MP4), statistical tracking, dashboard analytics, and progress charts — delivering a complete virtual personal trainer experience.

---

## 2. Software Requirement Specification (SRS)

### 2.1 Scope & Purpose
FormFlex helps users maintain proper biomechanical form during workouts, specifically Push-ups, Squats, Lunges, and Planks. By lowering the barrier to form correction (which traditionally requires a human trainer), the system reduces injury risk and optimises workout efficiency.

### 2.2 Functional Requirements

1. **User Authentication:** Users must be able to register, log in, and maintain a secure session using JWT (JSON Web Tokens). Workout, dashboard, and reports pages require login.
2. **Dashboard & Analytics:** Users must be able to view workout history, recent sessions, total statistics, and consecutive-day streak counts.
3. **Computer Vision Inference:** The application must process webcam streams in real-time to detect 33 body landmarks and calculate joint angles per frame.
4. **Live Feedback & Rep Counting:** The system must accurately count completed reps based on joint angle thresholds. Reps are only counted when form is valid. Voice feedback uses a 1-second debounce to prevent audio overlap.
5. **Skeleton Colour Feedback:** All 33 MediaPipe landmarks are drawn on the annotated frame. The skeleton turns **red** when a hard form failure is detected (red-category feedback), and **green** when form is correct.
6. **Target & Overlay:** Users set a target rep or time count before starting. When the target is reached, a modal overlay appears — the session continues live in the background. The user can choose to keep going or stop and save.
7. **Session Recording & Download:** The annotated canvas (with rep count and feedback overlays) is recorded via the `MediaRecorder` API. On stop, the WebM is uploaded to the backend, converted to MP4 via FFmpeg, and downloaded directly to the user's browser. Nothing is saved permanently on the server.
8. **Data Visualisation:** Users can view line and doughnut charts of workout output over time (Week, Month, Year).

### 2.3 Non-Functional Requirements

1. **Low Latency:** Frames are processed over WebSockets at ~10 FPS without noticeable UI lag.
2. **Privacy:** All video processing occurs on the local machine. Session MP4s are downloaded to the user's own browser — no permanent video files are stored on the server.
3. **Usability:** Light-themed UI (`#f7f6f3` parchment background, sage green accent) with a clear exercise selector, live stats panel, and feedback list.

---

## 3. System Architecture & Design

### 3.1 High-Level Architecture

```
Browser (React SPA)
    │  WebSocket frames (base64 JPEG)
    ▼
FastAPI Backend (Python)
    │  MediaPipe pose estimation per frame
    │  Exercise processor (angle checks, rep counting)
    │  draw_landmarks (red/green skeleton)
    ▼
JSON response: { frame, count, stage, depth_pct, feedbacks }
    │
    ▼
SQLite (gymlytics.db) — users, sessions metadata
```

### 3.2 Frontend Architecture (React)

- **Routing:** Manual `page` state in `App.js`. Auth-guarded pages (`workout`, `dashboard`, `reports`) redirect to login if no user in state.
- **State Management:** JWT token and user object stored in `localStorage`. Loaded into React state on mount.
- **Workout Loop:** `setInterval` at 100ms captures frames from a hidden `<video>` via `<canvas>`, sends as base64 JSON over WebSocket.
- **Recording:** A second hidden canvas (`recordCanvasRef`) receives each annotated frame from the backend and has rep count + feedback text burned in. `MediaRecorder` captures its stream at 15 FPS.
- **Data Visualisation:** `Chart.js` + `react-chartjs-2` for line and doughnut charts.

### 3.3 Backend Architecture (FastAPI + SQLite)

- **REST APIs:** Auth, session upload, dashboard, reports, and MP4 download endpoints.
- **Auth:** `PyJWT` — tokens verified via `verify_token()` which strips the `Bearer ` prefix internally. All protected endpoints receive the token via the `Authorization` HTTP header.
- **Video Conversion:** Uploaded WebM is converted to MP4 by `ffmpeg` (via `subprocess.run`) in the OS temp directory. The resulting MP4 is streamed back to the browser via `FileResponse`. No video files are kept permanently on disk.
- **Database:** SQLite via SQLAlchemy ORM. File: `gymlytics.db` in the project root.

### 3.4 WebSocket Real-Time Pipeline

1. **Capture:** Frontend captures webcam frame every 100ms via canvas.
2. **Transmit:** Base64-encoded JPEG sent as JSON over `ws://localhost:8000/ws/{exercise}`.
3. **Inference:** FastAPI decodes image → NumPy array → MediaPipe `Pose` processes landmarks.
4. **Calculate:** Exercise processor in `src/exercises/` checks joint angle constraints. Sets `is_form_valid`, updates rep count and stage.
5. **Draw:** `mp_drawing.draw_landmarks()` draws all 33 landmarks — green if `is_form_valid`, red if any red-category feedback exists.
6. **Return:** Re-encoded JPEG + metadata returned as JSON: `{"frame": "...", "count": 5, "stage": "UP", "depth_pct": 72.3, "feedbacks": [["Go lower!", "orange"]]}`.

---

## 4. Data Models (Database Schema)

### Table: `users`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | Integer | Primary Key | Unique internal user identifier |
| `email` | String | Unique, Index | User login email |
| `password_hash` | String | | SHA-256 hashed password |
| `name` | String | | Display name |
| `created_at` | DateTime | Default: Now | Account creation timestamp |

### Table: `sessions`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | Integer | Primary Key | Unique session ID |
| `user_id` | Integer | Foreign Key | Maps to `users.id` |
| `exercise` | String | | One of: pushup, squat, lunges, plank |
| `rep_count` | Integer | | Reps completed (or seconds for plank) |
| `duration` | Integer | | Actual elapsed seconds of the session |
| `video_path` | String | Nullable | Temp path of the converted MP4 (OS temp dir) |
| `created_at` | DateTime | Default: Now | Session timestamp |

---

## 5. API Specifications

### REST Endpoints

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `POST` | `/api/auth/register` | None | Register. Body: `{email, password, name}`. Returns user + JWT. |
| `POST` | `/api/auth/login` | None | Login. Body: `{email, password}`. Returns user + JWT. |
| `GET` | `/api/dashboard/{user_id}` | Bearer JWT | Returns streak, total workouts, total time, this-week count, and 5 recent sessions. |
| `POST` | `/api/sessions` | Bearer JWT | Multipart: `video` (WebM blob), `exercise`, `rep_count`, `duration`. Converts to MP4, saves session to DB. Returns `session_id`. |
| `GET` | `/api/sessions/{session_id}/download` | Bearer JWT (owner only) | Converts stored session to MP4 and streams it back for download. |
| `POST` | `/api/convert` | None | Guest endpoint. Accepts WebM, returns converted MP4. |
| `GET` | `/api/reports/{user_id}?range=week\|month\|year` | Bearer JWT | Returns chart labels, session counts, exercise distribution, total reps, and total time (seconds + minutes). |

### WebSocket Endpoint

| Endpoint | Description |
|----------|-------------|
| `WS /ws/{exercise_type}` | Persistent duplex connection. Accepts `{"frame": "<base64>"}` or `{"type": "reset"}`. Returns `{"frame", "count", "stage", "depth_pct", "feedbacks"}` per frame. |

---

## 6. Exercise Processors (`src/exercises/`)

Each processor receives `(image, idx, state)` and returns `(image, state, feedbacks, depth_pct)`.

| File | Key Landmarks Used | Rep Trigger |
|------|--------------------|-------------|
| `pushup.py` | Shoulder, elbow, wrist, hip, ankle | Elbow angle ≤ 90° (DOWN) → ≥ 155° (UP) |
| `squat.py` | Hip, knee, ankle, shoulder | Knee angle ≤ 100° (DOWN) → ≥ 160° (UP) |
| `lunges.py` | Both legs: hip, knee, ankle | Front knee angle ≤ 100° (DOWN) → ≥ 155° (UP) |
| `plank.py` | Shoulder, hip, ankle, elbow, wrist | Body line ≥ 158° → timer increments each second |

Feedback colours: `red` = hard form failure (skeleton turns red), `orange` = minor warning (skeleton stays green), `green` = correct form.

---

## 7. Project File Structure

```text
Main-Project/
├── backend.py              # FastAPI app — REST APIs, WebSocket, CV pipeline
├── models.py               # SQLAlchemy ORM — User and Session models
├── gymlytics.db            # SQLite local database (auto-created on first run)
├── requirements.txt        # Python dependencies
├── src/                    # Backend CV modules
│   ├── exercises/
│   │   ├── pushup.py
│   │   ├── squat.py
│   │   ├── lunges.py
│   │   └── plank.py
│   └── utils.py            # ang(), get_idx_to_coordinates()
└── frontend/               # React SPA
    ├── package.json
    ├── public/
    │   ├── index.html
    │   ├── favicon.ico
    │   ├── manifest.json
    │   └── robots.txt
    └── src/
        ├── App.js           # Page routing and auth state
        ├── header.js        # Global navbar
        ├── styles.js        # CSS-in-JS design system (light theme)
        ├── constants.js     # EXERCISES list, WS_URL, COLOR map
        └── pages/
            ├── LandingPage.js
            ├── LoginPage.js
            ├── TutorialsPage.js
            ├── WorkoutPage.js   # Camera, WebSocket, recording, target overlay
            ├── DashboardPage.js
            └── ReportsPage.js
```
