import requests
import time
import logging
from datetime import datetime

# Глобальная переменная для имени лог-файла
FILENAME = './logs/depth_ratio_log.txt'

# Настройка логгера для технического лога (только для технических сообщений)
technical_logger = logging.getLogger('technical_logger')
technical_logger.setLevel(logging.DEBUG)
technical_handler = logging.FileHandler('./logs_/depth_ratio_calc.log')
technical_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
technical_logger.addHandler(technical_handler)

def fetch_order_book(product_id='BTC-USD', level=2):
    """
    Получает книгу ордеров (bids и asks) из Coinbase через REST API.

    :param product_id: Торговая пара, например 'BTC-USD'
    :param level: Уровень детализации книги ордеров (1, 2 или 3)
    :return: Кортеж из двух списков: (bids, asks)
    """
    url = f"https://api.exchange.coinbase.com/products/{product_id}/book"
    params = {'level': level}
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()  # Проверка на успешность запроса
        data = response.json()
        
        # Извлечение заявок на покупку (bids) и продажу (asks)
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

    :param bids: Список заявок на покупку
    :param asks: Список заявок на продажу
    :param current_price: Текущая рыночная цена
    :param depths: Список процентных глубин
    :return: Словарь с Depth Ratio для каждой глубины
    """
    depth_ratios = {}
    for depth in depths:
        # Рассчитываем границы
        lower_bound = current_price * (1 - depth / 100)
        upper_bound = current_price * (1 + depth / 100)

        # Фильтруем заявки в пределах глубины
        filtered_bids = [float(bid[1]) for bid in bids if float(bid[0]) >= lower_bound]
        filtered_asks = [float(ask[1]) for ask in asks if float(ask[0]) <= upper_bound]

        # Рассчитываем общий объем в пределах текущей глубины
        bid_volume = sum(filtered_bids)
        ask_volume = sum(filtered_asks)

        # Рассчитываем Depth Ratio
        if (bid_volume + ask_volume) > 0:
            depth_ratio = (bid_volume / (bid_volume + ask_volume))
        else:
            depth_ratio = float('nan')

        depth_ratios[depth] = depth_ratio

    return depth_ratios

def write_to_log(message):
    """
    Записывает сообщение в лог-файл (для data logger).

    :param message: Строка сообщения для записи
    """
    try:
        with open(FILENAME, 'a', encoding='utf-8') as f:
            f.write(message)
    except Exception as e:
        technical_logger.error(f"Не удалось записать в основной лог: {e}")

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
            # Сортируем заявки по цене
            sorted_bids = sorted(bids, key=lambda x: float(x[0]), reverse=True)
            sorted_asks = sorted(asks, key=lambda x: float(x[0]))

            try:
                # Определяем текущую рыночную цену (среднее между лучшими bid и ask)
                best_bid = float(sorted_bids[0][0])
                best_ask = float(sorted_asks[0][0])
                current_price = (best_bid + best_ask) / 2

                # Рассчитываем Depth Ratios
                depth_ratios = calculate_depth_ratio(sorted_bids, sorted_asks, current_price, depths)

                # Формируем строку вывода
                ratios_str = ', '.join([f"{depth}%: {depth_ratios[depth]:.4f}" for depth in depths])
                output = f"[{current_timestamp()}] Depth Ratio для {product}: {ratios_str}\n"
                write_to_log(output)
            except (IndexError, ValueError) as e:
                error_message = f"[{current_timestamp()}] Ошибка при обработке данных книги ордеров: {e}\n"
                technical_logger.error(error_message)

        # Ждем перед следующим запросом
        time.sleep(sleep_interval)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        stop_message = f"[{current_timestamp()}] Программа остановлена пользователем.\n"
        technical_logger.info(stop_message)
        print("Программа остановлена пользователем.")
