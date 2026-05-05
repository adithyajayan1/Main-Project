import { S } from "./styles";

export default function Header({ page, navigate, voiceOn, setVoiceOn, wsStatus, user, setUser }) {
  const showVoice = page === "workout";

  const handleLogout = () => {
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    setUser(null);
    navigate("landing");
  };

  return (
    <header style={S.header} data-el="header">

      {/* Left — logo + nav links */}
      <div style={S.headerLeft}>
        <button onClick={() => navigate("landing")} style={S.logoBtn}>
          <span style={S.logoA}>FORM</span>
          <span style={S.logoB}>FLEX</span>
          <span style={S.logoTag} data-el="logo-tag">FITNESS COACH</span>
        </button>

        {/* Nav links */}
        <nav style={S.navLinks} data-el="nav-links">
          <button
            onClick={() => navigate("landing")}
            style={S.navLink(page === "landing")}
          >
            HOME
          </button>
          
          <button
            onClick={() => navigate("dashboard")}
            style={S.navLink(page === "dashboard")}
          >
            DASHBOARD
          </button>
          <button
            onClick={() => navigate("workout")}
            style={S.navLink(page === "workout")}
          >
            WORKOUT
          </button>
          <button
            onClick={() => navigate("reports")}
            style={S.navLink(page === "reports")}
          >
            REPORTS
          </button>

          <button
            onClick={() => navigate("tutorials")}
            style={S.navLink(page === "tutorials")}
          >
            TUTORIALS
          </button>
        </nav>
      </div>

      {/* Right — voice toggle + connection status + auth */}
      <div style={S.headerRight}>
        {showVoice && (
          <button
            onClick={() => {
              setVoiceOn(v => !v);
              window.speechSynthesis?.cancel();
            }}
            style={S.voiceBtn(voiceOn)}
            title={voiceOn ? "Voice ON — click to mute" : "Voice OFF — click to enable"}
          >
            {voiceOn ? "🔊 VOICE ON" : "🔇 VOICE OFF"}
          </button>
        )}

        {showVoice && (
          <div style={S.connWrap}>
            <div style={{
              ...S.dot,
              background:
                wsStatus === "connected"  ? "#00e676" :
                wsStatus === "connecting" ? "#ff9100" :
                wsStatus === "error"      ? "#ff1744" : "#333",
              animation: wsStatus === "connecting" ? "pulse-dot 1s infinite" : "none",
              boxShadow: wsStatus === "connected" ? "0 0 10px #00e676" : "none",
            }} />
            <span style={S.connLabel}>{wsStatus.toUpperCase()}</span>
          </div>
        )}

        {/* User Auth Info */}
        {!showVoice && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '15px' }}>
            {user ? (
              <>
                <span style={{ color: "#1c1c1e", fontSize: "14px", fontWeight: "600" }}>{user.name}</span>
                <button onClick={handleLogout} style={S.logoutBtn}>LOGOUT</button>
              </>
            ) : (
              <button onClick={() => navigate("login")} style={S.loginNavBtn}>LOGIN / SIGNUP</button>
            )}
          </div>
        )}
      </div>

    </header>
  );
}