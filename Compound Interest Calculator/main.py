import atexit # For playing a sound when the program finishes
import os # For running a command in the terminal
import matplotlib.pyplot as plt # For plotting graphs
import numpy as np # For creating arrays
import platform # For getting the operating system name
from colorama import Style # For coloring the terminal
from matplotlib.ticker import MaxNLocator # For setting the number of y axis ticks

# Macros:
class BackgroundColors: # Colors for the terminal
   CYAN = "\033[96m" # Cyan
   GREEN = "\033[92m" # Green
   YELLOW = "\033[93m" # Yellow
   RED = "\033[91m" # Red
   BOLD = "\033[1m" # Bold
   UNDERLINE = "\033[4m" # Underline
   CLEAR_TERMINAL = "\033[H\033[J" # Clear the terminal

# Sound Constants:
SOUND_COMMANDS = {"Darwin": "afplay", "Linux": "aplay", "Windows": "start"}
SOUND_FILE = "./.assets/Sounds/NotificationSound.wav" # The path to the sound file

# Input Constants:
PERIOD_TYPES = ["Years", "Months", "Days"] # The types of the period
CONTRIBUTION = {"Years": "Annual", "Months": "Monthly", "Days": "Daily"} # The contribution according to the period type
STR_PERIOD_TYPES = str(tuple(PERIOD_TYPES))[1:-1].replace("'", "") # The types of the period as a string list

# This function defines the command to play a sound when the program finishes
def play_sound():
   if os.path.exists(SOUND_FILE):
      if platform.system() in SOUND_COMMANDS: # If the platform.system() is in the SOUND_COMMANDS dictionary
         os.system(f"{SOUND_COMMANDS[platform.system()]} {SOUND_FILE}")
      else: # If the platform.system() is not in the SOUND_COMMANDS dictionary
         print(f"{BackgroundColors.RED}The {BackgroundColors.CYAN}platform.system(){BackgroundColors.RED} is not in the {BackgroundColors.CYAN}SOUND_COMMANDS dictionary{BackgroundColors.RED}. Please add it!{Style.RESET_ALL}")
   else: # If the sound file does not exist
      print(f"{BackgroundColors.RED}Sound file {BackgroundColors.CYAN}{SOUND_FILE}{BackgroundColors.RED} not found. Make sure the file exists.{Style.RESET_ALL}")

# Register the function to play a sound when the program finishes
atexit.register(play_sound)

# This function get for the type of the period from the user
def get_period_type():
   period_type = "" # Initialize the period type

   while period_type.capitalize() not in PERIOD_TYPES: # While the period type is not in the list of the period types
      period_type = input(f"{BackgroundColors.BOLD}{BackgroundColors.GREEN}Please enter the type of the period {BackgroundColors.CYAN}({STR_PERIOD_TYPES}){BackgroundColors.GREEN}: {Style.RESET_ALL}")

   return period_type.capitalize() # Return the period type

# This function get the number of the periods from the user
def get_number_of_periods():
   number_of_periods = -1 # Initialize the number of the periods

   while number_of_periods < 0: # While the number of the periods is less than or equal to 0
      number_of_periods = int(input(f"{BackgroundColors.BOLD}{BackgroundColors.GREEN}Please enter the number of the periods {BackgroundColors.CYAN}(Int){BackgroundColors.GREEN}: {Style.RESET_ALL}"))

   return number_of_periods # Return the number of the periods

# This function get the initial amount from the user
def get_initial_amount():
   initial_amount = -1 # Initialize the initial amount

   while initial_amount < 0: # While the initial amount is less than or equal to 0
      initial_amount = float(input(f"{BackgroundColors.BOLD}{BackgroundColors.GREEN}Please enter the initial amount {BackgroundColors.CYAN}(Int or Float){BackgroundColors.GREEN}: {Style.RESET_ALL}"))

   return initial_amount # Return the initial amount

# This function get the user regular contribution from the user
def get_regular_contribution(period_type):
   regular_contribution = -1 # Initialize the regular contribution

   while regular_contribution < 0: # While the regular contribution is less than or equal to 0
      regular_contribution = float(input(f"{BackgroundColors.BOLD}{BackgroundColors.GREEN}Please enter the {CONTRIBUTION[period_type]} Contribution {BackgroundColors.CYAN}(Int or Float){BackgroundColors.GREEN}: {Style.RESET_ALL}"))

   return regular_contribution # Return the regular contribution

# This function get the progressive contribution rate from the user
def get_progressive_contribution_rate():
   progressive_contribution = -1 # Initialize the progressive contribution
   
   while progressive_contribution < 0.00 or progressive_contribution > 1.00:
      progressive_contribution = float(input(f"{BackgroundColors.BOLD}{BackgroundColors.GREEN}Please enter the Progressive Contribution Rate{BackgroundColors.CYAN} (0.0 to 1.0){BackgroundColors.GREEN}: {Style.RESET_ALL}"))

   return progressive_contribution # Return the progressive contribution

# This function get the interest rate from the user
def get_interest_rate(period_type):
   interest_rate = -1 # Initialize the interest rate

   while interest_rate < 0.0 or interest_rate > 1.0: # While the interest rate is less than 0.0 or greater than 1.0
      interest_rate = float(input(f"{BackgroundColors.BOLD}{BackgroundColors.GREEN}Please enter the {period_type} Interest Rate {BackgroundColors.CYAN}(0.0 to 1.0){BackgroundColors.GREEN}: {Style.RESET_ALL}"))

   return interest_rate # Return the interest rate

# This function calculates the compound interest
def calculate_compound_interest(number_of_periods, initial_amount, regular_contribution, progressive_contribution_rate, interest_rate):
   total_amount = initial_amount + regular_contribution # Initialize the total amount
   total_amounts = [total_amount] # Initialize the list of the total amounts
   periods = [0] # Initialize the list of the periods

   for period in range(1, number_of_periods + 1): # For each period
      current_contribution = regular_contribution * (1 + progressive_contribution_rate) ** (period - 1) # Calculate the current contribution
      total_amount = total_amount * (1 + interest_rate) + current_contribution # Calculate the total amount
      total_amounts.append(f"{total_amount:.2f}") # Append the total amount to the list of the total amounts
      periods.append(period) # Append the period to the list of the periods

   return total_amounts, periods # Return the list of the total amounts and the list of the periods

# This function returns the reduced list
def reduce_list(list, period_type):
   if not len(list) > 100: # If the length of the list is not greater than 100
      return list # Return the list
   
   # Define the reduction ratio
   reduction_ratio = {"Years": 12, "Months": 6, "Days": 30}

   return list[::reduction_ratio[period_type]] # Return the reduced list

# This function plots the graph
def plot_graph(total_amounts, money_invested, profits, periods, period_type):
   fig, ax = plt.subplots(figsize=(16, 9)) # 16:9 Aspect Ratio for 1080p
   bar_width = 0.5 # Set the width of the bars

   x_values = np.arange(len(periods)) # Create an array of x values for each period

   # Plot the bars for the total amount with transparency
   ax.bar(x_values, total_amounts, width=bar_width, align="center", alpha=0.7, label="Total Amount")
   # Plot the bars for the invested amount with transparency, overlaying the total amount bars
   ax.bar(x_values, money_invested, width=bar_width, align="center", alpha=0.7, label="Money Invested")

   ax.set_xticks(np.arange(len(periods))) # Set the x ticks
   ax.set_xticklabels(periods) # Set the x tick labels
   ax.yaxis.set_major_locator(MaxNLocator(nbins=10)) # Set the number of y axis ticks

   plt.xlabel(f"{period_type}") # Set the x label
   plt.ylabel(f"Total Amount") # Set the y label
   plt.title(f"Compound Interest Calculator:\nTotal Amount of {total_amounts[-1]} R$ After {periods[-1]} {period_type}\nProfit: {profits[0]:.2f} R$, representing {profits[1]:.2f}% of the Money Invested.") # Set the title

   ax.legend() # Add a legend
   plt.show() # Show the graph

# This is the Main function
def main():
   print(f"{BackgroundColors.CLEAR_TERMINAL}{BackgroundColors.BOLD}{BackgroundColors.GREEN}Welcome to the {BackgroundColors.CYAN}Compound Interest Calculator {BackgroundColors.GREEN}Algorithm!{Style.RESET_ALL}", end="\n\n") # Output the Welcome message

   period_type = get_period_type() # Get the type of the period from the user
   number_of_periods = get_number_of_periods() # Get the number of the periods from the user
   initial_amount = get_initial_amount() # Get the initial amount from the user
   regular_contribution = get_regular_contribution(period_type) # Get the regular contribution from the user
   progressive_contribution_rate = get_progressive_contribution_rate() # Get the progressive contribution from the user
   interest_rate = get_interest_rate(period_type) # Get the interest rate from the user

   total_amounts, periods = calculate_compound_interest(number_of_periods, initial_amount, regular_contribution, progressive_contribution_rate, interest_rate) # Calculate the compound interest
   
   money_invested = np.array([initial_amount + regular_contribution * period for period in range(number_of_periods + 1)]) # Calculate the money invested

   total_amounts = reduce_list(total_amounts, period_type) # Reduce the list of the total amounts
   money_invested = reduce_list(money_invested, period_type) # Reduce the list of the money invested
   periods = reduce_list(periods, period_type) # Reduce the list of the periods

   total_amounts = np.array(total_amounts, dtype=float) # Convert the list to a float numpy array

   profits = [ float(total_amounts[-1]) - money_invested[-1], (( float(total_amounts[-1]) - money_invested[-1]) /  float(total_amounts[-1]) * 100)]

   plot_graph(total_amounts, money_invested, profits, periods, period_type) # Plot the graph

   print(f"\n{BackgroundColors.BOLD}{BackgroundColors.GREEN}Total Amount After {BackgroundColors.CYAN}{periods[-1]} {period_type}{BackgroundColors.GREEN}: {BackgroundColors.CYAN}{total_amounts[-1]}{BackgroundColors.GREEN} R$.")
   print(f"{BackgroundColors.BOLD}{BackgroundColors.GREEN}Profit: {BackgroundColors.CYAN}{profits[0]:.2f}{BackgroundColors.GREEN} R$, representing {BackgroundColors.CYAN}{profits[1]:.2f}%{BackgroundColors.GREEN} of the Money Invested.{Style.RESET_ALL}") # Output the profit message

   print(f"\n{BackgroundColors.BOLD}{BackgroundColors.GREEN}Program finished.{Style.RESET_ALL}") # Output the end of the program message

# This is the standard boilerplate that calls the main() function.
if __name__ == "__main__":
	main() # Call the main function
