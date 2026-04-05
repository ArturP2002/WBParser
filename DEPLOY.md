# Подробная инструкция: развёртывание WBParser на сервере через GitHub

Документ рассчитан на то, что вы впервые поднимаете сервис с нуля. ОС: **Ubuntu 22.04 / 24.04** (логика для Debian та же). Если у вас другой дистрибутив — команды пакетного менеджера замените на свои.

---

## Что вообще запускается

Одна команда `python main.py` поднимает **всё сразу**:

| Часть | Назначение |
|--------|------------|
| Парсер | Опрос Wildberries, запись в БД, постановка событий в Redis |
| Telegram-бот | Команды пользователей (aiogram, **long polling**) |
| Нотификатор | Чтение очереди из Redis, отправка сообщений в Telegram |
| Retention | Периодическая очистка старых записей в БД |
| Observability | HTTP **health/metrics** (по умолчанию порт **9090**) |

Отдельный веб-сервер (Nginx) для работы бота **не обязателен**: бот ходит к Telegram сам. Nginx может понадобиться только если вы захотите проксировать или закрывать доступ к `:9090`.

Нужны **PostgreSQL**, **Redis** и **исходящий интернет** (WB + `api.telegram.org`). Прокси **`PROXY_LIST`** в `.env` для WB сильно рекомендуются на проде.

### Рекомендуемый порядок (краткая дорожная карта)

1. **Часть A** — репозиторий на GitHub, убедиться что `.env` не в git.  
2. **Часть B** — зайти на сервер по SSH, `apt update`, поставить `git`, `build-essential`, при необходимости `python3-dev`, `libpq-dev`.  
3. **Часть C** — (по желанию) отдельный пользователь `wbparser`.  
4. **Части D и E** — установить и запустить PostgreSQL и Redis, создать БД и пользователя.  
5. **Часть G** — `git clone` проекта в `~/apps/WBParser`.  
6. **Части F и H** — Python 3.11+, `venv`, `pip install -r requirements.txt`.  
7. **Часть I** — создать `.env` на сервере (токен, `DATABASE_URL`, `REDIS_URL`, прокси).  
8. **Часть J** — `alembic upgrade head`.  
9. **Часть K** — ручной `python main.py`, проверка бота и `/health/live`.  
10. **Часть L** — unit systemd для автозапуска.  
11. **Части M–Q** — firewall, обновления, бэкапы, типовые сбои.

---

## Минимальные требования к серверу

- **CPU:** 2 ядра комфортно; 1 ядро может не хватить на установку `sentence-transformers` / сборку зависимостей.
- **RAM:** от **2 ГБ**; для `pip install -r requirements.txt` с ML-зависимостями лучше **4 ГБ** или **swap 2–4 ГБ**, иначе процесс установки упрётся в OOM.
- **Диск:** **10+ ГБ** свободного места под venv и кэш pip.
- **Доступ:** SSH под вашим пользователем (или под `root`, если так заведено у провайдера).

---

## Часть A. Подготовка GitHub (на вашем компьютере)

### A1. Проверьте, что секреты не уйдут в репозиторий

В корне проекта должен быть **`.gitignore`** с строками вроде `.env`, `venv/`, `.venv/`.

Перед первым коммитом выполните:

```bash
cd /путь/к/WBParser
git status
```

Убедитесь, что **`.env` не в списке добавляемых файлов**. Если Git его показывает — **не коммитьте**; добавьте `.env` в `.gitignore`.

### A2. Создайте репозиторий на GitHub

1. Зайдите на https://github.com/new  
2. Имя репозитория — например `WBParser`  
3. **Private** — предпочтительно (код без секретов, но приватность снимает лишний риск)  
4. Без README / .gitignore с сайта (у вас уже локальный проект)  
5. Нажмите **Create repository**

GitHub покажет URL вида:

- HTTPS: `https://github.com/ВАШ_ЛОГИН/WBParser.git`  
- SSH: `git@github.com:ВАШ_ЛОГИН/WBParser.git`

### A3. Первый push кода

Если в папке ещё **нет** git:

```bash
cd /путь/к/WBParser
git init
git add .
git commit -m "Initial commit: WBParser"
git branch -M main
git remote add origin https://github.com/ВАШ_ЛОГИН/WBParser.git
git push -u origin main
```

Если git **уже** есть — только добавьте `remote` и `push`:

```bash
git remote add origin https://github.com/ВАШ_ЛОГИН/WBParser.git
git branch -M main
git push -u origin main
```

При запросе логина GitHub:

- **Логин:** ваш GitHub username  
- **Пароль:** не пароль от аккаунта, а **Personal Access Token (PAT)**  

Как сделать PAT (классический):

1. GitHub → **Settings** → **Developer settings** → **Personal access tokens** → **Tokens (classic)**  
2. **Generate new token**  
3. Включите scope **`repo`** (для приватного репозитория)  
4. Скопируйте token один раз и храните в менеджере паролей — при `git push` вставляйте его вместо пароля  

### A4. Сохраните секреты для сервера отдельно

Скопируйте содержимое локального **`.env`** в менеджер паролей или в зашифрованную заметку. На сервере вы создадите **новый** `.env` вручную (или сольёте с локального **без** передачи через git).

---

## Часть B. Вход на сервер по SSH

С вашего компьютера:

```bash
ssh ваш_пользователь@IP_ИЛИ_ДОМЕН
```

Если ключ не настроен, провайдер выдаст пароль. После входа обновите пакеты (Ubuntu):

```bash
sudo apt update
sudo apt upgrade -y
```

Установите инструменты, которые понадобятся дальше:

```bash
sudo apt install -y git curl ca-certificates build-essential
```

Для сборки некоторых Python-зависимостей может понадобиться:

```bash
sudo apt install -y python3-dev python3-venv libpq-dev
```

---

## Часть C. Пользователь для сервиса (рекомендуется)

Чтобы бот не работал от `root`, создайте отдельного пользователя:

```bash
sudo adduser wbparser
```

Задайте пароль или оставьте вход **только по SSH-ключу** (настройка ключей для второго пользователя — по желанию). Дальше:

```bash
sudo usermod -aG sudo wbparser   # только если этому пользователю нужен sudo
sudo su - wbparser
mkdir -p ~/apps
cd ~/apps
```

Все следующие команды **в части D–J** выполняйте от **`wbparser`**, если создали его; пути тогда `/home/wbparser/apps/WBParser`. Если работаете под другим пользователем — замените `/home/wbparser` на `/home/ваш_логин`.

---

## Часть D. PostgreSQL на сервере

### D1. Установка

```bash
sudo apt install -y postgresql postgresql-contrib
sudo systemctl enable postgresql
sudo systemctl start postgresql
sudo systemctl status postgresql
```

Должно быть `active (running)`.

### D2. Создание БД и пользователя

Подставьте **свой** пароль вместо `СЛОЖНЫЙ_ПАРОЛЬ` (латиница, цифры, без пробелов или экранируйте спецсимволы в URL — см. ниже).

```bash
sudo -u postgres psql -c "CREATE USER wb_parser_bot WITH PASSWORD 'СЛОЖНЫЙ_ПАРОЛЬ';"
sudo -u postgres psql -c "CREATE DATABASE wb_parser_bot OWNER wb_parser_bot ENCODING 'UTF8' TEMPLATE template0;"
```

Проверка:

```bash
sudo -u postgres psql -c "\l" | grep wb_parser
```

### D3. Строка `DATABASE_URL` для `.env`

Формат для этого проекта — **обязательно** `postgresql+asyncpg://`:

```env
DATABASE_URL=postgresql+asyncpg://wb_parser_bot:СЛОЖНЫЙ_ПАРОЛЬ@127.0.0.1:5432/wb_parser_bot
```

Если в пароле есть символы вроде `@`, `#`, `%`, их нужно **URL-кодировать** в строке подключения (например `%` → `%25`). Проще изначально задать пароль без таких символов.

Postgres по умолчанию слушает только `localhost` — для одного сервера с приложением этого достаточно.

---

## Часть E. Redis на сервере

```bash
sudo apt install -y redis-server
sudo systemctl enable redis-server
sudo systemctl start redis-server
redis-cli ping
```

Ответ должен быть `PONG`.

Строка для `.env`:

```env
REDIS_URL=redis://127.0.0.1:6379/0
```

Если включите пароль на Redis — формат будет `redis://:ПАРОЛЬ@127.0.0.1:6379/0` (см. документацию redis).

**Безопасность:** не открывайте порт Redis (`6379`) в интернет без пароля и firewall.

---

## Часть F. Python 3 и виртуальное окружение

Проверьте версию:

```bash
python3 --version
```

Нужен **Python 3.11 или новее**.

- На **Ubuntu 24.04** пакет `python3` обычно уже **3.12** — можно сразу использовать `python3 -m venv .venv`.
- На **Ubuntu 22.04** по умолчанию часто **3.10**. Тогда поставьте 3.12 через PPA deadsnakes:

```bash
sudo apt install -y software-properties-common
sudo add-apt-repository -y ppa:deadsnakes/ppa
sudo apt update
sudo apt install -y python3.12 python3.12-venv
```

Дальше в командах ниже используйте `python3.12` вместо `python3`, если системный `python3` старше 3.11.

---

## Часть G. Клонирование репозитория с GitHub на сервер

Рабочая папка в примерах: `~/apps`. Перейдите в неё:

```bash
cd ~/apps
```

### G1. Публичный репозиторий (HTTPS)

```bash
git clone https://github.com/ВАШ_ЛОГИН/WBParser.git WBParser
cd WBParser
```

### G2. Приватный репозиторий (HTTPS + токен)

На сервере при `git clone` Git снова спросит учётные данные. **Username** — ваш логин GitHub, **Password** — **Personal Access Token** (как в части A3), не обычный пароль от сайта.

Чтобы не вводить token каждый раз при `git pull`, можно один раз включить кэш учётных данных (осторожно на общих серверах):

```bash
git config --global credential.helper store
```

Безопаснее на выделенном CI/сервере настроить **SSH** (часть G3).

### G3. Приватный репозиторий (SSH — удобно для сервера)

На **сервере**:

```bash
ssh-keygen -t ed25519 -C "wbparser-server" -f ~/.ssh/id_ed25519 -N ""
cat ~/.ssh/id_ed25519.pub
```

Скопируйте строку, начинающуюся с `ssh-ed25519`. На GitHub: **Settings → SSH and GPG keys → New SSH key** — вставьте ключ.

Проверка:

```bash
ssh -T git@github.com
```

Клонируйте по SSH:

```bash
cd ~/apps
git clone git@github.com:ВАШ_ЛОГИН/WBParser.git WBParser
cd WBParser
```

---

## Часть H. Виртуальное окружение и `pip`

Из каталога проекта:

```bash
cd ~/apps/WBParser
python3 -m venv .venv
# или: python3.12 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
```

Установка может занять **10–30+ минут** и пиково съесть много RAM. Если `pip` убит по OOM — добавьте swap:

```bash
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

(Для постоянного swap добавьте строку в `/etc/fstab` по документации вашей ОС.)

Проверка, что приложение «видит» конфиг (пока без полного запуска):

```bash
source .venv/bin/activate
python -c "from core.config import config; print('OK:', bool(config.DATABASE_URL))"
```

Без `.env` эта команда упадёт — это нормально до следующего шага.

---

## Часть I. Файл `.env` на сервере

### I1. Создание из шаблона

```bash
cd ~/apps/WBParser
cp .env.example .env
nano .env
```

(Вместо `nano` можно `vim`, либо править файл по SFTP / панели хостинга.)

### I2. Обязательные переменные

| Переменная | Что указать |
|------------|-------------|
| `TELEGRAM_BOT_TOKEN` | Токен от [@BotFather](https://t.me/BotFather) |
| `DATABASE_URL` | Строка из части D3, формат `postgresql+asyncpg://...` |
| `REDIS_URL` | Как минимум `redis://127.0.0.1:6379/0` |

### I3. Рекомендуемые для продакшена

| Переменная | Зачем |
|------------|--------|
| `PROXY_LIST` | Список прокси через **запятую** (`socks5://...`, `http://...`). Без прокси запросы к WB чаще упираются в лимиты. |
| `PARSER_TEST_MODE=false` | Прод: полноценный режим парсера (`true` только для отладки). |

### I4. Формат `.env` (важно)

- Одна переменная = одна строка `ИМЯ=значение`.
- **Без** префикса `export` (для systemd см. ниже).
- Пробелы вокруг `=` лучше не ставить.
- Строки не оборачивайте в кавычки, если в значении нет специальных случаев; внутри значения не ставьте неэкранированный перевод строки.

Сохраните файл. Права:

```bash
chmod 600 .env
```

---

## Часть J. Миграции базы (Alembic)

Миграции берут `DATABASE_URL` из того же модуля `core.config`, что подхватывает `.env` из каталога проекта.

```bash
cd ~/apps/WBParser
source .venv/bin/activate
alembic upgrade head
```

Ожидаемо: без traceback, в конце — что ревизии применены. Если ошибка подключения — проверьте Postgres, пароль и `DATABASE_URL`.

При старте приложения `init_db()` также вызывает `create_all` для моделей; для продакшена опирайтесь на **Alembic** как на источник схемы после первого деплоя.

---

## Часть K. Первый ручной запуск и проверки

В отдельной SSH-сессии:

```bash
cd ~/apps/WBParser
source .venv/bin/activate
python main.py
```

**Признаки успеха в логах:** инициализация БД, подключение к Redis, старт бота/парсера/нотификатора, нет немедленного traceback при импортах.

**Остановка:** `Ctrl+C`.

### Проверка observability

С другой машины (или с сервера):

```bash
curl -sS http://127.0.0.1:9090/health/live
curl -sS http://127.0.0.1:9090/health/ready
# Метрики Prometheus: http://127.0.0.1:9090/metrics
```

Если порт недоступен снаружи — проверьте firewall (часть M). Настройки порта и хоста: переменные **`OBS_HOST`**, **`OBS_PORT`**, **`OBSERVABILITY_ENABLED`** в `core/config.py` / `.env`.

### Проверка бота в Telegram

Откройте диалог с ботом в Telegram и отправьте команду из вашего меню (например `/start`). Если бот не отвечает — смотрите логи процесса и раздел P (типовые проблемы).

---

## Часть L. Автозапуск через systemd

Когда ручной запуск стабилен, оформите сервис. Файл создаётся **от root**:

```bash
sudo nano /etc/systemd/system/wbparser.service
```

### Вариант L1 (рекомендуется): без `EnvironmentFile` — только `.env` на диске

Приложение само загружает `.env` через `python-dotenv`, если рабочая директория — корень проекта.

```ini
[Unit]
Description=WBParser (бот + парсер + нотификатор)
After=network-online.target postgresql.service redis-server.service
Wants=network-online.target

[Service]
Type=simple
User=wbparser
Group=wbparser
WorkingDirectory=/home/wbparser/apps/WBParser
ExecStart=/home/wbparser/apps/WBParser/.venv/bin/python main.py
Restart=always
RestartSec=5

# Лимиты (по желанию)
# MemoryMax=3G

[Install]
WantedBy=multi-user.target
```

Подставьте **своего** пользователя и пути, если они отличаются.

### Вариант L2: дублирование переменных через `EnvironmentFile`

Используйте только если осознанно хотите передавать переменные из файла в формате systemd. Тогда **не кладите** в этот файл комментарии с `#` в конце строки со значением и следите за кавычками. Часто проще вариант L1.

Активация:

```bash
sudo systemctl daemon-reload
sudo systemctl enable wbparser
sudo systemctl start wbparser
sudo systemctl status wbparser
```

Логи в реальном времени:

```bash
journalctl -u wbparser -f
```

Последние 200 строк при сбое:

```bash
journalctl -u wbparser -n 200 --no-pager
```

Перезапуск после правок `.env` или кода:

```bash
sudo systemctl restart wbparser
```

---

## Часть M. Firewall (ufw, по желанию)

SSH **не закрывайте**. Минимум:

```bash
sudo apt install -y ufw
sudo ufw allow OpenSSH
sudo ufw enable
```

Порт **9090** открывайте только если нужен доступ к метрикам **свне** и только для доверенных IP:

```bash
sudo ufw allow from ВАШ_СТАТИЧЕСКИЙ_IP to any port 9090 proto tcp
```

Порты **5432** (Postgres) и **6379** (Redis) наружу обычно **не** открывают.

---

## Часть N. Обновление после пуша в GitHub

На сервере:

```bash
cd ~/apps/WBParser
git pull origin main
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
sudo systemctl restart wbparser
```

Ветку `main` замените на свою, если используете другую.

---

## Часть O. Резервные копии (кратко)

- Регулярно делайте **`pg_dump`** базы `wb_parser_bot` (скрипт по cron или сервис бэкапов провайдера).
- Храните копию **`.env`** вне сервера (менеджер паролей).

---

## Часть P. Типовые проблемы

| Симптом | Что проверить |
|---------|----------------|
| `could not connect to server` (Postgres) | Запущен ли `postgresql`, верный ли хост/порт/пароль в `DATABASE_URL` |
| Ошибка Redis / timeout | `redis-cli ping`, `systemctl status redis-server` |
| `TELEGRAM_BOT_TOKEN is required` | Есть ли `TELEGRAM_BOT_TOKEN` в `.env`, не пустой ли |
| 403/429 от WB, мало данных | `PROXY_LIST`, смена прокси, паузы в конфиге |
| OOM при `pip install` | RAM, swap, повтор установки |
| Бот молчит | Логи `journalctl`, токен бота, сеть до `api.telegram.org` |
| Порт 9090 недоступен | `OBS_HOST`/`OBS_PORT`, ufw, не слушает ли только localhost |

---

## Часть Q. Краткий чеклист

- [ ] Репозиторий на GitHub, **`.env` не в git**  
- [ ] Сервер: Ubuntu обновлён, установлены `git`, build-зависимости, при необходимости Python 3.11+  
- [ ] PostgreSQL: пользователь + БД, строка `DATABASE_URL`  
- [ ] Redis: `PONG` от `redis-cli ping`  
- [ ] `git clone` → `python -m venv .venv` → `pip install -r requirements.txt`  
- [ ] Заполнен `.env`, `chmod 600 .env`  
- [ ] `alembic upgrade head`  
- [ ] Успешный `python main.py`, затем `systemctl`  
- [ ] Firewall: не открывать лишнее, SSH сохранён  

Если после этого что-то падает — сохраните вывод `journalctl -u wbparser -n 150` и **замаскируйте** токены и пароли перед тем, как куда-либо отправлять лог.
