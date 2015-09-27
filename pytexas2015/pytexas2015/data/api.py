import logging

LOG = logging.getLogger(__name__)


class DataRepo(object):
    def __init__(self):
        self.routes = {}

    def get_routes(self):
        return self.routes.values()

    def get_public_ips(self):
        return self.routes.keys()

    def get_route(self, public_ip):
        return self.routes[public_ip]

    def set_route(self, route):
        self.routes[route['public_ip']] = route
