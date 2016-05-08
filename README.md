# byomb
**Bring Your Own Mute Button**  
WebSocket client and server for Midi-based mute buttons

**WARNING!**  
**There are no security measures taken at all!**  
**Use server and client in well-known/private networks only!**

The idea behind this project is, that every podcast guest can use his/her smartphone/tablet/mobile device with a recent browser as mute button.

##Server

Start server with ```cd SERVER/ ; python MuteServer.py```

```
usage: MuteServer.py [-h] [-p port] [-w wsport] [--rtmidi]

optional arguments:
  -h, --help      show this help
  -p, --port=     webserver port listening on, default 8080
  -w, --wsport=   websocket port listening on, default 9000
  --rtmidi        use RtMidi instead of PortMidi
```

Server propagates client-url (IP and port) through Bonjour/mDNS/Zeroconf as "Mute Button Service".
OS X/iOS devices can connect to client-app (mute button and admin interface) with URL ```http://mute.local:<port>``` respectively ```http://mute.local:<port>/admin.html``` for the admin interface.

### Dependencies
- Autobahn|Python using Twisted (http://autobahn.ws/python/)  
- Mido - MIDI Objects for Python (https://github.com/olemb/mido)  
- Zeroconf (https://pypi.python.org/pypi/zeroconf)  
- ... and probably others

##Clients
HTML clients use Material Design Lite and WebSockets.
Clients are successfully tested on recent iOS (Chrome/Firefox/Safari), recent Android (Chrome), Firefox OS 2.2, OS X/Windows (recent browser).
###Mute Button
Open ```http://<ip>:<port>``` in your browser.  

![](https://mabe.at/byomb/mute-button_connect.png)
![](https://mabe.at/byomb/mute-button_on.png)
![](https://mabe.at/byomb/mute-button_off.png)
###Admin Interface
Open ```http://<ip>:<port>/admin.html``` in your browser.  
Select MidiPort and assign individual channel and button to every mute button client.  

![](https://mabe.at/byomb/admin-interface.png)
