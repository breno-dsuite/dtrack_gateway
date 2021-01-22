import json
import socket
from datetime import datetime

import requests
import serial
import websocket
import time
import usb.core
import usb.util
from websocket import create_connection

# SECURE = False
# SERVER_URL = '0.0.0.0:9999'
# GATEWAY_TOKEN = ''

with open('config.json', 'r') as f:
    dados = json.loads(f.read())
    SECURE = dados.get('SECURE', True)
    SERVER_URL = dados.get('SERVER_URL', None)
    GATEWAY_TOKEN = dados.get('GATEWAY_TOKEN', None)
    GATEWAY_SECRET = dados.get('GATEWAY_SECRET', None)
    DEBUG = dados.get('DEBUG', True)
    if not SERVER_URL:
        raise Exception('Favor informar SERVER_URL no arquivo .env')
    if not GATEWAY_TOKEN:
        raise Exception('Favor informar GATEWAY_TOKEN no arquivo .env')
    if not GATEWAY_SECRET:
        raise Exception('Favor informar GATEWAY_SECRET no arquivo .env')


def log_to_file(log):
    msg = f'{datetime.now().isoformat()} - {SERVER_URL} - {GATEWAY_TOKEN} - {log}\n'
    if DEBUG:
        print(msg)
    with open('gateway.log', 'a') as f:
        f.write(msg)


def connect_websocket():
    ws = websocket.WebSocketApp(f"ws{'s' if SECURE else ''}://{SERVER_URL}/",
                                header={
                                    'gateway_token': GATEWAY_TOKEN,
                                    'gateway_secret': GATEWAY_SECRET,
                                },
                                on_message=on_message,
                                on_error=on_error,
                                on_close=on_close)
    ws.on_open = on_open
    ws.run_forever(
        skip_utf8_validation=True,
        ping_interval=60,
        ping_timeout=5,
    )


def on_message(ws, message):
    def ping(evento):
        data = {"action": "sendmessage", "data": {'type': 'ping', 'gateway_token': GATEWAY_TOKEN}}
        ws.send(json.dumps(data))

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
        host = evento['host']
        print_id = evento.get('print_id', '')
        print_secret = evento.get('print_secret', '')
        ip = evento.get('ip', '')
        id_vendor = evento.get('id_vendor', '')
        id_product = evento.get('id_product', '')

        porta = evento.get('porta', 9100)
        timeout = evento.get('timeout', 1)
        dados = {
            'type': 'print_id' if print_id else 'ping_impressora',
            'gateway_token': GATEWAY_TOKEN,
            'impressora_id': impressora_id,
            'print_id': print_id,
            'online': True,
        }
        if ip:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(timeout)
                try:
                    s.connect((ip, int(porta)))
                    if print_id and print_secret:
                        r_codigo = requests.get(f'https://{host}/gateway/codigo_print_id/{print_id}/{print_secret}')
                        if r_codigo.status_code == 200:
                            s.send(r_codigo.content)

                    log_to_file(f"{evento['type']} - {ip} - {porta} - {print_id} - OK")
                except socket.timeout:
                    log_to_file(f"{evento['type']} - {ip} - {porta} - {print_id} - TIMEOUT {timeout}s")
                    dados['online'] = False
                    dados['erro'] = f'Timeout {timeout}s'
                except Exception as ex:
                    log_to_file(f"{evento['type']} - {ip} - {porta} - {print_id} - {ex}")
                    dados['online'] = False
                    dados['erro'] = str(ex)
        else:
            try:
                device = usb.core.find(idVendor=int(id_vendor), idProduct=int(id_product))
                in_ep = 0x82
                out_ep = 0x01
                if device is not None:
                    check_driver = None
                    try:
                        check_driver = device.is_kernel_driver_active(0)
                    except NotImplementedError:
                        pass

                    if check_driver is None or check_driver:
                        try:
                            device.detach_kernel_driver(0)
                        except usb.core.USBError as e:
                            if check_driver is not None:
                                print("Could not detatch kernel driver: {0}".format(str(e)))

                    try:
                        device.set_configuration()
                        device.reset()
                    except usb.core.USBError as e:
                        print("Could not set configuration: {0}".format(str(e)))
                    if print_id and print_secret:
                        r_codigo = requests.get(f'https://{host}/gateway/codigo_print_id/{print_id}/{print_secret}')
                        if r_codigo.status_code == 200:
                            device.write(out_ep, r_codigo.content, timeout)
                            usb.util.dispose_resources(device)
                            log_to_file(f"{evento['type']} - {id_vendor} - {id_product} - {print_id} - OK")
                else:
                    log_to_file(f"{evento['type']} - {id_vendor} - {id_product} - {print_id} - NÃO ENCONTRADO")
                    dados['online'] = False
                    dados['erro'] = f'Impressora não encontrada ou desconectada'
            except Exception as ex:
                log_to_file(f"{evento['type']} - {id_vendor} - {id_product} - {print_id} - {ex}")
                dados['online'] = False
                dados['erro'] = str(ex)

        ws.send(json.dumps({"action": "sendmessage", "data": dados}))

    if DEBUG:
        log_to_file(f"MSG - {message}")

    message = json.loads(message)

    router = {
        'ping': ping,
        'balanca': balanca,
        'impressora': impressora,
        'impressora_cupom': impressora,
    }
    if 'type' in message:
        router[message['type']](message)
    elif 'message' in message:
        log_to_file(f"ROUTE NOT FOUND - {message}")
        ws.close()
        connect_websocket()


def on_error(ws, error):
    log_to_file(f"ERROR - {error}")
    ws.close()
    connect_websocket()


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
    ws = websocket.create_connection(f"ws{'s' if SECURE else ''}://{SERVER_URL}/",
                                header={
                                    'gateway_token': GATEWAY_TOKEN,
                                    'gateway_secret': GATEWAY_SECRET,
                                })
    try:
        connect_websocket()
    except Exception as err:
        if DEBUG:
            print(err)
            print("connect failed")



