import json
import datetime
from json import JSONEncoder
import requests
from sqs_polling import sqs_polling

dados = {}
try:
    with open('config.json', 'r') as f:
        dados = json.loads(f.read() or '{}')
except IOError:
    exit()

HOST = dados.get('HOST', '')
DEBUG = dados.get('DEBUG', True)
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
    evento = json.loads(evento)
    log_to_file(evento)
    job_token = evento['job_token']
    job_secret = evento['job_secret']
    url = f'https://{HOST}/gateway/sync_start/{job_token}/{job_secret}'
    rs = requests.get(url)
    if rs.status_code == 200:
        dados = json.loads(rs.content)
        modelo = dados['modelo']
        connection_string = dados['connection_string']
        sql = dados['sql']
        try:
            import pyodbc
            connection = pyodbc.connect(connection_string, timeout=10)
            connection.setdecoding(pyodbc.SQL_CHAR, encoding='utf-8')
            connection.setencoding(encoding='utf-8')
            cursor = connection.cursor().execute(sql)
            columns = [column[0] for column in cursor.description]
            log_to_file(columns)
            results = []
            for row in cursor.fetchall():
                # log_to_file(row)
                results.append(dict(zip(columns, row)))
            count = len(results)
            log_to_file(f"SYNC - {modelo} - {job_token} - {count}")
            r = requests.get(
                f'https://{HOST}/gateway/sync/{job_token}/{job_secret}',
                data=json.dumps(results, cls=DateTimeEncoder),
	            timeout=120,
            )
            if r.status_code != 200:
                requests.get(
                    f'https://{HOST}/gateway/sync_error/{job_token}',
                    data=r.content,
	                timeout=5,
                )
                log_to_file(f"SYNC ERROR SEND - {modelo} - {job_token}")
            else:
                return True

        except Exception as ex:
            requests.get(
                f'https://{HOST}/gateway/sync_error/{job_token}',
                data=str(ex),
	            timeout=5,
            )
            log_to_file(f"SYNC ERROR - {modelo} - {job_token} - {ex}")

    return False

if __name__ == "__main__":
    if not HOST:
        exit()
    sqs_polling(
        queue_url=QUEUE_URL,
        callback=sync,
        visibility_timeout=30,
        interval_seconds=2,
        max_workers=1,
        # process_worker=True,
        aws_profile_dict=json.load(open('aws_secret.json', 'r'))
        )
