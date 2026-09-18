const { glob } = require('./tw');

module.exports = {
  content: [
    glob('accounts/templates/accounts/faculty_email.html'),
    glob('accounts/templates/accounts/faculty_phone.html'),
    glob('accounts/templates/accounts/get_started.html'),
    glob('canteen_menu/templates/canteen_menu/category_confirm_delete.html'),
    glob('canteen_menu/templates/canteen_menu/category_form.html'),
    glob('canteen_menu/templates/canteen_menu/counter_board.html'),
    glob('canteen_menu/templates/canteen_menu/counter_pos.html'),
    glob('canteen_menu/templates/canteen_menu/menu_confirm_delete.html'),
    glob('canteen_menu/templates/canteen_menu/menu_list.html'),
    glob('customer_portal/templates/staff_portal/menu_list.html'),
  ],
  theme: {},
  plugins: [],
};