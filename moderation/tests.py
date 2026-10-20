from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from moderation.models import Report
from posts.models import Post, Comment


class ModerationAndReportingTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user1 = User.objects.create_user(username='alice', password='Password123!')
        self.user2 = User.objects.create_user(username='bob', password='Password123!')
        self.staff_user = User.objects.create_user(
            username='moderator',
            password='Password123!',
            is_staff=True
        )
        self.post = Post.objects.create(author=self.user2, content="Suspicious post content")
        self.comment = Comment.objects.create(author=self.user2, post=self.post, content="Offensive comment")

    def test_report_post(self):
        """User can submit a report against a post."""
        self.client.login(username='alice', password='Password123!')
        resp = self.client.post(reverse('moderation:report_post', kwargs={'post_id': self.post.id}), {
            'reason': 'spam',
            'notes': 'Unwanted spam advertisement link.'
        })
        self.assertRedirects(resp, reverse('posts:post_detail', kwargs={'post_id': self.post.id}))
        self.assertTrue(Report.objects.filter(post=self.post, reporter=self.user1).exists())

    def test_report_comment(self):
        """User can submit a report against a comment."""
        self.client.login(username='alice', password='Password123!')
        resp = self.client.post(reverse('moderation:report_comment', kwargs={'comment_id': self.comment.id}), {
            'reason': 'harassment',
            'notes': 'Personal insults directed in comment thread.'
        })
        self.assertRedirects(resp, reverse('posts:post_detail', kwargs={'post_id': self.post.id}))
        self.assertTrue(Report.objects.filter(comment=self.comment, reporter=self.user1).exists())

    def test_moderation_dashboard_access_control(self):
        """Only staff users can access the moderation dashboard."""
        # Regular user denied/redirected
        self.client.login(username='alice', password='Password123!')
        resp = self.client.get(reverse('moderation:dashboard'))
        self.assertEqual(resp.status_code, 302)

        # Staff user allowed
        self.client.login(username='moderator', password='Password123!')
        resp_staff = self.client.get(reverse('moderation:dashboard'))
        self.assertEqual(resp_staff.status_code, 200)

    def test_staff_moderation_action_delete_content(self):
        """Staff moderator can review report and delete violating content."""
        report = Report.objects.create(
            reporter=self.user1,
            post=self.post,
            reported_user=self.user2,
            reason='hate_speech',
            notes='Violates community terms'
        )

        self.client.login(username='moderator', password='Password123!')
        review_url = reverse('moderation:review', kwargs={'report_id': report.id})

        self.client.post(review_url, {
            'status': 'action_taken',
            'resolution_notes': 'Confirmed violation. Post deleted.',
            'delete_content': True,
        })

        report.refresh_from_db()
        self.assertEqual(report.status, 'action_taken')
        self.assertIsNone(report.post)
        self.assertFalse(Post.objects.filter(id=self.post.id).exists())
