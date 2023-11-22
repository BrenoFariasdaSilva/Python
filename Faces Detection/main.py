import atexit # For playing a sound when the program finishes
import cv2 # For image processing
import os # For listing the files in a directory
import platform # For getting the operating system name
from colorama import Style # For coloring the terminal
from tqdm import tqdm # For displaying a progress bar

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
SOUND_FILE = "./.assets/NotificationSound.wav" # The path to the sound file

# Input Constants:
INPUT_IMAGES = "./Dataset" # The path to the images directory
OUTPUT_IMAGES = "./Faces" # The path to the output directory

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

# This function creates the output directory
def create_output_directory():
   if os.path.exists(OUTPUT_IMAGES): # If the output directory exists
      os.system(f"rm -rf {OUTPUT_IMAGES}") # Delete the output directory
      os.system(f"mkdir {OUTPUT_IMAGES}") # Create a new output directory
   else: # If the output directory does not exist
      os.system(f"mkdir {OUTPUT_IMAGES}") # Create a new output directory

# This function extracts the character's face from an image
def extract_character_face(image_path, save_path):
   image = cv2.imread(image_path) # Load the image

   # Convert the image to grayscale
   gray_image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

   # Load the face detection model
   face_detector = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

   # Detect faces in the image
   faces = face_detector.detectMultiScale(gray_image, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))

   # For each detected face
   for (x, y, w, h) in faces:
      # Extract the region of the face from the original image
      face_region = image[y:y+h, x:x+w]

      # Save the image of the extracted face
      cv2.imwrite(save_path, face_region)

   return len(faces) # Return the number of detected faces

# This function prints the number of detected faces in each image
def print_detected_faces(detected_faces):
   print(f"") # Print a new line

   # For each image
   for image in detected_faces:
      print(f"{BackgroundColors.GREEN}Faces Detected in {BackgroundColors.CYAN}{image}{BackgroundColors.GREEN}: {BackgroundColors.CYAN}{detected_faces[image]}{Style.RESET_ALL}") # Print the number of detected faces

   print(f"") # Print a new line

# This is the Main function
def main():
   print(f"{BackgroundColors.CLEAR_TERMINAL}{BackgroundColors.GREEN}{BackgroundColors.BOLD}Welcome to {BackgroundColors.UNDERLINE}Faces Cut Algorithm{Style.RESET_ALL}") # Print the welcome message

   # Create the output directory
   create_output_directory()

   # A dictionary to store the number of detected faces in each image
   detected_faces = {}

   # Create a progress bar
   with tqdm(total=len(os.listdir(INPUT_IMAGES))) as progress_bar:
      # For each image in the input directory
      for image in os.listdir(INPUT_IMAGES):
         save_image_path = os.path.join(OUTPUT_IMAGES, image) # The path to save the image
         image_path = os.path.join(INPUT_IMAGES, image) # The path to the image

         # Extract the character's face from the image
         detected_faces[image] = extract_character_face(image_path, save_image_path)

         # Update the progress bar
         progress_bar.update(1)

   # Print the number of detected faces in each image
   print_detected_faces(detected_faces)

   print(f"{BackgroundColors.GREEN}All images extracted successfully!{Style.RESET_ALL}") # Print the success message

# This is the standard boilerplate that calls the main() function.
if __name__ == '__main__':
	main() # Call the main function
