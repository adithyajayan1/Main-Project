import { useState } from "react";
import { S } from "../styles";

export default function LoginPage({ onLogin }) {
  const [isRegister, setIsRegister] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    const endpoint = isRegister ? "http://localhost:8000/api/auth/register" : "http://localhost:8000/api/auth/login";
    const body = isRegister 
      ? { email, password, name } 
      : { email, password };
    
    try {
      const res = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body)
      });
      
      const data = await res.json();
      
      if (res.ok) {
        localStorage.setItem("token", data.token);
        localStorage.setItem("user", JSON.stringify(data.user));
        onLogin(data.user);
      } else {
        setError(data.detail || "Authentication failed");
      }
    } catch (err) {
      setError("Network error. Is backend running?");
    }
  };

  return (
    <div style={S.loginContainer}>
      <h1 style={{ color: "#fff", margin: 0, fontFamily: "'Orbitron', sans-serif" }}>
        {isRegister ? "CREATE ACCOUNT" : "WELCOME BACK"}
      </h1>
      
      {error && <div style={{ color: "#ff1744", fontSize: 14 }}>{error}</div>}

      <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 15 }}>
        {isRegister && (
          <input 
            style={S.input}
            placeholder="Name" 
            value={name} 
            onChange={e => setName(e.target.value)} 
            required 
          />
        )}
        <input 
          style={S.input}
          type="email" 
          placeholder="Email" 
          value={email} 
          onChange={e => setEmail(e.target.value)} 
          required 
        />
        <input 
          style={S.input}
          type="password" 
          placeholder="Password" 
          value={password} 
          onChange={e => setPassword(e.target.value)} 
          required 
        />
        <button type="submit" style={S.authBtn}>
          {isRegister ? "SIGN UP →" : "LOGIN →"}
        </button>
      </form>
      
      <p style={S.toggleText} onClick={() => setIsRegister(!isRegister)}>
        {isRegister ? "Already have account? Login here." : "Need an account? Register here."}
      </p>
    </div>
  );
}
