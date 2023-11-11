import pandas as pd # Pandas is used to read and write the CSV files
import os # For checking if the file exists
from colorama import Style # For coloring the terminal

# Macros:
class backgroundColors: # Colors for the terminal
	CYAN = "\033[96m" # Cyan
	GREEN = "\033[92m" # Green
	YELLOW = "\033[93m" # Yellow
	RED = "\033[91m" # Red
	BOLD = "\033[1m" # Bold
	UNDERLINE = "\033[4m" # Underline
	CLEAR_TERMINAL = "\033[H\033[J" # Clear the terminal

# Constants:
INPUT_CSV_FOLDER = "Bills" # The folder where the CSV files are located
INPUT_CSV_FILENAME = "debits.csv" # The CSV file to be read
INPUT_CSV_FILE = f"{INPUT_CSV_FOLDER}/{INPUT_CSV_FILENAME}" # The CSV file to be read
OUTPUT_CSV_FILENAME = "debits_sum.csv" # The CSV file to be written
OUTPUT_CSV_FILE = f"{INPUT_CSV_FOLDER}/{OUTPUT_CSV_FILENAME}" # The CSV file to be written

# @brief: This function verifies if the /Bills folder exists, if not, it creates it.
# @param: None
# @return: None
def verify_bills_folder():
	if not os.path.isdir(f"{INPUT_CSV_FOLDER}"):
		os.mkdir(f"{INPUT_CSV_FOLDER}")

# @brief: This function verifies if the debits csv file exists.
# @param: file_name is the name of the file to be verified
# @return: True if the file exists, False otherwise
def debits_csv_exists(file_name):
	return os.path.isfile(f"{file_name}")

# @brief: This function converts a string with the format "R$ 1,00" to a float
# @param: reais is a string with the format "R$ 1,00"
# @return: a float with the value 1
def reais_to_float(reais):
	return float(reais.replace("R$ ", "").replace(",", ".").strip())

# @brief: This is the main function.
# @param: None
# @return: None
def main():
	# Verify if the "Bills" folder exists
	verify_bills_folder()

	# Verify if the "debits.csv" file exists
	if not debits_csv_exists(f"{INPUT_CSV_FILE}"):
		print(f"{backgroundColors.RED}The file {backgroundColors.CYAN}\"{INPUT_CSV_FILE}\"{backgroundColors.RED} does not exist inside the {backgroundColors.CYAN}\"{INPUT_CSV_FOLDER}\"{backgroundColors.RED} folder.{Style.RESET_ALL}")
		exit(1)
	
	# Read the CSV file using the ";" delimiter
	df = pd.read_csv(f"{INPUT_CSV_FILE}", sep=";")

	# Remove any row in the "Valor" column starting with "R$ -"
	df = df[~df["Valor"].str.startswith("R$ -")]

	# Apply the function to the "Valor" column
	df["Valor"] = df["Valor"].apply(reais_to_float)

	# Convert the "Data" column to datetime objects assuming the format is "dd/mm/yyyy"
	df["Data"] = pd.to_datetime(df["Data"], format="%d/%m/%Y")
	df["Data"] = df["Data"].dt.strftime('%m/%d/%Y')

	# Sort the DataFrame by the "Data" column in ascending order
	df = df.sort_values(by="Data")

	# Calculate the cumulative sum of the "Valor" column
	df["Sum"] = df["Valor"].cumsum()

	# Round the "Sum" column to 3 decimal places
	df["Sum"] = df["Sum"].round(3)

	# Write the DataFrame with comma separator
	df.to_csv(f"{OUTPUT_CSV_FILE}", sep=",", index=False)

	# Print the total sum of the "Valor" column
	print(f"{backgroundColors.GREEN}Total sum of the \"Valor\" column: {backgroundColors.CYAN}R$ {df['Valor'].sum():.2f}{backgroundColors.GREEN}.{Style.RESET_ALL}")
 
# @brief: This is the standard boilerplate that calls the main() function.
if __name__ == "__main__":
	main()