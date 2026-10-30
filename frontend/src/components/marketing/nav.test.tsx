import type { ComponentProps } from "react";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MarketingNav } from "@/components/marketing/nav";

const navigation = vi.hoisted(() => ({ pathname: "/" }));

vi.mock("next/navigation", () => ({
  usePathname: () => navigation.pathname,
}));

vi.mock("next/link", () => ({
  default: ({ href, children, ...props }: ComponentProps<"a">) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

describe("MarketingNav", () => {
  afterEach(() => {
    navigation.pathname = "/";
  });

  it("keeps primary destinations visible and groups secondary pages under More", async () => {
    render(<MarketingNav />);

    const primary = screen.getByRole("navigation", { name: "Primary navigation" });
    for (const label of ["Product", "Simulator", "Migration", "Pricing", "Docs"]) {
      expect(within(primary).getByRole("link", { name: label })).toBeTruthy();
    }

    const more = screen.getByRole("button", { name: "More pages" });
    fireEvent.keyDown(more, { key: "ArrowDown" });
    for (const label of ["Roadmap", "Changelog", "Feedback", "Contact"]) {
      expect(await screen.findByRole("menuitem", { name: label })).toBeTruthy();
    }
  });

  it("closes the More menu with Escape", async () => {
    render(<MarketingNav />);

    const more = screen.getByRole("button", { name: "More pages" });
    fireEvent.keyDown(more, { key: "ArrowDown" });
    expect(await screen.findByRole("menuitem", { name: "Roadmap" })).toBeTruthy();
    fireEvent.keyDown(screen.getByRole("menu"), { key: "Escape" });

    await waitFor(() => expect(screen.queryByRole("menu")).toBeNull());
  });

  it("exposes every destination and account action in the mobile menu and closes on Escape", () => {
    render(<MarketingNav />);

    const toggle = screen.getByRole("button", { name: "Open navigation menu" });
    fireEvent.click(toggle);

    expect(toggle.getAttribute("aria-expanded")).toBe("true");
    const mobile = screen.getByRole("navigation", { name: "Mobile navigation" });
    for (const label of [
      "Product",
      "Simulator",
      "Migration",
      "Pricing",
      "Docs",
      "Roadmap",
      "Changelog",
      "Feedback",
      "Contact",
      "Sign In",
      "Start Evaluation",
    ]) {
      expect(within(mobile).getByRole("link", { name: label })).toBeTruthy();
    }

    fireEvent.keyDown(window, { key: "Escape" });
    expect(toggle.getAttribute("aria-expanded")).toBe("false");
    expect(document.activeElement).toBe(toggle);
  });

  it("marks the current route as active", () => {
    navigation.pathname = "/pricing";
    render(<MarketingNav />);

    const primary = screen.getByRole("navigation", { name: "Primary navigation" });
    expect(within(primary).getByRole("link", { name: "Pricing" }).getAttribute("aria-current")).toBe(
      "page",
    );
  });
});
