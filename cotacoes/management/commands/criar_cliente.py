from datetime import date

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from cotacoes.models import Licenca, PerfilUsuario


class Command(BaseCommand):
    help = ('Cria um usuário do cliente (sem privilégios de administrador) e, '
            'opcionalmente, a licença com data de vencimento.')

    def add_arguments(self, parser):
        parser.add_argument('--username', required=True)
        parser.add_argument('--password', required=True)
        parser.add_argument('--email', default='')
        parser.add_argument('--cliente', default='Electrolux',
                            help='Nome do cliente para a licença.')
        parser.add_argument('--vencimento', default=None,
                            help='Data de vencimento do contrato (AAAA-MM-DD). '
                                 'Se informada, cria/atualiza a licença vigente.')
        parser.add_argument('--valor', default='0', help='Valor anual do contrato.')

    def handle(self, *args, **opts):
        User = get_user_model()
        username = opts['username']

        if User.objects.filter(username=username).exists():
            raise CommandError(f'Usuário "{username}" já existe.')

        user = User.objects.create_user(
            username=username,
            password=opts['password'],
            email=opts['email'],
            is_staff=False,        # sem acesso ao admin do Django
            is_superuser=False,    # sem privilégios de administrador
        )
        self.stdout.write(self.style.SUCCESS(
            f'Usuário cliente "{user.username}" criado (sem privilégios de admin).'))

        lic = None
        if opts['vencimento']:
            try:
                venc = date.fromisoformat(opts['vencimento'])
            except ValueError:
                raise CommandError('--vencimento deve estar no formato AAAA-MM-DD.')
            lic, created = Licenca.objects.get_or_create(
                cliente=opts['cliente'],
                defaults={
                    'data_inicio': date.today(),
                    'data_vencimento': venc,
                    'valor_atual': opts['valor'],
                    'ativa': True,
                },
            )
            if not created:
                lic.data_vencimento = venc
                lic.valor_atual = opts['valor']
                lic.ativa = True
                lic.save()
            self.stdout.write(self.style.SUCCESS(
                f'Licença de "{lic.cliente}" com vencimento em {venc:%d/%m/%Y}.'))
        else:
            # vincula à licença existente do cliente, se houver
            lic = Licenca.objects.filter(cliente=opts['cliente'], ativa=True).first()

        PerfilUsuario.objects.update_or_create(user=user, defaults={'licenca': lic})
        if lic:
            self.stdout.write(self.style.SUCCESS(
                f'Usuário vinculado à empresa "{lic.cliente}".'))
