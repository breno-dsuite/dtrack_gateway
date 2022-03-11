import json
import datetime
import uuid
from json import JSONEncoder
import requests
from botocore.exceptions import ClientError
import boto3

session = boto3.Session(
	**json.load(open('aws_secret.json', 'r'))
	)
sqs = session.resource('sqs')
queue = sqs.get_queue_by_name(QueueName='DTrackSync.fifo')
out_queue = sqs.get_queue_by_name(QueueName='DTrackSyncOUT.fifo')

dados = {}
try:
	with open('config.json', 'r') as f:
		dados = json.loads(f.read() or '{}')
except IOError:
	exit()

HOST = dados.get('HOST', '')
# DEBUG = dados.get('DEBUG', True)
DEBUG = True
QUEUE_URL = 'https://sqs.us-east-1.amazonaws.com/509609055537/DTrackSync.fifo'


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


def agora():
	return datetime.datetime.now().isoformat()


def log_to_file(log):
	msg = f'{agora()} - {HOST} - {log}\n'
	if DEBUG:
		print(msg)
	with open(f'{datetime.datetime.now().strftime("%Y-%j")}-SYNC.log',
			  'a') as f:
		f.write(msg)


def sync(evento):
	log_to_file(evento)
	job_token = evento['job_token']
	job_secret = evento['job_secret']
	url = f'https://{HOST}/gateway/sync_start/{job_token}/{job_secret}'
	try:
		rs = requests.get(url, timeout=20)
		log_to_file(f'JOB - {job_token}')
		if rs.status_code == 200:
			dados = json.loads(rs.content)
			log_to_file(f'DADOS - {dados}')
			modelo = dados['modelo']
			connection_string = dados['connection_string']
			sql = dados['sql']
			try:
				import pyodbc
				connection = pyodbc.connect(connection_string, timeout=10)
				log_to_file(f'CONNECT - {modelo} - {job_token}')
				connection.setdecoding(pyodbc.SQL_CHAR, encoding='utf-8')
				connection.setencoding(encoding='utf-8')
				cursor = connection.cursor().execute(sql)
				log_to_file(f'QUERY - {modelo} - {job_token}')
				columns = [column[0] for column in cursor.description]
				log_to_file(columns)
				results = []
				for row in cursor.fetchall():
					# log_to_file(row)
					results.append(dict(zip(columns, row)))
				msg_id = str(uuid.uuid4())
				response = out_queue.send_message(
					MessageBody=json.dumps(
						{
							**evento,
							'results': json.dumps(results, cls=DateTimeEncoder)
						}),
					MessageDeduplicationId=msg_id,
					MessageGroupId=msg_id
					)
				count = len(results)
				log_to_file(f"SYNC - {modelo} - {job_token} - {count}")
				return True
				# r = requests.get(
				# 	f'https://{HOST}/gateway/sync/{job_token}/{job_secret}',
				# 	data=json.dumps(results, cls=DateTimeEncoder),
				# 	timeout=120,
				# )
				# log_to_file('SEND OK')
				# if r.status_code != 200:
				# 	requests.get(
				# 		f'https://{HOST}/gateway/sync_error/{job_token}',
				# 		data=r.content,
				# 		timeout=5,
				# 	)
				# 	log_to_file(f"SYNC ERROR SEND - {modelo} - {job_token}")
				# else:
				# 	return True

			except Exception as ex:
				requests.get(
					f'https://{HOST}/gateway/sync_error/{job_token}',
					data=str(ex),
					timeout=5,
				)
				log_to_file(f"SYNC ERROR - {modelo} - {job_token} - {ex}")
	except requests.ReadTimeout:
		return False
	return False

# if __name__ == "__main__":
if not HOST:
	raise ValueError('Definir HOST')

def receive_messages(queue, max_number=10, wait_time=20):
	"""
	Receive a batch of messages in a single request from an SQS queue.

	:param queue: The queue from which to receive messages.
	:param max_number: The maximum number of messages to receive. The actual number
					   of messages received might be less.
	:param wait_time: The maximum time to wait (in seconds) before returning. When
					  this number is greater than zero, long polling is used. This
					  can result in reduced costs and fewer false empty responses.
	:return: The list of Message objects received. These each contain the body
			 of the message and metadata and custom attributes.
	"""
	try:
		messages = queue.receive_messages(
			MessageAttributeNames=['All'],
			MaxNumberOfMessages=max_number,
			WaitTimeSeconds=wait_time
			)
		for msg in messages:
			yield msg
	except ClientError as error:
		raise error
	else:
		return messages
queue = sqs.get_queue_by_name(QueueName='DTrackSync.fifo')
while True:
	print('RECEBENDO')
	for msg in receive_messages(queue):
		print(msg)
		r = sync(json.loads(msg.body))
		if bool(r):
			msg.delete()

	# sqs_polling(
	# 	queue_url=QUEUE_URL,
	# 	callback=sync,
	# 	visibility_timeout=30,
	# 	interval_seconds=2,
	# 	max_workers=1,
	# 	# process_worker=True,
	# 	aws_profile_dict=json.load(open('aws_secret.json', 'r'))
	# 	)
