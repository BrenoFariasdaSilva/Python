import atexit  # For playing a sound when the program finishes
import json  # For saving the songs as a JSON file
import os  # For running a command in the terminal
import platform  # For getting the operating system name
import spotipy  # For using the Spotify API
import spotipy.util as util  # For using the Spotify API
from colorama import Style  # For coloring the terminal
from dotenv import load_dotenv  # For loading environment variables
from tqdm import tqdm  # For displaying a progress bar


# Macros:
class BackgroundColors:  # Colors for the terminal
    CYAN = "\033[96m"  # Cyan
    GREEN = "\033[92m"  # Green
    YELLOW = "\033[93m"  # Yellow
    RED = "\033[91m"  # Red
    BOLD = "\033[1m"  # Bold
    UNDERLINE = "\033[4m"  # Underline
    CLEAR_TERMINAL = "\033[H\033[J"  # Clear the terminal


# Execution Constants:
VERBOSE = False  # Set to True to output verbose messages

# Directories Constants:
INPUT_DIRECTORY = f"./Inputs"  # Input directory

# Filepath Constants:
SPOTIFY_LIKED_SONGS_FILE = f"{INPUT_DIRECTORY}/spotify_liked_songs.json"  # Spotify liked songs JSON file

# .env Constants:
load_dotenv()  # Load environment variables from .env file

# Spotify Constants:
CLIENT_ID = os.getenv("CLIENT_ID")  # Set your Spotify client ID
CLIENT_SECRET = os.getenv("CLIENT_SECRET")  # Set your Spotify client secret
REDIRECT_URI = os.getenv("REDIRECT_URI")  # Set your Spotify redirect URI
USERNAME = os.getenv("SPOTIFY_USERNAME")  # Set your Spotify username
SCOPE = "user-library-read"  # The scope for the Spotify API
TOKEN = util.prompt_for_user_token(
    USERNAME,
    SCOPE,
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET,
    redirect_uri=REDIRECT_URI,
)  # Get the Spotify access token

# Sound Constants:
SOUND_COMMANDS = {
    "Darwin": "afplay",
    "Linux": "aplay",
    "Windows": "start",
}  # The commands to play a sound for each operating system
SOUND_FILE = "./.assets/Sounds/NotificationSound.wav"  # The path to the sound file


def verbose_output(true_string="", false_string="", telegram_bot=None):
    """
    Outputs a message if the VERBOSE constant is set to True.

    :param true_string: The string to be outputted if the VERBOSE constant is set to True.
    :param false_string: The string to be outputted if the VERBOSE constant is set to False.
    :param telegram_bot: Optional TelegramBot instance to send the message to Telegram.
    :return: None
    """

    if VERBOSE and true_string != "":  # If VERBOSE is True and a true_string was provided
        print(true_string)  # Output the true statement string
        if telegram_bot is not None:  # If a Telegram bot instance was provided
            send_telegram_message(telegram_bot, [true_string])  # Send the true_string to Telegram
    elif false_string != "":  # If a false_string was provided
        print(false_string)  # Output the false statement string
        if telegram_bot is not None:  # If a Telegram bot instance was provided
            send_telegram_message(telegram_bot, [false_string])  # Send the false_string to Telegram


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


def authenticate_spotify(token):
    """
    Authenticate with Spotify using the provided token.

    :param token: The authentication token for Spotify
    :return: Spotipy client instance
    """

    return spotipy.Spotify(auth=token)  # Authenticate with Spotify using the provided token


def fetch_liked_songs_batch(sp, limit=50, offset=0):
    """
    Fetch a batch of liked songs from Spotify.

    :param sp: The Spotipy client instance
    :param limit: Number of songs to fetch per request
    :param offset: The offset for pagination
    :return: A dictionary of songs by artist
    """

    results = sp.current_user_saved_tracks(limit=limit, offset=offset)  # Fetch a batch of liked songs from Spotify

    if not results["items"]:  # If there are no items in the results
        return {}, False  # Return an empty dictionary and False

    songs_by_artist = {}  # Initialize an empty dictionary for songs by artist

    for item in results["items"]:  # Iterate through the items in the results
        track = item["track"]  # Get the track information
        artist_name = track["artists"][0]["name"].strip()  # Get the artist name
        song_name = track["name"].strip()  # Get the song name

        if artist_name not in songs_by_artist:  # If the artist name is not in the dictionary
            songs_by_artist[artist_name] = set()  # Initialize a set for the artist name

        songs_by_artist[artist_name].add(song_name)  # Add the song name to the set of songs for the artist name

    return songs_by_artist, True  # Return the dictionary of songs by artist and True


def get_liked_songs_from_spotify(token):
    """
    Fetch liked songs from Spotify, paginate the results, and remove duplicates.

    :param token: The authentication token for Spotify
    :return: A dictionary of songs organized by artist
    """

    sp = authenticate_spotify(token)  # Authenticate with Spotify using the provided token
    songs_by_artist = {}  # Initialize an empty dictionary for songs by artist
    offset = 0  # Initialize the offset to 0
    total_songs = 0  # Initialize the total number of songs to 0

    print(f"{BackgroundColors.GREEN}Fetching liked songs from Spotify...{Style.RESET_ALL}")  # Output the message

    with tqdm(unit=" songs") as pbar:
        while True:  # Infinite loop
            songs_batch, has_more = fetch_liked_songs_batch(
                sp, offset=offset
            )  # Fetch a batch of liked songs from Spotify

            if not has_more:  # If there are no more songs
                break  # Break the loop

            for artist, songs in songs_batch.items():  # Iterate through the artists and songs
                if artist not in songs_by_artist:  # If the artist is not in the dictionary
                    songs_by_artist[artist] = set()  # Initialize a set for the artist
                songs_by_artist[artist].update(songs)  # Add the songs to the artist's set

            batch_size = sum(len(songs) for songs in songs_batch.values())  # Calculate the batch size
            total_songs += batch_size  # Update the total number of songs
            offset += 50  # Move to the next batch

            pbar.update(batch_size)  # Update the progress bar

    return songs_by_artist, total_songs  # Return the dictionary of songs by artist and the total number of songs


def save_songs_to_json(songs_by_artist, filename=SPOTIFY_LIKED_SONGS_FILE):
    """
    Save the songs data to a JSON file.

    :param songs_by_artist: Dictionary of songs organized by artist
    :param filename: The name of the file to save the data
    :return: None
    """

    songs_by_artist = {
        artist: sorted(list(songs)) for artist, songs in songs_by_artist.items()
    }  # Convert sets to lists and sort the songs

    with open(filename, "w", encoding="utf-8") as f:  # Open the file for writing
        json.dump(songs_by_artist, f, indent=4, ensure_ascii=False)  # Save the data as JSON


def get_liked_songs(token=TOKEN):
    """
    Fetch liked songs from Spotify and save them to a JSON file, removing duplicates.

    :param token: The authentication token for Spotify
    :return: None
    """

    verbose_output(f"{BackgroundColors.GREEN}Fetching liked songs from Spotify...{Style.RESET_ALL}")

    songs_by_artist, total_songs = get_liked_songs_from_spotify(token)  # Fetch liked songs

    if songs_by_artist:  # If the songs by artist dictionary is not empty
        os.makedirs(INPUT_DIRECTORY, exist_ok=True)  # Create the directory if it does not exist
        save_songs_to_json(songs_by_artist)  # Save the data to a JSON file

    print(f"{BackgroundColors.GREEN}Total liked songs fetched: {BackgroundColors.CYAN}{total_songs}{Style.RESET_ALL}")


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

    print(
        f"{BackgroundColors.CLEAR_TERMINAL}{BackgroundColors.BOLD}{BackgroundColors.GREEN}Welcome to the {BackgroundColors.CYAN}Spotify Songs{BackgroundColors.GREEN} program!{Style.RESET_ALL}",
        end="\n\n",
    )  # Output the Welcome message

    if not TOKEN:  # If the token is not found
        print(
            f"{BackgroundColors.RED}Can't get token for{BackgroundColors.CYAN} {USERNAME}{BackgroundColors.RED}. Please set the environment variables.{Style.RESET_ALL}"
        )
        return  # Exit the program

    get_liked_songs()  # Fetch liked songs from Spotify and save to a JSON file, removing duplicates

    print(
        f"\n{BackgroundColors.BOLD}{BackgroundColors.GREEN}Program finished.{Style.RESET_ALL}"
    )  # Output the end of the program message

    atexit.register(play_sound)  # Register the function to play a sound when the program finishes


if __name__ == "__main__":
    """
    This is the standard boilerplate that calls the main() function.

    :return: None
    """

    main()  # Call the main function
