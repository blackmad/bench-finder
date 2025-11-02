import { LogIn, LogOut, User } from "lucide-react"
import { useState } from "react"
import styled from "styled-components"
import { useAuth } from "../../contexts/AuthContext"

const AuthContainer = styled.div`
    position: absolute;
    top: ${({ theme }) => theme.spacing[4]};
    right: ${({ theme }) => theme.spacing[4]};
    z-index: 1002;
    display: flex;
    align-items: center;
    gap: ${({ theme }) => theme.spacing[2]};
`

const AuthButton = styled.button`
    display: flex;
    align-items: center;
    gap: ${({ theme }) => theme.spacing[2]};
    padding: ${({ theme }) => theme.spacing[2]} ${({ theme }) => theme.spacing[3]};
    background: ${({ theme }) => theme.colors.background};
    border: 1px solid ${({ theme }) => theme.colors.borderLight};
    border-radius: ${({ theme }) => theme.borderRadius.lg};
    color: ${({ theme }) => theme.colors.textPrimary};
    font-size: ${({ theme }) => theme.typography.sizes.sm};
    font-weight: ${({ theme }) => theme.typography.weights.medium};
    cursor: pointer;
    box-shadow: ${({ theme }) => theme.shadows.md};
    transition: all ${({ theme }) => theme.transitions.fast};
    backdrop-filter: blur(8px);

    &:hover {
        background: ${({ theme }) => theme.colors.gray100};
        transform: translateY(-1px);
        box-shadow: ${({ theme }) => theme.shadows.lg};
    }

    &:active {
        transform: translateY(0);
    }

    svg {
        width: 16px;
        height: 16px;
    }
`

const UserMenu = styled.div`
    position: absolute;
    top: calc(100% + ${({ theme }) => theme.spacing[2]});
    right: 0;
    background: ${({ theme }) => theme.colors.background};
    border: 1px solid ${({ theme }) => theme.colors.borderLight};
    border-radius: ${({ theme }) => theme.borderRadius.lg};
    box-shadow: ${({ theme }) => theme.shadows.xl};
    padding: ${({ theme }) => theme.spacing[2]};
    min-width: 200px;
    backdrop-filter: blur(8px);
`

const UserInfo = styled.div`
    padding: ${({ theme }) => theme.spacing[2]} ${({ theme }) => theme.spacing[3]};
    border-bottom: 1px solid ${({ theme }) => theme.colors.borderLight};
    margin-bottom: ${({ theme }) => theme.spacing[2]};
`

const UserEmail = styled.div`
    font-size: ${({ theme }) => theme.typography.sizes.sm};
    color: ${({ theme }) => theme.colors.textPrimary};
    font-weight: ${({ theme }) => theme.typography.weights.medium};
    word-break: break-all;
`

const MenuButton = styled.button`
    width: 100%;
    display: flex;
    align-items: center;
    gap: ${({ theme }) => theme.spacing[2]};
    padding: ${({ theme }) => theme.spacing[2]} ${({ theme }) => theme.spacing[3]};
    background: none;
    border: none;
    border-radius: ${({ theme }) => theme.borderRadius.md};
    color: ${({ theme }) => theme.colors.textPrimary};
    font-size: ${({ theme }) => theme.typography.sizes.sm};
    cursor: pointer;
    transition: background ${({ theme }) => theme.transitions.fast};

    &:hover {
        background: ${({ theme }) => theme.colors.gray100};
    }

    svg {
        width: 16px;
        height: 16px;
    }
`

const LoginModal = styled.div`
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.7);
    backdrop-filter: blur(4px);
    z-index: 1003;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: ${({ theme }) => theme.spacing[4]};
`

const LoginCard = styled.div`
    background: ${({ theme }) => theme.colors.background};
    border-radius: ${({ theme }) => theme.borderRadius.xl};
    padding: ${({ theme }) => theme.spacing[6]};
    max-width: 400px;
    width: 100%;
    box-shadow: ${({ theme }) => theme.shadows.xl};
`

const LoginTitle = styled.h2`
    margin: 0 0 ${({ theme }) => theme.spacing[4]} 0;
    font-size: ${({ theme }) => theme.typography.sizes.xl};
    font-weight: ${({ theme }) => theme.typography.weights.semibold};
    color: ${({ theme }) => theme.colors.textPrimary};
`

const Input = styled.input`
    width: 100%;
    padding: ${({ theme }) => theme.spacing[3]};
    border: 1px solid ${({ theme }) => theme.colors.borderLight};
    border-radius: ${({ theme }) => theme.borderRadius.md};
    font-size: ${({ theme }) => theme.typography.sizes.base};
    margin-bottom: ${({ theme }) => theme.spacing[3]};
    background: ${({ theme }) => theme.colors.backgroundSecondary};
    color: ${({ theme }) => theme.colors.textPrimary};

    &:focus {
        outline: none;
        border-color: ${({ theme }) => theme.colors.primary};
    }
`

const ButtonGroup = styled.div`
    display: flex;
    gap: ${({ theme }) => theme.spacing[2]};
    margin-top: ${({ theme }) => theme.spacing[4]};
`

const Button = styled.button`
    flex: 1;
    padding: ${({ theme }) => theme.spacing[3]};
    border: none;
    border-radius: ${({ theme }) => theme.borderRadius.md};
    font-size: ${({ theme }) => theme.typography.sizes.base};
    font-weight: ${({ theme }) => theme.typography.weights.medium};
    cursor: pointer;
    transition: all ${({ theme }) => theme.transitions.fast};

    &:disabled {
        opacity: 0.5;
        cursor: not-allowed;
    }
`

const PrimaryButton = styled(Button)`
    background: ${({ theme }) => theme.colors.primary};
    color: white;

    &:hover:not(:disabled) {
        background: ${({ theme }) => theme.colors.primaryDark};
    }
`

const SecondaryButton = styled(Button)`
    background: ${({ theme }) => theme.colors.gray200};
    color: ${({ theme }) => theme.colors.textPrimary};

    &:hover:not(:disabled) {
        background: ${({ theme }) => theme.colors.gray300};
    }
`

const ErrorText = styled.div`
    color: ${({ theme }) => theme.colors.error};
    font-size: ${({ theme }) => theme.typography.sizes.sm};
    margin-top: ${({ theme }) => theme.spacing[2]};
`

export default function MobileAuthHeader() {
  const { user, signIn, signUp, signOut, loading } = useAuth()
  const [showMenu, setShowMenu] = useState(false)
  const [showLogin, setShowLogin] = useState(false)
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [isSignUp, setIsSignUp] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(false)

  const handleSignIn = async () => {
    setError(null)
    setIsLoading(true)
    const { error: signInError } = await signIn(email, password)
    setIsLoading(false)
    if (signInError) {
      setError(signInError.message || "Failed to sign in")
    } else {
      setShowLogin(false)
      setEmail("")
      setPassword("")
      setError(null)
    }
  }

  const handleSignUp = async () => {
    setError(null)
    setIsLoading(true)
    const { error: signUpError } = await signUp(email, password)
    setIsLoading(false)
    if (signUpError) {
      setError(signUpError.message || "Failed to sign up")
    } else {
      setError(null)
      // After signup, usually need to verify email, so show message
      setError("Please check your email to verify your account")
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (isSignUp) {
      await handleSignUp()
    } else {
      await handleSignIn()
    }
  }

  const handleSignOut = async () => {
    await signOut()
    setShowMenu(false)
  }

  if (loading) {
    return null
  }

  return (
    <>
      <AuthContainer>
        {user ? (
          <>
            <AuthButton onClick={() => setShowMenu(!showMenu)}>
              <User size={16} />
              <span>{user.email?.split("@")[0]}</span>
            </AuthButton>
            {showMenu && (
              <UserMenu>
                <UserInfo>
                  <UserEmail>{user.email}</UserEmail>
                </UserInfo>
                <MenuButton onClick={handleSignOut}>
                  <LogOut size={16} />
                  Sign Out
                </MenuButton>
              </UserMenu>
            )}
          </>
        ) : (
          <AuthButton onClick={() => setShowLogin(true)}>
            <LogIn size={16} />
            <span>Login</span>
          </AuthButton>
        )}
      </AuthContainer>

      {showLogin && (
        <LoginModal onClick={() => setShowLogin(false)}>
          <LoginCard onClick={(e) => e.stopPropagation()}>
            <LoginTitle>{isSignUp ? "Sign Up" : "Sign In"}</LoginTitle>
            <form onSubmit={handleSubmit}>
              <Input
                type="email"
                placeholder="Email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoComplete="email"
              />
              <Input
                type="password"
                placeholder="Password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                autoComplete={isSignUp ? "new-password" : "current-password"}
                minLength={6}
              />
              {error && <ErrorText>{error}</ErrorText>}
              <ButtonGroup>
                <SecondaryButton
                  type="button"
                  onClick={() => {
                    setIsSignUp(!isSignUp)
                    setError(null)
                  }}
                >
                  {isSignUp ? "Sign In Instead" : "Sign Up Instead"}
                </SecondaryButton>
                <PrimaryButton type="submit" disabled={isLoading}>
                  {isLoading ? "Loading..." : isSignUp ? "Sign Up" : "Sign In"}
                </PrimaryButton>
              </ButtonGroup>
              <SecondaryButton
                type="button"
                onClick={() => {
                  setShowLogin(false)
                  setError(null)
                  setEmail("")
                  setPassword("")
                }}
                style={{ marginTop: "8px", width: "100%" }}
              >
                Cancel
              </SecondaryButton>
            </form>
          </LoginCard>
        </LoginModal>
      )}
    </>
  )
}
