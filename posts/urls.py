from django.urls import path
from . import views

app_name = 'posts'

urlpatterns = [
    path('', views.feed_view, name='feed'),
    path('posts/create/', views.post_create_view, name='post_create'),
    path('posts/<int:post_id>/', views.post_detail_view, name='post_detail'),
    path('posts/<int:post_id>/edit/', views.post_edit_view, name='post_edit'),
    path('posts/<int:post_id>/delete/', views.post_delete_view, name='post_delete'),
    path('posts/<int:post_id>/like/', views.post_like_toggle_view, name='post_like_toggle'),
    path('posts/<int:post_id>/comment/', views.comment_create_view, name='comment_create'),
    path('comments/<int:comment_id>/edit/', views.comment_edit_view, name='comment_edit'),
    path('comments/<int:comment_id>/delete/', views.comment_delete_view, name='comment_delete'),

    # Phase 3A: Feed Preferences & Topic Control
    path('feed/mute-topic/', views.mute_topic_view, name='mute_topic'),
    path('feed/unmute-topic/', views.unmute_topic_view, name='unmute_topic'),
    path('feed/reset-preferences/', views.reset_feed_preferences_view, name='reset_feed_preferences'),

    # Phase 3A: Topic Communities
    path('communities/', views.community_list_view, name='community_list'),
    path('communities/create/', views.community_create_view, name='community_create'),
    path('communities/<slug:slug>/', views.community_detail_view, name='community_detail'),
    path('communities/<slug:slug>/join/', views.community_join_toggle_view, name='community_join_toggle'),
    path('communities/<slug:slug>/posts/<int:post_id>/delete/', views.community_post_delete_view, name='community_post_delete'),
]

