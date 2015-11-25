from mininet.node import Host


class VLANHost(Host):
    def config(self, vlan_id, **params):
        r = super(VLANHost, self).config(**params)
        intf = self.defaultIntf()

        vlan_intf = '%s.%d' % (intf, vlan_id)
        self.cmd('ip addr del %s dev %s' % (params['ip'], intf))
        self.cmd('ip link add link %s name %s type vlan id %d' % (
            intf, vlan_intf, vlan_id
        ))
        self.cmd('ip addr add %s brd 10.255.255.255 dev %s' % (
            params['ip'], vlan_intf
        ))
        self.cmd('ip link set dev %s up' % vlan_intf)

        intf.name = vlan_intf
        self.nameToIntf[vlan_intf] = intf

        return r
