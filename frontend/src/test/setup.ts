/**
 * Vitest setup: extend `expect` with jest-dom matchers and reset mocks between
 * tests so component tests stay isolated.
 */
import "@testing-library/jest-dom/vitest";
import { afterEach, vi } from "vitest";

afterEach(() => {
  vi.clearAllMocks();
});
