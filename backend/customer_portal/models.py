from django.db import models
from django.conf import settings
import urllib.parse

class MenuItem(models.Model):
    CATEGORY_CHOICES = [
        ('biscuits', 'Biscuits'),
        ('rice', 'Rice Meals'),
        ('beverages', 'Beverages'),
        ('meryenda', 'Meryenda'),
        ('dietary', 'Dietary Plans'),
        ('candies', 'Candies'),
    ]

    name = models.CharField(max_length=120)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='rice')
    price = models.DecimalField(max_digits=8, decimal_places=2)
    description = models.TextField(blank=True, null=True)
    badge = models.CharField(max_length=50, blank=True, null=True, help_text="hal. Popular, Bestseller")
    
    # Suporta sa image file o Image URL
    image = models.ImageField(upload_to='menu_images/', blank=True, null=True)
    image_url = models.URLField(max_length=500, blank=True, null=True, help_text="URL galing sa internet")
    
    is_siomai = models.BooleanField(default=False, verbose_name="Is Siomai Customizer?")
    is_available = models.BooleanField(default=True, verbose_name="Available in Kiosk?")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} - ₱{self.price}"

    @property
    def get_image_src(self):
        if self.image_url and self.image_url.strip():
            return self.image_url
        if self.image:
            try:
                if self.image.storage.exists(self.image.name):
                    return self.image.url
            except Exception:
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


class Order(models.Model):
    STATUS_CHOICES = [
        ('unpaid', 'Unpaid'),
        ('pending', 'Pending (Paid)'),
        ('preparing', 'Preparing'),
        ('ready', 'Ready'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    order_number = models.CharField(max_length=20, unique=True)
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='portal_orders')
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    delivery_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='unpaid')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Order {self.order_number} - ₱{self.total_amount}"

    @property
    def total_payment(self):
        return self.total_amount + self.delivery_fee


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    item_name = models.CharField(max_length=150)
    price = models.DecimalField(max_digits=8, decimal_places=2)
    quantity = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f"{self.quantity}x {self.item_name}"

    @property
    def total_price(self):
        return self.price * self.quantity

    @property
    def product(self):
        class DummyProduct:
            def __init__(self, name):
                self.name = name
        return DummyProduct(self.item_name)
