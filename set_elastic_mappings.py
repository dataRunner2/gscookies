from elasticsearch import Elasticsearch

# Connect to Elasticsearch
es = Elasticsearch("http://localhost:9200")  # Adjust to your Elasticsearch URL

# Define the index name
index_name = "scout_transactions"

# Define the mapping for the index
mapping = {
    "mappings": {
        "properties": {
            "scoutName": {"type": "text"},
            "scoutId": {"type": "keyword"},
            "amountReceived": {"type": "float"},
            "amtReceived_dt": {"type": "date"},  # Date in ISO8601 format
            "orderRef_id": {"type": "text"}
        }
    }
}

# Create the index
if not es.indices.exists(index=index_name):
    es.indices.create(index=index_name, body=mapping)
    print(f"Index '{index_name}' created successfully!")
else:
    print(f"Index '{index_name}' already exists.")
