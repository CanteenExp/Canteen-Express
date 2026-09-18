const { glob } = require('./tw');

module.exports = {
  content: [
    glob('templates/delivery_dashboard.html'),
    glob('templates/delivery_history.html'),
    glob('templates/delivery_tracking.html'),
    glob('templates/partials/pending_delivery_cards.html'),
  ],
  theme: {
    extend: {
      colors: {
        rider: {
          orange: '#FF6117',
          dark: '#08080b',
          card: '#121216',
          border: '#26262c',
        },
      },
      boxShadow: {
        'glow-orange': '0 0 25px rgba(255,97,23,0.35)',
        'glow-green': '0 0 25px rgba(34,197,94,0.35)',
        'glass': '0 8px 32px rgba(0,0,0,0.4)',
      },
    },
  },
  plugins: [],
};