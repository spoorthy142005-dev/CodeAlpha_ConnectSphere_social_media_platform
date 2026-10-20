from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
import json

from .forms import UserRegistrationForm, ProfileEditForm, PrivacySettingsForm, AccountDeleteForm
from .models import Profile
from social.models import Follow, Block, Mute, Bookmark
from social.utils import get_blocked_user_ids, is_blocked_relationship, get_muted_user_ids


def register_view(request):
    if request.user.is_authenticated:
        return redirect('posts:feed')

    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.set_password(form.cleaned_data['password'])
            user.save()
            messages.success(request, f"Welcome to ConnectSphere, @{user.username}! Your account has been created.")
            login(request, user)
            return redirect('posts:feed')
        else:
            messages.error(request, "Please correct the errors below to register.")
    else:
        form = UserRegistrationForm()

    return render(request, 'accounts/register.html', {'form': form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect('posts:feed')

    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f"Welcome back, @{user.username}!")
            next_url = request.POST.get('next') or request.GET.get('next')
            if next_url and next_url.startswith('/'):
                return redirect(next_url)
            return redirect('posts:feed')
        else:
            messages.error(request, "Invalid username or password.")
    else:
        form = AuthenticationForm(request)

    return render(request, 'accounts/login.html', {'form': form})


def logout_view(request):
    if request.method in ['POST', 'GET']:
        logout(request)
        messages.info(request, "You have been logged out successfully.")
    return redirect('accounts:login')


@login_required
def profile_detail_view(request, username):
    target_user = get_object_or_404(User.objects.select_related('profile'), username=username)
    viewer = request.user
    is_self = (viewer.id == target_user.id)

    # Check blocking
    blocked_ids = get_blocked_user_ids(viewer)
    is_blocked_by_viewer = Block.objects.filter(blocker=viewer, blocked=target_user).exists()
    is_blocked_by_target = Block.objects.filter(blocker=target_user, blocked=viewer).exists()

    if not is_self and (is_blocked_by_viewer or is_blocked_by_target):
        return render(request, 'accounts/profile.html', {
            'target_user': target_user,
            'is_self': False,
            'is_blocked': True,
            'is_blocked_by_viewer': is_blocked_by_viewer,
            'is_blocked_by_target': is_blocked_by_target,
            'posts': [],
        })

    is_following = False
    is_muted = False
    if not is_self:
        is_following = Follow.objects.filter(follower=viewer, following=target_user).exists()
        is_muted = Mute.objects.filter(muter=viewer, muted=target_user).exists()

    # Privacy logic: if private, viewer must be target or following
    can_view_content = is_self or (not target_user.profile.is_private) or is_following

    posts = []
    page_obj = None
    if can_view_content:
        posts_qs = target_user.posts.select_related('author', 'author__profile', 'community').prefetch_related('likes', 'comments').all()
        if not is_self:
            allowed_audiences = ['public']
            if is_following:
                allowed_audiences.append('followers')
            viewer_community_ids = viewer.community_memberships.values_list('community_id', flat=True)
            posts_qs = posts_qs.filter(
                Q(audience__in=allowed_audiences) |
                Q(audience='community', community_id__in=viewer_community_ids)
            )

        paginator = Paginator(posts_qs, 10)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)

    return render(request, 'accounts/profile.html', {
        'target_user': target_user,
        'profile': target_user.profile,
        'is_self': is_self,
        'is_following': is_following,
        'is_muted': is_muted,
        'is_blocked': False,
        'is_blocked_by_viewer': False,
        'can_view_content': can_view_content,
        'page_obj': page_obj,
    })


@login_required
def profile_edit_view(request):
    profile = request.user.profile
    if request.method == 'POST':
        form = ProfileEditForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, "Your profile has been updated.")
            return redirect('accounts:profile_detail', username=request.user.username)
        else:
            messages.error(request, "Failed to update profile. Please verify all fields.")
    else:
        form = ProfileEditForm(instance=profile)

    return render(request, 'accounts/profile_edit.html', {'form': form})


@login_required
def user_search_view(request):
    query = request.GET.get('q', '').strip()
    blocked_ids = get_blocked_user_ids(request.user)

    results = []
    if query:
        results = User.objects.select_related('profile').filter(
            Q(username__icontains=query) | Q(profile__display_name__icontains=query)
        ).exclude(id=request.user.id).exclude(id__in=blocked_ids)[:30]

    # Annotate following status
    following_ids = set(request.user.following_set.values_list('following_id', flat=True))
    for u in results:
        u.is_following = u.id in following_ids

    return render(request, 'accounts/user_search.html', {
        'query': query,
        'results': results,
    })


@login_required
def privacy_center_view(request):
    """
    ConnectSphere Privacy Control Center & Content Wellbeing dashboard.
    Manages account visibility, default audience, notification categories,
    quiet hours, blocked accounts, muted accounts, and muted topics.
    """
    profile = request.user.profile

    if request.method == 'POST':
        form = PrivacySettingsForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, "Your privacy and content wellbeing preferences have been saved.")
            return redirect('accounts:privacy_center')
        else:
            messages.error(request, "Failed to save privacy settings. Please check your inputs.")
    else:
        form = PrivacySettingsForm(instance=profile)

    blocked_records = Block.objects.filter(blocker=request.user).select_related('blocked', 'blocked__profile')
    muted_records = Mute.objects.filter(muter=request.user).select_related('muted', 'muted__profile')
    muted_topics = getattr(profile, 'muted_topics', [])

    return render(request, 'accounts/privacy_center.html', {
        'form': form,
        'profile': profile,
        'blocked_records': blocked_records,
        'muted_records': muted_records,
        'muted_topics': muted_topics,
        'followers_count': request.user.follower_set.count(),
        'following_count': request.user.following_set.count(),
        'posts_count': request.user.posts.count(),
    })


@login_required
def data_export_view(request):
    """
    Generate an authenticated personal data export in structured JSON format.
    Strictly excludes sensitive credentials (passwords, hashes, tokens, keys)
    and exports only authorized personal data.
    """
    user = request.user
    profile = user.profile
    now = timezone.now()

    # Collect user's posts
    posts_data = []
    for post in user.posts.select_related('community').prefetch_related('likes', 'comments').all():
        posts_data.append({
            'id': post.id,
            'content': post.content,
            'topic': post.topic,
            'audience': post.audience,
            'community': post.community.slug if post.community else None,
            'created_at': post.created_at.isoformat(),
            'updated_at': post.updated_at.isoformat(),
            'likes_count': post.likes.count(),
            'comments_count': post.comments.count(),
            'image_url': request.build_absolute_uri(post.image.url) if post.image else None,
        })

    # Collect user's comments
    comments_data = []
    for comment in user.comments.select_related('post', 'post__author').all():
        comments_data.append({
            'id': comment.id,
            'post_id': comment.post_id,
            'post_author': comment.post.author.username,
            'content': comment.content,
            'created_at': comment.created_at.isoformat(),
        })

    # Collect following relationships
    following_data = [
        {
            'username': f.following.username,
            'display_name': getattr(f.following.profile, 'display_name', ''),
            'followed_at': f.created_at.isoformat(),
        }
        for f in user.following_set.select_related('following', 'following__profile')
    ]

    # Collect follower relationships
    followers_data = [
        {
            'username': f.follower.username,
            'display_name': getattr(f.follower.profile, 'display_name', ''),
            'followed_at': f.created_at.isoformat(),
        }
        for f in user.follower_set.select_related('follower', 'follower__profile')
    ]

    # Collect bookmarks
    bookmarks_data = [
        {
            'post_id': b.post_id,
            'post_author': b.post.author.username,
            'content_snippet': b.post.content[:100],
            'saved_at': b.created_at.isoformat(),
        }
        for b in user.bookmarks.select_related('post', 'post__author')
    ]

    # Collect community memberships
    communities_data = [
        {
            'name': m.community.name,
            'slug': m.community.slug,
            'role': m.role,
            'joined_at': m.joined_at.isoformat(),
        }
        for m in user.community_memberships.select_related('community')
    ]

    # Collect blocked accounts
    blocked_data = [
        {
            'username': b.blocked.username,
            'blocked_at': b.created_at.isoformat(),
        }
        for b in user.blocking_set.select_related('blocked')
    ]

    # Collect muted accounts
    muted_data = [
        {
            'username': m.muted.username,
            'muted_at': m.created_at.isoformat(),
        }
        for m in user.muting_set.select_related('muted')
    ]

    export_payload = {
        'export_metadata': {
            'application': 'ConnectSphere',
            'format_version': '1.0',
            'generated_at': now.isoformat(),
            'description': 'ConnectSphere User Data Archive (Self-Service Data Ownership)',
        },
        'account': {
            'username': user.username,
            'email': user.email,
            'date_joined': user.date_joined.isoformat(),
            'last_login': user.last_login.isoformat() if user.last_login else None,
        },
        'profile': {
            'display_name': profile.display_name,
            'bio': profile.bio,
            'is_private': profile.is_private,
            'default_post_audience': profile.default_post_audience,
            'default_feed_mode': profile.default_feed_mode,
            'low_bandwidth': profile.low_bandwidth,
            'muted_topics': profile.muted_topics,
            'created_at': profile.created_at.isoformat(),
            'avatar_url': request.build_absolute_uri(profile.avatar.url) if profile.avatar else None,
        },
        'privacy_and_notification_preferences': {
            'notify_follows': profile.notify_follows,
            'notify_likes': profile.notify_likes,
            'notify_comments': profile.notify_comments,
            'notify_communities': profile.notify_communities,
            'notifications_paused': profile.notifications_paused,
            'quiet_hours_enabled': profile.quiet_hours_enabled,
            'quiet_hours_start': profile.quiet_hours_start.strftime("%H:%M") if profile.quiet_hours_start else None,
            'quiet_hours_end': profile.quiet_hours_end.strftime("%H:%M") if profile.quiet_hours_end else None,
        },
        'posts': posts_data,
        'comments': comments_data,
        'following': following_data,
        'followers': followers_data,
        'bookmarks': bookmarks_data,
        'communities': communities_data,
        'blocked_users': blocked_data,
        'muted_users': muted_data,
    }

    json_content = json.dumps(export_payload, indent=2, ensure_ascii=False)
    filename = f"connectsphere_export_{user.username}_{now.strftime('%Y%m%d_%H%M%S')}.json"

    response = HttpResponse(json_content, content_type='application/json; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@login_required
def account_delete_view(request):
    """
    Safe account deletion workflow with authentication, username re-entry,
    and explicit checkbox confirmation. Revokes session and removes personal data
    while preserving shared community discussion hubs (via SET_NULL creator).
    """
    user = request.user

    if request.method == 'POST':
        form = AccountDeleteForm(request.POST, user=user)
        if form.is_valid():
            username = user.username
            logout(request)
            user.delete()
            messages.info(request, f"Your account @{username} has been permanently deleted. We are sorry to see you go!")
            return redirect('accounts:login')
        else:
            messages.error(request, "Account deletion failed. Please ensure all confirmation details are correct.")
    else:
        form = AccountDeleteForm(user=user)

    return render(request, 'accounts/account_delete_confirm.html', {
        'form': form,
        'posts_count': user.posts.count(),
        'comments_count': user.comments.count(),
        'followers_count': user.follower_set.count(),
        'communities_count': user.community_memberships.count(),
    })
