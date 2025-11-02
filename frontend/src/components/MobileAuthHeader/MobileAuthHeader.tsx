import { Github, LogIn, LogOut, User } from "lucide-react"
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

const SocialButtons = styled.div`
    display: flex;
    flex-direction: column;
    gap: ${({ theme }) => theme.spacing[3]};
    margin-top: ${({ theme }) => theme.spacing[4]};
`

const SocialButton = styled.button`
    width: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: ${({ theme }) => theme.spacing[2]};
    padding: ${({ theme }) => theme.spacing[3]};
    border: 1px solid ${({ theme }) => theme.colors.borderLight};
    border-radius: ${({ theme }) => theme.borderRadius.md};
    font-size: ${({ theme }) => theme.typography.sizes.base};
    font-weight: ${({ theme }) => theme.typography.weights.medium};
    cursor: pointer;
    transition: all ${({ theme }) => theme.transitions.fast};
    background: ${({ theme }) => theme.colors.background};

    &:hover {
        background: ${({ theme }) => theme.colors.gray100};
        transform: translateY(-1px);
        box-shadow: ${({ theme }) => theme.shadows.md};
    }

    &:active {
        transform: translateY(0);
    }

    &:disabled {
        opacity: 0.5;
        cursor: not-allowed;
    }

    svg {
        width: 20px;
        height: 20px;
    }
`

const GoogleButton = styled(SocialButton)`
    background: white;
    color: #4285f4;
    border-color: #dadce0;

    &:hover {
        background: #f8f9fa;
        border-color: #4285f4;
    }
`

const GitHubButton = styled(SocialButton)`
    background: #24292e;
    color: white;
    border-color: #24292e;

    &:hover {
        background: #2f363d;
        border-color: #2f363d;
    }
`

const CancelButton = styled.button`
    width: 100%;
    padding: ${({ theme }) => theme.spacing[3]};
    margin-top: ${({ theme }) => theme.spacing[3]};
    border: 1px solid ${({ theme }) => theme.colors.borderLight};
    border-radius: ${({ theme }) => theme.borderRadius.md};
    font-size: ${({ theme }) => theme.typography.sizes.base};
    font-weight: ${({ theme }) => theme.typography.weights.medium};
    cursor: pointer;
    transition: all ${({ theme }) => theme.transitions.fast};
    background: ${({ theme }) => theme.colors.gray200};
    color: ${({ theme }) => theme.colors.textPrimary};

    &:hover {
        background: ${({ theme }) => theme.colors.gray300};
    }
`

const LoginSubtitle = styled.p`
    margin: 0 0 ${({ theme }) => theme.spacing[4]} 0;
    font-size: ${({ theme }) => theme.typography.sizes.sm};
    color: ${({ theme }) => theme.colors.textSecondary};
    text-align: center;
`

export default function MobileAuthHeader() {
  const { user, signInWithProvider, signOut, loading } = useAuth()
  const [showMenu, setShowMenu] = useState(false)
  const [showLogin, setShowLogin] = useState(false)
  const [isLoading, setIsLoading] = useState<string | null>(null)

  const handleSocialLogin = async (
    provider: "google" | "github" | "apple" | "facebook"
  ) => {
    setIsLoading(provider)
    const { error } = await signInWithProvider(provider)
    if (error) {
      console.error(`Failed to sign in with ${provider}:`, error)
      setIsLoading(null)
      // OAuth will redirect, so we don't need to handle errors here
    }
    // Note: OAuth redirects will handle the flow, so we don't close the modal here
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
            <LoginTitle>Sign In</LoginTitle>
            <LoginSubtitle>Choose a provider to continue</LoginSubtitle>
            <SocialButtons>
              <GoogleButton
                onClick={() => handleSocialLogin("google")}
                disabled={!!isLoading}
              >
                <svg
                  width="20"
                  height="20"
                  viewBox="0 0 24 24"
                  fill="none"
                  xmlns="http://www.w3.org/2000/svg"
                  aria-label="Google"
                  role="img"
                >
                  <path
                    d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                    fill="#4285F4"
                  />
                  <path
                    d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                    fill="#34A853"
                  />
                  <path
                    d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
                    fill="#FBBC05"
                  />
                  <path
                    d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
                    fill="#EA4335"
                  />
                </svg>
                {isLoading === "google"
                  ? "Connecting..."
                  : "Continue with Google"}
              </GoogleButton>
              <GitHubButton
                onClick={() => handleSocialLogin("github")}
                disabled={!!isLoading}
              >
                <Github size={20} />
                {isLoading === "github"
                  ? "Connecting..."
                  : "Continue with GitHub"}
              </GitHubButton>
            </SocialButtons>
            <CancelButton
              onClick={() => {
                setShowLogin(false)
                setIsLoading(null)
              }}
            >
              Cancel
            </CancelButton>
          </LoginCard>
        </LoginModal>
      )}
    </>
  )
}
