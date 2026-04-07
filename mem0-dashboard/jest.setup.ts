import "@testing-library/jest-dom";

// Mock next/navigation
jest.mock("next/navigation", () => ({
  usePathname: jest.fn(() => "/"),
  useRouter: jest.fn(() => ({
    push: jest.fn(),
    replace: jest.fn(),
    back: jest.fn(),
    prefetch: jest.fn(),
  })),
  useParams: jest.fn(() => ({})),
  useSearchParams: jest.fn(() => new URLSearchParams()),
}));

// Mock next/link
jest.mock("next/link", () => {
  const React = require("react");
  return function MockLink({ children, href, ...props }: { children: React.ReactNode; href: string; [key: string]: unknown }) {
    return React.createElement("a", { href, ...props }, children);
  };
});

// Mock fetch
global.fetch = jest.fn();

// Mock localStorage
const localStorageMock = (() => {
  let store: Record<string, string> = {};
  return {
    getItem: jest.fn((key: string) => store[key] || null),
    setItem: jest.fn((key: string, value: string) => { store[key] = value; }),
    removeItem: jest.fn((key: string) => { delete store[key]; }),
    clear: jest.fn(() => { store = {}; }),
    get length() { return Object.keys(store).length; },
    key: jest.fn((index: number) => Object.keys(store)[index] || null),
  };
})();
Object.defineProperty(window, "localStorage", { value: localStorageMock });

// Mock window.dispatchEvent
window.dispatchEvent = jest.fn();

// Mock AbortSignal.timeout
if (!AbortSignal.timeout) {
  (AbortSignal as unknown as Record<string, unknown>).timeout = jest.fn(() => new AbortController().signal);
}
