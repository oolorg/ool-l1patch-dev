import json
import patch_node
import patch_wire_group
import patch_error


class FlowRuleGenerator(object):
    def __init__(self, nodeinfo_filename, wireinfo_filename):
        self.node_mgr = self.gen_node_manager_by_file(nodeinfo_filename)
        self.wire_mgr = self.gen_wire_manager_by_file(wireinfo_filename)

    @staticmethod
    def gen_node_manager_by_file(file_name):
        try:
            node_data_file = open(file_name, 'r')
            node_data = json.load(node_data_file)
            node_data_file.close()
            return patch_node.NodeManager(node_data)
        except ValueError as err:
            msg = "Node info file, %s: json parse error.\n%s" % (file_name, err)
            raise patch_error.PatchDefinitionError(msg)
        except IOError as err:
            msg = "Cannot open node info file: %s.\n%s" % (file_name, err)
            raise patch_error.PatchError(msg)

    @staticmethod
    def gen_wire_manager_by_file(file_name):
        try:
            wire_data_file = open(file_name, 'r')
            wire_data = json.load(wire_data_file)
            wire_data_file.close()
            return patch_wire_group.WireManager(wire_data)
        except ValueError as err:
            msg = "Wire info file, %s: json parse error.\n%s" % (file_name, err)
            raise patch_error.PatchDefinitionError(msg)
        except IOError as err:
            msg = "Cannot open wire info file: %s.\n%s" % (file_name, err)
            raise patch_error.PatchError(msg)

    def _map_wire_and_port(self):
        for name, wire in self.wire_mgr.wire_index.items():
            wire.setup_wire_entity(self.node_mgr)

    def _generate_exclusive_mode_flow_rule(self, flow_rule):
        # create rules for exclusive mode wire
        for exc_wire_name, exc_wire in self.wire_mgr.exclusive_wire_index.items():
            flow_rule_by_exc_wire = exc_wire.generate_flow_rule()
            self._merge_flow_rule(flow_rule, flow_rule_by_exc_wire)

    def _generate_shared_mode_flow_rule(self, flow_rule):
        # create rules for shared mode wire by wire-group
        for wire_group_name, wire_group in self.wire_mgr.wire_group_index.items():
            for wire_name in wire_group.wires:
                # get wire object
                wire = self.wire_mgr.wire_by_name(wire_name)
                # get flow rules by wire
                flow_rule_by_wire = wire.generate_flow_rule()
                # save rules into flow_rule
                self._merge_flow_rule(flow_rule, flow_rule_by_wire)

            # get broadcast rules
            # Notice: use path of 1st wire in wire_group as broadcast path
            bcast_wire = self.wire_mgr.wire_by_name(wire_group.wires[0])
            out_ports = self.wire_mgr.generate_bcast_outports_by_wire_group(
                wire_group
            )
            flow_rule_by_wire_group = wire_group.generate_bcast_rule_by_wire_group(
                bcast_wire, out_ports
            )
            # save rules
            self._merge_flow_rule(flow_rule, flow_rule_by_wire_group)

    def generate_flow_rule(self, use_mode='all'):
        # at first, map physical port information to logical wire
        self._map_wire_and_port()
        flow_rule = {}
        if use_mode == 'all' or use_mode == 'exclusive':
            self._generate_exclusive_mode_flow_rule(flow_rule)
        if use_mode == 'all' or use_mode == 'shared':
            self._generate_shared_mode_flow_rule(flow_rule)
        return flow_rule

    @staticmethod
    def _merge_flow_rule(rule, wire_rule):
        for key, value in wire_rule.items():
            # value: list of rules
            if key in rule:
                rule[key].extend(value)
            else:
                rule[key] = value
        return rule

if __name__ == '__main__':
    flow_rule_generator = FlowRuleGenerator('nodeinfo_topo2.json', 'wireinfo_topo2.json')
    flow_rule = flow_rule_generator.generate_flow_rule()
    print json.dumps(flow_rule, indent=2)
