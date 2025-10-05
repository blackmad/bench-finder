import type React from "react"
import styled, { keyframes } from "styled-components"

const spin = keyframes`
  0% {
    transform: rotate(0deg);
  }
  100% {
    transform: rotate(360deg);
  }
`

const SpinnerContainer = styled.div`
  display: inline-block;
`

const Spinner = styled.div<{ size?: "small" | "medium" | "large" }>`
  width: ${({ size = "medium" }) => {
    switch (size) {
      case "small":
        return "16px"
      case "large":
        return "48px"
      default:
        return "32px"
    }
  }};
  height: ${({ size = "medium" }) => {
    switch (size) {
      case "small":
        return "16px"
      case "large":
        return "48px"
      default:
        return "32px"
    }
  }};
  border: ${({ size = "medium", theme }) => {
    const width = size === "small" ? "2px" : "3px"
    return `${width} solid ${theme.colors.gray200}`
  }};
  border-radius: 50%;
  border-top-color: ${({ theme }) => theme.colors.primary};
  animation: ${spin} 1s ease-in-out infinite;
`

interface LoadingSpinnerProps {
  size?: "small" | "medium" | "large"
  className?: string
}

const LoadingSpinner: React.FC<LoadingSpinnerProps> = ({
  size = "medium",
  className,
}) => {
  return (
    <SpinnerContainer className={className}>
      <Spinner size={size} />
    </SpinnerContainer>
  )
}

export default LoadingSpinner
