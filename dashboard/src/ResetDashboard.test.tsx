import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { App } from "./App";
import { approved, mockBackend } from "../tests/backend";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

it("requires exact confirmation, resets only on click and refreshes the queue", async () => {
  const { fetcher } = mockBackend({
    ...approved,
    status: "decided",
    payment: { amount: "1250" },
  });
  render(<App />);
  await screen.findByRole("tab", { name: "Finished (1)" });
  fireEvent.click(screen.getByRole("tab", { name: "Reset" }));
  const button = screen.getByRole("button", { name: "Reset all claims" });
  expect(button).toHaveProperty("disabled", true);
  expect(fetcher.mock.calls.some(([path]) => path === "/api/queue/reset")).toBe(
    false,
  );
  fireEvent.change(screen.getByLabelText("Type RESET to confirm"), {
    target: { value: "reset" },
  });
  expect(button).toHaveProperty("disabled", true);
  fireEvent.change(screen.getByLabelText("Type RESET to confirm"), {
    target: { value: "RESET" },
  });
  expect(button).toHaveProperty("disabled", false);
  fireEvent.click(button);
  expect(
    await screen.findByText("2 claims returned to waiting."),
  ).toBeDefined();
  fireEvent.click(screen.getByRole("tab", { name: "Queue (2)" }));
  expect(
    await screen.findByRole("button", { name: "Run agent" }),
  ).toBeDefined();
  expect(screen.getByRole("tab", { name: "Finished (0)" })).toBeDefined();
});

it("blocks reset while an individual claim is running", async () => {
  mockBackend({ running: true, status: "in_progress" });
  render(<App />);
  await screen.findByRole("tab", { name: "Queue (2)" });
  fireEvent.click(screen.getByRole("tab", { name: "Reset" }));
  expect(screen.getByLabelText("Type RESET to confirm")).toHaveProperty(
    "disabled",
    true,
  );
  expect(screen.getByText(/Wait for all agents/)).toBeDefined();
});

it("shows reset errors and supports retry with the same confirmation", async () => {
  const { fetcher } = mockBackend();
  render(<App />);
  await screen.findByRole("tab", { name: "Queue (2)" });
  fireEvent.click(screen.getByRole("tab", { name: "Reset" }));
  fireEvent.change(screen.getByLabelText("Type RESET to confirm"), {
    target: { value: "RESET" },
  });
  fetcher.mockResolvedValueOnce(new Response("{}", { status: 409 }));
  fireEvent.click(screen.getByRole("button", { name: "Reset all claims" }));
  expect(await screen.findByRole("alert")).toBeDefined();
  fireEvent.click(screen.getByRole("button", { name: "Reset all claims" }));
  expect(
    await screen.findByText("2 claims returned to waiting."),
  ).toBeDefined();
});
