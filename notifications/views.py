from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.core.paginator import Paginator
from django.http import HttpResponseForbidden
from .models import Notification


@login_required
def notification_list_view(request):
    notifications_qs = Notification.objects.filter(recipient=request.user).select_related('actor', 'actor__profile', 'post', 'comment')
    paginator = Paginator(notifications_qs, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'notifications/notification_list.html', {
        'page_obj': page_obj,
    })


@login_required
@require_POST
def mark_as_read_view(request, notification_id):
    notification = get_object_or_404(Notification, id=notification_id)

    # Ownership check
    if notification.recipient != request.user:
        return HttpResponseForbidden("Unauthorized")

    notification.is_read = True
    notification.save()

    return redirect('notifications:list')


@login_required
@require_POST
def mark_all_as_read_view(request):
    Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
    messages.success(request, "All notifications marked as read.")
    return redirect('notifications:list')
