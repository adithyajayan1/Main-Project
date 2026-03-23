import { useState } from "react";
import { GLOBAL_CSS } from "./constants";
import { S } from "./styles";
import Header from "./header";
import LandingPage from "./pages/LandingPage";
import TutorialsPage from "./pages/TutorialsPage";
import WorkoutPage from "./pages/WorkoutPage";


export default function App() {
  // ── Navigation state ──────────────────────────────────────────────────────
  // page: "landing" | "workout" | "tutorials"
  const [page, setPage]         = useState("landing");
  const [jumpTo, setJumpTo]     = useState(null); // pre-selected exercise id

  // ── Global state shared across pages ─────────────────────────────────────
  const [voiceOn, setVoiceOn]   = useState(true);
  const [wsStatus, setWsStatus] = useState("idle");

  /**
   * navigate(page, exerciseId?)
   * Called from any page or the header nav links.
   * exerciseId is optional — used when tutorials page
   * sends user directly to a specific exercise.
   */
  const navigate = (targetPage, exerciseId = null) => {
    setJumpTo(exerciseId);
    setPage(targetPage);
    window.scrollTo(0, 0);
  };

  return (
    <div style={S.root}>
      <style>{GLOBAL_CSS}</style>

      {/* Shared header with nav links on every page */}
      <Header
        page={page}
        navigate={navigate}
        voiceOn={voiceOn}
        setVoiceOn={setVoiceOn}
        wsStatus={wsStatus}
      />

      {/* Page routing */}
      {page === "landing" && (
        <LandingPage navigate={navigate} />
      )}

      {page === "tutorials" && (
        <TutorialsPage navigate={navigate} />
      )}

      {page === "workout" && (
        <WorkoutPage
          key={jumpTo}           // remount when jumping from tutorials
          initialExercise={jumpTo}
          voiceOn={voiceOn}
          wsStatus={wsStatus}
          setWsStatus={setWsStatus}
          navigate={navigate}
        />
      )}
    </div>
  );
}