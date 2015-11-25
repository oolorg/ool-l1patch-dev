import json
import httplib2
import sys
import time
import logging
import logging.config
import re
import argparse
import patch_ofc_error


class L1PatchFlowThrower:
    def __init__(self, base_url, port):
        self.base_url = base_url
        self.port = port
        self._read_flow_rules_from_stdin()
        self.rest_svr = httplib2.Http(".cache")
        logging.config.fileConfig('logger.conf')
        self.logger = logging.getLogger(__name__)

    def _read_flow_rules_from_stdin(self):
        self.flow_rules_dic = json.load(sys.stdin, encoding='utf-8')

    def dump(self):
        print json.dumps(self.flow_rules_dic, indent=2)

    def put_all_flow_rules(self, path, method):
        url = "http://" + self.base_url + ":" + str(self.port) + path
        self.logger.info("Set API URL: %s" % url)
        for dispatcher_name, flow_rules in self.flow_rules_dic.items():
            for flow_rule in flow_rules:
                self._put_flow_rule(url, dispatcher_name, method, flow_rule)

    def _put_flow_rule(self, api_url, dispatcher_name, method, rule):
        method = str(method).upper()
        if not (method == 'PUT' or method == 'DELETE'):
            msg = "Unknown method:%s to send OpenFlow Controller" % method
            raise patch_ofc_error.PatchOfcRestError(msg)

        time.sleep(0.1)
        response, content = self.rest_svr.request(
            api_url, method, json.dumps(rule)
        )
        log_level = logging.INFO
        if not re.match(r"2\d\d", response["status"]):
            log_level = logging.ERROR

        self.logger.log(
            log_level,
            "Send %s: node:%s, rule:%s",
            method, dispatcher_name, json.dumps(rule)
        )
        self.logger.log(log_level, "Response: %s", response)
        self.logger.log(log_level, "Content: %s", content)

if __name__ == '__main__':
    # parse options
    arg_parser = argparse.ArgumentParser(
        description="Send Flow Rule (REST json) to OpenFlow Controller"
    )
    arg_parser.add_argument(
        '-m', '--method',
        required=True, nargs=1, choices=["put", "delete"]
    )
    args = arg_parser.parse_args()

    # run
    flow_builder = L1PatchFlowThrower("localhost", 8080)
    # flow_builder.dump()
    flow_builder.put_all_flow_rules("/patch/flow", args.method[0])
