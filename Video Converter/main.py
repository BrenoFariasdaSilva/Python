import atexit # For playing a sound when the program finishes
import os # For running a command in the terminal
import platform # For getting the operating system name
import subprocess # For running a command in the terminal
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

# Sound Constants:
SOUND_COMMANDS = {"Darwin": "afplay", "Linux": "aplay", "Windows": "start"}
SOUND_FILE = "./.assets/Sounds/NotificationSound.wav" # The path to the sound file

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

# This function verifies if the ffmpeg command is installed
def verify_ffmpeg():
   try:
      subprocess.run(["ffmpeg", "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
   except subprocess.CalledProcessError:
      return False
   return True

# This function verifies if the input path exists
def verify_input_path_exists(input_file_or_directory):
   if not os.path.exists(input_file_or_directory):
      return False
   return True

# This function verifies if the input path is a file or directory
def verify_input_path_is_file(input_path):
   if os.path.isfile(input_path):
      return True
   return False

# This function converts a video file or all video files in a directory to a specific format
def convert_video(input_file, output_file):
   # Run ffmpeg command to convert the video
   command = ["ffmpeg", "-i", input_file, "-c", "copy"]

   # Add specific options based on the output format
   if output_file.split(".")[-1] == "mp4":
      command += ["-strict", "-2"] # Needed for certain audio codecs in mp4

   command += output_file # Add the output file to the command

   try:
      subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True) # Run the command
      print(f"Conversion successful. Output file: {output_file}") # Output the success message
   except subprocess.CalledProcessError as e:
      print(f"Error during conversion:\n{e.stderr.decode('utf-8')}") # Output the error message

# This is the Main function
def main():
   print(f"{BackgroundColors.CLEAR_TERMINAL}{BackgroundColors.BOLD}{BackgroundColors.GREEN}Welcome to the Video Converter!{Style.RESET_ALL}", end="\n\n") # Output the welcome message

   # Verify if ffmpeg is installed
   if not verify_ffmpeg():
      print(f"{BackgroundColors.YELLOW}Error: {BackgroundColors.CYAN}ffmpeg{BackgroundColors.YELLOW} is not installed. Please install ffmpeg and try again.{Style.RESET_ALL}")
      return
   
   input_path = "./"
   output_file_format = "mp4"
   
   # Verify if the input path does not exist
   if not verify_input_path_exists(input_path):
      print(f"{BackgroundColors.YELLOW}Error: {BackgroundColors.CYAN}{input_path}{BackgroundColors.YELLOW} does not exist. Please check the path and try again.{Style.RESET_ALL}")
      return
   
   video_files = [input_path]
   # Verify if the input path is a file
   if not verify_input_path_is_file(input_path):
      video_files = [os.path.join(input_path, f) for f in os.listdir(input_path) if os.path.isfile(os.path.join(input_path, f))] # Get all the files in the input path

   # Convert all the video files
   for video_file in video_files:
      output_file = os.path.splitext(video_file)[0] + "." + output_file_format # Create the output file name
      convert_video(video_file, output_file) # Convert the video file

   print(f"\n{BackgroundColors.BOLD}{BackgroundColors.GREEN}Program finished.{Style.RESET_ALL}") # Output the end of the program message

# This is the standard boilerplate that calls the main() function.
if __name__ == "__main__":
	main() # Call the main function
