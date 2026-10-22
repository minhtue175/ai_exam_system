from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    """Custom User Model"""
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=15, blank=True, null=True)
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    streak_count = models.IntegerField(default=0, help_text="Chuỗi ngày ôn tập liên tục (Daily Streak)")
    last_active_date = models.DateField(null=True, blank=True, help_text="Ngày hoạt động ôn thi gần nhất")
    
    class Meta:
        db_table = 'users'
        verbose_name = 'User'
        verbose_name_plural = 'Users'
    
    def __str__(self):
        return self.username

    def record_activity(self):
        """Cập nhật chuỗi ngày học tập liên tục (Study Streak)"""
        from django.utils import timezone
        from datetime import timedelta
        today = timezone.now().date()
        if self.last_active_date == today:
            return self.streak_count
        elif self.last_active_date == today - timedelta(days=1):
            self.streak_count += 1
        else:
            self.streak_count = 1
        self.last_active_date = today
        self.save(update_fields=['streak_count', 'last_active_date'])
        return self.streak_count

class UserProfile(models.Model):
    """User Profile Extended Information"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    bio = models.TextField(blank=True, null=True)
    date_of_birth = models.DateField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'user_profiles'
    
    def __str__(self):
        return f"Profile of {self.user.username}"