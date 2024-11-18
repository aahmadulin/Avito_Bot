import asyncio
import requests
from selectolax.parser import HTMLParser
import urllib.parse
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
import logging
import os
from dotenv import load_dotenv

# Загрузка переменных окружения из файла .env
load_dotenv()

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Получение значений из переменных окружения
TOKEN = os.getenv('TOKEN')
CHAT_ID = os.getenv('CHAT_ID')
USER_AGENT = os.getenv('USER_AGENT')  # Загружаем User-Agent из .env

# Определяем состояния разговора
QUERY, MAX_PRICE = range(2)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        logger.info("Функция start вызвана")
        await update.message.reply_text("Привет! Что вы хотите найти на Avito?")
        return QUERY
    except Exception as e:
        logger.error(f"Ошибка в функции start: {e}")
        return ConversationHandler.END

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Бот остановлен.")
    logger.info("Бот остановлен пользователем.")
    await context.application.stop()  # Завершение работы приложения

async def get_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['query'] = update.message.text
    await update.message.reply_text("Теперь введите максимальную цену (только число):")
    return MAX_PRICE

async def get_max_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        max_price = int(update.message.text)
        context.user_data['max_price'] = max_price
        await update.message.reply_text(f"Ищу '{context.user_data['query']}' на Avito с максимальной ценой {max_price} ₽...")
        await process_avito_search(context.user_data['query'], update, context)
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("Пожалуйста, введите корректное число для максимальной цены.")
        return MAX_PRICE

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Поиск отменен.")
    return ConversationHandler.END

async def process_avito_search(query: str, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        logger.info(f"Начало поиска на Avito для запроса: {query}")
        encoded_query = urllib.parse.quote(query)
        url = f'https://www.avito.ru/sankt-peterburg?q={encoded_query}'
        
        headers = {
            'User-Agent': USER_AGENT  # Используем User-Agent из .env
        }
        
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            tree = HTMLParser(response.text)
            block_of_code = tree.css('div[data-marker="item"]')
            logger.info(f"Найдено {len(block_of_code)} объявлений")
            await get_all_data(block_of_code, update, context)
        else:
            logger.error(f"Ошибка при получении страницы: {response.status_code}")
            await update.message.reply_text(f"Ошибка при получении страницы: {response.status_code}")
    except Exception as e:
        logger.error(f"Ошибка в функции process_avito_search: {e}")

async def send_message_with_retry(bot, chat_id, text):
    while True:
        try:
            await bot.send_message(chat_id=chat_id, text=text)
            break  # Если сообщение успешно отправлено, выходим из цикла
        except requests.exceptions.RequestException as e:
            logger.warning(f"Ошибка при отправке сообщения: {e}")
            await asyncio.sleep(1)  # Ждем перед повторной попыткой

async def get_all_data(block_of_code, update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        max_price = context.user_data.get('max_price', float('inf'))
        results_count = 0
        for block in block_of_code:
            if results_count >= 20:  # Ограничиваем до 20 результатов
                break
            
            link = block.css_first('a')
            description_meta = block.css_first('meta[itemprop="description"]')
            price_meta = block.css_first('meta[itemprop="price"]')
            images = block.css('img')

            if price_meta:
                price = int(price_meta.attributes.get('content', '0'))
                if price > max_price:
                    continue  # Пропускаем объявления с ценой выше максимальной

            result = {
                "index": results_count + 1,
                "link": f'https://www.avito.ru{link.attributes.get("href")}' if link else 'Ссылка не найдена',
                "description": description_meta.attributes.get('content').strip() if description_meta else 'Описание не найдено',
                "price": f"{price:,} ₽".replace(',', ' ') if price_meta else 'Цена не найдена',
                "image": images[0].attributes.get('src') if images else None
            }

            message = (f"{result['index']}) Ссылка: {result['link']}\n"
                       f"Описание: {result['description']}\n"
                       f"Цена: {result['price']}")
            
            logger.info(f"Отправка сообщения для объявления {result['index']}")
            await send_message_with_retry(context.bot, update.effective_chat.id, message)
            
            if result['image']:
                logger.info(f"Отправка изображения для объявления {result['index']}")
                await send_message_with_retry(context.bot, update.effective_chat.id, result['image'])
            
            results_count += 1

        if results_count == 0:
            await update.message.reply_text("Не найдено объявлений, соответствующих вашему запросу и ценовому диапазону.")
    except Exception as e:
        logger.error(f"Ошибка в функции get_all_data: {e}")

def main() -> None:
    logger.info("Бот запускается...")
    try:
        application = Application.builder().token(TOKEN).build()
        logger.info("Подключение к Telegram API успешно")
        
        conv_handler = ConversationHandler(
            entry_points=[CommandHandler("start", start)],
            states={
                QUERY: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_query)],
                MAX_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_max_price)],
            },
            fallbacks=[CommandHandler("cancel", cancel)],
        )
        
        # Добавляем обработчик для команды /stop
        application.add_handler(CommandHandler("stop", stop))
        
        application.add_handler(conv_handler)
        
        logger.info("Бот начинает работу")
        application.run_polling(allowed_updates=Update.ALL_TYPES)
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")

if __name__ == "__main__":
    main()
