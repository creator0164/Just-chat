from django.urls import path
from . import views

urlpatterns = [
    path('friend/list/<user_id>/', views.friend_list_view, name='list'),
    path('friend/friend_remove/', views.remove_friend, name='remove_friend'),
    path('friend/friend_request/', views.send_friend_request, name='friend_request'),
    path('friend/friend_request_cancel',
         views.cancel_friend_request, name='friend_request_cancel'),
    path('friend/friend_requests/<user_id>/',
         views.friend_requests, name='friend_requests'),
    path('friend/accept_friend_request/<friend_request_id>',
         views.accept_friend_request, name='friend_request_accept'),
    path('friend/decline_friend_request/<friend_request_id>/',
         views.decline_friend_request, name='friend_request_decline'),

]
