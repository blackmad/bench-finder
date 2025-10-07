import React, { useState } from 'react'
import styled from 'styled-components'
import { X, LogIn, UserPlus, Github, Mail } from 'lucide-react'
import { useAuth } from '../../contexts/AuthContext'

interface AuthModalProps {
  isOpen: boolean
  onClose: () => void
  initialMode?: 'signin' | 'signup'
}

const Overlay = styled.div`
  position: fixed
  top: 0
  left: 0
  right: 0
  bottom: 0
  background: rgba(0, 0, 0, 0.5)
  display: flex
  justify-content: center
  align-items: center
  z-index: 1000
`

const Modal = styled.div`
  background: white
  border-radius: 12px
  padding: 2rem
  width: 90%
  max-width: 400px
  position: relative
  box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)
`

const CloseButton = styled.button`
  position: absolute
  top: 1rem
  right: 1rem
  background: none
  border: none
  cursor: pointer
  color: ${props => props.theme.colors.text.secondary}
  
  &:hover {
    color: ${props => props.theme.colors.text.primary}
  }
`

const Title = styled.h2`
  margin: 0 0 1.5rem 0
  color: ${props => props.theme.colors.text.primary}
  text-align: center
  font-size: 1.5rem
`

const Form = styled.form`
  display: flex
  flex-direction: column
  gap: 1rem
`

const InputGroup = styled.div`
  display: flex
  flex-direction: column
  gap: 0.5rem
`

const Label = styled.label`
  font-weight: 500
  color: ${props => props.theme.colors.text.primary}
  font-size: 0.9rem
`

const Input = styled.input`
  padding: 0.75rem
  border: 2px solid ${props => props.theme.colors.border}
  border-radius: 8px
  font-size: 1rem
  transition: border-color 0.2s
  
  &:focus {
    outline: none
    border-color: ${props => props.theme.colors.primary}
  }
`

const Button = styled.button<{ variant?: 'primary' | 'secondary' }>`
  padding: 0.75rem 1rem
  border-radius: 8px
  font-weight: 500
  cursor: pointer
  transition: all 0.2s
  display: flex
  align-items: center
  justify-content: center
  gap: 0.5rem
  
  ${props => props.variant === 'primary' ? `
    background: ${props.theme.colors.primary};
    color: white;
    border: 2px solid ${props.theme.colors.primary};
    
    &:hover {
      background: ${props.theme.colors.primaryHover};
      border-color: ${props.theme.colors.primaryHover};
    }
  ` : `
    background: white;
    color: ${props.theme.colors.text.primary};
    border: 2px solid ${props.theme.colors.border};
    
    &:hover {
      border-color: ${props.theme.colors.primary};
    }
  `}
  
  &:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
`

const Divider = styled.div`
  display: flex
  align-items: center
  margin: 1rem 0
  
  &::before,
  &::after {
    content: '';
    flex: 1
    height: 1px
    background: ${props => props.theme.colors.border}
  }
  
  span {
    margin: 0 1rem
    color: ${props => props.theme.colors.text.secondary}
    font-size: 0.9rem
  }
`

const ToggleText = styled.p`
  text-align: center
  margin: 1rem 0 0 0
  color: ${props => props.theme.colors.text.secondary}
  
  button {
    background: none
    border: none
    color: ${props => props.theme.colors.primary}
    cursor: pointer
    font-weight: 500
    text-decoration: underline
  }
`

const ErrorMessage = styled.div`
  background: #fee2e2
  color: #dc2626
  padding: 0.75rem
  border-radius: 6px
  font-size: 0.9rem
  margin-bottom: 1rem
`

export const AuthModal: React.FC<AuthModalProps> = ({
  isOpen,
  onClose,
  initialMode = 'signin'
}) => {
  const [mode, setMode] = useState<'signin' | 'signup'>(initialMode)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [username, setUsername] = useState('')
  const [fullName, setFullName] = useState('')
  const [error, setError] = useState<string | null>(null)
  
  const { signIn, signUp, signInWithProvider, loading } = useAuth()

  if (!isOpen) return null

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)

    try {
      if (mode === 'signin') {
        const { error } = await signIn(email, password)
        if (error) {
          setError(error.message)
        } else {
          onClose()
        }
      } else {
        const { error } = await signUp(email, password, {
          username,
          full_name: fullName
        })
        if (error) {
          setError(error.message)
        } else {
          setError(null)
          // Show success message for signup
          alert('Check your email for the confirmation link!')
          onClose()
        }
      }
    } catch (err) {
      setError('An unexpected error occurred')
    }
  }

  const handleSocialLogin = async (provider: 'google' | 'github') => {
    setError(null)
    const { error } = await signInWithProvider(provider)
    if (error) {
      setError(error.message)
    }
  }

  return (
    <Overlay onClick={onClose}>
      <Modal onClick={(e) => e.stopPropagation()}>
        <CloseButton onClick={onClose}>
          <X size={24} />
        </CloseButton>
        
        <Title>
          {mode === 'signin' ? 'Sign In' : 'Sign Up'}
        </Title>

        {error && <ErrorMessage>{error}</ErrorMessage>}

        <Form onSubmit={handleSubmit}>
          {mode === 'signup' && (
            <>
              <InputGroup>
                <Label htmlFor="fullName">Full Name</Label>
                <Input
                  id="fullName"
                  type="text"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  placeholder="Your full name"
                />
              </InputGroup>
              
              <InputGroup>
                <Label htmlFor="username">Username</Label>
                <Input
                  id="username"
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="Choose a username"
                />
              </InputGroup>
            </>
          )}
          
          <InputGroup>
            <Label htmlFor="email">Email</Label>
            <Input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="your@email.com"
              required
            />
          </InputGroup>
          
          <InputGroup>
            <Label htmlFor="password">Password</Label>
            <Input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              required
              minLength={6}
            />
          </InputGroup>

          <Button type="submit" variant="primary" disabled={loading}>
            {mode === 'signin' ? (
              <>
                <LogIn size={18} />
                {loading ? 'Signing In...' : 'Sign In'}
              </>
            ) : (
              <>
                <UserPlus size={18} />
                {loading ? 'Creating Account...' : 'Sign Up'}
              </>
            )}
          </Button>
        </Form>

        <Divider>
          <span>or</span>
        </Divider>

        <Button
          onClick={() => handleSocialLogin('google')}
          disabled={loading}
        >
          <Mail size={18} />
          Continue with Google
        </Button>

        <Button
          onClick={() => handleSocialLogin('github')}
          disabled={loading}
          style={{ marginTop: '0.5rem' }}
        >
          <Github size={18} />
          Continue with GitHub
        </Button>

        <ToggleText>
          {mode === 'signin' ? (
            <>
              Don't have an account?{' '}
              <button onClick={() => setMode('signup')}>
                Sign up
              </button>
            </>
          ) : (
            <>
              Already have an account?{' '}
              <button onClick={() => setMode('signin')}>
                Sign in
              </button>
            </>
          )}
        </ToggleText>
      </Modal>
    </Overlay>
  )
}

export default AuthModal