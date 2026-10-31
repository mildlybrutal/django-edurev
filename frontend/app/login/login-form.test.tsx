import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { LoginForm, safeNext } from "./login-form";

const replace = vi.fn();
let searchParams = new URLSearchParams();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace }),
  useSearchParams: () => searchParams,
}));

function renderForm() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <LoginForm />
    </QueryClientProvider>,
  );
}

async function submit(email: string, password: string) {
  const user = userEvent.setup();
  await user.type(screen.getByLabelText("Email"), email);
  await user.type(screen.getByLabelText("Password"), password);
  await user.click(screen.getByRole("button", { name: "Sign in" }));
}

const me = { id: 1, email: "s@example.test", first_name: "", last_name: "", roles: ["student"], institution: null };

describe("LoginForm", () => {
  beforeEach(() => {
    document.cookie = "csrftoken=tok; path=/";
    searchParams = new URLSearchParams();
    replace.mockReset();
  });

  afterEach(() => vi.unstubAllGlobals());

  it("disables submit until both fields are filled", () => {
    renderForm();
    expect((screen.getByRole("button", { name: "Sign in" }) as HTMLButtonElement).disabled).toBe(true);
  });

  it("redirects to the role's home after a successful sign-in", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json(me)));
    renderForm();
    await submit("s@example.test", "pw");
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/student"));
  });

  it("returns to a safe ?next path after sign-in", async () => {
    searchParams = new URLSearchParams({ next: "/student/plan" });
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json(me)));
    renderForm();
    await submit("s@example.test", "pw");
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/student/plan"));
  });

  it("shows the server's error message on failure", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(Response.json({ detail: "Invalid email or password." }, { status: 401 })),
    );
    renderForm();
    await submit("s@example.test", "wrong");
    expect((await screen.findByRole("alert")).textContent).toBe("Invalid email or password.");
    expect(replace).not.toHaveBeenCalled();
  });
});

describe("safeNext", () => {
  it("accepts relative paths and rejects absolute or protocol-relative URLs", () => {
    expect(safeNext("/student")).toBe("/student");
    expect(safeNext("//evil.example")).toBeNull();
    expect(safeNext("https://evil.example")).toBeNull();
    expect(safeNext(null)).toBeNull();
  });
});

describe("LoginForm two-factor step", () => {
  beforeEach(() => {
    document.cookie = "csrftoken=tok; path=/";
    searchParams = new URLSearchParams();
    replace.mockReset();
  });
  afterEach(() => vi.unstubAllGlobals());

  it("asks for a code when the password step requires MFA, then signs in", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(Response.json({ mfa_required: true }))
      .mockResolvedValueOnce(Response.json(me));
    vi.stubGlobal("fetch", fetchMock);
    renderForm();
    await submit("s@example.test", "pw");
    const user = userEvent.setup();
    await user.type(await screen.findByLabelText("Authentication code"), "123456");
    await user.click(screen.getByRole("button", { name: "Verify" }));
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/student"));
    expect((fetchMock.mock.calls[1][0] as Request).url).toContain("/api/v1/auth/mfa/verify/");
  });
});
