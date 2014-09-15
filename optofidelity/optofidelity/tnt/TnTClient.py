"""
The MIT License (MIT)

Copyright (c) 2013 OptoFidelity Oy

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
"""

import sys
import os
import re
import sys
import json
import ntpath
import socket
import urllib2
import requests

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from collections import namedtuple

Point = namedtuple('Point', ['x', 'y', 'z'])

class TnTClientObject(object):
    """ Super class for TnT clients objects """

    HTTP_API = "http://%s:%s/TnTAPI/%s/%s/"

    # Constructor
    def __init__(self, type='', name='', host='127.0.0.1', port=8000):
        self._host = host
        self._port = port
        self._collection = type.capitalize()
        if type.capitalize() != "Analyses":
            self._collection += 's'  # E.g., robots, duts, fingers
        self._type = type.upper()
        self._name = name
        #host = socket.gethostbyname(socket.gethostname())

        if type:
            if name:
                self._url = "http://%s:%s/TnTAPI/%s/%s/" % (host, port, self._collection, name)
            else:
                self._url = "http://%s:%s/TnTAPI/%s/" % (host, port, self._collection)
        else:
            self._url = "http://%s:%s/TnTAPI/" % (host, port)

    @property
    def name(self):
        return self._name

    @property
    def host(self):
        return self._host

    @property
    def port(self):
        return self._port

    @property
    def type(self):
        """  """
        return self._type

    @property
    def parameters(self):
        """ All DUT parameters as a dictinonary """
        self._parameters = self._load_parameters()
        return self._parameters

    @property
    def collection(self):
        return self._collection

    def GET(self, request):
        return self._send_request('GET', request)

    def POST(self, request, expect=200):
        return self._send_request('POST', request, expect)

    def PUT(self, request):
        return self._send_request('PUT', request)

    def DELETE(self, request):
        return self._send_request('DELETE', request)

    @property
    def response_headers(self):
        return self._response_headers

    def _send_request(self, method, request, expected_status_code=200):
        # Send the request
        if method == 'GET':
            url = "%s%s?%s" % (self._url, request.name, request.query)
            r = requests.get(url, headers=request.headers)
        elif method == 'POST':
            url = "%s%s" % (self._url, request.name)
            if request.files:
                r = requests.post(url, files=request.files, data=request.json)
            else:
                r = requests.post(url, data=request.body, headers=request.headers)
        elif method == 'PUT':
            url = "%s%s" % (self._url, request.name)
            r = requests.put(url, headers=request.headers, data=request.body)
        elif method == 'DELETE':
            url = "%s%s?%s" % (self._url, request.name, request.query)
            r = requests.delete(url, headers=request.headers)
        else:
            raise Exception('Unknown or unsupported HTTP method -- %s' % method)

        # Store headers
        self._response_headers = r.headers

        # Convert to JSON if JSON is expected (default)
        if request.accept == 'application/json':
            try:
                value = json.loads(r.content)
            except TypeError as vr:
                value = r.content
            except ValueError as vr:
                value = r.content
        # Otherwise just return the content as text
        else:
            value = r.content

        # Check responce
        if r.status_code != expected_status_code:
            message = ""
            if "message" in value:
                message = value['message']
            raise HttpException(r.status_code, message)
            #raise Exception("Server error: %s" % r.status_code)
        elif r.status_code == 201:
            # Read location header (201 == resource created succesfully)
            value = r.headers['Location']

        return value

    def post_file(self, uri, parameters={}, files={}):
        response = requests.post(uri, params=parameters, files=files)
        if response.status_code != 200:
            raise Exception("Server error: %s" % response.status_code)
        return response.text

    def _set_parameter(self, input):
        """
        Send DUT parameters to the server.
        param - parameters as dict
        """
        parameters = []
        for (key, value) in input.iteritems():
            parameter = {}
            parameter['name'] = str(key)
            parameter['value'] = str(value)
            if isinstance(value, int):
                parameter['datatype'] = "int"
            elif isinstance(value, float):
                parameter['datatype'] = "float"
            elif isinstance(value, tuple):
                parameter['datatype'] = "tuple"
            elif isinstance(value, list):
                parameter['datatype'] = "list"
            else:
                parameter['datatype'] = "string"
            parameters.append(parameter)

        r = Request( )
        r.set('parameters', parameters)
        self.POST(r)

    def _load_parameters(self):
        """ Load DUT parameters from the server """
        params = {}
        data = self.GET(Request())
        if 'parameters' in data:
            for dict in data['parameters']:
                if 'name' in dict and 'value' in dict:
                    key = dict['name']
                    type = dict['datatype']
                    if type == 'int':
                        params[key] = int(dict['value'])
                    elif type == 'long':
                        params[key] = long(dict['value'])
                    elif type == 'double':
                        params[key] = float(dict['value'])
                    elif type == 'float':
                        params[key] = float(dict['value'])
                    elif type == 'tuple':
                        params[key] = tuple(dict['value'])
                    else:
                        params[key] = dict['value']
        return params

    def _get_resource_name_by_role(self, role):
        r = self.GET(Request())
        name = None
        if r:
            resources = r['subresources']
            for r in resources:
                if 'role' in r and r['role'] == role:
                    name = r['name']
        return name

    def json(self):
        return self.GET(Request())

    def __repr__(self):
        return "%s(%r)" % (self.__class__.__name__, self.name)

    def __str__(self):
        return self.name

    def help(self):
        """ Help """
        import inspect

        class_name = self.__class__.__name__
        print "CLASS %s" % class_name
        print "\nMethods:"

        members = dir(self)
        for member in members:
            if str(member).startswith('_'):
                continue
            try:
                #print member

                #object =  eval('self.' + member)
                object = getattr(self, member)

                if not inspect.ismethod(object):
                    continue
                doc = eval('self.' + member + '.__doc__')
                if doc:
                    doc = doc.replace("       ", "  ")
                args = inspect.getargspec(object)[0]
                print "%s.%s(%s)" % (class_name, member, (", ".join(args[1:])))
                print "   %s" % doc
                print ""
            except Exception as e:
                print e


class TnTClient(TnTClientObject):
    """ TnT client
    Usage:
        client = TnTClient('127.0.0.1', 8000)
        robot = client.robot('MyRobotName')
        robot.some_method()
        ....
    """
    def __init__(self, host='127.0.0.1', port=8000):
        super(TnTClient, self).__init__(host=host, port=port)

    def robots(self):
        """ Get all robots as objects """
        robots = {}
        for name in self._resources("Robots"):
            robots[name] = self.robot(name)
        return robots

    def duts(self):
        """ Get all duts as objects """
        duts = {}
        for name in self._resources("Duts"):
            duts[name] = self.dut(name)
        return duts

    def analyses(self):
        """ Get all analyses as objects """
        analyses = {}
        for name in self._resources("Analyses"):
            analyses[name] = self.analysis(name)
        return analyses

    def effectors(self):
        """ Get all effectors as objects """
        effectors = {}
        for name in self._resources("Effectors"):
            effectors[name] = self.effector(name)
        return effectors

    def cameras(self):
        """ Get all cameras as objects """
        cameras = {}
        for name in self._resources("Cameras"):
            cameras[name] = self.camera(name)
        return cameras

    def robot(self, name):
        """ Get a robot object with the given name """
        from TnTRobotClient import TnTRobotClient
        return TnTRobotClient(name, self.host, self.port)

    def dut(self, name):
        """ Get a DUT object with the given name """
        from TnTDUTClient import TnTDUTClient
        return TnTDUTClient(name, self.host, self.port)

    def effector(self, name):
        """ Get an effector object with the given name """
        from TnTEffectorClient import TnTEffectorClient
        return TnTEffectorClient(name, self.host, self.port)
        
    def camera(self, name):
        """ Get an camera object with the given name """
        from TnTCameraClient import TnTCameraClient
        return TnTCameraClient(name, self.host, self.port)

    def analysis(self, name):
        """ Get an analysis object with the given name """
        from TnTAnalysisClient import TnTAnalysisClient
        return TnTAnalysisClient(name, self.host, self.port)

    def _resources(self, collection):
        names = []
        r = Request(collection)
        for r in self.GET(r):
            names.append(r['name'])
        return names


class Request(object):
    """ Request class wraps a HTTP request to be sent to the server """
    def __init__(self, name="", params={}, content_type='application/json'):
        self._params = {}
        self._headers = {}
        self._name = name
        self._files = None
        self.content_type = content_type
        self.accept = 'application/json'
        for key, value in params.items():
            self.set(key, value)

    @property
    def name(self):
        return self._name

    @property
    def headers(self):
        return self._headers

    @property
    def files(self):
        return self._files

    @files.setter
    def files(self, value):
        self.content_type = 'application/octet-stream'
        self._files = value

    @property
    def json(self):
        return self._params

    @property
    def body(self):
        return json.dumps(self.json)

    @property
    def query(self):
        return self._dict_to_query(self._params)

    @property
    def length(self):
        return len(self.body)

    @property
    def accept(self):
        return self.headers['Accept']

    @accept.setter
    def accept(self, value):
        """ ['text/plain', 'application/json'] """
        self.set_header('Accept', value)

    @property
    def content_type(self):
        return self.headers['Content-type']

    @content_type.setter
    def content_type(self, value):
        self.set_header('Content-type', value)

    def set_header(self, key, value):
        self.headers[key] = value

    def _dict_to_query(self, params, class_name=''):
        query = ''
        for key, value in params.items():
            if query:
                query += '&'
            if type(value) == dict:
                query += self._dict_to_query(value, class_name + key + '.')
            else:
                query += '%s%s=%s' % (class_name, key, value)
        return query

    def set(self, key, value, def_val=None):
        if value is None:
            if def_val is None:
                return
            value = def_val
        if '.' in key:
            keys = key.split('.')
            params = self._params
            i = 1
            for k in keys:
                if k in params:
                    params = params[k]
                else:
                    if len(keys) == i:
                        params[k] = value
                    else:
                        params[k] = {}
                        params = params[k]
                i += 1
        else:
            self._params[key] = value

    def upload(self, file):
        if not self._files:
            self._files = {}
        #self._files = {'file': (filename, open(filename, 'rb'))}
        self._files = {'file': file}


class HttpException(Exception):
    def __init__(self, code, message=None):
        if message is None:
            Exception.__init__(self)
        else:
            Exception.__init__(self, message)
        self.status_code = code

    @property
    def code(self):
        return self.status_code

    def __str__(self):
        if self.message:
            return "HTTP %i: %s" % (self.code, self.message)
        return "Http error %i" % self.code

