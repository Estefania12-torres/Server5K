from django.urls import path
from .views import competencia_list_view, competencia_detail_view

app_name = 'app_ui'

urlpatterns = [
    path('', competencia_list_view, name='competencia_list'),
    path('<int:pk>/', competencia_detail_view, name='competencia_detail'),
]
