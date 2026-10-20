from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.http import JsonResponse, HttpResponseForbidden, Http404
from django.views.decorators.http import require_POST
from django.db.models import Q
from .models import Post, Like, Comment, Community, CommunityMembership
from .forms import PostCreateForm, PostEditForm, CommentForm, CommunityForm
from social.models import Follow
from social.utils import get_blocked_user_ids, is_blocked_relationship, get_muted_user_ids
from notifications.utils import create_notification


@login_required
def feed_view(request):
    """
    Main feed view supporting 'following' and 'discover' modes, topic filters,
    and user-controlled recommendation explanations.
    Chronological order with pagination.
    Excludes blocked users, muted users, and enforces post audience controls.
    """
    # 1. Determine feed mode (honoring user's preferred default mode if not specified in URL)
    raw_mode = request.GET.get('mode')
    if raw_mode and raw_mode.lower() in ['following', 'discover']:
        feed_mode = raw_mode.lower()
    else:
        user_pref_mode = getattr(request.user.profile, 'default_feed_mode', 'following')
        feed_mode = user_pref_mode if user_pref_mode in ['following', 'discover'] else 'following'

    topic_filter = request.GET.get('topic', '').strip()
    user_muted_topics = [t.lower() for t in getattr(request.user.profile, 'muted_topics', [])]
    blocked_user_ids = get_blocked_user_ids(request.user)
    muted_user_ids = get_muted_user_ids(request.user)
    hidden_user_ids = blocked_user_ids | muted_user_ids

    # User joined communities
    joined_community_ids = list(request.user.community_memberships.values_list('community_id', flat=True))

    if feed_mode == 'following':
        following_user_ids = list(
            request.user.following_set.values_list('following_id', flat=True)
        )
        # Include current user's posts as well in their home feed; exclude blocked/muted
        author_ids = set(following_user_ids + [request.user.id]) - hidden_user_ids
        posts_qs = Post.objects.filter(author_id__in=author_ids).filter(
            Q(author=request.user) |
            Q(audience__in=['public', 'followers']) |
            Q(audience='community', community_id__in=joined_community_ids)
        )
        if topic_filter:
            posts_qs = posts_qs.filter(topic__iexact=topic_filter)
    else:
        # Discover mode: recent public posts from others (and followed private accounts)
        following_user_ids = set(request.user.following_set.values_list('following_id', flat=True))
        # Visible posts: not hidden (blocked or muted), and obeys privacy & audience rules:
        posts_qs = Post.objects.exclude(author_id__in=hidden_user_ids).filter(
            Q(author=request.user) |
            (
                (Q(author__profile__is_private=False) | Q(author_id__in=following_user_ids)) &
                (
                    Q(audience='public') |
                    Q(audience='followers', author_id__in=following_user_ids) |
                    Q(audience='community', community_id__in=joined_community_ids)
                )
            )
        )
        if topic_filter:
            posts_qs = posts_qs.filter(topic__iexact=topic_filter)
        elif user_muted_topics:
            # User-controlled preference: suppress muted topics
            posts_qs = posts_qs.exclude(topic__in=user_muted_topics)

    posts_qs = posts_qs.select_related('author', 'author__profile', 'community').prefetch_related('likes', 'comments').order_by('-created_at')

    paginator = Paginator(posts_qs, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Attach transparent recommendation reasons to each post
    for post in page_obj:
        post.recommendation_reason = post.get_recommendation_reason(
            user=request.user,
            feed_mode=feed_mode,
            topic_filter=topic_filter
        )

    post_form = PostCreateForm(user=request.user)
    comment_form = CommentForm()

    popular_topics = [
        ('technology', 'Technology & AI'),
        ('design', 'Design & UI/UX'),
        ('science', 'Science & Research'),
        ('art', 'Art & Photography'),
        ('business', 'Business & Startups'),
        ('culture', 'Culture & Society'),
        ('career', 'Career & Engineering'),
    ]

    joined_communities = Community.objects.filter(memberships__user=request.user)

    return render(request, 'posts/feed.html', {
        'page_obj': page_obj,
        'feed_mode': feed_mode,
        'topic_filter': topic_filter,
        'popular_topics': popular_topics,
        'user_muted_topics': user_muted_topics,
        'joined_communities': joined_communities,
        'post_form': post_form,
        'comment_form': comment_form,
    })


@login_required
def post_create_view(request):
    if request.method == 'POST':
        form = PostCreateForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            post = form.save(commit=False)
            post.author = request.user

            # Security check: If posting to a community, verify membership
            if post.community:
                if not post.community.is_member(request.user):
                    messages.error(request, "You must be a member of this community to post in it.")
                    return redirect('posts:community_detail', slug=post.community.slug)

            post.save()
            messages.success(request, "Your post has been published to ConnectSphere!")

            if post.community:
                return redirect('posts:community_detail', slug=post.community.slug)
            return redirect('posts:feed')
        else:
            messages.error(request, "Failed to publish post. Please check the content.")
            # Render feed with form errors
            blocked_user_ids = get_blocked_user_ids(request.user)
            following_user_ids = list(request.user.following_set.values_list('following_id', flat=True))
            author_ids = set(following_user_ids + [request.user.id]) - blocked_user_ids
            posts_qs = Post.objects.filter(author_id__in=author_ids).select_related('author', 'author__profile', 'community').order_by('-created_at')
            paginator = Paginator(posts_qs, 10)
            page_obj = paginator.get_page(1)
            for p in page_obj:
                p.recommendation_reason = p.get_recommendation_reason(user=request.user, feed_mode='following')

            popular_topics = [
                ('technology', 'Technology & AI'),
                ('design', 'Design & UI/UX'),
                ('science', 'Science & Research'),
                ('art', 'Art & Photography'),
                ('business', 'Business & Startups'),
                ('culture', 'Culture & Society'),
                ('career', 'Career & Engineering'),
            ]

            return render(request, 'posts/feed.html', {
                'page_obj': page_obj,
                'feed_mode': 'following',
                'topic_filter': '',
                'popular_topics': popular_topics,
                'user_muted_topics': getattr(request.user.profile, 'muted_topics', []),
                'joined_communities': Community.objects.filter(memberships__user=request.user),
                'post_form': form,
                'comment_form': CommentForm(),
            })
    return redirect('posts:feed')


@login_required
def post_detail_view(request, post_id):
    post = get_object_or_404(
        Post.objects.select_related('author', 'author__profile', 'community').prefetch_related('comments__author__profile', 'likes'),
        id=post_id
    )

    # Check blocked relationship
    if is_blocked_relationship(request.user, post.author):
        messages.error(request, "This post is unavailable.")
        return redirect('posts:feed')

    # Centralized authorization: checks private account, follower status, community membership, and audience
    if not post.is_visible_to(request.user):
        messages.error(request, "This post is restricted or unavailable to your account.")
        return redirect('posts:feed')

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

    # Check blocked relationship or restricted audience
    if is_blocked_relationship(request.user, post.author) or not post.is_visible_to(request.user):
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'error': 'Action not permitted on this post.'}, status=403)
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

    # Check blocked or restricted audience
    if is_blocked_relationship(request.user, post.author) or not post.is_visible_to(request.user):
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


# ==============================================================================
# Phase 3A: Feed Preferences & Topic Intelligence
# ==============================================================================

@login_required
@require_POST
def mute_topic_view(request):
    """Adds a topic to user's muted list to reduce it in the Discover feed."""
    topic = request.POST.get('topic', '').strip()
    if topic:
        request.user.profile.mute_topic(topic)
        messages.success(request, f"Topics matching #{topic} will appear less often in your Discover feed.")
    next_url = request.POST.get('next') or request.META.get('HTTP_REFERER') or 'posts:feed'
    return redirect(next_url)


@login_required
@require_POST
def unmute_topic_view(request):
    """Removes a topic from user's muted list."""
    topic = request.POST.get('topic', '').strip()
    if topic:
        request.user.profile.unmute_topic(topic)
        messages.success(request, f"Unmuted topic #{topic}.")
    next_url = request.POST.get('next') or request.META.get('HTTP_REFERER') or 'posts:feed'
    return redirect(next_url)


@login_required
@require_POST
def reset_feed_preferences_view(request):
    """Resets all muted topics and feed mode to default."""
    request.user.profile.reset_feed_preferences()
    messages.success(request, "Your feed preferences and muted topics have been reset to defaults.")
    next_url = request.POST.get('next') or 'posts:feed'
    return redirect(next_url)


# ==============================================================================
# Phase 3A: Topic Communities
# ==============================================================================

@login_required
def community_list_view(request):
    """Browse and discover topic communities."""
    query = request.GET.get('q', '').strip()
    topic_filter = request.GET.get('topic', '').strip()

    communities = Community.objects.all().prefetch_related('memberships')

    if query:
        communities = communities.filter(
            Q(name__icontains=query) | Q(description__icontains=query) | Q(slug__icontains=query)
        )
    if topic_filter:
        communities = communities.filter(topic__iexact=topic_filter)

    communities = communities.order_by('name')

    # Get user's joined community IDs
    joined_ids = set(
        request.user.community_memberships.values_list('community_id', flat=True)
    )

    popular_topics = [
        ('technology', 'Technology & AI'),
        ('design', 'Design & UI/UX'),
        ('science', 'Science & Research'),
        ('art', 'Art & Photography'),
        ('business', 'Business & Startups'),
        ('culture', 'Culture & Society'),
        ('career', 'Career & Engineering'),
    ]

    return render(request, 'posts/community_list.html', {
        'communities': communities,
        'joined_ids': joined_ids,
        'query': query,
        'topic_filter': topic_filter,
        'popular_topics': popular_topics,
    })


@login_required
def community_create_view(request):
    """Create a new topic community."""
    if request.method == 'POST':
        form = CommunityForm(request.POST, request.FILES)
        if form.is_valid():
            community = form.save(commit=False)
            community.creator = request.user
            community.save()

            # Automatically make creator the admin
            CommunityMembership.objects.create(
                community=community,
                user=request.user,
                role='admin'
            )
            messages.success(request, f"Community c/{community.slug} has been created!")
            return redirect('posts:community_detail', slug=community.slug)
        else:
            messages.error(request, "Please correct the errors below to create your community.")
    else:
        form = CommunityForm()

    return render(request, 'posts/community_create.html', {
        'form': form,
    })


@login_required
def community_detail_view(request, slug):
    """Dedicated community page with community stream and member management."""
    community = get_object_or_404(
        Community.objects.select_related('creator'),
        slug=slug
    )

    blocked_user_ids = get_blocked_user_ids(request.user)
    following_user_ids = set(request.user.following_set.values_list('following_id', flat=True))

    is_member = community.is_member(request.user)
    is_moderator = community.is_moderator_or_creator(request.user)
    user_membership = community.memberships.filter(user=request.user).first()

    # Posts in community: exclude blocked users; enforce audience and private account rules
    allowed_audiences = ['public']
    if is_member:
        allowed_audiences.append('community')

    posts_qs = community.posts.exclude(author_id__in=blocked_user_ids).filter(
        Q(author=request.user) |
        (
            (Q(author__profile__is_private=False) | Q(author_id__in=following_user_ids)) &
            (Q(audience__in=allowed_audiences) | Q(audience='followers', author_id__in=following_user_ids))
        )
    ).select_related('author', 'author__profile', 'community').prefetch_related('likes', 'comments').order_by('-created_at')

    paginator = Paginator(posts_qs, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    for p in page_obj:
        p.recommendation_reason = f"c/{community.slug} community stream"

    post_form = PostCreateForm(user=request.user, community=community) if is_member else None
    comment_form = CommentForm()

    recent_members = community.memberships.select_related('user', 'user__profile').order_by('-joined_at')[:8]

    return render(request, 'posts/community_detail.html', {
        'community': community,
        'page_obj': page_obj,
        'is_member': is_member,
        'is_moderator': is_moderator,
        'user_membership': user_membership,
        'post_form': post_form,
        'comment_form': comment_form,
        'recent_members': recent_members,
    })


@login_required
@require_POST
def community_join_toggle_view(request, slug):
    """Join or leave a topic community."""
    community = get_object_or_404(Community, slug=slug)
    membership = CommunityMembership.objects.filter(community=community, user=request.user).first()

    if membership:
        # Prevent sole admin/creator from leaving if no other admins exist
        if community.creator == request.user and community.memberships.count() <= 1:
            messages.warning(request, "As the creator and sole member, you cannot leave this community.")
        else:
            membership.delete()
            messages.success(request, f"You have left c/{community.slug}.")
    else:
        CommunityMembership.objects.create(
            community=community,
            user=request.user,
            role='member'
        )
        messages.success(request, f"Welcome to c/{community.slug}! You are now a member.")

    return redirect(request.META.get('HTTP_REFERER') or 'posts:community_detail', slug=community.slug)


@login_required
@require_POST
def community_post_delete_view(request, slug, post_id):
    """Moderator action to remove a violating post from the community."""
    community = get_object_or_404(Community, slug=slug)

    # Authorization check: only community creator or moderator (or staff) can remove community posts
    if not community.is_moderator_or_creator(request.user):
        messages.error(request, "You do not have moderator privileges in this community.")
        return HttpResponseForbidden("Forbidden: Moderator privileges required.")

    post = get_object_or_404(Post, id=post_id, community=community)
    post.delete()
    messages.success(request, f"Post was removed from c/{community.slug} by community moderation.")

    return redirect('posts:community_detail', slug=community.slug)

