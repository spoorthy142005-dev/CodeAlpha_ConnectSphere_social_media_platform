from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.utils import timezone
from django.core.paginator import Paginator
from django.contrib.auth.models import User
from .models import Report
from .forms import ReportForm, ModerationActionForm
from posts.models import Post, Comment


@login_required
def report_post_view(request, post_id):
    post = get_object_or_404(Post, id=post_id)

    if request.method == 'POST':
        form = ReportForm(request.POST)
        if form.is_valid():
            report = form.save(commit=False)
            report.reporter = request.user
            report.post = post
            report.reported_user = post.author
            report.save()
            messages.success(request, "Thank you. Your report has been submitted to the ConnectSphere moderation team.")
            return redirect('posts:post_detail', post_id=post.id)
    else:
        form = ReportForm()

    return render(request, 'moderation/report_form.html', {
        'form': form,
        'target_type': 'Post',
        'target_object': post,
    })


@login_required
def report_comment_view(request, comment_id):
    comment = get_object_or_404(Comment, id=comment_id)

    if request.method == 'POST':
        form = ReportForm(request.POST)
        if form.is_valid():
            report = form.save(commit=False)
            report.reporter = request.user
            report.comment = comment
            report.reported_user = comment.author
            report.save()
            messages.success(request, "Your report has been submitted to moderation.")
            return redirect('posts:post_detail', post_id=comment.post_id)
    else:
        form = ReportForm()

    return render(request, 'moderation/report_form.html', {
        'form': form,
        'target_type': 'Comment',
        'target_object': comment,
    })


@login_required
def report_user_view(request, username):
    target_user = get_object_or_404(User, username=username)

    if request.method == 'POST':
        form = ReportForm(request.POST)
        if form.is_valid():
            report = form.save(commit=False)
            report.reporter = request.user
            report.reported_user = target_user
            report.save()
            messages.success(request, f"User @{target_user.username} has been reported.")
            return redirect('accounts:profile_detail', username=target_user.username)
    else:
        form = ReportForm()

    return render(request, 'moderation/report_form.html', {
        'form': form,
        'target_type': 'User',
        'target_object': target_user,
    })


def staff_check(user):
    return user.is_authenticated and (user.is_staff or user.is_superuser)


@user_passes_test(staff_check)
def moderation_dashboard_view(request):
    status_filter = request.GET.get('status', 'pending')
    reports_qs = Report.objects.select_related('reporter', 'reported_user', 'post', 'comment', 'reviewed_by')

    if status_filter in ['pending', 'reviewed', 'dismissed', 'action_taken']:
        reports_qs = reports_qs.filter(status=status_filter)

    paginator = Paginator(reports_qs, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    counts = {
        'pending': Report.objects.filter(status='pending').count(),
        'reviewed': Report.objects.filter(status='reviewed').count(),
        'dismissed': Report.objects.filter(status='dismissed').count(),
        'action_taken': Report.objects.filter(status='action_taken').count(),
    }

    return render(request, 'moderation/dashboard.html', {
        'page_obj': page_obj,
        'status_filter': status_filter,
        'counts': counts,
    })


@user_passes_test(staff_check)
def moderation_review_view(request, report_id):
    report = get_object_or_404(Report, id=report_id)

    if request.method == 'POST':
        form = ModerationActionForm(request.POST, instance=report)
        if form.is_valid():
            updated_report = form.save(commit=False)
            updated_report.reviewed_by = request.user
            updated_report.reviewed_at = timezone.now()

            # Handle content deletion if selected
            if form.cleaned_data.get('delete_content'):
                if report.post:
                    report.post.delete()
                    report.post = None
                elif report.comment:
                    report.comment.delete()
                    report.comment = None
                updated_report.status = 'action_taken'

            updated_report.save()
            messages.success(request, f"Report #{report.id} updated.")
            return redirect('moderation:dashboard')
    else:
        form = ModerationActionForm(instance=report)

    return render(request, 'moderation/review.html', {
        'report': report,
        'form': form,
    })
