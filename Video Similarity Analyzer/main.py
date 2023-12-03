import atexit # For playing a sound when the program finishes
import cv2 # For reading videos
import imagehash # For hashing images
import os # For running a command in the terminal
import platform # For getting the operating system name
import warnings # For ignoring warnings
from colorama import Style # For coloring the terminal
from PIL import Image # For opening images
from tqdm import tqdm

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

# This function verifies if the file exists
def file_exists(file):
   if os.path.exists(file): # If the file exists
      return True
   else: # If the file does not exist
      print(f"{BackgroundColors.RED}File {BackgroundColors.CYAN}{file}{BackgroundColors.RED} not found. Make sure the file exists.{Style.RESET_ALL}")
      return False

# This function returns the perceptual hash of an image
def perceptual_hash(image):
   with warnings.catch_warnings():
      warnings.simplefilter("ignore", category=DeprecationWarning)
      resized_img = image.resize((8, 8), Image.ANTIALIAS)
   return imagehash.average_hash(resized_img)

# This function compares two videos and returns True if they are similar and False if they are not
def are_videos_similar(video_path1, video_path2):
   video1 = cv2.VideoCapture(video_path1) # Open the first video
   video2 = cv2.VideoCapture(video_path2) # Open the second video

   try:
      frame_count = 0 # The frame count
      similar_frame_count = 0 # The similar frame count

      # Get the total number of frames
      total_frames = int(min(video1.get(cv2.CAP_PROP_FRAME_COUNT), video2.get(cv2.CAP_PROP_FRAME_COUNT)))

      # Loop through the frames
      for frame_count in tqdm(range(total_frames), desc=f"{BackgroundColors.GREEN}Comparing frames{Style.RESET_ALL}", unit="frame"):
         ret1, frame1 = video1.read() # Read the first frame
         ret2, frame2 = video2.read() # Read the second frame

         if not ret1 or not ret2:
            break # If the frame is not read, break the loop

         img1 = Image.fromarray(cv2.cvtColor(frame1, cv2.COLOR_BGR2RGB)) # Convert the first frame to an image
         img2 = Image.fromarray(cv2.cvtColor(frame2, cv2.COLOR_BGR2RGB)) # Convert the second frame to an image

         hash1 = perceptual_hash(img1) # Get the perceptual hash of the first image
         hash2 = perceptual_hash(img2) # Get the perceptual hash of the second image

         threshold = 5 # The threshold for the perceptual hash

         if hash1 - hash2 < threshold: # If the difference between the two hashes is less than the threshold
            similar_frame_count += 1 # Increment the similar frame count

      # Calculate similarity ratio
      similarity_ratio = similar_frame_count / total_frames

      # Adjust the similarity threshold as needed based on your requirements
      similarity_threshold = 0.9

      print(f"{BackgroundColors.BOLD}{BackgroundColors.GREEN}The similarity ratio is {BackgroundColors.CYAN}{similarity_ratio}{Style.RESET_ALL}")

      # Return True if the similarity ratio is greater than the similarity threshold
      return similarity_ratio >= similarity_threshold

   except Exception as e:
      print(f"Error comparing videos: {str(e)}")
      return False

   finally:
      video1.release()
      video2.release()

# This is the Main function
def main():
   print(f"{BackgroundColors.CLEAR_TERMINAL}{BackgroundColors.BOLD}{BackgroundColors.GREEN}Welcome to the {BackgroundColors.CYAN}Video Similarity Analyzer{BackgroundColors.GREEN}!{Style.RESET_ALL}") # Output the welcome message

   first_video = f"."
   second_video = f"."

   if not file_exists(first_video): # If the first file does not exist
      print(f"{BackgroundColors.RED}The first file {BackgroundColors.CYAN}{first_video}{BackgroundColors.RED} does not exist. Please try again.{Style.RESET_ALL}")
      return
   if not file_exists(second_video): # If the second file does not exist
      print(f"{BackgroundColors.RED}The second file {BackgroundColors.CYAN}{second_video}{BackgroundColors.RED} does not exist. Please try again.{Style.RESET_ALL}")
      return

   if are_videos_similar(first_video, second_video): # If the two videos are similar
      print(f"{BackgroundColors.BOLD}{BackgroundColors.GREEN}The {BackgroundColors.CYAN}{first_video}{BackgroundColors.GREEN} and {BackgroundColors.CYAN}{second_video}{BackgroundColors.GREEN} videos are similar.{Style.RESET_ALL}")
   else: # If the two videos are not similar
      print(f"{BackgroundColors.BOLD}{BackgroundColors.RED}The {BackgroundColors.CYAN}{first_video}{BackgroundColors.RED} and {BackgroundColors.CYAN}{second_video}{BackgroundColors.RED} videos are not similar.{Style.RESET_ALL}")

   print(f"{BackgroundColors.BOLD}{BackgroundColors.GREEN}Program finished.{Style.RESET_ALL}") # Output the end of the program message

# This is the standard boilerplate that calls the main() function.
if __name__ == '__main__':
	main() # Call the main function
