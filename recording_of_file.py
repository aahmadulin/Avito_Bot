import requests
from time import sleep
import random

# Заголовки для запроса
HEADERS_YA = {
    'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 YaBrowser/24.10.0.0 Safari/537.36',
}

# URL для запроса
URL = f'https://www.avito.ru/sankt-peterburg?q=квартира'
  
# Функция для выполнения запроса и сохранения HTML-ответа в файл
def save_response():
    # Добавляем задержку перед запросом
    sleep(random.uniform(2, 5))

    try:
        response = requests.get(URL, headers=HEADERS_YA)
        # Проверяем, что запрос прошел успешно
        if response.status_code == 200:
            with open('avito_page.html', 'w', encoding='utf-8') as file:
                file.write(response.text)
            print("HTML-ответ успешно сохранен в файл avito_page.html.")
        else:
            print(f"Ошибка при запросе: статус {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"Произошла ошибка при запросе: {e}")

# Запускаем функцию
if __name__ == "__main__":
    save_response()
