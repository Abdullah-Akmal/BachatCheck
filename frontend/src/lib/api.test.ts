import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, WAKING_UP, apiGet } from "./api";

function respond(status: number, body: unknown, contentType = "application/json") {
  return vi.fn().mockResolvedValue(
    new Response(typeof body === "string" ? body : JSON.stringify(body), {
      status,
      headers: { "content-type": contentType },
    }),
  );
}

afterEach(() => vi.unstubAllGlobals());

describe("apiGet", () => {
  it("builds the URL and drops empty params", async () => {
    const fetchMock = respond(200, { ok: true });
    vi.stubGlobal("fetch", fetchMock);
    await apiGet("/funds", { q: "", shariah: true, category: undefined, limit: 5 });
    expect(fetchMock.mock.calls[0][0]).toBe("http://localhost:8000/api/v1/funds?shariah=true&limit=5");
  });

  it("surfaces the API's error detail", async () => {
    vi.stubGlobal("fetch", respond(404, { detail: "fund 'x' not found" }));
    await expect(apiGet("/funds/x")).rejects.toMatchObject({ status: 404, message: "fund 'x' not found" });
  });

  it("explains a cold start when the host's gateway answers instead of the API", async () => {
    vi.stubGlobal("fetch", respond(502, "<html>Bad Gateway</html>", "text/html"));
    await expect(apiGet("/compare")).rejects.toMatchObject({ status: 502, message: WAKING_UP });
  });

  it("explains a cold start when the request can't connect or times out", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("fetch failed")));
    const err = await apiGet("/compare").catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect((err as ApiError).message).toBe(WAKING_UP);
  });

  it("keeps a real 503 from the API (e.g. stocks disabled)", async () => {
    vi.stubGlobal("fetch", respond(503, { detail: "Stock data is disabled on this deployment." }));
    await expect(apiGet("/stocks/search")).rejects.toMatchObject({ status: 503, message: "Stock data is disabled on this deployment." });
  });
});
