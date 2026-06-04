import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import i18n from "@/i18n/i18n";
import MacOuiSettingsModal from "@/pages/admin/components/MacOuiSettingsModal";

// ── Mocks ──────────────────────────────────────────────────────────────

const mockGetModuleSettings = vi.fn();
const mockUpdateModuleSettings = vi.fn();

vi.mock("@/api/admin/moduleStatus", () => ({
  getModuleStatus: vi.fn(),
  getModuleSettings: (...args: unknown[]) => mockGetModuleSettings(...args),
  updateModuleSettings: (...args: unknown[]) => mockUpdateModuleSettings(...args),
  triggerOuiSync: vi.fn(),
}));

// ── Helpers ────────────────────────────────────────────────────────────

const DEFAULT_SETTINGS = {
  module: "mac_oui",
  settings: {
    MAC_OUI_FRONTEND_INPUT_MAX_CHARS: "50000",
    MAC_OUI_BACKEND_BATCH_MAX_SIZE: "2000",
    MAC_OUI_HISTORY_PAGE_SIZE: "10",
    OUI_SYNC_HOUR: "3",
    OUI_SYNC_LOG_RETENTION_DAYS: "365",
  },
};

function renderModal(open = true, onClose = vi.fn()) {
  return render(<MacOuiSettingsModal open={open} onClose={onClose} />);
}

// ── Tests ──────────────────────────────────────────────────────────────

describe("MacOuiSettingsModal", () => {
  beforeEach(async () => {
    await i18n.changeLanguage("en");
    vi.clearAllMocks();
    mockGetModuleSettings.mockResolvedValue(DEFAULT_SETTINGS);
    mockUpdateModuleSettings.mockResolvedValue(DEFAULT_SETTINGS);
  });

  afterEach(async () => {
    await i18n.changeLanguage("en");
  });

  describe("rendering", () => {
    it("shows loading spinner initially", () => {
      mockGetModuleSettings.mockReturnValue(new Promise(() => {}));
      renderModal();
      expect(screen.getByRole("status")).toBeInTheDocument();
    });

    it("renders settings form after loading", async () => {
      renderModal();
      await waitFor(() => {
        expect(screen.getByText("MAC OUI Settings")).toBeInTheDocument();
      });
      // 4 number inputs should be present
      expect(screen.getByDisplayValue("50000")).toBeInTheDocument();
      expect(screen.getByDisplayValue("2000")).toBeInTheDocument();
      expect(screen.getByDisplayValue("10")).toBeInTheDocument();
      expect(screen.getByDisplayValue("3")).toBeInTheDocument();
      expect(screen.getByDisplayValue("365")).toBeInTheDocument();
    });

    it("renders error message on API failure", async () => {
      mockGetModuleSettings.mockRejectedValue(new Error("Load error"));
      renderModal();
      await waitFor(() => {
        expect(screen.getByText("Load error")).toBeInTheDocument();
      });
    });
  });

  describe("save", () => {
    it("calls update API on save button click", async () => {
      renderModal();
      await waitFor(() => {
        expect(screen.getByText("Save")).toBeInTheDocument();
      });
      fireEvent.click(screen.getByText("Save"));
      await waitFor(() => {
        expect(mockUpdateModuleSettings).toHaveBeenCalledWith("mac_oui", {
          MAC_OUI_FRONTEND_INPUT_MAX_CHARS: "50000",
          MAC_OUI_BACKEND_BATCH_MAX_SIZE: "2000",
          MAC_OUI_HISTORY_PAGE_SIZE: "10",
          OUI_SYNC_HOUR: "3",
          OUI_SYNC_LOG_RETENTION_DAYS: "365",
        });
      });
    });

    it("shows saved confirmation after successful save", async () => {
      renderModal();
      await waitFor(() => {
        expect(screen.getByText("Save")).toBeInTheDocument();
      });
      fireEvent.click(screen.getByText("Save"));
      await waitFor(() => {
        expect(screen.getByText("Settings saved.")).toBeInTheDocument();
      });
    });

    it("shows error on save failure", async () => {
      mockUpdateModuleSettings.mockRejectedValue(new Error("Save error"));
      renderModal();
      await waitFor(() => {
        expect(screen.getByText("Save")).toBeInTheDocument();
      });
      fireEvent.click(screen.getByText("Save"));
      await waitFor(() => {
        expect(screen.getByText("Save error")).toBeInTheDocument();
      });
    });
  });
});
