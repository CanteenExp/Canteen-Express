const { glob } = require('./tw');

module.exports = {
  content: [
    glob('canteen_menu/templates/canteen_menu/menu_form.html'),
  ],
  theme: {
    extend: {
      colors: {
        'brand-dark': '#0d0d12',
        'brand-card': '#16161e',
        'brand-orange': '#f97316',
        'brand-slate': '#94a3b8',
      },
    },
  },
  plugins: [],
};