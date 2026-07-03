import { create } from 'zustand'

export const useAuthStore = create((set) => ({
  user: null,
  oauthEnabled: false,
  checked: false,
  setUser: (user) => set({ user }),
  setAuthStatus: (oauthEnabled, user) => set({ oauthEnabled, user, checked: true }),
  clearAuth: () => set({ user: null }),
}))
