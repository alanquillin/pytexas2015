#!/usr/bin/env python

import os

from mininet.net import Mininet
from mininet.node import OVSSwitch, RemoteController
from mininet.topo import Topo
from mininet.log import setLogLevel
from mininet.cli import CLI
from mininet.util import dumpNetConnections

setLogLevel('info')
# setLogLevel('debug')    # For diagnostics


class TestTopo(Topo):

    def __init__(self):
        super(TestTopo, self).__init__()

        # add hosts
        h_public1 = self.addHost('h_public1', ip='10.0.0.1/24',
                                mac='00:00:00:00:00:01')
        h_public2 = self.addHost('h_public2', ip='10.0.0.2/24',
                                mac='00:00:00:00:02:01')
        h_vm1 = self.addHost('h_vm1', ip='172.16.0.1/24',
                             mac='00:00:00:00:00:02')
        h_vm2 = self.addHost('h_vm2', ip='172.16.0.2/24',
                             mac='00:00:00:00:00:03')
        h_vm3 = self.addHost('h_vm3', ip='172.16.0.3/24',
                             mac='00:00:00:00:00:04')
        h_vm4 = self.addHost('h_vm4', ip='172.16.0.4/24',
                             mac='00:00:00:00:00:05')

        # add switched
        s_north = self.addSwitch('northbound', dpid='0000000000000095')
        self.addSwitch('main', dpid='0000000000000096')
        s_south = self.addSwitch('southbound', dpid='0000000000000099')

        # build links
        self.addLink(h_public1, s_north)
        self.addLink(h_public2, s_north)
        self.addLink(h_vm1, s_south)
        self.addLink(h_vm2, s_south)
        self.addLink(h_vm3, s_south)
        self.addLink(h_vm4, s_south)


if __name__ == "__main__":
    topo = TestTopo()
    net = Mininet(topo=topo, switch=OVSSwitch, build=False)

    r_controller = net.addController('ryu', controller=RemoteController,
                                     ip='127.0.0.1')
    net.build()

    net.start()

    hp1 = net.getNodeByName('h_public1')
    hp1.cmdPrint('route add default gw 10.0.0.254 h_public1-eth0')
    hp1.setARP(ip='10.0.0.254', mac='00:00:00:00:11:11')

    hp2 = net.getNodeByName('h_public2')
    hp2.cmdPrint('route add default gw 10.0.0.254 h_public2-eth0')
    hp2.setARP(ip='10.0.0.254', mac='00:00:00:00:11:12')

    h1 = net.getNodeByName('h_vm1')
    h1.cmdPrint('route add default gw 172.16.0.254 h_vm1-eth0')
    h1.setARP(ip='172.16.0.254', mac='00:00:00:00:22:22')
    h1.cmdPrint('cd vm1 && sudo python -m SimpleHTTPServer 80 &')

    h2 = net.getNodeByName('h_vm2')
    h2.cmdPrint('route add default gw 172.16.0.254 h_vm2-eth0')
    h2.setARP(ip='172.16.0.254', mac='00:00:00:00:33:33')
    h2.cmdPrint('cd vm2 && sudo python -m SimpleHTTPServer 80 &')

    h3 = net.getNodeByName('h_vm3')
    h3.cmdPrint('route add default gw 172.16.0.254 h_vm3-eth0')
    h3.setARP(ip='172.16.0.254', mac='00:00:00:00:44:44')
    h3.cmdPrint('cd vm3 && sudo python -m SimpleHTTPServer 80 &')

    h4 = net.getNodeByName('h_vm4')
    h4.cmdPrint('route add default gw 172.16.0.254 h_vm4-eth0')
    h4.setARP(ip='172.16.0.254', mac='00:00:00:00:55:55')
    h4.cmdPrint('cd vm4 && sudo python -m SimpleHTTPServer 80 &')

    os.system("ovs-vsctl del-controller northbound")
    os.system("ovs-vsctl del-controller southbound")

    os.system("sudo ovs-vsctl add-port main to_northbound -- "
              "set interface to_northbound type=patch ofport_request=1 "
              "option:peer=to_main -- "
              "add-port northbound to_main -- "
              "set interface to_main type=patch "
              "option:peer=to_northbound")
    os.system("sudo ovs-vsctl add-port main to_southbound -- "
              "set interface to_southbound type=patch ofport_request=2 "
              "option:peer=to_main2 -- "
              "add-port southbound to_main2 -- "
              "set interface to_main2 type=patch "
              "option:peer=to_southbound")

    os.system("ovs-ofctl add-flows northbound northbound_flows.txt")
    os.system("ovs-ofctl add-flows southbound southbound_flows.txt")

    dumpNetConnections(net)

    CLI(net)
    net.stop()