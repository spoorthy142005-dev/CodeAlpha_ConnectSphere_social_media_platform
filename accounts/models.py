from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.exceptions import ValidationError


def validate_avatar_file(file):
    """Validate uploaded avatar size (<2MB), valid extensions, and binary image validity."""
    max_size = 2 * 1024 * 1024  # 2 MB
    if file.size > max_size:
        raise ValidationError("Profile picture must be under 2MB.")
    
    valid_extensions = ['.jpg', '.jpeg', '.png', '.webp', '.gif']
    import os
    ext = os.path.splitext(file.name)[1].lower()
    if ext not in valid_extensions:
        raise ValidationError("Unsupported file format. Please upload JPG, PNG, GIF, or WebP.")

    # Deep verification: ensure file contains real image data
    try:
        from PIL import Image
        img = Image.open(file)
        img.verify()
        if hasattr(file, 'seek'):
            file.seek(0)
    except Exception:
        raise ValidationError("The uploaded file is not a valid or readable image.")



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
    default_feed_mode = models.CharField(
        max_length=20,
        choices=[('following', 'Following'), ('discover', 'Discover')],
        default='following',
        blank=True,
        help_text="Default feed mode when accessing ConnectSphere."
    )
    muted_topics = models.JSONField(
        default=list,
        blank=True,
        help_text="Topics the user marked with 'Less like this' to reduce in Discover feed."
    )
    default_post_audience = models.CharField(
        max_length=20,
        choices=[('public', 'Public'), ('followers', 'Followers Only')],
        default='public',
        blank=True,
        help_text="Default audience when publishing new posts."
    )
    notify_follows = models.BooleanField(default=True, help_text="Receive notifications when someone follows you.")
    notify_likes = models.BooleanField(default=True, help_text="Receive notifications when someone likes your post.")
    notify_comments = models.BooleanField(default=True, help_text="Receive notifications when someone comments on your post.")
    notify_communities = models.BooleanField(default=True, help_text="Receive notifications for community activity.")
    notifications_paused = models.BooleanField(default=False, help_text="Temporarily pause all notifications.")
    quiet_hours_enabled = models.BooleanField(default=False, help_text="Mute notifications during scheduled quiet hours.")
    quiet_hours_start = models.TimeField(null=True, blank=True, help_text="Quiet hours start time (e.g. 22:00).")
    quiet_hours_end = models.TimeField(null=True, blank=True, help_text="Quiet hours end time (e.g. 08:00).")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def is_in_quiet_hours(self):
        if not self.quiet_hours_enabled or not self.quiet_hours_start or not self.quiet_hours_end:
            return False
        from django.utils import timezone
        now_time = timezone.localtime().time()
        if self.quiet_hours_start <= self.quiet_hours_end:
            return self.quiet_hours_start <= now_time <= self.quiet_hours_end
        else:
            return now_time >= self.quiet_hours_start or now_time <= self.quiet_hours_end

    def should_receive_notification(self, event_type):
        if self.notifications_paused:
            return False
        if self.is_in_quiet_hours():
            return False
        if event_type == 'follow' and not self.notify_follows:
            return False
        if event_type == 'like' and not self.notify_likes:
            return False
        if event_type == 'comment' and not self.notify_comments:
            return False
        if event_type == 'community' and not self.notify_communities:
            return False
        return True


    def mute_topic(self, topic):
        t = (topic or '').strip().lower()
        if t and t not in self.muted_topics:
            self.muted_topics.append(t)
            self.save(update_fields=['muted_topics'])

    def unmute_topic(self, topic):
        t = (topic or '').strip().lower()
        if t in self.muted_topics:
            self.muted_topics.remove(t)
            self.save(update_fields=['muted_topics'])

    def reset_feed_preferences(self):
        self.muted_topics = []
        self.default_feed_mode = 'following'
        self.save(update_fields=['muted_topics', 'default_feed_mode'])


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
