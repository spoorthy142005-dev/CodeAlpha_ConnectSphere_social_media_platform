from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from .forms import UserRegistrationForm, ProfileEditForm
from .models import Profile
from social.models import Follow, Block
from social.utils import get_blocked_user_ids, is_blocked_relationship


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
    if not is_self:
        is_following = Follow.objects.filter(follower=viewer, following=target_user).exists()

    # Privacy logic: if private, viewer must be target or following
    can_view_content = is_self or (not target_user.profile.is_private) or is_following

    posts = []
    page_obj = None
    if can_view_content:
        posts_qs = target_user.posts.select_related('author', 'author__profile').prefetch_related('likes', 'comments').all()
        paginator = Paginator(posts_qs, 10)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)

    return render(request, 'accounts/profile.html', {
        'target_user': target_user,
        'profile': target_user.profile,
        'is_self': is_self,
        'is_following': is_following,
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
