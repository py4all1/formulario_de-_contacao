# WeFix — Formulário de Cotação (Electrolux)

Sistema web em Django onde fornecedores preenchem um **formulário dinâmico de
cotação/cadastro** (baseado na macro `Electrolux macro_ajustada`) e o
proprietário consulta as cotações recebidas e faz **download em JSON, Excel e PDF**.

## Principais recursos

- **Formulário público por link/token único** (sem login para o fornecedor).
- **Campos dinâmicos**: as seções de *Serviços* e/ou *Mercadoria* aparecem
  conforme o "Tipo de fornecimento" escolhido.
- **Cálculo ao vivo** (mesmas fórmulas da macro):
  - Serviços: `Total retido = Valor × (%ISS+%INSS+%CSRF+%IRRF)`; `Líquido = Valor − Retido`.
  - Mercadoria: `Valor IPI = (Qtd×Unit)×IPI%`; base ICMS com/sem IPI conforme categoria
    (Uso ou Consumo / Ativo Fixo), redução de base, `Valor ICMS = Base×ICMS%`,
    `Total = Base + IPI + ST`.
  - Os valores são **recalculados no servidor** ao salvar (fonte autoritativa).
- **Preenchimento automático** de filial (CNPJ/planta/endereço/UF/CEP), descrição
  do código de serviço e **código SAP** (tabela CONSOLIDADO).
- **Área do proprietário** (login): painel, lista com busca/filtro, detalhe e exportações.
- **Exportações**: JSON, Excel (.xlsx, abas Cotação/Serviços/Mercadorias) e PDF.

## Estrutura

```
config/            # projeto Django (settings, urls)
cotacoes/          # app principal
  models.py        # Filial, CodigoAtividade, CodigoSAP, Convite, Cotacao, ItemServico, ItemMercadoria
  calc.py          # motor de cálculo (espelha as fórmulas da macro)
  exports.py       # geração JSON / Excel / PDF
  forms.py         # formulário + formsets de itens
  views.py         # área pública (token) e área do proprietário
  fixtures/seed_data.json          # dados extraídos da macro
  management/commands/importar_dados.py
templates/         # base, login, dashboard, lista, detalhe, convites, formulário público
static/            # css/app.css, js/form.js
base/              # arquivos originais (macro .xlsm e documentos)
```

## Como rodar (Windows / PowerShell)

```powershell
pip install -r requirements.txt
python manage.py migrate
python manage.py importar_dados          # carrega filiais, atividades e códigos SAP
python manage.py createsuperuser         # cria o usuário do proprietário
python manage.py runserver
```

- Área do proprietário: <http://127.0.0.1:8000/> (requer login)
- Admin do Django: <http://127.0.0.1:8000/admin/>

### Fluxo de uso

1. O proprietário acessa **Convites** e gera um link único.
2. Envia o link ao fornecedor (e-mail/WhatsApp).
3. O fornecedor abre o link, preenche o formulário e envia.
4. A cotação aparece em **Cotações**, pronta para download (JSON/Excel/PDF).

## Observações sobre cálculos e SAP

- Os percentuais são informados como **número inteiro/percentual** (ex.: `5` = 5%, `4.65` = 4,65%);
  o sistema divide por 100 internamente (frontend e backend).
- O **código SAP** é resolvido pelo código de atividade e, quando possível, pela
  alíquota de CSRF (tabela CONSOLIDADO). A macro usa uma chave concatenada de
  retenções; a busca aqui prioriza o cenário cuja alíquota corresponde e, na
  ausência, usa o primeiro cenário do código. Esse mapeamento pode ser refinado
  conforme as regras finais do SAP.

## Próximos passos sugeridos

- Refinar a chave exata do código SAP conforme as regras de negócio.
- Envio automático do convite por e-mail.
- Configuração de produção (DEBUG=False, SECRET_KEY via variável de ambiente,
  banco PostgreSQL, coleta de estáticos).
