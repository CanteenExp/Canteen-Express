const { glob } = require('./tw');

module.exports = {
  content: [
    glob('accounts/templates/accounts/delivery_login.html'),
  ],
  theme: {
    extend: {
      fontFamily: {
        poppins: ['Poppins', 'sans-serif'],
        jakarta: ['Plus Jakarta Sans', 'sans-serif'],
      },
      colors: {
        brand: {
          orange: '#FF6117',
          dark: '#08080b',
          card: '#121216',
          slate: '#8E8E93',
        },
      },
      boxShadow: {
        'glow-orange': '0 0 25px rgba(255,97,23,0.35)',
        'glass': '0 8px 32px rgba(0,0,0,0.4)',
      },
    },
  },
  plugins: [],
};