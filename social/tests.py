from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.db import IntegrityError
from social.models import Follow, Bookmark, Block
from posts.models import Post


class SocialFeaturesTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user1 = User.objects.create_user(username='alice', password='Password123!')
        self.user2 = User.objects.create_user(username='bob', password='Password123!')
        self.post = Post.objects.create(author=self.user2, content="Bob post")

    def test_follow_and_unfollow(self):
        """User can follow and unfollow another user."""
        self.client.login(username='alice', password='Password123!')
        follow_url = reverse('social:follow_toggle', kwargs={'username': 'bob'})

        # Follow
        self.client.post(follow_url)
        self.assertTrue(Follow.objects.filter(follower=self.user1, following=self.user2).exists())
        self.assertEqual(self.user2.follower_set.count(), 1)

        # Unfollow
        self.client.post(follow_url)
        self.assertFalse(Follow.objects.filter(follower=self.user1, following=self.user2).exists())
        self.assertEqual(self.user2.follower_set.count(), 0)

    def test_cannot_follow_self(self):
        """Self-follow is rejected by view and database constraint."""
        self.client.login(username='alice', password='Password123!')
        resp = self.client.post(reverse('social:follow_toggle', kwargs={'username': 'alice'}))
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(Follow.objects.filter(follower=self.user1, following=self.user1).exists())

    def test_duplicate_follow_prevented(self):
        """Database constraint prevents duplicate follow rows."""
        Follow.objects.create(follower=self.user1, following=self.user2)
        with self.assertRaises(IntegrityError):
            Follow.objects.create(follower=self.user1, following=self.user2)

    def test_bookmarks_private_and_toggle(self):
        """Bookmarks are private to the owner and prevent duplicates."""
        self.client.login(username='alice', password='Password123!')
        bm_url = reverse('social:bookmark_toggle', kwargs={'post_id': self.post.id})

        # Save bookmark
        self.client.post(bm_url)
        self.assertTrue(Bookmark.objects.filter(user=self.user1, post=self.post).exists())

        # View saved posts as Alice
        resp = self.client.get(reverse('social:saved_posts'))
        self.assertContains(resp, 'Bob post')

        # Log in as Bob: Bob should NOT see Alice's bookmarks
        self.client.login(username='bob', password='Password123!')
        resp_bob = self.client.get(reverse('social:saved_posts'))
        self.assertNotContains(resp_bob, 'Bob post')

    def test_block_user_and_clean_relations(self):
        """Blocking user removes existing follows in both directions."""
        Follow.objects.create(follower=self.user1, following=self.user2)
        Follow.objects.create(follower=self.user2, following=self.user1)

        self.client.login(username='alice', password='Password123!')
        self.client.post(reverse('social:block_toggle', kwargs={'username': 'bob'}))

        self.assertTrue(Block.objects.filter(blocker=self.user1, blocked=self.user2).exists())
        self.assertFalse(Follow.objects.filter(follower=self.user1, following=self.user2).exists())
        self.assertFalse(Follow.objects.filter(follower=self.user2, following=self.user1).exists())

    def test_cannot_block_self(self):
        """Self-blocking is rejected."""
        self.client.login(username='alice', password='Password123!')
        resp = self.client.post(reverse('social:block_toggle', kwargs={'username': 'alice'}))
        self.assertEqual(resp.status_code, 400)

    def test_mute_and_unmute_user(self):
        """User can mute and unmute an account without blocking."""
        from social.models import Mute
        self.client.login(username='alice', password='Password123!')
        mute_url = reverse('social:mute_toggle', kwargs={'username': 'bob'})

        # Mute Bob
        resp = self.client.post(mute_url)
        self.assertTrue(Mute.objects.filter(muter=self.user1, muted=self.user2).exists())

        # Unmute Bob
        resp = self.client.post(mute_url)
        self.assertFalse(Mute.objects.filter(muter=self.user1, muted=self.user2).exists())

    def test_cannot_mute_self(self):
        """User cannot mute their own account."""
        self.client.login(username='alice', password='Password123!')
        resp = self.client.post(reverse('social:mute_toggle', kwargs={'username': 'alice'}))
        self.assertEqual(resp.status_code, 400)

    def test_muted_user_posts_hidden_from_feed(self):
        """Muted user's posts are excluded from the muter's feed."""
        from social.models import Mute
        Follow.objects.create(follower=self.user1, following=self.user2)

        # Before mute: Alice sees Bob's post in Following feed
        self.client.login(username='alice', password='Password123!')
        resp1 = self.client.get(reverse('posts:feed') + '?mode=following')
        self.assertContains(resp1, "Bob post")

        # Alice mutes Bob
        Mute.objects.create(muter=self.user1, muted=self.user2)

        # After mute: Alice no longer sees Bob's post in feed
        resp2 = self.client.get(reverse('posts:feed') + '?mode=following')
        self.assertNotContains(resp2, "Bob post")

        # Discover feed also excludes Bob's post
        resp_disc = self.client.get(reverse('posts:feed') + '?mode=discover')
        self.assertNotContains(resp_disc, "Bob post")
