import { create } from 'zustand'

interface User {
  id: string
  email: string
  username: string
  first_name?: string
  last_name?: string
  is_active: boolean
  is_superadmin: boolean
}

interface Organization {
  id: string
  name: string
  slug: string
  description?: string
}

interface OrganizationMembership {
  organization: Organization
  role: string
  joined_at?: string
}

interface AuthState {
  user: User | null
  accessToken: string | null
  refreshToken: string | null
  isAuthenticated: boolean
  currentOrganization: Organization | null
  organizations: OrganizationMembership[]
  setAuth: (user: User, accessToken: string, refreshToken: string) => void
  clearAuth: () => void
  updateUser: (user: User) => void
  setOrganizations: (organizations: OrganizationMembership[]) => void
  setCurrentOrganization: (organization: Organization) => void
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  accessToken: localStorage.getItem('access_token'),
  refreshToken: localStorage.getItem('refresh_token'),
  isAuthenticated: !!localStorage.getItem('access_token'),
  currentOrganization: localStorage.getItem('current_organization')
    ? JSON.parse(localStorage.getItem('current_organization')!)
    : null,
  organizations: [],

  setAuth: (user, accessToken, refreshToken) => {
    localStorage.setItem('access_token', accessToken)
    localStorage.setItem('refresh_token', refreshToken)
    set({
      user,
      accessToken,
      refreshToken,
      isAuthenticated: true,
    })
  },

  clearAuth: () => {
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    localStorage.removeItem('current_organization')
    set({
      user: null,
      accessToken: null,
      refreshToken: null,
      isAuthenticated: false,
      currentOrganization: null,
      organizations: [],
    })
  },

  updateUser: (user) => {
    set({ user })
  },

  setOrganizations: (organizations) => {
    set({ organizations })
    // Auto-select first organization if none selected
    const currentOrg = localStorage.getItem('current_organization')
    if (!currentOrg && organizations.length > 0) {
      const firstOrg = organizations[0].organization
      localStorage.setItem('current_organization', JSON.stringify(firstOrg))
      set({ currentOrganization: firstOrg })
    }
  },

  setCurrentOrganization: (organization) => {
    localStorage.setItem('current_organization', JSON.stringify(organization))
    set({ currentOrganization: organization })
  },
}))
