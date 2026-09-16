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
        // Obsidian Command palette
        bg: {
          base: '#050505',
          sidebar: '#0B0B0D',
          surface: '#111113',
          elevated: '#1B1B1F',
          input: '#141416'
        },
        border: {
          subtle: '#1E1E22',
          default: '#2A2A2D',
          strong: '#3A3A3E'
        },
        text: {
          primary: '#F2F2F2',
          secondary: '#85858C',
          muted: '#55555D',
          inverted: '#050505',
          code: '#A8C5DA'
        },
        crimson: {
          DEFAULT: '#D63C4B',
          surface: '#321419'
        },
        amber: {
          DEFAULT: '#F0A23A',
          surface: '#2B2010'
        },
        emerald: {
          DEFAULT: '#46B887',
          surface: '#0E2420'
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
        'card': '6px',
        'badge': '4px',
        'button': '5px',
        'modal': '8px'
      }
    },
  },
  plugins: [],
}