import json


class NodePort(object):
    def __init__(self, port_name, port_data):
        self.name = port_name
        self.data = port_data
        self.number = 0  # default
        self.role = None

    def __str__(self):
        return "Port:{ name:%s, role:%s, data:%s }" % (
            self.name, self.role, json.dumps(self.data)
        )

    @staticmethod
    def is_dut_edge_port():
        return False

    @staticmethod
    def is_host_edge_port():
        return False

    @staticmethod
    def is_inter_switch_port():
        return False

    @staticmethod
    def is_test_host_port():
        return False

    @staticmethod
    def is_dut_host_port():
        return False


class DispatcherPort(NodePort):
    def __init__(self, port_name, port_data):
        super(DispatcherPort, self).__init__(port_name, port_data)
        self.number = port_data['number']


class DUTEdgePort(DispatcherPort):
    def __init__(self, port_name, port_data):
        super(DUTEdgePort, self).__init__(port_name, port_data)
        self.role = 'dut-edge'

    @staticmethod
    def is_dut_edge_port():
        return True


class HostEdgePort(DispatcherPort):
    def __init__(self, port_name, port_data):
        super(HostEdgePort, self).__init__(port_name, port_data)
        self.role = 'host-edge'

    @staticmethod
    def is_host_edge_port():
        return True


class InterSwitchPort(DispatcherPort):
    def __init__(self, port_name, port_data):
        super(InterSwitchPort, self).__init__(port_name, port_data)
        self.role = 'inter-switch'

    @staticmethod
    def is_inter_switch_port():
        return True


class HostPort(NodePort):
    def __init__(self, port_name, port_data):
        super(HostPort, self).__init__(port_name, port_data)
        self.role = 'host'
        self.vlan_id = 0  # default
        self.vlan_tagged = False  # default

    def has_vlan(self):
        return self.vlan_tagged


class TestHostPort(HostPort):
    def __init__(self, port_name, port_data):
        super(TestHostPort, self).__init__(port_name, port_data)
        self.mac_addr = port_data['mac-addr']
        self.ip_addr = port_data['ip-addr']
        # gateway is optional
        try:
            self.gateway = port_data['gateway']
        except KeyError:
            self.gateway = None
        self.role = 'test-host'

    @staticmethod
    def is_test_host_port():
        return True


class DUTHostPort(HostPort):
    def __init__(self, port_name, port_data):
        super(DUTHostPort, self).__init__(port_name, port_data)
        if 'vlan-id' in port_data:
            self.vlan_id = port_data['vlan-id']  # overwrite if exist key
        if 'vlan-tagged' in port_data:
            self.vlan_tagged = port_data['vlan-tagged']  # overwrite if exist key
        self.role = 'dut-host'

    def has_vlan(self):
        return self.vlan_tagged and 0 < self.vlan_id < 4096

    @staticmethod
    def is_dut_host_port():
        return True
