import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import SecretGeneratorPage from "../SecretGeneratorPage";

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

// ── Clipboard mock ─────────────────────────────────────────────────────

const mockWriteText = vi.fn();
const mockReadText = vi.fn();
const originalNavigator = { ...globalThis.navigator };

function setClipboardAvailable() {
  Object.defineProperty(globalThis, "navigator", {
    value: { ...originalNavigator, clipboard: { writeText: mockWriteText, readText: mockReadText } },
    writable: true,
    configurable: true,
  });
}

function setClipboardUnavailable() {
  Object.defineProperty(globalThis, "navigator", {
    value: { ...originalNavigator, clipboard: undefined },
    writable: true,
    configurable: true,
  });
}

/** Flush all pending microtasks (promises). */
function flushMicrotasks() {
  return act(() => Promise.resolve());
}

// ── Tests ─────────────────────────────────────────────────────────────

describe("SecretGeneratorPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockWriteText.mockReset();
    mockWriteText.mockResolvedValue(undefined);
    mockReadText.mockReset();
    mockReadText.mockResolvedValue("");
    setClipboardAvailable();
  });

  afterEach(() => {
    Object.defineProperty(globalThis, "navigator", {
      value: originalNavigator,
      writable: true,
      configurable: true,
    });
  });

  // ── Rendering ───────────────────────────────────────────────────────

  it("renders the page with mode tabs and regenerate button", () => {
    render(<SecretGeneratorPage />);
    expect(screen.getByText("Password")).toBeInTheDocument();
    expect(screen.getByText("Token")).toBeInTheDocument();
    expect(screen.getByText("Hex")).toBeInTheDocument();
    expect(screen.getByText("Regenerate")).toBeInTheDocument();
  });

  it("renders password mode parameters by default", () => {
    render(<SecretGeneratorPage />);
    // Password mode: 4 charset toggles visible via their labels
    expect(screen.getByText(/Uppercase/)).toBeInTheDocument();
    expect(screen.getByText(/Lowercase/)).toBeInTheDocument();
    expect(screen.getByText(/Digits/)).toBeInTheDocument();
    expect(screen.getByText(/Symbols/)).toBeInTheDocument();
  });

  // ── Mode switching ──────────────────────────────────────────────────

  it("switches to token mode and hides password params", async () => {
    render(<SecretGeneratorPage />);
    // Click the Token tab trigger (Radix uses role="tab")
    const tokenTab = screen.getByRole("tab", { name: "Token" });
    await act(async () => {
      fireEvent.mouseDown(tokenTab);
    });
    // Password charsets should now be hidden
    expect(screen.queryByText(/Uppercase/)).not.toBeInTheDocument();
  });

  it("switches to hex mode and hides password params", async () => {
    render(<SecretGeneratorPage />);
    const hexTab = screen.getByRole("tab", { name: "Hex" });
    await act(async () => {
      fireEvent.mouseDown(hexTab);
    });
    expect(screen.queryByText(/Uppercase/)).not.toBeInTheDocument();
  });

  // ── Generation ──────────────────────────────────────────────────────

  it("generates a password on first click of Regenerate", () => {
    render(<SecretGeneratorPage />);
    fireEvent.click(screen.getByText("Regenerate"));
    // A result textarea should appear with the generated secret
    const textareas = screen.getAllByRole("textbox");
    const secretTextarea = textareas.find((el) => el.tagName === "TEXTAREA")! as HTMLTextAreaElement;
    expect(secretTextarea).toBeTruthy();
    expect(secretTextarea.value.length).toBeGreaterThan(0);
  });

  it("generates different secrets on consecutive Regenerate clicks", () => {
    render(<SecretGeneratorPage />);
    fireEvent.click(screen.getByText("Regenerate"));
    const textareas1 = screen.getAllByRole("textbox");
    const ta1 = textareas1.find((el) => el.tagName === "TEXTAREA")! as HTMLTextAreaElement;
    const secret1 = ta1.value;

    fireEvent.click(screen.getByText("Regenerate"));
    const textareas2 = screen.getAllByRole("textbox");
    const ta2 = textareas2.find((el) => el.tagName === "TEXTAREA")! as HTMLTextAreaElement;
    const secret2 = ta2.value;

    // Extremely unlikely to get the same secret twice
    expect(secret1).not.toBe(secret2);
  });

  it("generates a token when in token mode", async () => {
    render(<SecretGeneratorPage />);
    const tokenTab = screen.getByRole("tab", { name: "Token" });
    await act(async () => {
      fireEvent.mouseDown(tokenTab);
    });
    fireEvent.click(screen.getByText("Regenerate"));
    const textareas = screen.getAllByRole("textbox");
    const secretTextarea = textareas.find((el) => el.tagName === "TEXTAREA")! as HTMLTextAreaElement;
    expect(secretTextarea).toBeTruthy();
    expect(secretTextarea.value.length).toBeGreaterThan(0);
  });

  it("generates a hex secret when in hex mode", async () => {
    render(<SecretGeneratorPage />);
    const hexTab = screen.getByRole("tab", { name: "Hex" });
    await act(async () => {
      fireEvent.mouseDown(hexTab);
    });
    fireEvent.click(screen.getByText("Regenerate"));
    const textareas = screen.getAllByRole("textbox");
    const secretTextarea = textareas.find((el) => el.tagName === "TEXTAREA")! as HTMLTextAreaElement;
    expect(secretTextarea).toBeTruthy();
    // Hex output should only contain hex chars
    expect(/^[0-9a-f]+$/.test(secretTextarea.value)).toBe(true);
  });

  // ── Strength indicator ──────────────────────────────────────────────

  it("shows a strength label after generation", () => {
    render(<SecretGeneratorPage />);
    fireEvent.click(screen.getByText("Regenerate"));
    // Should show one of the strength labels
    const strengthPattern = /Weak|Fair|Strong|Very strong/;
    expect(screen.getByText(strengthPattern)).toBeInTheDocument();
  });

  it("shows entropy information after generation", () => {
    render(<SecretGeneratorPage />);
    fireEvent.click(screen.getByText("Regenerate"));
    // Should show "N characters (X bits)" pattern
    expect(screen.getByText(/characters/)).toBeInTheDocument();
    expect(screen.getByText(/bits/)).toBeInTheDocument();
  });

  // ── Copy to clipboard ───────────────────────────────────────────────

  it("copies the secret to clipboard when copy button is clicked", async () => {
    render(<SecretGeneratorPage />);
    fireEvent.click(screen.getByText("Regenerate"));

    // Find and click the Copy button
    const copyButton = screen.getByText("Copy");
    await act(async () => {
      fireEvent.click(copyButton);
    });
    // Flush the writeText promise
    await flushMicrotasks();

    expect(mockWriteText).toHaveBeenCalledTimes(1);
    const copiedValue = mockWriteText.mock.calls[0]![0];
    expect(typeof copiedValue).toBe("string");
    expect(copiedValue.length).toBeGreaterThan(0);
  });

  it("shows 'Copied!' toast after successful copy", async () => {
    render(<SecretGeneratorPage />);
    fireEvent.click(screen.getByText("Regenerate"));

    await act(async () => {
      fireEvent.click(screen.getByText("Copy"));
    });
    // Flush the writeText promise → then() callback fires → state update
    await flushMicrotasks();

    expect(screen.getByText("Copied!")).toBeInTheDocument();
  });

  // ── Clipboard unavailable fallback ──────────────────────────────────

  it("hides copy button when clipboard API is unavailable", () => {
    setClipboardUnavailable();
    render(<SecretGeneratorPage />);
    fireEvent.click(screen.getByText("Regenerate"));

    // Copy button should not be rendered
    expect(screen.queryByText("Copy")).not.toBeInTheDocument();
    // Fallback message should be shown
    expect(screen.getByText(/Clipboard not available/)).toBeInTheDocument();
  });

  // ── Validation ──────────────────────────────────────────────────────

  it("shows validation error when no charset is selected in password mode", () => {
    render(<SecretGeneratorPage />);

    // Uncheck all charset toggles
    const toggles = screen.getAllByRole("switch");
    for (const toggle of toggles) {
      fireEvent.click(toggle);
    }

    fireEvent.click(screen.getByText("Regenerate"));

    expect(screen.getByText(/At least one character set/)).toBeInTheDocument();
  });

  // ── Reset ───────────────────────────────────────────────────────────

  it("clears the result on reset", () => {
    render(<SecretGeneratorPage />);
    fireEvent.click(screen.getByText("Regenerate"));

    // Result should be visible
    const textareas = screen.getAllByRole("textbox");
    const ta = textareas.find((el) => el.tagName === "TEXTAREA")! as HTMLTextAreaElement;
    expect(ta.value.length).toBeGreaterThan(0);

    fireEvent.click(screen.getByText("Reset"));

    // Entropy line should no longer be visible
    expect(screen.queryByText(/characters/)).not.toBeInTheDocument();
  });

  // ── Length bounds ───────────────────────────────────────────────────

  it("clamps password length to min 8 when generating", () => {
    render(<SecretGeneratorPage />);
    // The TextInput with type="number" for length
    const inputs = screen.getAllByRole("spinbutton");
    const lengthInput = inputs[0]!; // First number input = password length
    fireEvent.change(lengthInput, { target: { value: "3" } });
    // Generate — the component clamps in updateNumber
    fireEvent.click(screen.getByText("Regenerate"));
    const textareas = screen.getAllByRole("textbox");
    const ta = textareas.find((el) => el.tagName === "TEXTAREA")! as HTMLTextAreaElement;
    expect(ta.value.length).toBeGreaterThanOrEqual(8);
  });

  // ── Clipboard ownership guard (#437) ────────────────────────────────

  it("reset clears clipboard only when this tool wrote to it", async () => {
    render(<SecretGeneratorPage />);
    fireEvent.click(screen.getByText("Regenerate"));

    await act(async () => {
      fireEvent.click(screen.getByText("Copy"));
    });
    await flushMicrotasks();
    expect(mockWriteText).toHaveBeenCalledTimes(1);

    // Reset: should clear clipboard since we wrote to it
    fireEvent.click(screen.getByText("Reset"));
    await flushMicrotasks();
    expect(mockWriteText).toHaveBeenCalledTimes(2);
    expect(mockWriteText.mock.calls[1]![0]).toBe("");
  });

  it("reset does not clear clipboard when this tool did not write to it", () => {
    render(<SecretGeneratorPage />);
    // Generate but do NOT copy
    fireEvent.click(screen.getByText("Regenerate"));

    // Reset without having copied
    fireEvent.click(screen.getByText("Reset"));

    // writeText was never called (we didn't copy, so no write)
    expect(mockWriteText).not.toHaveBeenCalled();
  });
});
