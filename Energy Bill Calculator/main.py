"""
================================================================================
Copel Bill Estimator
================================================================================
Author      : Breno Farias da Silva
Created     : 2025-10-10
Description :
   Estimate the Copel (Companhia Paranaense de Energia) electricity bill amount
   based on the previous and current meter readings (in kWh). This script uses
   reference tariff and tax data extracted from an actual Copel bill to provide
   an accurate projection of the expected invoice total.

   Key features include:
      - Automatic computation of energy consumption (delta between readings)
      - Calculation of each billing component (energy, system use, flags, etc.)
      - Application of relevant taxes (ICMS, COFINS, PIS)
      - Inclusion of fixed items (Itaipu bonus and public lighting)
      - Formatted output summarizing all calculated components

Usage:
   1. Adjust readings inside the `main()` function or modify input dynamically.
   2. Run the script via terminal:
         $ make   or   $ python3 main.py
   3. The script prints a detailed summary of the estimated bill.

Outputs:
   - Console output displaying itemized billing information
   - Estimated total bill amount including all taxes

TODOs:
   - Implement CLI argument parsing for dynamic input
   - Add support for different tariff flags (green, yellow, red P1/P2)
   - Include export to CSV or JSON file for billing history
   - Add unit tests and error handling for invalid inputs

Dependencies:
   - Python >= 3.8
   - colorama (for colored terminal output)

Assumptions & Notes:
   - Tariff and tax rates are based on a real Copel bill from 2025
   - Calculations assume residential category and Bandeira Vermelha (P1/P2)
   - Lighting and Itaipu bonus values are treated as fixed
   - Output is purely informational and may differ slightly from the official bill
"""

import atexit  # For playing a sound when the program finishes
import os  # For running a command in the terminal
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

# Functions Definitions:


def obter_tarifas() -> dict:
    """
    Returns all tariff values used in the Copel electricity bill.

    :param: None
    :return: Dictionary containing energy, system usage, and flag rates in R$/kWh
    """

    return {
        "energia": 0.364272,
        "uso_sistema": 0.484460,
        "bandeira_vermelha": 0.058825,
        "bandeira_vermelha_p2": 0.103756,
    }


def obter_aliquotas() -> dict:
    """
    Returns the tax rates (aliquotas) applied to the bill.

    :param: None
    :return: Dictionary containing ICMS, COFINS, and PIS tax rates
    """

    return {
        "icms": 0.19,
        "cofins": 0.053936,
        "pis": 0.011694,
    }


def obter_taxas_fixas() -> dict:
    """
    Returns fixed charges and discounts applied to the bill.

    :param: None
    :return: Dictionary containing fixed bonus and public lighting fee (in R$)
    """

    return {
        "bonus_itaipu": -21.65,
        "iluminacao_publica": 37.54,
    }


def calcular_consumo(leitura_anterior: float, leitura_atual: float) -> float:
    """
    Calculates total kWh consumption.

    :param leitura_anterior: Previous meter reading (kWh)
    :param leitura_atual: Current meter reading (kWh)
    :return: Consumption in kWh
    """

    return leitura_atual - leitura_anterior


def calcular_itens_variaveis(consumo_kwh: float, tarifas: dict, taxas_fixas: dict) -> dict:
    """
    Calculates all variable cost components of the electricity bill.

    :param consumo_kwh: Energy consumption in kWh
    :param tarifas: Dictionary containing tariff values in R$/kWh
    :param taxas_fixas: Dictionary containing fixed values (bonus, public lighting)
    :return: Dictionary containing each itemized component and the subtotal
    """

    energia_consumo = consumo_kwh * tarifas["energia"]
    uso_sistema = consumo_kwh * tarifas["uso_sistema"]

    # Proportion of Red Flag levels (based on reference bill)
    perc_bv = 169.15 / 213
    perc_bv_p2 = 43.85 / 213

    energia_bv = consumo_kwh * perc_bv * tarifas["bandeira_vermelha"]
    energia_bv_p2 = consumo_kwh * perc_bv_p2 * tarifas["bandeira_vermelha_p2"]

    subtotal = (
        energia_consumo
        + uso_sistema
        + energia_bv
        + energia_bv_p2
        + taxas_fixas["bonus_itaipu"]
        + taxas_fixas["iluminacao_publica"]
    )

    return {
        "energia_consumo": energia_consumo,
        "uso_sistema": uso_sistema,
        "energia_bv": energia_bv,
        "energia_bv_p2": energia_bv_p2,
        "subtotal": subtotal,
    }


def calcular_tributos(subtotal: float, taxas_fixas: dict, impostos: dict) -> dict:
    """
    Calculates all applicable taxes for the electricity bill.

    :param subtotal: Total amount before taxes (R$)
    :param taxas_fixas: Dictionary containing fixed values (bonus, public lighting)
    :param impostos: Dictionary containing ICMS, COFINS, and PIS tax rates
    :return: Dictionary containing calculated tax amounts for ICMS, COFINS, and PIS (in R$)
    """

    base = subtotal - taxas_fixas["iluminacao_publica"]

    icms_valor = base * impostos["icms"]
    cofins_valor = base * impostos["cofins"]
    pis_valor = base * impostos["pis"]

    return {"icms": icms_valor, "cofins": cofins_valor, "pis": pis_valor}


def calcular_fatura_copel(leitura_anterior: float, leitura_atual: float) -> None:
    """
    Calculates and prints the estimated Copel electricity bill based on meter readings.

    :param leitura_anterior: Previous meter reading (kWh)
    :param leitura_atual: Current meter reading (kWh)
    :return: leitura_anterior, leitura_atual, consumo_kwh, itens_variaveis, tributos, total_fatura
    """

    tarifas = obter_tarifas()  # Get tariff values
    impostos = obter_aliquotas()  # Get tax rates
    taxas_fixas = obter_taxas_fixas()  # Get fixed charges

    consumo_kwh = calcular_consumo(leitura_anterior, leitura_atual)  # Calculate consumption
    itens_variaveis = calcular_itens_variaveis(consumo_kwh, tarifas, taxas_fixas)  # Calculate variable items
    tributos = calcular_tributos(itens_variaveis["subtotal"], taxas_fixas, impostos)  # Calculate taxes
    total_fatura = itens_variaveis["subtotal"] + sum(tributos.values())  # Calculate total bill

    return leitura_anterior, leitura_atual, consumo_kwh, itens_variaveis, tributos, total_fatura


def exibir_resultados(
    leitura_anterior: float, leitura_atual: float, consumo_kwh: float, itens: dict, tributos: dict, total: float
) -> None:
    """
    Displays all calculated results in a formatted, human-readable structure.

    :param leitura_anterior: Previous meter reading (kWh)
    :param leitura_atual: Current meter reading (kWh)
    :param consumo_kwh: Total energy consumption (kWh)
    :param itens: Dictionary containing detailed variable items and subtotal
    :param tributos: Dictionary containing calculated taxes (ICMS, COFINS, PIS)
    :param total: Final total amount of the estimated bill (R$)
    :return: None
    """

    print(f"{BackgroundColors.GREEN}========= ESTIMATIVA DE FATURA COPEL ========={Style.RESET_ALL}")
    print(f"{BackgroundColors.GREEN}--Leituras:{Style.RESET_ALL}")
    print(f"{BackgroundColors.GREEN}Leitura anterior: {leitura_anterior:>20}{Style.RESET_ALL}")
    print(f"{BackgroundColors.GREEN}Leitura atual:    {leitura_atual:>20}{Style.RESET_ALL}")
    print(f"{BackgroundColors.CYAN}Consumo:          {consumo_kwh:>20.2f} kWh\n{Style.RESET_ALL}")

    print(f"{BackgroundColors.GREEN}--Itens:{Style.RESET_ALL}")
    print(
        f"- {BackgroundColors.GREEN}Energia Elétrica Consumo:{Style.RESET_ALL}     {BackgroundColors.CYAN}R$ {itens['energia_consumo']:.2f}{Style.RESET_ALL}"
    )
    print(
        f"- {BackgroundColors.GREEN}Uso do Sistema de Distrib.:{Style.RESET_ALL}   {BackgroundColors.CYAN}R$ {itens['uso_sistema']:.2f}{Style.RESET_ALL}"
    )
    print(
        f"- {BackgroundColors.RED}Bandeira Vermelha (P1):{Style.RESET_ALL}       {BackgroundColors.CYAN}R$ {itens['energia_bv']:.2f}{Style.RESET_ALL}"
    )
    print(
        f"- {BackgroundColors.RED}Bandeira Vermelha (P2):{Style.RESET_ALL}       {BackgroundColors.CYAN}R$ {itens['energia_bv_p2']:.2f}{Style.RESET_ALL}"
    )
    print(
        f"- {BackgroundColors.YELLOW}Bônus Itaipu:{Style.RESET_ALL}                 {BackgroundColors.CYAN}R$ {-21.65:.2f}{Style.RESET_ALL}"
    )
    print(
        f"- {BackgroundColors.YELLOW}Iluminação Pública:{Style.RESET_ALL}           {BackgroundColors.CYAN}R$ {37.54:.2f}{Style.RESET_ALL}\n"
    )

    print(f"{BackgroundColors.GREEN}--Tributos:{Style.RESET_ALL}")
    print(
        f"- {BackgroundColors.RED}ICMS (19.00%):{Style.RESET_ALL}                {BackgroundColors.CYAN}R$ {tributos['icms']:.2f}{Style.RESET_ALL}"
    )
    print(
        f"- {BackgroundColors.RED}COFINS (5.3936%):{Style.RESET_ALL}             {BackgroundColors.CYAN}R$ {tributos['cofins']:.2f}{Style.RESET_ALL}"
    )
    print(
        f"- {BackgroundColors.RED}PIS (1.1694%):{Style.RESET_ALL}                {BackgroundColors.CYAN}R$ {tributos['pis']:.2f}{Style.RESET_ALL}\n"
    )

    print(
        f"{BackgroundColors.BOLD}{BackgroundColors.GREEN}TOTAL ESTIMADO DA FATURA:       {BackgroundColors.CYAN}R$ {total:.2f}{Style.RESET_ALL}"
    )
    print(f"{BackgroundColors.GREEN}============================================={Style.RESET_ALL}")


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

    :param: None
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

    :param: None
    :return: None
    """

    print(
        f"{BackgroundColors.CLEAR_TERMINAL}{BackgroundColors.BOLD}{BackgroundColors.GREEN}Welcome to the {BackgroundColors.CYAN}Copel Bill Estimator{Style.RESET_ALL}",
        end="\n\n",
    )  # Output the Welcome message

    leitura_anterior, leitura_atual, consumo_kwh, itens_variaveis, tributos, total_fatura = calcular_fatura_copel(
        leitura_anterior=13726, leitura_atual=13706
    )  # Call the function to calculate the Copel bill with example readings
    exibir_resultados(
        leitura_anterior, leitura_atual, consumo_kwh, itens_variaveis, tributos, total_fatura
    )  # Display the results

    print(
        f"\n{BackgroundColors.BOLD}{BackgroundColors.GREEN}Program finished.{Style.RESET_ALL}"
    )  # Output the end of the program message

    (
        atexit.register(play_sound) if RUN_FUNCTIONS["Play Sound"] else None
    )  # Register the play_sound function to be called when the program finishes


if __name__ == "__main__":
    """
    This is the standard boilerplate that calls the main() function.

    :return: None
    """

    main()  # Call the main function
