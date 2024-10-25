from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('sales_visualizations/', views.sales_visualizations, name='sales_visualizations'),
    path('association_rules/', views.association_rules_view, name='association_rules'),
    path('store/', views.store_view, name='store'),
    path('get_consequents/', views.get_consequents, name='get_consequents'),
]