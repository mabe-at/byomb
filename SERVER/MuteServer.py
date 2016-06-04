from autobahn.twisted.websocket import WebSocketServerProtocol, \
    WebSocketServerFactory

import signal
import sys
import getopt
import json
import mido
import socket
import os

from twisted.python import log
from twisted.internet import reactor
from twisted.web.server import Site
from twisted.web.static import File
from twisted.web.resource import Resource
from twisted.protocols.policies import TimeoutMixin

from zeroconf import ServiceInfo, Zeroconf

WSPORT = 9000
WEBPORT = 8080
SERVICENAME = 'Mute Button Service'
MIDI_OFF = 0
MIDI_ON = 127
WSPINGTIMEOUT = 5.0
WSPINGINTERVAL = 15.0

class WSPortJs(Resource):
    isLeaf = True
    
    def render_GET(self, request):
        request.setHeader('Content-Type', 'application/javascript')
        return 'var wsport = {};'.format(WSPORT)

class User:
    
    def __init__(self, wscon, name = None, channel = None, control = None):
        self.wscon = wscon
        self.peer = wscon.peer
        self.name = name
        self.channel = channel
        self.control = control

class UserEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, User):
            return { 'peer': obj.peer, 'name': obj.name, 'channel': obj.channel, 'control': obj.control }
        return json.JSONEncoder.default(self, obj)

class MuteServerProtocol(WebSocketServerProtocol):
    
    def onConnect(self, request):
        self.autoPingInterval = WSPINGINTERVAL
        self.autoPingTimeout = WSPINGTIMEOUT 
        print("Client connecting: {0}".format(request.peer))
        #try:
        #    self.transport.setTcpKeepAlive(1)
        #except AttributeError:
        #    print 'Keepalive error'
        #    pass

    def onOpen(self):
        print("WebSocket connection open.")

    def onMessage(self, payload, isBinary):
        #if isBinary:
        #    print("Binary message received: {0} bytes".format(len(payload)))
        #else:
        #    print("Text message received: {0}".format(payload.decode('utf8')))
        
        if not isBinary:
            # print("Text message received: {0}".format(payload.decode('utf8')))
            print("Text message received: {0}".format(payload))
            handleMessage(self, payload)
        
        # echo back message verbatim
        #self.sendMessage(payload, isBinary)
                
    def onClose(self, wasClean, code, reason):
        print("WebSocket connection closed: {0}".format(reason))      
        unsetAdminByWscon(self)
        removeUserByWscon(self)
        
    #def connectionLost(self, reason):
    #    print("WebSocket connection lost: {0}".format(reason))      
    #    unsetAdminByWscon(self)
    #    removeUserByWscon(self)


if __name__ == '__main__':
    
    users = []
    admin = None
    midiport = None
    
    serviceconf = None
    serviceinfo = None
    
    # mido.set_backend('mido.backends.rtmidi')
    # midiport = mido.open_output(u'PowerMateMIDI')
    
    def usage():
        print 'usage: ' + __file__ + ' [-h] [-p port] [-w wsport] [--rtmidi]\n';
        print 'optional arguments:'
        print '  -h, --help\tshow this help'
        print '  -p, --port=\twebserver port listening on, default {}'.format(WEBPORT)
        print '  -w, --wsport=\twebsocket port listening on, default {}'.format(WSPORT)
        print '  --rtmidi\tuse RtMidi instead of PortMidi'
    
    def customHandler(signum, stackframe):
        # print "Got signal: %s" % signum
        if midiport:
            midiport.close()
            
        if serviceconf:
            serviceconf.unregister_all_services()
            serviceconf.close()
            
        reactor.stop()
    
    def isAdmin(wscon):
        global admin
        if admin and admin.wscon.peer == wscon.peer:
            return True
        else:
            return False
    
    def handleMessage(wscon, payload):
        try:
            msg = json.loads(payload)
            if msg['type'] == 'admin':
                handleAdminMessage(wscon, msg)
            elif msg['type'] == 'user':
                handleUserMessage(wscon, msg)
        except ValueError:
            pass
    
    def handleAdminMessage(wscon, msg):
        print("Admin Message")
        if msg['command'] == 'connect':
            try:
                setAdmin(wscon)
                sendAdminMidiPorts()
                sendAdminUsers()
            except ValueError:
                pass
        elif msg['command'] == 'midiport' and isAdmin(wscon):
            global midiport
            try:
                if midiport:
                    midiport.close()
                midiport = None
                midiport = mido.open_output(msg['midiport'])
            except ValueError:
                pass
                
            sendAdminMidiPorts()
        elif msg['command'] == 'channel' and isAdmin(wscon):
            try:
                user = getUserByPeer(msg['peer'])
                if user:
                    uc = int(msg['channel'])
                    if uc > -1:
                        user.channel = uc
                    else:
                        user.channel = None
                sendAdminUsers()
            except ValueError:
                pass
        elif msg['command'] == 'control' and isAdmin(wscon):
            try:
                user = getUserByPeer(msg['peer'])
                if user:
                    uc = int(msg['control'])
                    if uc > -1:
                        user.control = uc
                    else:
                        user.control = None
                sendAdminUsers()
            except ValueError:
                pass
                
    def handleUserMessage(wscon, msg):
        print("User Message")
        user = None
        try:
            if msg['command'] == 'connect':
                try:
                    addUser(wscon, msg['name'])
                    sendAdminUsers()
                except ValueError:
                    pass
            elif msg['command'] == 'muteon':
                try:
                    user = getUserByWscon(wscon)
                    if user:
                        sendMidiMessageOn(user)
                except ValueError:
                    pass
            elif msg['command'] == 'muteoff':
                try:
                    user = getUserByWscon(wscon)
                    if user:
                        sendMidiMessageOff(user)
                except ValueError:
                    pass
            sendAdminUserState(user, msg['command'])
        except ValueError:
            pass
        
    
    def sendAdminUserState(user, state):
        if admin and user:
            admin.wscon.sendMessage(json.dumps({'user': user, 'state': state}, cls=UserEncoder))
    
    def sendMidiMessage(value, channel = 1, control = 5):
        print midiport
        if midiport:
            try:
                print "SEND MIDI MSG"
                msg = mido.Message('control_change', channel = channel, control = control, value = value)
                sm = midiport.send(msg)
                print "MIDI MSG SENT"
                print sm
            except ValueError:
                print "MIDI MSG FAILED"
                pass
    
    def sendMidiMessageOff(user):
        print user.channel, user.control 
        if user.channel is not None and user.control is not None:
            sendMidiMessage(channel = user.channel, control = user.control, value = MIDI_OFF)
    
    def sendMidiMessageOn(user):
        if user.channel is not None and user.control is not None:
            sendMidiMessage(channel = user.channel, control = user.control, value = MIDI_ON)
    
    def setAdmin(wscon):
        print("setAdmin")
        global admin
        closeAdmin()
        admin = User(wscon = wscon)
        
    def unsetAdmin():
        print("Unsetting Admin")
        global admin
        closeAdmin()
        admin = None
        
    def unsetAdminByWscon(wscon):
        global admin
        if admin:
            if admin.wscon == wscon:
                unsetAdmin()
    
    def closeAdmin():
        global admin
        if admin:
            try:
                admin.wscon.sendClose()
            except ValueError:
                pass
    
    def addUser(wscon, name):
        global users
        user = User(wscon = wscon, name = name)
        users.append(user)
    
    def getUserByPeer(peer):
        return next((user for user in users if user.wscon.peer == peer), None)
    
    def getUserByWscon(wscon):
        return next((user for user in users if user.wscon == wscon), None)
    
    def removeUser(user):
        global users
        try:
            users.remove(user)
            sendAdminUsers()
        except ValueError:
            pass
    
    def removeUserByWscon(wscon):
        global users
        for user in users:
            if user.wscon == wscon:
                removeUser(user)
                break
    
    def sendAdminUsers():
        if admin:
            admin.wscon.sendMessage(json.dumps({'users': users}, cls=UserEncoder))
    
    def sendAdminMidiPorts():
        if admin:
            msg = {'midiports': getMidiOutputs()}
            if midiport:
                msg['midiport'] = midiport.name;
            admin.wscon.sendMessage(json.dumps(msg))
    
    def setUserChannel(user, channel):
        user.channel = channel
    
    def setUserControl(user, control):
        user.control = control
    
    def getMidiOutputs():
        return mido.get_output_names()
    
    def get_ip():
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            # doesn't even have to be reachable
            s.connect(('10.255.255.255', 1))
            IP = s.getsockname()[0]
        except:
            #IP = socket.gethostbyname(socket.gethostname())
            IP = '127.0.0.1'
        finally:
            s.close()
        return IP
    
    try:
        opts, args = getopt.getopt(sys.argv[1:], "hp:w:", ["help", "port=", "wsport=", "rtmidi"])
    except getopt.GetoptError:
        usage()
        sys.exit(2)
        
    for opt, arg in opts:
        if opt in ("-h", "--help"):
            usage()
            sys.exit()
        elif opt in ("--rtmidi"):
            mido.set_backend('mido.backends.rtmidi')
            print "Using RtMidi ..."
        elif opt in ("-p", "--port"):
            try:
                tmpport = int(arg)
                if tmpport > 0:
                    WEBPORT = tmpport
            except ValueError:
                usage()
                sys.exit(2)
        elif opt in ("-w", "--wsport"):
            try:
                tmpport = int(arg)
                if tmpport > 0:
                    WSPORT = tmpport
            except ValueError:
                usage()
                sys.exit(2)

    serviceconf = Zeroconf()
    local_ip = get_ip()
    
    print 'Webserver listening on {}:{} ...'.format(local_ip, WEBPORT)
    print 'Webservice listening on {}:{} ...'.format(local_ip, WSPORT)
    
    serviceinfo = ServiceInfo(
        '_http._tcp.local.', 
        SERVICENAME+'._http._tcp.local.', 
        socket.inet_aton(local_ip), 
        WEBPORT,
        0,
        0,
        {"desc":SERVICENAME},
        "mute.local."
        )
    serviceconf.register_service(serviceinfo)
    
    log.startLogging(sys.stdout)
    
    # factory = WebSocketServerFactory(u"ws://127.0.0.1:9000")
    factory = WebSocketServerFactory()
    factory.protocol = MuteServerProtocol
    # factory.setProtocolOptions(maxConnections=2)
     
    signal.signal(signal.SIGINT, customHandler)
    
    reactor.listenTCP(WSPORT, factory)

    webdir_path = os.path.join(os.getcwd(), os.path.dirname(__file__), "../CLIENT")

    if not os.path.exists(webdir_path):
      print 'client directory not found: {}'.format(webdir_path)
    
    webdir = File(webdir_path)
    webdir.putChild('wsport.js', WSPortJs())
    web = Site(webdir)
    reactor.listenTCP(WEBPORT, web)
    
    reactor.run()
    