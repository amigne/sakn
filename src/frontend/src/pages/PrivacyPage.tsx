import PageLayout from "@/components/layout/PageLayout";

export default function PrivacyPage() {
  return (
    <PageLayout>
      <div className="max-w-2xl mx-auto prose prose-sm dark:prose-invert">
        <h1 className="text-lg font-semibold text-[var(--color-text)] mb-4">Privacy &amp; Cookies</h1>

        <section className="mb-6">
          <h2 className="text-base font-medium text-[var(--color-text)] mb-2">Cookies</h2>
          <div className="space-y-3 text-sm text-[var(--color-text-secondary)]">
            <p>
              SAKN uses only <strong>strictly necessary</strong> cookies to operate the service.
              Under the ePrivacy Directive (Art. 5.3) and GDPR, these cookies are exempt from consent
              requirements — they are essential for the security and functionality you expect.
            </p>

            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="border-b border-[var(--color-border)]">
                    <th scope="col" className="py-2 pe-4 text-xs font-semibold uppercase">Cookie</th>
                    <th scope="col" className="py-2 pe-4 text-xs font-semibold uppercase">Purpose</th>
                    <th scope="col" className="py-2 pe-4 text-xs font-semibold uppercase">Duration</th>
                    <th scope="col" className="py-2 text-xs font-semibold uppercase">Access</th>
                  </tr>
                </thead>
                <tbody className="align-top">
                  <tr className="border-b border-[var(--color-border)]">
                    <td className="py-2 pe-4 font-mono text-xs">sakn_session</td>
                    <td className="py-2 pe-4">Authenticates your session and keeps you signed in</td>
                    <td className="py-2 pe-4 text-xs">24 hours (renews with activity)</td>
                    <td className="py-2 text-xs">Server only (httpOnly)</td>
                  </tr>
                  <tr className="border-b border-[var(--color-border)]">
                    <td className="py-2 pe-4 font-mono text-xs">sakn_csrf</td>
                    <td className="py-2 pe-4">Prevents cross-site request forgery attacks</td>
                    <td className="py-2 pe-4 text-xs">Session</td>
                    <td className="py-2 text-xs">JavaScript can read (for CSRF header)</td>
                  </tr>
                </tbody>
              </table>
            </div>

            <p>
              No tracking, analytics, advertising, or third-party cookies are ever set.
              No personal data is shared with external services.
            </p>
          </div>
        </section>

        <section className="mb-6">
          <h2 className="text-base font-medium text-[var(--color-text)] mb-2">Data we store</h2>
          <div className="text-sm text-[var(--color-text-secondary)] space-y-2">
            <p>When you create an account, SAKN stores:</p>
            <ul className="list-disc ps-5 space-y-1">
              <li>Your email address, first name, and last name</li>
              <li>A cryptographic hash of your password (the password itself is never stored)</li>
              <li>Your language, theme, and locale preferences</li>
              <li>Active session information (IP address, browser type, timestamps)</li>
            </ul>
            <p>
              Session logs are retained for 90 days by default, then automatically deleted.
              Security events (failed logins, blocked requests) are retained for 90 days.
            </p>
          </div>
        </section>

        <section className="mb-6">
          <h2 className="text-base font-medium text-[var(--color-text)] mb-2">Your rights</h2>
          <div className="text-sm text-[var(--color-text-secondary)] space-y-2">
            <p>Under the GDPR, you have the right to:</p>
            <ul className="list-disc ps-5 space-y-1">
              <li><strong>Access</strong> your personal data</li>
              <li><strong>Rectify</strong> inaccurate data (you can edit your profile directly)</li>
              <li><strong>Delete</strong> your account and associated data</li>
              <li><strong>Portability</strong> — request a copy of your data</li>
            </ul>
            <p>
              To exercise these rights, contact the data controller at the email address below.
            </p>
          </div>
        </section>

        <section className="mb-6">
          <h2 className="text-base font-medium text-[var(--color-text)] mb-2">Data controller</h2>
          <p className="text-sm text-[var(--color-text-secondary)]">
            Yann GAUTERON<br />
            Email: yann@gauteron.me<br />
            Hosting: Hetzner, Germany (GDPR-compliant)
          </p>
        </section>

        <p className="text-xs text-[var(--color-text-secondary)]">
          Last updated: 2026-05-15
        </p>
      </div>
    </PageLayout>
  );
}
