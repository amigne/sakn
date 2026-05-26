import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import TraceroutePage from "@/pages/tools/TraceroutePage";
import { useToolStore } from "@/stores/toolStore";

// Mock PageLayout to avoid router context dependency
vi.mock("@/components/layout/PageLayout", () => ({
  default: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

// Mock useWebSocket hook
const mockUseWebSocket = vi.fn();
vi.mock("@/hooks/useWebSocket", () => ({
  useWebSocket: (params: unknown) => mockUseWebSocket(params),
}));

// Mock useToolStore (zustand store with getState/setState)
vi.mock("@/stores/toolStore", () => {
  const store = {
    displayMode: { traceroute: "table" as const },
    setDisplayMode: vi.fn(),
    setActiveTool: vi.fn(),
  };
  return {
    useToolStore: Object.assign(
      vi.fn((selector: (s: unknown) => unknown) => {
        return typeof selector === "function" ? selector(store) : store;
      }),
      { getState: vi.fn(() => store), setState: vi.fn() }
    ),
  };
});

// Default mock for useWebSocket returns
const defaultWsReturn = {
  status: "idle" as const,
  results: [],
  summary: null,
  terminatedBy: null,
  duration: null,
  error: null,
  connect: vi.fn(),
  cancel: vi.fn(),
  reset: vi.fn(),
};

function makeHop(overrides: Record<string, unknown> = {}) {
  return {
    ip: "8.8.8.8",
    hostname: "dns.google",
    probes: [{ rtt_ms: 20.456, status: "ok" as const }],
    reached: false,
    ...overrides,
  };
}

describe("TraceroutePage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseWebSocket.mockReturnValue(defaultWsReturn);
  });

  it("renders table with normal hops", () => {
    mockUseWebSocket.mockReturnValue({
      ...defaultWsReturn,
      status: "completed",
      results: [
        makeHop({ ip: "8.8.8.8", hostname: "dns.google", probes: [
          { rtt_ms: 20.456, status: "ok" },
        ] }),
      ],
      summary: { hops_probed: 1, destination_reached: true, total_time_ms: 20.456 },
      terminatedBy: "completed",
      duration: 20.456,
    });

    render(<TraceroutePage />);
    expect(screen.getByText("8.8.8.8")).toBeInTheDocument();
    expect(screen.getByText("dns.google")).toBeInTheDocument();
  });

  it("renders without crash when hop has no probes array (issue #212)", () => {
    mockUseWebSocket.mockReturnValue({
      ...defaultWsReturn,
      status: "completed",
      results: [
        makeHop({ ip: "[hidden]", hostname: null, probes: undefined }),
        makeHop({ ip: "8.8.8.8", hostname: "dns.google", probes: [
          { rtt_ms: 20.456, status: "ok" },
        ] }),
      ],
      summary: { hops_probed: 2, destination_reached: true, total_time_ms: 25.0 },
      terminatedBy: "completed",
      duration: 25.0,
    });

    render(<TraceroutePage />);
    // The table renders both rows without throwing
    expect(screen.getByText("[hidden]")).toBeInTheDocument();
    expect(screen.getByText("8.8.8.8")).toBeInTheDocument();
  });

  it("renders text mode without crash when hop has no probes array (issue #212)", () => {
    const mockSetDisplayMode = vi.fn();
    // Override toolStore mock for this test
    vi.mocked(useToolStore).mockImplementation(
      ((selector: (s: unknown) => unknown) => {
        const store = {
          displayMode: { traceroute: "text" as const },
          setDisplayMode: mockSetDisplayMode,
          setActiveTool: vi.fn(),
        };
        return typeof selector === "function" ? selector(store) : store;
      }) as any
    );

    mockUseWebSocket.mockReturnValue({
      ...defaultWsReturn,
      status: "completed",
      results: [
        makeHop({ ip: "[hidden]", hostname: null, probes: undefined }),
        makeHop({ ip: "8.8.8.8", hostname: "dns.google", probes: [
          { rtt_ms: 20.456, status: "ok" },
        ] }),
      ],
      summary: { hops_probed: 2, destination_reached: true, total_time_ms: 25.0 },
      terminatedBy: "completed",
      duration: 25.0,
    });

    render(<TraceroutePage />);
    // Text mode renders IPs inline without throwing
    expect(screen.getByText(/\[hidden\]/)).toBeInTheDocument();
    expect(screen.getByText(/8.8.8.8/)).toBeInTheDocument();
  });
});
