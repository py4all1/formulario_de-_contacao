#!/usr/bin/env bash
# =============================================================================
# Script de DEPLOY / ATUALIZACAO - app Electrolux
# Local na VPS: /var/www/electrolux/deploy/deploy.sh
#
# Uso:
#   cd /var/www/electrolux && ./deploy/deploy.sh
#
# O que faz (em ordem, parando no primeiro erro):
#   1. Garante que esta na pasta certa
#   2. Baixa o codigo novo do GitHub (git pull)
#   3. Atualiza dependencias do venv
#   4. Aplica migracoes do banco
#   5. Coleta arquivos estaticos
#   6. Reinicia SOMENTE o servico "electrolux" (nao toca nas outras apps)
#   7. Mostra o status final
#
# NAO mexe em: banco de dados (db.sqlite3 fica fora do Git), Nginx,
# outras aplicacoes, nem no /etc/electrolux.env.
# =============================================================================
set -euo pipefail

APP_DIR="/var/www/electrolux"
SERVICE="electrolux"
BRANCH="${1:-main}"   # opcional: ./deploy/deploy.sh main

cd "$APP_DIR"

echo "==> [1/6] Pasta: $(pwd)  |  Branch: $BRANCH"

echo "==> [2/6] Atualizando codigo do GitHub..."
git fetch origin "$BRANCH"
git reset --hard "origin/$BRANCH"   # garante igual ao remoto, descarta lixo local

echo "==> [3/6] Atualizando dependencias (venv)..."
source venv/bin/activate
pip install --upgrade pip >/dev/null
pip install -r requirements.txt

# Carrega as variaveis de producao para os comandos manage.py
set -a
# shellcheck disable=SC1091
source /etc/electrolux.env
set +a

echo "==> [4/6] Aplicando migracoes..."
python manage.py migrate --noinput

echo "==> [5/6] Coletando arquivos estaticos..."
python manage.py collectstatic --noinput

echo "==> [6/6] Reiniciando o servico $SERVICE..."
sudo systemctl restart "$SERVICE"

echo ""
echo "==> Deploy concluido. Status do servico:"
sudo systemctl status "$SERVICE" --no-pager --lines 5

echo ""
echo "OK! https://electrolux.taxcode.com.br"
