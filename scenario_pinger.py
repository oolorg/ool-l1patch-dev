import json
import time
import re
import signal
import scenario_result_manager
import scenario_error
import scenario_tester


class ScenarioPingerBase(scenario_tester.ScenarioTesterBase):
    def __init__(self, testdefs_file_name):
        super(ScenarioPingerBase, self).__init__(testdefs_file_name)
        self._set_ping_test_params()
        self._set_test_scenario_data()

    def _set_test_scenario_data(self):
        try:
            params = self.testdef_data["test-scenario-defs"]
            result_file_name = params["test-result-file"]
            scenario_file_name = params["scenario-file"]
            # generate result manager
            self.result_mgr = scenario_result_manager.ResultManager(result_file_name)
            # generate scenario file by pattern file
            gen_scenario_cmd = self._make_command(params, "generate-scenario-command")
            self._exec_command(gen_scenario_cmd)
            # load generated scenario
            scenario_file = open(scenario_file_name, 'r')
            self.scenario_list = json.load(scenario_file)
            scenario_file.close()
            # optional key
            self.runner_class = None  # 'this' class (default)
            if "class" in params:
                self.runner_class = params["class"]
        except KeyError as err:
            msg = "Cannot find key:%s in test definition 'test-scenario-defs' section." % err.message
            raise scenario_error.ScenarioTestDefinitionError(msg)
        except IOError as err:
            msg = "File operation error in test definition 'test-scenario-defs' section.\n%s" % err
            raise scenario_error.ScenarioTestError(msg)

    def _set_ping_test_params(self):
        try:
            params = self.testdef_data["ping-test-params"]
            self.ping_cmd = params["ping-command"]
            # optional keys
            self.ping_max_retry = 3  # (times) default
            if "ping-max-retry" in params:
                self.ping_max_retry = params["ping-max-retry"]
            self.ping_retry_interval = 1  # (sec) default
            if "ping-retry-interval" in params:
                self.ping_retry_interval = params["ping-retry-interval"]
        except KeyError as err:
            msg = "Cannot find key:%s in test definition 'ping-test-params' section." % err.message
            raise scenario_error.ScenarioTestDefinitionError(msg)

    @staticmethod
    def _check_arp_table(result_detail):
        result_re = r"(REACHABLE|STALE|DELAY)"
        if re.compile(result_re).search(result_detail):
            # FAIL to clear arp table if found a REACHABLE entry
            return "FAIL"
        else:
            return "SUCCESS"

    @staticmethod
    def _check_ping_result(result_detail):
        result_re = r"(\d+) packets transmitted, (\d+) received"
        match = re.compile(result_re, flags=0).search(result_detail)
        transmitted = int(match.group(1))
        received = int(match.group(2))
        if received > transmitted / 2:
            return "SUCCESS"
        else:
            return "FAIL"

    def _start_scenario(self, description):
        self.logger.info("run scenario: %s", description)
        self.result_mgr.append_scenario(description)

    def _start_sub_scenario(self, description):
        self.logger.info("run sub scenario: %s", description)
        self.result_mgr.append_sub_scenario(description)

    def _run_test_check_arp_table(self, description, host, expected_result):
        # check
        command = "ip neigh show"
        result_detail = self._run_command_at(host, command)
        result = self._check_arp_table(result_detail)
        self.result_mgr.append_task_result_by(
            description, host.name, command, expected_result, result, result_detail
        )

    def _run_test_pre_task(self):
        self._start_sub_scenario("pre-tasks")
        # run pre-task for all hosts
        for host in self.net.hosts:
            description = "clear host %s arp table" % host.name
            self.logger.info("run task: %s", description)
            # cleaning arp cache at host
            self._run_command_at(host, "ip neigh flush dev %s" % host.defaultIntf().name)
            self._run_test_check_arp_table(description, host, "SUCCESS")

    def _run_test_post_task(self):
        self._start_sub_scenario("post-tasks")
        for host in self.net.hosts:
            description = "check host %s arp table" % host.name
            self.logger.info("run task: %s", description)
            self._run_test_check_arp_table(description, host, "FAIL")

    def _run_test_ping_task(self, task_list):
        self._start_sub_scenario("main tasks")
        # convert table to get host instance by its name
        host_dict = {h.name: h for h in self.net.hosts}
        # run test
        count = 0
        total = len(task_list)
        for task in task_list:
            description = task['task']
            src_host_name = task["source"]
            dst_host_name = task["destination"]
            expected_result = task["expect"]
            count += 1

            command = self.ping_cmd
            self.logger.info(
                "[%-3.1f%%/current:%d/total:%d] run task: %s",
                100.0*count/total, count, total, description
            )
            if re.match(r"\d+\.\d+\.\d+\.\d+", dst_host_name):
                # if match IP address
                command = " ".join([command, dst_host_name])
            else:
                command = " ".join([command, host_dict[dst_host_name].IP()])

            # run at first
            result_detail, result = self._run_ping_at(host_dict[src_host_name], command)
            # check need to retry
            retry_count = 1
            retry_interval = self.ping_retry_interval
            while retry_count <= self.ping_max_retry and result != expected_result:
                self.logger.warning(
                    "task: %s, (retry:%d/%d, after wait %s[sec])",
                    description, retry_count, self.ping_max_retry, retry_interval
                )
                time.sleep(retry_interval)
                # run retry
                result_detail, result = self._run_ping_at(host_dict[src_host_name], command)
                retry_count += 1
                retry_interval += self.ping_retry_interval
            # save result
            self.result_mgr.append_task_result_by(
                description, src_host_name, command, expected_result, result, result_detail
            )

    def _run_ping_at(self, host, command):
        result_detail = self._run_command_at(host, command)
        result = self._check_ping_result(result_detail)
        self.logger.info("result: %s", result)
        return result_detail, result

    def _run_scenario_test(self):
        for scenario in self.scenario_list:
            self._start_scenario(scenario["scenario"])
            self._run_test_pre_task()
            self._run_test_ping_task(scenario['task-list'])
            self._run_test_post_task()
        # save test results to file
        self.result_mgr.write_to_file()

    def _run_test(self, opt_dic):
        # option handling
        # usecase selection
        opt_manual = opt_dic["manual"]
        opt_test_cli = opt_dic["test-cli"]
        # layer selection
        opt_layer1 = opt_dic["layer1"]
        opt_layer2 = opt_dic["layer2"]
        opt_all_layers = opt_dic["all-layers"]
        if opt_all_layers:
            opt_layer1 = True
            opt_layer2 = True

        # mininet setup
        self._build_mininet()
        self._start_mininet()
        # wire(flow rules) setup
        if opt_layer1:
            self._put_layer1_flow_rules()
        if opt_layer2:
            self._put_layer2_flow_rules()

        # run test
        if opt_manual:
            self._run_cli()
        else:
            if opt_layer2:
                # run auto scenario test
                self._set_sigint_handler()
                self._run_scenario_test()
                if opt_test_cli:
                    self._run_cli()
                self._delete_flow_rules()
            else:
                self.logger.warn("Setup only L1(exclusive) wire flow rules.")

        # post test operations
        self._stop_mininet()
