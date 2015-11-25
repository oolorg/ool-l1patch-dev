import logging
import json
from webob import Response
from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller import dpset
# from ryu.controller.handler import MAIN_DISPATCHER
from ryu.controller.handler import CONFIG_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_0
from ryu.ofproto import ofproto_v1_2
from ryu.ofproto import ofproto_v1_3
from ryu.lib import ofctl_v1_0
from ryu.lib import ofctl_v1_2
from ryu.lib import ofctl_v1_3
from ryu.app.wsgi import ControllerBase, WSGIApplication, route
import patch_ofc_flowbuilder
import patch_ofc_error

'''
"L1patch" OpenFlow controller based on "OFPatchPanel".
See also "OFPatchPanel" application.
nmasao/OFPatchPanel-SDNHackathon2014 · GitHub
https://github.com/nmasao/OFPatchPanel-SDNHackathon2014
'''

patch_instance_name = 'patch_app'
LOG = logging.getLogger('ryu.app.patch.patch_rest')


class PatchPanel(app_manager.RyuApp):

    OFP_VERSIONS = [ofproto_v1_0.OFP_VERSION,
                    ofproto_v1_2.OFP_VERSION,
                    ofproto_v1_3.OFP_VERSION]

    _CONTEXTS = {
        'wsgi': WSGIApplication,
        'dpset': dpset.DPSet}

    def __init__(self, *args, **kwargs):
        super(PatchPanel, self).__init__(*args, **kwargs)
        self.dpset = kwargs['dpset']
        wsgi = kwargs['wsgi']
        wsgi.register(PatchController, {patch_instance_name: self})
        self.patch_flows = []  # list of dict(flow)

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        message = 'connected datapath: dpid=%d' % datapath.id
        LOG.info(message)

        deny_any_flow = {
            'match': {
                # match any
            },
            'actions': [
                # empty : action DROP
            ],
            'priority': 0  # lowest priority
        }
        if not self._mod_patch_flow_entry(
                datapath, deny_any_flow, datapath.ofproto.OFPFC_ADD):
            msg = "DPID:%s, Cannot set default deny flow rule." % datapath.id
            raise patch_ofc_error.PatchOfcError(msg)

    def add_patch_flow(self, req_flow):
        self._mod_patch_flow(req_flow, 'put')

    def delete_patch_flow(self, req_flow):
        self._mod_patch_flow(req_flow, 'delete')

    def _mod_patch_flow(self, req_flow, command):
        # check command
        if command not in ['delete', 'put']:
            LOG.error("Unknown command: %s" % command)
            return Response(status=501)

        # Check before send flow-mod
        dpid = req_flow.get('dpid')
        dp = self.dpset.get(dpid)
        if dp is None:
            LOG.error("Cannot find datapath-id:%s" % dpid)
            return Response(status=400)

        # TODO: resource overwrap-check for exclusive mode wire
        # for flow in self.patch_flows:
        #     if dpid == flow['dpid'] and inport == flow['inport']:
        #         LOG.info('Requested inport is already used (dpid:%s, inport:%d)', dpid, inport)
        #         return Response(status=400)

        try:
            flow_rules = patch_ofc_flowbuilder.FlowRuleBuilder(dp, req_flow).build_flow()
            for flow_rule in flow_rules:
                print "--------------------------"
                print "%s, dpid:%d (ofp_ver:%d)" % (
                    command.upper(), dpid, dp.ofproto.OFP_VERSION
                )
                print json.dumps(req_flow)
                print json.dumps(flow_rule)
                self._mod_patch_flow_entry(
                    dp, flow_rule, self._get_datapath_command(dp, command)
                )
                self._post_mod_patch_flow(req_flow, command)
                print "--------------------------"
            cors_headers = {'Access-Control-Allow-Origin': '*'}
            # Notice: Any request will accepted (status=200)
            # if the request can send flow-mod to OFS
            # (When the request does not have invalid dpid, invalid ofp-version.)
            # Does not matter whether the request is match/correct.
            return Response(status=200, headers=cors_headers)
        except (patch_ofc_error.PatchOfcRestError,
                patch_ofc_error.PatchOfcError) as err:
            LOG.error(err.message)
            return Response(status=501)

    @staticmethod
    def _get_datapath_command(dp, command):
        if command == 'delete':
            return dp.ofproto.OFPFC_DELETE
        elif command == 'put':
            return dp.ofproto.OFPFC_ADD
        else:
            msg = "Unknown command: %s" % command
            raise patch_ofc_error.PatchOfcError(msg)

    def _post_mod_patch_flow(self, req_flow, command):
        if command == 'delete':
            self._delete_from_patch_flows(req_flow)
        elif command == 'put':
            self.patch_flows.append(req_flow)
        else:
            msg = "Unknown command: %s" % command
            raise patch_ofc_error.PatchOfcError(msg)

    def _delete_from_patch_flows(self, req_flow):
        # check each flows
        req_flow_str = json.dumps(req_flow)
        found_flow = None
        for flow in self.patch_flows:
            # TODO: now, use simplified/strict compare...
            # difficult to compare recursively complex dict/list data.
            # To compare it more simply, stringify these data...
            # (json.dumps default: dictionary sorted.
            flow_str = json.dumps(flow)
            if req_flow_str == flow_str:
                found_flow = flow
                break
        if found_flow:
            self.patch_flows.remove(found_flow)

    def _mod_patch_flow_entry(self, dp, flow_rule, command):
        if dp.ofproto.OFP_VERSION in self.OFP_VERSIONS:
            if dp.ofproto.OFP_VERSION == ofproto_v1_0.OFP_VERSION:
                ofctl_v1_0.mod_flow_entry(dp, flow_rule, command)
            elif dp.ofproto.OFP_VERSION == ofproto_v1_2.OFP_VERSION:
                ofctl_v1_2.mod_flow_entry(dp, flow_rule, command)
            elif dp.ofproto.OFP_VERSION == ofproto_v1_3.OFP_VERSION:
                ofctl_v1_3.mod_flow_entry(dp, flow_rule, command)
            return True
        else:
            msg = "Unsupported OFP version: %s" % dp.ofproto.OFP_VERSION
            raise patch_ofc_error.PatchOfcError(msg)

    def get_patch_flows(self):
        body = json.dumps(self.patch_flows)
        return Response(content_type='application/json',
                        body=body, status=200)


class PatchController(ControllerBase):
    def __init__(self, req, link, data, **config):
        super(PatchController, self).__init__(req, link, data, **config)
        self.patch_app = data[patch_instance_name]

    @route('patch', '/patch/flow', methods=['PUT'])
    def add_patch_flow(self, req, **kwargs):
        LOG.debug("start add_patch_flow")
        patch = self.patch_app
        try:
            flow = eval(req.body)
        except SyntaxError:
            LOG.debug('invalid syntax %s', req.body)
            return Response(status=400)

        result = patch.add_patch_flow(flow)
        return result

    @route('patch', '/patch/flow', methods=['DELETE'])
    def delete_patch_flow(self, req, **kwargs):
        patch = self.patch_app
        try:
            flow = eval(req.body)
        except SyntaxError:
            LOG.debug('invalid syntax %s', req.body)
            return Response(status=400)

        result = patch.delete_patch_flow(flow)
        return result

    @route('patch', '/patch/flow', methods=['GET'])
    def get_patch_flows(self, req, **kwargs):
        patch = self.patch_app
        result = patch.get_patch_flows()
        return result

    @route('patch', '/patch/flow', methods=['OPTIONS'])
    def opts_patch_flows(self, req, **kwargs):
        cors_headers = {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'PUT, GET, DELETE, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type, Origin'
        }
        return Response(status=200, headers=cors_headers)
