import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { apiFetch, readCookie } from "./http";

const BASE = "http://localhost";

function setCookie(value: string) {
  document.cookie = value;
}

describe("apiFetch", () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    setCookie("csrftoken=tok123; path=/");
    fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    setCookie("csrftoken=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/");
  });

  it("reads cookies by exact name", () => {
    setCookie("xcsrftoken=nope; path=/");
    expect(readCookie("csrftoken")).toBe("tok123");
  });

  it("adds the CSRF header to unsafe requests only", async () => {
    fetchMock.mockResolvedValue(new Response(null, { status: 204 }));

    await apiFetch(new Request(`${BASE}/api/v1/things/`, { method: "POST", body: "{}" }));
    await apiFetch(new Request(`${BASE}/api/v1/things/`));

    const [post, get] = fetchMock.mock.calls.map(([req]) => req as Request);
    expect(post.headers.get("X-CSRFToken")).toBe("tok123");
    expect(get.headers.get("X-CSRFToken")).toBeNull();
  });

  it("refreshes once on 401 and retries the original request", async () => {
    fetchMock
      .mockResolvedValueOnce(new Response(null, { status: 401 }))
      .mockResolvedValueOnce(new Response(null, { status: 204 })) // refresh
      .mockResolvedValueOnce(new Response("{}", { status: 200 }));

    const response = await apiFetch(new Request(`${BASE}/api/v1/things/`));

    expect(response.status).toBe(200);
    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(fetchMock.mock.calls[1][0]).toBe("/api/v1/auth/refresh/");
  });

  it("returns the 401 when refresh fails", async () => {
    fetchMock
      .mockResolvedValueOnce(new Response(null, { status: 401 }))
      .mockResolvedValueOnce(new Response(null, { status: 401 }));

    const response = await apiFetch(new Request(`${BASE}/api/v1/things/`));

    expect(response.status).toBe(401);
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("does not try to refresh when an auth endpoint itself returns 401", async () => {
    fetchMock.mockResolvedValueOnce(new Response(null, { status: 401 }));

    const response = await apiFetch(new Request(`${BASE}/api/v1/auth/login/`, { method: "POST", body: "{}" }));

    expect(response.status).toBe(401);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});

describe("apiFetch portal separation", () => {
  beforeEach(() => {
    document.cookie = "csrftoken=tok123; path=/";
  });
  afterEach(() => vi.unstubAllGlobals());

  it("refreshes recruiter requests through the recruiter auth endpoint", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response(null, { status: 401 }))
      .mockResolvedValueOnce(new Response(null, { status: 204 }))
      .mockResolvedValueOnce(new Response("{}", { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    await apiFetch(new Request(`${BASE}/api/v1/recruiter/drives/`));
    expect(fetchMock.mock.calls[1][0]).toBe("/api/v1/recruiter/auth/refresh/");
  });
});
