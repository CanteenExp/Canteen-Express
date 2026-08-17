from django.shortcuts import render, redirect

def kiosk_welcome(request):
    # Added 'customer_portal/' prefix
    return render(request, 'customer_portal/kiosk_welcome.html') 

def kiosk_home(request):
    # Added 'customer_portal/' prefix
    return render(request, 'customer_portal/kiosk_home.html')

def kiosk_auth(request):
    return render(request, 'customer_portal/kiosk_auth.html')

def kiosk_menu(request):
    # Fetch role from URL parameter (e.g. ?role=faculty) or default to 'student'
    role = request.GET.get('role', 'student')
    
    context = {
        'role': role,
    }
    return render(request, 'customer_portal/kiosk_menu.html', context)

# 1. Faculty Login View
def faculty_login(request):
    if request.method == 'POST':
        # TODO: Authenticate faculty member here
        
        # Pass role='faculty' when redirecting to kiosk_menu
        return redirect('/kiosk/menu/?role=faculty') 
        
    return render(request, 'customer_portal/faculty_login.html')

# 2. Faculty Signup View
def faculty_signup(request):
    if request.method == 'POST':
        # TODO: Process signup details and generate/send OTP email
        return redirect('faculty_otp') # Redirect to OTP page
    return render(request, 'customer_portal/faculty_signup.html')

# 3. Faculty OTP Verification View
def faculty_otp(request):
    if request.method == 'POST':
        # TODO: Validate the 6-digit OTP code
        return redirect('faculty_login') # Redirect to login or straight to menu
    return render(request, 'customer_portal/faculty_otp.html')