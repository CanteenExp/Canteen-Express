from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages

@login_required
def update_profile(request):
    if request.method == 'POST':
        request.user.first_name = request.POST.get('first_name', request.user.first_name)
        request.user.last_name = request.POST.get('last_name', request.user.last_name)
        request.user.phone = request.POST.get('phone', request.user.phone)
        request.user.department = request.POST.get('department', request.user.department)
        request.user.save()
        messages.success(request, 'Profile updated successfully!')
        return redirect('accounts:dashboard')
    return redirect('accounts:dashboard')
