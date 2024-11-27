import requests
import time
import logging
import psycopg2
from datetime import datetime

# Настройки подключения к базе данных PostgreSQL
DB_HOST = 'podojofe.beget.app'  # Адрес сервера базы данных
DB_NAME = 'default_db'  # Имя базы данных
DB_USER = 'cloud_user'  # Имя пользователя
DB_PASSWORD = 'nMhczImev9*w'  # Пароль

# Настройка логгера для технического лога (только для технических сообщений)
technical_logger = logging.getLogger('technical_logger')
technical_logger.setLevel(logging.DEBUG)
technical_handler = logging.FileHandler('./logs_/depth_ratio_calc.log')
technical_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
technical_logger.addHandler(technical_handler)

def connect_to_db():
    """
    Подключение к базе данных PostgreSQL
    """
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        return conn
    except Exception as e:
        technical_logger.error(f"Не удалось подключиться к базе данных: {e}")
        return None

def fetch_order_book(product_id='BTC-USD', level=2):
    """
    Получает книгу ордеров (bids и asks) из Coinbase через REST API.
    """
    url = f"https://api.exchange.coinbase.com/products/{product_id}/book"
    params = {'level': level}
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()  # Проверка на успешность запроса
        data = response.json()
        
        bids = data.get('bids', [])
        asks = data.get('asks', [])
        
        technical_logger.debug(f"Получены данные: {len(bids)} заявок на покупку, {len(asks)} заявок на продажу.")
        
        return bids, asks
    except requests.exceptions.RequestException as e:
        technical_logger.error(f"Ошибка при запросе к API: {e}")
        return [], []

def calculate_depth_ratio(bids, asks, current_price, depths):
    """
    Рассчитывает Depth Ratio для заданных процентных глубин.
    """
    depth_ratios = {}
    for depth in depths:
        lower_bound = current_price * (1 - depth / 100)
        upper_bound = current_price * (1 + depth / 100)

        filtered_bids = [float(bid[1]) for bid in bids if float(bid[0]) >= lower_bound]
        filtered_asks = [float(ask[1]) for ask in asks if float(ask[0]) <= upper_bound]

        bid_volume = sum(filtered_bids)
        ask_volume = sum(filtered_asks)

        if (bid_volume + ask_volume) > 0:
            depth_ratio = (bid_volume / (bid_volume + ask_volume))
            depth_ratio = round(depth_ratio,4)
        else:
            depth_ratio = float('nan')

        depth_ratios[depth] = round(depth_ratio,4)

    return depth_ratios

def save_depth_ratios_to_db(depth_ratios, timestamp):
    """
    Записывает Depth Ratios в таблицу PostgreSQL.
    """
    conn = connect_to_db()
    if conn:
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO btc_depth_ratios (timestamp, depth_3, depth_5, depth_8, depth_15, depth_30)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (timestamp, 
                  depth_ratios.get(3, None), 
                  depth_ratios.get(5, None), 
                  depth_ratios.get(8, None), 
                  depth_ratios.get(15, None), 
                  depth_ratios.get(30, None)))
            conn.commit()
        except Exception as e:
            technical_logger.error(f"Ошибка при записи в базу данных: {e}")
        finally:
            cursor.close()
            conn.close()

def current_timestamp():
    """
    Возвращает текущую метку времени в формате YYYY-MM-DD HH:MM:SS
    """
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def main():
    product = 'BTC-USD'  # Торговая пара
    depths = [3, 5, 8, 15, 30]  # Проценты глубины
    sleep_interval = 5  # Интервал между запросами в секундах

    while True:
        bids, asks = fetch_order_book(product_id=product, level=2)

        if not bids or not asks:
            warning_message = f"[{current_timestamp()}] Не удалось получить данные книги ордеров.\n"
            technical_logger.warning(warning_message)
        else:
            sorted_bids = sorted(bids, key=lambda x: float(x[0]), reverse=True)
            sorted_asks = sorted(asks, key=lambda x: float(x[0]))

            try:
                best_bid = float(sorted_bids[0][0])
                best_ask = float(sorted_asks[0][0])
                current_price = (best_bid + best_ask) / 2

                depth_ratios = calculate_depth_ratio(sorted_bids, sorted_asks, current_price, depths)

                timestamp = current_timestamp()
                save_depth_ratios_to_db(depth_ratios, timestamp)

            except (IndexError, ValueError) as e:
                error_message = f"[{current_timestamp()}] Ошибка при обработке данных книги ордеров: {e}\n"
                technical_logger.error(error_message)

        time.sleep(sleep_interval)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        stop_message = f"[{current_timestamp()}] Программа остановлена пользователем.\n"
        technical_logger.info(stop_message)
        print("Программа остановлена пользователем.")
