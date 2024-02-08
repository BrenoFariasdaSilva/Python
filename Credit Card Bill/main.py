import pandas as pd # Pandas is used to read and write the CSV files
import os # For checking if the file exists
from colorama import Style # For coloring the terminal

# Macros:
class BackgroundColors: # Colors for the terminal
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

# @brief: This function removes specified rows from the DataFrame
# @param: df is a DataFrame
# @return: A filtered DataFrame
def remove_rows(df):
	# Remove rows where "Estabelecimento" column contains "Pagamentos Validos Normais"
	df_filtered = df[df["Estabelecimento"] != "Pagamentos Validos Normais"].copy()

	return df_filtered # Return the filtered DataFrame

# @brief: This function converts a string with the format "R$ 1,00" to a float
# @param: reais is a string with the format "R$ 1,00"
# @return: a float with the value 1
def reais_to_float(reais):
	return float(reais.replace("R$ ", "").replace(".", "").replace(",", "."))

# @brief: This function gets the cash and credit payments from the DataFrame
# @param: df is a DataFrame
# @return: The number of cash and credit payments
def get_cash_and_credit_payments(df):
	cash_payments = df[df["Parcela"] == "-"].shape[0]
	credit_payments = df[df["Parcela"] != "-"].shape[0]

	return cash_payments, credit_payments # Return the number of cash and credit payments

# @brief: This is the main function.
# @param: None
# @return: None
def main():
	print(f"{BackgroundColors.CLEAR_TERMINAL}{BackgroundColors.BOLD}{BackgroundColors.GREEN}Welcome to {BackgroundColors.CYAN}Credit Card Bill{BackgroundColors.GREEN}!{Style.RESET_ALL}", end="\n\n") # Print the welcome message
	
	# Verify if the "Bills" folder exists
	verify_bills_folder()

	# Verify if the "debits.csv" file exists
	if not debits_csv_exists(f"{INPUT_CSV_FILE}"):
		print(f"{BackgroundColors.RED}The file {BackgroundColors.CYAN}\"{INPUT_CSV_FILE}\"{BackgroundColors.RED} does not exist inside the {BackgroundColors.CYAN}\"{INPUT_CSV_FOLDER}\"{BackgroundColors.RED} folder.{Style.RESET_ALL}")
		exit(1)
	
	# Read the CSV file using the ";" delimiter
	df = pd.read_csv(f"{INPUT_CSV_FILE}", sep=";")

	# Remove specified rows from the dataframe
	filtered_df = remove_rows(df)

	# Apply the function that converts the "Valor" column to a float
	filtered_df["Valor"] = filtered_df["Valor"].apply(reais_to_float)

	# Write it to the CSV file using the comma separator
	filtered_df.to_csv(f"{OUTPUT_CSV_FILE}", sep=",", index=False)

	# Convert the "Data" column to datetime objects assuming the format is "dd/mm/yyyy"
	filtered_df["Data"] = pd.to_datetime(filtered_df["Data"], format='%d/%m/%Y')
	filtered_df["Data"] = filtered_df["Data"].dt.strftime('%d/%m/%Y')

	# Sort the DataFrame by the "Data" column in ascending order
	filtered_df = filtered_df.sort_values(by="Data", ascending=True)

	# Calculate the cumulative sum of the "Valor" column
	filtered_df["Sum"] = filtered_df["Valor"].cumsum()

	# Round the "Sum" column to 3 decimal places
	filtered_df["Sum"] = filtered_df["Sum"].round(3)

	# Write the DataFrame with comma separator
	filtered_df.to_csv(f"{OUTPUT_CSV_FILE}", sep=",", index=False)

	# Get the number of Cash payments and the number of Credit payments
	cash_payments, credit_payments = get_cash_and_credit_payments(filtered_df)

	# Print the total sum of the "Valor" column
	print(f"{BackgroundColors.GREEN}Total Sum of the {BackgroundColors.CYAN}\"Valor\"{BackgroundColors.GREEN} column: {BackgroundColors.CYAN}R$ {filtered_df['Valor'].sum():.2f}{BackgroundColors.GREEN}.{Style.RESET_ALL}")
	print(f"{BackgroundColors.GREEN}Total Purchases: {BackgroundColors.CYAN}{filtered_df.shape[0]}{BackgroundColors.GREEN}.{Style.RESET_ALL}")
	print(f"{BackgroundColors.GREEN}Total Cash Payments: {BackgroundColors.CYAN}{cash_payments}{BackgroundColors.GREEN}.{Style.RESET_ALL}")
	print(f"{BackgroundColors.GREEN}Total Credit Payments: {BackgroundColors.CYAN}{credit_payments}{BackgroundColors.GREEN}.{Style.RESET_ALL}", end="\n\n")

	print(f"{BackgroundColors.BOLD}{BackgroundColors.GREEN}Execution finished.{Style.RESET_ALL}", end="\n\n")
 
# This is the standard boilerplate that calls the main() function
if __name__ == "__main__":
	main() # Call the main function
