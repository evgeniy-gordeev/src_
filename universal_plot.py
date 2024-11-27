import pandas as pd
import numpy as np
from flask import Flask, render_template_string, jsonify, render_template
from datetime import datetime
import plotly.graph_objs as go
from plotly.subplots import make_subplots
from sqlalchemy import create_engine
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Конфигурация базы данных PostgreSQL
DB_CONNECTION = {
    'dbname': 'default_db',
    'user': 'cloud_user',
    'password': 'nMhczImev9*w',
    'host': 'podojofe.beget.app',
    'port': '5432'
}

# Создание строки подключения SQLAlchemy
DATABASE_URL = f"postgresql://{DB_CONNECTION['user']}:{DB_CONNECTION['password']}@{DB_CONNECTION['host']}:{DB_CONNECTION['port']}/{DB_CONNECTION['dbname']}"
engine = create_engine(DATABASE_URL)

# Конфигурация Depth Ratios
DEPTH_PERCENTAGES = [3, 5, 8, 15, 30]
user_y_value = None
user_depth_ratio_value = None  # Для хранения выбранного Depth Ratio

# Flask-приложение
app = Flask(__name__)


def fetch_candles_from_db():
    """
    Извлекает данные о свечах из таблицы btc_price в PostgreSQL
    """
    query = """
    SELECT timestamp, open, high, low, close
    FROM btc_price
    ORDER BY timestamp;
    """
    try:
        candles_df = pd.read_sql(query, engine)
        if candles_df.empty:
            logger.warning("Данные о свечах отсутствуют.")
        return candles_df
    except Exception as e:
        logger.error(f"Ошибка при извлечении данных о свечах: {e}")
        return pd.DataFrame()

def fetch_depth_ratios_from_db(depth_percentages):
    """
    Извлекает данные о Depth Ratio из таблицы btc_depth_ratios в PostgreSQL
    """
    depth_columns = [f"depth_{depth}" for depth in depth_percentages]
    columns_str = ", ".join(depth_columns)

    query = f"""
    SELECT timestamp, {columns_str}
    FROM btc_depth_ratios
    ORDER BY timestamp;
    """
    try:
        depth_df = pd.read_sql(query, engine)
        if depth_df.empty:
            logger.warning("Данные о Depth Ratios отсутствуют.")
        return depth_df
    except Exception as e:
        logger.error(f"Ошибка при извлечении данных о Depth Ratios: {e}")
        return pd.DataFrame()

@app.route("/")
def index():
    try:
        # Получаем данные о свечах из PostgreSQL
        candles_df = fetch_candles_from_db()
        if candles_df.empty:
            return render_template_string("<h2>Нет доступных данных свечей.</h2>")

        # Получаем данные о Depth Ratio из PostgreSQL
        depth_df = fetch_depth_ratios_from_db(DEPTH_PERCENTAGES)
        if depth_df.empty:
            return render_template_string("<h2>Нет доступных данных Depth Ratio.</h2>")

        # Преобразуем столбец timestamp в datetime
        candles_df['timestamp'] = pd.to_datetime(candles_df['timestamp'])
        depth_df['timestamp'] = pd.to_datetime(depth_df['timestamp'])

        # Проверяем наличие необходимых столбцов
        required_columns = ['open', 'high', 'low', 'close']
        if not all(column in candles_df.columns for column in required_columns):
            logger.error("Необходимые столбцы отсутствуют в данных свечей.")
            return render_template_string("<h2>Данные свечей некорректны.</h2>")

        # Пример фильтрации по времени (если требуется)
        start_time = datetime.strptime("2024-11-20 19:16:00", "%Y-%m-%d %H:%M:%S")
        candles_df = candles_df[candles_df['timestamp'] >= start_time]
        depth_df = depth_df[depth_df['timestamp'] >= start_time]

        # Проверяем, что после фильтрации данные не пустые
        if candles_df.empty or depth_df.empty:
            logger.warning("Нет данных для отображения после фильтрации по времени.")
            return render_template_string("<h2>Нет данных для отображения.</h2>")

        # Создаем график с двумя подграфиками (OHLC и Depth Ratios)
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.1)

        # График свечей (OHLC)
        fig.add_trace(go.Candlestick(
            x=candles_df['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S').tolist(),
            open=candles_df['open'].tolist(),
            high=candles_df['high'].tolist(),
            low=candles_df['low'].tolist(),
            close=candles_df['close'].tolist(),
            increasing_line_color='green',
            decreasing_line_color='red',
            name="Свечи"
        ), row=1, col=1)

        # Графики Depth Ratio
        for depth in DEPTH_PERCENTAGES:
            column_name = f'depth_{depth}'
            if column_name in depth_df.columns:
                fig.add_trace(go.Scattergl(
                    x=depth_df['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S').tolist(),
                    y=depth_df[column_name].tolist(),
                    mode='lines',
                    name=f"{depth}% Depth Ratio"
                ), row=2, col=1)
            else:
                logger.warning(f"Столбец {column_name} отсутствует в данных Depth Ratio.")

        # Настройки графика
        fig.update_layout(
            title_text="BTC/USDT и Depth Ratio",
            height=800,
            legend=dict(x=0.02, y=0.98, bgcolor="rgba(255, 255, 255, 0.5)", bordercolor="Black", borderwidth=1)
        )

        fig.update_xaxes(rangeslider=dict(visible=False), row=1, col=1)
        fig.update_xaxes(title="Время", row=2, col=1)
        fig.update_yaxes(title="Цена (USDT)", row=1, col=1)
        fig.update_yaxes(title="Depth Ratio", row=2, col=1)

        # Преобразуем график в JSON-совместимый формат
        graph_data = fig.to_plotly_json()

        # Отображаем HTML с графиком
        return render_template('index.html', graph_data=graph_data)
    except Exception as e:
        logger.error(f"Ошибка в маршруте '/': {e}")
        return render_template_string("<h2>Произошла ошибка при обработке запроса.</h2>")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5004, debug=False)
