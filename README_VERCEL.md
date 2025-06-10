# FreelanceTM Bot - Vercel Deployment Guide

## ✅ Готовность к развертыванию

Код полностью настроен для Vercel с поддержкой webhook архитектуры.

## 🚀 Как развернуть

### 1. Загрузить в Vercel
- Подключите GitHub репозиторий к Vercel
- Выберите фреймворк: **Other**
- Build команда: оставьте пустой
- Output директория: оставьте пустой

### 2. Настроить переменные окружения в Vercel
```
BOT_TOKEN=your_telegram_bot_token_here
REQUIRED_CHANNEL=@FreelanceTM_channel
SESSION_SECRET=your_random_secret_key
```

### 3. Настроить webhook после развертывания
```bash
# Замените YOUR_DOMAIN на ваш домен Vercel
curl -X POST "https://api.telegram.org/bot{YOUR_BOT_TOKEN}/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://YOUR_DOMAIN.vercel.app/{YOUR_BOT_TOKEN}"}'
```

## 📋 Проверка работы

После развертывания проверьте:
- `GET /` - статус сервера
- `GET /bot_info` - информация о боте
- `POST /{BOT_TOKEN}` - webhook endpoint

## 🔧 Особенности архитектуры

- **Serverless совместимость**: Использует in-memory хранение данных
- **Webhook архитектура**: Заменена polling на webhook
- **Безопасность**: Token в URL для webhook
- **Обработка ошибок**: Graceful degradation без токена

## 📁 Структура файлов для Vercel

```
├── main.py          # Главный файл для Vercel
├── vercel.json      # Конфигурация Vercel
├── pyproject.toml   # Python зависимости
├── database.py      # База данных с serverless поддержкой
├── handlers.py      # Обработчики команд бота
├── keyboards.py     # Клавиатуры Telegram
├── texts.py         # Текста на разных языках
└── utils.py         # Утилиты
```

## ⚠️ Важные моменты

1. **База данных**: В serverless окружении данные хранятся в памяти и сбрасываются при перезапуске
2. **Токен бота**: Обязательно установите BOT_TOKEN в переменных окружения
3. **Webhook URL**: Должен включать токен бота для безопасности
4. **HTTPS**: Telegram требует HTTPS для webhook (Vercel предоставляет автоматически)

## 🔧 Troubleshooting

- Если бот не отвечает: проверьте BOT_TOKEN в настройках Vercel
- Если webhook не работает: проверьте правильность URL в setWebhook
- Для логов: используйте Vercel Functions logs