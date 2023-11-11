# Python program to generate word vectors using Word2Vec

from gensim.models import Word2Vec # Importing Word2Vec from gensim
import gensim # Importing gensim for the Word2Vec model
import nltk # Importing nltk for the tokenization
from nltk.tokenize import sent_tokenize, word_tokenize # Importing sent_tokenize and word_tokenize from nltk.tokenize
from getTitles import * # Import the getTitles function
from getIssuesCounter import * # Import the getIssuesCounter function
import warnings # Importing warnings to ignore any warnings

nltk.download("punkt") # Download the punkt package
warnings.filterwarnings(action="ignore") # Ignore any warnings

quantityOfissueTitlesToRead = 0 # The quantity of issue titles to read
numberOfSimilarissueTitles = 5 # The number of similar issue titles to find
issues_filepath = "./jabref/issues.json" # The filepath of the issues.json file

print(f"Number of Issues: {getIssuesCounter(issues_filepath)}") # Print the number of issues
issueTitles = getTitles(quantityOfissueTitlesToRead, issues_filepath) # Get the issue titles
mostSimilarIssueTitles = [] # Initialize the list of the most similar issue titles

data = [] # Initialize the list of words

# Tokenize the Sentence Into Words
for issue in issueTitles:
	data.append(word_tokenize(issue.lower()))

# Create CBOW model
CBOWModel = gensim.models.Word2Vec(data, min_count=1, vector_size=100, window=5)

for currentTitle in issueTitles:
	temp = []
	for similarTitle in issueTitles:
		if currentTitle == similarTitle:
			continue
		similarity = CBOWModel.wv.n_similarity([currentTitle], [similarTitle])
		if similarity > 0.0:
			if len(temp) <= numberOfSimilarissueTitles:
				temp.append((similarity, similarTitle))
			else:
				temp.sort(reverse=True)
				if similarity > temp[0][0]:
					temp[0] = ((similarity, similarTitle))

	temp.sort(reverse=True)
	mostSimilarIssueTitles.append(temp[0:numberOfSimilarissueTitles])

for idx,issue in enumerate(issueTitles):
	for similarIssue in mostSimilarIssueTitles:
		if (similarIssue.__len__() == 0):
			continue
		print(f'Issue Nº{idx}: "{issue}" Similar to "{similarIssue[0][1]}" - similarity = {similarIssue[0][0]}')
	print()
