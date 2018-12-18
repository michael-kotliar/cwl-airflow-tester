# cwl-airflow-tester

### Keep in mind

- Travis is configured to build and deploy on commits from `master` branch. To avoid
  deploying on every commit, use another branch for development and then merge it to
  `master`. Then, only last commit from `master` will be built.
- `cwl-airflow-tester` doesn't depend on `cwl-airflow-parser`. But `DAG_TEMPLATE` constant in
  `main.py` does. In future, it should be read from the text file.
- `cwltest` version is fixed to `1.0.20180601100346` in order to avoid possible changes of
   `cwltest.utils.compare` function.
- `cwltool` version is not fixed, because only few function are used from `cwltool.load_tool`
   and they are not likely to be changed.
- `schema_salad` is not set as dependency, because it will be installed with `cwltool`.
- if `--spin` is provided, the spinner will be displayed. This feature is useful when running tests
  on Travis (if there is no outputs more then 10 min Travis might kill the job).
- 
