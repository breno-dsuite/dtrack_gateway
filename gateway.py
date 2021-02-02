import json
import socket
import time
import datetime
from json import JSONEncoder
import pyodbc
import requests
import serial
import usb.core
import usb.util
import websocket


# SECURE = False
# SERVER_URL = '0.0.0.0:9999'
# GATEWAY_TOKEN = ''


# class DateTimeDecoder(JSONDecoder):
#
# 	def __init__(self, *args, **kargs):
# 		JSONDecoder.__init__(self, object_hook=self.dict_to_object,
# 		                     *args, **kargs)
#
# 	def dict_to_object(self, d):
# 		if '__type__' not in d:
# 			return d
#
# 		type = d.pop('__type__')
# 		try:
# 			dateobj = datetime(**d)
# 			return dateobj
# 		except:
# 			d['__type__'] = type
# 			return d


class DateTimeEncoder(JSONEncoder):
	""" Instead of letting the default encoder convert datetime to string,
		convert datetime objects into a dict, which can be decoded by the
		DateTimeDecoder
	"""

	def default(self, obj):
		if isinstance(obj, datetime.datetime):
			return {
				'__type__': 'datetime',
				'year': obj.year,
				'month': obj.month,
				'day': obj.day,
				'hour': obj.hour,
				'minute': obj.minute,
				'second': obj.second,
				'microsecond': obj.microsecond,
				}
		elif isinstance(obj, datetime.time):
			return {
				'__type__': 'time',
				# 'year': obj.year,
				# 'month': obj.month,
				# 'day': obj.day,
				'hour': obj.hour,
				'minute': obj.minute,
				'second': obj.second,
				'microsecond': obj.microsecond,
				}
		elif isinstance(obj, datetime.date):
			return {
				'__type__': 'date',
				'year': obj.year,
				'month': obj.month,
				'day': obj.day,
				# 'hour': obj.hour,
				# 'minute': obj.minute,
				# 'second': obj.second,
				# 'microsecond': obj.microsecond,
				}
		else:
			return JSONEncoder.default(self, obj)


with open('config.json', 'r') as f:
	dados = json.loads(f.read())
	SECURE = dados.get('SECURE', True)
	SERVER_URL = dados.get('SERVER_URL', None)
	HOST = dados.get('HOST', None)
	GATEWAY_TOKEN = dados.get('GATEWAY_TOKEN', None)
	GATEWAY_SECRET = dados.get('GATEWAY_SECRET', None)
	DEBUG = dados.get('DEBUG', True)
	if not SERVER_URL:
		raise Exception('Favor informar SERVER_URL no arquivo .env')
	if not HOST:
		raise Exception('Favor informar HOST no arquivo .env')
	if not GATEWAY_TOKEN:
		raise Exception('Favor informar GATEWAY_TOKEN no arquivo .env')
	if not GATEWAY_SECRET:
		raise Exception('Favor informar GATEWAY_SECRET no arquivo .env')


def agora():
	return datetime.datetime.now().isoformat()


def log_to_file(log):
	msg = f'{agora()} - {HOST} - {GATEWAY_TOKEN} - {log}\n'
	if DEBUG:
		print(msg)
	with open('gateway.log', 'a') as f:
		f.write(msg)


def connect_websocket():
	ws = websocket.WebSocketApp(
		f"ws{'s' if SECURE else ''}://{SERVER_URL}/",
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


def get_print_jobs():
	tentativas = 10
	tempo_espera = 2
	for x in range(tentativas):
		r = requests.get(
			f'https://{HOST}/gateway/print_jobs'
			f'/{GATEWAY_TOKEN}/{GATEWAY_SECRET}')
		if r.status_code == 200:
			return json.loads(r.content)
		time.sleep(tempo_espera)
	return []


def get_print_details(print_id, print_secret):
	tentativas = 10
	tempo_espera = 1
	for x in range(tentativas):
		r = requests.get(
			f'https://{HOST}/gateway/print_start'
			f'/{print_id}/{print_secret}')
		if r.status_code == 200:
			return json.loads(r.content)
		time.sleep(tempo_espera)
	return {}


def print_windows(details):
	try:
		import win32print
		printer = win32print.OpenPrinter(details['printer_name'])
		try:
			print_job = win32print.StartDocPrinter(
				printer, 1, (details['print_description'].encode('utf-8'),
				             None, "RAW")
				)
			try:
				win32print.StartPagePrinter(printer)
				win32print.WritePrinter(
					printer, details['print_code'].encode('utf-8')
					)
				win32print.EndPagePrinter(printer)
				r = requests.get(
					f'https://{HOST}/gateway/print_end'
					f'/{details["print_id"]}/{details["print_secret"]}'
					)
			finally:
				win32print.EndDocPrinter(printer)
		finally:
			win32print.ClosePrinter(printer)
	except ImportError:
		pass


def print_network(details):
	with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
		# s.settimeout(timeout)
		try:
			s.connect((details["printer_ip"], int(details["printer_port"])))
			s.send(details['print_code'].encode('utf-8'))
			requests.get(
				f'https://{HOST}/gateway/print_end'
				f'/{details["print_id"]}/{details["print_secret"]}'
				)
			log_to_file(f'PRINT_NETWORK - {details["print_id"]}')
		except socket.timeout:
			erro = 'TIMEOUT - Impressora indisponível ou não encontrada.'
			requests.get(
				f'https://{HOST}/gateway/print_end'
				f'/{details["print_id"]}/{details["print_secret"]}',
				json={'erro': erro}
				)
			log_to_file(f'PRINT_NETWORK TIMEOUT - {details["print_id"]}')
		except Exception as ex:
			erro = str(ex)
			requests.get(
				f'https://{HOST}/gateway/print_end'
				f'/{details["print_id"]}/{details["print_secret"]}',
				json={
					'erro': erro
					}
				)
			log_to_file(f'PRINT_NETWORK ERROR - {details["print_id"]} - {ex}')


def print_usb(details):
	try:
		device = usb.core.find(
			idVendor=int(details["printer_vendor"]),
			# idProduct=int(id_product)
			)
		if device is not None:
			device.reset()
			device.set_configuration()
			cfg = device.get_active_configuration()
			intf = cfg[(0, 0)]
			ep = usb.util.find_descriptor(
				intf,
				custom_match= \
					lambda e: \
						usb.util.endpoint_direction(
							e.bEndpointAddress) ==
						usb.util.ENDPOINT_OUT
				)
			ep.write(details['print_code'].encode('utf-8'), 300000)
			usb.util.dispose_resources(device)
			device.reset()
			requests.get(
				f'https://{HOST}/gateway/print_end'
				f'/{details["print_id"]}/{details["print_secret"]}'
				)
			log_to_file(f'PRINT_USB - {details["print_id"]}')
		else:
			erro = 'Impressora não encontrada ou desconectada'
			requests.get(
				f'https://{HOST}/gateway/print_end'
				f'/{details["print_id"]}/{details["print_secret"]}',
				json={
					'erro': erro
					}
				)
			log_to_file(f'PRINT_USB ERROR - {details["print_id"]} - {erro}')
	except Exception as ex:
		erro = str(ex)
		log_to_file(f'PRINT_USB ERROR - {details["print_id"]} - {erro}')

		requests.get(
			f'https://{HOST}/gateway/print_end'
			f'/{details["print_id"]}/{details["print_secret"]}',
			json={
				'erro': erro
				}
			)


def select_printer(details):
	if details.get('printer_ip'):
		print_network(details)
	elif details.get('printer_name'):
		print_windows(details)
	elif details.get('printer_vendor'):
		print_usb(details)


def on_message(ws, message):
	def ping(evento):
		host = evento['host']
		data = {
			"action": "sendmessage",
			"data": {
				'type': 'ping',
				'gateway_token': GATEWAY_TOKEN,
				'host': host,
				}
			}
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
		host = evento['host']
		print_id = evento.get('print_id', '')
		print_secret = evento.get('print_secret', '')
		print_detail = get_print_details(print_id, print_secret)
		if print_detail:
			select_printer(print_detail)


	def sync(evento):
		host = evento['host']
		job_token = evento['job_token']
		rs = requests.get(f'https://{host}/gateway/sync_start/{job_token}')
		if rs.status_code == 200:
			dados = rs.json()
			model = dados['model']
			connection_string = dados['connection_string']
			sql = dados['sql']

			try:
				connection = pyodbc.connect(connection_string)
				connection.setdecoding(pyodbc.SQL_CHAR, encoding='utf-8')
				connection.setencoding(encoding='utf-8')
				cursor = connection.cursor().execute(sql)
				columns = [column[0] for column in cursor.description]
				results = []
				for row in cursor.fetchall():
					results.append(dict(zip(columns, row)))
				r = requests.get(
					f'https://{host}/gateway/sync/{model}/{job_token}',
					data=json.dumps(results, cls=DateTimeEncoder)
					)

				if r.status_code != 200:
					requests.get(
						f'https://{host}/gateway/sync_error/{job_token}',
						data=r.content,
						)
			except Exception as ex:
				requests.get(
					f'https://{host}/gateway/sync_error/{job_token}',
					data=str(ex),
					)
				log_to_file(f"SYNC - {model} - {job_token} - {count}")
			# ws.send(json.dumps({
			# 	"action": "sendmessage",
			# 	"data": {
			# 		'type': 'log',
			# 		'gateway_token': GATEWAY_TOKEN,
			# 		'host': host,
			# 		'mensagem': f'SYNC - {model} - {job_token} - {count}',
			# 		}
			# 	}, cls=DateTimeEncoder))

	message = json.loads(message)

	if DEBUG:
		log_to_file(f"MSG - {message}")

	router = {
		'ping': ping,
		'balanca': balanca,
		'impressora': impressora,
		'impressora_cupom': impressora,
		'sync': sync,
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
	# lista = get_print_jobs()
	# for job in lista:
	# 	details = get_print_details(job['print_id'], job['print_secret'])


if __name__ == "__main__":
	websocket.enableTrace(DEBUG)
	try:
		connect_websocket()
	except Exception as err:
		if DEBUG:
			print(err)
			print("connect failed")
