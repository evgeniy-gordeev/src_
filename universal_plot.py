from sqlalchemy import create_engine
import pandas as pd
from datetime import datetime
from flask import Flask, render_template, request, jsonify
import plotly.graph_objs as go
from plotly.subplots import make_subplots

# Конфигурация базы данных PostgreSQL
DB_CONNECTION = {
    'dbname': 'default_db',
    'user': 'cloud_user',
    'password': 'nMhczImev9*w',
    'host': 'podojofe.beget.app',  # или другой адрес сервера
    'port': '5432'
}

# Создание строки подключения SQLAlchemy
DATABASE_URL = f"postgresql://{DB_CONNECTION['user']}:{DB_CONNECTION['password']}@{DB_CONNECTION['host']}:{DB_CONNECTION['port']}/{DB_CONNECTION['dbname']}"
engine = create_engine(DATABASE_URL)

# Конфигурация Depth Ratios
DEPTH_PERCENTAGES = [3, 5, 8, 15, 30]
user_y_value = None
user_depth_ratio_value = None  # Для хранения выбранного Depth Ratio

app = Flask(__name__)

@app.route("/")
def index():
    return render_template("index.html", DEPTH_PERCENTAGES=DEPTH_PERCENTAGES)

@app.route("/add-y-line", methods=["POST"])
def add_y_line():
    global user_y_value
    try:
        data = request.get_json()
        user_y_value = float(data['y-value'])
    except (ValueError, KeyError):
        return jsonify({"error": "Неверное Y значение. Пожалуйста, введите корректное число."}), 400
    return jsonify(_get_chart_data())

@app.route("/update-depth-ratio", methods=["POST"])
def update_depth_ratio():
    global user_depth_ratio_value
    try:
        data = request.get_json()
        depth_ratio_str = data['depth-ratio']
        # Валидируем, что введённый Depth Ratio присутствует в DEPTH_PERCENTAGES
        depth_ratio = int(depth_ratio_str)
        if depth_ratio not in DEPTH_PERCENTAGES:
            raise ValueError
        user_depth_ratio_value = depth_ratio
    except (KeyError, ValueError):
        return jsonify({"error": f"Неверный Depth Ratio. Пожалуйста, выберите одно из значений: {DEPTH_PERCENTAGES}."}), 400
    return jsonify({"message": "Depth Ratio успешно обновлён."})

@app.route("/reset", methods=["POST"])
def reset():
    global user_y_value, user_depth_ratio_value
    user_y_value = None
    user_depth_ratio_value = None
    return jsonify(_get_chart_data())

@app.route("/get-chart-data", methods=["GET"])
def get_chart_data():
    return jsonify(_get_chart_data())

def _get_chart_data():
    global user_y_value, user_depth_ratio_value, DEPTH_PERCENTAGES

    # Получаем данные о свечах из PostgreSQL
    candles_df = fetch_candles_from_db()
    if candles_df.empty:
        return {"error": "Нет доступных данных свечей."}

    # Получаем данные о Depth Ratio из PostgreSQL
    depth_df = fetch_depth_ratios_from_db(DEPTH_PERCENTAGES)
    if depth_df.empty:
        return {"error": "Нет доступных данных Depth Ratio."}

    # Преобразуем столбец timestamp в формат datetime
    candles_df['timestamp'] = pd.to_datetime(candles_df['timestamp'])
    depth_df['timestamp'] = pd.to_datetime(depth_df['timestamp'])

    # Пример фильтрации по времени (если требуется)
    start_time = datetime.strptime("2024-11-20 19:16:00", "%Y-%m-%d %H:%M:%S")
    depth_df = depth_df[depth_df['timestamp'] >= start_time]
    candles_df = candles_df[candles_df['timestamp'] >= start_time]

    # Создание графиков с использованием Plotly
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.1)

    # График свечей
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
    if user_depth_ratio_value is not None:
        column_name = f'depth_{user_depth_ratio_value}'
        if column_name in depth_df.columns:
            fig.add_trace(go.Scatter(
                x=depth_df['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S').tolist(),
                y=depth_df[column_name].tolist(),
                mode='lines',
                name=f"{user_depth_ratio_value}% Depth Ratio",
                line=dict(color='blue')
            ), row=2, col=1)
    else:
        # Отображаем все Depth Ratios
        for depth in DEPTH_PERCENTAGES:
            column_name = f'depth_{depth}'
            if column_name in depth_df.columns:
                fig.add_trace(go.Scatter(
                    x=depth_df['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S').tolist(),
                    y=depth_df[column_name].tolist(),
                    mode='lines',
                    name=f"{depth}% Depth Ratio"
                ), row=2, col=1)

    # Добавляем пользовательскую линию Y, если задано
    if user_y_value is not None:
        fig.add_trace(go.Scatter(
            x=depth_df['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S').tolist(),
            y=[user_y_value] * len(depth_df),
            mode='lines',
            line=dict(dash='dash', color='black'),
            name=f"Y={user_y_value}"
        ), row=2, col=1)

    fig.update_layout(
        title_text="BTC/USDT и Depth Ratio",
        height=800,
        legend=dict(x=0.02, y=0.98, bgcolor="rgba(255, 255, 255, 0.5)", bordercolor="Black", borderwidth=1)
    )

    fig.update_xaxes(rangeslider=dict(visible=False), row=1, col=1)
    fig.update_xaxes(title="Время", row=2, col=1)
    fig.update_yaxes(title="Цена (USDT)", row=1, col=1)
    fig.update_yaxes(title="Depth Ratio", row=2, col=1)

    return fig.to_plotly_json()

def fetch_candles_from_db():
    query = """
    SELECT timestamp, open, high, low, close
    FROM btc_price
    ORDER BY timestamp;
    """
    try:
        candles_df = pd.read_sql(query, engine)
        return candles_df
    except Exception as e:
        print(f"Ошибка при извлечении данных о свечах: {e}")
        return pd.DataFrame()

def fetch_depth_ratios_from_db(depth_percentages):
    depth_columns = [f"depth_{depth}" for depth in depth_percentages]
    columns_str = ", ".join(depth_columns)

    query = f"""
    SELECT timestamp, {columns_str}
    FROM btc_depth_ratios
    ORDER BY timestamp;
    """
    try:
        depth_df = pd.read_sql(query, engine)
        return depth_df
    except Exception as e:
        print(f"Ошибка при извлечении данных о Depth Ratios: {e}")
        return pd.DataFrame()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5004, debug=True)
