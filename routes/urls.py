from django.urls import path
from routes import views

urlpatterns = [
    path('fuel-plan/', views.fuel_plan, name='fuel-plan'),
]
