from TnTClient import TnTClientObject
from TnTClient import Request

class TnTCameraClient(TnTClientObject):

    def __init__(self, name, host=None, port=8000):
        super(TnTCameraClient, self).__init__('Camera', name, host, port)
        self._parameters    = None
        self._sub_resources = None
        self._model = None

        properties = self.GET(Request())

        # The following properties are consider as static
        if 'model' in properties:
            self._model = properties['model']

    @property
    def model(self):
        return self._model

    def pause(self):
        """
        """
        return self.PUT(Request('Pause'))

    def resume(self):
        """
        """
        return self.PUT(Request('Resume'))
