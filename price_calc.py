import requests
import time
import logging
import psycopg2
from datetime import datetime

# Настройка логгера для технических сообщений
technical_logger = logging.getLogger('technical_logger')
technical_logger.setLevel(logging.DEBUG)
technical_handler = logging.FileHandler('./logs_/price_calc.log')
technical_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
technical_logger.addHandler(technical_handler)

# Настройка подключения к базе данных
DB_CONNECTION = {
    'dbname': 'default_db',
    'user': 'cloud_user',
    'password': 'nMhczImev9*w',
    'host': 'podojofe.beget.app',  # или другой адрес сервера
    'port': '5432'
}

def fetch_current_price(product_id='BTC-USD'):
    """
    Получает текущую рыночную цену из Coinbase через REST API.

    :param product_id: Торговая пара, например 'BTC-USD'
    :return: Текущая рыночная цена (float) или None в случае ошибки
    """
    url = f"https://api.exchange.coinbase.com/products/{product_id}/ticker"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()  # Проверка на успешность запроса
        data = response.json()
        technical_logger.debug(f"Текущая цена для {product_id}: {data['price']}")
        return float(data['price'])
    except (requests.exceptions.RequestException, KeyError, ValueError) as e:
        technical_logger.error(f"Ошибка при запросе цены: {e}")
        return None

def calculate_minute_candle(data_points):
    """
    Рассчитывает минутные свечи OHLC.

    :param data_points: Список цен за минуту
    :return: Кортеж (open, high, low, close)
    """
    if not data_points:
        return None, None, None, None
    open_price = data_points[0]
    close_price = data_points[-1]
    high_price = max(data_points)
    low_price = min(data_points)
    return open_price, high_price, low_price, close_price

def write_candle_to_db(timestamp, ohlc):
    """
    Записывает свечу в базу данных.

    :param timestamp: Метка времени
    :param ohlc: Кортеж (open, high, low, close)
    """
    try:
        # Подключаемся к базе данных
        conn = psycopg2.connect(**DB_CONNECTION)
        cursor = conn.cursor()

        # SQL-запрос для вставки данных
        query = """
            INSERT INTO btc_price (timestamp, open, high, low, close)
            VALUES (%s, %s, %s, %s, %s);
        """
        cursor.execute(query, (timestamp, ohlc[0], ohlc[1], ohlc[2], ohlc[3]))

        # Сохраняем изменения и закрываем соединение
        conn.commit()
        cursor.close()
        conn.close()

        technical_logger.debug(f"Свеча добавлена в базу данных для {timestamp}")
    except Exception as e:
        technical_logger.error(f"Ошибка при записи в базу данных: {e}")

def current_timestamp():
    """
    Возвращает текущую метку времени в формате YYYY-MM-DD HH:MM:SS
    """
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def main():
    product = 'BTC-USD'  # Торговая пара
    sleep_interval = 5  # Интервал между запросами в секундах
    minute_data = []  # Для хранения цен за минуту
    last_minute = datetime.now().minute

    while True:
        # Получаем текущую рыночную цену
        current_price = fetch_current_price(product_id=product)
        if current_price:
            minute_data.append(current_price)

        # Проверяем, прошла ли минута
        current_minute = datetime.now().minute
        if current_minute != last_minute:
            # Рассчитываем и записываем свечу
            ohlc = calculate_minute_candle(minute_data)
            if all(ohlc):  # Убедимся, что данные есть
                write_candle_to_db(current_timestamp(), ohlc)
            minute_data = []  # Сбрасываем данные
            last_minute = current_minute

        time.sleep(sleep_interval)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        technical_logger.info("Программа остановлена пользователем.")
        print("Программа остановлена пользователем.")
