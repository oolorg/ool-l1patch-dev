from ryu.ofproto import ofproto_v1_0
from ryu.ofproto import ofproto_v1_2
from ryu.ofproto import ofproto_v1_3
import patch_ofc_flowrule
import patch_ofc_error


class FlowRuleBuilder(object):
    def __init__(self, dp, req_flow):
        self.req_flow = req_flow
        self.datapath = dp
        self._setup_flow_rule()

    def build_flow(self):
        self._check_flow_property()
        # match conditions
        self._check_inport_conditions()  # MUST option
        self._check_ether_conditions()
        self._check_vlan_conditions()
        self._check_mpls_conditions()
        # actions
        self._check_vlan_actions()
        self._check_mpls_actions()
        self._check_outport_actions()  # MUST options

        return self.flow_rule.rules()

    def _setup_flow_rule(self):
        if self.datapath.ofproto.OFP_VERSION == ofproto_v1_0.OFP_VERSION:
            self.flow_rule = patch_ofc_flowrule.FlowRuleOF10()
        elif (self.datapath.ofproto.OFP_VERSION == ofproto_v1_2.OFP_VERSION
              or self.datapath.ofproto.OFP_VERSION == ofproto_v1_3.OFP_VERSION):
            self.flow_rule = patch_ofc_flowrule.FlowRuleOF13()
        else:
            msg = "Unknown datapath ofp version for FlowRuleBuilder"
            raise patch_ofc_error.PatchOfcError(msg)

    def _check_flow_property(self):
        priority = self.req_flow.get('priority')
        if priority:
            self.flow_rule.update_priority(priority)

    def _check_inport_conditions(self):
        # MUST option
        inport = self.req_flow.get('inport')
        if inport:
            self.flow_rule.update_match_inport(inport)
        else:
            msg = "REST request does not include 'inport' key."
            raise patch_ofc_error.PatchOfcRestError(msg)

    def _check_ether_conditions(self):
        eth_src = self.req_flow.get('eth_src')
        if eth_src:
            self.flow_rule.update_match_eth_src(eth_src)

        eth_dst = self.req_flow.get('eth_dst')
        if eth_dst:
            self.flow_rule.update_match_eth_dst(eth_dst)

    def _check_vlan_conditions(self):
        vlan_vid = self.req_flow.get('vlan_vid')
        if vlan_vid:
            self.flow_rule.update_match_vlan_vid(vlan_vid)

    def _check_mpls_conditions(self):
        mpls_label = self.req_flow.get('mpls_label')
        if mpls_label:
            self.flow_rule.update_match_mpls_label(mpls_label)

    def _check_vlan_actions(self):
        push_vlan = self.req_flow.get('push_vlan')
        if push_vlan:
            self.flow_rule.action_push_vlan(push_vlan)
        pop_vlan = self.req_flow.get('pop_vlan')
        if pop_vlan:
            self.flow_rule.action_pop_vlan()
        set_vlan = self.req_flow.get('set_vlan')
        if set_vlan:
            self.flow_rule.action_set_vlan_vid(set_vlan)

    def _check_mpls_actions(self):
        push_mpls = self.req_flow.get('push_mpls')
        if push_mpls:
            self.flow_rule.action_push_mpls(push_mpls)
        pop_mpls = self.req_flow.get('pop_mpls')
        if pop_mpls:
            self.flow_rule.action_pop_mpls()

    def _check_outport_actions(self):
        # MUST one of them
        outports = self.req_flow.get('outports')
        outport = self.req_flow.get('outport')
        if outports:
            for port in outports:
                self.flow_rule.action_output(port)
        elif outport:
            self.flow_rule.action_output(outport)
        else:
            msg = "REST request does not include any outport(s) action."
            raise patch_ofc_error.PatchOfcRestError(msg)


class DummyReq(object):
    def __init__(self):
        self.dic = {
            "outport": 1,
            "dpid": 3,
            "eth_dst": "0a:00:00:00:00:01",
            "inport": 2,
            "pop_vlan": "true",
            "vlan_vid": 200
        }

        # self.dic = {
        #     "outport": 1,
        #     "mpls_label": 102,
        #     "inport": 2,
        #     "dpid": 2
        # }

        # self.dic = {
        #     "outport": "s3-eth1",
        #     "vlan_vid": 200,
        #     "push_mpls": 101,
        #     "dpid": "s3",
        #     "eth_dst": "ff:ff:ff:ff:ff:ff",
        #     "inport": "s3-eth2",
        #     "pop_vlan": "true"
        # }

        # self.dic = {
        #     "eth_src": "0a:00:00:00:00:02",
        #     "outport": "s1-eth1",
        #     "inport": "s1-eth3",
        #     "dpid": "s1"
        # }

    def get(self, key):
        return self.dic[key] if key in self.dic else None


if __name__ == '__main__':
    req = DummyReq()
    # print json.dumps(FlowRuleBuilder(req).build_flow(), indent=2)
