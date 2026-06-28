from django.urls import path

from . import views

urlpatterns = [
    # Área do proprietário
    path('', views.dashboard, name='dashboard'),
    path('cotacoes/', views.cotacao_lista, name='cotacao_lista'),
    path('cotacoes/<int:pk>/', views.cotacao_detalhe, name='cotacao_detalhe'),
    path('cotacoes/<int:pk>/export/<str:fmt>/', views.cotacao_export, name='cotacao_export'),
    path('convites/', views.convite_lista, name='convite_lista'),
    path('convites/<int:pk>/excluir/', views.convite_excluir, name='convite_excluir'),

    # Licenciamento
    path('licenca/', views.licenca_painel, name='licenca_painel'),
    path('licenca/bloqueada/', views.licenca_bloqueada, name='licenca_bloqueada'),

    # Usuários
    path('usuarios/', views.usuario_lista, name='usuario_lista'),
    path('usuarios/<int:pk>/senha/', views.usuario_senha, name='usuario_senha'),
    path('usuarios/<int:pk>/toggle/', views.usuario_toggle, name='usuario_toggle'),
    path('minha-senha/', views.minha_senha, name='minha_senha'),

    # Endpoints auxiliares
    path('api/filial/<int:pk>/', views.api_filial, name='api_filial'),
    path('api/atividade/', views.api_atividade, name='api_atividade'),

    # Termos de aceite
    path('termos/<str:slug>/', views.termo_download, name='termo_download'),

    # Área pública (token)
    path('f/<str:token>/', views.form_publico, name='form_publico'),
    path('f/<str:token>/enviado/', views.form_sucesso, name='form_sucesso'),
]
