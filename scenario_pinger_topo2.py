# need mininet.net because used in mininet.link
from mininet.net import Mininet
from mininet.link import Link
import mn_vlanhost
import scenario_pinger


class ScenarioPingerTopo2(scenario_pinger.ScenarioPingerBase):
    def __init__(self, testdefs_file_name):
        super(ScenarioPingerTopo2, self).__init__(testdefs_file_name)

    @staticmethod
    def _set_default_route_to_host(host, ip):
        cmd = "ip route add via %s" % ip
        host.cmd(cmd)

    def _build_mininet(self):
        s1 = self.net.addSwitch('s1')
        s2 = self.net.addSwitch('s2')
        s3 = self.net.addSwitch('s3')

        # create inter-switch at first to fix host interface name.
        Link(s1, s2)
        Link(s1, s2)
        Link(s2, s3)

        self._build_test_host(s1)

        # create dut host
        h6 = self.net.addHost('h6', cls=mn_vlanhost.VLANHost, vlan_id=200)
        h7 = self.net.addHost('h7')
        h8 = self.net.addHost('h8')
        # create dut host interfaces by Link-ing
        Link(h6, s3)
        Link(h7, s3)
        Link(h8, s2)

        self.net.build()

        # set interface parameters
        # so set interface parameters after build()
        # because net.build() reset host IP address...
        self._setup_test_host_intf()
        h6.intf('h6-eth0').setMAC('0a:00:00:00:00:06')
        h7.intf('h7-eth0').setMAC('0a:00:00:00:00:07')
        h8.intf('h8-eth0').setMAC('0a:00:00:00:00:08')
        h6.intf('h6-eth0').setIP('192.168.2.106/24')
        h7.intf('h7-eth0').setIP('192.168.2.107/24')
        h8.intf('h8-eth0').setIP('192.168.2.108/24')
        default_gw = '192.168.2.254'
        self._set_default_route_to_host(h6, default_gw)
        self._set_default_route_to_host(h7, default_gw)
        self._set_default_route_to_host(h8, default_gw)

        # add external nic to connect real devices
        self._add_external_nic(s1)
