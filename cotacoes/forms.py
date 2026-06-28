from django import forms
from django.contrib.auth.models import User
from django.forms import inlineformset_factory

from .models import Cotacao, ItemServico, ItemMercadoria, Convite, Filial, Licenca


TEXT = 'form-control'
SELECT = 'form-select'


class CotacaoForm(forms.ModelForm):
    class Meta:
        model = Cotacao
        fields = [
            'filial', 'tipo_fornecimento',
            'cnpj', 'razao_social', 'nome_fantasia', 'regime',
            'endereco', 'bairro', 'cidade', 'estado', 'cep',
            'email', 'telefone', 'numero_proposta', 'cep_contato',
            'frete', 'prazo_pagamento', 'data_emissao',
        ]
        widgets = {
            'filial': forms.Select(attrs={'class': SELECT, 'id': 'id_filial'}),
            'tipo_fornecimento': forms.Select(attrs={'class': SELECT, 'id': 'id_tipo'}),
            'cnpj': forms.TextInput(attrs={'class': TEXT, 'placeholder': '00.000.000/0000-00',
                                           'data-mask': 'cnpj'}),
            'razao_social': forms.TextInput(attrs={'class': TEXT}),
            'nome_fantasia': forms.TextInput(attrs={'class': TEXT}),
            'regime': forms.Select(attrs={'class': SELECT}),
            'endereco': forms.TextInput(attrs={'class': TEXT}),
            'bairro': forms.TextInput(attrs={'class': TEXT}),
            'cidade': forms.TextInput(attrs={'class': TEXT}),
            'estado': forms.TextInput(attrs={'class': TEXT, 'maxlength': 2,
                                             'style': 'text-transform:uppercase'}),
            'cep': forms.TextInput(attrs={'class': TEXT, 'placeholder': '00000-000'}),
            'email': forms.EmailInput(attrs={'class': TEXT}),
            'telefone': forms.TextInput(attrs={'class': TEXT}),
            'numero_proposta': forms.TextInput(attrs={'class': TEXT}),
            'cep_contato': forms.TextInput(attrs={'class': TEXT, 'placeholder': '00000-000'}),
            'frete': forms.TextInput(attrs={'class': TEXT}),
            'prazo_pagamento': forms.TextInput(attrs={'class': TEXT}),
            'data_emissao': forms.DateInput(attrs={'class': TEXT, 'type': 'date'},
                                            format='%Y-%m-%d'),
        }

    aceite = forms.BooleanField(
        required=True,
        error_messages={'required': 'É necessário ler e aceitar os termos para enviar.'},
        widget=forms.CheckboxInput(attrs={'id': 'id_aceite'}),
        label='Li e concordo com os termos e condições da Electrolux.',
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['filial'].queryset = Filial.objects.filter(ativo=True)
        self.fields['filial'].empty_label = 'Selecione a filial…'
        for f in ('cnpj', 'razao_social', 'regime', 'filial', 'tipo_fornecimento'):
            self.fields[f].required = True


class ItemServicoForm(forms.ModelForm):
    class Meta:
        model = ItemServico
        fields = ['valor_servico', 'codigo_servico', 'descricao',
                  'perc_iss', 'perc_inss', 'perc_csrf', 'perc_irrf', 'codigo_sap']
        widgets = {
            'valor_servico': forms.NumberInput(attrs={'class': TEXT + ' calc-srv money', 'step': '0.01'}),
            'codigo_servico': forms.Select(attrs={'class': SELECT + ' codserv'}),
            'descricao': forms.TextInput(attrs={'class': TEXT, 'readonly': True}),
            'perc_iss': forms.NumberInput(attrs={'class': TEXT + ' calc-srv pct', 'step': '0.01', 'placeholder': 'ex.: 5'}),
            'perc_inss': forms.NumberInput(attrs={'class': TEXT + ' calc-srv pct', 'step': '0.01', 'placeholder': 'ex.: 11'}),
            'perc_csrf': forms.NumberInput(attrs={'class': TEXT + ' calc-srv pct', 'step': '0.01', 'placeholder': 'ex.: 4.65'}),
            'perc_irrf': forms.NumberInput(attrs={'class': TEXT + ' calc-srv pct', 'step': '0.01', 'placeholder': 'ex.: 1.5'}),
            'codigo_sap': forms.TextInput(attrs={'class': TEXT, 'readonly': True}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from .models import CodigoAtividade
        choices = [('', '—')] + [
            (c.codigo, f'{c.codigo} — {(c.atividade or "")[:70]}')
            for c in CodigoAtividade.objects.all()
        ]
        self.fields['codigo_servico'].widget.choices = choices


class ItemMercadoriaForm(forms.ModelForm):
    class Meta:
        model = ItemMercadoria
        fields = ['item', 'quantidade', 'unidade', 'prazo_entrega', 'valor_unitario',
                  'cst_icms', 'cfop', 'cod_cest', 'categoria', 'ncm', 'excecao',
                  'perc_ipi', 'perc_icms', 'perc_reducao_base', 'icms_st', 'observacoes']
        widgets = {
            'item': forms.TextInput(attrs={'class': TEXT}),
            'quantidade': forms.NumberInput(attrs={'class': TEXT + ' calc-mer', 'step': '0.001'}),
            'unidade': forms.TextInput(attrs={'class': TEXT, 'placeholder': 'UN, KG…'}),
            'prazo_entrega': forms.TextInput(attrs={'class': TEXT}),
            'valor_unitario': forms.NumberInput(attrs={'class': TEXT + ' calc-mer money', 'step': '0.0001'}),
            'cst_icms': forms.TextInput(attrs={'class': TEXT}),
            'cfop': forms.TextInput(attrs={'class': TEXT}),
            'cod_cest': forms.TextInput(attrs={'class': TEXT}),
            'categoria': forms.Select(attrs={'class': SELECT + ' calc-mer'}),
            'ncm': forms.TextInput(attrs={'class': TEXT}),
            'excecao': forms.TextInput(attrs={'class': TEXT}),
            'perc_ipi': forms.NumberInput(attrs={'class': TEXT + ' calc-mer pct', 'step': '0.01', 'placeholder': 'ex.: 10'}),
            'perc_icms': forms.NumberInput(attrs={'class': TEXT + ' calc-mer pct', 'step': '0.01', 'placeholder': 'ex.: 18'}),
            'perc_reducao_base': forms.NumberInput(attrs={'class': TEXT + ' calc-mer pct', 'step': '0.01', 'placeholder': 'ex.: 0'}),
            'icms_st': forms.NumberInput(attrs={'class': TEXT + ' calc-mer money', 'step': '0.01'}),
            'observacoes': forms.TextInput(attrs={'class': TEXT}),
        }


ItemServicoFormSet = inlineformset_factory(
    Cotacao, ItemServico, form=ItemServicoForm,
    extra=1, can_delete=True,
)

ItemMercadoriaFormSet = inlineformset_factory(
    Cotacao, ItemMercadoria, form=ItemMercadoriaForm,
    extra=1, can_delete=True,
)


class LicencaForm(forms.ModelForm):
    class Meta:
        model = Licenca
        fields = ['cliente', 'responsavel', 'email', 'data_inicio', 'data_vencimento',
                  'valor_atual', 'indice_reajuste', 'dias_alerta', 'ativa', 'observacoes']
        widgets = {
            'cliente': forms.TextInput(attrs={'class': TEXT}),
            'responsavel': forms.TextInput(attrs={'class': TEXT}),
            'email': forms.EmailInput(attrs={'class': TEXT}),
            'data_inicio': forms.DateInput(attrs={'class': TEXT, 'type': 'date'}, format='%Y-%m-%d'),
            'data_vencimento': forms.DateInput(attrs={'class': TEXT, 'type': 'date'}, format='%Y-%m-%d'),
            'valor_atual': forms.NumberInput(attrs={'class': TEXT, 'step': '0.01'}),
            'indice_reajuste': forms.TextInput(attrs={'class': TEXT}),
            'dias_alerta': forms.NumberInput(attrs={'class': TEXT}),
            'observacoes': forms.Textarea(attrs={'class': TEXT, 'rows': 2}),
        }


class ReajusteForm(forms.Form):
    percentual = forms.DecimalField(
        label='% IPCA a aplicar', max_digits=7, decimal_places=4, min_value=0,
        widget=forms.NumberInput(attrs={'class': TEXT, 'step': '0.0001', 'placeholder': 'ex.: 4.62'}))
    meses = forms.IntegerField(
        label='Estender vencimento (meses)', min_value=1, initial=12,
        widget=forms.NumberInput(attrs={'class': TEXT}))
    observacao = forms.CharField(
        label='Observação', required=False,
        widget=forms.TextInput(attrs={'class': TEXT, 'placeholder': 'Renovação anual 2026, etc.'}))


class NovoUsuarioForm(forms.Form):
    nome = forms.CharField(label='Nome', max_length=150, required=False,
                           widget=forms.TextInput(attrs={'class': TEXT}))
    username = forms.CharField(label='Usuário (login)', max_length=150,
                               widget=forms.TextInput(attrs={'class': TEXT}))
    email = forms.EmailField(label='E-mail', required=False,
                             widget=forms.EmailInput(attrs={'class': TEXT}))
    licenca = forms.ModelChoiceField(label='Empresa / Licença', queryset=Licenca.objects.all(),
                                     widget=forms.Select(attrs={'class': SELECT}))
    password = forms.CharField(label='Senha', min_length=6,
                               widget=forms.PasswordInput(attrs={'class': TEXT}))

    def clean_username(self):
        u = self.cleaned_data['username'].strip()
        if User.objects.filter(username__iexact=u).exists():
            raise forms.ValidationError('Já existe um usuário com esse login.')
        return u


class DefinirSenhaForm(forms.Form):
    """Usada pelo administrador para redefinir a senha de um usuário."""
    password = forms.CharField(label='Nova senha', min_length=6,
                               widget=forms.PasswordInput(attrs={'class': TEXT}))
    password2 = forms.CharField(label='Confirmar nova senha', min_length=6,
                                widget=forms.PasswordInput(attrs={'class': TEXT}))

    def clean(self):
        data = super().clean()
        if data.get('password') and data.get('password') != data.get('password2'):
            raise forms.ValidationError('As senhas não conferem.')
        return data


class ConviteForm(forms.ModelForm):
    class Meta:
        model = Convite
        fields = ['fornecedor_nome', 'fornecedor_email', 'observacao', 'expira_em']
        widgets = {
            'fornecedor_nome': forms.TextInput(attrs={'class': TEXT,
                                'placeholder': 'Nome do fornecedor (opcional)'}),
            'fornecedor_email': forms.EmailInput(attrs={'class': TEXT,
                                'placeholder': 'email@fornecedor.com (opcional)'}),
            'observacao': forms.Textarea(attrs={'class': TEXT, 'rows': 2,
                                'placeholder': 'Observação interna (opcional)'}),
            'expira_em': forms.DateTimeInput(attrs={'class': TEXT, 'type': 'datetime-local'},
                                format='%Y-%m-%dT%H:%M'),
        }
