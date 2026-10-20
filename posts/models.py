import os
from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone


def validate_post_image(file):
    """Ensure post images are under 5MB and valid image formats."""
    max_size = 5 * 1024 * 1024
    if file.size > max_size:
        raise ValidationError("Image file size cannot exceed 5MB.")
    
    ext = os.path.splitext(file.name)[1].lower()
    valid_extensions = ['.jpg', '.jpeg', '.png', '.webp', '.gif']
    if ext not in valid_extensions:
        raise ValidationError("Unsupported file format. Please upload JPG, PNG, GIF, or WebP.")


class Post(models.Model):
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='posts')
    content = models.TextField(max_length=2000, blank=True, default='')
    image = models.ImageField(upload_to='posts/%Y/%m/', blank=True, null=True, validators=[validate_post_image])
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['author', '-created_at']),
        ]

    def __str__(self):
        snippet = self.content[:30] if self.content else f"Image post #{self.id}"
        return f"Post by {self.author.username}: {snippet}"

    def clean(self):
        super().clean()
        if not self.content.strip() and not self.image:
            raise ValidationError("A post must contain either text content or an image.")

    @property
    def is_edited(self):
        # Only mark as edited if updated_at is more than 3 seconds after created_at
        if not self.updated_at or not self.created_at:
            return False
        return (self.updated_at - self.created_at).total_seconds() > 3

    @property
    def likes_count(self):
        return self.likes.count()

    @property
    def comments_count(self):
        return self.comments.count()

    def is_liked_by(self, user):
        if not user or not user.is_authenticated:
            return False
        return self.likes.filter(user=user).exists()

    def is_bookmarked_by(self, user):
        if not user or not user.is_authenticated:
            return False
        return self.bookmarked_by.filter(user=user).exists()


class Like(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='post_likes')
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='likes')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user', 'post'], name='unique_post_like')
        ]
        indexes = [
            models.Index(fields=['post', 'user']),
        ]

    def __str__(self):
        return f"{self.user.username} liked post #{self.post_id}"


class Comment(models.Model):
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='comments')
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='comments')
    content = models.TextField(max_length=1000)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['post', 'created_at']),
        ]

    def __str__(self):
        return f"Comment by {self.author.username} on post #{self.post_id}"

    def clean(self):
        super().clean()
        if not self.content.strip():
            raise ValidationError("Comment content cannot be empty.")

    @property
    def is_edited(self):
        if not self.updated_at or not self.created_at:
            return False
        return (self.updated_at - self.created_at).total_seconds() > 3
