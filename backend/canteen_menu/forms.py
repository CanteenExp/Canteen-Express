from django import forms
from .models import MenuItem

class MenuItemForm(forms.ModelForm):
    class Meta:
        model = MenuItem
        fields = ['name', 'category', 'price', 'description', 'image', 'is_available']
        
        # Pwede mong idagdag sa 'fields' sa itaas ang iba pang fields (badge, image_url, is_siomai) KUNG mayroon ka nito sa Model.

        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'w-full bg-zinc-700/50 border border-white/10 text-white rounded-xl p-3 text-xs focus:outline-none focus:border-orange-500',
                'placeholder': 'hal. Porksilog'
            }),
            'category': forms.Select(attrs={
                'class': 'w-full bg-zinc-700/50 border border-white/10 text-white rounded-xl p-3 text-xs focus:outline-none focus:border-orange-500'
            }),
            'price': forms.NumberInput(attrs={
                'class': 'w-full bg-zinc-700/50 border border-white/10 text-white rounded-xl p-3 text-xs focus:outline-none focus:border-orange-500',
                'step': '0.01',
                'placeholder': '0.00'
            }),
            'description': forms.Textarea(attrs={
                'class': 'w-full bg-zinc-700/50 border border-white/10 text-white rounded-xl p-3 text-xs focus:outline-none focus:border-orange-500',
                'rows': 3,
                'placeholder': 'Maikling deskripsyon ng pagkain...'
            }),
            'image': forms.FileInput(attrs={
                'class': 'w-full bg-zinc-700/50 border border-white/10 text-zinc-400 rounded-xl p-2 text-xs file:mr-4 file:py-1 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-orange-600 file:text-white hover:file:bg-orange-500'
            }),
            'is_available': forms.CheckboxInput(attrs={
                'class': 'w-4 h-4 rounded bg-zinc-700 border-zinc-600 text-orange-600 focus:ring-orange-500'
            }),
        }