from django.db import models
from django.contrib.auth.models import User
from posts.models import Post, Comment


class Report(models.Model):
    REASON_CHOICES = [
        ('spam', 'Spam or Scam'),
        ('harassment', 'Harassment or Bullying'),
        ('hate_speech', 'Hate Speech'),
        ('inappropriate', 'Inappropriate or Sensitive Content'),
        ('misinformation', 'Misinformation'),
        ('other', 'Other Community Guideline Violation'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('reviewed', 'Reviewed / Safe'),
        ('dismissed', 'Dismissed'),
        ('action_taken', 'Action Taken / Hidden'),
    ]

    reporter = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reports_filed')
    post = models.ForeignKey(Post, on_delete=models.SET_NULL, null=True, blank=True, related_name='reports')
    comment = models.ForeignKey(Comment, on_delete=models.SET_NULL, null=True, blank=True, related_name='reports')
    reported_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reports_received')
    
    reason = models.CharField(max_length=50, choices=REASON_CHOICES)
    notes = models.TextField(max_length=500, blank=True, default='')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    resolution_notes = models.TextField(blank=True, default='')
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='moderated_reports')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', '-created_at']),
        ]

    def __str__(self):
        target = "Content"
        if self.post:
            target = f"Post #{self.post_id}"
        elif self.comment:
            target = f"Comment #{self.comment_id}"
        elif self.reported_user:
            target = f"User @{self.reported_user.username}"
        return f"Report #{self.id} by {self.reporter.username} on {target} [{self.get_status_display()}]"
