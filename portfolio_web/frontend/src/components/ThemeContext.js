/**
 * Theme Context and Hook
 * Manages dark/light theme state across the application
 */
import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export const useThemeStore = create(
  persist(
    (set) => ({
      theme: 'dark', // 'dark' or 'light'
      toggleTheme: () => set((state) => ({ 
        theme: state.theme === 'dark' ? 'light' : 'dark' 
      })),
      setTheme: (theme) => set({ theme })
    }),
    {
      name: 'portfolio-theme-storage',
    }
  )
);

// Apply theme to document
export const applyTheme = (theme) => {
  document.documentElement.setAttribute('data-theme', theme);
  
  // Update meta theme-color for mobile browsers
  const metaThemeColor = document.querySelector('meta[name="theme-color"]');
  if (metaThemeColor) {
    metaThemeColor.setAttribute('content', theme === 'dark' ? '#050d1a' : '#ffffff');
  }
};

export default useThemeStore;
