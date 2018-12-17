# cwl-airflow-tester

### Automatic deployment on Pypi

- Travis is configured to build and deploy every commit from `master` branch, so
  all development should be made in `devel` branch and then merged to `master`.
  If there are more then one commits merged into `master`, Travis will build and deploy
  only the last one