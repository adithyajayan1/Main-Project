import { useState, useEffect } from "react";
import { S } from "../styles";
import { EXERCISES, API_URL } from "../constants";

const StatCard = ({ icon, label, value }) => (
  <div style={{ ...S.sessionCard, flexDirection: 'column', alignItems: 'center', gap: 10, padding: 30 }}>
    <div style={{ fontSize: 32 }}>{icon}</div>
    <div style={{ fontSize: 24, fontWeight: 'bold', color: '#00e676', fontFamily: "'Orbitron', sans-serif" }}>{value}</div>
    <div style={{ fontSize: 12, color: '#888', letterSpacing: '0.1em' }}>{label.toUpperCase()}</div>
  </div>
);

const SessionCard = ({ session, onClick }) => (
  <div style={S.sessionCard} onClick={onClick}>
    <div style={S.sessionCardLeft}>
      <span style={S.sessionTitle}>{session.exercise.toUpperCase()}</span>
      <span style={S.sessionMeta}>
        {new Date(session.created_at).toLocaleString()} • {session.duration} sec
      </span>
    </div>
    <div style={S.sessionBadge}>
      {session.rep_count} {session.exercise === 'plank' ? 'SEC' : 'REPS'}
    </div>
  </div>
);

export default function DashboardPage({ user, navigate }) {
  const [stats, setStats] = useState(null);
  const [recentSessions, setRecentSessions] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API_URL}/api/dashboard/${user.id}`, {
      headers: { "Authorization": `Bearer ${localStorage.getItem("token")}` }
    })
      .then(res => res.json())
      .then(data => {
        setStats(data.stats);
        setRecentSessions(data.recent_sessions);
        setLoading(false);
      })
      .catch(err => {
        console.error("Dashboard fetch error:", err);
        setLoading(false);
      });
  }, [user.id]);

  if (loading) return <div style={{...S.dashboard, textAlign: 'center', marginTop: 100}}>Loading...</div>;

  return (
    <div style={S.dashboard} data-el="dashboard">
      <h1 style={{ fontFamily: "'Orbitron', sans-serif", marginBottom: 30 }}>
        WELCOME BACK, <span style={{ color: '#00e676' }}>{user.name.toUpperCase()}</span>!
      </h1>

      <div style={S.statsGrid} data-el="stats-grid">
        <StatCard icon="🔥" label="Streak" value={`${stats?.streak || 0} DAYS`} />
        <StatCard icon="🏋️" label="Total Workouts" value={stats?.total_workouts || 0} />
        <StatCard icon="⏱️" label="Total Time" value={`${stats?.total_minutes || 0} MIN`} />
        <StatCard icon="🎯" label="This Week" value={stats?.this_week || 0} />
      </div>

    
      <section style={S.recentSection}>
        <h2 style={{ fontSize: 14, letterSpacing: '0.2em', color: '#888', marginBottom: 20 }}>RECENT SESSIONS</h2>
        {recentSessions.length === 0 ? (
          <div style={{ color: "#555", fontStyle: "italic" }}>No sessions yet. Time to start training!</div>
        ) : (
          recentSessions.map(session => (
            <SessionCard key={session.id} session={session} onClick={() => {}} />
          ))
        )}
      </section>
    </div>
  );
}
