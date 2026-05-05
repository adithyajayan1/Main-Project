import { useState } from "react";
import { S } from "./styles";

const NAV_ITEMS = [
  { id: "landing",   label: "HOME" },
  { id: "dashboard", label: "DASHBOARD" },
  { id: "workout",   label: "WORKOUT" },
  { id: "reports",   label: "REPORTS" },
  { id: "tutorials", label: "TUTORIALS" },
];

export default function Header({ page, navigate, voiceOn, setVoiceOn, wsStatus, user, setUser }) {
  const [menuOpen, setMenuOpen] = useState(false);
  const showVoice = page === "workout";

  const handleLogout = () => {
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    setUser(null);
    navigate("landing");
    setMenuOpen(false);
  };

  const handleNav = (target) => {
    navigate(target);
    setMenuOpen(false);
  };

  return (
    <>
      <header style={S.header} data-el="header">

        {/* Left — logo + desktop nav */}
        <div style={S.headerLeft}>
          <button onClick={() => handleNav("landing")} style={S.logoBtn}>
            <span style={S.logoA}>FORM</span>
            <span style={S.logoB}>FLEX</span>
            <span style={S.logoTag} data-el="logo-tag">FITNESS COACH</span>
          </button>

          <nav style={S.navLinks} data-el="nav-links" className="desktop-nav">
            {NAV_ITEMS.map(item => (
              <button
                key={item.id}
                onClick={() => handleNav(item.id)}
                style={S.navLink(page === item.id)}
              >
                {item.label}
              </button>
            ))}
          </nav>
        </div>

        {/* Right — voice + auth + hamburger */}
        <div style={{ ...S.headerRight, gap: 10 }}>
          {showVoice && (
            <button
              onClick={() => { setVoiceOn(v => !v); window.speechSynthesis?.cancel(); }}
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

          {!showVoice && (
            <div className="desktop-nav" style={{ display: "flex", alignItems: "center", gap: 15 }}>
              {user ? (
                <>
                  <span style={{ color: "#1c1c1e", fontSize: 14, fontWeight: 600 }}>{user.name}</span>
                  <button onClick={handleLogout} style={S.logoutBtn}>LOGOUT</button>
                </>
              ) : (
                <button onClick={() => handleNav("login")} style={S.loginNavBtn}>LOGIN / SIGNUP</button>
              )}
            </div>
          )}

          {/* Hamburger — mobile only */}
          <button
            className="hamburger"
            onClick={() => setMenuOpen(o => !o)}
            style={{
              display: "none",
              background: "none",
              border: "1px solid #e8e6e1",
              borderRadius: 8,
              padding: "6px 10px",
              cursor: "pointer",
              fontSize: 18,
              color: "#1c1c1e",
              lineHeight: 1,
            }}
            aria-label="Menu"
          >
            {menuOpen ? "✕" : "☰"}
          </button>
        </div>
      </header>

      {/* Mobile dropdown menu */}
      {menuOpen && (
        <div
          className="mobile-menu"
          style={{
            position: "fixed",
            top: 57,
            left: 0,
            right: 0,
            background: "rgba(247,246,243,0.98)",
            backdropFilter: "blur(12px)",
            borderBottom: "1px solid #e8e6e1",
            zIndex: 99,
            display: "flex",
            flexDirection: "column",
            padding: "8px 0",
            boxShadow: "0 8px 24px rgba(0,0,0,0.08)",
          }}
        >
          {NAV_ITEMS.map(item => (
            <button
              key={item.id}
              onClick={() => handleNav(item.id)}
              style={{
                background: page === item.id ? "#e8f4ef" : "none",
                border: "none",
                padding: "14px 24px",
                textAlign: "left",
                fontSize: 14,
                fontWeight: 600,
                letterSpacing: "0.08em",
                color: page === item.id ? "#3d8c6e" : "#1c1c1e",
                cursor: "pointer",
                fontFamily: "inherit",
                borderLeft: page === item.id ? "3px solid #3d8c6e" : "3px solid transparent",
              }}
            >
              {item.label}
            </button>
          ))}

          <div style={{ borderTop: "1px solid #e8e6e1", margin: "8px 0" }} />

          {user ? (
            <>
              <div style={{ padding: "8px 24px", fontSize: 13, color: "#6b6b72", fontWeight: 600 }}>
                {user.name}
              </div>
              <button
                onClick={handleLogout}
                style={{
                  background: "none", border: "none", padding: "14px 24px",
                  textAlign: "left", fontSize: 14, fontWeight: 600,
                  letterSpacing: "0.08em", color: "#c0392b", cursor: "pointer",
                  fontFamily: "inherit", borderLeft: "3px solid transparent",
                }}
              >
                LOGOUT
              </button>
            </>
          ) : (
            <button
              onClick={() => handleNav("login")}
              style={{
                background: "none", border: "none", padding: "14px 24px",
                textAlign: "left", fontSize: 14, fontWeight: 600,
                letterSpacing: "0.08em", color: "#3d8c6e", cursor: "pointer",
                fontFamily: "inherit", borderLeft: "3px solid transparent",
              }}
            >
              LOGIN / SIGNUP
            </button>
          )}
        </div>
      )}
    </>
  );
}
