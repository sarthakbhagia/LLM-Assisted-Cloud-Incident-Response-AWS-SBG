import '@testing-library/jest-dom';

// Polyfill ResizeObserver for recharts
global.ResizeObserver = class ResizeObserver {
  constructor(cb) {
    this.cb = cb
  }
  observe() {}
  unobserve() {}
  disconnect() {}
}

// Suppress React Router future flag warnings
const originalWarn = console.warn
console.warn = (...args) => {
  if (args[0]?.includes?.('React Router Future Flag Warning')) return
  originalWarn.apply(console, args)
}
