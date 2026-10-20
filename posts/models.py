import os
from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone


def validate_post_image(file):
    """Ensure post images are under 5MB, valid image extensions, and real image binary data."""
    max_size = 5 * 1024 * 1024
    if file.size > max_size:
        raise ValidationError("Image file size cannot exceed 5MB.")
    
    ext = os.path.splitext(file.name)[1].lower()
    valid_extensions = ['.jpg', '.jpeg', '.png', '.webp', '.gif']
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



def validate_community_icon(file):
    """Ensure community icons are under 2MB, valid image extensions, and real image binary data."""
    max_size = 2 * 1024 * 1024
    if file.size > max_size:
        raise ValidationError("Community icon file size cannot exceed 2MB.")
    
    ext = os.path.splitext(file.name)[1].lower()
    valid_extensions = ['.jpg', '.jpeg', '.png', '.webp', '.gif']
    if ext not in valid_extensions:
        raise ValidationError("Unsupported file format. Please upload JPG, PNG, GIF, or WebP.")

    try:
        from PIL import Image
        img = Image.open(file)
        img.verify()
        if hasattr(file, 'seek'):
            file.seek(0)
    except Exception:
        raise ValidationError("The uploaded file is not a valid or readable image.")


class Community(models.Model):
    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=100, unique=True, db_index=True)
    description = models.TextField(max_length=600)
    topic = models.CharField(max_length=50, db_index=True)
    creator = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_communities')
    icon = models.ImageField(upload_to='communities/%Y/%m/', blank=True, null=True, validators=[validate_community_icon])
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['topic']),
        ]

    def __str__(self):
        return f"c/{self.slug} - {self.name}"

    @property
    def members_count(self):
        return self.memberships.count()

    @property
    def posts_count(self):
        return self.posts.count()

    def is_member(self, user):
        if not user or not user.is_authenticated:
            return False
        return self.memberships.filter(user=user).exists()

    def is_moderator_or_creator(self, user):
        if not user or not user.is_authenticated:
            return False
        if user == self.creator or user.is_staff:
            return True
        return self.memberships.filter(user=user, role__in=['moderator', 'admin']).exists()


class CommunityMembership(models.Model):
    ROLE_CHOICES = [
        ('member', 'Member'),
        ('moderator', 'Moderator'),
        ('admin', 'Admin'),
    ]
    community = models.ForeignKey(Community, on_delete=models.CASCADE, related_name='memberships')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='community_memberships')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='member')
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['community', 'user'], name='unique_community_membership')
        ]
        indexes = [
            models.Index(fields=['community', 'user']),
        ]

    def __str__(self):
        return f"{self.user.username} in {self.community.slug} ({self.role})"


class Post(models.Model):
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='posts')
    community = models.ForeignKey(Community, on_delete=models.SET_NULL, null=True, blank=True, related_name='posts')
    topic = models.CharField(max_length=50, blank=True, default='', db_index=True)
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

    def get_recommendation_reason(self, user=None, feed_mode='discover', topic_filter=None):
        """Transparent, explainable reason for post inclusion."""
        if self.community:
            return f"c/{self.community.slug}"
        if topic_filter and self.topic and self.topic.lower() == topic_filter.lower():
            return f"Topic #{self.topic}"
        if user and user.is_authenticated:
            if self.author == user:
                return "Your post"
            if user.following_set.filter(following=self.author).exists():
                return f"Followed creator @{self.author.username}"
        if self.topic:
            return f"Topic #{self.topic}"
        return "Public Discover feed"


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
