import React from 'react'
import styled from 'styled-components'
import { X, AlertTriangle } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'

const ToastContainer = styled(motion.div)`
  position: fixed;
  top: 20px;
  right: 20px;
  z-index: 1000;
  max-width: 400px;
  background: ${({ theme }) => theme.colors.error};
  color: white;
  padding: ${({ theme }) => theme.spacing[4]};
  border-radius: ${({ theme }) => theme.borderRadius.lg};
  box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04);
  display: flex;
  align-items: flex-start;
  gap: ${({ theme }) => theme.spacing[3]};
`

const IconContainer = styled.div`
  flex-shrink: 0;
  margin-top: 2px;
`

const Content = styled.div`
  flex: 1;
`

const Title = styled.div`
  font-weight: ${({ theme }) => theme.typography.weights.semibold};
  margin-bottom: ${({ theme }) => theme.spacing[1]};
`

const Message = styled.div`
  font-size: ${({ theme }) => theme.typography.sizes.sm};
  opacity: 0.9;
  line-height: 1.4;
`

const CloseButton = styled.button`
  background: none;
  border: none;
  color: white;
  cursor: pointer;
  padding: ${({ theme }) => theme.spacing[1]};
  border-radius: ${({ theme }) => theme.borderRadius.sm};
  transition: background-color 0.2s ease;

  &:hover {
    background: rgba(255, 255, 255, 0.1);
  }
`

interface ErrorToastProps {
    error: string
    onClose: () => void
}

export const ErrorToast: React.FC<ErrorToastProps> = ({ error, onClose }) => {
    return (
        <AnimatePresence>
            <ToastContainer
                initial={{ opacity: 0, y: -50, scale: 0.95 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: -50, scale: 0.95 }}
                transition={{ duration: 0.2 }}
            >
                <IconContainer>
                    <AlertTriangle size={20} />
                </IconContainer>
                <Content>
                    <Title>Error</Title>
                    <Message>{error}</Message>
                </Content>
                <CloseButton onClick={onClose}>
                    <X size={16} />
                </CloseButton>
            </ToastContainer>
        </AnimatePresence>
    )
}

export default ErrorToast
