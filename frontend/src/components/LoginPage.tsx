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

  async function handleSubmit(e?: React.FormEvent<HTMLFormElement>) {
    e?.preventDefault();

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

  function switchMode() {
    setMode((current) => (current === "login" ? "register" : "login"));
    setError(null);
  }

  return (
    <main className="auth-page">
      <section className="auth-card">
        <div className="auth-brand">
          <img className="auth-logo" src="/android-chrome-512x512.png" alt="Welfare Bot" />
          <div>
            <h1>Welfare Bot</h1>
            <p>Care. Support. Well-being.</p>
          </div>
        </div>

        <div className="auth-heading">
          <h2>{mode === "login" ? "Welcome back" : "Create your account"}</h2>
          <p>
            {mode === "login"
              ? "Sign in to continue your daily wellbeing support."
              : "Set up a calm, supportive wellbeing assistant."}
          </p>
        </div>

        {error && <div className="auth-error">{error}</div>}

        <form className="auth-form" onSubmit={handleSubmit}>
          {mode === "register" && (
            <>
              <div className="auth-name-grid">
                <label>
                  First name
                  <input
                    value={firstName}
                    onChange={(e) => setFirstName(e.target.value)}
                    autoComplete="given-name"
                    required
                  />
                </label>

                <label>
                  Last name
                  <input
                    value={lastName}
                    onChange={(e) => setLastName(e.target.value)}
                    autoComplete="family-name"
                  />
                </label>
              </div>

              <label>
                Phone number
                <input
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  placeholder="+358401234567"
                  autoComplete="tel"
                  required
                />
              </label>

              <label>
                Language
                <select value={language} onChange={(e) => setLanguage(e.target.value)}>
                  <option value="fi">Finnish</option>
                  <option value="en">English</option>
                  <option value="sv">Swedish</option>
                </select>
              </label>

              <label>
                Account type
                <select value={role} onChange={(e) => setRole(e.target.value)}>
                  <option value="user">User</option>
                  <option value="admin">Admin / care worker</option>
                </select>
              </label>
            </>
          )}

          <label>
            Email
            <input
              placeholder="name@example.com"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="email"
              required
            />
          </label>

          <label>
            Password
            <input
              placeholder="Your password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete={mode === "login" ? "current-password" : "new-password"}
              required
            />
          </label>

          <button className="auth-submit" type="submit" disabled={loading}>
            {loading ? "Please wait..." : mode === "login" ? "Sign in" : "Create account"}
          </button>
        </form>

        <button type="button" className="auth-switch" onClick={switchMode}>
          {mode === "login" ? "Don’t have an account? Register" : "Already have an account? Sign in"}
        </button>
      </section>
    </main>
  );
}