import json
import collections
import patch_port
import patch_link
import patch_error


# Node class
class TestEnvNode(object):
    def __init__(self, node_name, node_data):
        self.name = node_name
        self.data = node_data  # dictionary
        self.port_index = {}
        self.datapath_id = 0
        self.role = None
        # setup port index: dictionary of port object
        self._setup_port_index()

    def port_names(self):
        return self.port_index.keys()

    def port_by_name(self, port_name):
        if port_name in self.port_index:
            return self.port_index[port_name]
        return None

    def _setup_port_index(self):
        port_index = self.data['port-index']
        for port_name, port_data in port_index.items():
            self.port_index[port_name] = patch_port.NodePort(port_name, port_data)

    def __str__(self):
        return "Node: %s (dpid:%d)" % (self.name, self.datapath_id)

    def dump(self):
        print self
        for port in self.port_index.values():
            print "  %s" % port


class TestHost(TestEnvNode):
    def __init__(self, node_name, node_data):
        super(TestHost, self).__init__(node_name, node_data)
        self.role = 'test-host'


class DUTHost(TestEnvNode):
    def __init__(self, node_name, node_data):
        super(DUTHost, self).__init__(node_name, node_data)
        self.role = 'dut-host'


class Dispatcher(TestEnvNode):
    def __init__(self, node_name, node_data):
        super(Dispatcher, self).__init__(node_name, node_data)
        self.role = "switch"
        self.datapath_id = node_data['datapath-id']


# Node Manager
class NodeManager(object):
    def __init__(self, node_data):
        self.node_data = node_data
        # use OrderedDict to keep order defined in config file
        # (also, must use OrderedDict as node_data)
        self.dispatcher_index = collections.OrderedDict()
        self.test_host_index = collections.OrderedDict()
        self.dut_host_index = collections.OrderedDict()
        self.linkmgr = patch_link.NodeLinkManager(self.node_data['link-list'])
        self._setup_dispatchers()
        self._setup_test_hosts()
        self._setup_dut_hosts()
        self._setup_node_port()

    def _setup_dispatchers(self):
        try:
            dispatcher_data = self.node_data['dispatchers']
        except KeyError:
            msg = "Could not find 'dispatcher' data in node info"
            raise patch_error.PatchDefinitionError(msg)
        for di_name, di_data in dispatcher_data.items():
            self.dispatcher_index[di_name] = Dispatcher(di_name, di_data)

    def _setup_test_hosts(self):
        try:
            test_hosts_data = self.node_data['test-hosts']
        except KeyError:
            msg = "Could not find 'test-hosts' data in node info"
            raise patch_error.PatchDefinitionError(msg)
        for th_name, th_data in test_hosts_data.items():
            self.test_host_index[th_name] = TestHost(th_name, th_data)

    def _setup_dut_hosts(self):
        try:
            dut_hosts_data = self.node_data['dut-hosts']
        except KeyError:
            msg = "Could not find 'dut-hosts' data in node info"
            raise patch_error.PatchDefinitionError(msg)
        for dut_name, dut_data in dut_hosts_data.items():
            self.dut_host_index[dut_name] = DUTHost(dut_name, dut_data)

    @staticmethod
    def __do_each_node_port(node_index, func):
        """
        do some func() for each node/port
        """
        for node_name, node in node_index.items():
            for port_name in node.port_names():
                func(node, node_name, port_name)

    def __counterpart_node_role(self, node_name, port_name):
        link = self.linkmgr.find_link_by_name(node_name, port_name)
        if link:
            counterpart_port = link.counterpart_by_name(node_name, port_name)
            counterpart_node = self.node_by_name(counterpart_port.node)
            return counterpart_node.role
        else:
            msg = "Cound not find link counterpart of Node,Port=%s,%s" % (node_name, port_name)
            raise patch_error.PatchDefinitionError(msg)

    def __create_test_host_port(self, host, host_name, port_name):
        cp_role = self.__counterpart_node_role(host_name, port_name)
        port_data = host.port_index[port_name].data
        if cp_role == 'switch':
            host.port_index[port_name]\
                = patch_port.TestHostPort(port_name, port_data)
        else:
            msg = "Test-Host,Port=%s,%s does not connect switch" % (host_name, port_name)
            raise patch_error.PatchDefinitionError(msg)

    def __create_dut_host_port(self, host, host_name, port_name):
        cp_role = self.__counterpart_node_role(host_name, port_name)
        port_data = host.port_index[port_name].data
        if cp_role == 'switch':
            host.port_index[port_name]\
                = patch_port.DUTHostPort(port_name, port_data)
        else:
            msg = "DUT-Host,Port=%s,%s does not connect switch" % (host_name, port_name)
            raise patch_error.PatchDefinitionError(msg)

    def __create_dispatcher_port(self, dispatcher, dispatcher_name, port_name):
        cp_role = self.__counterpart_node_role(dispatcher_name, port_name)
        # print "// switch:%s, port:%s, role:%s" % (dispatcher_name, port_name, cp_role)
        port_data = dispatcher.port_index[port_name].data
        if cp_role == 'test-host':
            dispatcher.port_index[port_name]\
                = patch_port.HostEdgePort(port_name, port_data)
        elif cp_role == 'dut-host':
            dispatcher.port_index[port_name]\
                = patch_port.DUTEdgePort(port_name, port_data)
        elif cp_role == 'switch':
            dispatcher.port_index[port_name]\
                = patch_port.InterSwitchPort(port_name, port_data)
        else:
            msg = "Dispatcher,Port=%s,%s connected unknown host/port"
            raise patch_error.PatchDefinitionError(msg)

    def _setup_node_port(self):
        self.__do_each_node_port(
            self.test_host_index, self.__create_test_host_port)
        self.__do_each_node_port(
            self.dut_host_index, self.__create_dut_host_port)
        self.__do_each_node_port(
            self.dispatcher_index, self.__create_dispatcher_port)

    def dump_dispatchers(self):
        """ for debug """
        for dispatcher in self.dispatcher_index.values():
            dispatcher.dump()

    def dump_test_hosts(self):
        """ for debug """
        for test_host in self.test_host_index.values():
            test_host.dump()

    def dump_dut_hosts(self):
        """ for debug """
        for dut_host in self.dut_host_index.values():
            dut_host.dump()

    def dump_links(self):
        """ for debug """
        self.linkmgr.dump()

    def has_test_host(self, test_host_name):
        return test_host_name in self.test_host_index

    def has_dut_host(self, dut_host_name):
        return dut_host_name in self.dut_host_index

    def has_dispatcher(self, dispatcher_name):
        return dispatcher_name in self.dispatcher_index

    def has_node(self, node_name):
        return (self.has_test_host(node_name)
                or self.has_dispatcher(node_name)
                or self.has_dut_host(node_name))

    def node_by_name(self, node_name):
        if self.has_test_host(node_name):
            return self.test_host_index[node_name]
        elif self.has_dut_host(node_name):
            return self.dut_host_index[node_name]
        elif self.has_dispatcher(node_name):
            return self.dispatcher_index[node_name]
        return None

    def test_host_port_by_name(self, test_host_name, port_name):
        if test_host_name in self.test_host_index:
            return self.test_host_index[test_host_name].port_by_name(port_name)
        return None

    def dut_host_port_by_name(self, dut_host_name, port_name):
        if dut_host_name in self.dut_host_index:
            return self.dut_host_index[dut_host_name].port_by_name(port_name)
        return None

    def dispatcher_port_by_name(self, dispatcher_name, port_name):
        if self.has_dispatcher(dispatcher_name):
            return self.dispatcher_index[dispatcher_name].port_by_name(port_name)
        return None

    def node_port_by_name(self, node_name, port_name):
        return (self.test_host_port_by_name(node_name, port_name)
                or self.dut_host_port_by_name(node_name, port_name)
                or self.dispatcher_port_by_name(node_name, port_name))


if __name__ == '__main__':
    node_data_file_name = 'nodeinfo_topo2.json'
    node_data_file = open(node_data_file_name, 'r')
    node_data = json.load(node_data_file)
    node_data_file.close()

    # print "## data"
    # print json.dumps(node_data, indent=2)

    node_mgr = NodeManager(node_data)

    # print "# dump links"
    # node_mgr.dump_links()
    # print "# dump dispatchers"
    # node_mgr.dump_dispatchers()
    # print "# dump test hosts"
    # node_mgr.dump_test_hosts()
    # print "# dump dut hosts"
    # node_mgr.dump_dut_hosts()

    print "# host ip/mac settings for mininet"
    for host_name, host_obj in node_mgr.test_host_index.items():
        print "- host: %s" % host_name
        for port_name, port_obj in host_obj.port_index.items():
            print "  - port:%s, mac:%s, ip:%s" % (
                port_obj.name, port_obj.mac_addr, port_obj.ip_addr
            )
    print "# dispatcher list and its dpid"
    for dispatcher_name, dispatcher_obj in node_mgr.dispatcher_index.items():
        print "- dispatcher: %s, dpid: %d" % (dispatcher_name, dispatcher_obj.datapath_id)
