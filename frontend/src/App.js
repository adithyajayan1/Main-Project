import { useState, useEffect } from "react";
import { GLOBAL_CSS } from "./constants";
import { S } from "./styles";
import Header from "./header";
import LandingPage from "./pages/LandingPage";
import TutorialsPage from "./pages/TutorialsPage";
import WorkoutPage from "./pages/WorkoutPage";
import LoginPage from "./pages/LoginPage";
import DashboardPage from "./pages/DashboardPage";
import ReportsPage from "./pages/ReportsPage";

export default function App() {
  const [page, setPage]         = useState("landing");
  const [jumpTo, setJumpTo]     = useState(null);
  const [voiceOn, setVoiceOn]   = useState(true);
  const [wsStatus, setWsStatus] = useState("idle");
  const [user, setUser] = useState(null);

  useEffect(() => {
    const storedUser = localStorage.getItem("user");
    if (storedUser) {
      setUser(JSON.parse(storedUser));
    }
  }, []);

  const navigate = (targetPage, exerciseId = null) => {
    const authPages = ['workout', 'dashboard', 'reports'];
    if (authPages.includes(targetPage) && !user) {
      setPage("login");
      return;
    }
    
    setJumpTo(exerciseId);
    setPage(targetPage);
    window.scrollTo(0, 0);
  };

  const handleLogin = (user) => {
    setUser(user);
    setPage("dashboard");
  };

  return (
    <div style={S.root}>
      <style>{GLOBAL_CSS}</style>

      <Header
        page={page}
        navigate={navigate}
        voiceOn={voiceOn}
        setVoiceOn={setVoiceOn}
        wsStatus={wsStatus}
        user={user}
        setUser={setUser}
      />

      {page === "landing" && <LandingPage navigate={navigate} />}
      {page === "tutorials" && <TutorialsPage navigate={navigate} />}
      {page === "login" && <LoginPage onLogin={handleLogin} />}
      {page === "dashboard" && <DashboardPage user={user} navigate={navigate} />}
      {page === "reports" && <ReportsPage user={user} />}
      
      {page === "workout" && (
        <WorkoutPage
          key={jumpTo}
          initialExercise={jumpTo}
          voiceOn={voiceOn}
          wsStatus={wsStatus}
          setWsStatus={setWsStatus}
          token={localStorage.getItem("token")}
        />
      )}
    </div>
  );
}