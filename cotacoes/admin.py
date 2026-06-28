from django.contrib import admin
from django.utils.html import format_html

from .models import (Filial, CodigoAtividade, CodigoSAP, Convite,
                     Cotacao, ItemServico, ItemMercadoria,
                     Licenca, ReajusteLicenca, PerfilUsuario)


@admin.register(PerfilUsuario)
class PerfilUsuarioAdmin(admin.ModelAdmin):
    list_display = ('user', 'licenca')
    list_filter = ('licenca',)
    search_fields = ('user__username',)


@admin.register(Filial)
class FilialAdmin(admin.ModelAdmin):
    list_display = ('planta', 'municipio', 'uf', 'cnpj', 'ativo')
    list_filter = ('uf', 'ativo', 'empresa')
    search_fields = ('planta', 'municipio', 'cnpj')


@admin.register(CodigoAtividade)
class CodigoAtividadeAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'atividade')
    search_fields = ('codigo', 'atividade')


@admin.register(CodigoSAP)
class CodigoSAPAdmin(admin.ModelAdmin):
    list_display = ('codigo_sap', 'codigo_atividade', 'cenario', 'aliquota')
    list_filter = ('codigo_atividade',)
    search_fields = ('codigo_sap', 'codigo_atividade', 'chave1', 'chave2')


@admin.register(Convite)
class ConviteAdmin(admin.ModelAdmin):
    list_display = ('token_curto', 'fornecedor_nome', 'status', 'criado_em', 'expira_em')
    list_filter = ('status',)
    search_fields = ('fornecedor_nome', 'fornecedor_email', 'token')
    readonly_fields = ('token',)

    @admin.display(description='Token')
    def token_curto(self, obj):
        return format_html('<code>{}…</code>', obj.token[:10])


class ItemServicoInline(admin.TabularInline):
    model = ItemServico
    extra = 0


class ItemMercadoriaInline(admin.TabularInline):
    model = ItemMercadoria
    extra = 0


class ReajusteInline(admin.TabularInline):
    model = ReajusteLicenca
    extra = 0
    readonly_fields = ('data', 'percentual', 'valor_anterior', 'valor_novo',
                       'vencimento_anterior', 'vencimento_novo')


@admin.register(Licenca)
class LicencaAdmin(admin.ModelAdmin):
    list_display = ('cliente', 'data_vencimento', 'valor_atual', 'status_label', 'ativa')
    list_filter = ('ativa',)
    inlines = [ReajusteInline]


@admin.register(Cotacao)
class CotacaoAdmin(admin.ModelAdmin):
    list_display = ('id', 'razao_social', 'cnpj', 'filial', 'tipo_fornecimento',
                    'valor_liquido', 'criado_em')
    list_filter = ('tipo_fornecimento', 'regime', 'filial')
    search_fields = ('razao_social', 'nome_fantasia', 'cnpj')
    inlines = [ItemServicoInline, ItemMercadoriaInline]
    date_hierarchy = 'criado_em'
