from dagster import asset

def execute_query(query: str) -> None:
    print(f"Executing query: {query}")

@asset
def upstream_asset() -> None:
    execute_query("CREATE TABLE sugary_cereals AS SELECT * FROM cereals")

@asset(non_argument_deps={"upstream_asset"})
def downstream_asset() -> None:
    execute_query("CREATE TABLE shopping_list AS SELECT * FROM sugary_cereals")
    
# In this example, Dagster doesn’t need to load data from upstream_asset to successfully compute the downstream_asset.
# While downstream_asset does depend on upstream_asset, the key difference with non_argument_deps is that data isn’t being passed between the functions.
# Specifically, the data from the sugary_cereals table isn't being passed as an argument to downstream_asset.