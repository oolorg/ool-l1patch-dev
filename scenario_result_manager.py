import re
import datetime
import logging
from os.path import isfile, splitext, getsize
import scenario_error


class TaskResult(object):
    def __init__(self, description, hostname, command,
                 expected_result, result, result_detail):
        self.description = description
        self.hostname = hostname
        self.command = command
        self.expected_result = expected_result
        self.result = result
        self.result_detail = result_detail
        self.recorded_time = datetime.datetime.now()

    def judge_result(self):
        if self.result == self.expected_result:
            return "*OK*"
        else:
            return "**NG**"

    def _result_detail_str(self):
        res_str = re.sub(r"^", "    ", self.result_detail)
        res_str = re.sub(r"[\n\r]+", "\n    ", res_str)
        return res_str

    def write_to(self, fp):
        fp.write("### run task: %s\n\n" % self.description)
        fp.write("- host: %s\n" % self.hostname)
        fp.write("- command: `%s`\n" % self.command)
        fp.write("- recorded: %s\n" % self.recorded_time.strftime("%Y-%m-%d %H:%M:%S"))
        fp.write("- judge: %s\n" % self.judge_result())
        fp.write("  - expected result: %s\n" % self.expected_result)
        fp.write("  - result: %s\n" % self.result)
        fp.write("- result detail:\n\n%s" % self._result_detail_str())
        fp.write("\n\n")


class SubScenarioResult(object):
    def __init__(self, description):
        self.description = description
        self.task_results = []

    def write_summary_to(self, fp):
        fp.write("\n")
        fp.write("No.|host|command|result|expected|judge\n")
        fp.write("---|----|-------|------|--------|-----\n")
        count = 1
        for task_res in self.task_results:
            fp.write("%d|%s|`%s`|%s|%s|%s\n" % (
                count,
                task_res.hostname,
                task_res.command,
                task_res.result,
                task_res.expected_result,
                task_res.judge_result()
            ))
            count += 1
        fp.write("\n")

    def write_to(self, fp):
        fp.write("## run sub scenario: %s\n\n" % self.description)
        fp.write("### summary\n")
        self.write_summary_to(fp)
        for task_res in self.task_results:
            task_res.write_to(fp)


class ScenarioResult(object):
    def __init__(self, description):
        self.description = description
        self.sub_scenario_results = []

    def write_to(self, fp):
        fp.write("# run scenario: %s\n\n" % self.description)
        for sub_scenario_res in self.sub_scenario_results:
            sub_scenario_res.write_to(fp)


class ResultManager(object):
    def __init__(self, file_name):
        self.logger = logging.getLogger(__name__)
        self._set_file_object(file_name)
        self.scenario_results = []

    def _set_file_object(self, file_name):
        count = 1
        basename, ext = splitext(file_name)
        while isfile(file_name) and getsize(file_name) > 0:
            next_file_name = "".join([basename, "-", str(count), ext])
            self.logger.warning(
                "Result file:%s is already exists, change file name to %s.",
                file_name, next_file_name
            )
            count += 1
            file_name = next_file_name
        try:
            self.fp = open(file_name, "w")
        except IOError as err:
            msg = "Cannot open file:%s.\n%s" % (file_name, err.message)
            raise scenario_error.ScenarioTestError(msg)

    def append_task_result(self, task_result):
        self.scenario_results[-1].sub_scenario_results[-1].task_results.append(
            task_result
        )

    def append_task_result_by(
            self, description, hostname, command, expected_result, result, result_detail):
        self.append_task_result(
            TaskResult(description, hostname, command, expected_result, result, result_detail)
        )

    def append_scenario(self, description):
        self.scenario_results.append(
            ScenarioResult(description)
        )

    def append_sub_scenario(self, description):
        self.scenario_results[-1].sub_scenario_results.append(
            SubScenarioResult(description)
        )

    def write_to_file(self):
        now = datetime.datetime.now()
        self.fp.write("Report created date: %s\n\n" % now.strftime("%Y-%m-%d %H:%M:%S"))
        for scenario_result in self.scenario_results:
            scenario_result.write_to(self.fp)
