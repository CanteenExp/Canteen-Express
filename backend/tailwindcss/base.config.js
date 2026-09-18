const { glob } = require('./tw');

module.exports = {
  content: [
    glob('templates/base.html'),
    glob('accounts/templates/accounts/access_denied.html'),
    glob('canteen_menu/templates/canteen_menu/staff_dashboard.html'),
    glob('templates/admin_dashboard.html'),
    glob('templates/admin_pin_verify.html'),
    glob('templates/kitchen_dashboard.html'),
    glob('templates/staff_dashboard.html'),
    glob('templates/staff_menu_management.html'),
    glob('templates/accounts/login.html'),
    glob('templates/accounts/register.html'),
    glob('templates/accounts/verify_otp.html'),
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          50: '#fff7ed',
          100: '#ffedd5',
          500: '#f97316',
          600: '#ea580c',
          700: '#c2410c',
        },
        dark: {
          800: '#1e293b',
          900: '#0f172a',
        },
      },
    },
  },
  plugins: [],
};