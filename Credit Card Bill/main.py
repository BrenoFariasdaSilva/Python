import pandas as pd # Pandas is used to read and write the CSV files
from colorama import Style # For coloring the terminal

# Macros:
class backgroundColors: # Colors for the terminal
	CYAN = "\033[96m" # Cyan
	GREEN = "\033[92m" # Green
	YELLOW = "\033[93m" # Yellow
	RED = "\033[91m" # Red

# @brief: This function converts a string with the format "R$ 1,00" to a float
# @param: reais is a string with the format "R$ 1,00"
# @return: a float with the value 1
def reais_to_float(reais):
	return float(reais.replace("R$ ", "").replace(",", ".").strip())

# @brief: This is the main function.
# @param: None
# @return: None
def main():
	# Read the CSV file using the ";" delimiter
	df = pd.read_csv("debits.csv", delimiter=";")

	# Remove any row in the "Valor" column starting with "R$ -"
	df = df[~df["Valor"].str.startswith("R$ -")]

	# Apply the function to the "Valor" column
	df["Valor"] = df["Valor"].apply(reais_to_float)

	# Convert the "Data" column to datetime objects assuming the format is "dd/mm/yyyy"
	df["Data"] = pd.to_datetime(df["Data"], format="%d/%m/%Y")

	# Sort the DataFrame by the "Data" column in ascending order
	df = df.sort_values(by="Data")

	# Calculate the cumulative sum of the "Valor" column
	df["Sum"] = df["Valor"].cumsum()

	# Round the "Sum" column to 3 decimal places
	df["Sum"] = df["Sum"].round(3)

	# Write the DataFrame with comma separator
	df.to_csv("debits_sum.csv", sep=",", index=False)

	# Print the total sum of the "Valor" column
	print(f"{backgroundColors.GREEN}Total sum of the \"Valor\" column: {backgroundColors.CYAN}R$ {df['Valor'].sum():.2f}{backgroundColors.GREEN}.{Style.RESET_ALL}")
 
# @brief: This is the standard boilerplate that calls the main() function.
if __name__ == "__main__":
	main()