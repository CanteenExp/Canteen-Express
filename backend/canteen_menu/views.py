# canteen_menu/views.py
from django.http import HttpResponse

def menu_list(request):
    return HttpResponse("Canteen Menu List")