import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { PrivateBetaBadge } from "@/components/beta/private-beta-badge";

describe("PrivateBetaBadge", () => {
  it("renders Private Beta label", () => {
    render(<PrivateBetaBadge />);
    const el = screen.getByTestId("private-beta-badge");
    expect(el.textContent).toContain("Private Beta");
  });
});
