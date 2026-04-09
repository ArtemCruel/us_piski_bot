# US Piski Bot 🤖

Личный Telegram бот для трёх юзеров: Артем (два аккаунта) и Майя.

## Функциональность ✨

- 📝 **Факты про Майю** - Генерирует интересные и милые факты через ИИ
- 📋 **Вишлист** - Добавь, посмотри и удали желания
- 💬 **Цитаты** - Собирай и управляй любимыми цитатами
- 🤖 **ИИ помощник** - Общайся с Google Gemini 2.0
- 🔒 **Безопасность** - Доступ только для белого списка пользователей

## Локальный запуск 🏠

```bash
# 1. Установи зависимости
pip install -r requirements.txt

# 2. Экспортируй переменные окружения
export TELEGRAM_TOKEN="твой_токен_от_BotFather"
export OPENROUTER_KEY="твой_ключ_от_OpenRouter"

# 3. Запусти бота
python3 main.py
```

## Развёртывание на Render 🚀

### Шаг 1: Подготовь GitHub

```bash
cd /Users/byteup/Desktop/AI_one/us_piski_bot
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/ТВ̃ОЙ_USERNAME/us_piski_bot.git
git push -u origin main
```

### Шаг 2: Создай Render сервис

1. Перейди на [render.com](https://render.com)
2. Нажми **+ New** → **Web Service**
3. Подключи свой GitHub аккаунт
4. Выбери репозиторий `us_piski_bot`
5. Заполни настройки:
   - **Name**: `us_piski_bot`
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python3 main.py`
   - **Instance Type**: `Free`

### Шаг 3: Установи переменные окружения

В дашборде Render → **Environment** → добавь переменные:
- `TELEGRAM_TOKEN` = твой токен
- `OPENROUTER_KEY` = твой ключ

### Шаг 4: Развёртывание

Нажми **Create Web Service** и жди ~5 минут развёртывания.

Профит! 🎉 Бот будет работать 24/7!

## Белый список пользователей 👥

```python
ALLOWED_USERS = [
    7118929376,     # Артем личный
    1428288113,     # Артем основной (@A_rtemK)
    8481047835,     # Майя (@poqqg)
]
```

## API и токены 🔑

- **Telegram Bot API**: от @BotFather в Telegram
- **OpenRouter API**: от [openrouter.ai](https://openrouter.ai)
- **ИИ модель**: Google Gemini 2.0 Flash

---

Автор: us_piski_bot ❤️
