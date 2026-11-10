import { describe, expect, it } from "vitest";

import { DEFAULT_PARAMS, compareQuery, parseCompareParams } from "./params";

describe("parseCompareParams", () => {
  it("uses defaults for empty or junk input", () => {
    expect(parseCompareParams({})).toEqual({ ...DEFAULT_PARAMS, savings_rate: undefined });
    expect(parseCompareParams({ amount: "abc", years: "7", filer_status: "x" })).toEqual({
      ...DEFAULT_PARAMS,
      savings_rate: undefined,
    });
  });

  it("parses valid values", () => {
    expect(
      parseCompareParams({
        amount: "1,250,000",
        years: "5",
        shariah: "true",
        filer_status: "non_filer",
        savings_rate: "10.5",
      }),
    ).toEqual({ amount: 1_250_000, years: 5, shariah: true, filer_status: "non_filer", savings_rate: 10.5 });
  });

  it("rejects out-of-range amounts and rates", () => {
    expect(parseCompareParams({ amount: "-5" }).amount).toBe(DEFAULT_PARAMS.amount);
    expect(parseCompareParams({ amount: "1e15" }).amount).toBe(DEFAULT_PARAMS.amount);
    expect(parseCompareParams({ savings_rate: "80" }).savings_rate).toBeUndefined();
  });
});

describe("compareQuery", () => {
  it("round-trips through parseCompareParams", () => {
    const p = { amount: 500_000, years: 2, shariah: true, filer_status: "non_filer" as const, savings_rate: 9 };
    const parsed = parseCompareParams(Object.fromEntries(new URLSearchParams(compareQuery(p))));
    expect(parsed).toEqual(p);
  });
  it("omits defaults", () => {
    expect(compareQuery({ ...DEFAULT_PARAMS })).toBe("amount=100000&years=3");
  });
});
