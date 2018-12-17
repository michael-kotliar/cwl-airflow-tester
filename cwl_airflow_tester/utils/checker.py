import threading
import logging
import socketserver
import queue
from http.server import SimpleHTTPRequestHandler
from json import dumps, loads
from cwltest.utils import compare, CompareFail

from cwl_airflow_tester.utils.mute import Mute


RESULTS_QUEUE = None

class CustomHandler(SimpleHTTPRequestHandler):
    def do_POST(self):
        with Mute():  # Suppress output
            self.send_response(200)
        self.end_headers()
        headers = self.headers
        payload = loads(self.rfile.read(int(self.headers['Content-Length'])).decode("UTF-8"))["payload"]
        if "results" in payload or payload["state"] == "failed":
            RESULTS_QUEUE.put({
                "run_id":  payload["run_id"],
                "dag_id":  payload["dag_id"],
                "state":   payload["state"],
                "results": payload.get("results", None)
            })


def get_listener_thread(queue, port, daemon):
    global RESULTS_QUEUE
    RESULTS_QUEUE = queue
    httpd = socketserver.TCPServer(("", port), CustomHandler)
    return threading.Thread(target=httpd.serve_forever, daemon=daemon)


def evaluate_result(data):
    processed = 0
    while processed < len(data):
        try:
            item = RESULTS_QUEUE.get()
        except queue.Empty:
            continue
        processed = processed + 1
        try:
            compare(data[item["run_id"]]["output"], item["results"])
            logging.error(f"""Success - {item["dag_id"]}: {item["run_id"]}""")
        except CompareFail as ex:
            logging.error(f"""Fail    - {item["dag_id"]}: {item["run_id"]}""")
            logging.debug(f""" - {ex}""")


def get_checker_thread(data, daemon):
    return threading.Thread(target=evaluate_result,
                            daemon=daemon,
                            kwargs={"data": data})
