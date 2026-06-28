# Guia de Deploy — Electrolux (VPS Hostinger + Nginx)

App Django 5 (formulário de cotação) em **electrolux.taxcode.com.br**.

> ⚠️ **Regra de ouro deste guia:** já existem **3 aplicações rodando** nesta VPS.
> Tudo aqui usa nomes **exclusivos com prefixo `electrolux`** (usuário, serviço,
> socket, server block). Nenhum recurso é compartilhado. Nunca editamos arquivos
> das outras apps, e sempre rodamos `nginx -t` antes de recarregar o Nginx.

**Convenções**
- `$` = comando no seu PC (Windows / PowerShell ou Git Bash)
- `#` = comando na VPS via SSH (como root ou com `sudo`)
- Caminho do app na VPS: `/var/www/electrolux`
- Domínio: `electrolux.taxcode.com.br`

---

## Visão geral da arquitetura

```
Internet ──> Nginx (já instalado, na frente das 3 apps)
                │  server_name electrolux.taxcode.com.br  (NOVO bloco, isolado)
                ▼
        Gunicorn (socket unix: /run/electrolux/gunicorn.sock)
                │  serviço systemd: electrolux.service
                ▼
        Django (config.wsgi) + SQLite (db.sqlite3)
```

---

## Etapa 0 — Reconhecimento (não muda nada, só observa)

Conecte na VPS e confira o terreno **antes** de criar qualquer coisa. Isso garante
que não vamos pisar em porta/serviço/arquivo já usado pelas outras apps.

```bash
$ ssh root@SEU_IP_DA_VPS

# Confirma que o Nginx é o proxy e está ativo
# systemctl status nginx --no-pager

# Lista os sites já configurados (NÃO vamos editar nenhum deles)
# ls -la /etc/nginx/sites-enabled/

# Lista os serviços das outras apps (gunicorn/uwsgi/node/etc.)
# systemctl list-units --type=service --state=running | grep -Ei 'gunicorn|django|uwsgi|node|web'

# Confirma que NÃO existe nada chamado "electrolux" ainda
# systemctl list-units | grep -i electrolux || echo "Livre: nenhum servico electrolux existe"
# ls /etc/nginx/sites-available/ | grep -i electrolux || echo "Livre: nenhum site electrolux existe"
```

Anote para si: qual versão de Python o sistema tem (`python3 --version`) e se já
existe `certbot` instalado (`which certbot`). Seguimos.

---

## Etapa 1 — Apontar o DNS do domínio

No painel onde o domínio **taxcode.com.br** é gerenciado (Hostinger hPanel →
*Domínios → DNS / Nameservers*, ou onde estiverem as outras apps):

| Tipo | Nome (Host) | Valor          | TTL  |
|------|-------------|----------------|------|
| A    | `electrolux`| `SEU_IP_DA_VPS`| 3600 |

> Use o **mesmo IP** das outras 3 apps. O Nginx separa pelo `server_name`.

Confirme a propagação (pode levar de minutos a algumas horas):

```bash
$ nslookup electrolux.taxcode.com.br
# deve responder com o IP da VPS
```

> Não avance para a Etapa 7 (SSL) enquanto o DNS não estiver resolvendo para a VPS,
> senão o Certbot falha na validação.

---

## Etapa 2 — Chave SSH entre a VPS e o GitHub (deploy key)

Para a VPS conseguir baixar o código do repositório privado sem digitar senha,
geramos uma chave SSH **na própria VPS** e cadastramos a parte pública no GitHub
como **Deploy Key** (acesso somente-leitura, exclusivo deste repositório — mais
seguro que usar sua conta pessoal).

**2.1 — Gerar a chave na VPS:**

```bash
# ssh-keygen -t ed25519 -C "electrolux-vps-deploy" -f ~/.ssh/electrolux_deploy -N ""
```
Isso cria dois arquivos: `electrolux_deploy` (privada) e `electrolux_deploy.pub` (pública).

**2.2 — Fazer o Git da VPS usar essa chave só para este repo** (cria/edita `~/.ssh/config`):

```bash
# cat >> ~/.ssh/config <<'EOF'

Host github-electrolux
    HostName github.com
    User git
    IdentityFile ~/.ssh/electrolux_deploy
    IdentitiesOnly yes
EOF
# chmod 600 ~/.ssh/config
```

**2.3 — Copiar a chave PÚBLICA:**

```bash
# cat ~/.ssh/electrolux_deploy.pub
```
Copie a linha inteira que aparecer (começa com `ssh-ed25519 ...`).

**2.4 — Cadastrar no GitHub:**
1. Abra o repositório `py4all1/formulario_de-_contacao` no GitHub
2. **Settings → Deploy keys → Add deploy key**
3. *Title:* `VPS Hostinger Electrolux`
4. *Key:* cole a chave pública
5. **Deixe "Allow write access" DESmarcado** (a VPS só precisa ler)
6. **Add key**

**2.5 — Testar a conexão:**

```bash
# ssh -T github-electrolux
# Resposta esperada: "Hi py4all1/formulario_de-_contacao! You've successfully authenticated..."
```

> Por causa do `Host github-electrolux` no `~/.ssh/config`, a URL do repositório na
> VPS será `git@github-electrolux:py4all1/formulario_de-_contacao.git` (usamos isso
> na Etapa 4).

---

## Etapa 3 — Enviar o projeto completo para o GitHub (no seu PC)

Hoje só o commit inicial está no repositório — o código ainda **não foi enviado**.
Faça isso a partir do seu PC, na pasta do projeto:

```powershell
$ cd "C:\Users\Open\OneDrive\Tax Code\WeFix\wefix_formulario_contacao"
$ git add -A
$ git status        # confira: NÃO deve listar venv/, db.sqlite3 nem staticfiles/
$ git commit -m "Projeto completo + arquivos de deploy (Nginx/Gunicorn/systemd)"
$ git push origin main
```

> O `.gitignore` já exclui `venv/`, `db.sqlite3`, `staticfiles/` e `media/`.
> A pasta `base/` (com o `.xlsm` que o app usa) **será** enviada — isso é correto,
> o app precisa dela em produção.

---

## Etapa 4 — Preparar o servidor e clonar o app

**4.1 — Pacotes do sistema** (se ainda não tiver; `apt` não reinstala o que já existe):

```bash
# apt update
# apt install -y python3 python3-venv python3-pip git
```

**4.2 — Criar um usuário de sistema dedicado** (isola a app das outras):

```bash
# adduser --system --group --home /var/www/electrolux electrolux
# usermod -aG www-data electrolux
```

**4.3 — Clonar o repositório** (usando o alias SSH da Etapa 2):

```bash
# git clone git@github-electrolux:py4all1/formulario_de-_contacao.git /var/www/electrolux/repo_tmp
# shopt -s dotglob && mv /var/www/electrolux/repo_tmp/* /var/www/electrolux/ && rmdir /var/www/electrolux/repo_tmp
```
> Alternativa mais simples se a pasta estiver vazia:
> `git clone git@github-electrolux:py4all1/formulario_de-_contacao.git /var/www/electrolux`
> (clone direto quando `/var/www/electrolux` ainda não tem conteúdo).

**4.4 — Criar o ambiente virtual e instalar dependências:**

```bash
# cd /var/www/electrolux
# python3 -m venv venv
# source venv/bin/activate
# pip install --upgrade pip
# pip install -r requirements.txt
# mkdir -p logs staticfiles
```

**4.5 — Criar o arquivo de variáveis de produção** `/etc/electrolux.env`:

Gere uma SECRET_KEY nova:
```bash
# python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```
Crie o arquivo (cole a chave gerada acima no lugar indicado):
```bash
# nano /etc/electrolux.env
```
Conteúdo (modelo em `deploy/.env.example`). **Coloque a `SECRET_KEY` entre aspas
simples** — ela costuma ter caracteres como `(` `)` `&` `$`:
```
DJANGO_SECRET_KEY='COLE_A_CHAVE_GERADA_AQUI'
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=electrolux.taxcode.com.br
DJANGO_CSRF_TRUSTED_ORIGINS=https://electrolux.taxcode.com.br
```
Proteja o arquivo:
```bash
# chmod 640 /etc/electrolux.env
# chown root:electrolux /etc/electrolux.env
```

**4.6 — Preparar banco, dados e estáticos** (carregando o env):

```bash
# cd /var/www/electrolux && source venv/bin/activate
# set -a && source /etc/electrolux.env && set +a
# python manage.py migrate
# python manage.py importar_dados        # carrega filiais / códigos (seed_data.json)
# python manage.py collectstatic --noinput
# python manage.py createsuperuser        # crie o login do fornecedor (superusuário)
```

**4.7 — Ajustar dono dos arquivos** (a app roda como usuário `electrolux`):

```bash
# chown -R electrolux:www-data /var/www/electrolux
```

---

## Etapa 5 — Serviço systemd (Gunicorn)

Copie o modelo versionado do projeto e ative:

```bash
# cp /var/www/electrolux/deploy/electrolux.service /etc/systemd/system/electrolux.service
# systemctl daemon-reload
# systemctl enable --now electrolux
# systemctl status electrolux --no-pager
```

Você deve ver `active (running)` e o socket `/run/electrolux/gunicorn.sock` criado.
Se der erro, veja: `journalctl -u electrolux -n 50 --no-pager`.

---

## Etapa 6 — Nginx (server block isolado)

```bash
# cp /var/www/electrolux/deploy/electrolux.taxcode.com.br.nginx /etc/nginx/sites-available/electrolux.taxcode.com.br
# ln -s /etc/nginx/sites-available/electrolux.taxcode.com.br /etc/nginx/sites-enabled/

# TESTE a sintaxe ANTES de recarregar (não derruba as outras apps)
# nginx -t

# Só recarregue se o teste passou (reload não dá downtime nos outros sites)
# systemctl reload nginx
```

Teste em HTTP: abra `http://electrolux.taxcode.com.br` — o app deve responder
(ainda sem cadeado).

---

## Etapa 7 — SSL / HTTPS (Certbot — Let's Encrypt)

```bash
# Instale o Certbot se ainda não houver (cheque com: which certbot)
# apt install -y certbot python3-certbot-nginx

# Emite o certificado SÓ para este domínio e edita SÓ este server block
# certbot --nginx -d electrolux.taxcode.com.br --redirect -m taxgoldbr@gmail.com --agree-tos --no-eff-email
```

O Certbot adiciona o bloco `443` (HTTPS) e o redirect `80 → 443` automaticamente,
mexendo **apenas** no arquivo do electrolux. A renovação é automática (`certbot.timer`).

Teste final: `https://electrolux.taxcode.com.br` com cadeado. ✅

---

## Etapa 8 — Liberar o `deploy.sh` (atualizações futuras)

O script reinicia o serviço, o que exige `sudo`. Para que o usuário `electrolux`
faça isso sem senha (apenas este serviço, nada mais):

```bash
# echo 'electrolux ALL=(root) NOPASSWD: /bin/systemctl restart electrolux, /bin/systemctl status electrolux' > /etc/sudoers.d/electrolux
# chmod 440 /etc/sudoers.d/electrolux
# chmod +x /var/www/electrolux/deploy/deploy.sh
```

---

## 🔁 Atualizar a aplicação no dia a dia

Sempre que você fizer mudanças no código:

**1. No seu PC:**
```powershell
$ git add -A
$ git commit -m "minha alteração"
$ git push origin main
```

**2. Na VPS** (pode rodar como `root` ou com qualquer usuário sudo):
```bash
# /var/www/electrolux/deploy/deploy.sh
```

O script detecta se foi chamado por outro usuário e **se reexecuta sozinho como
`electrolux`** (o dono do repositório). Isso evita o erro do Git
`dubious ownership` e garante que banco/estáticos fiquem com o dono certo.

> Se preferir ser explícito, o equivalente manual é:
> `sudo -H -u electrolux bash /var/www/electrolux/deploy/deploy.sh`

O `deploy.sh` faz tudo: `git pull` → `pip install` → `migrate` → `collectstatic`
→ reinicia **só** o serviço `electrolux`. O banco `db.sqlite3` **não é tocado**
(fica fora do Git), então **nenhum dado é perdido** num deploy.

> **Por que não rodar como `root` direto?** O Gunicorn roda como `electrolux` e o
> banco SQLite precisa ser gravável por ele. Se o deploy rodasse como root, o
> `migrate`/`collectstatic` criariam arquivos com dono `root` e o app passaria a
> dar erro de permissão ao escrever no banco. Por isso o script força `electrolux`.

---

## Comandos úteis / solução de problemas

```bash
# Ver logs da aplicação em tempo real
# journalctl -u electrolux -f

# Logs do Gunicorn e do Nginx (deste app)
# tail -f /var/www/electrolux/logs/error.log
# tail -f /var/log/nginx/electrolux.error.log

# Reiniciar / parar SÓ esta app (não afeta as outras)
# systemctl restart electrolux
# systemctl stop electrolux

# Erro 502 Bad Gateway  -> o Gunicorn caiu. Veja: journalctl -u electrolux -n 50
# Erro 400 Bad Request  -> falta o domínio em DJANGO_ALLOWED_HOSTS (/etc/electrolux.env)
# CSS/JS sem estilo      -> rode collectstatic e confira o alias /static/ no Nginx
# "DisallowedHost"       -> idem ALLOWED_HOSTS; após editar o .env, systemctl restart electrolux
```

---

## Resumo dos arquivos versionados de deploy

| Arquivo | Função |
|---|---|
| `deploy/.env.example` | Modelo do `/etc/electrolux.env` (variáveis de produção) |
| `deploy/electrolux.service` | Serviço systemd do Gunicorn (vai p/ `/etc/systemd/system/`) |
| `deploy/electrolux.taxcode.com.br.nginx` | Server block do Nginx (vai p/ `sites-available/`) |
| `deploy/deploy.sh` | Script de atualização (rodar na VPS) |
| `config/settings.py` | Agora lê configs de produção via variáveis de ambiente |
| `.gitattributes` | Mantém `deploy.sh` com fim de linha LF (Unix) |
