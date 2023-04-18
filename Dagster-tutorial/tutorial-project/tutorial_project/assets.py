import requests # import the `requests` library
from dagster import asset # import the `dagster` library

@asset # add the asset decorator to tell Dagster this is an asset
def topstory_ids(): # define a function that returns the top 100 stories
	newstories_url = "https://hacker-news.firebaseio.com/v0/topstories.json" # define the URL
	top_new_story_ids = requests.get(newstories_url).json()[:100] # get the top 100 stories
	return top_new_story_ids # return the top 100 stories
