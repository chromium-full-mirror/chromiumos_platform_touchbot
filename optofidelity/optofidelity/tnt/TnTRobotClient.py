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
from collections import namedtuple
import TnTClient
from TnTClient import TnTClientObject
from TnTClient import Request
from TnTEffectorClient import TnTEffectorClient
from TnTRackClient import TnTRackClient
from TnTFingerClient import TnTFingerClient

class TnTRobotClient(TnTClientObject):
    """
    This class implements TnT robot client to remote control TnT server.
    """
    PRIMARY_FINGER = 1
    SECONDARY_FINGER = 2

    def __init__(self, name, host=None, port=8000):
        super(TnTRobotClient, self).__init__('Robot', name, host, port)

    @property
    def position(self):
        """ Robot position """
        return self.get_position( )

    @property
    def speed(self):
        """ Robot speed """
        return self.get_speed( )

    @speed.setter
    def speed(self, speed):
        """ Set robot speed """
        self.set_speed(speed)

    @property
    def finger(self):
        """ Get finger associated to this robot """
        name = self._get_resource_name_by_role('FINGER')
        if name:
            return TnTFingerClient(name)
        return None

    def create_rack(self):
        r = Request() # empty = index
        return self.POST(r)

    def pick_effector(self, name, manual=None, debug=None):
        r = Request('Effector')
        r.set('effector', name)
        r.set('manual', manual)
        r.set('debug', debug)
        return self.PUT(r)

    def drop_effector(self, manual=False):
        if manual:
            self.clear_effector()
            return True
        r = Request('Effector')
        return self.DELETE(r)

    def clear_effector(self):
        """ Clear effector(s). This method can be called during robot reset
        to set clear initial state (no effectors mounted).
        """
        r = Request('Effector')
        r.set('manual', True)
        return self.DELETE(r)

    def effector(self):
        """ Get effector in use: 1=primary and 2=secondary"""
        Effector = namedtuple('Effector', ['primary', 'secondary'])
        primary   = None
        secondary = None

        response = self.GET(Request('Effector'))

        if response:
            if 'primary' in response:
                primary = TnTEffectorClient(response['primary']['name'], self.host, self.port)
            if 'secondary' in response:
                secondary = TnTEffectorClient(response['secondary']['name'], self.host, self.port)
        return Effector(primary, secondary)

    def effectors(self):
        """ Get a list of effectors (TnTEffectorClient) assigned to this robot,
        i.e., in the racks assigned to this robot.
        """
        effectors = {}
        for rack in self.racks().itervalues():
            effectors.update(rack.effectors())
        return effectors

    def racks(self):
        """ Get list of racks assigned to this robot """
        racks = {}
        for name in self.GET(Request('Racks')):
            racks[name] = TnTRackClient(name, self.host, self.port)
        return racks

    def max_effectors(self):
        """ Number of effectors that can be used at the same time """
        if self.has_two_finger():
            return 2
        else:
            return 1

    def has_two_finger(self):
        """ Does this configuration include a two finger mechanism """
        response = self.GET(Request('finger'))
        try:
            model = response['model']
        except AttributeError:
            pass
        else:
            return model == "TWO_FINGER"
        return False

    def can_pick_effector(self):
        """
        Can robot pick an effector:
            No:
                * There are no effectors available for this robot
                * The currently used effector is homeless (no home rack)
            Yes:
                * Otherwise yes
        """
        # Any effectors available?
        if len(self.effectors()) == 0:
            return False
        # Is currently used effector commutable?
        return True

    def go_home(self):
        r = Request('GoHome')
        self.POST(r)

    def get_speed(self):
        """ Get robot speed """
        return self.GET(Request('Speed'))['speed']

    def set_speed(self, speed):
        """ Set robot speed """
        r = Request('Speed')
        if type(speed) == int or type(speed) == float or type(speed) == str:
            r.set('speed', [speed])
        else:
            r.set('speed', speed)
        self.PUT(r)

    def move_x(self, distance, safe=True):
        """ Moves the robot X axis by the specified distance [mm] """
        r = Request('MoveX')
        r.set('distance', distance)
        r.set('safe', safe)
        return self.GET(r)
        #return (position["x"], position["y"], position["z"], position["r"])

    def move_y(self, distance, safe=True):
        """ Moves the robot Y axis by the specified distance [mm] """
        r = Request('MoveY')
        r.set('distance', distance)
        r.set('safe', safe)
        return self.GET(r)

    def move_z(self, distance, safe=True):
        """ Moves the robot Z axis by the specified distance [mm] """
        r = Request('MoveZ')
        r.set('distance', distance)
        r.set('safe', safe)
        return self.GET(r)
        #position = self.GET(r)
        #return (position["x"], position["y"], position["z"], position["r"])

    def move(self, x=None, y=None, z=None, u=None, speed=None, safe=True):
        """ Moves robot into a location using a linear motion """
        request = Request('Move')
        request.set('x', x)
        request.set('y', y)
        request.set('z', z)
        request.set('u', u)
        request.set('speed', speed)
        request.set('safe', safe)
        return self.GET(request)

    def jump(self, position, height = None):
        """ Moves robot into a position using a jump motion """
        r = Request('Jump')
        x = None
        y = None
        z = None
        u = None

        if len(position) == 2:
            x, y = position
        elif len(position) == 3:
            x, y, z = position
        else:
            x, y, z, u = position[:4]

        r.set('x', x)
        r.set('y', y)
        r.set('z', z)
        r.set('u', u)
        r.set('jumpHeight', height)
        position = self.GET(r)
        if 'u' in position:
            return (position["x"], position["y"], position["z"], position["u"])
        else:
            return (position["x"], position["y"], position["z"])

    def go(self, x=None, y=None, z=None, u=None, speed=None):
        """ Moves robot into the given position """
        request = Request('Go')
        request.set('x', x)
        request.set('y', y)
        request.set('z', z)
        request.set('u', u)
        request.set('speed', speed)
        return self.PUT(request)

    def tap(self, x=None, y=None, z=None, duration=None, speed=None, depth=None):
        """
        Perform a tap gesture to given position.
        Usage of 'depth' attribute is deprecated. Use target 'z' instead.
        """
        # Support for legacy attribute
        if depth:
            z = depth

        r = Request('Tap')
        r.set('x', x)
        r.set('y', y)
        r.set('z', z)
        r.set('duration', duration)
        r.set('speed', speed)
        return self.GET(r)

    def double_tap(self, depth, height):
        """
        Performs a double tap gesture to the given depth using given height
        between taps
        """
        r = Request('DoubleTap')
        r.set('depth', depth)
        r.set('height', height)
        return self.GET(r)

    def get_position(self, timeout=10.0):
        """ Returns the current robot position [X Y Z R] """
        r = Request('Position')
        r.set('timeout', timeout)
        try:
            pos = self.GET(r)
        except:
            raise
        else:
            return TnTClient.Point(pos['x'], pos['y'], pos['z'])
        #return (position["x"], position["y"], position["z"], position["r"])

    def get_status(self):
        """ Returns robot SW version """
        return self.GET(Request('Status'))

    def finger_go_home(self):
        """ Moves fingers to home position """
        return self.GET(Request('FingerGoHome'))

    def rotate_go_home(self):
        """ Rotates finger actuator to home position """
        return self.GET(Request('RotateGoHome'))

    def rotate(self, angle, relative=None):
        """
        Rotate robot end effector to given angle. The angle is measured from the
        robot home angle (by default). To rotate robot relatively to current
        angle use relative=True.
        """
        r = Request('Rotate')
        r.set('angle', angle)
        r.set('relative', relative)
        return self.PUT(r)

    def rotate_rel(self, angle):
        """
        Rotates finger actuator by the number of degrees from last position.
        """
        r = Request('RotateRel')
        r.set('angle', angle)
        return self.GET(r)

    def rotate_abs(self, angle):
        """
        Rotates finger actuator by the number of degrees from home position.
        """
        r = Request('RotateAbs')
        r.set('angle', angle)
        try:
            self.GET(r)
        except:
            raise

    def move_finger_rel(self, distance):
        """ Moves finger by the number of millimeters from last position. """
        r = Request('MoveFingerRel')
        r.set('distance', distance)
        return self.GET(r)

    def move_finger_abs(self, distance):
        """ Moves finger by a number of millimeters from home position. """
        r = Request('MoveFingerAbs')
        r.set('distance', distance)
        return self.GET(r)

    def get_finger_position(self):
        """ Returns TwoFinger current location coordinates. """
        return self.GET(Request('FingerPosition'))

    def finger_move_speed(self, speed):
        """ Sets finger movement speed in mm/s (Range 1 - 70 mm/s). """
        r = Request('FingerMoveSpeed')
        r.set('speed', speed)
        return self.GET(r)

    def finger_rotate_speed(self, speed):
        """ Sets finger rotation speed in deg/s (Range 5 - 180 deg/s). """
        r = Request('FingerRotateSpeed')
        r.set('speed', speed)
        return self.GET(r)

    def finger_rotate_move_rel(self, rotation, distance, speed):
        """ Rotates and moves finger from last position at the same time. """
        r = Request('FingerRotateMoveRel')
        r.set('rotation', rotation)
        r.set('distance', distance)
        r.set('speed', speed)
        return self.GET(r)

    def finger_rotate_move_abs(self, rotation, distance, speed):
        """ Rotates and moves finger from home position at the same time. """
        r = Request('FingerRotateMoveAbs')
        r.set('rotation', rotation)
        r.set('distance', distance)
        r.set('speed', speed)
        return self.GET(r)

    def sync_move(self, finger_angle, finger_distance, x, y, z, speed):
        """
        Moves the robot head and two finger actuator to absolute coordinates
        given as a parameter array.

        All movements are synchronized.

        Robot movement speed is used for the movement. Please note that speed
        limit may occur for the two finger movement, if long transitions are
        used. Error is returned before movement, if max speed limit is reached.
        """
        r = Request('SyncMove')
        r.set('angle', finger_angle)
        r.set('distance', finger_distance)
        r.set('x', x)
        r.set('y', y)
        r.set('z', z)
        r.set('speed', speed)
        return self.GET(r)

    def pinch_move(self, pinch_mm, speed, z):
        """
        Does the pinch move using two fingers. Fingers move amount of parameter
        "pinch_mm".

        Positive "pinch_mm" value moves fingers opposite directions and negative
        value to towards (zoom).
        """
        r = Request('PinchMove')
        r.set('distance', pinch_mm)
        r.set('speed', speed)
        r.set('z', z)
        return self.GET(r)

    # def go_to(self, name=None):
    #     """ Go to resource """
    #     r = Request('GoTo')
    #     r.set('name', name)
    #     return self.POST(r)