import secrets
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from django.db import models
from django.urls import reverse
from django.utils import timezone


# ---------------------------------------------------------------------------
# Licenciamento (controle de contrato/assinatura vendido ao cliente)
# ---------------------------------------------------------------------------
class Licenca(models.Model):
    """Contrato/licença anual do sistema. Normalmente há uma licença ativa
    que governa o acesso dos usuários do cliente (ex.: Electrolux)."""
    cliente = models.CharField('Cliente', max_length=160, default='Electrolux')
    responsavel = models.CharField('Responsável', max_length=160, blank=True)
    email = models.EmailField('E-mail de contato', blank=True)
    data_inicio = models.DateField('Início do contrato')
    data_vencimento = models.DateField('Vencimento do contrato')
    valor_atual = models.DecimalField('Valor anual (R$)', max_digits=12,
                                      decimal_places=2, default=0)
    indice_reajuste = models.CharField('Índice de reajuste', max_length=20, default='IPCA')
    dias_alerta = models.PositiveIntegerField('Alertar com (dias) de antecedência', default=30)
    ativa = models.BooleanField('Ativa', default=True)
    observacoes = models.TextField('Observações', blank=True)
    criado_em = models.DateTimeField('Criado em', default=timezone.now)

    class Meta:
        verbose_name = 'Licença'
        verbose_name_plural = 'Licenças'
        ordering = ['-data_vencimento']

    def __str__(self):
        return f'{self.cliente} — vence em {self.data_vencimento:%d/%m/%Y}'

    @property
    def dias_restantes(self):
        return (self.data_vencimento - date.today()).days

    @property
    def expirada(self):
        return date.today() > self.data_vencimento

    @property
    def em_alerta(self):
        return not self.expirada and self.dias_restantes <= self.dias_alerta

    @property
    def status_label(self):
        if self.expirada:
            return 'Expirada'
        if self.em_alerta:
            return 'Vencendo'
        return 'Ativa'

    def aplicar_reajuste(self, percentual, meses=12, observacao=''):
        """Aplica reajuste (IPCA) ao valor e estende o vencimento.

        Retorna o registro de ReajusteLicenca criado.
        """
        perc = Decimal(str(percentual))
        valor_anterior = self.valor_atual
        venc_anterior = self.data_vencimento
        valor_novo = (valor_anterior * (Decimal('1') + perc / Decimal('100'))
                      ).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        venc_novo = _add_meses(venc_anterior, meses)
        self.valor_atual = valor_novo
        self.data_vencimento = venc_novo
        self.ativa = True
        self.save(update_fields=['valor_atual', 'data_vencimento', 'ativa'])
        return ReajusteLicenca.objects.create(
            licenca=self, percentual=perc,
            valor_anterior=valor_anterior, valor_novo=valor_novo,
            vencimento_anterior=venc_anterior, vencimento_novo=venc_novo,
            observacao=observacao,
        )


def _add_meses(d, meses):
    """Soma meses a uma data sem depender de bibliotecas externas."""
    m = d.month - 1 + meses
    ano = d.year + m // 12
    mes = m % 12 + 1
    # ajusta o dia para o último dia do mês quando necessário
    import calendar
    dia = min(d.day, calendar.monthrange(ano, mes)[1])
    return date(ano, mes, dia)


class ReajusteLicenca(models.Model):
    """Histórico de reajustes/renovações aplicados a uma licença."""
    licenca = models.ForeignKey(Licenca, on_delete=models.CASCADE, related_name='reajustes')
    data = models.DateField('Data do reajuste', default=date.today)
    percentual = models.DecimalField('% IPCA aplicado', max_digits=7, decimal_places=4, default=0)
    valor_anterior = models.DecimalField('Valor anterior', max_digits=12, decimal_places=2)
    valor_novo = models.DecimalField('Valor novo', max_digits=12, decimal_places=2)
    vencimento_anterior = models.DateField('Vencimento anterior')
    vencimento_novo = models.DateField('Vencimento novo')
    observacao = models.CharField('Observação', max_length=200, blank=True)
    criado_em = models.DateTimeField('Criado em', default=timezone.now)

    class Meta:
        verbose_name = 'Reajuste de Licença'
        verbose_name_plural = 'Reajustes de Licença'
        ordering = ['-data', '-id']

    def __str__(self):
        return f'{self.data:%d/%m/%Y} — {self.percentual}% '


def licenca_vigente():
    """Retorna a licença ativa mais recente (ou None)."""
    return Licenca.objects.filter(ativa=True).order_by('-data_vencimento').first()


class PerfilUsuario(models.Model):
    """Vincula um usuário a uma empresa/licença. Permite vários usuários por
    empresa e que o bloqueio respeite a licença daquele usuário."""
    user = models.OneToOneField('auth.User', on_delete=models.CASCADE, related_name='perfil')
    licenca = models.ForeignKey(Licenca, on_delete=models.SET_NULL, null=True, blank=True,
                                related_name='usuarios', verbose_name='Empresa / Licença')

    class Meta:
        verbose_name = 'Perfil de Usuário'
        verbose_name_plural = 'Perfis de Usuário'

    def __str__(self):
        return f'{self.user.username} → {self.licenca.cliente if self.licenca else "—"}'


def licenca_do_usuario(user):
    """Licença que governa o acesso de um usuário (perfil) ou a vigente global."""
    perfil = getattr(user, 'perfil', None)
    if perfil and perfil.licenca_id:
        return perfil.licenca
    return licenca_vigente()


# ---------------------------------------------------------------------------
# Tabelas de apoio (dados importados da macro)
# ---------------------------------------------------------------------------
class Filial(models.Model):
    """Filial / planta da Electrolux selecionável no formulário."""
    empresa = models.CharField('Empresa', max_length=20, blank=True)
    cia = models.CharField('CIA', max_length=20, blank=True)
    planta = models.CharField('Planta', max_length=120)
    municipio = models.CharField('Município', max_length=120, blank=True)
    uf = models.CharField('UF', max_length=2, blank=True)
    cnpj = models.CharField('CNPJ', max_length=20, blank=True)
    endereco = models.CharField('Endereço', max_length=200, blank=True)
    cep = models.CharField('CEP', max_length=12, blank=True)
    ativo = models.BooleanField('Ativo', default=True)

    class Meta:
        verbose_name = 'Filial'
        verbose_name_plural = 'Filiais'
        ordering = ['planta']

    def __str__(self):
        return f'{self.planta} — {self.municipio}/{self.uf}'

    @property
    def cnpj_formatado(self):
        c = ''.join(filter(str.isdigit, self.cnpj or ''))
        if len(c) == 14:
            return f'{c[:2]}.{c[2:5]}.{c[5:8]}/{c[8:12]}-{c[12:]}'
        return self.cnpj


class CodigoAtividade(models.Model):
    """Código de serviço da LC 116 (lista de atividades)."""
    codigo = models.CharField('Código', max_length=12, db_index=True)
    atividade = models.TextField('Atividade', blank=True)
    descricao = models.TextField('Descrição', blank=True)

    class Meta:
        verbose_name = 'Código de Atividade'
        verbose_name_plural = 'Códigos de Atividade'
        ordering = ['codigo']

    def __str__(self):
        return f'{self.codigo} — {self.atividade[:60]}'


class CodigoSAP(models.Model):
    """Tabela CONSOLIDADO: mapeia código de atividade + retenções → código SAP."""
    cenario = models.IntegerField('Cenário', null=True, blank=True)
    codigo_atividade = models.CharField('Código atividade', max_length=12, db_index=True)
    codigo_sap = models.CharField('Código SAP', max_length=40)
    aliquota = models.DecimalField('Alíquota', max_digits=8, decimal_places=4,
                                   null=True, blank=True)
    chave1 = models.CharField('Chave 1', max_length=60, blank=True, db_index=True)
    chave2 = models.CharField('Chave 2', max_length=60, blank=True, db_index=True)

    class Meta:
        verbose_name = 'Código SAP'
        verbose_name_plural = 'Códigos SAP'
        ordering = ['codigo_atividade', 'cenario']

    def __str__(self):
        return f'{self.codigo_sap} ({self.codigo_atividade})'


# ---------------------------------------------------------------------------
# Convite (link com token único por fornecedor)
# ---------------------------------------------------------------------------
class Convite(models.Model):
    STATUS_PENDENTE = 'pendente'
    STATUS_ENVIADO = 'enviado'
    STATUS_CHOICES = [
        (STATUS_PENDENTE, 'Aguardando preenchimento'),
        (STATUS_ENVIADO, 'Cotação enviada'),
    ]

    token = models.CharField('Token', max_length=48, unique=True, db_index=True)
    fornecedor_nome = models.CharField('Fornecedor (referência)', max_length=160, blank=True)
    fornecedor_email = models.EmailField('E-mail do fornecedor', blank=True)
    observacao = models.TextField('Observação interna', blank=True)
    status = models.CharField('Status', max_length=12, choices=STATUS_CHOICES,
                              default=STATUS_PENDENTE)
    criado_por = models.ForeignKey('auth.User', on_delete=models.SET_NULL,
                                   null=True, blank=True, related_name='convites')
    criado_em = models.DateTimeField('Criado em', default=timezone.now)
    expira_em = models.DateTimeField('Expira em', null=True, blank=True)

    class Meta:
        verbose_name = 'Convite'
        verbose_name_plural = 'Convites'
        ordering = ['-criado_em']

    def __str__(self):
        return f'Convite {self.token[:8]}… ({self.fornecedor_nome or "sem nome"})'

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = secrets.token_urlsafe(24)
        super().save(*args, **kwargs)

    @property
    def expirado(self):
        return bool(self.expira_em and timezone.now() > self.expira_em)

    @property
    def disponivel(self):
        return self.status == self.STATUS_PENDENTE and not self.expirado

    def get_form_url(self):
        return reverse('form_publico', args=[self.token])


# ---------------------------------------------------------------------------
# Cotação preenchida pelo fornecedor
# ---------------------------------------------------------------------------
class Cotacao(models.Model):
    TIPO_SERVICOS = 'Serviços'
    TIPO_MERCADORIA = 'Mercadoria'
    TIPO_AMBOS = 'Serviços e Mercadoria'
    TIPO_CHOICES = [
        (TIPO_SERVICOS, 'Serviços'),
        (TIPO_MERCADORIA, 'Mercadoria'),
        (TIPO_AMBOS, 'Serviços e Mercadoria'),
    ]

    REGIME_CHOICES = [
        ('Simples Nacional', 'Simples Nacional'),
        ('MEI', 'MEI'),
        ('Lucro Presumido', 'Lucro Presumido'),
        ('Lucro Real', 'Lucro Real'),
    ]

    STATUS_RASCUNHO = 'rascunho'
    STATUS_ENVIADA = 'enviada'
    STATUS_CHOICES = [
        (STATUS_RASCUNHO, 'Rascunho'),
        (STATUS_ENVIADA, 'Enviada'),
    ]

    convite = models.OneToOneField(Convite, on_delete=models.SET_NULL, null=True,
                                   blank=True, related_name='cotacao')

    # Dados da Electrolux
    filial = models.ForeignKey(Filial, on_delete=models.PROTECT, verbose_name='Filial')
    tipo_fornecimento = models.CharField('Tipo de fornecimento', max_length=30,
                                         choices=TIPO_CHOICES)

    # Dados do fornecedor
    cnpj = models.CharField('CNPJ', max_length=20)
    razao_social = models.CharField('Razão social', max_length=200)
    nome_fantasia = models.CharField('Nome fantasia', max_length=200, blank=True)
    regime = models.CharField('Regime tributário', max_length=30, choices=REGIME_CHOICES)
    endereco = models.CharField('Endereço', max_length=200, blank=True)
    bairro = models.CharField('Bairro', max_length=120, blank=True)
    cidade = models.CharField('Cidade', max_length=120, blank=True)
    estado = models.CharField('Estado (UF)', max_length=2, blank=True)
    cep = models.CharField('CEP', max_length=12, blank=True)

    # Contatos
    email = models.EmailField('E-mail', blank=True)
    telefone = models.CharField('Telefone / WhatsApp', max_length=40, blank=True)
    numero_proposta = models.CharField('Número da proposta', max_length=60, blank=True)
    cep_contato = models.CharField('CEP (proposta)', max_length=12, blank=True)

    # Condições comerciais
    frete = models.CharField('Frete', max_length=60, blank=True)
    prazo_pagamento = models.CharField('Prazo de pagamento', max_length=60, blank=True)
    data_emissao = models.DateField('Data de emissão', null=True, blank=True)

    # Totais (calculados)
    total_servico = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    total_material = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    total_ipi = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    total_icms = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    total_retido = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    valor_liquido = models.DecimalField(max_digits=16, decimal_places=2, default=0)

    # Aceite dos termos da Electrolux
    aceite_termos = models.BooleanField('Aceitou os termos', default=False)
    aceite_em = models.DateTimeField('Aceite em', null=True, blank=True)
    aceite_ip = models.GenericIPAddressField('IP do aceite', null=True, blank=True)

    status = models.CharField('Status', max_length=12, choices=STATUS_CHOICES,
                              default=STATUS_ENVIADA)
    criado_em = models.DateTimeField('Criado em', default=timezone.now)
    atualizado_em = models.DateTimeField('Atualizado em', auto_now=True)

    class Meta:
        verbose_name = 'Cotação'
        verbose_name_plural = 'Cotações'
        ordering = ['-criado_em']

    def __str__(self):
        return f'Cotação #{self.pk} — {self.razao_social}'

    @property
    def cnpj_formatado(self):
        c = ''.join(filter(str.isdigit, self.cnpj or ''))
        if len(c) == 14:
            return f'{c[:2]}.{c[2:5]}.{c[5:8]}/{c[8:12]}-{c[12:]}'
        return self.cnpj

    @property
    def tem_servicos(self):
        return self.tipo_fornecimento in (self.TIPO_SERVICOS, self.TIPO_AMBOS)

    @property
    def tem_mercadoria(self):
        return self.tipo_fornecimento in (self.TIPO_MERCADORIA, self.TIPO_AMBOS)

    def recalcular(self, commit=True):
        """Recalcula totais a partir dos itens (fonte autoritativa)."""
        servicos = list(self.servicos.all())
        mercadorias = list(self.mercadorias.all())
        ts = sum((i.valor_liquido for i in servicos), Decimal('0'))
        tr = sum((i.total_retido for i in servicos), Decimal('0'))
        tm = sum((i.valor_total for i in mercadorias), Decimal('0'))
        tipi = sum((i.valor_ipi for i in mercadorias), Decimal('0'))
        ticms = sum((i.valor_icms for i in mercadorias), Decimal('0'))
        self.total_servico = ts
        self.total_retido = tr
        self.total_material = tm
        self.total_ipi = tipi
        self.total_icms = ticms
        self.valor_liquido = ts + tm
        if commit:
            self.save(update_fields=[
                'total_servico', 'total_retido', 'total_material',
                'total_ipi', 'total_icms', 'valor_liquido', 'atualizado_em',
            ])


class ItemServico(models.Model):
    cotacao = models.ForeignKey(Cotacao, on_delete=models.CASCADE, related_name='servicos')
    valor_servico = models.DecimalField('Valor do serviço', max_digits=16, decimal_places=2,
                                         default=0)
    codigo_servico = models.CharField('Código do serviço', max_length=12, blank=True)
    descricao = models.TextField('Descrição', blank=True)
    perc_iss = models.DecimalField('% ISS retido', max_digits=7, decimal_places=4, default=0)
    perc_inss = models.DecimalField('% INSS retido', max_digits=7, decimal_places=4, default=0)
    perc_csrf = models.DecimalField('% CSRF retido', max_digits=7, decimal_places=4, default=0)
    perc_irrf = models.DecimalField('% IRRF retido', max_digits=7, decimal_places=4, default=0)
    total_retido = models.DecimalField('Total retido', max_digits=16, decimal_places=2, default=0)
    codigo_sap = models.CharField('Código SAP', max_length=40, blank=True)
    valor_liquido = models.DecimalField('Valor líquido', max_digits=16, decimal_places=2, default=0)
    ordem = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = 'Item de Serviço'
        verbose_name_plural = 'Itens de Serviço'
        ordering = ['ordem', 'id']

    def __str__(self):
        return f'{self.codigo_servico} — {self.valor_servico}'


class ItemMercadoria(models.Model):
    CATEGORIA_CHOICES = [
        ('Ativo Fixo', 'Ativo Fixo'),
        ('Uso ou Consumo', 'Uso ou Consumo'),
        ('Industrialização', 'Industrialização'),
        ('Comercialização', 'Comercialização'),
    ]

    cotacao = models.ForeignKey(Cotacao, on_delete=models.CASCADE, related_name='mercadorias')
    item = models.CharField('Código ou descrição do item', max_length=200, blank=True)
    quantidade = models.DecimalField('Quantidade', max_digits=14, decimal_places=3, default=0)
    unidade = models.CharField('Unidade de medida', max_length=20, blank=True)
    prazo_entrega = models.CharField('Prazo de entrega', max_length=60, blank=True)
    valor_unitario = models.DecimalField('Valor unitário', max_digits=16, decimal_places=4, default=0)
    cst_icms = models.CharField('CST ICMS', max_length=10, blank=True)
    cfop = models.CharField('CFOP', max_length=10, blank=True)
    cod_cest = models.CharField('COD CEST', max_length=12, blank=True)
    categoria = models.CharField('Categoria', max_length=30, choices=CATEGORIA_CHOICES, blank=True)
    ncm = models.CharField('NCM', max_length=12, blank=True)
    excecao = models.CharField('Exceção', max_length=12, blank=True)
    perc_ipi = models.DecimalField('IPI %', max_digits=7, decimal_places=4, default=0)
    valor_ipi = models.DecimalField('Valor IPI', max_digits=16, decimal_places=2, default=0)
    perc_icms = models.DecimalField('ICMS %', max_digits=7, decimal_places=4, default=0)
    perc_reducao_base = models.DecimalField('% Redução base ICMS', max_digits=7, decimal_places=4, default=0)
    base_icms = models.DecimalField('Base ICMS', max_digits=16, decimal_places=2, default=0)
    valor_icms = models.DecimalField('Valor ICMS', max_digits=16, decimal_places=2, default=0)
    icms_st = models.DecimalField('ICMS ST', max_digits=16, decimal_places=2, default=0)
    valor_total = models.DecimalField('Valor total', max_digits=16, decimal_places=2, default=0)
    observacoes = models.TextField('Observações', blank=True)
    ordem = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = 'Item de Mercadoria'
        verbose_name_plural = 'Itens de Mercadoria'
        ordering = ['ordem', 'id']

    def __str__(self):
        return f'{self.item} — {self.valor_total}'
