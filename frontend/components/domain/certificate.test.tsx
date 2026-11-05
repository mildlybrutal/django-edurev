import { describe, expect, it } from "vitest";
import { qs } from "@/lib/api/request";
import { certificateProblem } from "./certificate";

describe("certificateProblem", () => {
  it("accepts PDFs and images up to 5 MB", () => {
    expect(certificateProblem(new File(["x"], "aws.pdf"))).toBeNull();
    expect(certificateProblem(new File(["x"], "aws.JPEG"))).toBeNull();
  });

  it("rejects other types and oversized files", () => {
    expect(certificateProblem(new File(["x"], "aws.docx"))).toMatch(/PDF, PNG or JPEG/);
    const big = new File([new Uint8Array(5 * 1024 * 1024 + 1)], "big.pdf");
    expect(certificateProblem(big)).toMatch(/5 MB/);
  });
});

describe("qs", () => {
  it("drops empty filters so exports match what is on screen", () => {
    expect(qs({ q: "", department: "CSE", band: undefined, graduation_year: 2027 })).toBe(
      "?department=CSE&graduation_year=2027",
    );
    expect(qs({ q: "" })).toBe("");
  });
});
