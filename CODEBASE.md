# FormFlex — Full Codebase Documentation

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Technology Stack](#2-technology-stack)
3. [Repository Structure](#3-repository-structure)
4. [Backend](#4-backend)
   - [models.py](#41-modelspy)
   - [backend.py](#42-backendpy)
5. [Computer Vision Engine](#5-computer-vision-engine)
   - [src/utils.py](#51-srcutilspy)
   - [src/exercises/pushup.py](#52-srcexercisespushuppy)
   - [src/exercises/squat.py](#53-srcexercisessquatpy)
   - [src/exercises/lunges.py](#54-srcexerciseslungespy)
   - [src/exercises/plank.py](#55-srcexercisesplankpy)
6. [Frontend](#6-frontend)
   - [App.js](#61-appjs)
   - [constants.js](#62-constantsjs)
   - [styles.js](#63-stylesjs)
   - [header.js](#64-headerjs)
   - [pages/LoginPage.js](#65-pagesloginpagejs)
   - [pages/DashboardPage.js](#66-pagesdashboardpagejs)
   - [pages/WorkoutPage.js](#67-pagesworkoutpagejs)
   - [pages/ReportsPage.js](#68-pagesreportspagejs)
   - [pages/LandingPage.js & TutorialsPage.js](#69-pageslandingpagejs--tutorialspagejs)
7. [Data Flow: Full Request Lifecycle](#7-data-flow-full-request-lifecycle)
8. [Database Schema](#8-database-schema)
9. [API Reference](#9-api-reference)
10. [Configuration & Environment](#10-configuration--environment)

---

## 1. Project Overview

FormFlex is a full-stack AI-powered fitness coaching web application. It uses a webcam to perform real-time human pose detection, analyses exercise form, counts reps (or holds time for planks), and gives live corrective feedback through text and voice. Session statistics are persisted to a cloud database and visualised in a progress reports page. Completed workout sessions can be downloaded as video files directly from the browser.

**Core capabilities:**
- Live pose detection via MediaPipe running on the backend
- Form analysis with prioritised feedback (red critical → orange warning → green good)
- Rep counting for push-ups, squats, and lunges; second-level hold timer for planks
- Depth percentage visualisation showing how close to target range the user is
- Text-to-speech voice feedback using the Web Speech API
- Video recording of the session with rep count and feedback overlaid, downloadable as MP4 or WebM
- JWT-based user authentication
- PostgreSQL database hosted on Supabase
- Progress dashboard and chart-based reports (daily sessions, exercise distribution, totals, best streak)

---

## 2. Technology Stack

### Backend
| Technology | Version | Purpose |
|---|---|---|
| Python | 3.9+ | Runtime |
| FastAPI | latest | REST API + WebSocket server |
| Uvicorn | latest | ASGI server |
| MediaPipe | 0.10.5 | Human pose landmark detection |
| OpenCV (cv2) | latest | Image decoding, drawing, encoding |
| NumPy | latest | Angle maths and array operations |
| SQLAlchemy | latest | ORM for database models and queries |
| psycopg2-binary | latest | PostgreSQL driver |
| PyJWT | latest | JSON Web Token creation and verification |
| python-dotenv | latest | Environment variable loading |
| python-multipart | latest | Multipart form parsing (FastAPI dependency) |
| websockets | latest | WebSocket protocol support |

### Frontend
| Technology | Version | Purpose |
|---|---|---|
| React | 19.2.4 | UI framework |
| react-scripts | 5.0.1 | Build tooling (Create React App) |
| Chart.js | 4.4.0 | Line and doughnut chart rendering |
| react-chartjs-2 | 5.2.0 | React wrapper for Chart.js |
| Web Speech API | browser native | Text-to-speech voice feedback |
| MediaRecorder API | browser native | Canvas video recording |
| WebSocket API | browser native | Real-time frame streaming to backend |

### Infrastructure
| Technology | Purpose |
|---|---|
| Supabase (PostgreSQL) | Hosted database |
| Google Fonts | Orbitron (display) + DM Sans (body) typefaces |

---

## 3. Repository Structure

```
Main-Project/
├── backend.py                  # FastAPI app — all HTTP + WebSocket endpoints
├── models.py                   # SQLAlchemy models + database connection
├── requirements.txt            # Python dependencies
├── CODEBASE.md                 # This document
├── README.md                   # Setup and run instructions
│
├── src/
│   ├── utils.py                # Shared CV geometry utilities
│   └── exercises/
│       ├── pushup.py           # Push-up form analyser
│       ├── squat.py            # Squat form analyser
│       ├── lunges.py           # Lunges form analyser
│       └── plank.py            # Plank hold timer + form analyser
│
└── frontend/
    ├── package.json
    └── src/
        ├── App.js              # Root component, routing, auth state
        ├── constants.js        # WS URL, exercise definitions, CSS animations
        ├── styles.js           # Entire design system as JS objects
        ├── header.js           # Navigation header component
        └── pages/
            ├── LandingPage.js  # Marketing/home page
            ├── TutorialsPage.js# Exercise tutorial cards with YouTube links
            ├── LoginPage.js    # Login + registration form
            ├── DashboardPage.js# User stats + recent sessions
            ├── WorkoutPage.js  # Live workout session (main feature)
            └── ReportsPage.js  # Progress charts and totals
```

---

## 4. Backend

### 4.1 `models.py`

**Purpose:** Defines the database schema and connection using SQLAlchemy ORM.

**Database:** PostgreSQL on Supabase. Connection string is hardcoded in `DATABASE_URL`. Tables are auto-created on first run via `Base.metadata.create_all(bind=engine)`.

#### `User` model
| Column | Type | Details |
|---|---|---|
| `id` | Integer | Primary key, auto-increment |
| `email` | String | Unique, indexed |
| `password_hash` | String | SHA-256 hash of the password (no salt) |
| `name` | String | Display name |
| `created_at` | DateTime | UTC timestamp at creation |

Methods:
- `set_password(password)` — hashes and stores the password using `hashlib.sha256`
- `verify_password(password)` — hashes the input and compares to stored hash

#### `Session` model
| Column | Type | Details |
|---|---|---|
| `id` | Integer | Primary key, auto-increment |
| `user_id` | Integer | Foreign key → `users.id` |
| `exercise` | String | One of: `pushup`, `squat`, `lunges`, `plank` |
| `rep_count` | Integer | Reps completed, or seconds held for plank |
| `duration` | Integer | Estimated seconds: `rep_count × 3` for reps, `rep_count` for plank |
| `video_path` | String | Nullable — legacy column, no longer written |
| `created_at` | DateTime | UTC timestamp at creation |

---

### 4.2 `backend.py`

**Purpose:** The entire backend application. Handles authentication, session persistence, reporting, and the real-time WebSocket pose-detection pipeline.

#### Application setup
- FastAPI app with CORS middleware configured to allow all origins (`*`), all methods, all headers — suitable for local development
- `SECRET_KEY` for JWT signing (should be rotated in production)
- `ALGORITHM = "HS256"` for JWT

#### Authentication helpers
- `create_token(user_id)` — creates a JWT with `user_id` payload and 7-day expiry
- `verify_token(token)` — decodes and validates a JWT, returns `user_id` or raises HTTP 401

#### `POST /api/auth/register`
Accepts `{ email, password, name }`. Checks for duplicate email, creates `User` with hashed password, returns JWT token and user object.

#### `POST /api/auth/login`
Accepts `{ email, password }`. Looks up user by email, verifies password hash, returns JWT token and user object.

#### `GET /api/dashboard/{user_id}`
Returns stats for the user's dashboard:
- `streak` — simplified: 1 if any session exists, else 0 (not fully implemented)
- `total_workouts` — total session count all-time
- `total_minutes` — sum of all session durations in minutes (floor)
- `this_week` — sessions where `created_at` is within the last 7 days
- `recent_sessions` — last 5 sessions with id, exercise, rep_count, duration, created_at

#### `POST /api/sessions`
Accepts JSON body `{ exercise, rep_count, duration }` with `Authorization: Bearer <token>` header. Creates a `Session` record linked to the authenticated user. Called by the frontend when a workout ends.

#### `GET /api/reports/{user_id}`
Query param: `range` = `week` | `month` | `year`. Returns:
- `labels` — every calendar day in the range (no gaps), formatted `YYYY-MM-DD`
- `sessions` — session count per day (0 for days with no sessions)
- `exercises` — list of `{ name, count }` for the doughnut chart
- `total_sessions`, `total_reps`, `total_time` (rounded minutes), `best_streak` (all-time consecutive active days)

**Best streak algorithm:** Fetches all sessions for the user, extracts unique active dates, sorts descending, iterates counting consecutive days (where each day is exactly 1 day before the previous), tracks the longest run.

#### `WebSocket /ws/{exercise_type}`
The real-time pose detection pipeline. One WebSocket connection per workout session.

**State object** (`dict`):
```python
{ "count": 0, "stage": "UP", "flag": False }
```
- `count` — rep count (or seconds for plank)
- `stage` — current phase (`UP` / `DOWN` / `Xs` for plank)
- `flag` — True when a valid bottom position was reached, allows counting the rep on the way back up

**Per-frame pipeline:**
1. Receive JSON `{ "frame": "data:image/jpeg;base64,..." }` from client
2. Base64-decode → NumPy array → OpenCV image
3. Horizontally flip (mirror correction for front-facing camera)
4. Convert BGR → RGB, run `mp.solutions.pose.Pose.process()`
5. Draw MediaPipe skeleton landmarks on the frame
6. Call `get_idx_to_coordinates()` to convert visible landmarks to pixel coords dict
7. Call the exercise-specific processor function with `(image, idx, state)`
8. JPEG-encode the annotated frame, base64-encode
9. Send JSON `{ frame, count, stage, depth_pct, feedbacks }` back to client

**Reset:** If client sends `{ "type": "reset" }`, state is reset to initial values.

**Processor dispatch map:**
```python
EXERCISE_PROCESSORS = {
    "pushup": process_pushup,
    "squat":  process_squat,
    "lunges": process_lunges,
    "plank":  process_plank,
}
```

---

## 5. Computer Vision Engine

### 5.1 `src/utils.py`

**Purpose:** Shared geometric utilities used by all exercise processors.

#### `ang(lineA, lineB) → float`
The core angle calculation function used everywhere. Takes two line segments as pairs of `(x, y)` tuples and returns the angle between them in degrees (0–180).

**Implementation:** Computes vectors from each segment, takes the dot product, divides by the product of magnitudes to get cosine, then `math.acos` for the angle in radians, converts to degrees, applies modulo 360 and a reflection to ensure the result is in the 0–180 range.

#### `get_idx_to_coordinates(image, results, VISIBILITY_THRESHOLD=0.5, PRESENCE_THRESHOLD=0.5) → dict`
Converts MediaPipe pose landmark results into a dictionary mapping landmark index → `(x_px, y_px)` pixel coordinate. Filters out landmarks below the visibility or presence threshold (i.e., landmarks that MediaPipe is not confident about). Landmark indices follow the [MediaPipe Pose topology](https://developers.google.com/mediapipe/solutions/vision/pose_landmarker):
- `0` = nose
- `11/12` = left/right shoulder
- `13/14` = left/right elbow
- `15/16` = left/right wrist
- `23/24` = left/right hip
- `25/26` = left/right knee
- `27/28` = left/right ankle

#### `draw_ellipse(...)` and `convert_arc(...)`
Sub-pixel precision ellipse drawing using OpenCV's `shift` parameter. `convert_arc` computes the centre and radius of a circle passing through three points (two endpoints + a sagitta point). Used for optional arc visualisation.

#### `rescale_frame(frame, percent=75)`
Resizes an OpenCV frame by a percentage using `INTER_AREA` interpolation.

---

### 5.2 `src/exercises/pushup.py`

**Perspective:** Side view. Detects whichever side (left or right) has visible shoulder→elbow→wrist landmarks.

**Key angle:** Elbow angle (shoulder → elbow → wrist).

#### Thresholds
| Constant | Value | Meaning |
|---|---|---|
| `ELBOW_UP` | 155° | Arms extended = UP stage |
| `ELBOW_DOWN` | 90° | Full depth = rep counted |
| `BODY_MIN` | 160° | Minimum body line angle (hips sagging below this) |
| `BODY_MAX` | 195° | Maximum body line angle (hips too high above this) |
| `ELBOW_FLARE_LIMIT` | 80px | Horizontal distance elbow→shoulder before flare warning |
| `HEAD_DROP_OFFSET` | 45px | Nose y below shoulder y = head dropping |
| `NECK_FORWARD_LIM` | 40px | Nose x past shoulder x = neck forward |
| `SHOULDER_SYM_LIM` | 25px | L/R shoulder y difference = body twisting |
| `WRIST_ALIGN_LIM` | 45px | Wrist x past shoulder x = misaligned |
| `HIP_SYM_LIM` | 25px | L/R hip y difference = hip rotation |

#### Form checks (in priority order)
1. **Horizontal inclination** — shoulder→ankle angle must be 50–130°, otherwise not in push-up position
2. **Body line** — shoulder→hip→ankle must be 160–195°; outside this = hips sagging or piked
3. **Elbow flare** — when partially bent, checks horizontal elbow→shoulder offset
4. **Head drop** — nose below shoulder by more than 45px
5. **Neck forward** — nose x more than 40px past shoulder x
6. **Shoulder symmetry** — both shoulders at similar height
7. **Wrist alignment** — wrist x within 45px of shoulder x
8. **Hip symmetry** — both hips at similar height
9. **Wrist bend** — forearm angle 65–115°

#### Rep counting logic
- `depth_pct` = `np.interp(elbow_angle, (90, 155), (100, 0))` — 100% at bottom, 0% at top
- Elbow ≤ 90° and form valid → set `flag = True`, stage = "DOWN"
- Elbow ≥ 155° → if `flag` was set, increment `count`, clear `flag`, stage = "UP"

#### Feedback priority
All feedbacks are sorted: red (0) → orange (1) → gray (2) → green (3). Maximum 7 feedbacks returned.

---

### 5.3 `src/exercises/squat.py`

**Perspective:** Side view. Detects right leg (hip 24, knee 26, ankle 28) or falls back to left leg.

**Key angle:** Knee angle (hip → knee → ankle).

#### Thresholds
| Constant | Value | Meaning |
|---|---|---|
| `KNEE_UP` | 160° | Standing = UP stage |
| `KNEE_DOWN` | 100° | Valid squat depth = rep counted |
| `TORSO_LEAN_LIM` | 30° | Excessive forward lean (red) |
| `TORSO_WARN` | 45° | Moderate forward lean (orange) |
| `KNEE_TOE_BAD` | 65px | Knee x past ankle x = bad knee tracking |
| `KNEE_TOE_WARN` | 35px | Knee x past ankle x = warning |
| `HIP_DROP_LIM` | 20px | L/R hip y difference = lateral shift |
| `KNEE_SYM_LIM` | 30px | L/R knee x close together during squat = caving |
| `SHIN_ANGLE_MIN` | 65° | Shin too vertical |
| `SHIN_ANGLE_MAX` | 95° | Shin too far forward |

#### Form checks
1. **Upright inclination** — shoulder→ankle angle must be < 50° from vertical
2. **Torso angle** — shoulder→hip→knee; below 30° = severely forward (red), 30–45° = warning (orange)
3. **Knee over toe** — knee x vs ankle x; > 65px = red, > 35px = orange
4. **Knee symmetry / caving** — if both knees are tracked and close together during descent
5. **Back lean** — shoulder→hip vs vertical; > 50° = red
6. **Hip symmetry** — L/R hip y difference
7. **Shin angle** — ankle→knee vs vertical; must be 65–95°
8. **Foot width** — if both ankles visible: < 60px = too narrow, > 250px = too wide

#### Rep counting
- `depth_pct` = `np.interp(knee_angle, (100, 160), (100, 0))`
- Knee ≤ 100° and form valid → `flag = True`; bonus message if hip below knee (below parallel)
- Knee ≥ 160° → count rep if `flag` set

---

### 5.4 `src/exercises/lunges.py`

**Perspective:** Side or front-ish view. Detects both legs independently and assigns "front" (lower knee angle = more bent) and "back" roles dynamically each frame.

**Key angle:** Front knee angle (front hip → front knee → front ankle).

#### Thresholds
| Constant | Value | Meaning |
|---|---|---|
| `LUNGE_DOWN` | 100° | Valid lunge depth |
| `LUNGE_UP` | 155° | Standing = rep completed |
| `BACK_KNEE_TARGET` | 95° | Back knee target at bottom |
| `BACK_KNEE_WARN` | 130° | Back knee not bending enough |
| `TORSO_LIM` | 50px | Shoulder x vs hip x = torso lean |
| `FRONT_KNEE_TOE` | 40px | Front knee x vs ankle x = knee over toe |
| `HIP_LEVEL_LIM` | 35px | L/R hip y difference = hip drop |
| `STRIDE_MIN` | 80px | Min ankle separation = stride too short |
| `STRIDE_MAX` | 300px | Max ankle separation = stride too long |
| `SHIN_VERTICAL` | 85° | Front shin angle vs vertical |

#### Form checks
1. **Upright inclination** — shoulder→hip vs vertical < 40°
2. **Torso lean** — shoulder x vs hip x < 50px
3. **Front knee over toe** — front knee x vs front ankle x
4. **Hip level** — both hips at similar height
5. **Stride length** — distance between ankles 80–300px
6. **Front shin angle** — when partially bent, checks shin lean
7. **Back knee bend** — only checked mid-lunge when front angle < 130°

#### Rep counting
- Dynamic leg assignment each frame: `front = min(angles, key=angle)` (most bent = front leg)
- `depth_pct` = `np.interp(front_angle, (100, 155), (100, 0))`
- Front knee ≤ 100° and form valid → `flag = True`
- Front knee ≥ 155° → count rep if `flag` set

---

### 5.5 `src/exercises/plank.py`

**Perspective:** Side view. Uses shoulder→hip→ankle body line angle.

**Key difference from other processors:** Does not count reps — counts **elapsed seconds** of valid hold. Uses `time.time()` stored in state.

#### Thresholds
| Constant | Value | Meaning |
|---|---|---|
| `PLANK_GOOD_MIN` | 165° | Perfect body line minimum |
| `PLANK_GOOD_MAX` | 185° | Perfect body line maximum |
| `PLANK_ACTIVE` | 158° | Minimum to start timer |
| `HIP_SAG_BAD` | 150° | Severely sagging hips |
| `HEAD_OFFSET` | 40px | Nose y vs shoulder y for head position |
| `SHOULDER_WRIST_X` | 50px | Shoulder x vs wrist x = wrist placement |
| `ELBOW_STRAIGHT` | 160° | High plank arm angle |
| `ELBOW_BENT_MIN/MAX` | 80–100° | Forearm plank arm angle |
| `SHOULDER_SYM_LIM` | 25px | L/R shoulder y = body twist |
| `HIP_SYM_LIM` | 20px | L/R hip y = hip rotation |

#### Form checks
1. **Horizontal inclination** — body must be 50–130° from vertical to detect horizontal position
2. **Body line** — shoulder→hip→ankle: > 185° = hips too high, < 150° = severe sag, 150–165° = slightly low (orange)
3. **Head position** — nose y relative to shoulder y ± 40px
4. **Neck alignment** — nose x vs shoulder x < 35px
5. **Wrist under shoulder** — shoulder x vs wrist x < 50px
6. **Elbow angle** — acceptable if ~straight (high plank) or 80–100° (forearm plank)
7. **Shoulder symmetry**
8. **Hip symmetry**

#### Timer logic
- `align_pct` = `np.interp(body_angle, (120, 175), (0, 100))`
- If `body_angle >= 158°` and form valid: start `state['start_time']` (only on first valid frame), set `state['count'] = int(time.time() - start_time)`
- If form breaks: remove `start_time` from state (timer resets), stage = "HOLD"
- Timer resets whenever form is lost — only counts valid hold time

---

## 6. Frontend

### 6.1 `App.js`

**Purpose:** Root component. Owns all top-level state and acts as the router.

**State:**
- `page` — current page string: `landing` | `tutorials` | `login` | `dashboard` | `reports` | `workout`
- `jumpTo` — exercise ID to pre-select when navigating to workout page
- `voiceOn` — global voice feedback toggle, passed to Header and WorkoutPage
- `wsStatus` — WebSocket connection status: `idle` | `connecting` | `connected` | `error`
- `user` — authenticated user object `{ id, email, name }`, persisted in `localStorage`

**On mount:** Reads `user` from `localStorage` to restore session across page reloads.

**`navigate(targetPage, exerciseId)`:** Guards `workout`, `dashboard`, `reports` — redirects to `login` if not authenticated. Also calls `window.scrollTo(0, 0)` on navigation.

**`handleLogin(user)`:** Stores user in state, navigates to dashboard. The login page stores token to `localStorage` directly.

**Rendering:** Simple conditional rendering — one page component visible at a time. `WorkoutPage` uses `key={jumpTo}` so it fully remounts when a different exercise is selected from the landing page.

---

### 6.2 `constants.js`

**Exports:**

- `WS_URL = "ws://localhost:8000/ws"` — WebSocket base URL. Needs to change when deploying backend.
- `COLOR` — map of feedback colour names to hex: `green: #00e676`, `orange: #ff9100`, `red: #ff1744`, `gray: #9e9e9e`
- `EXERCISES` — array of `{ id, label, icon, desc }` for the 4 exercises
- `TUTORIALS` — array of `{ id, label, icon, url, channel, difficulty, diffColor, tips[] }` — YouTube tutorial links with curated form tips
- `GLOBAL_CSS` — CSS string injected into the document via `<style>` in App.js. Contains Google Font imports, CSS resets, and keyframe animations:
  - `flash` — rep counter number flash on new rep
  - `pulse-dot` — recording indicator pulsing dot
  - `slide-in` — feedback row entry animation
  - `badge-pop` — stage badge appearance
  - `fade-up` — page element entrance animations with delay variants

---

### 6.3 `styles.js`

**Purpose:** The entire design system as a single exported `S` object of inline style objects. No CSS files or CSS Modules are used — all styles are co-located here.

**Design system:**
- Background: `#f7f6f3` (warm parchment)
- Surface: `#ffffff`
- Accent: `#3d8c6e` (sage green)
- Text: `#1c1c1e`
- Danger: `#c0392b`
- Fonts: Orbitron (headings/labels), DM Sans (body)

**Major style groups:** `header`, `landing`, `tutorials`, `workout` (session, video panel, stats panel, feedback, depth bar, controls), `dashboard` (stat cards, recent sessions), `reports` (chart cards, time selector, stat items).

Notable patterns:
- Many styles are functions that accept state: `S.exCard(isSelected)`, `S.startBtn(disabled)`, `S.depthFill(pct)`, `S.timeBtn(isActive)` — return different style objects based on condition.
- All layout is done with flexbox.

---

### 6.4 `header.js`

**Purpose:** Persistent navigation bar rendered on all pages.

**Props:** `page`, `navigate`, `voiceOn`, `setVoiceOn`, `wsStatus`, `user`, `setUser`

**Features:**
- Logo click → navigates to `landing`
- Nav links: TRAIN, TUTORIALS, DASHBOARD, REPORTS (DASHBOARD and REPORTS hidden when not logged in)
- Voice toggle button — calls `window.speechSynthesis.cancel()` when turning off to stop any active speech
- WebSocket status dot — colour coded: green (connected), yellow (connecting), red (error), grey (idle)
- Login/Logout button — logout clears `localStorage` items `token` and `user`, sets `user` to null in App state

---

### 6.5 `pages/LoginPage.js`

**Purpose:** Combined login and registration form. Toggled with a "Switch to Register" / "Switch to Login" link.

**On login/register success:** Stores `token` and `user` to `localStorage`, calls `onLogin(user)` prop which navigates to dashboard.

**API calls:**
- Register: `POST /api/auth/register` with `{ email, password, name }`
- Login: `POST /api/auth/login` with `{ email, password }`

---

### 6.6 `pages/DashboardPage.js`

**Purpose:** Landing page for authenticated users. Fetches and displays user stats and recent session history.

**API call:** `GET /api/dashboard/{user.id}` with Bearer token.

**Displays:**
- 4 stat cards: Current Streak, Total Workouts, Total Minutes, This Week
- Recent sessions list (up to 5): exercise name, rep count or hold time, date
- "START WORKOUT" button → navigates to workout page

---

### 6.7 `pages/WorkoutPage.js`

The most complex component. Manages the entire live workout session lifecycle.

**Props:** `initialExercise`, `voiceOn`, `wsStatus`, `setWsStatus`, `token`

#### State and refs
| Name | Type | Purpose |
|---|---|---|
| `selected` | state | Currently selected exercise ID |
| `targetReps` | state | User-set target (reps or seconds for plank) |
| `running` | state | Whether a session is active |
| `count` | state | Current rep/time count from backend |
| `stage` | state | Current movement stage from backend |
| `depthPct` | state | Depth percentage from backend |
| `feedbacks` | state | Array of `[message, color]` pairs |
| `processedFrame` | state | Latest annotated frame as base64 data URL |
| `completionModal` | state | null or `{ count, exercise, duration }` when target reached |
| `flashCount` | state | Triggers CSS flash animation on new rep |
| `videoRef` | ref | Hidden `<video>` element for camera stream |
| `canvasRef` | ref | Hidden `<canvas>` for JPEG frame capture |
| `recordCanvasRef` | ref | Hidden `<canvas>` for recording overlay |
| `wsRef` | ref | Active WebSocket instance |
| `streamRef` | ref | Active MediaStream from camera |
| `intervalRef` | ref | setInterval handle for frame capture |
| `prevCount` | ref | Previous count for flash detection and saveAndDownload |
| `mediaRecorderRef` | ref | MediaRecorder instance |
| `videoChunksRef` | ref | Array of recorded Blob chunks |
| `recordingMimeRef` | ref | `video/mp4` or `video/webm` chosen at start |

#### Session lifecycle

**`startSession()`:**
1. Reset all state
2. Call `startCamera()` — `getUserMedia({ video: { width: 640, height: 480 } })`, attach stream to hidden `<video>`
3. Open WebSocket to `/ws/{exercise_type}`
4. On WebSocket open:
   - Set `running = true`, announce via voice
   - Detect MIME type: `MediaRecorder.isTypeSupported('video/mp4')` → prefer MP4, fallback WebM
   - Create `MediaRecorder` on `recordCanvasRef.captureStream(15fps)`, start chunking every 1s
   - Start `setInterval` at 100ms: capture JPEG frame from `canvasRef`, send to WebSocket
5. On WebSocket message: update all state from response, draw overlays onto `recordCanvasRef` (rep count, feedback bar)
6. On WebSocket close/error: update status

**Recording canvas overlays drawn per frame:**
- Top-left: `REPS: N` (or `TIME: Ns` for plank) in green Orbitron 34px
- Bottom strip: feedback message in colour-coded text with dark background

**`teardownSession()`:**
Closes WebSocket, clears interval, stops camera tracks, resets running/status state. Does not save or download.

**`saveAndDownload(exercise, count, duration)`:**
1. Stops MediaRecorder if still active
2. `POST /api/sessions` with `{ exercise, rep_count: count, duration }` and Bearer token
3. After 500ms (for final chunks): collect all chunks into a `Blob`, create object URL, programmatically click a hidden `<a download>` link, revoke object URL

**`stopSession()` (manual stop button):**
Calls `saveAndDownload` + `teardownSession` immediately. No modal.

**Target reached flow:**
1. `useEffect` watches `count >= targetReps && running`
2. After 1s delay: announces via voice, captures final count, calls `teardownSession()`, sets `completionModal`
3. Modal shows exercise name, rep/time count, estimated duration
4. "SAVE & DOWNLOAD" button → `saveAndDownload()` + close modal
5. "DISCARD" button → close modal without saving

#### Voice feedback
- `speak(text)` — queues utterances using Web Speech API, avoids overlap via `isSpeakingRef`
- Speaks rep number on each new rep
- Speaks exercise start announcement with target
- Bad posture feedback: only speaks if the same message persists for 1 second (debounced via `badPostureTimerRef`), preventing spam

#### Depth bar
Visual progress bar showing `depthPct` (0–100%). 70% marked as "GOOD". For plank shows "ALIGNMENT" label instead of "DEPTH".

---

### 6.8 `pages/ReportsPage.js`

**Purpose:** Progress visualisation over time.

**API call:** `GET /api/reports/{user.id}?range={week|month|year}` on mount and when `timeRange` changes.

**Charts (Chart.js via react-chartjs-2):**
- **Line chart** — sessions per day over the selected range. X-axis = date labels (filled for every day, no gaps). Y-axis = session count. Filled area, tension 0.4 for smooth curve. Colour: sage green.
- **Doughnut chart** — exercise distribution by session count. 5-colour palette.

**Stat cards:**
- Total Sessions
- Total Reps
- Total Time (in minutes, rounded to 1 decimal)
- Best Streak (days)

---

### 6.9 `pages/LandingPage.js` & `TutorialsPage.js`

**LandingPage:** Marketing/home page. Shows hero section and exercise cards. Clicking an exercise card calls `navigate('workout', exerciseId)` to jump directly into a workout for that exercise.

**TutorialsPage:** Maps over `TUTORIALS` from `constants.js`. Each card shows the exercise icon, name, difficulty badge, YouTube link (opens in new tab), instructor channel name, and a bulleted list of 4 form tips.

---

## 7. Data Flow: Full Request Lifecycle

### Workout session (real-time)

```
Browser (100ms interval)
  → capture JPEG from <canvas> via toDataURL
  → WebSocket send: { frame: "data:image/jpeg;base64,..." }

Backend WebSocket handler
  → base64 decode → NumPy array → OpenCV image
  → flip horizontally
  → MediaPipe Pose.process() → 33 landmark positions
  → get_idx_to_coordinates() → { landmark_idx: (x_px, y_px) }
  → exercise processor(image, idx, state)
      → compute angles using ang()
      → check form thresholds
      → update state (count, stage, flag)
      → annotate image with cv2.line/circle/putText
      → return (annotated_image, state, feedbacks, depth_pct)
  → JPEG encode annotated image → base64
  → WebSocket send: { frame, count, stage, depth_pct, feedbacks }

Browser receives message
  → setProcessedFrame(data.frame)  → displayed as <img>
  → setCount, setStage, setDepthPct, setFeedbacks
  → draw count + feedback onto recordCanvasRef
  → useEffect on count: flash animation, voice announcement
  → useEffect on count >= targetReps: show completion modal
```

### Session save (on stop)

```
Browser
  → saveAndDownload(exercise, count, duration)
  → POST /api/sessions { exercise, rep_count, duration }
     Authorization: Bearer <jwt>

Backend
  → verify_token() → user_id
  → INSERT INTO sessions (user_id, exercise, rep_count, duration, created_at)

Browser (500ms later)
  → collect videoChunksRef into Blob
  → URL.createObjectURL(blob)
  → programmatic <a download> click → file saved to user's Downloads
```

---

## 8. Database Schema

```sql
CREATE TABLE users (
    id           SERIAL PRIMARY KEY,
    email        VARCHAR UNIQUE NOT NULL,
    password_hash VARCHAR NOT NULL,
    name         VARCHAR,
    created_at   TIMESTAMP DEFAULT NOW()
);

CREATE TABLE sessions (
    id         SERIAL PRIMARY KEY,
    user_id    INTEGER REFERENCES users(id),
    exercise   VARCHAR,       -- 'pushup' | 'squat' | 'lunges' | 'plank'
    rep_count  INTEGER,       -- reps completed, or seconds held (plank)
    duration   INTEGER,       -- estimated seconds: rep_count*3 or rep_count (plank)
    video_path VARCHAR,       -- legacy, no longer written
    created_at TIMESTAMP DEFAULT NOW()
);
```

---

## 9. API Reference

| Method | Endpoint | Auth | Body / Params | Returns |
|---|---|---|---|---|
| POST | `/api/auth/register` | None | `{ email, password, name }` | `{ token, user }` |
| POST | `/api/auth/login` | None | `{ email, password }` | `{ token, user }` |
| GET | `/api/dashboard/{user_id}` | Bearer | — | `{ stats, recent_sessions }` |
| POST | `/api/sessions` | Bearer | `{ exercise, rep_count, duration }` | `{ session_id, status }` |
| GET | `/api/reports/{user_id}` | Bearer | `?range=week\|month\|year` | `{ labels, sessions, exercises, total_sessions, total_reps, total_time, best_streak }` |
| WS | `/ws/{exercise_type}` | None | JSON frames | JSON responses |

---

## 10. Configuration & Environment

### Backend
- `DATABASE_URL` in `models.py` — PostgreSQL connection string (Supabase)
- `SECRET_KEY` in `backend.py` — JWT signing secret, must be changed in production
- Backend runs on `http://localhost:8000` by default

### Frontend
- `WS_URL` in `constants.js` — WebSocket base URL, must change for deployed backend
- All `fetch` calls hardcode `http://localhost:8000` — must be updated for production
- Frontend runs on `http://localhost:3000` by default

### Running locally
```bash
# Backend
source venv/bin/activate
uvicorn backend:app --reload --port 8000

# Frontend (separate terminal)
cd frontend
npm start
```

### Dependencies
```
# Python (requirements.txt)
mediapipe==0.10.5
numpy
opencv-python
fastapi
uvicorn[standard]
websockets
python-multipart
sqlalchemy
PyJWT
psycopg2-binary
python-dotenv

# Node (frontend/package.json)
react@19.2.4
react-dom@19.2.4
chart.js@4.4.0
react-chartjs-2@5.2.0
react-scripts@5.0.1
```
