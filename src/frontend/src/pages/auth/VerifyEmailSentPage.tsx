import { useLocation, Link } from "react-router-dom";
import { useState } from "react";

export default function VerifyEmailSentPage() {
  const location = useLocation();
  const email = (location.state as { email?: string })?.email || "your email";
  const [cooldown, setCooldown] = useState(0);

  const handleResend = () => {
    setCooldown(60);
    const interval = setInterval(() => {
      setCooldown((c) => {
        if (c <= 1) { clearInterval(interval); return 0; }
        return c - 1;
      });
    }, 1000);
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-[var(--color-surface-alt)] px-4">
      <div className="w-full max-w-sm rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-6 text-center shadow-sm">
        <svg className="mx-auto h-12 w-12 text-primary-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
        </svg>
        <h1 className="mt-3 text-lg font-semibold text-[var(--color-text)]">Check Your Email</h1>
        <p className="mt-2 text-sm text-[var(--color-text-secondary)]">
          A verification email has been sent to <strong>{email}</strong>.
        </p>
        <p className="mt-1 text-xs text-[var(--color-text-secondary)]">Click the link in the email to verify your account.</p>

        <button
          onClick={handleResend}
          disabled={cooldown > 0}
          className="mt-4 text-sm text-primary-600 hover:text-primary-700 disabled:text-[var(--color-text-secondary)] disabled:cursor-not-allowed"
        >
          {cooldown > 0 ? `Resend in ${cooldown}s` : "Resend verification email"}
        </button>

        <div className="mt-4">
          <Link to="/login" className="text-sm text-[var(--color-text-secondary)] hover:text-[var(--color-text)]">Back to sign in</Link>
        </div>
      </div>
    </div>
  );
}
