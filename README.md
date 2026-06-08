# 💧 AquaTrack

O **AquaTrack** é um sistema completo para monitoramento em tempo real de reservatórios de água. Ele utiliza sensores simulados via MQTT para acompanhar métricas vitais como pH, turbidez, condutividade, nível e temperatura.

## 🚀 Funcionalidades

- **Dashboard em Tempo Real:** Interface web elegante e responsiva para visualização do estado dos reservatórios com gráficos atualizados.
- **Integração IoT (MQTT):** Leitura contínua de dados de sensores via broker MQTT hospedado na nuvem (AWS EC2).
- **Simulador de Sensores:** Script para gerar dados variados de qualidade da água (ideal para simulações e testes de estresse).
- **Armazenamento em Banco de Dados:** Gravação persistente das leituras utilizando PostgreSQL.
- **Integração com a Nuvem (AWS S3):** Geração de relatórios completos em `.csv` com o histórico de leituras e upload automático para um bucket na AWS.
- **Sistema de Alertas Dinâmico:** Identificação imediata de valores que fujam dos padrões esperados (por exemplo, pH fora da Portaria 5/2017).

## 🛠️ Tecnologias Utilizadas

- **Backend:** Python, Flask
- **Banco de Dados:** PostgreSQL
- **IoT & Mensageria:** MQTT (Biblioteca `paho-mqtt`)
- **Frontend:** HTML, CSS, JavaScript Vanilla, Chart.js
- **Cloud (AWS):** EC2 (Broker MQTT) e S3 (Buckets para armazenamento Boto3)
- **Acesso Remoto:** PuTTY (conexão SSH ao servidor EC2 na AWS)

## 📁 Estrutura de Arquivos

- `codigo.py`: Aplicação central (Servidor Flask), incluindo as rotas da API, regras de banco de dados, cliente MQTT e conexão Boto3 com S3.
- `simulador.py`: Script avulso que publica dados aleatórios no Broker simulando um reservatório em funcionamento.
- `banco.db`: Arquivo de configuração local; os registros e histórico de alertas são persistidos no banco de dados PostgreSQL.
- `labuser.ppk`: Chave privada no formato PuTTY (PPK) utilizada para autenticação SSH via PuTTY na instância EC2 da AWS.

## ⚙️ Como Executar o Projeto

### 1. Instalar as Dependências

Garanta que você tem o Python 3 instalado e execute o comando abaixo para instalar os pacotes necessários:

```bash
pip install flask paho-mqtt boto3
```

*(Nota: Para enviar relatórios em CSV, certifique-se de configurar suas credenciais do AWS CLI localmente)*.

### 2. Iniciar o Servidor (Dashboard)

Rode o script principal para ligar a interface Web e a conexão de escuta do MQTT:

```bash
python codigo.py
```

O painel ficará acessível no seu navegador pelo endereço que for gerado no próximo login feito no AWS EC2 onde nas configurações da instância do backend fica disponível o ip público que deverá ser usado para acessar o painel dashboard.

### 3. Iniciar a Simulação de Dados

Em outro terminal (com o mesmo ambiente virtual), ligue o simulador de sensores para que o sistema receba tráfego e alimente os gráficos:

```bash
python simulador.py
```
Ele passará a enviar requisições de pH, nível de água, turbidez e condutividade a cada 30 segundos!