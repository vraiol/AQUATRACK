import threading
import json
import paho.mqtt.client as mqtt
import psycopg2
import boto3
from psycopg2 import pool
from flask import Flask, jsonify, render_template_string

app = Flask(__name__)

# ── Configurações ──────────────────────────────────────────────
S3_BUCKET = "aquatrack-bucket-726921688608-us-east-1-an"
BROKER_HOST = "10.0.1.231"  # IP privado da EC2 broker

DB_CONFIG = {
    "host": "localhost",
    "dbname": "aquatrack",
    "user": "admin",
    "password": "Aquatrack123!"
}

s3_client = boto3.client('s3', region_name='us-east-1')
db_pool = psycopg2.pool.SimpleConnectionPool(1, 10, **DB_CONFIG)

def get_db():
    return db_pool.getconn()

def release_db(conn):
    db_pool.putconn(conn)
# ── MQTT ────────────────────────────────────────────────────────
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("[OK] Conectado ao broker MQTT")
        client.subscribe("aquatrack/#")
    else:
        print(f"[ERRO] Falha na conexão: {rc}")

def on_message(client, userdata, msg):
    conn = None
    try:
        dados = json.loads(msg.payload)
        sensor = msg.topic.split("/")[-1]
        reservatorio_id = dados.get("reservatorio_id", 1)
        valor = dados.get("valor")

        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO leituras_agua (reservatorio_id, tipo_sensor, valor)
            VALUES (%s, %s, %s)
        """, (reservatorio_id, sensor, valor))
        conn.commit()
        cur.close()
        print(f"[DB] Salvo: {sensor} = {valor}")
    except Exception as e:
        print(f"[ERRO] {e}")
    finally:
        if conn:
            release_db(conn)

mqtt_client = mqtt.Client()
mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message
try:
    mqtt_client.connect(BROKER_HOST, 1883, 60)
    threading.Thread(target=mqtt_client.loop_forever, daemon=True).start()
except Exception as e:
    print(f"[AVISO] Broker indisponível: {e}")

# ── API REST ─────────────────────────────────────────────────────
@app.route("/api/leituras")
def get_leituras():
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT l.tipo_sensor, l.valor, l.timestamp, r.nome
            FROM leituras_agua l
            JOIN reservatorios r ON r.id = l.reservatorio_id
            ORDER BY l.timestamp DESC
            LIMIT 50
        """)
        rows = cur.fetchall()
        cur.close()
        return jsonify([{
            "sensor": r[0],
            "valor": float(r[1]),
            "timestamp": r[2].isoformat(),
            "reservatorio": r[3]
        } for r in rows])
    finally:
        release_db(conn)

@app.route("/api/alertas")
def get_alertas():
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT l.tipo_sensor, l.valor, l.timestamp, r.nome,
                   p.valor_minimo, p.valor_maximo
 FROM leituras_agua l
            JOIN reservatorios r ON r.id = l.reservatorio_id
            JOIN parametros_limite p ON p.tipo_sensor = l.tipo_sensor
            WHERE l.valor < p.valor_minimo OR l.valor > p.valor_maximo
            ORDER BY l.timestamp DESC
            LIMIT 20
        """)
        rows = cur.fetchall()
        cur.close()
        return jsonify([{
            "sensor": r[0],
            "valor": float(r[1]),
            "timestamp": r[2].isoformat(),
            "reservatorio": r[3],
            "minimo": float(r[4]),
            "maximo": float(r[5])
        } for r in rows])
    finally:
        release_db(conn)

@app.route("/api/gerar-relatorio", methods=["POST"])
def gerar_relatorio():
    conn = get_db()
    try:
        cur = conn.cursor()
        # Busca o histórico completo para gerar a série
        cur.execute("""
            SELECT l.id, r.nome, l.tipo_sensor, l.valor, l.timestamp
            FROM leituras_agua l
            JOIN reservatorios r ON r.id = l.reservatorio_id
            ORDER BY l.timestamp DESC
        """)
        rows = cur.fetchall()
        cur.close()

        import csv
        import os
from datetime import datetime

        # Cria o CSV
        nome_arquivo = f"seriehistorica{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        with open(nome_arquivo, mode='w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['ID', 'Reservatorio', 'Sensor', 'Valor', 'Data_Hora'])
            for r in rows:
                writer.writerow([r[0], r[1], r[2], float(r[3]), r[4]])

        # Envia para a pasta series-historicas no S3
        caminho_s3 = f"series-historicas/{nome_arquivo}"
        s3_client.upload_file(nome_arquivo, S3_BUCKET, caminho_s3)

        if os.path.exists(nome_arquivo):
            os.remove(nome_arquivo)

        return jsonify({
            "status": "sucesso",
            "mensagem": "Série Histórica gerada e enviada para o S3 com sucesso!",
            "arquivo": caminho_s3
        }), 200
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500
    finally:
        release_db(conn)

# ── Dashboard ────────────────────────────────────────────────────
@app.route("/")
def dashboard():
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="pt-PT">
    <head>
        <meta charset="UTF-8"/>
        <title>AquaTrack Dashboard</title>
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <style>
            :root {
                --bg-color: #121212;
                --card-bg: #1e1e2f;
                --text-main: #e0e0e0;
                --text-muted: #888;
                --accent: #4cc9f0;
                --alert: #ff4d4d;
                --border: #333;
            }
            body {
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background: var(--bg-color);
                color: var(--text-main);
                padding: 20px;
                margin: 0;
            }
            .header-container {
                display: flex; justify-content: space-between; align-items: center;
                margin-bottom: 20px;
                border-bottom: 1px solid var(--border);
  padding-bottom: 10px;
            }
            h1 { color: var(--accent); margin: 0; }
            h2 { color: #fff; margin-top: 0; font-size: 1.2rem; margin-bottom: 15px;}

            /* Cartões Superiores (Tempo Real) */
            .kpi-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
                gap: 15px;
                margin-bottom: 20px;
            }
            .kpi-card {
                background: var(--card-bg);
                padding: 20px;
                border-radius: 10px;
                text-align: center;
                box-shadow: 0 4px 6px rgba(0,0,0,0.3);
                border-top: 4px solid var(--accent);
            }
            .kpi-card h3 { margin: 0 0 10px 0; font-size: 1rem; color: var(--text-muted); text-transform: uppercase;}
            .kpi-card .valor { font-size: 2rem; font-weight: bold; color: #fff; }

            .card {
                background: var(--card-bg); padding: 20px; border-radius: 10px;
                margin-bottom: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.3);
            }

            /* Grid para as tabelas ficarem lado a lado */
            .tables-grid {
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 20px;
            }
            @media (max-width: 900px) {
                .tables-grid { grid-template-columns: 1fr; }
            }

            table { width: 100%; border-collapse: collapse; font-size: 0.9rem;}
            th, td { padding: 12px; text-align: left; border-bottom: 1px solid var(--border); }
            th { color: var(--accent); font-weight: 600; background: rgba(255,255,255,0.02);}
            tr:hover { background: rgba(255,255,255,0.05); }
            .alerta-linha { border-left: 4px solid var(--alert); }
            .alerta-texto { color: var(--alert); font-weight: bold; }

            .btn-relatorio {
                background-color: var(--accent); color: #000; padding: 10px 20px;
                border: none; border-radius: 5px; cursor: pointer; font-size: 14px; font-weight: bold;
                transition: 0.2s;
            }
 .btn-relatorio:hover { background-color: #3ab0d1; }

            /* Scrollbar bonita para as tabelas */
            .table-wrapper { max-height: 400px; overflow-y: auto; }
            ::-webkit-scrollbar { width: 8px; height: 8px; }
            ::-webkit-scrollbar-track { background: var(--bg-color); }
            ::-webkit-scrollbar-thumb { background: #555; border-radius: 4px; }
            ::-webkit-scrollbar-thumb:hover { background: var(--accent); }
        </style>
    </head>
    <body>
        <div class="header-container">
            <h1>💧 AquaTrack Dashboard</h1>
            <button class="btn-relatorio" onclick="gerarRelatorio()">Gerar Relatório S3</button>
        </div>

        <div class="kpi-grid" id="kpi-container">
            </div>

        <div class="card">
            <h2>Histórico de Leituras (Tempo Real)</h2>
            <canvas id="grafico" height="80"></canvas>
        </div>

        <div class="tables-grid">
            <div class="card">
                <h2>⚠️ Alertas Ativos (Fora do padrão)</h2>
                <div class="table-wrapper" id="alertas">A carregar...</div>
            </div>

            <div class="card">
                <h2>Últimas 50 Leituras</h2>
                <div class="table-wrapper" id="tabela">A carregar...</div>
            </div>
        </div>

        <script>
        let chart;

        // Mapa de cores fixas para cada sensor
        const coresSensores = {
            'temperatura': '#ff6384',  // Vermelho
            'condutividade': '#ffce56', // Amarelo
            'turbidez': '#cc65fe',     // Roxo
            'ph': '#36a2eb',           // Azul claro
            'nivel': '#4bc0c0'         // Verde água
        };

        async function gerarRelatorio() {
            alert("A gerar histórico e enviar para o AWS S3... Por favor, aguarde.");
            try {
                const response = await fetch('/api/gerar-relatorio', { method: 'POST' });
                const data = await response.json();
                if (data.status === 'sucesso') {
                    alert("✅ Sucesso! Ficheiro guardado em: " + data.arquivo);
                } else {
                    alert("❌ Erro ao gerar: " + data.mensagem);

 } catch (e) {
                alert("❌ Erro na requisição do relatório.");
            }
        }

        async function carregar() {
            const [leituras, alertas] = await Promise.all([
                fetch('/api/leituras').then(r => r.json()),
                fetch('/api/alertas').then(r => r.json())
            ]);

            const sensores = [...new Set(leituras.map(d => d.sensor))];

            // 1. Atualizar Cartões KPI (Tempo Real)
            let kpiHtml = '';
            sensores.forEach(s => {
                // Pega a leitura mais recente deste sensor
                const ultimaLeitura = leituras.find(d => d.sensor === s);
                if(ultimaLeitura) {
                    const cor = coresSensores[s] || '#fff';
                    kpiHtml += `
                        <div class="kpi-card" style="border-top-color: ${cor}">
                            <h3>${s}</h3>
                            <div class="valor" style="color: ${cor}">${ultimaLeitura.valor.toFixed(2)}</div>
                        </div>
                    `;
                }
            });
            document.getElementById('kpi-container').innerHTML = kpiHtml;

            // 2. Gráfico
            const datasets = sensores.map(s => {
                const isAltoValor = s === 'condutividade'; // Cria eixo separado para valores altos
                return {
                    label: s,
                    data: leituras.filter(d => d.sensor === s).map(d => d.valor).reverse(),
                    borderColor: coresSensores[s] || '#fff',
                    backgroundColor: coresSensores[s] || '#fff',
                    borderWidth: 2,
                    fill: false,
                    tension: 0.4,
                    yAxisID: isAltoValor ? 'y-alto' : 'y-normal'
                };
            });
 const labels = leituras.filter(d => d.sensor === sensores[0])
                .map(d => new Date(d.timestamp).toLocaleTimeString('pt-PT')).reverse();

            if (!chart) {
                const ctx = document.getElementById('grafico').getContext('2d');
                Chart.defaults.color = '#888';
                chart = new Chart(ctx, {
                    type: 'line',
                    data: { labels, datasets },
                    options: {
                        responsive: true,
                        interaction: { mode: 'index', intersect: false },
                        scales: {
                            'y-normal': {
                                type: 'linear', position: 'left',
                                grid: { color: '#333' }
                            },
                            'y-alto': {
                                type: 'linear', position: 'right',
                                grid: { drawOnChartArea: false } // Evita grelha sobreposta
                            },
                            x: { grid: { color: '#333' } }
                        }
                    }
                });
            } else {
                chart.data.labels = labels;
                chart.data.datasets = datasets;
                chart.update();
            }

            // 3. Tabela de Alertas
            const divAlertas = document.getElementById('alertas');
            if (alertas.length === 0) {
                divAlertas.innerHTML = '<p style="color:#4bc0c0; padding:10px;">✓ Todos os parâmetros dentro do padrão.</p>';
            } else {
                divAlertas.innerHTML = '<table><tr><th>Sensor</th><th>Valor</th><th>Limite</th><th>Reservatório</th></tr>' +
                    alertas.map(a => `<tr class="alerta-linha">
                        <td>${a.sensor}</td>
                        <td class="alerta-texto">${a.valor.toFixed(2)}</td>
                        <td style="color:#888">${a.minimo} – ${a.maximo}</td>
                        <td>${a.reservatorio}</td>
                    </tr>`).join('') + '</table>';
            }

            // 4. Tabela de Leituras
            document.getElementById('tabela').innerHTML =
 '<table><tr><th>Sensor</th><th>Valor</th><th>Hora</th><th>Reservatório</th></tr>' +
                leituras.map(d => `<tr>
                    <td><span style="color:${coresSensores[d.sensor] || '#fff'}">●</span> ${d.sensor}</td>
                    <td style="font-weight:bold;">${d.valor.toFixed(3)}</td>
                    <td style="color:#888">${new Date(d.timestamp).toLocaleTimeString('pt-PT')}</td>
                    <td>${d.reservatorio}</td>
                </tr>`).join('') + '</table>';
        }

        carregar();
        setInterval(carregar, 5000); // Atualiza a cada 5 segundos
        </script>
    </body>
    </html>
    """)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=80)

