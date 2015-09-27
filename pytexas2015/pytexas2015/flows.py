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

import ip
from ryu import cfg
import logging
import six
from ryu.lib.mac import haddr_to_bin
from ryu.lib.packet import ether_types
from ryu.ofproto.nx_match import ClsRule


LOG = logging.getLogger(__name__)

flows_simple_opts = [
    cfg.IntOpt('drop_idle_timeout_sec', default=1000,
               help='Idle timeout for drop flow requests'),
    cfg.IntOpt('drop_hard_timeout_sec', default=120000,
               help='Hard timeout for drop flow requests'),
    cfg.IntOpt('northbound_ofport', default=1,
               help='Northbound bridge port'),
    cfg.IntOpt('southbound_ofport', default=2,
               help='Southbound bridge port')
]

cfg.CONF.register_opts(flows_simple_opts, 'flows')


def build_all(dp, route):
    north_ofport = cfg.CONF.flows.northbound_ofport
    south_ofport = cfg.CONF.flows.southbound_ofport

    LOG.info("Building flows for public ip:'%s', datapath id: %s, "
         "northbound ofport: %s, soundbound ofport: %s." %
         (route["public_ip"], dp.id, north_ofport, south_ofport))

    build_north_to_south(dp, route)
    build_south_to_north(dp, route)


def build_north_to_south(dp, route,
                         idle_timeout=0, hard_timeout=0):
    parser = dp.ofproto_parser
    public_ip = ip.ipv4_to_int(route['public_ip'])
    max_link = len(route['endpoints']) - 1
    north_ofport = cfg.CONF.flows.northbound_ofport
    south_ofport = cfg.CONF.flows.southbound_ofport

    for link, endpoint in enumerate(route['endpoints']):
        actions = [parser.NXActionResubmitTable(table=100)]
        match = build_rule(in_port=north_ofport, nw_dst=public_ip)
        add_flow(dp, actions=actions, match=match, cookie=public_ip,
                 idle_timeout=idle_timeout, hard_timeout=hard_timeout)

        # table 100
        bmf = build_multipath
        bmf(dp, public_ip, max_link,
            idle_timeout=idle_timeout, hard_timeout=hard_timeout)

        private_ip = ip.ipv4_to_int(endpoint['private_ip'])

        # table 110
        actions = [parser.OFPActionSetNwDst(private_ip),
                   parser.OFPActionOutput(port=south_ofport)]
        rule = build_rule(registers={1: link}, nw_dst=public_ip)
        add_flow(dp, table_id=110, actions=actions, match=rule,
                 cookie=public_ip, idle_timeout=idle_timeout,
                 hard_timeout=hard_timeout)


def build_multipath(dp, public_ip, max_links, idle_timeout=0, hard_timeout=0):
    ofproto = dp.ofproto
    parser = dp.ofproto_parser

    hash_f = ofproto.NX_HASH_FIELDS_SYMMETRIC_L4
    alg = ofproto.NX_BD_ALG_HRW
    reg = ofproto.nxm_nx_reg(1)
    actions = [parser.NXActionMultipath(hash_f, 0, alg, max_links, 0, 31, reg),
               parser.NXActionResubmitTable(table=110)]
    rule = build_rule(nw_dst=public_ip)
    add_flow(dp, table_id=100, actions=actions, match=rule, cookie=public_ip,
             idle_timeout=idle_timeout, hard_timeout=hard_timeout)


def build_south_to_north(dp, floating_ip,
                         drop_flows=False, idle_timeout=0, hard_timeout=0):
    parser = dp.ofproto_parser
    public_ip = ip.ipv4_to_int(floating_ip['public_ip'])
    north_ofport = cfg.CONF.flows.northbound_ofport
    south_ofport = cfg.CONF.flows.southbound_ofport

    for endpoint in floating_ip['endpoints']:
        private_ip = ip.ipv4_to_int(endpoint['private_ip'])
        rule = build_rule(in_port=south_ofport, nw_src=private_ip)

        actions = [parser.OFPActionSetNwSrc(public_ip),
                   parser.OFPActionOutput(port=north_ofport)]
        add_flow(dp, actions=actions, match=rule,
                 cookie=public_ip, idle_timeout=idle_timeout,
                 hard_timeout=hard_timeout)


def augment_command_with_table_id(command, table_id):
    return (int(table_id) << 8) + int(command)


def add_flow(datapath, table_id=0, match=None, actions=[],
             priority=None, idle_timeout=0, hard_timeout=0, cookie=0):
    ofproto = datapath.ofproto

    if priority is None:
        priority = ofproto.OFP_DEFAULT_PRIORITY

    cmd = augment_command_with_table_id(ofproto.OFPFC_ADD, table_id)
    datapath.send_flow_mod(rule=match, cookie=cookie, command=cmd,
                           actions=actions, idle_timeout=idle_timeout,
                           hard_timeout=hard_timeout, priority=priority)


def build_rule(in_port=None, nw_dst=None, nw_src=None, nw_proto=None,
               dl_dst=None, dl_src=None, registers=None, tun_id=None,
               dl_type=None):
    rule = ClsRule()

    if in_port is not None:
        rule.set_in_port(in_port)

    if dl_dst is not None:
        dl_dst = haddr_to_bin(dl_dst)
        rule.set_dl_dst(dl_dst)

    if dl_src is not None:
        dl_src = haddr_to_bin(dl_src)
        rule.set_dl_src(dl_src)

    if dl_type is None and (nw_dst is not None or nw_src is not None):
        dl_type = ether_types.ETH_TYPE_IP

    if dl_type is not None:
        rule.set_dl_type(dl_type)

    if nw_dst is not None:
        if isinstance(nw_dst, dict):
            nw_dst = nw_dst['destination']

        if isinstance(nw_dst, six.string_types):
            nw_dst = ip.ipv4_to_int(nw_dst)

        if isinstance(nw_dst, tuple):
            rule.set_nw_dst_masked(nw_dst[0], nw_dst[1])
        else:
            rule.set_nw_dst(nw_dst)

    if nw_src is not None:
        if isinstance(nw_src, dict):
            nw_src = nw_src['destination']

        if isinstance(nw_src, six.string_types):
            nw_src = ip.ipv4_to_int(nw_src)

        if isinstance(nw_src, tuple):
            rule.set_nw_src_masked(nw_src[0], nw_src[1])
        else:
            rule.set_nw_src(nw_src)

    if registers is not None:
        for k, v in registers.iteritems():
            rule.set_reg(k, v)

    if tun_id is not None:
        rule.set_tun_id(tun_id)

    if nw_proto is not None:
        rule.set_nw_proto(nw_proto)

    return rule
