import { TUTORIALS } from "../constants";
import { S } from "../styles";

export default function TutorialsPage({ navigate }) {
  return (
    <main style={S.tutMain}>

      <div style={S.tutPageHeader}>
        <p style={S.sectionLabel}>🎓 EXERCISE TUTORIALS</p>
        <p style={S.tutSubhead}>
          Study correct form before training. Watch the video, then jump straight
          into your session using the button on each card.
        </p>
      </div>

      <div style={S.tutGrid}>
        {TUTORIALS.map((t, i) => (
          <div
            key={t.id}
            className={`fade-up-d${Math.min(i + 1, 3)}`}
            style={S.tutCard}
          >
            {/* Card header */}
            <div style={S.tutCardTop}>
              <span style={S.tutCardIcon}>{t.icon}</span>
              <div>
                <p style={S.tutCardName}>{t.label}</p>
                <span style={{
                  ...S.diffBadge,
                  color: t.diffColor,
                  borderColor: t.diffColor + "60",
                  background: t.diffColor + "14",
                }}>
                  {t.difficulty}
                </span>
              </div>
            </div>

            {/* Form tips */}
            <div style={S.tutTips}>
              <p style={S.tutTipsTitle}>KEY FORM POINTS</p>
              {t.tips.map((tip, j) => (
                <div key={j} style={S.tutTipRow}>
                  <span style={S.tutTipDot}>▸</span>
                  <span style={S.tutTipTxt}>{tip}</span>
                </div>
              ))}
            </div>

            {/* Action buttons */}
            <div style={S.tutBtnRow}>
              <a
                href={t.url}
                target="_blank"
                rel="noreferrer"
                style={S.watchBtn}
              >
                ▶ WATCH ON YOUTUBE
                <span style={S.channelTag}>{t.channel}</span>
              </a>

              <button
                onClick={() => navigate("workout", t.id)}
                style={S.practiceBtn}
              >
                START {t.label.toUpperCase()} →
              </button>
            </div>

          </div>
        ))}
      </div>

    </main>
  );
}