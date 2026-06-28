from .models import licenca_vigente, licenca_do_usuario


def licenca(request):
    """Expõe a licença relevante e o estado de alerta/expiração aos templates.

    Para um usuário logado usa a licença do seu perfil; caso contrário, a vigente.
    """
    user = getattr(request, 'user', None)
    if user is not None and user.is_authenticated and not user.is_superuser:
        lic = licenca_do_usuario(user)
    else:
        lic = licenca_vigente()
    if not lic:
        return {'licenca': None}
    return {
        'licenca': lic,
        'licenca_dias': lic.dias_restantes,
        'licenca_expirada': lic.expirada,
        'licenca_alerta': lic.em_alerta,
    }
