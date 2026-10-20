from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from accounts.models import Profile


class AuthenticationAndProfileTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user1 = User.objects.create_user(
            username='alice',
            email='alice@example.com',
            password='Password123!'
        )
        self.user2 = User.objects.create_user(
            username='bob',
            email='bob@example.com',
            password='Password123!'
        )

    def test_profile_auto_created_on_user_creation(self):
        """User creation should automatically create an associated Profile."""
        self.assertTrue(hasattr(self.user1, 'profile'))
        self.assertEqual(self.user1.profile.get_display_name(), 'alice')

    def test_user_registration_success(self):
        """Valid registration creates user and profile and redirects to feed."""
        response = self.client.post(reverse('accounts:register'), {
            'username': 'charlie',
            'email': 'charlie@example.com',
            'password': 'ComplexPassword123!',
            'password_confirm': 'ComplexPassword123!',
        })
        self.assertRedirects(response, reverse('posts:feed'))
        self.assertTrue(User.objects.filter(username='charlie').exists())

    def test_registration_duplicate_username(self):
        """Duplicate username (including case-insensitive) should be rejected."""
        response = self.client.post(reverse('accounts:register'), {
            'username': 'Alice',  # case-insensitive check
            'email': 'alice2@example.com',
            'password': 'Password123!',
            'password_confirm': 'Password123!',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context['form'], 'username', 'This username is already taken. Please choose another.')

    def test_registration_duplicate_email(self):
        """Duplicate email should be rejected."""
        response = self.client.post(reverse('accounts:register'), {
            'username': 'newuser',
            'email': 'alice@example.com',
            'password': 'Password123!',
            'password_confirm': 'Password123!',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context['form'], 'email', 'An account with this email address already exists.')

    def test_registration_password_mismatch(self):
        """Mismatched password confirmation should fail."""
        response = self.client.post(reverse('accounts:register'), {
            'username': 'newuser2',
            'email': 'new2@example.com',
            'password': 'Password123!',
            'password_confirm': 'DifferentPassword123!',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context['form'], 'password_confirm', 'Passwords do not match.')

    def test_login_and_logout(self):
        """Valid credentials log in user, logout signs out."""
        login_resp = self.client.post(reverse('accounts:login'), {
            'username': 'alice',
            'password': 'Password123!',
        })
        self.assertRedirects(login_resp, reverse('posts:feed'))

        logout_resp = self.client.post(reverse('accounts:logout'))
        self.assertRedirects(logout_resp, reverse('accounts:login'))

    def test_login_required_protection(self):
        """Protected pages redirect unauthenticated users to login."""
        response = self.client.get(reverse('posts:feed'))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse('accounts:login')))

    def test_profile_edit_by_owner(self):
        """User can edit their own profile details."""
        self.client.login(username='alice', password='Password123!')
        response = self.client.post(reverse('accounts:profile_edit'), {
            'display_name': 'Alice Wonder',
            'bio': 'Software developer exploring ConnectSphere.',
            'is_private': True,
            'low_bandwidth': True,
        })
        self.assertRedirects(response, reverse('accounts:profile_detail', kwargs={'username': 'alice'}))
        self.user1.profile.refresh_from_db()
        self.assertEqual(self.user1.profile.display_name, 'Alice Wonder')
        self.assertTrue(self.user1.profile.is_private)
        self.assertTrue(self.user1.profile.low_bandwidth)

    def test_user_search(self):
        """User search finds matching usernames and display names."""
        self.client.login(username='alice', password='Password123!')
        response = self.client.get(reverse('accounts:search') + '?q=bob')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'bob')


class PrivacyControlCenterAndDataOwnershipTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='alice', password='Password123!', email='alice@example.com')
        self.user2 = User.objects.create_user(username='bob', password='Password123!', email='bob@example.com')

    def test_privacy_center_view_get_and_post(self):
        """User can view privacy center and update privacy & wellbeing settings."""
        self.client.login(username='alice', password='Password123!')
        get_resp = self.client.get(reverse('accounts:privacy_center'))
        self.assertEqual(get_resp.status_code, 200)
        self.assertContains(get_resp, 'Privacy & Wellbeing Center')

        # Save settings
        post_resp = self.client.post(reverse('accounts:privacy_center'), {
            'is_private': True,
            'default_post_audience': 'followers',
            'default_feed_mode': 'discover',
            'low_bandwidth': True,
            'notify_follows': True,
            'notify_likes': False,
            'notify_comments': True,
            'notify_communities': True,
            'notifications_paused': False,
            'quiet_hours_enabled': True,
            'quiet_hours_start': '22:00',
            'quiet_hours_end': '08:00',
        })
        self.assertRedirects(post_resp, reverse('accounts:privacy_center'))
        self.user.profile.refresh_from_db()
        self.assertTrue(self.user.profile.is_private)
        self.assertEqual(self.user.profile.default_post_audience, 'followers')
        self.assertEqual(self.user.profile.default_feed_mode, 'discover')
        self.assertFalse(self.user.profile.notify_likes)
        self.assertTrue(self.user.profile.quiet_hours_enabled)

    def test_data_export_authenticated_and_excludes_credentials(self):
        """Authenticated data export returns JSON and strictly excludes credentials."""
        import json
        from posts.models import Post
        from social.models import Follow, Bookmark

        # Create some data for Alice
        post = Post.objects.create(author=self.user, content="Alice export test post")
        Follow.objects.create(follower=self.user, following=self.user2)
        Bookmark.objects.create(user=self.user, post=post)

        self.client.login(username='alice', password='Password123!')
        resp = self.client.get(reverse('accounts:data_export'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/json; charset=utf-8')
        self.assertIn('attachment; filename="connectsphere_export_alice_', resp['Content-Disposition'])

        payload = json.loads(resp.content.decode('utf-8'))
        self.assertEqual(payload['export_metadata']['application'], 'ConnectSphere')
        self.assertEqual(payload['account']['username'], 'alice')
        self.assertEqual(payload['account']['email'], 'alice@example.com')
        self.assertEqual(len(payload['posts']), 1)
        self.assertEqual(payload['posts'][0]['content'], "Alice export test post")
        self.assertEqual(len(payload['following']), 1)
        self.assertEqual(len(payload['bookmarks']), 1)

        # STRICT SECURITY CHECK: No passwords or credential hashes in export
        raw_text = resp.content.decode('utf-8').lower()
        self.assertNotIn('password', payload['account'])
        self.assertNotIn('pbkdf2', raw_text)
        self.assertNotIn('hash', payload['account'])
        self.assertNotIn('secret_key', raw_text)

    def test_data_export_requires_authentication(self):
        """Unauthenticated data export is blocked and redirected to login."""
        resp = self.client.get(reverse('accounts:data_export'))
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(resp.url.startswith(reverse('accounts:login')))

    def test_account_deletion_flow_with_safety_and_preservation(self):
        """
        Account deletion requires deliberate username + password confirmation,
        revokes session, deletes user data, but preserves community hub.
        """
        from posts.models import Post, Community, CommunityMembership
        comm = Community.objects.create(
            name='Preserved Hub',
            slug='preserved-hub',
            topic='technology',
            description='Community that should survive creator deletion',
            creator=self.user
        )
        CommunityMembership.objects.create(community=comm, user=self.user, role='admin')
        CommunityMembership.objects.create(community=comm, user=self.user2, role='member')
        Post.objects.create(author=self.user, content="Post by Alice")

        self.client.login(username='alice', password='Password123!')

        # 1. GET confirmation page
        get_resp = self.client.get(reverse('accounts:account_delete'))
        self.assertEqual(get_resp.status_code, 200)
        self.assertContains(get_resp, 'Permanent Account Deletion')

        # 2. POST with mismatched username should fail
        fail_resp1 = self.client.post(reverse('accounts:account_delete'), {
            'confirmation_username': 'wrong_username',
            'password': 'Password123!',
            'confirm_permanent_loss': True,
        })
        self.assertEqual(fail_resp1.status_code, 200)
        self.assertTrue(User.objects.filter(username='alice').exists())

        # 3. POST with wrong password should fail
        fail_resp2 = self.client.post(reverse('accounts:account_delete'), {
            'confirmation_username': 'alice',
            'password': 'WrongPassword!',
            'confirm_permanent_loss': True,
        })
        self.assertEqual(fail_resp2.status_code, 200)
        self.assertTrue(User.objects.filter(username='alice').exists())

        # 4. Valid deletion
        del_resp = self.client.post(reverse('accounts:account_delete'), {
            'confirmation_username': 'alice',
            'password': 'Password123!',
            'confirm_permanent_loss': True,
        })
        self.assertRedirects(del_resp, reverse('accounts:login'))

        # Alice is deleted
        self.assertFalse(User.objects.filter(username='alice').exists())
        self.assertEqual(Post.objects.count(), 0)

        # Community Hub survives with creator set to None (models.SET_NULL)
        comm.refresh_from_db()
        self.assertIsNone(comm.creator)
        self.assertEqual(comm.slug, 'preserved-hub')
        self.assertTrue(CommunityMembership.objects.filter(community=comm, user=self.user2).exists())

    def test_notification_preferences_server_enforcement(self):
        """Notification categories and pause state are enforced on the server."""
        from notifications.models import Notification
        from notifications.utils import create_notification
        from posts.models import Post

        alice_post = Post.objects.create(author=self.user, content="Alice notification test")

        # By default, like creates a notification
        create_notification(recipient=self.user, actor=self.user2, event_type='like', post=alice_post)
        self.assertEqual(Notification.objects.filter(recipient=self.user).count(), 1)

        # Alice turns off notify_likes
        self.user.profile.notify_likes = False
        self.user.profile.save()

        create_notification(recipient=self.user, actor=self.user2, event_type='like', post=alice_post)
        # Count should still be 1 because notify_likes is False
        self.assertEqual(Notification.objects.filter(recipient=self.user).count(), 1)

        # Alice pauses all notifications
        self.user.profile.notifications_paused = True
        self.user.profile.save()

        create_notification(recipient=self.user, actor=self.user2, event_type='follow')
        # Count should still be 1 because notifications are paused
        self.assertEqual(Notification.objects.filter(recipient=self.user).count(), 1)


class SecurityAndRegressionDeepAuditTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.alice = User.objects.create_user(username='alice', password='Password123!', email='alice@test.com')
        self.bob = User.objects.create_user(username='bob', password='Password123!', email='bob@test.com')

    def test_overnight_quiet_hours_midnight_wrap_around(self):
        """
        Verify quiet hours behavior when start time is later than end time (e.g., 22:00–07:00).
        """
        import datetime
        from unittest.mock import patch

        self.alice.profile.quiet_hours_enabled = True
        self.alice.profile.quiet_hours_start = datetime.time(22, 0)
        self.alice.profile.quiet_hours_end = datetime.time(7, 0)
        self.alice.profile.save()

        # 1. During quiet hours (late evening: 23:30)
        with patch('django.utils.timezone.localtime') as mock_now:
            mock_now.return_value = datetime.datetime(2026, 10, 20, 23, 30)
            self.assertTrue(self.alice.profile.is_in_quiet_hours())
            self.assertFalse(self.alice.profile.should_receive_notification('like'))

        # 2. During quiet hours (early morning: 04:15)
        with patch('django.utils.timezone.localtime') as mock_now:
            mock_now.return_value = datetime.datetime(2026, 10, 20, 4, 15)
            self.assertTrue(self.alice.profile.is_in_quiet_hours())
            self.assertFalse(self.alice.profile.should_receive_notification('like'))

        # 3. Outside quiet hours (afternoon: 14:00)
        with patch('django.utils.timezone.localtime') as mock_now:
            mock_now.return_value = datetime.datetime(2026, 10, 20, 14, 0)
            self.assertFalse(self.alice.profile.is_in_quiet_hours())
            self.assertTrue(self.alice.profile.should_receive_notification('like'))

    def test_multi_session_revocation_on_account_deletion(self):
        """
        Confirm account deletion purges ALL active sessions belonging to the user
        across all devices/browsers, preventing lingering session token re-use.
        """
        from django.contrib.sessions.backends.db import SessionStore
        from django.contrib.sessions.models import Session

        # Simulate Session 1 (e.g. Chrome on Laptop)
        s1 = SessionStore()
        s1['_auth_user_id'] = str(self.alice.id)
        s1['_auth_user_backend'] = 'django.contrib.auth.backends.ModelBackend'
        s1.create()
        key1 = s1.session_key

        # Simulate Session 2 (e.g. Safari on Phone)
        s2 = SessionStore()
        s2['_auth_user_id'] = str(self.alice.id)
        s2['_auth_user_backend'] = 'django.contrib.auth.backends.ModelBackend'
        s2.create()
        key2 = s2.session_key

        # Confirm both sessions exist in the session database
        self.assertTrue(Session.objects.filter(session_key=key1).exists())
        self.assertTrue(Session.objects.filter(session_key=key2).exists())

        # Perform deletion
        self.client.login(username='alice', password='Password123!')
        del_resp = self.client.post(reverse('accounts:account_delete'), {
            'confirmation_username': 'alice',
            'password': 'Password123!',
            'confirm_permanent_loss': True,
        })
        self.assertRedirects(del_resp, reverse('accounts:login'))

        # Assert BOTH session keys have been revoked from the database
        self.assertFalse(Session.objects.filter(session_key=key1).exists())
        self.assertFalse(Session.objects.filter(session_key=key2).exists())

    def test_bookmark_export_excludes_restricted_and_blocked_posts(self):
        """
        Confirm personal data export does NOT leak captions of posts from authors
        who subsequently blocked the user or restricted audience.
        """
        import json
        from posts.models import Post
        from social.models import Bookmark, Block

        # Bob creates a post that Alice bookmarks
        bobs_post = Post.objects.create(author=self.bob, content="Bob secret content that should not leak")
        Bookmark.objects.create(user=self.alice, post=bobs_post)

        # Bob now blocks Alice
        Block.objects.create(blocker=self.bob, blocked=self.alice)

        # Alice exports her data
        self.client.login(username='alice', password='Password123!')
        resp = self.client.get(reverse('accounts:data_export'))
        self.assertEqual(resp.status_code, 200)

        payload = json.loads(resp.content.decode('utf-8'))
        # Alice's bookmarks list in export should NOT contain Bob's blocked post
        self.assertEqual(len(payload['bookmarks']), 0)
        self.assertNotIn("Bob secret content", resp.content.decode('utf-8'))

    def test_saved_posts_view_excludes_restricted_content(self):
        """
        Verify saved posts page (/social/saved/) hides bookmarked posts that become restricted.
        """
        from posts.models import Post
        from social.models import Bookmark, Follow

        # Bob creates a followers-only post
        bobs_post = Post.objects.create(author=self.bob, content="Bob followers post in bookmarks", audience='followers')
        Bookmark.objects.create(user=self.alice, post=bobs_post)

        # Alice does NOT follow Bob
        self.client.login(username='alice', password='Password123!')
        saved_resp = self.client.get(reverse('social:saved_posts'))
        self.assertNotContains(saved_resp, "Bob followers post in bookmarks")

        # Alice follows Bob: post now appears in saved posts
        Follow.objects.create(follower=self.alice, following=self.bob)
        saved_resp_followed = self.client.get(reverse('social:saved_posts'))
        self.assertContains(saved_resp_followed, "Bob followers post in bookmarks")
