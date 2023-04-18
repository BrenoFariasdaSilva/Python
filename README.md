# Python <img src="https://github.com/devicons/devicon/blob/master/icons/python/python-original.svg"  width="3%" height="3%">
This repo is made with the objective of showing the Python related codes i have written. \
Feel free to contribute and send suggestions.

## Installation:
* Python Language:

	* Manually:
		```bash
		sudo apt-get install python3 python3-venv python3-pip -y
		```

	* Using ShellScript:
		```bash
		git clone https://github.com/BrenoFariasdaSilva/Python.git
		cd Python
		chmod +x install.sh
		sudo ./install.sh
		```

## Run Python code:
* Manually:
	```bash
	python3 filename_here
	```

## Used Text Editor:
* Visual Studio Code:
	```bash
	sudo apt update -y
	sudo apt install software-properties-common apt-transport-https cd ~/Downloads
	wget -y
	cd ~/Downloads
	wget -O- https://packages.microsoft.com/keys/microsoft.asc | sudo gpg --dearmor | sudo tee /usr/share/keyrings/vscode.gpg
	echo deb [arch=amd64 signed-by=/usr/share/keyrings/vscode.gpg] https://packages.microsoft.com/repos/vscode stable main | sudo tee /etc/apt/sources.list.d/vscode.list
	sudo apt update -y
	sudo apt install code -y
	```