from django.urls import path
from . import views

app_name = 'social'

urlpatterns = [
    path('follow/<str:username>/', views.follow_toggle_view, name='follow_toggle'),
    path('users/<str:username>/followers/', views.followers_list_view, name='followers_list'),
    path('users/<str:username>/following/', views.following_list_view, name='following_list'),
    path('posts/<int:post_id>/bookmark/', views.bookmark_toggle_view, name='bookmark_toggle'),
    path('saved/', views.saved_posts_view, name='saved_posts'),
    path('block/<str:username>/', views.block_toggle_view, name='block_toggle'),
    path('settings/blocked/', views.blocked_users_view, name='blocked_users'),
    path('mute/<str:username>/', views.mute_toggle_view, name='mute_toggle'),
]

