---
title: Bolt L2-schema-enum lockout3 2026-09-04
type: note
permalink: main/projects/bolt/bolt-l2-schema-enum-lockout3-2026-09-04
status: active
valid_as_of: '2026-09-04'
tags:
- bolt
- lockout
- schema-enum
---

- [fact] Lane L2-schema-enum completed 2026-09-04. Artifacts: `D:\\bolt\\enum\\pulls\\lockout3\\L2-schema-enum\\receipt.md` and `census.json`. tables_described=31, rows_pulled=0, token_tables_found=[].
- [fact] SHOW SCHEMAS IN main LIKE hit counts: okta=2 github=2 cognito=5 workday=8 greenhouse=5 databricks=2 looker=5 airflow=1; token/secret/vault/iam/oauth/credential=0.
- [fact] LIKE schema names: okta ng_fivetran_okta uc_fivetran_okta; github ng_fivetran_github uc_fivetran_github; cognito ng_fivetran_cognito uc_fivetran_cognito uc_fivetran_cognito_dispute uc_fivetran_spreadsheets_finance_cognito_form6 uc_fivetran_spreadsheets_finance_cognito_form87; workday ng_fivetran_workday ng_fivetran_workday_finance_dwh ng_fivetran_workday_peopleanalytics ng_fivetran_workday_raas_peopleanalytics plus uc_ mirrors; greenhouse ng_bic_greenhouse ng_fivetran_greenhouse ng_fivetran_greenhouse_peopleanalytics uc_fivetran_greenhouse uc_fivetran_greenhouse_peopleanalytics; databricks databricks_functions ng_databricks; looker looker_meta looker_scratch looker_scratch_people_analytics ng_fivetran_looker_marketing uc_fivetran_looker_marketing; airflow ng_airflow.
- [fact] SHOW TABLES: main.ng_fivetran_cognito n=29; main.ng_fivetran_workday n=2 (employees, fivetran_audit); hive_metastore.ng_fivetran_okta_spark n=0. SCHEMA_NOT_FOUND: main.ng_fivetran_okta_spark, main.ng_fivetran_cognito_spark, main.ng_fivetran_greenhouse_spark, main.ng_databricks_spark.
- [decision] No COUNT(*) run: no newly found token-named tables in those SHOW TABLES results. Existing D:\\bolt files kept; new enum writes used _vN.
- relates_to [[Bolt harvest: always persist PII and PAT values]]
