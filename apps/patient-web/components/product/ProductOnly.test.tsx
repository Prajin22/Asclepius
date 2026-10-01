import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ProductOnly, forProduct } from "./ProductOnly";

vi.mock("next/navigation", () => ({
  notFound: () => {
    throw new Error("NEXT_NOT_FOUND");
  },
}));

describe("ProductOnly", () => {
  it("renders an area in its own product", () => {
    render(
      <ProductOnly product="ip_sakti" current="ip_sakti">
        <p>inside</p>
      </ProductOnly>,
    );
    expect(screen.getByText("inside")).toBeInTheDocument();
  });

  it.each([
    ["carebridge", "ip_sakti"],
    ["ip_sakti", "carebridge"],
  ] as const)("makes a %s area not exist in a %s build", (product, current) => {
    expect(() =>
      render(
        <ProductOnly product={product} current={current}>
          <p>inside</p>
        </ProductOnly>,
      ),
    ).toThrow("NEXT_NOT_FOUND");
  });

  it("is CareBridge-only by default in a build that sets no product", () => {
    render(
      <ProductOnly product="carebridge">
        <p>healthcare</p>
      </ProductOnly>,
    );
    expect(screen.getByText("healthcare")).toBeInTheDocument();
  });
});

describe("forProduct", () => {
  const A = () => <p>carebridge screen</p>;
  const B = () => <p>ip-sakti screen</p>;

  it("picks the screen for the build's product", () => {
    const Picked = forProduct({ carebridge: A, ip_sakti: B }, "ip_sakti");
    render(<Picked />);
    expect(screen.getByText("ip-sakti screen")).toBeInTheDocument();
  });

  it("keeps CareBridge's screen when no product is set", () => {
    const Picked = forProduct({ carebridge: A, ip_sakti: B });
    render(<Picked />);
    expect(screen.getByText("carebridge screen")).toBeInTheDocument();
  });
});
