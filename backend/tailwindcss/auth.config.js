const { glob } = require('./tw');

module.exports = {
  content: [
    glob('accounts/templates/accounts/faculty_auth.html'),
    glob('accounts/templates/accounts/faculty_location.html'),
    glob('accounts/templates/accounts/landing.html'),
    glob('accounts/templates/accounts/staff_login.html'),
    glob('customer_portal/templates/customer_portal/kiosk_welcome.html'),
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
          dark: '#0A0A0C',
          card: '#141416',
          slate: '#8E8E93',
          blue: '#3B82F6',
        },
      },
    },
  },
  plugins: [],
};