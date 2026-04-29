import { useMemo, useState } from "react";
import { login, register, requestPasswordReset } from "../api";
import type { UserRegister } from "../types";

interface LoginPageProps {
  onSuccess: () => void;
}

type Mode = "login" | "register";
type RoleValue = "user" | "family" | "";

interface FormErrors {
  first_name?: string;
  last_name?: string;
  email?: string;
  password?: string;
  role?: string;
  consents?: string;
}

export default function LoginPage({ onSuccess }: LoginPageProps) {
  const [mode, setMode] = useState<Mode>("login");
  const [loading, setLoading] = useState(false);
  const [resetLoading, setResetLoading] = useState(false);
  const [resetEmailSent, setResetEmailSent] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showPassword, setShowPassword] = useState(false);
  const [errors, setErrors] = useState<FormErrors>({});

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [phone, setPhone] = useState("");
  const [language, setLanguage] = useState("fi");
  const [role, setRole] = useState<RoleValue>("");

  const [consentPersonalData, setConsentPersonalData] = useState(false);
  const [consentAiAnalysis, setConsentAiAnalysis] = useState(false);
  const [consentMedicalDisclaimer, setConsentMedicalDisclaimer] = useState(false);

  function validateEmail(value: string) {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
  }

  const isEmailValid = validateEmail(email);
  const isPasswordValid = password.length >= 8;
  const allConsents = consentPersonalData && consentAiAnalysis && consentMedicalDisclaimer;

  const registerReady = useMemo(() => {
    return (
      firstName.trim().length > 0 &&
      lastName.trim().length > 0 &&
      email.trim().length > 0 &&
      isEmailValid &&
      isPasswordValid &&
      role === "user" &&
      allConsents
    );
  }, [firstName, lastName, email, isEmailValid, isPasswordValid, role, allConsents]);

  const loginReady = email.trim().length > 0 && isEmailValid && isPasswordValid;
  const submitDisabled = loading || (mode === "register" ? !registerReady : !loginReady);

  function clearFieldError(field: keyof FormErrors) {
    if (errors[field]) {
      setErrors((prev) => ({ ...prev, [field]: undefined }));
    }
  }

  function validateForm(): boolean {
    const nextErrors: FormErrors = {};

    if (mode === "register") {
      if (!firstName.trim()) nextErrors.first_name = "First name is required.";
      if (!lastName.trim()) nextErrors.last_name = "Last name is required.";
      if (!role) nextErrors.role = "Please select an account type.";
      if (role === "family") nextErrors.role = "Family member accounts are currently in development.";
      if (!allConsents) nextErrors.consents = "Please confirm all data and safety statements.";
    }

    if (!email.trim()) {
      nextErrors.email = "Email is required.";
    } else if (!isEmailValid) {
      nextErrors.email = "Please enter a valid email address.";
    }

    if (!password) {
      nextErrors.password = "Password is required.";
    } else if (!isPasswordValid) {
      nextErrors.password = "Password must be at least 8 characters.";
    }

    setErrors(nextErrors);
    return Object.keys(nextErrors).length === 0;
  }

  async function handlePasswordReset() {
    setError(null);
    setResetEmailSent(false);

    if (!email.trim()) {
      setErrors((prev) => ({
        ...prev,
        email: "Enter your email first.",
      }));
      return;
    }

    if (!validateEmail(email)) {
      setErrors((prev) => ({
        ...prev,
        email: "Please enter a valid email address.",
      }));
      return;
    }

    setResetLoading(true);

    try {
      await requestPasswordReset(email.trim());
      setResetEmailSent(true);
    } catch (err: unknown) {
      setError(
        err instanceof Error
          ? err.message
          : "Password reset request failed. Please try again."
      );
    } finally {
      setResetLoading(false);
    }
  }

  async function handleSubmit() {
    setError(null);

    if (!validateForm()) return;

    setLoading(true);

    try {
      if (mode === "login") {
        const result = await login({ email, password });
        localStorage.setItem("access_token", result.access_token);
        localStorage.setItem("current_user", JSON.stringify(result.user));
      } else {
        const payload: UserRegister = {
          first_name: firstName.trim(),
          last_name: lastName.trim(),
          phone_number: phone.trim(),
          language,
          email: email.trim(),
          password,
          role: "user",
        };

        const result = await register(payload);
        localStorage.setItem("access_token", result.access_token);
        localStorage.setItem("current_user", JSON.stringify(result.user));
      }

      onSuccess();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Something went wrong. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  function switchMode(nextMode: Mode) {
    setMode(nextMode);
    setError(null);
    setResetEmailSent(false);
    setErrors({});
    setEmail("");
    setPassword("");
    setFirstName("");
    setLastName("");
    setPhone("");
    setLanguage("fi");
    setRole("");
    setConsentPersonalData(false);
    setConsentAiAnalysis(false);
    setConsentMedicalDisclaimer(false);
    setShowPassword(false);
  }

  return (
    <main className="auth-page">
      <section className="auth-card" aria-labelledby="auth-title">
        <div className="auth-brand">
          <img className="auth-logo" src="/android-chrome-512x512.png" alt="Welfare Bot" />
          <div>
            <div className="auth-brand-name">Welfare Bot</div>
            <div className="auth-brand-subtitle">Care. Support. Well-being.</div>
          </div>
        </div>

        <header className="auth-header">
          <h1 id="auth-title">{mode === "login" ? "Welcome back" : "Create your account"}</h1>
          <p>
            {mode === "login"
              ? "Sign in to continue your wellbeing support."
              : "Set up a calm, supportive wellbeing profile."}
          </p>
        </header>

        {error && (
          <div className="auth-error-banner" role="alert">
            {error}
          </div>
        )}

        {resetEmailSent && mode === "login" && (
          <div className="auth-success-banner" role="status">
            If an account exists for this email, a password reset link has been sent.
          </div>
        )}

        <form
          className="auth-form"
          onSubmit={(event) => {
            event.preventDefault();
            void handleSubmit();
          }}
        >
          {mode === "register" && (
            <section className="auth-section">
              <h2>Personal details</h2>

              <div className="auth-field-grid">
                <div className="auth-field">
                  <label htmlFor="first-name">First name</label>
                  <input
                    id="first-name"
                    type="text"
                    value={firstName}
                    onChange={(e) => {
                      setFirstName(e.target.value);
                      clearFieldError("first_name");
                    }}
                    autoComplete="given-name"
                    disabled={loading}
                    aria-invalid={!!errors.first_name}
                  />
                  {errors.first_name && <span className="auth-field-error">{errors.first_name}</span>}
                </div>

                <div className="auth-field">
                  <label htmlFor="last-name">Last name</label>
                  <input
                    id="last-name"
                    type="text"
                    value={lastName}
                    onChange={(e) => {
                      setLastName(e.target.value);
                      clearFieldError("last_name");
                    }}
                    autoComplete="family-name"
                    disabled={loading}
                    aria-invalid={!!errors.last_name}
                  />
                  {errors.last_name && <span className="auth-field-error">{errors.last_name}</span>}
                </div>
              </div>

              <div className="auth-field">
                <label htmlFor="phone">Phone number</label>
                <input
                  id="phone"
                  type="tel"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  placeholder="+358 40 000 0000"
                  autoComplete="tel"
                  disabled={loading}
                />
                <span className="auth-field-hint">Used for emergency or care contact purposes.</span>
              </div>

              <div className="auth-field">
                <label htmlFor="language">Preferred language</label>
                <select
                  id="language"
                  value={language}
                  onChange={(e) => setLanguage(e.target.value)}
                  disabled={loading}
                >
                  <option value="fi">Finnish</option>
                  <option value="en">English</option>
                  <option value="sv">Swedish</option>
                </select>
              </div>
            </section>
          )}

          <section className="auth-section">
            <h2>Account access</h2>

            <div className="auth-field">
              <label htmlFor="email">Email</label>
              <input
                id="email"
                type="email"
                value={email}
                onChange={(e) => {
                  setEmail(e.target.value);
                  clearFieldError("email");
                  setResetEmailSent(false);
                }}
                placeholder="you@example.com"
                autoComplete="email"
                disabled={loading || resetLoading}
                aria-invalid={!!errors.email}
              />
              {errors.email && <span className="auth-field-error">{errors.email}</span>}
            </div>

            <div className="auth-field">
              <label htmlFor="password">Password</label>
              <div className="auth-password-field">
                <input
                  id="password"
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(e) => {
                    setPassword(e.target.value);
                    clearFieldError("password");
                  }}
                  placeholder="Minimum 8 characters"
                  autoComplete={mode === "login" ? "current-password" : "new-password"}
                  disabled={loading}
                  aria-invalid={!!errors.password}
                />
                <button
                  type="button"
                  className="auth-password-toggle"
                  onClick={() => setShowPassword((value) => !value)}
                  aria-label={showPassword ? "Hide password" : "Show password"}
                >
                  {showPassword ? "Hide" : "Show"}
                </button>
              </div>
              {errors.password ? (
                <span className="auth-field-error">{errors.password}</span>
              ) : (
                <span className="auth-field-hint">Minimum 8 characters.</span>
              )}
            </div>

            {mode === "login" && (
              <div className="auth-forgot-row">
                <button
                  type="button"
                  className="auth-forgot-btn"
                  onClick={() => void handlePasswordReset()}
                  disabled={loading || resetLoading}
                >
                  {resetLoading ? "Sending reset link..." : "Forgot password?"}
                </button>
              </div>
            )}
          </section>

          {mode === "register" && (
            <>
              <section className="auth-section">
                <h2>Account type</h2>

                <div className="auth-field">
                  <div className="auth-role-options" role="radiogroup" aria-label="Account type">
                    <label className={`auth-role-card ${role === "user" ? "selected" : ""}`}>
                      <input
                        type="radio"
                        name="role"
                        checked={role === "user"}
                        onChange={() => {
                          setRole("user");
                          clearFieldError("role");
                        }}
                        disabled={loading}
                      />
                      <span>
                        <strong>Elderly user / Main user</strong>
                        <small>For personal wellbeing check-ins.</small>
                      </span>
                    </label>

                    <label className={`auth-role-card ${role === "family" ? "selected" : ""}`}>
                      <input
                        type="radio"
                        name="role"
                        checked={role === "family"}
                        onChange={() => {
                          setRole("family");
                          clearFieldError("role");
                        }}
                        disabled={loading}
                      />
                      <span>
                        <strong>Family member / Care contact</strong>
                        <small>For supporting someone close.</small>
                      </span>
                    </label>
                  </div>

                  {role === "family" && (
                    <div className="auth-info-banner">
                      Family member accounts are currently in development. For this MVP, please register as the main user.
                    </div>
                  )}

                  {errors.role && <span className="auth-field-error">{errors.role}</span>}
                </div>
              </section>

              <section className="auth-section">
                <h2>Data & safety</h2>

                <div className="auth-consent-box">
                  <label>
                    <input
                      type="checkbox"
                      checked={consentPersonalData}
                      onChange={(e) => {
                        setConsentPersonalData(e.target.checked);
                        clearFieldError("consents");
                      }}
                      disabled={loading}
                    />
                    <span>I agree to the processing of my personal and wellbeing data.</span>
                  </label>

                  <label>
                    <input
                      type="checkbox"
                      checked={consentAiAnalysis}
                      onChange={(e) => {
                        setConsentAiAnalysis(e.target.checked);
                        clearFieldError("consents");
                      }}
                      disabled={loading}
                    />
                    <span>I agree that my messages may be analyzed by AI to assess wellbeing.</span>
                  </label>

                  <label>
                    <input
                      type="checkbox"
                      checked={consentMedicalDisclaimer}
                      onChange={(e) => {
                        setConsentMedicalDisclaimer(e.target.checked);
                        clearFieldError("consents");
                      }}
                      disabled={loading}
                    />
                    <span>
                      I understand this is not a medical service and does not replace professional care.
                    </span>
                  </label>
                </div>

                {errors.consents && <span className="auth-field-error">{errors.consents}</span>}

                <p className="auth-privacy-note">
                  We only collect data necessary to support your wellbeing. You can request deletion anytime.{" "}
                  <a href="/privacy">Privacy Policy</a> · <a href="/terms">Terms of Service</a>
                </p>
              </section>
            </>
          )}

          <button className="auth-submit" type="submit" disabled={submitDisabled}>
            {loading ? "Please wait..." : mode === "login" ? "Sign in" : "Create account"}
          </button>
        </form>

        <p className="auth-switch">
          {mode === "login" ? (
            <>
              Don&apos;t have an account?{" "}
              <button type="button" onClick={() => switchMode("register")}>
                Create account
              </button>
            </>
          ) : (
            <>
              Already have an account?{" "}
              <button type="button" onClick={() => switchMode("login")}>
                Sign in
              </button>
            </>
          )}
        </p>
      </section>
    </main>
  );
}