from django.shortcuts import redirect
from django.urls import reverse


class LicencaMiddleware:
    """Bloqueia usuários do cliente (não-superusuário) quando a licença está
    expirada ou inexistente. O fornecedor (superusuário) nunca é bloqueado.

    Páginas públicas (formulário por token, login, logout, estáticos) e a
    própria página de bloqueio permanecem acessíveis.
    """

    ALLOW_PREFIXES = ('/static/', '/media/', '/f/', '/termos/', '/login/', '/logout/')

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, 'user', None)
        if user and user.is_authenticated and not user.is_superuser:
            path = request.path
            bloqueio_url = reverse('licenca_bloqueada')
            liberado = path == bloqueio_url or path.startswith(self.ALLOW_PREFIXES)
            if not liberado:
                from .models import licenca_do_usuario
                lic = licenca_do_usuario(user)
                if lic is None or lic.expirada:
                    return redirect('licenca_bloqueada')
        return self.get_response(request)
