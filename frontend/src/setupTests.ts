import '@testing-library/jest-dom';

// jsdom doesn't implement ResizeObserver, which Recharts' ResponsiveContainer
// relies on to measure its container. A minimal no-op mock is sufficient for
// tests that don't assert on actual chart pixel dimensions.
global.ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
};
