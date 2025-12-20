import atexit  # For playing a sound when the program finishes
import csv  # For reading and writing CSV files
import os  # For running a command in the terminal
import math  # For mathematical operations
import platform  # For getting the operating system name
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


# Sound Constants:
SOUND_COMMANDS = {
    "Darwin": "afplay",
    "Linux": "aplay",
    "Windows": "start",
}  # The commands to play a sound for each operating system
SOUND_FILE = "./.assets/Sounds/NotificationSound.wav"  # The path to the sound file

# Data Constants:
STEAM_ACCOUNTS = ["BrenoVicioGamer", "BrenoVicioEurope", "ParzivalPsycho"]  # The list of Steam accounts
MAX_HOURS_PLAYED = 12.1  # The maximum hours played for a game
MAX_GAMES_PER_RUN = 32  # The maximum games per run for the filter

# Input/Output Constants:
INPUT_DIRECTORY = "Steam Games"  # The input directory
OUTPUT_DIRECTORY = INPUT_DIRECTORY  # The output directory

# Functions:


# This function creates a directory if it does not exist
def create_directories(directory_name):
    if not os.path.exists(directory_name):  # If the directory does not exist
        os.makedirs(directory_name)  # Create the directory


# This function reads the games from a CSV file
def read_games_from_csv(input_csv_filename, max_hours_played=MAX_HOURS_PLAYED):
    filtered_games = []  # The list of filtered games

    with open(input_csv_filename, mode="r", newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)  # Create a CSV reader
        for row in reader:  # For each row in the CSV file
            if (
                float(row["Hours Played"]) < max_hours_played
            ):  # If the hours played is less than the maximum hours played
                filtered_games.append(row)  # Add the game to the list of filtered games

    return filtered_games  # Return the list of filtered games


# This function writes the games to a CSV file
def write_games_to_csv(output_csv_filename, filtered_games):
    # Write the filtered games to the output CSV file
    with open(output_csv_filename, mode="w", newline="", encoding="utf-8") as file:
        fieldnames = ["Number", "Game Name", "AppID", "Hours Played"]  # The field names for the CSV file
        writer = csv.DictWriter(file, fieldnames=fieldnames)  # Create a CSV writer

        writer.writeheader()  # Write the header of the CSV file
        for index, game in enumerate(filtered_games, start=1):
            game["Number"] = index  # Update the game number for the new list
            writer.writerow(game)  # Write the game to the CSV file


# This function filters the games from a CSV file
def filter_games_from_csv(input_csv_filename, output_csv_filename, max_hours_played=MAX_HOURS_PLAYED):
    filtered_games = read_games_from_csv(input_csv_filename, max_hours_played)  # Read the games from the input CSV file
    write_games_to_csv(output_csv_filename, filtered_games)  # Write the games to the output CSV file

    return len(filtered_games)  # Return the number of filtered games


# This function defines the command to play a sound when the program finishes
def play_sound():
    if os.path.exists(SOUND_FILE):
        if platform.system() in SOUND_COMMANDS:  # If the platform.system() is in the SOUND_COMMANDS dictionary
            os.system(f"{SOUND_COMMANDS[platform.system()]} {SOUND_FILE}")
        else:  # If the platform.system() is not in the SOUND_COMMANDS dictionary
            print(
                f"{BackgroundColors.RED}The {BackgroundColors.CYAN}platform.system(){BackgroundColors.RED} is not in the {BackgroundColors.CYAN}SOUND_COMMANDS dictionary{BackgroundColors.RED}. Please add it!{Style.RESET_ALL}"
            )
    else:  # If the sound file does not exist
        print(
            f"{BackgroundColors.RED}Sound file {BackgroundColors.CYAN}{SOUND_FILE}{BackgroundColors.RED} not found. Make sure the file exists.{Style.RESET_ALL}"
        )


# Register the function to play a sound when the program finishes
atexit.register(play_sound)


# This is the Main function
def main():
    print(
        f"{BackgroundColors.CLEAR_TERMINAL}{BackgroundColors.BOLD}{BackgroundColors.GREEN}Welcome to the {BackgroundColors.CYAN}Steam Games Playtime Filter{BackgroundColors.GREEN} program!{Style.RESET_ALL}",
        end="\n\n",
    )  # Output the Welcome message

    create_directories(OUTPUT_DIRECTORY)  # Create the output directory

    for steam_account in STEAM_ACCOUNTS:  # For each Steam account in the list of Steam accounts
        input_csv_filename = f"{INPUT_DIRECTORY}/{steam_account}-Games.csv"  # The input CSV filename
        output_csv_filename = f"{OUTPUT_DIRECTORY}/{steam_account}-Games-Filtered.csv"  # The output CSV filename

        filtered_games = filter_games_from_csv(
            input_csv_filename, output_csv_filename
        )  # Filter the games from the input CSV file and save the output CSV file

        print(
            f"{BackgroundColors.GREEN}Filtered {BackgroundColors.CYAN}{steam_account}{BackgroundColors.GREEN} games from {BackgroundColors.CYAN}{input_csv_filename}{BackgroundColors.GREEN} to {BackgroundColors.CYAN}{output_csv_filename}{BackgroundColors.GREEN} with {BackgroundColors.CYAN}{filtered_games}{BackgroundColors.GREEN} games.{Style.RESET_ALL}"
        )  # Output the filtered games message
        print(
            f"{BackgroundColors.GREEN}Estimate: {BackgroundColors.CYAN}{math.ceil((filtered_games / MAX_GAMES_PER_RUN))}{BackgroundColors.GREEN} runs of {BackgroundColors.CYAN}{MAX_HOURS_PLAYED}{BackgroundColors.GREEN} each, totalling {BackgroundColors.CYAN}{math.ceil((filtered_games / MAX_GAMES_PER_RUN) * MAX_HOURS_PLAYED)}{BackgroundColors.GREEN} hours.{Style.RESET_ALL}",
            end="\n\n",
        )  # Output the estimate message

    print(
        f"\n{BackgroundColors.BOLD}{BackgroundColors.GREEN}Program finished.{Style.RESET_ALL}"
    )  # Output the end of the program message


# This is the standard boilerplate that calls the main() function.
if __name__ == "__main__":
    main()  # Call the main function
