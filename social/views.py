from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.http import require_POST
from django.core.paginator import Paginator
from .models import Follow, Bookmark, Block
from posts.models import Post
from notifications.utils import create_notification
from .utils import is_blocked_relationship


@login_required
@require_POST
def follow_toggle_view(request, username):
    target_user = get_object_or_404(User, username=username)

    if target_user == request.user:
        messages.error(request, "You cannot follow yourself.")
        return HttpResponseBadRequest("Cannot follow self.")

    # Check blocked
    if is_blocked_relationship(request.user, target_user):
        messages.error(request, "Cannot follow a user with an active block.")
        return HttpResponseBadRequest("Blocked relationship.")

    existing_follow = Follow.objects.filter(follower=request.user, following=target_user).first()
    if existing_follow:
        existing_follow.delete()
        is_following = False
        messages.info(request, f"You have unfollowed @{target_user.username}.")
    else:
        Follow.objects.create(follower=request.user, following=target_user)
        is_following = True
        create_notification(recipient=target_user, actor=request.user, event_type='follow')
        messages.success(request, f"You are now following @{target_user.username}!")

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'is_following': is_following,
            'followers_count': target_user.follower_set.count(),
        })

    return redirect(request.META.get('HTTP_REFERER') or 'accounts:profile_detail', username=target_user.username)


@login_required
def followers_list_view(request, username):
    target_user = get_object_or_404(User, username=username)
    followers_qs = User.objects.filter(following_set__following=target_user).select_related('profile')

    # Annotate whether current user follows each
    my_following = set(request.user.following_set.values_list('following_id', flat=True))
    for u in followers_qs:
        u.is_followed_by_me = u.id in my_following

    return render(request, 'social/follow_list.html', {
        'target_user': target_user,
        'user_list': followers_qs,
        'list_type': 'Followers',
    })


@login_required
def following_list_view(request, username):
    target_user = get_object_or_404(User, username=username)
    following_qs = User.objects.filter(follower_set__follower=target_user).select_related('profile')

    my_following = set(request.user.following_set.values_list('following_id', flat=True))
    for u in following_qs:
        u.is_followed_by_me = u.id in my_following

    return render(request, 'social/follow_list.html', {
        'target_user': target_user,
        'user_list': following_qs,
        'list_type': 'Following',
    })


@login_required
@require_POST
def bookmark_toggle_view(request, post_id):
    post = get_object_or_404(Post, id=post_id)

    if is_blocked_relationship(request.user, post.author):
        messages.error(request, "Cannot bookmark this post.")
        return HttpResponseBadRequest("Blocked content.")

    bookmark = Bookmark.objects.filter(user=request.user, post=post).first()
    if bookmark:
        bookmark.delete()
        is_bookmarked = False
        messages.info(request, "Post removed from your saved bookmarks.")
    else:
        Bookmark.objects.get_or_create(user=request.user, post=post)
        is_bookmarked = True
        messages.success(request, "Post saved to your bookmarks.")

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'is_bookmarked': is_bookmarked,
        })

    return redirect(request.META.get('HTTP_REFERER') or 'posts:feed')


@login_required
def saved_posts_view(request):
    """View bookmarks - only accessible to the logged-in user for their own saved posts."""
    bookmarks = Bookmark.objects.filter(user=request.user).select_related('post', 'post__author', 'post__author__profile')
    posts = [b.post for b in bookmarks]

    paginator = Paginator(posts, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'social/saved_posts.html', {
        'page_obj': page_obj,
    })


@login_required
@require_POST
def block_toggle_view(request, username):
    target_user = get_object_or_404(User, username=username)

    if target_user == request.user:
        messages.error(request, "You cannot block yourself.")
        return HttpResponseBadRequest("Cannot block self.")

    existing_block = Block.objects.filter(blocker=request.user, blocked=target_user).first()
    if existing_block:
        existing_block.delete()
        messages.info(request, f"You have unblocked @{target_user.username}.")
    else:
        Block.objects.create(blocker=request.user, blocked=target_user)
        # Clean up any existing follow relationships in both directions
        Follow.objects.filter(follower=request.user, following=target_user).delete()
        Follow.objects.filter(follower=target_user, following=request.user).delete()
        messages.success(request, f"You have blocked @{target_user.username}. Their content will no longer be visible.")

    return redirect('accounts:profile_detail', username=target_user.username)


@login_required
def blocked_users_view(request):
    """Settings page to manage blocked accounts."""
    blocked_records = Block.objects.filter(blocker=request.user).select_related('blocked', 'blocked__profile')
    return render(request, 'social/blocked_users.html', {
        'blocked_records': blocked_records,
    })
