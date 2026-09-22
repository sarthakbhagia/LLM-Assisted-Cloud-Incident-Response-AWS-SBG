/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        'sans': ['Inter', 'system-ui', 'sans-serif'],
        'mono': ['JetBrains Mono', 'Fira Code', 'monospace']
      },
      colors: {
        // Light & Premium palette (approved design).
        // Token names kept from the previous dark theme so existing
        // utility classes across all pages restyle automatically.
        bg: {
          base: '#F5F7FB',      // page background
          sidebar: '#FFFFFF',
          surface: '#FFFFFF',   // cards
          elevated: '#FAFBFE',  // hover / inset panels
          input: '#FFFFFF'
        },
        border: {
          subtle: '#EDF0F6',
          default: '#E7ECF3',
          strong: '#D9E1EB'
        },
        text: {
          primary: '#0B1220',   // ink
          secondary: '#51607A', // body
          muted: '#77839A',
          inverted: '#FFFFFF',
          code: '#475569'
        },
        // Solid dark ink used for primary buttons / brand mark
        ink: '#0B1220',
        crimson: {
          DEFAULT: '#E11D48',   // danger only (per design spec)
          surface: '#FDEEF2'
        },
        amber: {
          DEFAULT: '#D97706',
          surface: '#FDF3E3'
        },
        emerald: {
          DEFAULT: '#0C9B6C',
          surface: '#E8F7F1'
        },
        indigo: {
          DEFAULT: '#6366F1',   // active / focus accent
          surface: '#EEF0FE'
        },
        violet: {
          DEFAULT: '#7C3AED',
          surface: '#F1EBFD'
        }
      },
      spacing: {
        '1': '4px',
        '2': '8px',
        '3': '12px',
        '4': '16px',
        '5': '20px',
        '6': '24px',
        '8': '32px',
        '10': '40px',
        '12': '48px'
      },
      borderRadius: {
        'card': '14px',
        'badge': '999px',
        'button': '10px',
        'modal': '16px'
      },
      boxShadow: {
        'card': '0 1px 2px rgba(15, 23, 42, 0.05)',
        'lift': '0 10px 30px -12px rgba(15, 23, 42, 0.16)',
        'drawer': '0 24px 70px -24px rgba(15, 23, 42, 0.35)'
      }
    },
  },
  plugins: [],
}
