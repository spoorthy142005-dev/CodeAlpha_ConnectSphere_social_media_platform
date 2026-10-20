from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db.models import Q, F
from posts.models import Post


class Follow(models.Model):
    follower = models.ForeignKey(User, on_delete=models.CASCADE, related_name='following_set')
    following = models.ForeignKey(User, on_delete=models.CASCADE, related_name='follower_set')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['follower', 'following'], name='unique_follow_relation'),
            models.CheckConstraint(condition=~Q(follower=F('following')), name='prevent_self_follow')
        ]
        indexes = [
            models.Index(fields=['follower', 'following']),
            models.Index(fields=['following']),
        ]

    def clean(self):
        super().clean()
        if self.follower_id == self.following_id:
            raise ValidationError("You cannot follow yourself.")

    def __str__(self):
        return f"{self.follower.username} follows {self.following.username}"


class Bookmark(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bookmarks')
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='bookmarked_by')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(fields=['user', 'post'], name='unique_user_bookmark')
        ]
        indexes = [
            models.Index(fields=['user', '-created_at']),
        ]

    def __str__(self):
        return f"{self.user.username} saved post #{self.post_id}"


class Block(models.Model):
    blocker = models.ForeignKey(User, on_delete=models.CASCADE, related_name='blocking_set')
    blocked = models.ForeignKey(User, on_delete=models.CASCADE, related_name='blocked_by_set')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['blocker', 'blocked'], name='unique_block_relation'),
            models.CheckConstraint(condition=~Q(blocker=F('blocked')), name='prevent_self_block')
        ]
        indexes = [
            models.Index(fields=['blocker', 'blocked']),
        ]

    def clean(self):
        super().clean()
        if self.blocker_id == self.blocked_id:
            raise ValidationError("You cannot block yourself.")

    def __str__(self):
        return f"{self.blocker.username} blocked {self.blocked.username}"


class Mute(models.Model):
    muter = models.ForeignKey(User, on_delete=models.CASCADE, related_name='muting_set')
    muted = models.ForeignKey(User, on_delete=models.CASCADE, related_name='muted_by_set')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['muter', 'muted'], name='unique_mute_relation'),
            models.CheckConstraint(condition=~Q(muter=F('muted')), name='prevent_self_mute')
        ]
        indexes = [
            models.Index(fields=['muter', 'muted']),
        ]

    def clean(self):
        super().clean()
        if self.muter_id == self.muted_id:
            raise ValidationError("You cannot mute yourself.")

    def __str__(self):
        return f"{self.muter.username} muted {self.muted.username}"

