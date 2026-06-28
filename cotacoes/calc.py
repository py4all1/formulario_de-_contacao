"""Motor de cálculo — espelha as fórmulas da macro original (aba Formulário).

Percentuais são tratados como fração (ex.: 0,05 = 5%), igual à planilha.
"""
from decimal import Decimal, ROUND_HALF_UP

Q2 = Decimal('0.01')


def _d(v):
    if v in (None, ''):
        return Decimal('0')
    if isinstance(v, Decimal):
        return v
    return Decimal(str(v))


def round2(v):
    return _d(v).quantize(Q2, rounding=ROUND_HALF_UP)


CEM = Decimal('100')


def pct(v):
    """Converte um percentual informado como número inteiro (5 = 5%) em fração."""
    return _d(v) / CEM


# ---------------------------------------------------------------------------
# Serviços
# ---------------------------------------------------------------------------
def calcular_servico(valor, perc_iss, perc_inss, perc_csrf, perc_irrf):
    """Total retido = Valor × (%ISS+%INSS+%CSRF+%IRRF) ; Líquido = Valor − Retido.

    Os percentuais são informados como número inteiro (ex.: 5 = 5%).
    """
    b = _d(valor)
    total_retido = (b * pct(perc_iss) + b * pct(perc_inss)
                    + b * pct(perc_csrf) + b * pct(perc_irrf))
    total_retido = round2(total_retido)
    valor_liquido = round2(b - total_retido)
    return {'total_retido': total_retido, 'valor_liquido': valor_liquido}


# ---------------------------------------------------------------------------
# Mercadoria
# ---------------------------------------------------------------------------
CATEGORIAS_COM_IPI_NA_BASE = ('Uso ou Consumo', 'Ativo Fixo')


def calcular_mercadoria(quantidade, valor_unitario, categoria, perc_ipi,
                        perc_icms, perc_reducao_base, icms_st):
    """Replica:
        N (valor_ipi)  = ROUND((C*F)*M, 2)
        Q (base_icms)  = se categoria em (Uso/Consumo, Ativo Fixo):
                            ((C*F)+N) - ((C*F)+N)*P
                         senão:
                            (C*F) - (C*F)*P
        R (valor_icms) = Q * O
        T (total)      = Q + N + S
    onde C=qtd, F=unit, M=IPI%, O=ICMS%, P=%redução base, S=ICMS ST.
    """
    c = _d(quantidade)
    f = _d(valor_unitario)
    bruto = c * f
    valor_ipi = round2(bruto * pct(perc_ipi))
    p = pct(perc_reducao_base)
    if (categoria or '') in CATEGORIAS_COM_IPI_NA_BASE:
        base = (bruto + valor_ipi) - (bruto + valor_ipi) * p
    else:
        base = bruto - bruto * p
    base_icms = round2(base)
    valor_icms = round2(base_icms * pct(perc_icms))
    st = round2(icms_st)
    valor_total = round2(base_icms + valor_ipi + st)
    return {
        'valor_ipi': valor_ipi,
        'base_icms': base_icms,
        'valor_icms': valor_icms,
        'icms_st': st,
        'valor_total': valor_total,
    }


def aplicar_calculo_servico(item):
    r = calcular_servico(item.valor_servico, item.perc_iss, item.perc_inss,
                         item.perc_csrf, item.perc_irrf)
    item.total_retido = r['total_retido']
    item.valor_liquido = r['valor_liquido']
    return item


def aplicar_calculo_mercadoria(item):
    r = calcular_mercadoria(item.quantidade, item.valor_unitario, item.categoria,
                            item.perc_ipi, item.perc_icms, item.perc_reducao_base,
                            item.icms_st)
    item.valor_ipi = r['valor_ipi']
    item.base_icms = r['base_icms']
    item.valor_icms = r['valor_icms']
    item.icms_st = r['icms_st']
    item.valor_total = r['valor_total']
    return item


# ---------------------------------------------------------------------------
# Lookup de código SAP (tabela CONSOLIDADO)
# ---------------------------------------------------------------------------
def _fmt_pct(v):
    """Reproduz a concatenação da macro (A = C&H&G&F → cod&IRRF&CSRF&INSS).
    Como o formato exato da chave varia, fazemos a busca pela alíquota CSRF.
    """
    d = _d(v)
    if d == d.to_integral():
        return str(int(d))
    return str(d.normalize())


def buscar_codigo_sap(codigo_servico, perc_csrf=None):
    """Busca o código SAP a partir do código de atividade.

    A macro usa uma chave concatenada (código + retenções). Aqui priorizamos
    o cenário cujo CSRF (alíquota) bate com o informado; senão devolvemos o
    primeiro cenário do código. Retorna '' se nada for encontrado.
    """
    from .models import CodigoSAP
    qs = CodigoSAP.objects.filter(codigo_atividade=codigo_servico)
    if not qs.exists():
        return ''
    if perc_csrf is not None:
        # perc_csrf é informado como inteiro (ex.: 3,5 = 3,5%); a alíquota da
        # tabela CONSOLIDADO está em fração (0,035).
        alvo = pct(perc_csrf)
        match = qs.filter(aliquota=alvo).first()
        if match:
            return match.codigo_sap
    primeiro = qs.order_by('cenario').first()
    return primeiro.codigo_sap if primeiro else ''
