import requests # import the `requests` library
from dagster import AssetIn, asset # import the `dagster` library
import pandas as pd # Add new imports to the top of `assets.py`

@asset # add the asset decorator to tell Dagster this is an asset
def topstory_ids(): # define a function that returns the top 100 stories
	newstories_url = "https://hacker-news.firebaseio.com/v0/topstories.json" # define the URL
	top_new_story_ids = requests.get(newstories_url).json()[:100] # get the top 100 stories
	return top_new_story_ids # return the top 100 stories

# @asset(ins={"topstory_ids": AssetIn(topstory_ids)}) # add the asset decorator to tell Dagster this is an asset,
# and add the `ins` argument to tell Dagster that this asset depends on the `topstory_ids` asset
@asset
def topstories(topstory_ids): #this asset is dependent on topstory_ids
    results = []
    for item_id in topstory_ids:
        item = requests.get(f"https://hacker-news.firebaseio.com/v0/item/{item_id}.json").json()
        results.append(item)

        if len(results) % 20 == 0:
            print(f"Got {len(results)} items so far.")

    df = pd.DataFrame(results)

    return df
