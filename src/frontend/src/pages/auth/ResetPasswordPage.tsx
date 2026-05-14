import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { TextInput, Button, Alert } from "@/components/ui";
import PasswordStrengthIndicator from "@/components/auth/PasswordStrengthIndicator";

export default function ResetPasswordPage() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token");

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [passwordConfirm, setPasswordConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleRequest = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.trim()) { setError("Email is required."); return; }
    setLoading(true);
    await new Promise((r) => setTimeout(r, 500));
    setLoading(false);
    setSuccess(true);
  };

  const handleReset = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!password || !passwordConfirm) { setError("All fields are required."); return; }
    if (password !== passwordConfirm) { setError("Passwords do not match."); return; }
    if (password.length < 8) { setError("Password must be at least 8 characters."); return; }
    setLoading(true);
    await new Promise((r) => setTimeout(r, 500));
    setLoading(false);
    setSuccess(true);
  };

  // If success after reset form, show success message
  if (success && token) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[var(--color-surface-alt)] px-4">
        <div className="w-full max-w-sm rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-6 text-center shadow-sm">
          <svg className="mx-auto h-12 w-12 text-success-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <h1 className="mt-3 text-lg font-semibold text-[var(--color-text)]">Password Reset</h1>
          <p className="mt-2 text-sm text-[var(--color-text-secondary)]">Your password has been reset. You can now sign in.</p>
          <Link to="/login" className="mt-4 inline-block">
            <Button>Sign In</Button>
          </Link>
        </div>
      </div>
    );
  }

  // Request form (no token)
  if (!token) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[var(--color-surface-alt)] px-4">
        <div className="w-full max-w-sm rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-6 shadow-sm">
          <h1 className="mb-6 text-center text-xl font-semibold text-[var(--color-text)]">Reset Password</h1>

          {success && (
            <Alert variant="success" className="mb-4">
              If this email is registered, a reset link has been sent.
            </Alert>
          )}

          {error && <Alert variant="error" className="mb-4">{error}</Alert>}

          <form onSubmit={handleRequest} className="space-y-4">
            <label className="flex flex-col gap-1">
              <span className="text-sm font-medium text-[var(--color-text)]">Email</span>
              <TextInput type="email" placeholder="user@example.com" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" />
            </label>
            <Button type="submit" className="w-full" loading={loading}>Send Reset Link</Button>
          </form>

          <p className="mt-4 text-center text-sm">
            <Link to="/login" className="text-[var(--color-text-secondary)] hover:text-[var(--color-text)]">Back to sign in</Link>
          </p>
        </div>
      </div>
    );
  }

  // Reset form (with token)
  return (
    <div className="flex min-h-screen items-center justify-center bg-[var(--color-surface-alt)] px-4">
      <div className="w-full max-w-sm rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-6 shadow-sm">
        <h1 className="mb-6 text-center text-xl font-semibold text-[var(--color-text)]">Set New Password</h1>

        {error && <Alert variant="error" className="mb-4">{error}</Alert>}

        <form onSubmit={handleReset} className="space-y-4">
          <label className="flex flex-col gap-1">
            <span className="text-sm font-medium text-[var(--color-text)]">New Password</span>
            <TextInput type="password" placeholder="••••••••" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="new-password" />
            <PasswordStrengthIndicator password={password} />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-sm font-medium text-[var(--color-text)]">Confirm Password</span>
            <TextInput type="password" placeholder="••••••••" value={passwordConfirm} onChange={(e) => setPasswordConfirm(e.target.value)} autoComplete="new-password" />
          </label>
          <Button type="submit" className="w-full" loading={loading}>Reset Password</Button>
        </form>
      </div>
    </div>
  );
}
