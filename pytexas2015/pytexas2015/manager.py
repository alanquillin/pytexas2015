# Copyright (c) 2014 Rackspace Hosting
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from web import api as web_api
from data.api import DataRepo
import flows
from ryu.app.wsgi import WSGIApplication
from ryu.base import app_manager
from ryu import cfg
from ryu.controller.handler import MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.controller import ofp_event
from ryu.lib.packet import ipv4
from ryu.lib.packet import packet
from ryu.ofproto import ofproto_v1_0

import logging


LOG = logging.getLogger(__name__)


class Manager(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_0.OFP_VERSION]
    _CONTEXTS = {'wsgi': WSGIApplication}
    _data_paths = {}

    def __init__(self, *args, **kwargs):
        super(Manager, self).__init__(*args, **kwargs)

        # Start the REST web api
        wsgi = kwargs['wsgi']
        self.repo = DataRepo()
        cntlr_data = {'manager': self, 'repo': self.repo}
        wsgi.register(web_api.RouteController, cntlr_data)

        print "hey bro!"

    @set_ev_cls(ofp_event.EventOFPStateChange, MAIN_DISPATCHER)
    def new_connection(self, ev):
        dp = ev.datapath

        if dp.id not in self._data_paths:
            self._data_paths[dp.id] = dp

        self._enable_controller_to_set_flow_table_id(dp)

        LOG.info('Bridge connection established: |datapath id: %s|' % dp.id)

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def handle_packet(self, ev):
        msg = ev.msg
        dp = msg.datapath
        dpid = dp.id
        dp_info = self._data_paths[dp.id]

        pkt = packet.Packet(msg.data)
        if dp_info is None:
            LOG.error('Unexpected packet from an unknown datapath. '
                      'Datapath id: %s, Packet: %s' % dpid, pkt)

        ip = pkt.get_protocol(ipv4.ipv4)

        if ip is None:
            LOG.debug('Non layer 3 message received, ignoring. '
                      'Packet: %s' % pkt)
            return

        if ip.dst in self.repo.get_public_ips():
            route = self.repo.get_route(ip.dst)

            LOG.info('Recieved packet for ip address %s.  '
                     'Attempting to build the flows' % route['public_ip'])
            flows.build_all(dp_info, route)
        else:
            LOG.info('Unknown ip address %s: blocking temporarily.' % ip.dst)

    def create_route(self, route):
        self.repo.set_route(route)
        for (dp_id, dp) in self._data_paths.iteritems():
            flows.build_all(dp, route)

    @staticmethod
    def _enable_controller_to_set_flow_table_id(dp):
        """Sends the command to the bridge to allow the table id to be set for
        the flow.  By default, for OpenFlow v1.0 with Nicira Extensions, the
        bridges do not allow the table to be set.  This flag/feature needs to
        be turned on explicitly.

        :param dp: Datapath object of the target bridge
        """
        parser = dp.ofproto_parser

        msg = parser.NXTFlowModTableId(dp, 1)

        dp.send_msg(msg)