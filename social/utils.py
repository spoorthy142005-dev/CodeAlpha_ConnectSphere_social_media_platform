from django.db.models import Q
from .models import Block


def get_blocked_user_ids(user):
    """
    Returns a set of User IDs that have either blocked `user`
    or have been blocked by `user`.
    """
    if not user or not user.is_authenticated:
        return set()

    blocked_by_user = Block.objects.filter(blocker=user).values_list('blocked_id', flat=True)
    users_who_blocked = Block.objects.filter(blocked=user).values_list('blocker_id', flat=True)
    return set(blocked_by_user).union(set(users_who_blocked))


def is_blocked_relationship(user1, user2):
    """
    Returns True if either user1 has blocked user2 or user2 has blocked user1.
    """
    if not user1 or not user2 or not user1.is_authenticated or not user2.is_authenticated:
        return False
    if user1.id == user2.id:
        return False

    return Block.objects.filter(
        Q(blocker=user1, blocked=user2) | Q(blocker=user2, blocked=user1)
    ).exists()


def get_muted_user_ids(user):
    """
    Returns a set of User IDs that have been muted by `user`.
    """
    if not user or not user.is_authenticated:
        return set()

    from .models import Mute
    return set(Mute.objects.filter(muter=user).values_list('muted_id', flat=True))

