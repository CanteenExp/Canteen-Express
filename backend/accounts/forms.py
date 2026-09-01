from django import forms
from django.contrib.auth import get_user_model

User = get_user_model()

class FacultyStaffRegisterForm(forms.ModelForm):
    ROLE_CHOICES = (
        ('FACULTY', 'Faculty'),
        ('STAFF', 'Canteen Staff'),
    )
    
    role = forms.ChoiceField(
        choices=ROLE_CHOICES, 
        widget=forms.Select(attrs={
            'class': 'mt-1 w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-amber-500 focus:outline-none'
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'mt-1 w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-amber-500 focus:outline-none'
        })
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'mt-1 w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-amber-500 focus:outline-none'
        })
    )

    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name', 'role']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'mt-1 w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-amber-500 focus:outline-none'}),
            'email': forms.EmailInput(attrs={'class': 'mt-1 w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-amber-500 focus:outline-none'}),
            'first_name': forms.TextInput(attrs={'class': 'mt-1 w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-amber-500 focus:outline-none'}),
            'last_name': forms.TextInput(attrs={'class': 'mt-1 w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-amber-500 focus:outline-none'}),
        }

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if not email.endswith('@psu.palawan.edu.ph'):
            raise forms.ValidationError("Only institutional emails ending in @psu.palawan.edu.ph can be used for Faculty/Staff registration.")
        return email

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")

        if password and confirm_password and password != confirm_password:
            self.add_error('confirm_password', "Passwords do not match.")
        return cleaned_data