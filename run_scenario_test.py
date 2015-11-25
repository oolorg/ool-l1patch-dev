import argparse
import re
import logging
import logging.config
import scenario_pinger
import scenario_error

if '__main__' == __name__:
    # logger settings
    logging.config.fileConfig('logger.conf')
    logger = logging.getLogger(__name__)

    # parse options
    arg_parser = argparse.ArgumentParser(description="Run Scenario Test")
    # test param definition
    arg_parser.add_argument(
        '-f', '--testdef',
        required=True, type=str, metavar='JSON',
        help="Test definition file"
    )
    # usecase selection
    arg_gr_usecase = arg_parser.add_mutually_exclusive_group()
    arg_gr_usecase.add_argument(
        '-m', '--manual', action="store_true",
        help="Go to Mininet CLI with L1patch setup."
    )
    arg_gr_usecase.add_argument(
        '-t', '--test-cli', action="store_true",
        help="Run auto test and go to CLI when test finished."
    )
    # layer selection
    arg_gr_layer = arg_parser.add_mutually_exclusive_group()
    arg_gr_layer.add_argument(
        '-1', '--layer1',
        required=False, action="store_true", default=False,
        help="Setup L1(exclusive mode wire) flow rules"
    )
    arg_gr_layer.add_argument(
        '-2', '--layer2',
        required=False, action="store_true", default=False,
        help="Setup L2(shared mode wire) flow rules"
    )
    arg_gr_layer.add_argument(
        '-a', '--all-layers',
        required=False, action="store_true", default=False,
        help="Setup all flow rules"
    )

    args = arg_parser.parse_args()
    test_runner = scenario_pinger.ScenarioPingerBase(args.testdef)

    # test_runner selection
    class_str = test_runner.runner_class
    if class_str:
        logger.info("reload runner class: %s", class_str)
        match = re.match(r"(.+)\.(.+)", class_str)
        if match:
            package_name = match.group(1)
            class_name = match.group(2)
            try:
                exec("import %s" % package_name)
                class_gen_str = "%s(args.testdef)" % class_str
                test_runner = eval(class_gen_str)
            except ImportError as err:
                msg = "Cannot import package:%s of test runner class." % package_name
                raise scenario_error.ScenarioTestDefinitionError(msg)
            except AttributeError as err:
                msg = "Cannot find class:%s in package:%s.\n%s" % (class_name, package_name, err)
                raise scenario_error.ScenarioTestDefinitionError(msg)
        else:
            msg = "Test runner class string format error in file:%s." % args.testdef
            raise scenario_error.ScenarioTestDefinitionError(msg)

    # run test
    logger.info("run scenario test with runner-class: %s", test_runner.__class__.__name__)
    opt_dic = {
        'manual': args.manual,
        'test-cli': args.test_cli,
        'layer1': args.layer1,
        'layer2': args.layer2,
        'all-layers': args.all_layers
    }
    test_runner.run_test(opt_dic)
