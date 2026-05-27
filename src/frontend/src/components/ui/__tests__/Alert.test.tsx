import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import Alert from "../Alert";

describe("Alert", () => {
  it("renders error variant", () => {
    render(<Alert variant="error">Something went wrong</Alert>);
    expect(screen.getByText("Something went wrong")).toBeInTheDocument();
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });

  it("renders with title", () => {
    render(
      <Alert variant="success" title="Done">
        Operation complete
      </Alert>,
    );
    expect(screen.getByText("Done")).toBeInTheDocument();
  });
});
