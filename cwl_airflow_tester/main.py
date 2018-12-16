#! /usr/bin/env python3
import os
import sys
import uuid
import json
import logging
import argparse
import requests

from os.path import join, basename, splitext, dirname
from future.moves.urllib.parse import urljoin

from queue import Queue

from airflow.settings import DAGS_FOLDER

from cwl_airflow_tester.utils.helpers import normalize_args, load_yaml, gen_dag_id, get_folder
from cwl_airflow_tester.utils.cwl import load_job
from cwl_airflow_tester.utils.checker import start_status_updates_daemon, get_checker_thread


API_URL = "http://localhost:8080"


DAG_TEMPLATE="""#!/usr/bin/env python3
from cwl_airflow_parser import CWLDAG, CWLJobDispatcher, CWLJobGatherer
def cwl_workflow(workflow_file):
    dag = CWLDAG(cwl_workflow=workflow_file)
    dag.create()
    dag.add(CWLJobDispatcher(dag=dag), to='top')
    dag.add(CWLJobGatherer(dag=dag), to='bottom')
    return dag
dag = cwl_workflow("{}")
"""


def get_parser():
    parser = argparse.ArgumentParser(description='Run tests for CWL Airflow Parser', add_help=True)
    parser.add_argument("-c", "--conf", help="Path to the test file", required=True)
    parser.add_argument("-t", "--tmp",  help="Temp directory to save results", required=True)
    parser.add_argument("-p", "--port", help="Port for http server to listen to status updates", type=int, default=80)
    return parser


def load_test_data(args):
    logging.info(f"""Load tests from: \n{args.conf}""")
    test_data = load_yaml(args.conf)
    for test_item in test_data:
        test_item.update({
            "job":  os.path.normpath(os.path.join(dirname(args.conf), test_item["job"])),
            "tool": os.path.normpath(os.path.join(dirname(args.conf), test_item["tool"])),
            "run_id": str(uuid.uuid4())
        })
    return test_data


def gen_dags(test_data):
    processed = []
    for item in test_data:
        cwl_file = item["tool"]
        if cwl_file not in processed:
            with open(join(DAGS_FOLDER, splitext(basename(cwl_file))[0]+".py"), 'w') as out_stream:
                out_stream.write(DAG_TEMPLATE.format(cwl_file))
                processed.append(cwl_file)


def trigger_dags(test_data, args):
    for item in test_data:
        job = load_job(item["job"])
        job.update({"output_folder": get_folder(os.path.join(args.tmp, item["run_id"]))})
        json_data = {
            "run_id": item["run_id"],
            "conf": json.dumps({"job": job})
        }
        r = requests.post(url=urljoin(API_URL, f"""/api/experimental/dags/{gen_dag_id(item["tool"])}/dag_runs"""),
                          json=json_data)


def main(argsl=None):
    if argsl is None:
        argsl = sys.argv[1:]
    args,_ = get_parser().parse_known_args(argsl)
    args = normalize_args(args, ["port"])

    test_data = load_test_data(args)
    test_queue = Queue(maxsize=len(test_data))

    start_status_updates_daemon(test_queue, args.port)
    checker_tread = get_checker_thread(test_data)

    gen_dags(test_data)
    trigger_dags(test_data, args)

    checker_tread.join()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))


