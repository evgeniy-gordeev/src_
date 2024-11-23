from flask import Flask, render_template_string, request, jsonify
import pandas as pd
from datetime import datetime
import plotly.graph_objs as go
from plotly.subplots import make_subplots
import os
import re

# Конфигурация файлов
LOG_FILE = "./logs/depth_ratio_log.txt"
CANDLES_FILE = "./logs/btc_price_log.txt"
DEPTH_PERCENTAGES = [3, 5, 8, 15, 30]
user_y_value = None
user_depth_ratio_value = None  # Для хранения выбранного Depth Ratio

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>BTC Charts</title>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
</head>
<body>
    <div id="chart"></div>
    <form id="y-line-form" style="margin-bottom: 10px;">
        <label for="y-value">Введите Y значение (Depth Ratio):</label>
        <input type="text" id="y-value" name="y-value" required>
        <button type="submit">Отправить</button>
        <button type="button" onclick="resetAll()">Сбросить</button>
    </form>
    <form id="depth-ratio-form" style="margin-bottom: 10px;">
        <label for="depth-ratio">Выберите Depth Ratio:</label>
        <select id="depth-ratio" name="depth-ratio" required>
            <option value="" disabled selected>Выберите Depth Ratio</option>
            {% for depth in DEPTH_PERCENTAGES %}
                <option value="{{ depth }}">{{ depth }}%</option>
            {% endfor %}
        </select>
        <button type="button" onclick="updateDepthRatio()">Отправить</button>
        <button type="button" onclick="resetAll()">Сбросить</button>
    </form>
    <script>
        document.getElementById("y-line-form").addEventListener("submit", function(event) {
            event.preventDefault();

            const yValue = document.getElementById("y-value").value;

            fetch('/add-y-line', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ "y-value": yValue })
            })
            .then(response => response.json())
            .then(data => {
                if (data.error) {
                    alert(data.error);
                } else {
                    Plotly.react('chart', data.data, data.layout);
                }
            })
            .catch(error => console.error('Ошибка:', error));
        });

        function updateDepthRatio() {
            const depthRatio = document.getElementById("depth-ratio").value;

            fetch('/update-depth-ratio', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ "depth-ratio": depthRatio })
            })
            .then(response => response.json())
            .then(data => {
                if (data.error) {
                    alert(data.error);
                } else {
                    alert(data.message);
                    // Обновляем график после изменения Depth Ratio
                    fetchChartData();
                }
            })
            .catch(error => console.error('Ошибка:', error));
        }

        function resetAll() {
            fetch('/reset', { method: 'POST' })
            .then(response => response.json())
            .then(data => {
                if (data.error) {
                    alert(data.error);
                } else {
                    Plotly.react('chart', data.data, data.layout);
                }
            })
            .catch(error => console.error('Ошибка:', error));
        }

        function fetchChartData() {
            fetch('/get-chart-data')
                .then(response => response.json())
                .then(data => {
                    if (data.error) {
                        alert(data.error);
                    } else {
                        Plotly.react('chart', data.data, data.layout);
                    }
                })
                .catch(error => console.error('Ошибка при получении данных графика:', error));
        }

        // Инициализируем график при загрузке страницы
        window.onload = function() {
            fetchChartData();
        };
    </script>
</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE, DEPTH_PERCENTAGES=DEPTH_PERCENTAGES)

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

    candles_df = parse_candles_file(CANDLES_FILE)
    if candles_df.empty:
        return {"error": "Нет доступных данных свечей."}

    depth_df = parse_log_file(LOG_FILE, DEPTH_PERCENTAGES)
    if depth_df.empty:
        return {"error": "Нет доступных данных Depth Ratio."}

    start_time = datetime.strptime("2024-11-20 19:16:00", "%Y-%m-%d %H:%M:%S")
    depth_df = depth_df[depth_df['timestamp'] >= start_time]
    candles_df = candles_df[candles_df['timestamp'] >= start_time]

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
        # Отображаем только выбранный Depth Ratio
        column_name = f'{user_depth_ratio_value}%'
        if column_name in depth_df.columns:
            fig.add_trace(go.Scatter(
                x=depth_df['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S').tolist(),
                y=depth_df[column_name].tolist(),
                mode='lines',
                name=f"{column_name} Depth Ratio",
                line=dict(color='blue')
            ), row=2, col=1)
    else:
        # Отображаем все Depth Ratios
        for depth in DEPTH_PERCENTAGES:
            column_name = f'{depth}%'
            if column_name in depth_df.columns:
                fig.add_trace(go.Scatter(
                    x=depth_df['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S').tolist(),
                    y=depth_df[column_name].tolist(),
                    mode='lines',
                    name=f"{column_name} Depth Ratio"
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

# Вспомогательные функции для обработки файлов
def parse_candles_file(file_path):
    if not os.path.exists(file_path):
        return pd.DataFrame()

    data = {
        'timestamp': [],
        'open': [],
        'high': [],
        'low': [],
        'close': []
    }

    pattern = re.compile(
        r"\[(?P<timestamp>[\d\-: ]+)\] Open: (?P<open>\d+\.?\d*), High: (?P<high>\d+\.?\d*), Low: (?P<low>\d+\.?\d*), Close: (?P<close>\d+\.?\d*)"
    )

    with open(file_path, "r") as file:
        for line in file:
            match = pattern.match(line.strip())
            if match:
                data['timestamp'].append(datetime.strptime(match.group('timestamp'), "%Y-%m-%d %H:%M:%S"))
                data['open'].append(float(match.group('open')))
                data['high'].append(float(match.group('high')))
                data['low'].append(float(match.group('low')))
                data['close'].append(float(match.group('close')))

    return pd.DataFrame(data)

def parse_log_file(log_file, depth_percentages):
    if not os.path.exists(log_file):
        return pd.DataFrame()

    data = {'timestamp': []}
    for depth in depth_percentages:
        data[f'{depth}%'] = []

    with open(log_file, "r") as file:
        for line in file:
            parts = line.strip().split("] Depth Ratio для BTC-USD: ")
            if len(parts) != 2:
                continue

            try:
                timestamp = datetime.strptime(parts[0][1:], "%Y-%m-%d %H:%M:%S")
                data['timestamp'].append(timestamp)

                ratios = parts[1].split(", ")
                ratio_dict = {f"{d}%": None for d in depth_percentages}
                for ratio in ratios:
                    depth, value = ratio.split(": ")
                    depth = depth.strip()
                    if depth in ratio_dict:
                        ratio_dict[depth] = float(value)

                for depth in depth_percentages:
                    key = f"{depth}%"
                    value = ratio_dict.get(key)
                    if value is not None:
                        data[key].append(value)
                    else:
                        data[key].append(None)
            except Exception as e:
                # Можно добавить логирование ошибки
                continue

    # Преобразуем списки в pandas Series с правильными типами
    for key in data:
        if key != 'timestamp':
            data[key] = pd.to_numeric(data[key], errors='coerce')

    return pd.DataFrame(data)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5004, debug=True)
