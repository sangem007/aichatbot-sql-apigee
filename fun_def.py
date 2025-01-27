from google.cloud import bigquery
import json

BIGQUERY_DATASET_ID = "iInsights_analytic_logs"
client = bigquery.Client()
def list_datasets(msg,req_res,params):
    api_response = client.list_datasets()
    api_response = BIGQUERY_DATASET_ID
    req_res.append(
        [msg.tool_calls[0].function.name, params, api_response]
    )
    return api_response,req_res

def list_tables(msg,req_res,params):
    try:
        api_response = client.list_tables(BIGQUERY_DATASET_ID)
        api_response = str([table.table_id for table in api_response])
        req_res.append(
            [msg.tool_calls[0].function.name, params, api_response]
        )
    except Exception as e:
        api_response = f"{str(e)}"
        api_response = api_response.replace("\\", "").replace("\n", "")
        req_res.append(
            [msg.tool_calls[0].function.name, params, api_response]
        )
    return api_response,req_res

def get_table(msg,req_res,params):
    try:
        api_response = client.get_table(params["table_id"])
        api_response = api_response.to_api_repr()
        req_res.append(
            [
                msg.tool_calls[0].function.name,
                params,
                [
                    str(api_response.get("description", "")),
                    str(
                        [
                            column["name"]
                            for column in api_response["schema"]["fields"]
                        ]
                    ),
                ],
            ]
        )
        api_response = str(api_response)
    except Exception as e:
        api_response = f"{str(e)}"
        api_response = api_response.replace("\\", "").replace("\n", "")
        req_res.append(
            [msg.tool_calls[0].function.name, params, api_response]
        )
    return api_response,req_res

def sql_query(msg,req_res,params):
    job_config = bigquery.QueryJobConfig(
        maximum_bytes_billed=100000000
    )  # Data limit per query job
    try:
        cleaned_query = (
            params["query"]
            .replace("\\n", " ")
            .replace("\n", "")
            .replace("\\", "")
        )
        query_job = client.query(cleaned_query, job_config=job_config)
        api_response = query_job.result()
        api_response = str([dict(row) for row in api_response])
        api_response = api_response.replace("\\", "").replace("\n", "")
        req_res.append(
            [msg.tool_calls[0].function.name, params, api_response]
        )
    except Exception as e:
        api_response = f"{str(e)}"
        api_response = api_response.replace("\\", "").replace("\n", "")
        req_res.append(
            [msg.tool_calls[0].function.name, params, api_response]
        )
    return api_response,req_res

definitions = [
    {
        "type": "function",
        "function": {
            "name":"list_datasets",
            "description":"Get a list of datasets that will help answer the user's question",
            "parameters":{
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name":"list_tables",
            "description":"List tables in a dataset that will help answer the user's question",
            "parameters":{
                "type": "object",
                "properties": {
                    "dataset_id": {
                        "type": "string",
                        "description": "Dataset ID to fetch tables from."
                    }
                },
                "required": ["dataset_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name":"get_table",
            "description":"Get information about a table, including the description, schema, and number of rows that will help answer the user's question. Always use the fully qualified dataset and table names. Execute this function for all table_id.",
            "parameters":{
                "type": "object",
                "properties": {
                    "table_id": {
                        "type": "string",
                        "description": "Fully qualified ID of the table to get information about"
                    }
                },
                "required": ["table_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name":"sql_query",
            "description":"Get information from data in BigQuery using SQL queries. Always execute this function after all get_table functions are executed.",
            "parameters":{
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "SQL query on a single line that will help give quantitative answers to the user's question when run on a BigQuery dataset and table. In the SQL query, always use the fully qualified dataset and table names. Unless explicitly asked about specific error types consider all errors in the SQL query, consider 3xx status codes in success. TIMESTAMP_SUB does not support the MONTH date part when the argument is TIMESTAMP type in Bigquery so use DAYS in stead of MONTHS while building query."
                    }
                },
                "required": ["query"]
            }
        }
    }
]