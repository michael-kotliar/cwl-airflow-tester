#! /usr/bin/env python3
import os
import sys
import uuid
import logging
import argparse
import requests

from queue import Queue
from json import dumps, loads
from os.path import join, basename, splitext, dirname
from future.moves.urllib.parse import urljoin

from cwl_airflow_tester.utils.mute import Mute
with Mute():
    from airflow.settings import DAGS_FOLDER

    from cwl_airflow_tester.utils.helpers import normalize_args, load_yaml, gen_dag_id, get_folder
    from cwl_airflow_tester.utils.cwl import load_job
    from cwl_airflow_tester.utils.checker import get_listener_thread, get_checker_thread
    from cwl_airflow_tester.utils.airflow import conf_get_default
    from cwl_airflow_tester.utils.logger import reset_root_logger


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
    parser.add_argument("-t", "--test",     help="Path to the test file",     required=True)
    parser.add_argument("-o", "--output",   help="Directory to save outputs", required=True)
    parser.add_argument("-p", "--port",     help="Port to listen to status updates", type=int, default=80)
    parser.add_argument("-e", "--endpoint", help="Airflow endpoint to trigger DAG", default=conf_get_default("cli", "endpoint_url", "http://localhost:8080"))
    logging_level = parser.add_mutually_exclusive_group()
    logging_level.add_argument("-d", "--debug",    help="Output debug information", action="store_true")
    logging_level.add_argument("-q", "--quiet",    help="Suppress all outputs except errors", action="store_true")
    return parser


def load_data(args):
    logging.info(f"""Load test data from: {args.test}""")
    data = loads(dumps(load_yaml(args.test)))
    logging.debug(f""" - {len(data)} test[s] have been loaded""")
    for item in data:
        item.update({
            "job":  os.path.normpath(os.path.join(dirname(args.test), item["job"])),
            "tool": os.path.normpath(os.path.join(dirname(args.test), item["tool"])),
        })
    return {str(uuid.uuid4()): item for item in data}


def export_dags(data):
    logging.info(f"""Export DAGs to: {DAGS_FOLDER}""")
    dags = []
    for item in data.values():
        cwl_file = item["tool"]
        dag_file = join(DAGS_FOLDER, splitext(basename(cwl_file))[0]+".py")
        if dag_file not in dags:
            with open(dag_file, 'w') as out_stream:
                out_stream.write(DAG_TEMPLATE.format(cwl_file))
                dags.append(dag_file)
                logging.debug(f""" - {dag_file}""")


def trigger_dags(data, args):
    logging.info(f"""Trigger DAGs""")
    for run_id, value in data.items():
        dag_id = gen_dag_id(value["tool"])
        logging.debug(f""" - {dag_id}: {run_id}""")
        job = load_job(value["job"])
        job.update({"output_folder": get_folder(os.path.join(args.output, run_id))})
        r = requests.post(url=urljoin(args.endpoint, f"""/api/experimental/dags/{dag_id}/dag_runs"""),
                          json={
                              "run_id": run_id,
                              "conf": dumps({"job": job})
                          })


def main(argsl=None):
    if argsl is None:
        argsl = sys.argv[1:]
    args,_ = get_parser().parse_known_args(argsl)
    args = normalize_args(args, ["port", "endpoint", "debug", "quiet"])

    # Set logger level
    if args.debug:
        reset_root_logger(logging.DEBUG)
    elif args.quiet:
        reset_root_logger(logging.ERROR)
    else:
        reset_root_logger(logging.INFO)

    # Load data
    data_dict = load_data(args)
    queue = Queue(maxsize=len(data_dict))

    # Create dags in DAGS_FOLDER
    export_dags(data_dict)

    # Start status update listener
    listener = get_listener_thread(queue=queue, port=args.port, daemon=True)
    listener.start()

    # Start checker thread
    checker = get_checker_thread(data=data_dict, daemon=False)
    checker.start()

    # Trigger all dags
    trigger_dags(data_dict, args)

    # Wait until all triggered dags return results
    checker.join()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))


