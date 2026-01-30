import atexit  # For playing a sound when the program finishes
import google.generativeai as genai  # Import the Google AI Python SDK
import os  # For running a command in the terminal
import platform  # For getting the operating system name
import sys  # For exiting the program
from colorama import Style  # For coloring the terminal
from dotenv import load_dotenv  # For loading .env files


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
SOUND_FILE = "./assets/Sounds/NotificationSound.wav"  # The path to the sound file

# Execution Constants:
VERBOSE = False  # Verbose mode. If set to True, it will output messages at the start/call of each function (Note: It will output a lot of messages).

# .Env Constants:
ENV_PATH = "./.env"  # The path to the .env file
ENV_VARIABLE = "GEMINI_API_KEY"  # The environment variable to load

# File Path Constants:
OUTPUT_DIRECTORY = "./Outputs/"  # The path to the output directory
OUTPUT_FILE = f"{OUTPUT_DIRECTORY}output.txt"  # The path to the output file


def play_sound():
    """
    Plays a sound when the program finishes.
    :return: None
    """

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


def verbose_output(true_string="", false_string=""):
    """
    Outputs a message if the VERBOSE constant is set to True.

    :param true_string: The string to be outputted if the VERBOSE constant is set to True.
    :param false_string: The string to be outputted if the VERBOSE constant is set to False.
    :return: None
    """

    if VERBOSE and true_string != "":  # If VERBOSE is True and a true_string was provided
        print(true_string)  # Output the true statement string
    elif false_string != "":  # If a false_string was provided
        print(false_string)  # Output the false statement string


def verify_env_file(env_path=ENV_PATH, key=ENV_VARIABLE):
    """
    Verify if the .env file exists and if the desired key is present.
    :param env_path: Path to the .env file.
    :param key: The key to get in the .env file.
    :return: The value of the key if it exists.
    """

    verbose_output(true_string=f"{BackgroundColors.GREEN}Verifying the .env file...{Style.RESET_ALL}")

    # Verify if the .env file exists
    if not os.path.exists(env_path):
        print(
            f"{BackgroundColors.RED}The {BackgroundColors.CYAN}.env file{BackgroundColors.RED} not found at {BackgroundColors.CYAN}{env_path}{Style.RESET_ALL}"
        )
        sys.exit(1)  # Exit the program

    load_dotenv(env_path)  # Load the .env file
    api_key = os.getenv(key)  # Get the value of the key

    # Verify if the key exists
    if not api_key:
        print(
            f"{BackgroundColors.RED}The {BackgroundColors.CYAN}{key}{BackgroundColors.RED} key was not found in the .env file located at {BackgroundColors.CYAN}{env_path}{Style.RESET_ALL}"
        )
        sys.exit(1)  # Exit the program

    return api_key  # Return the value of the key


def create_directory(full_directory_name, relative_directory_name):
    """
    Creates a directory.

    :param full_directory_name: Name of the directory to be created.
    :param relative_directory_name: Relative name of the directory to be created that will be shown in the terminal.
    :return: None
    """

    verbose_output(
        true_string=f"{BackgroundColors.GREEN}Creating the {BackgroundColors.CYAN}{relative_directory_name}{BackgroundColors.GREEN} directory...{Style.RESET_ALL}"
    )

    if os.path.isdir(full_directory_name):  # Verify if the directory already exists
        return  # Return if the directory already exists
    try:  # Try to create the directory
        os.makedirs(full_directory_name)  # Create the directory
    except OSError:  # If the directory cannot be created
        print(
            f"{BackgroundColors.GREEN}The creation of the {BackgroundColors.CYAN}{relative_directory_name}{BackgroundColors.GREEN} directory failed.{Style.RESET_ALL}"
        )


def configure_model(api_key):
    """
    Configure the generative AI model.
    :param api_key: The API key to configure the model.
    :return: The configured model.
    """

    verbose_output(true_string=f"{BackgroundColors.GREEN}Configuring the Gemini Model...{Style.RESET_ALL}")

    genai.configure(api_key=api_key)  # Configure the Google AI Python SDK

    # Generation configuration
    generation_config = {
        "temperature": 0.1,  # Controls the randomness of the output. Values can range from [0.0, 2.0].
        "top_p": 0.95,  # Optional. The maximum cumulative probability of tokens to consider when sampling.
        "top_k": 64,  # Optional. The maximum number of tokens to consider when sampling.
        "max_output_tokens": 8192,  # Set the maximum number of output tokens
    }

    # Create the model
    model = genai.GenerativeModel(
        model_name="gemini-1.5-flash",  # Set the model name
        generation_config=generation_config,  # Set the generation configuration
    )

    return model  # Return the model


def start_chat_session(model, initial_user_message):
    """
    Start a chat session with the model.
    :param model: The generative AI model.
    :param initial_user_message: The initial user message.
    :return: The chat session.
    """

    verbose_output(true_string=f"{BackgroundColors.GREEN}Starting the chat session...{Style.RESET_ALL}")

    chat_session = model.start_chat(
        history=[
            {
                "role": "user",
                "parts": [
                    initial_user_message,
                ],
            }
        ]
    )

    return chat_session  # Return the chat session


def send_message(chat_session, user_message):
    """
    Send a message in the chat session and get the output.
    :param chat_session: The chat session.
    :param user_message: The user message to send.
    :return: The output.
    """

    verbose_output(true_string=f"{BackgroundColors.GREEN}Sending the message...{Style.RESET_ALL}")

    output = chat_session.send_message(user_message)  # Send the message
    return output.text  # Return the output


def write_output_to_file(output, file_path=OUTPUT_FILE):
    """
    Writes the chat output to a specified file.
    :param output: The output to write.
    :param file_path: The path to the file.
    :return: None
    """

    verbose_output(true_string=f"{BackgroundColors.GREEN}Writing the output to the file...{Style.RESET_ALL}")

    with open(file_path, "w") as file:
        file.write(output)  # Write the output to the file


def main():
    """
    Main function.
    :return: None
    """

    print(
        f"{BackgroundColors.CLEAR_TERMINAL}{BackgroundColors.BOLD}{BackgroundColors.GREEN}Welcome to the {BackgroundColors.CYAN}Google Gemini API Integration{BackgroundColors.GREEN}!{Style.RESET_ALL}",
        end="\n\n",
    )  # Output the Welcome message

    # Verify .env file and load API key
    api_key = verify_env_file(ENV_PATH, ENV_VARIABLE)

    create_directory(
        os.path.abspath(OUTPUT_DIRECTORY), OUTPUT_DIRECTORY.replace(".", "")
    )  # Create the output directory

    # Configure the model
    model = configure_model(api_key)

    # Setup the context message
    context_message = f"""
    Hi, Gemini.
    """

    # Setup the task message
    task_message = f""""
    Please analyze the provided data.
    """

    chat_session = start_chat_session(model, context_message)  # Start the chat session
    output = send_message(chat_session, task_message)  # Send the message

    write_output_to_file(output, OUTPUT_FILE)  # Write the output to a file

    print(
        f"{BackgroundColors.BOLD}{BackgroundColors.GREEN}Program finished.{Style.RESET_ALL}", end="\n\n"
    )  # Output the end of the program message


if __name__ == "__main__":
    """
    This is the standard boilerplate that calls the main() function.
    :return: None
    """

    main()  # Call the main function
