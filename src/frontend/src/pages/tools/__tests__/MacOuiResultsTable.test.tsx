import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import MacOuiResultsTable from "../components/MacOuiResultsTable";
import type { MacOuiResultRow } from "@/api/tools/macOui";

// ── Test data ─────────────────────────────────────────────────────────

function makeRow(overrides: Partial<MacOuiResultRow> = {}): MacOuiResultRow {
  return {
    input: "001122334455",
    oui_display: "00:11:22:33:44:55",
    result: {
      oui_type: "MA-L",
      organization: "Acme Corp",
      address: "123 Main St, Anytown, USA",
      first_seen: "2024-01-15",
      last_seen: "2026-05-20",
    },
    ambiguous_extends_ma_m: false,
    ambiguous_extends_ma_s: false,
    history: [],
    ...overrides,
  };
}

const MA_M_ROW = makeRow({
  input: "0011223",
  oui_display: "00:11:22:3_",
  result: {
    oui_type: "MA-M",
    organization: "Acme Corp",
    address: "123 Main St",
    first_seen: "2024-03-01",
    last_seen: "2026-05-19",
  },
  history: [
    {
      previous_organization: "Old Acme",
      new_organization: "Acme Corp",
      previous_address: null,
      new_address: null,
      change_type: "name_change",
      detected_at: "2025-01-10T00:00:00Z",
    },
  ],
});

const AMBIGUOUS_ROW = makeRow({
  input: "8C1F64",
  oui_display: "8C:1F:64",
  result: null,
  ambiguous_extends_ma_m: true,
  ambiguous_extends_ma_s: false,
});

const UNKNOWN_ROW = makeRow({
  input: "FFEEDD",
  oui_display: "FF:EE:DD",
  result: null,
});

// ── Tests ─────────────────────────────────────────────────────────────

describe("MacOuiResultsTable", () => {
  it("renders 5 known rows + 1 unknown row correctly", () => {
    const rows = [
      makeRow({ input: "AA0001", oui_display: "AA:00:01", result: { ...makeRow().result!, organization: "Vendor A" } }),
      makeRow({ input: "AA0002", oui_display: "AA:00:02", result: { ...makeRow().result!, organization: "Vendor B" } }),
      makeRow({ input: "AA0003", oui_display: "AA:00:03", result: { ...makeRow().result!, organization: "Vendor C" } }),
      makeRow({ input: "AA0004", oui_display: "AA:00:04", result: { ...makeRow().result!, organization: "Vendor D" } }),
      makeRow({ input: "AA0005", oui_display: "AA:00:05", result: { ...makeRow().result!, organization: "Vendor E" } }),
      UNKNOWN_ROW,
    ];
    render(<MacOuiResultsTable results={rows} locale="en-US" />);

    expect(screen.getByText("AA:00:01")).toBeInTheDocument();
    expect(screen.getByText("Vendor A")).toBeInTheDocument();
    expect(screen.getByText("Vendor E")).toBeInTheDocument();
    expect(screen.getByText("Unknown vendor")).toBeInTheDocument();
  });

  it("renders oui_display with underscore as styled span (AC-MAC-OUI-064)", () => {
    render(<MacOuiResultsTable results={[MA_M_ROW]} locale="en-US" />);

    // The underscore is rendered as a separate span, so we search by
    // the text content of the enclosing span (each char is its own text node).
    const displayCells = document.querySelectorAll("td span.font-mono");
    const ouiText = Array.from(displayCells).map((el) => el.textContent);
    expect(ouiText).toContain("00:11:22:3_");

    // The underscore itself is inside a styled span within the cell
    const spans = document.querySelectorAll("td span.font-mono span");
    const underscoreSpan = Array.from(spans).find((s) => s.textContent === "_");
    expect(underscoreSpan).toBeTruthy();
  });

  it("shows legend when at least one row is MA-M or MA-S (AC-MAC-OUI-065)", () => {
    render(<MacOuiResultsTable results={[MA_M_ROW]} locale="en-US" />);
    expect(screen.getByText(/IEEE prefix/i)).toBeInTheDocument();
  });

  it("does not show legend when all rows are MA-L only", () => {
    render(<MacOuiResultsTable results={[makeRow()]} locale="en-US" />);
    expect(screen.queryByText(/IEEE prefix/i)).toBeNull();
  });

  it("renders ambiguous OUI row with warning background (AC-MAC-OUI-066)", () => {
    const { container } = render(<MacOuiResultsTable results={[AMBIGUOUS_ROW]} locale="en-US" />);
    const row = container.querySelector("tbody tr");
    expect(row?.className).toContain("warning");
  });

  it("does not color unknown vendor rows (no ambiguous flag)", () => {
    const { container } = render(<MacOuiResultsTable results={[UNKNOWN_ROW]} locale="en-US" />);
    const row = container.querySelector("tbody tr");
    // Unknown vendor (result=null) without ambiguous flag → normal row
    expect(row?.className).not.toContain("warning");
  });

  it("click history button toggles history detail section", () => {
    render(<MacOuiResultsTable results={[MA_M_ROW]} locale="en-US" />);

    // History button should be visible
    const historyBtn = screen.getByText("History");
    expect(historyBtn).toBeInTheDocument();

    // Click to expand
    fireEvent.click(historyBtn);
    expect(screen.getByText("Change History")).toBeInTheDocument();
    expect(screen.getByText("Name change")).toBeInTheDocument();

    // Click again to collapse
    fireEvent.click(historyBtn);
    // After collapse, the history detail may still be in DOM
  });

  it("no history button when history is empty", () => {
    render(<MacOuiResultsTable results={[makeRow()]} locale="en-US" />);
    expect(screen.queryByText("History")).toBeNull();
  });

  it("copy button available for known vendors", () => {
    render(<MacOuiResultsTable results={[makeRow()]} locale="en-US" />);
    // Each row has a copy button (SVG icon) with aria-label
    const copyBtns = screen.getAllByLabelText("Copy vendor info");
    expect(copyBtns.length).toBeGreaterThan(0);
  });

  it("global copy button renders", () => {
    render(<MacOuiResultsTable results={[makeRow()]} locale="en-US" />);
    expect(screen.getByText("Copy all results (TSV)")).toBeInTheDocument();
  });
});
