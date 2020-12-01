import json
import socket
from datetime import datetime
import serial
import websocket
import time

# SECURE = False
# SERVER_URL = '0.0.0.0:9999'
# GATEWAY_ID = ''

with open('.env', 'r') as f:
    dados = json.loads(f.read())
    SECURE = dados.get('SECURE', True)
    SERVER_URL = dados.get('SERVER_URL', None)
    GATEWAY_ID = dados.get('GATEWAY_ID', None)
    DEBUG = dados.get('DEBUG', True)
    if not SERVER_URL:
        raise Exception('Favor informar SERVER_URL no arquivo .env')
    if not GATEWAY_ID:
        raise Exception('Favor informar GATEWAY_ID no arquivo .env')


def log_to_file(log):
    msg = f'{datetime.now().isoformat()} - {SERVER_URL} - {GATEWAY_ID} - {log}\n'
    if DEBUG:
        print(msg)
    with open('gateway.log', 'a') as f:
        f.write(msg)


def connect_websocket():
    ws = websocket.WebSocketApp(f"ws{'s' if SECURE else ''}://{SERVER_URL}/ws/gateway/{GATEWAY_ID}/",
                                on_message=on_message,
                                on_error=on_error,
                                on_close=on_close)
    ws.on_open = on_open
    ws.run_forever(
        skip_utf8_validation=True,
    )


def on_message(ws, message):
    def ler_serial(evento):
        def parse_peso(str_peso):
            if DEBUG:
                log_to_file(f"PESO RECEBIDO: {str_peso}")
            peso = float(str_peso.replace('+', '').replace(' kg', '').strip())
            if DEBUG:
                log_to_file(f"PESO CONVERTIDO: {peso}")
            return peso

        porta = evento['porta']
        baudrate = evento['baudrate']
        bytesize = evento['bytesize']
        stopbits = evento['stopbits']
        parity = evento['parity']
        xonxoff = evento['xonxoff']
        rtscts = evento['rtscts']
        timeout = evento['timeout']
        try:
            with serial.Serial(porta,
                               baudrate=baudrate,
                               bytesize=bytesize,
                               stopbits=stopbits,
                               parity=parity,
                               timeout=timeout,
                               xonxoff=xonxoff,
                               rtscts=rtscts
                               ) as ser:
                t = ser.readline().decode()
                if DEBUG:
                    log_to_file(f"LINHA RECEBIDA: {t}")
                if t:
                    t = t.split(',')
                    if '+' in t[2] and t[0] == 'ST':
                        return parse_peso(t[2])
                else:
                    return 0.000
        except:
            return 0.000

    def balanca(evento):
        balanca_id = evento['balanca_id']
        pesagem_id = evento.get('pesagem_id')

        peso = 0.000
        tentativa = 0
        while not peso:
            peso = ler_serial(evento)
            tentativa += 1
            if not peso:
                time.sleep(.2)
            if tentativa == 10:
                break
        dados = {
            'type': evento['type'],
            'balanca_id': balanca_id,
            'peso': peso
        }
        if pesagem_id:
            dados['pesagem_id'] = pesagem_id

        ws.send(json.dumps(dados))

    def impressora(evento):
        impressora_id = evento['impressora_id']
        print_id = evento.get('print_id')
        ip = evento['ip']
        codigo = evento.get('codigo')
        porta = evento.get('porta', 9100)
        timeout = evento.get('timeout', 1)
        dados = {
            'type': evento['type'],
            'impressora_id': impressora_id,
            'online': True,
        }
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            try:
                s.connect((ip, int(porta)))
                if print_id:
                    dados['print_id'] = print_id
                    if DEBUG:
                        log_to_file(codigo)
                    s.send(codigo.encode('utf-8'))

                log_to_file(f"{evento['type']} - {ip} - {porta} - {print_id} - OK")
            except socket.timeout:
                log_to_file(f"{evento['type']} - {ip} - {porta} - {print_id} TIMEOUT {timeout}s")
                dados['online'] = False
        ws.send(json.dumps(dados))

    if DEBUG:
        log_to_file(message)

    message = json.loads(message)

    router = {
        'balanca': balanca,
        'impressora': impressora,
        'impressora_cupom': impressora,
    }
    if 'type' in message:
        router[message['type']](message)


def on_error(ws, error):
    log_to_file(f"ERROR - {error}")


def on_close(ws):
    try:
        log_to_file('CLOSE')
        time.sleep(5)
        connect_websocket()
    except KeyboardInterrupt:
        pass


def on_open(ws):
    log_to_file('OPEN')


if __name__ == "__main__":
    websocket.enableTrace(DEBUG)
    try:
        connect_websocket()
    except Exception as err:
        if DEBUG:
            print(err)
            print("connect failed")



