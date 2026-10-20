from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('privacy/', views.privacy_center_view, name='privacy_center'),
    path('privacy/export/', views.data_export_view, name='data_export'),
    path('privacy/delete/', views.account_delete_view, name='account_delete'),
    path('profile/edit/', views.profile_edit_view, name='profile_edit'),
    path('profile/<str:username>/', views.profile_detail_view, name='profile_detail'),
    path('search/', views.user_search_view, name='search'),
]
