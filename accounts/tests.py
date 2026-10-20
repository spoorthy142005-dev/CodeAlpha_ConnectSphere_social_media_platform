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
