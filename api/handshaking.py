import sys

class ConnectServer(object):
    ExpectedProtocolVersion = "1.4"

    def __init__(self, protocolVersion = ExpectedProtocolVersion):
        super(ConnectServer, self).__init__()
        self.protocolVersion = protocolVersion

    def validate(self):
        if self.protocolVersion != self.ExpectedProtocolVersion:
            print >> sys.stderr, "This client version does not match network protocol version. Expected version {} received {}.".format(self.ExpectedProtocolVersion, self.protocolVersion)
            return False
        return True

    def __str__(self):
        return "ConnectServer"


class ConnectClient(object):
    def __init__(self, commanderName, language):
        super(ConnectClient, self).__init__()
        self.commanderName = commanderName
        self.language = language

    def __str__(self):
        return "ConnectClient commanderName = {}, language = {}".format(self.commanderName, self.language)


def toJSON(python_object):
    if isinstance(python_object, ConnectServer):
        connect = python_object
        return {'__class__': 'ConnectServer',
                '__value__': { 'protocolVersion': connect.protocolVersion }}

    if isinstance(python_object, ConnectClient):
        connect = python_object
        return {'__class__': 'ConnectClient',
                '__value__': { 'commanderName': connect.commanderName, 'language': connect.language }}


def fromJSON(dct):
    if '__class__' in dct:
        if dct['__class__'] == 'ConnectServer':
            value = dct['__value__']
            return ConnectServer(value['protocolVersion'].encode('utf-8'))

        if dct['__class__'] == 'ConnectClient':
            value = dct['__value__']
            return ConnectClient(value['commanderName'].encode('utf-8'), value['language'].encode('utf-8'))

    return dct

