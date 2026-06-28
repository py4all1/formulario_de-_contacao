from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.models import User
from django.db.models import Count, Q, Sum
from django.http import JsonResponse, Http404, FileResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone

from .calc import aplicar_calculo_servico, aplicar_calculo_mercadoria, buscar_codigo_sap
from .forms import (CotacaoForm, ItemServicoFormSet, ItemMercadoriaFormSet, ConviteForm,
                    LicencaForm, ReajusteForm, NovoUsuarioForm, DefinirSenhaForm)
from .models import (Cotacao, Convite, Filial, CodigoAtividade, ItemMercadoria,
                     Licenca, PerfilUsuario, licenca_vigente)
from . import exports, termos as termos_mod

superusuario = user_passes_test(lambda u: u.is_superuser)


def _client_ip(request):
    fwd = request.META.get('HTTP_X_FORWARDED_FOR')
    if fwd:
        return fwd.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


# ===========================================================================
# Área pública (fornecedor) — acesso por token
# ===========================================================================
def _get_convite_or_404(token):
    return get_object_or_404(Convite, token=token)


def form_publico(request, token):
    convite = _get_convite_or_404(token)

    if convite.expirado:
        return render(request, 'cotacoes/form_indisponivel.html',
                      {'motivo': 'expirado', 'convite': convite}, status=410)
    if convite.status == Convite.STATUS_ENVIADO:
        return render(request, 'cotacoes/form_indisponivel.html',
                      {'motivo': 'enviado', 'convite': convite}, status=409)

    if request.method == 'POST':
        form = CotacaoForm(request.POST)
        srv_fs = ItemServicoFormSet(request.POST, prefix='srv')
        mer_fs = ItemMercadoriaFormSet(request.POST, prefix='mer')

        if form.is_valid() and srv_fs.is_valid() and mer_fs.is_valid():
            cotacao = form.save(commit=False)
            cotacao.convite = convite
            cotacao.status = Cotacao.STATUS_ENVIADA
            cotacao.aceite_termos = True
            cotacao.aceite_em = timezone.now()
            cotacao.aceite_ip = _client_ip(request)
            cotacao.save()

            _salvar_itens(cotacao, srv_fs, mer_fs)
            cotacao.recalcular()

            convite.status = Convite.STATUS_ENVIADO
            convite.save(update_fields=['status'])

            return redirect('form_sucesso', token=token)
        messages.error(request, 'Há campos com erro. Revise os itens destacados.')
    else:
        form = CotacaoForm()
        srv_fs = ItemServicoFormSet(prefix='srv')
        mer_fs = ItemMercadoriaFormSet(prefix='mer')

    return render(request, 'cotacoes/form_publico.html', {
        'convite': convite, 'form': form,
        'srv_fs': srv_fs, 'mer_fs': mer_fs,
        'regime_choices': Cotacao.REGIME_CHOICES,
        'categoria_choices': ItemMercadoria.CATEGORIA_CHOICES,
        'termos': termos_mod.termos_para_template(),
    })


def termo_download(request, slug):
    """Serve o documento .docx original do termo para download."""
    caminho = termos_mod.caminho_arquivo(slug)
    if not caminho or not caminho.exists():
        raise Http404
    return FileResponse(open(caminho, 'rb'), as_attachment=True,
                        filename=caminho.name)


def _salvar_itens(cotacao, srv_fs, mer_fs):
    """Persiste os itens das formsets recalculando os valores no servidor."""
    cotacao.servicos.all().delete()
    cotacao.mercadorias.all().delete()

    if cotacao.tem_servicos:
        ordem = 0
        for f in srv_fs:
            if not f.cleaned_data or f.cleaned_data.get('DELETE'):
                continue
            if not (f.cleaned_data.get('valor_servico') or f.cleaned_data.get('codigo_servico')):
                continue
            item = f.save(commit=False)
            item.cotacao = cotacao
            item.ordem = ordem
            ordem += 1
            # Regra fiscal: Simples Nacional não tem retenção de CSRF e IRRF
            # em serviços. Forçamos zero no servidor (fonte autoritativa).
            if cotacao.regime == 'Simples Nacional':
                item.perc_csrf = 0
                item.perc_irrf = 0
            # descrição e SAP autoritativos no servidor
            if item.codigo_servico:
                ca = CodigoAtividade.objects.filter(codigo=item.codigo_servico).first()
                if ca and not item.descricao:
                    item.descricao = ca.atividade
                item.codigo_sap = buscar_codigo_sap(item.codigo_servico, item.perc_csrf)
            aplicar_calculo_servico(item)
            item.save()

    if cotacao.tem_mercadoria:
        ordem = 0
        for f in mer_fs:
            if not f.cleaned_data or f.cleaned_data.get('DELETE'):
                continue
            if not (f.cleaned_data.get('item') or f.cleaned_data.get('quantidade')):
                continue
            item = f.save(commit=False)
            item.cotacao = cotacao
            item.ordem = ordem
            ordem += 1
            aplicar_calculo_mercadoria(item)
            item.save()


def form_sucesso(request, token):
    convite = _get_convite_or_404(token)
    return render(request, 'cotacoes/form_sucesso.html', {'convite': convite})


# --- endpoints auxiliares (AJAX) ------------------------------------------
def api_filial(request, pk):
    f = get_object_or_404(Filial, pk=pk)
    return JsonResponse({
        'planta': f.planta, 'municipio': f.municipio, 'uf': f.uf,
        'cep': f.cep, 'endereco': f.endereco, 'cnpj': f.cnpj_formatado,
    })


def api_atividade(request):
    codigo = request.GET.get('codigo', '')
    ca = CodigoAtividade.objects.filter(codigo=codigo).first()
    csrf = request.GET.get('csrf')
    sap = buscar_codigo_sap(codigo, csrf if csrf not in (None, '') else None) if ca else ''
    return JsonResponse({
        'descricao': ca.atividade if ca else '',
        'codigo_sap': sap,
    })


# ===========================================================================
# Área do proprietário (login)
# ===========================================================================
@login_required
def dashboard(request):
    cotacoes = Cotacao.objects.select_related('filial')
    agg = cotacoes.aggregate(total=Count('id'), valor=Sum('valor_liquido'))
    por_tipo = {row['tipo_fornecimento']: row['n']
                for row in cotacoes.values('tipo_fornecimento').annotate(n=Count('id'))}
    convites = Convite.objects.aggregate(
        pendentes=Count('id', filter=Q(status=Convite.STATUS_PENDENTE)),
        enviados=Count('id', filter=Q(status=Convite.STATUS_ENVIADO)),
    )
    return render(request, 'cotacoes/dashboard.html', {
        'total': agg['total'] or 0,
        'valor_total': agg['valor'] or 0,
        'por_tipo': por_tipo,
        'convites': convites,
        'ultimas': cotacoes[:8],
    })


@login_required
def cotacao_lista(request):
    qs = Cotacao.objects.select_related('filial')
    busca = request.GET.get('q', '').strip()
    tipo = request.GET.get('tipo', '').strip()
    if busca:
        qs = qs.filter(Q(razao_social__icontains=busca) | Q(cnpj__icontains=busca) |
                       Q(nome_fantasia__icontains=busca))
    if tipo:
        qs = qs.filter(tipo_fornecimento=tipo)
    return render(request, 'cotacoes/cotacao_lista.html', {
        'cotacoes': qs, 'busca': busca, 'tipo': tipo,
        'tipos': Cotacao.TIPO_CHOICES,
    })


@login_required
def cotacao_detalhe(request, pk):
    cotacao = get_object_or_404(
        Cotacao.objects.select_related('filial', 'convite'), pk=pk)
    return render(request, 'cotacoes/cotacao_detalhe.html', {'cotacao': cotacao})


@login_required
def cotacao_export(request, pk, fmt):
    cotacao = get_object_or_404(Cotacao, pk=pk)
    if fmt == 'json':
        return exports.export_json(cotacao)
    if fmt == 'excel':
        return exports.export_excel(cotacao)
    if fmt == 'pdf':
        return exports.export_pdf(cotacao)
    raise Http404


@login_required
def convite_lista(request):
    if request.method == 'POST':
        form = ConviteForm(request.POST)
        if form.is_valid():
            convite = form.save(commit=False)
            convite.criado_por = request.user
            convite.save()
            messages.success(request, 'Convite criado! Copie o link e envie ao fornecedor.')
            return redirect('convite_lista')
    else:
        form = ConviteForm()
    convites = Convite.objects.select_related('cotacao').all()
    return render(request, 'cotacoes/convite_lista.html', {
        'form': form, 'convites': convites,
    })


@login_required
def convite_excluir(request, pk):
    convite = get_object_or_404(Convite, pk=pk)
    if request.method == 'POST':
        convite.delete()
        messages.info(request, 'Convite removido.')
    return redirect('convite_lista')


# ===========================================================================
# Licenciamento (somente o fornecedor / superusuário)
# ===========================================================================
@login_required
@superusuario
def licenca_painel(request):
    lic = licenca_vigente() or Licenca.objects.order_by('-data_vencimento').first()
    form = LicencaForm(instance=lic)
    reajuste_form = ReajusteForm()

    if request.method == 'POST':
        acao = request.POST.get('acao')
        if acao == 'salvar':
            form = LicencaForm(request.POST, instance=lic)
            if form.is_valid():
                form.save()
                messages.success(request, 'Licença salva com sucesso.')
                return redirect('licenca_painel')
        elif acao == 'reajustar' and lic:
            reajuste_form = ReajusteForm(request.POST)
            if reajuste_form.is_valid():
                r = lic.aplicar_reajuste(
                    reajuste_form.cleaned_data['percentual'],
                    meses=reajuste_form.cleaned_data['meses'],
                    observacao=reajuste_form.cleaned_data['observacao'],
                )
                messages.success(
                    request,
                    f'Reajuste de {r.percentual}% aplicado. Novo valor R$ {r.valor_novo} · '
                    f'novo vencimento {r.vencimento_novo:%d/%m/%Y}.')
                return redirect('licenca_painel')

    return render(request, 'cotacoes/licenca_painel.html', {
        'licenca': lic,
        'form': form,
        'reajuste_form': reajuste_form,
        'reajustes': lic.reajustes.all() if lic else [],
    })


def licenca_bloqueada(request):
    return render(request, 'cotacoes/licenca_bloqueada.html', status=403)


# ===========================================================================
# Gestão de usuários (somente superusuário)
# ===========================================================================
@login_required
@superusuario
def usuario_lista(request):
    form = NovoUsuarioForm()
    if request.method == 'POST':
        form = NovoUsuarioForm(request.POST)
        if form.is_valid():
            cd = form.cleaned_data
            user = User.objects.create_user(
                username=cd['username'], password=cd['password'],
                email=cd['email'], first_name=cd['nome'],
                is_staff=False, is_superuser=False,
            )
            PerfilUsuario.objects.create(user=user, licenca=cd['licenca'])
            messages.success(request, f'Usuário "{user.username}" criado.')
            return redirect('usuario_lista')

    usuarios = (User.objects.filter(is_superuser=False)
                .select_related('perfil', 'perfil__licenca').order_by('username'))
    return render(request, 'cotacoes/usuario_lista.html', {
        'form': form, 'usuarios': usuarios,
    })


@login_required
@superusuario
def usuario_senha(request, pk):
    user = get_object_or_404(User, pk=pk, is_superuser=False)
    form = DefinirSenhaForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user.set_password(form.cleaned_data['password'])
        user.save()
        messages.success(request, f'Senha de "{user.username}" redefinida.')
        return redirect('usuario_lista')
    return render(request, 'cotacoes/usuario_senha.html', {'form': form, 'alvo': user})


@login_required
@superusuario
def usuario_toggle(request, pk):
    user = get_object_or_404(User, pk=pk, is_superuser=False)
    if request.method == 'POST':
        user.is_active = not user.is_active
        user.save(update_fields=['is_active'])
        estado = 'ativado' if user.is_active else 'desativado'
        messages.info(request, f'Usuário "{user.username}" {estado}.')
    return redirect('usuario_lista')


# ===========================================================================
# Troca da própria senha (qualquer usuário logado)
# ===========================================================================
@login_required
def minha_senha(request):
    form = PasswordChangeForm(request.user, request.POST or None)
    for f in form.fields.values():
        f.widget.attrs.update({'class': 'form-control'})
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        update_session_auth_hash(request, user)  # mantém o usuário logado
        messages.success(request, 'Sua senha foi alterada com sucesso.')
        return redirect('dashboard')
    return render(request, 'cotacoes/minha_senha.html', {'form': form})
