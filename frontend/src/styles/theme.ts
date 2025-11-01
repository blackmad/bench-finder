export const theme = {
  colors: {
    // Primary palette - Nature-inspired forest green
    primary: "#2D8659",
    primaryLight: "#4FB286",
    primaryDark: "#1E5C3F",

    // Accent Colors - Warm gold for highlights
    accent: "#D4AF37",
    accentLight: "#E8D19A",
    accentDark: "#B8941F",

    // Neutral colors - Warmer, more refined grays
    gray50: "#FAFAF9",
    gray100: "#F5F5F4",
    gray200: "#E7E5E4",
    gray300: "#D6D3D1",
    gray400: "#A8A29E",
    gray500: "#78716C",
    gray600: "#57534E",
    gray700: "#44403C",
    gray800: "#292524",
    gray900: "#1C1917",

    // Semantic colors (keep modern, accessible colors)
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
    primaryHover: "#1E5C3F",
    info: "#3B82F6",
    infoLight: "#DBEAFE",

    // Background colors - Warmer, more refined
    background: "#ffffff",
    backgroundSecondary: "#FAFAF9",
    backgroundTertiary: "#F5F5F4",
    surface: "#ffffff",
    surfaceElevated: "#ffffff",

    // Text colors - Adjusted for new grays
    textPrimary: "#1C1917",
    textSecondary: "#57534E",
    textTertiary: "#A8A29E",

    // Border colors - Warmer, softer
    border: "#E7E5E4",
    borderLight: "#F5F5F4",

    // Special colors
    overlay: "rgba(0, 0, 0, 0.5)",
    overlayLight: "rgba(0, 0, 0, 0.1)",

    // Glassmorphism support
    glassBackground: "rgba(255, 255, 255, 0.85)",
    glassBorder: "rgba(0, 0, 0, 0.06)",
  },

  typography: {
    fonts: {
      primary:
        "'Inter', 'SF Pro Display', 'Helvetica Neue', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
      mono: "'JetBrains Mono', 'SF Mono', 'Monaco', 'Inconsolata', 'Roboto Mono', monospace",
      display: "'Inter Display', 'Inter', sans-serif",
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
      "5xl": "3rem", // 48px
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
      loose: 2,
    },
    letterSpacing: {
      tighter: "-0.04em",
      tight: "-0.02em",
      normal: "0",
      wide: "0.025em",
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
    "3xl": "2rem", // 32px
    full: "9999px",
  },

  shadows: {
    sm: "0 1px 2px rgba(0, 0, 0, 0.04), 0 1px 3px rgba(0, 0, 0, 0.06)",
    base: "0 2px 4px rgba(0, 0, 0, 0.04), 0 1px 2px rgba(0, 0, 0, 0.06)",
    md: "0 4px 6px rgba(0, 0, 0, 0.05), 0 2px 4px rgba(0, 0, 0, 0.06)",
    lg: "0 10px 15px rgba(0, 0, 0, 0.08), 0 4px 6px rgba(0, 0, 0, 0.05)",
    xl: "0 20px 25px rgba(0, 0, 0, 0.1), 0 8px 10px rgba(0, 0, 0, 0.04)",
    "2xl": "0 25px 50px rgba(0, 0, 0, 0.15), 0 10px 15px rgba(0, 0, 0, 0.06)",
    inner: "inset 0 2px 4px rgba(0, 0, 0, 0.05)",
    primary: "0 4px 12px rgba(45, 134, 89, 0.25)",
    primaryHover: "0 8px 20px rgba(45, 134, 89, 0.3)",
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
    fast: "150ms cubic-bezier(0.4, 0, 0.2, 1)",
    normal: "250ms cubic-bezier(0.4, 0, 0.2, 1)",
    slow: "300ms cubic-bezier(0.4, 0, 0.2, 1)",
  },

  // Animation curves
  easing: {
    easeInOut: "cubic-bezier(0.4, 0, 0.2, 1)",
    easeOut: "cubic-bezier(0, 0, 0.2, 1)",
    easeIn: "cubic-bezier(0.4, 0, 1, 1)",
    bounce: "cubic-bezier(0.68, -0.55, 0.265, 1.55)",
  },

  // Glassmorphism effects
  glass: {
    background: "rgba(255, 255, 255, 0.85)",
    backdrop: "blur(20px) saturate(180%)",
    border: "1px solid rgba(0, 0, 0, 0.06)",
    shadow:
      "0 1px 0 0 rgba(255, 255, 255, 0.5) inset, 0 4px 24px rgba(0, 0, 0, 0.04)",
  },
}

export type Theme = typeof theme
export default theme
