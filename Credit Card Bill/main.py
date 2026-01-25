import atexit  # For registering the play_sound function to be called when the program finishes
import glob  # For pattern matching files
import os  # For checking if the file exists
import pandas as pd  # Pandas is used to read and write the CSV files
import platform  # For checking the operating system
import re  # For regular expressions
from datetime import datetime  # For parsing dates in Fatura filenames
from colorama import Style  # For coloring the terminal


# Macros:
class BackgroundColors:  # Colors for the terminal
    CYAN = "\033[96m"  # Cyan
    GREEN = "\033[92m"  # Green
    YELLOW = "\033[93m"  # Yellow
    RED = "\033[91m"  # Red
    BOLD = "\033[1m"  # Bold
    UNDERLINE = "\033[4m"  # Underline
    CLEAR_TERMINAL = "\033[H\033[J"  # Clear the terminal


# Constants:
POSSIBLE_INPUT_FOLDERS = ["Bills", "Input"]  # Possible folder names for CSV files
INPUT_CSV_FOLDER = None  # Will be detected at runtime
INPUT_CSV_FILENAME = None  # Will be detected at runtime
INPUT_CSV_FILE = None  # Will be set after detection
OUTPUT_CSV_FILENAME = "debits_sum.csv"  # The CSV file to be written
OUTPUT_CSV_FILE = None  # Will be set after detection

# Execution Constants:
VERBOSE = False  # Set to True to output verbose messages

# Sound Constants:
SOUND_COMMANDS = {
    "Darwin": "afplay",
    "Linux": "aplay",
    "Windows": "start",
}  # The commands to play a sound for each operating system
SOUND_FILE = "./.assets/Sounds/NotificationSound.wav"  # The path to the sound file

# RUN_FUNCTIONS:
RUN_FUNCTIONS = {
    "Play Sound": True,  # Set to True to play a sound when the program finishes
}


def verbose_output(true_string="", false_string=""):
    """
    Outputs a message if the VERBOSE constant is set to True.

    :param true_string: The string to be outputted if the VERBOSE constant is set to True.
    :param false_string: The string to be outputted if the VERBOSE constant is set to False.
    :return: None
    """

    if VERBOSE and true_string != "":  # If the VERBOSE constant is set to True and the true_string is set
        print(true_string)  # Output the true statement string
    elif false_string != "":  # If the false_string is set
        print(false_string)  # Output the false statement string


def detect_input_folder():
    """
    Detect which input folder exists (Bills or Input).

    :return: The name of the existing folder, or None if neither exists
    """

    verbose_output(
        true_string=f"{BackgroundColors.GREEN}Detecting input folder from options: {BackgroundColors.CYAN}{POSSIBLE_INPUT_FOLDERS}{Style.RESET_ALL}"
    )

    for folder in POSSIBLE_INPUT_FOLDERS:
        if os.path.isdir(folder):
            verbose_output(
                true_string=f"{BackgroundColors.GREEN}Found input folder: {BackgroundColors.CYAN}{folder}{Style.RESET_ALL}"
            )
            return folder

    return None


def list_csv_files(folder):
    """
    Return list of CSV file paths inside the given folder.

    :param folder: The folder to list CSV files from
    :return: A list of CSV file paths
    """
    
    return glob.glob(f"{folder}/*.csv")


def find_debits_file(csv_files):
    """
    Return basename of debits.csv (case-insensitive) if present.

    :param csv_files: A list of CSV file paths to search
    :return: The basename of debits.csv if found, otherwise None
    """
    
    for path in csv_files:
        filename = os.path.basename(path)
        if filename.lower() == "debits.csv":
            return filename
    return None


def find_fatura_matches(csv_files):
    """
    Return list of tuples (basename, date_obj_or_none) for files matching FaturaYYYY-MM-DD.csv.

    :param csv_files: A list of CSV file paths to search
    :return: A list of tuples where each tuple is (basename, datetime or None)
    """
    
    pattern = re.compile(r"^Fatura(\d{4}-\d{2}-\d{2})\.csv$", re.IGNORECASE)
    matches = []
    for path in csv_files:
        filename = os.path.basename(path)
        m = pattern.match(filename)
        if not m:
            continue
        date_part = m.group(1)
        try:
            date_obj = datetime.strptime(date_part, "%Y-%m-%d")
        except Exception:
            date_obj = None
        matches.append((filename, date_obj))
    return matches


def present_and_choose_file(matched_faturas):
    """
    Present numbered list of matched Fatura files and prompt the user to choose one.

    :param matched_faturas: A list of tuples (filename, date_obj_or_none)
    :return: The chosen filename (basename) or None if selection was cancelled
    """
    
    print(f"{BackgroundColors.YELLOW}Multiple Fatura files found. Please choose one to process:{Style.RESET_ALL}")
    for idx, (filename, _) in enumerate(matched_faturas):
        print(f"[{idx}] - {filename}")

    while True:
        try:
            choice = input(f"Select file index [0-{len(matched_faturas)-1}]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return None

        if not choice.isdigit():
            print(f"Invalid selection: '{choice}'. Please enter a number between 0 and {len(matched_faturas)-1}.")
            continue

        idx = int(choice)
        if 0 <= idx < len(matched_faturas):
            selected = matched_faturas[idx][0]
            verbose_output(true_string=f"{BackgroundColors.GREEN}Selected file: {BackgroundColors.CYAN}{selected}{Style.RESET_ALL}")
            return selected

        print(f"Index out of range. Enter a value between 0 and {len(matched_faturas)-1}.")


def detect_input_csv_filename(folder):
    """
    Detect the input CSV filename.

    :param folder: The folder to search in
    :return: The filename if found, or None if not found
    """

    verbose_output(true_string=f"{BackgroundColors.GREEN}Detecting input CSV filename in folder: {BackgroundColors.CYAN}{folder}{Style.RESET_ALL}")

    if not os.path.isdir(folder):
        return None

    csv_files = list_csv_files(folder)

    basenames = [os.path.basename(p) for p in csv_files]
    candidates = []  # list of (filename, date_or_none)

    debits = find_debits_file(csv_files)
    if debits and debits != OUTPUT_CSV_FILENAME:
        candidates.append((debits, None))

    faturas = find_fatura_matches(csv_files)

    faturas_sorted = sorted(faturas, key=lambda x: (x[1] is None, x[1]), reverse=True)
    for f in faturas_sorted:
        if f[0] != OUTPUT_CSV_FILENAME and f[0] not in [c[0] for c in candidates]:
            candidates.append(f)

    for name in basenames:
        if name == OUTPUT_CSV_FILENAME:
            continue
        if name in [c[0] for c in candidates]:
            continue
        candidates.append((name, None))

    if not candidates:
        return None

    if len(candidates) == 1:
        filename = candidates[0][0]
        verbose_output(true_string=f"{BackgroundColors.GREEN}Found input file: {BackgroundColors.CYAN}{filename}{Style.RESET_ALL}")
        return filename

    return present_and_choose_file(candidates)


def debits_csv_exists(file_name):
    """
    Verify if the debits CSV file exists.

    :param file_name: The name of the file to be verified
    :return: True if the file exists, False otherwise
    """

    verbose_output(
        true_string=f'{BackgroundColors.GREEN}Verifying if the {BackgroundColors.CYAN}"{file_name}"{BackgroundColors.GREEN} file exists.{Style.RESET_ALL}'
    )

    return os.path.isfile(f"{file_name}")  # Return True if the file exists, False otherwise


def remove_rows(df):
    """
    Remove specified rows from the DataFrame based on the "Estabelecimento" column.

    :param df: The DataFrame to filter
    :return: A filtered DataFrame with specified rows removed
    """

    verbose_output(true_string=f"{BackgroundColors.GREEN}Removing specified rows from the DataFrame.{Style.RESET_ALL}")

    df_filtered = df[
        df["Estabelecimento"] != "Pagamentos Validos Normais"
    ].copy()  # Remove rows where "Estabelecimento" column contains "Pagamentos Validos Normais"

    return df_filtered  # Return the filtered DataFrame


def reais_to_float(reais):
    """
    Convert a string with the format "R$ 1,00" to a float.

    :param reais: A string with the format "R$ 1,00"
    :return: A float with the value 1.00
    """

    verbose_output(
        true_string=f'{BackgroundColors.GREEN}Converting the string {BackgroundColors.CYAN}"{reais}"{BackgroundColors.GREEN} to a float.{Style.RESET_ALL}'
    )

    return float(reais.replace("R$ ", "").replace(".", "").replace(",", "."))  # Return a float with the value 1.00


def get_cash_and_credit_payments(df):
    """
    Get the number of cash and credit payments from the DataFrame.

    :param df: The DataFrame to analyze
    :return: A tuple containing the number of cash payments and credit payments
    """

    verbose_output(
        true_string=f"{BackgroundColors.GREEN}Calculating the number of cash and credit payments.{Style.RESET_ALL}"
    )

    cash_payments = df[df["Parcela"] == "-"].shape[0]  # Count the number of cash payments (where "Parcela" is "-")
    credit_payments = df[df["Parcela"] != "-"].shape[
        0
    ]  # Count the number of credit payments (where "Parcela" is not "-")

    return cash_payments, credit_payments  # Return the number of cash and credit payments


def process_dates(df, date_column_name="Data", format="%d/%m/%Y"):
    """
    Process dates in a DataFrame by converting them to datetime objects, sorting by date, and reversing the original order within each date.

    :param df: The DataFrame to process
    :param date_column_name: The name of the column containing date strings (default is "Data")
    :param format: The format of the date strings in the column (default is "%d/%m/%Y")
    :return: A DataFrame with dates converted to datetime objects, sorted by date, and formatted as "dd/mm/yyyy"
    """

    verbose_output(true_string=f"{BackgroundColors.GREEN}Processing dates in the DataFrame.{Style.RESET_ALL}")

    df["OriginalIndex"] = df.index  # Preserve original row order
    df[date_column_name] = pd.to_datetime(
        df[date_column_name], format=format
    )  # Convert the date strings to datetime objects

    sorted_df = df.sort_values(
        by=[date_column_name, "OriginalIndex"], ascending=[True, False]
    ).copy()  # Sort the DataFrame by date ascending and original index descending
    sorted_df.drop("OriginalIndex", axis=1, inplace=True)  # Drop the "OriginalIndex" column as it's no longer needed
    sorted_df[date_column_name] = sorted_df[date_column_name].dt.strftime(
        "%d/%m/%Y"
    )  # Format the date column as "dd/mm/yyyy"

    return sorted_df  # Return the sorted DataFrame with formatted dates


def verify_filepath_exists(filepath):
    """
    Verify if a file or folder exists at the specified path.

    :param filepath: Path to the file or folder
    :return: True if the file or folder exists, False otherwise
    """

    verbose_output(
        f"{BackgroundColors.GREEN}Verifying if the file or folder exists at the path: {BackgroundColors.CYAN}{filepath}{Style.RESET_ALL}"
    )  # Output the verbose message

    return os.path.exists(filepath)  # Return True if the file or folder exists, False otherwise


def play_sound():
    """
    Plays a sound when the program finishes and skips if the operating system is Windows.
    :return: None
    """

    current_os = platform.system()  # Get the current operating system
    if current_os == "Windows":  # If the current operating system is Windows
        return  # Do nothing

    if verify_filepath_exists(SOUND_FILE):  # If the sound file exists
        if current_os in SOUND_COMMANDS:  # If the platform.system() is in the SOUND_COMMANDS dictionary
            os.system(f"{SOUND_COMMANDS[current_os]} {SOUND_FILE}")  # Play the sound
        else:  # If the platform.system() is not in the SOUND_COMMANDS dictionary
            print(
                f"{BackgroundColors.RED}The {BackgroundColors.CYAN}{current_os}{BackgroundColors.RED} is not in the {BackgroundColors.CYAN}SOUND_COMMANDS dictionary{BackgroundColors.RED}. Please add it!{Style.RESET_ALL}"
            )
    else:  # If the sound file does not exist
        print(
            f"{BackgroundColors.RED}Sound file {BackgroundColors.CYAN}{SOUND_FILE}{BackgroundColors.RED} not found. Make sure the file exists.{Style.RESET_ALL}"
        )


def main():
    """
    Main function.

    :return: None
    """

    global INPUT_CSV_FOLDER, INPUT_CSV_FILENAME, INPUT_CSV_FILE, OUTPUT_CSV_FILE  # Declare global variables

    print(
        f"{BackgroundColors.CLEAR_TERMINAL}{BackgroundColors.BOLD}{BackgroundColors.GREEN}Welcome to {BackgroundColors.CYAN}Credit Card Bill{BackgroundColors.GREEN}!{Style.RESET_ALL}",
        end="\n\n",
    )  # Print the welcome message

    INPUT_CSV_FOLDER = detect_input_folder()  # Detect the input folder
    if INPUT_CSV_FOLDER is None:  # If no input folder was found
        print(
            f"{BackgroundColors.RED}Could not find any input folder. Expected one of: {BackgroundColors.CYAN}{POSSIBLE_INPUT_FOLDERS}{Style.RESET_ALL}"
        )
        exit(1)  # Exit the program if no input folder was found

    INPUT_CSV_FILENAME = detect_input_csv_filename(INPUT_CSV_FOLDER)  # Detect the input CSV filename
    if INPUT_CSV_FILENAME is None:  # If no valid CSV file was found
        print(
            f'{BackgroundColors.RED}Could not find a valid CSV file in {BackgroundColors.CYAN}"{INPUT_CSV_FOLDER}"{BackgroundColors.RED}. Expected "debits.csv" (case insensitive) or "FaturaYYYY-MM-DD.csv" pattern.{Style.RESET_ALL}'
        )
        exit(1)  # Exit the program if no valid CSV file was found

    INPUT_CSV_FILE = f"{INPUT_CSV_FOLDER}/{INPUT_CSV_FILENAME}"  # Set the input CSV file path
    OUTPUT_CSV_FILE = f"{INPUT_CSV_FOLDER}/{OUTPUT_CSV_FILENAME}"  # Set the output CSV file path

    if not debits_csv_exists(f"{INPUT_CSV_FILE}"):  # Verify if the CSV file exists
        print(
            f'{BackgroundColors.RED}The file {BackgroundColors.CYAN}"{INPUT_CSV_FILE}"{BackgroundColors.RED} does not exist.{Style.RESET_ALL}'
        )
        exit(1)  # Exit the program if the file does not exist

    df = pd.read_csv(f"{INPUT_CSV_FILE}", sep=";")  # Read the CSV file using the ";" delimiter

    filtered_df = remove_rows(df)  # Remove specified rows from the dataframe

    filtered_df["Valor"] = filtered_df["Valor"].apply(
        reais_to_float
    )  # Apply the function that converts the "Valor" column to a float

    filtered_df.to_csv(f"{OUTPUT_CSV_FILE}", sep=",", index=False)  # Write it to the CSV file using the comma separator

    sorted_df = process_dates(filtered_df, "Data", "%d/%m/%Y")  # Process the dates and sort the DataFrame

    sorted_df["Sum"] = (
        sorted_df["Valor"].cumsum().round(2)
    )  # Calculate the cumulative sum of the "Valor" column and round it to 2 decimal places

    sorted_df.to_csv(f"{OUTPUT_CSV_FILE}", sep=",", index=False)  # Write the DataFrame with comma separator

    cash_payments, credit_payments = get_cash_and_credit_payments(
        sorted_df
    )  # Get the number of Cash payments and the number of Credit payments

    # Print the total sum of the "Valor" column
    print(
        f"{BackgroundColors.GREEN}Total Sum of the {BackgroundColors.CYAN}\"Valor\"{BackgroundColors.GREEN} column: {BackgroundColors.CYAN}R$ {sorted_df['Valor'].sum():.2f}{BackgroundColors.GREEN}.{Style.RESET_ALL}"
    )
    print(
        f"{BackgroundColors.GREEN}Total Purchases: {BackgroundColors.CYAN}{sorted_df.shape[0]}{BackgroundColors.GREEN}. Cash Payments: {BackgroundColors.CYAN}{cash_payments}{BackgroundColors.GREEN}. Credit Payments: {BackgroundColors.CYAN}{credit_payments}{BackgroundColors.GREEN}.{Style.RESET_ALL}",
        end="\n\n",
    )
    print(f"{BackgroundColors.BOLD}{BackgroundColors.GREEN}Execution finished.{Style.RESET_ALL}", end="\n\n")

    (
        atexit.register(play_sound) if RUN_FUNCTIONS["Play Sound"] else None
    )  # Register the play_sound function to be called when the program finishes


if __name__ == "__main__":
    """
    This is the standard boilerplate that calls the main() function.

    :return: None
    """

    main()  # Call the main function
