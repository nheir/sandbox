from django.urls import path

from . import views

app_name = "loader"

urlpatterns = [
   path('loader/fr/', views.FrozenViewSet.as_view(), name='frozen'),
   path('loader/fr/<str:hash>/', views.FrozenViewSet.as_view(), name='frozen'),
]
