from django.urls import path
from . import views

app_name = 'moderation'

urlpatterns = [
    path('report/post/<int:post_id>/', views.report_post_view, name='report_post'),
    path('report/comment/<int:comment_id>/', views.report_comment_view, name='report_comment'),
    path('report/user/<str:username>/', views.report_user_view, name='report_user'),
    path('dashboard/', views.moderation_dashboard_view, name='dashboard'),
    path('review/<int:report_id>/', views.moderation_review_view, name='review'),
]
