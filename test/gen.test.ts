import { describe, it, expect, vi, afterEach } from "vitest";
import { generateSheet, DEFAULT_MODEL, DEFAULT_ENV } from "../src/core/gen.js";
import type { GenContext } from "../src/core/gen.js";
import type { RawImage } from "../src/core/image.js";

const PROVIDERS = ["replicate", "gemini", "novita-seedream", "novita-qwen"];

const template: RawImage = { width: 1, height: 1, data: new Uint8ClampedArray([0, 0, 0, 255]) };
const out: RawImage = { width: 2, height: 2, data: new Uint8ClampedArray(16) };

const ctx: GenContext = {
  apiKey: () => "test-token",
  codec: {
    encodePng: async () => new Uint8Array([1, 2, 3]),
    decodeImage: () => out,
    drawLabel: async () => ({ width: 1, height: 1, data: new Uint8ClampedArray(4) }),
  },
};

afterEach(() => vi.unstubAllGlobals());

describe("provider tables", () => {
  it("DEFAULT_MODEL and DEFAULT_ENV cover every provider", () => {
    expect(Object.keys(DEFAULT_MODEL).sort()).toEqual([...PROVIDERS].sort());
    expect(Object.keys(DEFAULT_ENV).sort()).toEqual([...PROVIDERS].sort());
  });
  it("replicate defaults to nano-banana-pro on REPLICATE_API_TOKEN", () => {
    expect(DEFAULT_MODEL.replicate).toBe("google/nano-banana-pro");
    expect(DEFAULT_ENV.replicate).toBe("REPLICATE_API_TOKEN");
  });
});

describe("replicate generation branch", () => {
  function stubFetch(predictionJson: unknown) {
    const calls: { url: string; init: any }[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init: any) => {
        calls.push({ url: String(url), init });
        if (String(url).includes("/predictions")) {
          return { ok: true, json: async () => predictionJson } as any;
        }
        return { ok: true, arrayBuffer: async () => new Uint8Array([9, 9, 9]).buffer } as any;
      }),
    );
    return calls;
  }

  it("posts to the model's predictions endpoint with Prefer:wait and the bearer token", async () => {
    const calls = stubFetch({ status: "succeeded", output: ["https://img/x.png"] });
    const result = await generateSheet(ctx, template, "a golem", { provider: "replicate" });
    expect(result).toBe(out);
    expect(calls[0].url).toContain("api.replicate.com/v1/models/google/nano-banana-pro/predictions");
    expect(calls[0].init.headers.Prefer).toBe("wait");
    expect(calls[0].init.headers.Authorization).toBe("Bearer test-token");
    const body = JSON.parse(calls[0].init.body);
    expect(body.input.prompt).toBe("a golem");
    expect(body.input.image_input[0]).toMatch(/^data:image\/png;base64,/);
  });

  it("is the default provider", async () => {
    const calls = stubFetch({ status: "succeeded", output: ["https://img/x.png"] });
    await generateSheet(ctx, template, "a golem");
    expect(calls[0].url).toContain("google/nano-banana-pro/predictions");
  });

  it("accepts a single-string output", async () => {
    stubFetch({ status: "succeeded", output: "https://img/x.png" });
    expect(await generateSheet(ctx, template, "x", { provider: "replicate" })).toBe(out);
  });

  it("throws when the prediction did not succeed", async () => {
    stubFetch({ status: "failed", error: "boom" });
    await expect(generateSheet(ctx, template, "x", { provider: "replicate" })).rejects.toThrow(/replicate failed/);
  });

  it("throws when the prediction returns no image", async () => {
    stubFetch({ status: "succeeded", output: [] });
    await expect(generateSheet(ctx, template, "x", { provider: "replicate" })).rejects.toThrow(/no image/);
  });
});
