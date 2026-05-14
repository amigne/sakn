import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { TextInput, Button, Alert } from "@/components/ui";
import PasswordStrengthIndicator from "@/components/auth/PasswordStrengthIndicator";

export default function RegisterPage() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [password, setPassword] = useState("");
  const [passwordConfirm, setPasswordConfirm] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!email || !password || !passwordConfirm) { setError("All fields are required."); return; }
    if (password !== passwordConfirm) { setError("Passwords do not match."); return; }
    if (password.length < 8) { setError("Password must be at least 8 characters."); return; }
    setLoading(true);
    await new Promise((r) => setTimeout(r, 500));
    setLoading(false);
    navigate("/verify-email-sent", { state: { email } });
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-[var(--color-surface-alt)] px-4">
      <div className="w-full max-w-sm rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-6 shadow-sm">
        <h1 className="mb-6 text-center text-xl font-semibold text-[var(--color-text)]">Create Account</h1>

        {error && <Alert variant="error" className="mb-4">{error}</Alert>}

        <form onSubmit={handleSubmit} className="space-y-4">
          <label className="flex flex-col gap-1">
            <span className="text-sm font-medium text-[var(--color-text)]">Email</span>
            <TextInput type="email" placeholder="user@example.com" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" />
          </label>

          <div className="grid grid-cols-2 gap-3">
            <label className="flex flex-col gap-1">
              <span className="text-sm font-medium text-[var(--color-text)]">First Name</span>
              <TextInput type="text" value={firstName} onChange={(e) => setFirstName(e.target.value)} autoComplete="given-name" />
            </label>
            <label className="flex flex-col gap-1">
              <span className="text-sm font-medium text-[var(--color-text)]">Last Name</span>
              <TextInput type="text" value={lastName} onChange={(e) => setLastName(e.target.value)} autoComplete="family-name" />
            </label>
          </div>

          <label className="flex flex-col gap-1">
            <span className="text-sm font-medium text-[var(--color-text)]">Password</span>
            <div className="relative">
              <TextInput
                type={showPassword ? "text" : "password"}
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="new-password"
              />
              <button
                type="button"
                className="absolute end-2 top-1/2 -translate-y-1/2 text-[var(--color-text-secondary)] hover:text-[var(--color-text)]"
                onClick={() => setShowPassword(!showPassword)}
                aria-label={showPassword ? "Hide password" : "Show password"}
              >
                <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  {showPassword ? (
                    <>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19m-6.72-1.07a3 3 0 11-4.24-4.24" />
                      <line x1="1" y1="1" x2="23" y2="23" />
                    </>
                  ) : (
                    <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0zM2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                  )}
                </svg>
              </button>
            </div>
            <PasswordStrengthIndicator password={password} />
          </label>

          <label className="flex flex-col gap-1">
            <span className="text-sm font-medium text-[var(--color-text)]">Confirm Password</span>
            <TextInput type="password" placeholder="••••••••" value={passwordConfirm} onChange={(e) => setPasswordConfirm(e.target.value)} autoComplete="new-password" />
          </label>

          <Button type="submit" className="w-full" loading={loading}>Create Account</Button>
        </form>

        <p className="mt-4 text-center text-sm text-[var(--color-text-secondary)]">
          Already have an account? <Link to="/login" className="text-primary-600 hover:text-primary-700">Sign in</Link>
        </p>
      </div>
    </div>
  );
}
