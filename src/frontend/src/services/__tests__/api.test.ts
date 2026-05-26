import { describe, it, expect } from "vitest";
import { ApiError } from "../api";

describe("ApiError messageKey rewriting", () => {
  it("rewrites errors.X to errors:X for i18next namespace lookup", () => {
    const err = new ApiError(401, {
      error: { message_key: "errors.invalid_credentials", message: "Invalid." },
    });
    expect(err.messageKey).toBe("errors:invalid_credentials");
  });

  it("leaves non-errors keys unchanged", () => {
    const err = new ApiError(200, {
      error: { message_key: "common.success", message: "OK" },
    });
    expect(err.messageKey).toBe("common.success");
  });

  it("handles null message_key gracefully", () => {
    const err = new ApiError(500, { error: { message: "Internal" } });
    expect(err.messageKey).toBeNull();
  });
});
