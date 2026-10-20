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
]
