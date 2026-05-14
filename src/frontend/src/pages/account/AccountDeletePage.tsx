import { useState } from "react";
import { useNavigate } from "react-router-dom";
import PageLayout from "@/components/layout/PageLayout";
import { TextInput, Button, Alert, Modal } from "@/components/ui";
import { useAuthStore } from "@/stores/authStore";

export default function AccountDeletePage() {
  const navigate = useNavigate();
  const logout = useAuthStore((s) => s.logout);
  const [password, setPassword] = useState("");
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleDelete = async () => {
    setError(null);
    if (!password) { setError("Password is required."); return; }
    setLoading(true);
    await new Promise((r) => setTimeout(r, 500));
    setLoading(false);
    logout();
    navigate("/login");
  };

  return (
    <PageLayout>
      <div className="max-w-lg">
        <h1 className="text-lg font-semibold text-[var(--color-text)] mb-4">Delete Account</h1>

        <div className="card p-4">
          <Alert variant="warning" className="mb-4">
            <strong>Warning:</strong> This action is irreversible. All your data, preferences, and session history will be permanently deleted.
          </Alert>

          {error && <Alert variant="error" className="mb-4">{error}</Alert>}

          <label className="flex flex-col gap-1 mb-4">
            <span className="text-sm font-medium text-[var(--color-text)]">Enter your password to confirm</span>
            <TextInput type="password" placeholder="••••••••" value={password} onChange={(e) => setPassword(e.target.value)} />
          </label>

          <Button variant="danger" onClick={() => setConfirmOpen(true)}>Delete My Account</Button>
        </div>

        <Modal
          open={confirmOpen}
          onClose={() => setConfirmOpen(false)}
          title="Confirm Account Deletion"
          footer={
            <>
              <Button variant="secondary" onClick={() => setConfirmOpen(false)}>Cancel</Button>
              <Button variant="danger" onClick={handleDelete} loading={loading}>Delete Permanently</Button>
            </>
          }
        >
          <p>Are you absolutely sure you want to delete your account? This action cannot be undone.</p>
        </Modal>
      </div>
    </PageLayout>
  );
}
