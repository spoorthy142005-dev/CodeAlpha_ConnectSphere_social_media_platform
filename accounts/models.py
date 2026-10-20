from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.exceptions import ValidationError


def validate_avatar_file(file):
    """Validate uploaded avatar size (<2MB) and valid extensions."""
    max_size = 2 * 1024 * 1024  # 2 MB
    if file.size > max_size:
        raise ValidationError("Profile picture must be under 2MB.")
    
    valid_extensions = ['.jpg', '.jpeg', '.png', '.webp', '.gif']
    import os
    ext = os.path.splitext(file.name)[1].lower()
    if ext not in valid_extensions:
        raise ValidationError("Unsupported file format. Please upload JPG, PNG, GIF, or WebP.")


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    display_name = models.CharField(max_length=60, blank=True, default='')
    bio = models.TextField(max_length=500, blank=True, default='')
    avatar = models.ImageField(upload_to='avatars/%Y/%m/', blank=True, null=True, validators=[validate_avatar_file])
    is_private = models.BooleanField(
        default=False,
        help_text="If private, only approved followers can see full posts."
    )
    low_bandwidth = models.BooleanField(
        default=False,
        help_text="Enable low-bandwidth mode to reduce animations and image preloading."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"{self.user.username}'s Profile"

    def get_display_name(self):
        return self.display_name.strip() if self.display_name.strip() else self.user.username

    @property
    def posts_count(self):
        return self.user.posts.count()

    @property
    def followers_count(self):
        return self.user.follower_set.count()

    @property
    def following_count(self):
        return self.user.following_set.count()


@receiver(post_save, sender=User)
def create_or_save_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)
    else:
        if hasattr(instance, 'profile'):
            instance.profile.save()
        else:
            Profile.objects.create(user=instance)
