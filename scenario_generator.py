import json
import itertools
import collections
import re
import argparse
import scenario_error


class ScenarioGenerator(object):
    PARAM_RE = r"@.+@"
    TASK_RE = r"([a-zA-Z\d\-\_]+)\(([A-Z]+)\)"

    def __init__(self, file_name):
        try:
            scenario_data_file = open(file_name, 'r')
            # use Ordered Dict to keep key order in file
            scenario_data = json.load(
                scenario_data_file, object_pairs_hook=collections.OrderedDict)
            self.params = scenario_data["params"]
            self.scenarios = scenario_data["scenarios"]
            self.data = []
        except ValueError as err:
            msg = "Scenario data file, %s: json parse error.\n%s" % (file_name, err)
            raise scenario_error.ScenarioTestDefinitionError(msg)
        except IOError as err:
            msg = "Cannot open sceanrio data file: %s.\n%s" % (file_name, err)
            raise scenario_error.ScenarioTestError(msg)

    def dump(self):
        print json.dumps(self.data, indent=2)

    def generate_scenario(self):
        for scenario in self.scenarios.keys():
            # print "* Scenario: %s" % scenario
            scenario_data = {
                "scenario": scenario,
                "task-list": []
            }
            for task in self.scenarios[scenario].keys():
                # print "** Task: %s" % task
                scenario_data["task-list"].extend(
                    self.generate_task(task, self.scenarios[scenario][task])
                )
            self.data.append(scenario_data)

    def generate_task(self, task, task_data):
        # print "### %s" % task_data
        task_list = []
        for set1, set2 in itertools.permutations(task_data, 2):
            # print "*** set1:%s, set2:%s" % (set1, set2)
            for prod1, prod2 in itertools.product(set1, set2):
                prod1_is_param = self._is_param(prod1)
                if not prod1_is_param:
                    task_list.append(self._generate_ping_task(task, prod1, prod2))
        return task_list

    def _generate_ping_task(self, task, host1, host2):
        try:
            match = re.match(self.TASK_RE, task)
            task_name = match.group(1)
            expected_result = match.group(2)
        except AttributeError as err:
            msg = "task:%s does not match pattern 'task-name(RESULT)'.\n%s" % (task, err)
            raise scenario_error.ScenarioTestDefinitionError(msg)
        return {
            "task": "[%s] ping %s to %s" % (task_name, host1, host2),
            "source": self._param_value(host1),
            "destination": self._param_value(host2),
            "command": "ping",
            "expect": expected_result
        }

    def _is_param(self, value):
        return re.match(self.PARAM_RE, value)

    def _param_value(self, key):
        try:
            if self._is_param(key):
                return self.params[key]
            elif re.search(r"@", key):
                msg = "Word:%s contains '@', cannot distinguish it `hostname` or `@parameter@`." % key
                raise scenario_error.ScenarioTestDefinitionError(msg)
            else:
                return key
        except KeyError as err:
            msg = "Parameter:%s not found in param table.\n%s" % (key, err)
            raise scenario_error.ScenarioTestDefinitionError(msg)


if __name__ == '__main__':
    arg_parser = argparse.ArgumentParser(description="Generate Sceanrio by pattern")
    arg_parser.add_argument(
        '-f', '--file',
        required=True,
        type=str, metavar='JSON',
        help="Scenario pattern information file"
    )
    args = arg_parser.parse_args()

    # generate scenario file by pattern file
    scenario_gen = ScenarioGenerator(args.file)
    scenario_gen.generate_scenario()
    scenario_gen.dump()
