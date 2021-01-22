import json
import websocket
import win32serviceutil
import win32service
import win32event
import servicemanager
import socket
import gateway


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


class AppServerSvc(win32serviceutil.ServiceFramework):
    _svc_name_ = "DTrackGateway"
    _svc_display_name_ = "DTrack GATEWAY"

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
        socket.setdefaulttimeout(60)

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.hWaitStop)

    def SvcDoRun(self):
        servicemanager.LogMsg(servicemanager.EVENTLOG_INFORMATION_TYPE,
                              servicemanager.PYS_SERVICE_STARTED,
                              (self._svc_name_, ''))
        self.main()

    def main(self):
        websocket.enableTrace(DEBUG)
        try:
            gateway.connect_websocket()
        except Exception as err:
            if DEBUG:
                print(err)
                print("connect failed")


if __name__ == '__main__':
    win32serviceutil.HandleCommandLine(AppServerSvc)