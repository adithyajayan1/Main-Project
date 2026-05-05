export const API_URL = process.env.REACT_APP_API_URL || "http://localhost:8000";
export const WS_URL  = process.env.REACT_APP_WS_URL  || "ws://localhost:8000/ws";

export const COLOR = {
  green:  "#00e676",
  orange: "#ff9100",
  red:    "#ff1744",
  gray:   "#9e9e9e",
};

export const EXERCISES = [
  { id: "pushup", label: "Push Up", icon: "💪", desc: "Side view recommended" },
  { id: "squat",  label: "Squat",   icon: "🦵", desc: "Side view recommended" },
  { id: "lunges", label: "Lunges",  icon: "🏃", desc: "Side view recommended" },
  { id: "plank",  label: "Plank",   icon: "🧘", desc: "Side view · shows hold time" },
];

export const TUTORIALS = [
  {
    id: "pushup",
    label: "Push Up",
    icon: "💪",
    url: "https://www.youtube.com/watch?v=IODxDxX7oi4",
    channel: "Jeff Nippard",
    difficulty: "BEGINNER",
    diffColor: "#00e676",
    tips: [
      "Keep body in a straight line shoulder to ankle",
      "Elbows at 45° from body — don't flare out",
      "Full range of motion — chest close to floor",
      "Don't let hips sag or pike up",
    ],
  },
  {
    id: "squat",
    label: "Squat",
    icon: "🦵",
    url: "https://www.youtube.com/watch?v=ultWZbUMPL8",
    channel: "Alan Thrall",
    difficulty: "INTERMEDIATE",
    diffColor: "#ff9100",
    tips: [
      "Feet shoulder-width apart, toes slightly out",
      "Knees track over toes throughout",
      "Break parallel for full depth",
      "Keep chest upright — don't cave forward",
    ],
  },
  {
    id: "lunges",
    label: "Lunges",
    icon: "🏃",
    url: "https://www.youtube.com/watch?v=QOVaHwm-Q6U",
    channel: "Calisthenic Movement",
    difficulty: "BEGINNER",
    diffColor: "#00e676",
    tips: [
      "Step far enough for 90° front knee angle",
      "Keep torso upright throughout",
      "Back knee should nearly touch the floor",
      "Drive through front heel to stand back up",
    ],
  },
  {
    id: "plank",
    label: "Plank",
    icon: "🧘",
    url: "https://www.youtube.com/watch?v=pSHjTRCQxIw",
    channel: "Athlean-X",
    difficulty: "BEGINNER",
    diffColor: "#00e676",
    tips: [
      "Body forms a straight line head to heels",
      "Engage core and squeeze glutes",
      "Don't hold breath — breathe steadily",
      "Wrists directly under shoulders",
    ],
  },
];

export const GLOBAL_CSS = `
  @import url('https://fonts.googleapis.com/css2?family=Rajdhani:wght@400;600;700&family=Orbitron:wght@700;900&display=swap');
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: #07070f; font-family: 'Rajdhani', sans-serif; }
  ::-webkit-scrollbar { width: 4px; }
  ::-webkit-scrollbar-thumb { background: #1e1e2e; border-radius: 2px; }

  @keyframes flash {
    0%   { color:#fff; text-shadow:0 0 40px #00e676,0 0 80px #00e676; transform:scale(1.15); }
    100% { color:#00e676; text-shadow:0 0 24px #00e67644; transform:scale(1); }
  }
  @keyframes pulse-dot  { 0%,100%{opacity:1} 50%{opacity:0.4} }
  @keyframes slide-in   { from{opacity:0;transform:translateX(-8px)} to{opacity:1;transform:translateX(0)} }
  @keyframes badge-pop  { 0%{transform:scale(0.85);opacity:0} 60%{transform:scale(1.08)} 100%{transform:scale(1);opacity:1} }
  @keyframes fade-up    { from{opacity:0;transform:translateY(20px)} to{opacity:1;transform:translateY(0)} }

  .fb-row      { animation: slide-in 0.25s ease; }
  .counter-val { transition: color 0.2s, text-shadow 0.2s, transform 0.2s; }
  .counter-val.flash { animation: flash 0.4s ease; }
  .stage-badge { animation: badge-pop 0.3s ease; }
  .fade-up     { animation: fade-up 0.5s ease forwards; }
  .fade-up-d1  { animation: fade-up 0.5s 0.1s ease both; }
  .fade-up-d2  { animation: fade-up 0.5s 0.2s ease both; }
  .fade-up-d3  { animation: fade-up 0.5s 0.3s ease both; }
  button:hover { opacity:0.88; transform:translateY(-1px); transition:all 0.15s; }
  a:hover      { opacity:0.8; }
`;