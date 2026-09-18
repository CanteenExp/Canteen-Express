const { glob } = require('./tw');

module.exports = {
  content: [
    glob('customer_portal/templates/customer_portal/kiosk_auth.html'),
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          orange: '#FF6117',
          dark: '#1E1E1E',
          card: '#292929',
          light: '#EAEAEA',
          slate: '#8E8E93',
        },
      },
    },
  },
  plugins: [],
};