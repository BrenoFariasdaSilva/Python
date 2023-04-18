import requests # import the `requests` library
from dagster import asset # import the `dagster` library
import pandas as pd # Add new imports to the top of `assets.py`

@asset # add the asset decorator to tell Dagster this is an asset
def topstories(topstory_ids): #this asset is dependent on topstory_ids 
	results = [] # create an empty list
	for item_id in topstory_ids: # loop through the top 100 stories
		item = requests.get(f"https://hacker-news.firebaseio.com/v0/item/{item_id}.json").json() # get the story
		results.append(item) # append the story to the list

		if len(results) % 20 == 0: # print the number of stories we have so far
			print(f"Got {len(results)} items so far.") # print the number of stories we have so far

	dataframe = pd.DataFrame(results) # create a dataframe from the list

	return dataframe # return the dataframe