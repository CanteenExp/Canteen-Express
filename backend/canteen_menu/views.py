from django.shortcuts import render

def menu_list_view(request):
    return render(request, 'canteen_menu/menu_list.html')