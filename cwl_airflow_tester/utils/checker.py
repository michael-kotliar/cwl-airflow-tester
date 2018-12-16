import threading
import logging
import socketserver
import queue
from http.server import SimpleHTTPRequestHandler
from json import dumps, loads
from cwltest.utils import compare, CompareFail

RESULTS_QUEUE = None

class Handler(SimpleHTTPRequestHandler):
    def do_POST(self):
        self.send_response(200)
        self.end_headers()
        headers = self.headers
        payload = loads(self.rfile.read(int(self.headers['Content-Length'])).decode("UTF-8"))["payload"]
        if "results" in payload or payload["state"] == "failed":
            RESULTS_QUEUE.put({
                "run_id":  payload["run_id"],
                "dag_id":  payload["dag_id"],
                "results": payload.get("results", {})
            })


def start_status_updates_daemon(queue, port=8080):
    global RESULTS_QUEUE
    RESULTS_QUEUE = queue
    httpd = socketserver.TCPServer(("", port), Handler)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()


def check_result(test_data):
    processed = 0
    while processed < len(test_data):
        try:
            item = RESULTS_QUEUE.get()
        except queue.Empty:
            continue
        processed = processed + 1
        try:
            controls = [i for i in test_data if i["run_id"] == item["run_id"]][0]
            # print(dumps(controls, indent=4))
            # print(dumps(item["results"], indent=4))
            compare(controls.get("output"), item["results"])
            logging.warning("Test Ok")
        except CompareFail as ex:
            logging.warning("Test failed")
            logging.warning(f"Compare failure {ex}")


def get_checker_thread(test_data):
    t = threading.Thread(target=check_result, kwargs={"test_data": test_data})
    t.start()
    return t
