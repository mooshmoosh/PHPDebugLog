#!/usr/bin/python3
"""
PHP Debug Log

Make a HTTP(S) request to a PHP application, and generate a complete log of the state of the interpreter at every line of code.
"""

import socket, xml.dom.minidom, base64, sys, json

def getFullnameOfProperty(p):
    """
    *Only used internally*
    Takes a property description object as returned by 

        xml.dom.minidom.parseString(ResponseFromXdebug).getElementsByTagName("property")

    and returns the full php name of the variable.
    """
    if "fullname" not in p.attributes:
        return p.attributes["name"].value
    else:
        return p.attributes["fullname"].value

FakeAddressCounter = 0
def getFakeAddress():
    """
    *Only used internally*
    Returns new unique strings of the form "F0" "F1" "F2" etc.
    Used to create placeholders for the memory addresses of variables we can't get the value/address of. (Such as when they haven't been initialised yet)
    """
    global FakeAddressCounter
    FakeAddressCounter += 1
    return "F" + str(FakeAddressCounter)

class VariablePrinter:
    """
        
    """
    def __init__(self, variableList):
        self.yetToVisit = variableList
        self.visited = {}
        self.objects = {}
        self.output = []

    def printVariable(self, name, variable, indent):
        if type(variable) is str:
            self.output += [indent, name, ': ', variable, "\n"]
        else:
            self.output += [indent, name, ': ', variable.value, "\n"]
            for v in variable.subProperties:
                self.printVariable(v, self.objects[v], indent + "  ")

    def printAll(self, xdb):
        self.generateStateTree(xdb)
        result = []
        for (name, variable) in self.objects.items():
            if '->' in name or '[' in name:
                continue
            self.printVariable(name, variable, "")
        return self.output

    def generateStateTree(self, xdb):
        for v in self.yetToVisit:
            if not xdb.isIgnored(v):
                variable = xdb.getVariable(v)
                if variable.address in self.visited.keys():
                    self.objects[v] = '(Reference to ' + self.visited[variable.address] + ')'
                else:
                    self.objects[v] = variable
                    self.visited[variable.address] = v
                    self.yetToVisit += variable.subProperties

# Variable object
# Describes a variable. It holds all the information retrieved from xDebug from a property_get call
# has the following properties:
#   - type
#   - value (If its a string or number, this is its value. Arrays or Objects have value array() or the classname)
#   - address
#   - subProperties (for arrays and objects this is a list of full names of the contents of the object)

class XDebugVariableObject:
    def __init__(self, variableXML):
        if len(variableXML.getElementsByTagName("property")) == 0:
            self.type = 'error'
            self.value = '(could not get property)'
            self.subProperties = []
            self.address = getFakeAddress()
            return
        self.type = variableXML.getElementsByTagName("property")[0].attributes["type"].value
        if variableXML.getElementsByTagName("property")[0].firstChild is None:
            rawValue = ''
        else:
            rawValue = variableXML.getElementsByTagName("property")[0].firstChild.nodeValue
        if self.type == 'array':
            self.value = 'array()'
        elif self.type == 'string':
            self.value = base64.decodestring(rawValue.encode()).decode('latin-1')
        elif self.type == 'object':
            self.value = variableXML.getElementsByTagName("property")[0].attributes["classname"].value + "()"
        else:
            self.value = rawValue

        self.address = None
        if len(variableXML.getElementsByTagName("property")) > 0:
            if "address" in variableXML.getElementsByTagName("property")[0].attributes:
                self.address = variableXML.getElementsByTagName("property")[0].attributes['address'].value

        self.subProperties = []
        if len(variableXML.getElementsByTagName("property")) > 1:
            subPropertyNames = variableXML.getElementsByTagName("property")[1:]
            for p in subPropertyNames:
                self.subProperties.append(getFullnameOfProperty(p))

class XdebugClient:
    def __init__(self):
        self.XDEBUG_PORT = 9000
        self.MAX_INT_LENGTH = 16
        self.LONGEST_XDEBUG_CHUNK = 4096
        self.transactionNumber = 0
        self.status = 'break'
        self.lastResponse = None
        self.config = None

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setblocking(True)
        s.bind(('', self.XDEBUG_PORT))
        s.listen(1)
        (self.socket, self.address) = s.accept()
    
    def setConfig(self, configFile):
        self.config = configFile

    def receive(self):
        messageLengthString = b''
        messageLengthString = self.socket.recv(self.MAX_INT_LENGTH)
        if len(messageLengthString) == 0:
            return ""
        positionOfNull = messageLengthString.index(b'\0')
        messageLength = int(messageLengthString[0:positionOfNull].decode())

        msg = messageLengthString[positionOfNull+1:]

        counter = len(msg)
        chunk = self.socket.recv(1)
        while chunk != b'\x00' and counter < messageLength+1:
            counter += 1
            msg += chunk
            chunk = self.socket.recv(1)
        return (msg).decode()

    def send(self, command):
        command = command.encode() + b" -i " + str(self.transactionNumber).encode() + b"\0"
        self.transactionNumber += 1
        msglen = len(command)
        sent = 0
        while sent < msglen:
            sent += self.socket.send(command[sent:])

    def execute(self, command):
        self.send(command)
        result = self.receive()
        return result

    def addBreakPoint(self, fileName, lineNumber):
        self.send("breakpoint_set -t line -f " + fileName + " -n " + str(lineNumber))
        self.receive()

    def run(self):
        self.send("run")
        response = self.receive()
        if response == "":
            return
        parsedmessage = xml.dom.minidom.parseString(response)
        self.status = parsedmessage.getElementsByTagName('response')[0].attributes['status'].value
        if len(parsedmessage.getElementsByTagNameNS('*','message')) == 0:
            self.currentFilename = ""
            self.currentLine = ""
        else:
            self.currentFilename = parsedmessage.getElementsByTagNameNS('*','message')[0].attributes['filename'].value
            self.currentLine = parsedmessage.getElementsByTagNameNS('*','message')[0].attributes['lineno'].value

    def getVariables(self):
        response = self.execute("context_get")
        parsedmessage = xml.dom.minidom.parseString(response)
        variables = parsedmessage.getElementsByTagName("property")
        result = []
        for p in variables:
            name = getFullnameOfProperty(p)
            if '->' in name or '[' in name:
                continue
            result.append(getFullnameOfProperty(p))
        return result

    def resetVisited(self):
        self.visited = {}

    def getVariable(self, variableName):
        response = self.execute("property_get -n " + variableName)
        parsedMessage = xml.dom.minidom.parseString(response)
        return XDebugVariableObject(parsedMessage)

    def getCurrentStatePrinted(self):
        variables = self.getVariables()
        variablePrinter = VariablePrinter(variables)
        result = variablePrinter.printAll(self)
        return "".join(result)

    def getCurrentIgnoredVariables(self):
        for f in self.config['files']:
            if self.currentFilename.endswith(f['remote']):
                if 'ignore_variables' not in f:
                    return []
                else:
                    return f['ignore_variables']
    
    def isIgnored(self, variableName):
        if self.config is None:
            return False
        currentFileIgnoredVariables = self.getCurrentIgnoredVariables()
        for v in currentFileIgnoredVariables:
            if variableName.startswith(v):
                return True
        return False

def getFileLine(filename, linenumber):
    if linenumber == 0:
        return ""
    linenumber = int(linenumber) - 1
    with open(filename, "r") as file:
        lines = file.read().splitlines()
    return lines[linenumber]

def getLocalEquivilentFile(targets, remoteFile):
    for t in targets:
        if remoteFile.endswith(t['remote']):
            return t['local']
    print ("no local for: " + remoteFile)

if __name__=="__main__":
    if len(sys.argv) < 2:
        print ("usage: " + sys.argv[0] + " {target list file}")
        exit()

    with open(sys.argv[1], "r") as file:
        config = json.loads(file.read())

    xdb = XdebugClient()
    xdb.setConfig(config)
    init = xdb.receive()

    for fileConfig in config['files']:
        fileToDebug = fileConfig['remote']
        if 'lines' in fileConfig:
            for line in fileConfig['lines']:
                xdb.addBreakPoint(fileToDebug, line)
        else:        
            lines = sum(1 for line in open(fileConfig['local']))
            for i in range(0,lines):
                xdb.addBreakPoint(fileToDebug, i)
    xdb.run()
    while xdb.status == 'break':
        print (xdb.currentFilename + ':' + str(xdb.currentLine) + ": " + getFileLine(getLocalEquivilentFile(config['files'], xdb.currentFilename), xdb.currentLine))
        print (xdb.getCurrentStatePrinted())
        xdb.run()
    xdb.run()

