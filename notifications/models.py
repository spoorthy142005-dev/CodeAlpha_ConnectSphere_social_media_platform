from django.db import models
from django.contrib.auth.models import User
from posts.models import Post, Comment


class Notification(models.Model):
    EVENT_TYPES = [
        ('follow', 'started following you'),
        ('like', 'liked your post'),
        ('comment', 'commented on your post'),
    ]

    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    actor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_notifications')
    event_type = models.CharField(max_length=20, choices=EVENT_TYPES)
    post = models.ForeignKey(Post, on_delete=models.CASCADE, null=True, blank=True, related_name='notifications')
    comment = models.ForeignKey(Comment, on_delete=models.CASCADE, null=True, blank=True, related_name='notifications')
    is_read = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', 'is_read', '-created_at']),
        ]

    def __str__(self):
        return f"Notification for {self.recipient.username}: {self.actor.username} {self.get_event_type_display()}"
