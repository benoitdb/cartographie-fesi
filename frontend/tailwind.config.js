/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,jsx}",
  ],
  darkMode: 'media',
  theme: {
    fontFamily: {
      'sans': ['IBM Plex Sans', 'system-ui', 'sans-serif'],
      'body': ['Lato', 'system-ui', 'sans-serif'],
    },
    extend: {
      colors: {
        // Couleurs primaires - Look moderne
        primary: '#0066cc',      // Bleu EU
        secondary: '#ff6600',    // Orange régions
        accent: '#ff8533',       // Orange clair

        // Couleurs régions (exemples - à personnaliser)
        'region-auvergne': '#1f77b4',
        'region-bourgogne': '#ff7f0e',
        'region-bretagne': '#2ca02c',
        'region-centre': '#d62728',
        'region-champagne': '#9467bd',
        'region-corse': '#8c564b',
        'region-grand-est': '#e377c2',
        'region-hauts-de-france': '#7f7f7f',
        'region-ile-de-france': '#bcbd22',
        'region-normandie': '#17becf',
        'region-nouvelle-aquitaine': '#1f77b4',
        'region-occitanie': '#ff7f0e',
        'region-pays-de-loire': '#2ca02c',
        'region-paca': '#d62728',
        'region-rhone-alpes': '#9467bd',
        'region-reunion': '#8c564b',

        // Grays modernes
        gray: {
          50: '#f8fafc',
          100: '#f1f5f9',
          200: '#e2e8f0',
          300: '#cbd5e1',
          400: '#94a3b8',
          500: '#64748b',
          600: '#475569',
          700: '#334155',
          800: '#1e293b',
          900: '#0f172a',
          950: '#020617',
        },

        // Statuts
        success: '#10b981',
        warning: '#f59e0b',
        error: '#ef4444',
        info: '#3b82f6',
      },
      spacing: {
        '128': '32rem',
        '144': '36rem',
      },
      borderRadius: {
        'lg': '0.5rem',
        'xl': '0.75rem',
        '2xl': '1rem',
      },
      boxShadow: {
        'sm': '0 1px 2px 0 rgba(0, 0, 0, 0.05)',
        'md': '0 4px 6px -1px rgba(0, 0, 0, 0.1)',
        'lg': '0 10px 15px -3px rgba(0, 0, 0, 0.1)',
        'xl': '0 20px 25px -5px rgba(0, 0, 0, 0.1)',
      },
    },
  },
  plugins: [],
}
