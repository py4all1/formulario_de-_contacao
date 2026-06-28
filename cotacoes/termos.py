"""Termos de aceite da Electrolux exibidos no formulário.

Os documentos originais (.docx) ficam em ``base/`` e são servidos para download;
o texto é extraído para exibição inline (em seções recolhíveis).
"""
import zipfile
from functools import lru_cache
from pathlib import Path
from xml.etree import ElementTree as ET

from django.conf import settings

_W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'

# slug -> metadados do documento
TERMOS = [
    {
        'slug': 'ehs',
        'titulo': 'Manual de EHS para Prestadores de Serviço',
        'arquivo': 'A1. Manaual de EHS para prestadores de serviço.docx',
    },
    {
        'slug': 'contratacao',
        'titulo': 'POS.SAF-7 — Instrução para Contratação de Serviços',
        'arquivo': 'POS.SAF-7 Instrução para contratação de serviços.docx',
    },
    {
        'slug': 'condicoes',
        'titulo': 'Termos e Condições Gerais de Compra (Serviços)',
        'arquivo': 'TERMOS E CONDIÇÕES GERAIS DE COMPRA DA ELECTROLUX - Apenas Serviços.docx',
    },
]

TERMOS_POR_SLUG = {t['slug']: t for t in TERMOS}


def caminho_arquivo(slug):
    termo = TERMOS_POR_SLUG.get(slug)
    if not termo:
        return None
    return Path(settings.BASE_DIR) / 'base' / termo['arquivo']


@lru_cache(maxsize=8)
def extrair_paragrafos(slug):
    """Extrai os parágrafos de texto do .docx (ignora imagens/formatação)."""
    caminho = caminho_arquivo(slug)
    if not caminho or not caminho.exists():
        return []
    try:
        with zipfile.ZipFile(caminho) as z:
            root = ET.fromstring(z.read('word/document.xml'))
    except (zipfile.BadZipFile, KeyError, ET.ParseError):
        return []
    paragrafos = []
    for p in root.iter(_W + 'p'):
        texto = ''.join(t.text or '' for t in p.iter(_W + 't')).strip()
        if texto:
            paragrafos.append(texto)
    return paragrafos


def termos_para_template():
    """Lista de termos com os parágrafos extraídos, para renderizar no form."""
    dados = []
    for t in TERMOS:
        dados.append({
            'slug': t['slug'],
            'titulo': t['titulo'],
            'paragrafos': extrair_paragrafos(t['slug']),
        })
    return dados
