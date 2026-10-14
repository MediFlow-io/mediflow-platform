import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const store = new Map();
globalThis.localStorage = {
  getItem: (k) => (store.has(k) ? store.get(k) : null),
  setItem: (k, v) => store.set(k, String(v)),
  removeItem: (k) => store.delete(k),
};

const { errorMessage, request, setTokens, getAccessToken, onSessionExpired, ApiError } = await import("../api/client");

const json = (status, body) => ({ ok: status < 400, status, json: async () => body });

describe("errorMessage", () => {
  it("prefers detail", () => expect(errorMessage({ detail: "Nope." }, 403)).toBe("Nope."));
  it("names the field for validation errors", () =>
    expect(errorMessage({ fullName: ["This field is required."], non_field_errors: ["Bad."] }, 400))
      .toBe("fullName: This field is required. Bad."));
  it("handles nested errors and empty bodies", () => {
    expect(errorMessage({ vitals: { spo2: ["Too high."] } }, 400)).toBe("vitals: spo2: Too high.");
    expect(errorMessage(null, 500)).toBe("Request failed (500).");
  });
});

describe("request", () => {
  beforeEach(() => store.clear());
  afterEach(() => vi.unstubAllGlobals());

  it("routes auth calls to the gateway and others to the API, with the bearer token", async () => {
    setTokens({ access: "A1", refresh: "R1" });
    const fetch = vi.fn(async () => json(200, { ok: true }));
    vi.stubGlobal("fetch", fetch);
    await request("/api/patients");
    expect(fetch.mock.calls[0][0]).toBe("/api/patients");
    expect(fetch.mock.calls[0][1].headers.Authorization).toBe("Bearer A1");
  });

  it("refreshes once on 401, stores the rotated pair and retries", async () => {
    setTokens({ access: "old", refresh: "R1" });
    const fetch = vi.fn()
      .mockResolvedValueOnce(json(401, { detail: "expired" }))
      .mockResolvedValueOnce(json(200, { access: "new", refresh: "R2" }))
      .mockResolvedValueOnce(json(200, [1, 2]));
    vi.stubGlobal("fetch", fetch);
    await expect(request("/api/queue")).resolves.toEqual([1, 2]);
    expect(fetch.mock.calls[1][0]).toBe("/api/auth/token/refresh");
    expect(fetch.mock.calls[2][1].headers.Authorization).toBe("Bearer new");
    expect(getAccessToken()).toBe("new");
  });

  it("signals session expiry when refresh fails", async () => {
    setTokens({ access: "old", refresh: "R1" });
    vi.stubGlobal("fetch", vi.fn()
      .mockResolvedValueOnce(json(401, { detail: "expired" }))
      .mockResolvedValueOnce(json(401, { detail: "revoked" })));
    const expired = vi.fn();
    const stop = onSessionExpired(expired);
    await expect(request("/api/queue")).rejects.toBeInstanceOf(ApiError);
    expect(expired).toHaveBeenCalledOnce();
    expect(getAccessToken()).toBeNull();
    stop();
  });

  it("turns network failures into a readable error", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => { throw new TypeError("Failed to fetch"); }));
    await expect(request("/api/dashboard")).rejects.toThrow("Can't reach the MediFlow server");
  });
});
