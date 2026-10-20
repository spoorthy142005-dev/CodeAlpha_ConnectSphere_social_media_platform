from .models import Notification


def create_notification(recipient, actor, event_type, post=None, comment=None):
    """
    Safely creates a notification.
    Ensures:
    1. Users do not receive notifications for their own actions.
    2. Duplicate unread notifications for the same event and target are prevented.
    """
    if not recipient or not actor or recipient == actor:
        return None

    # Check for existing unread notification for the same action
    existing = Notification.objects.filter(
        recipient=recipient,
        actor=actor,
        event_type=event_type,
        post=post,
        comment=comment,
        is_read=False
    ).first()

    if existing:
        return existing

    return Notification.objects.create(
        recipient=recipient,
        actor=actor,
        event_type=event_type,
        post=post,
        comment=comment
    )
