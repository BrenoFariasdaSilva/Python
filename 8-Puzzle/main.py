import heapq # For priority queue
from colorama import Style # For coloring the terminal

# Macros:
class backgroundColors: # Colors for the terminal
	CYAN = "\033[96m" # Cyan
	GREEN = "\033[92m" # Green
	YELLOW = "\033[93m" # Yellow
	RED = "\033[91m" # Red
	CLEAR_TERMINAL = "\033[H\033[J" # Clear the terminal

# Define the goal state and initial state as 2D lists
goal_state = [[1, 2, 3], [4, 5, 6], [7, 8, 0]] # 0 represents the empty space
initial_state = [[1, 0, 3], [4, 2, 5], [7, 8, 6]] # Initial state

# Define a class to represent the puzzle state
class PuzzleState:
	# Initialize the class
	def __init__(self, state, parent=None, move=""):
		self.state = state # Current state of the puzzle
		self.parent = parent # Parent state
		self.move = move # Move that led to the current state
		self.g = 0 # Cost from start node to current node
		self.h = self.calculate_heuristic() # Heuristic (estimated cost to goal)
		self.f = self.g + self.h # Total estimated cost
	
	# Define a function to calculate the heuristic
	def calculate_heuristic(self):
		h = 0 # Number of misplaced tiles
		for i in range(3): # For each row
			for j in range(3): # For each column
				if self.state[i][j] != 0: # If the tile is not empty
					goal_row, goal_col = divmod(self.state[i][j] - 1, 3) # Find the goal position of the tile
					h += abs(i - goal_row) + abs(j - goal_col) # Add the Manhattan distance to the heuristic
		return h # Return the heuristic

	def __lt__(self, other): 
		return self.f < other.f # Compare the f values of the states

# Define possible moves
moves = [(0, 1), (1, 0), (0, -1), (-1, 0)]
move_names = ["right", "down", "left", "up"]

# Define a function to find possible moves from a given state
# Input: state (2D list)
# Returns a list of possible moves
def find_possible_moves(state):
	empty_row, empty_col = None, None
	for i in range(3): # For each row
		for j in range(3): # For each column
			if state[i][j] == 0: # If the tile is empty
				empty_row, empty_col = i, j # Store the row and column of the empty tile
				break # Break out of the loop
	
	possible_moves = [] # List of possible moves
	for move, move_name in zip(moves, move_names): # For each move
		new_row, new_col = empty_row + move[0], empty_col + move[1] # Find the new row and column of the empty tile
		if 0 <= new_row < 3 and 0 <= new_col < 3: # If the new row and column are valid
			possible_moves.append(move_name) # Add the move to the list of possible moves
	
	return possible_moves # Return the list of possible moves

# Define a function to perform a move and generate a new state
# Input: state (2D list), move (string)
# Returns a new state (2D list)
def perform_move(state, move):
	empty_row, empty_col = None, None
	for i in range(3): # For each row
		for j in range(3): # For each column
			if state[i][j] == 0: # If the tile is empty
				empty_row, empty_col = i, j # Store the row and column of the empty tile
				break # Break out of the loop
	
	# Create a copy of the state
	new_state = [row[:] for row in state]
	if move == "right": # If the move is right
		new_state[empty_row][empty_col], new_state[empty_row][empty_col + 1] = new_state[empty_row][empty_col + 1], new_state[empty_row][empty_col]
	elif move == "down": # If the move is down
		new_state[empty_row][empty_col], new_state[empty_row + 1][empty_col] = new_state[empty_row + 1][empty_col], new_state[empty_row][empty_col]
	elif move == "left": # If the move is left
		new_state[empty_row][empty_col], new_state[empty_row][empty_col - 1] = new_state[empty_row][empty_col - 1], new_state[empty_row][empty_col]
	elif move == "up": # If the move is up
		new_state[empty_row][empty_col], new_state[empty_row - 1][empty_col] = new_state[empty_row - 1][empty_col], new_state[empty_row][empty_col]
	
	return new_state # Return the new state

# Define the A* search algorithm
# Input: initial_state (2D list)
# Returns the solution node
def solve_8_puzzle(initial_state):
	open_list = [] # Priority queue
	closed_set = set() # Set of visited states
	initial_node = PuzzleState(initial_state) # Initial state
	heapq.heappush(open_list, initial_node) # Add the initial state to the priority queue
	
	# While the priority queue is not empty
	while open_list:
		current_node = heapq.heappop(open_list) # Pop the node with the lowest f value
		if current_node.state == goal_state: # If the current state is the goal state
			return current_node # Return the current node
		
		# Print the current state
		closed_set.add(tuple(map(tuple, current_node.state)))
		
		# Print the current state
		possible_moves = find_possible_moves(current_node.state)
		for move in possible_moves: # For each possible move
			new_state = perform_move(current_node.state, move) # Generate a new state
			if tuple(map(tuple, new_state)) not in closed_set: # If the new state has not been visited
				child_node = PuzzleState(new_state, current_node, move) # Create a child node
				child_node.g = current_node.g + 1 # Update the cost from start node to current node
				child_node.f = child_node.g + child_node.h # Update the total estimated cost
				heapq.heappush(open_list, child_node) # Add the child node to the priority queue

# Function to print the solution path
# Input: solution_node (PuzzleState)
# Returns nothing
def print_solution(solution_node):
	path = [] # List of states and moves in the solution path

	# Print the solution path
	while solution_node:
		path.append((solution_node.state, solution_node.move)) # Add the state and move to the list
		solution_node = solution_node.parent # Go to the parent node
	path.reverse() # Reverse the list
	
	# Print the solution path
	for state, move in path: # For each state and move
		for row in state: # For each row
			# change the background color of the terminal
			print(f"{backgroundColors.CYAN}{' '.join(map(str, row))}{Style.RESET_ALL}")
		print(f"{backgroundColors.GREEN}Move: {move}{Style.RESET_ALL}") # Print the move
		print(f"{backgroundColors.YELLOW}------------------{Style.RESET_ALL}")

# Solve the 8-puzzle problem
solution_node = solve_8_puzzle(initial_state)

# Print the solution
if solution_node:
	print(f"{backgroundColors.GREEN}Solution found in {solution_node.g} moves!{Style.RESET_ALL}")
	print(f"{backgroundColors.GREEN}Initial state: {Style.RESET_ALL}")
	print_solution(solution_node)
else:
	print(f"{backgroundColors.RED}Solution not found!{Style.RESET_ALL}")
