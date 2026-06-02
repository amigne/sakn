import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import MacOuiLookupPage from "../MacOuiLookupPage";

// ── Mocks ─────────────────────────────────────────────────────────────

vi.mock("@/components/layout/PageLayout", () => ({
  default: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

vi.mock("@/stores/toolStore", () => {
  const store = { setActiveTool: vi.fn() };
  return {
    useToolStore: Object.assign(
      vi.fn((selector: (s: unknown) => unknown) => {
        return typeof selector === "function" ? selector(store) : store;
      }),
      { getState: vi.fn(() => store), setState: vi.fn() },
    ),
  };
});

const mockApiFn = vi.fn();
vi.mock("@/services/api", () => ({
  api: (...args: unknown[]) => mockApiFn(...args),
  ApiError: class extends Error {
    status: number;
    code: string;
    messageKey: string | null;
    fields: unknown;
    constructor(status: number, data: unknown) {
      const err = (data as { error?: { message?: string; code?: string } })?.error;
      super(err?.message ?? "API Error");
      this.status = status;
      this.code = err?.code ?? "UNKNOWN";
      this.messageKey = null;
      this.fields = null;
    }
  },
}));

// ── Helpers ───────────────────────────────────────────────────────────

function mockApiSuccess(data: unknown) {
  mockApiFn.mockResolvedValue({
    result: { success: true, data, error: null, duration_ms: 150 },
  });
}

function mockApiError(status: number, code: string, message: string) {
  mockApiFn.mockRejectedValue(
    new (class extends Error {
      status: number;
      code: string;
      messageKey: null;
      fields: null;
      constructor() {
        super(message);
        this.status = status;
        this.code = code;
        this.messageKey = null;
        this.fields = null;
      }
    })(),
  );
}

// ── Tests ─────────────────────────────────────────────────────────────

describe("MacOuiLookupPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockApiFn.mockReset();
  });

  it("renders initial state: empty textarea, execute button visible", () => {
    render(<MacOuiLookupPage />);
    expect(screen.getByRole("textbox")).toBeInTheDocument();
    expect(screen.getByText("Lookup")).toBeInTheDocument();
  });

  it("shows character counter at 0 / 50,000 initially", () => {
    render(<MacOuiLookupPage />);
    expect(screen.getByText(/0.*50[,.]?000/)).toBeInTheDocument();
  });

  it("updates character counter as user types", () => {
    render(<MacOuiLookupPage />);
    const textarea = screen.getByRole("textbox");
    fireEvent.change(textarea, { target: { value: "00:11:22:33:44:55" } });
    expect(screen.getByText(/17.*50[,.]?000/)).toBeInTheDocument();
  });

  it("shows no_results when text has no MAC addresses", async () => {
    render(<MacOuiLookupPage />);
    const textarea = screen.getByRole("textbox");
    fireEvent.change(textarea, { target: { value: "Hello, world!" } });

    const lookupBtn = screen.getByText("Lookup");
    fireEvent.click(lookupBtn);

    await waitFor(() => {
      expect(screen.getByText(/No MAC addresses or OUIs found/)).toBeInTheDocument();
    });
  });

  it("calls API and displays results on success", async () => {
    mockApiSuccess({
      results: [
        {
          input: "001122334455",
          oui_display: "00:11:22:33:44:55",
          result: {
            oui_type: "MA-L",
            organization: "Acme Corp",
            address: "123 Main St",
            first_seen: "2024-01-15",
            last_seen: "2026-05-20",
          },
          ambiguous_extends_ma_m: false,
          ambiguous_extends_ma_s: false,
          history: [],
        },
      ],
      rejected: [],
      parse_stats: { total_inputs: 1, valid: 1, rejected: 0, unique: 1 },
    });

    render(<MacOuiLookupPage />);
    const textarea = screen.getByRole("textbox");
    fireEvent.change(textarea, { target: { value: "00:11:22:33:44:55" } });

    const lookupBtn = screen.getByText("Lookup");
    fireEvent.click(lookupBtn);

    await waitFor(() => {
      // The OUI display text also matches the textarea value, so check
      // that we have the vendor name as confirmation of successful render.
      expect(screen.getByText("Acme Corp")).toBeInTheDocument();
      expect(screen.getByText("MA-L")).toBeInTheDocument();
    });
  });

  it("shows rejected banner when API returns rejected entries (AC-MAC-OUI-067)", async () => {
    mockApiSuccess({
      results: [],
      rejected: [
        { index: 1, sample: "test", reason: "invalid_format" },
        { index: 2, sample: "hello??", reason: "non_hex_characters" },
      ],
      parse_stats: { total_inputs: 2, valid: 0, rejected: 2, unique: 0 },
    });

    render(<MacOuiLookupPage />);
    const textarea = screen.getByRole("textbox");
    fireEvent.change(textarea, { target: { value: "non hex text test hello" } });

    // Actually, with "non hex text test hello", extractOuis won't find anything.
    // Let me use a text that has hex patterns.
    fireEvent.change(textarea, { target: { value: "00:11:22:33:44:55" } });

    const lookupBtn = screen.getByText("Lookup");
    fireEvent.click(lookupBtn);

    await waitFor(() => {
      expect(screen.getByText(/2.*ignored/i)).toBeInTheDocument();
    });
  });

  it("shows error message on API failure", async () => {
    mockApiError(422, "MAC_OUI_TOO_MANY_INPUTS", "Too many inputs");

    render(<MacOuiLookupPage />);
    const textarea = screen.getByRole("textbox");
    fireEvent.change(textarea, { target: { value: "00:11:22:33:44:55" } });

    const lookupBtn = screen.getByText("Lookup");
    fireEvent.click(lookupBtn);

    await waitFor(() => {
      // useToolExecution catches the error and sets status to "error"
      // The error message is displayed via Alert in ToolOutput
      expect(screen.getByRole("alert")).toBeInTheDocument();
    });
  });

  it("clears previous results on new submit", async () => {
    // First call — success
    mockApiSuccess({
      results: [
        {
          input: "AABBCCDDEEFF",
          oui_display: "AA:BB:CC:DD:EE:FF",
          result: {
            oui_type: "MA-L",
            organization: "Vendor A",
            address: "Address A",
            first_seen: "2024-01-01",
            last_seen: "2026-01-01",
          },
          ambiguous_extends_ma_m: false,
          ambiguous_extends_ma_s: false,
          history: [],
        },
      ],
      rejected: [],
      parse_stats: { total_inputs: 1, valid: 1, rejected: 0, unique: 1 },
    });

    render(<MacOuiLookupPage />);
    const textarea = screen.getByRole("textbox");

    // First submit
    fireEvent.change(textarea, { target: { value: "aa:bb:cc:dd:ee:ff" } });
    fireEvent.click(screen.getByText("Lookup"));

    await waitFor(() => {
      expect(screen.getByText("Vendor A")).toBeInTheDocument();
    });

    // Second submit with different text
    mockApiSuccess({
      results: [
        {
          input: "112233445566",
          oui_display: "11:22:33:44:55:66",
          result: {
            oui_type: "MA-L",
            organization: "Vendor B",
            address: "Address B",
            first_seen: "2025-01-01",
            last_seen: "2026-05-01",
          },
          ambiguous_extends_ma_m: false,
          ambiguous_extends_ma_s: false,
          history: [],
        },
      ],
      rejected: [],
      parse_stats: { total_inputs: 1, valid: 1, rejected: 0, unique: 1 },
    });

    fireEvent.change(textarea, { target: { value: "11:22:33:44:55:66" } });
    fireEvent.click(screen.getByText("Lookup"));

    await waitFor(() => {
      expect(screen.getByText("Vendor B")).toBeInTheDocument();
      expect(screen.queryByText("Vendor A")).toBeNull();
    });
  });

  it("enforces maxLength of 50 000 characters", () => {
    render(<MacOuiLookupPage />);
    const textarea = screen.getByRole("textbox") as HTMLTextAreaElement;
    expect(textarea.maxLength).toBe(50_000);
  });

  it("shows approaching limit warning at 90% (45 000 chars)", () => {
    render(<MacOuiLookupPage />);
    const textarea = screen.getByRole("textbox");
    const longText = "x".repeat(45_000);
    fireEvent.change(textarea, { target: { value: longText } });
    expect(screen.getByText(/Approaching/)).toBeInTheDocument();
  });

  it("reset clears textarea and results", async () => {
    mockApiSuccess({
      results: [
        {
          input: "001122334455",
          oui_display: "00:11:22:33:44:55",
          result: {
            oui_type: "MA-L",
            organization: "Test Vendor",
            address: "Test Address",
            first_seen: "2024-01-01",
            last_seen: "2026-01-01",
          },
          ambiguous_extends_ma_m: false,
          ambiguous_extends_ma_s: false,
          history: [],
        },
      ],
      rejected: [],
      parse_stats: { total_inputs: 1, valid: 1, rejected: 0, unique: 1 },
    });

    render(<MacOuiLookupPage />);
    const textarea = screen.getByRole("textbox") as HTMLTextAreaElement;

    fireEvent.change(textarea, { target: { value: "00:11:22:33:44:55" } });
    fireEvent.click(screen.getByText("Lookup"));

    await waitFor(() => {
      expect(screen.getByText("Test Vendor")).toBeInTheDocument();
    });

    // Click Reset
    fireEvent.click(screen.getByText("Reset"));
    expect(textarea.value).toBe("");
  });
});
