from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.http import JsonResponse, HttpResponseForbidden, Http404
from django.views.decorators.http import require_POST
from django.db.models import Q
from .models import Post, Like, Comment
from .forms import PostCreateForm, PostEditForm, CommentForm
from social.models import Follow
from social.utils import get_blocked_user_ids, is_blocked_relationship
from notifications.utils import create_notification


@login_required
def feed_view(request):
    """
    Main feed view supporting 'following' and 'discover' modes.
    Chronological order with pagination.
    Excludes blocked users and private profiles that the user doesn't follow.
    """
    feed_mode = request.GET.get('mode', 'following').lower()
    if feed_mode not in ['following', 'discover']:
        feed_mode = 'following'

    blocked_user_ids = get_blocked_user_ids(request.user)

    if feed_mode == 'following':
        following_user_ids = list(
            request.user.following_set.values_list('following_id', flat=True)
        )
        # Include current user's posts as well in their home feed
        author_ids = set(following_user_ids + [request.user.id]) - blocked_user_ids
        posts_qs = Post.objects.filter(author_id__in=author_ids)
    else:
        # Discover mode: recent public posts from others (and followed private accounts)
        following_user_ids = set(request.user.following_set.values_list('following_id', flat=True))
        # Visible posts: not blocked, and (not private OR author is in following OR author is self)
        posts_qs = Post.objects.exclude(author_id__in=blocked_user_ids).filter(
            Q(author__profile__is_private=False) |
            Q(author_id__in=following_user_ids) |
            Q(author=request.user)
        )

    posts_qs = posts_qs.select_related('author', 'author__profile').prefetch_related('likes', 'comments').order_by('-created_at')

    paginator = Paginator(posts_qs, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    post_form = PostCreateForm()
    comment_form = CommentForm()

    return render(request, 'posts/feed.html', {
        'page_obj': page_obj,
        'feed_mode': feed_mode,
        'post_form': post_form,
        'comment_form': comment_form,
    })


@login_required
def post_create_view(request):
    if request.method == 'POST':
        form = PostCreateForm(request.POST, request.FILES)
        if form.is_valid():
            post = form.save(commit=False)
            post.author = request.user
            post.save()
            messages.success(request, "Your post has been published to ConnectSphere!")
            return redirect('posts:feed')
        else:
            messages.error(request, "Failed to publish post. Please check the content.")
            # Render feed with form errors
            blocked_user_ids = get_blocked_user_ids(request.user)
            following_user_ids = list(request.user.following_set.values_list('following_id', flat=True))
            author_ids = set(following_user_ids + [request.user.id]) - blocked_user_ids
            posts_qs = Post.objects.filter(author_id__in=author_ids).select_related('author', 'author__profile').order_by('-created_at')
            paginator = Paginator(posts_qs, 10)
            page_obj = paginator.get_page(1)
            return render(request, 'posts/feed.html', {
                'page_obj': page_obj,
                'feed_mode': 'following',
                'post_form': form,
                'comment_form': CommentForm(),
            })
    return redirect('posts:feed')


@login_required
def post_detail_view(request, post_id):
    post = get_object_or_404(
        Post.objects.select_related('author', 'author__profile').prefetch_related('comments__author__profile', 'likes'),
        id=post_id
    )

    # Check blocked relationship
    if is_blocked_relationship(request.user, post.author):
        messages.error(request, "This post is unavailable.")
        return redirect('posts:feed')

    # Check privacy
    if post.author != request.user and post.author.profile.is_private:
        is_following = Follow.objects.filter(follower=request.user, following=post.author).exists()
        if not is_following:
            messages.error(request, "This post is from a private account.")
            return redirect('accounts:profile_detail', username=post.author.username)

    comment_form = CommentForm()

    return render(request, 'posts/post_detail.html', {
        'post': post,
        'comment_form': comment_form,
    })


@login_required
def post_edit_view(request, post_id):
    post = get_object_or_404(Post, id=post_id)

    # Authorization check: only author can edit
    if post.author != request.user:
        messages.error(request, "You are not authorized to edit this post.")
        return HttpResponseForbidden("Forbidden: You cannot edit another user's post.")

    if request.method == 'POST':
        form = PostEditForm(request.POST, request.FILES, instance=post)
        if form.is_valid():
            form.save()
            messages.success(request, "Your post was updated successfully.")
            return redirect('posts:post_detail', post_id=post.id)
        else:
            messages.error(request, "Failed to update post. Check your input.")
    else:
        form = PostEditForm(instance=post)

    return render(request, 'posts/post_edit.html', {
        'form': form,
        'post': post,
    })


@login_required
def post_delete_view(request, post_id):
    post = get_object_or_404(Post, id=post_id)

    # Authorization check
    if post.author != request.user:
        messages.error(request, "You are not authorized to delete this post.")
        return HttpResponseForbidden("Forbidden: You cannot delete another user's post.")

    if request.method == 'POST':
        post.delete()
        messages.success(request, "Post was deleted successfully.")
        return redirect('posts:feed')

    return render(request, 'posts/post_confirm_delete.html', {'post': post})


@login_required
@require_POST
def post_like_toggle_view(request, post_id):
    post = get_object_or_404(Post, id=post_id)

    # Check blocked relationship
    if is_blocked_relationship(request.user, post.author):
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'error': 'Action not permitted with blocked user.'}, status=403)
        messages.error(request, "Cannot interact with this content.")
        return redirect('posts:feed')

    existing_like = Like.objects.filter(user=request.user, post=post).first()
    if existing_like:
        existing_like.delete()
        liked = False
    else:
        Like.objects.get_or_create(user=request.user, post=post)
        liked = True
        create_notification(recipient=post.author, actor=request.user, event_type='like', post=post)

    likes_count = post.likes.count()

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'liked': liked,
            'likes_count': likes_count,
        })

    return redirect(request.META.get('HTTP_REFERER') or 'posts:feed')


@login_required
@require_POST
def comment_create_view(request, post_id):
    post = get_object_or_404(Post, id=post_id)

    # Check blocked
    if is_blocked_relationship(request.user, post.author):
        messages.error(request, "Cannot comment on this post.")
        return redirect('posts:feed')

    form = CommentForm(request.POST)
    if form.is_valid():
        comment = form.save(commit=False)
        comment.author = request.user
        comment.post = post
        comment.save()

        create_notification(recipient=post.author, actor=request.user, event_type='comment', post=post, comment=comment)

        messages.success(request, "Comment added.")
    else:
        messages.error(request, "Comment could not be submitted. It cannot be empty.")

    next_url = request.POST.get('next')
    if next_url and next_url.startswith('/'):
        return redirect(next_url)
    return redirect('posts:post_detail', post_id=post.id)


@login_required
def comment_edit_view(request, comment_id):
    comment = get_object_or_404(Comment, id=comment_id)

    if comment.author != request.user:
        messages.error(request, "You are not authorized to edit this comment.")
        return HttpResponseForbidden("Forbidden: Cannot edit another user's comment.")

    if request.method == 'POST':
        form = CommentForm(request.POST, instance=comment)
        if form.is_valid():
            form.save()
            messages.success(request, "Comment updated.")
            return redirect('posts:post_detail', post_id=comment.post_id)
        else:
            messages.error(request, "Failed to update comment.")
    else:
        form = CommentForm(instance=comment)

    return render(request, 'posts/comment_edit.html', {
        'form': form,
        'comment': comment,
    })


@login_required
def comment_delete_view(request, comment_id):
    comment = get_object_or_404(Comment, id=comment_id)

    if comment.author != request.user:
        messages.error(request, "You are not authorized to delete this comment.")
        return HttpResponseForbidden("Forbidden: Cannot delete another user's comment.")

    post_id = comment.post_id
    if request.method == 'POST':
        comment.delete()
        messages.success(request, "Comment deleted.")
        return redirect('posts:post_detail', post_id=post_id)

    return render(request, 'posts/comment_confirm_delete.html', {'comment': comment})
