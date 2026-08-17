from django import forms
from .models import MenuItem

class MenuItemForm(forms.ModelForm):
    class Meta:
        model = MenuItem
        fields = ['name', 'category', 'price', 'description', 'badge', 'image', 'image_url', 'is_siomai', 'is_available']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'w-full bg-zinc-800 border border-white/10 rounded-xl p-3 text-white', 'placeholder': 'Hal. Chicken Adobo'}),
            'category': forms.Select(attrs={'class': 'w-full bg-zinc-800 border border-white/10 rounded-xl p-3 text-white'}),
            'price': forms.NumberInput(attrs={'class': 'w-full bg-zinc-800 border border-white/10 rounded-xl p-3 text-white', 'step': '0.01', 'placeholder': '0.00'}),
            'description': forms.Textarea(attrs={'class': 'w-full bg-zinc-800 border border-white/10 rounded-xl p-3 text-white', 'rows': 3, 'placeholder': 'Maikling deskripsyon...'}),
            'badge': forms.TextInput(attrs={'class': 'w-full bg-zinc-800 border border-white/10 rounded-xl p-3 text-white', 'placeholder': 'Hal. Popular, Bestseller'}),
            'image_url': forms.URLInput(attrs={'class': 'w-full bg-zinc-800 border border-white/10 rounded-xl p-3 text-white', 'placeholder': 'https://...'}),
            'is_siomai': forms.CheckboxInput(attrs={'class': 'w-5 h-5 accent-orange-500 rounded'}),
            'is_available': forms.CheckboxInput(attrs={'class': 'w-5 h-5 accent-orange-500 rounded'}),
        }