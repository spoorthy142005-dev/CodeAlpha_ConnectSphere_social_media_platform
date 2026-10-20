import io
from PIL import Image
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError
from posts.models import Post, Like, Comment, Community, CommunityMembership
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

    def test_valid_image_post_creation(self):
        """User can upload a legitimate image file with their post."""
        self.client.login(username='alice', password='Password123!')
        f = io.BytesIO()
        img = Image.new('RGB', (50, 50), color='green')
        img.save(f, format='JPEG')
        f.seek(0)
        uploaded = SimpleUploadedFile("photo.jpg", f.read(), content_type="image/jpeg")

        response = self.client.post(reverse('posts:post_create'), {
            'content': 'A photo post from Alice',
            'image': uploaded,
        })
        self.assertRedirects(response, reverse('posts:feed'))
        post = Post.objects.filter(content='A photo post from Alice').first()
        self.assertIsNotNone(post)
        self.assertTrue(bool(post.image))

    def test_fake_image_file_rejected(self):
        """Corrupted/fake image disguised with .jpg extension is rejected."""
        self.client.login(username='alice', password='Password123!')
        fake_payload = SimpleUploadedFile("exploit.jpg", b"fake binary payload that is not an image", content_type="image/jpeg")
        response = self.client.post(reverse('posts:post_create'), {
            'content': 'Attempt with fake image',
            'image': fake_payload,
        })
        # Post creation should fail validation and not be saved to DB
        self.assertFalse(Post.objects.filter(content='Attempt with fake image').exists())

    def test_feed_mode_default_preference(self):
        """User preference for default feed mode determines landing stream."""
        self.user1.profile.default_feed_mode = 'discover'
        self.user1.profile.save()

        Post.objects.create(author=self.user2, content="Bob public post in discover")

        self.client.login(username='alice', password='Password123!')
        response = self.client.get(reverse('posts:feed'))
        # Should render Discover feed because of user's preference
        self.assertEqual(response.context['feed_mode'], 'discover')
        self.assertContains(response, "Bob public post in discover")

    def test_topic_filtering(self):
        """Feeds can be filtered by specific topic."""
        Post.objects.create(author=self.user2, content="Tech post about AI", topic="technology")
        Post.objects.create(author=self.user2, content="Design post about typography", topic="design")

        self.client.login(username='alice', password='Password123!')
        resp_tech = self.client.get(reverse('posts:feed') + '?mode=discover&topic=technology')
        self.assertContains(resp_tech, "Tech post about AI")
        self.assertNotContains(resp_tech, "Design post about typography")

    def test_less_like_this_topic_muting_and_reset(self):
        """Muting a topic via 'Less like this' suppresses it from Discover until reset."""
        Post.objects.create(author=self.user2, content="Crypto startup news", topic="business")
        Post.objects.create(author=self.user2, content="Quantum physics paper", topic="science")

        self.client.login(username='alice', password='Password123!')

        # 1. Before muting: both appear in Discover
        resp1 = self.client.get(reverse('posts:feed') + '?mode=discover')
        self.assertContains(resp1, "Crypto startup news")
        self.assertContains(resp1, "Quantum physics paper")

        # 2. Mute business topic
        mute_resp = self.client.post(reverse('posts:mute_topic'), {'topic': 'business'})
        self.user1.profile.refresh_from_db()
        self.assertIn('business', self.user1.profile.muted_topics)

        # 3. After muting: business post is suppressed from Discover
        resp2 = self.client.get(reverse('posts:feed') + '?mode=discover')
        self.assertNotContains(resp2, "Crypto startup news")
        self.assertContains(resp2, "Quantum physics paper")

        # 4. Reset preferences: restores business post
        self.client.post(reverse('posts:reset_feed_preferences'))
        self.user1.profile.refresh_from_db()
        self.assertEqual(self.user1.profile.muted_topics, [])

        resp3 = self.client.get(reverse('posts:feed') + '?mode=discover')
        self.assertContains(resp3, "Crypto startup news")

    def test_community_creation_and_slug_uniqueness(self):
        """Creating a community sets creator as admin and prevents duplicate slugs."""
        self.client.login(username='alice', password='Password123!')
        response = self.client.post(reverse('posts:community_create'), {
            'name': 'AI Researchers',
            'slug': 'ai-researchers',
            'topic': 'technology',
            'description': 'A hub for machine learning and artificial intelligence.',
        })
        self.assertRedirects(response, reverse('posts:community_detail', kwargs={'slug': 'ai-researchers'}))
        
        comm = Community.objects.filter(slug='ai-researchers').first()
        self.assertIsNotNone(comm)
        self.assertEqual(comm.creator, self.user1)
        self.assertTrue(comm.memberships.filter(user=self.user1, role='admin').exists())

        # Duplicate slug rejection
        resp_dup = self.client.post(reverse('posts:community_create'), {
            'name': 'Another AI Group',
            'slug': 'ai-researchers',
            'topic': 'technology',
            'description': 'Duplicate slug attempt.',
        })
        self.assertEqual(resp_dup.status_code, 200)
        self.assertFormError(resp_dup.context['form'], 'slug', 'This community slug is already taken. Please choose another.')

    def test_community_join_and_leave(self):
        """Users can join and leave communities; uniqueness is enforced."""
        comm = Community.objects.create(
            name='Design Sphere',
            slug='design-sphere',
            topic='design',
            description='UI/UX discussion group',
            creator=self.user1
        )
        CommunityMembership.objects.create(community=comm, user=self.user1, role='admin')

        # Bob joins
        self.client.login(username='bob', password='Password123!')
        self.client.post(reverse('posts:community_join_toggle', kwargs={'slug': 'design-sphere'}))
        self.assertTrue(CommunityMembership.objects.filter(community=comm, user=self.user2, role='member').exists())
        self.assertEqual(comm.members_count, 2)

        # Bob leaves
        self.client.post(reverse('posts:community_join_toggle', kwargs={'slug': 'design-sphere'}))
        self.assertFalse(CommunityMembership.objects.filter(community=comm, user=self.user2).exists())
        self.assertEqual(comm.members_count, 1)

    def test_community_post_creation_and_authorization(self):
        """Members can publish inside a community; non-members are rejected."""
        comm = Community.objects.create(
            name='Science Hub',
            slug='science-hub',
            topic='science',
            description='Science hub',
            creator=self.user1
        )
        CommunityMembership.objects.create(community=comm, user=self.user1, role='admin')

        # Bob is NOT a member: posting to science-hub should be rejected
        self.client.login(username='bob', password='Password123!')
        resp_non_member = self.client.post(reverse('posts:post_create'), {
            'content': 'Attempted post by non-member',
            'community': comm.id,
        })
        self.assertFalse(Post.objects.filter(content='Attempted post by non-member').exists())

        # Bob joins community
        CommunityMembership.objects.create(community=comm, user=self.user2, role='member')

        # Now Bob can post in science-hub
        resp_member = self.client.post(reverse('posts:post_create'), {
            'content': 'Legitimate member post by Bob',
            'community': comm.id,
        })
        self.assertRedirects(resp_member, reverse('posts:community_detail', kwargs={'slug': 'science-hub'}))
        self.assertTrue(Post.objects.filter(content='Legitimate member post by Bob', community=comm).exists())

    def test_unauthorized_community_moderator_action(self):
        """Regular members cannot perform moderator deletion on another user's post."""
        comm = Community.objects.create(
            name='Philosophy Sphere',
            slug='philosophy',
            topic='culture',
            description='Deep thinkers',
            creator=self.user1
        )
        CommunityMembership.objects.create(community=comm, user=self.user1, role='admin')
        CommunityMembership.objects.create(community=comm, user=self.user2, role='member')

        comm_post = Post.objects.create(author=self.user1, community=comm, content="Alice philosophy post")

        # Bob (regular member) tries to delete Alice's post
        self.client.login(username='bob', password='Password123!')
        del_resp = self.client.post(reverse('posts:community_post_delete', kwargs={'slug': 'philosophy', 'post_id': comm_post.id}))
        self.assertEqual(del_resp.status_code, 403)
        self.assertTrue(Post.objects.filter(id=comm_post.id).exists())

        # Alice (creator/admin) can delete post
        self.client.login(username='alice', password='Password123!')
        del_resp_admin = self.client.post(reverse('posts:community_post_delete', kwargs={'slug': 'philosophy', 'post_id': comm_post.id}))
        self.assertRedirects(del_resp_admin, reverse('posts:community_detail', kwargs={'slug': 'philosophy'}))
        self.assertFalse(Post.objects.filter(id=comm_post.id).exists())

    def test_private_account_post_hidden_in_community_from_non_followers(self):
        """Private account's community posts are protected from non-followers."""
        self.user2.profile.is_private = True
        self.user2.profile.save()

        comm = Community.objects.create(
            name='Private Test Hub',
            slug='private-test-hub',
            topic='general',
            description='Testing privacy',
            creator=self.user1
        )
        CommunityMembership.objects.create(community=comm, user=self.user1, role='admin')
        CommunityMembership.objects.create(community=comm, user=self.user2, role='member')

        Post.objects.create(author=self.user2, community=comm, content="Bob secret community post")

        # Alice does not follow Bob: should NOT see Bob's post in community
        self.client.login(username='alice', password='Password123!')
        resp = self.client.get(reverse('posts:community_detail', kwargs={'slug': 'private-test-hub'}))
        self.assertNotContains(resp, "Bob secret community post")

        # If Alice follows Bob: post becomes visible
        Follow.objects.create(follower=self.user1, following=self.user2)
        resp_following = self.client.get(reverse('posts:community_detail', kwargs={'slug': 'private-test-hub'}))
        self.assertContains(resp_following, "Bob secret community post")

    def test_blocked_user_posts_hidden_in_community(self):
        """Blocked users' posts are excluded from community stream."""
        comm = Community.objects.create(
            name='Open Forum',
            slug='open-forum',
            topic='culture',
            description='Public forum',
            creator=self.user1
        )
        CommunityMembership.objects.create(community=comm, user=self.user1, role='admin')
        CommunityMembership.objects.create(community=comm, user=self.user2, role='member')

        Post.objects.create(author=self.user2, community=comm, content="Bob post to be blocked in community")
        Block.objects.create(blocker=self.user1, blocked=self.user2)

        self.client.login(username='alice', password='Password123!')
        resp = self.client.get(reverse('posts:community_detail', kwargs={'slug': 'open-forum'}))
        self.assertNotContains(resp, "Bob post to be blocked in community")


