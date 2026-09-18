const { glob } = require('./tw');

module.exports = {
  content: [
    glob('customer_portal/templates/customer_portal/kiosk_home.html'),
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          DEFAULT: '#1BAC4B',
          dark: '#158C3C',
          light: '#E8F7ED',
        },
      },
    },
  },
  plugins: [],
};