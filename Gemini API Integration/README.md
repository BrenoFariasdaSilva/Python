<div align="center">

# [Google Gemini.](https://github.com/BrenoFariasdaSilva/Worked-Example-Miner/tree/main/Gemini)  <img src="https://github.com/devicons/devicon/blob/master/icons/python/python-original.svg"  width="3%" height="3%">

</div>

<div align="center">
  
---

Welcome to the Google Gemini API integration directory, in which you will find the script used to interact with the Google Gemini API.

---

</div>

- [Google Gemini.  ](#google-gemini--)
  - [Important Notes](#important-notes)
  - [Setup](#setup)
    - [Python and Pip](#python-and-pip)
      - [Linux](#linux)
      - [MacOS](#macos)
      - [Windows](#windows)
    - [Requirements](#requirements)
    - [Cleaning Up](#cleaning-up)
  - [How to use](#how-to-use)
    - [Gemini Script](#gemini-script)
      - [Configuration](#configuration)
      - [Run](#run)
      - [Workflow](#workflow)
    - [Gemini File Input](#gemini-file-input)
      - [Configuration](#configuration-1)
      - [Run](#run-1)
      - [Workflow](#workflow-1)
    - [Gemini PDF](#gemini-pdf)
      - [Configuration](#configuration-2)
      - [Run](#run-2)
      - [Workflow](#workflow-2)
  - [Generated Data](#generated-data)
  - [Contributing](#contributing)
  - [License](#license)

## Important Notes

- Make sure you don't have whitespaces in the path of the project, otherwise it will not work.
- To enhance the readability of the code, please note that the files adhere to a Bottom-Up approach in function ordering. This means that each function is defined above the function that calls it.
- All of the Scripts have a `Makefile`that handles virtual environment creation, dependencies installation and script execution. You can run the scripts by using the `make` command, as shown in the `How to use` section.

## Setup

This section provides instructions for installing the Python Language and Pip Python package manager, as well as the project's dependencies. It also explains how to run the scripts using the provided `makefile`. The `makefile` automates the process of creating a virtual environment, installing dependencies, and running the scripts.

### Python and Pip

In order to run the scripts, you must have python3 and pip installed in your machine. If you don't have it installed, you can use the following commands to install it:

#### Linux

In order to install python3 and pip in Linux, you can use the following commands:

```
sudo apt install python3 -y
sudo apt install python3-pip -y
```

#### MacOS

In order to install python3 and pip in MacOS, you can use the following commands:

```
brew install python3
```

#### Windows

In order to install python3 and pip in Windows, you can use the following commands in case you have `choco` installed:

```
choco install python3
```

Or just download the installer from the [official website](https://www.python.org/downloads/).

Great, you now have python3 and pip installed. Now, we need to install the project requirements/dependencies.

### Requirements

This project depends on the following libraries:

- [Gemini GenAI](https://pypi.org/project/google-generativeai/) -> Gemini, now called Google GenerativeAI, is the core of this project. It analyzes candidates to generate worked examples for Software Engineering course classes.
- [Python dotenv Module](https://pypi.org/project/python-dotenv/) -> Used for loading environment variables from `.env` files, crucial for reading the Google GenerativeAI API Key.
- [Colorama](https://pypi.org/project/colorama/) -> For adding color and style to terminal outputs, enhancing the readability of command-line feedback.
- Standard Libraries:
    - [atexit](https://docs.python.org/3/library/atexit.html) -> For executing cleanup functions when the program terminates.
    - [os](https://docs.python.org/3/library/os.html) -> For interacting with the operating system, like running terminal commands.
    - [sys](https://docs.python.org/3/library/sys.html) -> For accessing system-specific parameters and functions, such as exiting the program.
    - [platform](https://docs.python.org/3/library/platform.html) -> For obtaining the name of the operating system.

Futhermore, this project requires a virtual environment to ensure all dependencies are installed and managed in an isolated manner. A virtual environment is a self-contained directory tree that contains a Python installation for a particular version of Python, plus a number of additional packages. Using a virtual environment helps avoid conflicts between project dependencies and system-wide Python packages. 

To set up and use a virtual environment for this project, we leverage Python's built-in `venv` module. The `makefile` included with the project automates the process of creating a virtual environment, installing the necessary dependencies, and running scripts within this environment.

Follow these steps to prepare your environment:

1. **Create and Activate the Virtual Environment:** 
   
   The project uses a `makefile` to streamline the creation and activation of a virtual environment named `venv`. This environment is where all required packages, such as `Gemini` and `Python-dotenv` will be installed.
This will also be handled by the `Makefile` during the dependencies installation process, so no command must be executed in order to create the virtual environment.

1. **Install Dependencies:** 
   
   Run the following command to set up the virtual environment and install all necessary dependencies on it:

    ```
    make dependencies
    ```

   This command performs the following actions:
  - Creates a new virtual environment by running `python3 -m venv venv`.
  - Installs the project's dependencies within the virtual environment using `pip` based on the `requirements.txt` file. The `requirements.txt` file contains a list of all required packages and their versions. This is the recommended way to manage dependencies in Python projects, as it allows for consistent and reproducible installations across different environments.

      If you need to manually activate the virtual environment, you can do so by running the following command:

      ```
      source venv/bin/activate
      ```

2. **Running Scripts:**
   
   The `makefile` also defines commands to run every script with the virtual environment's Python interpreter. For example, to run the `gemini.py` file, use:

   ```
   make gemini_script
   ```

   This ensures that the script runs using the Python interpreter and packages installed in the `venv` directory.

3. **Generate the requirements.txt file:**

   If you changed the project dependencies and want to update the `requirements.txt` file, you can run the following command:

   ```
   make generate_requirements
   ```

   This command will generate the `requirements.txt` file in the root of the tool directory (`Gemini/`), which will contain all the dependencies used in the virtual environment of the project.

### Cleaning Up

To clean your project directory from the virtual environment and Python cache files, use the `clean` rule defined in the `makefile`:

```
make clean
```

This command removes the `venv` directory and deletes any cached Python files in the project directory, helping maintain a clean workspace.

By following these instructions, you'll ensure that all project dependencies are correctly managed and isolated, leading to a more stable and consistent development environment.
	
## How to use

In order to use the makefile rules, you must be in the `Gemini/` directory.

### Gemini Script

This script is used to interact with the Google Gemini API given a input specified in the `context_message` variable and the result will be written in the `Gemini/Outputs/` directory. 

#### Configuration

In order to run this code as you want, you must modify the following constants:

1. `VERBOSE` If you want to see the progress bar and the print statements, you must set the `VERBOSE` constant to `True`. If not, then a more clean output will be shown, with only the progress bar of the script execution, which is the default value of the `VERBOSE` constant.
2. `context_message` This variable is the message that will be sent to the Gemini API. You can modify it as you want, but it must be a string. 

#### Run

Now that you have set the constants, you can run the following command to execute the `gemini.py` file:

```
make gemini_script
```

#### Workflow

1. **Check for Whitespaces in Project Path:**
   - The script initially verifies if there are any whitespaces in the project path. If detected, it halts the process.

2. **Verify `.env` File:**
   - Calls `verify_env_file()` to ensure the existence of the `.env` file containing the required `GEMINI_API_KEY`.
   - If either the `.env` file or the key is missing, the script terminates.

3. **Configure the Generative AI Model:**
   - Invokes `configure_model()` to set up the Google Generative AI model using the API key obtained from the `.env` file.
   - This step involves configuring the model with parameters such as temperature, top_p, top_k, and max_output_tokens.

4. **Start Chat Session with Model:**
   - Prepares an initial message for the chat session, explaining the format and content of the CSV data.
   - Initiates a chat session with the AI model using `start_chat_session()` and the initial message.

5. **Send Task Messages to the Model:**
   - Dispatches the `task_message` to the model, instructing it on the required tasks. The model generates corresponding outputs.

6. **Print and Save Outputs:**
   - Utilizes `write_output_to_file()` to preserve the AI model's responses in the specified output file (`OUTPUT_FILE`).

7. **Play Sound on Completion:**
   - Upon script completion, triggers a notification sound using the `play_sound()` function, registered with `atexit`.

### Gemini File Input

This script interacts with the Google Gemini API using input specified in the `input.txt` file, with the result being saved in the `Outputs/` directory.

#### Configuration

To run this code, you must modify the following constants:

1. `VERBOSE`: Set this constant to `True` to enable detailed progress and print statements. The default value is `False`.
2. `.env` File: Ensure the `.env` file contains the `GEMINI_API_KEY` required for API access.

#### Run

Once you have configured the constants, run the following command to execute the `gemini_file_input.py` file:
   
   ```
   make gemini_file_input_script
   ```

#### Workflow

1. **Check for Whitespaces in Project Path:**
   - The script initially verifies if there are any whitespaces in the project path. If detected, it halts the process.

2. **Verify `.env` File:**
   - Calls `verify_env_file()` to ensure the existence of the `.env` file containing the required `GEMINI_API_KEY`.
   - If either the `.env` file or the key is missing, the script terminates.

3. **Create Output Directory:**
   - Uses `create_directory()` to ensure the output directory exists or creates it if it doesn't.

4. **Configure the Generative AI Model:**
   - Invokes `configure_model()` to set up the Google Generative AI model using the API key obtained from the `.env` file.
   - This step involves configuring the model with parameters such as temperature, top_p, top_k, and max_output_tokens.

5. **Read Input File:**
   - Reads the `input.txt` file from the `Inputs/` directory using `read_input_file()`.

6. **Prepare Context Message:**
   - Constructs an initial message for the chat session, integrating the content from the input file.

7. **Start Chat Session with Model:**
   - Initiates a chat session with the AI model using `start_chat_session()` and the context message.

8. **Send Task Message to the Model:**
   - Dispatches a `task_message` to the model, instructing it to analyze the provided data. The model generates corresponding outputs.

9. **Print and Save Outputs:**
   - Utilizes `write_output_to_file()` to save the AI model's responses in the specified output file (`output.txt`).

10. **Play Sound on Completion:**
    - Upon script completion, triggers a notification sound using the `play_sound()` function, registered with `atexit`.

### Gemini PDF

This script interacts with the Google Gemini API using input from the `input.txt` file located in the `Inputs/` directory. The output will be written to the `Outputs/` directory.

#### Configuration

To customize the script, modify the following constants:

1. `VERBOSE`: If set to `True`, the script will display detailed progress messages. By default, it is set to `False`, showing minimal output.
2. `.env File`: Ensure the `.env` file is present in the root directory with the `GEMINI_API_KEY` variable set to your Google Gemini API key.

#### Run

To execute the `gemini_pdf.py` script, use the following command:

```bash
make gemini_pdf_script
```

#### Workflow

1. **Play Sound on Completion:**
   - Uses `atexit.register(play_sound)` to trigger a notification sound when the script finishes.

2. **Verify `.env` File:**
   - Calls `verify_env_file()` to ensure the `.env` file and the `GEMINI_API_KEY` are present. If not, the script will terminate.

3. **Create Necessary Directories:**
   - Utilizes `create_directory()` to ensure the `Outputs/` directory exists.

4. **Configure the Generative AI Model:**
   - Uses `configure_model()` to set up the Google Generative AI model with parameters such as temperature, top_p, top_k, and max_output_tokens.

5. **Read Input File:**
   - Reads content from `input.txt` using `read_input_file()`.

6. **Start Chat Session with Model:**
   - Prepares an initial message using the input data and starts a chat session with the model via `start_chat_session()`.

7. **Send Task Messages to the Model:**
   - Dispatches a task message to the model, instructing it to analyze the provided data with `send_message()`. The model generates the corresponding output.

8. **Print and Save Outputs:**
   - Writes the model's responses to `output.txt` using `write_output_to_file()`.

## Generated Data

The outputs of the scripts are stored in the `Gemini/Outputs/` directory.

## Contributing

If you want to contribute to this project, please read the Contributing section of the [Main README](../README.md) file, as well as the [CONTRIBUTING](../CONTRIBUTING.md) file in this repository.

## License

This project is licensed under the [Apache License 2.0](../LICENSE). This license permits use, modification, distribution, and sublicense of the code for both private and commercial purposes, provided that the original copyright notice and a disclaimer of warranty are included in all copies or substantial portions of the software. It also requires a clear attribution back to the original author(s) of the repository. For more details, see the [LICENSE](../LICENSE) file in this repository.
