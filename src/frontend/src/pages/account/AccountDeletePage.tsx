import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import PageLayout from "@/components/layout/PageLayout";
import { Alert, Button, Modal, TextInput } from "@/components/ui";
import { type ApiError, api } from "@/services/api";
import { useAuthStore } from "@/stores/authStore";

export default function AccountDeletePage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const logout = useAuthStore((s) => s.logout);
  const [password, setPassword] = useState("");
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleDelete = async () => {
    setError(null);
    if (!password) {
      setError(t("account.password_required"));
      return;
    }
    setLoading(true);
    try {
      await api("/account", { method: "DELETE", body: { password } });
      logout();
      navigate("/login");
    } catch (err) {
      const apiErr = err as ApiError;
      setError(apiErr.messageKey ? t(apiErr.messageKey) : apiErr.message);
    } finally {
      setLoading(false);
      setConfirmOpen(false);
    }
  };

  return (
    <PageLayout>
      <div className="max-w-lg">
        <h1 className="text-lg font-semibold text-[var(--color-text)] mb-4">{t("account.delete_account")}</h1>

        <div className="card p-4">
          <Alert variant="warning" className="mb-4">
            <strong>{t("account.warning_label")}:</strong> {t("account.delete_warning")}
          </Alert>

          {error && (
            <Alert variant="error" className="mb-4">
              {error}
            </Alert>
          )}

          <label className="flex flex-col gap-1 mb-4">
            <span className="text-sm font-medium text-[var(--color-text)]">{t("account.enter_password_confirm")}</span>
            <TextInput
              type="password"
              placeholder="••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </label>

          <Button variant="danger" onClick={() => setConfirmOpen(true)}>
            {t("account.delete_my_account")}
          </Button>
        </div>

        <Modal
          open={confirmOpen}
          onClose={() => setConfirmOpen(false)}
          title={t("account.confirm_deletion")}
          footer={
            <>
              <Button variant="secondary" onClick={() => setConfirmOpen(false)}>
                {t("common.cancel")}
              </Button>
              <Button variant="danger" onClick={handleDelete} loading={loading}>
                {t("account.delete_permanently")}
              </Button>
            </>
          }
        >
          <p>{t("account.delete_confirmation")}</p>
        </Modal>
      </div>
    </PageLayout>
  );
}
