#!/usr/bin/env bash
# =============================================================================
# Script de DEPLOY / ATUALIZACAO - app Electrolux
# Local na VPS: /var/www/electrolux/deploy/deploy.sh
#
# Uso (de qualquer usuario com sudo, ou ja como electrolux):
#   /var/www/electrolux/deploy/deploy.sh
# Se chamado como root, ele se reexecuta sozinho como o usuario "electrolux".
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
APP_USER="electrolux"
SERVICE="electrolux"
BRANCH="${1:-main}"   # opcional: ./deploy/deploy.sh main

# Este app roda como o usuario "electrolux" e o repositorio pertence a ele.
# Se alguem chamar o script como root (ou outro usuario), reexecuta como
# electrolux para evitar "dubious ownership" no git e arquivos com dono errado.
if [ "$(id -un)" != "$APP_USER" ]; then
    echo "==> Reexecutando como usuario '$APP_USER'..."
    exec sudo -H -u "$APP_USER" bash "$APP_DIR/deploy/deploy.sh" "$@"
fi

cd "$APP_DIR"

echo "==> [1/6] Pasta: $(pwd)  |  Branch: $BRANCH"

echo "==> [2/6] Atualizando codigo do GitHub..."
git fetch origin "$BRANCH"
git reset --hard "origin/$BRANCH"   # garante igual ao remoto, descarta lixo local

echo "==> [3/6] Atualizando dependencias (venv)..."
source venv/bin/activate
pip install --upgrade pip >/dev/null
pip install -r requirements.txt

# Carrega as variaveis de producao para os comandos manage.py.
# Lemos linha-a-linha (sem "source") para tratar o valor como texto literal,
# igual ao systemd faz. Assim caracteres especiais da SECRET_KEY como ( ) & $
# nao quebram o script, com ou sem aspas no arquivo.
ENV_FILE="/etc/electrolux.env"
if [ -f "$ENV_FILE" ]; then
    while IFS= read -r line || [ -n "$line" ]; do
        case "$line" in
            ''|'#'*) continue ;;          # ignora linhas vazias e comentarios
        esac
        key="${line%%=*}"
        val="${line#*=}"
        # remove aspas externas (simples ou duplas), se houver
        val="${val%\"}"; val="${val#\"}"
        val="${val%\'}"; val="${val#\'}"
        export "$key=$val"
    done < "$ENV_FILE"
else
    echo "AVISO: $ENV_FILE nao encontrado." >&2
fi

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
