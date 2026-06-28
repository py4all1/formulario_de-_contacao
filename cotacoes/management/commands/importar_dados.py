import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from cotacoes.models import Filial, CodigoAtividade, CodigoSAP


class Command(BaseCommand):
    help = 'Importa filiais, códigos de atividade e códigos SAP da macro (fixture seed_data.json).'

    def add_arguments(self, parser):
        parser.add_argument('--arquivo', default=None,
                            help='Caminho do JSON de seed (padrão: fixtures/seed_data.json).')
        parser.add_argument('--limpar', action='store_true',
                            help='Apaga os registros das tabelas de apoio antes de importar.')

    def handle(self, *args, **opts):
        caminho = opts['arquivo'] or (
            Path(settings.BASE_DIR) / 'cotacoes' / 'fixtures' / 'seed_data.json')
        caminho = Path(caminho)
        if not caminho.exists():
            self.stderr.write(self.style.ERROR(f'Arquivo não encontrado: {caminho}'))
            return

        data = json.loads(caminho.read_text(encoding='utf-8'))

        with transaction.atomic():
            if opts['limpar']:
                Filial.objects.all().delete()
                CodigoAtividade.objects.all().delete()
                CodigoSAP.objects.all().delete()

            nf = self._importar_filiais(data.get('filiais', []))
            na = self._importar_atividades(data.get('atividades', []))
            ns = self._importar_sap(data.get('sap', []))

        self.stdout.write(self.style.SUCCESS(
            f'Importação concluída: {nf} filiais, {na} atividades, {ns} códigos SAP.'))

    def _importar_filiais(self, rows):
        n = 0
        for r in rows:
            planta = (r.get('planta') or '').strip()
            cnpj = (r.get('cnpj') or '').strip()
            if not planta and not cnpj:
                continue
            Filial.objects.update_or_create(
                planta=planta or f'Filial {cnpj}', cnpj=cnpj,
                defaults={
                    'empresa': r.get('empresa') or '',
                    'cia': r.get('cia') or '',
                    'municipio': r.get('municipio') or '',
                    'uf': r.get('uf') or '',
                    'endereco': r.get('endereco') or '',
                    'cep': r.get('cep') or '',
                })
            n += 1
        return n

    def _importar_atividades(self, rows):
        n = 0
        for r in rows:
            codigo = (r.get('codigo') or '').strip()
            if not codigo:
                continue
            CodigoAtividade.objects.update_or_create(
                codigo=codigo,
                defaults={
                    'atividade': r.get('atividade') or '',
                    'descricao': r.get('descricao') or '',
                })
            n += 1
        return n

    def _importar_sap(self, rows):
        n = 0
        for r in rows:
            sap = (r.get('codigo_sap') or '').strip()
            if not sap:
                continue
            aliquota = r.get('aliquota')
            CodigoSAP.objects.create(
                cenario=r.get('cenario'),
                codigo_atividade=(r.get('codigo_atividade') or '').strip(),
                codigo_sap=sap,
                aliquota=aliquota if aliquota is not None else None,
                chave1=(r.get('chave1') or '')[:60],
                chave2=(r.get('chave2') or '')[:60],
            )
            n += 1
        return n
