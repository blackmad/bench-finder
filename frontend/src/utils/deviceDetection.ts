import { useEffect, useState } from "react"

/**
 * Detect if the current device is a mobile device
 */
export function isMobileDevice(): boolean {
  if (typeof window === "undefined") return false

  // Check user agent
  const userAgent =
    navigator.userAgent || navigator.vendor || (window as any).opera

  // Check for mobile devices
  const mobileRegex =
    /android|webos|iphone|ipad|ipod|blackberry|iemobile|opera mini/i
  if (mobileRegex.test(userAgent)) {
    return true
  }

  // Check screen width (more reliable for modern browsers)
  if (window.innerWidth <= 768) {
    return true
  }

  // Check for touch capability
  if ("ontouchstart" in window || navigator.maxTouchPoints > 0) {
    // Only consider it mobile if screen is small
    if (window.innerWidth <= 1024) {
      return true
    }
  }

  return false
}

/**
 * Hook to detect if device is mobile and update on resize
 */
export function useIsMobile(): boolean {
  const [isMobile, setIsMobile] = useState(isMobileDevice)

  useEffect(() => {
    const handleResize = () => {
      setIsMobile(isMobileDevice())
    }

    window.addEventListener("resize", handleResize)
    return () => window.removeEventListener("resize", handleResize)
  }, [])

  return isMobile
}
