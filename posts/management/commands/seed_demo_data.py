from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from posts.models import Post, Comment, Like
from social.models import Follow, Bookmark
from notifications.utils import create_notification


class Command(BaseCommand):
    help = "Seeds ConnectSphere with initial users, posts, comments, follows, and bookmarks for evaluation."

    def handle(self, *args, **options):
        self.stdout.write("Seeding ConnectSphere demonstration data...")

        # 1. Create Superuser / Moderator
        admin_user, created = User.objects.get_or_create(
            username='admin',
            defaults={
                'email': 'admin@connectsphere.local',
                'is_staff': True,
                'is_superuser': True,
            }
        )
        admin_user.set_password('Admin@12345')
        admin_user.save()
        admin_user.profile.display_name = 'ConnectSphere Admin'
        admin_user.profile.bio = 'Official platform administration and Trust & Safety moderation team.'
        admin_user.profile.save()

        # 2. Create Demo Users
        users_data = [
            {
                'username': 'sophia_dev',
                'email': 'sophia@connectsphere.local',
                'name': 'Sophia Chen',
                'bio': 'Senior Full-Stack Architect & Python enthusiast. Passionate about clean code, distributed systems, and open web standards.',
                'private': False,
            },
            {
                'username': 'marcus_ai',
                'email': 'marcus@connectsphere.local',
                'name': 'Marcus Vance',
                'bio': 'AI/ML researcher exploring generative agents and conversational reasoning. Coffee, robotics, and open science.',
                'private': False,
            },
            {
                'username': 'elena_design',
                'email': 'elena@connectsphere.local',
                'name': 'Elena Rostova',
                'bio': 'Principal Product Designer. Crafting accessible, delightful design systems with typography that speaks.',
                'private': False,
            },
            {
                'username': 'alex_coder',
                'email': 'alex@connectsphere.local',
                'name': 'Alex Rivera',
                'bio': 'DevOps & Site Reliability Engineer. Making deployments boring and pipelines rock-solid.',
                'private': True,  # Private account demo
            }
        ]

        created_users = {}
        for u in users_data:
            user_obj, _ = User.objects.get_or_create(
                username=u['username'],
                defaults={'email': u['email']}
            )
            user_obj.set_password('Password@123')
            user_obj.save()
            user_obj.profile.display_name = u['name']
            user_obj.profile.bio = u['bio']
            user_obj.profile.is_private = u['private']
            user_obj.profile.save()
            created_users[u['username']] = user_obj

        # 3. Create Follow Relationships
        Follow.objects.get_or_create(follower=created_users['sophia_dev'], following=created_users['marcus_ai'])
        Follow.objects.get_or_create(follower=created_users['sophia_dev'], following=created_users['elena_design'])
        Follow.objects.get_or_create(follower=created_users['marcus_ai'], following=created_users['sophia_dev'])
        Follow.objects.get_or_create(follower=created_users['elena_design'], following=created_users['sophia_dev'])
        Follow.objects.get_or_create(follower=created_users['elena_design'], following=created_users['marcus_ai'])
        Follow.objects.get_or_create(follower=created_users['alex_coder'], following=created_users['sophia_dev'])

        # 4. Create Engaging Posts
        posts_data = [
            (
                'sophia_dev',
                "Welcome to ConnectSphere! 🚀 Built with Django and modern vanilla web craftsmanship. No bloated client frameworks, just lightning-fast server rendering, accessible semantic markup, and reliable session authentication."
            ),
            (
                'marcus_ai',
                "Exciting breakthrough in local reasoning models today! Running small language models with constrained decoding allows real-time structured data output without high-latency cloud roundtrips."
            ),
            (
                'elena_design',
                "Design tip for web platforms: High contrast ratios, comfortable whitespace, and clear focus states aren't just accessibility checkboxes — they make the experience 10x more trustworthy for all users."
            ),
            (
                'sophia_dev',
                "Writing automated test suites in Django: from database constraint verification to HTTP access control tests, having 100% passing tests brings unmatched peace of mind during deployments."
            ),
            (
                'alex_coder',
                "Private update: Our infrastructure automation scripts just reached sub-minute deployment speeds. Loving the stability!"
            )
        ]

        created_posts = []
        for author_username, content in posts_data:
            author = created_users[author_username]
            post, _ = Post.objects.get_or_create(
                author=author,
                content=content,
            )
            created_posts.append(post)

        # 5. Add Likes & Comments
        if created_posts:
            # Likes
            Like.objects.get_or_create(user=created_users['marcus_ai'], post=created_posts[0])
            Like.objects.get_or_create(user=created_users['elena_design'], post=created_posts[0])
            Like.objects.get_or_create(user=created_users['sophia_dev'], post=created_posts[1])
            Like.objects.get_or_create(user=created_users['sophia_dev'], post=created_posts[2])

            # Comments
            c1, _ = Comment.objects.get_or_create(
                author=created_users['marcus_ai'],
                post=created_posts[0],
                content="Spot on, Sophia. The snappy page loads and clean typography make this feel exceptionally polished!"
            )
            c2, _ = Comment.objects.get_or_create(
                author=created_users['elena_design'],
                post=created_posts[0],
                content="The blue accent palette and card hierarchy feel so cohesive."
            )

            # Notifications
            create_notification(recipient=created_users['sophia_dev'], actor=created_users['marcus_ai'], event_type='like', post=created_posts[0])
            create_notification(recipient=created_users['sophia_dev'], actor=created_users['elena_design'], event_type='comment', post=created_posts[0], comment=c2)

            # Bookmarks
            Bookmark.objects.get_or_create(user=created_users['sophia_dev'], post=created_posts[2])
            Bookmark.objects.get_or_create(user=created_users['marcus_ai'], post=created_posts[0])

        self.stdout.write(self.style.SUCCESS("Successfully seeded demonstration data!"))
        self.stdout.write("Credentials:")
        self.stdout.write("  Admin:      username: admin        / password: Admin@12345")
        self.stdout.write("  User 1:     username: sophia_dev   / password: Password@123")
        self.stdout.write("  User 2:     username: marcus_ai    / password: Password@123")
        self.stdout.write("  User 3:     username: elena_design / password: Password@123")
        self.stdout.write("  User 4:     username: alex_coder   / password: Password@123 (Private account)")
