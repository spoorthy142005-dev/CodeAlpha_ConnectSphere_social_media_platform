def user_preferences_processor(request):
    """Provides user preferences like low_bandwidth mode to all templates."""
    if hasattr(request, 'user') and request.user.is_authenticated:
        profile = getattr(request.user, 'profile', None)
        low_bandwidth = profile.low_bandwidth if profile else False
        return {
            'user_profile': profile,
            'low_bandwidth_mode': low_bandwidth,
        }
    return {
        'user_profile': None,
        'low_bandwidth_mode': False,
    }
