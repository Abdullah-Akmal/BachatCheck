import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AssetList } from "./asset-list";
import { CompareForm } from "./compare-form";
import { GrowthChart } from "./growth-chart";
import { Headline } from "./headline";
import { DEFAULT_PARAMS } from "@/lib/params";
import { asset, compareFixture } from "@/test/fixtures";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));

describe("Headline", () => {
  it("states what the amount needs to be today to keep up with inflation", () => {
    render(<Headline data={compareFixture} />);
    expect(screen.getByRole("heading", { level: 2 })).toHaveTextContent(
      "Rs 100,000 in 10 Nov 2023 needs Rs 125,086 today to buy the same things.",
    );
    expect(screen.getByText(/Prices rose 25.1% over 3 years/)).toHaveTextContent("(7.7% a year)");
    expect(screen.getByText(/options beat inflation/)).toHaveTextContent("2 of 3 options beat inflation — best was KSE-100 index.");
  });

  it("explains when inflation data is missing", () => {
    const data = { ...compareFixture, headline: { ...compareFixture.headline, inflation: null, amount_needed_to_keep_up: null } };
    render(<Headline data={data} />);
    expect(screen.getByRole("heading")).toHaveTextContent("Inflation data isn't available");
  });
});

describe("AssetList", () => {
  it("orders by real return and shows values, real badges and tax status", () => {
    render(<AssetList assets={compareFixture.assets} />);
    const cards = screen.getAllByRole("listitem").filter((li) => li.closest("ul")?.classList.contains("grid"));
    expect(cards.map((c) => within(c).getAllByText(/./)[0].textContent?.trim())).toEqual([
      "KSE-100 index",
      "Money Market funds (median) Demo data",
      "T-bills (3 months, rolled over)",
      "Bank savings account",
    ]);

    const kse = cards[0];
    expect(kse).toHaveTextContent("Rs 313,924");
    expect(kse).toHaveTextContent("+151.0%");
    expect(kse).toHaveTextContent("beat inflation");
    expect(kse).toHaveTextContent("After tax (15%): Rs 281,835");

    const savings = cards[3];
    expect(savings).toHaveTextContent("-1.5%");
    expect(savings).toHaveTextContent("lost to inflation");
    expect(savings).toHaveTextContent("tax rate not yet verified");
  });

  it("lists unavailable assets with the reason instead of a number", () => {
    render(<AssetList assets={compareFixture.assets} />);
    expect(screen.getByText("Not included").parentElement).toHaveTextContent(
      "Gold (24k, per tola): Gold prices are maintained by hand",
    );
  });
});

describe("GrowthChart", () => {
  it("defaults to the core series and caps the selection at four", async () => {
    const user = userEvent.setup();
    const assets = [
      ...compareFixture.assets,
      asset({ key: "usd", label: "US dollars (cash)" }),
      asset({ key: "fund:equity", label: "Equity funds (median)" }),
    ];
    render(<GrowthChart data={{ ...compareFixture, assets }} />);

    const chip = (name: string) => screen.getByRole("button", { name });
    // Default: savings, T-bills, KSE-100, money market (4 of 4).
    expect(chip("Bank savings account")).toHaveAttribute("aria-pressed", "true");
    expect(chip("KSE-100 index")).toHaveAttribute("aria-pressed", "true");
    expect(chip("US dollars (cash)")).toBeDisabled();
    // Gold isn't available, so it isn't offered.
    expect(screen.queryByRole("button", { name: /Gold/ })).toBeNull();

    await user.click(chip("Bank savings account"));
    expect(chip("Bank savings account")).toHaveAttribute("aria-pressed", "false");
    expect(chip("US dollars (cash)")).toBeEnabled();
    await user.click(chip("US dollars (cash)"));
    expect(chip("US dollars (cash)")).toHaveAttribute("aria-pressed", "true");

    await user.click(screen.getByRole("radio", { name: "Rupees (nominal)" }));
    expect(screen.getByRole("radio", { name: "Rupees (nominal)" })).toHaveAttribute("aria-checked", "true");
    expect(screen.getByText(/what you'd need just to keep up/)).toBeInTheDocument();
  });
});

describe("CompareForm", () => {
  beforeEach(() => push.mockReset());

  it("formats the amount and pushes a shareable URL", async () => {
    const user = userEvent.setup();
    render(<CompareForm initial={DEFAULT_PARAMS} />);
    const amount = screen.getByRole("textbox", { name: /Amount/ });
    await user.clear(amount);
    await user.type(amount, "1250000");
    expect(amount).toHaveValue("1,250,000");
    await user.click(screen.getByRole("radio", { name: "5y" }));
    await user.click(screen.getByRole("checkbox", { name: /Shariah/ }));
    await user.click(screen.getByRole("button", { name: "Compare" }));
    expect(push).toHaveBeenCalledWith("/?amount=1250000&years=5&shariah=true", { scroll: false });
  });

  it("blocks an empty amount with a message", async () => {
    const user = userEvent.setup();
    render(<CompareForm initial={DEFAULT_PARAMS} />);
    await user.clear(screen.getByRole("textbox", { name: /Amount/ }));
    await user.click(screen.getByRole("button", { name: "Compare" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Enter an amount");
    expect(push).not.toHaveBeenCalled();
  });
});
