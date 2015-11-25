#!/usr/bin/python

import json
import argparse
import patch_flowgen

if __name__ == "__main__":
    # parse options
    arg_parser = argparse.ArgumentParser(
        description="Create L1patch Flow Rule (REST json)"
    )
    arg_parser.add_argument(
        '-p', '--physical',
        required=True,
        type=str, metavar='JSON',
        help="Physical topology information file"
    )
    arg_parser.add_argument(
        '-l', '--logical',
        required=True,
        type=str, metavar='JSON',
        help="Logical topology (wire) information file"
    )
    arg_parser.add_argument(
        '-m', '--mode',
        required=True,
        nargs=1, choices=['all', 'exclusive', 'shared']
    )
    args = arg_parser.parse_args()

    # generate flow rules for OFC REST
    flow_rule_generator = patch_flowgen.FlowRuleGenerator(
        args.physical, args.logical
    )
    flow_rule = flow_rule_generator.generate_flow_rule(args.mode[0])
    print json.dumps(flow_rule, indent=2)
