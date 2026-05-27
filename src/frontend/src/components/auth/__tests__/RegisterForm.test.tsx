import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { MemoryRouter } from "react-router-dom";
import i18n from "@/i18n/i18n";
import { ApiError } from "@/services/api";
import RegisterForm from "../RegisterForm";

const { mockRegister } = vi.hoisted(() => ({
  mockRegister: vi.fn(),
}));

vi.mock("@/stores/authStore", () => ({
  useAuthStore: Object.assign(
    vi.fn((selector?: (s: unknown) => unknown) => {
      const store = {
        register: mockRegister,
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
      <RegisterForm />
    </MemoryRouter>,
  );
}

describe("RegisterForm — i18n field errors", () => {
  beforeEach(async () => {
    await i18n.changeLanguage("en");
    mockRegister.mockReset();
  });

  afterEach(async () => {
    await i18n.changeLanguage("en");
  });

  it("renders field error in French when locale is fr", async () => {
    mockRegister.mockRejectedValue(
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

    // Fill required fields so validation passes and the submit reaches register()
    fireEvent.change(screen.getByPlaceholderText("user@example.com"), {
      target: { value: "test@example.com" },
    });
    fireEvent.change(screen.getAllByPlaceholderText("••••••••")[0], {
      target: { value: "StrongP@ss1" },
    });
    fireEvent.change(screen.getAllByPlaceholderText("••••••••")[1], {
      target: { value: "StrongP@ss1" },
    });
    // Fill first/last name (required fields)
    const textInputs = screen.getAllByRole("textbox");
    const nameInputs = textInputs.filter(
      (el) => el.getAttribute("autocomplete") === "given-name" || el.getAttribute("autocomplete") === "family-name",
    );
    if (nameInputs.length >= 2) {
      fireEvent.change(nameInputs[0], { target: { value: "Jean" } });
      fireEvent.change(nameInputs[1], { target: { value: "Dupont" } });
    }

    fireEvent.click(screen.getByRole("button", { name: /create account|créer un compte/i }));

    await waitFor(() => {
      expect(screen.getByText(/ce champ|obligatoire/i)).toBeInTheDocument();
      expect(screen.queryByText("This field is required.")).not.toBeInTheDocument();
    });
  });
});
