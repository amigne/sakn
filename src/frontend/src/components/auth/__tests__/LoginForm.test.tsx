import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import i18n from "@/i18n/i18n";
import { ApiError } from "@/services/api";
import LoginForm from "../LoginForm";

const { mockLogin } = vi.hoisted(() => ({
  mockLogin: vi.fn(),
}));

vi.mock("@/stores/authStore", () => ({
  useAuthStore: Object.assign(
    vi.fn((selector?: (s: unknown) => unknown) => {
      const store = {
        login: mockLogin,
        user: null,
        preferences: null,
        isLoading: false,
        isInitialized: true,
      };
      return typeof selector === "function" ? selector(store) : store;
    }),
    { getState: vi.fn(), setState: vi.fn() },
  ),
}));

function renderForm() {
  return render(
    <MemoryRouter>
      <LoginForm />
    </MemoryRouter>,
  );
}

describe("LoginForm — i18n field errors", () => {
  beforeEach(async () => {
    await i18n.changeLanguage("en");
    mockLogin.mockReset();
  });

  afterEach(async () => {
    await i18n.changeLanguage("en");
  });

  it("renders field error in French when locale is fr", async () => {
    mockLogin.mockRejectedValue(
      new ApiError(422, {
        error: {
          code: "VALIDATION_FAILED",
          message: "Validation failed",
          details: {
            fields: {
              email: { message_key: "errors.field_required", message: "This field is required." },
            },
          },
        },
      }),
    );

    await i18n.changeLanguage("fr");
    renderForm();

    fireEvent.click(screen.getByRole("button", { name: /sign in|connexion/i }));

    await waitFor(() => {
      expect(screen.getByText(/ce champ|obligatoire/i)).toBeInTheDocument();
      expect(screen.queryByText("This field is required.")).not.toBeInTheDocument();
    });
  });
});
