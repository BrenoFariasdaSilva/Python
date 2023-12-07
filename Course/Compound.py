def calculateExp(rate, period):
	if (rate >= 1):
		rate /= 100
		
	return ((1 + rate)**period)

def total (capital, rate):
	return (capital * rate)

def main():
	capital = float (input ("Digite um valor do capital: "))
	rate = float (input ("Digite um valor da taxa: "))
	period = int (input ("Digite um valor do período: "))

	for i in range (1, period):
		rate = calculateExp(rate, i)
		totalCapital = total(capital, rate)
		print ("Total Capital:R$ = %.2f" %totalCapital)

# This is the standard boilerplate that calls the main() function.
if __name__ == "__main__":
   main() # Call the main function
