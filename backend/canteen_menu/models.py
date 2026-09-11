from django.db import models
import urllib.parse

class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name_plural = "Categories"

    def __str__(self):
        return self.name

class MenuItem(models.Model):
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='items')
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=8, decimal_places=2)
    image = models.ImageField(upload_to='menu_items/', blank=True, null=True)
    image_url = models.URLField(max_length=500, blank=True, null=True, help_text="URL galing sa internet")
    is_available = models.BooleanField(default=True)
    stock = models.PositiveIntegerField(default=50, help_text="Available stock count")
    estimated_prep_time = models.PositiveIntegerField(default=15, help_text="Prep time in minutes")
    ingredient_summary_notes = models.TextField(blank=True, help_text="e.g., 1 chicken quarter per portion")

    def __str__(self):
        return f"{self.name} - ₱{self.price}"

    @property
    def get_image_src(self):
        if self.image_url and self.image_url.strip():
            return self.image_url
        if self.image:
            try:
                return self.image.url
            except ValueError:
                pass
        name_lower = self.name.lower()
        cat_name = str(self.category).lower() if self.category else ''
        if 'coke' in name_lower or 'sprite' in name_lower or 'royal' in name_lower or 'pepsi' in name_lower or 'drink' in name_lower or 'beverage' in name_lower or 'coffee' in name_lower or 'energen' in name_lower:
            return "https://images.unsplash.com/photo-1554866585-cd94860890b7?auto=format&fit=crop&w=600&q=80"
        elif 'rice' in name_lower or 'silog' in name_lower or 'adobo' in name_lower or 'sinigang' in name_lower or 'menudo' in name_lower or 'curry' in name_lower or 'tinola' in name_lower or 'chicken' in name_lower or 'pork' in name_lower or 'beef' in name_lower or 'fish' in name_lower or 'ulam' in cat_name:
            return "https://images.unsplash.com/photo-1555396273-367ea4eb4db5?auto=format&fit=crop&w=600&q=80"
        elif 'cookie' in name_lower or 'biscuit' in name_lower or 'crinkle' in name_lower or 'brownie' in name_lower:
            return "https://images.unsplash.com/photo-1558961363-fa8fdf82db35?auto=format&fit=crop&w=600&q=80"
        elif 'turon' in name_lower or 'bread' in name_lower or 'pastry' in name_lower or 'meryenda' in name_lower or 'snack' in name_lower or 'puto' in name_lower or 'suman' in name_lower:
            return "https://images.unsplash.com/photo-1509440159596-0249088772ff?auto=format&fit=crop&w=600&q=80"
        return "https://images.unsplash.com/photo-1546069901-ba9599a7e63c?auto=format&fit=crop&w=600&q=80"