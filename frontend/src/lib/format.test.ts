import { describe, expect, it } from "vitest";

import {
  formatDate,
  formatFractionPct,
  formatPercentValue,
  formatPKR,
  formatPKRCompact,
  formatSignedPct,
} from "./format";

describe("formatPKR", () => {
  it("adds thousands separators and the Rs prefix", () => {
    expect(formatPKR("1250000.40")).toBe("Rs 1,250,000");
    expect(formatPKR(125085.66)).toBe("Rs 125,086");
  });
  it("handles negatives and missing values", () => {
    expect(formatPKR("-1250")).toBe("-Rs 1,250");
    expect(formatPKR(null)).toBe("—");
    expect(formatPKR("")).toBe("—");
  });
});

describe("percentages", () => {
  it("formats fractions as percent", () => {
    expect(formatFractionPct("0.126825")).toBe("12.7%");
    expect(formatFractionPct("0.15", 0)).toBe("15%");
  });
  it("signs real returns", () => {
    expect(formatSignedPct("0.023")).toBe("+2.3%");
    expect(formatSignedPct("-0.015201")).toBe("-1.5%");
    expect(formatSignedPct(null)).toBe("—");
  });
  it("formats published percent values", () => {
    expect(formatPercentValue("10.83")).toBe("10.83%");
    expect(formatPercentValue(null)).toBe("—");
  });
});

describe("compact axis labels", () => {
  it.each([
    [125_000, "Rs 125k"],
    [1_250_000, "Rs 1.25M"],
    [25_000_000, "Rs 25M"],
    [950, "Rs 950"],
  ])("%d -> %s", (v, expected) => {
    expect(formatPKRCompact(v)).toBe(expected);
  });
});

describe("formatDate", () => {
  it("formats ISO dates without timezone drift", () => {
    expect(formatDate("2026-11-06")).toBe("6 Nov 2026");
    expect(formatDate(null)).toBe("—");
  });
});
