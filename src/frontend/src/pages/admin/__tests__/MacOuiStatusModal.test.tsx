import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import i18n from "@/i18n/i18n";
import MacOuiStatusModal from "@/pages/admin/components/MacOuiStatusModal";

// ── Mocks ──────────────────────────────────────────────────────────────

const mockGetModuleStatus = vi.fn();
const mockTriggerOuiSync = vi.fn();

vi.mock("@/api/admin/moduleStatus", () => ({
  getModuleStatus: (...args: unknown[]) => mockGetModuleStatus(...args),
  getModuleSettings: vi.fn(),
  updateModuleSettings: vi.fn(),
  triggerOuiSync: (...args: unknown[]) => mockTriggerOuiSync(...args),
}));

// ── Helpers ────────────────────────────────────────────────────────────

const SUCCESS_STATUS = {
  status: "success" as const,
  last_run: {
    started_at: "2026-06-01T03:00:00Z",
    finished_at: "2026-06-01T03:02:15Z",
    triggered_by: "scheduler" as const,
    added: 12,
    changed: 3,
    confirmed: 48729,
    files_failed: [],
  },
  next_scheduled_run: "2026-06-02T03:00:00Z",
  consecutive_failures: { "MA-L": 0, "MA-M": 0, "MA-S": 0 },
  total_records: 48744,
  history: [
    {
      started_at: "2026-06-01T03:00:00Z",
      finished_at: "2026-06-01T03:02:15Z",
      triggered_by: "scheduler",
      status: "success",
      added: 12,
      changed: 3,
      confirmed: 48729,
      files_failed: [],
      error_message: null,
    },
  ],
};

const IDLE_STATUS = {
  status: "idle" as const,
  last_run: null,
  next_scheduled_run: "2026-06-02T03:00:00Z",
  consecutive_failures: { "MA-L": 0, "MA-M": 0, "MA-S": 0 },
  total_records: 0,
  history: [],
};

function renderModal(open = true, onClose = vi.fn()) {
  return render(<MacOuiStatusModal open={open} onClose={onClose} />);
}

// ── Tests ──────────────────────────────────────────────────────────────

describe("MacOuiStatusModal", () => {
  beforeEach(async () => {
    await i18n.changeLanguage("en");
    vi.clearAllMocks();
    mockGetModuleStatus.mockResolvedValue(SUCCESS_STATUS);
  });

  afterEach(async () => {
    await i18n.changeLanguage("en");
  });

  describe("rendering states", () => {
    it("renders loading spinner initially", () => {
      mockGetModuleStatus.mockReturnValue(new Promise(() => {}));
      renderModal();
      expect(screen.getByRole("status")).toBeInTheDocument();
    });

    it("renders status after loading", async () => {
      renderModal();
      await waitFor(() => {
        expect(screen.getByText("MAC OUI Sync Status")).toBeInTheDocument();
      });
      expect(screen.getByText("Success")).toBeInTheDocument();
    });

    it("renders 'no data' for idle status", async () => {
      mockGetModuleStatus.mockResolvedValue(IDLE_STATUS);
      renderModal();
      await waitFor(() => {
        expect(screen.getByText("No sync data")).toBeInTheDocument();
      });
    });

    it("renders error message on API failure", async () => {
      mockGetModuleStatus.mockRejectedValue(new Error("API Error"));
      renderModal();
      await waitFor(() => {
        expect(screen.getByText("API Error")).toBeInTheDocument();
      });
    });
  });

  describe("trigger sync", () => {
    it("shows confirmation on trigger button click", async () => {
      renderModal();
      await waitFor(() => {
        expect(screen.getByText("Run Sync Now")).toBeInTheDocument();
      });
      fireEvent.click(screen.getByText("Run Sync Now"));
      expect(screen.getByText("Confirm")).toBeInTheDocument();
    });

    it("calls trigger API on confirm", async () => {
      mockTriggerOuiSync.mockResolvedValue({ task_id: "abc", started_at: "..." });
      renderModal();
      await waitFor(() => {
        expect(screen.getByText("Run Sync Now")).toBeInTheDocument();
      });
      fireEvent.click(screen.getByText("Run Sync Now"));
      fireEvent.click(screen.getByText("Confirm"));
      await waitFor(() => {
        expect(mockTriggerOuiSync).toHaveBeenCalled();
      });
    });
  });

  describe("history table", () => {
    it("renders history entries", async () => {
      renderModal();
      await waitFor(() => {
        expect(screen.getByText("Sync History")).toBeInTheDocument();
      });
      // The confirmed count 48729 appears both in the summary and history table
      const elements = await screen.findAllByText("48729");
      expect(elements.length).toBeGreaterThan(0);
    });
  });
});
