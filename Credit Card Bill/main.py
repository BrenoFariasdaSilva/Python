import atexit # For registering the play_sound function to be called when the program finishes
import os # For checking if the file exists
import pandas as pd # Pandas is used to read and write the CSV files
import platform # For checking the operating system
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

# Execution Constants:
VERBOSE = False # Set to True to output verbose messages

# Sound Constants:
SOUND_COMMANDS = {"Darwin": "afplay", "Linux": "aplay", "Windows": "start"} # The commands to play a sound for each operating system
SOUND_FILE = "./.assets/Sounds/NotificationSound.wav" # The path to the sound file

# RUN_FUNCTIONS:
RUN_FUNCTIONS = {
   "Play Sound": True, # Set to True to play a sound when the program finishes
}

def verbose_output(true_string="", false_string=""):
   """
   Outputs a message if the VERBOSE constant is set to True.

   :param true_string: The string to be outputted if the VERBOSE constant is set to True.
   :param false_string: The string to be outputted if the VERBOSE constant is set to False.
   :return: None
   """

   if VERBOSE and true_string != "": # If the VERBOSE constant is set to True and the true_string is set
      print(true_string) # Output the true statement string
   elif false_string != "": # If the false_string is set
      print(false_string) # Output the false statement string

def verify_filepath_exists(filepath):
   """
   Verify if a file or folder exists at the specified path.

   :param filepath: Path to the file or folder
   :return: True if the file or folder exists, False otherwise
   """

   verbose_output(f"{BackgroundColors.GREEN}Verifying if the file or folder exists at the path: {BackgroundColors.CYAN}{filepath}{Style.RESET_ALL}") # Output the verbose message

   return os.path.exists(filepath) # Return True if the file or folder exists, False otherwise

def debits_csv_exists(file_name):
	"""
	Verify if the debits CSV file exists.
     
	:param file_name: The name of the file to be verified
	:return: True if the file exists, False otherwise
	"""

	verbose_output(true_string=f"{BackgroundColors.GREEN}Verifying if the {BackgroundColors.CYAN}\"{file_name}\"{BackgroundColors.GREEN} file exists.{Style.RESET_ALL}")

	return os.path.isfile(f"{file_name}") # Return True if the file exists, False otherwise

def remove_rows(df):
	"""
	Remove specified rows from the DataFrame based on the "Estabelecimento" column.
     
	:param df: The DataFrame to filter
	:return: A filtered DataFrame with specified rows removed
	"""

	verbose_output(true_string=f"{BackgroundColors.GREEN}Removing specified rows from the DataFrame.{Style.RESET_ALL}")

	df_filtered = df[df["Estabelecimento"] != "Pagamentos Validos Normais"].copy() # Remove rows where "Estabelecimento" column contains "Pagamentos Validos Normais"

	return df_filtered # Return the filtered DataFrame

def reais_to_float(reais):
	"""
	Convert a string with the format "R$ 1,00" to a float.
     
	:param reais: A string with the format "R$ 1,00"
	:return: A float with the value 1.00
	"""

	verbose_output(true_string=f"{BackgroundColors.GREEN}Converting the string {BackgroundColors.CYAN}\"{reais}\"{BackgroundColors.GREEN} to a float.{Style.RESET_ALL}")

	return float(reais.replace("R$ ", "").replace(".", "").replace(",", ".")) # Return a float with the value 1.00

def get_cash_and_credit_payments(df):
	"""
	Get the number of cash and credit payments from the DataFrame.
     
	:param df: The DataFrame to analyze
	:return: A tuple containing the number of cash payments and credit payments
	"""

	verbose_output(true_string=f"{BackgroundColors.GREEN}Calculating the number of cash and credit payments.{Style.RESET_ALL}")

	cash_payments = df[df["Parcela"] == "-"].shape[0] # Count the number of cash payments (where "Parcela" is "-")
	credit_payments = df[df["Parcela"] != "-"].shape[0] # Count the number of credit payments (where "Parcela" is not "-")

	return cash_payments, credit_payments # Return the number of cash and credit payments

def process_dates(df, date_column_name="Data", format="%d/%m/%Y"):
	"""
	Process dates in a DataFrame by converting them to datetime objects, sorting, and formatting.
     
	:param df: The DataFrame to process
	:param date_column_name: The name of the column containing date strings (default is "Data")
	:param format: The format of the date strings in the column (default is "%d/%m/%Y")
	:return: A DataFrame with dates converted to datetime objects, sorted by date, and formatted as "dd/mm/yyyy"
	"""

	verbose_output(true_string=f"{BackgroundColors.GREEN}Processing dates in the DataFrame.{Style.RESET_ALL}")

	df[date_column_name] = pd.to_datetime(df[date_column_name], format=format) # Convert the date strings to datetime objects

	df["SecondsSinceEpoch"] = (df[date_column_name] - pd.Timestamp("01-01-1970")).dt.total_seconds() # Calculate seconds since the Unix epoch for each date

	sorted_df = df.sort_values(by="SecondsSinceEpoch", ascending=True) # Sort the DataFrame by the "SecondsSinceEpoch" column in ascending order

	sorted_df.drop("SecondsSinceEpoch", axis=1, inplace=True) # Remove the "SecondsSinceEpoch" column if it's no longer needed

	sorted_df["Data"] = sorted_df["Data"].dt.strftime("%d/%m/%Y") # Change the data format from "yyyy-mm-dd" to "dd/mm/yyyy"

	return sorted_df # Return the sorted DataFrame

def play_sound():
   """
   Plays a sound when the program finishes.

   :return: None
   """

   if verify_filepath_exists(SOUND_FILE): # If the sound file exists
      if platform.system() in SOUND_COMMANDS: # If the platform.system() is in the SOUND_COMMANDS dictionary
         os.system(f"{SOUND_COMMANDS[platform.system()]} {SOUND_FILE}") # Play the sound
      else: # If the platform.system() is not in the SOUND_COMMANDS dictionary
         print(f"{BackgroundColors.RED}The {BackgroundColors.CYAN}platform.system(){BackgroundColors.RED} is not in the {BackgroundColors.CYAN}SOUND_COMMANDS dictionary{BackgroundColors.RED}. Please add it!{Style.RESET_ALL}")
   else: # If the sound file does not exist
      print(f"{BackgroundColors.RED}Sound file {BackgroundColors.CYAN}{SOUND_FILE}{BackgroundColors.RED} not found. Make sure the file exists.{Style.RESET_ALL}")

def main():
	"""
   Main function.

   :return: None
   """
   
	print(f"{BackgroundColors.CLEAR_TERMINAL}{BackgroundColors.BOLD}{BackgroundColors.GREEN}Welcome to {BackgroundColors.CYAN}Credit Card Bill{BackgroundColors.GREEN}!{Style.RESET_ALL}", end="\n\n") # Print the welcome message
	
	verify_filepath_exists(f"{INPUT_CSV_FOLDER}") # Verify if the input folder exists
      
	if not debits_csv_exists(f"{INPUT_CSV_FILE}"): # Verify if the "debits.csv" file exists
		print(f"{BackgroundColors.RED}The file {BackgroundColors.CYAN}\"{INPUT_CSV_FILE}\"{BackgroundColors.RED} does not exist inside the {BackgroundColors.CYAN}\"{INPUT_CSV_FOLDER}\"{BackgroundColors.RED} folder.{Style.RESET_ALL}")
		exit(1) # Exit the program if the file does not exist
	
	df = pd.read_csv(f"{INPUT_CSV_FILE}", sep=";") # Read the CSV file using the ";" delimiter

	filtered_df = remove_rows(df) # Remove specified rows from the dataframe

	filtered_df["Valor"] = filtered_df["Valor"].apply(reais_to_float) # Apply the function that converts the "Valor" column to a float

	filtered_df.to_csv(f"{OUTPUT_CSV_FILE}", sep=",", index=False) # Write it to the CSV file using the comma separator

	sorted_df = process_dates(filtered_df, "Data", "%d/%m/%Y") # Process the dates and sort the DataFrame

	sorted_df["Sum"] = sorted_df["Valor"].cumsum().round(2) # Calculate the cumulative sum of the "Valor" column and round it to 2 decimal places

	sorted_df.to_csv(f"{OUTPUT_CSV_FILE}", sep=",", index=False) # Write the DataFrame with comma separator

	cash_payments, credit_payments = get_cash_and_credit_payments(sorted_df) # Get the number of Cash payments and the number of Credit payments

	# Print the total sum of the "Valor" column
	print(f"{BackgroundColors.GREEN}Total Sum of the {BackgroundColors.CYAN}\"Valor\"{BackgroundColors.GREEN} column: {BackgroundColors.CYAN}R$ {sorted_df['Valor'].sum():.2f}{BackgroundColors.GREEN}.{Style.RESET_ALL}")
	print(f"{BackgroundColors.GREEN}Total Purchases: {BackgroundColors.CYAN}{sorted_df.shape[0]}{BackgroundColors.GREEN}. Cash Payments: {BackgroundColors.CYAN}{cash_payments}{BackgroundColors.GREEN}. Credit Payments: {BackgroundColors.CYAN}{credit_payments}{BackgroundColors.GREEN}.{Style.RESET_ALL}", end="\n\n")
	print(f"{BackgroundColors.BOLD}{BackgroundColors.GREEN}Execution finished.{Style.RESET_ALL}", end="\n\n")
   
	atexit.register(play_sound) if RUN_FUNCTIONS["Play Sound"] else None # Register the play_sound function to be called when the program finishes
 
if __name__ == "__main__":
   """
   This is the standard boilerplate that calls the main() function.

   :return: None
   """

   main() # Call the main function
