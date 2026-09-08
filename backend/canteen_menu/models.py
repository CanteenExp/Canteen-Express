from django.db import models

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
        import os
        import urllib.parse
        if self.image:
            try:
                if self.image.storage.exists(self.image.name):
                    return self.image.url
                base_name = os.path.basename(self.image.name)
                alt_name = os.path.join('menu_items', base_name.replace('_', ' '))
                if self.image.storage.exists(alt_name):
                    return self.image.storage.url(alt_name)
                alt_name2 = os.path.join('menu_items', base_name.replace(' ', '_'))
                if self.image.storage.exists(alt_name2):
                    return self.image.storage.url(alt_name2)
            except Exception:
                pass
        if self.image_url:
            return self.image_url
        try:
            encoded_query = urllib.parse.quote(f"{self.name},food,dish,filipino food")
            return f"https://loremflickr.com/600/400/{encoded_query}"
        except Exception:
            return "https://images.unsplash.com/photo-1546069901-ba9599a7e63c?auto=format&fit=crop&w=600&q=80"