from django.db import models

class MenuItem(models.Model):
    CATEGORY_CHOICES = [
        ('biscuits', 'Biscuits'),
        ('rice', 'Rice Meals'),
        ('beverages', 'Beverages'),
        ('meryenda', 'Meryenda'),
        ('dietary', 'Dietary Plans'),
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
        if self.image:
            return self.image.url
        elif self.image_url:
            return self.image_url
        return "https://images.unsplash.com/photo-1546069901-ba9599a7e63c?auto=format&fit=crop&w=600&q=80"


class Order(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('preparing', 'Preparing'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    order_number = models.CharField(max_length=20, unique=True)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Order {self.order_number} - ₱{self.total_amount}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    item_name = models.CharField(max_length=150)
    price = models.DecimalField(max_digits=8, decimal_places=2)
    quantity = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f"{self.quantity}x {self.item_name}"