import requests
import unittest
from concurrent.futures import ThreadPoolExecutor, as_completed
import io
import time


# Make sure this is the right web address
server_url = "http://127.0.0.1:8000"

# This is some test input data for the individual runs
test_input = {'luminosity': 100000, 'teff': 30000, 'mstar': 15, 'zscale': 0.5,
              'abundances': {'H': 0.7440796, 'HE': 0.249248650077, 'LI': 2.84352661e-11,
                             'BE': 7.90803641e-11, 'B': 1.98191714e-09, 'C': 0.00118248706,
                             'N': 0.000346387617, 'O': 0.00286640275, 'F': 2.52304529e-07,
                             'NE': 0.000628258526, 'NA': 1.46135656e-06, 'MG': 0.000353926315,
                             'AL': 2.78157879e-05, 'SI': 0.000332423454, 'P': 2.91215526e-06,
                             'S': 0.0001546187, 'CL': 4.10081545e-06, 'AR': 3.67039048e-05,
                             'K': 1.53239868e-06, 'CA': 3.20717951e-05, 'SC': 2.322767e-08,
                             'TI': 1.5608866e-06, 'V': 1.58593241e-07, 'CR': 8.30208474e-06,
                             'MN': 5.40866488e-06, 'FE': 0.000645977033, 'CO': 2.10656939e-06,
                             'NI': 3.56271711e-05, 'CU': 3.60002531e-07, 'ZN': 8.68417369e-07},
              'email': '', 'expert_mode': True}


def calc_single_model():
    """Sends a request to calculate a single mass-loss rate. """
    return requests.post(f"{server_url}/process_data", json=test_input)


def calc_model_grid():
    """Sends a request to calculate a set of mass-loss rates based on an input csv-file"""
    file_path = 'test_sample.csv'
    with open(file_path, 'r') as file:
        file_content = file.read()
    fake_file = io.BytesIO(file_content.encode())
    return requests.post(f"{server_url}/upload_csv",
                         data={"email": "e@mail.com"},
                         files={"file": ("test_sample.csv", fake_file, "text/csv")})


class TestLimeServer(unittest.TestCase):

    def test_single_model(self):
        """
        Tests if a single mass loss rate can be calculated.
        """
        response = calc_single_model()
        task_id = response.json().get("task_id")
        timeout = 60
        start_time = time.time()
        while True:
            status_response = requests.get(f"{server_url}/task_status/{task_id}")
            status_data = status_response.json()
            if status_data["status"] in ["SUCCESS", "FAILURE"]:
                break
            if time.time() - start_time > timeout:
                raise TimeoutError(f"It took longer than {timeout} seconds, that is too long!")
            time.sleep(0.1)

        # This is still a very basic check now. As long as it thinks it was a success it is all good.
        self.assertEqual(status_data["status"],"SUCCESS")

    def test_multiple_models(self):
        """
        Does the single model test, but multiple at once, preferably more than the number of workers to stress test
        the server a little.
        """
        n_requests = 500  # Put in many requests at once (more than the expected number of workers of the server)
        with ThreadPoolExecutor(max_workers=n_requests) as executor:
            futures = [executor.submit(calc_single_model) for _ in range(n_requests)]
            results = [future.result() for future in as_completed(futures)]

        timeout = 600
        start_time = time.time()
        n_success = 0
        while True:
            for res in results:

                task_id = res.json().get("task_id")
                status_response = requests.get(f"{server_url}/task_status/{task_id}")
                status_data = status_response.json()
                if status_data["status"] in ["SUCCESS", "FAILURE"]:
                    self.assertEqual(status_data["status"], "SUCCESS")
                    n_success += 1
                    results.remove(res)
            if n_success == n_requests:
                break
            if time.time() - start_time > timeout:
                raise TimeoutError(f"It took longer than {timeout} seconds, that is too long!")
            time.sleep(0.1)

    # NOTE: This is a flawed test, it does not work properly as it does not require models to be calculated.
    # It only waits for the server response, which is (nearly) instant. Though it likely causes the other tests to fail
    # as they get stuck in a "queue" waiting for a response that doesn't come. We would need a proper queue system for
    # this.
    def test_csv_grid_run(self):
        """Tests if a single grid of models can be successfully be computed"""
        response = calc_model_grid()
        self.assertEqual(response.status_code, 200)

    # NOTE: This is a flawed test, it does not work properly as it does not require models to be calculated.
    # It only waits for the server response, which is (nearly) instant. Therefore, it does not test the "overloading"
    # of the server.
    def test_many_csv_grid_runs(self):
        """Tests if a many grids of models can be successfully be computed"""
        n_requests = 4  # Put in many requests at once
        with ThreadPoolExecutor(max_workers=n_requests) as executor:
            futures = [executor.submit(calc_model_grid) for _ in range(n_requests)]
            results = [future.result() for future in as_completed(futures)]

        for result in results:
            self.assertEqual(result.status_code, 200)


if __name__ == "__main__":
    unittest.main()