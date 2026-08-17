from django.shortcuts import render, redirect

def landing_view(request):
    return render(request, 'accounts/landing.html')

# STEP 1: Faculty Location Check
def faculty_location_view(request):
    if request.method == 'POST':
        lat = request.POST.get('latitude')
        lng = request.POST.get('longitude')
        
        # I-save sa session ang location ng faculty
        request.session['faculty_lat'] = lat
        request.session['faculty_lng'] = lng
        
        # Kapag nakuha na ang location, lipat sa Step 2: Phone
        return redirect('accounts:faculty_phone')
        
    return render(request, 'accounts/faculty_location.html')

# STEP 2: Faculty Phone Verification
def faculty_phone_view(request):
    if request.method == 'POST':
        phone = request.POST.get('phone_number')
        
        # I-save ang phone number sa session at magpadala ng OTP
        request.session['faculty_phone'] = phone
        
        # Proceed sa Step 3: Email Verification / OTP Check
        return redirect('accounts:faculty_email')
        
    return render(request, 'accounts/faculty_phone.html')