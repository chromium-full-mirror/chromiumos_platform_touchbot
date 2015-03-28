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

import os
import math
import ntpath
import tempfile
from os.path import expanduser # user home
import TnTClient
from TnTClient import TnTClientObject
from TnTClient import Request
import urllib
from TnTCameraClient import TnTCameraClient

class TnTDUTClient(TnTClientObject):
    """
    This class implements TnT DUT client to remote control TnT server.
    """
    def __init__(self, name, host=None, port=8000, **kwds):
        super(TnTDUTClient, self).__init__('Dut', name, host, port)
        self._parameters    = None
        self._sub_resources = None

    @property
    def panel_width(self):
        """ Width of a DUT screen (DUT x-axis) """
        return self.parameters.get('panel_width')

    @property
    def ppmm(self):
        """ Pixels per millimeter in camera image"""
        return self.parameters.get('ppmm')

    @property
    def panel_height(self):
        """ Height of a DUT screen (DUT y-axis) """
        return self.parameters.get('panel_height')

    @property
    def panel_distance(self):
        """ Distance of DUT screen from robot topmost position (robot z=0) """
        return self.parameters.get('panel_distance')

    @panel_distance.setter
    def panel_distance(self, distance):
        """ Getter for PanelDistance """
        self._set_parameter({'panel_distance': distance})

    @property
    def panel_angle(self):
        """
        Angle of DUT screen compared to robot coordinate system [degrees].
            0   -- Dut coordinates equals to robot coordinates
            90  -- Dut right side goes along with the robot x -axis
            180 -- Dut top is against robot x axis
            270 -- Dut left side goes along with the robot x -axis
        """
        top_left = self.top_left_position()
        bottom_left = self.bottom_left_position()

        delta_y = bottom_left.get('y') - top_left.get('y')
        delta_x = bottom_left.get('x') - top_left.get('x')

        # Debug data
        # 0 dec => 0.7
        # delta_y = 80.5
        # delta_x = -1

        # 180 dec => 179
        # delta_y = -80.5
        # delta_x = 1

        # 270 dec astetta
        # delta_y = -1
        # delta_x = -80.5
        if delta_x == 0:
            if delta_y > 0:
                angle = 0
            else:
                angle = 180
        else:
            k = delta_y / delta_x
            radians = math.atan2(delta_y, delta_x)
            if delta_x < 0 < delta_y:
                angle = (360 + 90) - math.degrees(radians)
            else:
                angle = 90 - math.degrees(radians)
        return angle

    @property
    def top_left(self):
        """ Position of DUT top left corner (x,y,z) """
        return (0, 0, 0)

    @property
    def top_right(self):
        """ Position of DUT top right corner (x,y,z) """
        return (self.panel_width, 0, 0)

    @property
    def bottom_left(self):
        """ Position of DUT bottom left corner (x,y,z) """
        return (0, self.panel_height, 0)

    @property
    def bottom_right(self):
        """ Position of DUT bottom right corner """
        return (self.panel_width, self.panel_height, 0)

    @property
    def subresources(self):
        """ DUT subresources as a dictionary """
        if not self._sub_resources:
            self._sub_resources = self._load_sub_resources()
        return self._sub_resources

    @property
    def camera(self):
        """ Get a camera associated with the DUT """
        name = self._get_resource_name_by_role('CAMERA_FINGER')
        if name:
            return TnTCameraClient(name)
        return None


    @camera.setter
    def camera(self, value):
        """ Set a camera associated with the DUT """
        if not value:
            self.DELETE(Request('Camera'))
        elif isinstance(value, (str, unicode)): # Or basestring
            r = Request('Camera')
            r.set('name', value)
            self.PUT(r)
        elif isinstance(value, TnTCameraClient):
            r = Request('Camera')
            r.set('name', value.name)
            self.PUT(r)

    def _load_sub_resources(self):
        subs = {}
        data = self.GET(Request())
        if 'subresources' in data:
            for dict in data['subresources']:
                if 'type' in dict:
                    key = dict['type']
                    subs[key] = dict
        return subs

    def _load_parameters(self):
        """ Load DUT parameters from the server """
        params = {}
        data = self.GET(Request(""))
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

    def get_position(self, timeout=10.0):
        """ Returns the current robot position in DUT coordinates """
        r = Request('Position')
        try:
            pos = self.GET(r)
        except:
            raise
        else:
            return TnTClient.Point(pos['x'], pos['y'], pos['z'])

    def tap(self, x=None, y=None, angle=None, duration=None, clearance=None):
        """
        Perform a tap gesture on a given x and y coordinates. If x and y
        coordinates are not defined, the gesture is performed at the current
        finger position.

        Duration parameter is used to defined how long the touch event
        takes at least in milliseconds.

        Clearance parameter can be used to make the gesture happen at a given
        distance above the DUT surface. For example, if the clearance value
        is two, the gesture is performed two millimeters above the DUT surface.

        Returns:
            x -- x after gesture
            y -- y after gesture
            z -- z after gesture
        """
        r = Request('Tap')
        r.set('x', x)
        r.set('y', y)
        r.set('angle', angle)
        r.set('duration', duration)
        r.set('clearance', clearance)
        return self.POST(r, async=True)

    def double_tap(self, x=None, y=None, duration=None, interval=None, clearance=None, lift=None):
        """
        Perform a double tap gesture on a given x and y coordinates. If x and y
        coordinates are not defined, the gesture is performed at the current
        finger position.

        Duration parameter defines how long the touch event takes at least time
        in milliseconds. By default, the gesture is executed without an additional
        delay.

        Interval parameter defines the time interval between the taps in
        milliseconds. By default, there is no additional delay between taps.

        Clearance parameter can be used to make the gesture happen at a given
        distance above the DUT surface. For example, if the clearance value
        is two, the gesture is performed two millimeters above the DUT surface.

        Lift is how many millimeters finger(s) is lift up between the taps
        (measured from the DUT surface or given vertical offset i.e. clearance).
        Defaults to DUT clear distance.

        Returns:
            x -- x after gesture
            y -- y after gesture
            z -- z after gesture
        """
        r = Request('DoubleTap')
        r.set('x', x)
        r.set('y', y)
        r.set('duration', duration)
        r.set('interval', interval)
        r.set('clearance', clearance)
        r.set('lift', lift)
        return self.POST(r, async=True)

    def multi_tap(self, points=[], duration=None, interval=None, clearance=None):
        """
            points: [
                [1,1],
                [2,2],
                [3,3]
                ]
        """
        # points = [
        #     [0,0],
        #     [10,10],
        #     [20,20],
        #     [30,30]
        #     ]
        r = Request('MultiTap')
        r.set('points', points)
        r.set('duration', duration)
        r.set('interval', interval)
        r.set('clearance', clearance)
        return self.POST(r, async=True)

    def toss(self, from_x, from_y, to_x, to_y, clearance=None):
        r = Request('Toss')
        r.set('from.x', from_x)
        r.set('from.y', from_y)
        r.set('to.x', to_x)
        r.set('to.y', to_y)
        r.set('clearance', clearance)
        return self.POST(r, async=True)

    def drag(self, from_x=None, from_y=None, to_x=None, to_y=None, angle=None, begin_hold_time=0, end_hold_time=0, clearance=None, speed=None):
        """
        Perform a drag gesture from x1 and y1 coordinates to x2 and y2
        coordinates.

        Clearance parameter can be used to make the gesture happen at a given
        distance above the DUT surface. For example, if the clearance value
        is two, the gesture is performed two millimeters above the DUT surface.
        """
        r = Request('Drag')
        r.set('from.x', from_x)
        r.set('from.y', from_y)
        r.set('to.x', to_x)
        r.set('to.y', to_y)
        r.set('angle', angle)
        r.set('clearance', clearance)
        r.set('speed', speed)
        r.set('beginHoldTime', begin_hold_time)
        r.set('endHoldTime', end_hold_time)
        return self.POST(r, async=True)

    def drag_and_hold(self, from_x=None, from_y=None, to_x=None, to_y=None, angle=None, duration=None, clearance=None):
        """ Similar like drag, but user has defined delay before and after
            contact is moved.
            from_x -- Drag from x
            from_y -- Drag from y
            to_x -- Drag to x
            to_y -- Drag to y
            duration -- Hold time in milliseconds.
        """
        r = Request('DragAndHold')
        r.set('from.x', from_x)
        r.set('from.y', from_y)
        r.set('to.x', to_x)
        r.set('to.y', to_y)
        r.set('angle', angle)
        r.set('duration', duration)
        r.set('clearance', clearance)
        return self.POST(r, async=True)

    def swipe(self, from_x=None, from_y=None, to_x=None, to_y=None, angle=None, clearance=None, radius=6.0):
        """
        Perform a swipe gesture from x1 and y1 coordinates to x2 and y2
        coordinates.

        Clearance parameter can be used to make the gesture happen at a given
        distance above the DUT surface. For example, if the clearance value
        is two, the gesture is performed two millimeters above the DUT surface.
        """
        r = Request('Swipe')
        r.set('from.x', from_x)
        r.set('from.y', from_y)
        r.set('to.x', to_x)
        r.set('to.y', to_y)
        r.set('angle', angle)
        r.set('clearance', clearance)
        r.set('radius', radius)
        return self.POST(r, async=True)

    def swipe_right(self, length=1.0, clearance=None, radius=6.0):
        """
        Perform a horizontal swipe from left to right. Vertically the
        swipe gesture is executed in the middle of the DUT screen.

        Length parameter defines a relative length of the gesture. 1.0 equals
        to the full width of a DUT (default).

        Clearance parameter can be used to make the gesture happen at a given
        distance above the DUT surface. For example, if the clearance value
        is two, the gesture is performed two millimeters above the DUT surface.
        """
        return self._do_swipe_towards("RIGHT", length, clearance=clearance, radius=radius)

    def swipe_left(self, length=1.0, clearance=None, radius=6.0):
        """
        Perform a horizontal swipe from right to left. Vertically the
        swipe gesture is executed in the middle of the DUT screen.

        Length parameter defines a relative length of the gesture. 1.0 equals
        to the full width of a DUT (default).

        Clearance parameter can be used to make the gesture happen at a given
        distance above the DUT surface. For example, if the clearance value
        is two, the gesture is performed two millimeters above the DUT surface.
        """
        return self._do_swipe_towards("LEFT", length, radius=radius)

    def swipe_down(self, length=1.0, clearance=None, radius=6.0):
        """
        Perform a horizontal swipe from top to bottom of the DUT. Horizontally
        the gesture is executed in the middle of the DUT screen.

        Length parameter defines a relative length of the gesture. 1.0 equals
        to the full height of a DUT (default).

        Clearance parameter can be used to make the gesture happen at a given
        distance above the DUT surface. For example, if the clearance value
        is two, the gesture is performed two millimeters above the DUT surface.
        """
        return self._do_swipe_towards("DOWN", length, clearance=clearance, radius=radius)

    def swipe_up(self, length=1.0, clearance=None, radius=6.0):
        """
        Perform a horizontal swipe from bottom to top of the DUT. Horizontally
        the gesture is executed in the middle of the DUT screen.

        Length parameter defines a relative length of the gesture. 1.0 equals
        to the full height of a DUT (default).

        Clearance parameter can be used to make the gesture happen at a given
        distance above the DUT surface. For example, if the clearance value
        is two, the gesture is performed two millimeters above the DUT surface.
        """
        return self._do_swipe_towards("UP", length, clearance=clearance, radius=radius)

    def _do_swipe_towards(self, direction, length=1.0, clearance=None, radius=1.0):
        """
        Perform a swipe towards a given direction. Unpack the
        parameters and call driver for the action.
        Return the position within in DUT coordinates after the gesture.
        """
        # Toward LEFT or RIGHT side of the device
        if direction == 'LEFT' or direction == 'RIGHT':
            y1 = y2 = self.panel_height / 2
            offset = (self.panel_width * (1.0 - length)) / 2
            if direction == 'RIGHT':
                x1 = offset
                x2 = self.panel_width - offset
            else:
                x1 = self.panel_width - offset
                x2   = offset
        # Towards TOP or BOTTOM of the device
        elif direction == 'UP' or direction == 'DOWN':
            x1 = x2 = self.panel_width / 2
            offset = (self.panel_height * (1.0 - length)) / 2
            if direction == 'DOWN':
                y1 = offset
                y2 = self.panel_height - offset
            else:
                y1 = self.panel_height - offset
                y2 = offset

        return self.swipe(x1, y1, x2, y2, clearance, radius)

    def press(self, x=None, y=None, duration=1000, clearance=None):
        """ Perform a 'press' gesture """
        r = Request('Press')
        r.set('x', x)
        r.set('y', y)
        r.set('duration', duration)
        r.set('clearance', clearance)
        return self.GET(r)

    def pinch(self, x=None, y=None, angle=None, distance=None, threshold=None, speed=None, clearance=None):
        """ Perform a pinch gesture on a given position """
        r = Request('Pinch')
        r.set('x', x)
        r.set('y', y)
        r.set('angle', angle)
        r.set('distance', distance)
        r.set('threshold', threshold)
        r.set('speed', speed)
        r.set('clearance', clearance)
        return self.POST(r, async=True)

    def zoom(self, x=None, y=None, angle=None, distance=None, offset=None, speed=None, clearance=None):
        """ Perform a zoom gesture on a given position """
        r = Request('Zoom')
        r.set('x', x)
        r.set('y', y)
        r.set('angle', angle)
        r.set('distance', distance)
        r.set('offset', offset)
        r.set('speed', speed)
        r.set('clearance', clearance)
        return self.POST(r, async=True)

    def top_left_position(self):
        """
        DUT top left position in robot coordinates (x,y,z).

        Returns:
            x -- X -coordinate
            y -- Y -coordinate
            z -- Z -coordinate
        """
        return self.GET(Request('TopLeftPosition'))

    def top_right_position(self):
        """
        DUT top right position in robot coordinates (x,y,z).

        Returns:
            x -- X -coordinate
            y -- Y -coordinate
            z -- Z -coordinate
        """
        return self.GET(Request('TopRightPosition'))

    def bottom_right_position(self):
        """
        DUT bottom right position in robot coordinates (x,y,z).

        Returns:
            x -- X -coordinate
            y -- Y -coordinate
            z -- Z -coordinate
        """
        return self.GET(Request('BottomRightPosition'))

    def bottom_left_position(self):
        """
        DUT bottom left position in robot coordinates (x,y,z).

        Returns:
            x -- X -coordinate
            y -- Y -coordinate
            z -- Z -coordinate
        """
        return self.GET(Request('BottomLeftPosition'))

    def move_x(self, distance=1.0):
        """
        Move robot along DUT x axis. Distance is x movement in millimeters.

        """
        r = Request('MoveX', {'distance': distance})
        return self.GET(r, async=True)

    def move_y(self, distance=1.0):
        """
        Move robot along DUT y axis. Distance is y movement in millimeters.
        """
        r = Request('MoveY', {'distance': distance})
        return self.GET(r, async=True)

    def move_z(self, distance=1.0):
        """
        Move robot along DUT z axis by a number of millimeters given as a
        parameter. Distance is z movement in millimeters. Positive value moves
        finger further away and negative value towards the DUT surface.
        """
        r = Request('MoveZ', {'distance': distance})
        return self.GET(r, async=True)

    def move(self, x=None, y=None, z=None, u=None, speed=None):
        """
        Move robot to the given x, y, and z coordinates within DUT coordinates.
        Top left coordinates of the DUT are x=0, y=0 and z=0.

        Examples:
            dut.move(x, y)
            dut.move(x, y, z)
        """
        r = Request('Move')
        r.set('x', x)
        r.set('y', y)
        r.set('z', z)
        r.set('u', u)
        r.set('speed', speed)
        return self.PUT(r, async=True)

    def jump(self, x=None, y=None, z=None, height=None, speed=None):
        """
        Move robot to the given x, y and z coordinates by first raising
        the robot head to a jump height.

        Jump height can be also given as a parameter, which is calculated from
        the DUT surface (0 = DUT surface).

        Top left coordinates of the DUT are x=0, y=0 and z=0.
        """
        r = Request('Jump')
        r.set('x', x)
        r.set('y', y)
        r.set('z', z)
        r.set('height', height)
        r.set('speed', speed)
        return self.GET(r, async=True)

    def go(self, x=None, y=None, z=None, u=None, speed=None):
        """
        Move robot to the given x, y, and z coordinates within DUT coordinates.
        Top left coordinates of the DUT are x=0, y=0 and z=0.

        Examples:
            dut.go(x, y)
            dut.go(x, y, z)
        """
        r = Request('Go')
        r.set('x', x)
        r.set('y', y)
        r.set('z', z)
        r.set('u', u)
        r.set('speed', speed)
        return self.PUT(r, async=True)

    def find_objects(self, filename, min_score=None, crop_left=None,
        crop_upper=None, crop_right=None, crop_lower=None, crop_unit=None):
        """
        Find an object model (.shm) from the currently visible portion of the screen.

        Parameters:
            filename -- File containing object model
            min_score -- Minimum accepted confidence score of result [0.0 .. 1.0] (optional)
            crop_left -- Left coordinate for cropping rectangle
            crop_upper -- Upper coordinate for cropping rectangle
            crop_right -- Right coordinate for cropping rectangle
            crop_lower -- Lower coordinate for cropping rectangle
            crop_unit -- Unit of crop coordinates (per/mm/pix)

        Return:
            Response body:
                success -- Any matches found [True | False]
                screenshot -- Address of the screenshot
                results -- Array of Result objects

            Result object:
                score -- Match score [0.0 .. 1.0]
                topLeftX -- Bounding box top left x coordinate
                topLeftY -- Bounding box top left x coordinate
                bottomRightX -- Bounding box bottom right x coordinate
                bottomRightY -- Bounding box bottom right y coordinate
                shape -- Name of the shape file

            Example:
            {
                "success": True
                "screenshot": "localhost:8000/TnTAPI/Screenshots/1.jpg"
                "results":
                [{
                    "topLeftX": 4.21,
                    "topLeftY": 2.37,
                    "bottomRightX": 6.23,
                    "bottomRightX": 3.54,
                    "shape": "shapeName.shm",
                    "score": 0.781
                }]
            }
        """
        r = Request('FindObjects', content_type='application/octet-stream')
        r.upload(open(filename, "rb"))
        r.set('minScore', min_score)
        r.set('cropLeft', crop_left)
        r.set('cropUpper', crop_upper)
        r.set('cropRight', crop_right)
        r.set('cropLower', crop_lower)
        r.set('cropUnit', crop_unit)
        return self.POST(r)

    def screenshot(self, filename=None):
        """
        Take a screenshot.

        Parameters:
            filename -- Output filename (optional)
        """
        r = Request('Screenshot')
        response = self.GET(r)
        url = response.get('url')

        if not filename:
            # No filename, use same filename as server does.
            _, filename = ntpath.split(url)
            # Save file into user home directory under pictures folder
            filename = "%s/Pictures/%s" % (expanduser("~"), filename)

        try:
            # Download the image file from the server
            urllib.urlretrieve(url, filename)
        except:
            # Any exception?
            raise
        else:
            return filename

    def read_text(self, language='English'):
        """
        Read all text within the visible portion of the DUT screen.

        Parameters:
            language -- OCR language
        """
        r = Request('SearchText')
        r.set('language', language)
        return self.POST(r)

    def search_text(self, pattern="", regexp=False, language='English', min_score=1.0, case_sensitive=True,
        crop_left=None, crop_upper=None, crop_right=None, crop_lower=None, crop_unit=None):
        """
        Search text pattern from the visible portion of the DUT screen..

        Parameters:
            pattern -- Text or pattern to find. Search all by default
            regexp -- Use pattern as a regexp. [True | False (default)]
            language -- OCR language. [English (default)|Finnish]
            score -- Minimum score (confidence value). 0.0 - 1.0. Default is 1.0
                     Value over 0.6 means the sequences are close matches
            case_sensitive -- Should the comparision be done case sensitive or not. [True (default) | False]
            crop_left -- Left coordinate for cropping rectangle
            crop_upper -- Upper coordinate for cropping rectangle
            crop_right -- Right coordinate for cropping rectangle
            crop_lower -- Lower coordinate for cropping rectangle
            crop_unit -- Unit of crop coordinates (per/mm/pix)
        """
        r = Request('SearchText')
        r.set('language', language)
        r.set('pattern', pattern)
        r.set('regexp', str(regexp))
        r.set('minScore', min_score)
        r.set('caseSensitive', str(case_sensitive))
        r.set('cropLeft', crop_left)
        r.set('cropUpper', crop_upper)
        r.set('cropRight', crop_right)
        r.set('cropLower', crop_lower)
        r.set('cropUnit', crop_unit)
        return self.POST(r)

    def start_data_acquisition(self, averaging=1, timeout=600):
        """
        Start data acquisition from sensors connected to the DUT

        Parameters:
            averaging -- How many samples are averaged before writing
            timeout   -- Maximum duration of the measurement in seconds. Default 600s (10min)
        """
        r = Request('StartDataAcquisition')
        r.set('averaging', averaging)
        r.set('timeout', timeout)
        timestamp = self.POST(r)['timestamp']
        return "Started at timestamp %.2f" % timestamp

    def stop_data_acquisition(self):
        """
        Stop data acquisition from sensors connected to the DUT
        and return measured data

        Parameters:
            None
        Returns:
            Measured data in format [[timestamp1, value1], [[timestamp2, value2]]
        """
        r = Request('StopDataAcquisition')
        temp_dir = tempfile.gettempdir()

        uri = self.GET(r)['url']
        url, file = ntpath.split(uri)
        filename = os.path.join(temp_dir, file)

        r = Request(uri)
        data = self.GET(r)
        with open(filename, 'wb') as f:
            f.write(data)
        return filename

    def record(self, source=None, message=None):
        """
        Record a video within this DUT context. If the request is executed
        succesfully method returns a link to the video resource.

        Parameter:
            message -- additional message to describe the recording
            source -- source attribute can be used to select video source.
        """
        r = Request('Record')
        r.set('source', source)
        r.set('message', message)
        return self.POST(r, 201)

    def records(self):
        """
        """
        return self.GET(Request('Records'))
