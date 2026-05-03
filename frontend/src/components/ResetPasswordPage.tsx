import { useState } from "react";

const API_BASE = "/api/v1";

interface Props {
  token: string;
  onSuccess: () => void;
}

export default function ResetPasswordPage({ token, onSuccess }: Props) {
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const passwordsMatch = password === confirmPassword;
  const isValid = password.length >= 8 && confirmPassword.length >= 8 && passwordsMatch;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!isValid) return;

    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`${API_BASE}/auth/reset-password`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token, new_password: password }),
      });

      const data = await response.json();

      if (!response.ok) {
        setError(data.detail || "Password reset failed. The link may have expired.");
        return;
      }

      setSuccess(true);
      setTimeout(() => {
        // Remove token from URL and go back to login
        window.history.replaceState({}, "", "/");
        onSuccess();
      }, 2000);
    } catch {
      setError("Something went wrong. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="auth-page">
      <section className="auth-card" aria-labelledby="reset-title">
        <div className="auth-brand">
          <img className="auth-logo" src="/android-chrome-512x512.png" alt="Welfare Bot" />
          <div>
            <div className="auth-brand-name">Welfare Bot</div>
            <div className="auth-brand-subtitle">Care. Support. Well-being.</div>
          </div>
        </div>

        <header className="auth-header">
          <h1 id="reset-title">Set a new password</h1>
          <p>Enter your new password below.</p>
        </header>

        {success ? (
          <div className="auth-success-banner" role="status">
            Password changed successfully. Redirecting to login...
          </div>
        ) : (
          <>
            {error && (
              <div className="auth-error-banner" role="alert">{error}</div>
            )}

            <form className="auth-form" onSubmit={handleSubmit}>
              <section className="auth-section">
                <h2>New password</h2>

                <div className="auth-field">
                  <label htmlFor="new-password">Password</label>
                  <div className="auth-password-field">
                    <input
                      id="new-password"
                      type={showPassword ? "text" : "password"}
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder="Minimum 8 characters"
                      autoComplete="new-password"
                      disabled={loading}
                    />
                    <button
                      type="button"
                      className="auth-password-toggle"
                      onClick={() => setShowPassword((v) => !v)}
                    >
                      {showPassword ? "Hide" : "Show"}
                    </button>
                  </div>
                  <span className="auth-field-hint">Minimum 8 characters.</span>
                </div>

                <div className="auth-field">
                  <label htmlFor="confirm-new-password">Confirm password</label>
                  <div className="auth-password-field">
                    <input
                      id="confirm-new-password"
                      type={showPassword ? "text" : "password"}
                      value={confirmPassword}
                      onChange={(e) => setConfirmPassword(e.target.value)}
                      placeholder="Repeat your password"
                      autoComplete="new-password"
                      disabled={loading}
                    />
                  </div>
                  {confirmPassword && !passwordsMatch && (
                    <span className="auth-field-error">Passwords do not match.</span>
                  )}
                  {confirmPassword && passwordsMatch && password.length >= 8 && (
                    <span style={{ color: "#16a34a", fontSize: 13 }}>Passwords match</span>
                  )}
                </div>
              </section>

              <button
                className="auth-submit"
                type="submit"
                disabled={!isValid || loading}
              >
                {loading ? "Saving..." : "Set new password"}
              </button>
            </form>
          </>
        )}
      </section>
    </main>
  );
}


