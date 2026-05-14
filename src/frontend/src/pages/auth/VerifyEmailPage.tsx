import { useSearchParams, Link } from "react-router-dom";
import { useEffect, useState } from "react";
import { Alert, Button } from "@/components/ui";

export default function VerifyEmailPage() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token");
  const [state, setState] = useState<"loading" | "success" | "expired" | "already-verified">("loading");

  useEffect(() => {
    if (!token) { setState("expired"); return; }
    const timer = setTimeout(() => {
      // Mock: if token starts with "valid", success; else expired
      setState(token.startsWith("valid") ? "success" : "expired");
    }, 800);
    return () => clearTimeout(timer);
  }, [token]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-[var(--color-surface-alt)] px-4">
      <div className="w-full max-w-sm rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-6 text-center shadow-sm">
        {state === "loading" && (
          <div className="py-4">
            <svg className="mx-auto h-10 w-10 animate-spin text-primary-600" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            <p className="mt-3 text-sm text-[var(--color-text-secondary)]">Verifying your email...</p>
          </div>
        )}

        {state === "success" && (
          <>
            <svg className="mx-auto h-12 w-12 text-success-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <h1 className="mt-3 text-lg font-semibold text-[var(--color-text)]">Email Verified</h1>
            <p className="mt-2 text-sm text-[var(--color-text-secondary)]">Your email has been verified. You can now sign in.</p>
            <Link to="/login" className="mt-4 inline-block">
              <Button>Sign In</Button>
            </Link>
          </>
        )}

        {state === "expired" && (
          <>
            <svg className="mx-auto h-12 w-12 text-warning-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
            </svg>
            <h1 className="mt-3 text-lg font-semibold text-[var(--color-text)]">Verification Link Expired</h1>
            <p className="mt-2 text-sm text-[var(--color-text-secondary)]">This verification link has expired or is invalid.</p>
            <Button variant="primary" className="mt-4">Send New Verification Link</Button>
          </>
        )}

        {state === "already-verified" && (
          <Alert variant="info">This email is already verified. You can sign in.</Alert>
        )}
      </div>
    </div>
  );
}
