import { useState } from "react";
import { login, register } from "../api";
import type { UserRegister } from "../types";

interface Props {
  onSuccess: () => void;
}

export default function LoginPage({ onSuccess }: Props) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [phone, setPhone] = useState("");
  const [language, setLanguage] = useState("fi");
  const [role, setRole] = useState("user");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit() {
    setError(null);
    setLoading(true);
    try {
      if (mode === "login") {
        const result = await login({ email, password });
        localStorage.setItem("access_token", result.access_token);
        localStorage.setItem("current_user", JSON.stringify(result.user));
      } else {
        const payload: UserRegister = {
          first_name: firstName,
          last_name: lastName,
          phone_number: phone,
          language,
          email,
          password,
          role,
        };
        const result = await register(payload);
        localStorage.setItem("access_token", result.access_token);
        localStorage.setItem("current_user", JSON.stringify(result.user));
      }
      onSuccess();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={styles.container}>
      <div style={styles.card}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: "12px", marginBottom: "8px" }}>
          <img 
            src="/android-chrome-512x512.png" 
            alt="Welfare Bot" 
            style={{ width: "40px", height: "40px", objectFit: "contain", borderRadius: "10px" }} 
          />
          <h1 style={{ fontSize: "24px", fontWeight: "800", color: "#0D2152" }}>Welfare Bot</h1>
        </div>
        <p style={styles.subtitle}>
          {mode === "login" ? "Sign in to your account" : "Create a new account"}
        </p>

        {error && <div style={styles.error}>{error}</div>}

        {mode === "register" && (
          <>
            <input style={styles.input} placeholder="First name" value={firstName} onChange={(e) => setFirstName(e.target.value)} />
            <input style={styles.input} placeholder="Last name" value={lastName} onChange={(e) => setLastName(e.target.value)} />
            <input style={styles.input} placeholder="Phone number (e.g. +358401234567)" value={phone} onChange={(e) => setPhone(e.target.value)} />
            <select style={styles.input} value={language} onChange={(e) => setLanguage(e.target.value)}>
              <option value="fi">Finnish</option>
              <option value="en">English</option>
              <option value="sv">Swedish</option>
            </select>
            <select style={styles.input} value={role} onChange={(e) => setRole(e.target.value)}>
              <option value="user">User (elderly person)</option>
              <option value="admin">Admin (care worker)</option>
            </select>
          </>
        )}

        <input style={styles.input} placeholder="Email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
        <input style={styles.input} placeholder="Password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} onKeyDown={(e) => e.key === "Enter" && void handleSubmit()} />

        <button style={styles.button} onClick={() => void handleSubmit()} disabled={loading}>
          {loading ? "Please wait..." : mode === "login" ? "Sign in" : "Create account"}
        </button>

        <p style={styles.toggle}>
          {mode === "login" ? "Don't have an account? " : "Already have an account? "}
          <span style={styles.link} onClick={() => { setMode(mode === "login" ? "register" : "login"); setError(null); }}>
            {mode === "login" ? "Register" : "Sign in"}
          </span>
        </p>
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: { minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", background: "#0f172a" },
  card: { background: "#1e293b", padding: "40px", borderRadius: "16px", width: "100%", maxWidth: "400px", display: "flex", flexDirection: "column", gap: "12px" },
  title: { color: "#f8fafc", fontSize: "28px", margin: 0, textAlign: "center" },
  subtitle: { color: "#94a3b8", textAlign: "center", margin: 0, fontSize: "14px" },
  input: { padding: "12px 16px", borderRadius: "8px", border: "1px solid #334155", background: "#0f172a", color: "#f8fafc", fontSize: "15px", outline: "none", width: "100%", boxSizing: "border-box" as const },
  button: { padding: "12px", borderRadius: "8px", background: "#3b82f6", color: "white", border: "none", fontSize: "16px", cursor: "pointer", fontWeight: 600, marginTop: "4px" },
  error: { background: "#450a0a", color: "#fca5a5", padding: "10px 14px", borderRadius: "8px", fontSize: "14px" },
  toggle: { textAlign: "center", color: "#94a3b8", fontSize: "14px", margin: 0 },
  link: { color: "#3b82f6", cursor: "pointer", fontWeight: 600 },
};