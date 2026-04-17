from django.urls import path
from . import views
app_name = 'formulas'
urlpatterns = [
    path('<uuid:pk>/',               views.formula_editor, name='editor'),
    path('<uuid:pk>/preview/',       views.preview,        name='preview'),
    path('<uuid:pk>/save/',          views.save_formula,   name='save'),
    path('<uuid:pk>/delete/<int:col_id>/', views.delete_formula, name='delete'),
]
