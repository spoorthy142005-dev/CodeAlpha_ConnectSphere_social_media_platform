import io
import os
import shutil
import sqlite3
import tarfile
import tempfile
from PIL import Image

from django.test import TestCase, Client, override_settings
from django.contrib.auth.models import User
from django.urls import reverse
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile

from accounts.models import validate_avatar_file
from posts.models import Post, Community, CommunityMembership, validate_post_image, validate_community_icon


class Phase5CSRFAndSecurityTests(TestCase):
    """Verifies strict CSRF protection and server-side request boundaries."""

    def setUp(self):
        self.user = User.objects.create_user(username='csrf_user', password='Password123!', email='csrf@test.com')

    def test_state_changing_post_without_csrf_is_rejected(self):
        """CSRF enforcement blocks unauthorized state-changing POST requests with 403."""
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.login(username='csrf_user', password='Password123!')

        # Attempt to create post without CSRF token
        response = csrf_client.post(reverse('posts:post_create'), {'content': 'Unprotected post attempt'})
        self.assertEqual(response.status_code, 403)

    def test_state_changing_post_with_csrf_succeeds(self):
        """Standard client with CSRF token successfully creates content."""
        self.client.login(username='csrf_user', password='Password123!')
        response = self.client.post(reverse('posts:post_create'), {
            'content': 'Authorized post with valid CSRF',
            'audience': 'public'
        })
        self.assertRedirects(response, reverse('posts:feed'))
        self.assertTrue(Post.objects.filter(content='Authorized post with valid CSRF').exists())


class Phase5ServerSideUploadCeilingTests(TestCase):
    """Verifies that file uploads exceeding limits or containing invalid payloads are rejected."""

    def test_middleware_rejects_payload_exceeding_5mb(self):
        """MaxUploadSizeMiddleware rejects oversized requests (>5MB) with HTTP 413 before parsing."""
        client = Client()
        # Simulate an incoming multipart upload with Content-Length = 6MB
        oversized_bytes = 6 * 1024 * 1024
        response = client.post(
            reverse('posts:post_create'),
            data={'content': 'oversized upload'},
            CONTENT_LENGTH=str(oversized_bytes),
            CONTENT_TYPE='multipart/form-data; boundary=BoUnDaRy'
        )
        self.assertEqual(response.status_code, 413)
        self.assertIn(b"Maximum allowed upload size is 5MB", response.content)

    def test_middleware_handles_malformed_content_length(self):
        """MaxUploadSizeMiddleware handles malformed or non-numeric Content-Length gracefully."""
        client = Client()
        response = client.post(
            reverse('accounts:login'),
            data={'username': 'test', 'password': 'pwd'},
            CONTENT_LENGTH='malformed_non_integer'
        )
        self.assertIn(response.status_code, [200, 302])

    def test_middleware_allows_normal_form_submission(self):
        """MaxUploadSizeMiddleware allows normal form submissions with small Content-Length."""
        client = Client()
        response = client.post(
            reverse('accounts:login'),
            data={'username': 'test', 'password': 'pwd'},
            CONTENT_LENGTH='128'
        )
        self.assertNotEqual(response.status_code, 413)

    def test_post_image_validator_rejects_over_5mb(self):
        """validate_post_image raises ValidationError for files > 5MB."""
        large_content = b'0' * (5 * 1024 * 1024 + 10)
        uploaded = SimpleUploadedFile("too_large.jpg", large_content, content_type="image/jpeg")
        with self.assertRaises(ValidationError) as ctx:
            validate_post_image(uploaded)
        self.assertIn("cannot exceed 5MB", str(ctx.exception))

    def test_avatar_validator_rejects_over_2mb(self):
        """validate_avatar_file raises ValidationError for avatars > 2MB."""
        large_avatar = b'0' * (2 * 1024 * 1024 + 10)
        uploaded = SimpleUploadedFile("big_avatar.png", large_avatar, content_type="image/png")
        with self.assertRaises(ValidationError) as ctx:
            validate_avatar_file(uploaded)
        self.assertIn("under 2MB", str(ctx.exception))

    def test_disguised_executable_rejected_by_image_verification(self):
        """Files with .jpg extension containing executable/shellcode fail PIL verification."""
        fake_image = SimpleUploadedFile(
            "malicious.jpg",
            b"#!/bin/bash\necho 'exploit'\n<?php phpinfo(); ?>",
            content_type="image/jpeg"
        )
        with self.assertRaises(ValidationError) as ctx:
            validate_post_image(fake_image)
        self.assertIn("not a valid or readable image", str(ctx.exception))

    def test_valid_image_binary_passes_validation(self):
        """Valid image binaries pass both size and structure verification."""
        img_io = io.BytesIO()
        img = Image.new('RGB', (100, 100), color='blue')
        img.save(img_io, format='JPEG')
        img_io.seek(0)
        valid_file = SimpleUploadedFile("valid.jpg", img_io.read(), content_type="image/jpeg")
        # Should not raise
        validate_post_image(valid_file)


class Phase5ErrorPagesAndSecurityHardeningTests(TestCase):
    """Tests custom error rendering and production security behavior under DEBUG=False."""

    @override_settings(DEBUG=False)
    def test_404_page_renders_branded_template(self):
        """Nonexistent paths render branded ConnectSphere 404 page."""
        response = self.client.get('/definitely-nonexistent-route-for-404-test/', secure=True)
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "Page Not Found", status_code=404)
        self.assertContains(response, "Back to Home Feed", status_code=404)

    @override_settings(DEBUG=False)
    def test_403_page_renders_branded_template(self):
        """Direct invocation of permission denied renders branded 403 template."""
        from django.views.defaults import permission_denied
        from django.test import RequestFactory
        factory = RequestFactory()
        req = factory.get('/', secure=True)
        # Note: request.user may not exist in early 403 handlers; tests our defensive context processor
        response = permission_denied(req, Exception("Access Denied"))
        self.assertEqual(response.status_code, 403)
        self.assertContains(response, "Access Forbidden", status_code=403)
        self.assertContains(response, "Review Privacy Settings", status_code=403)

    @override_settings(DEBUG=False)
    def test_500_page_renders_standalone_template(self):
        """Server error renders completely standalone 500 template without context dependency."""
        from django.views.defaults import server_error
        from django.test import RequestFactory
        factory = RequestFactory()
        req = factory.get('/', secure=True)
        response = server_error(req)
        self.assertEqual(response.status_code, 500)
        self.assertContains(response, "Something Went Wrong (500)", status_code=500)


class Phase5IsolatedBackupAndDisasterRecoveryTests(TestCase):
    """Verifies database and media backup/restore mechanisms using isolated temporary environments."""

    def test_isolated_sqlite_backup_and_restore(self):
        """Validates online SQLite backup API in an isolated temporary location."""
        temp_dir = tempfile.mkdtemp()
        try:
            source_path = os.path.join(temp_dir, 'source.sqlite3')
            backup_path = os.path.join(temp_dir, 'backup.sqlite3')

            # Create source database with test records
            src_conn = sqlite3.connect(source_path)
            src_conn.execute("CREATE TABLE backup_test (id INTEGER PRIMARY KEY, note TEXT);")
            src_conn.execute("INSERT INTO backup_test (note) VALUES ('Disaster recovery validation');")
            src_conn.commit()

            # Execute online SQLite backup API
            dst_conn = sqlite3.connect(backup_path)
            src_conn.backup(dst_conn)
            dst_conn.close()
            src_conn.close()

            # Verify integrity of backup
            verify_conn = sqlite3.connect(backup_path)
            cursor = verify_conn.cursor()
            cursor.execute("SELECT note FROM backup_test WHERE id = 1;")
            row = cursor.fetchone()
            verify_conn.close()

            self.assertIsNotNone(row)
            self.assertEqual(row[0], 'Disaster recovery validation')
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_isolated_media_archive_and_extraction(self):
        """Validates media directory packaging and full extraction integrity in an isolated location."""
        temp_dir = tempfile.mkdtemp()
        try:
            isolated_media = os.path.join(temp_dir, 'media')
            avatars_dir = os.path.join(isolated_media, 'avatars', '2026', '10')
            os.makedirs(avatars_dir, exist_ok=True)

            sample_file = os.path.join(avatars_dir, 'avatar_sample.jpg')
            sample_payload = b'SIMULATED_BINARY_IMAGE_DATA_12345'
            with open(sample_file, 'wb') as f:
                f.write(sample_payload)

            # Archive
            tar_archive = os.path.join(temp_dir, 'media_backup.tar.gz')
            with tarfile.open(tar_archive, 'w:gz') as tar:
                tar.add(isolated_media, arcname='media')
            self.assertTrue(os.path.exists(tar_archive))

            # Restore into clean directory
            restore_target = os.path.join(temp_dir, 'restored')
            os.makedirs(restore_target, exist_ok=True)
            with tarfile.open(tar_archive, 'r:gz') as tar:
                tar.extractall(restore_target)

            restored_sample = os.path.join(restore_target, 'media', 'avatars', '2026', '10', 'avatar_sample.jpg')
            self.assertTrue(os.path.exists(restored_sample))
            with open(restored_sample, 'rb') as f:
                self.assertEqual(f.read(), sample_payload)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


class Phase5EndToEndJourneyTests(TestCase):
    """Comprehensive end-to-end user workflow: register, post, community, privacy, and cleanup."""

    def test_end_to_end_user_lifecycle(self):
        """Tests the full multi-feature lifecycle of an active ConnectSphere member."""
        # 1. Register new user
        reg_response = self.client.post(reverse('accounts:register'), {
            'username': 'e2e_sam',
            'email': 'sam@example.com',
            'password': 'SecureE2EPassword123!',
            'password_confirm': 'SecureE2EPassword123!',
        })
        self.assertRedirects(reg_response, reverse('posts:feed'))
        user = User.objects.get(username='e2e_sam')
        self.assertTrue(hasattr(user, 'profile'))

        # 2. Update profile with bio and low-bandwidth mode
        self.client.login(username='e2e_sam', password='SecureE2EPassword123!')
        edit_resp = self.client.post(reverse('accounts:profile_edit'), {
            'display_name': 'Sam Developer',
            'bio': 'End-to-End verified user',
            'low_bandwidth': True,
        })
        self.assertRedirects(edit_resp, reverse('accounts:profile_detail', kwargs={'username': 'e2e_sam'}))
        user.profile.refresh_from_db()
        self.assertEqual(user.profile.display_name, 'Sam Developer')
        self.assertTrue(user.profile.low_bandwidth)

        # 3. Create a community
        comm_resp = self.client.post(reverse('posts:community_create'), {
            'name': 'Cloud Engineers',
            'slug': 'cloud-engineers',
            'topic': 'technology',
            'description': 'DevOps, CI/CD, and Cloud Architecture discussions.',
        })
        self.assertRedirects(comm_resp, reverse('posts:community_detail', kwargs={'slug': 'cloud-engineers'}))
        community = Community.objects.get(slug='cloud-engineers')
        self.assertEqual(community.creator, user)
        self.assertTrue(CommunityMembership.objects.filter(community=community, user=user, role='admin').exists())

        # 4. Post in community
        post_resp = self.client.post(reverse('posts:post_create'), {
            'content': 'Welcome to the Cloud Engineers sphere!',
            'community': community.id,
            'audience': 'community',
            'topic': 'technology',
        })
        self.assertRedirects(post_resp, reverse('posts:community_detail', kwargs={'slug': 'cloud-engineers'}))
        post = Post.objects.get(content='Welcome to the Cloud Engineers sphere!')
        self.assertEqual(post.community, community)

        # 5. Comment on post
        comment_resp = self.client.post(reverse('posts:comment_create', kwargs={'post_id': post.pk}), {
            'content': 'First constructive comment in community post.',
        })
        self.assertRedirects(comment_resp, reverse('posts:post_detail', kwargs={'post_id': post.pk}))
        self.assertEqual(post.comments.count(), 1)

        # 6. Bookmark post via AJAX
        bm_resp = self.client.post(
            reverse('social:bookmark_toggle', kwargs={'post_id': post.pk}),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(bm_resp.status_code, 200)
        self.assertTrue(bm_resp.json()['is_bookmarked'])

        # 7. Data export
        export_resp = self.client.get(reverse('accounts:data_export'))
        self.assertEqual(export_resp.status_code, 200)
        self.assertIn('application/json', export_resp['Content-Type'])

        # 8. Logout
        logout_resp = self.client.post(reverse('accounts:logout'))
        self.assertRedirects(logout_resp, reverse('accounts:login'))
