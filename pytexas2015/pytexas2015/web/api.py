import json
import logging

from ryu.app.wsgi import ControllerBase
from ryu.app.wsgi import route
from webob import Response

from pytexas2015 import flows

LOG = logging.getLogger(__name__)

BASE_URI_V1_0 = '/v1.0'
CONTENT_TYPE_JSON = 'application/json'


class RouteController(ControllerBase):
    uri = '/routes'
    route_name = 'floating_ips'

    def __init__(self, req, link, data, **config):
        super(RouteController, self).__init__(req, link, data, **config)
        self.nw = data
        self.manager = data['manager']
        self.repo = data['repo']

    @route(route_name, uri + '/{public_ip}', methods=['GET'])
    def get(self, req, **kwargs):
        public_ip = kwargs.get('public_ip', None)

        route = self.repo.get_route(public_ip)
        body = self._to_json({'route': route})

        return Response(status=200, content_type=CONTENT_TYPE_JSON,
                        body=body)

    @route(route_name, uri, methods=['GET'])
    def lists(self, req, **kwargs):
        routes = self.repo.get_routes()
        body = self._to_json({'routes': routes})

        return Response(status=200, content_type=CONTENT_TYPE_JSON,
                        body=body)

    @route(route_name, uri, methods=['POST'])
    def create(self, req, **kwargs):
        try:
            content = req.json_body
            route = content["route"]
            self.manager.create_route(route)

            return Response(status=201, content_type=CONTENT_TYPE_JSON)
        except Exception as e:
            LOG.exception('Generic Exception')
            msg = self._to_json({"error": e.message})
            return Response(status=500, content_type=CONTENT_TYPE_JSON,
                            body=msg)

    @staticmethod
    def _to_json(obj):
        if isinstance(obj, list):
            return json.dumps(map(lambda f: f.to_dict(), obj),
                              cls=JSONObjectEncoder)

        return json.dumps(obj, cls=JSONObjectEncoder)


class JSONObjectEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (list, set)):
            return map(lambda o: self.serialize(o), obj)

        return self.serialize(obj)

    def serialize(self, obj):
        if hasattr(obj, "to_dict"):
            return obj.to_dict()

        return json.JSONEncoder.default(self, obj)