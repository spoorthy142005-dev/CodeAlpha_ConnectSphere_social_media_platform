from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from posts.models import Post, Like, Comment
from social.models import Follow, Block


class PostsAndFeedInteractionsTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user1 = User.objects.create_user(username='alice', password='Password123!')
        self.user2 = User.objects.create_user(username='bob', password='Password123!')
        self.post1 = Post.objects.create(author=self.user1, content="Hello from Alice!")

    def test_create_post(self):
        """Authenticated user can create a post."""
        self.client.login(username='alice', password='Password123!')
        response = self.client.post(reverse('posts:post_create'), {
            'content': 'A brand new post on ConnectSphere.'
        })
        self.assertRedirects(response, reverse('posts:feed'))
        self.assertEqual(Post.objects.count(), 2)

    def test_empty_post_rejected(self):
        """A post with neither text content nor image is rejected."""
        self.client.login(username='alice', password='Password123!')
        response = self.client.post(reverse('posts:post_create'), {
            'content': '   '
        })
        # Should stay on page and not create post
        self.assertEqual(Post.objects.count(), 1)

    def test_post_edit_by_author(self):
        """Author can edit their post."""
        self.client.login(username='alice', password='Password123!')
        response = self.client.post(reverse('posts:post_edit', kwargs={'post_id': self.post1.id}), {
            'content': 'Updated Alice post content.'
        })
        self.assertRedirects(response, reverse('posts:post_detail', kwargs={'post_id': self.post1.id}))
        self.post1.refresh_from_db()
        self.assertEqual(self.post1.content, 'Updated Alice post content.')

    def test_unauthorized_post_edit_forbidden(self):
        """Another user cannot edit someone else's post."""
        self.client.login(username='bob', password='Password123!')
        response = self.client.post(reverse('posts:post_edit', kwargs={'post_id': self.post1.id}), {
            'content': 'Hacked content by Bob!'
        })
        self.assertEqual(response.status_code, 403)
        self.post1.refresh_from_db()
        self.assertEqual(self.post1.content, "Hello from Alice!")

    def test_unauthorized_post_delete_forbidden(self):
        """Another user cannot delete someone else's post."""
        self.client.login(username='bob', password='Password123!')
        response = self.client.post(reverse('posts:post_delete', kwargs={'post_id': self.post1.id}))
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Post.objects.filter(id=self.post1.id).exists())

    def test_post_delete_by_author(self):
        """Author can delete their own post."""
        self.client.login(username='alice', password='Password123!')
        response = self.client.post(reverse('posts:post_delete', kwargs={'post_id': self.post1.id}))
        self.assertRedirects(response, reverse('posts:feed'))
        self.assertFalse(Post.objects.filter(id=self.post1.id).exists())

    def test_like_and_unlike_toggle(self):
        """User can like and unlike a post; duplicate likes are prevented."""
        self.client.login(username='bob', password='Password123!')
        like_url = reverse('posts:post_like_toggle', kwargs={'post_id': self.post1.id})

        # 1. Like
        self.client.post(like_url)
        self.assertEqual(self.post1.likes.count(), 1)
        self.assertTrue(Like.objects.filter(user=self.user2, post=self.post1).exists())

        # 2. Unlike
        self.client.post(like_url)
        self.assertEqual(self.post1.likes.count(), 0)
        self.assertFalse(Like.objects.filter(user=self.user2, post=self.post1).exists())

    def test_comments_create_and_ownership(self):
        """Comments can be added, edited, and deleted by owner."""
        self.client.login(username='bob', password='Password123!')
        comment_url = reverse('posts:comment_create', kwargs={'post_id': self.post1.id})

        # Add comment
        self.client.post(comment_url, {'content': 'Great post, Alice!'})
        self.assertEqual(self.post1.comments.count(), 1)
        comment = self.post1.comments.first()
        self.assertEqual(comment.author, self.user2)

        # Alice cannot edit Bob's comment
        self.client.login(username='alice', password='Password123!')
        edit_resp = self.client.post(reverse('posts:comment_edit', kwargs={'comment_id': comment.id}), {
            'content': 'Attempt to hijack Bob comment'
        })
        self.assertEqual(edit_resp.status_code, 403)

        # Bob can edit his comment
        self.client.login(username='bob', password='Password123!')
        self.client.post(reverse('posts:comment_edit', kwargs={'comment_id': comment.id}), {
            'content': 'Updated comment by Bob'
        })
        comment.refresh_from_db()
        self.assertEqual(comment.content, 'Updated comment by Bob')

        # Bob can delete his comment
        self.client.post(reverse('posts:comment_delete', kwargs={'comment_id': comment.id}))
        self.assertEqual(self.post1.comments.count(), 0)

    def test_feed_filtering_following_and_discover(self):
        """Following feed shows followed user's posts; Discover shows public posts."""
        bob_post = Post.objects.create(author=self.user2, content="Bob public post")
        
        self.client.login(username='alice', password='Password123!')
        
        # Before following: Alice's following feed should only show Alice's post
        resp_following = self.client.get(reverse('posts:feed') + '?mode=following')
        self.assertContains(resp_following, 'Hello from Alice!')
        self.assertNotContains(resp_following, "Bob public post")

        # Discover feed should show Bob's post
        resp_discover = self.client.get(reverse('posts:feed') + '?mode=discover')
        self.assertContains(resp_discover, "Bob public post")

        # After following Bob: Following feed should show Bob's post
        Follow.objects.create(follower=self.user1, following=self.user2)
        resp_following_after = self.client.get(reverse('posts:feed') + '?mode=following')
        self.assertContains(resp_following_after, "Bob public post")

    def test_blocked_user_posts_hidden_from_feed(self):
        """Posts from blocked users are excluded from the feed."""
        Post.objects.create(author=self.user2, content="Bob post to be blocked")
        Block.objects.create(blocker=self.user1, blocked=self.user2)

        self.client.login(username='alice', password='Password123!')
        resp = self.client.get(reverse('posts:feed') + '?mode=discover')
        self.assertNotContains(resp, "Bob post to be blocked")
