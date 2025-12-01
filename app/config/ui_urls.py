from django.urls import path
from app.views import competencia_list_view, competencia_detail_view, equipo_detail_view

app_name = 'ui'  

urlpatterns = [
    path('', competencia_list_view, name='competencia_list'),
    path('<int:pk>/', competencia_detail_view, name='competencia_detail'),
    path('equipo/<int:pk>/', equipo_detail_view, name='equipo_detail'),
]
