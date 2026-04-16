# GymLytics - Project Documentation & System Design

This document provides a comprehensive A to Z overview of the **GymLytics** application. It is structured to serve as the foundation for your Software Requirement Specification (SRS) and System Architecture Design reports.

---

## 1. Executive Summary

**GymLytics** is a real-time, AI-powered personal fitness tracking application. It utilizes local device cameras and computer vision (via Google MediaPipe and OpenCV) to analyze user posture, count repetitions, and provide immediate, text-to-speech audio feedback during exercise. Furthermore, the platform features persistent user authentication, statistical workout tracking, dashboard analytics, and video session recording, delivering a complete "virtual personal trainer" experience.

---

## 2. Software Requirement Specification (SRS)

### 2.1 Scope & Purpose
The objective of GymLytics is to help users maintain proper biomechanical form during workouts, specifically focusing on exercises like Squats, Push-ups, Lunges, and Planks. By lowering the barrier to entry for form-correction (which traditionally requires a human trainer), the system reduces injury risk and optimizes workout efficiency.

### 2.2 Functional Requirements
1. **User Authentication:** Users must be able to register, log in, and securely maintain a session using JWT (JSON Web Tokens).
2. **Dashboard & Analytics:** Users must be able to view their workout history, recent sessions, total statistics, and streak counts on a centralized dashboard.
3. **Computer Vision Inference:** The application must process webcam streams in real-time to detect body landmarks and calculate joint angles.
4. **Live Feedback & Repetition Counting:** The system must accurately count completed reps based on physics/angle thresholds and speak corrective actions out loud (e.g., "Go lower", "Straighten back") optimized with a 1-second delay threshold to prevent audio overlap.
5. **Session Recording:** The system must allow users to specify a **Target Rep / Time count** prior to starting. Workouts must automatically stop when the target is reached, and the visual layout (including textual feedback and rep numbers) must be dynamically burned onto a hidden canvas and recorded into a `.webm` file.
6. **Data Visualization:** Users must be able to view visual graphs representing their workout outputs mapped over time (Week, Month, Year charts).

### 2.3 Non-Functional Requirements
1. **Low Latency:** Real-time feedback relies on processing frames over WebSockets at roughly 10-15 FPS without noticeable UI lag.
2. **Privacy:** Video processing is kept locally to the machine. Saved session recordings are stored safely in a local `/recordings` folder.
3. **Usability:** The interface must use a modern, dark-themed, glassmorphic UI prioritizing high contrast and layout responsiveness.

---

## 3. System Architecture & Design

### 3.1 High-Level Architecture
The system operates on a decoupled **Client-Server Architecture**. 
* **Client (Frontend):** React.js Single Page Application (SPA).
* **Server (Backend):** Python FastAPI handling REST APIs and WebSocket streams.
* **Database:** Local SQLite utilizing SQLAlchemy ORM.

### 3.2 Frontend Architecture (React)
The frontend utilizes a component-based architectural approach, driven by state management (`useState`, `useEffect`). 
* **Routing:** Handled manually via an `activePage` state within `App.js`.
* **State Management:** JWT Tokens and user IDs are stored in `localStorage` to persist sessions.
* **Data Visualization:** `Chart.js` combined with `react-chartjs-2` handles complex reporting interfaces.
* **Hardware Interfacing:** The HTML5 `MediaRecorder` API and `navigator.mediaDevices` interface handles the transmission of camera payload to the server layer.

### 3.3 Backend Architecture (FastAPI & SQLite)
FastAPI acts as the connective tissue between the React frontend and the computer vision processors.
* **REST APIs:** Endpoints `/api/auth/*` handle standard HTTP requests for login, session posting, and dashboard data. 
* **Auth Layer:** Uses standard `PyJWT` decoding logic validated via middleware dependency injection (`Depends(get_db)`).

### 3.4 WebSocket & Real-Time Pipeline
The defining architectural feature of GymLytics is the real-time AI loop:
1. **Capture:** Frontend captures webcam frame at 100ms intervals.
2. **Transmit:** Encodes image in base64 and ships via WebSocket to `ws://localhost:8000/ws/{exercise}`.
3. **Inference:** FastAPI decodes image into NumPy arrays. MediaPipe `pose_landmarks` algorithm processes the spatial matrix.
4. **Calculate:** Internal `/src/exercises/` logic checks joint angle constraints (e.g., `calculate_angle(hip, knee, ankle)`).
5. **Return:** The backend draws skeletons via OpenCV, re-encodes, and returns JSON: `{"frame": "...", "count": 12, "depth_pct": 80, "feedbacks": []}`.

---

## 4. Data Models (Database Schema)

The architecture utilizes a relational database mapped via SQLAlchemy.

### Table: `users`
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | Integer | Primary Key | Unique internal user identifier. |
| `email` | String | Unique, Index | User login email. |
| `password_hash`| String | | Securely hashed password text. |
| `name` | String | | Display name on the dashboard. |
| `created_at` | DateTime | Default: Now | Account creation timestamp. |

### Table: `sessions`
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | Integer | Primary Key | Unique workout session ID. |
| `user_id` | Integer | Foreign Key | Maps to `users.id`. |
| `exercise` | String | | Enum representation (e.g. "squat", "plank"). |
| `rep_count` | Integer | | Number of reps/seconds completed. |
| `duration` | Integer | | Total active period duration. |
| `video_path`| String | | Path pointing to the saved `.webm` file. |
| `created_at`| DateTime | Default: Now | When the session was logged. |

---

## 5. API Specifications

#### REST Endpoints
* `POST /api/auth/register` - Registers a user. Expects `email`, `password`, `name`. Returns standard User object & JWT.
* `POST /api/auth/login` - Authenticates user. Expects `email`, `password`. Returns JWT Token.
* `GET /api/dashboard/{user_id}` - Expects `Authorization: Bearer <JWT>`. Returns aggregate statistics (streaks, total workouts, etc.) and `recent_sessions` nested dictionary.
* `POST /api/sessions` - Accepts `multipart/form-data`. Expects `video` file blob, `exercise`, `rep_count`, `duration`. Automatically extracts user context from the `Authorization` header. Saves output to `/recordings/`.
* `GET /api/reports/{user_id}?range={week/month/year}` - Computes timeline aggregations of completed sessions mapped logically for Chart.js ingest. 

#### WebSocket Endpoints
* `WS /ws/{exercise_type}` - Persistent duplex connection. Accepts `{"frame":...}` base64 blobs and expects rigorous real-time metadata returns.

---

## 6. Project File Structure
A brief overview of the directory hierarchy mapping to system components:

```text
GymLytics-Personal/
├── backend.py                 # FastAPI Application Core + WebSockets
├── models.py                  # SQLAlchemy Database Schema definitions
├── gymlytics.db               # SQLite local database
├── requirements.txt           # Python dependency manifests
├── recordings/                # Directory containing user video .webm blob artifacts
├── src/                       # Backend Computer Vision Modules
│   ├── exercises/             # Algorithm maps tracking distinct biomechanical movements
│   │   ├── squat.py
│   │   └── ...
│   └── utils.py               # Shared CV geometry mathematical utilities
├── frontend/                  # React Application
│   ├── package.json           # Node.js dependency manifests
│   ├── src/
│   │   ├── App.js             # High-level component routing
│   │   ├── header.js          # Global navbar navigation component
│   │   ├── styles.js          # Global CSS-in-JS design system
│   │   ├── constants.js       # App-wide global states and configuration mapping
│   │   └── pages/             # Distinct DOM Views
│   │       ├── DashboardPage.js
│   │       ├── LoginPage.js
│   │       ├── ReportsPage.js
│   │       └── WorkoutPage.js # MediaRecorder UI + Real-time Canvas overlay generator
```
