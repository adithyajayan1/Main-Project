import { EXERCISES } from "../constants";
import { S } from "../styles";

export default function LandingPage({ navigate }) {
  return (
    <main style={S.landingMain}>

      {/* Hero text */}
      <div className="fade-up" style={S.landingHero}>
        <h1 style={S.heroTitle}>
          YOUR <span style={{ color: "#00e676" }}>TRAINER</span>
          <br />IS READY.
        </h1>
        <p style={S.heroSub}>
          Real-time posture correction · Live rep counting · Voice feedback
        </p>
      </div>

      {/* Two main cards */}
      <div className="fade-up-d1" style={S.landingCards} data-el="landing-cards">

        <button onClick={() => navigate("workout")} style={S.landingCard("#00e676")}>
          <span style={S.landingCardIcon}>🏋️</span>
          <span style={S.landingCardTitle}>START WORKOUT</span>
          <span style={S.landingCardDesc}>
            Begin a real-time session.<br />
            Get instant form feedback.
          </span>
          <span style={{ ...S.landingCardBtn, background: "#00e676", color: "#000" }}>
            LET'S GO →
          </span>
        </button>

        <button onClick={() => navigate("tutorials")} style={S.landingCard("#7c6af7")}>
          <span style={S.landingCardIcon}>🎓</span>
          <span style={S.landingCardTitle}>TUTORIALS</span>
          <span style={S.landingCardDesc}>
            Learn perfect form before you train.<br />
            Curated video guides.
          </span>
          <span style={{ ...S.landingCardBtn, background: "#7c6af7", color: "#fff" }}>
            LEARN →
          </span>
        </button>

      </div>

      {/* Exercise preview chips */}
      <div className="fade-up-d2" style={S.exPreviewRow} data-el="ex-preview-row">
        {EXERCISES.map(ex => (
          <div key={ex.id} style={S.exPreviewChip}>
            <span>{ex.icon}</span>
            <span style={{ fontSize: 13, fontWeight: 700 }}>{ex.label}</span>
          </div>
        ))}
      </div>

      <p className="fade-up-d3" style={S.landingFooter}>
        No equipment needed · Works with any webcam
      </p>

    </main>
  );
}