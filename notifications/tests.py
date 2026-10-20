from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from notifications.models import Notification
from posts.models import Post


class NotificationsTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user1 = User.objects.create_user(username='alice', password='Password123!')
        self.user2 = User.objects.create_user(username='bob', password='Password123!')
        self.post = Post.objects.create(author=self.user1, content="Alice's post")

    def test_follow_creates_notification(self):
        """Following a user creates a notification for recipient."""
        self.client.login(username='bob', password='Password123!')
        self.client.post(reverse('social:follow_toggle', kwargs={'username': 'alice'}))

        self.assertTrue(Notification.objects.filter(
            recipient=self.user1,
            actor=self.user2,
            event_type='follow'
        ).exists())

    def test_like_creates_notification(self):
        """Liking another user's post creates a notification."""
        self.client.login(username='bob', password='Password123!')
        self.client.post(reverse('posts:post_like_toggle', kwargs={'post_id': self.post.id}))

        self.assertTrue(Notification.objects.filter(
            recipient=self.user1,
            actor=self.user2,
            event_type='like',
            post=self.post
        ).exists())

    def test_self_like_no_notification(self):
        """Liking one's own post does NOT generate a notification."""
        self.client.login(username='alice', password='Password123!')
        self.client.post(reverse('posts:post_like_toggle', kwargs={'post_id': self.post.id}))

        self.assertFalse(Notification.objects.filter(recipient=self.user1, actor=self.user1).exists())

    def test_mark_as_read(self):
        """User can mark notification as read; unauthorized user cannot."""
        note = Notification.objects.create(
            recipient=self.user1,
            actor=self.user2,
            event_type='follow'
        )

        # Bob cannot mark Alice's notification
        self.client.login(username='bob', password='Password123!')
        resp = self.client.post(reverse('notifications:mark_as_read', kwargs={'notification_id': note.id}))
        self.assertEqual(resp.status_code, 403)
        note.refresh_from_db()
        self.assertFalse(note.is_read)

        # Alice can mark her notification
        self.client.login(username='alice', password='Password123!')
        self.client.post(reverse('notifications:mark_as_read', kwargs={'notification_id': note.id}))
        note.refresh_from_db()
        self.assertTrue(note.is_read)

    def test_mark_all_as_read(self):
        """User can mark all unread notifications as read."""
        Notification.objects.create(recipient=self.user1, actor=self.user2, event_type='follow')
        Notification.objects.create(recipient=self.user1, actor=self.user2, event_type='like', post=self.post)

        self.client.login(username='alice', password='Password123!')
        self.client.post(reverse('notifications:mark_all_as_read'))
        self.assertEqual(Notification.objects.filter(recipient=self.user1, is_read=False).count(), 0)
