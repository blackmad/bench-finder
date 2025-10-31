import { createGlobalStyle } from "styled-components"

const GlobalStyles = createGlobalStyle`
  * {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
  }

  html {
    scroll-behavior: smooth;
  }

  body {
    font-family: ${({ theme }) => theme.typography.fonts.primary};
    font-size: ${({ theme }) => theme.typography.sizes.base};
    line-height: ${({ theme }) => theme.typography.lineHeights.normal};
    color: ${({ theme }) => theme.colors.textPrimary};
    background: ${({ theme }) => theme.colors.backgroundSecondary};
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
    min-height: 100vh;
  }

  #root {
    min-height: 100vh;
    display: flex;
    flex-direction: column;
  }

  /* Scrollbar styles */
  ::-webkit-scrollbar {
    width: 8px;
    height: 8px;
  }

  ::-webkit-scrollbar-track {
    background: ${({ theme }) => theme.colors.gray100};
  }

  ::-webkit-scrollbar-thumb {
    background: ${({ theme }) => theme.colors.gray300};
    border-radius: ${({ theme }) => theme.borderRadius.full};
  }

  ::-webkit-scrollbar-thumb:hover {
    background: ${({ theme }) => theme.colors.gray400};
  }

  /* Focus styles - Refined */
  :focus-visible {
    outline: 2px solid ${({ theme }) => theme.colors.primary};
    outline-offset: 3px;
    border-radius: ${({ theme }) => theme.borderRadius.base};
  }

  :focus:not(:focus-visible) {
    outline: none;
  }

  /* Selection styles */
  ::selection {
    background: ${({ theme }) => theme.colors.primary}25;
    color: ${({ theme }) => theme.colors.textPrimary};
  }

  /* Link styles */
  a {
    color: ${({ theme }) => theme.colors.primary};
    text-decoration: none;
    transition: color ${({ theme }) => theme.transitions.fast};

    &:hover {
      color: ${({ theme }) => theme.colors.primaryDark};
    }
  }

  /* Button reset */
  button {
    border: none;
    background: none;
    cursor: pointer;
    font-family: inherit;
  }

  /* Input and form element styles */
  input, select, textarea {
    font-family: inherit;
    font-size: inherit;
  }

  /* Leaflet overrides */
  .leaflet-container {
    font-family: ${({ theme }) => theme.typography.fonts.primary};
  }

  .leaflet-popup-content-wrapper {
    border-radius: ${({ theme }) => theme.borderRadius.lg};
    box-shadow: ${({ theme }) => theme.shadows.xl};
  }

  .leaflet-popup-content {
    margin: ${({ theme }) => theme.spacing[4]};
    font-size: ${({ theme }) => theme.typography.sizes.sm};
    line-height: ${({ theme }) => theme.typography.lineHeights.normal};
  }

  /* Loading animation */
  @keyframes spin {
    from {
      transform: rotate(0deg);
    }
    to {
      transform: rotate(360deg);
    }
  }

  .spinner {
    animation: spin 1s linear infinite;
  }

  /* Utility classes */
  .sr-only {
    position: absolute;
    width: 1px;
    height: 1px;
    padding: 0;
    margin: -1px;
    overflow: hidden;
    clip: rect(0, 0, 0, 0);
    white-space: nowrap;
    border: 0;
  }

  .text-center {
    text-align: center;
  }

  .text-left {
    text-align: left;
  }

  .text-right {
    text-align: right;
  }

  /* Responsive typography */
  @media (max-width: ${({ theme }) => theme.breakpoints.sm}) {
    body {
      font-size: ${({ theme }) => theme.typography.sizes.sm};
    }
  }

  /* Print styles */
  @media print {
    body {
      background: white;
    }

    .no-print {
      display: none !important;
    }
  }

  /* High contrast mode support */
  @media (prefers-contrast: high) {
    body {
      background: white;
      color: black;
    }
  }

  /* Reduced motion support */
  @media (prefers-reduced-motion: reduce) {
    * {
      animation-duration: 0.01ms !important;
      animation-iteration-count: 1 !important;
      transition-duration: 0.01ms !important;
      scroll-behavior: auto !important;
    }
  }

  /* Dark mode support (future enhancement) */
  @media (prefers-color-scheme: dark) {
    /* Dark mode styles would go here */
  }
`

export default GlobalStyles
