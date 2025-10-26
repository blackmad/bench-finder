export const theme = {
  colors: {
    // Primary palette
    primary: "#3b82f6",
    primaryLight: "#60a5fa",
    primaryDark: "#2563eb",

    // Neutral colors
    gray50: "#f8f9fb",
    gray100: "#f1f5f9",
    gray200: "#e2e8f0",
    gray300: "#cbd5e1",
    gray400: "#94a3b8",
    gray500: "#64748b",
    gray600: "#475569",
    gray700: "#334155",
    gray800: "#1e293b",
    gray900: "#0f172a",

    // Semantic colors
    success: "#10b981",
    successLight: "#34d399",
    warning: "#f59e0b",
    warningLight: "#fbbf24",
    error: "#ef4444",
    errorLight: "#f87171",

    // Detection type colors
    roboflow: "#2563eb",
    ultralytics: "#059669",
    mapillary: "#ea580c",

    // Additional colors for UI components
    primaryHover: "#2563eb",
    info: "#17a2b8",
    infoLight: "#d1ecf1",

    // Background colors
    background: "#ffffff",
    backgroundSecondary: "#f8f9fb",
    backgroundTertiary: "#f1f5f9",

    // Text colors
    textPrimary: "#1e293b",
    textSecondary: "#64748b",
    textTertiary: "#94a3b8",

    // Border colors
    border: "#e2e8f0",
    borderLight: "#f1f5f9",

    // Special colors
    overlay: "rgba(0, 0, 0, 0.5)",
    overlayLight: "rgba(0, 0, 0, 0.1)",
  },

  typography: {
    fonts: {
      primary:
        "'SF Pro Display', 'Helvetica Neue', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
      mono: "'SF Mono', 'Monaco', 'Inconsolata', 'Roboto Mono', monospace",
    },
    sizes: {
      xs: "0.75rem", // 12px
      sm: "0.875rem", // 14px
      base: "1rem", // 16px
      lg: "1.125rem", // 18px
      xl: "1.25rem", // 20px
      "2xl": "1.5rem", // 24px
      "3xl": "1.875rem", // 30px
      "4xl": "2.25rem", // 36px
    },
    weights: {
      normal: 400,
      medium: 500,
      semibold: 600,
      bold: 700,
    },
    lineHeights: {
      tight: 1.25,
      normal: 1.5,
      relaxed: 1.625,
    },
  },

  spacing: {
    0: "0",
    1: "0.25rem", // 4px
    2: "0.5rem", // 8px
    3: "0.75rem", // 12px
    4: "1rem", // 16px
    5: "1.25rem", // 20px
    6: "1.5rem", // 24px
    8: "2rem", // 32px
    10: "2.5rem", // 40px
    12: "3rem", // 48px
    16: "4rem", // 64px
    20: "5rem", // 80px
    24: "6rem", // 96px
  },

  borderRadius: {
    none: "0",
    sm: "0.125rem", // 2px
    base: "0.375rem", // 6px
    md: "0.5rem", // 8px
    lg: "0.75rem", // 12px
    xl: "1rem", // 16px
    "2xl": "1.5rem", // 24px
    full: "9999px",
  },

  shadows: {
    sm: "0 1px 2px 0 rgba(0, 0, 0, 0.05)",
    base: "0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px -1px rgba(0, 0, 0, 0.1)",
    md: "0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -2px rgba(0, 0, 0, 0.1)",
    lg: "0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -4px rgba(0, 0, 0, 0.1)",
    xl: "0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.1)",
    "2xl": "0 25px 50px -12px rgba(0, 0, 0, 0.25)",
    inner: "inset 0 2px 4px 0 rgba(0, 0, 0, 0.05)",
  },

  breakpoints: {
    sm: "640px",
    md: "768px",
    lg: "1024px",
    xl: "1280px",
    "2xl": "1536px",
  },

  zIndex: {
    dropdown: 1000,
    sticky: 1020,
    fixed: 1030,
    modalBackdrop: 1040,
    modal: 1050,
    popover: 1060,
    tooltip: 1070,
  },

  transitions: {
    fast: "150ms ease-in-out",
    normal: "250ms ease-in-out",
    slow: "300ms ease-in-out",
  },

  // Animation curves
  easing: {
    easeInOut: "cubic-bezier(0.4, 0, 0.2, 1)",
    easeOut: "cubic-bezier(0, 0, 0.2, 1)",
    easeIn: "cubic-bezier(0.4, 0, 1, 1)",
  },
}

export type Theme = typeof theme
export default theme
