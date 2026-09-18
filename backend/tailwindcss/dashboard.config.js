const { glob } = require('./tw');

module.exports = {
  content: [
    glob('accounts/templates/accounts/dashboard.html'),
    glob('customer_portal/templates/customer_portal/kiosk_menu.html'),
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          orange: '#FF6117',
          dark: '#121212',
          card: '#242424',
          light: '#EAEAEA',
          amber: '#FFB800',
          peach: '#FFECD9',
          slate: '#8E8E93',
        },
      },
    },
  },
  plugins: [],
};