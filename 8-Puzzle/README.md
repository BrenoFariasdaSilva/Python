<div align="center">

# [8-Puzzle Solver](https://github.com/BrenoFariasdaSilva/Python) <img src="https://github.com/devicons/devicon/blob/master/icons/python/python-original.svg"  width="3%" height="3%">

</div>

<div align="center">

---

This Python code is an implementation of the A* search algorithm to solve the 8-puzzle problem. The 8-puzzle is a sliding puzzle that consists of a 3x3 grid with eight numbered tiles and one empty space. The goal is to rearrange the tiles from an initial configuration to a target configuration by sliding them one at a time into the empty space.

---

</div>

## Table of Contents
- [8-Puzzle Solver ](#8-puzzle-solver-)
	- [Table of Contents](#table-of-contents)
	- [How to Run](#how-to-run)
	- [Code Structure](#code-structure)
	- [How it Works](#how-it-works)
	- [Dependencies](#dependencies)
	- [License](#license)

## How to Run

To run the 8-puzzle solver, follow these steps:

1. **Clone the Repository:**
	```bash
		git clone https://github.com/BrenoFariasdaSilva/Python
		cd Python/8-Puzzle/
	```

2. **Install Dependencies:**
You need to install the `colorama` library, which is used for terminal coloring. You can install it using pip:
	```bash
		make dependencies
	```

3. **Run the Code:**
   ```bash
		make run
	```


4. **View the Solution:**
The code will print the solution path in the terminal, along with colored formatting to visualize the steps.

## Code Structure

The code is organized as follows:

- `main.py`: This is the main Python script that contains the 8-puzzle solver implementation.
- `README.md`: This is the README file that you are currently reading.

## How it Works

The code works as follows:

1. **Import necessary libraries:**
- `heapq`: This library is used for implementing a priority queue to manage the states during the search.
- `colorama.Style`: This library is used for coloring the terminal output.

2. **Define the goal state and initial state as 2D lists:**
- `goal_state`: Represents the target configuration of the puzzle.
- `initial_state`: Represents the initial configuration of the puzzle.

3. **Define a `PuzzleState` class:**
- This class is used to represent a state of the puzzle.
- It contains the current state of the puzzle, a reference to its parent state, the move that led to the current state, the cost `g` from the start node to the current node, the heuristic `h` (estimated cost to the goal), and the total estimated cost `f = g + h`.

4. **Define possible moves:**
- `moves`: A list of tuples representing possible moves (right, down, left, up).
- `move_names`: A list of corresponding move names.

5. **Define helper functions:**
- `find_possible_moves(state)`: Finds possible moves from a given state.
- `perform_move(state, move)`: Performs a move on a state and generates a new state.

6. **Define the A* search algorithm in the `solve_8_puzzle(initial_state)` function:**
- Initialize an open list (priority queue) and a closed set to keep track of visited states.
- Create the initial node with the initial state and add it to the open list.
- While the open list is not empty:
  - Pop the node with the lowest `f` value from the open list.
  - If the current state is the goal state, return the current node.
  - Generate possible moves, create child nodes, and add them to the open list if they haven't been visited.

7. **Define a function `print_solution(solution_node)` to print the solution path:**
- Traverses from the solution node back to the initial state, collecting states and moves.
- Prints each state with colored formatting to visualize the solution steps.

8. **Solve the 8-puzzle problem:**
- Call the `solve_8_puzzle(initial_state)` function to find the solution.
- If a solution is found, print the solution path and the number of moves.
- If no solution is found, indicate that the solution is not possible.

## Dependencies

- [colorama](https://pypi.org/project/colorama/): A Python library used for terminal text coloring.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

